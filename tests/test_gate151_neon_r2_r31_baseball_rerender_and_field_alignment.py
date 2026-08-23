from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def test_r31_visual_assets_remain_valid_under_adaptive_pipeline() -> None:
    root = ROOT / "static" / "neon-r2"
    for sport in ("football", "basketball", "baseball", "softball"):
        assert Image.open(root / f"{sport}-neutral.png").size == (1024, 640)


