"""Layout Builder P0 (docs/LAYOUT_BUILDER_RECONCILIATION.md): the layout/
content/style data model's Layout layer -- a serializable per-customer
document (stored in identity_profile.json, managed by identity_service.py)
that both the In-Game engine (csrn-production-theme-runtime.js's additive
apply hook) and the Pregame/Halftime presentation module
(pregame_presentation.py's additive read) consult for per-element
visibility/position/behavior overrides.

Content (score, stats, spotlight triggers -- the data engine) and Style
(theme/skin/identity colors) are untouched by this module; per the
recovered spec, Layout is the only new artifact.

Design decision (flagged for confirmation, not silently assumed): this
module does NOT parse or mirror csrn-broadcast-layout-engine.js's
PACKAGE_MANIFESTS/ZONES/SPORT_CONTRACTS into Python. That frozen data is
already exposed to JavaScript at window.CSRNBroadcastLayoutEngine (zones,
manifests, sports, resolvePlacements, ...) -- the runtime-side apply hook
(csrn-production-theme-runtime.js) reads it directly, in the same browser
context that already executes it. Mirroring the same catalog into Python
here would be a second, driftable copy of frozen data this module has no
way to keep in sync automatically (Python cannot execute the .js file).
This service instead owns exactly what needs to be engine-independent,
sport-agnostic knowledge: the elements/scenes vocabulary the layout
DOCUMENT itself uses (spec Sec.5.1 element inventory), the empty
"default" preset construction, and the override-resolution/fallback
logic (per-base_family, then the "default" family key) any consumer --
Python or JS -- applies identically.

"Default" preset semantics: every element for every (scene, base_family)
in the shipped "default" preset is intentionally ABSENT, not populated
with captured pixel values. Absence of an override IS the "reproduces
resolvePlacements() output exactly" contract -- a captured-value default
would silently go stale the moment resolvePlacements()'s own algorithm or
a theme's zone geometry ever changed, whereas "no override present" can
never drift from whatever the engine currently does. Any future P1 UI
that wants to show an element's CURRENT actual position as an editing
starting point reads that live from the browser
(window.CSRNBroadcastLayoutEngine), not from this stored document.
"""

from __future__ import annotations

import copy
from typing import Any, Mapping

# Spec: "one system, three scenes."
#
# Scene vs PRESENTATION_SCENARIOS (kickoff prompt deliverable 5; full
# reasoning in docs/LAYOUT_BUILDER_RECONCILIATION.md Sec.2): `scene` is the
# broadcast PHASE (in_game / pregame / halftime) this module's overrides
# are keyed by. The frozen engine's own `PRESENTATION_SCENARIOS`
# (baseline/captions/player/highlight/sponsor/feature) are a DIFFERENT,
# orthogonal axis -- they are the In-Game scene's own trigger/component-set
# states (which of spotlight_zone/video_zone/sponsor_slot/captions is
# currently popped in, driven by live game state, not by this layout
# document). An in_game element's `behavior` field (e.g. sponsor_slot's
# persistent/on_call) NAMES one of those trigger states for the runtime to
# bind to -- it never redefines or replaces PRESENTATION_SCENARIOS, which
# this module does not touch.
SCENES: tuple[str, ...] = ("in_game", "pregame", "halftime")

# Spec Sec.5.1 element inventory -- "game_fields" replaces "down_distance"
# per the reconciliation doc's own resolution (family-resolved, not
# sport-specific, Sec.5.3). score_box stays a single paired element in P0
# (independent home/visitor placement is a P2 decision, reconciliation
# doc Sec.6 item 4).
ELEMENTS: tuple[str, ...] = (
    "score_box", "clock_period", "game_fields", "ticker", "sponsor_slot",
    "spotlight_zone", "video_zone", "logo", "background",
)

# Spec: "The Builder cannot delete the region or strip its attributes" --
# video_zone's data-module="video.board" / [data-video-mode] markup must
# survive any override; visibility toggles it, nothing ever removes it.
CONTRACT_BOUND_ELEMENTS: frozenset[str] = frozenset({"video_zone"})

# background is pregame/halftime only -- spec: "never an In-Game element"
# (transparency is load-bearing for OBS compositing there).
SCENE_ONLY_ELEMENTS: dict[str, frozenset[str]] = {
    "background": frozenset({"pregame", "halftime"}),
}

# The layout document's own all-sports/unspecified-family fallback key.
# Deliberately not reusing sport_families.py's "default"/base_family
# vocabulary directly -- this key means "no per-family override was
# authored," a layout-document concept, not a sport-family one.
DEFAULT_FAMILY_KEY = "default"

DEFAULT_PRESET_NAME = "default"

# An element override is {visible, zone|rect, z, behavior, ...} (kickoff
# prompt deliverable 1). This module treats that value as an opaque dict --
# it never validates or interprets zone/rect/z/behavior itself (see module
# docstring: no mirrored engine geometry in Python). The convention, fixed
# by the runtime apply hook (csrn-production-theme-runtime.js) that's the
# first real consumer: `zone` is a STRING naming a zone from the frozen
# engine's own ZONES table (e.g. "bottom-center") -- reused directly via
# window.CSRNBroadcastLayoutEngine.zones, zero duplicated geometry; `rect`
# is an explicit {x, y, w, h} in % of the 1920x1080 canvas, taking
# precedence over `zone` when both are present (the P1/P2 freeform escape
# hatch). `visible: false` hides the element; absent or `true` leaves it
# alone.


def default_preset() -> dict[str, Any]:
    """The shipped 'default' preset: every scene present, but with zero
    per-family/per-element overrides. See module docstring for why empty
    is the correct 'reproduces today's render exactly' contract, not a
    placeholder to fill in later."""
    return {scene: {} for scene in SCENES}


def default_layouts_document() -> dict[str, Any]:
    return {
        "active": DEFAULT_PRESET_NAME,
        "presets": {DEFAULT_PRESET_NAME: default_preset()},
    }


def element_applies_to_scene(element: str, scene: str) -> bool:
    if element not in ELEMENTS:
        raise ValueError(f"unknown layout element: {element}")
    if scene not in SCENES:
        raise ValueError(f"unknown layout scene: {scene}")
    restriction = SCENE_ONLY_ELEMENTS.get(element)
    if restriction is None:
        return True
    return scene in restriction


def normalize_layouts(raw: Any) -> dict[str, Any]:
    """Merge a raw (possibly partial/legacy/absent) layouts document onto
    the default shape. Never raises on malformed input -- returns the
    default document instead, the same defensive convention
    identity_service.py's own _normalize() already uses for its other
    sections."""
    base = default_layouts_document()
    if not isinstance(raw, Mapping):
        return base

    presets_raw = raw.get("presets")
    if isinstance(presets_raw, Mapping) and presets_raw:
        presets: dict[str, Any] = {}
        for name, preset in presets_raw.items():
            if not isinstance(preset, Mapping):
                continue
            merged_preset: dict[str, Any] = {}
            for scene in SCENES:
                scene_value = preset.get(scene)
                merged_preset[scene] = (
                    copy.deepcopy(dict(scene_value))
                    if isinstance(scene_value, Mapping)
                    else {}
                )
            presets[str(name)] = merged_preset
        if presets:
            base["presets"] = presets

    active = raw.get("active")
    if isinstance(active, str) and active in base["presets"]:
        base["active"] = active
    elif DEFAULT_PRESET_NAME not in base["presets"]:
        # Whatever preset survived normalization becomes "active" if the
        # shipped default name itself isn't present (e.g. a customer
        # renamed/deleted it) -- never point "active" at a preset that
        # doesn't exist.
        base["active"] = next(iter(base["presets"]))
    return base


def active_preset(layouts_document: Mapping[str, Any] | None) -> dict[str, Any]:
    doc = normalize_layouts(layouts_document)
    return doc["presets"][doc["active"]]


def resolve_override(
    layouts_document: Mapping[str, Any] | None,
    *,
    scene: str,
    base_family: str,
    element: str,
) -> dict[str, Any] | None:
    """The lookup every consumer (the runtime apply hook, the pregame/
    halftime read hook) uses identically: the active preset's
    (scene, base_family, element) override if present, else the scene's
    (DEFAULT_FAMILY_KEY, element) all-sports fallback, else None -- None
    meaning "no override; let the existing renderer do what it already
    does," never an empty dict standing in for "hide this."
    """
    if scene not in SCENES:
        raise ValueError(f"unknown layout scene: {scene}")
    preset = active_preset(layouts_document)
    scene_doc = preset.get(scene) or {}

    family_doc = scene_doc.get(base_family)
    if isinstance(family_doc, Mapping) and element in family_doc:
        value = family_doc[element]
        return dict(value) if isinstance(value, Mapping) else None

    fallback_doc = scene_doc.get(DEFAULT_FAMILY_KEY)
    if isinstance(fallback_doc, Mapping) and element in fallback_doc:
        value = fallback_doc[element]
        return dict(value) if isinstance(value, Mapping) else None

    return None


def scene_overrides_for_family(
    layouts_document: Mapping[str, Any] | None,
    *,
    scene: str,
    base_family: str,
) -> dict[str, dict[str, Any]]:
    """Every element with a resolved override for (scene, base_family) --
    what a read hook (pregame/halftime, or a future P1 UI) actually needs:
    one lookup per scene rather than one call to resolve_override() per
    element name."""
    return {
        element: override
        for element in ELEMENTS
        if element_applies_to_scene(element, scene)
        and (override := resolve_override(
            layouts_document, scene=scene, base_family=base_family, element=element,
        )) is not None
    }


# ---------------------------------------------------------------------------
# Layout Builder P1: the guided-customization builder's catalog + write path.
#
# Everything above is the P0 data model (read side). Everything below is what
# P1's builder UI (templates/layout_builder.html, routes/layout_routes.py)
# needs: which controls the runtime ACTUALLY honours today, the curated
# starter presets, and strict validation of a document before it is written to
# identity_profile.json for the first time.
#
# Like the rest of this module it does not mirror the frozen engine's zone
# geometry: the builder page reads window.CSRNBroadcastLayoutEngine.zones in
# the browser, and validation here only checks that a `zone` is a plausible
# zone NAME (unknown names are a harmless no-op at runtime).
# ---------------------------------------------------------------------------

FAMILY_KEYS: tuple[str, ...] = (DEFAULT_FAMILY_KEY, "football", "basketball", "baseball", "softball")

FAMILY_LABELS: dict[str, str] = {
    DEFAULT_FAMILY_KEY: "All sports",
    "football": "Football",
    "basketball": "Basketball",
    "baseball": "Baseball",
    "softball": "Softball",
}

ELEMENT_LABELS: dict[str, str] = {
    "score_box": "Scoreboard",
    "ticker": "Ticker",
    "sponsor_slot": "Sponsor",
    "spotlight_zone": "Player spotlight",
    "video_zone": "Highlight video",
    "background": "Background",
}

SCENE_LABELS: dict[str, str] = {
    "in_game": "In game",
    "pregame": "Pregame",
    "halftime": "Halftime",
}

# What each scene's runtime consumer honours TODAY -- the single source the
# builder UI is generated from, so it can never offer a control that does
# nothing. Capabilities: "visible" (show/hide) and "zone" (placement).
# tests/test_layout_builder_p1.py pins every entry to the consumer that
# implements it (csrn-production-theme-runtime.js for in_game,
# pregame_universal_overlay.html for pregame/halftime); clock_period,
# game_fields and logo stay schema-only until the themes expose them.
LIVE_CONTROLS: dict[str, dict[str, tuple[str, ...]]] = {
    "in_game": {
        "score_box": ("visible", "zone"),
        "ticker": ("visible", "zone"),
        "sponsor_slot": ("visible",),
        "spotlight_zone": ("visible",),
        "video_zone": ("visible",),
    },
    "pregame": {
        "sponsor_slot": ("visible",),
        "background": ("visible",),
    },
    "halftime": {
        "sponsor_slot": ("visible",),
        "spotlight_zone": ("visible",),
        "background": ("visible",),
    },
}

# Zones the scoreboard placement is offered. The bonded board is a full-canvas
# composition that is scaled to fit (see applyScoreBoxPlacementR1), so only
# zones large enough to keep it legible (fit scale >= 0.5) are meaningful; the
# engine's compact strips (top-left, bottom-center, ...) would be refused at
# runtime. Value None = "leave the theme's own placement".
SCORE_BOX_ZONE_CHOICES: tuple[tuple[str | None, str], ...] = (
    (None, "Theme default"),
    ("full-safe", "Fit to safe area"),
    ("center", "Centered, reduced size"),
)

MAX_PRESETS = 12
_PRESET_NAME_MAX = 40
_ALLOWED_OVERRIDE_KEYS = frozenset({"visible", "zone", "rect", "z", "behavior", "rotation_seconds"})


def _hide(*elements: str) -> dict[str, dict[str, Any]]:
    return {element: {"visible": False} for element in elements}


def _starter(scenes: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    preset = default_preset()
    for scene, elements in scenes.items():
        preset[scene] = {DEFAULT_FAMILY_KEY: copy.deepcopy(dict(elements))} if elements else {}
    return preset


# Curated starting points (all written under the "All sports" family key, so
# they apply to every sport and can be refined per sport afterwards).
STARTER_PRESETS: tuple[dict[str, Any], ...] = (
    {
        "id": "theme-default",
        "label": "Theme as designed",
        "description": "No changes: every element exactly where the theme puts it.",
        "preset": _starter({}),
    },
    {
        "id": "no-ticker",
        "label": "No ticker",
        "description": "Hides the ticker during the game.",
        "preset": _starter({"in_game": _hide("ticker")}),
    },
    {
        "id": "centered-board",
        "label": "Centered board",
        "description": "Scales the scoreboard down and centers it on the canvas.",
        "preset": _starter({"in_game": {"score_box": {"zone": "center"}}}),
    },
    {
        "id": "board-only",
        "label": "Scoreboard only",
        "description": "Hides the ticker, sponsor, player spotlight and highlight video in game.",
        "preset": _starter({"in_game": _hide("ticker", "sponsor_slot", "spotlight_zone", "video_zone")}),
    },
    {
        "id": "no-sponsors",
        "label": "No sponsors",
        "description": "Hides sponsor content in game, pregame and halftime.",
        "preset": _starter({
            "in_game": _hide("sponsor_slot"),
            "pregame": _hide("sponsor_slot"),
            "halftime": _hide("sponsor_slot"),
        }),
    },
)


def builder_catalog() -> dict[str, Any]:
    """Everything the builder page needs that is not the customer's own
    document: scenes, the live controls per scene, family choices, starters."""

    def zone_choices(element: str, capabilities: tuple[str, ...]) -> Any:
        if "zone" not in capabilities:
            return None
        if element == "score_box":
            return [{"value": value, "label": label} for value, label in SCORE_BOX_ZONE_CHOICES]
        return "engine"  # the page fills these from window.CSRNBroadcastLayoutEngine.zones

    return {
        "scenes": [{"id": scene, "label": SCENE_LABELS[scene]} for scene in SCENES],
        "families": [{"id": key, "label": FAMILY_LABELS[key]} for key in FAMILY_KEYS],
        "controls": {
            scene: [
                {
                    "element": element,
                    "label": ELEMENT_LABELS[element],
                    "capabilities": list(capabilities),
                    "zone_choices": zone_choices(element, capabilities),
                }
                for element, capabilities in LIVE_CONTROLS[scene].items()
            ]
            for scene in SCENES
        },
        "starters": copy.deepcopy(list(STARTER_PRESETS)),
        "max_presets": MAX_PRESETS,
    }


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value == value


def _is_slug(value: str) -> bool:
    return bool(value) and value[0].isalpha() and all(ch.islower() or ch == "-" for ch in value)


def _check_rect(path: str, value: Any, errors: list[str]) -> dict[str, Any] | None:
    if not isinstance(value, Mapping) or set(value) != {"x", "y", "w", "h"}:
        errors.append(f"{path}: must have exactly x, y, w and h (percent of the canvas)")
        return None
    if not all(_is_number(value[key]) for key in ("x", "y", "w", "h")):
        errors.append(f"{path}: x, y, w and h must be numbers")
        return None
    x, y, w, h = (value[key] for key in ("x", "y", "w", "h"))
    if x < 0 or y < 0 or w <= 0 or h <= 0 or x + w > 100 or y + h > 100:
        errors.append(f"{path}: must sit inside the canvas (0-100%) with a positive size")
        return None
    return {"x": x, "y": y, "w": w, "h": h}


def _check_override(path: str, override: Any, errors: list[str]) -> dict[str, Any] | None:
    if not isinstance(override, Mapping):
        errors.append(f"{path}: an override must be an object")
        return None
    clean: dict[str, Any] = {}
    for key, value in override.items():
        where = f"{path}.{key}"
        if key not in _ALLOWED_OVERRIDE_KEYS:
            errors.append(f"{where}: unknown override field")
        elif key == "visible":
            if isinstance(value, bool):
                clean[key] = value
            else:
                errors.append(f"{where}: must be true or false")
        elif key == "zone":
            if isinstance(value, str) and len(value) <= 32 and _is_slug(value):
                clean[key] = value
            else:
                errors.append(f'{where}: must be a zone name such as "center"')
        elif key == "rect":
            rect = _check_rect(where, value, errors)
            if rect is not None:
                clean[key] = rect
        elif key == "z":
            if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 1000:
                clean[key] = value
            else:
                errors.append(f"{where}: must be a whole number from 0 to 1000")
        elif key == "behavior":
            if isinstance(value, str) and 0 < len(value) <= 32:
                clean[key] = value
            else:
                errors.append(f"{where}: must be a short text value")
        elif key == "rotation_seconds":
            if _is_number(value) and 1 <= value <= 600:
                clean[key] = value
            else:
                errors.append(f"{where}: must be between 1 and 600")
    return clean


def _valid_preset_name(name: str) -> bool:
    return (
        0 < len(name) <= _PRESET_NAME_MAX
        and name == name.strip()
        and name[0].isalnum()
        and all(ch.isalnum() or ch in " _.-" for ch in name)
    )


def sanitize_layouts_document(raw: Any) -> tuple[dict[str, Any] | None, list[str]]:
    """Strict validation for the WRITE path (normalize_layouts() is the
    forgiving READ path). Returns (canonical document, errors); the document is
    None whenever there are errors, so nothing partially valid is ever saved.
    Canonical = empty overrides/families dropped, so a save of an untouched
    document round-trips to the same bytes."""
    errors: list[str] = []
    if not isinstance(raw, Mapping):
        return None, ["layouts: must be an object"]
    presets_raw = raw.get("presets")
    if not isinstance(presets_raw, Mapping) or not presets_raw:
        return None, ["layouts.presets: must be an object with at least one preset"]
    if len(presets_raw) > MAX_PRESETS:
        errors.append(f"layouts.presets: at most {MAX_PRESETS} presets")
    if DEFAULT_PRESET_NAME not in presets_raw:
        errors.append(f'layouts.presets: the "{DEFAULT_PRESET_NAME}" preset cannot be removed')

    presets: dict[str, Any] = {}
    for name, preset in presets_raw.items():
        label = f"layouts.presets[{name!r}]"
        if not isinstance(name, str) or not _valid_preset_name(name):
            errors.append(f"{label}: preset names are 1-{_PRESET_NAME_MAX} letters, numbers, spaces, - _ .")
            continue
        if not isinstance(preset, Mapping):
            errors.append(f"{label}: must be an object")
            continue
        for scene in preset:
            if scene not in SCENES:
                errors.append(f"{label}: unknown scene {scene!r}")
        clean_preset: dict[str, Any] = {}
        for scene in SCENES:
            scene_raw = preset.get(scene, {})
            if not isinstance(scene_raw, Mapping):
                errors.append(f"{label}.{scene}: must be an object")
                continue
            clean_scene: dict[str, Any] = {}
            for family, elements in scene_raw.items():
                fpath = f"{label}.{scene}.{family}"
                if family not in FAMILY_KEYS:
                    errors.append(f"{fpath}: unknown sport family")
                    continue
                if not isinstance(elements, Mapping):
                    errors.append(f"{fpath}: must be an object")
                    continue
                clean_family: dict[str, Any] = {}
                for element, override in elements.items():
                    epath = f"{fpath}.{element}"
                    if element not in ELEMENTS:
                        errors.append(f"{epath}: unknown element")
                    elif not element_applies_to_scene(element, scene):
                        errors.append(f"{epath}: not available in the {scene} scene")
                    else:
                        clean = _check_override(epath, override, errors)
                        if clean:
                            clean_family[element] = clean
                if clean_family:
                    clean_scene[family] = clean_family
            clean_preset[scene] = clean_scene
        presets[name] = clean_preset

    active = raw.get("active")
    if not isinstance(active, str) or active not in presets_raw:
        errors.append("layouts.active: must name one of the presets")
    if errors:
        return None, errors
    return {"active": active, "presets": presets}, []
