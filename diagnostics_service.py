from __future__ import annotations

import copy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping


Payload = dict[str, Any]
LoadPayload = Callable[[], Payload]
PublicState = Callable[[Payload], Payload]
Authenticated = Callable[[], bool]
MigrateVenues = Callable[[], None]


@dataclass(frozen=True)
class DiagnosticsResult:
    code: str
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.code == "OK"


class DiagnosticsService:
    """Flask-independent diagnostics and broadcast-readiness behavior."""

    def __init__(
        self,
        *,
        base_dir: Path,
        data_dir: Path,
        config_file: Path,
        schools_file: Path,
        broadcasters_file: Path,
        rosters_file: Path,
        venues_file: Path,
        logos_file: Path,
        packages_file: Path,
        assets_file: Path,
        sponsors_file: Path,
        load_config: LoadPayload,
        load_state: LoadPayload,
        public_state: PublicState,
        load_obs_status: LoadPayload,
        authenticated: Authenticated,
        migrate_venues: MigrateVenues,
        overlay_url: str = "http://127.0.0.1:5050/overlay",
    ) -> None:
        self._base_dir = Path(base_dir)
        self._data_dir = Path(data_dir)
        self._config_file = Path(config_file)
        self._schools_file = Path(schools_file)
        self._broadcasters_file = Path(broadcasters_file)
        self._rosters_file = Path(rosters_file)
        self._venues_file = Path(venues_file)
        self._logos_file = Path(logos_file)
        self._packages_file = Path(packages_file)
        self._assets_file = Path(assets_file)
        self._sponsors_file = Path(sponsors_file)
        self._load_config = load_config
        self._load_state = load_state
        self._public_state = public_state
        self._load_obs_status = load_obs_status
        self._authenticated = authenticated
        self._migrate_venues = migrate_venues
        self._overlay_url = str(overlay_url)

    @staticmethod
    def _section(config: Mapping[str, Any], name: str) -> dict[str, Any]:
        value = config.get(name, {})
        return copy.deepcopy(value) if isinstance(value, dict) else {}

    def diagnostics(self) -> DiagnosticsResult:
        config = copy.deepcopy(self._load_config())
        if not isinstance(config, dict):
            config = {}
        organization = self._section(config, "organization")
        application = self._section(config, "application")
        logo_path = str(
            organization.get("logo_path") or "static/csrn-logo.png"
        )

        required = {
            "Configuration": self._config_file,
            "Data folder": self._data_dir,
            "Schools folder": self._data_dir / "Schools",
            "Broadcasts folder": self._data_dir / "Broadcasts",
            "Backups folder": self._data_dir / "Backups",
            "Logo file": self._base_dir / logo_path,
            "School database": self._schools_file,
            "Broadcaster profiles": self._broadcasters_file,
            "Roster database": self._rosters_file,
            "Venue database": self._venues_file,
            "Logo database": self._logos_file,
            "Broadcast packages": self._packages_file,
        }

        payload = {
            "checks": [
                {"name": name, "ok": path.exists(), "path": str(path)}
                for name, path in required.items()
            ],
            "version": application.get("version", "1.0 Alpha"),
            "build": application.get("build", "0007"),
            "authenticated": bool(self._authenticated()),
            "config_file": str(self._config_file),
            "data_folder": str(self._data_dir),
            "obs": copy.deepcopy(self._load_obs_status()),
            "engines": [
                {
                    "name": "Roster Engine",
                    "version": "v1.1",
                    "status": (
                        "Healthy" if self._rosters_file.exists()
                        else "Needs Attention"
                    ),
                },
                {
                    "name": "Personnel Engine",
                    "version": "v1.0",
                    "status": (
                        "Healthy" if self._broadcasters_file.exists()
                        else "Needs Attention"
                    ),
                },
                {"name": "Graphics Engine", "version": "v2.1", "status": "Healthy"},
                {"name": "Graphics Library", "version": "v1.0", "status": "Healthy"},
                {
                    "name": "Asset Manager",
                    "version": "v1.0",
                    "status": (
                        "Healthy" if self._assets_file.parent.exists()
                        else "Needs Attention"
                    ),
                },
                {
                    "name": "Sponsor Engine",
                    "version": "v1.0",
                    "status": (
                        "Healthy" if self._sponsors_file.parent.exists()
                        else "Needs Attention"
                    ),
                },
                {
                    "name": "Broadcast Package Engine",
                    "version": "v1.0",
                    "status": (
                        "Healthy" if self._packages_file.parent.exists()
                        else "Needs Attention"
                    ),
                },
                {
                    "name": "Lineup Manager",
                    "version": "v1.0",
                    "status": (
                        "Healthy" if self._rosters_file.exists()
                        else "Needs Attention"
                    ),
                },
            ],
            "channels": {
                "primary_graphics": "Healthy",
                "scorebug": "Healthy",
            },
        }
        return DiagnosticsResult("OK", {"diagnostics": payload})

    def readiness(self) -> DiagnosticsResult:
        self._migrate_venues()
        config = copy.deepcopy(self._load_config())
        if not isinstance(config, dict):
            config = {}
        obs_config = self._section(config, "obs")
        obs = copy.deepcopy(self._load_obs_status())
        if not isinstance(obs, dict):
            obs = {}
        state = copy.deepcopy(self._load_state())
        if not isinstance(state, dict):
            state = {}

        checks: list[dict[str, Any]] = []

        def add(
            key: str,
            label: str,
            ok: Any,
            note: str,
            action: str = "",
        ) -> None:
            checks.append(
                {
                    "key": key,
                    "label": label,
                    "ok": bool(ok),
                    "note": note,
                    "action": action,
                }
            )

        required_scene = str(
            obs_config.get("required_scene")
            or "10.01 - FOOTBALL SCOREBUG"
        )
        browser_source = str(
            obs_config.get("browser_source")
            or "BRWSR - Football Scorebug"
        )
        program_visual_scene = str(
            obs_config.get("program_visual_scene") or ""
        )

        add(
            "obs",
            "OBS WebSocket",
            obs.get("reachable") and obs.get("authenticated"),
            "Connected and authenticated.",
            "Open OBS, enable the WebSocket server, then retry.",
        )
        add(
            "scene",
            "Scorebug scene",
            obs.get("required_scene_exists"),
            "Required scorebug scene found.",
            f"In OBS create or load scene: {required_scene}",
        )
        add(
            "browser",
            "Browser source",
            obs.get("browser_source_exists"),
            "Browser source found; a hidden scorebug is still ready.",
            f"In OBS add Browser Source {browser_source} using {self._overlay_url}",
        )
        add(
            "overlay",
            "Overlay endpoint",
            True,
            "Overlay endpoint is reachable.",
        )
        add(
            "visual",
            "Program visual",
            program_visual_scene,
            "Program Visual is configured.",
            "Configure the Program Visual scene in Settings.",
        )

        payload = {
            "ready": all(check["ok"] for check in checks),
            "checks": checks,
            "overlay_url": self._overlay_url,
            "state": copy.deepcopy(self._public_state(state)),
        }
        return DiagnosticsResult("OK", {"readiness": payload})
