from __future__ import annotations

from pathlib import Path

from tools.apply_phase_4_13 import apply


LEGACY_APP = '''\
from logo_service import LogoService


def apply_change(changes):
    return changes


@app.get("/")
def control_panel():
    return "ok"


@app.get("/api/obs/status")
def obs_status():
    return jsonify(copy.deepcopy(last_obs_status))


@app.post("/api/obs/test")
def test_obs_connection():
    cfg = load_config()
    result = validate_obs_read_only(cfg.get("obs", {}))
    return jsonify(result)


def command_scorebug_visibility(visible):
    return set_scorebug_visibility(load_config().get("obs", {}), visible)


@app.post("/api/obs/scorebug-visibility")
def obs_scorebug_visibility():
    return jsonify(command_scorebug_visibility(True))


@app.post("/api/obs/program-visual-mode")
def obs_program_visual_mode():
    return jsonify(set_program_visual_mode({}, "graphic"))


@app.get("/api/config")
def get_config():
    return jsonify(load_config())
'''


def test_phase_4_13_migration_is_idempotent(tmp_path: Path) -> None:
    target = tmp_path / "app.py"
    target.write_text(LEGACY_APP, encoding="utf-8")

    first = apply(target)
    second = apply(target)
    text = target.read_text(encoding="utf-8")

    assert first is True
    assert second is False
    assert text.count("from obs_service import OBSService") == 1
    assert text.count("OBS_SERVICE: OBSService | None = None") == 1
    assert "get_obs_service().test_connection()" in text
    assert "get_obs_service().scorebug_visibility" in text
    assert "get_obs_service().program_visual_mode" in text
    assert "validate_obs_read_only(cfg.get(\"obs\", {}))" not in text
