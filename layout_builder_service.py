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
