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
    "player_highlight": {
        "visible": False,
        "roster_id": "",
        "player_id": "",
        "school_id": "",
        "full_name": "",
        "display_name": "",
        "number": "",
        "position": "",
        "grade": "",
        "team_logo": "",
        "team_name": "",
        "team_color": "#C9203B",
        "eyebrow": "PLAYER HIGHLIGHT",
        "detail": "",
        "media_asset_id": "",
        "media_name": "",
        "media_url": "",
        "media_type": "video",
        "duration": 0,
        "expires_at": 0,
        "updated_at": 0,
    },
    "sponsor_spotlight": {
        "visible": False,
        "sponsor_id": "",
        "sponsor_name": "",
        "sponsor_logo": "",
        "lead_in": "SPONSOR SPOTLIGHT",
        "caption": "",
        "media_asset_id": "",
        "media_name": "",
        "media_url": "",
        "media_type": "image",
        "duration": 0,
        "expires_at": 0,
        "updated_at": 0,
    },
    "graphics_queue": [],
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
        "player_highlight": copy.deepcopy(DEFAULTS["player_highlight"]),
        "personnel_graphic": copy.deepcopy(DEFAULTS["personnel_graphic"]),
        "sponsor_spotlight": copy.deepcopy(DEFAULTS["sponsor_spotlight"]),
        "graphics_queue": [],
    }


def service(*, now: float = 1000.0, sponsors=None, assets=None) -> GraphicsService:
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
        load_assets=lambda: copy.deepcopy(assets or []),
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


def test_player_spotlight_persists_type_eyebrow_and_detail() -> None:
    result = service().update_player(
        base_state(),
        {
            "action": "show",
            "roster_id": "caledonia-football",
            "player_id": "12-jason",
            "graphic_type": "player_spotlight",
            "eyebrow": "PLAYER SPOTLIGHT",
            "play_detail": "8 tackles · 2 sacks · forced fumble",
            "duration": 8,
        },
    )
    graphic = result.data["graphic"]
    assert graphic["visible"] is True
    assert graphic["graphic_type"] == "player_spotlight"
    assert graphic["eyebrow"] == "PLAYER SPOTLIGHT"
    assert graphic["play_detail"] == "8 tackles · 2 sacks · forced fumble"
    assert graphic["expires_at"] == 1008


def test_touchdown_queues_behind_active_player_spotlight_and_advances_once() -> None:
    state = base_state()
    state["player_graphic"].update(
        {
            "visible": True,
            "graphic_type": "player_spotlight",
            "player_id": "12-jason",
            "expires_at": 1005,
        }
    )
    queued = service(now=1000).show_automation_player(
        state,
        roster(),
        roster()["players"][0],
        "touchdown",
        8,
        eyebrow="TOUCHDOWN",
        play_detail="42-yard touchdown",
    )
    assert queued.data["queued"] is True
    assert queued.data["state"]["player_graphic"]["graphic_type"] == "player_spotlight"
    assert len(queued.data["state"]["graphics_queue"]) == 1

    advanced = service(now=1005).reconcile_queue(queued.data["state"])
    player = advanced.data["state"]["player_graphic"]
    assert player["graphic_type"] == "touchdown"
    assert player["play_detail"] == "42-yard touchdown"
    assert player["visible"] is True
    assert player["expires_at"] == 1013
    assert advanced.data["state"]["graphics_queue"] == []


def test_queue_cancel_prevents_delivery() -> None:
    state = base_state()
    state["graphics_queue"] = [
        {
            "id": "GQ-1",
            "channel": "player",
            "graphic": {"duration": 8, "player_id": "12-jason"},
        }
    ]
    result = service().update_queue(state, {"action": "cancel", "id": "GQ-1"})
    assert result.data["state"]["graphics_queue"] == []
    assert result.data["state"]["player_graphic"]["visible"] is False


def test_sponsor_spotlight_accepts_active_sponsor_media_and_preserves_scorebug() -> None:
    approved = {
        "id": "bank-video",
        "name": "Bank Spotlight",
        "category": "Sponsor",
        "asset_type": "Video",
        "rights_status": "Licensed",
        "file_url": "/asset-files/bank.webm",
        "active": True,
    }
    state = base_state()
    state["scorebug_visible"] = True
    result = service(assets=[approved]).update_sponsor_spotlight(
        state,
        {
            "action": "show",
            "sponsor_id": "bank",
            "media_asset_id": "bank-video",
            "caption": "Community banking since 1954",
            "duration": 12,
        },
    )
    spotlight = result.data["state"]["sponsor_spotlight"]
    assert spotlight["visible"] is True
    assert spotlight["media_type"] == "video"
    assert spotlight["expires_at"] == 1012
    assert result.data["state"]["scorebug_visible"] is True

    documented_only = service(
        assets=[dict(approved, rights_status="Unverified")]
    ).update_sponsor_spotlight(
        state,
        {
            "action": "show",
            "sponsor_id": "bank",
            "media_asset_id": "bank-video",
        },
    )
    assert documented_only.ok
    assert documented_only.data["graphic"]["media_url"] == "/asset-files/bank.webm"


def test_sponsor_spotlight_enforces_placement_and_sponsor_association() -> None:
    approved = {
        "id": "bank-video",
        "name": "Bank Spotlight",
        "category": "Sponsor",
        "asset_type": "Video",
        "placement": "sponsor_feature_video",
        "sponsor_id": "bank",
        "rights_status": "Licensed",
        "file_url": "/asset-files/bank.webm",
        "active": True,
    }
    state = base_state()
    accepted = service(assets=[approved]).update_sponsor_spotlight(
        state,
        {
            "action": "show",
            "sponsor_id": "bank",
            "media_asset_id": "bank-video",
            "duration": 30,
        },
    )
    assert accepted.ok
    wrong_sponsor = service(assets=[approved]).update_sponsor_spotlight(
        state,
        {
            "action": "show",
            "sponsor_id": "other",
            "media_asset_id": "bank-video",
            "duration": 30,
        },
    )
    assert wrong_sponsor.code == "SPONSOR_MEDIA_NOT_APPROVED"
    wrong_placement = service(
        assets=[dict(approved, placement="scorebug_sponsor")]
    ).update_sponsor_spotlight(
        state,
        {
            "action": "show",
            "sponsor_id": "bank",
            "media_asset_id": "bank-video",
            "duration": 30,
        },
    )
    assert wrong_placement.code == "SPONSOR_MEDIA_NOT_APPROVED"


def test_player_highlight_video_is_player_linked_timed_and_scorebug_safe() -> None:
    clip = {
        "id": "jason-week-4",
        "name": "Week 4 touchdown",
        "category": "Player",
        "asset_type": "Video",
        "placement": "player_highlight_video",
        "roster_id": "caledonia-football",
        "player_id": "12-jason",
        "rights_status": "Owned",
        "file_url": "/asset-files/jason-week-4.mp4",
        "active": True,
    }
    state = base_state()
    state["scorebug_visible"] = True
    result = service(assets=[clip]).update_player_highlight(
        state,
        {
            "action": "show",
            "roster_id": "caledonia-football",
            "player_id": "12-jason",
            "media_asset_id": "jason-week-4",
            "detail": "Week 4 · 72-yard touchdown",
            "duration": 30,
        },
    )
    highlight = result.data["graphic"]
    assert highlight["visible"] is True
    assert highlight["display_name"] == "J.P."
    assert highlight["media_url"] == "/asset-files/jason-week-4.mp4"
    assert highlight["expires_at"] == 1030
    assert result.data["state"]["scorebug_visible"] is True
    assert result.data["state"]["primary_graphic_channel"] == "highlight"


def test_player_highlight_rejects_unlinked_or_unapproved_media() -> None:
    clip = {
        "id": "wrong-player",
        "name": "Wrong player",
        "category": "Player",
        "asset_type": "Video",
        "placement": "player_highlight_video",
        "roster_id": "caledonia-football",
        "player_id": "other-player",
        "rights_status": "Owned",
        "file_url": "/asset-files/wrong.mp4",
        "active": True,
    }
    result = service(assets=[clip]).update_player_highlight(
        base_state(),
        {
            "action": "show",
            "roster_id": "caledonia-football",
            "player_id": "12-jason",
            "media_asset_id": "wrong-player",
            "duration": 30,
        },
    )
    assert result.code == "PLAYER_HIGHLIGHT_MEDIA_NOT_APPROVED"


def test_touchdown_queues_behind_player_highlight_video_and_advances() -> None:
    state = base_state()
    state["player_highlight"].update(
        {
            "visible": True,
            "player_id": "12-jason",
            "media_url": "/asset-files/highlight.mp4",
            "duration": 30,
            "expires_at": 1030,
        }
    )
    queued = service().show_automation_player(
        state,
        roster(),
        roster()["players"][0],
        "touchdown",
        8,
    )
    assert queued.data["queued"] is True
    assert len(queued.data["state"]["graphics_queue"]) == 1
    hidden = service().update_player_highlight(
        queued.data["state"],
        {"action": "hide"},
    )
    assert hidden.data["state"]["player_graphic"]["visible"] is True
    assert hidden.data["state"]["player_graphic"]["graphic_type"] == "touchdown"
    assert hidden.data["state"]["graphics_queue"] == []


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
