"""Program Visual's Camera button and the Video Mode toggle are one switch.

Camera sets video_mode (the theme's idle clash art becomes a transparent
window) and, when OBS validates, enables the camera source in Program
Visual. If OBS can't be switched, the overlay still changes and the result
carries a warning naming the scene, the source and the Settings field.
Graphic reverses both. visual_mode and video_mode always move together.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest

import app
import obs_client
from game_operations_service import GameOperationsService
from obs_service import OBSService
from tests.test_game_operations_service import base_state, build_service as build_game_service

ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")


def build_obs_service(*, obs: dict[str, Any] | None = None, fail: str = ""):
    settings = {"controlled_commands": True, **(obs or {})}
    status: dict[str, Any] = {}
    state = {"visual_mode": "graphic", "video_mode": False}
    calls: list[str] = []

    def set_visual(_settings, mode):
        calls.append(mode)
        if fail:
            raise RuntimeError(fail)
        return {"command_sent": True, "visual_mode": mode}

    def update_visual_state(mode):
        # Mirrors app.update_obs_visual_state.
        state["visual_mode"] = mode
        state["video_mode"] = mode == "camera"
        return copy.deepcopy(state)

    def save_status(value):
        status.clear()
        status.update(value)

    service = OBSService(
        load_config=lambda: {"obs": copy.deepcopy(settings)},
        load_status=lambda: copy.deepcopy(status),
        save_status=save_status,
        validate_obs=lambda _s: {},
        set_scorebug_visibility=lambda _s, _v: {},
        set_program_visual_mode=set_visual,
        update_visual_state=update_visual_state,
    )
    return service, state, status, calls


# --- OBSService ---------------------------------------------------------------


def test_camera_with_obs_ready_switches_obs_and_opens_video_window() -> None:
    service, state, status, calls = build_obs_service()
    result = service.program_visual_mode("camera")
    assert result.ok
    assert calls == ["camera"]
    assert state == {"visual_mode": "camera", "video_mode": True}
    assert result.data["obs_switched"] is True
    assert "warning" not in result.data
    assert status["visual_mode"] == "camera"


def test_camera_without_camera_source_still_turns_video_mode_on_with_warning() -> None:
    service, state, status, _ = build_obs_service(
        fail='OBS has no source named "CAM - Primary Camera" in scene "10.02 - PROGRAM VISUAL".'
    )
    result = service.program_visual_mode("camera")
    assert result.ok
    assert state == {"visual_mode": "camera", "video_mode": True}
    assert result.data["obs_switched"] is False
    warning = result.data["warning"]
    assert warning.startswith("Video mode is on")
    assert '"10.02 - PROGRAM VISUAL"' in warning
    assert '"CAM - Primary Camera"' in warning
    assert "Settings > OBS > Camera Source Name" in warning
    # A failed command never overwrites the last real OBS status.
    assert status == {}


def test_camera_warning_uses_the_configured_scene_and_source_names() -> None:
    service, _, _, _ = build_obs_service(
        obs={"program_visual_scene": "PV", "camera_source": "iPhone Cam"},
        fail="Could not connect to OBS WebSocket.",
    )
    warning = service.program_visual_mode("camera").data["warning"]
    assert 'scene "PV"' in warning
    assert 'source named "iPhone Cam"' in warning
    assert "Could not connect to OBS WebSocket" in warning


def test_graphic_with_obs_unreachable_still_turns_video_mode_off() -> None:
    service, state, _, _ = build_obs_service(fail="Could not connect to OBS WebSocket.")
    service.program_visual_mode("camera")
    result = service.program_visual_mode(" Graphic ")
    assert result.ok
    assert state == {"visual_mode": "graphic", "video_mode": False}
    assert result.data["warning"].startswith("Video mode is off")


def test_invalid_mode_changes_nothing() -> None:
    service, state, _, calls = build_obs_service()
    result = service.program_visual_mode("slides")
    assert result.code == "OBS_COMMAND_BLOCKED"
    assert calls == []
    assert state == {"visual_mode": "graphic", "video_mode": False}


# --- obs_client message -------------------------------------------------------


def test_missing_camera_source_message_names_scene_and_source(monkeypatch) -> None:
    monkeypatch.setattr(
        obs_client,
        "validate_obs_read_only",
        lambda _settings: {
            "reachable": True,
            "authenticated": True,
            "profile_matches": True,
            "scene_collection_matches": True,
            "program_visual_scene_exists": True,
            "graphic_source_exists": True,
            "graphic_scene_item_id": 4,
        },
    )
    with pytest.raises(obs_client.OBSConnectionError) as excinfo:
        obs_client.set_program_visual_mode(
            {"program_visual_scene": "PV", "camera_source": "iPhone Cam"}, "camera"
        )
    assert str(excinfo.value) == 'OBS has no source named "iPhone Cam" in scene "PV".'


# --- state: one source of truth -----------------------------------------------


def _isolated_app_state(monkeypatch, initial: dict[str, Any]) -> dict[str, Any]:
    store = copy.deepcopy(initial)
    monkeypatch.setattr(app, "load_state", lambda: copy.deepcopy(store))
    monkeypatch.setattr(app, "push_history", lambda _state: None)
    monkeypatch.setattr(app, "save_state", lambda state: store.update(copy.deepcopy(state)))
    return store


def test_app_visual_state_update_sets_both_fields(monkeypatch) -> None:
    store = _isolated_app_state(monkeypatch, {"visual_mode": "graphic", "video_mode": False})
    app.update_obs_visual_state("camera")
    assert store["visual_mode"] == "camera" and store["video_mode"] is True
    app.update_obs_visual_state("graphic")
    assert store["visual_mode"] == "graphic" and store["video_mode"] is False


@pytest.mark.parametrize(("value", "visual"), [(True, "camera"), (False, "graphic")])
def test_setting_video_mode_directly_moves_visual_mode_with_it(value, visual) -> None:
    start = {**base_state(), "video_mode": not value, "visual_mode": "graphic" if value else "camera"}
    service, current, *_ = build_game_service(start)
    result = service.set_values({"video_mode": value})
    assert result.ok
    assert current["video_mode"] is value
    assert current["visual_mode"] == visual


def test_unrelated_set_leaves_visual_mode_alone() -> None:
    service, current, *_ = build_game_service({**base_state(), "visual_mode": "camera", "video_mode": True})
    service.set_values({"ticker_visible": False})
    assert current["visual_mode"] == "camera"
    assert current["video_mode"] is True


def test_reset_keeps_the_visual_pair_together() -> None:
    assert "visual_mode" in GameOperationsService.RESET_PRESERVED_FIELDS
    assert "video_mode" in GameOperationsService.RESET_PRESERVED_FIELDS


def test_broadcast_planned_on_camera_loads_with_video_mode_on() -> None:
    source = (ROOT / "broadcast_lifecycle_service.py").read_text(encoding="utf-8")
    assert '"video_mode": item.get("visual_mode", "graphic") == "camera",' in source


# --- operator UI ----------------------------------------------------------------


def test_video_mode_toggle_and_program_visual_share_one_endpoint() -> None:
    assert "onclick=\"changeProgramVisual(currentState.video_mode?'graphic':'camera')\"" in INDEX_HTML
    assert "onclick=\"changeProgramVisual('camera')\"" in INDEX_HTML
    assert "onclick=\"setState('video_mode'" not in INDEX_HTML


def test_program_visual_buttons_follow_video_mode_for_every_sport() -> None:
    render_start = INDEX_HTML.index("function render() {")
    mark_at = INDEX_HTML.index(
        "markActive('visualModeButtons', currentState.video_mode ? 'camera' : 'graphic');",
        render_start,
    )
    branch_at = INDEX_HTML.index("isDiamondSport", render_start)
    assert mark_at < branch_at


def test_ui_shows_the_obs_warning_instead_of_failing() -> None:
    fn = INDEX_HTML[INDEX_HTML.index("async function changeProgramVisual(mode)"):]
    fn = fn[: fn.index("\n}\n") + 2]
    assert "result.warning" in fn
    assert "'videoModeMessage'" in fn and "'visualModeMessage'" in fn


# --- overlay: the window really is see-through -----------------------------------

RUNTIME_JS = (ROOT / "static" / "csrn-production-theme-runtime.js").read_text(encoding="utf-8")


def _hole_fn() -> str:
    start = RUNTIME_JS.index("function patchVideoWindowHole(root) {")
    return RUNTIME_JS[start: RUNTIME_JS.index("\n}\n", start) + 2]


def test_video_window_is_cut_out_of_the_translucent_board_layers() -> None:
    # The board card and main display paint ~93% opaque behind the
    # transparent window; the runtime masks the window's rect out of both.
    fn = _hole_fn()
    assert '".bl-scorebug.bl-collegiate, .bl-college-main-display"' in fn
    assert "mask-composite\", \"exclude\"" in fn
    assert "-webkit-mask-composite\", \"xor\"" in fn


def test_mask_only_for_the_real_window_never_the_guide_or_a_graphic() -> None:
    fn = _hole_fn()
    # The calibration guide is meant to be seen; a Player/Sponsor/Highlight
    # graphic replaces the window element, so neither gets a hole.
    assert '.bl-college-video-window:not(.bl-college-video-window-guide)' in fn
    assert "VIDEO_WINDOW_MASK_PROPERTIES.forEach(name => layer.style.removeProperty(name));" in fn


def test_mask_is_reapplied_on_both_render_paths() -> None:
    assert RUNTIME_JS.count("patchVideoWindowHole(scoreLayout());") == 1
    assert RUNTIME_JS.count("patchVideoWindowHole(scoreTarget);") == 1
