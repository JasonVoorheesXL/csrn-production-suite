from __future__ import annotations

import copy
from contextlib import nullcontext
from typing import Any

from broadcast_lifecycle_service import BroadcastLifecycleService


def record(status: str = "planned") -> dict[str, Any]:
    return {
        "broadcast_id": "FB-2026-01",
        "status": status,
        "sport": "Football",
        "season": "2026",
        "week": "1",
        "classification": "5A",
        "home_classification": "5A",
        "home_region": "Region 1",
        "visitor_classification": "5A",
        "visitor_region": "Region 2",
        "home_pregame_record": {"wins": 3, "losses": 1, "ties": 1},
        "home_pregame_region_record": {"wins": 2, "losses": 0, "ties": 0},
        "visitor_pregame_record": {"wins": 4, "losses": 0, "ties": 0},
        "visitor_pregame_region_record": {"wins": 1, "losses": 0, "ties": 0},
        "contest_type": "official",
        "record_policy": "official",
        "region_game": True,
        "special_designations": ["homecoming", "rivalry"],
        "record_tracking": {"primary_side": "home"},
        "level": "Varsity",
        "division": "Boys",
        "home_school_id": "caledonia",
        "visitor_school_id": "new-hope",
        "home_team": "Caledonia",
        "visitor_team": "New Hope",
        "venue_id": "cavaliers-stadium",
        "venue": "Cavalier Stadium",
        "date": "2026-08-21",
        "scheduled_start": "07:00 PM",
        "visual_mode": "graphic",
        "crew": {"play_by_play": "Jason"},
        "final_home_score": 28,
        "final_visitor_score": 14,
    }


def default_state() -> dict[str, Any]:
    return {
        "broadcast_created": False,
        "broadcast_id": "",
        "status": "planned",
        "broadcast_phase": "pregame",
        "scorebug_visible": False,
        "home_score": 0,
        "visitor_score": 0,
        "history": [],
    }


def build_service(
    *,
    records: list[dict[str, Any]] | None = None,
    packages: list[dict[str, Any]] | None = None,
    state: dict[str, Any] | None = None,
    controlled_commands: bool = False,
    command_error: Exception | None = None,
):
    broadcast_rows = copy.deepcopy(records if records is not None else [record()])
    package_rows = copy.deepcopy(packages if packages is not None else [])
    current = copy.deepcopy(state if state is not None else default_state())
    saved: list[dict[str, Any]] = []
    normalized: list[dict[str, Any]] = []
    linked: list[tuple[str, str, Any]] = []
    commands: list[bool] = []
    resumed: list[str] = []

    def load_state() -> dict[str, Any]:
        return copy.deepcopy(current)

    def save_state(incoming: dict[str, Any]) -> None:
        current.clear()
        current.update(copy.deepcopy(incoming))
        saved.append(copy.deepcopy(incoming))

    def normalize_state(incoming: dict[str, Any]) -> dict[str, Any]:
        normalized.append(copy.deepcopy(incoming))
        result = default_state()
        result.update(copy.deepcopy(incoming))
        result["normalized"] = True
        return result

    def command_scorebug(visible: bool) -> dict[str, Any]:
        commands.append(visible)
        if command_error is not None:
            raise command_error
        return {"reachable": True, "visible": visible}

    service = BroadcastLifecycleService(
        load_broadcasts=lambda: copy.deepcopy(broadcast_rows),
        load_packages=lambda: copy.deepcopy(package_rows),
        load_state=load_state,
        save_state=save_state,
        normalize_state=normalize_state,
        default_state=lambda: copy.deepcopy(default_state()),
        get_school=lambda school_id: {
            "id": school_id,
            "broadcast_name": school_id.replace("-", " ").title(),
        },
        build_identity=lambda school, sport: {
            "school_id": (school or {}).get("id", ""),
            "sport": sport,
        },
        readiness=lambda: {"ready": True},
        update_linked_status=lambda bid, status, extra: linked.append(
            (bid, status, extra)
        ),
        load_config=lambda: {
            "obs": {"controlled_commands": controlled_commands}
        },
        command_scorebug_visibility=command_scorebug,
        public_state=lambda incoming: {**copy.deepcopy(dict(incoming)), "public": True},
        resume_record=lambda bid: resumed.append(bid),
        transaction_lock=nullcontext(),
    )
    return {
        "service": service,
        "state": current,
        "saved": saved,
        "normalized": normalized,
        "linked": linked,
        "commands": commands,
        "resumed": resumed,
    }


def test_phase_for_status_maps_supported_lifecycle_values() -> None:
    assert BroadcastLifecycleService.phase_for_status("planned") == "pregame"
    assert BroadcastLifecycleService.phase_for_status("live") == "live"
    assert BroadcastLifecycleService.phase_for_status("completed") == "final"
    assert BroadcastLifecycleService.phase_for_status("unknown") == "pregame"


def test_load_returns_not_found_for_missing_or_archived_record() -> None:
    rows = [record()]
    rows[0]["archived"] = True
    built = build_service(records=rows)
    result = built["service"].load("FB-2026-01")
    assert result.code == "NOT_FOUND"
    assert built["saved"] == []


def test_load_returns_already_active_state_without_resaving() -> None:
    state = default_state()
    state.update({"broadcast_created": True, "broadcast_id": "FB-2026-01"})
    built = build_service(state=state)
    result = built["service"].load("FB-2026-01")
    assert result.ok
    assert result.data["state"]["broadcast_id"] == "FB-2026-01"
    assert built["saved"] == []


def test_load_normalizes_saved_live_snapshot() -> None:
    row = record("live")
    row["live_state"] = {
        "broadcast_created": True,
        "broadcast_id": "FB-2026-01",
        "home_score": 7,
    }
    built = build_service(records=[row])
    result = built["service"].load("FB-2026-01")
    assert result.ok
    assert result.data["state"]["normalized"] is True
    assert result.data["state"]["home_score"] == 7
    assert result.data["state"]["broadcast_phase"] == "live"
    assert len(built["normalized"]) == 1
    assert len(built["saved"]) == 1


def test_load_builds_new_state_and_team_identities() -> None:
    built = build_service()
    result = built["service"].load("FB-2026-01")
    state = result.data["state"]
    assert state["broadcast_created"] is True
    assert state["home_identity"] == {
        "school_id": "caledonia",
        "sport": "Football",
    }
    assert state["visitor_identity"]["school_id"] == "new-hope"
    assert state["home_score"] == 0
    assert state["review_mode"] is False
    assert state["home_pregame_record"]["ties"] == 1
    assert state["region_game"] is True
    assert state["special_designations"] == ["homecoming", "rivalry"]


def test_load_completed_record_restores_final_score_and_review_mode() -> None:
    built = build_service(records=[record("completed")])
    result = built["service"].load("FB-2026-01")
    state = result.data["state"]
    assert state["home_score"] == 28
    assert state["visitor_score"] == 14
    assert state["review_mode"] is True
    assert state["broadcast_phase"] == "final"


def test_load_restores_package_and_roster_links() -> None:
    built = build_service(
        packages=[
            {
                "id": "package-1",
                "broadcast_id": "FB-2026-01",
                "roster_ids": ["home-roster", "visitor-roster"],
            }
        ]
    )
    state = built["service"].load("FB-2026-01").data["state"]
    assert state["broadcast_package_id"] == "package-1"
    assert state["package_roster_ids"] == ["home-roster", "visitor-roster"]


def test_initialize_requires_active_broadcast() -> None:
    built = build_service()
    result = built["service"].initialize()
    assert result.code == "NO_ACTIVE_BROADCAST"


def test_initialize_returns_readiness_and_deprecation_marker() -> None:
    state = default_state()
    state["broadcast_id"] = "FB-2026-01"
    built = build_service(state=state)
    result = built["service"].initialize()
    assert result.ok
    assert result.data["readiness"] == {"ready": True}
    assert result.data["deprecated"] is True


def test_start_requires_active_broadcast() -> None:
    built = build_service()
    result = built["service"].start()
    assert result.code == "NO_ACTIVE_BROADCAST"
    assert built["linked"] == []


def test_start_marks_state_live_and_updates_linked_record() -> None:
    state = default_state()
    state["broadcast_id"] = "FB-2026-01"
    built = build_service(state=state)
    result = built["service"].start()
    assert result.ok
    assert built["state"]["status"] == "live"
    assert built["state"]["broadcast_phase"] == "live"
    assert built["state"]["scorebug_visible"] is True
    assert built["linked"] == [("FB-2026-01", "live", None)]
    assert result.data["state"]["public"] is True
    assert result.data["broadcast"]["broadcast_id"] == "FB-2026-01"


def test_start_sends_obs_command_when_control_is_enabled() -> None:
    state = default_state()
    state["broadcast_id"] = "FB-2026-01"
    built = build_service(state=state, controlled_commands=True)
    result = built["service"].start()
    assert built["commands"] == [True]
    assert result.data["obs"] == {"reachable": True, "visible": True}


def test_start_captures_obs_boundary_failure_without_losing_live_state() -> None:
    state = default_state()
    state["broadcast_id"] = "FB-2026-01"
    built = build_service(
        state=state,
        controlled_commands=True,
        command_error=RuntimeError("OBS unavailable"),
    )
    result = built["service"].start()
    assert result.ok
    assert result.data["obs"] == {"error": "OBS unavailable"}
    assert built["state"]["status"] == "live"


def test_resume_requires_active_broadcast() -> None:
    built = build_service()
    result = built["service"].resume()
    assert result.code == "NO_ACTIVE_BROADCAST"
    assert built["resumed"] == []


def test_resume_reopens_record_and_keeps_scorebug_hidden() -> None:
    state = default_state()
    state.update(
        {
            "broadcast_id": "FB-2026-01",
            "status": "completed",
            "broadcast_phase": "final",
            "review_mode": True,
            "scorebug_visible": True,
            "home_score": 28,
        }
    )
    built = build_service(state=state)
    result = built["service"].resume()
    assert result.ok
    assert built["state"]["status"] == "live"
    assert built["state"]["broadcast_phase"] == "live"
    assert built["state"]["review_mode"] is False
    assert built["state"]["scorebug_visible"] is False
    assert built["state"]["home_score"] == 28
    assert built["resumed"] == ["FB-2026-01"]
    assert result.data["state"]["public"] is True
