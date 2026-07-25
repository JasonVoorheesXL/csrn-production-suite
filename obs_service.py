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

    def program_visual_mode(self, mode: Any) -> OBSServiceResult:
        normalized_mode = str(mode or "").strip().lower()
        settings = self._obs_settings()
        blocked = self._controlled_command_block(settings)
        if blocked is not None:
            return blocked

        try:
            result = copy.deepcopy(
                self._set_program_visual_mode(settings, normalized_mode)
            )
        except Exception as exc:
            return OBSServiceResult(
                "OBS_COMMAND_BLOCKED",
                {"message": str(exc)},
            )

        self._save_status(result)
        state = copy.deepcopy(self._update_visual_state(normalized_mode))
        return OBSServiceResult(
            "OK",
            {"state": state, "obs": result},
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
