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
