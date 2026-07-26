from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import tools.game_day_recovery as recovery_tool


@dataclass(frozen=True)
class StubResult:
    code: str
    data: dict[str, Any] = field(default_factory=dict)


class StubService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []

    def mark_startup(self, *, pid: int):
        self.calls.append(("startup", pid))
        return StubResult("STARTUP_MARKED", {"session": {"pid": pid}})

    def mark_clean_shutdown(self):
        self.calls.append(("shutdown", None))
        return StubResult("CLEAN_SHUTDOWN_MARKED")

    def status(self):
        self.calls.append(("status", None))
        return StubResult("OK", {"recovery": {}})

    def clear_unclean_shutdown(self):
        self.calls.append(("clear", None))
        return StubResult("UNCLEAN_MARKER_CLEARED")

    def rollback_plan(self):
        self.calls.append(("plan", None))
        return StubResult("ROLLBACK_PLAN_READY", {"rollback": {}})

    def register_known_good(self, *, commit: str, note: str):
        self.calls.append(("known_good", (commit, note)))
        return StubResult("KNOWN_GOOD_REGISTERED")

    def rehearse_restore(self, snapshot_id: str):
        self.calls.append(("rehearse", snapshot_id))
        return StubResult("RECOVERY_REHEARSAL_READY")

    def restore_snapshot(self, snapshot_id: str, *, confirmation: str, note: str):
        self.calls.append(("restore", (snapshot_id, confirmation, note)))
        return StubResult("SNAPSHOT_RESTORED")


def test_startup_command_marks_session(monkeypatch, capsys) -> None:
    service = StubService()
    monkeypatch.setattr(recovery_tool, "_service", lambda: service)
    assert recovery_tool.main(["startup"]) == 0
    assert service.calls[0][0] == "startup"
    assert '"code": "STARTUP_MARKED"' in capsys.readouterr().out


def test_restore_command_passes_confirmation(monkeypatch) -> None:
    service = StubService()
    monkeypatch.setattr(recovery_tool, "_service", lambda: service)
    assert recovery_tool.main(
        ["restore", "snap-1", "--confirm", "snap-1", "--note", "Approved"]
    ) == 0
    assert service.calls[-1] == (
        "restore",
        ("snap-1", "snap-1", "Approved"),
    )


def test_failed_command_returns_nonzero(monkeypatch) -> None:
    class FailedService(StubService):
        def rollback_plan(self):
            return StubResult("KNOWN_GOOD_NOT_SET")

    monkeypatch.setattr(recovery_tool, "_service", FailedService)
    assert recovery_tool.main(["rollback-plan"]) == 1


def test_direct_script_adds_repository_root_to_import_path(tmp_path: Path) -> None:
    root = tmp_path / "suite"
    tools_dir = root / "tools"
    tools_dir.mkdir(parents=True)
    source = Path(__file__).resolve().parents[1] / "tools" / "game_day_recovery.py"
    shutil.copy2(source, tools_dir / "game_day_recovery.py")
    (root / "app.py").write_text(
        """
from dataclasses import dataclass

@dataclass(frozen=True)
class Result:
    code: str = "OK"
    data: dict = None

class Service:
    def status(self):
        return Result(data={"recovery": {"direct": True}})

def get_recovery_service():
    return Service()
""".strip()
        + "\n",
        encoding="utf-8",
    )

    completed = subprocess.run(
        [sys.executable, str(tools_dir / "game_day_recovery.py"), "status"],
        cwd=tmp_path,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert '"direct": true' in completed.stdout.lower()
