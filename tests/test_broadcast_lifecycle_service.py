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


def test_load_carries_jurisdiction_onto_state_for_the_rules_engine() -> None:
    # Round 26 Phase B 2/5: the jurisdiction tuple on a broadcast record
    # reaches game state, so ruleset_service.active_ruleset(state) resolves
    # the right ruleset.
    import ruleset_service

    # legacy record (no jurisdiction fields) -> generic US / NFHS
    state = build_service()["service"].load("FB-2026-01").data["state"]
    assert (state["country"], state["region"], state["association"]) == ("US", "", "")
    assert ruleset_service.active_ruleset_id(state) == "football/us-nfhs"

    # Canadian record -> ca-cjfl-ofc
    ca_row = record()
    ca_row.update({"country": "CA", "region": "ON", "association": "CJFL"})
    ca_state = build_service(records=[ca_row])["service"].load("FB-2026-01").data["state"]
    assert (ca_state["country"], ca_state["region"], ca_state["association"]) == ("CA", "ON", "CJFL")
    assert ruleset_service.active_ruleset_id(ca_state) == "football/ca-cjfl-ofc"


def test_load_stamps_effective_profile_id_and_version_at_creation() -> None:
    # Baseball engine P0 (CSRN_NFHS_Baseball_Softball_Rules_Engine_Spec_2026
    # Sec.3.2): "A game stores effectiveProfileId and effectiveProfileVersion
    # at creation." Football's own rulesets predate the "version" field, so
    # an absent one defaults to 1 rather than requiring every shipped
    # document to be edited (see test_ruleset_golden.py -- football stays
    # byte-identical).
    state = build_service()["service"].load("FB-2026-01").data["state"]
    assert state["effective_profile_id"] == "football/us-nfhs"
    assert state["effective_profile_version"] == 1

    bb_row = record()
    bb_row.update({"sport": "Baseball", "country": "US", "association": "NFHS"})
    bb_state = build_service(records=[bb_row])["service"].load("FB-2026-01").data["state"]
    assert bb_state["effective_profile_id"] == "baseball/us-nfhs"
    assert bb_state["effective_profile_version"] == 1

    sb_row = record()
    sb_row.update({"sport": "Softball", "country": "US"})
    sb_state = build_service(records=[sb_row])["service"].load("FB-2026-01").data["state"]
    assert sb_state["effective_profile_id"] == "softball/us-nfhs"


def test_load_stamps_a_fresh_diamond_substate_for_baseball_and_softball() -> None:
    # P5: a freshly-loaded baseball/softball broadcast gets a clean
    # namespaced diamond sub-state (inning 1, TOP, empty lineups) the
    # moment it's loaded, same standard as every other field _state_from_
    # record() stamps -- no separate "initialize" step required before the
    # operator UI has something sane to render.
    bb_row = record()
    bb_row.update({"sport": "Baseball", "country": "US", "association": "NFHS"})
    bb_state = build_service(records=[bb_row])["service"].load("FB-2026-01").data["state"]
    assert bb_state["diamond"]["inning"] == 1
    assert bb_state["diamond"]["inning_half"] == "TOP"
    assert bb_state["diamond"]["lineup"]["home"]["slots"] == {}

    sb_row = record()
    sb_row.update({"sport": "Softball", "country": "US"})
    sb_state = build_service(records=[sb_row])["service"].load("FB-2026-01").data["state"]
    assert sb_state["diamond"]["inning"] == 1

    # Football is untouched -- no "diamond" key appears at all.
    fb_state = build_service()["service"].load("FB-2026-01").data["state"]
    assert "diamond" not in fb_state


def test_load_never_restamps_a_resumed_live_snapshot() -> None:
    # Sec.3.2 continued: "Changing a master profile affects only future
    # games unless an explicit migration is performed." A resumed snapshot
    # already carries whatever was stamped when the game was first loaded;
    # this must survive unchanged even if the underlying ruleset catalog
    # later changes, since load() only computes the stamp on the "build a
    # fresh state from the record" branch, never on the snapshot-resume one.
    row = record("live")
    row.update({"sport": "Baseball", "country": "US", "association": "NFHS"})
    row["live_state"] = {
        "broadcast_created": True,
        "broadcast_id": "FB-2026-01",
        "effective_profile_id": "baseball/us-nfhs",
        "effective_profile_version": 7,  # a hypothetical later profile edit
    }
    built = build_service(records=[row])
    result = built["service"].load("FB-2026-01")
    state = result.data["state"]
    assert state["effective_profile_id"] == "baseball/us-nfhs"
    assert state["effective_profile_version"] == 7


def test_load_never_overwrites_a_resumed_diamond_snapshot() -> None:
    # Same principle as the profile-stamp test above, for the diamond
    # sub-state: a resumed snapshot's in-progress game (outs recorded,
    # runners on base) must survive unchanged -- the fresh-diamond stamp
    # only ever applies on the "build from record" branch.
    row = record("live")
    row.update({"sport": "Baseball", "country": "US", "association": "NFHS"})
    row["live_state"] = {
        "broadcast_created": True,
        "broadcast_id": "FB-2026-01",
        "diamond": {"inning": 5, "inning_half": "BOTTOM", "outs": 2},
    }
    built = build_service(records=[row])
    state = built["service"].load("FB-2026-01").data["state"]
    assert state["diamond"] == {"inning": 5, "inning_half": "BOTTOM", "outs": 2}


def test_load_stamps_a_fresh_hoops_substate_for_basketball() -> None:
    # P5: a freshly-loaded basketball broadcast gets a clean period/clock/
    # hoops sub-state the moment it's loaded, same standard as the diamond
    # stamp above -- but ruleset-derived (period length, shot clock,
    # timeouts) via hoops_period_service.start_game(), not a bare
    # structural default, since basketball's own initial values depend on
    # the active ruleset.
    bb_row = record()
    bb_row.update({"sport": "Basketball", "country": "US", "association": "NFHS"})
    bb_state = build_service(records=[bb_row])["service"].load("FB-2026-01").data["state"]
    assert bb_state["period"] == "1"
    assert bb_state["clock_seconds"] == 480
    assert bb_state["clock_running"] is False
    assert bb_state["hoops"]["home_timeouts"] == 5
    assert bb_state["hoops"]["home_bonus"] == "NONE"

    # Football is untouched -- no "hoops" key appears at all, and its own
    # "period" field (a plain quarter counter, not basketball's clock/hoops
    # apparatus) is whatever football's own default already was.
    fb_state = build_service()["service"].load("FB-2026-01").data["state"]
    assert "hoops" not in fb_state


def test_load_never_overwrites_a_resumed_hoops_snapshot() -> None:
    # Same principle as the diamond snapshot test above: a resumed
    # basketball snapshot's in-progress game (fouls recorded, a real
    # clock reading) must survive unchanged -- the fresh-hoops stamp only
    # ever applies on the "build from record" branch.
    row = record("live")
    row.update({"sport": "Basketball", "country": "US", "association": "NFHS"})
    row["live_state"] = {
        "broadcast_created": True,
        "broadcast_id": "FB-2026-01",
        "period": "3",
        "clock_seconds": 214,
        "hoops": {"home_team_fouls": 4, "home_bonus": "DOUBLE"},
    }
    built = build_service(records=[row])
    state = built["service"].load("FB-2026-01").data["state"]
    assert state["period"] == "3"
    assert state["clock_seconds"] == 214
    assert state["hoops"] == {"home_team_fouls": 4, "home_bonus": "DOUBLE"}


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


