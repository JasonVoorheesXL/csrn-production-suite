from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_FILE = ROOT / "app.py"


def _replace_block(
    text: str,
    start_marker: str,
    end_marker: str,
    replacement: str,
) -> str:
    start = text.find(start_marker)
    if start < 0:
        raise RuntimeError(f"Missing integration marker: {start_marker!r}")
    end = text.find(end_marker, start)
    if end < 0:
        raise RuntimeError(f"Missing integration marker: {end_marker!r}")
    return text[:start] + replacement + text[end:]


def apply(path: Path = APP_FILE) -> bool:
    text = path.read_text(encoding="utf-8")
    if "BROADCAST_LIFECYCLE_SERVICE: BroadcastLifecycleService | None = None" in text:
        return False

    import_marker = "from support_media_service import SupportMediaService\n"
    if import_marker not in text:
        raise RuntimeError("SupportMediaService import marker was not found.")
    text = text.replace(
        import_marker,
        import_marker
        + "from broadcast_lifecycle_service import BroadcastLifecycleService\n",
        1,
    )

    lifecycle_block = '''BROADCAST_LIFECYCLE_SERVICE: BroadcastLifecycleService | None = None


def get_broadcast_lifecycle_service() -> BroadcastLifecycleService:
    global BROADCAST_LIFECYCLE_SERVICE
    if BROADCAST_LIFECYCLE_SERVICE is None:
        BROADCAST_LIFECYCLE_SERVICE = BroadcastLifecycleService(
            load_broadcasts=load_broadcasts,
            load_packages=load_packages,
            load_state=load_state,
            save_state=save_state,
            normalize_state=normalize_state,
            default_state=lambda: copy.deepcopy(DEFAULT_STATE),
            get_school=get_school,
            build_identity=broadcast_identity,
            readiness=readiness_payload,
            update_linked_status=update_linked_broadcast_status,
            load_config=load_config,
            command_scorebug_visibility=command_scorebug_visibility,
            public_state=public_state,
            resume_record=get_broadcast_service().resume_record,
            transaction_lock=lock,
        )
    return BROADCAST_LIFECYCLE_SERVICE


@app.post("/api/broadcasts/<broadcast_id>/load")
@require_auth
def load_planned_broadcast(broadcast_id: str):
    result = get_broadcast_lifecycle_service().load(broadcast_id)
    if result.code == "NOT_FOUND":
        return jsonify({"error": result.code}), 404
    return jsonify(result.data["state"])


@app.post("/api/initialize-broadcast")
@require_auth
def initialize_broadcast():
    result = get_broadcast_lifecycle_service().initialize()
    if result.code == "NO_ACTIVE_BROADCAST":
        return jsonify({"error": result.code}), 409
    return jsonify(result.data)


@app.post("/api/start-broadcast")
@require_auth
def start_broadcast():
    result = get_broadcast_lifecycle_service().start()
    if result.code == "NO_ACTIVE_BROADCAST":
        return jsonify({"error": result.code}), 409
    return jsonify(result.data)


@app.post("/api/resume-broadcast")
@require_auth
def resume_broadcast():
    result = get_broadcast_lifecycle_service().resume()
    if result.code == "NO_ACTIVE_BROADCAST":
        return jsonify({"error": result.code}), 409
    return jsonify(result.data["state"])


'''
    text = _replace_block(
        text,
        '@app.post("/api/broadcasts/<broadcast_id>/load")\n',
        '@app.post("/api/create-broadcast")\n',
        lifecycle_block,
    )

    path.write_text(text, encoding="utf-8")
    return True


def main() -> None:
    changed = apply()
    if changed:
        print("Phase 4.23 BroadcastLifecycleService integration applied.")
    else:
        print("Phase 4.23 BroadcastLifecycleService integration was already present.")


if __name__ == "__main__":
    main()
