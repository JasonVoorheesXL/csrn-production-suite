from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "app.py"


SERVICE_SETUP = '''\
def load_obs_status() -> dict[str, Any]:
    with obs_status_lock:
        return copy.deepcopy(last_obs_status)


def save_obs_status(status: dict[str, Any]) -> None:
    with obs_status_lock:
        last_obs_status.clear()
        last_obs_status.update(copy.deepcopy(status))


def update_obs_visual_state(mode: str) -> dict[str, Any]:
    with lock:
        state = load_state()
        push_history(state)
        state["visual_mode"] = mode
        save_state(state)
        return state


OBS_SERVICE: OBSService | None = None


def get_obs_service() -> OBSService:
    global OBS_SERVICE
    if OBS_SERVICE is None:
        OBS_SERVICE = OBSService(
            load_config=load_config,
            load_status=load_obs_status,
            save_status=save_obs_status,
            validate_obs=validate_obs_read_only,
            set_scorebug_visibility=set_scorebug_visibility,
            set_program_visual_mode=set_program_visual_mode,
            update_visual_state=update_obs_visual_state,
        )
    return OBS_SERVICE


'''


ROUTE_BLOCK = '''\
@app.get("/api/obs/status")
@require_auth
def obs_status():
    result = get_obs_service().status()
    return jsonify(result.data["status"])


@app.post("/api/obs/test")
@require_auth
def test_obs_connection():
    result = get_obs_service().test_connection()
    return jsonify(result.data["obs"])


def command_scorebug_visibility(visible: bool) -> dict[str, Any]:
    result = get_obs_service().scorebug_visibility(visible)
    if not result.ok:
        raise OBSConnectionError(
            str(result.data.get("message", result.code))
        )
    return result.data["obs"]


@app.post("/api/obs/scorebug-visibility")
@require_auth
def obs_scorebug_visibility():
    incoming = request.get_json(force=True) or {}
    result = get_obs_service().scorebug_visibility(incoming.get("visible"))
    if result.code == "VISIBLE_MUST_BE_BOOLEAN":
        return jsonify({"error": result.code}), 400
    if result.code == "OBS_COMMAND_BLOCKED":
        return jsonify(
            {
                "error": result.code,
                "message": result.data.get("message", ""),
            }
        ), 409
    return jsonify(result.data["obs"])


@app.post("/api/obs/program-visual-mode")
@require_auth
def obs_program_visual_mode():
    incoming = request.get_json(force=True) or {}
    result = get_obs_service().program_visual_mode(incoming.get("mode", ""))
    if result.code == "OBS_COMMAND_BLOCKED":
        return jsonify(
            {
                "error": result.code,
                "message": result.data.get("message", ""),
            }
        ), 409
    return jsonify(result.data)


'''


def apply(path: Path = APP_PATH) -> bool:
    text = path.read_text(encoding="utf-8")
    original = text

    import_marker = "from logo_service import LogoService\n"
    import_line = "from obs_service import OBSService\n"
    if import_line not in text:
        if import_marker not in text:
            raise RuntimeError("LogoService import marker was not found.")
        text = text.replace(import_marker, import_marker + import_line, 1)

    setup_marker = '@app.get("/")\n'
    if "OBS_SERVICE: OBSService | None = None" not in text:
        if setup_marker not in text:
            raise RuntimeError("Control-panel route marker was not found.")
        text = text.replace(setup_marker, SERVICE_SETUP + setup_marker, 1)

    route_start = text.find('@app.get("/api/obs/status")')
    route_end = text.find('@app.get("/api/config")', route_start)
    if route_start < 0 or route_end < 0:
        raise RuntimeError("OBS route block markers were not found.")
    current_routes = text[route_start:route_end]
    if "get_obs_service().status()" not in current_routes:
        text = text[:route_start] + ROUTE_BLOCK + text[route_end:]

    required = (
        "from obs_service import OBSService",
        "OBS_SERVICE: OBSService | None = None",
        "get_obs_service().test_connection()",
        "get_obs_service().scorebug_visibility",
        "get_obs_service().program_visual_mode",
    )
    missing = [marker for marker in required if marker not in text]
    if missing:
        raise RuntimeError("Incomplete OBSService integration: " + ", ".join(missing))

    if text != original:
        path.write_text(text, encoding="utf-8")
        return True
    return False


def main() -> None:
    changed = apply()
    print(
        "Phase 4.13 OBSService integration applied."
        if changed
        else "Phase 4.13 OBSService integration already present."
    )


if __name__ == "__main__":
    main()
