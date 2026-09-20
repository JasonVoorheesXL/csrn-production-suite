from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_neon_r2_separates_raw_team_color_from_bright_display_color() -> None:
    js = (ROOT / "static" / "csrn-neon-r2-engine.js").read_text(encoding="utf-8")
    assert "function neonColor(" in js
    assert "--n2-left-raw:" in js
    assert "--n2-right-raw:" in js
    assert "--n2-left:${neonColor(" in js
    assert "--n2-right:${neonColor(" in js


def test_neon_r2_uses_wide_bloom_and_hot_core() -> None:
    css = (ROOT / "static" / "csrn-neon-r2-engine.css").read_text(encoding="utf-8")
    assert "blur(10px)" in css
    assert "drop-shadow(0 0 36px var(--n2-left))" in css
    assert "color-mix(in srgb,var(--n2-left) 72%,white)" in css
    assert "drop-shadow(0 0 24px var(--n2-left))" in css
    assert "background-color:color-mix(in srgb,var(--n2-left) 88%,white)" in css
    assert "background-color:color-mix(in srgb,var(--n2-right) 88%,white)" in css
    assert "opacity:.82" in css
    assert "brightness(1.18)" in css


def test_clash_uses_bright_display_neon_while_raw_team_colors_remain_available() -> None:
    css = (ROOT / "static" / "csrn-neon-r2-engine.css").read_text(encoding="utf-8")
    js = (ROOT / "static" / "csrn-neon-r2-engine.js").read_text(encoding="utf-8")
    assert "var(--n2-left) 88%,white" in css
    assert "var(--n2-right) 88%,white" in css
    assert "--n2-left-raw:" in js
    assert "--n2-right-raw:" in js
    assert "leftRaw" in js and "rightRaw" in js


