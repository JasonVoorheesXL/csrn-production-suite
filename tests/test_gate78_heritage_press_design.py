from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_heritage_uses_independent_sport_state_panels() -> None:
    source = (ROOT / "static" / "csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
    for token in (
        "function pressFootballPanel(",
        "function pressBasketballPanel(",
        "function pressDiamondPanel(",
    ):
        assert token in source
    assert 'if (sport === "football") return pressFootballPanel(state);' in source
    assert 'if (sport === "basketball") return pressBasketballPanel(state);' in source
    assert "return pressDiamondPanel(state,sport);" in source


def test_heritage_scorebug_has_explicit_runtime_footprint() -> None:
    source = (ROOT / "static" / "csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
    heritage = source.split("heritage_press:", 1)[1].split("friday_night_stadium:", 1)[0]
    assert heritage.count('scorebug:{zone:"top-center",width:1140,height:234,layer:100}') == 4


def test_heritage_editorial_design_tokens_exist() -> None:
    css = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    for token in (
        "Gate 7.8 — Heritage Press editorial composition",
        "border:5px double var(--press-ink)",
        ".bl-press-section-line",
        ".bl-press-diamond-bases",
        ".package-press .bl-captions",
        "Gate 7.8 R3 runtime-footprint safeguards",
        ".package-press .bl-scorebug>*{min-width:0;min-height:0}",
    ):
        assert token in css


def test_heritage_secondary_components_share_editorial_system() -> None:
    source = (ROOT / "static" / "csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
    for token in ("SPORTS WIRE", "PLAYER OF THE GAME", "ADVERTISEMENT", "PHOTO / VIDEO"):
        assert token in source


def test_internal_theme_name_is_not_rendered_inside_graphics() -> None:
    source = (ROOT / "static" / "csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
    assert source.count('name:"Heritage Press"') == 1
    renderer_region = source.split("function pressFootballPanel", 1)[1].split("const SCOREBUG_RENDERERS", 1)[0]
    assert "Heritage Press" not in renderer_region


def test_gate78_r3_asset_contract_is_atomic() -> None:
    lab = (ROOT / "static" / "csrn-layout-lab.html").read_text(encoding="utf-8")
    source = (ROOT / "static" / "csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
    assert lab.count("csrn-broadcast-layout-engine.js?v=11") == 1
    assert lab.count("csrn-broadcast-layout-engine.css?v=11") == 1
    assert 'const VERSION = "1.7.0"' in source


def test_heritage_diagnostic_label_and_frame_use_separate_pseudo_elements() -> None:
    css = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    assert ".package-press .bl-scorebug::after" in css
    assert ".package-press .bl-player-card::after" in css
    assert ".package-press .bl-highlight::after" in css
    assert ".package-press .bl-sponsor::after" in css
    assert ".package-press .bl-captions::after" in css
    assert ".package-press .bl-scorebug::before,.package-press .bl-player-card::before" not in css
    block = css.split(
        ".csrn-broadcast-layout.diagnostics .package-press .bl-component::before",
        1,
    )[1].split("}", 1)[0]
    assert "width:max-content" in block
    assert "max-width:320px" in block
    assert "right:auto" in block
    assert "bottom:auto" in block


def test_heritage_diamond_assigns_pitcher_and_batter_to_team_rows() -> None:
    source = (ROOT / "static" / "csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
    assert 'pressRoleDetail("pitcher"' in source
    assert 'pressRoleDetail("batter"' in source
    assert 'data-role="${kind}"' in source
    assert "bl-press-matchup" not in source[source.index("function pressDiamondPanel"):source.index("const SCOREBUG_RENDERERS")]


def test_heritage_uses_period_role_illustrations_and_monochrome_media() -> None:
    source = (ROOT / "static" / "csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
    css = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    assert "function pressRoleIcon(kind)" in source
    assert "bl-press-role-${kind}" in source
    assert 'pressRoleDetail("pitcher"' in source
    assert 'pressRoleDetail("batter"' in source
    assert "filter:grayscale(1) sepia(.18)" in css
    assert "filter:grayscale(1) sepia(.2)" in css


def test_heritage_player_cards_are_sport_aware_collectible_cards() -> None:
    source = (ROOT / "static" / "csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
    css = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    assert "function heritagePlayerStats(state, sport)" in source
    for label in ("COMP/ATT", "PTS", "RBI", "SB"):
        assert label in source
    assert "bl-press-gum-card" in source
    assert ".bl-press-card-stats" in css


def test_heritage_wire_ticker_has_type_hold_and_advance_phases() -> None:
    source = (ROOT / "static" / "csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
    css = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    assert "function splitPressWireStories(value)" in source
    assert "function hydratePressWire(root" in source
    assert 'wire.dataset.wirePhase = "type"' in source
    assert 'wire.dataset.wirePhase = "hold"' in source
    assert 'wire.dataset.wirePhase = "advance"' in source
    assert "is-advancing" in source
    assert ".bl-press-wire.is-advancing .bl-wire-copy" in css


def test_heritage_sponsor_restores_double_rule_advertisement_frame() -> None:
    source = (ROOT / "static" / "csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
    css = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    assert "bl-press-advert" in source
    assert ".package-press .bl-press-advert" in css
    assert "border:6px double var(--press-rule)" in css


def test_heritage_football_and_basketball_visitor_rows_are_mirrored() -> None:
    source = (ROOT / "static" / "csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
    football = source[source.index("function pressFootballPanel"):source.index("function pressBasketballPanel")]
    basketball = source[source.index("function pressBasketballPanel"):source.index("function pressDiamondPanel")]
    visitor = '<section class="bl-press-row bl-visitor" data-module="visitor.team"><strong class="bl-score"'
    assert visitor in football
    assert visitor in basketball
    assert '${pressTeamIdentity(state.visitor,"visitor")}</section>' in football
    assert '${pressTeamIdentity(state.visitor,"visitor")}</section>' in basketball


def test_heritage_visitor_identity_places_copy_before_logo() -> None:
    source = (ROOT / "static" / "csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
    identity = source[source.index("function pressTeamIdentity"):source.index("const PRESS_WIRE_TIMERS")]
    assert 'side === "visitor" ? `${copy}${logo}` : `${logo}${copy}`' in identity
    assert 'bl-press-meta' in identity


def test_heritage_diamond_visitor_order_is_score_role_identity() -> None:
    source = (ROOT / "static" / "csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
    diamond = source[source.index("function pressDiamondPanel"):source.index("const SCOREBUG_RENDERERS")]
    visitor_start = diamond.index('<section class="bl-press-row bl-visitor"')
    visitor_end = diamond.index("</section>", visitor_start)
    visitor = diamond[visitor_start:visitor_end]
    assert visitor.index('class="bl-score"') < visitor.index("${visitorRole}")
    assert visitor.index("${visitorRole}") < visitor.index('${pressTeamIdentity(state.visitor,"visitor")}')


def test_heritage_css_freezes_accepted_team_row_geometry() -> None:
    css = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    assert ".package-press .bl-press-football .bl-visitor" in css
    assert "grid-template-columns:104px minmax(0,1fr)" in css
    assert ".package-press .bl-press-diamond .bl-visitor" in css
    assert "grid-template-columns:100px 244px minmax(0,1fr)" in css
    assert ".package-press .bl-press-diamond .bl-press-role{" in css
    assert "flex-direction:column" in css


def test_heritage_records_share_the_home_visitor_meta_line() -> None:
    source = (ROOT / "static" / "csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
    css = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    assert '<div class="bl-press-meta">' in source
    assert '<span class="bl-record"' in source
    assert ".package-press .bl-press-meta" in css
    assert ".package-press .bl-record" in css


def test_gate711_registers_real_heritage_role_assets() -> None:
    source = (ROOT / "static" / "csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
    assert "const HERITAGE_PRESS_ASSETS" in source
    assert "/static/heritage/press-pitcher-1920s.png" in source
    assert "/static/heritage/press-batter-1920s.png" in source
    assert '<img src="${source}"' in source


def test_gate711_football_and_basketball_state_column_is_uninterrupted() -> None:
    css = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    assert "right:330px" in css
    assert "width:330px" in css
    assert "top:34px" in css
    assert "bottom:0" in css


def test_gate711_diamond_uses_exact_approved_row_order_and_state_width() -> None:
    css = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    source = (ROOT / "static" / "csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
    assert "right:300px" in css
    assert "width:300px" in css
    assert "grid-template-columns:100px 220px minmax(0,1fr)" in css
    diamond = source[source.index("function pressDiamondPanel"):source.index("const SCOREBUG_RENDERERS")]
    visitor = diamond[diamond.index('<section class="bl-press-row bl-visitor"'):diamond.index("</section>", diamond.index('<section class="bl-press-row bl-visitor"'))]
    assert visitor.index('class="bl-score"') < visitor.index("${visitorRole}") < visitor.index('${pressTeamIdentity(state.visitor,"visitor")}')


def test_gate711_base_indicator_contains_only_three_bases() -> None:
    source = (ROOT / "static" / "csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
    diamond = source[source.index("function pressDiamondPanel"):source.index("const SCOREBUG_RENDERERS")]
    bases = diamond[diamond.index('class="bl-press-diamond-bases"'):diamond.index("</div>", diamond.index('class="bl-press-diamond-bases"'))]
    assert bases.count("<i ") == 3


def test_gate711_player_and_sponsor_cards_match_editorial_contract() -> None:
    source = (ROOT / "static" / "csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
    css = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    assert "bl-press-card-tonight" in source
    assert "bl-press-advert-art" in source
    assert "SUPPORT LOCAL · INVEST LOCAL · CHEER LOCAL" in source
    assert ".package-press .bl-press-card-main" in css
    assert ".package-press .bl-press-advert-copy" in css


def test_gate712_heritage_scorebugs_gain_five_percent_height() -> None:
    source = (ROOT / "static" / "csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
    heritage = source[source.index("heritage_press: {"):]
    assert heritage.count("width:1140,height:234") >= 4


def test_gate712_game_clock_uses_three_explicit_columns() -> None:
    css = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    assert "grid-template-columns:72px 52px minmax(0,1fr)" in css
    assert ".package-press .bl-press-clock>b" in css


def test_gate712_basketball_fouls_are_structured_and_readable() -> None:
    source = (ROOT / "static" / "csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
    assert '<div class="bl-press-fouls"><strong>FOULS</strong>' in source
    assert '<span>HOME <b>${esc(state.game.homeFouls)}</b></span>' in source
    assert '<span>VIS <b>${esc(state.game.visitorFouls)}</b></span>' in source


def test_gate712_scores_and_baseball_bottom_content_are_centered() -> None:
    css = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    assert "place-items:center" in css
    assert "grid-template-rows:54px 72px minmax(48px,1fr)" in css
    assert "grid-template-rows:66px 22px" in css


def test_gate712_player_card_banner_has_no_overlapping_subtitle() -> None:
    source = (ROOT / "static" / "csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
    player = source[source.index("function pressPlayerCard"):source.index("function splitPressWireStories")]
    assert 'class="bl-sr-only">PLAYER OF THE GAME' in player
    assert "bl-press-card-purpose" not in player


def test_gate712_r2_count_row_uses_contained_flexible_geometry() -> None:
    css = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    assert "padding-bottom:8px" in css
    assert "min-height:48px" in css
    assert "align-self:stretch" in css
    assert ".bl-press-card-banner .bl-sr-only" in css


def test_gate712_r4_count_row_has_explicit_bottom_clearance() -> None:
    css = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    assert "grid-template-rows:54px 72px minmax(48px,1fr)" in css
    assert "padding-bottom:8px" in css
    assert "max-height:100%" in css
    assert ".package-press .bl-press-count span{" in css


def test_gate712_r5_heritage_scorebugs_are_five_percent_taller() -> None:
    source = (ROOT / "static" / "csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
    heritage = source[source.index("heritage_press:"):source.index("friday_night_stadium:")]
    assert heritage.count('width:1140,height:234') == 4
    assert 'width:1140,height:222' not in heritage


def test_gate712_r5_diamond_count_uses_explicit_bounded_position() -> None:
    css = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    assert "Gate 7.12 R5 — deterministic Heritage diamond-state containment" in css
    block = css.rsplit(".package-press .bl-press-diamond-state .bl-press-count{", 1)[1].split("}", 1)[0]
    assert "position:absolute" in block
    assert "top:126px" in block
    assert "bottom:8px" in block
    assert "height:auto" in block
    assert "min-height:0" in block


def test_gate713_shared_frame_rules_stop_at_inset_frame() -> None:
    css = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    section = css[css.index("/* Gate 7.13 — Heritage shared frame cleanup."):]
    assert ".package-press .bl-press-masthead{" in section
    assert "left:8px" in section
    assert "right:8px" in section
    assert "width:322px" in section
    assert "width:292px" in section


def test_gate713_preserves_approved_score_separators() -> None:
    css = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    section = css[css.index("/* Gate 7.13 — Heritage shared frame cleanup."):]
    assert ".bl-home .bl-score" in section
    assert "border-left:1px solid var(--press-rule)" in section
    assert ".bl-visitor .bl-score" in section
    assert "border-right:1px solid var(--press-rule)" in section


def test_gate714_removes_legacy_scorebug_inset_pseudo_frame() -> None:
    css = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    section = css[css.index("/* Gate 7.14 — Heritage inset-frame artifact removal."):]
    assert ".package-press .bl-scorebug::after{" in section
    assert "content:none!important" in section
    assert "display:none!important" in section
    assert "border:0!important" in section


def test_gate714_keeps_real_frame_and_score_separators() -> None:
    css = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    assert "outline:1px solid rgba(232,221,191,.82)" in css
    assert "box-shadow:" in css
    assert "border-left:1px solid var(--press-rule)" in css
    assert "border-right:1px solid var(--press-rule)" in css


def test_gate715_removes_border_before_visitor_score_only() -> None:
    css = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    section = css[css.index("/* Gate 7.15 — Heritage visitor score separator correction."):]
    assert ".bl-visitor .bl-score" in section
    assert "border-left:0!important" in section
    assert "border-right:1px solid var(--press-rule)!important" in section


def test_gate715_preserves_home_score_separator() -> None:
    css = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    assert ".bl-home .bl-score" in css
    assert "border-left:1px solid var(--press-rule)" in css


def test_gate716_neon_sports_network_manifest_and_version() -> None:
    source = (ROOT / "static" / "csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
    assert 'const VERSION = "1.7.0"' in source
    assert 'id:"digital_neon", name:"Neon Sports Network"' in source
    assert 'data-neon-package="sports-network"' in source


def test_gate716_neon_uses_team_aware_accents() -> None:
    source = (ROOT / "static" / "csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
    assert "function neonTeamAccent(" in source
    assert "function neonTeamStyle(" in source
    assert "--neon-team-rgb:" in source
    assert 'neonTeamStyle(team,side)' in source
    assert 'neonIdentityPanel(state.home,"home")' in source
    assert 'neonIdentityPanel(state.visitor,"visitor")' in source
    assert 'neonScoreBay(state.home,"home"' in source
    assert 'neonScoreBay(state.visitor,"visitor"' in source


def test_gate716_neon_has_independent_four_sport_scorebugs() -> None:
    source = (ROOT / "static" / "csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
    assert "bl-neon-five-zone-field" in source
    assert "bl-neon-five-zone-diamond" in source
    assert 'data-possession="${possession}"' in source
    assert 'data-inning-half="${normalizeInningHalf(state.game.inningHalf).toLowerCase()}"' in source


def test_gate716_neon_components_and_reduced_motion() -> None:
    source = (ROOT / "static" / "csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
    css = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    assert "bl-neon-stat-grid" in source
    assert "bl-neon-live-capsule" in source
    assert "bl-neon-native-sponsor" in source
    assert "Gate 7.16 — Neon Sports Network Design Lab foundation" in css
    assert "@media (prefers-reduced-motion:reduce)" in css
    assert "@keyframes neonRailPulse" in css


def test_gate716_neon_does_not_enter_production_overlay() -> None:
    overlay = (ROOT / "templates" / "overlay.html").read_text(encoding="utf-8")
    assert "csrn-broadcast-layout-engine.js" not in overlay
    assert "csrn-scorebug-engine.js" in overlay


def test_gate716_r3_neon_avoids_obsolete_176px_manifest_override() -> None:
    source = (ROOT / "static" / "csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
    neon = source[source.index("digital_neon:"):source.index("collegiate_traditional:")]
    assert "width:1140,height:176" not in neon
    assert 'id:"digital_neon", name:"Neon Sports Network"' in neon


def test_gate716_r4_neon_uses_existing_sport_stat_helper() -> None:
    source = (ROOT / "static" / "csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
    assert "function heritagePlayerStats(state, sport)" in source
    assert "heritagePlayerStats(state,sport)" in source
    assert "playerStatsForSport(" not in source


def test_gate717_neon_hides_identification_labels_but_keeps_diagnostics() -> None:
    css = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    section = css[css.index("/* Gate 7.17 — Neon visual frame and diagnostic cleanup."):]
    assert ".csrn-broadcast-layout.diagnostics .package-neon.bl-component::before" in section
    assert 'content:""!important' in section
    assert "background:transparent!important" in section
    assert "outline:1px dashed rgba(36,216,255,.62)" in section


def test_gate717_neon_uses_approved_angular_glass_frame_language() -> None:
    css = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    section = css[css.index("/* Gate 7.17 — Neon visual frame and diagnostic cleanup."):]
    assert "clip-path:polygon(" in section
    assert ".package-neon .bl-scorebug::after" in section
    assert "linear-gradient(90deg,var(--neon-cyan)" in section
    assert ".package-neon .bl-neon-player-number" in section
    assert ".package-neon .bl-neon-highlight .bl-video-placeholder::after" in section


def test_gate718_r3_yellow_labels_require_separate_opt_in_class() -> None:
    css = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    assert '.csrn-broadcast-layout.diagnostics.diagnostic-labels .bl-component::before' in css
    assert '.csrn-broadcast-layout.diagnostics .bl-component::before{content:attr(data-component)' not in css
    assert "Gate 7.18 R3 — Layout Lab yellow diagnostic labels disabled" in css


def test_gate718_r3_outlines_and_collision_markers_still_use_diagnostics() -> None:
    css = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    assert ".csrn-broadcast-layout.diagnostics .bl-component{outline:" in css
    assert '.bl-component[data-collision="true"]' in css


def test_gate719_neon_owns_top_full_lane_and_future_placements() -> None:
    source = (ROOT / "static" / "csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
    assert '"top-full": {x: 40, y: 30, w: 1840, h: 280}' in source
    neon = source[source.index("digital_neon:"):source.index("collegiate_traditional:")]
    assert neon.count('scorebug:{zone:"top-full",width:1840,height:250') == 4
    assert neon.count('captions:{zone:"bottom-center",height:56') == 4
    assert 'scorebug:{zone:"bottom-center"' not in neon


def test_gate719_neon_has_possession_side_football_and_future_diamond() -> None:
    source = (ROOT / "static" / "csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
    assert 'class="bl-neon-possession-badge' in source
    assert 'sport === "football"' in source
    assert "bl-neon-five-zone-diamond" in source
    assert "bl-neon-command-diamond" in source


def test_gate719_neon_visual_contract_is_not_modern_skin() -> None:
    css = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    section = css[css.index("/* Gate 7.19 — Neon future-broadcast composition."):]
    assert "grid-template-columns:minmax(0,1fr) 330px minmax(0,1fr)" in section
    assert "font-size:clamp(36px,2.65vw,54px)" in section
    assert ".bl-neon-possession-ball" in section
    assert ".bl-neon-diamond-future" in section
    assert "grid-template-columns:112px minmax(0,1fr) 28px" in section
    assert "outline:none!important" in section


def test_gate719_r2_supersedes_old_neon_placement_contract_cleanly() -> None:
    source = (ROOT / "static" / "csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
    neon = source[source.index("digital_neon:"):source.index("collegiate_traditional:")]
    assert neon.count('scorebug:{zone:"top-full",width:1840,height:250') == 4
    assert 'scorebug:{zone:"bottom-center",layer:100}' not in neon
    assert 'scorebug:{zone:"top-right",layer:100}' not in neon


def test_gate719_r4_targets_neon_root_owned_component_wrappers() -> None:
    css = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    section = css[css.index("/* Gate 7.19 R4 — Correct Neon diagnostic-wrapper targeting."):]
    assert ".csrn-broadcast-layout.package-neon.diagnostics .bl-component" in section
    assert ".bl-component[data-collision=\"true\"]" in section
    assert "outline:none!important" in section


def test_gate720_neon_uses_dedicated_native_dom() -> None:
    source = (ROOT / "static" / "csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
    assert "function neonIdentityPanel(" in source
    assert "function neonScoreBay(" in source
    assert "function neonCorePanel(" in source
    assert "function neonFootballSvg(" in source
    assert "bl-neon-five-zone-field" in source
    assert "bl-neon-five-zone-diamond" in source
    assert "bl-neon-identity-shell" in source
    assert "bl-neon-score-shell" in source
    assert "bl-neon-component-shell" in source


def test_gate720_neon_names_are_responsive_not_ellipsized() -> None:
    source = (ROOT / "static" / "csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
    css = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    assert "function neonNameClass(" in source
    assert "bl-neon-name-xl" in source
    section = css[css.index("/* Gate 7.20 — Neon-native composition rebuild."):]
    assert ".bl-neon-name-sm .bl-neon-team-name" in section
    assert ".bl-neon-name-xl .bl-neon-team-name" in section
    assert "text-overflow:ellipsis" not in section[section.index("/* Team identity"):section.index("/* Center command core")]


def test_gate720_neon_mascot_logo_and_possession_use_real_glow_layers() -> None:
    source = (ROOT / "static" / "csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
    css = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    assert "bl-neon-football-svg" in source
    assert "bl-neon-logo-halo" in source
    section = css[css.index("/* Gate 7.20 — Neon-native composition rebuild."):]
    assert "drop-shadow(0 0 16px var(--neon-team))" in section
    assert ".bl-neon-mascot" in section
    assert ".bl-neon-possession-emitter" in section


def test_gate720_neon_components_have_native_shells() -> None:
    source = (ROOT / "static" / "csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
    assert "bl-neon-native-player" in source
    assert "bl-neon-native-highlight" in source
    assert "bl-neon-native-ticker" in source
    assert "bl-neon-live-capsule" in source
    assert "bl-neon-video-bay" in source


def test_gate720_r2_neon_name_fit_uses_weighted_glyph_width() -> None:
    source = (ROOT / "static" / "csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
    css = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    assert 'if ("MW".includes(char)) widthUnits += 1.45' in source
    assert 'if (widthUnits >= 8.5) return "bl-neon-name-md"' in source
    section = css[css.index("/* Gate 7.20 R2 — Responsive Neon team-name fit correction."):]
    assert "width:100%" in section
    assert ".bl-neon-name-md .bl-neon-team-name{font-size:36px" in section


def test_gate720_r3_neon_names_use_browser_measured_post_render_fit() -> None:
    source = (ROOT / "static" / "csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
    assert "function fitNeonTeamNames(root)" in source
    assert 'node.scrollWidth > available + 1' in source
    assert 'node.dataset.fitOverflow' in source
    assert 'manifest.componentRendererFamily === "neon"' in source
    assert "fitNeonTeamNames(root);" in source


def test_gate721_neon_scorebug_is_true_five_zone_structure() -> None:
    source = (ROOT / "static" / "csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
    css = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    assert "function neonIdentityPanel(" in source
    assert "function neonScoreBay(" in source
    assert "bl-neon-five-zone" in source
    section = css[css.index("/* Gate 7.21 — Neon five-zone scorebug rebuild."):]
    assert "grid-template-columns:minmax(0,1fr) 176px 330px 176px minmax(0,1fr)" in section
    assert ".bl-neon-score-bay" in section


def test_gate721_captions_are_placed_immediately_above_ticker() -> None:
    source = (ROOT / "static" / "csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
    neon = source[source.index("digital_neon:"):source.index("collegiate_traditional:")]
    assert neon.count('captions:{zone:"bottom-center",height:56,stackAboveHeight:64,layer:120}') == 4
    assert 'offsetY:-66' not in neon


def test_gate721_r4_scorebug_footprint_matches_five_zone_height() -> None:
    source = (ROOT / "static" / "csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
    neon = source[source.index("digital_neon:"):source.index("collegiate_traditional:")]
    assert neon.count('scorebug:{zone:"top-full",width:1840,height:250,layer:100}') == 4
    assert 'scorebug:{zone:"top-full",width:1840,height:210,layer:100}' not in neon




def test_gate721_r8_manifest_uses_approved_270px_and_rejects_210px() -> None:
    source = (ROOT / "static" / "csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
    neon = source[source.index("digital_neon:"):source.index("collegiate_traditional:")]
    assert neon.count('scorebug:{zone:"top-full",width:1840,height:250,layer:100}') == 4
    assert 'scorebug:{zone:"top-full",width:1840,height:210,layer:100}' not in neon


def test_gate721_r9_caption_spacing_uses_builtin_bottom_lane_gap() -> None:
    source = (ROOT / "static" / "csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
    neon = source[source.index("digital_neon:"):source.index("collegiate_traditional:")]
    assert neon.count('captions:{zone:"bottom-center",height:56,stackAboveHeight:64,layer:120}') == 4
    assert 'offsetY:-66' not in neon


def test_gate721_r11_neon_neutralizes_legacy_caption_translation() -> None:
    css = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    assert '.bl-component.bl-captions[data-zone="bottom-center"]{transform:translateY(-78px)}' in css
    section = css[css.index("/* Gate 7.21 R10 — Neon caption wrapper placement isolation."):]
    assert '.csrn-broadcast-layout.package-neon .bl-component.bl-captions[data-zone="bottom-center"]' in section
    assert "transform:translateY(-12px)!important" in section


def test_gate721_r11_neon_caption_adjustment_targets_eight_pixel_gap() -> None:
    css = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    section = css[css.index("/* Gate 7.21 R10 — Neon caption wrapper placement isolation."):]
    assert "transform:translateY(-12px)!important" in section
    assert "Gate 7.21 R11 — Measured caption/ticker separation." in section


def test_gate722_team_adaptive_neon_visual_fidelity_contract() -> None:
    source = (ROOT / "static" / "csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
    css = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    assert "--neon-team-secondary:" in source
    assert "Gate 7.22 — Team-adaptive Neon visual fidelity." in css
    assert ".bl-sport-baseball .bl-neon-command-diamond .bl-diamond i.on" in css
    assert ".bl-sport-softball .bl-neon-command-diamond .bl-diamond i.on" in css
    assert "animation:neon-fidelity-breathe" in css
    assert "@media (prefers-reduced-motion:reduce)" in css



def test_gate723_neon_root_exposes_team_adaptive_chassis_colors() -> None:
    source = (ROOT / "static" / "csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
    assert "function neonPackageStyle(state)" in source
    assert "--neon-home:" in source
    assert "--neon-visitor:" in source
    assert "${neonPackageStyle(state)}" in source


def test_gate723_geometry_engine_uses_interlocking_package_shells() -> None:
    css = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    section = css[css.index("/* Gate 7.23 — Neon Broadcast Package geometry engine."):]
    assert "grid-template-columns:minmax(0,1fr) 176px 384px 176px minmax(0,1fr)" in section
    assert ".bl-neon-identity-shell::before" in section
    assert ".bl-neon-score-shell::before" in section
    assert ".bl-neon-core-shell::before" in section
    assert "var(--neon-home)" in section
    assert "var(--neon-visitor)" in section


def test_gate723_preserves_sport_specific_base_personalities() -> None:
    css = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    section = css[css.index("/* Gate 7.23 — Neon Broadcast Package geometry engine."):]
    assert ".bl-sport-baseball" in section and "#24D8FF!important" in section
    assert ".bl-sport-softball" in section and "#FF2DAA!important" in section
    assert "@media (prefers-reduced-motion:reduce)" in section


def test_gate724_concept_fidelity_uses_readable_identity_typography() -> None:
    css = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    section = css[css.index("/* Gate 7.24 — Neon concept-fidelity composition."):]
    assert ".bl-neon-mascot" in section
    assert "font-size:27px!important" in section
    assert ".bl-neon-team-name" in section
    assert "font-size:43px" in section


def test_gate724_replaces_sliding_highlight_with_stationary_bloom() -> None:
    css = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    section = css[css.index("/* Gate 7.24 — Neon concept-fidelity composition."):]
    identity_highlight = section[section.index(".bl-neon-identity-shell::after"):section.index("/* Identity pods:")]
    assert "animation:none!important" in identity_highlight
    assert "transform:none!important" in identity_highlight
    assert "@keyframes neon-concept-ambient-pulse" in section


def test_gate724_preserves_baseball_and_softball_base_colors() -> None:
    css = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    section = css[css.index("/* Gate 7.24 — Neon concept-fidelity composition."):]
    assert ".bl-sport-baseball" in section and "#24D8FF!important" in section
    assert ".bl-sport-softball" in section and "#FF2DAA!important" in section


def test_gate724_concept_fidelity_uses_heavy_chrome_component_materials() -> None:
    css = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    section = css[css.index("/* Gate 7.24 — Neon concept-fidelity composition."):]
    assert "--concept-chrome:" in section
    assert ".bl-neon-logo-halo" in section
    assert ".bl-neon-score-shell" in section
    assert ".bl-neon-core-shell" in section
    assert ".bl-neon-component-shell" in section


def test_gate725_approved_concept_uses_distinct_identity_score_and_core_modules() -> None:
    css = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    section = css[css.index("/* Gate 7.25 — Approved concept chassis fidelity."):]
    assert "grid-template-columns:minmax(0,1fr) 214px 404px 214px minmax(0,1fr)" in section
    assert ".bl-neon-identity-shell" in section
    assert ".bl-neon-score-shell" in section
    assert ".bl-neon-core-shell" in section


def test_gate725_mascot_is_broadcast_readable() -> None:
    css = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    section = css[css.index("/* Gate 7.25 — Approved concept chassis fidelity."):]
    mascot = section[section.index(".bl-neon-mascot"):section.index(".bl-neon-record")]
    assert "font-size:30px!important" in mascot
    assert "font-weight:1000" in mascot
    assert "opacity" not in mascot


def test_gate725_material_highlight_does_not_slide() -> None:
    css = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    section = css[css.index("/* Gate 7.25 — Approved concept chassis fidelity."):]
    highlight = section[section.rindex(".bl-neon-identity-shell::after"):]
    assert "animation:none!important" in highlight
    assert "transform:none!important" in highlight
    assert "@keyframes neon-approved-material-breathe" in section


def test_gate725_preserves_sport_specific_base_contracts() -> None:
    css = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    assert ".bl-sport-baseball .bl-neon-command-diamond" in css
    assert "#24D8FF!important" in css
    assert ".bl-sport-softball .bl-neon-command-diamond" in css
    assert "#FF2DAA!important" in css


def test_gate725_r2_command_cockpit_meets_runtime_width_contract() -> None:
    css = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    section = css[css.index("/* Gate 7.25 — Approved concept chassis fidelity."):]
    core = section[section.index(".bl-neon-five-zone .bl-neon-command-core"):section.index(".bl-neon-five-zone .bl-neon-core-shell")]
    assert "width:424px" in core
    assert "grid-template-columns:minmax(0,1fr) 214px 404px 214px minmax(0,1fr)" in section


def test_gate800_renderer_uses_interlocking_chassis_geometry() -> None:
    css = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    section = css[css.index("/* Gate 8.0 — Neon Rendering Engine v1."):]
    assert ".bl-neon-home-identity .bl-neon-identity-shell" in section
    assert ".bl-neon-visitor-identity .bl-neon-identity-shell" in section
    assert ".bl-neon-score-shell" in section
    assert ".bl-neon-core-shell" in section
    assert "clip-path:polygon" in section


def test_gate800_renderer_has_optical_score_crystals() -> None:
    css = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    section = css[css.index("/* Gate 8.0 — Neon Rendering Engine v1."):]
    assert ".bl-neon-score-bay::after" in section
    assert "font-size:116px" in section
    assert "0 0 68px" in section


def test_gate800_renderer_keeps_mascot_broadcast_readable() -> None:
    css = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    section = css[css.index("/* Gate 8.0 — Neon Rendering Engine v1."):]
    mascot = section[section.index(".bl-neon-mascot"):section.index("/* Logo chamber")]
    assert "font-size:31px!important" in mascot
    assert "opacity:1!important" in mascot


def test_gate800_renderer_uses_stationary_material_motion_only() -> None:
    css = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    section = css[css.index("/* Gate 8.0 — Neon Rendering Engine v1."):css.index("/* Gate 10.0 — Approved Concept System Rebuild.")]
    assert "@keyframes neon-renderer-power-pulse" in section
    assert "translateX" not in section
    assert "transform:none!important" in section


def test_gate800_renderer_preserves_baseball_and_softball_color_contracts() -> None:
    css = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    assert ".bl-sport-baseball .bl-neon-command-diamond" in css
    assert "#24D8FF!important" in css
    assert ".bl-sport-softball .bl-neon-command-diamond" in css
    assert "#FF2DAA!important" in css


def test_gate810_renderer_preserves_vector_library_through_gate900_compositor() -> None:
    source = (ROOT / "static" / "csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
    assert "function neonGeometryAsset" in source
    assert "function neonLogoEndcap" in source
    assert 'data-neon-compositor="true-chassis-v1"' in source
    assert source.count("${neonLogoEndcap(") == 2
    assert source.count("${neonIdentityPanel(") >= 2
    assert source.count("${neonScoreBay(") >= 2


def test_gate810_vector_asset_library_exists() -> None:
    required = [
        "identity-pod-left.svg",
        "identity-pod-right.svg",
        "score-crystal.svg",
        "command-cockpit.svg",
        "logo-chamber.svg",
        "chassis-spine.svg",
        "component-frame.svg",
    ]
    for name in required:
        path = ROOT / "static" / "neon" / name
        assert path.is_file(), name
        text = path.read_text(encoding="utf-8")
        assert "<svg" in text and "viewBox=" in text


def test_gate810_css_uses_real_svg_masks() -> None:
    css = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    section = css[css.index("/* Gate 8.1 — Neon Vector Chassis Asset Renderer."):]
    assert 'url("/static/neon/identity-pod-left.svg")' in section
    assert 'url("/static/neon/score-crystal.svg")' in section
    assert 'url("/static/neon/command-cockpit.svg")' in section
    assert 'url("/static/neon/component-frame.svg")' in section


def test_gate810_geometry_dominates_visual_hierarchy() -> None:
    css = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    section = css[css.index("/* Gate 8.1 — Neon Vector Chassis Asset Renderer."):]
    assert "width:442px" in section
    assert "font-size:120px" in section
    assert "font-size:32px!important" in section
    assert "grid-template-columns:minmax(0,1fr) 226px 418px 226px minmax(0,1fr)" in section


def test_gate810_disables_translational_geometry_animation() -> None:
    css = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    section = css[css.index("/* Gate 8.1 — Neon Vector Chassis Asset Renderer."):css.index("/* Gate 10.0 — Approved Concept System Rebuild.")]
    assert "animation:none!important" in section
    assert "transform:none!important" in section
    assert "translateX" not in section


def test_gate820_masks_use_transparent_frame_geometry() -> None:
    for name in [
        "identity-pod-left.svg",
        "identity-pod-right.svg",
        "score-crystal.svg",
        "command-cockpit.svg",
        "logo-chamber.svg",
        "component-frame.svg",
    ]:
        text = (ROOT / "static" / "neon" / name).read_text(encoding="utf-8")
        assert 'fill-rule="evenodd"' in text, name
        assert '<path fill="black"' not in text, name


def test_gate820_scorebug_fidelity_hierarchy() -> None:
    css = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    section = css[css.index("/* Gate 8.2 — Neon Scorebug Asset Fidelity."):]
    assert "font-size:126px" in section
    assert "font-size:47px" in section
    assert "font-size:34px!important" in section
    assert "width:150px" in section


def test_gate820_has_sport_specific_cockpit_composition() -> None:
    css = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    section = css[css.index("/* Gate 8.2 — Neon Scorebug Asset Fidelity."):]
    assert ".bl-sport-football .bl-neon-command-core .bl-game-state" in section
    assert "font-size:62px" in section
    assert ".bl-neon-command-diamond .bl-baseball-state" in section
    assert "transform:scale(1.30)" in section


def test_gate820_reduces_white_connector_dominance() -> None:
    css = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    section = css[css.index("/* Gate 8.2 — Neon Scorebug Asset Fidelity."):]
    identity = section[section.index(".bl-neon-geometry-identity"):section.index(".bl-neon-geometry-score")]
    assert "var(--neon-team)" in identity
    assert "rgba(232,244,255,.76)" in identity
    assert "rgba(255,255,255,.95)" not in identity


def test_gate900_uses_true_seven_piece_chassis_dom() -> None:
    source = (ROOT / "static" / "csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
    assert "function neonLogoEndcap" in source
    assert 'data-neon-compositor="true-chassis-v1"' in source
    assert source.count("${neonLogoEndcap(") == 2
    assert source.count("${neonIdentityPanel(") >= 2
    assert source.count("${neonScoreBay(") >= 2


def test_gate900_has_dedicated_v2_geometry_assets() -> None:
    required = [
        "v2-logo-endcap-left.svg",
        "v2-logo-endcap-right.svg",
        "v2-identity-wing-left.svg",
        "v2-identity-wing-right.svg",
        "v2-score-crystal-left.svg",
        "v2-score-crystal-right.svg",
        "v2-cockpit-field.svg",
        "v2-cockpit-diamond.svg",
        "v2-continuous-rail.svg",
    ]
    for name in required:
        path = ROOT / "static" / "neon" / name
        assert path.is_file(), name
        text = path.read_text(encoding="utf-8")
        assert "<svg" in text and 'fill-rule="evenodd"' in text or name == "v2-continuous-rail.svg"


def test_gate900_css_declares_seven_column_compositor() -> None:
    css = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    section = css[css.index("/* Gate 9.0 — Neon True Chassis Compositor."):]
    assert "grid-template-columns:170px minmax(300px,1fr) 224px 430px 224px minmax(300px,1fr) 170px" in section
    assert ".bl-neon-logo-endcap" in section
    assert ".bl-neon-identity-wing" in section
    assert ".bl-neon-score-crystal" in section


def test_gate900_preserves_legacy_runtime_contract_classes() -> None:
    source = (ROOT / "static" / "csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
    assert "bl-neon-five-zone bl-neon-true-chassis" in source
    assert "bl-neon-identity-panel bl-neon-identity-wing" in source
    assert "bl-neon-score-bay bl-neon-score-crystal" in source
    assert "bl-neon-command-core" in source


def test_gate900_cockpit_remains_sport_specific() -> None:
    css = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    section = css[css.index("/* Gate 9.0 — Neon True Chassis Compositor."):]
    assert ".bl-sport-football .bl-neon-command-core .bl-game-state" in section
    assert ".bl-neon-command-diamond .bl-baseball-state" in section
    assert "transform:scale(1.34)" in section

def test_gate900_true_chassis_respects_frozen_220px_scorebug_footprint() -> None:
    css = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    section = css[css.index("/* Gate 9.0 — Neon True Chassis Compositor."):]
    block = section[section.index(".csrn-broadcast-layout.package-neon .bl-neon-true-chassis{"):]
    block = block[:block.index("}")]
    assert "height:220px;" in block
    assert "height:250px;" not in block


def test_gate910_converges_on_approved_compact_chassis_geometry() -> None:
    source = (ROOT / "static" / "csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
    css = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    section = css[css.index("/* Gate 9.1 — Approved Concept Visual Convergence."):css.index("/* Gate 10.0 — Approved Concept System Rebuild.")]
    assert 'data-neon-convergence="approved-v2"' in source
    assert "grid-template-columns:190px 370px 195px 330px 195px 370px 190px" in section
    assert "height:220px;" in section
    assert "width:330px!important" in section
    assert "width:154px" in section
    assert "font-size:37px" in section
    assert "font-size:112px" in section


def test_gate910_uses_team_energy_without_dominant_silver_slabs() -> None:
    css = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    section = css[css.index("/* Gate 9.1 — Approved Concept Visual Convergence."):css.index("/* Gate 10.0 — Approved Concept System Rebuild.")]
    assert "var(--neon-team-secondary),var(--neon-team)" in section
    assert "var(--neon-home) 0 47%" in section
    assert "var(--neon-visitor) 53% 100%" in section
    assert "rgba(236,247,255,.76)" not in section
    assert "#FF2DAA" not in section


def test_gate910_v2_assets_are_compact_and_directional() -> None:
    assets = ROOT / "static" / "neon"
    expected_views = {
        "v2-logo-endcap-left.svg": 'viewBox="0 0 230 220"',
        "v2-logo-endcap-right.svg": 'viewBox="0 0 230 220"',
        "v2-identity-wing-left.svg": 'viewBox="0 0 430 220"',
        "v2-identity-wing-right.svg": 'viewBox="0 0 430 220"',
        "v2-score-crystal-left.svg": 'viewBox="0 0 230 220"',
        "v2-score-crystal-right.svg": 'viewBox="0 0 230 220"',
        "v2-cockpit-field.svg": 'viewBox="0 0 360 220"',
        "v2-cockpit-diamond.svg": 'viewBox="0 0 360 220"',
        "v2-continuous-rail.svg": 'viewBox="0 0 1840 220"',
    }
    for name, view_box in expected_views.items():
        source = (assets / name).read_text(encoding="utf-8")
        assert view_box in source, name
        assert "<path" in source, name


def test_gate910_preserves_sport_specific_cockpit_colors() -> None:
    css = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    assert ".bl-sport-baseball .bl-neon-command-diamond .bl-diamond i.on" in css
    assert "#24D8FF!important" in css
    assert ".bl-sport-softball .bl-neon-command-diamond .bl-diamond i.on" in css
    assert "#FF2DAA!important" in css
    section = css[css.index("/* Gate 9.1 — Approved Concept Visual Convergence."):css.index("/* Gate 10.0 — Approved Concept System Rebuild.")]
    assert "transform:scale(1.12)" in section
    assert "grid-template-columns:112px 1fr" in section


def test_gate1000_rebuilds_the_neon_package_at_the_approved_scorebug_proportion() -> None:
    source = (ROOT / "static" / "csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
    css = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    section = css[css.index("/* Gate 10.0 — Approved Concept System Rebuild."):]
    assert 'data-neon-convergence="approved-v2"' in source
    assert source.count('scorebug:{zone:"top-full",width:1840,height:250,layer:100}') == 4
    assert '"top-full": {x: 40, y: 30, w: 1840, h: 280}' in source
    assert "grid-template-columns:210px 350px 190px 340px 190px 350px 210px" in section
    assert "height:270px;" in section
    assert "width:340px!important" in section


def test_gate1000_separates_team_scorebug_energy_from_shared_neon_modules() -> None:
    source = (ROOT / "static" / "csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
    css = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    section = css[css.index("/* Gate 10.0 — Approved Concept System Rebuild."):]
    assert "playerHeadshot: esc(state.player.headshot || \"\")" in source
    assert "bl-neon-portrait-bay" in source
    assert "bl-neon-player-silhouette" in source
    assert "display:none!important;content:none!important;background:none!important" in section
    assert "#24d8ff 0 18%" in section
    assert "#ff2daa 91%" in section
    assert "bl-neon-native-card>*:not(.bl-neon-component-shell)" in section


def test_gate1000_preserves_neon_sport_state_contracts() -> None:
    css = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    section = css[css.index("/* Gate 10.0 — Approved Concept System Rebuild."):]
    assert ".bl-sport-football .bl-neon-command-core .bl-game-state" in section
    assert ".bl-neon-command-diamond .bl-baseball-state" in section
    assert ".bl-neon-command-diamond .bl-diamond{transform:scale(1.16)}" in section


def test_gate1000_bottom_lane_uses_declared_ticker_geometry() -> None:
    source = (ROOT / "static" / "csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
    css = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    neon = source[source.index("digital_neon:"):source.index("collegiate_traditional:")]
    section = css[css.index("/* Gate 10.0 — Approved Concept System Rebuild."):]
    assert "const configuredStackHeight = Number(rule.stackAboveHeight);" in source
    assert "Number.isFinite(configuredStackHeight) && configuredStackHeight > 0" in source
    assert neon.count('ticker:{zone:"bottom-center",height:64,layer:110}') == 4
    assert neon.count('captions:{zone:"bottom-center",height:56,stackAboveHeight:64,layer:120}') == 4
    assert '.bl-component.bl-captions[data-zone="bottom-center"]' in section
    assert "transform:none!important" in section
    assert "height:56px!important" in section
    assert "max-height:56px" in section
    assert ".bl-neon-native-captions" in section
    assert ".bl-component.bl-ticker" in section
    assert "max-height:64px" in section


