from pathlib import Path
from PIL import Image
import hashlib, json

ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/'static'/'neon-r2'

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()

def test_r43a_supplemental_driver_load_order():
    lab=(ROOT/'static/csrn-layout-lab.html').read_text(encoding='utf-8')
    assert 'csrn-neon-baseball-r43-driver.css?v=15.3-r43a' in lab
    assert 'csrn-neon-baseball-r43-driver.js?v=15.3-r43a' in lab
    assert lab.index('csrn-neon-r2-engine.js?v=15.1-r40') < lab.index('csrn-neon-softball-r42-driver.js?v=15.3-r42a') < lab.index('csrn-neon-baseball-r43-driver.js?v=15.3-r43a')

def test_r43a_routes_only_baseball_and_preserves_wrapper_chain():
    js=(ROOT/'static/csrn-neon-baseball-r43-driver.js').read_text(encoding='utf-8')
    css=(ROOT/'static/csrn-neon-baseball-r43-driver.css').read_text(encoding='utf-8')
    assert 'VERSION="1.0.0-r43a"' in js
    assert 'if(sport!=="baseball")return result' in js
    assert 'const result=base.renderPackage' in js
    assert 'window.CSRNNeonR2Engine=Object.freeze({...base,renderPackage})' in js
    assert 'baseball-r43-scene-with-jersey-holes.png' in css
    assert 'var(--n2-left-raw)' in css and 'var(--n2-right-raw)' in css

def test_r43a_assets_are_exact_native_rgba_canvas():
    names=['baseball-r43-scene-with-jersey-holes.png', 'baseball-r43-home-jersey-alpha.png', 'baseball-r43-home-jersey-color-slot.png', 'baseball-r43-home-jersey-texture-luminosity.png', 'baseball-r43-visitor-jersey-alpha.png', 'baseball-r43-visitor-jersey-color-slot.png', 'baseball-r43-visitor-jersey-texture-luminosity.png']
    for name in names:
        image=Image.open(ASSETS/name)
        assert image.size==(1163,665)
        assert image.mode=='RGBA'

def test_r43a_masks_do_not_overlap_and_scene_holes_match_union():
    home=Image.open(ASSETS/'baseball-r43-home-jersey-alpha.png').convert('RGBA').getchannel('A')
    visitor=Image.open(ASSETS/'baseball-r43-visitor-jersey-alpha.png').convert('RGBA').getchannel('A')
    scene=Image.open(ASSETS/'baseball-r43-scene-with-jersey-holes.png').convert('RGBA').getchannel('A')
    assert sum(1 for h,v in zip(home.getdata(),visitor.getdata()) if h>0 and v>0)==0
    assert sum(1 for h,v,s in zip(home.getdata(),visitor.getdata(),scene.getdata()) if s != 255-max(h,v))==0
    assert sum(1 for v in home.getdata() if v>0)==17308
    assert sum(1 for v in visitor.getdata() if v>0)==2961

def test_r43a_contract_has_one_home_and_one_visitor_primary_slot():
    contract=json.loads((ASSETS/'baseball-r43-template-driver-contract.json').read_text(encoding='utf-8'))
    assert contract['canvas']=={'width':1163,'height':665,'origin':'top-left'}
    assert set(contract['runtime_color_slots'])=={'home_primary','visitor_primary'}
    assert len(contract['stack_bottom_to_top'])==5
    assert contract['runtime_color_slots']['home_primary']['subject']=='male batter visible jersey fabric'
    assert contract['runtime_color_slots']['visitor_primary']['subject']=='male catcher visible jersey sleeves'

def test_r43a_preserves_softball_and_frozen_neon_files():
    expected={
      'static/csrn-neon-r2-engine.js':'6AFEE5D838FB183F975E10E2F29AA75526C675167D7AABE21B2D99075F3DCA5C',
      'static/csrn-neon-r2-engine.css':'C9F1F9316EA1F16E86099F90DDD417075FF7111DA341867A8BFE2D7378EF043F',
      'static/csrn-neon-softball-r42-driver.js':'3221E0FF67B6D27D11B479132BB2925CC41AA6BDB19C6833924D5F53346C25A2',
      'static/csrn-neon-softball-r42-driver.css':'9B5A83A59DBA7CD6ABC5B3FDFCCC63E08BE12F45A52D2F81010F9F397842B556',
    }
    for relative,expected_digest in expected.items():
        assert digest(ROOT/relative)==expected_digest
