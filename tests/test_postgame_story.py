"""Postgame story (Social Publishing round 1, 2026-11-01): the facts, the
built-in writer, the newspaper-style card, and the two routes."""
from __future__ import annotations

import copy

import pytest

import app as app_module
import postgame_card
import postgame_story as ps

BROADCAST_ID = "FB-TEST-POSTGAME"

BROADCAST = {
    "broadcast_id": BROADCAST_ID,
    "sport": "Football",
    "status": "completed",
    "date": "2026-10-23",
    "venue": "Hamblin Stadium",
    "home_team": "West Point",
    "visitor_team": "CALEDONIA",
    "home_school_id": "west-point",
    "visitor_school_id": "caledonia",
    "home_identity": {"mascot": "Green Wave"},
    "visitor_identity": {"mascot": "Cavaliers"},
    "final_home_score": 21,
    "final_visitor_score": 10,
}

ROSTERS = {
    "home": [
        {"number": "2", "first_name": "Kingston", "last_name": "Branham"},
        {"number": "8", "first_name": "Jaylen", "last_name": "Hall"},
        {"number": "9", "first_name": "Eli", "last_name": "McKellar"},
        {"number": "21", "first_name": "Marcus", "last_name": "Hall"},
    ],
    "visitor": [
        {"number": "1", "first_name": "Caleb", "last_name": "Lang"},
        {"number": "12", "first_name": "Brody", "last_name": "Watrous"},
        {"number": "5", "first_name": "Michael", "last_name": "Brewer jr"},
    ],
}


def statistics() -> dict:
    return {
        "teams": {
            "home": {"name": "West Point", "total_yards": 360, "rushing_yards": 300},
            "visitor": {"name": "Caledonia", "total_yards": 240, "rushing_yards": 60},
        },
        # Deliberately out of order (a Q2 score recorded before a Q1 score) and with
        # a stale running score on one row: the story recounts from the points.
        "scoring_summary": [
            {"quarter": "2", "team": "home", "label": "Touchdown Run", "points": 6,
             "description": "#8 jaylen hall run for 63 yards, touchdown", "home_score": 99, "visitor_score": 0, "created_at": 300},
            {"quarter": "2", "team": "home", "label": "Extra Point", "points": 1,
             "description": "Extra point good by Eli McKellar", "home_score": 14, "visitor_score": 3, "created_at": 310},
            {"quarter": "1", "team": "home", "label": "Touchdown Run", "points": 6,
             "description": "#2 Kingston Branham run for 20 yards, touchdown", "home_score": 6, "visitor_score": 0, "created_at": 100},
            {"quarter": "1", "team": "home", "label": "Extra Point", "points": 1,
             "description": "Extra point good by West Point", "home_score": 7, "visitor_score": 0, "created_at": 110},
            {"quarter": "2", "team": "visitor", "label": "Field Goal", "points": 3,
             "description": "Finn Stubbendorff field goal good", "home_score": 7, "visitor_score": 3, "created_at": 200},
            {"quarter": "4", "team": "visitor", "label": "Touchdown Pass", "points": 6,
             "description": "#12 Brody Watrous complete to #1 Caleb Lang for 47 yards, touchdown", "created_at": 500},
            {"quarter": "4", "team": "visitor", "label": "Extra Point", "points": 1,
             "description": "Extra point good by Finn Stubbendorff", "created_at": 510},
            {"quarter": "4", "team": "home", "label": "Touchdown Run", "points": 6,
             "description": "#21 Marcus Hall run for 4 yards, touchdown", "created_at": 600},
            {"quarter": "4", "team": "home", "label": "Extra Point", "points": 1,
             "description": "Extra point good by Eli McKellar", "created_at": 610},
        ],
        "play_register": [
            {"play_number": 3, "created_at": 100, "quarter": "1", "offense": "home", "defense": "visitor",
             "play_type": "run", "yards": 20, "player_number": "2", "player_name": "Kingston Branham"},
            {"play_number": 9, "created_at": 290, "quarter": "2", "offense": "home", "defense": "visitor",
             "play_type": "run", "yards": 63, "player_number": "8", "player_name": "jaylen hall"},
            # Kick rows follow the ball: offense is the receiving side.
            {"play_number": 10, "created_at": 320, "quarter": "2", "offense": "visitor", "defense": "home",
             "kicking_team": "home", "play_type": "kickoff", "return_yards": 41,
             "returner_number": "1", "returner_name": "Caleb Lang"},
            {"play_number": 14, "created_at": 400, "quarter": "3", "offense": "visitor", "defense": "home",
             "play_type": "pass", "turnover": True, "turnover_type": "interception",
             "turnover_player_number": "", "turnover_player_name": ""},
            {"play_number": 20, "created_at": 495, "quarter": "4", "offense": "visitor", "defense": "home",
             "play_type": "pass", "yards": 47, "passer_number": "12", "passer_name": "Brody Watrous",
             "receiver_number": "1", "receiver_name": "Caleb Lang"},
            {"play_number": 21, "created_at": 520, "quarter": "4", "offense": "home", "defense": "visitor",
             "play_type": "pass", "turnover": True, "turnover_type": "interception",
             "turnover_player_number": "5", "turnover_player_name": "michael brewer jr", "return_yards": 6},
        ],
        "players": [
            {"team": "home", "number": "2", "name": "Kingston Branham", "rushing_attempts": 18, "rushing_yards": 157, "touchdowns": 1},
            {"team": "home", "number": "8", "name": "jaylen hall", "rushing_attempts": 9, "rushing_yards": 120, "touchdowns": 1},
            {"team": "home", "number": "21", "name": "Marcus Hall", "rushing_attempts": 6, "rushing_yards": 45, "touchdowns": 1},
            {"team": "home", "number": "4", "name": "Backup Qb", "pass_attempts": 2, "completions": 1, "passing_yards": -2},
            {"team": "visitor", "number": "12", "name": "Brody Watrous", "pass_attempts": 21, "completions": 12,
             "passing_yards": 192, "passing_touchdowns": 1},
            {"team": "visitor", "number": "1", "name": "Caleb Lang", "receptions": 6, "receiving_yards": 161, "touchdowns": 1},
            {"team": "visitor", "number": "5", "name": "michael brewer jr", "interceptions": 1},
        ],
    }


def facts(stats: dict | None = None, broadcast: dict | None = None) -> dict:
    return ps.build_facts(
        broadcast=broadcast or BROADCAST,
        state={},
        statistics=stats or statistics(),
        roster_for_team=lambda team: ROSTERS[team],
    )


def test_scoring_plays_are_in_quarter_order_with_the_try_and_a_recounted_score() -> None:
    plays = facts()["scoring"]
    assert [(p["quarter"], p["team"], p["kind"]) for p in plays] == [
        (1, "home", "touchdown"), (2, "visitor", "field_goal"), (2, "home", "touchdown"),
        (4, "visitor", "touchdown"), (4, "home", "touchdown"),
    ]
    assert (plays[2]["home_score"], plays[2]["visitor_score"]) == (14, 3)  # not the stale 99
    # A team name typed as the kicker is not a person.
    assert ps.scoring_line(plays[0]) == "Kingston Branham 20 run (kick)"
    assert ps.scoring_line(plays[2]) == "Jaylen Hall 63 run (Eli McKellar kick)"
    assert ps.scoring_line(plays[3]) == "Caleb Lang 47 pass from Brody Watrous (Finn Stubbendorff kick)"


def test_line_score_adds_up_or_is_left_out() -> None:
    good = facts()
    assert good["line_score"] == {"labels": ["1", "2", "3", "4"], "home": [7, 7, 0, 7], "visitor": [0, 3, 0, 7]}
    assert good["scores_reliable"] is True
    bad = facts(broadcast={**BROADCAST, "final_home_score": 28})
    assert bad["line_score"] is None and bad["scores_reliable"] is False


def test_big_plays_credit_the_right_team_and_skip_nameless_players() -> None:
    plays = facts()["big_plays"]
    lines = [(p["team"], ps.big_play_line(p)) for p in plays]
    assert ("home", "Jaylen Hall 63-yd TD run") in lines
    assert ("visitor", "Michael Brewer Jr. interception, 6-yd return") in lines
    assert all("No." not in line and line.strip() for _, line in lines)  # the nameless interception is dropped
    assert [p["quarter"] for p in plays] == sorted(p["quarter"] for p in plays)
    names = ps.Names(lambda team: ROSTERS[team])
    kick = [row for row in statistics()["play_register"] if row["play_type"] == "kickoff"]
    returns = ps.big_plays(kick, [], names)
    # Kick rows follow the ball, so the returner belongs to the side that did not kick.
    assert [(p["team"], ps.big_play_line(p)) for p in returns] == [("visitor", "Caleb Lang 41-yd kickoff return")]


def test_names_come_from_the_roster_and_are_tidied() -> None:
    names = ps.Names(lambda team: ROSTERS[team], ["West Point", "CALEDONIA"])
    assert names.person("home", "8", "jaylen hall")["name"] == "Jaylen Hall"
    assert names.person("visitor", "5", "")["name"] == "Michael Brewer Jr."
    assert names.person("home", "", "West Point")["name"] == ""
    assert names.person("home", "77", "")["name"] == "No. 77"
    assert ps.tidy_team_name("ITAWAMBA AHS") == "Itawamba AHS"


def test_standouts_never_list_a_negative_yardage_leader() -> None:
    home = facts()["standouts"]["home"]
    assert [r["player"]["name"] for r in home] == ["Kingston Branham", "Jaylen Hall", "Marcus Hall"]
    assert ps.standout_line(home[0]) == "18 car, 157 yds, 1 TD"


def test_story_reads_from_the_facts() -> None:
    out = ps.write_story(facts(), sponsor_name="Main Street Hardware", station_name="WSN",
                         watch_link="https://facebook.com/wsn")
    assert out["headline"] in {"West Point beats Caledonia, 21-10", "West Point handles Caledonia, 21-10",
                               "West Point pulls away from Caledonia, 21-10"}
    lede = out["paragraphs"][0]
    assert lede.startswith("Kingston Branham ran for 157 yards and a touchdown on 18 carries") or "behind Kingston Branham" in lede
    assert "the West Point Green Wave" in lede and "on Friday at Hamblin Stadium" in lede
    assert "West Point led 7-0 after the first quarter and built a 14-3 lead by halftime." in out["story"]
    # Two Halls in the story: never a bare "Hall".
    assert " Hall " not in out["story"].replace("Jaylen Hall", "").replace("Marcus Hall", "")
    defense = {"player": {"name": "x"}, "category": "defense", "touchdowns": 0,
               "detail": {"interceptions": 1, "sacks": 0, "recoveries": 0}}
    assert ps._feat(defense) == "had an interception"
    assert "SCORING\nQ1 West Point: Kingston Branham 20 run (kick), West Point 7-0" in out["post_text"]
    assert "WSN coverage is brought to you by Main Street Hardware. Watch the full game: https://facebook.com/wsn" in out["post_text"]
    assert out["post_text"].endswith("#WestPointFootball #CaledoniaFootball #HighSchoolFootball")
    assert {ps.write_story(facts(), variant=v)["headline"] for v in range(3)} >= {out["headline"]}
    assert len({ps.write_story(facts(), variant=v)["headline"] for v in range(3)}) == 3  # variants rotate wording


def test_players_missing_from_the_roster_are_listed_and_named_by_team() -> None:
    stats = statistics()
    stats["play_register"].append({"play_number": 30, "created_at": 50, "quarter": "1", "offense": "home",
                                   "defense": "visitor", "play_type": "run", "yards": 90, "player_number": "33"})
    found = facts(stats)
    assert found["unnamed"] == [("home", "33")]
    run = next(p for p in found["big_plays"] if p["yards"] == 90)
    assert ps._big_play_sentence(run, found, 0, ps._Refs(found)) == "West Point's No. 33 had a 90-yard run in the first quarter."
    out = ps.write_story(found, sponsor_name="OxyCare Plus, Inc.")
    assert "brought to you by OxyCare Plus, Inc." in out["post_text"] and "Inc.." not in out["post_text"]


def test_story_leaves_out_running_scores_that_do_not_add_up() -> None:
    out = ps.write_story(facts(broadcast={**BROADCAST, "final_home_score": 28}))
    assert "to make it" not in out["story"] and "putting" not in out["story"]
    assert "West Point 7-0" not in "\n".join(out["scoring"])


def test_card_is_the_light_newspaper_look() -> None:
    document = postgame_card.render_card_html(
        facts(), headline="West Point beats Caledonia, 21-10", deck="Lede.", station_name="WSN",
        logos={"home": "data:image/png;base64,AA==", "visitor": ""}, sponsor_name="Main Street Hardware",
    )
    assert "--paper: #f3efe5" in document and "grayscale(1)" in document
    assert "WSN Sports" in document and "West Point beats Caledonia, 21-10" in document
    assert 'class="line-score"' in document and "Brought to you by" in document
    assert "Key Plays" in document and "Standouts" in document
    no_line = postgame_card.render_card_html(facts(broadcast={**BROADCAST, "final_home_score": 28}),
                                             headline="x", station_name="WSN")
    assert 'class="line-score"' not in no_line


@pytest.fixture
def postgame_client(monkeypatch: pytest.MonkeyPatch):
    broadcasts = [copy.deepcopy(BROADCAST)]
    rosters = [{"school_id": "west-point", "players": ROSTERS["home"]}, {"school_id": "caledonia", "players": ROSTERS["visitor"]}]
    monkeypatch.setattr(app_module, "SOCIAL_MEDIA_PREVIEW_SERVICE", None, raising=False)
    monkeypatch.setattr(app_module, "pin_is_configured", lambda: True)
    monkeypatch.setattr(app_module, "load_broadcasts", lambda: copy.deepcopy(broadcasts))
    monkeypatch.setattr(app_module, "load_state", lambda: {})
    monkeypatch.setattr(app_module, "load_broadcast_live_state", lambda broadcast_id: None)
    monkeypatch.setattr(app_module, "load_final_state_archive", lambda broadcast_id: {"events": [{"id": "e"}], "plays": [{"id": "p"}]})
    monkeypatch.setattr(app_module, "build_statistics", lambda state: statistics())
    monkeypatch.setattr(app_module, "load_rosters", lambda: copy.deepcopy(rosters))
    monkeypatch.setitem(app_module.app.config, "TESTING", True)
    monkeypatch.setitem(app_module.app.config, "SECRET_KEY", "postgame-story-route-test")
    with app_module.app.test_client() as client:
        with client.session_transaction() as active_session:
            active_session["authenticated"] = True
        yield client
    app_module.SOCIAL_MEDIA_PREVIEW_SERVICE = None


def test_story_route_returns_the_written_story(postgame_client) -> None:
    response = postgame_client.get(f"/api/broadcasts/{BROADCAST_ID}/postgame-story?variant=2")
    assert response.status_code == 200
    data = response.get_json()
    assert data["story"]["variant"] == 2 and data["story"]["writer"] == "built-in"
    assert data["story"]["headline"].endswith("21-10")
    assert data["scores_reliable"] is True
    assert postgame_client.get("/api/broadcasts/NOPE/postgame-story").status_code == 404


def test_story_route_needs_recorded_plays(postgame_client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(app_module, "build_statistics", lambda state: {})
    response = postgame_client.get(f"/api/broadcasts/{BROADCAST_ID}/postgame-story")
    assert response.status_code == 409 and response.get_json()["error"] == "NO_GAME_DATA"


def test_card_route_renders_a_real_png(postgame_client) -> None:
    response = postgame_client.get(f"/api/broadcasts/{BROADCAST_ID}/postgame-story.png?headline=Custom+headline")
    assert response.status_code == 200 and response.mimetype == "image/png"
    assert response.data[:8] == b"\x89PNG\r\n\x1a\n"
    from PIL import Image
    import io
    assert Image.open(io.BytesIO(response.data)).size == (1080, 1350)


def test_watch_link_is_the_public_page_not_the_producer_link(postgame_client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(app_module, "load_config", lambda: {
        "organization": {"short_name": "WSN"},
        "streaming": {"facebook_live": "https://www.facebook.com/live/producer/v2/?target_id=1"},
        "social": {"facebook": "https://www.facebook.com/wsn"},
    })
    post = postgame_client.get(f"/api/broadcasts/{BROADCAST_ID}/postgame-story").get_json()["story"]["post_text"]
    assert "Watch the full game: https://www.facebook.com/wsn" in post
    assert "producer" not in post


def test_requires_login() -> None:
    with app_module.app.test_client() as client:
        assert client.get(f"/api/broadcasts/{BROADCAST_ID}/postgame-story").status_code == 401
