"""Layout Builder P1 (docs/LAYOUT_BUILDER_P1.md).

Part A1: sponsor_slot / spotlight_zone / video_zone VISIBILITY.

P0 tried to hide these by display:none on the video-board mode host and the
2026-09-14 live smoke test caught the result: a blank hole where the board
belongs, because sponsor / player / highlight REPLACE the board's content in
the theme markup. The fix is upstream: a layout-hidden element makes its
mode UNAVAILABLE so `themeVideoModeFor()` falls through (next mode, else the
theme's idle board), plus a legacy-overlay suppression class so the old
overlay cannot pop the same content up on top of the themed board.

This repo has no JS test runner, so -- like test_layout_builder_p0.py -- the
runtime is exercised here by static-source assertions, and the BEHAVIOUR was
verified live in a real browser on all four board themes (see the commit
message and docs/LAYOUT_BUILDER_P1.md). tools/layout_builder_smoke.js is that
smoke test made repeatable; the last test below pins that it stays in sync.

Part A2: score_box PLACEMENT. The bonded scorebug node is the theme's whole
full-canvas board, so placement is a uniform scale-to-fit transform (see the
A2 section below), live-verified on all four board themes.
"""

from __future__ import annotations

import re
from pathlib import Path

import app
import layout_builder_service

ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


RUNTIME = "static/csrn-production-theme-runtime.js"


def _function(js: str, name: str) -> str:
    """Source of a top-level `function name(...) { ... }` (brace matched)."""
    start = js.index(f"function {name}(")
    depth, i = 0, js.index("{", start)
    while True:
        depth += {"{": 1, "}": -1}.get(js[i], 0)
        if depth == 0:
            return js[start : i + 1]
        i += 1


# --- the mode -> element -> trigger mapping is consistent everywhere --------


def _js_mapping(js: str, const_name: str) -> dict[str, str]:
    block = re.search(rf"const {const_name} = Object\.freeze\(\{{(.*?)\}}\);", js, re.S).group(1)
    return dict(re.findall(r"(\w+):\s*\"([\w-]+)\"", block))


def test_mode_element_and_trigger_mappings_are_consistent_with_the_rest_of_the_system() -> None:
    js = _read(RUNTIME)
    element_for = _js_mapping(js, "LAYOUT_MODE_ELEMENT_R1")
    trigger_for = _js_mapping(js, "LAYOUT_MODE_TRIGGER_R1")
    assert element_for == {"highlight": "video_zone", "sponsor": "sponsor_slot", "player": "spotlight_zone"}
    assert trigger_for == {"highlight": "player_highlight", "sponsor": "sponsor_spotlight", "player": "player_graphic"}
    assert set(element_for) == set(trigger_for)
    # every owning element is a real layout element the document can carry ...
    assert set(element_for.values()) <= set(layout_builder_service.ELEMENTS)
    # ... every one of them applies to the in-game scene ...
    assert all(layout_builder_service.element_applies_to_scene(e, "in_game") for e in element_for.values())
    # ... and every trigger is a real graphic in the game state.
    for key in trigger_for.values():
        assert isinstance(app.DEFAULT_STATE[key], dict) and app.DEFAULT_STATE[key]["visible"] is False


def test_the_modes_match_the_ones_the_runtime_actually_selects_between() -> None:
    js = _read(RUNTIME)
    body = _function(js, "themeVideoModeFor")
    assert 'return "highlight"' in body and 'return "sponsor"' in body and 'return "player"' in body
    # priority is unchanged: highlight, then sponsor, then player, then idle
    assert body.index('return "highlight"') < body.index('return "sponsor"') < body.index('return "player"')
    assert 'return "broadcast"' in body and 'return "clash"' in body  # the idle modes it falls through to


# --- themeVideoModeFor treats a layout-hidden element as unavailable --------


def test_theme_video_mode_masks_layout_hidden_triggers_before_choosing() -> None:
    body = _function(_read(RUNTIME), "themeVideoModeFor")
    assert "runtime = layoutMaskedRuntimeR1(runtime);" in body
    # the mask is applied BEFORE any selection, including the non-board branch
    assert body.index("layoutMaskedRuntimeR1(runtime)") < body.index("themedVideoBoardSupported(alias)")
    assert body.index("layoutMaskedRuntimeR1(runtime)") < body.index("primaryGraphicVisible(runtime.player_highlight)")


def test_masking_is_inert_without_a_layout_and_never_mutates_its_input() -> None:
    body = _function(_read(RUNTIME), "layoutMaskedRuntimeR1")
    # default preset / no layouts section: the SAME object comes back (zero behaviour change)
    assert "if (!runtime || !runtime.layouts) return runtime;" in body
    assert "return masked || runtime;" in body
    # copies, not in-place edits
    assert "Object.assign({}, runtime)" in body
    assert "Object.assign({}, graphic, {visible: false})" in body
    # only a currently-visible trigger is touched
    assert "!graphic.visible" in body
    assert "runtime[key] =" not in body and "graphic.visible =" not in body


def test_hidden_means_an_explicit_visible_false_override_only() -> None:
    body = _function(_read(RUNTIME), "layoutHidesModeR1")
    assert "override.visible === false" in body
    assert "Boolean(override) &&" in body  # no override -> not hidden (absence is the default preset)
    assert "productionSportFamily(runtime.sport)" in body  # same family key the P0 hook resolves with
    assert "resolveLayoutOverrideR0(" in body  # one resolution routine, not a second copy


# --- renderSelected: one masked view of the runtime for every consumer ------


def test_render_selected_masks_the_runtime_once_and_never_reads_the_raw_payload_again() -> None:
    body = _function(_read(RUNTIME), "renderSelected")
    assert "const [rawRuntime, captionState] = await Promise.all([" in body
    assert "const runtime = layoutMaskedRuntimeR1(rawRuntime);" in body
    assert "syncLayoutSuppressionR1(rawRuntime);" in body
    # everything after the fetch reads `runtime` (the masked view)
    assert body.count("rawRuntime") == 3  # the destructure, the mask, the suppression sync
    # mask is established before the mode, the pending flag and the signature are computed
    assert body.index("layoutMaskedRuntimeR1(rawRuntime)") < body.index("themeVideoModeFor(alias, runtime)")
    assert body.index("layoutMaskedRuntimeR1(rawRuntime)") < body.index("playerVisible(runtime) && themedIntegratedPlayerSupported(alias)")
    assert body.index("layoutMaskedRuntimeR1(rawRuntime)") < body.index("const signature = JSON.stringify([")


def test_a_layout_driven_mode_change_still_forces_a_full_rebuild() -> None:
    """The mode is in the render signature (that is what gates rebuild-vs-patch),
    so hiding/un-hiding an element re-renders instead of leaving stale markup."""
    body = _function(_read(RUNTIME), "renderSelected")
    signature = body.split("const signature = JSON.stringify([")[1].split("]);")[0]
    assert "polledVideoMode" in signature
    # and the mode that goes into it is the layout-aware one
    assert "const polledVideoMode = themeVideoModeFor(alias, runtime);" in body


# --- legacy overlay suppression --------------------------------------------


def test_legacy_nodes_are_suppressed_by_class_while_the_layout_hides_the_element() -> None:
    js = _read(RUNTIME)
    classes = _js_mapping(js, "LAYOUT_HIDE_CLASSES_R1")
    assert classes == {
        "player": "csrn-production-layout-hide-player",
        "sponsor": "csrn-production-layout-hide-sponsor",
        "highlight": "csrn-production-layout-hide-highlight",
    }
    body = _function(js, "syncLayoutSuppressionR1")
    assert "layoutHidesModeR1(runtime, mode)" in body
    assert "classList.toggle(" in body  # set AND cleared, so un-hiding restores the legacy path

    css = _read("static/csrn-production-theme-runtime.css")
    rule = css[css.index("html.csrn-production-layout-hide-player #playerGraphic") :].split("}")[0]
    for selector in (
        "html.csrn-production-layout-hide-player #playerGraphic",
        "html.csrn-production-layout-hide-sponsor #sponsorSpotlight",
        "html.csrn-production-layout-hide-highlight #playerHighlight",
    ):
        assert selector in rule
    assert "display:none!important" in rule and "visibility:hidden!important" in rule


def test_the_suppressed_legacy_nodes_are_the_ones_overlay_html_owns() -> None:
    html = _read("templates/overlay.html")
    for node_id in ("playerGraphic", "sponsorSpotlight", "playerHighlight"):
        assert f'id="{node_id}"' in html
    # overlay.html already guards sponsor for every board alias, but NOT highlight/player --
    # live-verified 2026-09-19: without the class the legacy highlight card leaks on screen.
    assert "CSRN_BOARD_SPONSOR_ALIASES" in html
    assert "playerHighlightEl.classList.toggle('hidden',!playerHighlightVisible)" in html


def test_deactivate_releases_the_suppression_when_the_themed_package_stops_owning_the_overlay() -> None:
    body = _function(_read(RUNTIME), "deactivate")
    assert "...Object.values(LAYOUT_HIDE_CLASSES_R1)" in body


# --- the P0 apply hook must NOT go back to hiding mode hosts ----------------


def test_apply_hook_still_never_hides_a_video_board_mode_host() -> None:
    """The blank-hole bug came from display:none on the mode host. The effect is
    delivered upstream now, so re-adding it here would reintroduce the bug."""
    hook = _function(_read(RUNTIME), "applyLayoutOverrides")
    assert "setNodeVisibilityR0(nativeVideoBoardHost(" not in hook
    for element in ("sponsor_slot", "spotlight_zone", "video_zone"):
        assert f'resolveLayoutOverrideR0(layouts, family, "{element}")' not in hook
    assert "themeVideoModeFor()" in hook and "syncLayoutSuppressionR1()" in hook  # points at where it lives now


def test_default_preset_changes_nothing_in_the_runtime_pipeline() -> None:
    """No layouts -> no mask, no classes: the P0 default-preset guarantee."""
    js = _read(RUNTIME)
    assert "if (!runtime || !runtime.layouts) return runtime;" in _function(js, "layoutMaskedRuntimeR1")
    # syncLayoutSuppressionR1 with no layouts resolves every mode to "not hidden"
    assert "if (!element || !runtime || !runtime.layouts) return false;" in _function(js, "layoutHidesModeR1")


# --- the repeatable browser smoke test --------------------------------------


def test_smoke_harness_exists_and_covers_every_mode_and_fallthrough() -> None:
    smoke = _read("tools/layout_builder_smoke.js")
    for token in (
        "window.__matrix",
        "window.__observe",
        "'/api/runtime-state'",
        "sponsor_slot",
        "spotlight_zone",
        "video_zone",
        "falls through to sponsor",
        "falls through to player",
        "ALL three forced, ALL three hidden",
        "no legacy leak",
        "IDLE",  # collegiate's idle board has no data-video-mode node
    ):
        assert token in smoke, token
    # the harness reads the same class prefix the runtime sets
    assert "csrn-production-layout-hide" in smoke


# --- A2: score_box placement (uniform scale-to-fit) -------------------------


def test_score_box_placement_is_a_transform_never_a_box_resize() -> None:
    body = _function(_read(RUNTIME), "applyScoreBoxPlacementR1")
    # transform + origin 0 0, computed from the node's own layout box
    assert "node.style.transformOrigin = \"0 0\";" in body
    assert "translate(" in body and "scale(" in body
    for forbidden in ("style.left", "style.top", "style.width", "style.height", "style.position"):
        assert forbidden not in body  # the P0 crush: resizing the box leaves px-sized children behind
    # offset* is untouched by a transform, so re-running every poll cannot drift;
    # getBoundingClientRect() would read the already-scaled box and compound
    assert "node.offsetLeft" in body and "node.offsetWidth" in body
    assert "getBoundingClientRect" not in body


def test_score_box_placement_never_upscales_and_refuses_an_illegible_scale() -> None:
    js = _read(RUNTIME)
    assert "const SCORE_BOX_MIN_SCALE_R1 = 0.5;" in js
    body = _function(js, "applyScoreBoxPlacementR1")
    assert "Math.min(target.w / base.w, target.h / base.h, 1)" in body  # fit, capped at native size
    assert "if (scale < SCORE_BOX_MIN_SCALE_R1) {" in body
    refused = body.split("if (scale < SCORE_BOX_MIN_SCALE_R1) {")[1].split("}")[0]
    assert 'dataset.csrnLayoutScoreBox = "too-small"' in refused
    assert "clearScoreBoxPlacementR1(node)" in refused  # the board stays where the theme put it


def test_score_box_placement_is_undone_when_the_override_goes_away() -> None:
    js = _read(RUNTIME)
    body = _function(js, "applyScoreBoxPlacementR1")
    assert "const target = override ? layoutTargetPxR0(override) : null;" in body
    assert "clearScoreBoxPlacementR1(node);" in body.split("if (!target")[1].split("return;")[0]
    clear = _function(js, "clearScoreBoxPlacementR1")
    assert 'node.style.transform = "";' in clear and 'node.style.transformOrigin = "";' in clear
    assert "delete node.dataset.csrnLayoutScoreBox" in clear
    assert "=== undefined) return;" in clear  # a node the layout never touched is left byte-identical


def test_score_box_placement_reuses_the_p0_target_resolver_and_aligns_by_zone_name() -> None:
    js = _read(RUNTIME)
    assert "layoutTargetPxR0(override)" in _function(js, "applyScoreBoxPlacementR1")  # rect wins over zone; zones from the engine
    align = _function(js, "layoutZoneAlignmentR1")
    for token in ('endsWith("-left")', 'endsWith("-right")', 'startsWith("top-")', 'startsWith("bottom-")', "layoutHasRectR1(override)"):
        assert token in align


def test_apply_hook_wires_placement_after_visibility_and_always_offers_the_undo() -> None:
    hook = _function(_read(RUNTIME), "applyLayoutOverrides")
    block = hook.split('"score_box"')[1].split("ticker: visibility")[0]
    assert "setNodeVisibilityR0(scorebugNode, scorebugOverride ? scorebugOverride.visible !== false : true);" in block
    # called for a null override too -> that is what clears a placement live
    assert "applyScoreBoxPlacementR1(scorebugNode, scorebugOverride);" in block
    assert block.index("setNodeVisibilityR0(") < block.index("applyScoreBoxPlacementR1(")


def test_placement_is_inert_by_default() -> None:
    """No layouts section -> the hook returns before touching the board; a
    layouts document with no score_box override reaches the placement call
    with null, whose only effect is clearing what this hook itself set."""
    js = _read(RUNTIME)
    assert 'if (!layouts || typeof layouts !== "object") return; // no section -> untouched' in js
    assert "node.dataset.csrnLayoutScoreBox === undefined) return;" in _function(js, "clearScoreBoxPlacementR1")


def test_smoke_harness_covers_score_box_placement_on_every_theme() -> None:
    smoke = _read("tools/layout_builder_smoke.js")
    for token in (
        "window.__placementMatrix",
        "csrnLayoutScoreBox",
        "REFUSED, board untouched",
        "placed board survives a full rebuild into",
        "layout removed -> board back at native box",
        "idempotent",
    ):
        assert token in smoke, token


# --- B0: ticker placement is reversible; "override removed" undoes visibility --


def test_ticker_placement_remembers_and_restores_the_inline_box() -> None:
    js = _read(RUNTIME)
    assert 'const TICKER_PLACEMENT_PROPS_R1 = ["position", "left", "top", "width", "height"];' in js
    apply = _function(js, "applyTickerPlacementR1")
    assert "node.dataset.csrnLayoutTickerPrev === undefined" in apply  # saved once, before the first write
    assert "const target = override ? layoutTargetPxR0(override) : null;" in apply
    assert "clearTickerPlacementR1(node);" in apply.split("if (!target")[1].split("return;")[0]
    clear = _function(js, "clearTickerPlacementR1")
    assert "raw === undefined) return;" in clear  # a node the layout never touched stays byte-identical
    assert "node.style[prop] = saved[prop] || \"\"" in clear
    assert "delete node.dataset.csrnLayoutTickerPrev" in clear


def test_ticker_placement_takes_the_zones_x_and_width_but_keeps_the_bars_own_height() -> None:
    apply = _function(_read(RUNTIME), "applyTickerPlacementR1")
    assert 'node.style.left = target.x + "px";' in apply
    assert 'node.style.width = target.w + "px";' in apply
    assert "Math.min(nativeHeight || target.h, target.h)" in apply  # never the zone's 245-280px height
    assert 'node.style.height = height + "px";' in apply
    assert "layoutZoneAlignmentR1(override)" in apply  # top-* / bottom-* edge alignment shared with score_box


def test_hook_always_offers_visibility_and_placement_so_a_removed_override_is_undone() -> None:
    hook = _function(_read(RUNTIME), "applyLayoutOverrides")
    # visibility: a null override means "visible" -> setNodeVisibilityR0 restores what it hid
    assert "setNodeVisibilityR0(tickerNode, tickerOverride ? tickerOverride.visible !== false : true);" in hook
    assert "setNodeVisibilityR0(scorebugNode, scorebugOverride ? scorebugOverride.visible !== false : true);" in hook
    # placement: called with the (possibly null) override, never gated on it
    assert "if (isolatedTicker) applyTickerPlacementR1(isolatedTicker, tickerOverride);" in hook
    assert "if (tickerOverride) {" not in hook


def test_only_the_isolated_ticker_component_is_ever_placed() -> None:
    js = _read(RUNTIME)
    assert "setNodeZonePxR0" not in js  # P0's non-reversible, height-stretching setter is gone
    isolated = _function(js, "resolveIsolatedTickerComponentR0")
    assert "closest('[data-component=\"ticker\"]')" in isolated


def test_smoke_harness_covers_ticker_placement() -> None:
    smoke = _read("tools/layout_builder_smoke.js")
    for token in (
        "window.__tickerMatrix",
        "csrnLayoutTickerPrev",
        "override removed -> ticker back at its exact native inline box",
        "no isolated ticker component on this theme",
    ):
        assert token in smoke, token


# --- B1: the builder catalog, strict write validation, routes, live apply -----

import copy
import json

import pytest
from flask import Flask, jsonify

from routes.layout_routes import LayoutRoutesDependencies, create_layout_blueprint

SVC = layout_builder_service


def _doc(**presets):
    return {"active": "default", "presets": {"default": SVC.default_preset(), **presets}}


# LIVE_CONTROLS is what the builder offers; every entry must be something a real
# consumer implements, or the page would show a control that does nothing.


def test_every_live_control_is_a_real_element_that_applies_to_its_scene() -> None:
    assert set(SVC.LIVE_CONTROLS) == set(SVC.SCENES)
    for scene, controls in SVC.LIVE_CONTROLS.items():
        for element, capabilities in controls.items():
            assert element in SVC.ELEMENTS and SVC.element_applies_to_scene(element, scene)
            assert set(capabilities) <= {"visible", "zone"} and "visible" in capabilities
            assert element in SVC.ELEMENT_LABELS


def test_schema_only_elements_are_not_offered_by_the_builder() -> None:
    offered = {element for controls in SVC.LIVE_CONTROLS.values() for element in controls}
    assert {"clock_period", "game_fields", "logo"}.isdisjoint(offered)


def test_in_game_live_controls_match_what_the_theme_runtime_implements() -> None:
    js = _read(RUNTIME)
    hook = _function(js, "applyLayoutOverrides")
    controls = SVC.LIVE_CONTROLS["in_game"]
    # score_box: visibility + placement
    assert controls["score_box"] == ("visible", "zone")
    assert "setNodeVisibilityR0(scorebugNode" in hook and "applyScoreBoxPlacementR1(scorebugNode" in hook
    # ticker: visibility + placement
    assert controls["ticker"] == ("visible", "zone")
    assert "setNodeVisibilityR0(tickerNode" in hook and "applyTickerPlacementR1(isolatedTicker" in hook
    # sponsor / spotlight / video: visibility only, via the layout-aware mode selection
    modes = _js_mapping(js, "LAYOUT_MODE_ELEMENT_R1")
    for element in ("sponsor_slot", "spotlight_zone", "video_zone"):
        assert controls[element] == ("visible",)
        assert element in modes.values()
    assert set(controls) == {"score_box", "ticker", "sponsor_slot", "spotlight_zone", "video_zone"}


def test_pregame_and_halftime_live_controls_match_the_overlay_that_reads_them() -> None:
    html = _read("templates/pregame_universal_overlay.html")
    assert "elementHidden(layoutScene,'sponsor_slot')" in html  # both scenes
    assert "elementHidden('halftime','spotlight_zone')" in html  # halftime ONLY
    assert "elementHidden(scene,'background')" in html  # both scenes
    assert SVC.LIVE_CONTROLS["pregame"] == {"sponsor_slot": ("visible",), "background": ("visible",)}
    assert SVC.LIVE_CONTROLS["halftime"] == {
        "sponsor_slot": ("visible",), "spotlight_zone": ("visible",), "background": ("visible",),
    }


def test_the_scoreboard_zone_choices_are_the_zones_the_runtime_will_not_refuse() -> None:
    values = [value for value, _label in SVC.SCORE_BOX_ZONE_CHOICES]
    assert values == [None, "full-safe", "center"]
    # the engine's own zone sizes (mirrored here only to prove the choice list,
    # not used by the service): board 1840x1000 (smallest measured) needs >= 0.5
    engine = _read("static/csrn-broadcast-layout-engine.js")
    for name in ("full-safe", "center"):
        assert f'"{name}":' in engine
    assert '"full-safe": {x: 40, y: 30, w: 1840, h: 1000}' in engine
    assert '"center": {x: 450, y: 300, w: 1020, h: 520}' in engine


def test_builder_catalog_is_complete_and_json_serialisable() -> None:
    catalog = SVC.builder_catalog()
    json.dumps(catalog)
    assert [s["id"] for s in catalog["scenes"]] == list(SVC.SCENES)
    assert [f["id"] for f in catalog["families"]] == list(SVC.FAMILY_KEYS)
    for scene, rows in catalog["controls"].items():
        assert [r["element"] for r in rows] == list(SVC.LIVE_CONTROLS[scene])
    ticker = next(r for r in catalog["controls"]["in_game"] if r["element"] == "ticker")
    assert ticker["zone_choices"] == "engine"  # filled from window.CSRNBroadcastLayoutEngine.zones
    board = next(r for r in catalog["controls"]["in_game"] if r["element"] == "score_box")
    assert board["zone_choices"][0] == {"value": None, "label": "Theme default"}
    sponsor = next(r for r in catalog["controls"]["in_game"] if r["element"] == "sponsor_slot")
    assert sponsor["zone_choices"] is None


def test_family_keys_agree_with_the_runtime_and_sport_families() -> None:
    import sport_families

    assert set(SVC.FAMILY_KEYS) - {"default"} == {"football", "basketball", "baseball", "softball"}
    for sport in ("football", "canadian_football", "basketball", "baseball", "softball"):
        assert sport_families.base_family(sport) in SVC.FAMILY_KEYS


# --- starters -----------------------------------------------------------------


def test_starters_are_valid_unique_and_only_use_live_all_sports_controls() -> None:
    ids = [s["id"] for s in SVC.STARTER_PRESETS]
    assert len(ids) == len(set(ids)) and "theme-default" in ids
    assert next(s for s in SVC.STARTER_PRESETS if s["id"] == "theme-default")["preset"] == SVC.default_preset()
    for starter in SVC.STARTER_PRESETS:
        assert starter["label"] and starter["description"]
        document, errors = SVC.sanitize_layouts_document(_doc(**{"starter": starter["preset"]}))
        assert errors == [], starter["id"]
        for scene, families in starter["preset"].items():
            assert set(families) <= {"default"}, starter["id"]  # All-sports key only
            for element in families.get("default", {}):
                assert element in SVC.LIVE_CONTROLS[scene], (starter["id"], scene, element)


def test_starter_presets_cannot_be_mutated_through_the_catalog() -> None:
    catalog = SVC.builder_catalog()
    catalog["starters"][0]["preset"]["in_game"]["default"] = {"ticker": {"visible": False}}
    assert SVC.STARTER_PRESETS[0]["preset"] == SVC.default_preset()


# --- strict write validation --------------------------------------------------


def test_a_valid_document_round_trips_canonically() -> None:
    doc = _doc(**{"Friday night": {
        "in_game": {"default": {"ticker": {"visible": False}, "score_box": {"zone": "center"}}, "football": {"sponsor_slot": {"visible": True}}},
        "pregame": {"default": {"background": {"visible": False}}},
        "halftime": {},
    }})
    doc["active"] = "Friday night"
    clean, errors = SVC.sanitize_layouts_document(doc)
    assert errors == [] and clean["active"] == "Friday night"
    again, errors = SVC.sanitize_layouts_document(clean)
    assert errors == [] and again == clean  # idempotent: what was saved re-validates to itself
    assert clean["presets"]["Friday night"]["in_game"]["default"]["score_box"] == {"zone": "center"}
    # and the normalizer the read path uses keeps it byte-for-byte
    assert SVC.normalize_layouts(clean) == clean


def test_empty_overrides_and_families_are_dropped_from_the_canonical_document() -> None:
    doc = _doc(x={"in_game": {"default": {"ticker": {}}, "football": {}}, "pregame": {}, "halftime": {}})
    clean, errors = SVC.sanitize_layouts_document(doc)
    assert errors == [] and clean["presets"]["x"]["in_game"] == {}


def test_an_explicit_visible_true_override_is_kept_so_a_sport_can_opt_out_of_all_sports() -> None:
    clean, errors = SVC.sanitize_layouts_document(_doc(x={"in_game": {"football": {"ticker": {"visible": True}}}}))
    assert errors == [] and clean["presets"]["x"]["in_game"] == {"football": {"ticker": {"visible": True}}}
    # ...and the resolver honours it over the All-sports hide
    doc = _doc(x={"in_game": {"default": {"ticker": {"visible": False}}, "football": {"ticker": {"visible": True}}}})
    clean, _ = SVC.sanitize_layouts_document(doc)
    clean["active"] = "x"
    assert SVC.resolve_override(clean, scene="in_game", base_family="football", element="ticker") == {"visible": True}
    assert SVC.resolve_override(clean, scene="in_game", base_family="basketball", element="ticker") == {"visible": False}


BAD_DOCUMENTS = {
    "not an object": "nope",
    "no presets": {"active": "default", "presets": {}},
    "presets not an object": {"active": "default", "presets": []},
    "default removed": {"active": "x", "presets": {"x": {}}},
    "active missing": {"presets": {"default": {}}},
    "active unknown": {"active": "ghost", "presets": {"default": {}}},
    "unknown scene": _doc(x={"warmup": {}}),
    "scene not an object": _doc(x={"in_game": []}),
    "unknown family": _doc(x={"in_game": {"rugby": {"ticker": {"visible": False}}}}),
    "family not an object": _doc(x={"in_game": {"default": []}}),
    "unknown element": _doc(x={"in_game": {"default": {"jumbotron": {"visible": False}}}}),
    "background in game": _doc(x={"in_game": {"default": {"background": {"visible": False}}}}),
    "override not an object": _doc(x={"in_game": {"default": {"ticker": True}}}),
    "unknown field": _doc(x={"in_game": {"default": {"ticker": {"opacity": 0.5}}}}),
    "visible not a bool": _doc(x={"in_game": {"default": {"ticker": {"visible": "no"}}}}),
    "zone not a name": _doc(x={"in_game": {"default": {"ticker": {"zone": "Bottom Center"}}}}),
    "zone not a string": _doc(x={"in_game": {"default": {"ticker": {"zone": 3}}}}),
    "rect missing keys": _doc(x={"in_game": {"default": {"ticker": {"rect": {"x": 1, "y": 1}}}}}),
    "rect outside canvas": _doc(x={"in_game": {"default": {"ticker": {"rect": {"x": 90, "y": 1, "w": 20, "h": 5}}}}}),
    "rect zero size": _doc(x={"in_game": {"default": {"ticker": {"rect": {"x": 1, "y": 1, "w": 0, "h": 5}}}}}),
    "rect boolean": _doc(x={"in_game": {"default": {"ticker": {"rect": {"x": True, "y": 1, "w": 5, "h": 5}}}}}),
    "z out of range": _doc(x={"in_game": {"default": {"ticker": {"z": 5000}}}}),
    "rotation out of range": _doc(x={"in_game": {"default": {"sponsor_slot": {"rotation_seconds": 0}}}}),
    "name with slash": {"active": "default", "presets": {"default": {}, "a/b": {}}},
    "name empty": {"active": "default", "presets": {"default": {}, "": {}}},
    "name too long": {"active": "default", "presets": {"default": {}, "x" * 41: {}}},
    "name leading space": {"active": "default", "presets": {"default": {}, " x": {}}},
    "too many presets": {"active": "default", "presets": {"default": {}, **{f"p{i}": {} for i in range(SVC.MAX_PRESETS)}}},
}


@pytest.mark.parametrize("label", sorted(BAD_DOCUMENTS))
def test_the_write_path_rejects_a_bad_document_whole(label: str) -> None:
    clean, errors = SVC.sanitize_layouts_document(copy.deepcopy(BAD_DOCUMENTS[label]))
    assert clean is None and errors, label  # nothing partially valid is ever returned to save


def test_a_preset_named_default_is_required_but_others_are_free() -> None:
    clean, errors = SVC.sanitize_layouts_document({"active": "default", "presets": {"default": {}, "Game 1.5-b_c": {}}})
    assert errors == [] and set(clean["presets"]) == {"default", "Game 1.5-b_c"}


def test_sanitize_never_mutates_its_input() -> None:
    doc = _doc(x={"in_game": {"default": {"ticker": {"visible": False}}}})
    before = copy.deepcopy(doc)
    SVC.sanitize_layouts_document(doc)
    assert doc == before


# --- routes (real blueprint, fake deps) ----------------------------------------


def _routes_app(*, authed: bool = True, save=None, current=None):
    calls: dict = {"save": []}

    def require_auth(func):
        def wrapper(*args, **kwargs):
            if not authed:
                return jsonify({"error": "AUTH_REQUIRED"}), 401
            return func(*args, **kwargs)
        wrapper.__name__ = func.__name__
        return wrapper

    def default_save(document):
        calls["save"].append(copy.deepcopy(document))
        return document

    app_ = Flask(__name__, template_folder=str(ROOT / "templates"))
    app_.register_blueprint(create_layout_blueprint(LayoutRoutesDependencies(
        require_auth=require_auth,
        get_layouts=lambda: copy.deepcopy(current or SVC.default_layouts_document()),
        save_layouts=save or default_save,
    )))
    return app_, calls


def test_get_returns_the_document_and_catalog_uncached() -> None:
    app_, _ = _routes_app()
    response = app_.test_client().get("/api/layouts")
    assert response.status_code == 200 and "no-store" in response.headers["Cache-Control"]
    body = response.get_json()
    assert body["layouts"] == SVC.default_layouts_document()
    assert body["catalog"]["controls"]["in_game"][0]["element"] == "score_box"


def test_post_saves_the_canonical_document_and_reports_live() -> None:
    app_, calls = _routes_app()
    doc = _doc(x={"in_game": {"default": {"ticker": {}, "sponsor_slot": {"visible": False}}}})
    response = app_.test_client().post("/api/layouts", json={"layouts": doc})
    assert response.status_code == 200
    body = response.get_json()
    assert body["applied"] == "live"
    assert calls["save"] == [{"active": "default", "presets": {
        "default": {"in_game": {}, "pregame": {}, "halftime": {}},
        "x": {"in_game": {"default": {"sponsor_slot": {"visible": False}}}, "pregame": {}, "halftime": {}},
    }}]  # the empty ticker override was dropped BEFORE saving


@pytest.mark.parametrize("body", [None, {}, {"layouts": "x"}, {"layouts": {"active": "default", "presets": {}}}, [1]])
def test_post_rejects_invalid_bodies_without_saving(body) -> None:
    app_, calls = _routes_app()
    response = app_.test_client().post("/api/layouts", json=body) if body is not None else app_.test_client().post("/api/layouts", data="not json")
    assert response.status_code == 400
    assert response.get_json()["error"] in {"LAYOUTS_REQUIRED", "LAYOUTS_INVALID"} and response.get_json()["errors"]
    assert calls["save"] == []


def test_post_reports_a_write_failure_as_500_not_a_crash() -> None:
    def broken(_document):
        raise OSError("disk full")

    app_, _ = _routes_app(save=broken)
    response = app_.test_client().post("/api/layouts", json={"layouts": SVC.default_layouts_document()})
    assert response.status_code == 500 and response.get_json()["error"] == "LAYOUTS_SAVE_FAILED"


def test_every_builder_route_is_behind_require_auth() -> None:
    app_, calls = _routes_app(authed=False)
    client = app_.test_client()
    assert client.get("/layouts").status_code == 401
    assert client.get("/api/layouts").status_code == 401
    assert client.post("/api/layouts", json={"layouts": SVC.default_layouts_document()}).status_code == 401
    assert calls["save"] == []


def test_the_real_app_gates_the_builder_and_registers_it_as_an_authed_blueprint() -> None:
    import app as app_module

    client = app_module.app.test_client()
    for method, path in (("get", "/layouts"), ("get", "/api/layouts"), ("post", "/api/layouts")):
        assert getattr(client, method)(path).status_code in {401, 403}, path
    rules = {r.rule: r for r in app_module.app.url_map.iter_rules() if r.endpoint.startswith("layout_routes.")}
    assert set(rules) == {"/layouts", "/api/layouts"}
    assert "layout_routes" in __import__("phase5_architecture").EXPECTED_BLUEPRINTS


# --- live apply: the write path actually reaches the runtime ------------------


@pytest.fixture()
def isolated_identity(tmp_path, monkeypatch):
    import app as app_module
    import identity_service
    import runtime_state_cache

    identity_file = tmp_path / "identity_profile.json"
    profile = identity_service.load_identity_profile(identity_file, existing_install=True)
    identity_service.save_identity_profile(identity_file, profile, existing_install=True)
    monkeypatch.setattr(app_module, "IDENTITY_FILE", identity_file)
    monkeypatch.setattr(app_module, "IDENTITY_PROFILE", profile)
    monkeypatch.setattr(app_module, "_EXISTING_INSTALL", True)
    runtime_state_cache._cached = None
    yield app_module, identity_file
    runtime_state_cache._cached = None


def test_save_writes_only_layouts_rebinds_the_profile_and_drops_the_runtime_cache(isolated_identity) -> None:
    app_module, identity_file = isolated_identity
    before = json.loads(identity_file.read_text(encoding="utf-8"))
    client = app_module.app.test_client()

    first = client.get("/api/runtime-state").get_json()
    assert first["layouts"] == SVC.default_layouts_document()  # primes the 250 ms runtime-state cache

    document, errors = SVC.sanitize_layouts_document(_doc(x={"in_game": {"default": {"ticker": {"visible": False}}}}))
    assert errors == []
    document["active"] = "x"
    saved = app_module.save_layouts_document(document)

    after = json.loads(identity_file.read_text(encoding="utf-8"))
    assert after["layouts"] == saved == document
    assert {k: v for k, v in after.items() if k != "layouts"} == {k: v for k, v in before.items() if k != "layouts"}
    assert app_module.IDENTITY_PROFILE["layouts"] == document  # rebound: no restart

    # served on the very next poll, even inside the 250 ms cache window
    second = client.get("/api/runtime-state").get_json()
    assert second["layouts"] == document
    assert SVC.resolve_override(second["layouts"], scene="in_game", base_family="football", element="ticker") == {"visible": False}


def test_save_is_seen_by_the_pregame_and_halftime_payload_without_a_restart(isolated_identity) -> None:
    import pregame_presentation

    app_module, _ = isolated_identity
    assert pregame_presentation._layout_overrides("football", "pregame") == {}
    document, _ = SVC.sanitize_layouts_document(_doc(x={
        "pregame": {"default": {"sponsor_slot": {"visible": False}}},
        "halftime": {"football": {"spotlight_zone": {"visible": False}}},
    }))
    document["active"] = "x"
    app_module.save_layouts_document(document)
    assert pregame_presentation._layout_overrides("football", "pregame") == {"sponsor_slot": {"visible": False}}
    assert pregame_presentation._layout_overrides("football", "halftime") == {"spotlight_zone": {"visible": False}}
    assert pregame_presentation._layout_overrides("basketball", "halftime") == {}  # football-only override


def test_other_identity_writers_do_not_wipe_the_layouts_section(isolated_identity) -> None:
    """Configuration Manager saves re-write identity_profile.json
    (_persist_identity_sections); the builder's document must survive them."""
    app_module, identity_file = isolated_identity
    document, _ = SVC.sanitize_layouts_document(_doc(x={"in_game": {"default": {"ticker": {"visible": False}}}}))
    document["active"] = "x"
    app_module.save_layouts_document(document)
    config = json.loads(identity_file.read_text(encoding="utf-8"))
    app_module._persist_identity_sections({"organization": dict(config["organization"])})
    assert json.loads(identity_file.read_text(encoding="utf-8"))["layouts"] == document


def test_save_preserves_layouts_across_a_reload_from_disk(isolated_identity) -> None:
    import identity_service

    app_module, identity_file = isolated_identity
    document, _ = SVC.sanitize_layouts_document(_doc(**{"Game night": {"in_game": {"default": {"score_box": {"zone": "full-safe"}}}}}))
    document["active"] = "Game night"
    app_module.save_layouts_document(document)
    reloaded = identity_service.load_identity_profile(identity_file, existing_install=True)
    assert reloaded["layouts"] == document
