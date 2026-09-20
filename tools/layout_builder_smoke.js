/*
 * Layout Builder manual smoke harness (paste into the browser console on
 * /overlay, or evaluate it through any browser-automation tool).
 *
 * WHY THIS EXISTS: csrn-production-theme-runtime.js has no JS test runner in
 * this repo, and the 2026-09-14 Layout Builder P0 smoke test caught two bugs
 * that no static test could. This file is that smoke test, made repeatable.
 * Run it against every theme after ANY change that touches
 * csrn-production-theme-runtime.js's layout hooks (applyLayoutOverrides,
 * themeVideoModeFor, layoutMaskedRuntimeR1, syncLayoutSuppressionR1).
 *
 * HOW: it wraps window.fetch for /api/runtime-state so a test can inject a
 * layouts document and force the sponsor / player / highlight triggers live,
 * exercising the real render, transition and patch paths. No server state is
 * touched. Do NOT use a real broadcast; run an isolated instance.
 *
 *   1. Select a theme (Data/production_template_state.json package_id).
 *   2. Open /overlay at 1920x1080 and paste this whole file.
 *   3. `__idle = __observe().mode; await __matrix(__idle)`
 *      idle mode is `clash` (Friday Night Stadium, 8-Bit), `broadcast`
 *      (Heritage Press) or `IDLE` (Collegiate: its idle board has no
 *      data-video-mode node).
 *   4. Every line must start with PASS. The matrix takes ~30s per theme.
 *
 * What a PASS means (see the layoutMaskedRuntimeR1 comment in the runtime):
 *   - hiding sponsor_slot / spotlight_zone / video_zone makes that mode
 *     UNAVAILABLE, so the theme falls through to the next mode or its idle
 *     board -- never a blank hole where the board belongs;
 *   - the legacy overlay node for the same content does not pop up over the
 *     themed board (verified on screen 2026-09-19: without the suppression
 *     class the legacy "PLAYER HIGHLIGHT" card leaks through);
 *   - un-hiding brings the mode back.
 */
if (!window.__origFetch) {
  window.__origFetch = window.fetch.bind(window);
  window.__smoke = { layouts: null, force: {} };
  window.fetch = async (u, o) => {
    const r = await window.__origFetch(u, o);
    if (String(u).includes('/api/runtime-state')) {
      const j = await r.clone().json();
      const s = window.__smoke;
      if (s.layouts) j.layouts = s.layouts;
      for (const [k, v] of Object.entries(s.force || {})) {
        j[k] = Object.assign({}, j[k] || {}, v, { visible: true });
      }
      return new Response(JSON.stringify(j), { status: 200, headers: { 'content-type': 'application/json' } });
    }
    return r;
  };
}

window.__FORCE = {
  sponsor:   { sponsor_spotlight: { sponsor_name: 'ACME Auto', lead_in: 'SPONSOR SPOTLIGHT', caption: 'Thanks for watching', media_type: 'image' } },
  player:    { player_graphic: { full_name: 'Caleb Lang', display_name: 'Caleb Lang', number: '7', position: 'RB', graphic_type: 'touchdown', eyebrow: 'TOUCHDOWN', team_name: 'Caledonia', play_detail: '70-yard run' } },
  highlight: { player_highlight: { full_name: 'Caleb Lang', display_name: 'Caleb Lang', number: '7', detail: '70-yard run', eyebrow: 'PLAYER HIGHLIGHT', media_type: 'video' } }
};

// A layouts document that hides the given in-game football elements.
window.__hide = (...els) => ({
  active: 'default',
  presets: { default: { in_game: { football: Object.fromEntries(els.map(e => [e, { visible: false }])) }, pregame: {}, halftime: {} } }
});

window.__wait = ms => new Promise(r => setTimeout(r, ms));

window.__legacy = id => {
  const n = document.getElementById(id);
  if (!n) return 'absent';
  const c = getComputedStyle(n);
  return { hiddenClass: n.classList.contains('hidden'), display: c.display, visibility: c.visibility, opacity: c.opacity };
};

window.__observe = () => {
  const h = document.documentElement.classList;
  const root = document.querySelector('#csrnProductionThemeLayout');
  const node = root && root.querySelector('[data-video-mode]');
  const st = window.CSRNProductionThemeBindingState;
  const measure = root && (root.querySelector('.bl-college-stage') || node);
  const b = measure && measure.getBoundingClientRect();
  return {
    mode: (st && st.active) ? (node ? node.dataset.videoMode : 'IDLE') : 'NONE',
    binding: st ? (st.error || 'ok') : 'unset',
    layoutHide: [...h].filter(c => c.startsWith('csrn-production-layout-hide')).map(c => c.replace('csrn-production-layout-hide-', '')),
    legacy: { player: __legacy('playerGraphic'), sponsor: __legacy('sponsorSpotlight'), highlight: __legacy('playerHighlight') },
    boardBox: b ? [Math.round(b.width), Math.round(b.height)] : null
  };
};

window.__shown = n => {
  if (!n) return false;
  const c = getComputedStyle(n);
  return !n.classList.contains('hidden') && c.display !== 'none' && c.visibility !== 'hidden' && Number(c.opacity) > 0.01;
};
window.__legacyShown = () => ({
  player: __shown(document.getElementById('playerGraphic')),
  sponsor: __shown(document.getElementById('sponsorSpotlight')),
  highlight: __shown(document.getElementById('playerHighlight'))
});

window.__matrix = async (idle) => {
  const EL = { sponsor: 'sponsor_slot', player: 'spotlight_zone', highlight: 'video_zone' };
  const rows = [];
  const W = 2000; // > the runtime's slowest poll (900ms) + a render
  const set = async (layout, forceKeys) => {
    __smoke.layouts = layout;
    __smoke.force = Object.assign({}, ...forceKeys.map(k => __FORCE[k]));
    await __wait(W);
    const o = __observe();
    o.legacyShown = __legacyShown();
    return o;
  };
  const anyLegacy = o => Object.values(o.legacyShown).some(Boolean);
  const check = (name, cond, o) => rows.push(
    (cond ? 'PASS ' : 'FAIL ') + name + '  [mode=' + o.mode + ' box=' + (o.boardBox || []).join('x') +
    ' legacyShown=' + Object.entries(o.legacyShown).filter(e => e[1]).map(e => e[0]).join(',') +
    ' hideCls=' + o.layoutHide.join(',') + ']'
  );

  const base = await set(null, []);
  rows.push('baseline mode=' + base.mode + ' box=' + base.boardBox.join('x'));
  const baseBox = base.boardBox;

  for (const m of ['sponsor', 'player', 'highlight']) {
    let o = await set(null, [m]);
    check(m + ' forced, no layout -> ' + m, o.mode === m && !anyLegacy(o), o);
    o = await set(__hide(EL[m]), [m]);
    check(m + ' forced, ' + EL[m] + ' HIDDEN -> idle, no legacy leak, board intact',
      o.mode === idle && !anyLegacy(o) && o.boardBox && o.boardBox[0] >= baseBox[0] * 0.9 && o.layoutHide.includes(m), o);
    o = await set(null, [m]);
    check(m + ' un-hidden -> ' + m + ' returns', o.mode === m, o);
  }

  let o = await set(__hide('video_zone'), ['highlight', 'sponsor']);
  check('highlight+sponsor forced, video_zone hidden -> falls through to sponsor', o.mode === 'sponsor', o);
  o = await set(__hide('sponsor_slot'), ['sponsor', 'player']);
  check('sponsor+player forced, sponsor_slot hidden -> falls through to player', o.mode === 'player', o);
  o = await set(__hide('sponsor_slot', 'spotlight_zone', 'video_zone'), ['sponsor', 'player', 'highlight']);
  check('ALL three forced, ALL three hidden -> idle, nothing leaks',
    o.mode === idle && !anyLegacy(o) && o.boardBox[0] >= baseBox[0] * 0.9, o);
  o = await set(null, []);
  check('everything cleared -> idle', o.mode === idle, o);
  return rows.join('\n');
};

/*
 * score_box PLACEMENT matrix (Layout Builder P1, A2). Same setup as above;
 *   `await __placementMatrix()`   -- every line must start with PASS.
 * The bonded scorebug node is the theme's whole board, so placement is a
 * uniform scale-to-fit (applyScoreBoxPlacementR1); zones the board would have
 * to shrink below SCORE_BOX_MIN_SCALE_R1 (0.5) are refused, not crushed.
 */
window.__place = (score_box) => ({
  active: 'default',
  presets: { default: { in_game: { football: { score_box } }, pregame: {}, halftime: {} } }
});
window.__sbNode = () => document.querySelector('#csrnProductionThemeLayout .bl-component[data-component="scorebug"]');
window.__sbState = () => {
  const n = __sbNode();
  if (!n) return null;
  const b = n.getBoundingClientRect();
  return { rect: [b.left, b.top, b.width, b.height].map(Math.round), marker: n.dataset.csrnLayoutScoreBox || null, tf: n.style.transform || '' };
};
window.__placementMatrix = async () => {
  const Z = window.CSRNBroadcastLayoutEngine.zones;
  const rows = [];
  const W = 2000;
  const set = async (doc, force) => {
    __smoke.layouts = doc;
    __smoke.force = force ? Object.assign({}, ...force.map(k => __FORCE[k])) : {};
    await __wait(W);
    return __sbState();
  };
  const inside = (r, z, tol = 2) => r[0] >= z.x - tol && r[1] >= z.y - tol && r[0] + r[2] <= z.x + z.w + tol && r[1] + r[3] <= z.y + z.h + tol;
  const check = (name, cond, o) => rows.push((cond ? 'PASS ' : 'FAIL ') + name + '  ' + JSON.stringify(o));

  const base = await set(null);
  rows.push('baseline ' + JSON.stringify(base));
  const bw = base.rect[2], bh = base.rect[3];

  let o = await set(__place({ zone: 'center' }));
  check('zone center -> placed, scaled to fit, inside the zone, aspect kept',
    o.marker === 'placed' && inside(o.rect, Z['center']) && o.rect[2] < bw && Math.abs(o.rect[2] / o.rect[3] - bw / bh) < 0.02, o);
  const centred = o;

  o = await set(__place({ zone: 'full-safe' }));
  check('zone full-safe -> placed, inside the zone', o.marker === 'placed' && inside(o.rect, Z['full-safe']), o);

  o = await set(__place({ rect: { x: 4, y: 40, w: 60, h: 56 } }));
  const R = { x: 0.04 * 1920, y: 0.40 * 1080, w: 0.60 * 1920, h: 0.56 * 1080 };
  check('rect (% of canvas) -> placed, inside the rect', o.marker === 'placed' && inside(o.rect, R), o);

  o = await set(__place({ zone: 'top-left' }));
  check('zone top-left (fit scale < 0.5) -> REFUSED, board untouched', o.marker === 'too-small' && o.tf === '' && o.rect.join() === base.rect.join(), o);
  o = await set(__place({ zone: 'bottom-center' }));
  check('zone bottom-center (fit scale < 0.5) -> REFUSED, board untouched', o.marker === 'too-small' && o.rect.join() === base.rect.join(), o);

  o = await set(__place({ visible: false, zone: 'center' }));
  check('visible:false still hides the board (placement does not resurrect it)', getComputedStyle(__sbNode()).display === 'none', o);

  for (const m of ['sponsor', 'player', 'highlight']) {
    o = await set(__place({ zone: 'center' }), [m]);
    const mode = document.querySelector('#csrnProductionThemeLayout [data-video-mode]');
    check('placed board survives a full rebuild into ' + m + ' mode',
      o.marker === 'placed' && inside(o.rect, Z['center']) && (!mode || mode.dataset.videoMode === m), Object.assign({ mode: mode && mode.dataset.videoMode }, o));
  }

  o = await set(__place({ zone: 'center' }));
  check('re-applying is idempotent (no drift across polls)', o.rect.join() === centred.rect.join(), o);
  o = await set(null);
  check('layout removed -> board back at native box, marker cleared', o.rect.join() === base.rect.join() && o.marker === null && o.tf === '', o);
  return rows.join('\n');
};

/*
 * ticker PLACEMENT matrix (Layout Builder P1, B0). `await __tickerMatrix()`.
 * Only Friday Night Stadium and Eight-Bit Gameday have an isolated ticker
 * component; on Heritage Press / Collegiate the expected result is the two
 * "no-op" PASS lines. A zone gives the bar its x + width; the height stays the
 * bar's own; removing the override restores the exact native inline box.
 */
window.__tk = () => {
  const n = document.querySelector('#csrnProductionThemeLayout .bl-component[data-component="ticker"]');
  if (!n) return null;
  const b = n.getBoundingClientRect();
  const host = n.querySelector('.bl-fns-top-ticker, .bl-8bit-top-ticker');
  return {
    rect: [b.left, b.top, b.width, b.height].map(Math.round),
    style: n.getAttribute('style'),
    prev: n.dataset.csrnLayoutTickerPrev || null,
    hostDisplay: host ? getComputedStyle(n.querySelector('.csrn-theme-ticker-viewport') || host).display : null
  };
};
window.__tickerMatrix = async () => {
  const Z = window.CSRNBroadcastLayoutEngine.zones;
  const rows = [];
  const W = 2000;
  const set = async (t) => {
    __smoke.layouts = t ? { active: 'default', presets: { default: { in_game: { football: { ticker: t } }, pregame: {}, halftime: {} } } } : null;
    await __wait(W);
    return __tk();
  };
  const check = (name, cond, o) => rows.push((cond ? 'PASS ' : 'FAIL ') + name + '  ' + JSON.stringify(o));
  const px = (o, prop) => parseFloat(o.style.match(new RegExp(prop + ': ([\d.]+)px'))[1]);
  const base = await set(null);
  rows.push('baseline ' + JSON.stringify(base));
  if (!base) {
    rows.push('PASS no isolated ticker component on this theme -> placement is a no-op (nothing to move)');
    const o = await set({ zone: 'top-right' });
    check('zone override on a theme without an isolated ticker changes nothing and does not throw', o === null, o);
    return rows.join('\n');
  }
  const nativeH = base.rect[3];
  for (const zn of ['bottom-center', 'top-right', 'top-full', 'center']) {
    const o = await set({ zone: zn });
    const z = Z[zn];
    check('zone ' + zn + ' -> x/width of the zone, native height, inside the zone',
      o.rect[0] === z.x && o.rect[2] === z.w && o.rect[3] === nativeH && o.rect[1] >= z.y && o.rect[1] + o.rect[3] <= z.y + z.h, o);
  }
  let o = await set({ zone: 'bottom-center' });
  check('bottom-* zone aligns the bar to the zone bottom', px(o, 'top') + px(o, 'height') === Z['bottom-center'].y + Z['bottom-center'].h, o);
  o = await set({ zone: 'top-right' });
  check('top-* zone aligns the bar to the zone top', o.rect[1] === Z['top-right'].y, o);
  o = await set({ rect: { x: 10, y: 50, w: 50, h: 10 } });
  check('explicit rect (% of canvas) is honoured', o.rect[0] === 192 && o.rect[2] === 960, o);
  o = await set({ visible: false });
  check('visible:false hides the ticker host', o.hostDisplay === 'none', o);
  o = await set({ visible: true, zone: 'top-right' });
  check('visible again + placement -> shown and placed', o.hostDisplay !== 'none' && o.rect[0] === Z['top-right'].x, o);
  o = await set(null);
  check('override removed -> ticker back at its exact native inline box, marker cleared',
    o.style === base.style && o.rect.join() === base.rect.join() && o.prev === null && o.hostDisplay !== 'none', o);
  return rows.join('\n');
};
