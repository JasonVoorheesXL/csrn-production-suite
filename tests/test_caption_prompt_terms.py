from __future__ import annotations

import app as app_module


def test_caption_prompt_terms_include_active_roster_and_coach_names(monkeypatch) -> None:
    monkeypatch.setattr(
        app_module,
        "load_state",
        lambda: {
            "sport": "Football",
            "level": "Varsity",
            "home_team": "Caledonia",
            "visitor_team": "New Hope",
            "home_school_id": "caledonia",
            "visitor_school_id": "new-hope",
            "home_identity": {"broadcast_name": "Caledonia", "mascot": "Cavaliers"},
            "visitor_identity": {"broadcast_name": "New Hope", "mascot": "Tigers"},
            "package_roster_ids": ["caledonia-football"],
        },
    )
    monkeypatch.setattr(
        app_module,
        "load_rosters",
        lambda: [
            {
                "id": "caledonia-football",
                "school_id": "caledonia",
                "sport": "Football",
                "level": "Varsity",
                "players": [
                    {
                        "number": "2",
                        "first_name": "Darquez",
                        "last_name": "Williams",
                        "preferred_name": "Jazz",
                        "pronunciation": "DArkwez WIlliams",
                        "status": "active",
                    },
                    {
                        "number": "99",
                        "first_name": "Inactive",
                        "last_name": "Player",
                        "status": "inactive",
                    },
                ],
            },
            {
                "id": "test-roster",
                "school_id": "test-school",
                "sport": "Football",
                "level": "Varsity",
                "players": [{"first_name": "Test", "last_name": "Only", "status": "active"}],
            },
        ],
    )
    monkeypatch.setattr(
        app_module,
        "load_broadcasters",
        lambda: [
            {
                "full_name": "Michael Campbell",
                "name": "Michael Campbell",
                "category": "Coach",
                "role": "Head Coach",
                "title": "Head Coach",
                "school_id": "caledonia",
                "status": "active",
            }
        ],
    )
    monkeypatch.setattr(
        app_module,
        "get_school",
        lambda school_id: {"id": school_id, "broadcast_name": "Caledonia"} if school_id == "caledonia" else None,
    )

    terms = app_module.current_caption_prompt_terms()

    assert "Darquez Williams" in terms
    assert "Jazz Williams" in terms
    assert "DArkwez WIlliams" in terms
    assert "number 2 Darquez Williams" in terms
    assert "Michael Campbell" in terms
    assert "Head Coach Michael Campbell" in terms
    assert "Inactive Player" not in terms
    assert "Test Only" not in terms


def test_caption_prompt_terms_do_not_inject_a_hardcoded_cavaliers(monkeypatch) -> None:
    # Round 13 Task B: the mascot seed used to be a literal "Cavaliers". Now
    # the team names / mascots come only from the loaded game state.
    monkeypatch.setattr(
        app_module,
        "load_state",
        lambda: {
            "sport": "Football",
            "home_team": "Amory",
            "visitor_team": "Houston",
            "home_identity": {"broadcast_name": "Amory", "mascot": "Panthers"},
            "visitor_identity": {"broadcast_name": "Houston", "mascot": "Hilltoppers"},
        },
    )
    monkeypatch.setattr(app_module, "load_rosters", lambda: [])
    monkeypatch.setattr(app_module, "load_broadcasters", lambda: [])

    terms = app_module.current_caption_prompt_terms()

    assert "Cavaliers" not in terms
    assert "Amory" in terms and "Panthers" in terms
    assert "first and ten" in terms and "yard line" in terms
