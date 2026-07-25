from __future__ import annotations

from pathlib import Path

from tools.apply_phase_4_23 import apply


LEGACY_APP = '''from support_media_service import SupportMediaService


@app.post("/api/broadcasts/<broadcast_id>/load")
@require_auth
def load_planned_broadcast(broadcast_id: str):
    item = next((x for x in load_broadcasts() if x.get("broadcast_id") == broadcast_id), None)
    return jsonify(item)


@app.post("/api/initialize-broadcast")
@require_auth
def initialize_broadcast():
    state = load_state()
    return jsonify({"state": state, "readiness": readiness_payload(), "deprecated": True})


@app.post("/api/start-broadcast")
@require_auth
def start_broadcast():
    state = load_state()
    state["status"] = "live"
    save_state(state)
    return jsonify({"state": state})


@app.post("/api/resume-broadcast")
@require_auth
def resume_broadcast():
    state = load_state()
    state["review_mode"] = False
    save_state(state)
    return jsonify(state)


@app.post("/api/create-broadcast")
@require_auth
def create_broadcast():
    return jsonify({})
'''


def test_phase_4_23_migration_integrates_broadcast_lifecycle_service(
    tmp_path: Path,
) -> None:
    target = tmp_path / "app.py"
    target.write_text(LEGACY_APP, encoding="utf-8")

    assert apply(target) is True
    migrated = target.read_text(encoding="utf-8")

    assert (
        "from broadcast_lifecycle_service import BroadcastLifecycleService"
        in migrated
    )
    assert (
        "BROADCAST_LIFECYCLE_SERVICE: BroadcastLifecycleService | None = None"
        in migrated
    )
    assert "get_broadcast_lifecycle_service().load" in migrated
    assert "get_broadcast_lifecycle_service().initialize" in migrated
    assert "get_broadcast_lifecycle_service().start" in migrated
    assert "get_broadcast_lifecycle_service().resume" in migrated
    assert "item = next((x for x in load_broadcasts()" not in migrated
    assert apply(target) is False
