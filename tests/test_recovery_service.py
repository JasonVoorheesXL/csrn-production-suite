from __future__ import annotations

import json
from pathlib import Path

from game_day_safety_service import GameDaySafetyService
from recovery_service import RecoveryService


class Clock:
    def __init__(self, value: int = 1_700_000_000) -> None:
        self.value = value

    def __call__(self) -> float:
        self.value += 1
        return float(self.value)


def build_services(tmp_path: Path, *, live: bool = False):
    base = tmp_path
    data = base / "Data"
    (data / "Settings").mkdir(parents=True)
    (data / "Settings" / "config.json").write_text(
        json.dumps({"value": "original"}), encoding="utf-8"
    )
    (data / "Schools").mkdir()
    (data / "Schools" / "schools.json").write_text("[]", encoding="utf-8")
    state_file = base / "state.json"
    state_file.write_text(
        json.dumps({"status": "live" if live else "planned", "clock_running": False}),
        encoding="utf-8",
    )
    security_file = base / "security.json"
    security_file.write_text(json.dumps({"secret_key": "secret"}), encoding="utf-8")
    version_file = base / "VERSION.txt"
    version_file.write_text("1.13.0-alpha.6a", encoding="utf-8")
    backup_root = data / "Backups" / "GameDay"
    recovery_root = data / "Backups" / "Recovery"
    clock = Clock()
    safety = GameDaySafetyService(
        base_dir=base,
        data_dir=data,
        backup_root=backup_root,
        state_file=state_file,
        security_file=security_file,
        config_file=data / "Settings" / "config.json",
        version_file=version_file,
        clock=clock,
        minimum_free_bytes=0,
    )

    def load_state():
        return json.loads(state_file.read_text(encoding="utf-8"))

    recovery = RecoveryService(
        safety_service=safety,
        data_dir=data,
        backup_root=backup_root,
        recovery_root=recovery_root,
        state_file=state_file,
        security_file=security_file,
        version_file=version_file,
        load_state=load_state,
        clock=clock,
    )
    return recovery, safety, data, state_file, recovery_root


def create_snapshot(safety: GameDaySafetyService) -> str:
    result = safety.create_snapshot(kind="manual", note="Recovery test")
    assert result.code == "SNAPSHOT_CREATED"
    return result.data["snapshot"]["snapshot_id"]


def test_status_starts_empty(tmp_path: Path) -> None:
    recovery, _, _, _, _ = build_services(tmp_path)
    status = recovery.status()
    assert status.code == "OK"
    assert status.data["recovery"]["active_session"] is None
    assert status.data["recovery"]["known_good_release"] is None


def test_mark_startup_creates_session_marker(tmp_path: Path) -> None:
    recovery, _, _, _, root = build_services(tmp_path)
    result = recovery.mark_startup(pid=123)
    assert result.code == "STARTUP_MARKED"
    assert result.data["session"]["pid"] == 123
    assert (root / "active_session.json").exists()


def test_second_startup_detects_unclean_shutdown(tmp_path: Path) -> None:
    recovery, _, _, _, root = build_services(tmp_path)
    recovery.mark_startup(pid=123)
    result = recovery.mark_startup(pid=456)
    assert result.code == "UNCLEAN_SHUTDOWN_DETECTED"
    assert result.data["previous_session"]["pid"] == 123
    assert (root / "last_unclean_shutdown.json").exists()


def test_clean_shutdown_removes_active_marker(tmp_path: Path) -> None:
    recovery, _, _, _, root = build_services(tmp_path)
    recovery.mark_startup(pid=123)
    result = recovery.mark_clean_shutdown()
    assert result.code == "CLEAN_SHUTDOWN_MARKED"
    assert not (root / "active_session.json").exists()


def test_clear_unclean_shutdown_removes_warning(tmp_path: Path) -> None:
    recovery, _, _, _, root = build_services(tmp_path)
    recovery.mark_startup(pid=123)
    recovery.mark_startup(pid=456)
    result = recovery.clear_unclean_shutdown()
    assert result.code == "UNCLEAN_MARKER_CLEARED"
    assert not (root / "last_unclean_shutdown.json").exists()


def test_register_known_good_rejects_invalid_commit(tmp_path: Path) -> None:
    recovery, _, _, _, _ = build_services(tmp_path)
    assert recovery.register_known_good(commit="not-a-commit").code == "INVALID_RELEASE_COMMIT"


def test_register_known_good_persists_release(tmp_path: Path) -> None:
    recovery, _, _, _, _ = build_services(tmp_path)
    result = recovery.register_known_good(commit="abcdef1234567", note="Rehearsed")
    assert result.code == "KNOWN_GOOD_REGISTERED"
    assert recovery.status().data["recovery"]["known_good_release"]["note"] == "Rehearsed"


def test_rollback_plan_requires_known_good_release(tmp_path: Path) -> None:
    recovery, _, _, _, _ = build_services(tmp_path)
    assert recovery.rollback_plan().code == "KNOWN_GOOD_NOT_SET"


def test_rollback_plan_contains_confirmation_command(tmp_path: Path) -> None:
    recovery, _, _, _, _ = build_services(tmp_path)
    recovery.register_known_good(commit="abcdef1234567")
    result = recovery.rollback_plan()
    assert result.code == "ROLLBACK_PLAN_READY"
    assert "--confirm abcdef1234567" in result.data["rollback"]["command"]


def test_restore_requires_exact_confirmation(tmp_path: Path) -> None:
    recovery, safety, _, _, _ = build_services(tmp_path)
    snapshot_id = create_snapshot(safety)
    assert recovery.restore_snapshot(snapshot_id, confirmation="wrong").code == "RESTORE_CONFIRMATION_REQUIRED"


def test_restore_is_locked_out_while_broadcast_is_live(tmp_path: Path) -> None:
    recovery, _, _, _, _ = build_services(tmp_path, live=True)
    assert recovery.restore_snapshot("snapshot", confirmation="snapshot").code == "LIVE_BROADCAST_ACTIVE"


def test_restore_reports_missing_snapshot(tmp_path: Path) -> None:
    recovery, _, _, _, _ = build_services(tmp_path)
    result = recovery.restore_snapshot("missing", confirmation="missing")
    assert result.code == "SNAPSHOT_NOT_FOUND"


def test_rehearsal_validates_snapshot_without_changing_data(tmp_path: Path) -> None:
    recovery, safety, data, _, _ = build_services(tmp_path)
    snapshot_id = create_snapshot(safety)
    path = data / "Settings" / "config.json"
    path.write_text(json.dumps({"value": "changed"}), encoding="utf-8")
    result = recovery.rehearse_restore(snapshot_id)
    assert result.code == "RECOVERY_REHEARSAL_READY"
    assert json.loads(path.read_text(encoding="utf-8"))["value"] == "changed"


def test_restore_recovers_data_and_state_but_retains_runtime_version(tmp_path: Path) -> None:
    recovery, safety, data, state_file, _ = build_services(tmp_path)
    snapshot_id = create_snapshot(safety)
    (data / "Settings" / "config.json").write_text(
        json.dumps({"value": "changed"}), encoding="utf-8"
    )
    state_file.write_text(json.dumps({"status": "planned", "changed": True}), encoding="utf-8")
    (tmp_path / "VERSION.txt").write_text("1.13.0-alpha.6b", encoding="utf-8")

    result = recovery.restore_snapshot(snapshot_id, confirmation=snapshot_id)

    assert result.code == "SNAPSHOT_RESTORED"
    restored = json.loads((data / "Settings" / "config.json").read_text(encoding="utf-8"))
    assert restored["value"] == "original"
    assert "changed" not in json.loads(state_file.read_text(encoding="utf-8"))
    assert (tmp_path / "VERSION.txt").read_text(encoding="utf-8") == "1.13.0-alpha.6b"
    assert result.data["restore"]["pre_restore_snapshot_id"]


def test_corrupt_snapshot_cannot_be_rehearsed_or_restored(tmp_path: Path) -> None:
    recovery, safety, _, _, _ = build_services(tmp_path)
    snapshot_id = create_snapshot(safety)
    payload = tmp_path / "Data" / "Backups" / "GameDay" / snapshot_id / "payload" / "state.json"
    payload.write_text("{}", encoding="utf-8")
    assert recovery.rehearse_restore(snapshot_id).code == "SNAPSHOT_CORRUPT"
    assert recovery.restore_snapshot(snapshot_id, confirmation=snapshot_id).code == "SNAPSHOT_CORRUPT"




# --- Round 19: trimmed snapshots + relocated backup_root ---


def _relocated_services(tmp_path: Path):
    """Services with backup_root OUTSIDE data_dir (mirrors the Round 19 move
    to %LOCALAPPDATA%\...\GameDay) and a data_dir that carries media."""
    data = tmp_path / "proj" / "Data"
    (data / "Settings").mkdir(parents=True)
    (data / "Settings" / "config.json").write_text(json.dumps({"v": "orig"}), encoding="utf-8")
    (data / "Schools").mkdir()
    (data / "Schools" / "schools.json").write_text(json.dumps([{"id": "a"}]), encoding="utf-8")
    (data / "Rosters").mkdir()
    (data / "Rosters" / "rosters.json").write_text(json.dumps({"players": 1}), encoding="utf-8")
    (data / "Rosters" / "Headshots").mkdir()
    (data / "Rosters" / "Headshots" / "p1.png").write_bytes(b"PNGDATA-1")
    (data / "Assets").mkdir()
    (data / "Assets" / "clip.mp4").write_bytes(b"VIDEO" * 100)
    (data / "Captions").mkdir()
    (data / "Captions" / "caption_state.json").write_text(json.dumps({"live": True}), encoding="utf-8")
    state_file = tmp_path / "proj" / "state.json"
    state_file.write_text(json.dumps({"status": "planned"}), encoding="utf-8")
    security_file = tmp_path / "proj" / "security.json"
    security_file.write_text(json.dumps({"secret_key": "s"}), encoding="utf-8")
    version_file = tmp_path / "proj" / "VERSION.txt"
    version_file.write_text("1.13.0-test", encoding="utf-8")

    backup_root = tmp_path / "LOCALAPPDATA" / "PossumFrog" / "CSRN Production Suite" / "GameDay"
    recovery_root = tmp_path / "LOCALAPPDATA" / "PossumFrog" / "CSRN Production Suite" / "GameDay" / "Recovery"
    clock = Clock()
    safety = GameDaySafetyService(
        base_dir=tmp_path / "proj", data_dir=data, backup_root=backup_root,
        state_file=state_file, security_file=security_file,
        config_file=data / "Settings" / "config.json", version_file=version_file,
        clock=clock, minimum_free_bytes=0,
    )
    recovery = RecoveryService(
        safety_service=safety, data_dir=data, backup_root=backup_root,
        recovery_root=recovery_root, state_file=state_file, security_file=security_file,
        version_file=version_file, load_state=lambda: json.loads(state_file.read_text()),
        clock=clock,
    )
    return recovery, safety, data, state_file


def test_snapshot_is_trimmed_of_media(tmp_path: Path) -> None:
    _, safety, _, _ = _relocated_services(tmp_path)
    result = safety.create_snapshot(kind="manual")
    assert result.code == "SNAPSHOT_CREATED"
    payload = Path(result.data["path"]) / "payload" / "Data"
    # game state IS captured
    assert (payload / "Schools" / "schools.json").exists()
    assert (payload / "Rosters" / "rosters.json").exists()
    # re-derivable media is NOT
    assert not (payload / "Rosters" / "Headshots").exists()
    assert not (payload / "Assets").exists()
    assert not (payload / "Captions").exists()


def test_restore_from_relocated_root_rolls_back_state_and_preserves_media(tmp_path: Path) -> None:
    recovery, safety, data, state_file = _relocated_services(tmp_path)
    snap = safety.create_snapshot(kind="manual")
    snapshot_id = snap.data["snapshot"]["snapshot_id"]

    # drift the live tree AFTER the snapshot
    (data / "Schools" / "schools.json").write_text(json.dumps([{"id": "b"}]), encoding="utf-8")
    (data / "Rosters" / "rosters.json").write_text(json.dumps({"players": 99}), encoding="utf-8")
    (data / "Rosters" / "Headshots" / "p2.png").write_bytes(b"PNGDATA-2")  # new headshot
    (data / "Assets" / "clip.mp4").write_bytes(b"EDITED-VIDEO")
    (data / "Captions" / "caption_state.json").write_text(json.dumps({"live": False}), encoding="utf-8")
    state_file.write_text(json.dumps({"status": "planned", "changed": True}), encoding="utf-8")

    result = recovery.restore_snapshot(snapshot_id, confirmation=snapshot_id)
    assert result.code == "SNAPSHOT_RESTORED", result.data

    # game state rolled back
    assert json.loads((data / "Schools" / "schools.json").read_text()) == [{"id": "a"}]
    assert json.loads((data / "Rosters" / "rosters.json").read_text()) == {"players": 1}
    assert "changed" not in json.loads(state_file.read_text())
    # media preserved as it was at restore time (NOT wiped, NOT rolled back)
    assert (data / "Rosters" / "Headshots" / "p1.png").read_bytes() == b"PNGDATA-1"
    assert (data / "Rosters" / "Headshots" / "p2.png").read_bytes() == b"PNGDATA-2"
    assert (data / "Assets" / "clip.mp4").read_bytes() == b"EDITED-VIDEO"
    assert json.loads((data / "Captions" / "caption_state.json").read_text()) == {"live": False}
    # no holding dir left behind
    assert not (data / ".restore-preserve").exists()
