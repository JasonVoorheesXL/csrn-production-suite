"""Settings > Appearance (2026-10-31, "Night Game Glass").

* One brand color (defaults to the organization's primary), checked against
  white button text; a deeper shade is used for buttons when it won't read.
* Logo shape (circle / square / diamond / glass) and the glass effect.
* Logo cleaning: a plain, edge-touching background becomes see-through, the
  same color inside the artwork is kept, busy backgrounds are left alone.
"""
from __future__ import annotations

import random
from functools import wraps
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, request
from PIL import Image, ImageDraw

import appearance_service as appearance
import identity_service
from routes.appearance_routes import AppearanceRoutesDependencies, create_appearance_blueprint


# ---------------------------------------------------------------- settings
def test_defaults_and_bad_values_fall_back_safely() -> None:
    assert appearance.normalize_appearance(None) == {
        "accent": "", "logo_shape": "circle", "glass": True, "glass_blur": 18,
    }
    assert appearance.normalize_appearance(
        {"accent": "e0263f", "logo_shape": "Diamond", "glass": "off", "glass_blur": 99, "extra": 1}
    ) == {"accent": "#E0263F", "logo_shape": "diamond", "glass": False, "glass_blur": 32}
    assert appearance.normalize_appearance({"accent": "red", "logo_shape": "star"})["logo_shape"] == "circle"
    assert appearance.validate_appearance({"accent": "red", "logo_shape": "star", "glass_blur": "x"}) == [
        "accent", "logo_shape", "glass_blur",
    ]
    assert appearance.validate_appearance({"accent": "", "logo_shape": "glass"}) == []


def test_brand_color_defaults_to_the_organization_primary() -> None:
    effective = appearance.effective_appearance({}, {"primary_color": "#C9203B"})
    assert effective["accent_resolved"] == "#C9203B"
    assert effective["accent_button"] == "#C9203B"
    assert effective["accent_adjusted"] is False
    assert appearance.effective_appearance({}, {})["accent_resolved"] == appearance.FALLBACK_ACCENT


def test_a_light_brand_color_gets_a_readable_button_shade() -> None:
    effective = appearance.effective_appearance({"accent": "#E3A92B"}, {})
    assert effective["accent_resolved"] == "#E3A92B"
    assert effective["accent_adjusted"] is True
    assert appearance.white_text_contrast(effective["accent_button"]) >= 4.5
    # only as dark as needed: one step lighter would not pass
    lighter = "#" + "".join(
        f"{min(255, round(int(effective['accent_button'][i:i + 2], 16) / 0.93)):02X}" for i in (1, 3, 5)
    )
    assert appearance.white_text_contrast(lighter) < 4.5


def test_identity_profile_keeps_appearance_and_seeds_it_for_old_profiles() -> None:
    old = identity_service._normalize({"organization": {"name": "X"}}, existing_install=True)
    assert old["appearance"] == appearance.normalize_appearance(None)
    saved = identity_service._normalize(
        {"appearance": {"accent": "#2F6FEB", "logo_shape": "glass", "junk": True}}, existing_install=True
    )
    assert saved["appearance"] == {"accent": "#2F6FEB", "logo_shape": "glass", "glass": True, "glass_blur": 18}


# ---------------------------------------------------------------- logo cleaning
def badge_on_white(size: int = 400) -> Image.Image:
    image = Image.new("RGB", (size, size), (254, 254, 254))
    draw = ImageDraw.Draw(image)
    draw.ellipse((20, 20, size - 20, size - 20), fill=(0, 0, 0))
    draw.rectangle((size // 2 - 40, size // 2 - 40, size // 2 + 40, size // 2 + 40), fill=(255, 255, 255))
    return image


def test_cleaning_removes_the_edge_background_and_keeps_white_inside_the_badge() -> None:
    cleaned, info = appearance.clean_plain_background(badge_on_white())
    assert info["code"] == "CLEANED" and info["background"] == "#FEFEFE"
    assert cleaned is not None and cleaned.mode == "RGBA"
    alpha = cleaned.getchannel("A")
    assert alpha.getpixel((0, 0)) == 0  # corner background gone
    center = (cleaned.width // 2, cleaned.height // 2)
    assert cleaned.getpixel(center) == (255, 255, 255, 255)  # white inside the ring kept
    assert cleaned.size[0] < 400  # trimmed to the artwork


def test_busy_or_already_transparent_backgrounds_are_left_alone() -> None:
    rng = random.Random(7)
    noisy = Image.new("RGB", (120, 120))
    noisy.putdata([(rng.randrange(256), rng.randrange(256), rng.randrange(256)) for _ in range(120 * 120)])
    assert appearance.clean_plain_background(noisy) == (None, {"code": "NO_PLAIN_BACKGROUND"})

    transparent = Image.new("RGBA", (120, 120), (0, 0, 0, 0))
    ImageDraw.Draw(transparent).ellipse((10, 10, 110, 110), fill=(200, 20, 40, 255))
    assert appearance.clean_plain_background(transparent) == (None, {"code": "ALREADY_TRANSPARENT"})


# ---------------------------------------------------------------- routes
def build_client(tmp_path: Path):
    profile: dict[str, Any] = {
        "organization": {"primary_color": "#C9203B", "logo_path": "/static/organization/organization-logo.png"},
        "appearance": appearance.normalize_appearance(None),
    }
    static_dir = tmp_path / "static" / "organization"
    static_dir.mkdir(parents=True)
    badge_on_white(200).save(static_dir / "organization-logo.png")

    def require_auth(view):
        @wraps(view)
        def guarded(*args, **kwargs):
            if request.headers.get("X-Test-Auth") != "yes":
                return jsonify({"error": "AUTH_REQUIRED"}), 401
            return view(*args, **kwargs)
        return guarded

    def save(settings):
        profile["appearance"] = dict(settings)
        return profile["appearance"]

    def resolve(path: str):
        if not path.startswith("/static/organization/"):
            return None
        candidate = static_dir / path.rsplit("/", 1)[-1]
        return candidate if candidate.is_file() else None

    app = Flask(__name__)
    app.register_blueprint(create_appearance_blueprint(AppearanceRoutesDependencies(
        require_auth=require_auth,
        load_profile=lambda: profile,
        save_appearance=save,
        branding_logo=identity_service.branding_logo,
        resolve_logo=resolve,
        clean_logo_dir=static_dir,
        clean_logo_url_prefix="/static/organization",
    )))
    return app.test_client(), profile, static_dir


AUTH = {"X-Test-Auth": "yes"}


def test_reading_is_public_and_saving_needs_the_operator(tmp_path: Path) -> None:
    client, profile, _ = build_client(tmp_path)
    body = client.get("/api/appearance").get_json()
    assert body["effective"]["accent_resolved"] == "#C9203B"
    assert body["logo"] == "/static/organization/organization-logo.png"
    assert body["logo_shapes"] == ["circle", "square", "diamond", "glass"]

    assert client.post("/api/appearance", json={"logo_shape": "glass"}).status_code == 401
    saved = client.post("/api/appearance", json={"logo_shape": "glass", "accent": "#E3A92B"}, headers=AUTH)
    assert saved.status_code == 200
    assert profile["appearance"] == {"accent": "#E3A92B", "logo_shape": "glass", "glass": True, "glass_blur": 18}
    assert saved.get_json()["effective"]["accent_adjusted"] is True

    bad = client.post("/api/appearance", json={"logo_shape": "star"}, headers=AUTH)
    assert bad.status_code == 400 and bad.get_json()["fields"] == ["logo_shape"]


def test_clean_logo_writes_a_new_file_and_never_touches_the_original(tmp_path: Path) -> None:
    client, _, static_dir = build_client(tmp_path)
    original = (static_dir / "organization-logo.png").read_bytes()
    response = client.post(
        "/api/appearance/clean-logo", json={"logo_path": "/static/organization/organization-logo.png"}, headers=AUTH
    )
    body = response.get_json()
    assert response.status_code == 200 and body["code"] == "CLEANED"
    assert body["clean_path"].startswith("/static/organization/organization-logo-clean-")
    assert (static_dir / body["clean_path"].rsplit("/", 1)[-1]).is_file()
    assert (static_dir / "organization-logo.png").read_bytes() == original

    remote = client.post("/api/appearance/clean-logo", json={"logo_path": "https://example.com/x.png"}, headers=AUTH)
    assert remote.status_code == 400 and remote.get_json()["error"] == "LOGO_NOT_LOCAL"
