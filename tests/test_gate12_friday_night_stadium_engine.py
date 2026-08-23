from hashlib import sha256
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "static" / "csrn-friday-night-stadium-engine.js"
CSS = ROOT / "static" / "csrn-friday-night-stadium-engine.css"
LAB = (ROOT / "static" / "csrn-layout-lab.html").read_text(encoding="utf-8")
BIBLE = (ROOT / "CSRN_PROJECT_BIBLE.md").read_text(encoding="utf-8")
SOURCE = ENGINE.read_text(encoding="utf-8")
STYLE = CSS.read_text(encoding="utf-8")


def _digest(relative: str) -> str:
    return sha256((ROOT / relative).read_bytes()).hexdigest().upper()


def test_gate12_isolated_engine_exists_and_preserves_frozen_neon() -> None:
    assert ENGINE.is_file()
    assert CSS.is_file()
    assert _digest("static/csrn-broadcast-layout-engine.css") == "4641A675512EA8C92E1408E421B690F862B49EA509D1009903A5F0B5EFB655EF"
    assert _digest("static/csrn-broadcast-layout-engine.js") == "961E39C83C94C1F12194E2D984247E576E96916FB8E5D35BBEC77EFF5B5EA68D"


def test_gate12_lab_loads_and_routes_the_approved_stadium_engine() -> None:
    assert LAB.count('csrn-friday-night-stadium-engine.css?v=12.6') == 1
    assert LAB.count('csrn-friday-night-stadium-engine.js?v=12.6') == 1
    assert 'window.CSRNFridayNightStadiumEngine' in LAB
    assert 'packageId===stadiumEngine.packageId?stadiumEngine:engine' in LAB
    assert 'const targetEngine=rendererFor(manifest.id)' in LAB


def test_gate12_owns_deterministic_led_glyph_geometry() -> None:
    assert 'const LED_GLYPHS = Object.freeze({' in SOURCE
    assert 'function ledSvg(' in SOURCE
    assert '<circle cx=' in SOURCE
    assert 'preserveAspectRatio=' in SOURCE
    for glyph in ('"0":', '"9":', '"A":', '"Z":', '":":'):
        assert glyph in SOURCE


def test_gate12_layout_reserves_top_ticker_board_and_bottom_caption() -> None:
    assert 'zone:"stadium-top-ticker",rect:{x:40,y:20,w:1840,h:62}' in SOURCE
    assert 'zone:"stadium-board",rect:{x:16,y:90,w:1888,h:958}' in SOURCE
    assert 'state.captionsEnabled=activeComponents.includes("captions")' in SOURCE
    assert 'state.captionsEnabled ? captionMarkup(state) : ""' in SOURCE
    assert 'placements.captions=' not in SOURCE
    assert '.bl-fns-top-ticker' in STYLE
    assert '.bl-fns-caption' in STYLE


def test_gate121_captions_and_controls_cannot_clip_the_cabinet() -> None:
    assert '.bl-fns-video-board>.bl-fns-caption' in STYLE
    assert 'position:absolute' in STYLE
    assert '.bl-fns-football-bottom{position:static' in STYLE
    assert '.bl-fns-board{grid-template-rows:72px minmax(0,1fr)' in STYLE


def test_gate121_clash_uses_project_vs_art_and_rebalanced_logos() -> None:
    assert '/static/friday-night-stadium/vs-lightning-silver.png' in SOURCE
    assert '.bl-fns-versus img' in STYLE
    assert '.bl-fns-team-tower>.bl-fns-logo' in STYLE


def test_gate121_diamond_swaps_bases_into_the_inning_tier() -> None:
    assert 'class="bl-fns-role-bases"' in SOURCE
    assert SOURCE.count('<small>BASES</small>') == 0
    assert '.bl-fns-diamond-center' in STYLE


def test_gate122_clash_renderer_is_sport_aware_and_team_colored() -> None:
    assert 'const VERSION = "1.5.0"' in SOURCE
    assert 'function paintClash(root, state)' in SOURCE
    assert 'bl-fns-clash-${sport}' in SOURCE
    for sport in ('football', 'basketball', 'baseball', 'softball'):
        assert f'.bl-fns-clash-{sport} .bl-fns-field-art' in STYLE
    for sport in ('football', 'basketball', 'baseball', 'softball'):
        assert f'{sport}:"/static/friday-night-stadium/clash/{sport}-athletes-keyed.png"' in SOURCE
    assert 'function recolorUniformPixels(data, visitorColor, homeColor)' in SOURCE
    assert '.bl-fns-clash-art' in STYLE
    assert '.bl-fns-clash-basketball .bl-fns-field-art' in STYLE
    assert '.bl-fns-versus img{width:205px;height:205px' in STYLE


def test_gate122_football_removes_timeouts_and_duplicate_plain_state() -> None:
    assert 'VISITOR TOL' not in SOURCE and 'HOME TOL' not in SOURCE
    assert 'bl-fns-football-state' not in SOURCE
    assert SOURCE.count('<small>DOWN</small>') == 1
    assert SOURCE.count('<small>QUARTER</small>') == 1
    assert '.bl-fns-football-control-bank{grid-template-columns:1fr' in STYLE
    assert '.bl-fns-football-control-bank .bl-fns-primary-clock' in STYLE


def test_gate123_possession_is_football_only() -> None:
    assert 'function possessionBall(sport, active)' in SOURCE
    assert 'bl-fns-football-possession' in SOURCE
    assert '.bl-fns-possession-ball' in STYLE
    assert '.bl-fns-possession-panel{display:none}' in STYLE
    assert 'const marker = sport === "football" ? possessionBall(sport,possession) : ""' in SOURCE


def test_gate122_basketball_timeouts_are_mirrored() -> None:
    assert 'bl-fns-timeout-visitor' in SOURCE
    assert 'bl-fns-timeout-home' in SOURCE
    assert '${timeoutDots(state.game.homeTimeouts)}<small>TIMEOUTS ▶</small>' in SOURCE
    assert '<small>◀ TIMEOUTS</small>${timeoutDots(state.game.visitorTimeouts)}' in SOURCE


def test_gate122_diamond_roles_move_into_score_towers() -> None:
    assert 'bl-fns-diamond-role' in SOURCE
    assert 'side === "visitor" ? "AT BAT" : "PITCHER"' in SOURCE
    assert '.bl-fns-diamond-role' in STYLE
    assert '.bl-fns-diamond-center' in STYLE


def test_gate123_tower_logos_are_reduced_ten_percent() -> None:
    assert '.bl-fns-team-tower>.bl-fns-logo img{width:90%;height:90%' in STYLE


def test_gate124_uses_distinct_photographic_sport_backdrops() -> None:
    for sport, asset in (
        ('football', 'football-field-background.png'),
        ('basketball', 'basketball-court-background.png'),
        ('baseball', 'baseball-ballpark-background.png'),
        ('softball', 'softball-ballpark-background.png'),
    ):
        relative = f'static/friday-night-stadium/clash/{asset}'
        assert (ROOT / relative).is_file()
        assert f'{sport}:"/static/friday-night-stadium/clash/{asset}"' in SOURCE
    assert 'const CLASH_BACKDROPS = Object.freeze({' in SOURCE
    assert 'data-field-asset="${CLASH_BACKDROPS[sport]}"' in SOURCE


def test_gate124_moves_both_rhe_strips_into_lower_control_bank() -> None:
    assert 'data-rhe-side="${side}"' in SOURCE
    assert '${rheMarkup(state,"visitor")}<strong aria-label="INNING">' in SOURCE
    assert '${rheMarkup(state,"home")}</div>' in SOURCE
    assert '.bl-fns-diamond-center>.bl-fns-rhe-visitor{grid-column:1}' in STYLE
    assert '.bl-fns-diamond-center>.bl-fns-rhe-home{grid-column:4;' in STYLE


def test_gate125_rhe_values_use_led_geometry_and_bases_are_unlabeled() -> None:
    assert SOURCE.count('"bl-fns-rhe-led"') == 3
    assert '.bl-fns-rhe-led{' in STYLE
    assert '<small>BASES</small>' not in SOURCE
    assert '<span class="bl-fns-role-bases">${baseDiamond(game.bases)}</span>' in SOURCE
    assert '.bl-fns-diamond-center>.bl-fns-role-bases{display:grid;place-items:center' in STYLE


def test_gate125_freeze_candidate_labels_are_expanded_and_scaled() -> None:
    assert '<small>QUARTER</small>' in SOURCE
    assert '<small>QTR</small>' not in SOURCE
    assert '.bl-fns-football-bottom small{font-size:26px;' in STYLE
    assert '.bl-fns-diamond-bottom small{font-size:33px;' in STYLE
    assert '.bl-fns-basketball-bottom small{font-size:20px;' in STYLE


def test_gate12_only_video_opening_changes_presentation_content() -> None:
    assert 'function videoModeFor(' in SOURCE
    for mode in ('"clash"', '"highlight"', '"sponsor"', '"player"', '"broadcast"'):
        assert mode in SOURCE
    assert 'data-module="video.board"' in SOURCE
    assert 'data-video-mode=' in SOURCE
    assert 'bl-fns-video-replacement' in SOURCE
    assert 'data-video-mode="broadcast"><div class="bl-fns-video-feed">LIVE VIDEO</div>' in SOURCE


def test_gate12_football_and_basketball_have_distinct_instruments() -> None:
    assert 'function footballControls(' in SOURCE
    assert '<small>DOWN</small>' in SOURCE and '<small>TO GO</small>' in SOURCE
    assert 'function basketballControls(' in SOURCE
    assert SOURCE.count('<small>FOULS</small>') == 2
    assert 'state.game.visitorFouls' in SOURCE
    assert 'state.game.homeFouls' in SOURCE
    assert 'BONUS' in SOURCE
    assert 'scoreText.padStart(3," ")' in SOURCE
    assert 'data-led-capacity="${sport === "basketball" ? "3" : "2"}"' in SOURCE


def test_gate12_diamond_layout_includes_all_required_live_state() -> None:
    for contract in ('AT BAT', 'PITCHER', 'INNING', 'BALLS', 'STRIKES', 'OUTS'):
        assert contract in SOURCE
    assert 'homeHits' in SOURCE and 'visitorHits' in SOURCE
    assert 'homeErrors' in SOURCE and 'visitorErrors' in SOURCE
    assert 'class="bl-fns-rhe bl-fns-rhe-${side}"' in SOURCE
    assert '<span>R<b>' in SOURCE and '<span>H<b>' in SOURCE and '<span>E<b>' in SOURCE


def test_gate12_venue_identity_has_an_explicit_character_rule() -> None:
    assert 'combined.length <= 24 ? combined : school' in SOURCE
    assert 'STADIUM' in SOURCE


def test_gate12_bible_locks_the_approved_sport_contracts() -> None:
    assert 'Gate 12.0 — Friday Night Stadium approved system contract' in BIBLE
    assert 'Only the large central video-board opening changes content' in BIBLE
    assert 'fixed-width three-digit field' in BIBLE
    assert 'At Bat' in BIBLE and 'Pitcher' in BIBLE
    assert 'No production migration is authorized by this gate' in BIBLE


