"""Video-mode support (CSRN_VIDEO_MODE_BUILD_PROMPT.md), shipped concretely
on Collegiate Tech this round: a per-theme, operator-toggleable transparent
"video window" so a camera feed composited in OBS behind CSRN's graphic
shows through cleanly. CSRN never ingests video -- see app.py's DEFAULT_
STATE comment for the full boundary statement.

Source assertions follow this repo's static-content convention. An opt-in
Chromium check additionally exercises the real engine markup and computed
styles: set CSRN_PLAYWRIGHT_MODULE to an installed Playwright module path
(and CSRN_BROWSER_TEST_NODE if Node is not on PATH). No browser dependency
is added to the production application.
"""

from __future__ import annotations

from pathlib import Path
import os
import shutil
import subprocess

import pytest

import app
from game_operations_service import GameOperationsService

ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


ENGINE_JS = read("static/csrn-broadcast-layout-engine.js")
ENGINE_CSS = read("static/csrn-broadcast-layout-engine.css")
RUNTIME_JS = read("static/csrn-production-theme-runtime.js")
INDEX_HTML = read("templates/index.html")


def _fn(source: str, signature: str) -> str:
    start = source.index(signature)
    rest = source[start:]
    for marker in ("\n  function ", "\nfunction ", "\n  const ", "\n}\n\n"):
        idx = rest.find(marker, 1)
        if idx != -1:
            return rest[: idx + 1]
    return rest


# --- backend: the three raw state fields -----------------------------------


def test_default_state_carries_the_three_video_mode_fields_off() -> None:
    # False/off is the existing byte-identical default for every current
    # broadcast -- this feature must never change behavior for a game that
    # never touches it.
    assert app.DEFAULT_STATE["video_mode"] is False
    assert app.DEFAULT_STATE["sidebars_hidden"] is False
    assert app.DEFAULT_STATE["video_calibration_guide"] is False


def test_video_mode_fields_are_live_settable() -> None:
    # Confirmed decision: live, mid-broadcast toggle (matches every other
    # broadcast-level display setting -- scorebug_visible, ticker_visible,
    # visual_mode -- none of which are pregame-only in this codebase).
    for field in ("video_mode", "sidebars_hidden", "video_calibration_guide"):
        assert field in GameOperationsService.ALLOWED_SET_FIELDS


# --- runtime: raw state -> normalized render-state mapping ------------------


def test_runtime_maps_raw_fields_onto_distinctly_named_render_state() -> None:
    # Named videoWindowActive/etc, NOT videoMode -- this file's own
    # polledVideoMode (highlight/sponsor/player/clash per-component
    # dispatch) already owns that name; reusing it for the new boolean
    # would be a second, confusing meaning for the same identifier.
    assert "base.videoWindowActive = Boolean(source.video_mode);" in RUNTIME_JS
    assert "base.sidebarsHidden = Boolean(source.sidebars_hidden);" in RUNTIME_JS
    assert "base.videoCalibrationGuide = Boolean(source.video_calibration_guide);" in RUNTIME_JS


def test_render_signature_includes_the_new_fields_to_force_a_full_rerender() -> None:
    # These fields change the rendered DOM structure itself (opaque clash
    # <-> transparent window, 3-column <-> full-width grid). The "signature
    # unchanged" fast path skips mergeRuntimeState()/renderPackage() entirely
    # and only re-runs a handful of lightweight patch functions -- a
    # signature that didn't include these would silently never apply the
    # toggle until some UNRELATED field also happened to change.
    sig_start = RUNTIME_JS.index("const signature = JSON.stringify([")
    sig_body = RUNTIME_JS[sig_start : RUNTIME_JS.index("]);", sig_start)]
    assert "runtime.video_mode" in sig_body
    assert "runtime.sidebars_hidden" in sig_body
    assert "runtime.video_calibration_guide" in sig_body


# --- frozen engine: the actual transparency / sidebar-hide / guide render --


def test_clash_fallback_becomes_the_video_window_only_when_active() -> None:
    body = _fn(ENGINE_JS, "function collegiateVideoBoardContent(state, mode) {")
    assert "if (state.videoWindowActive) {" in body
    assert "return collegiateVideoWindow(state);" in body
    assert "return collegiateClashStage(state);" in body
    # Order matters: an active highlight/sponsor/player graphic must still
    # win over the video window (checked earlier in the same function),
    # not get swallowed by it.
    assert body.index('if (mode === "player")') < body.index("if (state.videoWindowActive)")


def test_video_window_helper_supports_real_and_calibration_guide_modes() -> None:
    body = _fn(ENGINE_JS, "function collegiateVideoWindow(state) {")
    assert "bl-college-video-window" in body
    assert "videoCalibrationGuide" in body
    assert "bl-college-video-window-guide" in body
    assert "rect-label" in body


def test_stage_strips_its_own_opaque_background_when_the_window_is_showing() -> None:
    body = _fn(ENGINE_JS, "function collegiateStage(state, videoMode, sport = \"football\") {")
    assert "bl-college-stage-video-active" in body
    assert '!["highlight", "sponsor", "player"].includes(videoMode)' in body


def test_sidebars_hidden_collapses_rails_via_a_shared_helper_for_both_sports() -> None:
    body = _fn(ENGINE_JS, "function collegiateMainDisplay(state, sport, videoMode) {")
    assert "Boolean(state.sidebarsHidden)" in body
    assert "bl-college-main-display-full" in body
    # When hidden, the rail calls are genuinely omitted (not just visually
    # hidden by CSS) -- confirms the "does the board reflow" investigation
    # finding was actually acted on, not left as a CSS-only cosmetic fix.
    assert body.count("collegiateTeamPanel(") == 2

    assert "collegiateMainDisplay(state, \"football\", videoMode)" in ENGINE_JS
    assert "collegiateMainDisplay(state, sport, videoMode)" in ENGINE_JS


def test_engine_css_defines_the_new_selectors() -> None:
    assert ".bl-college-main-display-full{grid-template-columns:minmax(0,1fr)}" in ENGINE_CSS
    assert ".bl-college-stage-video-active{" in ENGINE_CSS
    assert ".bl-college-stage-video-active .bl-college-stage-field,.bl-college-stage-video-active::after{display:none}" in ENGINE_CSS
    assert ".bl-college-video-window{" in ENGINE_CSS
    assert ".bl-college-video-window-guide{" in ENGINE_CSS
    assert ".bl-college-video-window-label{" in ENGINE_CSS


def test_top_and_bottom_scorebug_bars_are_never_touched_by_either_toggle() -> None:
    # Spec requirement: "Top and bottom scorebug overlays are unaffected --
    # always rendered, regardless of video_mode or the sidebar toggle."
    # collegiateScoreClockRow/collegiateBaseballScoreClockRow (top) and
    # collegiateField/collegiateBaseballLineScoreBank (bottom) must not
    # reference either new field at all.
    for fn_signature in (
        "function collegiateScoreClockRow(state) {",
        "function collegiateBaseballScoreClockRow(state) {",
        "function collegiateField(state) {",
    ):
        body = _fn(ENGINE_JS, fn_signature)
        assert "videoWindowActive" not in body
        assert "sidebarsHidden" not in body


# --- unpinned runtime: live calibration-guide rect measurement --------------


def test_calibration_guide_measurement_lives_in_the_unpinned_runtime_not_the_frozen_engine() -> None:
    # A live DOM measurement (getBoundingClientRect) belongs in the mutable
    # runtime, not the SHA-256-pinned engine -- keeps the frozen file's own
    # diff to markup/classes only.
    assert "function patchVideoWindowGuide(root, runtime)" in RUNTIME_JS
    assert "getBoundingClientRect()" in _fn(RUNTIME_JS, "function patchVideoWindowGuide(root, runtime) {")
    assert "patchVideoWindowGuide(scoreLayout(), runtime);" in RUNTIME_JS
    assert "patchVideoWindowGuide(scoreTarget, runtime);" in RUNTIME_JS


def test_hole_disables_and_restores_both_wrapper_backdrop_filter_properties() -> None:
    body = _fn(RUNTIME_JS, "function patchVideoWindowHole(root) {")
    for prop in ("backdrop-filter", "-webkit-backdrop-filter"):
        assert f'layer.style.setProperty("{prop}", "none");' in body
        assert f'layer.style.removeProperty("{prop}");' in body
    assert 'layer.matches(".bl-collegiate-tech")' in body
    assert "patchVideoWindowHole(scoreLayout());" in RUNTIME_JS
    assert "patchVideoWindowHole(scoreTarget);" in RUNTIME_JS


def test_video_hole_computed_styles_and_restoration_in_chromium() -> None:
    module = os.environ.get("CSRN_PLAYWRIGHT_MODULE")
    if not module:
        pytest.skip("Set CSRN_PLAYWRIGHT_MODULE to run computed-style browser coverage")
    node = os.environ.get("CSRN_BROWSER_TEST_NODE") or shutil.which("node")
    assert node, "Chromium coverage requested but Node is unavailable"
    script = r'''
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require(process.env.CSRN_PLAYWRIGHT_MODULE);
(async () => {
  const browser = await chromium.launch({headless:true});
  try {
    const page = await browser.newPage({viewport:{width:1920,height:1080}});
    await page.setContent('<style>html,body{margin:0;background:transparent}</style><div id="layout"></div>');
    const read = name => fs.readFileSync(path.join(process.cwd(),'static',name),'utf8');
    for (const name of ['csrn-broadcast-layout-engine.css','csrn-production-theme-runtime.css','csrn-collegiate-neon.css']) {
      await page.addStyleTag({content:read(name)});
    }
    await page.addScriptTag({content:read('csrn-broadcast-layout-engine.js')});
    const source = read('csrn-production-theme-runtime.js').replace(/\r\n/g,'\n');
    const start = source.indexOf('const VIDEO_WINDOW_MASK_PROPERTIES');
    const end = source.indexOf('\n}\n',start)+3;
    assert(start >= 0 && end > start);
    await page.addScriptTag({content:source.slice(start,end)});
    const cases = await page.evaluate(() => {
      const check = (condition,message) => {if(!condition) throw Error(message)};
      const root = document.querySelector('#layout');
      const engine = window.CSRNBroadcastLayoutEngine;
      let count = 0;
      for (const theme of ['collegiate_traditional','digital_neon']) {
        for (const sport of ['football','basketball','baseball','softball']) {
          for (const hidden of [false,true]) {
            const state={videoWindowActive:true,sidebarsHidden:hidden};
            const render = (target,value,mode='clash') => engine.renderPackage(target,theme,sport,value,{activeComponents:['scorebug'],videoMode:mode});
            render(root,state);
            const card=root.querySelector('.bl-collegiate-tech');
            const normalBlur=getComputedStyle(card).backdropFilter;
            const nodes=[...root.querySelectorAll('*')];
            const layers=nodes.map(node=>getComputedStyle(node).zIndex);
            root.style.transform='scale(.75)';
            patchVideoWindowHole(root);
            const win=root.querySelector('.bl-college-video-window');
            const stage=win.parentElement;
            const main=stage.parentElement;
            check(main.matches('.bl-college-main-display') && main.parentElement===card,'Actual ancestor chain changed');
            check(getComputedStyle(card).backdropFilter==='none','Wrapper blur remains over the window');
            check(card.style.getPropertyValue('backdrop-filter')==='none','Missing inline override');
            check(getComputedStyle(stage).backgroundColor==='rgba(0, 0, 0, 0)' && getComputedStyle(stage).backgroundImage==='none','Stage still paints a background');
            check(getComputedStyle(stage.querySelector('.bl-college-stage-field')).display==='none','Field art still covers the window');
            for(const layer of [card,main]) {
              check(getComputedStyle(layer).maskImage!=='none','Missing ancestor mask');
              const sizes=layer.style.maskSize.split(',')[1].trim().split(' ').map(parseFloat);
              const rect=win.getBoundingClientRect();
              check(Math.abs(sizes[0]-rect.width/.75)<.1 && Math.abs(sizes[1]-rect.height/.75)<.1,'Mask does not follow scaled geometry');
            }
            check(nodes.every((node,i)=>node===root.querySelectorAll('*')[i] && getComputedStyle(node).zIndex===layers[i]),'Patch changed DOM or stacking order');
            for(const rail of root.querySelectorAll('.bl-college-team')) {
              check(!rail.contains(win),'Blur panel contains the window');
              check(getComputedStyle(rail).backdropFilter.includes('blur('),'Rail lost its glass blur');
            }
            // Exercise cleanup on the SAME wrapper, so a fresh render cannot
            // hide a stale inline blur override or mask.
            win.classList.add('bl-college-video-window-guide');
            patchVideoWindowHole(root);
            const restored=()=> {
              check(card.style.getPropertyValue('backdrop-filter')==='' && card.style.getPropertyValue('-webkit-backdrop-filter')==='','Blur override was not removed');
              check(getComputedStyle(card).backdropFilter===normalBlur,'Theme blur was not restored');
              for(const layer of [card,main]) check(getComputedStyle(layer).maskImage==='none','Stale mask covers the guide/graphic');
            };
            restored();
            win.classList.remove('bl-college-video-window-guide');
            patchVideoWindowHole(root);
            for(const mode of ['player','sponsor','highlight','off']) {
              const temp=document.createElement('div');
              render(temp,{...state,videoWindowActive:mode!=='off'},mode==='off'?'clash':mode);
              main.querySelector('.bl-college-stage').replaceWith(temp.querySelector('.bl-college-stage'));
              patchVideoWindowHole(root);
              check(!root.querySelector('.bl-college-video-window'),'Graphic must replace the window');
              restored();
              // Put a real window back on the same card before the next mode.
              render(temp,state);
              main.querySelector('.bl-college-stage').replaceWith(temp.querySelector('.bl-college-stage'));
              patchVideoWindowHole(root);
            }
            root.style.transform='';
            count++;
          }
        }
      }
      return count;
    });
    assert.equal(cases,16);
    console.log(`Chromium ${browser.version()}: ${cases} theme/sport/sidebar combinations and restoration transitions passed`);
  } finally {await browser.close()}
})().catch(error=>{console.error(error);process.exit(1)});
'''
    result = subprocess.run(
        [node, "-e", script], cwd=ROOT, capture_output=True, text=True, timeout=90,
    )
    assert result.returncode == 0, result.stdout + result.stderr


# --- operator UI ------------------------------------------------------------


def test_operator_ui_exposes_all_three_toggles() -> None:
    # Video Mode goes through Program Visual's endpoint (one switch, see
    # tests/test_camera_video_mode_link.py).
    assert "onclick=\"changeProgramVisual(currentState.video_mode?'graphic':'camera')\"" in INDEX_HTML
    assert "onclick=\"setState('sidebars_hidden',!Boolean(currentState.sidebars_hidden))\"" in INDEX_HTML
    assert "onclick=\"setState('video_calibration_guide',!Boolean(currentState.video_calibration_guide))\"" in INDEX_HTML


def test_toggle_labels_update_ahead_of_the_diamond_sport_branch() -> None:
    # Video mode is cross-sport by design -- its label-sync code must run
    # before render()'s "return" for a baseball/softball broadcast, or a
    # diamond broadcast's toggle buttons would silently go stale (the way
    # the pre-existing scorebug/halftime toggles already do, a P5-era gap
    # this change deliberately does not repeat).
    render_start = INDEX_HTML.index("function render() {")
    label_sync_at = INDEX_HTML.index("videoModeToggleState", render_start)
    branch_at = INDEX_HTML.index("isDiamondSport", render_start)
    assert render_start < label_sync_at < branch_at
