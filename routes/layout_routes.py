"""Layout Builder P1: the guided-customization builder's page + save endpoint.

GET  /layouts      the builder page (templates/layout_builder.html)
GET  /api/layouts  the customer's layouts document + the builder catalog
POST /api/layouts  validate and save the whole document; applied live

This is the first thing that WRITES the identity profile's `layouts` section
(P0 only ever read it). Validation is layout_builder_service's strict
sanitize_layouts_document(): a document with any error is rejected whole, so
nothing partially valid reaches disk.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from flask import Blueprint, jsonify, render_template, request

import layout_builder_service

RouteDecorator = Callable[[Callable[..., Any]], Callable[..., Any]]


@dataclass(frozen=True)
class LayoutRoutesDependencies:
    require_auth: RouteDecorator
    get_layouts: Callable[[], dict[str, Any]]
    save_layouts: Callable[[dict[str, Any]], dict[str, Any]]


def create_layout_blueprint(dependencies: LayoutRoutesDependencies) -> Blueprint:
    routes = Blueprint("layout_routes", __name__)

    def _json(payload: dict[str, Any], status: int = 200):
        response = jsonify(payload)
        response.status_code = status
        response.headers["Cache-Control"] = "no-store, max-age=0"
        return response

    @routes.get("/layouts")
    @dependencies.require_auth
    def layout_builder_page():
        return render_template("layout_builder.html")

    @routes.get("/api/layouts")
    @dependencies.require_auth
    def get_layouts():
        return _json({
            "layouts": dependencies.get_layouts(),
            "catalog": layout_builder_service.builder_catalog(),
        })

    @routes.post("/api/layouts")
    @dependencies.require_auth
    def save_layouts():
        incoming = request.get_json(force=True, silent=True)
        if not isinstance(incoming, dict) or "layouts" not in incoming:
            return _json({"error": "LAYOUTS_REQUIRED", "errors": ["body must be {\"layouts\": {...}}"]}, 400)
        document, errors = layout_builder_service.sanitize_layouts_document(incoming["layouts"])
        if errors or document is None:
            return _json({"error": "LAYOUTS_INVALID", "errors": errors}, 400)
        try:
            saved = dependencies.save_layouts(document)
        except OSError:
            return _json({"error": "LAYOUTS_SAVE_FAILED", "errors": ["The identity profile could not be written."]}, 500)
        # The overlay polls /api/runtime-state (layouts ride along on every
        # poll) and the pregame/halftime payload is built per request, so a
        # save is live within one poll -- no restart.
        return _json({"layouts": saved, "applied": "live"})

    return routes
