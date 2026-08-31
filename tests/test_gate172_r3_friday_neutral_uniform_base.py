from pathlib import Path
import math

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
LAYERS = ROOT / "static" / "friday-night-stadium" / "clash" / "layers-v10"
RUNTIME = ROOT / "static" / "csrn-production-theme-runtime.js"

BASE = LAYERS / "football-neutral-equipment-anatomy.png"

MASKS = [
    "visitor-jersey-primary-mask.png",
    "home-jersey-primary-mask.png",
    "visitor-pants-mask.png",
    "home-pants-mask.png",
    "visitor-helmet-primary-mask.png",
    "home-helmet-primary-mask.png",
    "visitor-number-trim-mask.png",
    "home-number-trim-mask.png",
]

NEUTRAL_LAYERS = [
    "football-uniform-color-clarity-texture.png",
    "football-uniform-texture.png",
    "football-highlights.png",
    "football-shadows.png",
]

ALL_ASSETS = [
    "football-neutral-equipment-anatomy.png",
    *NEUTRAL_LAYERS,
    *MASKS,
]


def test_friday_v10_texture_highlight_shadow_layers_are_neutral():
    for name in NEUTRAL_LAYERS:
        img = Image.open(LAYERS / name).convert("RGBA")
        pixels = (
            img.get_flattened_data()
            if hasattr(img, "get_flattened_data")
            else img.getdata()
        )
        for r, g, b, a in pixels:
            if a:
                assert r == g == b, f"{name} contains color tint"


def test_friday_v10_runtime_binds_every_layer_asset():
    runtime = RUNTIME.read_text(encoding="utf-8")
    assert "const FRIDAY_LAYERED_CLASH_ASSETS" in runtime
    for name in ALL_ASSETS:
        assert (
            f"/static/friday-night-stadium/clash/layers-v10/{name}"
            in runtime
        ), f"runtime does not bind v10 asset: {name}"


def test_friday_v10_layered_painter_is_in_production_render_path():
    runtime = RUNTIME.read_text(encoding="utf-8")
    assert "async function paintFridayNightLayeredFootballClash" in runtime
    assert "await paintFridayNightLayeredFootballClash" in runtime
