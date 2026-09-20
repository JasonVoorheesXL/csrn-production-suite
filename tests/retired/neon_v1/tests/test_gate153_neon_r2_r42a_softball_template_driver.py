from pathlib import Path
from PIL import Image
import hashlib

ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/'static'/'neon-r2'

def test_r42a_supplemental_driver_is_loaded_after_frozen_neon_engine():
    lab=(ROOT/'static/csrn-layout-lab.html').read_text(encoding='utf-8')
    assert 'csrn-neon-softball-r42-driver.css?v=15.3-r42a' in lab
    assert 'csrn-neon-softball-r42-driver.js?v=15.3-r42a' in lab
    assert lab.index('csrn-neon-r2-engine.js?v=15.1-r40') < lab.index('csrn-neon-softball-r42-driver.js?v=15.3-r42a')

def test_r42a_driver_routes_softball_without_touching_other_sports():
    js=(ROOT/'static/csrn-neon-softball-r42-driver.js').read_text(encoding='utf-8')
    css=(ROOT/'static/csrn-neon-softball-r42-driver.css').read_text(encoding='utf-8')
    assert 'VERSION="1.0.0-r42a"' in js
    assert 'if(sport!=="softball")return result' in js
    assert 'opening.querySelectorAll(":scope > .n2-action")' in js
    assert 'window.CSRNNeonR2Engine=Object.freeze({...base,renderPackage})' in js
    assert 'softball-r42-scene-with-jersey-holes.png' in css
    assert 'var(--n2-left-raw)' in css
    assert 'var(--n2-right-raw)' in css

def test_r42a_runtime_assets_match_driver_contract():
    names=[
      'softball-r42-scene-with-jersey-holes.png',
      'softball-r42-home-jersey-alpha.png',
      'softball-r42-visitor-jersey-alpha.png',
      'softball-r42-home-jersey-color-slot.png',
      'softball-r42-visitor-jersey-color-slot.png',
      'softball-r42-home-jersey-texture-luminosity.png',
      'softball-r42-visitor-jersey-texture-luminosity.png',
    ]
    for name in names:
        image=Image.open(ASSETS/name).convert('RGBA')
        assert image.size==(1208,840)
        assert image.mode=='RGBA'

def test_r42a_masks_do_not_overlap_and_scene_holes_match_union():
    home=Image.open(ASSETS/'softball-r42-home-jersey-alpha.png').convert('RGBA').getchannel('A')
    visitor=Image.open(ASSETS/'softball-r42-visitor-jersey-alpha.png').convert('RGBA').getchannel('A')
    scene=Image.open(ASSETS/'softball-r42-scene-with-jersey-holes.png').convert('RGBA').getchannel('A')
    overlap=sum(1 for h,v in zip(home.getdata(),visitor.getdata()) if h>0 and v>0)
    assert overlap==0
    mismatches=sum(1 for h,v,s in zip(home.getdata(),visitor.getdata(),scene.getdata()) if s != 255-max(h,v))
    assert mismatches==0

def test_r42a_frozen_basketball_contract_still_passes_by_hash():
    # The supplemental driver must not rewrite frozen Neon renderer files.
    expected={
      'static/csrn-neon-r2-engine.js':'6AFEE5D838FB183F975E10E2F29AA75526C675167D7AABE21B2D99075F3DCA5C',
      'static/csrn-neon-r2-engine.css':'C9F1F9316EA1F16E86099F90DDD417075FF7111DA341867A8BFE2D7378EF043F',
    }
    for relative,digest in expected.items():
        assert hashlib.sha256((ROOT/relative).read_bytes()).hexdigest().upper()==digest
