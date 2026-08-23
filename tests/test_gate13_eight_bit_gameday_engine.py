from hashlib import sha256
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "static" / "csrn-eight-bit-gameday-engine.js"
CSS = ROOT / "static" / "csrn-eight-bit-gameday-engine.css"
LAB = (ROOT / "static" / "csrn-layout-lab.html").read_text(encoding="utf-8")
SOURCE = ENGINE.read_text(encoding="utf-8")
STYLE = CSS.read_text(encoding="utf-8")
BIBLE = (ROOT / "CSRN_PROJECT_BIBLE.md").read_text(encoding="utf-8")


def _digest(relative: str) -> str:
    return sha256((ROOT / relative).read_bytes()).hexdigest().upper()


def test_gate13_is_isolated_and_preserves_both_frozen_renderers() -> None:
    assert ENGINE.is_file() and CSS.is_file()
    assert _digest("static/csrn-broadcast-layout-engine.css") == "4641A675512EA8C92E1408E421B690F862B49EA509D1009903A5F0B5EFB655EF"
    assert _digest("static/csrn-broadcast-layout-engine.js") == "961E39C83C94C1F12194E2D984247E576E96916FB8E5D35BBEC77EFF5B5EA68D"
    assert _digest("static/csrn-friday-night-stadium-engine.css") == "C3E6F2A90E7E6080454D5DDE75387EFC09FB1BE0E4FA31B9732910D69FE5845C"
    assert _digest("static/csrn-friday-night-stadium-engine.js") == "454AE2B0A3C145D16E7C94816BEE2D66A459D67DDBF34C752CBAF03F10E32E39"


def test_gate13_lab_loads_and_routes_the_pixel_engine_once() -> None:
    assert LAB.count('csrn-eight-bit-gameday-engine.css?v=13.7') == 1
    assert LAB.count('csrn-eight-bit-gameday-engine.js?v=13.7') == 1
    assert "window.CSRNEightBitGamedayEngine" in LAB
    assert "packageId===pixelEngine.packageId?pixelEngine:" in LAB
    assert 'packageSelect.value="pixel_gameday"' in LAB
    assert LAB.count('csrn-friday-night-stadium-engine.css?v=12.6') == 1
    assert LAB.count('csrn-friday-night-stadium-engine.js?v=12.6') == 1


def test_gate13_owns_pixel_led_geometry_and_full_display_placement() -> None:
    assert 'const VERSION = "1.7.0"' in SOURCE
    assert 'const PACKAGE_ID = "pixel_gameday"' in SOURCE
    assert '<b>${esc(formatGameDate(state.scheduledDate))}</b><span>${esc(gameDesignation(state))}</span>' in SOURCE
    assert "const LED_GLYPHS = Object.freeze({" in SOURCE
    assert "function ledSvg(" in SOURCE and "<circle cx=" in SOURCE
    assert 'zone:"stadium-top-ticker",rect:{x:40,y:20,w:1840,h:62}' in SOURCE
    assert 'zone:"stadium-board",rect:{x:16,y:90,w:1888,h:958}' in SOURCE


def test_gate13_clash_athletes_use_two_live_uniform_materials() -> None:
    for sport in ("football", "basketball", "baseball", "softball"):
        relative = f"static/8bit-gameday/athletes/{sport}-athletes.png"
        assert (ROOT / relative).is_file()
        assert f'{sport}:"8bit-gameday/athletes/{sport}-athletes.png"' in SOURCE
    assert 'data-art-ready="pending"' in SOURCE
    assert "async function paintClash(root,state)" in SOURCE
    assert "function keyedMaterial(" in SOURCE
    assert 'return"visitorPrimary"' in SOURCE
    assert 'return"visitorSecondary"' in SOURCE
    assert 'return"homePrimary"' in SOURCE
    assert 'return"homeSecondary"' in SOURCE
    assert "function shadePixel(" in SOURCE
    assert "neutralShadowPixels" in SOURCE
    assert "recolored<5000||neutralShadows<250" in SOURCE


def test_gate13_sports_have_separate_backdrops_and_state_contracts() -> None:
    for sport in ("football", "basketball", "baseball", "softball"):
        assert f".bl-8bit-clash-{sport} .bl-8bit-field-art" in STYLE
    for relative in (
        "static/8bit-gameday/environments/football-stadium.png",
        "static/8bit-gameday/environments/basketball-gym.png",
        "static/8bit-gameday/environments/baseball-ballpark.png",
        "static/8bit-gameday/environments/softball-park.png",
    ):
        assert (ROOT / relative).is_file()
        assert relative.removeprefix("static/") in STYLE
    assert "function footballControls(" in SOURCE
    assert "<small>QUARTER</small>" in SOURCE
    assert "function basketballControls(" in SOURCE
    assert 'scoreText.padStart(3," ")' in SOURCE
    assert "function diamondControls(" in SOURCE
    for text in ("AT BAT", "PITCHING", "BALLS", "STRIKES", "OUTS"):
        assert text in SOURCE
    assert "VISITOR TOL" not in SOURCE and "HOME TOL" not in SOURCE
    assert 'identityPlate(team,side)' in SOURCE


def test_gate13_only_the_video_opening_switches_and_owns_captions() -> None:
    assert "function videoModeFor(" in SOURCE
    for mode in ('"clash"', '"highlight"', '"sponsor"', '"player"', '"broadcast"'):
        assert mode in SOURCE
    assert 'data-module="video.board"' in SOURCE
    assert 'state.captionsEnabled ? captionMarkup(state) : ""' in SOURCE
    assert ".bl-8bit-caption{" in STYLE
    assert "bottom:18px" in STYLE


def test_gate13_bible_locks_the_approved_contract() -> None:
    assert "Gate 13.0 — 8-Bit Gameday approved system contract" in BIBLE
    assert "Football does not track or display timeouts" in BIBLE
    assert "hardwood court without stadium-light clutter" in BIBLE
    assert "Gate 11.6 Neon and Gate 12.6 Friday" in BIBLE
    assert "authorizes no production migration" in BIBLE


def test_gate132_uses_the_approved_baseball_family_pixel_cabinet() -> None:
    assert "Gate 13.2 approved baseball-family pixel cabinet rebuild" in STYLE
    assert "grid-template-columns:370px minmax(0,1fr) 370px" in STYLE
    assert "border:10px solid #d7dde1" in STYLE
    assert "drop-shadow(0 0 8px currentColor)" in STYLE
    assert 'r=".42"' in SOURCE
    assert "if(v>.9)" not in SOURCE


def test_gate133_uses_generated_frame_mini_players_and_frozen_led_geometry() -> None:
    frame = ROOT / "static/8bit-gameday/frame/cabinet-frame.png"
    assert frame.is_file()
    assert 'url("8bit-gameday/frame/cabinet-frame.png")' in STYLE
    assert "Gate 13.3 generated approved-concept cabinet plate" in STYLE
    assert "function playerPortrait(" in SOURCE
    assert 'data-mini-player="${esc(side)}"' in SOURCE
    assert 'portrait.dataset.portraitReady="true"' in SOURCE
    assert "function sportIcon(" not in SOURCE
    assert SOURCE.count('<div class="bl-8bit-versus">') == 1
    stadium = (ROOT / "static/csrn-friday-night-stadium-engine.js").read_text(encoding="utf-8")
    pixel_glyphs = SOURCE.split("const LED_GLYPHS = Object.freeze(", 1)[1].split("  });", 1)[0]
    stadium_glyphs = stadium.split("const LED_GLYPHS = Object.freeze(", 1)[1].split("  });", 1)[0]
    assert pixel_glyphs == stadium_glyphs
    assert 'r=".42"' in SOURCE and 'r=".42"' in stadium
    assert "grid-template-columns:.8fr .9fr 1.15fr 1.15fr 1.3fr .8fr" in STYLE
    assert ".bl-8bit-ticker-led{min-width:0" in STYLE


def test_gate134_aligns_every_live_module_to_the_generated_openings() -> None:
    assert "Gate 13.4 exact generated-frame opening coordinates" in STYLE
    for coordinate in (
        "left:720px;top:64px;width:445px;height:108px",
        "top:193px;width:365px;height:520px",
        "left:32px",
        "left:1490px",
        "left:424px;top:193px;width:1035px;height:520px",
        "left:114px;top:738px;width:1658px;height:142px",
    ):
        assert coordinate in STYLE
    assert "grid-template-columns:355fr 125fr 229fr 223fr 257fr 150fr" in STYLE
    assert "function sportIcon(" not in SOURCE
    assert "CSRN</b><span>8-BIT GAMEDAY" not in SOURCE
    assert "<small>CLOCK</small>" in SOURCE
    assert "<small>BASES</small>" in SOURCE
    assert "bl-8bit-count-pair" in SOURCE
    assert 'state.sport==="softball"&&x>canvas.width*.86&&y<canvas.height*.2' in SOURCE
    corrected_softball = _digest("static/8bit-gameday/athletes/softball-athletes.png")
    assert corrected_softball == "868700C27899492234A8BE0CF09C9FC1BF8744C29A7EE4341AEB0C0D2124D658"


def test_gate137_owns_metadata_roles_and_legible_instrument_labels() -> None:
    assert "Gate 13.5 metadata marquee, identity possession, and legibility closeout" in STYLE
    assert "Gate 13.6 explicit lower-bank football possession" in STYLE
    assert "Gate 13.7 LED football possession closeout candidate" in STYLE
    assert "function formatGameDate(" in SOURCE
    assert "function gameDesignation(" in SOURCE
    for field in (
        "scheduledDate", "scheduled_date", "gameDate", "game_date",
        "contestType", "contest_type", "specialGameDesignations",
        "special_game_designations",
    ):
        assert field in SOURCE
    assert '"REGULAR SEASON"' in SOURCE
    assert 'state.specialGameDesignations=["RIVALRY"]' in LAB
    assert 'state.scheduledDate="2026-08-30"' in LAB
    assert '<small>PLAY CLOCK</small>' not in SOURCE
    assert 'class="bl-8bit-possession-cell"' in SOURCE
    assert '<small>POSSESSION</small>${ledSvg(state.game.possession==="visitor"?"VISITOR":"HOME","bl-8bit-possession-led")}' in SOURCE
    assert SOURCE.index('<small>POSSESSION</small>') < SOURCE.index('<small>BALL ON</small>')
    assert 'identityPlate(team,side,possessionBall(' not in SOURCE
    assert "bl-8bit-diamond-player-role" in SOURCE
    assert 'data-diamond-role="${esc(side)}"' in SOURCE
    assert "${playerPortrait(state.sport,side)}" not in SOURCE
    assert ".bl-8bit-diamond-role" not in SOURCE
    assert "font-size:24px" in STYLE
    assert "width:18px;height:18px;border-width:3px" in STYLE
    assert "font:900 29px/1" in STYLE
    assert "grid-template-columns:84px 46px" in STYLE
    assert "transform:translateX(-8px)" in STYLE
    assert ".bl-8bit-possession-led{width:280px;height:66px;color:#ffd21a" in STYLE


