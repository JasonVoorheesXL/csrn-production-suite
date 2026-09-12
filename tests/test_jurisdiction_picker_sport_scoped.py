"""Deferred trunk TODO (Round 27 / Round 26 collision, recorded in
docs/ROUND_27_ACCESS_MODEL.md and PHASE_C_THEME_SPORT_DISPATCH_PLAN.md):
scope Round 26's jurisdiction/country picker (#rulesetJurisdiction,
GET /api/rulesets, loadRulesetOptions) to CA-only rulesets under the
canadian_football sport-context and US-only under football, now that both
pieces exist in the same tree.

American and Canadian football load the same engine (sport_families.
base_family collapses canadian_football -> football); only the ruleset
choice differs, which is exactly what this picker offers.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _fn(name: str) -> str:
    html = _read("templates/index.html")
    start = html.index(name)
    # find the end of this function by locating the next top-level
    # "function "/"async function " declaration
    rest = html[start:]
    for marker in ("\nasync function ", "\nfunction "):
        idx = rest.find(marker, 1)
        if idx != -1:
            return rest[:idx]
    return rest


def test_load_ruleset_options_filters_by_the_active_sport_context() -> None:
    body = _fn("async function loadRulesetOptions() {")
    # Sport scoping (added alongside the baseball engine's P0 ruleset docs --
    # baseball/softball share country="US" with football, so the country
    # filter alone would leak baseball rulesets into a football picker and
    # vice versa without this).
    assert "sportContext === 'canadian_football' ? 'football' : (sportContext === 'football' || sportContext === 'baseball' || sportContext === 'softball') ? sportContext : null" in body
    assert "if (rulesetSport) rows = rows.filter((r) => (r.sport || '') === rulesetSport);" in body
    assert "sportContext === 'canadian_football' ? 'CA' : sportContext === 'football' ? 'US' : null" in body
    assert "if (rulesetCountry) rows = rows.filter((r) => (r.country || '') === rulesetCountry);" in body
    # bails gracefully rather than showing an empty/broken picker
    assert "if (!rows.length) return;" in body


def test_session_context_loads_before_the_jurisdiction_picker() -> None:
    # loadRulesetOptions() reads the module-level `sportContext`, which
    # loadSessionContext() sets -- it must run first at startup.
    html = _read("templates/index.html")
    init_start = html.index("await loadConfig();")
    init_region = html[init_start: init_start + 400]
    assert init_region.index("await loadSessionContext();") < init_region.index("await loadRulesetOptions();")


def test_switch_sport_context_refreshes_the_jurisdiction_picker() -> None:
    body = _fn("async function switchSportContext(value) {")
    assert "await loadRulesetOptions();" in body
    # refresh happens after sportContext itself is updated
    assert body.index("sportContext = data.sport_context") < body.index("await loadRulesetOptions();")
