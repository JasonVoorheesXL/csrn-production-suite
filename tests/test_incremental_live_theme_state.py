from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = (ROOT / "static" / "csrn-production-theme-runtime.js").read_text(encoding="utf-8")


def test_live_game_updates_are_incremental():
    assert "function patchLiveGameState" in RUNTIME
    assert "function patchThemeScoresAndPossession" in RUNTIME
    assert "patchLiveGameState(runtime);" in RUNTIME
    assert "patchThemeTicker(runtime);" in RUNTIME


def test_all_three_supported_themes_have_live_score_contracts():
    assert 'alias === "friday_night_stadium"' in RUNTIME
    assert 'alias === "eight_bit_gameday"' in RUNTIME
    assert 'alias === "heritage_press"' in RUNTIME
    assert '[data-module="home.score"]' in RUNTIME
    assert '[data-module="visitor.score"]' in RUNTIME
    assert '[data-bind="home.score"]' in RUNTIME
    assert '[data-bind="visitor.score"]' in RUNTIME


def test_ticker_tracks_seen_transient_items():
    assert "tickerKnownTransientKeys" in RUNTIME
    assert "tickerItemsForPresentation" in RUNTIME
    assert "freshTransient" in RUNTIME
    assert "tickerStateSignature" in RUNTIME


def test_player_activation_no_longer_depends_on_latest_event():
    block = RUNTIME.split("function playerActivationKey(runtime)", 1)[1].split(
        "function imageCandidate", 1
    )[0]
    assert "latest.id" not in block
    assert "activeEvents(runtime)" not in block


def test_destructive_signature_excludes_gameplay_and_ticker_history():
    block = RUNTIME.split("const signature = JSON.stringify([", 1)[1].split(
        "csrnLogThemeSignatureDiffR4", 1
    )[0]
    assert "runtime.home_score" not in block
    assert "runtime.visitor_score" not in block
    assert "runtime.down" not in block
    assert "runtime.distance" not in block
    assert "runtime.possession" not in block
    assert "activeEvents(runtime)" not in block
    assert "runtime.ticker_speed" not in block
    assert "runtime.ticker_pause" not in block


def test_digital_neon_was_not_added_to_incremental_contract():
    score_patch = RUNTIME.split("function patchThemeScoresAndPossession", 1)[1].split(
        "function patchLiveGameState", 1
    )[0]
    assert 'alias === "digital_neon"' not in score_patch
