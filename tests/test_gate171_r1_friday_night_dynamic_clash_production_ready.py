from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def read(rel):
    return (ROOT/rel).read_text(encoding="utf-8")

def test_friday_dynamic_clash_production_waits_for_frozen_canvas():
    runtime=read("static/csrn-production-theme-runtime.js")
    assert 'async function ensureFridayNightDynamicClashReady' in runtime
    assert 'alias !== "friday_night_stadium" || mode !== "clash"' in runtime
    assert 'await renderResult.ready' in runtime
    assert '.bl-fns-clash-art' in runtime
    assert 'canvas.dataset.artReady !== "true"' in runtime
    assert 'root.dataset.productionClashReady = "true"' in runtime

def test_friday_frozen_engine_pipeline_remains_intact_as_pre_layer_fallback():
    engine=read("static/csrn-friday-night-stadium-engine.js")
    assert '/static/friday-night-stadium/clash/football-athletes-keyed.png' in engine
    assert '/static/friday-night-stadium/clash/football-field-background.png' in engine
    assert 'recolorUniformPixels' in engine
    assert 'state.visitor.primary' in engine
    assert 'state.home.primary' in engine
    assert 'paintClash(root,state)' in engine or 'paintClash(root, state)' in engine

def test_friday_football_clash_assets_exist():
    for rel in (
        "static/friday-night-stadium/clash/football-athletes-keyed.png",
        "static/friday-night-stadium/clash/football-field-background.png",
        "static/friday-night-stadium/vs-lightning-silver.png",
    ):
        p=ROOT/rel
        assert p.is_file(), rel
        assert p.stat().st_size > 1024, rel

def test_friday_dynamic_clash_keeps_native_idle_mode():
    runtime=read("static/csrn-production-theme-runtime.js")
    assert 'if (alias === "friday_night_stadium") return "clash";' in runtime
