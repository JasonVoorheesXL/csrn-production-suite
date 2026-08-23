from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from tools.commissioning_report import main


@dataclass
class StubResult:
    code: str
    data: dict[str, Any] = field(default_factory=dict)


class StubService:
    def __init__(self, ready: bool) -> None:
        self.ready = ready
        self.obs_calls = 0

    def run_obs_check(self) -> StubResult:
        self.obs_calls += 1
        return StubResult(
            "OBS_CHECK_COMPLETE",
            {"obs_check": {"ready": self.ready, "observed": {"error": ""}}},
        )

    def report(self) -> StubResult:
        return StubResult(
            "COMMISSIONING_READY" if self.ready else "COMMISSIONING_INCOMPLETE",
            {
                "report": {
                    "ready": self.ready,
                    "passed_required": 1 if self.ready else 0,
                    "required_total": 1,
                    "checks": [
                        {
                            "key": "audio.no_clipping",
                            "label": "No clipping",
                            "passed": self.ready,
                            "required": True,
                            "note": "",
                        },
                        {
                            "key": "network.backup",
                            "label": "Backup internet",
                            "passed": False,
                            "required": False,
                            "note": "Not connected",
                        },
                    ],
                }
            },
        )


def test_ready_report_returns_zero(capsys) -> None:
    service = StubService(True)
    assert main([], service) == 0
    output = capsys.readouterr().out
    assert "[PASS] No clipping" in output
    assert "Commissioning ready." in output


def test_incomplete_report_returns_one(capsys) -> None:
    service = StubService(False)
    assert main([], service) == 1
    output = capsys.readouterr().out
    assert "[FAIL] No clipping" in output
    assert "[WARN] Backup internet" in output
    assert "Commissioning incomplete." in output


def test_obs_test_refreshes_contract(capsys) -> None:
    service = StubService(True)
    assert main(["--obs-test"], service) == 0
    assert service.obs_calls == 1
    assert "OBS contract check: ready" in capsys.readouterr().out


