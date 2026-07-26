from __future__ import annotations

import copy
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


LoadMapping = Callable[[], dict[str, Any]]
OBSValidator = Callable[[], dict[str, Any]]
Clock = Callable[[], float]


@dataclass(frozen=True)
class CommissioningResult:
    code: str
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.code in {
            "OK",
            "PROFILE_UPDATED",
            "CHECK_UPDATED",
            "OBS_CHECK_COMPLETE",
            "COMMISSIONING_READY",
        }


class HardwareOBSCommissioningService:
    """Persistent, Flask-independent P4next and OBS commissioning boundary."""

    SCHEMA = 1
    AUDIO_CHECKS = (
        "input_gain_verified",
        "headphone_mixes_verified",
        "no_clipping",
        "no_hum_or_noise",
        "channel_isolation_verified",
        "local_multitrack_recording_verified",
        "master_recording_verified",
        "obs_audio_routing_verified",
    )
    NETWORK_CHECKS = (
        "phone_control_verified",
        "primary_internet_verified",
        "backup_internet_verified",
        "private_stream_test_verified",
        "local_recording_test_verified",
    )
    DEVICE_CHECKS = (
        "sd_card_installed",
        "sd_card_formatted_in_device",
        "usb_data_cable_verified",
        "windows_driver_installed",
        "usb_power_verified",
        "backup_power_verified",
    )
    REQUIRED_OBS_FIELDS = (
        "reachable",
        "authenticated",
        "profile_matches",
        "scene_collection_matches",
        "required_scene_exists",
        "browser_source_exists",
        "browser_source_in_required_scene",
        "program_visual_scene_exists",
        "graphic_source_exists",
    )

    def __init__(
        self,
        *,
        profile_file: Path,
        load_config: LoadMapping,
        validate_obs: OBSValidator,
        clock: Clock = time.time,
    ) -> None:
        self._profile_file = Path(profile_file)
        self._load_config = load_config
        self._validate_obs = validate_obs
        self._clock = clock

    @classmethod
    def default_profile(cls) -> dict[str, Any]:
        return {
            "schema": cls.SCHEMA,
            "device": {
                "manufacturer": "ZOOM",
                "model": "P4next",
                "usb_device_name": "ZOOM P4next",
                "usb_mode": "Multi Track",
                "recorder_mode": "Multi Track",
                "sample_rate_hz": 48000,
                "bit_depth": 24,
                "sd_card_installed": False,
                "sd_card_formatted_in_device": False,
                "usb_data_cable_verified": False,
                "windows_driver_installed": False,
                "usb_power_verified": False,
                "backup_power_verified": False,
            },
            "channels": [
                {
                    "channel": 1,
                    "enabled": True,
                    "speaker": "Jason",
                    "role": "Play-by-Play",
                    "microphone": "Audio-Technica BPHS1",
                },
                {
                    "channel": 2,
                    "enabled": True,
                    "speaker": "Jordan",
                    "role": "Color Analyst",
                    "microphone": "Audio-Technica BPHS1",
                },
                {
                    "channel": 3,
                    "enabled": False,
                    "speaker": "",
                    "role": "Sideline Reporter",
                    "microphone": "",
                },
                {
                    "channel": 4,
                    "enabled": False,
                    "speaker": "",
                    "role": "Guest",
                    "microphone": "",
                },
            ],
            "audio_checks": {
                key: {"passed": False, "note": ""} for key in cls.AUDIO_CHECKS
            },
            "network_checks": {
                key: {"passed": False, "note": ""} for key in cls.NETWORK_CHECKS
            },
            "last_obs_check": {},
            "notes": "",
            "updated_at": 0,
        }

    @staticmethod
    def _clean_check(value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return {
                "passed": bool(value.get("passed", False)),
                "note": str(value.get("note", "")).strip()[:500],
            }
        return {"passed": bool(value), "note": ""}

    @classmethod
    def _normalize_channels(cls, value: Any) -> list[dict[str, Any]]:
        by_channel: dict[int, dict[str, Any]] = {}
        if isinstance(value, list):
            for item in value:
                if not isinstance(item, dict):
                    continue
                try:
                    channel = int(item.get("channel", 0))
                except (TypeError, ValueError):
                    continue
                if channel not in {1, 2, 3, 4}:
                    continue
                by_channel[channel] = {
                    "channel": channel,
                    "enabled": bool(item.get("enabled", False)),
                    "speaker": str(item.get("speaker", "")).strip()[:80],
                    "role": str(item.get("role", "")).strip()[:80],
                    "microphone": str(item.get("microphone", "")).strip()[:120],
                }
        defaults = cls.default_profile()["channels"]
        return [copy.deepcopy(by_channel.get(item["channel"], item)) for item in defaults]

    @classmethod
    def normalize_profile(cls, value: Any) -> dict[str, Any]:
        default = cls.default_profile()
        incoming = value if isinstance(value, dict) else {}
        device_in = incoming.get("device", {})
        if not isinstance(device_in, dict):
            device_in = {}
        device = copy.deepcopy(default["device"])
        for key in (
            "manufacturer",
            "model",
            "usb_device_name",
            "usb_mode",
            "recorder_mode",
        ):
            if key in device_in:
                device[key] = str(device_in.get(key, "")).strip()[:120]
        for key in ("sample_rate_hz", "bit_depth"):
            try:
                device[key] = int(device_in.get(key, device[key]))
            except (TypeError, ValueError):
                pass
        for key in cls.DEVICE_CHECKS:
            device[key] = bool(device_in.get(key, device[key]))

        audio_in = incoming.get("audio_checks", {})
        network_in = incoming.get("network_checks", {})
        audio_in = audio_in if isinstance(audio_in, dict) else {}
        network_in = network_in if isinstance(network_in, dict) else {}

        obs = incoming.get("last_obs_check", {})
        if not isinstance(obs, dict):
            obs = {}

        try:
            updated_at = int(incoming.get("updated_at", 0) or 0)
        except (TypeError, ValueError):
            updated_at = 0

        return {
            "schema": cls.SCHEMA,
            "device": device,
            "channels": cls._normalize_channels(incoming.get("channels")),
            "audio_checks": {
                key: cls._clean_check(audio_in.get(key, {}))
                for key in cls.AUDIO_CHECKS
            },
            "network_checks": {
                key: cls._clean_check(network_in.get(key, {}))
                for key in cls.NETWORK_CHECKS
            },
            "last_obs_check": copy.deepcopy(obs),
            "notes": str(incoming.get("notes", "")).strip()[:4000],
            "updated_at": updated_at,
        }

    def _write(self, profile: dict[str, Any]) -> None:
        self._profile_file.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._profile_file.with_suffix(self._profile_file.suffix + ".tmp")
        temporary.write_text(json.dumps(profile, indent=2), encoding="utf-8")
        temporary.replace(self._profile_file)

    def load(self) -> CommissioningResult:
        raw: Any = {}
        if self._profile_file.exists():
            try:
                raw = json.loads(self._profile_file.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError):
                raw = {}
        profile = self.normalize_profile(raw)
        if raw != profile:
            self._write(profile)
        return CommissioningResult("OK", {"profile": profile})

    def update_profile(self, incoming: Any) -> CommissioningResult:
        if not isinstance(incoming, dict):
            return CommissioningResult("PROFILE_MUST_BE_OBJECT")
        current = self.load().data["profile"]
        merged = copy.deepcopy(current)
        for key in (
            "device",
            "channels",
            "audio_checks",
            "network_checks",
            "notes",
        ):
            if key in incoming:
                merged[key] = copy.deepcopy(incoming[key])
        merged["last_obs_check"] = current.get("last_obs_check", {})
        merged["updated_at"] = int(self._clock())
        profile = self.normalize_profile(merged)
        self._write(profile)
        return CommissioningResult("PROFILE_UPDATED", {"profile": profile})

    def set_check(
        self,
        *,
        section: Any,
        key: Any,
        passed: Any,
        note: Any = "",
    ) -> CommissioningResult:
        normalized_section = str(section or "").strip().lower()
        normalized_key = str(key or "").strip()
        if normalized_section not in {"device", "audio_checks", "network_checks"}:
            return CommissioningResult("INVALID_CHECK_SECTION")
        allowed = {
            "device": set(self.DEVICE_CHECKS),
            "audio_checks": set(self.AUDIO_CHECKS),
            "network_checks": set(self.NETWORK_CHECKS),
        }[normalized_section]
        if normalized_key not in allowed:
            return CommissioningResult("INVALID_CHECK_KEY")
        if not isinstance(passed, bool):
            return CommissioningResult("PASSED_MUST_BE_BOOLEAN")

        profile = self.load().data["profile"]
        if normalized_section == "device":
            profile["device"][normalized_key] = passed
        else:
            profile[normalized_section][normalized_key] = {
                "passed": passed,
                "note": str(note or "").strip()[:500],
            }
        profile["updated_at"] = int(self._clock())
        self._write(profile)
        return CommissioningResult("CHECK_UPDATED", {"profile": profile})

    def run_obs_check(self) -> CommissioningResult:
        try:
            observed = self._validate_obs()
        except Exception as exc:
            observed = {"reachable": False, "authenticated": False, "error": str(exc)}
        if not isinstance(observed, dict):
            observed = {"reachable": False, "authenticated": False, "error": "Invalid OBS result."}

        config = self._load_config()
        obs_config = config.get("obs", {}) if isinstance(config, dict) else {}
        if not isinstance(obs_config, dict):
            obs_config = {}
        required = {
            key: bool(observed.get(key, False)) for key in self.REQUIRED_OBS_FIELDS
        }
        ready = all(required.values())
        check = {
            "ready": ready,
            "checked_at": int(self._clock()),
            "required": required,
            "expected": {
                "profile": str(obs_config.get("profile", "")),
                "scene_collection": str(obs_config.get("scene_collection", "")),
                "required_scene": str(obs_config.get("required_scene", "")),
                "browser_source": str(obs_config.get("browser_source", "")),
                "program_visual_scene": str(obs_config.get("program_visual_scene", "")),
                "graphic_source": str(obs_config.get("graphic_source", "")),
            },
            "observed": copy.deepcopy(observed),
        }
        profile = self.load().data["profile"]
        profile["last_obs_check"] = check
        profile["updated_at"] = int(self._clock())
        self._write(profile)
        return CommissioningResult("OBS_CHECK_COMPLETE", {"obs_check": check, "profile": profile})

    @staticmethod
    def _passed(check: Any) -> bool:
        return bool(check.get("passed", False)) if isinstance(check, dict) else bool(check)

    def report(self) -> CommissioningResult:
        profile = self.load().data["profile"]
        checks: list[dict[str, Any]] = []

        def add(key: str, label: str, passed: bool, *, required: bool = True, note: str = "") -> None:
            checks.append(
                {
                    "key": key,
                    "label": label,
                    "passed": bool(passed),
                    "required": bool(required),
                    "note": str(note),
                }
            )

        device = profile["device"]
        add("device.model", "P4next profile selected", str(device.get("model", "")).lower() == "p4next")
        add("device.usb_mode", "USB audio interface in Multi Track mode", str(device.get("usb_mode", "")).lower() == "multi track")
        add("device.recorder_mode", "microSD recorder in Multi Track mode", str(device.get("recorder_mode", "")).lower() == "multi track")
        add("device.sample_rate", "Audio sample rate is 48 kHz", int(device.get("sample_rate_hz", 0) or 0) == 48000)
        add("device.bit_depth", "Audio bit depth is 24-bit", int(device.get("bit_depth", 0) or 0) == 24)
        for key in self.DEVICE_CHECKS:
            add(f"device.{key}", key.replace("_", " ").title(), bool(device.get(key, False)))

        enabled_channels = [item for item in profile["channels"] if item.get("enabled")]
        speakers = [str(item.get("speaker", "")).strip().lower() for item in enabled_channels]
        assignments_ready = len(enabled_channels) >= 2 and all(speakers) and len(speakers) == len(set(speakers))
        add("channels.assignments", "At least two unique channel-to-speaker assignments", assignments_ready)

        for key in self.AUDIO_CHECKS:
            item = profile["audio_checks"][key]
            add(f"audio.{key}", key.replace("_", " ").title(), self._passed(item), note=str(item.get("note", "")))
        for key in self.NETWORK_CHECKS:
            item = profile["network_checks"][key]
            add(
                f"network.{key}",
                key.replace("_", " ").title(),
                self._passed(item),
                required=key != "backup_internet_verified",
                note=str(item.get("note", "")),
            )

        obs_check = profile.get("last_obs_check", {})
        add(
            "obs.contract",
            "OBS profile, collection, scenes, and sources match",
            bool(isinstance(obs_check, dict) and obs_check.get("ready", False)),
            note=str(obs_check.get("observed", {}).get("error", "")) if isinstance(obs_check, dict) else "",
        )

        ready = all(item["passed"] for item in checks if item["required"])
        recommended_ready = all(item["passed"] for item in checks)
        report = {
            "ready": ready,
            "recommended_ready": recommended_ready,
            "checked_at": int(self._clock()),
            "passed_required": sum(1 for item in checks if item["required"] and item["passed"]),
            "required_total": sum(1 for item in checks if item["required"]),
            "checks": checks,
            "channels": copy.deepcopy(profile["channels"]),
        }
        return CommissioningResult(
            "COMMISSIONING_READY" if ready else "COMMISSIONING_INCOMPLETE",
            {"report": report, "profile": profile},
        )
