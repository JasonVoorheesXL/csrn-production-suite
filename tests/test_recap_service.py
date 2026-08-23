from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from recap_service import GroundedGameRecapService


def game_state() -> dict:
    return {
        "broadcast_id": "GAME-42",
        "home_team": "Caledonia",
        "visitor_team": "New Hope",
        "home_score": 28,
        "visitor_score": 21,
        "date": "2026-08-21",
        "venue": "Cavalier Stadium",
        "status": "completed",
        "broadcast_phase": "final",
        "halftime_score": {"home_score": 7, "visitor_score": 14},
        "events": [
            {"id": "E1", "event": "TD", "quarter": "1", "description": "Caledonia opened the scoring", "after": {"home_score": 7, "visitor_score": 0}},
            {"id": "E2", "event": "TD", "quarter": "2", "description": "New Hope tied the game", "after": {"home_score": 7, "visitor_score": 7}},
            {"id": "E3", "event": "TD", "quarter": "2", "description": "New Hope took the lead", "after": {"home_score": 7, "visitor_score": 14}},
            {"id": "E4", "event": "TD", "quarter": "3", "description": "Caledonia tied the game", "after": {"home_score": 14, "visitor_score": 14}},
            {"id": "E5", "event": "TD", "quarter": "3", "description": "Caledonia regained the lead", "after": {"home_score": 21, "visitor_score": 14}},
            {"id": "E6", "event": "TD", "quarter": "4", "description": "New Hope tied it again", "after": {"home_score": 21, "visitor_score": 21}},
            {"id": "E7", "event": "TD", "quarter": "4", "description": "Caledonia scored the winning touchdown", "after": {"home_score": 28, "visitor_score": 21}},
            {"id": "E8", "event": "TURNOVER", "quarter": "4", "description": "Caledonia recovered a fumble"},
            {"id": "E9", "event": "WEATHER_DELAY", "description": "Play was delayed by lightning"},
            {"id": "E10", "event": "GAME_RESUMPTION", "description": "Play resumed after the delay"},
            {"id": "E11", "event": "TD", "description": "99-yard touchdown by Invented Player", "undone": True, "after": {"home_score": 35, "visitor_score": 21}},
        ],
        "plays": [
            {"play_id": "P1", "event_id": "E1", "result": "Recorded play"},
            {"play_id": "P2", "event_id": "E11", "result": "Undone play", "undone": True},
        ],
        "statistician_enabled": False,
    }


def service(tmp_path: Path, state: dict | None = None, social_callback=None):
    state = state or game_state()
    svc = GroundedGameRecapService(
        state_file=tmp_path / "recaps.json",
        load_broadcast_state=lambda: state,
        create_social_draft=social_callback,
        clock=lambda: 1_700_000_000,
    )
    return svc, state


def test_generate_uses_recorded_final_score_and_events_only(tmp_path: Path) -> None:
    svc, _ = service(tmp_path)
    result = svc.generate()
    assert result.code == "RECAP_GENERATED"
    recap = result.data["recap"]
    assert recap["headline"] == "Caledonia tops New Hope 28-21"
    assert "Caledonia scored the winning touchdown" in recap["body"]
    assert "Invented Player" not in recap["body"]
    assert "E11" not in recap["grounding"]["event_ids"]
    assert recap["grounding"]["play_ids"] == ["P1"]


def test_halftime_leader_and_lead_changes_are_grounded(tmp_path: Path) -> None:
    svc, _ = service(tmp_path)
    recap = svc.generate().data["recap"]
    assert "New Hope led 14-7 at the break." in recap["body"]
    assert recap["facts"]["lead_changes"] == 2
    assert "2 lead changes" in recap["body"]


def test_turnover_and_weather_sections_use_recorded_descriptions(tmp_path: Path) -> None:
    svc, _ = service(tmp_path)
    recap = svc.generate().data["recap"]
    assert "Caledonia recovered a fumble" in recap["body"]
    assert "Play was delayed by lightning" in recap["body"]
    assert "Play resumed after the delay" in recap["body"]
    assert recap["facts"]["turnovers"] == 1
    assert recap["facts"]["weather_events"] == 2


def test_missing_data_is_omitted_not_invented(tmp_path: Path) -> None:
    state = game_state()
    state.pop("halftime_score")
    state["events"] = []
    state["plays"] = []
    svc, _ = service(tmp_path, state)
    recap = svc.generate().data["recap"]
    assert recap["body"] == ""
    omitted = recap["grounding"]["omitted"]
    assert "halftime score" in omitted
    assert "scoring sequence" in omitted
    assert "turnovers" in omitted
    assert "statistician-only team and player statistics" in omitted


def test_available_statistics_are_included_with_source_paths(tmp_path: Path) -> None:
    state = game_state()
    state["statistician_enabled"] = True
    state["team_stats"] = {
        "home": {"first_downs": 18, "total_yards": 355, "turnovers": 1},
        "visitor": {"first_downs": 15, "total_yards": 301, "turnovers": 2},
    }
    state["player_stats"] = {
        "rushing": {"name": "Alex Morgan", "yards": 142, "touchdowns": 2}
    }
    svc, _ = service(tmp_path, state)
    recap = svc.generate().data["recap"]
    assert "Caledonia recorded 18 first downs, 355 total yards, 1 turnover." in recap["body"]
    assert "Recorded rushing leader Alex Morgan: 142 yards, 2 touchdowns." in recap["body"]
    assert "team_stats.home.total_yards" in recap["grounding"]["stat_paths"]
    assert "player_stats.rushing.yards" in recap["grounding"]["stat_paths"]


def test_duplicate_generate_requires_regenerate_flag(tmp_path: Path) -> None:
    svc, _ = service(tmp_path)
    first = svc.generate()
    second = svc.generate()
    assert second.code == "RECAP_ALREADY_EXISTS"
    regenerated = svc.generate(regenerate=True)
    assert regenerated.code == "RECAP_GENERATED"
    assert regenerated.data["recap"]["revision"] == first.data["recap"]["revision"] + 1


def test_editing_marks_operator_fields_and_resets_approval(tmp_path: Path) -> None:
    svc, _ = service(tmp_path)
    recap = svc.generate().data["recap"]
    svc.approve(recap["id"], operator="Jason", confirmation="APPROVE GROUNDED RECAP")
    updated = svc.update(recap["id"], {"headline": "Edited headline", "body": "Edited body"})
    assert updated.code == "RECAP_UPDATED"
    assert updated.data["recap"]["status"] == "DRAFT"
    assert updated.data["recap"]["approved_at"] == 0
    assert updated.data["recap"]["grounding"]["operator_edited_fields"] == ["body", "headline"]


def test_approval_requires_exact_phrase(tmp_path: Path) -> None:
    svc, _ = service(tmp_path)
    recap_id = svc.generate().data["recap"]["id"]
    assert svc.approve(recap_id, operator="Jason", confirmation="approve").code == "RECAP_APPROVAL_CONFIRMATION_REQUIRED"
    result = svc.approve(recap_id, operator="Jason", confirmation="APPROVE GROUNDED RECAP")
    assert result.code == "RECAP_APPROVED"
    assert result.data["recap"]["approved_by"] == "Jason"


def test_source_change_marks_recap_stale_and_blocks_approval(tmp_path: Path) -> None:
    svc, state = service(tmp_path)
    recap_id = svc.generate().data["recap"]["id"]
    state["events"].append({"id": "E12", "event": "TURNOVER", "description": "Late interception"})
    status = svc.status().data["recaps"][0]
    assert status["stale"] is True
    assert svc.approve(recap_id, operator="Jason", confirmation="APPROVE GROUNDED RECAP").code == "RECAP_STALE"


def test_text_export_contains_finished_recap(tmp_path: Path) -> None:
    svc, _ = service(tmp_path)
    recap = svc.generate().data["recap"]
    result = svc.export_text(recap["id"])
    assert result.code == "OK"
    assert result.data["filename"].endswith(".txt")
    assert recap["headline"] in result.data["text"]
    assert recap["closing"] in result.data["text"]


def test_social_handoff_requires_approved_recap(tmp_path: Path) -> None:
    calls = []

    def callback(recap):
        calls.append(dict(recap))
        return SimpleNamespace(code="DRAFT_CREATED", ok=True, data={"draft": {"id": "SOC-99"}})

    svc, _ = service(tmp_path, social_callback=callback)
    recap = svc.generate().data["recap"]
    assert svc.create_social_final_draft(recap["id"]).code == "RECAP_NOT_APPROVED"
    svc.approve(recap["id"], operator="Jason", confirmation="APPROVE GROUNDED RECAP")
    result = svc.create_social_final_draft(recap["id"])
    assert result.code == "SOCIAL_DRAFT_CREATED"
    assert result.data["recap"]["social_draft_id"] == "SOC-99"
    assert calls[0]["social_summary"].startswith("FINAL:")


def test_delete_requires_exact_confirmation(tmp_path: Path) -> None:
    svc, _ = service(tmp_path)
    recap_id = svc.generate().data["recap"]["id"]
    assert svc.delete(recap_id, "delete").code == "RECAP_DELETE_CONFIRMATION_REQUIRED"
    assert svc.delete(recap_id, "DELETE GAME RECAP").code == "RECAP_DELETED"


