from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tools.game_day_preflight import main


@dataclass(frozen=True)
class StubResult:
    code: str
    data: dict[str, Any] = field(default_factory=dict)


class StubService:
    def __init__(self, result: StubResult) -> None:
        self.result = result
        self.calls = 0

    def ensure_startup_snapshot(self) -> StubResult:
        self.calls += 1
        return self.result


def preflight_payload(*, ready: bool = True) -> dict[str, Any]:
    return {
        "preflight": {
            "ready": ready,
            "checks": [
                {
                    "label": "Data storage",
                    "ok": ready,
                    "required": True,
                    "note": "Writable" if ready else "Unavailable",
                },
                {
                    "label": "Recent snapshot",
                    "ok": False,
                    "required": False,
                    "note": "No recent snapshot.",
                },
            ],
        }
    }


def test_preflight_tool_accepts_current_snapshot(capsys) -> None:
    service = StubService(
        StubResult(
            "SNAPSHOT_CURRENT",
            {
                **preflight_payload(),
                "snapshot": {"snapshot_id": "current-snapshot"},
            },
        )
    )
    assert main(service) == 0
    output = capsys.readouterr().out
    assert "[PASS] Data storage" in output
    assert "[WARN] Recent snapshot" in output
    assert "current-snapshot" in output
    assert service.calls == 1


def test_preflight_tool_reports_new_snapshot(capsys) -> None:
    service = StubService(
        StubResult(
            "SNAPSHOT_CREATED",
            {
                **preflight_payload(),
                "snapshot": {"snapshot_id": "new-snapshot"},
            },
        )
    )
    assert main(service) == 0
    assert "snapshot created: new-snapshot" in capsys.readouterr().out


def test_preflight_tool_blocks_failed_preflight(capsys) -> None:
    service = StubService(
        StubResult("PREFLIGHT_FAILED", preflight_payload(ready=False))
    )
    assert main(service) == 1
    output = capsys.readouterr().out
    assert "[FAIL] Data storage" in output
    assert "startup blocked: PREFLIGHT_FAILED" in output


def test_preflight_tool_blocks_snapshot_failure(capsys) -> None:
    service = StubService(
        StubResult(
            "SNAPSHOT_FAILED",
            {**preflight_payload(), "message": "Disk full"},
        )
    )
    assert main(service) == 1
    output = capsys.readouterr().out
    assert "SNAPSHOT_FAILED" in output
    assert "Disk full" in output


def test_direct_script_adds_repository_root_to_import_path(
    tmp_path: Path,
) -> None:
    root = tmp_path / "suite"
    tools_dir = root / "tools"
    tools_dir.mkdir(parents=True)
    source = Path(__file__).resolve().parents[1] / "tools" / "game_day_preflight.py"
    shutil.copy2(source, tools_dir / "game_day_preflight.py")
    (root / "app.py").write_text(
        """
from dataclasses import dataclass

@dataclass(frozen=True)
class Result:
    code: str = "SNAPSHOT_CURRENT"
    data: dict = None

class Service:
    def ensure_startup_snapshot(self):
        return Result(data={
            "preflight": {"checks": []},
            "snapshot": {"snapshot_id": "direct-script"},
        })

def get_game_day_safety_service():
    return Service()
""".strip()
        + "\n",
        encoding="utf-8",
    )

    completed = subprocess.run(
        [sys.executable, str(tools_dir / "game_day_preflight.py")],
        cwd=tmp_path,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "snapshot is current: direct-script" in completed.stdout
