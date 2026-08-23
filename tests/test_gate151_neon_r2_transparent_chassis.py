from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ASSET = ROOT / "static" / "neon-r2"
MASKS = [
    "football-left-mask.png","football-right-mask.png",
    "basketball-left-mask.png","basketball-right-mask.png",
    "baseball-left-mask.png","baseball-right-mask.png",
    "softball-left-mask.png","softball-right-mask.png",
    "neon-frame-left-core-mask.png","neon-frame-right-core-mask.png",
    "neon-frame-left-bloom-mask.png","neon-frame-right-bloom-mask.png",
    "neon-frame-openings-mask.png",
]

def _nonzero_fraction(image: Image.Image) -> float:
    total = image.width * image.height
    return sum(1 for value in image.getdata() if value) / total

def _alpha(path: Path) -> Image.Image:
    image = Image.open(path)
    assert image.mode == "RGBA", f"{path.name} must be RGBA"
    alpha = image.getchannel("A")
    lo, hi = alpha.getextrema()
    assert lo == 0 and hi > 0, path.name
    return alpha

def test_adaptive_player_masks_have_real_alpha_and_transparent_perimeters() -> None:
    asset_root = ROOT / "static" / "neon-r2"
    for sport in ("football", "basketball", "baseball", "softball"):
        for side in ("left", "right"):
            image = Image.open(asset_root / f"{sport}-{side}-mask.png").convert("RGBA")
            alpha = image.getchannel("A")
            assert image.size == (1024, 640)
            assert alpha.getbbox() is not None
            assert alpha.getpixel((0, 0)) == 0
            assert alpha.getpixel((1023, 639)) == 0


def test_central_clash_opening_is_not_covered_by_chassis() -> None:
    alpha = Image.open(ASSET / "neon-frame-neutral-chassis.png").convert("RGBA").getchannel("A")
    interior = alpha.crop((380,150,1540,700))
    assert _nonzero_fraction(interior) < 0.04

def test_frame_alpha_masks_remain_narrow() -> None:
    limits = {
        "neon-frame-left-core-mask.png":0.08,
        "neon-frame-right-core-mask.png":0.08,
        "neon-frame-left-bloom-mask.png":0.27,
        "neon-frame-right-bloom-mask.png":0.27,
    }
    for name, limit in limits.items():
        assert _nonzero_fraction(_alpha(ASSET / name)) < limit, name

def test_css_uses_alpha_masks_and_safe_stack() -> None:
    css = (ROOT / "static" / "csrn-neon-r2-engine.css").read_text(encoding="utf-8")
    assert css.count("mask-mode:alpha") >= 4
    assert ".n2-opening{position:absolute;z-index:5;" in css
    assert ".n2-action.neutral{z-index:5;" in css
    assert ".n2-action.lcolor{z-index:6;" in css
    assert ".n2-action.rcolor{z-index:7;" in css
    assert ".n2-frame{position:absolute;inset:0;z-index:18;" in css
    assert '.n2-page:before,.n2-page:after{content:"";position:absolute;inset:0;z-index:19;' in css


