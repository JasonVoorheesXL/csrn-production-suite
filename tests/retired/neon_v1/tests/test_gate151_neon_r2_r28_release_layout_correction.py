from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def test_diamond_linescore_is_full_width_and_player_details_move_to_team_panels() -> None:
    js = (ROOT / "static" / "csrn-neon-r2-engine.js").read_text(encoding="utf-8")
    css = (ROOT / "static" / "csrn-neon-r2-engine.css").read_text(encoding="utf-8")
    assert "function teamPanelDetail" in js
    assert "ON THE MOUND" in js
    assert '<div class="n2-sport-deck n2-diamond-deck"><table' in js
    assert "grid-template-columns:265px" not in css.split("Gate 15.1 R28")[-1]
    assert ".n2-linescore .team-col{width:220px}" in css
    assert ".n2-linescore th,.n2-linescore td{font-size:25px" in css


def test_basketball_removes_shot_clock_and_possession_and_enlarges_team_text() -> None:
    js = (ROOT / "static" / "csrn-neon-r2-engine.js").read_text(encoding="utf-8")
    css = (ROOT / "static" / "csrn-neon-r2-engine.css").read_text(encoding="utf-8")
    basketball = js[js.index("function basketballState"):js.index("function diamondState")]
    assert "SHOT" not in basketball
    assert "HOME BALL" not in basketball
    assert "VISITOR BALL" not in basketball
    assert "font-size:58px" in css
    assert "font-size:32px" in css


def test_football_uses_graphic_layer_large_ball_and_non_neon_endzone_logos() -> None:
    js = (ROOT / "static" / "csrn-neon-r2-engine.js").read_text(encoding="utf-8")
    css = (ROOT / "static" / "csrn-neon-r2-engine.css").read_text(encoding="utf-8")
    field = Image.open(ROOT / "static" / "neon-r2" / "football-field-base.png")
    assert field.size == (1500, 146)
    assert "endzoneIdentity(s.home)" in js
    assert "endzoneIdentity(s.visitor)" in js
    assert "football-field-base.png" in css
    assert "width:72px" in css and "height:42px" in css
    assert ".n2-endzone img" in css and "filter:none" in css


def test_baseball_clash_remains_implementation_size() -> None:
    image = Image.open(ROOT / "static" / "neon-r2" / "baseball-neutral.png")
    assert image.size == (1024, 640)


