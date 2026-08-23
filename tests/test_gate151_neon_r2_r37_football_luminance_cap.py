from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/"static"/"neon-r2"

def test_r37_luminance_contract_survives_r39() -> None:
    js=(ROOT/"static"/"csrn-neon-r2-engine.js").read_text(encoding="utf-8")
    assert 'artworkColorMode:"adaptive-blacklight-field-football"' in js
    assert Image.open(ASSETS/"football-new-luminance-cap.png").getchannel("A").getextrema()[1] >= 240


