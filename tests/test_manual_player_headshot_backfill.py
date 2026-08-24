from __future__ import annotations

import app as app_module


ROSTERS = [
    {
        "id": "caledonia-football-2026-varsity-boys",
        "school_id": "caledonia",
        "players": [
            {
                "id": "P-79",
                "number": "79",
                "first_name": "Jaraylon",
                "last_name": "Washington",
                "status": "active",
                "headshot": "/roster-headshots/caledonia__79-jaraylon-washington.jpg",
                "grade": "12",
            },
            {
                "id": "P-1",
                "number": "1",
                "first_name": "Caleb",
                "last_name": "Lang",
                "status": "active",
                "headshot": "",
            },
            {
                "id": "P-99",
                "number": "99",
                "first_name": "Old",
                "last_name": "Bench",
                "status": "inactive",
                "headshot": "/roster-headshots/caledonia__99-old-bench.jpg",
            },
        ],
    }
]


def test_manual_player_backfills_headshot_from_roster_by_number(monkeypatch) -> None:
    # Reproduces the reported bug: the operator UI submits only a typed
    # jersey number (no roster_id/player_id), same as when the automatic
    # roster match is rejected by the stale-number guard. Before this fix,
    # manual_automation_player() always returned headshot="" regardless of
    # whether that player actually has a photo on file.
    monkeypatch.setattr(app_module, "load_rosters", lambda: ROSTERS)

    player = app_module.manual_automation_player(
        {"number": "79", "name": "Jaraylon Washington"},
        "Caledonia",
        "caledonia",
    )

    assert player is not None
    assert player["headshot"] == "/roster-headshots/caledonia__79-jaraylon-washington.jpg"
    assert player["grade"] == "12"
    assert player["id"] == ""  # still a manual entry, not roster-linked
    assert player["manual"] is True


def test_manual_player_stays_headshot_empty_when_roster_player_has_none(monkeypatch) -> None:
    # Caleb Lang genuinely has no headshot on file -- confirms the backfill
    # doesn't invent one, and doesn't fall back to some other player's photo.
    monkeypatch.setattr(app_module, "load_rosters", lambda: ROSTERS)

    player = app_module.manual_automation_player(
        {"number": "1", "name": "Caleb Lang"},
        "Caledonia",
        "caledonia",
    )

    assert player is not None
    assert player["headshot"] == ""


def test_manual_player_ignores_inactive_roster_entries(monkeypatch) -> None:
    monkeypatch.setattr(app_module, "load_rosters", lambda: ROSTERS)

    player = app_module.manual_automation_player(
        {"number": "99", "name": "Old Bench"},
        "Caledonia",
        "caledonia",
    )

    assert player is not None
    assert player["headshot"] == ""


def test_manual_player_without_school_id_skips_lookup_but_still_builds_player(monkeypatch) -> None:
    calls: list[str] = []

    def tracking_load_rosters():
        calls.append("called")
        return ROSTERS

    monkeypatch.setattr(app_module, "load_rosters", tracking_load_rosters)

    player = app_module.manual_automation_player(
        {"number": "79", "name": "Jaraylon Washington"},
        "Caledonia",
        "",
    )

    assert player is not None
    assert player["headshot"] == ""
    assert calls == []  # no roster_id/school_id context -- don't guess


def test_manual_player_without_number_returns_none(monkeypatch) -> None:
    monkeypatch.setattr(app_module, "load_rosters", lambda: ROSTERS)
    assert app_module.manual_automation_player({"name": "No Number"}, "Caledonia", "caledonia") is None
