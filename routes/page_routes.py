from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping

from flask import Blueprint, render_template


@dataclass(frozen=True)
class PageRoutesDependencies:
    """Injected application boundaries used by the public page Blueprint."""

    application_identity: Callable[[], Mapping[str, str]]


def create_page_blueprint(dependencies: PageRoutesDependencies) -> Blueprint:
    """Create public command-center and overlay page routes."""

    routes = Blueprint("page_routes", __name__)

    @routes.get("/")
    def control_panel():
        identity = dependencies.application_identity()
        return render_template(
            "index.html",
            app_product=identity["product"],
            app_version=identity["version"],
            app_build=identity["build"],
            copyright_year=2026,
            copyright_owner="Jason Chrest",
        )

    @routes.get("/overlay")
    def overlay():
        return render_template("overlay.html")

    return routes
