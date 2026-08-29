from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")

def test_gate167_theme_owned_ticker_suppresses_legacy_for_the_whole_active_package():
    # Previously TICKER_ACTIVE_CLASS was toggled by whether the theme ticker
    # had something to scroll THIS tick -- so on a quiet play it came off and
    # the legacy #eventTicker flashed back in at the bottom of the screen.
    # An active production package owns the ticker slot regardless of content;
    # only deactivate() (package -> legacy fallback) releases it.
    js = read("static/csrn-production-theme-runtime.js")
    css = read("static/csrn-production-theme-runtime.css")
    assert 'TICKER_ACTIVE_CLASS = "csrn-production-theme-ticker-active"' in js
    assert "html.csrn-production-theme-ticker-active #eventTicker" in css

    # Ownership is asserted (add), never conditionally toggled off, on the
    # per-tick patch path and the full-render path.
    assert "classList.toggle(TICKER_ACTIVE_CLASS" not in js
    assert js.count("classList.add(TICKER_ACTIVE_CLASS)") == 2

    # deactivate() is the ONLY place the class is removed.
    assert js.count("classList.remove(TICKER_ACTIVE_CLASS)") == 0
    deactivate = js[js.index("function deactivate("):js.index("function deactivate(") + 700]
    assert "TICKER_ACTIVE_CLASS" in deactivate
    assert "SCORE_ACTIVE_CLASS" in deactivate  # removed together on fallback

def test_gate167_legacy_event_ticker_css_suppression_is_hard():
    # The legacy #eventTicker's own refresh() in overlay.html toggles the
    # .hidden CLASS (opacity:0). The theme suppression must beat that -- it is
    # display:none!important, not just visibility -- otherwise the legacy
    # ticker's opacity toggle could still show it per play.
    css = read("static/csrn-production-theme-runtime.css")
    block_start = css.index("html.csrn-production-theme-ticker-active #eventTicker{")
    block = css[block_start:block_start + 160]
    assert "display:none!important" in block


def test_gate167_patch_theme_ticker_still_bails_for_legacy_alias():
    # Legacy fallback must be untouched: when no approved package is active the
    # patch path returns immediately and never asserts TICKER_ACTIVE_CLASS.
    js = read("static/csrn-production-theme-runtime.js")
    fn = js[js.index("function patchThemeTicker(runtime) {"):]
    fn = fn[:fn.index("\n}\n") + 3]
    assert 'currentAlias === "legacy"' in fn
    assert fn.index('currentAlias === "legacy"') < fn.index("classList.add(TICKER_ACTIVE_CLASS)")


def test_gate167_theme_ticker_uses_frozen_visual_targets():
    js = read("static/csrn-production-theme-runtime.js")
    for selector in (
        ".bl-fns-ticker-led",
        ".bl-8bit-ticker-led",
        ".hp-wire-copy",
        ".n2-ticker span",
    ):
        assert selector in js

def test_gate167_legacy_ticker_is_not_used_as_theme_data_source():
    js = read("static/csrn-production-theme-runtime.js")
    assert "document.getElementById(\"tickerTrack\")" not in js
    assert "eventPlainText(runtime)" in js

def test_gate167_gate7_boundary_remains_intact():
    overlay = read("templates/overlay.html")
    for engine in (
        "csrn-broadcast-layout-engine.js",
        "csrn-friday-night-stadium-engine.js",
        "csrn-eight-bit-gameday-engine.js",
        "csrn-heritage-press-engine.js",
        "csrn-neon-r2-engine.js",
    ):
        assert engine not in overlay


