from pathlib import Path
from PIL import Image
import hashlib

ROOT = Path(__file__).resolve().parents[1]

def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()

def test_manifest_declares_adaptive_artwork() -> None:
    js = (ROOT/"static"/"csrn-neon-r2-engine.js").read_text(encoding="utf-8")
    assert 'artworkColorMode:"adaptive-blacklight-field-football"' in js

def test_all_four_sports_have_nonempty_constrained_masks() -> None:
    root = ROOT/"static"/"neon-r2"
    for sport in ("football","basketball","baseball","softball"):
        for side in ("left","right"):
            alpha = Image.open(root/f"{sport}-{side}-mask.png").convert("RGBA").getchannel("A")
            assert alpha.getbbox() is not None
            assert alpha.getpixel((0,0)) == 0
            assert alpha.getpixel((1023,639)) == 0
            coverage = sum(1 for value in alpha.getdata() if value > 8) / (1024*640)
            assert 0.006 <= coverage <= 0.35

def test_runtime_color_layers_are_enabled() -> None:
    css = (ROOT/"static"/"csrn-neon-r2-engine.css").read_text(encoding="utf-8")
    final = css.split("Gate 15.1 R34")[-1]
    assert "display:block !important" in final
    assert "background-color:var(--n2-left-raw) !important" in final
    assert "background-color:var(--n2-right-raw) !important" in final
    assert "mix-blend-mode:normal !important" in final

def test_r34_asset_hashes() -> None:
    root = ROOT/"static"/"neon-r2"
    assert digest(root/"football-neutral.png") == "D5B25AFAB7978E5B768D192F00D22D383FA8C8DDCBA8CD74E7D86B89B5CF8BED"
    assert digest(root/"football-left-mask.png") == "E4C37AED84DB2B7B0189D04CDE7024492F027AE3A3FEF6718C056128A03CBBA9"
    assert digest(root/"football-right-mask.png") == "642FE30FDA801922225FACB897B1796E52AF8CA8546042161150BD82DE3FC645"
    assert digest(root/"basketball-neutral.png") == "87FF6997E6AE6D4960C549D63F81D4E95A688AE602582B14A07EA4B196BB12D2"
    assert digest(root/"basketball-left-mask.png") == "C1D7627BD05D552EEE0EC74BE869EE3C863142835F3FD51942BD8A35AD9DD5C2"
    assert digest(root/"basketball-right-mask.png") == "78B356F5089811987F2102B8FB3EEF26A1F907B2174494B02DB1237949B270DD"
    assert digest(root/"baseball-neutral.png") == "D218FE3347F6CAADD4DD00B4B607F3EBE0613935929EE2C03D4E8A24F21216D9"
    assert digest(root/"baseball-left-mask.png") == "711919348ADDEF4F1763D6B483F47BC5FD7A7D03AA91C235952F4919F4364EC0"
    assert digest(root/"baseball-right-mask.png") == "A5B983F571478AE97421497B191BA138B3D18F1871F4EB1DD9338594831A5589"
    assert digest(root/"softball-neutral.png") == "37C1573FDD265827DA5913C42F7C71A8CC0A0B4DE854D588A92197E1DA15A6A9"
    assert digest(root/"softball-left-mask.png") == "0CD4BA3C18B18A1E6D88E6D4E30E35716A89CA94FFF5CA7DC1804CD4B86C75FD"
    assert digest(root/"softball-right-mask.png") == "0F174A367BB348E8B39FCC70D8EA10DA1591C753069AC5DD28C2A828E42DE367"
