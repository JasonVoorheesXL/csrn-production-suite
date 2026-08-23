from __future__ import annotations

import json
from pathlib import Path

from game_day_safety_service import GameDaySafetyService


class Clock:
    def __init__(self, value: float = 1_800_000_000.0) -> None:
        self.value = value

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


def build_service(
    tmp_path: Path,
    *,
    clock: Clock | None = None,
    retention: int = 10,
    publish_attempts: int = 4,
    publish_retry_delay: float = 0.0,
) -> tuple[GameDaySafetyService, Clock]:
    clock = clock or Clock()
    data_dir = tmp_path / "Data"
    (data_dir / "Settings").mkdir(parents=True)
    (data_dir / "Schools").mkdir(parents=True)
    (data_dir / "Settings" / "config.json").write_text(
        json.dumps({"application": {"version": "test"}}),
        encoding="utf-8",
    )
    (data_dir / "Schools" / "schools.json").write_text(
        json.dumps([{"id": "caledonia"}]),
        encoding="utf-8",
    )
    (tmp_path / "state.json").write_text(
        json.dumps({"status": "planned"}),
        encoding="utf-8",
    )
    (tmp_path / "security.json").write_text(
        json.dumps({"secret_key": "test"}),
        encoding="utf-8",
    )
    (tmp_path / "VERSION.txt").write_text("1.13.0-test\n", encoding="utf-8")
    service = GameDaySafetyService(
        base_dir=tmp_path,
        data_dir=data_dir,
        backup_root=data_dir / "Backups" / "GameDay",
        state_file=tmp_path / "state.json",
        security_file=tmp_path / "security.json",
        config_file=data_dir / "Settings" / "config.json",
        version_file=tmp_path / "VERSION.txt",
        clock=clock,
        minimum_free_bytes=0,
        automatic_retention=retention,
        publish_attempts=publish_attempts,
        publish_retry_delay=publish_retry_delay,
    )
    return service, clock


def test_preflight_reports_required_health_and_snapshot_warning(tmp_path: Path) -> None:
    service, _ = build_service(tmp_path)
    result = service.preflight()
    assert result.code == "OK"
    payload = result.data["preflight"]
    assert payload["ready"] is True
    checks = {item["key"]: item for item in payload["checks"]}
    assert checks["state"]["ok"] is True
    assert checks["backup_writable"]["ok"] is True
    assert checks["recent_snapshot"]["ok"] is False
    assert checks["recent_snapshot"]["required"] is False


def test_preflight_fails_when_live_state_json_is_corrupt(tmp_path: Path) -> None:
    service, _ = build_service(tmp_path)
    (tmp_path / "state.json").write_text("{not-json", encoding="utf-8")
    result = service.preflight()
    assert result.code == "PREFLIGHT_FAILED"
    assert result.data["preflight"]["ready"] is False
    checks = {item["key"]: item for item in result.data["preflight"]["checks"]}
    assert checks["state"]["ok"] is False


def test_snapshot_copies_runtime_payload_and_excludes_nested_backups(
    tmp_path: Path,
) -> None:
    service, _ = build_service(tmp_path)
    old_backup = tmp_path / "Data" / "Backups" / "old" / "ignored.json"
    old_backup.parent.mkdir(parents=True)
    old_backup.write_text("{}", encoding="utf-8")

    result = service.create_snapshot(kind="manual", note="Pregame")
    assert result.code == "SNAPSHOT_CREATED"
    snapshot = result.data["snapshot"]
    root = Path(result.data["path"])
    assert snapshot["kind"] == "manual"
    assert snapshot["note"] == "Pregame"
    assert (root / "payload" / "Data" / "Schools" / "schools.json").exists()
    assert (root / "payload" / "state.json").exists()
    assert (root / "payload" / "security.json").exists()
    assert not (root / "payload" / "Data" / "Backups").exists()
    assert snapshot["file_count"] == len(snapshot["files"])
    assert snapshot["total_bytes"] > 0


def test_snapshot_publish_retries_transient_directory_replace_failure(
    tmp_path: Path,
) -> None:
    service, _ = build_service(tmp_path, publish_attempts=3)
    original = service._replace_snapshot_directory
    attempts = {"count": 0}

    def flaky_replace(temporary_path: Path, final_path: Path) -> None:
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise OSError("temporary Drive lock")
        original(temporary_path, final_path)

    service._replace_snapshot_directory = flaky_replace  # type: ignore[method-assign]

    result = service.create_snapshot(kind="manual", note="Pregame")

    assert result.code == "SNAPSHOT_CREATED"
    assert attempts["count"] == 3
    root = Path(result.data["path"])
    assert root.is_dir()
    assert not (root.parent / f".tmp-{root.name}").exists()


def test_snapshot_publish_failure_reports_attempts_and_cleans_staging(
    tmp_path: Path,
) -> None:
    service, _ = build_service(tmp_path, publish_attempts=2)

    def locked_replace(temporary_path: Path, final_path: Path) -> None:
        raise OSError(f"locked {temporary_path.name}")

    service._replace_snapshot_directory = locked_replace  # type: ignore[method-assign]

    result = service.create_snapshot(kind="manual", note="Pregame")

    assert result.code == "SNAPSHOT_FAILED"
    assert "2 attempts" in result.data["message"]
    backup_root = tmp_path / "Data" / "Backups" / "GameDay"
    assert not list(backup_root.glob(".tmp-*"))


def test_snapshot_list_is_newest_first(tmp_path: Path) -> None:
    service, clock = build_service(tmp_path)
    first = service.create_snapshot(kind="manual")
    clock.advance(2)
    second = service.create_snapshot(kind="manual")
    snapshots = service.list_snapshots().data["snapshots"]
    assert snapshots[0]["snapshot_id"] == second.data["snapshot"]["snapshot_id"]
    assert snapshots[1]["snapshot_id"] == first.data["snapshot"]["snapshot_id"]


def test_snapshot_verification_succeeds_for_unchanged_payload(tmp_path: Path) -> None:
    service, _ = build_service(tmp_path)
    created = service.create_snapshot(kind="manual")
    snapshot_id = created.data["snapshot"]["snapshot_id"]
    result = service.verify_snapshot(snapshot_id)
    assert result.code == "SNAPSHOT_VERIFIED"
    assert result.data["verification"]["verified"] is True
    assert result.data["verification"]["errors"] == []


def test_snapshot_verification_detects_modified_payload(tmp_path: Path) -> None:
    service, _ = build_service(tmp_path)
    created = service.create_snapshot(kind="manual")
    snapshot_id = created.data["snapshot"]["snapshot_id"]
    target = (
        Path(created.data["path"])
        / "payload"
        / "Data"
        / "Schools"
        / "schools.json"
    )
    target.write_text("[]", encoding="utf-8")
    result = service.verify_snapshot(snapshot_id)
    assert result.code == "SNAPSHOT_CORRUPT"
    assert result.data["verification"]["verified"] is False
    assert result.data["verification"]["errors"]


def test_snapshot_verification_rejects_invalid_identifier(tmp_path: Path) -> None:
    service, _ = build_service(tmp_path)
    assert service.verify_snapshot("../outside").code == "INVALID_SNAPSHOT_ID"
    assert service.verify_snapshot("missing").code == "SNAPSHOT_NOT_FOUND"


def test_startup_snapshot_is_reused_while_current_and_verified(
    tmp_path: Path,
) -> None:
    service, clock = build_service(tmp_path)
    first = service.ensure_startup_snapshot(max_age_seconds=3600)
    assert first.code == "SNAPSHOT_CREATED"
    clock.advance(30)
    second = service.ensure_startup_snapshot(max_age_seconds=3600)
    assert second.code == "SNAPSHOT_CURRENT"
    assert (
        second.data["snapshot"]["snapshot_id"]
        == first.data["snapshot"]["snapshot_id"]
    )


def test_startup_snapshot_is_replaced_when_current_copy_is_corrupt(
    tmp_path: Path,
) -> None:
    service, clock = build_service(tmp_path)
    first = service.ensure_startup_snapshot(max_age_seconds=3600)
    first_path = Path(first.data["path"])
    (first_path / "payload" / "state.json").write_text("{}", encoding="utf-8")
    clock.advance(1)
    second = service.ensure_startup_snapshot(max_age_seconds=3600)
    assert second.code == "SNAPSHOT_CREATED"
    assert (
        second.data["snapshot"]["snapshot_id"]
        != first.data["snapshot"]["snapshot_id"]
    )


def test_automatic_retention_does_not_delete_manual_snapshots(
    tmp_path: Path,
) -> None:
    service, clock = build_service(tmp_path, retention=2)
    manual = service.create_snapshot(kind="manual")
    for _ in range(4):
        clock.advance(1)
        service.create_snapshot(kind="startup")
    snapshots = service.list_snapshots().data["snapshots"]
    kinds = [item["kind"] for item in snapshots]
    assert kinds.count("startup") == 2
    assert any(
        item["snapshot_id"] == manual.data["snapshot"]["snapshot_id"]
        for item in snapshots
    )


