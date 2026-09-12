"""T1 (docs/PHASE_C_THEME_SPORT_DISPATCH_PLAN.md "Tracked TODO -> T1"):
Collegiate Tech baseball/softball at football's structural weight, replacing
the R9 throwaway prototype (ensureCollegiateBaseballBottomBar /
patchCollegiateLineScore / .bl-cls-table, runtime-only, layout-only) with the
real, engine-native structure -- see test_phasec_r9_collegiate_baseball_
bottom_bar.py's removal and test_phasec_r5_collegiate_diamond.py's removal
(the diamond graphic is promoted from a runtime injection into the engine).

Covers: (1) the football-weight skeleton for baseball/softball, (2) the
"same class as football" visual-parity bar (field art, color-mix team
tinting, glass-morphism, never a plain table), (3) the open-ended-columns /
shrink / roll-window extra-innings rule, and (4) the sport-aware rail stat
grid. Item 3's "On the Mound"/"At Bat" live rail *content* is a follow-up
commit on top of this one (depends on this landing first, per the T1 spec).
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "static" / "csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
CSS = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
RUNTIME_JS = (ROOT / "static" / "csrn-production-theme-runtime.js").read_text(encoding="utf-8")
RUNTIME_CSS = (ROOT / "static" / "csrn-production-theme-runtime.css").read_text(encoding="utf-8")


def _fn(source: str, signature: str) -> str:
    start = source.index(signature)
    rest = source[start:]
    for marker in ("\n  function ", "\nfunction ", "\n  const ", "\n}\n\n"):
        idx = rest.find(marker, 1)
        if idx != -1:
            return rest[: idx + 1]
    return rest


def test_r9_and_r5_prototypes_are_fully_gone():
    # The prototype was explicitly throwaway/layout-only; T1 replaces it,
    # not extends it. No prototype CODE should remain in the unfrozen
    # runtime (a historical mention in a comment, like this test file's own
    # module docstring, is fine -- these check for the actual declarations).
    for gone in (
        "function ensureCollegiateBaseballBottomBar",
        "function ensureCollegiateDiamond",
        "function patchCollegiateLineScore",
        "bl-college-baseball-bar",
        "bl-cls-table",
        'data-prototype="baseball-bottom-bar"',
    ):
        assert gone not in RUNTIME_JS, gone
        assert gone not in RUNTIME_CSS, gone


def test_dispatcher_routes_baseball_and_softball_through_the_real_structure():
    body = _fn(JS, "collegiate(state, sport, videoMode) {")
    assert 'if (sport === "baseball" || sport === "softball") return collegiateBaseballScorebug(state, sport, videoMode);' in body
    assert "baseballLineScore(state,\"collegiate\")" not in body


def test_baseball_scorebug_reuses_the_football_skeleton_at_full_weight():
    assert "function collegiateBaseballScorebug(state, sport, videoMode)" in JS
    body = _fn(JS, "function collegiateBaseballScorebug(state, sport, videoMode) {")
    # Same cabinet / live-strip / score-clock-row / main-display shell as
    # collegiateFootballScorebug -- not a re-cast of the compact baseballLineScore.
    assert "bl-college-cabinet" in body
    assert "bl-college-live-strip" in body
    assert "collegiateBaseballScoreClockRow(state)" in body
    assert "bl-college-main-display" in body
    assert "collegiateTeamPanel(state.visitor, \"visitor\", sport)" in body
    assert "collegiateTeamPanel(state.home, \"home\", sport)" in body
    assert "collegiateStage(state, videoMode, sport)" in body
    assert "collegiateBaseballLineScoreBank(state)" in body
    # Structural prominence, not the old compact board.
    assert "bl-collegiate-tech" in body


def test_stage_field_art_swaps_per_sport_like_footballs_stadium_photo():
    assert 'function collegiateStage(state, videoMode, sport = "football")' in JS
    assert 'data-sport="${esc(sport)}"' in JS
    for sport, asset in (
        ("baseball", "baseball-ballpark-background.png"),
        ("softball", "softball-ballpark-background.png"),
    ):
        assert f'.bl-college-stage-field[data-sport="{sport}"]' in CSS
        block = CSS[CSS.index(f'.bl-college-stage-field[data-sport="{sport}"]'):]
        block = block[: block.index("}") + 1]
        assert asset in block
        # per-team color-mix tint carries over, same as football's stage bg
        assert "color-mix(in srgb,var(--visitor-primary" in block
        assert "color-mix(in srgb,var(--home-primary" in block


def test_never_a_plain_table_even_at_rest():
    # R9's flat .bl-cls-table is the named anti-example. The line score is
    # built from styled divs/spans in the same glass-morphism idiom as the
    # rest of the board, not a literal <table>.
    body = _fn(JS, "function collegiateBaseballLineScore(state) {")
    assert "<table" not in body
    assert "<th" not in body and "<td" not in body


def test_line_score_and_diamond_carry_the_visual_parity_bar():
    # 1. Field art / stadium-photo lockup already covered above.
    # 2. color-mix() team tinting on every baseball surface.
    assert "color-mix(in srgb,var(--team-primary" in CSS  # .bl-cls-row
    assert "--cd-accent:var(--visitor-primary" in CSS and "--cd-accent:var(--home-primary" in CSS
    assert "color-mix(in srgb,var(--cd-accent)" in CSS  # runner glow
    # 3. Glass-morphism panel treatment, matching .bl-college-video-replacement.
    line_score_css = CSS[CSS.index(".bl-college-line-score{"):]
    line_score_css = line_score_css[: line_score_css.index("}") + 1]
    assert "backdrop-filter:blur" in line_score_css
    assert "var(--glass-line)" in line_score_css


def test_extra_innings_open_ended_columns_shrink_and_roll():
    assert "function baseballInningPlan(state)" in JS
    body = _fn(JS, "function baseballInningPlan(state) {")
    assert "const CAP = 12;" in body
    assert "const WINDOW = 9;" in body
    assert "rolled" in body and "hiddenCount" in body
    # innings actually played drives the count, not a fixed 1-9 grid
    assert "Math.max(regulation, current, homeRuns.length, visitorRuns.length)" in body
    # column width shrinks past the baseline via the CSS custom property
    assert "--csrn-inning-count" in CSS
    assert "grid-template-columns:repeat(var(--csrn-inning-count,9),minmax(18px,1fr))" in CSS
    # rolled-off cue
    assert "bl-cls-rolled" in JS and "bl-cls-rolled" in CSS
    # R/H/E stay separate, fixed-width, never part of the rolling window
    assert "function collegiateBaseballLineScoreRow(state, side, plan) {" in JS
    row_body = _fn(JS, "function collegiateBaseballLineScoreRow(state, side, plan) {")
    assert "bl-cls-rhe" in row_body
    assert "grid-template-columns:repeat(3,30px)" in CSS  # .bl-cls-rhe: fixed width


def test_extra_innings_rule_is_documented_as_theme_runtime_wide():
    body = _fn(JS, "function baseballInningPlan(state) {")
    assert "theme-runtime-wide" in body


def test_diamond_is_promoted_into_the_frozen_engine_not_runtime_injected():
    assert "function collegiateBaseballDiamond(state)" in JS
    for cls in ("bl-cd-grass", "bl-cd-dirt", "bl-cd-infield", "bl-cd-foul",
                "bl-cd-mound", "bl-cd-base", "bl-cd-home"):
        assert cls in JS
    assert JS.count('class="bl-cd-runner') >= 3
    for base in ("first", "second", "third"):
        assert f'bl-cd-runner {base}' in JS
    # engine CSS owns the diamond's visual treatment now, not the runtime
    assert ".bl-college-diamond-art .bl-cd-runner.on{" in CSS
    assert ".bl-college-diamond{" not in RUNTIME_CSS


def test_rail_stat_grid_is_sport_aware_football_stays_byte_identical():
    assert 'function collegiateTeamPanel(team, side, sport = "football")' in JS
    assert "COLLEGIATE_RAIL_STATS" in JS
    rail_stats = JS[JS.index("const COLLEGIATE_RAIL_STATS"):]
    rail_stats = rail_stats[: rail_stats.index(");") + 2]
    for sport, keys in (
        ("football", ("passing_yards", "rushing_yards", "turnovers_gained")),
        ("baseball", ("batting_avg", "hits", "rbi")),
        ("softball", ("batting_avg", "hits", "rbi")),
    ):
        block = rail_stats[rail_stats.index(f"{sport}: Object.freeze(["):]
        block = block[: block.index("]]") + 2]
        for key in keys:
            assert key in block
    # football's rendered rail markup is generated from the same [label, key]
    # pairs the original hard-coded markup used, in the same order -- byte-
    # identical output for the football path.
    body = _fn(JS, "function collegiateTeamPanel(team, side, sport = \"football\") {")
    assert 'const statCells = stats.map(([label, key]) => `<b><small>${label}</small><strong data-stat="${key}">-</strong></b>`).join("");' in body


def test_runtime_fast_path_patches_the_new_structure_without_rerender():
    assert "function patchCollegiateBaseballDiamond(root, d, runtime)" in RUNTIME_JS
    assert "function patchCollegiateBaseballLineScore(root, runtime)" in RUNTIME_JS
    diamond_fn = RUNTIME_JS[RUNTIME_JS.index("function applyDiamondBoardOverrides(root, alias, runtime) {"):
                             RUNTIME_JS.index("function applyFootballBoardOverrides(root, alias, runtime) {")]
    branch = diamond_fn[diamond_fn.index('if (alias === "collegiate_traditional") {'):]
    assert "patchCollegiateBaseballDiamond(root, {half, inning, balls, strikes, outs, bases}, runtime);" in branch
    assert "patchCollegiateBaseballLineScore(root, runtime);" in branch


def test_line_score_column_plan_is_duplicated_in_the_runtime_fast_path():
    # Can't share code across the two script files -- same pattern as the
    # field-geometry helpers (applyFieldGeometry/spotFromPercent).
    assert "function baseballLineScorePlan(runtime) {" in RUNTIME_JS
    body = _fn(RUNTIME_JS, "function baseballLineScorePlan(runtime) {")
    assert "const CAP = 12;" in body
    assert "const WINDOW = 9;" in body
