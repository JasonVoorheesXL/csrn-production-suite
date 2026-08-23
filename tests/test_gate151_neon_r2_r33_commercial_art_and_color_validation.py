from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def test_r33_controls_and_r34_adaptive_assets_coexist() -> None:
    lab = (ROOT / "static" / "csrn-layout-lab.html").read_text(encoding="utf-8")
    root = ROOT / "static" / "neon-r2"
    assert 'id="homeColor"' in lab
    assert 'id="visitorColor"' in lab
    assert 'id="colorPreset"' in lab
    for sport in ("football", "basketball", "baseball", "softball"):
        assert Image.open(root / f"{sport}-neutral.png").size == (1024, 640)
        assert Image.open(root / f"{sport}-left-mask.png").getchannel("A").getbbox() is not None
        assert Image.open(root / f"{sport}-right-mask.png").getchannel("A").getbbox() is not None


