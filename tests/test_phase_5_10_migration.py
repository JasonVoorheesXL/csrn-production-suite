from __future__ import annotations

from pathlib import Path

from tools.apply_phase_5_10 import apply


BLUEPRINT_NAMES = (
    "PAGE_ROUTES_BLUEPRINT",
    "BROADCAST_PACKAGE_ROUTES_BLUEPRINT",
    "SPONSOR_ROUTES_BLUEPRINT",
    "ASSET_ROUTES_BLUEPRINT",
    "PERSONNEL_ROUTES_BLUEPRINT",
    "ROSTER_ROUTES_BLUEPRINT",
    "VENUE_ROUTES_BLUEPRINT",
    "SCHOOL_ROUTES_BLUEPRINT",
    "ASSOCIATION_ROUTES_BLUEPRINT",
    "LOGO_ROUTES_BLUEPRINT",
    "SECURITY_UPGRADE_ROUTES_BLUEPRINT",
    "OBS_ROUTES_BLUEPRINT",
    "SYSTEM_ROUTES_BLUEPRINT",
    "BROADCAST_LIFECYCLE_ROUTES_BLUEPRINT",
    "BROADCAST_ROUTES_BLUEPRINT",
    "LIVE_GAME_ROUTES_BLUEPRINT",
    "SUPPORT_ROUTES_BLUEPRINT",
    "GRAPHICS_ROUTES_BLUEPRINT",
)


def legacy_app() -> str:
    registrations = "\n".join(
        f"app.register_blueprint({name})" for name in BLUEPRINT_NAMES
    )
    return f'''from __future__ import annotations
from typing import Any
from flask import Flask, jsonify, render_template, request, session, send_from_directory, Response

SESSION_SECONDS = 3600
app = Flask(__name__)


def load_security():
    return {{"secret_key": "secret"}}


security = load_security()
app.secret_key = security["secret_key"]
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Strict",
    SESSION_COOKIE_SECURE=False,
    PERMANENT_SESSION_LIFETIME=SESSION_SECONDS,
)


def require_auth(func):
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper


{registrations}


def activate_upgrade_secret_key(secret_key: str) -> None:
    app.secret_key = secret_key


def local_ip() -> str:
    return "127.0.0.1"


if __name__ == "__main__":
    serve(app)
'''


def test_phase_5_10_migration_builds_application_factory(
    tmp_path: Path,
) -> None:
    target = tmp_path / "app.py"
    target.write_text(legacy_app(), encoding="utf-8")

    assert apply(target) is True
    migrated = target.read_text(encoding="utf-8")

    assert "from application_factory import create_application" in migrated
    assert "from flask import Flask, current_app, jsonify, session" in migrated
    assert "APPLICATION_BLUEPRINTS: list[Any] = []" in migrated
    assert migrated.count("APPLICATION_BLUEPRINTS.append(") == 18
    assert "app.register_blueprint(" not in migrated
    assert "app = Flask(__name__)" not in migrated
    assert "current_app.secret_key = secret_key" in migrated
    assert 'setattr(wrapper, "_csrn_requires_auth", True)' in migrated
    assert "def create_app(" in migrated
    assert "app = create_app()" in migrated
    assert "PERMANENT_SESSION_LIFETIME=SESSION_SECONDS" not in migrated
    assert apply(target) is False
