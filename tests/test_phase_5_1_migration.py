from __future__ import annotations

from pathlib import Path

from tools.apply_phase_5_1 import apply


LEGACY_APP = '''from broadcast_lifecycle_service import BroadcastLifecycleService


@app.get("/api/config")
@require_auth
def get_config():
    return jsonify(get_configuration_service().read().data["config"])


@app.post("/api/config")
@require_auth
def update_config():
    return jsonify({})


@app.get("/api/diagnostics")
@require_auth
def diagnostics():
    return jsonify(diagnostic_status())


@app.get("/api/state")
def get_state():
    return jsonify(public_state(load_state()))


def update_linked_broadcast_status(
    broadcast_id: str,
    status: str,
    extra: dict | None = None,
) -> None:
    pass


def readiness_payload() -> dict:
    return {"ready": True}


@app.get("/api/readiness")
@require_auth
def readiness():
    return jsonify(readiness_payload())


BROADCAST_LIFECYCLE_SERVICE: BroadcastLifecycleService | None = None


@app.get("/api/build-journal")
@require_auth
def build_journal():
    return jsonify(load_build_journal())


GAME_OPERATIONS_SERVICE: GameOperationsService | None = None
'''


def test_phase_5_1_migration_registers_system_routes_blueprint(
    tmp_path: Path,
) -> None:
    target = tmp_path / "app.py"
    target.write_text(LEGACY_APP, encoding="utf-8")

    assert apply(target) is True
    migrated = target.read_text(encoding="utf-8")

    assert "from routes.system_routes import (" in migrated
    assert "SystemRoutesDependencies" in migrated
    assert "SYSTEM_ROUTES_BLUEPRINT = create_system_blueprint(" in migrated
    assert "app.register_blueprint(SYSTEM_ROUTES_BLUEPRINT)" in migrated
    assert "def update_linked_broadcast_status(" in migrated
    assert "def readiness_payload()" in migrated
    assert '@app.get("/api/config")' not in migrated
    assert '@app.get("/api/diagnostics")' not in migrated
    assert '@app.get("/api/state")' not in migrated
    assert '@app.get("/api/readiness")' not in migrated
    assert '@app.get("/api/build-journal")' not in migrated
    assert apply(target) is False
