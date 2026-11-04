"""Basketball reels, reel headshots and player heads on reels."""
from __future__ import annotations

import io
import re
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

import hoop_reel_render
import hoop_reel_story as story
import reel_headshot
import reel_render
import reel_story

ROOT = Path(__file__).resolve().parents[1]
NAMES = {"home": {f"h{i}": {"name": f"Home Player{i}", "last": f"Player{i}", "number": str(10 + i)} for i in range(6)},
         "visitor": {f"v{i}": {"name": f"Away Guy{i}", "last": f"Guy{i}", "number": str(30 + i)} for i in range(6)}}
TEAMS = {"home": "Caledonia", "visitor": "Lafayette"}


def event(event_id, event_type, voided=False, **payload):
    return {"event_id": event_id, "event_type": event_type, "payload": payload, "voided": voided}


def game():
    return {"hoops": {"hoops_events": [
        event("a", "LINEUP_SET", team="home", playerIds=["h0", "h1", "h2", "h3", "h4"]),
        event("b", "LINEUP_SET", team="visitor", playerIds=["v0", "v1", "v2", "v3", "v4"]),
        event("s1", "SHOT", team="home", made=True, points=3, shooterId="h0", spotX=60, spotY=12, zone="left_wing_three", period="2", clockSeconds=200),
        event("n1", "PLAY_NOTE", targetEventId="s1", assistId="h1"),
        event("m1", "SHOT", team="visitor", made=False, points=2, shooterId="v0", period="2"),
        event("gone", "SHOT", voided=True, team="home", made=True, points=2, shooterId="h2"),
        event("f1", "FREE_THROW", team="visitor", made=True),
        event("sub", "SUBSTITUTION", team="home", outPlayerId="h4", inPlayerId="h5"),
        event("s2", "SHOT", team="home", made=True, points=2, shooterId="h5", spotX=77, spotY=25, zone="rim", period="3"),
        event("foul", "FOUL", team="visitor", andOne=True, drewFoulOn="h5"),
        event("s3", "SHOT", team="visitor", made=False, points=2, shooterId="v1", spotX=70, spotY=30, period="3"),
        event("n3", "PLAY_NOTE", targetEventId="s3", blockPlayerId="h3"),
        event("t1", "TURNOVER", team="visitor", stealPlayerId="h2", period="4"),
        event("n4", "PLAY_NOTE", targetEventId="t1", turnoverPlayerId="v2"),
        event("s4", "SHOT", team="home", made=True, points=2, shooterId="stranger"),
    ]}}


def test_only_makes_blocks_and_steals_by_known_players_become_reels() -> None:
    plays = story.plays(game(), NAMES, TEAMS)
    assert [(p["id"], p["kind"]) for p in plays] == [("s1", "three"), ("s2", "layup"), ("s3", "block"), ("t1", "steal")]
    assert plays[0]["label"] == "Q2 · Caledonia · Home Player0 3-pointer, assist Player1"
    assert plays[0]["helper"]["id"] == "h1"


def test_the_score_lineup_and_and_one_are_the_ones_at_that_moment() -> None:
    plays = story.plays(game(), NAMES, TEAMS)
    assert plays[0]["score"] == {"home": 3, "visitor": 0}
    assert plays[1]["score"] == {"home": 5, "visitor": 1}
    assert plays[0]["floor"]["home"][-1] == "h4" and plays[1]["floor"]["home"][-1] == "h5"
    assert plays[1]["and_one"] and not plays[0]["and_one"] and plays[1]["label"].endswith("(and one)")


def test_the_player_on_the_wrong_end_is_never_named_and_blocks_credit_the_blocker() -> None:
    plays = story.plays(game(), NAMES, TEAMS)
    block, steal = plays[2], plays[3]
    assert block["team"] == "home" and block["player"]["id"] == "h3" and block["other_number"] == "31"
    assert steal["player"]["id"] == "h2" and steal["other_number"] == "32"
    for play in (block, steal):
        built = story.script(play, teams=TEAMS, names=NAMES)
        words = str(built["title"]) + str(built["captions"])
        assert "Guy" not in words


def test_a_spot_in_the_far_half_is_turned_around_and_a_missing_one_gets_a_default() -> None:
    assert story._spot({"spotX": 20, "spotY": 10}, "jumper") == {"x": 64.0, "y": 40.0}
    assert story._spot({}, "three") == {"x": 60.0, "y": 25.0}


def test_heads_only_reach_the_figures_they_are_asked_for() -> None:
    play = story.plays(game(), NAMES, TEAMS)[0]
    head = lambda side, pid: f"head-{side}-{pid}"
    off = story.script(play, teams=TEAMS, names=NAMES)
    assert not off["hero"]["head"] and not off["helper"]["head"] and not any(t["head"] for t in off["teammates"])
    featured = story.script(play, teams=TEAMS, names=NAMES, featured_head=head)
    assert featured["hero"]["head"] == "head-home-h0" and featured["helper"]["head"] == "head-home-h1"
    assert not any(t["head"] for t in featured["teammates"])
    team = story.script(play, teams=TEAMS, names=NAMES, featured_head=head, team_head=head)
    assert [t["head"] for t in team["teammates"]] == ["head-home-h2", "head-home-h3", "head-home-h4"]
    assert not any(o.get("head") for o in team["opponents"])


def test_the_basketball_page_keeps_its_shared_pieces_and_has_no_shot_clock() -> None:
    script = story.script(story.plays(game(), NAMES, TEAMS)[0], teams=TEAMS, names=NAMES)
    page = hoop_reel_render.page({**script, "title": {**script["title"], "name": "</script><b>x"}})
    assert "__SCRIPT__" not in page and "__DANCES__" not in page and "</script><b>" not in page
    assert "window.reelReady" in page and "const PAL =" in page and "const word = S.word;" in page
    assert "shot clock" not in page.lower()
    assert "goal posts" not in page


def test_every_dance_on_offer_exists_on_the_page_and_none_borrows_a_game_name() -> None:
    for key in reel_story.DANCES:
        assert re.search(rf"\b{key}: b =>", reel_render.DANCE_MOVES), key
    labels = " ".join(reel_story.DANCES.values()).lower()
    for borrowed in ("floss", "orange justice", "default dance", "take the l", "fortnite"):
        assert borrowed not in labels


def test_football_only_passes_a_head_for_players_who_have_one() -> None:
    assert "putFace(hero, S.hero.head);" in reel_render.PAGE
    assert "if (kind === 'pass') putFace(passer, S.passer.head);" in reel_render.PAGE
    assert "TH === 'chalk') return;" in reel_render.PAGE


def photo(background=(120, 130, 140), size=(600, 800), mode="JPEG"):
    image = Image.new("RGB", size, background)
    draw = ImageDraw.Draw(image)
    draw.ellipse((220, 120, 380, 330), fill=(180, 120, 90))
    draw.rectangle((100, 420, 500, 800), fill=(130, 10, 10))
    buffer = io.BytesIO()
    image.save(buffer, mode)
    return buffer.getvalue()


OVAL = {"x": 0.5, "y": 0.28, "width": 0.45, "height": 0.42}


def corners_clear(png: bytes) -> bool:
    image = Image.open(io.BytesIO(png)).convert("RGBA")
    return all(image.getpixel(p)[3] == 0 for p in ((0, 0), (image.width - 1, 0)))


def background_share(png: bytes, colour=(120, 130, 140)) -> float:
    pixels = np.asarray(Image.open(io.BytesIO(png)).convert("RGBA")).astype(int)
    near = np.abs(pixels[..., :3] - np.array(colour)).sum(axis=2) < 30
    return float((near & (pixels[..., 3] > 200)).mean())


def test_the_background_goes_and_the_face_stays() -> None:
    cut = reel_headshot.cut_head(photo(), **OVAL)
    done = Image.open(io.BytesIO(cut.png)).convert("RGBA")
    assert max(done.size) == reel_headshot.OUTPUT_SIZE and corners_clear(cut.png)
    assert background_share(cut.png) < 0.02
    assert done.getpixel((done.width // 2, done.height // 2))[:3] != (120, 130, 140)


def test_tolerance_zero_keeps_the_plain_oval() -> None:
    assert background_share(reel_headshot.cut_head(photo(), tolerance=0, **OVAL).png) > 0.2


def test_a_setting_strong_enough_to_reach_the_face_falls_back_to_the_oval() -> None:
    cut = reel_headshot.cut_head(photo(background=(180, 120, 90)), tolerance=120, **OVAL)
    assert Image.open(io.BytesIO(cut.png)).getbbox()


def test_a_transparent_png_keeps_its_own_cut_out() -> None:
    image = Image.new("RGBA", (400, 400), (0, 0, 0, 0))
    ImageDraw.Draw(image).ellipse((100, 100, 300, 300), fill=(180, 120, 90, 255))
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    cut = reel_headshot.cut_head(buffer.getvalue(), x=0.5, y=0.5, width=0.9, height=0.9)
    assert corners_clear(cut.png) and background_share(cut.png, (0, 0, 0)) == 0


def test_bad_oval_numbers_do_not_break_the_cut() -> None:
    assert reel_headshot.cut_head(photo(), x="nan", y="", width=None, height="abc", tolerance="x").png


def test_a_small_head_is_flagged() -> None:
    assert reel_headshot.cut_head(photo(size=(600, 800)), x=0.5, y=0.3, width=0.1, height=0.08).low_resolution


def test_the_reel_headshot_is_saved_apart_and_removed_cleanly(tmp_path: Path) -> None:
    from support_media_service import SupportMediaService

    rosters = [{"id": "r", "players": [{"id": "p", "headshot": "/roster-headshots/on-air.png"}]}]
    saved = []
    service = SupportMediaService.__new__(SupportMediaService)
    service._headshots_dir = tmp_path
    service._load_rosters = lambda: rosters
    service._save_rosters = lambda data: saved.append(True)
    result = service.save_reel_headshot("r", "p", original_filename="a.jpg", raw=photo(), **OVAL)
    assert result.code == "OK" and result.data["reel_headshot"] == "/roster-headshots/reel__r__p.png"
    assert (tmp_path / "reel__r__p.png").is_file() and saved
    assert rosters[0]["players"][0]["headshot"] == "/roster-headshots/on-air.png"
    assert service.save_reel_headshot("r", "nobody", original_filename="a.jpg", raw=photo(), **OVAL).code == "PLAYER_NOT_FOUND"
    assert service.save_reel_headshot("r", "p", original_filename="a.gif", raw=photo(), **OVAL).code == "UNSUPPORTED_IMAGE_TYPE"
    assert service.remove_reel_headshot("r", "p").code == "OK"
    assert not (tmp_path / "reel__r__p.png").exists() and "reel_headshot" not in rosters[0]["players"][0]


def test_the_screens_offer_it() -> None:
    social = (ROOT / "templates" / "social_manager.html").read_text(encoding="utf-8")
    assert 'id="reelSport"' in social and 'id="reelHeads"' in social and "heads:byId('reelHeads').value" in social
    page = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    assert "reelHeadOpen(this.files[0])" in page and "csrn-reel-headshot.js" in page and "reelHeadShow();" in page
