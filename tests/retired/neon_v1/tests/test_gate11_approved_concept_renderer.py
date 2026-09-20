from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "static" / "csrn-broadcast-layout-engine.js"
CSS = ROOT / "static" / "csrn-broadcast-layout-engine.css"
LAB = ROOT / "static" / "csrn-layout-lab.html"


def engine_source() -> str:
    return ENGINE.read_text(encoding="utf-8")


def approved_css() -> str:
    css = CSS.read_text(encoding="utf-8")
    return css[css.index("/* Gate 11.0 — Isolated Approved Concept Renderer.") :]


def test_gate11_uses_an_isolated_renderer_class() -> None:
    source = engine_source()
    assert 'styleClass:"package-neon-approved"' in source
    assert 'data-neon-renderer="approved-concept-v1"' in source
    assert ".package-neon-approved" in approved_css()
    assert ".package-neon ." not in approved_css()


def test_gate11_freezes_the_approved_scoreboard_geometry() -> None:
    source = engine_source()
    css = approved_css()
    neon = source[source.index("digital_neon:") : source.index("collegiate_traditional:")]
    assert neon.count('scorebug:{zone:"top-full",width:1840,height:250,layer:100}') == 4
    assert "grid-template-columns:200px 350px 190px 360px 190px 350px 200px" in css
    assert "width:1840px" in css
    assert "height:250px" in css


def test_gate11_uses_all_seven_directional_chassis_assets() -> None:
    css = approved_css()
    for asset in (
        "v2-logo-endcap-left.svg",
        "v2-logo-endcap-right.svg",
        "v2-identity-wing-left.svg",
        "v2-identity-wing-right.svg",
        "v2-score-crystal-left.svg",
        "v2-score-crystal-right.svg",
        "v2-cockpit-field.svg",
        "v2-cockpit-diamond.svg",
    ):
        assert f'/static/neon/{asset}' in css


def test_gate11_boosts_dark_team_colors_for_display_energy() -> None:
    source = engine_source()
    assert "function hasNeonChroma(value)" in source
    assert "function boostNeonColor(value, fallback)" in source
    assert "const scale = peak < 208 ? 255 / peak : 1" in source
    assert "boostNeonColor(primary, fallback)" in source


def test_gate11_support_modules_are_dark_system_surfaces() -> None:
    source = engine_source()
    css = approved_css()
    assert source.count('data-neon-surface="dark-system"') == 5
    surface = css[css.index('[data-neon-surface="dark-system"]{') :]
    surface_rule = surface[: surface.index("}")]
    assert "background:#01040a!important" in surface_rule
    assert "linear-gradient(90deg,#24d8ff" not in surface_rule
    shell = css[css.index(".package-neon-approved .bl-neon-component-shell{") :]
    shell_rule = shell[: shell.index("}")]
    assert "linear-gradient(145deg,#071426" in shell_rule
    assert "padding-box" in shell_rule
    assert "border-box" in shell_rule


def test_gate11_player_highlight_sponsor_caption_and_ticker_have_complete_rules() -> None:
    css = approved_css()
    for selector in (
        ".package-neon-approved .bl-neon-native-player",
        ".package-neon-approved .bl-neon-native-highlight",
        ".package-neon-approved .bl-neon-native-sponsor",
        ".package-neon-approved .bl-neon-native-ticker",
        ".package-neon-approved .bl-neon-native-captions",
    ):
        assert selector in css
    assert "grid-template-columns:215px minmax(0,1fr)" in css
    assert "grid-template-columns:58% 42%" in css
    assert "height:64px" in css
    assert "height:56px!important" in css


def test_gate11_adds_play_clock_and_sponsor_logo_contracts() -> None:
    source = engine_source()
    assert 'gameFields: ["period", "clock", "downDistance", "playClock", "possession"]' in source
    assert 'playClock: "25"' in source
    assert 'data-bind="game.playClock"' in source
    assert 'sponsorLogo: esc(state.sponsor.logo || "")' in source
    assert "bl-neon-sponsor-logo" in source


def test_gate11_layout_lab_uses_sport_aware_fixtures_and_current_assets() -> None:
    lab = LAB.read_text(encoding="utf-8")
    assert lab.count("csrn-broadcast-layout-engine.js?v=11") == 1
    assert lab.count("csrn-broadcast-layout-engine.css?v=11") == 1
    assert 'packageSelect.value="pixel_gameday"' in lab
    assert "function sportFixture(sport)" in lab
    for token in (
        'state.game.downDistance="3RD & 7"',
        'state.game.shotClock="25"',
        'state.home.score=3;state.visitor.score=5',
        'state.home.score=2;state.visitor.score=4',
        'state.ticker.text="TOP 5 - PINE VALLEY LEADS 4-2 - ONE OUT"',
    ):
        assert token in lab


def test_gate11_caption_and_ticker_lanes_remain_engine_separated() -> None:
    source = engine_source()
    neon = source[source.index("digital_neon:") : source.index("collegiate_traditional:")]
    assert neon.count('ticker:{zone:"bottom-center",height:64,layer:110}') == 4
    assert neon.count('captions:{zone:"bottom-center",height:56,stackAboveHeight:64,layer:120}') == 4
    assert "const laneGap = 12" in source
    assert "transform:none!important" in approved_css()


