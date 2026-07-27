from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping
from zoneinfo import available_timezones


@dataclass(frozen=True)
class UxResult:
    code: str
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.code in {"OK", "THEME_UPDATED"}


ResultFactory = Callable[[], Any]
LoadMapping = Callable[[], Mapping[str, Any]]


class CommercialUxService:
    """Product-wide discoverability, readiness, and controlled-option boundary."""

    MODULES = (
        {"id": "command", "name": "Command Center", "description": "Run the active broadcast.", "href": "/"},
        {"id": "games", "name": "Game Manager", "description": "Create, load, and complete broadcasts.", "href": "/?module=games"},
        {"id": "themes", "name": "Graphics Themes", "description": "Preview and activate original design presets.", "href": "/themes"},
        {"id": "social", "name": "Social Publishing", "description": "Connect accounts, review drafts, and publish approved posts.", "href": "/social"},
        {"id": "captions", "name": "Captions", "description": "Assign speakers and manage channel-based captions.", "href": "/setup#captions"},
        {"id": "weather", "name": "Venue Weather", "description": "Verify venue weather, alerts, and safety controls.", "href": "/setup#weather"},
        {"id": "obs", "name": "OBS & Hardware", "description": "Commission OBS, mixer inputs, and browser sources.", "href": "/?module=obs"},
        {"id": "recovery", "name": "Recovery & Backups", "description": "Check snapshots, recovery, and rollback readiness.", "href": "/setup#recovery"},
        {"id": "licensing", "name": "Licensing & Updates", "description": "Review product activation and update readiness.", "href": "/setup#licensing"},
        {"id": "settings", "name": "Advanced Settings", "description": "Technical settings for unusual installations.", "href": "/?module=settings"},
    )

    def __init__(
        self,
        *,
        load_config: LoadMapping,
        theme_status: ResultFactory,
        theme_catalog: ResultFactory,
        oauth_status: ResultFactory,
        social_status: ResultFactory,
    ) -> None:
        self.load_config = load_config
        self.theme_status = theme_status
        self.theme_catalog = theme_catalog
        self.oauth_status = oauth_status
        self.social_status = social_status

    @staticmethod
    def _data(result: Any) -> dict[str, Any]:
        return copy.deepcopy(getattr(result, "data", {}) or {})

    def options(self) -> UxResult:
        catalog = self._data(self.theme_catalog())
        timezones = sorted(available_timezones())
        preferred = [zone for zone in ("America/Chicago", "America/New_York", "America/Denver", "America/Los_Angeles") if zone in timezones]
        remaining = [zone for zone in timezones if zone not in preferred]
        return UxResult(
            "OK",
            {
                "themes": catalog.get("presets", []),
                "timezones": preferred + remaining,
                "caption_channel_roles": ["Play-by-Play", "Color Analyst", "Sideline Reporter", "Guest", "Producer", "Disabled"],
                "social_providers": ["x", "facebook"],
                "modules": copy.deepcopy(list(self.MODULES)),
            },
        )

    def status(self) -> UxResult:
        config = dict(self.load_config() or {})
        organization = config.get("organization", {}) if isinstance(config.get("organization"), dict) else {}
        application = config.get("application", {}) if isinstance(config.get("application"), dict) else {}
        theme = self._data(self.theme_status()).get("theme", {})
        oauth = self._data(self.oauth_status())
        social = self._data(self.social_status()).get("social", {})
        providers = oauth.get("providers", [])
        connected_count = sum(1 for row in providers if row.get("connected"))
        checks = [
            {"id": "organization", "label": "Organization identity", "complete": bool(organization.get("name"))},
            {"id": "theme", "label": "Graphics theme selected", "complete": bool((theme.get("active") or {}).get("id"))},
            {"id": "timezone", "label": "Time zone selected", "complete": bool(application.get("timezone") or config.get("timezone"))},
            {"id": "social", "label": "Social account connected", "complete": connected_count > 0, "optional": True},
            {"id": "backup", "label": "Automatic backups enabled", "complete": bool(application.get("automatic_backup", True))},
        ]
        required = [row for row in checks if not row.get("optional")]
        completed = sum(1 for row in required if row.get("complete"))
        return UxResult(
            "OK",
            {
                "setup": {
                    "checks": checks,
                    "completed": completed,
                    "required": len(required),
                    "percent": round((completed / len(required)) * 100) if required else 100,
                },
                "theme": theme,
                "oauth": oauth,
                "social": {
                    "accounts": social.get("accounts", []),
                    "draft_count": len(social.get("drafts", [])),
                },
                "modules": copy.deepcopy(list(self.MODULES)),
            },
        )
