from hashlib import sha256
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "static" / "csrn-heritage-press-engine.js"
CSS = ROOT / "static" / "csrn-heritage-press-engine.css"
LAB = (ROOT / "static" / "csrn-layout-lab.html").read_text(encoding="utf-8")
SOURCE = ENGINE.read_text(encoding="utf-8")
STYLE = CSS.read_text(encoding="utf-8")
BIBLE = (ROOT / "CSRN_PROJECT_BIBLE.md").read_text(encoding="utf-8")
HANDOFF = (ROOT / "CSRN_THEME_CONTINUITY_HANDOFF.md").read_text(encoding="utf-8")


def _digest(relative: str) -> str:
    return sha256((ROOT / relative).read_bytes()).hexdigest().upper()


def test_gate14_isolated_engine_preserves_all_frozen_renderers() -> None:
    assert ENGINE.is_file() and CSS.is_file()
    # Neon + Friday-Night renderer hashes re-pinned Round 9 (2026-08-31) --
    # see test_gate116 / test_gate126. 8-Bit engine hashes are unchanged.
    assert _digest("static/csrn-broadcast-layout-engine.css") == "822755B7ABBA1F6D7439246904DB3AAEEFDE9649C617461457B73053672A02C9"
    assert _digest("static/csrn-broadcast-layout-engine.js") == "CE29D87BCB4DE6F5E21F00B8F61DBA76F18ABB5C340D2D5DF165BF8A6CD3B2A2"
    assert _digest("static/csrn-friday-night-stadium-engine.css") == "766686DAB90AABC40021919E65C01318FD426E86CB3E95A9B33CB72643E689AF"
    assert _digest("static/csrn-friday-night-stadium-engine.js") == "E2B3872D6D70A47FB733794CA02A46ADC4C3D9BAABBE192E6A17B96748926CBB"
    assert _digest("static/csrn-eight-bit-gameday-engine.css") == "6CFA49C22E2F9DE74E97E4BBA8FB9FE09E1F10F4AE64242066FBC9A728643BC4"
    assert _digest("static/csrn-eight-bit-gameday-engine.js") == "3830863DEE0B7424666096BD14D12B813D88BE6491394A85EE06162AAAC81206"


def test_gate141_layout_lab_loads_and_routes_heritage_once() -> None:
    assert LAB.count('csrn-heritage-press-engine.css?v=14.1') == 1
    assert LAB.count('csrn-heritage-press-engine.js?v=14.1') == 1
    assert 'window.CSRNHeritagePressEngine' in LAB
    assert 'packageId===heritageEngine.packageId?heritageEngine:' in LAB
    assert '...heritageEngine.validateManifests()' in LAB
    assert LAB.count('csrn-friday-night-stadium-engine.css?v=12.6') == 1
    assert LAB.count('csrn-eight-bit-gameday-engine.css?v=13.7') == 1


def test_gate141_full_page_and_opening_contract_remain_intact() -> None:
    assert 'const VERSION = "2.3.0"' in SOURCE
    assert 'const PACKAGE_ID = "heritage_press"' in SOURCE
    assert 'zone:"heritage-full-page",rect:{x:40,y:24,w:1840,h:1032}' in SOURCE
    assert 'data-scorebug-family="heritage-newspaper-r23"' in SOURCE
    assert 'data-module="video.board"' in SOURCE
    assert '.package-heritage-newspaper .hp-live-opening{position:absolute;inset:0;background:transparent}' in STYLE
    assert 'captionsEnabled ? captionMarkup(state) : ""' in SOURCE


def test_gate141_dispatch_uses_a_controlled_twelve_line_library() -> None:
    assert 'const LIVELY_LINES = Object.freeze([' in SOURCE
    for line_id in (
        'pay-dirt','shimmied-shook-cooked','grandstand-unhinged','coat-tails',
        'midnight-limited','scoreboard-tune','telegram-urgent','far-reaches',
        'swinging-shadows','rafters-hardwood','clerk-receipt','baseball-mischief',
    ):
        assert f'id:"{line_id}"' in SOURCE
    assert 'function stableIndex(seed, length)' in SOURCE
    assert 'String(dispatch.livelyLineId || "").toLowerCase() === "none"' in SOURCE
    assert 'operatorOverride' in SOURCE and 'operator_override' in SOURCE
    assert 'function buildDispatch(state, sport)' in SOURCE


def test_gate141_dispatch_is_sport_specific_and_fact_bound() -> None:
    for label in ('GRIDIRON DISPATCH','COURTSIDE DISPATCH','DIAMOND DISPATCH'):
        assert label in SOURCE
    for fn in ('pregameDispatch','footballDispatch','basketballDispatch','diamondDispatch','scoreConsequence'):
        assert f'function {fn}' in SOURCE
    for field in ('teamSide','playerName','yards','down','distance','scoreAfter','conversion','runSize','rbi','inningHalf'):
        assert field in SOURCE
    assert 'No verified dispatch copy entered.' in SOURCE
    assert 'LOREM' not in SOURCE.upper()
    assert '.hp-dispatch blockquote' in STYLE


def test_gate141_diamond_roles_stack_left_and_softball_owns_female_assets() -> None:
    assert 'class="hp-role-stack"' in SOURCE
    assert 'right:dispatchMarkup(state,sport)' in SOURCE
    assert 'softball ? ASSETS.softballBatter : ASSETS.baseballBatter' in SOURCE
    assert 'softball ? ASSETS.softballPitcher : ASSETS.baseballPitcher' in SOURCE
    assert 'softball ? "In The Circle" : "On The Mound"' in SOURCE
    for relative in (
        'static/heritage/press-softball-batter-1920s.png',
        'static/heritage/press-softball-pitcher-1920s.png',
    ):
        assert (ROOT / relative).is_file()
    assert '.hp-role-stack' in STYLE and 'grid-template-rows:minmax(0,1fr) minmax(0,1fr)' in STYLE
    assert _digest('static/heritage/press-softball-batter-1920s.png') == '0DDC8966DED0DCA3FDE396E2BF00C5BC4A2AFE22029FB1BA42D01C365BA24026'
    assert _digest('static/heritage/press-softball-pitcher-1920s.png') == '760C70AACB06AD7FED36A76AE043F725F256A75510CA621B09AA569BC6BFE48B'


def test_gate141_inning_line_score_is_ready_for_future_stats_engine() -> None:
    for fn in ('lineScoreValues','inningCount','lineTotal','lineScoreRow'):
        assert f'function {fn}' in SOURCE
    assert 'Math.max(9, Math.min(12' in SOURCE
    assert 'game.lineScore || game.line_score' in SOURCE
    assert 'data-module="game.lineScore"' in SOURCE
    assert 'innings[index] ?? "—"' in SOURCE
    assert 'repeat(var(--hp-inning-count)' in STYLE


def test_gate141_typography_keeps_r1_score_face_and_period_text_hierarchy() -> None:
    assert '--hp-score-face:Georgia,"Times New Roman",serif' in STYLE
    assert 'font-family:var(--hp-score-face)!important' in STYLE
    assert '--hp-news-head:' in STYLE and '--hp-news-gothic:' in STYLE and '--hp-news-mast:' in STYLE
    assert 'SPORTING NEWS TYPE STUDY' in STYLE


def test_gate141_newspaper_assets_and_texture_remain_protected() -> None:
    for relative in (
        'static/heritage/press-pitcher-1920s.png',
        'static/heritage/press-batter-1920s.png',
        'static/heritage/press-softball-pitcher-1920s.png',
        'static/heritage/press-softball-batter-1920s.png',
        'static/heritage/press-sponsor-truck.png',
        'static/heritage/press-player-placeholder.png',
        'static/heritage/press-newsprint-texture.png',
    ):
        assert (ROOT / relative).is_file()
    assert _digest('static/heritage/press-newsprint-texture.png') == '9163C1FED3EC186CD847CEA48F87C784003B49491EC68C96F19E02A6D0418155'
    assert 'filter:grayscale(1)' in STYLE


def test_gate141_documentation_preserves_both_fallback_layers() -> None:
    assert 'Gate 14.1 — Heritage Press live dispatch and diamond desk candidate' in BIBLE
    assert 'installed Gate 14.0 R2 files as its exact rollback fallback' in BIBLE
    assert 'unchanged shared-engine Heritage renderer remains the deeper R1 fallback' in BIBLE
    assert 'No production migration is authorized' in BIBLE
    assert 'Heritage Press — R2.3 dispatch implementation candidate' in HANDOFF
    assert 'Gate 14.0 R2 is installed and retained as the exact correction fallback' in HANDOFF
