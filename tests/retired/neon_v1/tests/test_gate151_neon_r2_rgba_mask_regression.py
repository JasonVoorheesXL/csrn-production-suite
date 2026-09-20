from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def test_adaptive_clash_assets_use_rgba_and_authored_masks() -> None:
    asset_root = ROOT / "static" / "neon-r2"
    for sport in ("football", "basketball", "baseball", "softball"):
        neutral = Image.open(asset_root / f"{sport}-neutral.png").convert("RGBA")
        assert neutral.size == (1024, 640)
        for side in ("left", "right"):
            mask = Image.open(asset_root / f"{sport}-{side}-mask.png").convert("RGBA")
            assert mask.size == (1024, 640)
            assert mask.getchannel("A").getbbox() is not None


