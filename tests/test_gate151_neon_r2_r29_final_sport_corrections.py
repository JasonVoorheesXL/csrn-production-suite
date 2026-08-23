from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def test_r29_sport_assets_remain_valid_under_adaptive_pipeline() -> None:
    root = ROOT / "static" / "neon-r2"
    for sport in ("football", "basketball", "baseball", "softball"):
        assert Image.open(root / f"{sport}-neutral.png").size == (1024, 640)
        assert Image.open(root / f"{sport}-left-mask.png").getchannel("A").getbbox() is not None
        assert Image.open(root / f"{sport}-right-mask.png").getchannel("A").getbbox() is not None


