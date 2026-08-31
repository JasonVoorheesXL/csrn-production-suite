"""Round 10 Task B: the game-statistics report must never emit the
Windows-1252/UTF-8 mojibake dash.

Root cause was a corrupted em-dash literal in rules_service.py's kickoff/punt
phrasing ("... ball at RIGHT 20 <mojibake> touchback"). That literal is fixed
at the source; StatisticsService also repairs the signature on the way out so
games already recorded with the bad bytes still export clean.
"""

from __future__ import annotations

import json
from typing import Any

from statistics_service import StatisticsService

# The exact three-codepoint signature that a UTF-8 em dash (U+2014) leaves
# after a round-trip through Windows-1252: â + € + U+201D.
MOJIBAKE_EM_DASH = "â€”"
MOJIBAKE_PREFIX = "â€"


def _state_with_kick_result(result_text: str) -> dict[str, Any]:
    return {
        "broadcast_id": "FB-2026-99",
        "sport": "Football",
        "home_team": "Caledonia",
        "visitor_team": "New Hope",
        "home_score": 0,
        "visitor_score": 0,
        "events": [],
        "plays": [
            {
                "broadcast_id": "FB-2026-99",
                "play_id": "P1",
                "play_number": "1",
                "quarter": "1",
                "play_type": "kickoff",
                "offense": "visitor",
                "defense": "home",
                "kicking_team": "home",
                "result": result_text,
                "description": result_text,
                "yards": 0,
            }
        ],
    }


def _report(state: dict[str, Any]) -> dict[str, Any]:
    result = StatisticsService(now=lambda: 1_700_000_000).report(state)
    assert result.ok
    return result.data["statistics"]


def test_repair_helper_replaces_the_em_dash_signature() -> None:
    dirty = f"Kickoff by #12 landed at RIGHT 40, ball at RIGHT 20{MOJIBAKE_EM_DASH} touchback"
    fixed = StatisticsService._repair_text(dirty)
    assert MOJIBAKE_PREFIX not in fixed
    assert "—" in fixed  # a real em dash now
    assert fixed == "Kickoff by #12 landed at RIGHT 40, ball at RIGHT 20— touchback"


def test_repair_helper_leaves_clean_text_untouched() -> None:
    clean = "Kickoff by #12, ball at RIGHT 20 — touchback"
    assert StatisticsService._repair_text(clean) == clean
    assert StatisticsService._repair_text("plain ascii, no dash") == "plain ascii, no dash"
    assert StatisticsService._repair_text(None) is None


def test_report_play_register_never_contains_a_mangled_dash() -> None:
    state = _state_with_kick_result(
        f"Kickoff by #12 landed at LEFT 5{MOJIBAKE_EM_DASH} fair catch"
    )
    report = _report(state)

    play = report["play_register"][0]
    assert MOJIBAKE_PREFIX not in play["result"]
    assert MOJIBAKE_PREFIX not in play["description"]
    assert "— fair catch" in play["result"]

    # Nothing anywhere in the serialized report carries the signature.
    assert MOJIBAKE_PREFIX not in json.dumps(report, ensure_ascii=False)


def test_report_scoring_summary_dash_is_also_repaired() -> None:
    state = _state_with_kick_result("Kickoff, ball at RIGHT 20 — touchback")
    state["events"] = [
        {
            "id": "E1",
            "broadcast_id": "FB-2026-99",
            "event": "TD",
            "team": "home",
            "score_delta": 6,
            "quarter": "1",
            "description": f"#7 punt return{MOJIBAKE_EM_DASH} 80 yards, touchdown",
            "after": {"home_score": 6, "visitor_score": 0},
        }
    ]
    report = _report(state)
    summary = report["scoring_summary"][0]
    assert MOJIBAKE_PREFIX not in summary["description"]
    assert "— 80 yards" in summary["description"]
