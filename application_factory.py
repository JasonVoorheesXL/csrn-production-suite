from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence

from flask import Blueprint, Flask


@dataclass(frozen=True)
class RouteManifestEntry:
    """Normalized HTTP contract registered on a Flask application."""

    rule: str
    endpoint: str
    blueprint: str
    methods: tuple[str, ...]
    auth_required: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_route_manifest(application: Flask) -> tuple[RouteManifestEntry, ...]:
    """Return a stable, serializable view of every registered route."""

    entries: list[RouteManifestEntry] = []
    for rule in application.url_map.iter_rules():
        endpoint = str(rule.endpoint)
        blueprint = endpoint.split(".", 1)[0] if "." in endpoint else ""
        view = application.view_functions.get(endpoint)
        methods = tuple(sorted(set(rule.methods) - {"HEAD", "OPTIONS"}))
        entries.append(
            RouteManifestEntry(
                rule=str(rule.rule),
                endpoint=endpoint,
                blueprint=blueprint,
                methods=methods,
                auth_required=bool(
                    getattr(view, "_csrn_requires_auth", False)
                ),
            )
        )
    return tuple(
        sorted(
            entries,
            key=lambda entry: (
                entry.rule,
                entry.methods,
                entry.endpoint,
            ),
        )
    )


def duplicate_route_methods(
    manifest: Sequence[RouteManifestEntry],
) -> tuple[tuple[str, str, str, str], ...]:
    """Return duplicate rule/method registrations with both endpoints."""

    seen: dict[tuple[str, str], str] = {}
    duplicates: list[tuple[str, str, str, str]] = []
    for entry in manifest:
        for method in entry.methods:
            key = (entry.rule, method)
            previous = seen.get(key)
            if previous is not None:
                duplicates.append(
                    (entry.rule, method, previous, entry.endpoint)
                )
            else:
                seen[key] = entry.endpoint
    return tuple(duplicates)


def direct_route_endpoints(
    manifest: Sequence[RouteManifestEntry],
) -> tuple[str, ...]:
    """Return non-static endpoints that are not owned by a Blueprint."""

    return tuple(
        sorted(
            entry.endpoint
            for entry in manifest
            if not entry.blueprint and entry.endpoint != "static"
        )
    )


def create_application(
    import_name: str,
    *,
    blueprints: Sequence[Blueprint],
    secret_key: str,
    session_seconds: int,
    config_overrides: Mapping[str, Any] | None = None,
) -> Flask:
    """Construct, configure, register, and audit a CSRN Flask instance."""

    application = Flask(import_name)
    application.secret_key = secret_key
    application.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Strict",
        SESSION_COOKIE_SECURE=False,
        PERMANENT_SESSION_LIFETIME=session_seconds,
    )
    if config_overrides:
        application.config.update(dict(config_overrides))

    names = [blueprint.name for blueprint in blueprints]
    duplicate_names = sorted(
        name for name in set(names) if names.count(name) > 1
    )
    if duplicate_names:
        raise RuntimeError(
            "Duplicate Blueprint names: " + ", ".join(duplicate_names)
        )

    for blueprint in blueprints:
        application.register_blueprint(blueprint)

    manifest = build_route_manifest(application)
    duplicates = duplicate_route_methods(manifest)
    if duplicates:
        rendered = "; ".join(
            f"{method} {rule}: {first} / {second}"
            for rule, method, first, second in duplicates
        )
        raise RuntimeError(f"Duplicate route methods: {rendered}")

    direct_endpoints = direct_route_endpoints(manifest)
    if direct_endpoints:
        raise RuntimeError(
            "Routes must be Blueprint-owned: "
            + ", ".join(direct_endpoints)
        )

    application.extensions["csrn_route_manifest"] = tuple(
        entry.to_dict() for entry in manifest
    )
    application.extensions["csrn_blueprints"] = tuple(names)
    return application
