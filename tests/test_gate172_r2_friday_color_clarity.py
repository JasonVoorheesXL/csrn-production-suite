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
