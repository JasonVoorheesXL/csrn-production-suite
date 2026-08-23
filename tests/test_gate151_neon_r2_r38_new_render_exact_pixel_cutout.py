from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/"static"/"neon-r2"

def test_r38_new_render_contract_survives_r39() -> None:
    js=(ROOT/"static"/"csrn-neon-r2-engine.js").read_text(encoding="utf-8")
    assert 'artworkColorMode:"adaptive-blacklight-field-football"' in js
    assert Image.open(ASSETS/"football-neutral-smoke-master.png").size==(1024,640)
    assert Image.open(ASSETS/"football-new-home-primary-cutout.png").getchannel("A").getbbox() is not None
    assert Image.open(ASSETS/"football-new-visitor-primary-cutout.png").getchannel("A").getbbox() is not None


