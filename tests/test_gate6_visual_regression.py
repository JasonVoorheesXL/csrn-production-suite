from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _scorebug_fragment(overlay: str) -> str:
    start = overlay.index('<div id="scorebug"')
    end = overlay.index('<div id="eventTicker"', start)
    return overlay[start:end]


def test_scorebug_identity_order_places_record_below_mascot() -> None:
    overlay = (ROOT / "templates" / "overlay.html").read_text(encoding="utf-8")
    scorebug = _scorebug_fragment(overlay)

    home_name = scorebug.index('id="homeName"')
    home_mascot = scorebug.index('id="homeMascot"')
    home_record = scorebug.index('id="homeRecord"')
    visitor_name = scorebug.index('id="visitorName"')
    visitor_mascot = scorebug.index('id="visitorMascot"')
    visitor_record = scorebug.index('id="visitorRecord"')

    assert home_name < home_mascot < home_record
    assert visitor_name < visitor_mascot < visitor_record
    assert scorebug.count('class="name-wrap"') == 2


def test_empty_identity_rows_collapse_without_geometry_changes() -> None:
    overlay = (ROOT / "templates" / "overlay.html").read_text(encoding="utf-8")

    assert ".mascot:empty{display:none}" in overlay
    assert ".team-record:empty{display:none}" in overlay
    assert "grid-template-columns:484px 174px 484px;height:112px" in overlay
    assert "grid-template-columns:738px 248px 738px;height:224px" in overlay


def test_score_elements_remain_outside_identity_stacks() -> None:
    overlay = (ROOT / "templates" / "overlay.html").read_text(encoding="utf-8")
    scorebug = _scorebug_fragment(overlay)

    home_stack_end = scorebug.index('</div><div id="homeScore"')
    visitor_score = scorebug.index('id="visitorScore"')
    visitor_stack = scorebug.index('<div class="name-wrap">', visitor_score)

    assert scorebug.index('id="homeRecord"') < home_stack_end
    assert visitor_score < visitor_stack
    assert scorebug.index('id="visitorRecord"') > visitor_stack


def test_gate6_overlay_revision_is_published_consistently() -> None:
    overlay = (ROOT / "templates" / "overlay.html").read_text(encoding="utf-8")
    app = (ROOT / "app.py").read_text(encoding="utf-8")

    assert "const OVERLAY_SCHEMA_REVISION='gate6-visual-regression-v1';" in overlay
    assert 'OVERLAY_SCHEMA_REVISION = "gate6-visual-regression-v1"' in app


def test_gate5_record_rendering_rules_remain_unchanged() -> None:
    overlay = (ROOT / "templates" / "overlay.html").read_text(encoding="utf-8")

    assert "function structuredRecord(value)" in overlay
    assert "return ties?`${wins}-${losses}-${ties}`:`${wins}-${losses}`" in overlay
    assert "official&&Boolean(state.region_game)" in overlay
    assert "return region?`${overall} • REG ${region}`:overall" in overlay
    assert "scorebugRecord(s,'home')" in overlay
    assert "scorebugRecord(s,'visitor')" in overlay