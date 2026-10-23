from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Callable


LoadMapping = Callable[[], dict[str, Any]]
SaveMapping = Callable[[dict[str, Any]], None]
ValidateOBS = Callable[[dict[str, Any]], dict[str, Any]]
SetScorebugVisibility = Callable[[dict[str, Any], bool], dict[str, Any]]
SetProgramVisualMode = Callable[[dict[str, Any], str], dict[str, Any]]
UpdateVisualState = Callable[[str], dict[str, Any]]


@dataclass(frozen=True)
class OBSServiceResult:
    code: str
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.code == "OK"


class OBSService:
    """Flask-independent boundary for approved OBS validation and commands."""

    def __init__(
        self,
        *,
        load_config: LoadMapping,
        load_status: LoadMapping,
        save_status: SaveMapping,
        validate_obs: ValidateOBS,
        set_scorebug_visibility: SetScorebugVisibility,
        set_program_visual_mode: SetProgramVisualMode,
        update_visual_state: UpdateVisualState,
    ) -> None:
        self._load_config = load_config
        self._load_status = load_status
        self._save_status = save_status
        self._validate_obs = validate_obs
        self._set_scorebug_visibility = set_scorebug_visibility
        self._set_program_visual_mode = set_program_visual_mode
        self._update_visual_state = update_visual_state

    def status(self) -> OBSServiceResult:
        return OBSServiceResult(
            "OK",
            {"status": copy.deepcopy(self._load_status())},
        )

    def test_connection(self) -> OBSServiceResult:
        settings = self._obs_settings()
        result = copy.deepcopy(self._validate_obs(settings))
        self._save_status(result)
        return OBSServiceResult("OK", {"obs": result})

    def scorebug_visibility(self, visible: Any) -> OBSServiceResult:
        if not isinstance(visible, bool):
            return OBSServiceResult("VISIBLE_MUST_BE_BOOLEAN")

        settings = self._obs_settings()
        blocked = self._controlled_command_block(settings)
        if blocked is not None:
            return blocked

        try:
            result = copy.deepcopy(
                self._set_scorebug_visibility(settings, visible)
            )
        except Exception as exc:
            return OBSServiceResult(
                "OBS_COMMAND_BLOCKED",
                {"message": str(exc)},
            )

        self._save_status(result)
        return OBSServiceResult("OK", {"obs": result})

    VISUAL_MODES = {"graphic", "camera"}

    def program_visual_mode(self, mode: Any) -> OBSServiceResult:
        """Switch the overlay's video window and, when OBS allows, its layer.

        The overlay side (video_mode) always follows the operator: Camera
        opens the theme's transparent video window, Graphic closes it. The
        OBS layer switch is best effort -- if OBS is off, unreachable or
        missing the camera source, the overlay still changes and the result
        carries a warning naming what OBS needs.
        """
        normalized_mode = str(mode or "").strip().lower()
        if normalized_mode not in self.VISUAL_MODES:
            return OBSServiceResult(
                "OBS_COMMAND_BLOCKED",
                {"message": "Program visual mode must be graphic or camera."},
            )

        settings = self._obs_settings()
        obs: dict[str, Any] = {}
        obs_message = ""
        blocked = self._controlled_command_block(settings)
        if blocked is not None:
            obs_message = str(blocked.data.get("message", ""))
        else:
            try:
                obs = copy.deepcopy(
                    self._set_program_visual_mode(settings, normalized_mode)
                )
            except Exception as exc:
                obs_message = str(exc)
            else:
                self._save_status(obs)

        state = copy.deepcopy(self._update_visual_state(normalized_mode))
        data: dict[str, Any] = {
            "state": state,
            "obs": obs,
            "obs_switched": not obs_message,
        }
        if obs_message:
            data["warning"] = self._obs_switch_warning(
                settings, normalized_mode, obs_message
            )
        return OBSServiceResult("OK", data)

    @staticmethod
    def _obs_switch_warning(
        settings: dict[str, Any], mode: str, reason: str
    ) -> str:
        scene = str(
            settings.get("program_visual_scene") or "10.02 - PROGRAM VISUAL"
        ).strip()
        if mode == "camera":
            source = str(
                settings.get("camera_source") or "CAM - Primary Camera"
            ).strip()
            return (
                "Video mode is on: the overlay's video window is open. "
                f"OBS was not switched ({reason.rstrip('.')}). "
                f'For CSRN to switch it, OBS needs scene "{scene}" with a '
                f'source named "{source}" (Settings > OBS > Camera Source '
                "Name changes the name CSRN looks for). Otherwise place the "
                "camera behind the overlay in OBS yourself."
            )
        source = str(
            settings.get("graphic_source") or "IMG - Broadcast Background"
        ).strip()
        return (
            "Video mode is off: the overlay's graphic is back. "
            f"OBS was not switched ({reason.rstrip('.')}). "
            f'Check that OBS scene "{scene}" shows "{source}".'
        )

    def command_scorebug_visibility(self, visible: bool) -> dict[str, Any]:
        """Compatibility helper for broadcast-start automation."""
        result = self.scorebug_visibility(visible)
        if not result.ok:
            raise RuntimeError(
                str(result.data.get("message", result.code))
            )
        return copy.deepcopy(result.data["obs"])

    def _obs_settings(self) -> dict[str, Any]:
        config = self._load_config()
        if not isinstance(config, dict):
            return {}
        settings = config.get("obs", {})
        return copy.deepcopy(settings) if isinstance(settings, dict) else {}

    @staticmethod
    def _controlled_command_block(
        settings: dict[str, Any],
    ) -> OBSServiceResult | None:
        if settings.get("controlled_commands", False):
            return None
        return OBSServiceResult(
            "OBS_COMMAND_BLOCKED",
            {"message": "Controlled OBS commands are disabled in Settings."},
        )
