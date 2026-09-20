from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "static" / "neon-r2"


def test_r35_controls_and_r36_cutout_assets_coexist() -> None:
    js = (ROOT/"static"/"csrn-neon-r2-engine.js").read_text(encoding="utf-8")
    lab = (ROOT/"static"/"csrn-layout-lab.html").read_text(encoding="utf-8")
    assert 'artworkColorMode:"adaptive-blacklight-field-football"' in js
    assert 'id="homeSecondaryColor"' in lab
    assert 'id="visitorSecondaryColor"' in lab
    assert Image.open(ASSETS/"football-cutout-master.png").size == (1024,640)
    assert Image.open(ASSETS/"football-home-primary-cutout.png").getchannel("A").getbbox() is not None
    assert Image.open(ASSETS/"football-visitor-primary-cutout.png").getchannel("A").getbbox() is not None


