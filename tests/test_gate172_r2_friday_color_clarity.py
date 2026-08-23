from pathlib import Path
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]

def read(rel): return (ROOT/rel).read_text(encoding="utf-8")

def test_r2_uses_color_clarity_texture_without_changing_player_masks():
    runtime=read("static/csrn-production-theme-runtime.js")
    texture=ROOT/"static/friday-night-stadium/clash/layers-v10/football-uniform-color-clarity-texture.png"
    assert texture.is_file() and texture.stat().st_size>1024
    with Image.open(texture) as image:
        assert image.size==(1672,941)
        assert image.mode=="RGBA"
    assert "football-uniform-color-clarity-texture.png?v=18.5-r12" in runtime
    assert "football-uniform-texture.png?v=18.5-r12" in runtime
    assert "ctx.globalAlpha=.54;" in runtime
    assert "ctx.globalAlpha=.30;" in runtime
    assert "ctx.globalAlpha=.22;" in runtime
    assert "ctx.globalAlpha=.14;" in runtime
    assert "ctx.globalAlpha=.10;" in runtime
    assert "ctx.globalAlpha=.82;" not in runtime

def test_r2_advances_only_runtime_and_cache_contract():
    runtime=read("static/csrn-production-theme-runtime.js")
    overlay=read("templates/overlay.html")
    assert "csrn-production-theme-binding-v46" in runtime
    assert "/static/csrn-production-theme-runtime.css?v=18.5-r11" in overlay
    assert "/static/csrn-production-theme-runtime.js?v=18.5-r11" in overlay
    assert 'canvas.dataset.layeredSchema="friday-football-v10"' in runtime
    for name in (
      "visitor-jersey-primary-mask.png","visitor-pants-mask.png",
      "visitor-helmet-primary-mask.png","visitor-number-trim-mask.png",
      "home-jersey-primary-mask.png","home-pants-mask.png",
      "home-helmet-primary-mask.png","home-number-trim-mask.png",
    ):
        assert name in runtime






