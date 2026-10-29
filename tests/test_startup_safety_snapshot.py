"""The automatic game-day safety snapshot runs from the shared server builder,
so the desktop shell (csrn_desktop.py) gets one on every launch -- not only
RUN_CSRN_COMMAND_CENTER.bat via tools/game_day_preflight.py."""
from __future__ import annotations

import os
import sys
import types
from pathlib import Path

import pytest

import app as app_module
import csrn_desktop
from game_day_safety_service import GameDaySafetyResult, GameDaySafetyService


ROOT = Path(__file__).resolve().parents[1]


class _Clock:
    def __init__(self, value: float = 1_800_000_000.0) -> None:
        self.value = value

    def __call__(self) -> float:
        return self.value


def _service(tmp_path: Path, clock: _Clock) -> GameDaySafetyService:
    data_dir = tmp_path / "Data"
    (data_dir / "Settings").mkdir(parents=True)
    (data_dir / "Settings" / "config.json").write_text("{}", encoding="utf-8")
    (tmp_path / "state.json").write_text('{"score": 7}', encoding="utf-8")
    (tmp_path / "security.json").write_text("{}", encoding="utf-8")
    (tmp_path / "VERSION.txt").write_text("t\n", encoding="utf-8")
    return GameDaySafetyService(
        base_dir=tmp_path,
        data_dir=data_dir,
        backup_root=tmp_path / "GameDay",
        state_file=tmp_path / "state.json",
        security_file=tmp_path / "security.json",
        config_file=data_dir / "Settings" / "config.json",
        version_file=tmp_path / "VERSION.txt",
        clock=clock,
        minimum_free_bytes=0,
    )


def _startup_ids(service: GameDaySafetyService) -> list[str]:
    return [
        item["snapshot_id"]
        for item in service.list_snapshots().data["snapshots"]
        if item["kind"] == "startup"
    ]


@pytest.fixture
def isolated_outcome(monkeypatch):
    monkeypatch.setattr(app_module, "STARTUP_SAFETY_SNAPSHOT", None)


# -- test isolation ----------------------------------------------------------


def test_tests_never_point_at_the_real_localappdata_gameday_folder() -> None:
    backup_root = Path(app_module.GAME_DAY_BACKUP_DIR).resolve()
    assert backup_root == Path(os.environ["CSRN_GAME_DAY_BACKUP_ROOT"]).resolve()
    local = os.environ.get("LOCALAPPDATA", "").strip()
    if local:
        real = (Path(local) / "PossumFrog").resolve()
        assert real not in (backup_root, *backup_root.parents)


# -- run_startup_safety_snapshot ----------------------------------------------


def test_startup_snapshot_creates_then_reuses_within_12_hours(
    monkeypatch, tmp_path, isolated_outcome
) -> None:
    clock = _Clock()
    service = _service(tmp_path, clock)
    monkeypatch.setattr(app_module, "get_game_day_safety_service", lambda: service)

    first = app_module.run_startup_safety_snapshot()
    assert first["ok"] is True
    assert first["code"] == "SNAPSHOT_CREATED"
    assert _startup_ids(service) == [first["snapshot_id"]]
    assert app_module.STARTUP_SAFETY_SNAPSHOT == first

    clock.value += 11 * 60 * 60  # relaunch the same evening
    second = app_module.run_startup_safety_snapshot()
    assert second["ok"] is True
    assert second["code"] == "SNAPSHOT_CURRENT"
    assert second["snapshot_id"] == first["snapshot_id"]
    assert _startup_ids(service) == [first["snapshot_id"]]

    clock.value += 2 * 60 * 60  # now 13 hours after the first one
    third = app_module.run_startup_safety_snapshot()
    assert third["code"] == "SNAPSHOT_CREATED"
    assert third["snapshot_id"] != first["snapshot_id"]
    assert len(_startup_ids(service)) == 2


def test_startup_snapshot_preflight_failure_warns_and_does_not_raise(
    monkeypatch, tmp_path, capsys, isolated_outcome
) -> None:
    service = _service(tmp_path, _Clock())
    (tmp_path / "state.json").write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(app_module, "get_game_day_safety_service", lambda: service)

    outcome = app_module.run_startup_safety_snapshot()

    assert outcome["ok"] is False
    assert outcome["code"] == "PREFLIGHT_FAILED"
    assert any(item.startswith("Live state:") for item in outcome["failed_checks"])
    assert "FAILED" in outcome["message"]
    assert "Live state" in outcome["message"]
    assert "WITHOUT a fresh rollback point" in outcome["message"]
    assert _startup_ids(service) == []
    assert app_module.STARTUP_SAFETY_SNAPSHOT == outcome
    printed = capsys.readouterr().out
    assert "[WARN] Game-day safety snapshot FAILED (PREFLIGHT_FAILED)" in printed


def test_startup_snapshot_unexpected_error_is_contained(
    monkeypatch, isolated_outcome
) -> None:
    class _Broken:
        def ensure_startup_snapshot(self):
            raise PermissionError("GameDay folder is locked")

    monkeypatch.setattr(app_module, "get_game_day_safety_service", lambda: _Broken())

    outcome = app_module.run_startup_safety_snapshot()

    assert outcome["ok"] is False
    assert outcome["code"] == "SNAPSHOT_FAILED"
    assert "GameDay folder is locked" in outcome["message"]


# -- build_command_center_server ----------------------------------------------


def _stub_server_build(monkeypatch, events: list[str]):
    import waitress

    monkeypatch.setattr(app_module, "ensure_data_architecture", lambda: events.append("data"))
    monkeypatch.setattr(app_module, "load_config", lambda: events.append("config") or {})
    monkeypatch.setattr(app_module, "start_isolated_media_server", lambda *a, **k: 5051)
    sentinel = object()
    monkeypatch.setattr(
        waitress, "create_server", lambda *a, **k: events.append("server") or sentinel
    )
    return sentinel


def test_server_builder_takes_the_snapshot_before_serving(monkeypatch, isolated_outcome) -> None:
    events: list[str] = []
    sentinel = _stub_server_build(monkeypatch, events)
    monkeypatch.setattr(
        app_module,
        "run_startup_safety_snapshot",
        lambda: events.append("snapshot") or {"ok": True},
    )

    assert app_module.build_command_center_server() is sentinel
    assert events == ["data", "config", "snapshot", "server"]


def test_server_builder_still_starts_when_the_snapshot_fails(
    monkeypatch, isolated_outcome
) -> None:
    events: list[str] = []
    sentinel = _stub_server_build(monkeypatch, events)

    class _Failing:
        def ensure_startup_snapshot(self):
            return GameDaySafetyResult("SNAPSHOT_FAILED", {"message": "disk full"})

    monkeypatch.setattr(app_module, "get_game_day_safety_service", lambda: _Failing())

    assert app_module.build_command_center_server() is sentinel
    assert app_module.STARTUP_SAFETY_SNAPSHOT["ok"] is False
    assert "disk full" in app_module.STARTUP_SAFETY_SNAPSHOT["message"]


def test_server_builder_writes_a_real_snapshot_into_the_isolated_root(
    monkeypatch, tmp_path, isolated_outcome
) -> None:
    events: list[str] = []
    _stub_server_build(monkeypatch, events)
    service = _service(tmp_path, _Clock())
    monkeypatch.setattr(app_module, "get_game_day_safety_service", lambda: service)

    app_module.build_command_center_server()

    ids = _startup_ids(service)
    assert len(ids) == 1
    assert app_module.STARTUP_SAFETY_SNAPSHOT["snapshot_id"] == ids[0]
    assert (tmp_path / "GameDay" / ids[0] / "payload" / "state.json").is_file()


# -- desktop shell ------------------------------------------------------------


class _FakeServer:
    def run(self) -> None:
        pass

    def close(self) -> None:
        pass


def _run_shell(monkeypatch, outcome: dict | None) -> tuple[list[str], list[tuple[str, str]]]:
    events: list[str] = []
    warnings: list[tuple[str, str]] = []
    fake_app = types.SimpleNamespace(
        build_command_center_server=lambda: events.append("build") or _FakeServer(),
        command_center_clean_shutdown=lambda: events.append("clean"),
        STARTUP_SAFETY_SNAPSHOT=outcome,
    )
    fake_webview = types.SimpleNamespace(
        create_window=lambda *a, **k: events.append("window"),
        start=lambda **k: events.append("loop"),
        settings={},
        screens=[],
    )
    monkeypatch.setattr(csrn_desktop, "current_state", lambda: "DOWN")
    monkeypatch.setattr(csrn_desktop, "wait_until_healthy", lambda *a, **k: True)
    monkeypatch.setattr(
        csrn_desktop,
        "_warn_operator",
        lambda title, message: (events.append("warn"), warnings.append((title, message))),
    )
    monkeypatch.setitem(sys.modules, "app", fake_app)
    monkeypatch.setitem(sys.modules, "webview", fake_webview)

    assert csrn_desktop.run(health_timeout=1) == 0
    return events, warnings


def test_desktop_shell_warns_the_operator_and_still_opens_when_snapshot_failed(
    monkeypatch,
) -> None:
    events, warnings = _run_shell(
        monkeypatch,
        {"ok": False, "code": "PREFLIGHT_FAILED", "message": "Game-day safety snapshot FAILED"},
    )

    assert events == ["build", "warn", "window", "loop", "clean"]
    assert len(warnings) == 1
    title, message = warnings[0]
    assert "FAILED" in title
    assert message == "Game-day safety snapshot FAILED"


def test_desktop_shell_is_silent_when_snapshot_succeeded(monkeypatch) -> None:
    events, warnings = _run_shell(
        monkeypatch, {"ok": True, "code": "SNAPSHOT_CREATED", "message": "created"}
    )

    assert warnings == []
    assert events == ["build", "window", "loop", "clean"]


def test_command_center_bat_still_blocks_on_a_failed_preflight() -> None:
    bat = (ROOT / "RUN_CSRN_COMMAND_CENTER.bat").read_text(encoding="utf-8")
    preflight = bat.index("tools\\game_day_preflight.py")
    app_start = bat.index('".venv\\Scripts\\python.exe" app.py')
    blocked = bat.index("Game-day preflight failed. The application was not started.")
    assert preflight < blocked < app_start
