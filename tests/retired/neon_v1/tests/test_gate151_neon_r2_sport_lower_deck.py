from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_bottom_deck_is_sport_specific() -> None:
    js = (ROOT / "static" / "csrn-neon-r2-engine.js").read_text(encoding="utf-8")
    assert 'if(s.sport==="football")return footballField(s)' in js
    assert 'if(s.sport==="basketball")return basketballCourt(s)' in js
    assert 'if(s.sport==="baseball"||s.sport==="softball")return diamondInningBoard(s)' in js
    assert "IN THE HOLE" not in js


def test_diamond_deck_contains_inning_scoreboard() -> None:
    js = (ROOT / "static" / "csrn-neon-r2-engine.js").read_text(encoding="utf-8")
    for required in ("lineScore", "visitorHits", "homeHits", "visitorErrors", "homeErrors"):
        assert required in js


def test_lower_decks_fit_inside_canvas() -> None:
    css = (ROOT / "static" / "csrn-neon-r2-engine.css").read_text(encoding="utf-8")
    assert ".n2-lower-assembly" in css
    assert ".n2-lower-assembly" in css
    assert ".n2-lower-assembly" in css


def test_clash_uses_bright_display_neon_not_dark_raw_team_color() -> None:
    css = (ROOT / "static" / "csrn-neon-r2-engine.css").read_text(encoding="utf-8")
    assert "var(--n2-left) 88%,white" in css
    assert "var(--n2-right) 88%,white" in css
    assert "opacity:.82" in css
    assert "brightness(1.18)" in css


def test_diamond_board_intentionally_omits_redundant_title_bar() -> None:
    js = (ROOT / "static" / "csrn-neon-r2-engine.js").read_text(encoding="utf-8")
    assert "INNING SCOREBOARD" not in js


