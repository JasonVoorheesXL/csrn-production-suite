"""2026-09-02 hotfix: renderSelected() reported CSRNProductionThemeBindingState
.tickerActive from an undeclared variable, throwing a ReferenceError that the
catch swallowed as "theme binding blocked" -- the Game Overlay stayed a white
screen for the whole production theme.
"""
from pathlib import Path

RUNTIME = (
    Path(__file__).resolve().parents[1] / "static" / "csrn-production-theme-runtime.js"
).read_text(encoding="utf-8")


def _render_selected_body() -> str:
    start = RUNTIME.index("async function renderSelected()")
    end = RUNTIME.index("async function scheduleRenderSelected(", start)
    return RUNTIME[start:end]


def test_ticker_active_is_declared_before_it_is_reported() -> None:
    body = _render_selected_body()
    decl = body.index("const tickerActive = activateThemeTicker(")
    use = body.index("\n      tickerActive,\n")  # inside the Object.freeze payload
    assert decl < use, "tickerActive must be declared before the binding-state build"


def test_ticker_active_binds_the_theme_ticker_result() -> None:
    body = _render_selected_body()
    # exactly one declaration, wired to the activate call (not a bare literal)
    assert body.count("const tickerActive =") == 1
    assert "const tickerActive = activateThemeTicker(" in body
