from __future__ import annotations

import copy
import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
from typing import Any, Callable


LoadMapping = Callable[[], dict[str, Any]]
Clock = Callable[[], float]


@dataclass(frozen=True)
class ThemeResult:
    code: str
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.code in {
            "OK",
            "PREVIEW_READY",
            "THEME_ACTIVATED",
            "THEME_LOCKED",
            "THEME_UNLOCKED",
            "VARIANT_SAVED",
            "VARIANT_DELETED",
            "VARIANT_ACTIVATED",
            "OVERRIDES_RESET",
        }


class GraphicsThemeService:
    """Flask-independent theme catalog, activation, variants, and CSS generation."""

    SCHEMA = 1
    MAX_VARIANTS = 24
    HEX_PATTERN = re.compile(r"^#[0-9A-Fa-f]{6}$")
    VARIANT_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _.-]{0,47}$")
    FONT_STACKS = {
        "system_sans": "Arial, Helvetica, sans-serif",
        "condensed_sans": "'Arial Narrow', 'Roboto Condensed', Arial, sans-serif",
        "serif": "Georgia, 'Times New Roman', serif",
        "slab": "Rockwell, 'Roboto Slab', Georgia, serif",
        "mono": "Consolas, 'Courier New', monospace",
    }
    OVERRIDE_KEYS = {
        "primary_color",
        "secondary_color",
        "accent_color",
        "font_key",
        "radius_px",
        "panel_opacity",
        "texture_intensity",
        "motion_scale",
    }

    PRESETS: dict[str, dict[str, Any]] = {
        "classic_1980s": {
            "name": "Classic 1980s Broadcast",
            "description": "Bold bars, squared geometry, restrained motion, and high-contrast analog-era structure.",
            "category": "retro",
            "tokens": {
                "font_key": "condensed_sans",
                "radius_px": 2,
                "border_width_px": 4,
                "panel_opacity": 0.96,
                "texture": "scanline",
                "texture_intensity": 0.18,
                "motion_scale": 0.55,
                "surface": "#151515",
                "surface_alt": "#2B2B2B",
                "text": "#FFFFFF",
                "muted": "#D7D7D7",
                "border": "#F4F4F4",
                "center_style": "solid",
                "shadow": "0 8px 0 rgba(0,0,0,.55)",
            },
        },
        "early_cable": {
            "name": "Early Cable Sports",
            "description": "Layered gradients, beveled edges, energetic accents, and compact cable-era information density.",
            "category": "retro",
            "tokens": {
                "font_key": "system_sans",
                "radius_px": 8,
                "border_width_px": 3,
                "panel_opacity": 0.95,
                "texture": "diagonal",
                "texture_intensity": 0.14,
                "motion_scale": 0.8,
                "surface": "#111722",
                "surface_alt": "#33445F",
                "text": "#FFFFFF",
                "muted": "#C9D3E2",
                "border": "#DCE8F8",
                "center_style": "bevel",
                "shadow": "0 10px 22px rgba(0,0,0,.62)",
            },
        },
        "modern_network": {
            "name": "Modern Network",
            "description": "Clean modular panels, confident typography, subtle depth, and balanced motion.",
            "category": "modern",
            "tokens": {
                "font_key": "system_sans",
                "radius_px": 14,
                "border_width_px": 2,
                "panel_opacity": 0.94,
                "texture": "none",
                "texture_intensity": 0.0,
                "motion_scale": 1.0,
                "surface": "#101318",
                "surface_alt": "#242A33",
                "text": "#FFFFFF",
                "muted": "#C8D0DB",
                "border": "#E8EDF4",
                "center_style": "gradient",
                "shadow": "0 16px 34px rgba(0,0,0,.58)",
            },
        },
        "minimal_radio": {
            "name": "Minimal Radio",
            "description": "Low-clutter geometry, flat surfaces, compact typography, and minimal animation for audio-first productions.",
            "category": "minimal",
            "tokens": {
                "font_key": "system_sans",
                "radius_px": 4,
                "border_width_px": 1,
                "panel_opacity": 0.88,
                "texture": "none",
                "texture_intensity": 0.0,
                "motion_scale": 0.35,
                "surface": "#0D0F12",
                "surface_alt": "#191D22",
                "text": "#FFFFFF",
                "muted": "#AEB7C2",
                "border": "#7D8792",
                "center_style": "solid",
                "shadow": "0 6px 16px rgba(0,0,0,.42)",
            },
        },
        "heritage_press_box": {
            "name": "Heritage Press Box",
            "description": "Warm paper tones, serif typography, restrained brass accents, and archival scorebook character.",
            "category": "heritage",
            "tokens": {
                "font_key": "serif",
                "radius_px": 5,
                "border_width_px": 3,
                "panel_opacity": 0.96,
                "texture": "paper",
                "texture_intensity": 0.2,
                "motion_scale": 0.5,
                "surface": "#2E251B",
                "surface_alt": "#57452D",
                "text": "#FFF5D8",
                "muted": "#E6D6AC",
                "border": "#D8B76A",
                "center_style": "solid",
                "shadow": "0 10px 24px rgba(20,12,5,.62)",
            },
        },
        "friday_night_stadium": {
            "name": "Friday Night Stadium",
            "description": "Dark stadium surfaces, bright field-light highlights, strong team-color energy, and dramatic depth.",
            "category": "event",
            "tokens": {
                "font_key": "condensed_sans",
                "radius_px": 12,
                "border_width_px": 3,
                "panel_opacity": 0.95,
                "texture": "stadium",
                "texture_intensity": 0.22,
                "motion_scale": 1.1,
                "surface": "#080B10",
                "surface_alt": "#1C2530",
                "text": "#FFFFFF",
                "muted": "#D5DEE8",
                "border": "#FFFFFF",
                "center_style": "glow",
                "shadow": "0 18px 42px rgba(0,0,0,.72)",
            },
        },
        "digital_neon": {
            "name": "Digital Neon",
            "description": "Electric edge lighting, compact digital typography, angular framing, and controlled neon glow.",
            "category": "digital",
            "tokens": {
                "font_key": "mono",
                "radius_px": 3,
                "border_width_px": 2,
                "panel_opacity": 0.91,
                "texture": "grid",
                "texture_intensity": 0.2,
                "motion_scale": 1.2,
                "surface": "#060812",
                "surface_alt": "#10172A",
                "text": "#F7FBFF",
                "muted": "#A9B9D6",
                "border": "#80E9FF",
                "center_style": "glow",
                "shadow": "0 0 28px rgba(70,220,255,.28),0 14px 30px rgba(0,0,0,.64)",
            },
        },
        "collegiate_traditional": {
            "name": "Collegiate Traditional",
            "description": "Structured school-color panels, slab typography, formal borders, and traditional athletics presentation.",
            "category": "traditional",
            "tokens": {
                "font_key": "slab",
                "radius_px": 8,
                "border_width_px": 4,
                "panel_opacity": 0.96,
                "texture": "stripe",
                "texture_intensity": 0.12,
                "motion_scale": 0.75,
                "surface": "#121212",
                "surface_alt": "#292929",
                "text": "#FFFFFF",
                "muted": "#D7D7D7",
                "border": "#FFFFFF",
                "center_style": "solid",
                "shadow": "0 12px 26px rgba(0,0,0,.62)",
            },
        },
    }

    DEFAULT_STATE: dict[str, Any] = {
        "schema": SCHEMA,
        "active_preset": "modern_network",
        "overrides": {},
        "locked": False,
        "locked_at": 0,
        "variants": {},
        "updated_at": 0,
    }

    def __init__(
        self,
        *,
        state_file: Path,
        load_state: LoadMapping,
        load_config: LoadMapping,
        clock: Clock = time.time,
    ) -> None:
        self.state_file = Path(state_file)
        self._load_broadcast_state = load_state
        self._load_config = load_config
        self._clock = clock
        self._lock = Lock()
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _read_json(path: Path, default: Any) -> Any:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return copy.deepcopy(default)

    def _load(self) -> dict[str, Any]:
        payload = self._read_json(self.state_file, self.DEFAULT_STATE)
        if not isinstance(payload, dict):
            payload = copy.deepcopy(self.DEFAULT_STATE)
        merged = copy.deepcopy(self.DEFAULT_STATE)
        merged.update(payload)
        merged["overrides"] = payload.get("overrides", {}) if isinstance(payload.get("overrides"), dict) else {}
        merged["variants"] = payload.get("variants", {}) if isinstance(payload.get("variants"), dict) else {}
        if merged.get("active_preset") not in self.PRESETS:
            merged["active_preset"] = self.DEFAULT_STATE["active_preset"]
        return merged

    def _write(self, payload: dict[str, Any]) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.state_file.with_name(f".{self.state_file.name}.tmp")
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        temporary.replace(self.state_file)

    @classmethod
    def catalog(cls) -> ThemeResult:
        presets = []
        for preset_id, preset in cls.PRESETS.items():
            presets.append(
                {
                    "id": preset_id,
                    "name": preset["name"],
                    "description": preset["description"],
                    "category": preset["category"],
                    "tokens": copy.deepcopy(preset["tokens"]),
                }
            )
        return ThemeResult("OK", {"presets": presets, "count": len(presets)})

    @classmethod
    def _normalize_overrides(cls, overrides: Any) -> tuple[dict[str, Any], list[str]]:
        if overrides is None:
            return {}, []
        if not isinstance(overrides, dict):
            return {}, ["Overrides must be an object."]
        normalized: dict[str, Any] = {}
        errors: list[str] = []
        unknown = sorted(set(overrides) - cls.OVERRIDE_KEYS)
        if unknown:
            errors.append("Unsupported override keys: " + ", ".join(unknown))
        for key in ("primary_color", "secondary_color", "accent_color"):
            if key not in overrides:
                continue
            value = str(overrides.get(key, "")).strip()
            if not cls.HEX_PATTERN.fullmatch(value):
                errors.append(f"{key} must be a six-digit hexadecimal color.")
            else:
                normalized[key] = value.upper()
        if "font_key" in overrides:
            value = str(overrides.get("font_key", "")).strip()
            if value not in cls.FONT_STACKS:
                errors.append("font_key is not allowlisted.")
            else:
                normalized["font_key"] = value
        ranges = {
            "radius_px": (0, 28, int),
            "panel_opacity": (0.65, 1.0, float),
            "texture_intensity": (0.0, 0.4, float),
            "motion_scale": (0.0, 1.5, float),
        }
        for key, (minimum, maximum, caster) in ranges.items():
            if key not in overrides:
                continue
            try:
                value = caster(overrides[key])
            except (TypeError, ValueError):
                errors.append(f"{key} must be numeric.")
                continue
            if value < minimum or value > maximum:
                errors.append(f"{key} must be between {minimum} and {maximum}.")
            else:
                normalized[key] = value
        return normalized, errors

    @classmethod
    def _color(cls, value: Any, fallback: str) -> str:
        candidate = str(value or "").strip()
        return candidate.upper() if cls.HEX_PATTERN.fullmatch(candidate) else fallback

    @staticmethod
    def _rgba(hex_color: str, alpha: float) -> str:
        value = hex_color.lstrip("#")
        red, green, blue = int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)
        return f"rgba({red},{green},{blue},{alpha:.3f})"

    @staticmethod
    def _texture(name: str, intensity: float) -> str:
        alpha = max(0.0, min(0.4, float(intensity)))
        if name == "scanline":
            return f"repeating-linear-gradient(0deg,rgba(255,255,255,{alpha:.3f}) 0 1px,transparent 1px 4px)"
        if name == "diagonal":
            return f"repeating-linear-gradient(135deg,rgba(255,255,255,{alpha:.3f}) 0 2px,transparent 2px 11px)"
        if name == "paper":
            return f"radial-gradient(circle at 20% 30%,rgba(255,245,210,{alpha:.3f}) 0 1px,transparent 2px),radial-gradient(circle at 75% 65%,rgba(80,45,15,{alpha:.3f}) 0 1px,transparent 2px)"
        if name == "stadium":
            return f"radial-gradient(ellipse at top,rgba(255,255,255,{alpha:.3f}),transparent 42%)"
        if name == "grid":
            return f"linear-gradient(rgba(100,220,255,{alpha:.3f}) 1px,transparent 1px),linear-gradient(90deg,rgba(100,220,255,{alpha:.3f}) 1px,transparent 1px)"
        if name == "stripe":
            return f"repeating-linear-gradient(90deg,rgba(255,255,255,{alpha:.3f}) 0 3px,transparent 3px 18px)"
        return "none"

    def _school_colors(self) -> dict[str, str]:
        config = self._load_config()
        state = self._load_broadcast_state()
        organization = config.get("organization", {}) if isinstance(config, dict) else {}
        home = state.get("home_identity", {}) if isinstance(state, dict) else {}
        visitor = state.get("visitor_identity", {}) if isinstance(state, dict) else {}
        return {
            "organization_primary": self._color(organization.get("primary_color"), "#C9203B"),
            "organization_secondary": self._color(organization.get("secondary_color"), "#111111"),
            "organization_accent": self._color(organization.get("accent_color"), "#FFFFFF"),
            "home_primary": self._color(home.get("primary_color"), "#C9203B"),
            "visitor_primary": self._color(visitor.get("primary_color"), "#5B6470"),
        }

    def _resolve(self, preset_id: str, overrides: dict[str, Any]) -> dict[str, Any]:
        preset = copy.deepcopy(self.PRESETS[preset_id])
        tokens = preset["tokens"]
        tokens.update(overrides)
        colors = self._school_colors()
        primary = self._color(tokens.get("primary_color"), colors["organization_primary"])
        secondary = self._color(tokens.get("secondary_color"), colors["organization_secondary"])
        accent = self._color(tokens.get("accent_color"), colors["organization_accent"])
        font_key = str(tokens.get("font_key", "system_sans"))
        tokens.update(
            {
                "primary_color": primary,
                "secondary_color": secondary,
                "accent_color": accent,
                "font_key": font_key,
                "font_stack": self.FONT_STACKS[font_key],
                "radius_px": int(tokens.get("radius_px", 8)),
                "panel_opacity": float(tokens.get("panel_opacity", 0.94)),
                "texture_intensity": float(tokens.get("texture_intensity", 0.0)),
                "motion_scale": float(tokens.get("motion_scale", 1.0)),
                "texture_css": self._texture(str(tokens.get("texture", "none")), float(tokens.get("texture_intensity", 0.0))),
                "primary_rgba": self._rgba(primary, float(tokens.get("panel_opacity", 0.94))),
                "secondary_rgba": self._rgba(secondary, float(tokens.get("panel_opacity", 0.94))),
            }
        )
        return {
            "id": preset_id,
            "name": preset["name"],
            "description": preset["description"],
            "category": preset["category"],
            "tokens": tokens,
            "school_colors": colors,
        }

    def status(self) -> ThemeResult:
        with self._lock:
            state = self._load()
            resolved = self._resolve(state["active_preset"], state["overrides"])
            return ThemeResult(
                "OK",
                {
                    "theme": {
                        "active": resolved,
                        "overrides": copy.deepcopy(state["overrides"]),
                        "locked": bool(state.get("locked", False)),
                        "locked_at": int(state.get("locked_at", 0) or 0),
                        "variants": copy.deepcopy(state["variants"]),
                        "updated_at": int(state.get("updated_at", 0) or 0),
                    }
                },
            )

    def public_state(self) -> ThemeResult:
        status = self.status().data["theme"]
        return ThemeResult(
            "OK",
            {
                "theme": {
                    "active": status["active"],
                    "locked": status["locked"],
                    "updated_at": status["updated_at"],
                }
            },
        )

    def preview(self, preset_id: Any, overrides: Any = None) -> ThemeResult:
        preset_id = str(preset_id or "").strip()
        if preset_id not in self.PRESETS:
            return ThemeResult("PRESET_NOT_FOUND")
        normalized, errors = self._normalize_overrides(overrides)
        if errors:
            return ThemeResult("OVERRIDES_INVALID", {"errors": errors})
        resolved = self._resolve(preset_id, normalized)
        return ThemeResult("PREVIEW_READY", {"preview": resolved, "css": self._css_for(resolved)})

    def activate(self, preset_id: Any, overrides: Any = None, *, confirmation: Any = None) -> ThemeResult:
        preset_id = str(preset_id or "").strip()
        if preset_id not in self.PRESETS:
            return ThemeResult("PRESET_NOT_FOUND")
        normalized, errors = self._normalize_overrides(overrides)
        if errors:
            return ThemeResult("OVERRIDES_INVALID", {"errors": errors})
        with self._lock:
            state = self._load()
            changing = preset_id != state["active_preset"] or normalized != state["overrides"]
            if state.get("locked") and changing and str(confirmation or "") != "CHANGE LOCKED SEASON THEME":
                return ThemeResult("LOCKED_THEME_CONFIRMATION_REQUIRED")
            state.update(
                {
                    "active_preset": preset_id,
                    "overrides": normalized,
                    "updated_at": int(self._clock()),
                }
            )
            self._write(state)
            resolved = self._resolve(preset_id, normalized)
            return ThemeResult("THEME_ACTIVATED", {"theme": resolved, "locked": bool(state.get("locked"))})

    def set_lock(self, locked: Any, confirmation: Any) -> ThemeResult:
        if not isinstance(locked, bool):
            return ThemeResult("LOCK_VALUE_REQUIRED")
        phrase = "LOCK SEASON THEME" if locked else "UNLOCK SEASON THEME"
        if str(confirmation or "") != phrase:
            return ThemeResult("LOCK_CONFIRMATION_REQUIRED", {"required_confirmation": phrase})
        with self._lock:
            state = self._load()
            state["locked"] = locked
            state["locked_at"] = int(self._clock()) if locked else 0
            state["updated_at"] = int(self._clock())
            self._write(state)
            return ThemeResult("THEME_LOCKED" if locked else "THEME_UNLOCKED", {"locked": locked})

    def reset_overrides(self, *, confirmation: Any = None) -> ThemeResult:
        with self._lock:
            state = self._load()
            if state.get("locked") and str(confirmation or "") != "CHANGE LOCKED SEASON THEME":
                return ThemeResult("LOCKED_THEME_CONFIRMATION_REQUIRED")
            state["overrides"] = {}
            state["updated_at"] = int(self._clock())
            self._write(state)
            return ThemeResult("OVERRIDES_RESET", {"theme": self._resolve(state["active_preset"], {})})

    def save_variant(self, name: Any, preset_id: Any, overrides: Any = None) -> ThemeResult:
        name = str(name or "").strip()
        preset_id = str(preset_id or "").strip()
        if not self.VARIANT_PATTERN.fullmatch(name):
            return ThemeResult("VARIANT_NAME_INVALID")
        if preset_id not in self.PRESETS:
            return ThemeResult("PRESET_NOT_FOUND")
        normalized, errors = self._normalize_overrides(overrides)
        if errors:
            return ThemeResult("OVERRIDES_INVALID", {"errors": errors})
        key = name.casefold()
        with self._lock:
            state = self._load()
            variants = state["variants"]
            if key not in variants and len(variants) >= self.MAX_VARIANTS:
                return ThemeResult("VARIANT_LIMIT_REACHED")
            variant = {
                "name": name,
                "preset_id": preset_id,
                "overrides": normalized,
                "updated_at": int(self._clock()),
            }
            variants[key] = variant
            state["updated_at"] = int(self._clock())
            self._write(state)
            return ThemeResult("VARIANT_SAVED", {"variant": copy.deepcopy(variant)})

    def delete_variant(self, name: Any, confirmation: Any) -> ThemeResult:
        name = str(name or "").strip()
        if str(confirmation or "") != "DELETE THEME VARIANT":
            return ThemeResult("VARIANT_DELETE_CONFIRMATION_REQUIRED")
        with self._lock:
            state = self._load()
            variant = state["variants"].pop(name.casefold(), None)
            if variant is None:
                return ThemeResult("VARIANT_NOT_FOUND")
            state["updated_at"] = int(self._clock())
            self._write(state)
            return ThemeResult("VARIANT_DELETED", {"variant": variant})

    def activate_variant(self, name: Any, *, confirmation: Any = None) -> ThemeResult:
        name = str(name or "").strip()
        with self._lock:
            state = self._load()
            variant = copy.deepcopy(state["variants"].get(name.casefold()))
        if not isinstance(variant, dict):
            return ThemeResult("VARIANT_NOT_FOUND")
        result = self.activate(
            variant.get("preset_id"),
            variant.get("overrides", {}),
            confirmation=confirmation,
        )
        if not result.ok:
            return result
        return ThemeResult("VARIANT_ACTIVATED", {"variant": variant, **result.data})

    def css(self) -> ThemeResult:
        status = self.status().data["theme"]
        return ThemeResult(
            "OK",
            {
                "css": self._css_for(status["active"]),
                "preset_id": status["active"]["id"],
                "updated_at": status["updated_at"],
            },
        )

    @staticmethod
    def _css_for(resolved: dict[str, Any]) -> str:
        tokens = resolved["tokens"]
        radius = int(tokens["radius_px"])
        border_width = int(tokens["border_width_px"])
        texture_size = "22px 22px" if tokens.get("texture") == "grid" else "auto"
        panel_background = (
            f"{tokens['texture_css']},linear-gradient(115deg,{tokens['surface']},{tokens['surface_alt']})"
            if tokens["texture_css"] != "none"
            else f"linear-gradient(115deg,{tokens['surface']},{tokens['surface_alt']})"
        )
        center_background = (
            f"linear-gradient(180deg,{tokens['primary_color']},{tokens['secondary_color']})"
            if tokens.get("center_style") != "solid"
            else tokens["primary_color"]
        )
        return f"""/* CSRN generated theme: {resolved['id']} */
:root {{
  --csrn-theme-primary: {tokens['primary_color']};
  --csrn-theme-secondary: {tokens['secondary_color']};
  --csrn-theme-accent: {tokens['accent_color']};
  --csrn-theme-surface: {tokens['surface']};
  --csrn-theme-surface-alt: {tokens['surface_alt']};
  --csrn-theme-text: {tokens['text']};
  --csrn-theme-muted: {tokens['muted']};
  --csrn-theme-border: {tokens['border']};
  --csrn-theme-radius: {radius}px;
  --csrn-theme-border-width: {border_width}px;
  --csrn-theme-font: {tokens['font_stack']};
  --csrn-theme-shadow: {tokens['shadow']};
  --csrn-theme-motion: {tokens['motion_scale']};
  --caption-bg: {tokens['secondary_rgba']};
  --caption-border: {tokens['border']};
  --caption-text: {tokens['text']};
  --caption-speaker: {tokens['primary_color']};
}}
html,body {{ font-family: var(--csrn-theme-font) !important; }}
#scorebug,.panel,#lowerThird,#playerGraphic,#personnelGraphic,#eventTicker,.caption-line {{ font-family: var(--csrn-theme-font) !important; }}
#scorebug .team {{ border-width: var(--csrn-theme-border-width) !important; border-color: var(--csrn-theme-border) !important; color: var(--csrn-theme-text) !important; box-shadow: var(--csrn-theme-shadow); }}
#scorebug .team.home {{ border-radius: var(--csrn-theme-radius) 0 0 var(--csrn-theme-radius) !important; }}
#scorebug .team.visitor {{ border-radius: 0 var(--csrn-theme-radius) var(--csrn-theme-radius) 0 !important; }}
#scorebug .center {{ background: {center_background} !important; border-color: var(--csrn-theme-border) !important; color: var(--csrn-theme-text) !important; }}
#scorebug .score {{ background: {tokens['surface_alt']} !important; color: var(--csrn-theme-text) !important; border-color: var(--csrn-theme-border) !important; }}
#eventTicker,#lowerThird,#playerGraphic,#personnelGraphic,.pg-sponsor-bar {{ background: {panel_background} !important; background-size: {texture_size}; color: var(--csrn-theme-text) !important; border-color: var(--csrn-theme-border) !important; border-radius: var(--csrn-theme-radius) !important; box-shadow: var(--csrn-theme-shadow) !important; }}
.lt-footer,.pg-onair-preferred,.pg-onair-details,.pg-sponsor-lead {{ color: var(--csrn-theme-muted) !important; }}
.caption-line {{ background: {tokens['secondary_rgba']} !important; color: var(--csrn-theme-text) !important; border: var(--csrn-theme-border-width) solid var(--csrn-theme-border) !important; border-radius: var(--csrn-theme-radius) !important; box-shadow: var(--csrn-theme-shadow) !important; }}
.caption-line .speaker {{ color: var(--csrn-theme-primary) !important; }}
#weather-overlay .panel,.bug,.banner,.fullscreen {{ font-family: var(--csrn-theme-font) !important; border-radius: var(--csrn-theme-radius) !important; box-shadow: var(--csrn-theme-shadow) !important; }}
.bug,.banner {{ background: {tokens['secondary_rgba']} !important; color: var(--csrn-theme-text) !important; border-color: var(--csrn-theme-border) !important; }}
.banner:not(.emergency) {{ border-left-color: var(--csrn-theme-primary) !important; }}
.fullscreen {{ background: {tokens['surface']} !important; color: var(--csrn-theme-text) !important; }}
#scorebug,#eventTicker,#lowerThird,#playerGraphic,#personnelGraphic,#captions,.panel {{ transition-duration: calc(.30s * var(--csrn-theme-motion)) !important; }}
"""
