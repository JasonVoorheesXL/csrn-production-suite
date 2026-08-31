from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")

def test_gate166_themed_scorebug_allows_only_scorebug_and_captions():
    # Relaxed Round 9 (2026-08-31): commit 9064c67 intentionally added captions
    # alongside the themed scorebug. The render contract now permits exactly
    # {scorebug, captions} -- scorebug always required, captions only when
    # state.captionsActive -- and still rejects any other component.
    js = read("static/csrn-production-theme-runtime.js")
    assert 'activeComponents:state.captionsActive ? ["scorebug", "captions"] : ["scorebug"]' in js
    assert 'scoreResult.components.includes("scorebug")' in js
    assert '!["scorebug", "captions"].includes(component)' in js
    assert "baselineComponents" not in js

def test_gate166_scorebug_suppression_contract_survives():
    js = read("static/csrn-production-theme-runtime.js")
    css = read("static/csrn-production-theme-runtime.css")
    assert 'SCORE_ACTIVE_CLASS = "csrn-production-theme-scorebug-active"' in js
    assert "classList.add(SCORE_ACTIVE_CLASS)" in js
    assert "html.csrn-production-theme-scorebug-active #scorebug" in css

def test_gate166_failure_still_restores_legacy():
    js = read("static/csrn-production-theme-runtime.js")
    assert 'deactivate("render-error")' in js
    assert "classList.remove(" in js


