from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
LAYER_ROOT = ROOT / "static/friday-night-stadium/clash/layers-v9"

MASKS = (
    "visitor-jersey-primary-mask.png",
    "visitor-pants-mask.png",
    "visitor-helmet-primary-mask.png",
    "visitor-number-trim-mask.png",
    "home-jersey-primary-mask.png",
    "home-pants-mask.png",
    "home-helmet-primary-mask.png",
    "home-number-trim-mask.png",
)

def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")

def alpha(name):
    return Image.open(LAYER_ROOT / name).convert("RGBA").getchannel("A")

def test_gate172_assets_share_authoritative_dimensions_and_are_nonempty():
    all_names = MASKS + (
        "football-neutral-equipment-anatomy.png",
        "football-neutral-equipment-anatomy-source-chroma.png",
        "football-uniform-texture.png",
        "football-highlights.png",
        "football-shadows.png",
    )
    for name in all_names:
        path = LAYER_ROOT / name
        assert path.is_file() and path.stat().st_size > 1024, name
        with Image.open(path) as image:
            if name == "football-neutral-equipment-anatomy-source-chroma.png":
                assert image.size[0] >= 1500 and image.size[1] >= 900, name
                continue
            assert image.size == (1672, 941), name
            if name == "football-neutral-equipment-anatomy.png":
                assert image.mode == "RGBA"
                assert image.getchannel("A").getbbox() is not None
                assert image.getpixel((0, 0))[3] == 0
    for name in MASKS:
        assert sum(value > 0 for value in alpha(name).getdata()) > 3000, name

def test_gate172_dynamic_masks_are_pairwise_disjoint():
    values = {name: list(alpha(name).getdata()) for name in MASKS}
    for index, left in enumerate(MASKS):
        for right in MASKS[index + 1:]:
            assert not any(a and b for a, b in zip(values[left], values[right])), (left, right)

def test_gate172_runtime_uses_v4_assets_and_selected_game_colors():
    runtime = read("static/csrn-production-theme-runtime.js")
    overlay = read("templates/overlay.html")
    for token in (
        "csrn-production-theme-binding-v46",
        'canvas.dataset.layeredSchema="friday-football-v10"',
        "clash/layers-v10/visitor-jersey-primary-mask.png",
        "clash/layers-v10/visitor-number-trim-mask.png",
        "clash/layers-v10/home-jersey-primary-mask.png",
        "clash/layers-v10/home-number-trim-mask.png",
        "football-neutral-equipment-anatomy.png?v=18.5-r12",
        "football-uniform-texture.png?v=18.5-r12",
        "constrainFridayColorMask",
        "protectWhite:true",
        "protectWarm=true",
        "protectEquipment=false",
        "protectEquipment:true",
        "isFridayNeutralEquipmentPixel",
        "warmSkinOrLeather",
        "luma>175 && chroma<74",
        "deriveFridayUniformReliefLayer",
        'ctx.globalCompositeOperation="color"',
        'ctx.globalCompositeOperation="source-over"',
        'ctx.globalCompositeOperation="soft-light"',
        'ctx.globalCompositeOperation="destination-in"',
        "state.visitor && state.visitor.primary",
        "state.visitor && state.visitor.secondary",
        "state.home && state.home.primary",
        "state.home && state.home.secondary",
    ):
        assert token in runtime
    assert "/static/csrn-production-theme-runtime.css?v=18.5-r11" in overlay
    assert "/static/csrn-production-theme-runtime.js?v=18.5-r11" in overlay

def test_gate172_r11_generated_players_have_core_uniform_coverage():
    regions = (
        ("visitor-jersey-primary-mask.png", (240, 175, 725, 505), .14),
        ("home-jersey-primary-mask.png", (1025, 175, 1515, 535), .18),
        ("visitor-pants-mask.png", (170, 375, 540, 705), .06),
        ("home-pants-mask.png", (940, 380, 1535, 690), .04),
    )
    for name, (left, top, right, bottom), minimum in regions:
        mask = alpha(name)
        total = (right - left) * (bottom - top)
        covered = sum(
            mask.getpixel((x, y)) > 0
            for y in range(top, bottom)
            for x in range(left, right)
        )
        assert covered / total >= minimum, name

def test_gate172_r11_trim_masks_stay_bounded_to_numbers_and_stripes():
    guards = (
        ("visitor-number-trim-mask.png", (80, 300, 250, 610), .04),
        ("home-number-trim-mask.png", (900, 120, 1070, 360), .04),
    )
    for name, (left, top, right, bottom), maximum in guards:
        mask = alpha(name)
        total = (right - left) * (bottom - top)
        covered = sum(
            mask.getpixel((x, y)) > 0
            for y in range(top, bottom)
            for x in range(left, right)
        )
        assert covered / total <= maximum, name

def test_gate172_r11_generated_player_base_is_neutral_under_uniform_masks():
    base = Image.open(LAYER_ROOT / "football-neutral-equipment-anatomy.png").convert("RGBA")
    pixels = base.load()
    samples = []
    for name in MASKS:
        mask = alpha(name)
        for y in range(0, base.height, 4):
            for x in range(0, base.width, 4):
                if mask.getpixel((x, y)) > 180 and pixels[x, y][3] > 80:
                    red, green, blue, _ = pixels[x, y]
                    samples.append(max(red, green, blue) - min(red, green, blue))
    assert len(samples) > 9000
    samples.sort()
    p95 = samples[int(len(samples) * .95)]
    assert sum(samples) / len(samples) < 18
    assert p95 < 72

def test_gate172_preserves_r7_fallback_and_protected_theme_boundaries():
    runtime = read("static/csrn-production-theme-runtime.js")
    engine = read("static/csrn-friday-night-stadium-engine.js")
    assert 'alias !== "friday_night_stadium" || mode !== "clash"' in runtime
    assert 'String(state.sport || "football").toLowerCase() !== "football"' in runtime
    assert "/static/friday-night-stadium/clash/football-athletes-keyed.png" in engine
    assert "paintFridayNightLayeredFootballClash" in runtime
    assert "eight_bit_gameday" in runtime
    assert "heritage_press" in runtime







