from __future__ import annotations

import copy

from graphics_service import GraphicsService


DEFAULTS = {
    "lower_third": {
        "visible": False,
        "eyebrow": "CSRN",
        "headline": "",
        "secondary": "",
        "footer": "",
        "logo_source": "csrn",
        "accent_source": "csrn",
        "custom_accent": "#C9203B",
        "duration": 0,
        "expires_at": 0,
        "updated_at": 0,
    },
    "player_graphic": {
        "visible": False,
        "graphic_type": "player_id",
        "roster_id": "",
        "player_id": "",
        "school_id": "",
        "full_name": "",
        "display_name": "",
        "number": "",
        "position": "",
        "secondary_position": "",
        "grade": "",
        "height": "",
        "weight": "",
        "headshot": "",
        "team_logo": "",
        "team_name": "",
        "team_color": "#C9203B",
        "play_detail": "",
        "eyebrow": "PLAYER PROFILE",
        "sponsor_id": "",
        "sponsor_name": "",
        "sponsor_logo": "",
        "duration": 0,
        "expires_at": 0,
        "updated_at": 0,
    },
    "personnel_graphic": {
        "visible": False,
        "personnel_id": "",
        "graphic_type": "coach_id",
        "full_name": "",
        "display_name": "",
        "title": "",
        "role": "",
        "organization": "",
        "headshot": "",
        "logo": "",
        "accent": "#C9203B",
        "eyebrow": "COACH",
        "sponsor_id": "",
        "sponsor_name": "",
        "sponsor_logo": "",
        "duration": 0,
        "expires_at": 0,
        "updated_at": 0,
    },
}


def roster() -> dict:
    return {
        "id": "caledonia-football",
        "school_id": "caledonia",
        "sport": "Football",
        "players": [
            {
                "id": "12-jason",
                "first_name": "Jason",
                "last_name": "Player",
                "preferred_name": "J.P.",
                "number": "12",
                "position": "Quarterback",
                "secondary_position": "Safety/Returner",
                "grade": "12",
                "height": "6-2",
                "weight": "205",
                "headshot": "/roster-headshots/jason.png",
            }
        ],
    }


def school() -> dict:
    return {
        "id": "caledonia",
        "broadcast_name": "Caledonia",
        "official_name": "Caledonia High School",
        "primary_color": "#B5121B",
    }


def person() -> dict:
    return {
        "id": "jordan",
        "full_name": "Jordan Smith",
        "preferred_name": "Jordan",
        "title": "Color Analyst",
        "role": "Color Analyst",
        "organization": "CSRN",
        "school_id": "caledonia",
        "headshot": "/personnel-headshots/jordan.png",
    }


def base_state() -> dict:
    return {
        "lower_third": copy.deepcopy(DEFAULTS["lower_third"]),
        "player_graphic": copy.deepcopy(DEFAULTS["player_graphic"]),
        "personnel_graphic": copy.deepcopy(DEFAULTS["personnel_graphic"]),
    }


def service(*, now: float = 1000.0, sponsors=None) -> GraphicsService:
    def apply_sponsor(graphic: dict, incoming: dict) -> str:
        if sponsors is not None:
            sponsors.append((copy.deepcopy(graphic), copy.deepcopy(incoming)))
        if incoming.get("sponsor_id"):
            graphic["sponsor_id"] = str(incoming["sponsor_id"])
            graphic["sponsor_name"] = "Sponsor Name"
            graphic["sponsor_logo"] = "/asset-files/sponsor.png"
            return "SPONSOR_WARNING" if incoming.get("warning") else ""
        return ""

    return GraphicsService(
        default_state=lambda: copy.deepcopy(DEFAULTS),
        load_rosters=lambda: [roster()],
        load_schools=lambda: [school()],
        load_personnel=lambda: [person()],
        build_identity=lambda record, sport: {
            "logo": "/school-logos/caledonia.png",
            "primary_color": "#B5121B",
            "sport": sport,
        },
        apply_sponsor=apply_sponsor,
        clock=lambda: now,
    )


def test_duration_boolean_and_position_helpers() -> None:
    assert GraphicsService._duration(500) == 120
    assert GraphicsService._duration("bad") == 0
    assert GraphicsService._boolean("yes") is True
    assert GraphicsService._boolean("off") is False
    assert GraphicsService.normalize_position("Athlete") == "ATH"
    assert GraphicsService.normalize_position("") == "ATH"
    assert GraphicsService.event_position(roster()["players"][0]) == "Quarterback"
    assert GraphicsService.event_position(
        roster()["players"][0], defensive=True
    ) == "Safety"
    assert GraphicsService.player_display(roster()["players"][0]) == "J.P."


def test_activate_primary_hides_other_graphics() -> None:
    state = base_state()
    state["lower_third"]["visible"] = True
    state["personnel_graphic"]["visible"] = True
    updated = service().activate_primary(state, "player")
    assert updated["lower_third"]["visible"] is False
    assert updated["personnel_graphic"]["visible"] is False
    assert updated["primary_graphic_channel"] == "player"
    assert "primary_graphic_channel" not in state


def test_lower_third_show_updates_fields_duration_and_exclusivity() -> None:
    state = base_state()
    state["player_graphic"]["visible"] = True
    result = service().update_lower_third(
        state,
        {
            "action": "show",
            "headline": "A" * 220,
            "secondary": "Tonight",
            "duration": 15,
        },
    )
    lower = result.data["state"]["lower_third"]
    assert len(lower["headline"]) == 180
    assert lower["secondary"] == "Tonight"
    assert lower["visible"] is True
    assert lower["expires_at"] == 1015
    assert lower["updated_at"] == 1000
    assert result.data["state"]["player_graphic"]["visible"] is False


def test_lower_third_update_defaults_to_hidden() -> None:
    state = base_state()
    state["lower_third"]["visible"] = True
    result = service().update_lower_third(
        state,
        {"action": "update", "headline": "Updated"},
    )
    lower = result.data["graphic"]
    assert lower["headline"] == "Updated"
    assert lower["visible"] is False


def test_lower_third_hide_and_clear_contracts() -> None:
    state = base_state()
    state["lower_third"].update(
        {"visible": True, "headline": "Live", "expires_at": 1100}
    )
    hidden = service().update_lower_third(state, {"action": "hide"})
    assert hidden.data["graphic"]["visible"] is False
    assert hidden.data["graphic"]["expires_at"] == 0

    cleared = service().update_lower_third(state, {"action": "clear"})
    assert cleared.data["graphic"] == DEFAULTS["lower_third"]


def test_player_show_requires_player_identifier() -> None:
    result = service().update_player(base_state(), {"action": "show"})
    assert result.code == "PLAYER_REQUIRED"


def test_player_show_enriches_roster_identity_and_sponsor() -> None:
    calls: list = []
    result = service(sponsors=calls).update_player(
        base_state(),
        {
            "action": "show",
            "roster_id": "caledonia-football",
            "player_id": "12-jason",
            "duration": 20,
            "sponsor_id": "sponsor-1",
            "warning": True,
        },
    )
    graphic = result.data["graphic"]
    assert graphic["visible"] is True
    assert graphic["full_name"] == "Jason Player"
    assert graphic["display_name"] == "J.P."
    assert graphic["team_name"] == "Caledonia"
    assert graphic["team_logo"] == "/school-logos/caledonia.png"
    assert graphic["team_color"] == "#B5121B"
    assert graphic["sponsor_name"] == "Sponsor Name"
    assert graphic["expires_at"] == 1020
    assert result.data["sponsor_warning"] == "SPONSOR_WARNING"
    assert len(calls) == 1


def test_player_highlight_persists_type_eyebrow_and_detail() -> None:
    result = service().update_player(
        base_state(),
        {
            "action": "show",
            "roster_id": "caledonia-football",
            "player_id": "12-jason",
            "graphic_type": "player_highlight",
            "eyebrow": "PLAYER HIGHLIGHT",
            "play_detail": "8 tackles · 2 sacks · forced fumble",
            "duration": 8,
        },
    )
    graphic = result.data["graphic"]
    assert graphic["visible"] is True
    assert graphic["graphic_type"] == "player_highlight"
    assert graphic["eyebrow"] == "PLAYER HIGHLIGHT"
    assert graphic["play_detail"] == "8 tackles · 2 sacks · forced fumble"
    assert graphic["expires_at"] == 1008


def test_player_hide_preserves_identity_and_resets_timer() -> None:
    state = base_state()
    state["player_graphic"].update(
        {
            "player_id": "12-jason",
            "roster_id": "caledonia-football",
            "visible": True,
            "expires_at": 1100,
        }
    )
    result = service().update_player(state, {"action": "hide"})
    assert result.data["graphic"]["player_id"] == "12-jason"
    assert result.data["graphic"]["visible"] is False
    assert result.data["graphic"]["expires_at"] == 0


def test_player_clear_restores_default_graphic() -> None:
    state = base_state()
    state["player_graphic"]["player_id"] = "12-jason"
    result = service().update_player(state, {"action": "clear"})
    assert result.data["graphic"] == DEFAULTS["player_graphic"]


def test_personnel_show_requires_resolved_personnel() -> None:
    result = service().update_personnel(
        base_state(),
        {"action": "show", "personnel_id": "missing"},
    )
    assert result.code == "PERSONNEL_REQUIRED"


def test_personnel_show_enriches_identity_and_sponsor() -> None:
    result = service().update_personnel(
        base_state(),
        {
            "action": "show",
            "personnel_id": "jordan",
            "duration": 30,
            "sponsor_id": "sponsor-1",
        },
    )
    graphic = result.data["graphic"]
    assert graphic["visible"] is True
    assert graphic["personnel_id"] == "jordan"
    assert graphic["display_name"] == "Jordan"
    assert graphic["organization"] == "CSRN"
    assert graphic["logo"] == "/school-logos/caledonia.png"
    assert graphic["accent"] == "#B5121B"
    assert graphic["expires_at"] == 1030
    assert graphic["sponsor_name"] == "Sponsor Name"


def test_personnel_hide_and_clear_contracts() -> None:
    state = base_state()
    state["personnel_graphic"].update(
        {"personnel_id": "jordan", "visible": True, "expires_at": 1100}
    )
    hidden = service().update_personnel(state, {"action": "hide"})
    assert hidden.data["graphic"]["visible"] is False
    assert hidden.data["graphic"]["expires_at"] == 0

    cleared = service().update_personnel(state, {"action": "clear"})
    assert cleared.data["graphic"] == DEFAULTS["personnel_graphic"]


def test_automation_player_skips_incomplete_requests() -> None:
    subject = service()
    assert subject.show_automation_player(
        base_state(), None, None, "touchdown", 8
    ).data["applied"] is False
    assert subject.show_automation_player(
        base_state(), roster(), roster()["players"][0], "touchdown", 0
    ).data["applied"] is False


def test_automation_player_builds_timed_primary_graphic() -> None:
    source_roster = roster()
    source_player = source_roster["players"][0]
    state = base_state()
    state["lower_third"]["visible"] = True
    result = service().show_automation_player(
        state,
        source_roster,
        source_player,
        "touchdown",
        8,
        defensive=True,
        play_detail="42-yard return",
    )
    graphic = result.data["graphic"]
    assert result.data["applied"] is True
    assert graphic["eyebrow"] == "TOUCHDOWN"
    assert graphic["position"] == "Safety"
    assert graphic["play_detail"] == "42-yard return"
    assert graphic["expires_at"] == 1008
    assert result.data["state"]["lower_third"]["visible"] is False
    assert result.data["state"]["primary_graphic_channel"] == "player"
