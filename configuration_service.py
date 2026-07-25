from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Callable
from urllib.parse import urlparse


Config = dict[str, Any]
LoadConfig = Callable[[], Config]
SaveConfig = Callable[[Config], None]


@dataclass(frozen=True)
class ConfigurationResult:
    code: str
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.code == "OK"


class ConfigurationService:
    """Flask-independent application configuration behavior."""

    SOCIAL_PLATFORMS = (
        "facebook",
        "x",
        "instagram",
        "youtube",
        "website",
    )

    def __init__(
        self,
        *,
        load_config: LoadConfig,
        save_config: SaveConfig,
        runtime_version: str,
        runtime_build: str,
    ) -> None:
        self._load_config = load_config
        self._save_config = save_config
        self._runtime_version = str(runtime_version)
        self._runtime_build = str(runtime_build)

    def read(self) -> ConfigurationResult:
        return ConfigurationResult(
            "OK",
            {"config": copy.deepcopy(self._load_config())},
        )

    def update(self, incoming: Any) -> ConfigurationResult:
        if not isinstance(incoming, dict):
            return ConfigurationResult("CONFIG_PAYLOAD_REQUIRED")

        current = copy.deepcopy(self._load_config())
        patch = copy.deepcopy(incoming)

        if "social" in patch:
            social = patch.get("social")
            if not isinstance(social, dict):
                return ConfigurationResult(
                    "INVALID_SOCIAL_URL",
                    {"fields": {"social": "Expected a social settings object"}},
                )
            normalized_social, errors = self.normalize_social_block(social)
            if errors:
                return ConfigurationResult(
                    "INVALID_SOCIAL_URL",
                    {"fields": errors},
                )
            patch["social"] = normalized_social

        for section, existing in current.items():
            candidate = patch.get(section)
            if isinstance(existing, dict) and isinstance(candidate, dict):
                existing.update(candidate)

        application = current.setdefault("application", {})
        if not isinstance(application, dict):
            application = {}
            current["application"] = application
        application["version"] = self._runtime_version
        application["build"] = self._runtime_build

        self._save_config(copy.deepcopy(current))
        return ConfigurationResult("OK", {"config": current})

    @staticmethod
    def normalize_social_url(
        platform: str,
        value: Any,
    ) -> tuple[str, bool, str]:
        platform_name = str(platform or "").strip().lower()
        normalized = str(value or "").strip()
        if not normalized:
            return "", True, ""

        if normalized.startswith("@"):
            normalized = normalized[1:]

        if "://" not in normalized and "/" not in normalized:
            domains = {
                "facebook": "https://facebook.com/",
                "x": "https://x.com/",
                "instagram": "https://instagram.com/",
                "youtube": "https://youtube.com/@",
            }
            if platform_name in domains:
                normalized = domains[platform_name] + normalized
            elif platform_name == "website":
                normalized = "https://" + normalized
        elif "://" not in normalized:
            normalized = "https://" + normalized

        try:
            hostname = (urlparse(normalized).hostname or "").lower()
        except ValueError:
            hostname = ""

        valid_domains = {
            "facebook": ("facebook.com", "www.facebook.com"),
            "x": ("x.com", "twitter.com", "www.x.com", "www.twitter.com"),
            "instagram": ("instagram.com", "www.instagram.com"),
            "youtube": ("youtube.com", "www.youtube.com", "youtu.be"),
        }
        if platform_name == "website":
            valid = bool(hostname) and normalized.lower().startswith(
                ("http://", "https://")
            )
        else:
            valid = any(
                hostname == domain or hostname.endswith(f".{domain}")
                for domain in valid_domains.get(platform_name, ())
            )

        message = "" if valid else f"Expected a valid {platform_name} URL"
        return normalized, valid, message

    @classmethod
    def normalize_social_block(
        cls,
        block: dict[str, Any],
    ) -> tuple[dict[str, str], dict[str, str]]:
        normalized: dict[str, str] = {}
        errors: dict[str, str] = {}
        for platform in cls.SOCIAL_PLATFORMS:
            value, valid, message = cls.normalize_social_url(
                platform,
                block.get(platform, ""),
            )
            normalized[platform] = value
            if not valid:
                errors[platform] = message
        return normalized, errors
