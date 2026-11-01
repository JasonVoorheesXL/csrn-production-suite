"""Play reels: draw a script (reel_story.script) frame by frame in headless
Chromium and encode the frames into a vertical MP4 (1080 x 1920).

The motion is shared and the theme decides how it is drawn: construction-paper
cutouts, neon outlines, chalkboard Xs and Os, or a comic book. Everything moves
"on twos" (12 drawings a second) with a slight boil, like stop-motion. Players
are generic figures identified only by team colours and numbers.
"""
from __future__ import annotations

import io
import json
import tempfile
from fractions import Fraction
from pathlib import Path
from typing import Any, Callable, Mapping

WIDTH = 1080
HEIGHT = 1920
DRAW_FPS = 12      # new drawing 12 times a second: the stop-motion feel
VIDEO_FPS = 24     # each drawing held for two video frames
# Chalkboard uses the handwriting fonts that ship with Windows.
THEME_FONTS = {"paper": "bangers-regular.woff2", "neon": "michroma-regular.woff2", "comic": "bangers-regular.woff2"}

PAGE = r"""<!doctype html>
<html><head><meta charset="utf-8">
<style>
  @font-face { font-family: 'ReelFont'; src: url('__FONT__') format('woff2'); }
  html, body { margin: 0; padding: 0; background: #23301f; }
  svg { display: block; }
  .big { font-family: 'ReelFont', Impact, sans-serif; letter-spacing: 1px; }
  .chalk .big { font-family: 'Segoe Print', 'Ink Free', cursive; font-weight: 700; letter-spacing: 0; }
  .plain { font-family: 'Segoe UI', Arial, sans-serif; font-weight: 800; }
  .jersey { font-family: 'Arial Black', Impact, sans-serif; font-weight: 900; letter-spacing: -4px; }
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
    <filter id="drop" x="-30%" y="-30%" width="160%" height="160%">
      <feGaussianBlur in="SourceAlpha" stdDeviation="4" result="blur"/>
      <feOffset in="blur" dx="4" dy="6" result="off"/>
      <feComponentTransfer in="off" result="shadow"><feFuncA type="linear" slope="0.4"/></feComponentTransfer>
      <feMerge><feMergeNode in="shadow"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <filter id="puppet" x="-25%" y="-25%" width="150%" height="150%">
      <feTurbulence type="fractalNoise" baseFrequency="1.1" numOctaves="3" seed="9" result="grain"/>
      <feColorMatrix in="grain" type="matrix" values="0 0 0 0 0.25  0 0 0 0 0.18  0 0 0 0 0.1  0 0 0 0.2 -0.05" result="tint"/>
      <feComposite in="tint" in2="SourceGraphic" operator="in" result="speck"/>
      <feGaussianBlur in="SourceAlpha" stdDeviation="3.5" result="blur"/>
      <feOffset in="blur" dx="3" dy="5" result="off"/>
      <feComponentTransfer in="off" result="shadow"><feFuncA type="linear" slope="0.38"/></feComponentTransfer>
      <feMerge><feMergeNode in="shadow"/><feMergeNode in="SourceGraphic"/><feMergeNode in="speck"/></feMerge>
    </filter>
    <clipPath id="helmetClip"><path d="M 285 400 C 240 398 205 375 180 335 C 150 300 135 260 140 215 C 150 110 235 28 345 27 C 470 27 565 105 590 200 L 600 330 L 560 400 Z"/></clipPath>
    <pattern id="felt" width="140" height="140" patternUnits="userSpaceOnUse">
      <rect width="140" height="140" fill="#3f8a3a"/>
      <path d="M0 20 Q35 10 70 22 T140 18" stroke="#4c9a45" stroke-width="10" fill="none" opacity=".5"/>
      <path d="M0 90 Q40 80 80 95 T140 88" stroke="#357a31" stroke-width="12" fill="none" opacity=".5"/>
    </pattern>
    <filter id="neonField" filterUnits="userSpaceOnUse" x="0" y="560" width="1080" height="800">
      <feGaussianBlur in="SourceGraphic" stdDeviation="9" result="soft"/>
      <feMerge><feMergeNode in="soft"/><feMergeNode in="soft"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <filter id="neonText" x="-15%" y="-40%" width="130%" height="180%">
      <feGaussianBlur in="SourceGraphic" stdDeviation="7" result="soft"/>
      <feMerge><feMergeNode in="soft"/><feMergeNode in="soft"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <filter id="chalkField" filterUnits="userSpaceOnUse" x="0" y="560" width="1080" height="800">
      <feTurbulence type="fractalNoise" baseFrequency="0.05" numOctaves="1" seed="3" result="warp"/>
      <feDisplacementMap in="SourceGraphic" in2="warp" scale="7" result="rough"/>
      <feTurbulence type="fractalNoise" baseFrequency="0.7" numOctaves="1" seed="8"/>
      <feColorMatrix type="matrix" values="0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 -2.6 2.35" result="gaps"/>
      <feComposite in="rough" in2="gaps" operator="in"/>
    </filter>
    <filter id="chalkText" x="-5%" y="-20%" width="110%" height="140%">
      <feTurbulence type="fractalNoise" baseFrequency="0.05" numOctaves="2" seed="5" result="warp"/>
      <feDisplacementMap in="SourceGraphic" in2="warp" scale="4" result="rough"/>
      <feTurbulence type="fractalNoise" baseFrequency="0.8" numOctaves="2" seed="2"/>
      <feColorMatrix type="matrix" values="0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 -2.2 2.3" result="gaps"/>
      <feComposite in="rough" in2="gaps" operator="in"/>
    </filter>
    <pattern id="comicTurf" width="22" height="22" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
      <rect width="22" height="22" fill="#2fa84a"/><circle cx="11" cy="11" r="5" fill="#238a3b"/>
    </pattern>
    <pattern id="comicPage" width="34" height="34" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
      <rect width="34" height="34" fill="#ffcf1f"/><circle cx="17" cy="17" r="9" fill="#f2a20c"/>
    </pattern>
    <clipPath id="fieldClip"><rect x="0" y="560" width="1080" height="800"/></clipPath>
  </defs>
  <rect id="backdrop" width="1080" height="1920" fill="#2a3a26" filter="url(#paper)"/>
  <g id="field" clip-path="url(#fieldClip)"></g>
  <g id="actors" clip-path="url(#fieldClip)"></g>
  <g id="overlay"></g>
  <g id="title"></g>
  <g id="caption"></g>
  <g id="footer"></g>
</svg>
<script>
const S = __SCRIPT__;
const TH = ['paper', 'neon', 'chalk', 'comic'].includes(S.theme) ? S.theme : 'paper';
document.documentElement.classList.add(TH);
const NS = 'http://www.w3.org/2000/svg';
const FIELD_TOP = 560, FIELD_H = 800, PX = 64;   // pixels per yard
const $ = (tag, attrs, parent) => { const el = document.createElementNS(NS, tag); for (const k in attrs) el.setAttribute(k, attrs[k]); if (parent) parent.appendChild(el); return el; };
let seed = 7; const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
function noise(i, t) { const x = Math.sin(i * 12.9898 + Math.floor(t * 12) * 78.233) * 43758.5453; return x - Math.floor(x); }
function torn(x, y, w, h, jag) { const pts = []; const step = 26; for (let i = 0; i <= w; i += step) pts.push([x + i, y + (rnd() - .5) * jag]); for (let i = 0; i <= h; i += step) pts.push([x + w + (rnd() - .5) * jag, y + i]); for (let i = w; i >= 0; i -= step) pts.push([x + i, y + h + (rnd() - .5) * jag]); for (let i = h; i >= 0; i -= step) pts.push([x + (rnd() - .5) * jag, y + i]); return pts.map(p => p.join(',')).join(' '); }
function text(parent, x, y, str, size, fill, cls, anchor) { const t = $('text', {x, y, 'font-size': size, fill, class: cls || 'big', 'text-anchor': anchor || 'middle'}, parent); t.textContent = str; return t; }
const fitted = [];
function fitText(el, width, size, again) { if (!again) fitted.push([el, width, size]); el.setAttribute('font-size', size); const used = el.getComputedTextLength(); if (used > width) el.setAttribute('font-size', Math.floor(size * width / used)); }
function inked(el, color, width) { el.setAttribute('stroke', color); el.setAttribute('stroke-width', width); el.setAttribute('paint-order', 'stroke'); el.setAttribute('stroke-linejoin', 'round'); return el; }
function hex(c, d) { return /^#[0-9a-f]{6}$/i.test(c || '') ? c : d; }
function lum(c) { const n = parseInt(c.slice(1), 16); return (0.299 * (n >> 16) + 0.587 * ((n >> 8) & 255) + 0.114 * (n & 255)) / 255; }
function near(a, b) { const x = parseInt(a.slice(1), 16), y = parseInt(b.slice(1), 16); return Math.abs((x >> 16) - (y >> 16)) + Math.abs(((x >> 8) & 255) - ((y >> 8) & 255)) + Math.abs((x & 255) - (y & 255)) < 120; }

// -- colours: the two teams must read apart on the felt -------------------------
const OFF = hex(S.offense.primary, '#c8102e'), OFF2 = hex(S.offense.secondary, '#ffffff');
let DEF = hex(S.defense.primary, '#1d3f8f'), DEF2 = hex(S.defense.secondary, '#ffffff');
const ink = c => lum(c) > 0.6 ? '#1b1b1b' : '#ffffff';
function shade(c, amount) { const n = parseInt(c.slice(1), 16); const m = v => Math.max(0, Math.round(v * amount)).toString(16).padStart(2, '0'); return '#' + m(n >> 16) + m((n >> 8) & 255) + m(n & 255); }
// Uniforms in the team's own colours. Home: primary helmet, gloves, jersey and pants with secondary
// number, socks and sleeves. Away is the reverse, unless that clashes with the home team.
function uniforms() {
  const home = S.offense.side === 'visitor' ? S.defense : S.offense, away = home === S.offense ? S.defense : S.offense;
  const hp = hex(home.primary, '#c8102e'), hs = hex(home.secondary, ink(hp));
  const ap = hex(away.primary, '#1d3f8f'), as = hex(away.secondary, ink(ap));
  let awayMain = as, awayAccent = ap;
  if (near(awayMain, hp)) { awayMain = ap; awayAccent = as; }
  if (near(awayMain, hp)) { awayMain = lum(hp) < .6 ? '#f4f1e8' : '#2f3338'; awayAccent = ap; }
  const dress = (main, accent) => ({main, accent: near(main, accent) ? ink(main) : accent});
  const h = dress(hp, hs), a = dress(awayMain, awayAccent);
  return home === S.offense ? [h, a] : [a, h];
}
const [OFFU, DEFU] = uniforms();
// A number has to read against the jersey even when the two team colours are close in brightness.
const numberOn = u => Math.abs(lum(u.main) - lum(u.accent)) >= .3 ? u.accent : ink(u.main);
function toHsl(c) { const n = parseInt(c.slice(1), 16), r = (n >> 16) / 255, g = ((n >> 8) & 255) / 255, b = (n & 255) / 255, hi = Math.max(r, g, b), lo = Math.min(r, g, b), d = hi - lo, l = (hi + lo) / 2; const s = d ? d / (1 - Math.abs(2 * l - 1)) : 0; const h = !d ? 0 : hi === r ? ((g - b) / d + 6) % 6 : hi === g ? (b - r) / d + 2 : (r - g) / d + 4; return [h * 60, s, l]; }
function fromHsl(h, s, l) { const f = k => { const m = (k + h / 30) % 12; const v = l - s * Math.min(l, 1 - l) * Math.max(-1, Math.min(m - 3, 9 - m, 1)); return Math.round(v * 255).toString(16).padStart(2, '0'); }; return '#' + f(0) + f(8) + f(4); }
const tube = c => { const [h, s] = toHsl(c); return s < .18 ? '#f4f7ff' : fromHsl(h, 1, .62); };    // team colour as a neon tube
const stick = c => { const [h, s] = toHsl(c); return s < .18 ? '#f2f1ea' : fromHsl(h, .75, .78); }; // team colour as a stick of chalk
const NH = tube(OFFU.main), ND0 = tube(DEFU.main), ND = near(NH, ND0) ? (near(NH, '#00e5ff') ? '#ff2bd6' : '#00e5ff') : ND0;
const CH = stick(OFFU.main), CD0 = stick(DEFU.main), CD = near(CH, CD0) ? '#f2f1ea' : CD0;

// -- timing ---------------------------------------------------------------------
const G = S.geometry, kind = S.kind;
const dist = Math.abs((G.end ?? 0) - (G.start ?? 0));
const INTRO = 2.2, SNAP = 0.5;
const AIR = (kind === 'pass' || kind === 'interception') ? 0.9 + Math.abs((G.catch ?? G.start) - G.los) * 0.03 : (kind.endsWith('_return') ? 1.6 : 0);
const RUN = kind === 'field_goal' ? 1.8 : Math.min(6.5, Math.max(1.6, 1.0 + dist * 0.07));
const FINISH = 3.8, END = 2.4;
const T_SNAP = INTRO, T_AIR = T_SNAP + SNAP, T_RUN = T_AIR + AIR, T_FIN = T_RUN + RUN, T_END = T_FIN + FINISH;
window.REEL_DURATION = T_END + END;

// -- the field --------------------------------------------------------------------
const field = document.getElementById('field');
const fieldWorld = $('g', {}, field);
const X = yd => yd * PX;   // world x before the camera shift
const backdrop = document.getElementById('backdrop');
let endZoneName;
const turf = fill => $('rect', {x: 0, y: FIELD_TOP, width: 1080, height: FIELD_H, fill}, field).parentNode.insertBefore(field.lastChild, fieldWorld);
const midY = FIELD_TOP + FIELD_H / 2;
function zoneName(fill, size) { endZoneName = text(fieldWorld, X(105), midY, (S.defense.name || '').toUpperCase().slice(0, 14), size, fill); endZoneName.setAttribute('transform', `rotate(-90 ${X(105)} ${midY})`); return endZoneName; }
function postPaths(attrs, parent) { $('path', {d: `M ${X(110)} ${FIELD_TOP + 660} V ${FIELD_TOP + 305} M ${X(110) - 55} ${FIELD_TOP + 65} V ${FIELD_TOP + 305} H ${X(110) + 55} V ${FIELD_TOP + 65}`, fill: 'none', ...attrs}, parent); }
const FIELDS = {
  paper() {
    turf('url(#felt)');
    $('rect', {x: X(-10), y: FIELD_TOP, width: X(10), height: FIELD_H, fill: OFF, opacity: .85, filter: 'url(#paper)'}, fieldWorld);
    $('rect', {x: X(100), y: FIELD_TOP, width: X(10), height: FIELD_H, fill: DEF, opacity: .85, filter: 'url(#paper)'}, fieldWorld);
    zoneName(ink(DEF), 64);
    for (let yd = 0; yd <= 100; yd += 5) {
      const w = yd % 10 === 0 ? 12 : 7, wob = (rnd() - .5) * 3;
      $('rect', {x: X(yd) - w / 2, y: FIELD_TOP - 10, width: w, height: FIELD_H + 20, fill: '#fbf7e8', transform: `rotate(${wob} ${X(yd)} ${midY})`, filter: 'url(#paper)'}, fieldWorld);
      if (yd % 10 === 0 && yd > 0 && yd < 100) { const n = String(yd <= 50 ? yd : 100 - yd); text(fieldWorld, X(yd), FIELD_TOP + 120, n, 72, '#fbf7e8'); text(fieldWorld, X(yd), FIELD_TOP + FIELD_H - 50, n, 72, '#fbf7e8'); }
    }
    // goal posts at the back of the end zone
    const posts = $('g', {filter: 'url(#cut)'}, fieldWorld);
    $('rect', {x: X(110) - 9, y: FIELD_TOP + 300, width: 18, height: 360, fill: '#f6c915'}, posts);
    $('rect', {x: X(110) - 60, y: FIELD_TOP + 300, width: 120, height: 16, fill: '#f6c915'}, posts);
    $('rect', {x: X(110) - 60, y: FIELD_TOP + 60, width: 14, height: 250, fill: '#f6c915'}, posts);
    $('rect', {x: X(110) + 46, y: FIELD_TOP + 60, width: 14, height: 250, fill: '#f6c915'}, posts);
  },
  neon() {
    backdrop.setAttribute('fill', '#05060f'); backdrop.removeAttribute('filter');
    turf('#070a1c');
    $('rect', {x: X(-10), y: FIELD_TOP, width: X(10), height: FIELD_H, fill: NH, opacity: .16}, fieldWorld);
    $('rect', {x: X(100), y: FIELD_TOP, width: X(10), height: FIELD_H, fill: ND, opacity: .16}, fieldWorld);
    zoneName(ND, 46);
    const line = (x, w, color) => { $('rect', {x: x - w * 2, y: FIELD_TOP, width: w * 4, height: FIELD_H, fill: color, opacity: .16}, fieldWorld); $('rect', {x: x - w / 2, y: FIELD_TOP, width: w, height: FIELD_H, fill: color}, fieldWorld); };
    for (let yd = 0; yd <= 100; yd += 5) {
      const main = yd % 10 === 0;
      line(X(yd), main ? 6 : 3, main ? '#9fe8ff' : '#3f6d96');
      if (main && yd > 0 && yd < 100) { const n = String(yd <= 50 ? yd : 100 - yd); text(fieldWorld, X(yd), FIELD_TOP + 110, n, 44, '#9fe8ff'); text(fieldWorld, X(yd), FIELD_TOP + FIELD_H - 50, n, 44, '#9fe8ff'); }
    }
    postPaths({stroke: '#ffe45c', 'stroke-width': 26, opacity: .2}, fieldWorld);
    postPaths({stroke: '#ffe45c', 'stroke-width': 9}, fieldWorld);
  },
  chalk() {
    backdrop.setAttribute('fill', '#20302a'); backdrop.removeAttribute('filter');
    turf('#22342d');
    field.setAttribute('filter', 'url(#chalkField)');
    const white = '#f2f1ea';
    const hatch = (from, color) => { let d = ''; for (let i = -14; i < 26; i++) d += `M ${X(from) + i * 44} ${FIELD_TOP} L ${X(from) + i * 44 + 180} ${FIELD_TOP + FIELD_H} `; $('path', {d, stroke: color, 'stroke-width': 4, opacity: .22, 'clip-path': `url(#zone${from})`}, fieldWorld); };
    [-10, 100].forEach(from => { const c = $('clipPath', {id: `zone${from}`}, fieldWorld); $('rect', {x: X(from), y: FIELD_TOP, width: X(10), height: FIELD_H}, c); });
    hatch(-10, CH); hatch(100, CD);
    zoneName(CD, 60);
    for (let yd = 0; yd <= 100; yd += 5) {
      const main = yd % 10 === 0, wob = (rnd() - .5) * 2.4;
      $('path', {d: `M ${X(yd)} ${FIELD_TOP - 10} L ${X(yd) + wob * 6} ${FIELD_TOP + FIELD_H + 10}`, stroke: white, 'stroke-width': main ? 8 : 4, opacity: main ? .95 : .6}, fieldWorld);
      if (main && yd > 0 && yd < 100) { const n = String(yd <= 50 ? yd : 100 - yd); text(fieldWorld, X(yd), FIELD_TOP + 110, n, 60, white); text(fieldWorld, X(yd), FIELD_TOP + FIELD_H - 40, n, 60, white); }
      if (yd < 100) for (let i = 1; i < 5; i++) $('path', {d: `M ${X(yd + i)} ${FIELD_TOP + 300} v 22 M ${X(yd + i)} ${FIELD_TOP + 480} v 22`, stroke: white, 'stroke-width': 3, opacity: .5}, fieldWorld);
    }
    postPaths({stroke: '#f7e27a', 'stroke-width': 8}, fieldWorld);
  },
  comic() {
    backdrop.setAttribute('fill', 'url(#comicPage)'); backdrop.removeAttribute('filter');
    turf('url(#comicTurf)');
    $('rect', {x: X(-10), y: FIELD_TOP, width: X(10), height: FIELD_H, fill: OFFU.main}, fieldWorld);
    $('rect', {x: X(100), y: FIELD_TOP, width: X(10), height: FIELD_H, fill: DEFU.main}, fieldWorld);
    inked(zoneName('#ffffff', 70), '#111', 8);
    for (let yd = 0; yd <= 100; yd += 5) {
      const main = yd % 10 === 0, w = main ? 12 : 7;
      $('rect', {x: X(yd) - w / 2, y: FIELD_TOP - 10, width: w, height: FIELD_H + 20, fill: '#fff', stroke: '#111', 'stroke-width': 3}, fieldWorld);
      if (main && yd > 0 && yd < 100) { const n = String(yd <= 50 ? yd : 100 - yd); inked(text(fieldWorld, X(yd), FIELD_TOP + 120, n, 84, '#fff'), '#111', 8); inked(text(fieldWorld, X(yd), FIELD_TOP + FIELD_H - 50, n, 84, '#fff'), '#111', 8); }
    }
    postPaths({stroke: '#111', 'stroke-width': 26}, fieldWorld);
    postPaths({stroke: '#ffd21f', 'stroke-width': 14}, fieldWorld);
  },
};
FIELDS[TH]();

// -- paper figures: traced from the station's concept player. Coordinates are the concept's
// own (675 x 900 artboard); the rig scales them down and stands the figure on its feet.
const actors = document.getElementById('actors');
const EDGE = '#8a5f33', CREAM = '#efe1c5', CLEAT = '#2a2a2c', SOLE = '#6d4a28', CAGE = '#8c8c8a', MASK = '#2b2b2e';
const cut = (extra) => ({stroke: K.edge, 'stroke-width': K.edgeW, 'stroke-linejoin': 'round', 'stroke-linecap': 'round', ...extra});
// Every player wears full-length sleeves, socks and team-colored gloves, with a dark, empty face
// mask and neckline: no skin shows anywhere, so nothing about a figure suggests who it is.
const inUniform = (u, look) => ({...look, base: u.main, pants: u.main, glove: u.main, sleeve: u.accent, sock: u.accent, trim: u.accent, stripe: u.main, num: numberOn(u)});
const PAPER_KIT = {edge: EDGE, edgeW: 4, cage: CAGE, cageEdge: EDGE, cleat: CLEAT, sole: SOLE, lace: CREAM, mask: MASK, filter: 'url(#puppet)'};
const COMIC_KIT = {edge: '#111', edgeW: 9, cage: '#a3a3a3', cageEdge: '#111', cleat: '#1b1b1b', sole: '#111', lace: '#fff', mask: '#15151a'};
const neonKit = (c, accent) => ({base: '#0b1030', sleeve: '#0b1030', sock: '#0b1030', trim: accent, stripe: c, num: accent, pants: shade(c, .3), glove: c, edge: c, edgeW: 7, cage: '#e8f0ff', cageEdge: c, cleat: '#060814', sole: c, lace: c, mask: '#02030a'});
const neonAccent = (u, c) => { const a = tube(u.accent); return near(a, c) ? '#ffffff' : a; };
const KITS = {
  paper: [inUniform(OFFU, PAPER_KIT), inUniform(DEFU, PAPER_KIT)],
  neon: [neonKit(NH, neonAccent(OFFU, NH)), neonKit(ND, neonAccent(DEFU, ND))],
  chalk: [{ink: CH, mark: 'O'}, {ink: CD, mark: 'X'}],
  comic: [inUniform(OFFU, COMIC_KIT), inUniform(DEFU, COMIC_KIT)],
};
const [HOME, AWAY] = KITS[TH];
let K = HOME;   // the kit of the figure being built
function pivot(parent, x, y) { const g = $('g', {}, parent); g._pivot = [x, y]; return g; }
function fold(parent, d) { $('path', {d, fill: '#000', opacity: .14}, parent); }   // the soft shadow a layered piece casts
function nearLeg(rig) {
  const g = pivot(rig, 300, 610);
  $('path', cut({d: 'M 178 712 L 268 742 L 244 794 L 160 782 Z', fill: K.sock}), g);                                  // sock
  $('path', {d: 'M 176 732 L 258 758 M 168 756 L 250 778', stroke: K.stripe, 'stroke-width': 13}, g);
  $('path', cut({d: 'M 240 590 L 362 622 L 342 682 L 262 748 L 172 716 C 188 680 214 640 240 590 Z', fill: K.pants}), g); // pants
  $('rect', {x: 228, y: 620, width: 100, height: 76, rx: 12, transform: 'rotate(18 278 658)', fill: '#000', opacity: .1, stroke: '#000', 'stroke-width': 3}, g); // knee pad
  $('path', cut({d: 'M 158 778 C 136 792 128 826 138 848 L 340 852 C 356 816 318 800 272 792 L 244 786 Z', fill: K.cleat}), g); // cleat
  $('path', {d: 'M 138 848 L 340 852', stroke: K.sole, 'stroke-width': 11, 'stroke-linecap': 'round'}, g);
  $('path', {d: 'M 236 802 L 254 788 M 256 808 L 274 794 M 276 814 L 294 802', stroke: K.lace, 'stroke-width': 7, 'stroke-linecap': 'round'}, g);
  $('path', {d: 'M 170 856 L 170 862 M 222 858 L 222 864 M 274 858 L 274 864 M 322 858 L 322 862', stroke: K.cleat, 'stroke-width': 18, 'stroke-linecap': 'round'}, g);
  return g;
}
function farLeg(rig) {
  const g = pivot(rig, 440, 610);
  $('path', cut({d: 'M 420 728 L 526 706 L 522 768 L 428 794 Z', fill: K.sock}), g);
  $('path', {d: 'M 422 746 L 524 726 M 424 766 L 523 746', stroke: K.stripe, 'stroke-width': 12}, g);
  $('path', cut({d: 'M 362 668 L 500 592 L 536 704 L 424 732 C 418 706 396 688 362 668 Z', fill: K.pants}), g);
  $('rect', {x: 440, y: 618, width: 78, height: 78, rx: 12, transform: 'rotate(-12 480 656)', fill: '#000', opacity: .1, stroke: '#000', 'stroke-width': 3}, g);
  $('path', cut({d: 'M 426 790 C 410 806 406 830 416 846 L 610 840 C 628 806 580 786 532 776 L 520 766 Z', fill: K.cleat}), g);
  $('path', {d: 'M 416 846 L 610 840', stroke: K.sole, 'stroke-width': 11, 'stroke-linecap': 'round'}, g);
  $('path', {d: 'M 510 784 L 526 772 M 528 792 L 546 780 M 548 800 L 566 788', stroke: K.lace, 'stroke-width': 7, 'stroke-linecap': 'round'}, g);
  $('path', {d: 'M 446 854 L 446 860 M 496 852 L 496 858 M 546 850 L 546 856 M 592 848 L 592 854', stroke: K.cleat, 'stroke-width': 18, 'stroke-linecap': 'round'}, g);
  return g;
}
function farArm(rig) {
  const g = pivot(rig, 512, 450);
  $('path', cut({d: 'M 496 500 L 532 486 C 556 530 578 570 596 612 L 540 642 C 526 600 508 552 496 500 Z', fill: K.sleeve}), g);
  $('path', {d: 'M 520 612 L 584 582', stroke: K.stripe, 'stroke-width': 13}, g);
  $('path', cut({d: 'M 538 628 C 524 654 540 684 572 680 C 604 672 610 632 590 604 Z', fill: K.glove}), g);          // glove
  $('path', cut({d: 'M 538 628 C 528 616 520 626 522 640 C 526 654 536 656 544 650 Z', fill: K.glove}), g);          // thumb
  $('path', cut({d: 'M 506 426 L 548 488 L 512 532 C 500 500 496 462 506 426 Z', fill: K.sleeve}), g);                  // sleeve
  $('path', {d: 'M 514 448 L 536 486 M 504 470 L 524 506', stroke: K.stripe, 'stroke-width': 13}, g);
  return g;
}
function nearArm(rig) {
  const g = pivot(rig, 205, 440);
  $('path', cut({d: 'M 155 458 C 134 490 124 524 120 560 L 206 580 C 214 544 234 512 252 492 Z', fill: K.sleeve}), g);
  $('path', cut({d: 'M 122 552 C 98 580 98 636 130 656 C 164 670 196 652 202 624 L 216 612 C 218 596 206 590 206 576 Z', fill: K.glove}), g);  // glove
  $('path', {d: 'M 126 548 L 210 570', stroke: K.stripe, 'stroke-width': 14}, g);
  fold(g, 'M 150 462 L 250 516 L 246 530 L 146 480 Z');
  $('path', cut({d: 'M 146 452 L 212 388 L 322 422 L 250 522 Z', fill: K.sleeve}), g);                                 // shoulder cap
  $('path', {d: 'M 192 404 L 298 438 M 172 424 L 280 468 M 156 446 L 262 500', stroke: K.stripe, 'stroke-width': 13}, g);
  return g;
}
function chalkFigure(number, facing, role) {
  const g = $('g', {}, actors), inner = $('g', {}, g), hero = role === 'hero';
  const line = {stroke: K.ink, 'stroke-width': hero ? 9 : 7, fill: 'none', 'stroke-linecap': 'round', 'stroke-linejoin': 'round'};
  const limbs = $('g', {display: 'none'}, inner);   // stick arms and legs: only the dancing hero shows them
  const limb = (x, y, d) => { const l = pivot(limbs, x, y); $('path', {d, ...line}, l); return l; };
  const legF = limb(-16, -28, 'M -16 -28 L -24 0 L -40 0'), legB = limb(16, -28, 'M 16 -28 L 24 0 L 40 0');
  const armF = limb(-38, -66, 'M -38 -66 L -52 -18'), armB = limb(38, -66, 'M 38 -66 L 52 -18');
  const torso = pivot(inner, 0, -66), head = pivot(inner, 0, -66);
  if (K.mark === 'X') $('path', {d: 'M -36 -102 L 36 -30 M 36 -102 L -36 -30', ...line}, head);
  else $('circle', {cx: 0, cy: -66, r: 42, ...line}, head);
  if (hero) $('circle', {cx: 0, cy: -66, r: 54, ...line, 'stroke-width': 4, 'stroke-dasharray': '14 12'}, head);
  if (role === 'block') $('path', {d: 'M 48 -66 H 80 M 80 -90 V -42', ...line, 'stroke-width': 6}, inner);
  const num = text(head, 0, -50, hero ? number || '' : '', 46, K.ink);
  return {g, inner, torso, head, legF, legB, armF, armB, num, numX: 0, limbs, facing};
}
function figure(kit, number, facing, role) {
  K = kit;
  if (TH === 'chalk') return chalkFigure(number, facing, role);
  const g = $('g', kit.filter ? {filter: kit.filter} : {}, actors);
  const inner = $('g', {}, g);            // flips with the way the player faces
  const rig = $('g', {transform: 'scale(.287) translate(-360 -860)'}, inner);
  const legB = farLeg(rig), legF = nearLeg(rig), armB = farArm(rig);
  $('path', cut({d: 'M 236 570 L 508 566 L 516 640 L 372 676 L 228 628 Z', fill: K.pants}), rig);                       // hips
  const torso = pivot(rig, 370, 600);
  $('path', cut({d: 'M 240 572 L 244 624 C 340 636 430 630 496 602 L 500 566 Z', fill: K.base}), torso);               // hem, a second layer
  fold(torso, 'M 240 572 L 500 566 L 500 580 L 242 588 Z');
  $('path', cut({d: 'M 252 400 L 510 428 L 520 472 L 500 584 Q 360 612 238 580 Z', fill: K.base}), torso);
  $('path', {d: 'M 372 424 L 404 452 L 440 424 Z', fill: K.mask}, torso);                                             // V-neck
  const num = text(torso, 402, 578, number || '', number && number.length > 1 ? 150 : 170, K.num, 'jersey');
  const armF = nearArm(rig);
  const head = pivot(rig, 350, 410);
  $('path', cut({d: 'M 285 400 C 240 398 205 375 180 335 C 150 300 135 260 140 215 C 150 110 235 28 345 27 C 470 27 565 105 590 200 L 600 330 L 560 400 Z', fill: K.base}), head);
  $('path', {d: 'M 328 26 C 360 22 395 24 422 32 C 472 75 506 130 520 194 L 468 202 C 450 132 400 66 328 26 Z', fill: K.trim, 'clip-path': 'url(#helmetClip)'}, head);
  $('path', cut({d: 'M 296 240 L 586 212 L 592 336 L 572 394 C 500 412 420 412 340 404 L 300 372 Z', fill: K.mask}), head);   // the dark opening
  const rail = 'M 590 205 L 322 232 Q 292 236 286 268 L 282 336 Q 298 380 332 398 C 420 414 510 410 572 396 L 602 334 L 272 346 M 404 348 L 396 406';
  $('path', {d: rail, stroke: K.cageEdge, 'stroke-width': 25, fill: 'none', 'stroke-linecap': 'round', 'stroke-linejoin': 'round'}, head);
  $('path', {d: rail, stroke: K.cage, 'stroke-width': 18, fill: 'none', 'stroke-linecap': 'round', 'stroke-linejoin': 'round'}, head);
  $('ellipse', cut({cx: 228, cy: 318, rx: 17, ry: 33, fill: K.mask, transform: 'rotate(-12 228 318)'}), head);        // ear hole
  $('ellipse', cut({cx: 173, cy: 232, rx: 13, ry: 22, fill: K.cage, 'stroke-width': 4}), head);                        // helmet snap
  $('circle', cut({cx: 272, cy: 345, r: 17, fill: K.cage, 'stroke-width': 4}), head);                                  // mask clip
  return {g, inner, torso, head, legF, legB, armF, armB, num, numX: 402, facing};
}
function ballShape(parent) { const looks = {paper: ['#7a3e1a', '#3d2410', 3], neon: ['#2a1405', '#ffb347', 5], chalk: ['none', '#f7e27a', 5], comic: ['#8a4a1c', '#111', 6]}[TH]; const g = $('g', TH === 'paper' ? {filter: 'url(#drop)'} : {}, parent); $('ellipse', {cx: 0, cy: 0, rx: 24, ry: 15, fill: looks[0], stroke: looks[1], 'stroke-width': looks[2]}, g); $('path', {d: 'M -18 -8 Q -14 0 -18 8 M 18 -8 Q 14 0 18 8', stroke: CREAM, 'stroke-width': 3.5, fill: 'none'}, g); $('path', {d: 'M -8 0 L 8 0 M -5 -4 L -5 4 M 0 -4 L 0 4 M 5 -4 L 5 4', stroke: CREAM, 'stroke-width': 2.5}, g); return g; }

const lane = i => FIELD_TOP + 290 + i * 106;   // the figure's feet
const offense = [], defense = [];
if (TH === 'neon') actors.setAttribute('filter', 'url(#neonField)');
if (TH === 'chalk') actors.setAttribute('filter', 'url(#chalkField)');
const trail = $('path', {fill: 'none', stroke: '#f7e27a', 'stroke-width': 7, 'stroke-linecap': 'round', 'stroke-linejoin': 'round'}, fieldWorld);
const throwLine = $('path', {fill: 'none', stroke: '#f2f1ea', 'stroke-width': 5, 'stroke-dasharray': '4 18', 'stroke-linecap': 'round'}, fieldWorld);
const streaks = [...Array(5)].map(() => $('rect', {height: TH === 'comic' ? 9 : 6, rx: 3, fill: TH === 'comic' ? '#fff' : NH, stroke: TH === 'comic' ? '#111' : 'none', 'stroke-width': 2, opacity: 0}, actors));
const floorRing = $('ellipse', {rx: 220, ry: 44, fill: 'none', stroke: NH, 'stroke-width': 8, opacity: 0}, actors);
const hero = figure(HOME, S.hero.number, 1, 'hero');
let passer = null, kicker = null;
for (let i = 0; i < 4; i++) offense.push(figure(HOME, String([52, 66, 71, 64][i]), 1, 'block'));
for (let i = 0; i < 7; i++) defense.push(figure(AWAY, String([44, 9, 21, 55, 3, 24, 6][i]), -1));
if (kind === 'pass') passer = figure(HOME, S.passer.number || '7', 1);
if (kind === 'interception') passer = figure(AWAY, '7', -1);
if (kind.endsWith('_return')) kicker = figure(AWAY, '18', -1);
if (kind === 'field_goal') { passer = figure(HOME, '12', 1); }
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
function turn(el, angle) { el.setAttribute('transform', `rotate(${angle} ${el._pivot[0]} ${el._pivot[1]})`); }
function place(f, x, y, rot, t, running, idx, pose) {
  const boil = (noise(idx, t) - .5) * 2.4;
  const sx = X(x) - camera, p = pose || {};
  const scale = p.scale || (TH === 'chalk' ? 1.1 : .82);
  const flip = (p.flip ?? 1) * f.facing;
  f.g.setAttribute('transform', `translate(${sx.toFixed(1)} ${y.toFixed(1)}) rotate(${(rot + boil).toFixed(2)}) scale(${scale})`);
  f.inner.setAttribute('transform', `scale(${flip} 1)`);
  f.num.setAttribute('transform', `translate(${f.numX} 0) scale(${flip < 0 ? -1 : 1} 1) translate(${-f.numX} 0)`);
  if (f.limbs) f.limbs.setAttribute('display', p.scale > 1 ? 'inline' : 'none');
  const stride = running ? (Math.floor(t * 12) % 2 ? 1 : -1) : 0;
  turn(f.legF, p.legF ?? 20 * stride);
  turn(f.legB, p.legB ?? -20 * stride);
  turn(f.armF, p.armF ?? (running ? 28 * stride : 0));
  turn(f.armB, p.armB ?? (running ? 28 * stride : 0));
  turn(f.torso, p.torso ?? (running ? 4 : 0));
  turn(f.head, p.head ?? (p.torso ?? (running ? 4 : 0)) * .6);
  f._y = y;
}
function stackActors() {   // nearer the camera (lower on the field) draws on top; the ball stays in front
  [hero, passer, kicker, ...offense, ...defense].filter(Boolean).sort((a, b) => a._y - b._y).forEach(f => actors.appendChild(f.g));
  actors.appendChild(ball);
}
// Celebrations: each beat holds one pose for a few drawings, like stop-motion.
const DANCES = {
  shimmy: b => ({torso: b % 2 ? 7 : -7, armF: b % 2 ? 115 : 65, armB: b % 2 ? -65 : -115, legF: b % 2 ? 6 : -6, legB: b % 2 ? 6 : -6}),
  robot: b => [{armF: 90, armB: 0, head: 10}, {armF: 0, armB: -90, head: -10}, {armF: 90, armB: -90, head: 0}, {armF: 125, armB: 0, head: 10}][b % 4],
  disco: b => ({armB: b % 2 ? -125 : -30, armF: 15, torso: b % 2 ? 7 : -7, legF: b % 2 ? 14 : 0, legB: b % 2 ? 0 : -14}),
  moonwalk: b => ({dx: -b * .42, legF: b % 2 ? 20 : -8, legB: b % 2 ? -8 : 20, armF: b % 2 ? 26 : -18, armB: b % 2 ? -18 : 26, torso: -5}),
  fistpump: b => ({dy: b % 2 ? -44 : 0, armB: b % 2 ? -125 : -60, armF: 12, legF: b % 2 ? 20 : 0, legB: b % 2 ? -20 : 0}),
  kneeknock: b => ({legF: b % 2 ? -18 : 10, legB: b % 2 ? 18 : -10, armF: 28, armB: -28, torso: b % 2 ? 3 : -3}),
  twirl: b => ({flip: [1, .35, -1, -.35][b % 4], armF: 120, armB: -120, dy: b % 4 === 1 || b % 4 === 3 ? -18 : 0}),
};
function dancePose(t) {
  const name = DANCES[S.dance] ? S.dance : 'shimmy';
  const beat = Math.floor((t - T_FIN - .35) * 3.4);
  return DANCES[name](Math.max(0, beat));
}
let camera = 0;
function clampCamera(c) { return Math.max(X(-10), Math.min(X(112) - 1080, c)); }
function cameraFor(ballX) { return clampCamera(X(ballX) - 1080 * (kind === 'interception' || kind.endsWith('_return') ? .42 : .38)); }

// -- the overlay: title, captions, footer, big words ----------------------------------
const PAL = {
  paper: {kicker: ink(OFF), name: '#1b1b1b', tag: '#5b4b32', line: '#1b1b1b', caption: '#1b1b1b', station: '#fbf7e8', label: '#c9d6c2', scoreHead: '#5b4b32', score: '#1b1b1b'},
  neon: {kicker: NH, name: '#ffffff', tag: ND, line: '#cfe9ff', caption: '#ffffff', station: '#ffffff', label: '#7f8db0', scoreHead: ND, score: '#ffffff'},
  chalk: {kicker: '#f7e27a', name: '#f7f6ef', tag: '#c9d6c2', line: '#f2f1ea', caption: '#f7f6ef', station: '#f7f6ef', label: '#9fb3a8', scoreHead: '#f7e27a', score: '#f7f6ef'},
  comic: {kicker: ink(OFFU.main), name: '#111', tag: '#c21d24', line: '#111', caption: '#111', station: '#111', label: '#111', scoreHead: '#c21d24', score: '#111'},
}[TH];
const FILLS = {
  paper: {title: '#f2e6c9', caption: '#fffdf6', sponsor: '#fffdf6', score: '#fffdf6'},
  neon: {title: '#0a0e24', caption: '#0a0e24', sponsor: '#f7f8ff', score: '#0a0e24'},
  chalk: {title: 'none', caption: 'none', sponsor: '#f4ecd6', score: '#22342d'},
  comic: {title: '#fffdf2', caption: '#ffe94a', sponsor: '#ffffff', score: '#fffdf2'},
}[TH];
function panel(parent, x, y, w, h, role) {
  const fill = FILLS[role];
  if (TH === 'paper') return $('polygon', {points: torn(x, y, w, h, role === 'title' ? 18 : role === 'sponsor' ? 12 : role === 'score' ? 18 : 16), fill, filter: 'url(#cut)'}, parent);
  if (TH === 'neon') {
    const color = role === 'caption' ? ND : NH;
    $('rect', {x: x - 5, y: y - 5, width: w + 10, height: h + 10, rx: 30, fill: 'none', stroke: color, 'stroke-width': 18, opacity: .22}, parent);
    return $('rect', {x, y, width: w, height: h, rx: 26, fill, stroke: color, 'stroke-width': 6}, parent);
  }
  if (TH === 'chalk') {
    if (role === 'sponsor') {   // a taped note, so a dark logo still shows on the board
      const note = $('g', {transform: `rotate(-1 ${x + w / 2} ${y + h / 2})`}, parent);
      $('rect', {x, y, width: w, height: h, fill}, note);
      $('rect', {x: x + w / 2 - 70, y: y - 16, width: 140, height: 32, fill: '#d9c98f', opacity: .9}, note);
      return note;
    }
    const box = $('g', {filter: 'url(#chalkText)'}, parent);
    return $('rect', {x, y, width: w, height: h, rx: 8, fill, stroke: '#f2f1ea', 'stroke-width': 5}, box);
  }
  $('rect', {x: x + 12, y: y + 12, width: w, height: h, fill: '#111'}, parent);
  return $('rect', {x, y, width: w, height: h, fill, stroke: '#111', 'stroke-width': 8}, parent);
}
const titleG = document.getElementById('title');
panel(titleG, 40, 40, 1000, 470, 'title');
if (TH === 'paper') $('polygon', {points: torn(70, 70, 940, 70, 10), fill: OFF, filter: 'url(#paper)'}, titleG);
if (TH === 'neon') $('rect', {x: 70, y: 70, width: 940, height: 70, rx: 14, fill: NH, opacity: .14}, titleG);
if (TH === 'comic') $('rect', {x: 70, y: 70, width: 940, height: 70, fill: OFFU.main, stroke: '#111', 'stroke-width': 6}, titleG);
fitText(text(titleG, 540, 120, S.title.kicker, 40, PAL.kicker, 'plain'), 900, 40);
const nameEl = text(titleG, 540, 330, S.title.name.toUpperCase(), 150, PAL.name);
fitText(nameEl, 900, Math.min(150, Math.floor(1700 / Math.max(6, S.title.name.length))));
const placeName = () => nameEl.setAttribute('y', 180 + Number(nameEl.getAttribute('font-size')) * .8);
placeName();
if (TH === 'neon') nameEl.setAttribute('filter', 'url(#neonText)');
if (TH === 'chalk') titleG.setAttribute('filter', 'url(#chalkText)');
text(titleG, 540, 380, S.title.tag, 42, PAL.tag, 'plain');
fitText(text(titleG, 540, 450, `${S.title.line}${S.title.when ? ' · ' + S.title.when : ''}`, 40, PAL.line, 'plain'), 920, 40);

const captionG = document.getElementById('caption');
panel(captionG, 60, 1400, 960, 210, 'caption');
const captionText = text(captionG, 540, 1530, '', 84, PAL.caption);
if (TH === 'chalk') captionText.setAttribute('filter', 'url(#chalkText)');

const footerG = document.getElementById('footer');
if (S.sponsor) { panel(footerG, 80, 1640, 640, 170, 'sponsor'); text(footerG, 400, 1682, 'BROUGHT TO YOU BY', 28, '#5b4b32', 'plain'); if (S.sponsor_logo) { const img = $('image', {x: 140, y: 1692, width: 520, height: 104, preserveAspectRatio: 'xMidYMid meet'}, footerG); img.setAttributeNS('http://www.w3.org/1999/xlink', 'href', S.sponsor_logo); img.setAttribute('href', S.sponsor_logo); } else fitText(text(footerG, 400, 1755, S.sponsor, 46, '#1b1b1b', 'plain'), 590, 46); }
const markX = S.sponsor ? 860 : 540;
if (S.station_logo) {
  const size = 164, left = markX - size / 2, top = 1643, style = S.logo_style;
  const clip = $('clipPath', {id: 'stationClip'}, footerG);
  if (style === 'round') $('circle', {cx: markX, cy: top + size / 2, r: size / 2}, clip);
  else $('rect', {x: left, y: top, width: size, height: size, rx: style === 'glass' ? 26 : 0}, clip);
  if (style === 'glass') {
    const sheen = $('linearGradient', {id: 'stationGlass', x1: 0, y1: 0, x2: .6, y2: 1}, footerG);
    $('stop', {offset: 0, 'stop-color': '#ffffff', 'stop-opacity': .55}, sheen);
    $('stop', {offset: 1, 'stop-color': '#ffffff', 'stop-opacity': .08}, sheen);
    $('rect', {x: left, y: top, width: size, height: size, rx: 26, fill: 'url(#stationGlass)', stroke: '#ffffff', 'stroke-opacity': .55, 'stroke-width': 2}, footerG);
  }
  const inset = style === 'glass' ? 14 : 0;
  const mark = $('image', {x: left + inset, y: top + inset, width: size - inset * 2, height: size - inset * 2, 'clip-path': 'url(#stationClip)',
    preserveAspectRatio: style === 'round' ? 'xMidYMid slice' : 'xMidYMid meet'}, footerG);
  mark.setAttribute('href', S.station_logo);
} else fitText(text(footerG, markX, 1735, S.station || '', 56, PAL.station), S.sponsor ? 300 : 800, 56);
text(footerG, 540, 1860, S.label, 30, PAL.label, 'plain');

const overlay = document.getElementById('overlay');
if (TH === 'comic') $('rect', {x: 0, y: 560, width: 1080, height: 800, fill: 'none', stroke: '#111', 'stroke-width': 14}, overlay);
if (TH === 'neon') $('rect', {x: 0, y: 560, width: 1080, height: 800, fill: 'none', stroke: NH, 'stroke-width': 5, opacity: .7}, overlay);
function burst(parent, cx, cy, rx, ry, spikes, fill) {
  const pts = [];
  for (let i = 0; i < spikes * 2; i++) { const a = i * Math.PI / spikes, r = i % 2 ? .72 : 1 + rnd() * .12; pts.push(`${(cx + Math.cos(a) * rx * r).toFixed(1)},${(cy + Math.sin(a) * ry * r).toFixed(1)}`); }
  return $('polygon', {points: pts.join(' '), fill, stroke: '#111', 'stroke-width': 8, 'stroke-linejoin': 'round'}, parent);
}
const bigWord = $('g', {opacity: 0}, overlay);
const word = kind === 'field_goal' ? "IT'S GOOD!" : (S.td ? 'TOUCHDOWN!' : (kind === 'interception' ? 'PICKED OFF!' : 'BIG PLAY!'));
if (TH === 'comic') burst(bigWord, 540, 695, 535, 175, 22, '#e8222b');
const scrawl = TH === 'chalk' ? $('ellipse', {cx: 540, cy: 690, rx: 520, ry: 122, fill: 'none', stroke: '#f7e27a', 'stroke-width': 8, pathLength: 100, 'stroke-dasharray': '100', 'stroke-dashoffset': 100, filter: 'url(#chalkText)'}, bigWord) : null;
const LETTER = {paper: 110, neon: 76, chalk: 96, comic: 134}[TH];
const letters = [...word].map((ch, i) => {
  const g = $('g', TH === 'neon' ? {filter: 'url(#neonText)'} : TH === 'chalk' ? {filter: 'url(#chalkText)'} : TH === 'paper' ? {filter: 'url(#cut)'} : {}, bigWord);
  const w = ch === ' ' ? 0 : 86;
  if (TH === 'paper' && w) $('rect', {x: -43, y: -70, width: 86, height: 120, fill: i % 2 ? OFF : '#fffdf6', transform: `rotate(${(rnd() - .5) * 18})`}, g);
  const fill = {paper: i % 2 ? ink(OFF) : '#1b1b1b', neon: i % 2 ? ND : NH, chalk: '#f7f6ef', comic: '#ffe01b'}[TH];
  const letter = text(g, 0, 30, ch, LETTER, fill);
  if (TH === 'comic') inked(letter, '#111', 12);
  return g;
});
const CONFETTI = {paper: [OFF, OFF2, '#f6c915', '#fffdf6'], neon: [NH, ND, '#ffffff', '#ffe45c'], chalk: ['#f2f1ea', '#f2f1ea', '#f7e27a', CH], comic: ['#e8222b', '#ffe01b', '#1f6fe0', '#ffffff']}[TH];
const confetti = [...Array(36)].map(() => { const small = TH === 'chalk' ? .45 : 1; const r = $('rect', {width: (18 + rnd() * 16) * small, height: (10 + rnd() * 8) * small, fill: CONFETTI[Math.floor(rnd() * 4)], opacity: 0}, overlay); r._x = rnd() * 1080; r._v = 260 + rnd() * 260; r._s = (rnd() - .5) * 600; return r; });
// comic book sound effects, one at a time; none are aimed at a player
const SFX = TH !== 'comic' ? [] : [[T_SNAP, .6, 'HUT!', 260, 690, 170]]
  .concat(kind === 'field_goal' ? [[T_RUN, .9, 'BOOM!', 330, 760, 210]]
    : (AIR ? [[T_RUN, .8, kind.endsWith('_return') ? 'GOT IT!' : 'SNAG!', 760, 720, 200]] : [])
      .concat([[T_RUN + Math.max(.9, RUN * .35), .9, 'ZOOM!', 770, 1180, 210]]))
  .map(([at, long, say, x, y, size]) => { const g = $('g', {opacity: 0}, overlay); burst(g, 0, 0, size, size * .62, 12, '#ffe01b'); inked(text(g, 0, size * .17, say, size * .52, '#e8222b'), '#111', 6); return {at, long, g, x, y}; });
const endG = $('g', {opacity: 0}, overlay);
panel(endG, 90, 820, 900, 300, 'score');
text(endG, 540, 920, S.score_after ? 'SCORE' : (S.td ? 'TOUCHDOWN' : 'BIG PLAY'), 56, PAL.scoreHead, 'plain');
const lines = (S.score_after || `${S.title.name} · ${S.title.line}`).split(', ');
lines.forEach((l, i) => fitText(text(endG, 540, 1010 + i * 80, l.toUpperCase(), 64, PAL.score), 820, 64));

function ballAt(t) {
  const h = heroPath(t);
  let bx = h.x + .8, by = h.y - 86, brot = 0;
  if (kind === 'pass' && t < T_RUN) { const q = passer ? passerX(t) : G.los - 6; if (t < T_AIR) { bx = q + .5; by = lane(2.6) - 100; } else { const p = clamp01((t - T_AIR) / AIR); bx = q + (G.catch - q) * p; by = (lane(2.6) - 100) + (h.y - 95 - (lane(2.6) - 100)) * p - Math.sin(p * Math.PI) * 260; brot = t * 900; } }
  if (kind === 'interception' && t < T_RUN) { const q = G.catch + 14; if (t < T_AIR) { bx = q; by = lane(2) - 100; } else { const p = clamp01((t - T_AIR) / AIR); bx = q + (G.catch - q) * p; by = lane(2) - 100 - Math.sin(p * Math.PI) * 240; brot = -t * 900; } }
  if (kind.endsWith('_return') && t < T_RUN) { const q = G.los; if (t < T_AIR) { bx = q; by = lane(2.4) - 30; } else { const p = clamp01((t - T_AIR) / AIR); bx = q + (G.catch - q) * p; by = lane(2.4) - 30 - Math.sin(p * Math.PI) * 420; brot = -t * 700; } }
  if (kind === 'field_goal') { if (t < T_RUN) { bx = G.start + .3; by = lane(2.6) - 10; } else { const p = clamp01((t - T_RUN) / RUN); bx = G.start + (110 - G.start) * p; by = lane(2.6) - 10 - Math.sin(p * Math.PI * .9) * 520 - p * 120; brot = t * 600; } }
  return {bx, by, brot};
}
// the chalk arrow follows the runner, a dotted line follows a throw or kick
function chalkLines(t) {
  const points = [];
  if (kind !== 'field_goal') for (let s = kind === 'run' ? T_AIR : T_RUN; s <= Math.min(t, T_FIN); s += 1 / 12) { const q = heroPath(s); points.push([X(q.x), q.y - 40]); }
  let d = points.length > 1 ? 'M ' + points.map(q => q.map(v => v.toFixed(1)).join(' ')).join(' L ') : '';
  if (points.length > 2) { const [ax, ay] = points[points.length - 3], [bx, by] = points[points.length - 1], a = Math.atan2(by - ay, bx - ax); const wing = o => `${(bx - Math.cos(a + o) * 34).toFixed(1)} ${(by - Math.sin(a + o) * 34).toFixed(1)}`; d += ` M ${wing(.55)} L ${bx.toFixed(1)} ${by.toFixed(1)} L ${wing(-.55)}`; }
  trail.setAttribute('d', d);
  const air = [];
  if (AIR || kind === 'field_goal') { const end = kind === 'field_goal' ? T_FIN : T_RUN; const from = kind === 'field_goal' ? T_RUN : T_AIR; for (let s = from; s <= Math.min(t, end); s += 1 / 12) { const b = ballAt(s); air.push(`${X(b.bx).toFixed(1)} ${b.by.toFixed(1)}`); } }
  throwLine.setAttribute('d', air.length > 1 ? 'M ' + air.join(' L ') : '');
}

// -- one frame ------------------------------------------------------------------------
window.drawFrame = function (time) {
  const t = Math.floor(time * 12) / 12;   // on twos: 12 drawings a second
  const h = heroPath(t);
  // the ball: carried, thrown or kicked
  let {bx, by, brot} = ballAt(t);
  endZoneName.setAttribute('opacity', t >= T_FIN ? 0 : 1);
  const dance = t >= T_FIN + .35 ? dancePose(t) : null;
  const danceX = kind === 'field_goal' ? G.start + 1 : h.x;
  camera = cameraFor(bx);
  if (t >= T_FIN) { const m = ease((t - T_FIN) / .5); camera = clampCamera(camera + (X(danceX) - 540 - camera) * m); }
  // the ball comes down at the start of the finish and stays on the turf
  if (t >= T_FIN && kind !== 'field_goal') { const m = clamp01((t - T_FIN) / .3); bx = danceX + 3.1; by = (h.y - 86) + (lane(3.55) - 14 - (h.y - 86)) * m - Math.abs(Math.sin(m * Math.PI * 2)) * 40 * (1 - m); brot = 75 * m; }
  if (kind === 'field_goal' && t >= T_FIN) { bx = -50; }
  fieldWorld.setAttribute('transform', `translate(${-camera.toFixed(1)} 0)`);
  // offense line and the hero
  // blockers: on the line for a snap; on a return they set up a wall in front of the returner
  const wallX = kind.endsWith('_return') ? G.catch + 9 : G.los - 1;
  offense.forEach((f, i) => { const jostle = t > T_SNAP ? Math.sin(t * 9 + i) * .3 : 0; place(f, wallX + jostle + (kind.endsWith('_return') ? (i % 2) * 2 : (i % 2) * -.9), lane(i + (i > 1 ? 1.2 : 0)), 0, t, false, i); });
  const heroRunning = t >= T_RUN || (kind === 'pass' && t > T_AIR - .4) || (kind === 'run' && t > T_AIR);
  const tackled = !S.td && kind !== 'field_goal' && t > T_FIN;
  const carrying = kind !== 'field_goal' && t >= T_RUN && t < T_FIN ? {armF: -68} : {};
  if (dance) { const dy = dance.dy || 0; place(hero, danceX + (dance.dx || 0), lane(3.55) + dy, 0, t, false, 20, {scale: 1.5, ...dance}); }
  else place(hero, h.x, h.y, tackled && t < T_FIN + .35 ? -70 : (kind === 'field_goal' && t > T_RUN - .2 && t < T_RUN + .4 ? -18 : 0), t, heroRunning && !tackled && t < T_FIN, 20, carrying);
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
  stackActors();
  ball.setAttribute('transform', `translate(${(X(bx) - camera).toFixed(1)} ${by.toFixed(1)}) rotate(${brot % 360}) scale(1.2)`);
  if (TH === 'chalk') chalkLines(t);
  const racing = (TH === 'neon' || TH === 'comic') && kind !== 'field_goal' && t >= T_RUN && t < T_FIN;
  streaks.forEach((r, i) => { r.setAttribute('opacity', racing ? 1 : 0); if (!racing) return; const long = 170 + noise(i + 70, t) * 240, sx = X(h.x) - camera - 70 - i % 2 * 30; r.setAttribute('x', sx - long); r.setAttribute('width', long); r.setAttribute('y', h.y - 30 - i * 40); });
  floorRing.setAttribute('opacity', TH === 'neon' && dance ? .8 : 0);
  if (TH === 'neon' && dance) { floorRing.setAttribute('cx', X(danceX + (dance.dx || 0)) - camera); floorRing.setAttribute('cy', lane(3.55)); floorRing.setAttribute('rx', 200 + noise(5, t) * 50); }
  SFX.forEach(fx => { const age = t - fx.at, on = age >= 0 && age < fx.long; fx.g.setAttribute('opacity', on ? 1 : 0); if (on) fx.g.setAttribute('transform', `translate(${fx.x} ${fx.y}) rotate(-7) scale(${(1 + Math.max(0, .2 - age) * 2.4).toFixed(2)})`); });
  // captions by phase
  // the 'action' caption waits for the catch on passes, picks and kicks
  const phase = t < (AIR ? T_RUN : T_AIR) ? 'setup' : (t < T_FIN ? 'action' : 'finish');
  const cap = (S.captions.find(c => c.phase === phase) || {}).text || '';
  captionText.textContent = cap;
  fitText(captionText, 880, cap.length > 22 ? 64 : 84, true);
  captionText.setAttribute('transform', `rotate(${((noise(99, t) - .5) * 2).toFixed(2)} 540 1510)`);
  // the big word, letter by letter, then confetti
  const celebrate = t >= T_FIN && t < T_END;
  bigWord.setAttribute('opacity', celebrate ? 1 : 0);
  if (scrawl) scrawl.setAttribute('stroke-dashoffset', (100 * (1 - clamp01((t - T_FIN - .9) * 2.2))).toFixed(1));
  letters.forEach((g, i) => { const shown = clamp01((t - T_FIN) * 12 - i); const lx = 540 + (i - (letters.length - 1) / 2) * 92; const pop = 1 + (1 - shown) * .6; g.setAttribute('opacity', TH === 'neon' && t - T_FIN < .7 && noise(i + 40, t) < .3 ? shown * .25 : shown); g.setAttribute('transform', `translate(${lx} ${690 + Math.sin(i * 1.7) * 14}) rotate(${((noise(i + 200, t) - .5) * 10).toFixed(1)}) scale(${pop})`); });
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
window.reelReady = (document.fonts ? document.fonts.ready : Promise.resolve()).then(() => { fitted.forEach(([el, width, size]) => fitText(el, width, size, true)); placeName(); window.drawFrame(0); return true; });
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

    # Fast start (the index at the front, as Facebook asks for) needs a real file to rewrite.
    workspace = tempfile.TemporaryDirectory(prefix="csrn-reel-")
    target = Path(workspace.name) / "reel.mp4"
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True) if launch is None else launch(playwright)
        try:
            page_ = browser.new_page(viewport={"width": WIDTH, "height": HEIGHT})
            page_.set_content(document, wait_until="load")
            page_.wait_for_function("window.drawFrame !== undefined && window.REEL_DURATION > 0")
            page_.evaluate("window.reelReady")
            duration = float(page_.evaluate("window.REEL_DURATION"))
            container = av.open(str(target), mode="w", format="mp4", options={"movflags": "+faststart"})
            stream = container.add_stream("libx264", rate=VIDEO_FPS)
            stream.width, stream.height, stream.pix_fmt = WIDTH, HEIGHT, "yuv420p"
            stream.options = {"crf": "21", "preset": "veryfast"}
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
    try:
        return target.read_bytes()
    finally:
        workspace.cleanup()
