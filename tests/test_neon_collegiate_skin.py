"""Neon redesign (2026-09-20, docs/NEON_REDESIGN.md): Neon is a bold, TEAM-TINTED
neon skin over Collegiate Tech -- same renderer family, same DOM, same data
bindings, one extra stylesheet. It replaces the retired standalone Neon build
(archived under tests/retired/neon_v1/).

This repo has no JS runner, so the JS/CSS is pinned by source assertions here and
its BEHAVIOUR was verified live in a real browser (see the docs): the runtime
polling a real server, per-game colours, possession / down-and-distance changing
with no reload, on-air (transparent video window) mode, and the Layout Builder's
in-game and placement matrices. The one piece of real logic, the team-tint
function, is ported to Python below and checked against the outputs the browser
produced, with its constants tied back to the JS source so the port cannot drift.
"""

from __future__ import annotations

import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE = "static/csrn-broadcast-layout-engine.js"
RUNTIME = "static/csrn-production-theme-runtime.js"
NEON_CSS = "static/csrn-collegiate-neon.css"


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def manifest_block(js: str, package_id: str) -> str:
    start = js.index(f"    {package_id}: {{")
    depth, i = 0, js.index("{", start)
    while True:
        depth += {"{": 1, "}": -1}.get(js[i], 0)
        if depth == 0:
            return js[start : i + 1]
        i += 1


# --- one structure, two skins ------------------------------------------------------


def test_neon_manifest_is_collegiates_renderer_family_with_the_neon_skin_class() -> None:
    js = read(ENGINE)
    neon = manifest_block(js, "digital_neon")
    assert 'scorebugRenderer:"collegiate"' in neon
    assert 'componentRendererFamily: "collegiate"' in neon
    assert 'styleClass:"package-collegiate package-collegiate-neon"' in neon  # Collegiate's classes + the skin's
    assert "neonTint: true" in neon
    assert 'name:"Neon"' in neon and 'id:"digital_neon"' in neon


def test_neon_and_collegiate_share_one_per_sport_component_table() -> None:
    js = read(ENGINE)
    assert js.count("const COLLEGIATE_SPORT_COMPONENTS = Object.freeze(") == 1
    assert "sports: COLLEGIATE_SPORT_COMPONENTS" in manifest_block(js, "digital_neon")
    assert "sports: COLLEGIATE_SPORT_COMPONENTS" in manifest_block(js, "collegiate_traditional")
    table = js.split("const COLLEGIATE_SPORT_COMPONENTS = Object.freeze(")[1].split("\n  const PACKAGE_MANIFESTS")[0]
    # the four sports Collegiate covers, football on the full-safe 1840x1000 board
    for sport in ("football", "basketball", "baseball", "softball"):
        assert f"{sport}:{{components:{{" in table
    assert 'scorebug:{zone:"full-safe",width:1840,height:1000,layer:100}' in table
    # nothing of the retired standalone Neon lane survives in the manifest
    assert 'zone:"top-full",width:1840,height:250' not in manifest_block(js, "digital_neon")


def test_neon_does_not_use_the_retired_renderer_or_its_style_class() -> None:
    neon = manifest_block(read(ENGINE), "digital_neon")
    assert 'scorebugRenderer:"neon"' not in neon and 'componentRendererFamily: "neon"' not in neon
    assert "package-neon-approved" not in neon


def test_the_skin_lives_in_its_own_file_and_collegiates_stylesheet_is_untouched() -> None:
    engine_css = read("static/csrn-broadcast-layout-engine.css")
    assert "package-collegiate-neon" not in engine_css and "--visitor-neon" not in engine_css
    assert (ROOT / NEON_CSS).is_file()


def test_the_uniform_recolour_pipeline_stays_retired() -> None:
    """Out of scope by decision: nothing new may resurrect the layers-v10 clash pipeline."""
    neon_css = read(NEON_CSS)
    code = re.sub(r"/\*.*?\*/", "", neon_css, flags=re.S)  # comments may say "clash screen"; code may not resurrect the pipeline
    # the only clash-folder files Neon may name are the three plain field photographs (the stage background), never
    # the keyed player layers; the softball sky mask is the one place a mask is allowed
    named = re.findall(r"clash/([\w.-]+)", code)
    assert sorted(named) == [
        "baseball-ballpark-background.png", "basketball-court-background.png",
        "football-field-background.png", "softball-ballpark-background.png",
    ]
    # the only masks: the softball sky and the basketball floor (each written -webkit- and standard)
    assert "layers-v10" not in neon_css and code.count("mask-image") == 4
    assert "football-athletes" not in neon_css and "athletes-keyed" not in neon_css


# --- runtime: Collegiate's patches apply to the whole family ------------------------------


def test_the_runtime_treats_neon_as_a_collegiate_family_package() -> None:
    js = read(RUNTIME)
    assert 'new Set(["collegiate_traditional", "digital_neon"])' in js
    assert "function isCollegiateFamily(alias) {" in js
    # every Collegiate-specific patch keys on the family, none on the single alias
    assert not re.findall(r'(?:===|!==) "collegiate_traditional"', js)
    assert js.count("isCollegiateFamily(") >= 9
    assert 'digital_neon: ".bl-college-stage"' in js  # the audited native board


def test_neon_is_wired_through_the_shared_engine_like_collegiate() -> None:
    js = read(RUNTIME)
    spec = js.split("  digital_neon: Object.freeze({")[1].split("  }),")[0]
    college = js.split("  collegiate_traditional: Object.freeze({")[1].split("  })\n});")[0]
    assert 'globalName: "CSRNBroadcastLayoutEngine"' in spec and 'globalName: "CSRNBroadcastLayoutEngine"' in college
    assert 'tickerSelector: ".bl-college-ticker-copy"' in spec and 'tickerKind: "inside"' in spec
    assert "playerSupported: false" in spec
    assert "/static/csrn-collegiate-neon.css" in spec  # the skin
    assert "csrn-neon-" not in spec.replace("csrn-collegiate-neon", "")  # and none of the retired engines
    assert "CSRNNeonR2Engine" not in js


def test_neon_owns_a_themed_video_board_so_the_legacy_sponsor_panel_steps_aside() -> None:
    assert "'digital_neon'" in read("templates/overlay.html").split("CSRN_BOARD_SPONSOR_ALIASES=new Set([")[1].split("]")[0]
    assert "isCollegiateFamily(alias);" in read(RUNTIME).split("function themedVideoBoardSupported(alias) {")[1].split("}")[0]


def test_the_readiness_probe_loads_neon_from_the_shared_engine() -> None:
    probe = read("static/csrn-production-theme-readiness-probe.js")
    block = probe.split('packageId: "digital_neon",')[1].split("}),")[0]
    assert 'globalName: "CSRNBroadcastLayoutEngine"' in block


# --- Layout Builder contract ---------------------------------------------------------------


def test_neon_gets_the_layout_builder_contract_because_it_renders_through_the_shared_engine() -> None:
    """P1 found the old Neon never stamped data-component (it rendered through its own
    engine), so score_box no-oped on it. Through the shared engine every component
    is stamped by applyRect(); live-verified: in-game 12/12 and placement 11/11."""
    js = read(ENGINE)
    apply_rect = js.split("function applyRect(node, placement) {")[1].split("\n  }")[0]
    assert "node.dataset.component = placement.component;" in apply_rect
    assert "root.dataset.package = manifest.id;" in js
    assert 'data-component="scorebug"' in read("docs/LAYOUT_BUILDER_P1.md")


# --- the team tint ----------------------------------------------------------------------------


def _hex_to_hsl(value: str):
    m = re.fullmatch(r"#?([0-9a-fA-F]{6})", (value or "").strip())
    if not m:
        return None
    r, g, b = (int(m.group(1)[i : i + 2], 16) / 255 for i in (0, 2, 4))
    mx, mn = max(r, g, b), min(r, g, b)
    l = (mx + mn) / 2
    d = mx - mn
    if d == 0:
        return (0.0, 0.0, l)
    s = d / (1 - abs(2 * l - 1))
    if mx == r:
        h = ((g - b) / d) % 6
    elif mx == g:
        h = (b - r) / d + 2
    else:
        h = (r - g) / d + 4
    return ((h * 60 + 360) % 360, s, l)


def _hsl_to_hex(h: float, s: float, l: float) -> str:
    c = (1 - abs(2 * l - 1)) * s
    x = c * (1 - abs(((h / 60) % 2) - 1))
    m = l - c / 2
    r = g = b = 0.0
    if h < 60:
        r, g = c, x
    elif h < 120:
        r, g = x, c
    elif h < 180:
        g, b = c, x
    elif h < 240:
        g, b = x, c
    elif h < 300:
        r, b = x, c
    else:
        r, b = c, x
    return "#" + "".join(f"{math.floor((v + m) * 255 + 0.5):02X}" for v in (r, g, b))


ICE = "#EAF6FF"


def neon_electrify(primary: str, secondary: str) -> str:
    """Python port of neonElectrify() in csrn-broadcast-layout-engine.js."""

    def usable(c):
        return c is not None and c[1] >= 0.22 and 0.08 <= c[2] <= 0.94

    first, second = _hex_to_hsl(primary), _hex_to_hsl(secondary)
    source = first if usable(first) else (second if usable(second) else None)
    if source is None:
        return ICE
    h = source[0]
    l = 0.6
    if 215 <= h < 275:
        l = 0.7
    elif h < 15 or h >= 345:
        l = 0.62
    elif 45 <= h < 70:
        l = 0.56
    elif 70 <= h < 170:
        l = 0.55
    return _hsl_to_hex(h, 1, l)


# Outputs the real engine produced in a real browser (CSRNBroadcastLayoutEngine.neonElectrify).
LIVE_BROWSER_TABLE = {
    ("#0A2342", "#FFFFFF"): "#338EFF", ("#FFB81C", "#000000"): "#FFBF33", ("#4B2E83", "#FFFFFF"): "#9A66FF",
    ("#00693E", "#FFFFFF"): "#1AFFA1", ("#111111", "#C9A227"): "#FFC91F", ("#FFFFFF", "#7A0019"): "#FF3D65",
    ("#000000", "#FFFFFF"): "#EAF6FF", ("#808080", "#FFFFFF"): "#EAF6FF", ("#810909", "#FFFFFF"): "#FF3D3D",
    ("#CC0000", "#FFFFFF"): "#FF3D3D", ("#FF6600", "#000000"): "#FF8533", ("#1D428A", "#FFC72C"): "#669AFF",
    ("#006400", "#FFD700"): "#1AFF1A", ("#800000", "#FFFFFF"): "#FF3D3D", ("#7BAFD4", "#FFFFFF"): "#33AAFF",
    ("#C8102E", "#003087"): "#FF3D5D", ("", ""): "#EAF6FF",
}


def test_the_python_port_reproduces_what_the_engine_computed_in_the_browser() -> None:
    for (primary, secondary), expected in LIVE_BROWSER_TABLE.items():
        assert neon_electrify(primary, secondary) == expected, (primary, secondary)


def test_the_port_uses_the_same_constants_as_the_js_it_mirrors() -> None:
    js = read(ENGINE)
    body = js.split("function neonElectrify(primary, secondary) {")[1].split("\n  }")[0]
    for token in ("c.s >= 0.22 && c.l >= 0.08 && c.l <= 0.94", "let l = 0.6;",
                  "h >= 215 && h < 275) l = 0.7", "h < 15 || h >= 345) l = 0.62",
                  "h >= 45 && h < 70) l = 0.56", "h >= 70 && h < 170) l = 0.55",
                  "return neonHslToHex(h, 1, l);", "return NEON_ICE;"):
        assert token in body, token
    assert 'const NEON_ICE = "#EAF6FF";' in js


def test_a_school_reads_as_itself_electrified_and_never_as_a_fixed_accent() -> None:
    for primary, secondary in LIVE_BROWSER_TABLE:
        source = _hex_to_hsl(primary)
        out = _hex_to_hsl(neon_electrify(primary, secondary))
        if not primary or source[1] < 0.22 or not 0.08 <= source[2] <= 0.94:
            continue
        assert out[1] > 0.99                                                   # fully saturated: neon
        hue_gap = abs(out[0] - source[0])
        assert min(hue_gap, 360 - hue_gap) < 1.5, (primary, source[0], out[0])  # the school's own hue
    # different schools -> different colours (not one hardcoded accent on every game)
    assert len({neon_electrify(p, s) for (p, s) in LIVE_BROWSER_TABLE if _hex_to_hsl(p) and _hex_to_hsl(p)[1] > 0.3}) >= 8


def test_achromatic_school_colours_fall_back_to_the_secondary_then_to_ice() -> None:
    assert neon_electrify("#111111", "#C9A227") == "#FFC91F"  # black primary -> gold secondary
    assert neon_electrify("#808080", "#FFFFFF") == ICE
    assert neon_electrify("", "") == ICE and neon_electrify("nonsense", None) == ICE


def test_the_tint_is_computed_per_game_from_the_teams_and_applied_only_to_neon() -> None:
    js = read(ENGINE)
    apply = js.split("function applyNeonTint(root, state) {")[1].split("\n  }")[0]
    assert 'root.style.setProperty("--visitor-neon", neonElectrify(visitor.primary, visitor.secondary));' in apply
    assert 'root.style.setProperty("--home-neon", neonElectrify(home.primary, home.secondary));' in apply
    assert "if (manifest.neonTint) applyNeonTint(root, state);" in js
    assert js.count("applyNeonTint(") == 2  # the definition and the one guarded call
    # Collegiate Traditional's own markup is not touched by any of this
    assert 'return `style="--visitor-primary:${visitor};--home-primary:${home}"`;' in js
    assert "neonElectrify," in js.split("Object.freeze({")[-1]  # exported for the browser smoke test


# --- the skin: bold, static, scoped, team-derived -----------------------------------------------


def _css_rules(css: str):
    body = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    for match in re.finditer(r"([^{}]+)\{[^{}]*\}", body):
        yield match.group(1).strip(), match.group(0)


def _split_top_level_commas(selector: str):
    parts, depth, current = [], 0, ""
    for ch in selector:
        depth += {"(": 1, ")": -1}.get(ch, 0)
        if ch == "," and depth == 0:
            parts.append(current.strip())
            current = ""
        else:
            current += ch
    parts.append(current.strip())
    return parts


def test_every_rule_is_scoped_to_the_neon_root_so_collegiate_traditional_cannot_change() -> None:
    rules = list(_css_rules(read(NEON_CSS)))
    assert len(rules) > 40
    for selector, _rule in rules:
        for part in _split_top_level_commas(selector):
            assert part.startswith(".package-collegiate-neon"), part


def test_the_glow_is_static_no_animation_no_transition() -> None:
    css = re.sub(r"/\*.*?\*/", "", read(NEON_CSS), flags=re.S)
    for forbidden in ("@keyframes", "animation", "transition"):
        assert forbidden not in css


def test_colour_is_team_derived_the_only_fixed_colours_are_semantic() -> None:
    css = re.sub(r"/\*.*?\*/", "", read(NEON_CSS), flags=re.S)
    fixed = set(h.lower() for h in re.findall(r"#[0-9a-fA-F]{3,8}\b", css))
    # white, black (the mask), ink, the LIVE badge red, the first-down-line yellow, the turf greens,
    # and Collegiate's own default team-primary FALLBACKS inside var(--x-primary, ...): none is a team accent
    # Turf is expressed in rgba()/custom properties, never as a fixed hex: the only hex left are the neutrals,
    # the LIVE red, the first-down yellow, and Collegiate's own default team-primary fallbacks.
    assert fixed <= {"#fff", "#000", "#02030a", "#ff3b6b", "#f6ff2a", "#f4fbff", "#064624", "#0a2342"}, fixed
    for var in ("--vn", "--hn", "--mn", "--poss"):
        assert f"var({var}" in css
    assert "--visitor-neon" in css and "--home-neon" in css


def test_the_glow_is_bold() -> None:
    css = read(NEON_CSS)
    panel = css.split(".package-collegiate-neon :is(.bl-college-live-strip")[1].split("}")[0]
    assert "border: 2px solid" in panel
    for radius in ("0 0 3px", "0 0 10px", "0 0 24px", "0 0 48px"):  # four stacked layers
        assert radius in panel
    ring = css.split(".package-collegiate-neon .bl-college-stage::before {")[1].split("}")[0]
    assert "padding: 6px" in ring and "var(--vn)" in ring and "var(--hn)" in ring


def test_down_and_distance_is_a_rounded_pill_in_the_possession_teams_colour() -> None:
    css = read(NEON_CSS)
    pill = css.split(".bl-college-field-meta span:nth-child(2) {")[1].split("}")[0]
    assert "border-radius: 999px" in pill and "var(--poss)" in pill
    assert 'data-possession="visitor"] { --poss: var(--vn); }' in css
    assert 'data-possession="home"] { --poss: var(--hn); }' in css
    # the bar keeps its four-cell footprint: only the cell styling changes, not the grid
    assert "grid-template-columns: repeat(4" not in css
    # the DOM the pill styles is Collegiate's (Down is the second cell, live-patched data-possession)
    engine = read(ENGINE)
    meta = engine.split('<div class="bl-college-field-meta">')[1].split("</div>")[0]
    assert meta.index("<small>Possession</small>") < meta.index("<small>Down</small>") < meta.index("<small>Ball</small>")
    assert 'data-bind="game.downDistance"' in meta
    assert "fieldRoot.dataset.possession = field.possession;" in read(RUNTIME)  # so the pill follows possession live


def test_the_video_window_stays_a_true_hole_with_its_outline_kept_on_air() -> None:
    """Live-found: a dark fill on the shell or main-display sits BEHIND the transparent
    video stage and dims the OBS picture."""
    css = read(NEON_CSS)
    shell = css.split(".package-collegiate-neon .bl-collegiate-tech {")[1].split("}")[0]
    assert "background: transparent;" in shell
    assert "inset" not in shell.replace("inset 0", "") or "inset 0 0 46px" not in shell  # no dark inner fill
    assert ".package-collegiate-neon .bl-college-main-display { background: transparent; }" in css
    on_air = css.split(".package-collegiate-neon .bl-college-stage-video-active {")[1].split("}")[0]
    assert "background: transparent;" in on_air and "inset" not in on_air  # halo only, no inner tint
    assert ".bl-college-stage::before" in css  # the gradient ring survives (it is not conditional on mode)
    # team tint is confined to the rail zones, never over the window
    tint = css.split(".package-collegiate-neon .bl-collegiate-tech::before {")[1].split("}")[0]
    assert "transparent 21% 79%" in tint


# --- the retired build is archived, not deleted ---------------------------------------------------


def test_the_retired_engines_and_tests_are_archived_with_a_readme() -> None:
    retired = ROOT / "tests" / "retired" / "neon_v1"
    assert (retired / "README.md").is_file()
    engines = sorted(p.name for p in (retired / "static").iterdir())
    assert engines == sorted([
        "csrn-neon-baseball-r43-driver.css", "csrn-neon-baseball-r43-driver.js", "csrn-neon-r1-engine.css",
        "csrn-neon-r1-engine.js", "csrn-neon-r2-engine.css", "csrn-neon-r2-engine.js",
        "csrn-neon-softball-r42-driver.css", "csrn-neon-softball-r42-driver.js"])
    for name in engines:
        assert not (ROOT / "static" / name).exists()  # moved, not copied
    tests = sorted(p.name for p in (retired / "tests").iterdir())
    assert "test_gate116_neon_visual_freeze.py" in tests  # moved with the rest, its SHA pin untouched
    assert len([t for t in tests if t.startswith(("test_gate150", "test_gate151", "test_gate152", "test_gate153"))]) >= 30
    assert any(t.startswith("test_gate78_heritage_press_design__retired") for t in tests)
    assert 'collect_ignore = ["retired"]' in read("tests/conftest.py")


def test_the_readme_names_what_was_archived_and_why() -> None:
    readme = read("tests/retired/neon_v1/README.md")
    for token in ("gate116", "test_gate150_*", "csrn-neon-r2-engine", "layers-v10", "out of scope",
                  "test_gate78_heritage_press_design", "collect_ignore"):
        assert token.lower() in readme.lower(), token


# --- checkpoint 3: baseball / softball / basketball, the field art, and what live screenshots caught -------


def _rule(css: str, selector: str) -> str:
    """Body of the LAST rule whose selector text contains `selector` (later rules win in the cascade)."""
    start = css.rindex(selector)
    return css[css.index("{", start) + 1 : css.index("}", start)]


def test_baseball_and_softball_count_is_the_same_pill_as_football_down_and_distance() -> None:
    css = read(NEON_CSS)
    count = _rule(css, ".package-collegiate-neon .bl-college-diamond-meta span:nth-child(2) {")
    assert "border-radius: 999px" in count and "var(--poss)" in count
    # same shape as football's pill (rounded, poss-coloured border, glow), not a different treatment
    football = _rule(css, ".package-collegiate-neon .bl-college-field-meta span:nth-child(2) {")
    assert "border-radius: 999px" in football and "var(--poss)" in football
    # the DOM it styles is Collegiate's: Count is the second of Batting | Count | Outs
    engine = read(ENGINE)
    meta = engine.split('<div class="bl-college-diamond-meta">')[1].split("</div>")[0]
    assert meta.index("<small>Batting</small>") < meta.index("<small>Count</small>") < meta.index("<small>Outs</small>")


def test_the_diamond_follows_the_batting_team_like_football_follows_possession() -> None:
    css = read(NEON_CSS)
    base = _rule(css, ".package-collegiate-neon .bl-college-diamond {")
    assert "--poss: var(--vn)" in base and "--cd-accent: var(--vn)" in base  # top of the inning: visitor bats
    bottom = _rule(css, '.package-collegiate-neon .bl-college-diamond[data-inning-half="bottom"] {')
    assert "--poss: var(--hn)" in bottom and "--cd-accent: var(--hn)" in bottom
    assert 'data-inning-half="${half === "BOTTOM" ? "bottom" : "top"}"' in read(ENGINE)  # the attribute the engine sets
    assert "runner.on" in css.replace(".bl-cd-runner.on", "runner.on")  # occupied bases glow in the batting team's neon


def test_the_line_score_rows_are_each_in_their_own_teams_neon() -> None:
    css = read(NEON_CSS)
    assert ".package-collegiate-neon .bl-cls-row.bl-visitor { --c: var(--vn); }" in css
    assert ".package-collegiate-neon .bl-cls-row.bl-home { --c: var(--hn); }" in css
    engine = read(ENGINE)
    assert 'class="bl-cls-row bl-${side}"' in engine  # the classes those selectors rely on


def test_the_count_pill_has_room_in_the_diamond_column() -> None:
    """Live-found: Collegiate's 320px diamond column truncated "2-1" inside a pill."""
    css = read(NEON_CSS)
    assert ".package-collegiate-neon .bl-college-baseball-bank { grid-template-columns: minmax(0, 1fr) 430px; }" in css


def test_basketball_is_a_full_board_so_the_compact_strip_skin_is_gone() -> None:
    """Basketball panel parity (docs/BASKETBALL_PANEL_PARITY.md): basketball renders the same Collegiate Tech board as
    football and baseball, so Neon needs no basketball-specific shell / panel / rail / ring rule. The old palette+glow
    block for the compact strip (`:not(.bl-collegiate-tech)`) is retired; what remains is the court photo and the
    foul & timeout board."""
    css = read(NEON_CSS)
    assert ":not(.bl-collegiate-tech)" not in css
    block = css[css.index("/* ---- basketball (docs/BASKETBALL_PANEL_PARITY.md)"):]
    assert ".bl-college-court" in block and ".bl-court-row" in block
    # the LAST BASKET pill is the callout, in the neon of the team that scored (not the possession team)
    pill = _rule(block, ".package-collegiate-neon .bl-college-court-meta span:nth-child(2) {")
    assert "999px" in pill and "var(--callout)" in pill
    assert 'data-last-team="visitor"] { --callout: var(--vn); }' in block
    assert 'data-last-team="home"] { --callout: var(--hn); }' in block


def test_the_basketball_court_photo_is_lit_by_inverting_it_first() -> None:
    """The court's lines are BLACK on light wood, so the line-light layers invert the photo (a white `difference`
    blend), grayscale it, then isolate it exactly as the fields do; the bloom is tinted afterwards. The glow is masked
    to the floor, and to the middle of it (the far corner boxes are dark maroon and would light up as blocks)."""
    css = _css_code()
    layers = _rule(css, '.package-collegiate-neon .bl-college-stage-field[data-sport="basketball"]::before,\n'
                        '.package-collegiate-neon .bl-college-stage-field[data-sport="basketball"]::after {')
    assert "background-color: #fff;" in layers and "background-blend-mode: difference;" in layers
    assert "mask-composite: intersect;" in layers
    assert "grayscale(1)" in _rule(css, '.package-collegiate-neon .bl-college-stage-field[data-sport="basketball"]::before {')
    bloom = _rule(css, '.package-collegiate-neon .bl-college-stage-field[data-sport="basketball"]::after {')
    assert "blur(" in bloom and "hue-rotate(" in bloom
    # a deep-violet floor, not the shared grade's red
    assert 'data-sport="basketball"] { background-color: rgba(58, 52, 255, 1); }' in css


# --- what full-resolution captures caught ------------------------------------------------------------------------


def test_the_shell_never_blurs_or_darkens_what_is_behind_the_video_window() -> None:
    shell = _rule(read(NEON_CSS), ".package-collegiate-neon .bl-collegiate-tech {")
    assert "backdrop-filter: none;" in shell  # Collegiate's blur(8px) softened the camera feed (live-found)
    assert "background: transparent;" in shell


def test_the_readout_bank_keeps_1px_borders_so_the_pills_are_not_clipped() -> None:
    """Live-found at 1920x1080: 2px borders on these two containers clipped the bottom of
    the readout pills (the bank is a fixed-height stack that Collegiate's 1px borders just fit)."""
    css = read(NEON_CSS)
    assert ".package-collegiate-neon :is(.bl-college-control-bank, .bl-college-field) { border-width: 1px; }" in css
    assert ".package-collegiate-neon .bl-college-field { padding: 10px 10px 4px; gap: 6px; }" in css
    assert "grid-template-rows:minmax(140px,1fr) 50px" in read("static/csrn-broadcast-layout-engine.css")  # the geometry that forced it


def test_the_legacy_stats_ribbon_is_hidden_only_while_neon_is_active() -> None:
    js = read(RUNTIME)
    assert 'const NEON_ACTIVE_CLASS = "csrn-production-theme-neon-active";' in js
    assert 'document.documentElement.classList.toggle(NEON_ACTIVE_CLASS, alias === "digital_neon");' in js
    deactivate = js.split("function deactivate(reason")[1].split("setHostState(scoreHost(), false")[0]
    assert "NEON_ACTIVE_CLASS" in deactivate  # released with the other classes
    css = read("static/csrn-production-theme-runtime.css")
    rule = css[css.index("html.csrn-production-theme-neon-active #statBar"):].split("}")[0]
    assert "display:none!important" in rule
    assert "neon-active" not in css.split("html.csrn-production-layout-hide-player")[1]  # not applied to anything else


# --- blacklight turf (owner redirect after checkpoint 3) -------------------------------------------------------


def _css_code() -> str:
    return re.sub(r"/\*.*?\*/", "", read(NEON_CSS), flags=re.S)


def test_turf_is_near_black_not_daylight_grass() -> None:
    """Live review: mowed daylight grass with plain white lines clashed with the neon package. Every turf
    surface must be near-black (channel values low), with only a faint mow pattern."""
    css = _css_code()
    turf_rules = (
        ".package-collegiate-neon .bl-college-field-grid {",
        ".package-collegiate-neon .bl-college-diamond-grid {",
    )
    for selector in turf_rules:
        body = _rule(css, selector)
        for r, g, b, a in re.findall(r"rgba\((\d+),\s*(\d+),\s*(\d+),\s*(\.?\d+)\)", body):
            if float(a) >= 0.98:               # the solid base colours
                assert int(r) <= 12 and int(g) <= 40 and int(b) <= 30, (selector, r, g, b)
            elif int(g) > 100:                 # the mint mow stripes: faint only
                assert float(a) <= 0.16, (selector, a)
    for fill in re.findall(r"bl-cd-(?:grass|dirt|infield|mound) \{\s*fill: rgba\((\d+), (\d+), (\d+)", css):
        assert max(int(c) for c in fill) <= 30, fill


def test_every_field_line_has_a_bright_core_and_a_soft_bloom() -> None:
    """The same technique as the panel borders and the Down / Count pills: a thin bright core (var(--turf-core))
    with stacked drop-shadows in the bloom colour, never flat white."""
    css = _css_code()
    linework = (
        ".package-collegiate-neon .bl-college-field-grid::before {",   # field bar: sideline bands
        ".package-collegiate-neon .bl-college-field-grid::after {",    # field bar: yard lines
        ".package-collegiate-neon .bl-college-five-yard-lines {",
        ".package-collegiate-neon .bl-college-hashmarks {",
        ".package-collegiate-neon .bl-college-diamond-art .bl-cd-infield {",
        ".package-collegiate-neon .bl-college-diamond-art .bl-cd-foul {",
        ".package-collegiate-neon .bl-college-diamond-art .bl-cd-mound {",
        ".package-collegiate-neon .bl-college-diamond-art .bl-cd-dirt {",
    )
    for selector in linework:
        body = _rule(css, selector)
        assert "filter: drop-shadow(" in body and "var(--turf-bloom)" in body, selector
    for selector in linework[:2] + linework[3:6]:
        assert "var(--turf-core)" in _rule(css, selector), selector      # the bright core
    numbers = _rule(css, ".package-collegiate-neon .bl-college-yard-numbers {")
    assert numbers.count("var(--turf-bloom)") >= 2 and "var(--turf-core)" in numbers  # glowing text, layered


def test_no_field_line_is_flat_white_any_more() -> None:
    css = _css_code()
    raw = read(NEON_CSS)
    field = re.sub(r"/\*.*?\*/", "", raw[raw.index("/* -- football field bar */"):raw.index("/* -- clash screen")], flags=re.S)
    assert "rgba(255, 255, 255" not in field and "#fff" not in field.replace("color-mix(in srgb, var(--vn) 85%, #fff)", "")
    root = _rule(css, ".package-collegiate-neon {")
    assert "--turf-core:" in root and "--turf-bloom:" in root


def test_the_clash_screen_is_the_real_field_photo_under_a_blacklight_grade() -> None:
    """Owner: "look like real fields ... a picture of a real field with blacklight effects" (a drawn plane read as a
    radar image). The stage keeps Collegiate's three photographs, grades them into deep blue, and lights the photo's own
    lines: ::before crisp and contrast-isolated, ::after the same copy blurred, both screen-blended in mint."""
    css = _css_code()
    urls = re.findall(r"url\(\"([^\"]+)\"\)", css)
    assert sorted(urls) == [
        "/static/friday-night-stadium/clash/baseball-ballpark-background.png",
        "/static/friday-night-stadium/clash/basketball-court-background.png",
        "/static/friday-night-stadium/clash/football-field-background.png",
        "/static/friday-night-stadium/clash/softball-ballpark-background.png",
    ]
    for path in urls:
        assert (ROOT / path.lstrip("/")).is_file(), path
    stage = _rule(css, ".package-collegiate-neon .bl-college-stage-field {")
    assert "background-blend-mode: normal, normal, normal, normal, multiply" in stage and "isolation: isolate" in stage
    wash = _rule(
        css,
        ".package-collegiate-neon .bl-college-stage-field,\n"
        '.package-collegiate-neon .bl-college-stage-field[data-sport="baseball"],\n'
        '.package-collegiate-neon .bl-college-stage-field[data-sport="softball"] {',
    )
    assert "var(--vn)" in wash and "var(--hn)" in wash and "var(--neon-photo)" in wash   # team tint survives
    core = _rule(css, ".package-collegiate-neon .bl-college-stage-field::before {")
    bloom = _rule(css, ".package-collegiate-neon .bl-college-stage-field::after {")
    assert "contrast(" in core and "blur(" not in core
    assert "contrast(" in bloom and "blur(" in bloom
    shared = _rule(
        css,
        ".package-collegiate-neon .bl-college-stage-field::before,\n"
        ".package-collegiate-neon .bl-college-stage-field::after {",
    )
    assert "mix-blend-mode: screen" in shared and "var(--turf-bloom)" in shared
    # the softball sky is bright enough to pass the isolation, so its glow layers are masked to the ground
    assert "mask-image: linear-gradient(180deg, transparent" in css


def test_the_field_bar_keeps_its_readable_structure_and_the_redesigned_ball_marker() -> None:
    css = _css_code()
    grid = _rule(css, ".package-collegiate-neon .bl-college-field-grid {")
    assert "repeating-linear-gradient(90deg, rgba(0, 255, 160" in grid
    ball = _rule(css, ".package-collegiate-neon .bl-college-ball-marker {")
    assert "border-radius: 0 100% 0 100%" in ball and "rotate(-45deg)" in ball and "var(--poss)" in ball
    assert ".bl-college-ball-marker > * { transform: rotate(45deg); }" in css
    engine = read(ENGINE)
    for hook in ("bl-college-yard-numbers", "bl-college-five-yard-lines", "bl-college-hashmarks", "bl-college-endzone"):
        assert hook in engine  # the DOM the linework rules style is Collegiate's
