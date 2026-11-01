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
    assert script["title"]["kicker"] == "CALEDONIA AT WEST POINT"
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

    season = reel_client.get("/api/reel-plays").get_json()
    assert [g["broadcast_id"] for g in season["games"]] == [BROADCAST_ID]
    assert {d["id"] for d in season["dances"]} == set(rs.DANCES)
    play = next(p for p in season["games"][0]["plays"] if p["kind"] == "run" and p["td"])
    assert reel_client.get(f"/api/broadcasts/{BROADCAST_ID}/reel.mp4?play=nope").status_code == 404
    response = reel_client.get(f"/api/broadcasts/{BROADCAST_ID}/reel.mp4?play={play['id']}")
    assert response.status_code == 200 and response.mimetype == "video/mp4"
    assert response.data.find(b"moov") < response.data.find(b"mdat")   # fast start, as Facebook asks for
    container = av.open(io.BytesIO(response.data))
    stream = container.streams.video[0]
    assert (stream.width, stream.height) == (1080, 1920) and stream.codec_context.name == "h264"
    assert 8 < float(stream.duration * stream.time_base) < 20


def test_reels_need_login() -> None:
    with app_module.app.test_client() as client:
        assert client.get("/api/reel-plays").status_code == 401


def _service(monkeypatch, sponsors, rng=None):
    import random
    monkeypatch.setattr(app_module, "SOCIAL_MEDIA_PREVIEW_SERVICE", None, raising=False)

    class Sponsors:
        def __init__(self):
            self.asked = []

        def list_payload(self, sport=""):
            self.asked.append(sport)
            return {"sponsors": [s for s in sponsors if not sport or s.get("sport", "") in ("", sport.casefold())]}

    holder = Sponsors()
    monkeypatch.setattr(app_module, "get_sponsor_service", lambda: holder)
    service = app_module.get_social_media_preview_service()
    service._rng = rng or random.Random(4)
    return service, holder


def test_random_sponsor_comes_from_the_games_sport(monkeypatch) -> None:
    sponsors = [{"id": "a", "name": "Alpha", "sport": "football", "active": True},
                {"id": "b", "name": "Bravo", "sport": "basketball", "active": True},
                {"id": "c", "name": "Charlie", "sport": "", "active": True}]
    service, holder = _service(monkeypatch, sponsors)
    picks = {service._reel_sponsor({"sport": "Football"}, "random")["name"] for _ in range(30)}
    assert picks == {"Alpha", "Charlie"} and holder.asked[-1] == "Football"
    assert service._reel_sponsor({"sport": "Football"}, "none") is None
    assert service._reel_sponsor({"sport": "Football"}, "a")["name"] == "Alpha"
    app_module.SOCIAL_MEDIA_PREVIEW_SERVICE = None


def test_script_carries_the_dance_and_the_page_knows_every_dance() -> None:
    found = facts()
    play = rs.plays(found)[0]
    assert rs.script(found, play, broadcast=BROADCAST, dance="robot")["dance"] == "robot"
    assert rs.script(found, play, broadcast=BROADCAST, dance="nope")["dance"] == "shimmy"
    page = reel_render.page(rs.script(found, play, broadcast=BROADCAST))
    for name in rs.DANCES:
        assert f"{name}: b =>" in page


def test_reel_footer_uses_the_station_logo_in_the_chosen_style() -> None:
    found = facts()
    script = rs.script(found, rs.plays(found)[0], broadcast=BROADCAST, station_name="WSN",
                       station_logo="data:image/png;base64,AAAA", logo_style="glass")
    document = reel_render.page(script)
    assert "data:image/png;base64,AAAA" in document
    assert '"logo_style": "glass"' in document or '"logo_style":"glass"' in document
    assert "stationClip" in document and "stationGlass" in document


def _themed_page(theme, home, visitor, team="visitor"):
    found = facts()
    play = {**rs.plays(found)[0], "team": team}
    return reel_render.page(rs.script(found, play, broadcast=BROADCAST, theme=theme, colors={"home": home, "visitor": visitor}))


def _uniforms(page, document):
    errors = []
    page.on("pageerror", lambda error: errors.append(error.message))
    page.set_content(document, wait_until="load")
    page.evaluate("window.reelReady")
    page.evaluate("window.drawFrame(window.REEL_DURATION * .7)")
    assert errors == []
    return page.evaluate("[OFFU, DEFU, TH]")


def test_every_theme_draws_and_teams_wear_their_own_colors() -> None:
    from playwright.sync_api import sync_playwright

    assert set(rs.THEMES) == {"paper", "neon", "chalk", "comic"}
    caledonia = {"primary": "#810909", "secondary": "#ffffff"}
    lafayette = {"primary": "#9a1c1f", "secondary": "#ffffff"}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1080, "height": 1920})
        for theme in rs.THEMES:
            offense, defense, drawn = _uniforms(browser.new_page(viewport={"width": 1080, "height": 1920}), _themed_page(theme, caledonia, lafayette))
            assert drawn == theme
            assert defense == {"main": "#810909", "accent": "#ffffff"}     # home: primary with secondary
            assert offense == {"main": "#ffffff", "accent": "#9a1c1f"}     # away: secondary with primary
        # both secondaries are white here, so away stays in its primary rather than clash
        offense, defense, _ = _uniforms(page, _themed_page("paper", {"primary": "#ffffff", "secondary": "#102a6b"}, {"primary": "#b5121b", "secondary": "#ffffff"}))
        assert defense["main"] == "#ffffff" and offense == {"main": "#b5121b", "accent": "#ffffff"}
        browser.close()

