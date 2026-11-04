"""Basketball reels: a half court drawn to the real shot geometry, with five players a side.

The page shares the football reel's themes, colours, title, captions and big word
(cut out of reel_render.PAGE, so a change there shows up here). The floor, the
players and the motion are basketball's own. Generic players are team colours all
over with a dark visor, so no skin shows and nothing suggests who a figure is. A
player's own head only appears when the operator has given them a reel headshot
and asked for heads on this reel.
"""
from __future__ import annotations

import json
from typing import Any, Mapping

from reel_render import DANCE_MOVES, PAGE

TIMING_MARK = "// -- timing"
FIGURES_MARK = "// -- paper figures"
FOOTBALL_FIGURE_MARK = "function figure(kit"
OVERLAY_MARK = "// -- the overlay"
WORD_MARK = "const word = kind ==="
LETTERS_MARK = "const LETTER ="
EFFECTS_MARK = "// comic book sound"
SCORE_PANEL_MARK = "const endG ="
FOOTBALL_BALL_MARK = "function ballAt"
READY_MARK = "window.reelReady ="

COURT = r"""
// -- timing ---------------------------------------------------------------------
const kind = S.kind, jumpShot = kind === 'three' || kind === 'jumper', atRim = kind === 'layup' || kind === 'dunk';
const INTRO = 1.5, PASS = S.helper ? .7 : 0, MOVE = atRim ? 1.0 : (kind === 'block' || kind === 'steal' ? .9 : .5);
const FLIGHT = kind === 'three' ? 1.05 : (kind === 'jumper' ? .85 : (kind === 'dunk' ? .25 : (kind === 'layup' ? .4 : .3)));
const T_PASS = INTRO, T_MOVE = T_PASS + PASS, T_SHOT = T_MOVE + MOVE, T_FIN = T_SHOT + FLIGHT, FINISH = 3.6, END = 2.3, T_END = T_FIN + FINISH;
window.REEL_DURATION = T_END + END;
const T_RUN = T_MOVE, AIR = 0;

// -- the floor: real court measurements, 42 feet of it, seen from the side ----------
const FIELD_LEFT_FT = 40, FT_X = 1080 / 44, FLOOR_TOP = 690, FT_Y = 12.4;
const CX = x => (x - FIELD_LEFT_FT) * FT_X, CY = y => FLOOR_TOP + y * FT_Y;
const field = document.getElementById('field');
const backdrop = document.getElementById('backdrop');
const RIM_FLOOR = {x: CX(S.rim.x), y: CY(S.rim.y)}, RIM = {x: RIM_FLOOR.x, y: RIM_FLOOR.y - 305};
function courtPath() {
  let arc = `M ${CX(84)} ${CY(5.25)} L ${CX(S.rim.x - Math.sqrt(19.75 * 19.75 - (25 - 5.25) ** 2))} ${CY(5.25)}`;
  for (let a = -90 + 3; a <= 90; a += 3) { const r = a * Math.PI / 180; const x = S.rim.x - Math.cos(r) * 19.75, y = S.rim.y + Math.sin(r) * 19.75; if (y >= 5.25 && y <= 44.75) arc += ` L ${CX(x).toFixed(1)} ${CY(y).toFixed(1)}`; }
  arc += ` L ${CX(84)} ${CY(44.75)}`;
  const lane = `M ${CX(84)} ${CY(19)} L ${CX(65)} ${CY(19)} L ${CX(65)} ${CY(31)} L ${CX(84)} ${CY(31)}`;
  const ring = (cx, r) => { let d = ''; for (let a = 0; a <= 360; a += 10) { const q = a * Math.PI / 180; d += `${a ? 'L' : 'M'} ${CX(cx + Math.cos(q) * r).toFixed(1)} ${CY(25 + Math.sin(q) * r).toFixed(1)} `; } return d; };
  return {arc, lane, top: ring(65, 6), centre: ring(42, 6), edge: `M ${CX(42)} ${CY(0)} L ${CX(84)} ${CY(0)} L ${CX(84)} ${CY(50)} L ${CX(42)} ${CY(50)} Z`};
}
const FLOORS = {
  paper: {boards: '#d9a860', plank: '#c4924c', line: '#fbf7e8', paint: OFFU.main, paintOpacity: .55, width: 8},
  neon: {boards: '#070a1c', plank: '#10163a', line: '#9fe8ff', paint: NH, paintOpacity: .16, width: 5},
  chalk: {boards: '#22342d', plank: 'none', line: '#f2f1ea', paint: CH, paintOpacity: .12, width: 7},
  comic: {boards: '#ffb54a', plank: '#e8983a', line: '#ffffff', paint: OFFU.main, paintOpacity: 1, width: 10},
}[TH];
if (TH === 'neon') { backdrop.setAttribute('fill', '#05060f'); backdrop.removeAttribute('filter'); }
if (TH === 'chalk') { backdrop.setAttribute('fill', '#20302a'); backdrop.removeAttribute('filter'); field.setAttribute('filter', 'url(#chalkField)'); }
if (TH === 'comic') { backdrop.setAttribute('fill', 'url(#comicPage)'); backdrop.removeAttribute('filter'); }
$('rect', {x: 0, y: FIELD_TOP, width: 1080, height: FIELD_H, fill: TH === 'paper' ? '#4c6b42' : FLOORS.boards}, field);
$('rect', {x: 0, y: FLOOR_TOP - 16, width: 1080, height: FIELD_TOP + FIELD_H - FLOOR_TOP + 16, fill: FLOORS.boards, filter: TH === 'paper' ? 'url(#paper)' : 'none'}, field);
if (FLOORS.plank !== 'none') for (let y = FLOOR_TOP; y < FIELD_TOP + FIELD_H; y += 44) $('rect', {x: 0, y, width: 1080, height: 3, fill: FLOORS.plank}, field);
const court = courtPath();
const stroke = {fill: 'none', stroke: FLOORS.line, 'stroke-width': FLOORS.width, 'stroke-linejoin': 'round'};
if (TH === 'comic') { const outline = {fill: 'none', stroke: '#111', 'stroke-width': FLOORS.width + 7}; [court.edge, court.arc, court.lane, court.top, court.centre].forEach(d => $('path', {d, ...outline}, field)); }
$('path', {d: court.lane + ' Z', fill: FLOORS.paint, opacity: FLOORS.paintOpacity}, field);
[court.edge, court.arc, court.lane, court.top, court.centre].forEach(d => { if (TH === 'neon') $('path', {d, ...stroke, 'stroke-width': 16, opacity: .18}, field); $('path', {d, ...stroke}, field); });
const courtName = text(field, 300, FIELD_TOP + 80, (S.offense.name || '').toUpperCase(), 60, TH === 'paper' ? '#fbf7e8' : (TH === 'neon' ? NH : (TH === 'comic' ? '#111' : CH)));
fitText(courtName, 500, 60);
// the goal: a pole on the baseline, the backboard, and the rim above the floor
const goal = $('g', TH === 'paper' ? {filter: 'url(#drop)'} : {}, field);
const steel = {paper: '#54585e', neon: '#ffe45c', chalk: '#f7e27a', comic: '#111'}[TH];
$('path', {d: `M ${RIM.x + 82} ${RIM_FLOOR.y + 30} V ${RIM.y - 30} H ${RIM.x + 42}`, fill: 'none', stroke: steel, 'stroke-width': 18}, goal);
$('rect', {x: RIM.x + 30, y: RIM.y - 110, width: 18, height: 150, fill: TH === 'chalk' || TH === 'neon' ? 'none' : '#fffdf6', stroke: steel, 'stroke-width': 6}, goal);
const netG = $('g', {}, field);
const netPath = $('path', {fill: 'none', stroke: TH === 'paper' ? '#fffdf6' : (TH === 'comic' ? '#111' : FLOORS.line), 'stroke-width': 4}, netG);
const rimFront = $('ellipse', {cx: RIM.x, cy: RIM.y, rx: 34, ry: 9, fill: 'none', stroke: '#e8541c', 'stroke-width': 8}, netG);
function drawNet(sway) { const w = 30, h = 46 + sway * 14, nx = RIM.x, ny = RIM.y + 5; let d = ''; for (let i = -2; i <= 2; i++) d += `M ${nx + i * w / 2.2} ${ny} L ${nx + i * (w / 3.6) + sway * 7 * i} ${ny + h} `; for (let row = 1; row < 3; row++) d += `M ${nx - w * (1 - row * .16)} ${ny + h * row / 3} L ${nx + w * (1 - row * .16)} ${ny + h * row / 3} `; netPath.setAttribute('d', d); }
drawNet(0);
"""

PLAYERS = r"""
// -- players: a tank top and shorts over team-colored long sleeves and tights, sneakers, gloves
function hoopLegNear(rig) {
  const g = pivot(rig, 300, 610);
  $('path', cut({d: 'M 178 712 L 268 742 L 244 794 L 160 782 Z', fill: K.sleeve}), g);
  $('path', cut({d: 'M 240 590 L 362 622 L 342 682 L 262 748 L 172 716 C 188 680 214 640 240 590 Z', fill: K.sleeve}), g);
  $('path', cut({d: 'M 232 586 L 368 618 L 344 690 L 206 656 Z', fill: K.pants}), g);                     // shorts
  $('path', cut({d: 'M 158 778 C 136 792 128 826 138 848 L 340 852 C 356 816 318 800 272 792 L 244 786 Z', fill: K.cleat}), g);
  $('path', {d: 'M 138 848 L 340 852', stroke: '#f4f1e8', 'stroke-width': 14, 'stroke-linecap': 'round'}, g);
  return g;
}
function hoopLegFar(rig) {
  const g = pivot(rig, 440, 610);
  $('path', cut({d: 'M 420 728 L 526 706 L 522 768 L 428 794 Z', fill: K.sleeve}), g);
  $('path', cut({d: 'M 362 668 L 500 592 L 536 704 L 424 732 C 418 706 396 688 362 668 Z', fill: K.sleeve}), g);
  $('path', cut({d: 'M 356 660 L 496 586 L 526 668 L 392 716 Z', fill: K.pants}), g);
  $('path', cut({d: 'M 426 790 C 410 806 406 830 416 846 L 610 840 C 628 806 580 786 532 776 L 520 766 Z', fill: K.cleat}), g);
  $('path', {d: 'M 416 846 L 610 840', stroke: '#f4f1e8', 'stroke-width': 14, 'stroke-linecap': 'round'}, g);
  return g;
}
function hoopArmFar(rig) {
  const g = pivot(rig, 500, 440);
  $('path', cut({d: 'M 482 426 L 536 430 C 556 500 578 560 596 612 L 540 642 C 520 580 496 500 482 426 Z', fill: K.sleeve}), g);
  $('path', cut({d: 'M 538 628 C 524 654 540 684 572 680 C 604 672 610 632 590 604 Z', fill: K.glove}), g);
  return g;
}
function hoopArmNear(rig) {
  const g = pivot(rig, 250, 440);
  $('path', cut({d: 'M 216 420 L 286 440 C 262 480 226 530 206 580 L 120 560 C 134 510 170 456 216 420 Z', fill: K.sleeve}), g);
  $('path', cut({d: 'M 122 552 C 98 580 98 636 130 656 C 164 670 196 652 202 624 L 216 612 C 218 596 206 590 206 576 Z', fill: K.glove}), g);
  return g;
}
function hoopFigure(kit, number, facing, role, head) {
  K = kit;
  if (TH === 'chalk') return chalkFigure(number, facing, role);
  const g = $('g', kit.filter ? {filter: kit.filter} : {}, actors);
  const inner = $('g', {}, g);
  const rig = $('g', {transform: 'scale(.287) translate(-360 -860)'}, inner);
  const legB = hoopLegFar(rig), legF = hoopLegNear(rig), armB = hoopArmFar(rig);
  $('path', cut({d: 'M 236 570 L 508 566 L 516 640 L 372 676 L 228 628 Z', fill: K.pants}), rig);
  const torso = pivot(rig, 370, 600);
  $('path', cut({d: 'M 256 410 L 504 432 L 520 472 L 500 590 Q 360 618 238 586 Z', fill: K.base}), torso);
  $('path', {d: 'M 340 414 L 402 470 L 462 428', fill: K.mask}, torso);
  const num = text(torso, 382, 572, number || '', number && number.length > 1 ? 130 : 150, K.num, 'jersey');
  const armF = hoopArmNear(rig);
  const headG = pivot(rig, 370, 420);
  let face = null;
  if (head) {
    face = $('g', {}, headG);
    const h = 560, w = h * .82;
    $('image', {href: head, x: 370 - w / 2, y: -150, width: w, height: h, preserveAspectRatio: 'xMidYMax meet'}, face);
  } else {
    $('path', cut({d: 'M 262 400 C 214 300 240 120 372 110 C 508 112 536 300 484 404 C 430 436 316 432 262 400 Z', fill: K.base}), headG);
    $('path', {d: 'M 238 196 C 310 166 438 168 512 198 L 514 240 C 438 212 312 210 236 240 Z', fill: K.trim}, headG);   // headband
    $('path', cut({d: 'M 262 270 C 330 250 430 250 496 272 L 486 330 C 430 346 330 346 270 328 Z', fill: K.mask}), headG);  // dark visor
  }
  return {g, inner, torso, head: headG, legF, legB, armF, armB, num, numX: 382, face, facing};
}
const [MINE, THEIRS] = KITS[TH];
const FOUNDS = [[72, 9], [72, 41], [58, 13], [58, 37], [52, 25], [74, 25]];
const spot = S.spot, spots = FOUNDS.slice().sort((a, b) => Math.hypot(b[0] - spot.x, b[1] - spot.y) - Math.hypot(a[0] - spot.x, a[1] - spot.y));
const heroF = hoopFigure(MINE, S.hero.number, 1, 'hero', S.hero.head);
const helperF = S.helper ? hoopFigure(MINE, S.helper.number, 1, '', S.helper.head) : null;
const helperAt = S.helper ? spots[0] : null;
const taken = helperAt ? 1 : 0;
const mates = [...Array(helperF ? 3 : 4)].map((_, i) => { const who = S.teammates[i] || {number: ''}; const at = spots[(taken + i) % spots.length]; return {f: hoopFigure(MINE, who.number, 1, 'block', who.head), x: at[0], y: at[1]}; });
const facing = (kind === 'block' || kind === 'steal') ? [{number: S.other_number}, ...S.opponents] : S.opponents;
const defenders = [...Array(5)].map((_, i) => { const who = facing[i] || {number: ''}; return {f: hoopFigure(THEIRS, who.number, -1), i}; });
function ballShape(parent) {
  const looks = {paper: ['#e8772e', '#7a3e1a', 3], neon: ['#2a1405', '#ffb347', 5], chalk: ['none', '#f7e27a', 5], comic: ['#f28a2e', '#111', 6]}[TH];
  const g = $('g', TH === 'paper' ? {filter: 'url(#drop)'} : {}, parent);
  $('circle', {r: 23, fill: looks[0], stroke: looks[1], 'stroke-width': looks[2]}, g);
  $('path', {d: 'M -23 0 H 23 M 0 -23 V 23 M -16 -16 Q -6 0 -16 16 M 16 -16 Q 6 0 16 16', fill: 'none', stroke: looks[1], 'stroke-width': 3}, g);
  return g;
}
const ball = ballShape(actors);
"""

MOTION = r"""
// -- motion -----------------------------------------------------------------------
const ease = p => p < 0 ? 0 : p > 1 ? 1 : p * p * (3 - 2 * p);
const clamp01 = p => Math.max(0, Math.min(1, p));
function turn(el, angle) { el.setAttribute('transform', `rotate(${angle} ${el._pivot[0]} ${el._pivot[1]})`); }
function place(f, sx, y, rot, t, running, idx, pose) {
  const boil = (noise(idx, t) - .5) * 2.4, p = pose || {};
  const scale = p.scale || (TH === 'chalk' ? 1.1 : .8);
  const flip = (p.flip ?? 1) * f.facing;
  f.g.setAttribute('transform', `translate(${sx.toFixed(1)} ${(y + (p.lift || 0)).toFixed(1)}) rotate(${(rot + boil).toFixed(2)}) scale(${scale})`);
  f.inner.setAttribute('transform', `scale(${flip} 1)`);
  f.num.setAttribute('transform', `translate(${f.numX} 0) scale(${flip < 0 ? -1 : 1} 1) translate(${-f.numX} 0)`);
  if (f.face) f.face.setAttribute('transform', `translate(370 0) scale(${flip < 0 ? -1 : 1} 1) translate(-370 0)`);
  if (f.limbs) f.limbs.setAttribute('display', p.scale > 1 ? 'inline' : 'none');
  const stride = running ? (Math.floor(t * 12) % 2 ? 1 : -1) : 0;
  turn(f.legF, p.legF ?? 20 * stride);
  turn(f.legB, p.legB ?? -20 * stride);
  turn(f.armF, p.armF ?? (running ? 28 * stride : 0));
  turn(f.armB, p.armB ?? (running ? 28 * stride : 0));
  turn(f.torso, p.torso ?? (running ? 4 : 0));
  turn(f.head, p.head ?? 0);
  f._y = y;
}
const DANCES = __DANCES__;
function dancePose(t) { const name = DANCES[S.dance] ? S.dance : 'fistpump'; return DANCES[name](Math.max(0, Math.floor((t - T_FIN - .35) * 3.4))); }
// Where the hero stands, in feet. A drive ends under the rim; a block waits between the shooter and the rim.
const start = spot, finish = atRim ? {x: S.rim.x - 2.5, y: S.rim.y + 1.5} : spot;
const guard = kind === 'block' ? {x: spot.x + (S.rim.x - spot.x) * .3, y: spot.y + (S.rim.y - spot.y) * .3} : (kind === 'steal' ? {x: spot.x - 5, y: spot.y + 6} : null);
function heroFeet(t) {
  if (guard) { const p = ease((t - T_MOVE) / MOVE); const from = {x: guard.x + 3, y: guard.y + 4}; return {x: from.x + (guard.x - from.x) * p, y: from.y + (guard.y - from.y) * p}; }
  if (atRim) { const p = ease((t - T_MOVE) / MOVE); return {x: start.x + (finish.x - start.x) * p, y: start.y + (finish.y - start.y) * p}; }
  return spot;
}
const shooterF = (kind === 'block' || kind === 'steal') ? defenders[0] : null;
function arc(from, to, p, height) { return {x: from.x + (to.x - from.x) * p, y: from.y + (to.y - from.y) * p - Math.sin(p * Math.PI) * height}; }
function ballAt(t, hx, hy, airborne) {
  const hand = {x: hx + 26, y: hy - 120 + airborne};
  const dribble = {x: hx + 34, y: hy - 18 - Math.abs(Math.sin(t * 7)) * 50};
  if (kind === 'block') {
    const sx = CX(spot.x), sy = CY(spot.y), release = {x: sx + 20, y: sy - 170};
    if (t < T_SHOT) return {x: sx + 30, y: sy - 18 - Math.abs(Math.sin(t * 7)) * 50};
    if (t < T_FIN) return arc(release, {x: hx + 10, y: hy - 200}, clamp01((t - T_SHOT) / FLIGHT), 40);
    const age = t - T_FIN; return age > .8 ? {x: -80, y: 0} : {x: hx + 10 - age * 900, y: hy - 200 + age * age * 500 - age * 200};
  }
  if (kind === 'steal') {
    const sx = CX(spot.x), sy = CY(spot.y);
    if (t < T_SHOT) return {x: sx + 30, y: sy - 18 - Math.abs(Math.sin(t * 7)) * 50};
    if (t < T_FIN) return arc({x: sx + 30, y: sy - 40}, {x: hx + 20, y: hy - 90}, clamp01((t - T_SHOT) / FLIGHT), 20);
    return {x: hx + 34, y: hy - 18 - Math.abs(Math.sin(t * 7)) * 50};
  }
  if (S.helper && t < T_MOVE) {
    const from = {x: CX(helperAt[0]) + 26, y: CY(helperAt[1]) - 110};
    if (t < T_PASS) return {x: CX(helperAt[0]) + 34, y: CY(helperAt[1]) - 18 - Math.abs(Math.sin(t * 7)) * 50};
    return arc(from, {x: CX(start.x) + 20, y: CY(start.y) - 90}, (t - T_PASS) / PASS, 26);
  }
  if (t < T_SHOT) return dribble;
  if (t < T_FIN) return arc(hand, {x: RIM.x, y: RIM.y - 18}, clamp01((t - T_SHOT) / FLIGHT), kind === 'three' ? 210 : (kind === 'jumper' ? 150 : 50));
  const age = t - T_FIN;   // through the net and down to the floor
  const drop = Math.min(RIM_FLOOR.y - 24, RIM.y + age * 900);
  return {x: RIM.x - age * 18, y: drop - (drop >= RIM_FLOOR.y - 25 ? Math.abs(Math.sin(age * 8)) * 70 * Math.max(0, 1 - age * .6) : 0)};
}
function stackActors() {
  const all = [heroF, helperF, ...mates.map(m => m.f), ...defenders.map(d => d.f)].filter(Boolean).sort((a, b) => a._y - b._y);
  all.forEach(f => actors.appendChild(f.g));
  actors.appendChild(ball);
}
const pc = p => ({x: CX(p.x), y: CY(p.y)});
const men = [null, ...(helperAt ? [{x: helperAt[0], y: helperAt[1]}] : []), ...mates.map(m => ({x: m.x, y: m.y}))];
window.drawFrame = function (time) {
  const t = Math.floor(time * 12) / 12;
  const feet = heroFeet(t), h = pc(feet);
  const dance = t >= T_FIN + .35 ? dancePose(t) : null;
  // the hero
  let shooting = jumpShot && t >= T_SHOT - .15 && t < T_SHOT + .45;
  const rising = atRim && t >= T_SHOT - .3 && t < T_FIN + .25;
  const swatting = kind === 'block' && t >= T_FIN - .3 && t < T_FIN + .3;
  const lift = shooting ? -46 * Math.sin(clamp01((t - T_SHOT + .15) / .6) * Math.PI) : (rising ? (kind === 'dunk' ? -190 : -110) * Math.sin(clamp01((t - T_SHOT + .3) / (FLIGHT + .55)) * Math.PI) : (swatting ? -120 * Math.sin(clamp01((t - T_FIN + .3) / .6) * Math.PI) : 0));
  const reach = {armF: 160, armB: -150, legF: 14, legB: -14};
  const moving = (atRim && t >= T_MOVE && t < T_SHOT - .3) || (guard && t >= T_MOVE && t < T_SHOT);
  if (dance) {
    const cx = 540 + (dance.dx || 0);
    place(heroF, cx, 1280, 0, t, false, 20, {scale: 1.45, ...dance});
  } else place(heroF, h.x, h.y, 0, t, moving, 20, {lift, ...((shooting || rising || swatting) ? reach : (t < T_SHOT && !guard ? {armF: -40} : {}))});
  if (helperF) {
    const passing = t >= T_PASS - .2 && t < T_PASS + .25;
    place(helperF, CX(helperAt[0]), CY(helperAt[1]), 0, t, false, 21, passing ? {armF: 95} : (t >= T_FIN + .2 && !dance ? {armF: 140, armB: -130} : {}));
  }
  mates.forEach((m, i) => place(m.f, CX(m.x), CY(m.y), 0, t, false, 22 + i, t >= T_FIN + .2 ? {armF: 130, armB: -120} : {}));
  defenders.forEach(({f, i}) => {
    if (shooterF && i === 0) { place(f, CX(spot.x), CY(spot.y), 0, t, false, 30, kind === 'block' && t >= T_SHOT - .15 && t < T_FIN + .1 ? {...reach, lift: -40} : (kind === 'steal' && t > T_FIN ? {armF: 30} : {})); return; }
    // each one guards a player, a step toward the rim; the one on the ball closes out late
    const onBall = !shooterF && i === 0;
    const man = onBall ? feet : (men[i] || men[0]);
    const late = onBall ? clamp01((t - T_MOVE) / 1.2) : 1;
    const x = man.x + (S.rim.x - man.x) * .2 + (onBall ? 6 * (1 - late) : Math.sin(t * 2 + i) * .4), y = man.y + (S.rim.y - man.y) * .2 + 2.5;
    place(f, CX(x), CY(y), 0, t, onBall && t > T_MOVE && t < T_FIN, 30 + i, onBall && jumpShot && t >= T_SHOT - .1 && t < T_SHOT + .4 ? {armF: 150, armB: -140} : {});
  });
  stackActors();
  const airborne = lift;
  const b = ballAt(t, h.x, h.y, airborne);
  const held = dance && kind !== 'block' && kind !== 'steal' ? b : (dance && kind === 'steal' ? {x: 540 + 150, y: 1260} : b);
  ball.setAttribute('transform', `translate(${held.x.toFixed(1)} ${held.y.toFixed(1)}) rotate(${(t * 340 % 360).toFixed(0)}) scale(${kind === 'three' && t < T_FIN && t > T_SHOT ? 1.05 : 1})`);
  drawNet(t >= T_FIN && t < T_FIN + .5 && kind !== 'block' && kind !== 'steal' ? Math.sin((t - T_FIN) * 26) * (1 - (t - T_FIN) * 2) + 1 : 0);
  // words
  const phase = t < T_MOVE ? 'setup' : (t < T_FIN ? 'action' : 'finish');
  const cap = (S.captions.find(c => c.phase === phase) || {}).text || '';
  captionText.textContent = cap;
  fitText(captionText, 880, cap.length > 22 ? 64 : 84, true);
  captionText.setAttribute('transform', `rotate(${((noise(99, t) - .5) * 2).toFixed(2)} 540 1510)`);
  const celebrate = t >= T_FIN && t < T_END;
  courtName.setAttribute('opacity', t >= T_FIN ? 0 : 1);
  bigWord.setAttribute('opacity', celebrate ? 1 : 0);
  if (scrawl) scrawl.setAttribute('stroke-dashoffset', (100 * (1 - clamp01((t - T_FIN - .9) * 2.2))).toFixed(1));
  letters.forEach((g, i) => { const shown = clamp01((t - T_FIN) * 12 - i); const lx = 540 + (i - (letters.length - 1) / 2) * 92; const pop = 1 + (1 - shown) * .6; g.setAttribute('opacity', TH === 'neon' && t - T_FIN < .7 && noise(i + 40, t) < .3 ? shown * .25 : shown); g.setAttribute('transform', `translate(${lx} ${690 + Math.sin(i * 1.7) * 14}) rotate(${((noise(i + 200, t) - .5) * 10).toFixed(1)}) scale(${pop})`); });
  confetti.forEach((r, i) => { const age = t - T_FIN; if (age < 0) { r.setAttribute('opacity', 0); return; } r.setAttribute('opacity', 1); const y = 540 + age * r._v - 200 + (i % 6) * 40; r.setAttribute('transform', `translate(${(r._x + Math.sin(age * 3 + i) * 40).toFixed(1)} ${y.toFixed(1)}) rotate(${(age * r._s).toFixed(1)})`); });
  endG.setAttribute('opacity', t >= T_END ? 1 : 0);
  endG.setAttribute('transform', `rotate(${((noise(300, t) - .5) * 2).toFixed(2)} 540 960)`);
  actors.setAttribute('opacity', t >= T_END ? .35 : 1);
};
"""


def _between(start: str, end: str) -> str:
    return PAGE[PAGE.index(start):PAGE.index(end)]


def build_page() -> str:
    """The football page's shared pieces around basketball's own floor, players and motion."""
    return "".join((
        PAGE[:PAGE.index(TIMING_MARK)],
        COURT,
        _between(FIGURES_MARK, FOOTBALL_FIGURE_MARK),
        PLAYERS,
        _between(OVERLAY_MARK, WORD_MARK),
        "const word = S.word;\n",
        _between("if (TH === 'comic') burst(bigWord", LETTERS_MARK),
        _between(LETTERS_MARK, EFFECTS_MARK),
        _between(SCORE_PANEL_MARK, FOOTBALL_BALL_MARK),
        MOTION,
        PAGE[PAGE.index(READY_MARK):],
    )).replace("__DANCES__", DANCE_MOVES)


def page(script: Mapping[str, Any], font_uri: str = "") -> str:
    data = json.dumps(script).replace("</", "<\\/")
    return build_page().replace("__SCRIPT__", data).replace("__FONT__", font_uri)
