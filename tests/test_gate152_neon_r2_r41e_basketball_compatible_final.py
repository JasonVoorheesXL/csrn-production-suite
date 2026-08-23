from pathlib import Path
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/"static"/"neon-r2"

def a(name): return Image.open(ASSETS/name).convert("RGBA").getchannel("A")

def test_r41e_preserves_frozen_r40_contract_and_adds_basketball_route():
    js=(ROOT/"static/csrn-neon-r2-engine.js").read_text(encoding="utf-8")
    css=(ROOT/"static/csrn-neon-r2-engine.css").read_text(encoding="utf-8")
    lab=(ROOT/"static/csrn-layout-lab.html").read_text(encoding="utf-8")
    assert 'VERSION="2.0.0-r40"' in js
    assert 'artworkColorMode:"adaptive-blacklight-field-football"' in js
    assert 'if(s.sport==="basketball")return' in js
    assert 'Gate 15.2 R41E compatible adaptive basketball clash deployment' in css
    assert 'csrn-neon-r2-engine.css?v=15.1-r40' in lab
    assert 'csrn-neon-r2-engine.js?v=15.1-r40' in lab

def test_r41e_layers_are_aligned():
    names=[p.name for p in ASSETS.glob("basketball-r41-*.png")]
    assert len(names)==15
    for name in names:
        assert Image.open(ASSETS/name).convert("RGBA").size==(1260,620)

def test_r41e_secondary_masks_empty_and_primary_masks_nonempty():
    assert a("basketball-r41-home-secondary-cutout.png").getbbox() is None
    assert a("basketball-r41-visitor-secondary-cutout.png").getbbox() is None
    assert a("basketball-r41-home-primary-cutout.png").getbbox() is not None
    assert a("basketball-r41-visitor-primary-cutout.png").getbbox() is not None

def test_r41e_full_court_masks_are_large_split_and_do_not_overlap_players():
    home=a("basketball-r41-home-court-glow-mask.png")
    visitor=a("basketball-r41-visitor-court-glow-mask.png")
    under=a("basketball-r41-player-occlusion-underlay.png")
    hp=sum(v>8 for v in home.getdata()); vp=sum(v>8 for v in visitor.getdata())
    assert hp>11000 and vp>11000
    assert home.crop((630,0,1260,620)).getbbox() is None
    assert visitor.crop((0,0,628,620)).getbbox() is None
    assert sum(1 for u,h,v in zip(under.getdata(),home.getdata(),visitor.getdata()) if u>8 and (h>8 or v>8))==0

def test_r41e_ball_channel_is_constrained():
    visible=sum(v>8 for v in a("basketball-r41-ball-channel-home-glow-mask.png").getdata())
    assert 40<=visible<=900


