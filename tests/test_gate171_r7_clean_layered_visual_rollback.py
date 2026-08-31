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
