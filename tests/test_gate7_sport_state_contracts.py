from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_gate73_sport_state_contracts_are_exported():
    source=(ROOT/"static"/"csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
    assert 'const VERSION = "1.7.0"' in source
    assert "BASEBALL_FUTURE_COMPONENTS" in source
    for name in ("lineup","atBat","onDeck","inTheHole","defensiveAlignment","lineScore"):
        assert f'"{name}"' in source
    assert "sportStateContracts" in source

def test_football_possession_is_persistent_and_visible():
    source=(ROOT/"static"/"csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
    css=(ROOT/"static"/"csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    assert "normalizePossession" in source
    assert 'data-possession="${possession}"' in source
    assert "bl-possession-${possession}" in source
    assert ".bl-possession" in css
    for family in ("modern","pixel","minimal","press","stadium","neon","collegiate","classic"):
        assert f".package-{family} .bl-possession" in css

def test_baseball_inning_half_is_explicit():
    source=(ROOT/"static"/"csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
    assert "normalizeInningHalf" in source
    assert 'data-inning-half="${inningHalf.toLowerCase()}"' in source
    assert 'inningArrow = inningHalf === "BOTTOM" ? "▼" : "▲"' in source
    assert 'inningShort = inningHalf === "BOTTOM" ? "BOT" : "TOP"' in source

def test_caption_lane_is_separated_from_ticker():
    css=(ROOT/"static"/"csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    assert '.bl-component.bl-captions[data-zone="bottom-center"]{transform:translateY(-78px)}' in css


