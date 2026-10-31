"""Console appearance ("Night Game Glass", 2026-10-31).

The operator console's look, set from Settings > Appearance: one brand color,
the shape logos are framed in, and the frosted-glass effect. Broadcast
overlay colors are NOT here; those belong to the overlay themes.

Kept deliberately small so every install stays readable at night: the dark
base, text and meaning colors (amber = clock/flag, green = confirmed) are
fixed in static/csrn-console-glass.css. The brand color is checked against
white button text and a deeper shade is used for buttons when it would be
hard to read.

Also here: clean_plain_background(), which makes a logo's plain, edge-touching
background see-through, so a badge saved on a white square sits cleanly on
any frame shape (and on glass).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Mapping

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps

LOGO_SHAPES = ("circle", "square", "diamond", "glass")
GLASS_BLUR_RANGE = (4, 32)
FALLBACK_ACCENT = "#C9203B"
DEFAULT_APPEARANCE: dict[str, Any] = {
    # "" = follow the organization's primary color
    "accent": "",
    "logo_shape": "circle",
    "glass": True,
    "glass_blur": 18,
}

_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


def normalize_hex(value: Any) -> str:
    text = str(value or "").strip()
    if re.fullmatch(r"#?[0-9a-fA-F]{6}", text):
        return ("#" + text.lstrip("#")).upper()
    return ""


def normalize_appearance(raw: Mapping[str, Any] | None) -> dict[str, Any]:
    source = raw if isinstance(raw, Mapping) else {}
    shape = str(source.get("logo_shape", "") or "").strip().lower()
    try:
        blur = int(round(float(source.get("glass_blur", DEFAULT_APPEARANCE["glass_blur"]))))
    except (TypeError, ValueError):
        blur = DEFAULT_APPEARANCE["glass_blur"]
    glass = source.get("glass", DEFAULT_APPEARANCE["glass"])
    if isinstance(glass, str):
        glass = glass.strip().lower() not in {"false", "0", "off", "no", ""}
    return {
        "accent": normalize_hex(source.get("accent")),
        "logo_shape": shape if shape in LOGO_SHAPES else DEFAULT_APPEARANCE["logo_shape"],
        "glass": bool(glass),
        "glass_blur": max(GLASS_BLUR_RANGE[0], min(GLASS_BLUR_RANGE[1], blur)),
    }


def validate_appearance(raw: Mapping[str, Any] | None) -> list[str]:
    """Field names the operator sent that can't be used as given."""
    if not isinstance(raw, Mapping):
        return ["appearance"]
    bad = []
    accent = raw.get("accent", "")
    if accent not in ("", None) and not normalize_hex(accent):
        bad.append("accent")
    if "logo_shape" in raw and str(raw.get("logo_shape") or "").strip().lower() not in LOGO_SHAPES:
        bad.append("logo_shape")
    if "glass_blur" in raw:
        try:
            float(raw.get("glass_blur"))
        except (TypeError, ValueError):
            bad.append("glass_blur")
    return bad


def _channels(hex_color: str) -> tuple[int, int, int]:
    value = int(hex_color.lstrip("#"), 16)
    return (value >> 16) & 255, (value >> 8) & 255, value & 255


def _luminance(hex_color: str) -> float:
    def linear(channel: int) -> float:
        c = channel / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (linear(c) for c in _channels(hex_color))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def white_text_contrast(hex_color: str) -> float:
    return 1.05 / (_luminance(hex_color) + 0.05)


def button_shade(hex_color: str, minimum: float = 4.5) -> str:
    """The brand color, deepened just enough for white button text to read."""
    rgb = list(_channels(hex_color))
    shade = hex_color.upper()
    for _ in range(60):
        if white_text_contrast(shade) >= minimum:
            break
        rgb = [round(c * 0.93) for c in rgb]
        shade = "#" + "".join(f"{c:02X}" for c in rgb)
    return shade


def effective_appearance(appearance: Mapping[str, Any] | None, organization: Mapping[str, Any] | None) -> dict[str, Any]:
    """What the console paints with: the saved settings, the brand color
    resolved (organization primary when none is set) and its button shade."""
    settings = normalize_appearance(appearance)
    org = organization if isinstance(organization, Mapping) else {}
    accent = settings["accent"] or normalize_hex(org.get("primary_color")) or FALLBACK_ACCENT
    button = button_shade(accent)
    return {
        **settings,
        "accent_resolved": accent,
        "accent_button": button,
        "accent_adjusted": button != accent,
    }


# --- Logo background cleaning -------------------------------------------------

_WORK_SIZE = 600  # the background mask is found on a copy this size, then scaled up (soft edges for free)


def _border_points(width: int, height: int) -> list[tuple[int, int]]:
    points = [(x, 0) for x in range(width)] + [(x, height - 1) for x in range(width)]
    points += [(0, y) for y in range(1, height - 1)] + [(width - 1, y) for y in range(1, height - 1)]
    return points


def clean_plain_background(image: Image.Image, tolerance: int = 26) -> tuple[Image.Image | None, dict[str, Any]]:
    """Make a logo's plain background see-through.

    Only background that touches the image's edges is removed (flood-filled in
    from the border), so the same color inside the artwork stays: white
    lettering inside a badge's dark ring is kept. A busy background (a photo,
    a gradient) is left alone. Returns (cleaned RGBA image or None, info).
    """
    source = ImageOps.exif_transpose(image).convert("RGBA")
    width, height = source.size
    if width < 8 or height < 8:
        return None, {"code": "TOO_SMALL"}

    scale = min(1.0, _WORK_SIZE / max(width, height))
    work = source.resize((max(8, round(width * scale)), max(8, round(height * scale))), Image.Resampling.BILINEAR) if scale < 1 else source.copy()
    ww, wh = work.size
    border = _border_points(ww, wh)

    alpha = work.getchannel("A")
    if sum(1 for p in border if alpha.getpixel(p) < 16) / len(border) >= 0.5:
        return None, {"code": "ALREADY_TRANSPARENT"}

    rgb = work.convert("RGB")
    samples = [rgb.getpixel(p) for p in border]
    background = tuple(sorted(c[i] for c in samples)[len(samples) // 2] for i in range(3))
    close = sum(1 for c in samples if max(abs(c[i] - background[i]) for i in range(3)) <= tolerance)
    if close / len(samples) < 0.85:
        return None, {"code": "NO_PLAIN_BACKGROUND"}

    r, g, b = ImageChops.difference(rgb, Image.new("RGB", (ww, wh), background)).split()
    distance = ImageChops.lighter(ImageChops.lighter(r, g), b)
    mask = distance.point(lambda v: 255 if v <= tolerance else 0)
    for point in border:
        if mask.getpixel(point) == 255:
            ImageDraw.floodfill(mask, point, 128, thresh=0)
    edge_background = mask.point(lambda v: 255 if v == 128 else 0)
    removed_share = edge_background.histogram()[255] / (ww * wh)
    if removed_share < 0.01:
        return None, {"code": "NO_PLAIN_BACKGROUND"}

    # Grow one work-pixel into the anti-aliased fringe, soften, then scale up.
    soft = edge_background.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(0.6))
    if soft.size != (width, height):
        soft = soft.resize((width, height), Image.Resampling.BILINEAR)
    cleaned = source.copy()
    cleaned.putalpha(ImageChops.subtract(source.getchannel("A"), soft))
    box = cleaned.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
    if box:
        cleaned = cleaned.crop(box)
    return cleaned, {
        "code": "CLEANED",
        "background": "#" + "".join(f"{c:02X}" for c in background),
        "removed_share": round(removed_share, 3),
    }


def clean_logo_file(source: Path, target: Path) -> dict[str, Any]:
    """Clean `source` into the PNG `target` (the original is never touched)."""
    with Image.open(source) as opened:
        opened.load()
        cleaned, info = clean_plain_background(opened)
    if cleaned is None:
        return info
    target.parent.mkdir(parents=True, exist_ok=True)
    cleaned.save(target, format="PNG", optimize=True)
    return {**info, "width": cleaned.width, "height": cleaned.height}
