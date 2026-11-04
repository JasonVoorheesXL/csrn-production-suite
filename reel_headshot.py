"""Reel headshots: a player's head cut out of a photo, for the figures in play reels.

Team photos come in every kind of background, so nothing here guesses where the
head is. The operator places an oval over it, and the oval is the scissors. Inside
it, the background is whatever the top and sides of the oval can reach without
crossing a change of colour; how big a change counts is the operator's setting, and
0 keeps the plain oval. A transparent PNG keeps its own cut-out. The operator sees
every result before it is saved.
"""
from __future__ import annotations

import io
import math
from dataclasses import dataclass

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps

WORK_SIZE = 480       # the long side the background is worked out at
OUTPUT_SIZE = 600     # the long side of the saved cut-out
MAX_TOLERANCE = 120
DEFAULT_TOLERANCE = 30
EDGE = (255, 253, 244, 255)   # the white scissor edge
KEY = (255, 0, 255)
SMALL_HEAD_PIXELS = 90


@dataclass
class CutHead:
    png: bytes = b""
    width: int = 0
    height: int = 0
    low_resolution: bool = False   # the head in this photo is small and will look soft


def open_photo(raw: bytes) -> Image.Image:
    image = Image.open(io.BytesIO(raw))
    image.load()
    return ImageOps.exif_transpose(image).convert("RGBA")


def _clean_number(value: float, low: float, high: float, fallback: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return fallback
    return fallback if not math.isfinite(number) else max(low, min(high, number))


def _inside(size: tuple[int, int]) -> Image.Image:
    oval = Image.new("L", size, 0)
    ImageDraw.Draw(oval).ellipse((1, 1, size[0] - 2, size[1] - 2), fill=255)
    return oval


def _without_background(crop: Image.Image, tolerance: int) -> Image.Image:
    """The part of the oval that its top and sides cannot reach across a colour change."""
    ratio = WORK_SIZE / max(crop.size)
    size = (max(16, round(crop.width * ratio)), max(16, round(crop.height * ratio)))
    small = crop.convert("RGB").resize(size, Image.LANCZOS)
    oval = _inside(size)
    marked = Image.composite(small, Image.new("RGB", size, KEY), oval)
    cx, cy, rx, ry = size[0] / 2, size[1] / 2, size[0] / 2 - 4, size[1] / 2 - 4
    # Round the oval from the left side, over the top, to the right side. The bottom is chin and neck.
    for step in range(0, 61):
        angle = math.radians(180 + step * 3)
        point = (round(cx + rx * math.cos(angle)), round(cy + ry * math.sin(angle)))
        if marked.getpixel(point) != KEY:
            ImageDraw.floodfill(marked, point, KEY, thresh=tolerance)
    kept = ImageChops.difference(marked, Image.new("RGB", size, KEY)).convert("L").point(lambda v: 255 if v > 0 else 0)
    # Specks around the hair go; only the piece joined to the middle of the head stays.
    kept = kept.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.MaxFilter(3))
    middle = (size[0] // 2, size[1] // 2)
    if kept.getpixel(middle) == 0:   # the fill got into the face: too strong a setting, so keep the whole oval
        return Image.new("L", crop.size, 255)
    ImageDraw.floodfill(kept, middle, 128)
    kept = kept.point(lambda v: 255 if v == 128 else 0)
    kept = kept.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.MinFilter(3))
    return kept.resize(crop.size, Image.BICUBIC).filter(ImageFilter.GaussianBlur(max(1.0, 2 / ratio))).point(lambda v: 255 if v > 127 else 0)


def _edged(crop: Image.Image, mask: Image.Image) -> bytes:
    """The cut-out on a white paper edge, trimmed to fit."""
    mask = mask.filter(ImageFilter.GaussianBlur(max(0.6, max(crop.size) / 700)))
    pad = max(6, round(max(crop.size) * 0.035))
    canvas = (crop.width + pad * 2, crop.height + pad * 2)
    placed = Image.new("L", canvas, 0)
    placed.paste(mask, (pad, pad))
    edge = placed.filter(ImageFilter.GaussianBlur(pad * 0.6)).point(lambda v: 255 if v > 18 else 0).filter(ImageFilter.GaussianBlur(max(0.6, pad * 0.08)))
    out = Image.new("RGBA", canvas, (0, 0, 0, 0))
    out.paste(EDGE, (0, 0), edge)
    out.paste(crop.convert("RGB"), (pad, pad), mask)
    out = out.crop(out.getbbox())
    # Small photos are enlarged too, so every cut-out draws the same on a figure.
    scale = OUTPUT_SIZE / max(out.size)
    out = out.resize((max(1, round(out.width * scale)), max(1, round(out.height * scale))), Image.LANCZOS)
    buffer = io.BytesIO()
    out.save(buffer, "PNG", optimize=True)
    return buffer.getvalue()


def cut_head(raw: bytes, *, x: float = 0.5, y: float = 0.3, width: float = 0.4, height: float = 0.5,
             tolerance: float = DEFAULT_TOLERANCE) -> CutHead:
    """Cut out the oval centred at (x, y) with the given size, all as shares of the photo's width and height."""
    image = open_photo(raw)
    x, y = _clean_number(x, 0, 1, 0.5), _clean_number(y, 0, 1, 0.3)
    width, height = _clean_number(width, 0.02, 1.5, 0.4), _clean_number(height, 0.02, 1.5, 0.5)
    tolerance = round(_clean_number(tolerance, 0, MAX_TOLERANCE, DEFAULT_TOLERANCE))
    rx, ry = max(8.0, width * image.width / 2), max(8.0, height * image.height / 2)
    cx, cy = x * image.width, y * image.height
    left, top = round(cx - rx), round(cy - ry)
    box = (left, top, round(cx + rx), round(cy + ry))
    # An oval hanging off the photo is filled out with nothing, so its shape stays true.
    crop = Image.new("RGBA", (box[2] - box[0], box[3] - box[1]), (0, 0, 0, 0))
    crop.paste(image, (-left, -top))
    oval = ImageChops.multiply(_inside(crop.size), crop.getchannel("A"))
    transparent = sum(image.getchannel("A").histogram()[:16]) > image.width * image.height * 0.05
    if not transparent and tolerance > 0:
        oval = ImageChops.multiply(oval, _without_background(crop, tolerance))
    if not oval.getbbox():
        raise ValueError("Nothing is left inside the oval.")
    png = _edged(crop, oval)
    done = Image.open(io.BytesIO(png))
    return CutHead(png=png, width=done.width, height=done.height, low_resolution=max(crop.size) < SMALL_HEAD_PIXELS)
