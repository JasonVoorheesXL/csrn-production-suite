from __future__ import annotations

from dataclasses import dataclass, field
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
