"""Paper-cutout play reels: draw a script (reel_story.script) frame by frame
in headless Chromium and encode the frames into a vertical MP4 (1080 x 1920).

The look is our own construction-paper cutout style: flat paper shapes with
white cut edges and soft shadows, a felt field, figures in team colours that
move "on twos" (12 drawings a second) with a slight boil, like stop-motion.
Players are generic figures identified only by team colours and numbers.
"""
from __future__ import annotations

import io
import json
from fractions import Fraction
from typing import Any, Callable, Mapping

WIDTH = 1080
HEIGHT = 1920
DRAW_FPS = 12      # new drawing 12 times a second: the stop-motion feel
VIDEO_FPS = 24     # each drawing held for two video frames

PAGE = r"""<!doctype html>
<html><head><meta charset="utf-8">
<style>
  @font-face { font-family: 'Bangers'; src: url('__FONT__') format('woff2'); }
  html, body { margin: 0; padding: 0; background: #23301f; }
  svg { display: block; }
  .big { font-family: 'Bangers', Impact, sans-serif; letter-spacing: 1px; }
  .plain { font-family: 'Segoe UI', Arial, sans-serif; font-weight: 800; }
</style></head>
<body>
<svg id="stage" width="1080" height="1920" viewBox="0 0 1080 1920" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <filter id="paper" x="-20%" y="-20%" width="140%" height="140%">
      <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" seed="4" result="grain"/>
      <feColorMatrix in="grain" type="saturate" values="0" result="mono"/>
      <feComponentTransfer in="mono" result="soft"><feFuncA type="table" tableValues="0 0.10"/></feComponentTransfer>
      <feComposite in="soft" in2="SourceGraphic" operator="in" result="speck"/>
      <feMerge><feMergeNode in="SourceGraphic"/><feMergeNode in="speck"/></feMerge>
    </filter>
    <filter id="cut" x="-30%" y="-30%" width="160%" height="160%">
      <feMorphology in="SourceAlpha" operator="dilate" radius="4" result="grow"/>
      <feFlood flood-color="#fffdf4"/><feComposite in2="grow" operator="in" result="edge"/>
      <feGaussianBlur in="SourceAlpha" stdDeviation="5" result="blur"/>
      <feOffset in="blur" dx="5" dy="7" result="drop"/>
      <feComponentTransfer in="drop" result="shadow"><feFuncA type="linear" slope="0.45"/></feComponentTransfer>
      <feMerge><feMergeNode in="shadow"/><feMergeNode in="edge"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <pattern id="felt" width="140" height="140" patternUnits="userSpaceOnUse">
      <rect width="140" height="140" fill="#3f8a3a"/>
      <path d="M0 20 Q35 10 70 22 T140 18" stroke="#4c9a45" stroke-width="10" fill="none" opacity=".5"/>
      <path d="M0 90 Q40 80 80 95 T140 88" stroke="#357a31" stroke-width="12" fill="none" opacity=".5"/>
    </pattern>
    <clipPath id="fieldClip"><rect x="0" y="560" width="1080" height="800"/></clipPath>
  </defs>
  <rect width="1080" height="1920" fill="#2a3a26" filter="url(#paper)"/>
  <g id="field" clip-path="url(#fieldClip)"></g>
  <g id="actors" clip-path="url(#fieldClip)"></g>
  <g id="overlay"></g>
  <g id="title"></g>
  <g id="caption"></g>
  <g id="footer"></g>
</svg>
<script>
const S = __SCRIPT__;
const NS = 'http://www.w3.org/2000/svg';
const FIELD_TOP = 560, FIELD_H = 800, PX = 64;   // pixels per yard
const $ = (tag, attrs, parent) => { const el = document.createElementNS(NS, tag); for (const k in attrs) el.setAttribute(k, attrs[k]); if (parent) parent.appendChild(el); return el; };
let seed = 7; const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
function noise(i, t) { const x = Math.sin(i * 12.9898 + Math.floor(t * 12) * 78.233) * 43758.5453; return x - Math.floor(x); }
function torn(x, y, w, h, jag) { const pts = []; const step = 26; for (let i = 0; i <= w; i += step) pts.push([x + i, y + (rnd() - .5) * jag]); for (let i = 0; i <= h; i += step) pts.push([x + w + (rnd() - .5) * jag, y + i]); for (let i = w; i >= 0; i -= step) pts.push([x + i, y + h + (rnd() - .5) * jag]); for (let i = h; i >= 0; i -= step) pts.push([x + (rnd() - .5) * jag, y + i]); return pts.map(p => p.join(',')).join(' '); }
function text(parent, x, y, str, size, fill, cls, anchor) { const t = $('text', {x, y, 'font-size': size, fill, class: cls || 'big', 'text-anchor': anchor || 'middle'}, parent); t.textContent = str; return t; }
function hex(c, d) { return /^#[0-9a-f]{6}$/i.test(c || '') ? c : d; }
function lum(c) { const n = parseInt(c.slice(1), 16); return (0.299 * (n >> 16) + 0.587 * ((n >> 8) & 255) + 0.114 * (n & 255)) / 255; }
function near(a, b) { const x = parseInt(a.slice(1), 16), y = parseInt(b.slice(1), 16); return Math.abs((x >> 16) - (y >> 16)) + Math.abs(((x >> 8) & 255) - ((y >> 8) & 255)) + Math.abs((x & 255) - (y & 255)) < 120; }

// -- colours: the two teams must read apart on the felt -------------------------
const OFF = hex(S.offense.primary, '#c8102e'), OFF2 = hex(S.offense.secondary, '#ffffff');
let DEF = hex(S.defense.primary, '#1d3f8f'), DEF2 = hex(S.defense.secondary, '#ffffff');
if (near(OFF, DEF)) { DEF = '#f4f1e8'; DEF2 = hex(S.defense.primary, '#1d3f8f'); }
const ink = c => lum(c) > 0.6 ? '#1b1b1b' : '#ffffff';

// -- timing ---------------------------------------------------------------------
const G = S.geometry, kind = S.kind;
const dist = Math.abs((G.end ?? 0) - (G.start ?? 0));
const INTRO = 2.2, SNAP = 0.5;
const AIR = (kind === 'pass' || kind === 'interception') ? 0.9 + Math.abs((G.catch ?? G.start) - G.los) * 0.03 : (kind.endsWith('_return') ? 1.6 : 0);
const RUN = kind === 'field_goal' ? 1.8 : Math.min(6.5, Math.max(1.6, 1.0 + dist * 0.07));
const FINISH = 2.6, END = 2.6;
const T_SNAP = INTRO, T_AIR = T_SNAP + SNAP, T_RUN = T_AIR + AIR, T_FIN = T_RUN + RUN, T_END = T_FIN + FINISH;
window.REEL_DURATION = T_END + END;

// -- the field --------------------------------------------------------------------
const field = document.getElementById('field');
const fieldWorld = $('g', {}, field);
$('rect', {x: 0, y: FIELD_TOP, width: 1080, height: FIELD_H, fill: 'url(#felt)'}, field).parentNode.insertBefore(field.lastChild, fieldWorld);
const X = yd => yd * PX;   // world x before the camera shift
$('rect', {x: X(-10), y: FIELD_TOP, width: X(10), height: FIELD_H, fill: OFF, opacity: .85, filter: 'url(#paper)'}, fieldWorld);
$('rect', {x: X(100), y: FIELD_TOP, width: X(10), height: FIELD_H, fill: DEF, opacity: .85, filter: 'url(#paper)'}, fieldWorld);
text(fieldWorld, X(105), FIELD_TOP + FIELD_H / 2, (S.defense.name || '').toUpperCase().slice(0, 14), 64, ink(DEF)).setAttribute('transform', `rotate(-90 ${X(105)} ${FIELD_TOP + FIELD_H / 2})`);
for (let yd = 0; yd <= 100; yd += 5) {
  const w = yd % 10 === 0 ? 12 : 7, wob = (rnd() - .5) * 3;
  $('rect', {x: X(yd) - w / 2, y: FIELD_TOP - 10, width: w, height: FIELD_H + 20, fill: '#fbf7e8', transform: `rotate(${wob} ${X(yd)} ${FIELD_TOP + FIELD_H / 2})`, filter: 'url(#paper)'}, fieldWorld);
  if (yd % 10 === 0 && yd > 0 && yd < 100) { const n = String(yd <= 50 ? yd : 100 - yd); text(fieldWorld, X(yd), FIELD_TOP + 120, n, 72, '#fbf7e8'); text(fieldWorld, X(yd), FIELD_TOP + FIELD_H - 50, n, 72, '#fbf7e8'); }
}
// goal posts at the back of the end zone
const posts = $('g', {filter: 'url(#cut)'}, fieldWorld);
$('rect', {x: X(110) - 9, y: FIELD_TOP + 300, width: 18, height: 360, fill: '#f6c915'}, posts);
$('rect', {x: X(110) - 60, y: FIELD_TOP + 300, width: 120, height: 16, fill: '#f6c915'}, posts);
$('rect', {x: X(110) - 60, y: FIELD_TOP + 60, width: 14, height: 250, fill: '#f6c915'}, posts);
$('rect', {x: X(110) + 46, y: FIELD_TOP + 60, width: 14, height: 250, fill: '#f6c915'}, posts);

// -- paper figures ----------------------------------------------------------------
const actors = document.getElementById('actors');
function figure(color, trim, number, facing) {
  const g = $('g', {filter: 'url(#cut)'}, actors);
  const body = $('g', {}, g);            // flips with the way the player faces
  const legA = $('g', {}, body), legB = $('g', {}, body);
  for (const leg of [legA, legB]) { $('rect', {x: -13, y: -46, width: 26, height: 70, rx: 9, fill: trim}, leg); $('rect', {x: -14, y: 18, width: 34, height: 16, rx: 7, fill: '#1c1c1c'}, leg); }
  legA.setAttribute('data-x', -12); legB.setAttribute('data-x', 12);
  $('path', {d: 'M -44 -120 Q -46 -138 -24 -142 L 24 -142 Q 46 -138 44 -120 L 34 -40 L -34 -40 Z', fill: color}, body);
  $('rect', {x: -36, y: -58, width: 72, height: 20, rx: 6, fill: trim}, body);
  const arm = $('rect', {x: -10, y: -132, width: 22, height: 66, rx: 10, fill: color}, body);
  $('circle', {cx: 2, cy: -176, r: 42, fill: color}, body);
  $('rect', {x: -8, y: -218, width: 14, height: 80, fill: trim, opacity: .9}, body);
  $('path', {d: 'M 20 -184 L 52 -184 M 20 -168 L 52 -168 M 46 -194 L 46 -158', stroke: '#9aa0a6', 'stroke-width': 6, 'stroke-linecap': 'round', fill: 'none'}, body);
  $('rect', {x: 14, y: -192, width: 22, height: 16, rx: 5, fill: '#1c1c1c'}, body);
  const num = text(g, 0, -78, number || '', 46, ink(color), 'plain');   // outside the flip: never mirrored
  return {g, body, legA, legB, arm, num, facing};
}
function ballShape(parent) { const g = $('g', {filter: 'url(#cut)'}, parent); $('ellipse', {cx: 0, cy: 0, rx: 22, ry: 13, fill: '#7a3e1a'}, g); $('path', {d: 'M -8 0 L 8 0 M -4 -4 L -4 4 M 0 -4 L 0 4 M 4 -4 L 4 4', stroke: '#fff', 'stroke-width': 2.5}, g); return g; }

const lane = i => FIELD_TOP + 280 + i * 108;   // the figure's feet
const offense = [], defense = [];
const heroTeamColor = OFF;
const hero = figure(OFF, OFF2, S.hero.number, 1);
let passer = null, kicker = null;
for (let i = 0; i < 4; i++) offense.push(figure(OFF, OFF2, String([52, 66, 71, 64][i]), 1));
for (let i = 0; i < 7; i++) defense.push(figure(DEF, DEF2, String([44, 9, 21, 55, 3, 24, 6][i]), -1));
if (kind === 'pass') passer = figure(OFF, OFF2, S.passer.number || '7', 1);
if (kind === 'interception') passer = figure(DEF, DEF2, '7', -1);
if (kind.endsWith('_return')) kicker = figure(DEF, DEF2, '18', -1);
if (kind === 'field_goal') { passer = figure(OFF, OFF2, '12', 1); }
const ball = ballShape(actors);

// -- motion -----------------------------------------------------------------------
const ease = p => p < 0 ? 0 : p > 1 ? 1 : p * p * (3 - 2 * p);
const clamp01 = p => Math.max(0, Math.min(1, p));
function heroPath(t) {
  if (kind === 'field_goal') return {x: G.start + 1, y: lane(2.2)};
  const startX = kind === 'run' ? G.los - 5 : (kind === 'pass' ? G.los - 1 : G.catch);
  if (t < T_RUN) {
    if (kind === 'pass') { const p = ease((t - T_AIR + 0.4) / (AIR + 0.4)); return {x: startX + (G.catch - startX) * p, y: lane(.4) + 60 * p}; }
    if (kind === 'run') { const p = clamp01((t - T_AIR) / 0.3); return {x: startX + 2 * p, y: lane(2.3)}; }
    return {x: startX - 1, y: lane(2) + Math.sin(t * 3) * 6};
  }
  const p = ease((t - T_RUN) / RUN), from = kind === 'run' ? startX + 2 : G.catch;
  const goal = S.td ? G.end + 4 : G.end;   // a touchdown carries into the end zone
  const x = from + (goal - from) * p;
  return {x, y: lane(2) + Math.sin(p * Math.PI * 3) * 70 * (1 - p * .4)};
}
function place(f, x, y, rot, t, running, idx) {
  const boil = (noise(idx, t) - .5) * 2.4;
  const sx = X(x) - camera;
  f.g.setAttribute('transform', `translate(${sx.toFixed(1)} ${y.toFixed(1)}) rotate(${(rot + boil).toFixed(2)})`);
  f.body.setAttribute('transform', `scale(${f.facing} 1)`);
  const stride = running ? (Math.floor(t * 12) % 2 ? 1 : -1) : 0;
  f.legA.setAttribute('transform', `translate(-12 0) rotate(${24 * stride} 0 -46)`);
  f.legB.setAttribute('transform', `translate(12 0) rotate(${-24 * stride} 0 -46)`);
  f.arm.setAttribute('transform', `rotate(${running ? -35 * stride - 25 : -10} 1 -126)`);
}
let camera = 0;
function cameraFor(ballX) { const target = X(ballX) - 1080 * (kind === 'interception' || kind.endsWith('_return') ? .42 : .38); return Math.max(X(-10), Math.min(X(112) - 1080, target)); }

// -- the paper overlay: title, captions, footer, big words ----------------------------
const titleG = document.getElementById('title');
$('polygon', {points: torn(40, 40, 1000, 470, 18), fill: '#f2e6c9', filter: 'url(#cut)'}, titleG);
$('polygon', {points: torn(70, 70, 940, 70, 10), fill: OFF, filter: 'url(#paper)'}, titleG);
text(titleG, 540, 120, S.title.kicker, 40, ink(OFF), 'plain');
const nameSize = Math.min(150, Math.floor(1700 / Math.max(6, S.title.name.length)));
text(titleG, 540, 180 + nameSize * .8, S.title.name.toUpperCase(), nameSize, '#1b1b1b');
text(titleG, 540, 380, S.title.tag, 42, '#5b4b32', 'plain');
text(titleG, 540, 450, `${S.title.line}${S.title.when ? ' · ' + S.title.when : ''}`, 40, '#1b1b1b', 'plain');

const captionG = document.getElementById('caption');
$('polygon', {points: torn(60, 1400, 960, 210, 16), fill: '#fffdf6', filter: 'url(#cut)'}, captionG);
const captionText = text(captionG, 540, 1530, '', 84, '#1b1b1b');

const footerG = document.getElementById('footer');
if (S.sponsor) { $('polygon', {points: torn(80, 1660, 600, 110, 12), fill: '#f6c915', filter: 'url(#cut)'}, footerG); text(footerG, 380, 1700, 'BROUGHT TO YOU BY', 28, '#3b2f00', 'plain'); text(footerG, 380, 1750, S.sponsor, 46, '#1b1b1b', 'plain'); }
text(footerG, S.sponsor ? 860 : 540, 1735, S.station || '', 56, '#fbf7e8');
text(footerG, 540, 1860, S.label, 30, '#c9d6c2', 'plain');

const overlay = document.getElementById('overlay');
const bigWord = $('g', {opacity: 0}, overlay);
const word = kind === 'field_goal' ? "IT'S GOOD!" : (S.td ? 'TOUCHDOWN!' : (kind === 'interception' ? 'PICKED OFF!' : 'BIG PLAY!'));
const letters = [...word].map((ch, i) => { const g = $('g', {filter: 'url(#cut)'}, bigWord); const w = ch === ' ' ? 0 : 86; if (w) $('rect', {x: -43, y: -70, width: 86, height: 120, fill: i % 2 ? OFF : '#fffdf6', transform: `rotate(${(rnd() - .5) * 18})`}, g); text(g, 0, 30, ch, 110, i % 2 ? ink(OFF) : '#1b1b1b'); return g; });
const confetti = [...Array(36)].map(() => { const r = $('rect', {width: 18 + rnd() * 16, height: 10 + rnd() * 8, fill: [OFF, OFF2, '#f6c915', '#fffdf6'][Math.floor(rnd() * 4)], opacity: 0}, overlay); r._x = rnd() * 1080; r._v = 260 + rnd() * 260; r._s = (rnd() - .5) * 600; return r; });
const endG = $('g', {opacity: 0}, overlay);
$('polygon', {points: torn(90, 820, 900, 300, 18), fill: '#fffdf6', filter: 'url(#cut)'}, endG);
text(endG, 540, 920, S.score_after ? 'SCORE' : (S.td ? 'TOUCHDOWN' : 'BIG PLAY'), 56, '#5b4b32', 'plain');
const lines = (S.score_after || `${S.title.name} · ${S.title.line}`).split(', ');
lines.forEach((l, i) => text(endG, 540, 1010 + i * 80, l.toUpperCase(), 64, '#1b1b1b'));

// -- one frame ------------------------------------------------------------------------
window.drawFrame = function (time) {
  const t = Math.floor(time * 12) / 12;   // on twos: 12 drawings a second
  const h = heroPath(t);
  // the ball: carried, thrown or kicked
  let bx = h.x + .75, by = h.y - 62, brot = 0;
  if (kind === 'pass' && t < T_RUN) { const q = passer ? passerX(t) : G.los - 6; if (t < T_AIR) { bx = q + .5; by = lane(2.6) - 100; } else { const p = clamp01((t - T_AIR) / AIR); bx = q + (G.catch - q) * p; by = (lane(2.6) - 100) + (h.y - 95 - (lane(2.6) - 100)) * p - Math.sin(p * Math.PI) * 260; brot = t * 900; } }
  if (kind === 'interception' && t < T_RUN) { const q = G.catch + 14; if (t < T_AIR) { bx = q; by = lane(2) - 100; } else { const p = clamp01((t - T_AIR) / AIR); bx = q + (G.catch - q) * p; by = lane(2) - 100 - Math.sin(p * Math.PI) * 240; brot = -t * 900; } }
  if (kind.endsWith('_return') && t < T_RUN) { const q = G.los; if (t < T_AIR) { bx = q; by = lane(2.4) - 30; } else { const p = clamp01((t - T_AIR) / AIR); bx = q + (G.catch - q) * p; by = lane(2.4) - 30 - Math.sin(p * Math.PI) * 420; brot = -t * 700; } }
  if (kind === 'field_goal') { if (t < T_RUN) { bx = G.start + .3; by = lane(2.6) - 10; } else { const p = clamp01((t - T_RUN) / RUN); bx = G.start + (110 - G.start) * p; by = lane(2.6) - 10 - Math.sin(p * Math.PI * .9) * 520 - p * 120; brot = t * 600; } }
  camera = cameraFor(bx);
  fieldWorld.setAttribute('transform', `translate(${-camera.toFixed(1)} 0)`);
  // offense line and the hero
  // blockers: on the line for a snap; on a return they set up a wall in front of the returner
  const wallX = kind.endsWith('_return') ? G.catch + 9 : G.los - 1;
  offense.forEach((f, i) => { const jostle = t > T_SNAP ? Math.sin(t * 9 + i) * .3 : 0; place(f, wallX + jostle + (kind.endsWith('_return') ? (i % 2) * 2 : 0), lane(i + (i > 1 ? 1.2 : 0)), 0, t, false, i); });
  const heroRunning = t >= T_RUN || (kind === 'pass' && t > T_AIR - .4) || (kind === 'run' && t > T_AIR);
  const tackled = !S.td && kind !== 'field_goal' && t > T_FIN;
  place(hero, h.x, h.y, tackled ? -70 : (kind === 'field_goal' && t > T_RUN - .2 && t < T_RUN + .4 ? -18 : 0), t, heroRunning && !tackled && t < T_FIN, 20);
  // defenders: line up, then chase, dive and fall as the hero goes by
  defense.forEach((f, i) => {
    // five near the ball, then two deep along the hero's path who get their shot later
    const deep = i >= 5 ? (G.start + (G.end - G.start) * (i === 5 ? .45 : .75)) : null;
    const homeX = deep ?? (kind.endsWith('_return') ? G.los - 6 - i * 4 : G.los + 1.5 + (i > 2 ? 7 : 0));
    const homeY = lane([0.3, 1.6, 3.0, 4.3, 2.2, 0.6, 3.6][i]);
    let x = homeX, y = homeY, rot = 0, running = false;
    if (t > T_SNAP && kind !== 'field_goal') {
      const chase = clamp01((t - T_SNAP) / (T_FIN - T_SNAP));
      x = homeX + (h.x - homeX) * chase * .8; y = homeY + (h.y - homeY) * chase * .7; running = true;
      const passed = h.x > x + 1.5 && t > T_RUN;
      if (passed) { rot = -85; running = false; y += 40; }
      if (tackled && i === 4) { x = h.x + 1; y = h.y; rot = -80; running = false; }
    }
    place(f, x, y, rot, t, running, 30 + i);
  });
  if (passer) { const q = passerX(t); place(passer, q, kind === 'interception' ? lane(2) : lane(2.6), 0, t, kind === 'pass' && t > T_SNAP && t < T_AIR, 50); }
  if (kicker) { const kx = G.los + (t > T_AIR ? -clamp01((t - T_AIR) / (AIR + RUN)) * 25 : 0); place(kicker, kx, lane(2.4), 0, t, t > T_AIR, 60); }
  ball.setAttribute('transform', `translate(${(X(bx) - camera).toFixed(1)} ${by.toFixed(1)}) rotate(${brot % 360}) scale(1.3)`);
  // captions by phase
  // the 'action' caption waits for the catch on passes, picks and kicks
  const phase = t < (AIR ? T_RUN : T_AIR) ? 'setup' : (t < T_FIN ? 'action' : 'finish');
  const cap = (S.captions.find(c => c.phase === phase) || {}).text || '';
  captionText.textContent = cap;
  captionText.setAttribute('font-size', cap.length > 22 ? 64 : 84);
  captionText.setAttribute('transform', `rotate(${((noise(99, t) - .5) * 2).toFixed(2)} 540 1510)`);
  // the big word, letter by letter, then confetti
  const celebrate = t >= T_FIN && t < T_END;
  bigWord.setAttribute('opacity', celebrate ? 1 : 0);
  letters.forEach((g, i) => { const shown = clamp01((t - T_FIN) * 12 - i); const lx = 540 + (i - (letters.length - 1) / 2) * 92; const pop = 1 + (1 - shown) * .6; g.setAttribute('opacity', shown); g.setAttribute('transform', `translate(${lx} ${790 + Math.sin(i * 1.7) * 20}) rotate(${((noise(i + 200, t) - .5) * 10).toFixed(1)}) scale(${pop})`); });
  confetti.forEach((r, i) => { const age = t - T_FIN; if (!(S.td || kind === 'field_goal') || age < 0) { r.setAttribute('opacity', 0); return; } r.setAttribute('opacity', 1); const y = 540 + age * r._v - 200 + (i % 6) * 40; r.setAttribute('transform', `translate(${(r._x + Math.sin(age * 3 + i) * 40).toFixed(1)} ${y.toFixed(1)}) rotate(${(age * r._s).toFixed(1)})`); });
  endG.setAttribute('opacity', t >= T_END ? 1 : 0);
  endG.setAttribute('transform', `rotate(${((noise(300, t) - .5) * 2).toFixed(2)} 540 960)`);
  actors.setAttribute('opacity', t >= T_END ? .35 : 1);
};
function passerX(t) {
  if (kind === 'field_goal') return G.start - .5;
  if (kind === 'interception') return G.catch + 14;
  const drop = clamp01((t - T_SNAP) / .5);
  return G.los - 2 - 5 * drop;
}
window.reelReady = (document.fonts ? document.fonts.ready : Promise.resolve()).then(() => { window.drawFrame(0); return true; });
</script>
</body></html>
"""


def page(script: Mapping[str, Any], font_uri: str = "") -> str:
    data = json.dumps(script).replace("</", "<\\/")
    return PAGE.replace("__SCRIPT__", data).replace("__FONT__", font_uri)


def render_mp4(document: str, *, launch: Callable[[], Any] | None = None) -> bytes:
    """Draw every frame of the page in headless Chromium and encode an H.264 MP4."""
    import av
    from PIL import Image
    from playwright.sync_api import sync_playwright

    buffer = io.BytesIO()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True) if launch is None else launch(playwright)
        try:
            page_ = browser.new_page(viewport={"width": WIDTH, "height": HEIGHT})
            page_.set_content(document, wait_until="load")
            page_.wait_for_function("window.drawFrame !== undefined && window.REEL_DURATION > 0")
            page_.evaluate("window.reelReady")
            duration = float(page_.evaluate("window.REEL_DURATION"))
            container = av.open(buffer, mode="w", format="mp4")
            stream = container.add_stream("libx264", rate=VIDEO_FPS)
            stream.width, stream.height, stream.pix_fmt = WIDTH, HEIGHT, "yuv420p"
            stream.options = {"crf": "21", "preset": "veryfast", "movflags": "+faststart"}
            stream.time_base = Fraction(1, VIDEO_FPS)
            pts = 0
            for index in range(int(duration * DRAW_FPS) + 1):
                page_.evaluate(f"window.drawFrame({index / DRAW_FPS})")
                shot = page_.screenshot(type="jpeg", quality=90)
                frame = av.VideoFrame.from_image(Image.open(io.BytesIO(shot)).convert("RGB"))
                for _ in range(VIDEO_FPS // DRAW_FPS):
                    frame.pts = pts
                    pts += 1
                    for packet in stream.encode(frame):
                        container.mux(packet)
            for packet in stream.encode():
                container.mux(packet)
            container.close()
        finally:
            browser.close()
    return buffer.getvalue()
