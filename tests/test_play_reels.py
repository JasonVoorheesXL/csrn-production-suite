"""Paper-cutout play reels (Social Publishing, 2026-11-01)."""
from __future__ import annotations

import copy
import io

import pytest

import app as app_module
import reel_render
import reel_story as rs
from tests.test_postgame_story import BROADCAST, BROADCAST_ID, ROSTERS, facts, statistics


def test_reel_plays_are_the_scores_and_big_plays_with_a_named_player() -> None:
    plays = rs.plays(facts())
    labels = [p["label"] for p in plays]
    assert "Q1 · West Point · Kingston Branham 20-yd TD run" in labels
    assert "Q2 · West Point · Jaylen Hall 63-yd TD run" in labels
    assert "Q4 · Caledonia · Caleb Lang 47-yd TD catch from Watrous" in labels
    assert any(p["kind"] == "kickoff_return" and p["team"] == "visitor" for p in plays)
    assert all(not (p["player"] or {}).get("unknown") for p in plays)
    assert any(p["kind"] == "field_goal" and p["player"]["name"] == "Finn Stubbendorff" for p in plays)
    assert len({p["id"] for p in plays}) == len(plays)


def test_geometry_trusts_the_yardage_on_a_touchdown() -> None:
    td = rs._geometry("run", "home", 63, {"ball_spot": "RIGHT 20"}, {}, True)
    assert td == {"los": 37.0, "start": 37.0, "end": 100.0}
    gain = rs._geometry("run", "home", 25, None, {}, False)
    assert gain["end"] - gain["start"] == 25
    pass_play = rs._geometry("pass", "home", 40, None, {}, True)
    assert pass_play["start"] < pass_play["catch"] < pass_play["end"] == 100.0
    events = {"e": {"before": {"home_direction": "right", "visitor_direction": "left"}}}
    kick = rs._geometry("kickoff_return", "visitor", 41, {"event_id": "e", "landing_spot": "RIGHT 5", "ball_spot": "LEFT 40"}, events, False)
    assert kick["catch"] == 5.0 and kick["end"] == 46.0


def test_script_has_the_title_captions_and_the_recreation_label() -> None:
    found = facts()
    play = next(p for p in rs.plays(found) if "63-yd TD run" in p["label"])
    broadcast = {**BROADCAST, "week": "9"}
    script = rs.script(found, play, broadcast=broadcast, station_name="WSN", sponsor_name="Main Street Hardware",
                       colors={"home": {"primary": "#0b6b3a"}, "visitor": {"primary": "#b5121b"}})
    assert script["title"]["kicker"] == "WEEK 9 · CALEDONIA AT WEST POINT"
    assert script["title"]["name"] == "Jaylen Hall" and script["title"]["line"] == "63-yard touchdown run"
    assert [c["text"] for c in script["captions"]] == ["Hall takes the handoff", "Hall breaks free!", "TOUCHDOWN!"]
    assert script["score_after"] == "Caledonia 3, West Point 14"
    assert script["label"] == "Animated recreation from the official stats"
    html = reel_render.page({**script, "title": {**script["title"], "name": "</script><b>x"}})
    assert "</script><b>" not in html  # a name can't break out of the page's script


@pytest.fixture
def reel_client(monkeypatch: pytest.MonkeyPatch):
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
    monkeypatch.setitem(app_module.app.config, "SECRET_KEY", "reel-route-test")
    with app_module.app.test_client() as client:
        with client.session_transaction() as active_session:
            active_session["authenticated"] = True
        yield client
    app_module.SOCIAL_MEDIA_PREVIEW_SERVICE = None


def test_reel_routes_list_plays_and_return_a_real_vertical_mp4(reel_client) -> None:
    import av

    plays = reel_client.get(f"/api/broadcasts/{BROADCAST_ID}/reel-plays").get_json()["plays"]
    play = next(p for p in plays if p["kind"] == "run" and p["td"])
    assert reel_client.get(f"/api/broadcasts/{BROADCAST_ID}/reel.mp4?play=nope").status_code == 404
    response = reel_client.get(f"/api/broadcasts/{BROADCAST_ID}/reel.mp4?play={play['id']}")
    assert response.status_code == 200 and response.mimetype == "video/mp4"
    container = av.open(io.BytesIO(response.data))
    stream = container.streams.video[0]
    assert (stream.width, stream.height) == (1080, 1920) and stream.codec_context.name == "h264"
    assert 8 < float(stream.duration * stream.time_base) < 20


def test_reels_need_login() -> None:
    with app_module.app.test_client() as client:
        assert client.get(f"/api/broadcasts/{BROADCAST_ID}/reel-plays").status_code == 401
