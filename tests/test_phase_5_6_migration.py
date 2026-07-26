from __future__ import annotations

from pathlib import Path

from tools.apply_phase_5_6 import apply


LEGACY_APP = '''from routes.sponsor_routes import (
    SponsorRoutesDependencies,
    create_sponsor_blueprint,
)


@app.get("/api/packages")
@require_auth
def list_packages_route():
    return jsonify([])


@app.post("/api/packages")
@require_auth
def create_package_route():
    return jsonify({})


SPONSOR_ROUTES_BLUEPRINT = create_sponsor_blueprint(
    SponsorRoutesDependencies(require_auth=require_auth)
)
app.register_blueprint(SPONSOR_ROUTES_BLUEPRINT)


BROADCAST_LIFECYCLE_SERVICE: BroadcastLifecycleService | None = None


def get_broadcast_lifecycle_service() -> BroadcastLifecycleService:
    return BROADCAST_LIFECYCLE_SERVICE


@app.post("/api/broadcasts/<broadcast_id>/load")
@require_auth
def load_planned_broadcast(broadcast_id: str):
    return jsonify({})


@app.post("/api/initialize-broadcast")
@require_auth
def initialize_broadcast():
    return jsonify({})


@app.post("/api/start-broadcast")
@require_auth
def start_broadcast():
    return jsonify({})


@app.post("/api/resume-broadcast")
@require_auth
def resume_broadcast():
    return jsonify({})


@app.post("/api/create-broadcast")
@require_auth
def create_broadcast():
    return jsonify({})


@app.get("/api/broadcasts")
@require_auth
def list_broadcasts():
    return jsonify([])


GAME_OPERATIONS_SERVICE: GameOperationsService | None = None
'''


def test_phase_5_6_migration_registers_broadcast_blueprints(
    tmp_path: Path,
) -> None:
    target = tmp_path / "app.py"
    target.write_text(LEGACY_APP, encoding="utf-8")

    assert apply(target) is True
    migrated = target.read_text(encoding="utf-8")

    assert "from routes.broadcast_package_routes import (" in migrated
    assert "from routes.broadcast_lifecycle_routes import (" in migrated
    assert "from routes.broadcast_routes import (" in migrated
    assert "BROADCAST_PACKAGE_ROUTES_BLUEPRINT = create_broadcast_package_blueprint(" in migrated
    assert "BROADCAST_LIFECYCLE_ROUTES_BLUEPRINT = create_broadcast_lifecycle_blueprint(" in migrated
    assert "BROADCAST_ROUTES_BLUEPRINT = create_broadcast_blueprint(" in migrated
    assert "def get_broadcast_lifecycle_service()" in migrated
    assert "SPONSOR_ROUTES_BLUEPRINT = create_sponsor_blueprint(" in migrated
    assert "GAME_OPERATIONS_SERVICE: GameOperationsService | None = None" in migrated
    assert '@app.get("/api/packages")' not in migrated
    assert '@app.post("/api/broadcasts/<broadcast_id>/load")' not in migrated
    assert '@app.post("/api/create-broadcast")' not in migrated
    assert '@app.get("/api/broadcasts")' not in migrated
    assert apply(target) is False
