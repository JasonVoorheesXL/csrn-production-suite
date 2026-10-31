"""Console appearance routes (2026-10-31): Settings > Appearance.

GET is public and read-only (colors and a logo path, nothing private) so the
console can paint before an operator signs in. Saving and logo cleaning need
the operator PIN.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from flask import Blueprint, jsonify, request

import appearance_service

RouteDecorator = Callable[[Callable[..., Any]], Callable[..., Any]]

_CLEAN_MESSAGES = {
    "ALREADY_TRANSPARENT": "This logo already has a see-through background.",
    "NO_PLAIN_BACKGROUND": "This logo's background isn't one plain color, so it was left as it is.",
    "TOO_SMALL": "This image is too small to clean.",
}


@dataclass(frozen=True)
class AppearanceRoutesDependencies:
    require_auth: RouteDecorator
    load_profile: Callable[[], Mapping[str, Any]]
    save_appearance: Callable[[Mapping[str, Any]], Mapping[str, Any]]
    branding_logo: Callable[[Mapping[str, Any]], str]
    # Resolve a "/static/..." logo path to a local file, or None when it isn't one.
    resolve_logo: Callable[[str], Path | None]
    # Folder for cleaned logos and the URL prefix it is served under.
    clean_logo_dir: Path
    clean_logo_url_prefix: str


def create_appearance_blueprint(dependencies: AppearanceRoutesDependencies) -> Blueprint:
    routes = Blueprint("appearance_routes", __name__)

    def payload() -> dict[str, Any]:
        profile = dependencies.load_profile()
        organization = profile.get("organization") or {}
        return {
            "appearance": appearance_service.normalize_appearance(profile.get("appearance")),
            "effective": appearance_service.effective_appearance(profile.get("appearance"), organization),
            "logo": dependencies.branding_logo(organization),
            "organization_name": str(organization.get("short_name") or organization.get("name") or ""),
            "organization_primary": appearance_service.normalize_hex(organization.get("primary_color"))
            or appearance_service.FALLBACK_ACCENT,
            "logo_shapes": list(appearance_service.LOGO_SHAPES),
        }

    @routes.get("/api/appearance")
    def read_appearance():
        return jsonify(payload())

    @routes.post("/api/appearance")
    @dependencies.require_auth
    def save_appearance():
        incoming = request.get_json(force=True, silent=True)
        bad = appearance_service.validate_appearance(incoming)
        if bad:
            return jsonify({"error": "INVALID_APPEARANCE", "fields": bad}), 400
        current = appearance_service.normalize_appearance(dependencies.load_profile().get("appearance"))
        merged = {**current, **{k: v for k, v in incoming.items() if k in current}}
        dependencies.save_appearance(appearance_service.normalize_appearance(merged))
        return jsonify(payload())

    @routes.post("/api/appearance/clean-logo")
    @dependencies.require_auth
    def clean_logo():
        incoming = request.get_json(force=True, silent=True) or {}
        logo_path = str(incoming.get("logo_path") or "").strip()
        source = dependencies.resolve_logo(logo_path)
        if source is None:
            return jsonify({
                "error": "LOGO_NOT_LOCAL",
                "message": "Only an uploaded logo can be cleaned. Upload the file first.",
            }), 400
        digest = hashlib.sha256(source.read_bytes()).hexdigest()[:10]
        target = dependencies.clean_logo_dir / f"organization-logo-clean-{digest}.png"
        info = appearance_service.clean_logo_file(source, target)
        if info.get("code") != "CLEANED":
            return jsonify({**info, "message": _CLEAN_MESSAGES.get(str(info.get("code")), "")})
        in_use = dependencies.branding_logo(dependencies.load_profile().get("organization") or {})
        for old in dependencies.clean_logo_dir.glob("organization-logo-clean-*.png"):
            # Keep the one the organization logo still points at until a save moves off it.
            if old != target and not in_use.split("?")[0].endswith(old.name):
                try:
                    old.unlink()
                except OSError:
                    pass
        return jsonify({
            **info,
            "original_path": logo_path,
            "clean_path": f"{dependencies.clean_logo_url_prefix}/{target.name}",
        })

    return routes
