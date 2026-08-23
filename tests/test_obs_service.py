from __future__ import annotations

import copy

from obs_service import OBSService


def build_service(*, controlled: bool = True):
    config = {"obs": {"controlled_commands": controlled, "host": "127.0.0.1"}}
    status = {"reachable": False, "checked_at": 0}
    state = {"visual_mode": "graphic", "history": []}
    calls: dict[str, list] = {
        "validate": [],
        "scorebug": [],
        "visual": [],
        "saved_status": [],
        "visual_state": [],
    }

    def load_config():
        return copy.deepcopy(config)

    def load_status():
        return copy.deepcopy(status)

    def save_status(value):
        status.clear()
        status.update(copy.deepcopy(value))
        calls["saved_status"].append(copy.deepcopy(value))

    def validate(settings):
        calls["validate"].append(copy.deepcopy(settings))
        return {"reachable": True, "authenticated": True, "checked_at": 10}

    def set_scorebug(settings, visible):
        calls["scorebug"].append((copy.deepcopy(settings), visible))
        return {"command_sent": True, "browser_source_enabled": visible}

    def set_visual(settings, mode):
        calls["visual"].append((copy.deepcopy(settings), mode))
        if mode not in {"graphic", "camera"}:
            raise RuntimeError("Program visual mode must be graphic or camera.")
        return {"command_sent": True, "visual_mode": mode}

    def update_visual_state(mode):
        calls["visual_state"].append(mode)
        previous = state.get("visual_mode")
        state.setdefault("history", []).append({"visual_mode": previous})
        state["visual_mode"] = mode
        return copy.deepcopy(state)

    service = OBSService(
        load_config=load_config,
        load_status=load_status,
        save_status=save_status,
        validate_obs=validate,
        set_scorebug_visibility=set_scorebug,
        set_program_visual_mode=set_visual,
        update_visual_state=update_visual_state,
    )
    return service, config, status, state, calls


def test_status_returns_copy():
    service, _, status, _, _ = build_service()
    result = service.status()
    result.data["status"]["reachable"] = True
    assert result.ok
    assert status["reachable"] is False


def test_connection_uses_obs_settings_and_updates_status():
    service, _, status, _, calls = build_service()
    result = service.test_connection()
    assert result.ok
    assert calls["validate"] == [{"controlled_commands": True, "host": "127.0.0.1"}]
    assert status["reachable"] is True
    assert result.data["obs"]["authenticated"] is True


def test_scorebug_requires_boolean():
    service, _, _, _, calls = build_service()
    result = service.scorebug_visibility("true")
    assert result.code == "VISIBLE_MUST_BE_BOOLEAN"
    assert calls["scorebug"] == []


def test_scorebug_is_blocked_when_controlled_commands_are_disabled():
    service, _, _, _, calls = build_service(controlled=False)
    result = service.scorebug_visibility(True)
    assert result.code == "OBS_COMMAND_BLOCKED"
    assert result.data["message"] == "Controlled OBS commands are disabled in Settings."
    assert calls["scorebug"] == []


def test_scorebug_command_updates_status():
    service, _, status, _, calls = build_service()
    result = service.scorebug_visibility(False)
    assert result.ok
    assert calls["scorebug"][0][1] is False
    assert status["browser_source_enabled"] is False


def test_scorebug_command_error_is_returned_without_status_change():
    service, _, status, _, calls = build_service()

    def fail(*_args):
        raise RuntimeError("OBS unavailable")

    service._set_scorebug_visibility = fail
    result = service.scorebug_visibility(True)
    assert result.code == "OBS_COMMAND_BLOCKED"
    assert result.data["message"] == "OBS unavailable"
    assert status == {"reachable": False, "checked_at": 0}
    assert calls["saved_status"] == []


def test_program_visual_mode_normalizes_and_persists_state():
    service, _, status, state, calls = build_service()
    result = service.program_visual_mode(" CAMERA ")
    assert result.ok
    assert calls["visual"][0][1] == "camera"
    assert calls["visual_state"] == ["camera"]
    assert state["visual_mode"] == "camera"
    assert state["history"] == [{"visual_mode": "graphic"}]
    assert status["visual_mode"] == "camera"


def test_program_visual_mode_rejects_invalid_mode_without_state_change():
    service, _, _, state, calls = build_service()
    result = service.program_visual_mode("slides")
    assert result.code == "OBS_COMMAND_BLOCKED"
    assert result.data["message"] == "Program visual mode must be graphic or camera."
    assert state["visual_mode"] == "graphic"
    assert calls["visual_state"] == []


def test_program_visual_mode_is_blocked_before_state_update():
    service, _, _, state, calls = build_service(controlled=False)
    result = service.program_visual_mode("camera")
    assert result.code == "OBS_COMMAND_BLOCKED"
    assert state["visual_mode"] == "graphic"
    assert calls["visual"] == []
    assert calls["visual_state"] == []


def test_command_scorebug_visibility_returns_payload():
    service, _, _, _, _ = build_service()
    payload = service.command_scorebug_visibility(True)
    assert payload["command_sent"] is True
    assert payload["browser_source_enabled"] is True


def test_command_scorebug_visibility_raises_on_block():
    service, _, _, _, _ = build_service(controlled=False)
    try:
        service.command_scorebug_visibility(True)
    except RuntimeError as exc:
        assert str(exc) == "Controlled OBS commands are disabled in Settings."
    else:
        raise AssertionError("Expected RuntimeError")


