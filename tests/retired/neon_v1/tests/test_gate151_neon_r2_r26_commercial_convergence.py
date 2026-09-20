from pathlib import Path
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]


def test_football_field_uses_two_distributed_number_rows() -> None:
    js = (ROOT / "static" / "csrn-neon-r2-engine.js").read_text(encoding="utf-8")
    css = (ROOT / "static" / "csrn-neon-r2-engine.css").read_text(encoding="utf-8")
    assert "endzoneIdentity(s.home)" in js
    assert "endzoneIdentity(s.visitor)" in js
    assert "n2-field-grid" in js
    assert "football-field-base.png" in css
    assert "102030405040302010" not in js


def test_diamond_score_center_has_exactly_three_bases() -> None:
    js = (ROOT / "static" / "csrn-neon-r2-engine.js").read_text(encoding="utf-8")
    assert "b.slice(0,3)" in js
    assert "${bases(s)}" in js
    css = (ROOT / "static" / "csrn-neon-r2-engine.css").read_text(encoding="utf-8")
    assert ".n2-bases i:nth-child(1)" in css
    assert ".n2-bases i:nth-child(2)" in css
    assert ".n2-bases i:nth-child(3)" in css


def test_line_score_has_fixed_columns_and_current_inning_highlight() -> None:
    js = (ROOT / "static" / "csrn-neon-r2-engine.js").read_text(encoding="utf-8")
    css = (ROOT / "static" / "csrn-neon-r2-engine.css").read_text(encoding="utf-8")
    assert 'class="${i+1===current?"current":""}"' in js
    assert "table-layout:fixed" in css
    assert ".team-col{width:146px}" in css
    assert ".rhe{width:42px}" in css


def test_lower_assembly_and_clash_opening_do_not_overlap() -> None:
    css = (ROOT / "static" / "csrn-neon-r2-engine.css").read_text(encoding="utf-8")
    assert ".n2-opening{top:120px;height:610px}" in css
    assert ".n2-lower-assembly{top:730px;height:304px;" in css


