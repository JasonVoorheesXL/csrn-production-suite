from pathlib import Path
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]

def read(rel): return (ROOT/rel).read_text(encoding="utf-8")

def test_layered_compositor_is_production_owned_and_friday_football_scoped():
    js=read("static/csrn-production-theme-runtime.js")
    assert "async function paintFridayNightLayeredFootballClash" in js
    assert "async function paintFridayNightStandaloneFootballPlayers" in js
    assert 'alias !== "friday_night_stadium" || mode !== "clash"' in js
    assert 'await paintFridayNightLayeredFootballClash(scoreTarget, alias, activeVideoMode, state);' in js
    assert 'canvas.dataset.layeredDynamic="false"' in js
    assert 'canvas.dataset.layeredSchema="friday-football-standalone-v1"' in js

def test_layered_assets_exist_and_share_authoritative_dimensions():
    rels=(
      "static/friday-night-stadium/clash/layers/football-neutral-base.png",
      "static/friday-night-stadium/clash/layers/football-uniform-texture.png",
      "static/friday-night-stadium/clash/layers/football-visitor-primary-mask.png",
      "static/friday-night-stadium/clash/layers/football-visitor-secondary-mask.png",
      "static/friday-night-stadium/clash/layers/football-home-primary-mask.png",
      "static/friday-night-stadium/clash/layers/football-home-secondary-mask.png",
    )
    dims=set()
    for rel in rels:
      p=ROOT/rel
      assert p.is_file() and p.stat().st_size>1024, rel
      with Image.open(p) as im: dims.add(im.size)
    assert dims=={(1672,941)}

def test_primary_and_secondary_masks_are_nonempty_and_disjoint_per_side():
    def alpha(rel): return Image.open(ROOT/rel).convert("RGBA").getchannel("A")
    vp=alpha("static/friday-night-stadium/clash/layers/football-visitor-primary-mask.png")
    vs=alpha("static/friday-night-stadium/clash/layers/football-visitor-secondary-mask.png")
    hp=alpha("static/friday-night-stadium/clash/layers/football-home-primary-mask.png")
    hs=alpha("static/friday-night-stadium/clash/layers/football-home-secondary-mask.png")
    assert sum(v>0 for v in vp.getdata())>50000
    assert sum(v>0 for v in hp.getdata())>50000
    assert sum(v>0 for v in vs.getdata())>5000
    assert sum(v>0 for v in hs.getdata())>5000
    assert not any(a and b for a,b in zip(vp.getdata(),vs.getdata()))
    assert not any(a and b for a,b in zip(hp.getdata(),hs.getdata()))

def test_standalone_compositor_uses_finished_palette_v2_players():
    js=read("static/csrn-production-theme-runtime.js")
    for token in (
      "state.visitor && state.visitor.primary",
      "state.home && state.home.primary",
      "/static/friday-night-stadium/players/palette-v2/visitor/visitor-28-",
      "/static/friday-night-stadium/players/palette-v2/home/home-31-",
      "const width=1920, height=1080",
      "fridayStandaloneVisibleBounds",
      "const pad=Math.round(Math.max(imageWidth,imageHeight)*.035)",
      "const playerHeight=height*.76",
      "centerX:width*.178",
      "centerX:width*.822"
    ): assert token in js

def test_runtime_and_cache_advance_to_gate171_r3():
    js=read("static/csrn-production-theme-runtime.js")
    overlay=read("templates/overlay.html")
    assert "csrn-production-theme-binding-v46" in js
    assert "/static/csrn-production-theme-runtime.css?v=19.2-r18-r3" in overlay
    assert "/static/csrn-production-theme-runtime.js?v=19.2-r18-r3" in overlay


def test_enhanced_secondary_masks_include_uniform_detail_polish():
    def count(rel):
        return sum(v>0 for v in Image.open(ROOT/rel).convert("RGBA").getchannel("A").getdata())
    assert count("static/friday-night-stadium/clash/layers/football-visitor-secondary-mask.png") > 10000
    assert count("static/friday-night-stadium/clash/layers/football-home-secondary-mask.png") > 10000


def test_r5_perspective_masks_have_zero_primary_secondary_overlap():
    def alpha(rel):
        return Image.open(ROOT/rel).convert("RGBA").getchannel("A")
    vp=alpha("static/friday-night-stadium/clash/layers/football-visitor-primary-mask.png")
    vs=alpha("static/friday-night-stadium/clash/layers/football-visitor-secondary-mask.png")
    hp=alpha("static/friday-night-stadium/clash/layers/football-home-primary-mask.png")
    hs=alpha("static/friday-night-stadium/clash/layers/football-home-secondary-mask.png")
    assert not any(a and b for a,b in zip(vp.getdata(),vs.getdata()))
    assert not any(a and b for a,b in zip(hp.getdata(),hs.getdata()))





