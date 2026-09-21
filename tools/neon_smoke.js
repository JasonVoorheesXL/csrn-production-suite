/*
 * Neon manual smoke harness (paste into the browser console on /overlay, or
 * evaluate it through a browser-automation tool). This repo has no JS runner, so
 * this is the repeatable form of the checks that were done by hand.
 *
 * Setup: an isolated instance with production_template_state package_id
 * "digital_neon" (selectable in the picker since the Neon redesign), /overlay at 1920x1080.
 *
 *   __nx = {home:['#4B2E83','#FFFFFF'], visitor:['#00693E','#FFFFFF'],
 *           possession:'home', down:'4th', distance:'Goal', video:true}
 *   await __wait(3000); __neonProbe()
 *
 * __nx injects into the polled /api/runtime-state (the same path the runtime uses
 * for live data), so possession / down / colours change with no reload.
 *
 * What the probe must show:
 *   - package "digital_neon", root classes "package-collegiate package-collegiate-neon"
 *   - --visitor-neon / --home-neon = the electrified school colours for THIS game
 *   - data-component="scorebug" on the bonded board (Layout Builder contract)
 *   - pill: 999px radius, in the possession team's neon (--poss follows data-possession)
 *   - video on: opaqueBehindWindow is [] (the OBS video is not dimmed) and the stage
 *     still has its gradient outline
 * For the Layout Builder matrices on Neon use tools/layout_builder_smoke.js
 * (`__matrix('IDLE')`, `__placementMatrix()`, `__tickerMatrix()`).
 */
if (!window.__neonOrigFetch) {
  window.__neonOrigFetch = window.fetch.bind(window);
  window.__nx = {};
  window.fetch = async (u, o) => {
    const r = await window.__neonOrigFetch(u, o);
    if (!String(u).includes('/api/runtime-state')) return r;
    const j = await r.clone().json();
    const n = window.__nx;
    if (n.home) j.home_identity = Object.assign({}, j.home_identity, { primary_color: n.home[0], secondary_color: n.home[1] });
    if (n.visitor) j.visitor_identity = Object.assign({}, j.visitor_identity, { primary_color: n.visitor[0], secondary_color: n.visitor[1] });
    if (n.possession) {
      j.possession = n.possession;
      if (j.canonical_field_state) j.canonical_field_state = Object.assign({}, j.canonical_field_state, { possession: n.possession, offense: n.possession });
    }
    if (n.down) {
      j.down = n.down; j.distance = n.distance;
      if (j.canonical_field_state) j.canonical_field_state = Object.assign({}, j.canonical_field_state, { down: n.down, distance: n.distance, distance_display: n.distance });
    }
    if (n.video !== undefined) { j.video_mode = n.video; j.sidebars_hidden = Boolean(n.sidebars); }
    return new Response(JSON.stringify(j), { status: 200, headers: { 'content-type': 'application/json' } });
  };
}
window.__wait = (ms) => new Promise((r) => setTimeout(r, ms));

window.__neonProbe = () => {
  const layout = document.querySelector('#csrnProductionThemeLayout');
  const cs = layout && getComputedStyle(layout);
  const field = document.querySelector('.bl-college-field');
  const pill = document.querySelectorAll('.bl-college-field-meta span')[1];
  const stage = document.querySelector('.bl-college-stage');
  const windowNode = document.querySelector('.bl-college-video-window');
  const opaqueBehindWindow = [];
  for (let e = windowNode; e && e !== document.body; e = e.parentElement) {
    const c = getComputedStyle(e);
    if (c.backgroundColor !== 'rgba(0, 0, 0, 0)' || c.backgroundImage !== 'none') opaqueBehindWindow.push(e.className);
  }
  return {
    package: layout && layout.dataset.package,
    rootClass: layout && layout.className,
    visitorNeon: cs && cs.getPropertyValue('--visitor-neon').trim(),
    homeNeon: cs && cs.getPropertyValue('--home-neon').trim(),
    dataComponent: (document.querySelector('.bl-component[data-component="scorebug"]') || {}).dataset && 'scorebug',
    possession: field && field.dataset.possession,
    poss: field && getComputedStyle(field).getPropertyValue('--poss').trim(),
    down: (document.querySelector('[data-bind="game.downDistance"]') || {}).textContent,
    pillRadius: pill && getComputedStyle(pill).borderRadius,
    videoOn: Boolean(stage && stage.classList.contains('bl-college-stage-video-active')),
    stageRing: stage && getComputedStyle(stage, '::before').content,
    opaqueBehindWindow
  };
};
