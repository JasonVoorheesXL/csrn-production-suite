from pathlib import Path
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]

def read(rel): return (ROOT/rel).read_text(encoding="utf-8")

def count(rel):
    return sum(v>0 for v in Image.open(ROOT/rel).convert("RGBA").getchannel("A").getdata())

def test_r7_restores_clean_r2_layer_population():
    assert count("static/friday-night-stadium/clash/layers/football-visitor-primary-mask.png") == 84312
    assert count("static/friday-night-stadium/clash/layers/football-visitor-secondary-mask.png") == 10822
    assert count("static/friday-night-stadium/clash/layers/football-home-primary-mask.png") == 103215
    assert count("static/friday-night-stadium/clash/layers/football-home-secondary-mask.png") == 11245

def test_r7_restores_r2_compositor_treatment_without_losing_current_binding():
    js=read("static/csrn-production-theme-runtime.js")
    overlay=read("templates/overlay.html")
    assert "csrn-production-theme-binding-v46" in js
    assert "secondaryAlpha=.68" not in js
    assert 'ctx.drawImage(tintFridayMask(visitorSecondary,visitorAccent,width,height),0,0);' in js
    assert 'ctx.drawImage(tintFridayMask(homeSecondary,homeAccent,width,height),0,0);' in js
    assert 'canvas.dataset.layeredSchema="friday-football-v10"' in js
    assert 'ctx.globalCompositeOperation="color";' in js
    assert 'ctx.globalCompositeOperation="soft-light";' in js
    assert 'ctx.globalAlpha=.54;' in js
    assert "/static/csrn-production-theme-runtime.js?v=18.5-r11" in overlay
    assert "/static/csrn-production-theme-runtime.css?v=18.5-r11" in overlay






