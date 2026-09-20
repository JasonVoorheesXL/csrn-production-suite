from pathlib import Path
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]


def test_one_shared_lower_assembly_owns_score_and_sport_deck() -> None:
    js = (ROOT / "static" / "csrn-neon-r2-engine.js").read_text(encoding="utf-8")
    css = (ROOT / "static" / "csrn-neon-r2-engine.css").read_text(encoding="utf-8")
    assert 'class="n2-lower-assembly"' in js
    assert ".n2-lower-assembly" in css
    assert ".n2-sport-deck" in css


def test_all_lower_content_stays_inside_1080_canvas() -> None:
    css = (ROOT / "static" / "csrn-neon-r2-engine.css").read_text(encoding="utf-8")
    # 738 + 292 = 1030, leaving a 50 px bottom safe margin.
    assert "top:730px;height:304px" in css
    assert "grid-template-rows:150px 146px;gap:8px" in css


def test_diamond_linescore_is_a_real_table_with_fixed_columns() -> None:
    js = (ROOT / "static" / "csrn-neon-r2-engine.js").read_text(encoding="utf-8")
    css = (ROOT / "static" / "csrn-neon-r2-engine.css").read_text(encoding="utf-8")
    assert '<table class="n2-linescore">' in js
    assert "<thead><tr>" in js and "<tbody>" in js
    assert 's.sport==="baseball"?9:7' in js
    assert "table-layout:fixed" in css
    assert ".team-col{width:128px}" in css
    assert ".rhe{width:38px}" in css


def test_basketball_fouls_and_bonus_belong_to_team_score_sections() -> None:
    js = (ROOT / "static" / "csrn-neon-r2-engine.js").read_text(encoding="utf-8")
    assert "function scoreSide(" in js
    assert "FOULS ${esc(fouls)}" in js
    assert "· BONUS" in js
    assert "n2-basket-side" not in js


def test_generic_chassis_no_longer_draws_obsolete_lower_boxes() -> None:
    for name in ("neon-frame-neutral-chassis.png", "neon-frame-neutral-highlights.png"):
        image = Image.open(ROOT / "static" / "neon-r2" / name).convert("RGBA")
        alpha = image.getchannel("A")
        interior = alpha.crop((28, 720, image.width - 28, image.height - 28))
        assert interior.getbbox() is None, name


