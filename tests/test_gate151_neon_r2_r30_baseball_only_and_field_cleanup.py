from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def test_r30_layout_assets_remain_valid_under_adaptive_pipeline() -> None:
    root = ROOT / "static" / "neon-r2"
    assert Image.open(root / "football-field-base.png").size == (1500, 146)
    for sport in ("football", "basketball", "baseball", "softball"):
        assert Image.open(root / f"{sport}-neutral.png").size == (1024, 640)


