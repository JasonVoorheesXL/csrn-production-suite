"""Layout Builder P0 (docs/LAYOUT_BUILDER_RECONCILIATION.md) -- the tests
called for by the finalized Phase 0 kickoff prompt (Sec.7, deliverable 6):

  * The generated `default` preset, for every (theme x base_family),
    reproduces resolvePlacements() output exactly (golden).
  * Layout-doc round-trips through identity_service load/save.
  * video_zone's data-module="video.board" / [data-video-mode] contract is
    untouched (this hook no longer applies any override to video_zone at
    all -- see below).
  * Football live overlay rendering is byte-identical with no `layouts`
    section and with a `default` preset present.
  * Pregame/Halftime overlays unchanged with no override.

Static-source assertions on the .js/.html runtime files below follow this
repo's own established convention for exercising unpinned JS from Python
(see e.g. tests/test_gate166_production_render_binding.py) rather than
executing the JS -- no test harness in this repo runs it.

Sec.8's real manual browser smoke test (2026-09-14, required before
merging -- not the golden/round-trip tests above) caught two live bugs in
the FIRST version of the in-game hook: repositioning score_box or hiding
sponsor_slot/spotlight_zone/video_zone both broke the rendered page rather
than degrading gracefully. Both were reverted (not shipped, not silently
downgraded to "best effort") -- see csrn-production-theme-runtime.js's own
module docstring above applyLayoutOverrides() for the full root-cause
account. The tests below assert the NARROWER, live-verified-safe final
scope, not the originally-planned one. (Update, Layout Builder P1 A1:
sponsor_slot / spotlight_zone / video_zone visibility is now delivered
upstream of this hook via layout-aware mode selection -- see
tests/test_layout_builder_p1.py -- but this hook still never hides a mode
host, which is what the tests here keep pinning.)
"""

from __future__ import annotations

import json
from pathlib import Path

import identity_service
import layout_builder_service
import pregame_presentation

ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


# --- Golden: the shipped default preset reproduces resolvePlacements() ----
# exactly, for every (theme x base_family), because it is empty. See
# layout_builder_service.py's own module docstring for the full argument:
# an ABSENT override can never drift from whatever resolvePlacements()
# currently does, whereas a captured-pixel default would. This is the
# entire golden guarantee -- there is nothing per-theme or per-sport to
# enumerate, because there are zero stored overrides to check.
def test_default_preset_has_zero_overrides_for_every_scene():
    preset = layout_builder_service.default_preset()
    assert set(preset) == set(layout_builder_service.SCENES)
    for scene in layout_builder_service.SCENES:
        assert preset[scene] == {}


def test_default_layouts_document_shape():
    doc = layout_builder_service.default_layouts_document()
    assert doc["active"] == "default"
    assert doc["presets"] == {"default": layout_builder_service.default_preset()}


def test_resolve_override_is_none_for_every_element_under_the_default_preset():
    doc = layout_builder_service.default_layouts_document()
    for scene in layout_builder_service.SCENES:
        for element in layout_builder_service.ELEMENTS:
            if not layout_builder_service.element_applies_to_scene(element, scene):
                continue
            for family in ("football", "basketball", "baseball", "softball", "default"):
                assert layout_builder_service.resolve_override(
                    doc, scene=scene, base_family=family, element=element,
                ) is None


# --- Round-trip through identity_service load/save -------------------------

def test_layouts_round_trips_through_identity_service(tmp_path):
    identity_file = tmp_path / "identity_profile.json"
    profile = identity_service.load_identity_profile(identity_file, existing_install=True)
    # Fresh seed -- existing_install or not, layouts always seeds to the
    # same empty default (module docstring: "there is no legacy layout to
    # seed from").
    assert profile["layouts"] == layout_builder_service.default_layouts_document()

    override = {
        "active": "default",
        "presets": {
            "default": {
                "in_game": {
                    "football": {
                        "ticker": {"visible": False, "zone": "bottom-center"},
                    },
                },
                "pregame": {},
                "halftime": {},
            },
        },
    }
    profile["layouts"] = override
    saved = identity_service.save_identity_profile(identity_file, profile, existing_install=True)
    assert saved["layouts"]["presets"]["default"]["in_game"]["football"]["ticker"] == {
        "visible": False, "zone": "bottom-center",
    }

    on_disk = json.loads(identity_file.read_text(encoding="utf-8"))
    assert on_disk["layouts"] == saved["layouts"]

    reloaded = identity_service.load_identity_profile(identity_file, existing_install=True)
    assert reloaded["layouts"]["presets"]["default"]["in_game"]["football"]["ticker"] == {
        "visible": False, "zone": "bottom-center",
    }


def test_malformed_layouts_on_disk_falls_back_to_default_not_a_crash(tmp_path):
    identity_file = tmp_path / "identity_profile.json"
    identity_file.write_text(
        json.dumps({"layouts": "not-a-document"}), encoding="utf-8",
    )
    profile = identity_service.load_identity_profile(identity_file, existing_install=True)
    assert profile["layouts"] == layout_builder_service.default_layouts_document()


# --- In-Game runtime hook: static-source assertions -------------------------

def test_apply_layout_overrides_is_wired_into_both_render_paths():
    js = _read("static/csrn-production-theme-runtime.js")
    assert "function applyLayoutOverrides(root, runtime)" in js
    # the lightweight "signature unchanged" patch path
    assert "applyLayoutOverrides(scoreLayout(), runtime);" in js
    # the full renderPackage() path
    assert "applyLayoutOverrides(scoreTarget, runtime);" in js


def test_apply_layout_overrides_no_ops_with_no_layouts_section():
    js = _read("static/csrn-production-theme-runtime.js")
    assert 'if (!layouts || typeof layouts !== "object") return; // no section -> untouched' in js


def test_apply_hook_never_hides_a_video_board_mode_host():
    # 2026-09-14 manual smoke test caught a real bug: hiding
    # sponsor_slot/spotlight_zone/video_zone via nativeVideoBoardHost() left
    # a blank hole where the whole scoreboard should be (sponsor/player/
    # highlight modes REPLACE the board's visible content in at least one
    # theme's markup, rather than overlaying on top of an always-present
    # board). That code path was removed rather than shipped broken --
    # confirm it stays removed, not silently reintroduced. (Layout Builder P1
    # A1 delivers the visibility effect upstream instead, by making
    # themeVideoModeFor() layout-aware; see tests/test_layout_builder_p1.py.)
    js = _read("static/csrn-production-theme-runtime.js")
    hook = js.split("function applyLayoutOverrides")[1].split("\nasync function renderSelected")[0]
    # These exact call/lookup patterns are what the removed code path used
    # (a prose mention of the bare function name in the explanatory comment
    # that replaced it doesn't match these stricter patterns).
    assert "setNodeVisibilityR0(nativeVideoBoardHost(" not in hook
    assert 'resolveLayoutOverrideR0(layouts, family, "sponsor_slot")' not in hook
    assert 'resolveLayoutOverrideR0(layouts, family, "spotlight_zone")' not in hook
    assert 'resolveLayoutOverrideR0(layouts, family, "video_zone")' not in hook
    # video_zone's data-module/[data-video-mode] contract was never at risk
    # in the first place -- nothing in this hook removes a node or attribute.
    assert "removeAttribute" not in hook


def test_ticker_is_the_only_element_using_the_px_zone_setter():
    js = _read("static/csrn-production-theme-runtime.js")
    hook = js.split("function applyLayoutOverrides")[1].split("\nasync function renderSelected")[0]
    # setNodeZonePxR0() writes position/left/top/width/height. That is exactly
    # what P0 live-verified crushes the bonded scorebug board, so score_box
    # must never go through it -- only the isolated ticker component does.
    # (score_box placement is a uniform transform: see test_layout_builder_p1.py.)
    assert hook.count("setNodeZonePxR0(") == 1
    assert "resolveIsolatedTickerComponentR0(root, alias)" in hook


def test_score_box_visibility_is_a_display_toggle_and_placement_never_resizes_the_box():
    js = _read("static/csrn-production-theme-runtime.js")
    hook = js.split("function applyLayoutOverrides")[1].split("\nasync function renderSelected")[0]
    scorebug_block = hook.split('"score_box"')[1].split("ticker: visibility")[0]
    assert "setNodeVisibilityR0(scorebugNode" in scorebug_block
    assert "setNodeZonePxR0(scorebugNode" not in scorebug_block
    assert "applyScoreBoxPlacementR1(scorebugNode, scorebugOverride)" in scorebug_block


# --- Pregame/Halftime read hook ---------------------------------------------

def test_layout_overrides_empty_when_no_layouts_document(monkeypatch):
    monkeypatch.setattr(pregame_presentation, "_layouts_document", lambda: None)
    assert pregame_presentation._layout_overrides("football", "pregame") == {}
    assert pregame_presentation._layout_overrides("football", "halftime") == {}


def test_layout_overrides_resolves_family_and_falls_back_to_default_key(monkeypatch):
    doc = {
        "active": "default",
        "presets": {
            "default": {
                "in_game": {},
                "pregame": {"default": {"sponsor_slot": {"visible": False}}},
                "halftime": {"basketball": {"spotlight_zone": {"visible": False}}},
            },
        },
    }
    monkeypatch.setattr(pregame_presentation, "_layouts_document", lambda: doc)
    assert pregame_presentation._layout_overrides("football", "pregame") == {
        "sponsor_slot": {"visible": False},
    }
    assert pregame_presentation._layout_overrides("basketball", "halftime") == {
        "spotlight_zone": {"visible": False},
    }
    # canadian_football shares the football base_family (Round 27) -- still
    # falls back to the "default" family key for pregame.
    assert pregame_presentation._layout_overrides("canadian_football", "pregame") == {
        "sponsor_slot": {"visible": False},
    }


def test_payload_layout_key_present_and_empty_with_no_overrides():
    # No app module wired up in a bare unit-test import -- _layouts_document()
    # must degrade to "no overrides" rather than raising.
    assert pregame_presentation._layout_overrides("football", "pregame") == {}


def test_overlay_template_layout_hooks_are_wired_and_default_to_untouched():
    html = _read("templates/pregame_universal_overlay.html")
    assert "function elementHidden(scene,element){" in html
    assert "applyLayoutOverrides(halftime?'halftime':'pregame');" in html
    assert "const sponsorsHidden=elementHidden(layoutScene,'sponsor_slot');" in html
    assert "const spotlightsHidden=elementHidden('halftime','spotlight_zone');" in html
    # absent data.layout entirely, layoutSceneOverrides() returns {} and
    # elementHidden() is false for everything -- untouched, matching the
    # "no override -> today's exact render" contract.
    assert "const doc=data?.layout?.[scene];" in html
    assert "return (doc&&typeof doc==='object')?doc:{};" in html
