from pathlib import Path

import production_template_service as service


ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_collegiate_is_approved_for_production_template_host():
    assert "collegiate_traditional" in service.APPROVED_PACKAGE_IDS
    assert '"collegiate_traditional"' in read("static/csrn-production-theme-adapter.js")
    assert "collegiate_traditional: Object.freeze" in read("static/csrn-production-theme-runtime.js")
    assert '<option value="collegiate_traditional">Collegiate Tech</option>' in read("templates/index.html")
    assert 'collegiate_traditional: "Collegiate Tech"' in read("static/csrn-pregame-theme-selector.js")


def test_collegiate_football_uses_field_position_panel_not_legacy_down_box():
    js = read("static/csrn-broadcast-layout-engine.js")
    css = read("static/csrn-broadcast-layout-engine.css")
    assert "function collegiateFootballScorebug" in js
    assert "function collegiateField" in js
    assert "function collegiateScoreClockRow" in js
    assert 'data-module="game.field"' in js
    assert "bl-college-ticker-copy" in js
    assert "bl-college-score-clock-row" in js
    assert 'data-bind="game.possessionLogo"' in js
    assert "bl-college-hashmarks" in js
    assert "bl-college-first-down" in js
    assert "bl-college-line-scrimmage" in js
    assert "bl-college-drive-start" in js
    assert 'scorebug:{zone:"full-safe",width:1840,height:1000' in js
    assert "function collegiateStage" in js
    assert "bl-collegiate-tech" in css
    assert "bl-college-score-clock-row" in css
    assert "bl-college-hashmarks" in css
    assert "grid-template-columns:minmax(0,1fr)" in css
    assert "backdrop-filter:blur" in css
    assert 'content:"1ST DOWN"' in css
    assert "font-variant-numeric:tabular-nums" in css


def test_collegiate_runtime_patches_live_field_state_without_rerender():
    runtime = read("static/csrn-production-theme-runtime.js")
    assert "function productionFieldState" in runtime
    assert 'alias === "collegiate_traditional"' in runtime
    assert 'tickerSelector: ".bl-college-ticker-copy"' in runtime
    assert '[data-bind="game.ballSpot"]' in runtime
    assert '[data-bind="game.possessionLogo"]' in runtime
    assert "--first-x" in runtime
    assert "dataset.hasFirstDown" in runtime
