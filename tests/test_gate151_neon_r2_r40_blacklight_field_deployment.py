from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "static" / "neon-r2"


def test_r40_assets_and_routes_exist() -> None:
    js = (ROOT/"static"/"csrn-neon-r2-engine.js").read_text(encoding="utf-8")
    css = (ROOT/"static"/"csrn-neon-r2-engine.css").read_text(encoding="utf-8")
    lab = (ROOT/"static"/"csrn-layout-lab.html").read_text(encoding="utf-8")
    assert 'VERSION="2.0.0-r40"' in js
    assert 'artworkColorMode:"adaptive-blacklight-field-football"' in js
    assert 'n2-r40 field-base' in js
    assert 'csrn-neon-r2-engine.css?v=15.1-r40' in lab
    assert 'csrn-neon-r2-engine.js?v=15.1-r40' in lab
    assert 'Gate 15.1 R40 adaptive blacklight football field deployment' in css


def test_r40_blacklight_assets_are_present_and_aligned() -> None:
    names = [
        'football-r40-field-neutral.png',
        'football-r40-field-home-primary-mask.png',
        'football-r40-field-home-secondary-mask.png',
        'football-r40-field-visitor-primary-mask.png',
        'football-r40-field-visitor-secondary-mask.png',
        'football-r40-ground-shadows.png',
        'football-r40-player-occlusion-underlay.png',
        'football-r40-ballcarrier-primary-cutout.png',
        'football-r40-ballcarrier-secondary-cutout.png',
        'football-r40-defender-primary-cutout.png',
        'football-r40-defender-secondary-cutout.png',
        'football-r40-cutout-master.png',
        'football-r40-luminance.png',
        'football-r40-shadows.png',
        'football-r40-highlights.png',
    ]
    for name in names:
        image = Image.open(ASSETS/name).convert("RGBA")
        assert image.size == (1260, 620)


def test_r40_masks_have_visible_alpha() -> None:
    for name in [
        'football-r40-field-home-primary-mask.png',
        'football-r40-field-visitor-primary-mask.png',
        'football-r40-ballcarrier-primary-cutout.png',
        'football-r40-defender-primary-cutout.png',
    ]:
        alpha = Image.open(ASSETS/name).convert("RGBA").getchannel("A")
        assert alpha.getbbox() is not None


def test_r40a_player_occlusion_is_fully_opaque_inside_silhouette() -> None:
    alpha = Image.open(ASSETS/'football-r40-player-occlusion-underlay.png').convert('RGBA').getchannel('A')
    assert alpha.getbbox() is not None
    assert alpha.getextrema()[1] == 255
    js = (ROOT/'static'/'csrn-neon-r2-engine.js').read_text(encoding='utf-8')
    css = (ROOT/'static'/'csrn-neon-r2-engine.css').read_text(encoding='utf-8')
    assert 'n2-r40 player-occlusion' in js
    assert 'var(--n2-r40-player-occlusion)' in css

def test_r40b_primary_uniform_masks_have_opaque_interiors() -> None:
    for name in [
        'football-r40-ballcarrier-primary-cutout.png',
        'football-r40-defender-primary-cutout.png',
    ]:
        assert Image.open(ASSETS/name).convert('RGBA').getchannel('A').getextrema()[1] == 255


def test_r40b_secondary_uniform_masks_are_fully_transparent() -> None:
    for name in [
        'football-r40-ballcarrier-secondary-cutout.png',
        'football-r40-defender-secondary-cutout.png',
    ]:
        alpha = Image.open(ASSETS/name).convert('RGBA').getchannel('A')
        assert alpha.getextrema() == (0, 0)
        assert alpha.getbbox() is None


def test_r40b_secondary_uniform_stripes_are_disabled() -> None:
    for name in [
        "football-r40-ballcarrier-secondary-cutout.png",
        "football-r40-defender-secondary-cutout.png",
    ]:
        image = Image.open(ASSETS/name).convert("RGBA")
        assert image.size == (1260, 620)
        assert image.getchannel("A").getbbox() is None

def test_r40c_helmet_groove_cleanup_assets_remain_aligned() -> None:
    for name in [
        "football-r40-cutout-master.png",
        "football-r40-luminance.png",
        "football-r40-shadows.png",
        "football-r40-highlights.png",
        "football-r40-player-occlusion-underlay.png",
    ]:
        image = Image.open(ASSETS/name).convert("RGBA")
        assert image.size == (1260, 620)


def test_r40c_secondary_masks_remain_disabled() -> None:
    for name in [
        "football-r40-ballcarrier-secondary-cutout.png",
        "football-r40-defender-secondary-cutout.png",
    ]:
        assert Image.open(ASSETS/name).convert("RGBA").getchannel("A").getbbox() is None

def test_r40d_helmet_stripe_erasure_assets_remain_aligned() -> None:
    for name in [
        "football-r40-cutout-master.png",
        "football-r40-player-occlusion-underlay.png",
        "football-r40-luminance.png",
        "football-r40-shadows.png",
        "football-r40-highlights.png",
    ]:
        image = Image.open(ASSETS/name).convert("RGBA")
        assert image.size == (1260, 620)


def test_r40d_secondary_uniform_masks_remain_disabled() -> None:
    for name in [
        "football-r40-ballcarrier-secondary-cutout.png",
        "football-r40-defender-secondary-cutout.png",
    ]:
        assert Image.open(ASSETS/name).convert("RGBA").getchannel("A").getbbox() is None

def test_r40e_primary_helmet_masks_have_no_center_gap() -> None:
    samples = {
        "football-r40-ballcarrier-primary-cutout.png": [(417,48),(420,72),(421,94)],
        "football-r40-defender-primary-cutout.png": [(635,202),(634,226),(632,248)],
    }
    for name, points in samples.items():
        alpha = Image.open(ASSETS/name).convert("RGBA").getchannel("A")
        for point in points:
            assert alpha.getpixel(point) >= 245
