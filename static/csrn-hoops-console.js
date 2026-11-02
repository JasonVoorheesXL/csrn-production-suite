// CSRN basketball statistician console. Loaded after csrn-hoops-controls.js and
// shares its globals (currentState, api(), render(), escapeHtml(), hoopsState(),
// hoopsRosterPlayers(), clockAction(), setClockDialog(), openHoopsBoxScore()).
//
// The idea: tap where the shot was taken, then Made / Made +1 / Missed / Fouled and
// the shooter. It saves itself on the second pick. Anything after that (assist,
// rebound, tags) is one optional tap, and tapping the court again simply moves on,
// so one person can keep up with a live game.
//
// Spots are sent from the shooter's point of view; see hoops_shot_geometry.py.

const HC_COURT = { length: 84, width: 50, rimX: 78.75, rimY: 25, arc: 19.75, cornerY: 5.25 };
const HC_ZONE_NAMES = {
  rim: 'at the rim', paint: 'in the paint', mid_range: 'mid-range', top_three: 'top of the arc',
  left_wing_three: 'left wing', right_wing_three: 'right wing',
  left_corner_three: 'left corner', right_corner_three: 'right corner',
};
const HC_FOUL_TYPES = [['personal', 'Personal'], ['offensive', 'Offensive'], ['loose_ball', 'Loose ball'], ['technical', 'Technical'], ['intentional', 'Intentional'], ['flagrant_1', 'Flagrant']];
const HC_VIOLATIONS = [['traveling', 'Traveling'], ['double_dribble', 'Double dribble'], ['three_second', '3 seconds'], ['five_second', '5 seconds'], ['ten_second_backcourt', '10 seconds'], ['out_of_bounds', 'Out of bounds'], ['carry', 'Carrying'], ['kicked_ball', 'Kicked ball']];

let hc = hcFresh();
let hcToastData = null;
let hcHideMarks = false;
let hcDragging = false;
let hcStarters = { home: [], visitor: [] };

function hcFresh() {
  return { mode: 'idle', team: '', screen: null, points: 2, autoPoints: 2, result: '', shooter: '', shotType: '', targetId: '', fixId: '', ft: null, foulType: 'personal', foulFrom: null, subIn: '', subOut: '', subSide: '', benchCredit: null, afterSub: null, notes: {} };
}

// --- reading the game -------------------------------------------------------

function hcOther(team) { return team === 'home' ? 'visitor' : 'home'; }
function hcName(team) { return (team === 'home' ? currentState.home_team : currentState.visitor_team) || (team === 'home' ? 'Home' : 'Visitor'); }

function hcAttacks(team) {
  const base = hoopsState().home_first_half_attacks === 'left' ? 'left' : 'right';
  const firstHalf = ['1', '2'].includes(String(currentState.period || '1'));
  const home = firstHalf ? base : (base === 'right' ? 'left' : 'right');
  return team === 'home' ? home : (home === 'right' ? 'left' : 'right');
}

function hcToShooterView(team, screen) {
  return hcAttacks(team) === 'right' ? { x: screen.x, y: screen.y } : { x: HC_COURT.length - screen.x, y: HC_COURT.width - screen.y };
}

function hcIsThree(spot) {
  if (spot.y < HC_COURT.cornerY || spot.y > HC_COURT.width - HC_COURT.cornerY) return true;
  return Math.hypot(HC_COURT.rimX - spot.x, HC_COURT.rimY - spot.y) > HC_COURT.arc;
}

function hcZone(spot) {
  const dist = Math.hypot(HC_COURT.rimX - spot.x, HC_COURT.rimY - spot.y);
  if (hcIsThree(spot)) {
    if (spot.x >= HC_COURT.rimX - 8) return spot.y < HC_COURT.rimY ? 'left_corner_three' : 'right_corner_three';
    if (Math.abs(spot.y - HC_COURT.rimY) < 8) return 'top_three';
    return spot.y < HC_COURT.rimY ? 'left_wing_three' : 'right_wing_three';
  }
  if (dist <= 4.5) return 'rim';
  if (spot.x >= HC_COURT.length - 19 && Math.abs(spot.y - HC_COURT.rimY) <= 6) return 'paint';
  return 'mid_range';
}

function hcEvents() { return (hoopsState().hoops_events || []).filter(e => !e.voided); }

function hcStats() {
  const stats = {};
  const line = id => (stats[id] = stats[id] || { pts: 0, threes: 0, threeTries: 0 });
  hcEvents().forEach(e => {
    const p = e.payload || {};
    if (e.event_type === 'SHOT' && p.shooterId) {
      const row = line(p.shooterId);
      if (Number(p.points) === 3) row.threeTries += 1;
      if (p.made) { row.pts += Number(p.points || 2); if (Number(p.points) === 3) row.threes += 1; }
    } else if (e.event_type === 'FREE_THROW' && p.shooterId && p.made) {
      line(p.shooterId).pts += 1;
    }
  });
  return stats;
}

function hcRun() {
  let team = '', points = 0, other = 0;
  [...hcEvents()].reverse().some(e => {
    const p = e.payload || {};
    const scored = e.event_type === 'SHOT' && p.made ? Number(p.points || 2) : (e.event_type === 'FREE_THROW' && p.made ? 1 : 0);
    if (!scored) return false;
    if (!team) team = p.team;
    if (p.team !== team) { other = 1; return true; }
    points += scored;
    return false;
  });
  return { team, points, broken: other };
}

function hcPlayer(id) {
  for (const side of ['home', 'visitor']) {
    const found = hoopsRosterPlayers(side).find(p => p.id === id);
    if (found) return { ...found, side };
  }
  return null;
}
function hcLabel(id) {
  const p = hcPlayer(id);
  return p ? `#${p.number || '?'} ${p.last_name || p.first_name || ''}`.trim() : (id ? 'Player' : 'No name');
}
function hcClockText() {
  const sec = Math.max(0, Number(currentState?.clock_seconds ?? 0));
  return `${Math.floor(sec / 60)}:${String(sec % 60).padStart(2, '0')}`;
}
function hcColor(team) {
  const identity = currentState[`${team}_identity`] || {};
  return identity.primary_color || currentState[`${team}_primary_color`] || (team === 'home' ? '#c8102e' : '#2f6fd0');
}
function hcStamp(extra) {
  return { ...extra, clockSeconds: Number(currentState.clock_seconds || 0), period: String(currentState.period || '') };
}

// --- saving ------------------------------------------------------------------

async function hcSend(action, payload) {
  try {
    currentState = await api(`/api/hoops/action/${encodeURIComponent(action)}`, payload || {});
    return true;
  } catch (err) {
    const message = (err.data && (err.data.message || err.data.error)) || err.message || 'That could not be saved.';
    hcToastData = { bad: true, text: `Not saved: ${message}`, sub: '' };
    render();
    return false;
  }
}
function hcLastEventId() { const events = hcEvents(); return events.length ? events[events.length - 1].event_id : ''; }
function hcDone(toast) { hc = hcFresh(); hcToastData = toast || hcToastData; render(); }

// --- court -------------------------------------------------------------------

function hcBasket(dir) {
  const line = 'rgba(255,255,255,.92)';
  const laneX = dir > 0 ? 0 : 65, circleX = dir > 0 ? 19 : 65, rimX = dir > 0 ? 5.25 : 78.75, edge = dir > 0 ? 0 : 84, sweep = dir > 0 ? 1 : 0, board = dir > 0 ? 4 : 80;
  return `<rect x="${laneX}" y="19" width="19" height="12" fill="rgba(0,0,0,.14)" stroke="${line}" stroke-width=".28"/><circle cx="${circleX}" cy="25" r="6" fill="none" stroke="${line}" stroke-width=".28"/><path d="M${edge} 5.25 L${rimX} 5.25 A19.75 19.75 0 0 ${sweep} ${rimX} 44.75 L${edge} 44.75" fill="none" stroke="${line}" stroke-width=".32"/><line x1="${board}" y1="22" x2="${board}" y2="28" stroke="${line}" stroke-width=".4"/><circle cx="${rimX}" cy="25" r=".8" fill="none" stroke="#ff7a3c" stroke-width=".32"/>`;
}

function hcMarks() {
  if (hcHideMarks) return '';
  return hcEvents().filter(e => e.event_type === 'SHOT' && e.payload && e.payload.spotX != null).map(e => {
    const p = e.payload;
    const spot = hcAttacks(p.team) === 'right' ? { x: p.spotX, y: p.spotY } : { x: 84 - p.spotX, y: 50 - p.spotY };
    if (p.made) return `<circle cx="${spot.x}" cy="${spot.y}" r="1.05" fill="#28d070" stroke="#08361b" stroke-width=".22"/>`;
    return `<g stroke="#fff" stroke-width=".42" stroke-linecap="round"><line x1="${spot.x - .8}" y1="${spot.y - .8}" x2="${spot.x + .8}" y2="${spot.y + .8}"/><line x1="${spot.x + .8}" y1="${spot.y - .8}" x2="${spot.x - .8}" y2="${spot.y + .8}"/></g>`;
  }).join('');
}

function hcCourtSvg() {
  const line = 'rgba(255,255,255,.92)';
  const left = hcAttacks('home') === 'left' ? 'home' : 'visitor', right = hcOther(left);
  const pin = hc.screen ? `<g id="hcPin"><circle cx="${hc.screen.x}" cy="${hc.screen.y}" r="3.1" fill="none" stroke="#ffd23f" stroke-width=".35" opacity=".7"/><circle cx="${hc.screen.x}" cy="${hc.screen.y}" r="1.55" fill="#ffd23f" stroke="#111" stroke-width=".35"/></g>` : '';
  return `<svg id="hcCourt" class="hc-court" viewBox="0 0 84 50" role="img" aria-label="Basketball court"><defs><pattern id="hcWood" width="6" height="2.4" patternUnits="userSpaceOnUse"><rect width="6" height="2.4" fill="#a97b4c"/><line x1="0" y1="2.4" x2="6" y2="2.4" stroke="#8f6539" stroke-width=".07"/><line x1="3.4" y1="0" x2="3.4" y2="2.4" stroke="#8f6539" stroke-width=".05"/></pattern></defs><rect width="84" height="50" fill="url(#hcWood)"/><rect x=".15" y=".15" width="83.7" height="49.7" fill="none" stroke="${line}" stroke-width=".32"/><line x1="42" y1="0" x2="42" y2="50" stroke="${line}" stroke-width=".28"/><circle cx="42" cy="25" r="6" fill="none" stroke="${line}" stroke-width=".28"/>${hcBasket(1)}${hcBasket(-1)}<text x="30" y="3" font-size="1.45" font-weight="800" fill="#fff" text-anchor="middle">&#8592; ${escapeHtml(hcName(left).toUpperCase())} ATTACKS</text><text x="54" y="3" font-size="1.45" font-weight="800" fill="#fff" text-anchor="middle">${escapeHtml(hcName(right).toUpperCase())} ATTACKS &#8594;</text><g opacity="${hc.screen ? .45 : 1}">${hcMarks()}</g>${pin}</svg>`;
}

function hcPointerSpot(event) {
  const box = document.getElementById('hcCourt').getBoundingClientRect();
  return {
    x: Math.round(Math.min(84, Math.max(0, (event.clientX - box.left) / box.width * 84)) * 10) / 10,
    y: Math.round(Math.min(50, Math.max(0, (event.clientY - box.top) / box.height * 50)) * 10) / 10,
  };
}

function hcBindCourt() {
  const svg = document.getElementById('hcCourt');
  if (!svg) return;
  svg.addEventListener('pointerdown', event => {
    if (!hcReady()) return;
    event.preventDefault();
    const spot = hcPointerSpot(event);
    hcDragging = true;
    try { svg.setPointerCapture(event.pointerId); } catch (e) { /* a mouse without capture still works */ }
    hcSetSpot(spot, true);
  });
  svg.addEventListener('pointermove', event => {
    if (hcDragging) hcSetSpot(hcPointerSpot(event), false);
  });
  const finish = () => { if (hcDragging) { hcDragging = false; render(); } };
  svg.addEventListener('pointerup', finish);
  svg.addEventListener('pointercancel', finish);
}

function hcSetSpot(screen, isNewPress) {
  if (hc.mode === 'steal_spot') {
    if (!isNewPress) return;
    hcDragging = false;
    const spot = hcToShooterView(hc.team, screen);
    const targetEventId = hc.targetId;
    hcSend('play_note', { targetEventId, spotX: spot.x, spotY: spot.y }).then(ok => { if (ok) hcDone({ text: 'Steal spot marked.', sub: '' }); });
    return;
  }
  const stillPlacing = hc.mode === 'shot';
  if (!stillPlacing) { const fixId = hc.fixId; hc = hcFresh(); hc.fixId = fixId; hc.mode = 'shot'; hc.team = screen.x >= 42 ? (hcAttacks('home') === 'right' ? 'home' : 'visitor') : (hcAttacks('home') === 'left' ? 'home' : 'visitor'); hcToastData = null; }
  hc.screen = screen;
  const three = hcIsThree(hcToShooterView(hc.team, screen));
  hc.autoPoints = three ? 3 : 2;
  hc.points = hc.autoPoints;
  if (hc.points === 3 || hcZone(hcToShooterView(hc.team, screen)) !== 'rim') hc.shotType = '';
  const pinGroup = document.getElementById('hcPin');
  if (pinGroup) {
    pinGroup.querySelectorAll('circle').forEach(c => { c.setAttribute('cx', screen.x); c.setAttribute('cy', screen.y); });
  } else {
    hcRenderCourt();
    hcBindCourt();
  }
  hcRenderHead();
}

// --- the flows ----------------------------------------------------------------

function hcReady() {
  const h = hoopsState();
  return hcEvents().some(e => e.event_type === 'GAME_START') && (h.home_on_floor || []).length === 5 && (h.visitor_on_floor || []).length === 5 || hcNoRosterMode();
}
function hcNoRosterMode() {
  return hcEvents().some(e => e.event_type === 'GAME_START') && !hoopsRosterPlayers('home').length && !hoopsRosterPlayers('visitor').length;
}

function hcSetResult(result) { hc.result = result; hcTryCommitShot(); render(); }
function hcSetPoints(points) { hc.points = points; render(); }
function hcSetType(type) { hc.shotType = hc.shotType === type ? '' : type; render(); }
function hcSwapTeam() {
  hc.team = hcOther(hc.team);
  const spot = hcToShooterView(hc.team, hc.screen);
  hc.autoPoints = hcIsThree(spot) ? 3 : 2; hc.points = hc.autoPoints; hc.shooter = '';
  render();
}

async function hcTryCommitShot() {
  if (hc.mode !== 'shot' || !hc.result || hc.shooter === '') return;
  const team = hc.team, points = hc.points, shooter = hc.shooter === 'none' ? '' : hc.shooter, spot = hcToShooterView(team, hc.screen), result = hc.result, type = hc.shotType, fixId = hc.fixId;
  const base = hcStamp({ team, points, shooterId: shooter, spotX: spot.x, spotY: spot.y, shotType: type });
  const named = shooter ? hcLabel(shooter) : hcName(team);
  const made = result === 'made' || result === 'plus';
  if (result === 'fouled') {
    hc = { ...hcFresh(), mode: 'foul_on_shot', team, points, shooter, foulFrom: { spotX: spot.x, spotY: spot.y, shotPoints: points, andOne: false }, ft: { team, shooter, total: points, done: 0 } };
    hcToastData = { text: `${named} fouled on the shot. Who fouled?`, sub: '' };
    render();
    return;
  }
  if (fixId) {
    const previous = hcEvents().find(e => e.event_id === fixId);
    const notes = hcNotesFor(fixId);
    const replacement = { ...base, made, clockSeconds: previous?.payload?.clockSeconds ?? base.clockSeconds, period: previous?.payload?.period ?? base.period };
    ['assistId', 'blockPlayerId'].forEach(field => { if (notes[field]) replacement[field] = notes[field]; });
    if (await hcSend('correct_event', { event_id: fixId, replacement_payload: replacement, reason: 'console fix' })) hcDone({ text: `Fixed: ${named}.`, sub: '' });
    return;
  }
  const payload = { ...base, made };
  if (result === 'made') payload.possessionAfter = hcOther(team);
  if (!(await hcSend('shot', payload))) return;
  const targetId = hcLastEventId();
  const zone = HC_ZONE_NAMES[hcZone(spot)] || '';
  const kind = type || (points === 3 ? '3-pointer' : '2-pointer');
  if (result === 'missed') {
    const stats = hcStats()[shooter];
    hc = { ...hcFresh(), mode: 'rebound', team, targetId };
    hcToastData = { bad: true, text: `Saved: ${named} misses ${points === 3 ? 'a 3' : 'a 2'} ${zone ? `(${zone})` : ''}.`, sub: stats && points === 3 ? `${hcLabel(shooter)} is ${stats.threes} of ${stats.threeTries} from three` : '' };
    render();
    return;
  }
  const scoreLine = `${hcName('home')} ${currentState.home_score}, ${hcName('visitor')} ${currentState.visitor_score}`;
  const run = hcRun();
  const subs = [];
  if (run.team === team && run.points >= 5 && run.broken) subs.push(`${hcName(team)} on a ${run.points}-0 run`);
  if (shooter && hcStats()[shooter]) subs.push(`${hcLabel(shooter)} now has ${hcStats()[shooter].pts}`);
  hcToastData = { text: `Saved: ${named}, ${kind} ${zone ? `(${zone})` : ''}. ${scoreLine}.`, sub: subs.join(' · ') };
  if (result === 'plus') {
    hc = { ...hcFresh(), mode: 'foul_on_shot', team, points, shooter, targetId, foulFrom: { spotX: spot.x, spotY: spot.y, shotPoints: points, andOne: true }, ft: { team, shooter, total: 1, done: 0 } };
  } else {
    hc = { ...hcFresh(), mode: 'assist', team, shooter, targetId, points };
  }
  render();
}

function hcNotesFor(eventId) {
  const merged = {};
  hcEvents().filter(e => e.event_type === 'PLAY_NOTE' && e.payload?.targetEventId === eventId).forEach(e => Object.assign(merged, e.payload));
  return merged;
}

async function hcNote(fields, toast) {
  if (!hc.targetId) return false;
  const ok = await hcSend('play_note', { targetEventId: hc.targetId, ...fields });
  if (ok && toast) hcToastData = { text: toast, sub: '' };
  return ok;
}

async function hcAddTag(tag) {
  const tags = [...(hcNotesFor(hc.targetId).tags || [])];
  if (!tags.includes(tag)) tags.push(tag);
  await hcNote({ tags }, null);
  render();
}

function hcAddPlusOne() {
  const shot = hcEvents().find(e => e.event_id === hc.targetId);
  const p = shot?.payload || {};
  hc = { ...hcFresh(), mode: 'foul_on_shot', team: p.team, shooter: p.shooterId || '', points: Number(p.points || 2), targetId: hc.targetId, foulFrom: { spotX: p.spotX, spotY: p.spotY, shotPoints: Number(p.points || 2), andOne: true }, ft: { team: p.team, shooter: p.shooterId || '', total: 1, done: 0 } };
  render();
}

async function hcPick(side, id) {
  switch (hc.mode) {
    case 'idle': return hcSubFromFloor(side, id);
    case 'shot':
      if (side !== hc.team) return;
      hc.shooter = id; hcTryCommitShot(); return render();
    case 'assist': {
      if (side !== hc.team || id === hc.shooter) return;
      const ok = await hcNote({ assistId: id }, `Assist: ${hcLabel(id)}.`);
      if (ok) hcDone();
      return;
    }
    case 'rebound': {
      const kind = side === hc.team ? 'offensive' : 'defensive';
      if (await hcSend('rebound', hcStamp({ team: side, playerId: id, kind }))) hcDone({ text: `Rebound: ${hcLabel(id)} (${kind}).`, sub: '' });
      return;
    }
    case 'rebound_any': {
      const kind = side === currentState.possession ? 'offensive' : 'defensive';
      if (await hcSend('rebound', hcStamp({ team: side, playerId: id, kind }))) hcDone({ text: `Rebound: ${hcLabel(id)} (${kind}).`, sub: '' });
      return;
    }
    case 'block': {
      if (side === hc.team) return;
      const team = hc.team, targetId = hc.targetId;
      if (await hcNote({ blockPlayerId: id }, `Block: ${hcLabel(id)}. Who got the rebound?`)) { hc = { ...hcFresh(), mode: 'rebound', team, targetId }; render(); }
      return;
    }
    case 'foul_on_shot': return hcSaveShootingFoul(side, id);
    case 'foul': return hcSaveFoul(side, id);
    case 'ft_who':
      if (side !== hc.ft.team) return;
      hc.ft.shooter = id; hc.mode = 'ft'; return render();
    case 'steal': {
      const team = hcOther(side);
      if (!(await hcSend('turnover', hcStamp({ team, stealPlayerId: id })))) return;
      hcToastData = { text: `Saved: ${hcLabel(id)} steal. Turnover on ${hcName(team)}.`, sub: `Ball to ${hcName(side)}` };
      hc = { ...hcFresh(), mode: 'stolen', team: side, targetId: hcLastEventId() };
      return render();
    }
    case 'stolen': {
      if (side === hc.team) return;
      if (await hcNote({ turnoverPlayerId: id }, `Stolen from ${hcLabel(id)}.`)) hcDone();
      return;
    }
    case 'turnover':
      if (await hcSend('turnover', hcStamp({ team: side, playerId: id }))) hcDone({ text: `Turnover: ${hcLabel(id)}. Ball to ${hcName(hcOther(side))}.`, sub: '' });
      return;
    case 'sub_out': return hcFinishSub(side, id);
    case 'sub_in_for': return hcFinishSub(side, hc.subOut, id);
    case 'replace': return hcFinishBenchCredit(side, id);
    default: return;
  }
}

function hcSubFromFloor(side, id) {
  hc = { ...hcFresh(), mode: 'sub_in_for', subSide: side, subOut: id };
  hcToastData = null;
  render();
}

function hcBench(side, id) {
  if (['idle', 'sub_out', 'sub_in_for'].includes(hc.mode) || hc.mode === 'assist' && side !== hc.team || hc.mode === 'stolen') {
    if (hc.mode === 'sub_in_for' && hc.subSide === side) return hcFinishSub(side, hc.subOut, id);
    hc = { ...hcFresh(), mode: 'sub_out', subSide: side, subIn: id };
    hcToastData = null;
    return render();
  }
  // A stat for someone the console has on the bench: credit the player and fix the lineup.
  hc.benchCredit = { side, id, mode: hc.mode };
  hc.mode = 'replace';
  render();
}

async function hcFinishBenchCredit(side, outId) {
  const credit = hc.benchCredit;
  if (!credit || side !== credit.side) return;
  const snapshot = { ...hc, mode: credit.mode, benchCredit: null };
  const ok = await hcSend('substitute', { team: side, out_player_id: outId, in_player_id: credit.id });
  if (!ok) return;
  hc = snapshot;
  hcToastData = { text: `Lineup fixed: ${hcLabel(credit.id)} in for ${hcLabel(outId)}.`, sub: '' };
  await hcPick(side, credit.id);
  render();
}

function hcCreditOnly() {
  const credit = hc.benchCredit;
  hc = { ...hc, mode: credit.mode, benchCredit: null };
  hcPick(credit.side, credit.id);
}

async function hcFinishSub(side, outId, inId) {
  const incoming = inId || hc.subIn;
  if (side !== hc.subSide || !outId || !incoming) return;
  if (await hcSend('substitute', { team: side, out_player_id: outId, in_player_id: incoming })) hcDone({ text: `Sub: ${hcLabel(incoming)} in for ${hcLabel(outId)}.`, sub: '' });
}

async function hcSaveShootingFoul(side, id) {
  if (side === hc.team) return;
  const from = hc.foulFrom;
  const payload = hcStamp({ team: side, playerId: id, foulType: 'shooting', isShootingFoul: true, shotPoints: from.shotPoints, andOne: from.andOne, drewFoulOn: hc.shooter, possessionAfter: hc.team });
  if (from.spotX != null) { payload.spotX = from.spotX; payload.spotY = from.spotY; }
  const ft = hc.ft;
  if (!(await hcSend('foul', payload))) return;
  const fouls = hoopsState().player_fouls?.[id] || 0;
  hcToastData = { text: `Foul on ${hcLabel(id)}${fouls >= 4 ? `: now has ${fouls}` : ''}.`, sub: '' };
  hc = { ...hcFresh(), mode: ft.shooter ? 'ft' : 'ft_who', ft };
  render();
}

function hcFreeThrowsAfterFoul(foulType, side) {
  const other = hcOther(side);
  if (foulType === 'offensive') return 0;
  if (['technical', 'intentional', 'flagrant_1'].includes(foulType)) return 2;
  return (hoopsState()[`${other}_bonus`] || 'NONE') !== 'NONE' ? 2 : 0;
}

async function hcSaveFoul(side, id) {
  const foulType = hc.foulType;
  const payload = hcStamp({ team: side, foulType });
  if (id) payload.playerId = id;
  if (foulType !== 'technical') payload.possessionAfter = hcOther(side);
  if (!(await hcSend('foul', payload))) return;
  const shots = hcFreeThrowsAfterFoul(foulType, side);
  const fouls = id ? hoopsState().player_fouls?.[id] || 0 : 0;
  const out = id && (hoopsState().disqualified || []).includes(id);
  hcToastData = { text: `Foul on ${id ? hcLabel(id) : hcName(side)}.${out ? ' Fouled out: sub someone in.' : fouls >= 4 ? ` Now has ${fouls}.` : ''}`, sub: shots ? `${hcName(hcOther(side))} shoots ${shots}` : '' };
  if (shots) {
    hc = { ...hcFresh(), mode: 'ft_who', ft: { team: hcOther(side), shooter: '', total: shots, done: 0, keepBall: foulType === 'technical' } };
    render();
    return;
  }
  hcDone();
}

function hcStartFreeThrows() {
  const team = currentState.possession === 'visitor' ? 'visitor' : 'home';
  hc = { ...hcFresh(), mode: 'ft_who', ft: { team, shooter: '', total: 2, done: 0 } };
  hcToastData = null;
  render();
}
function hcFtTotal(total) { hc.ft.total = total; render(); }
function hcFtSwapTeam() { hc.ft.team = hcOther(hc.ft.team); hc.ft.shooter = ''; hc.mode = 'ft_who'; render(); }
function hcFtNoName() { hc.ft.shooter = 'none'; hc.mode = 'ft'; render(); }

async function hcFtResult(made) {
  const ft = hc.ft;
  const number = ft.done + 1;
  const last = number >= ft.total;
  const shooter = ft.shooter === 'none' ? '' : ft.shooter;
  const payload = hcStamp({ team: ft.team, made, shooterId: shooter, attemptNumber: number, ofAttempts: ft.total });
  if (last && made && !ft.keepBall) payload.possessionAfter = hcOther(ft.team);
  if (!(await hcSend('free_throw', payload))) return;
  const named = shooter ? hcLabel(shooter) : hcName(ft.team);
  if (!last) {
    hc.ft.done = number;
    hcToastData = { text: `${named} ${made ? 'makes' : 'misses'} free throw ${number} of ${ft.total}.`, sub: '' };
    return render();
  }
  hcToastData = { text: `${named} ${made ? 'makes' : 'misses'} the last free throw.`, sub: `${hcName('home')} ${currentState.home_score}, ${hcName('visitor')} ${currentState.visitor_score}` };
  if (!made && !ft.keepBall) { hc = { ...hcFresh(), mode: 'rebound', team: ft.team }; return render(); }
  hcDone();
}

function hcMode(mode, extra) { hc = { ...hcFresh(), mode, ...(extra || {}) }; hcToastData = null; render(); }
async function hcSkip() { hc = hcFresh(); render(); }
async function hcTeamRebound(team) {
  const kind = team === hc.team ? 'offensive' : 'defensive';
  if (await hcSend('rebound', hcStamp({ team, kind: 'team', reboundFor: kind }))) hcDone({ text: `Team rebound: ${hcName(team)}.`, sub: '' });
}
async function hcOutOfBounds(team) {
  if (await hcSend('ruling', { possessionTo: team })) hcDone({ text: `Out of bounds. Ball to ${hcName(team)}.`, sub: '' });
}
async function hcJumpBall() {
  if (await hcSend('held_ball', hcStamp({}))) hcDone({ text: `Jump ball. Ball to ${hcName(currentState.possession)} on the arrow.`, sub: '' });
}
async function hcTeamTurnover(team) {
  if (await hcSend('turnover', hcStamp({ team }))) hcDone({ text: `Team turnover: ${hcName(team)}.`, sub: '' });
}
async function hcTimeout(team) {
  if (await hcSend('timeout', hcStamp({ team }))) hcDone({ text: `Timeout ${hcName(team)}. ${hoopsState()[`${team}_timeouts`]} left.`, sub: '' });
}
async function hcViolation(team, violationType, label) {
  if (await hcSend('violation', hcStamp({ team, violationType, possessionTo: hcOther(team) }))) hcDone({ text: `${label} on ${hcName(team)}. Ball to ${hcName(hcOther(team))}.`, sub: '' });
}
async function hcUndo() { if (await hcSend('undo', {})) hcDone({ text: 'Undone.', sub: '' }); }
async function hcRedo() { if (await hcSend('redo', {})) hcDone({ text: 'Put back.', sub: '' }); }
async function hcEndPeriod() {
  if (!confirm(`End ${hcPeriodName()} now?`)) return;
  if (await hcSend('end_period', {})) hcDone({ text: 'Quarter ended.', sub: '' });
}
async function hcConfirmFinal() {
  if (!confirm('Make this the official final?')) return;
  if (await hcSend('confirm_game_end', { reason: 'OFFICIAL' })) hcDone({ text: 'Final.', sub: '' });
}
async function hcStartGame() {
  try { currentState = await api('/api/hoops/initialize', {}); hcDone({ text: 'Game started. Now the starting fives.', sub: '' }); }
  catch (err) { hcToastData = { bad: true, text: err.message || 'The game could not be started.', sub: '' }; render(); }
}
async function hcTip(team) {
  if (await hcSend('opening_tip', { team })) hcDone({ text: `${hcName(team)} won the tip. Arrow to ${hcName(hcOther(team))}.`, sub: '' });
}
async function hcSwapEnds() {
  const base = hoopsState().home_first_half_attacks === 'left' ? 'left' : 'right';
  if (await hcSend('set_direction', { homeFirstHalfAttacks: base === 'left' ? 'right' : 'left' })) hcDone();
}
function hcToggleMarks() { hcHideMarks = !hcHideMarks; render(); }
function hcToggleStarter(side, id) {
  const list = hcStarters[side];
  const at = list.indexOf(id);
  if (at >= 0) list.splice(at, 1); else if (list.length < 5) list.push(id);
  if (list.length === 5) {
    hcSend('set_starting_five', { team: side, player_ids: [...list] }).then(ok => { if (ok) { hcStarters[side] = []; render(); } });
    return;
  }
  render();
}
async function hcDelete(eventId) {
  if (!confirm('Delete this play?')) return;
  if (await hcSend('void_event', { event_id: eventId, reason: 'console delete' })) hcDone({ text: 'Deleted.', sub: '' });
}
function hcFixShot(eventId) {
  const event = hcEvents().find(e => e.event_id === eventId);
  if (!event) return;
  const p = event.payload || {};
  const screen = p.spotX == null ? { x: 60, y: 25 } : (hcAttacks(p.team) === 'right' ? { x: p.spotX, y: p.spotY } : { x: 84 - p.spotX, y: 50 - p.spotY });
  hc = { ...hcFresh(), mode: 'shot', team: p.team, screen, points: Number(p.points || 2), autoPoints: Number(p.points || 2), shotType: p.shotType || '', fixId: eventId };
  hcToastData = { text: 'Fixing this shot: move the pin, then pick the result and the shooter again.', sub: '' };
  render();
}

// --- drawing ------------------------------------------------------------------

function hcPeriodName() {
  const period = String(currentState.period || '1');
  return /^\d$/.test(period) ? `${['1st', '2nd', '3rd', '4th'][Number(period) - 1] || period} quarter` : (period === 'OT' ? 'overtime' : period);
}

function hcRenderTop() {
  const h = hoopsState();
  const running = Boolean(currentState.clock_running);
  const teamBlock = (team, right) => {
    const inBonus = (h[`${hcOther(team)}_bonus`] || 'NONE') !== 'NONE';
    const fouls = Number(h[`${team}_team_fouls`] ?? 0);
    const info = `Team fouls ${fouls} · Timeouts ${h[`${team}_timeouts`] ?? 0}${inBonus ? ` · <span class="hc-bonus">${escapeHtml(hcName(hcOther(team)))} in the bonus</span>` : ''}`;
    const score = `<div class="hc-score">${Number(currentState[`${team}_score`] ?? 0)}</div>`;
    const name = `<div style="min-width:0"><b>${escapeHtml(hcName(team))}</b><div class="hc-sub">${info}</div></div>`;
    return `<div class="hc-team ${right ? 'r' : ''}">${right ? score + name : name + score}</div>`;
  };
  const poss = currentState.possession;
  const arrow = h.possession_arrow ? `Arrow: ${escapeHtml(hcName(h.possession_arrow))}` : 'Arrow not set';
  document.getElementById('hcTop').innerHTML = `${teamBlock('visitor', false)}
    <div class="hc-mid"><div><div class="hc-period">${escapeHtml(hcPeriodName().toUpperCase())}</div><div id="hcClock" class="hc-clock">${hcClockText()}</div></div>
    <button onclick="clockAction('${running ? 'stop' : 'start'}')">${running ? 'Stop clock' : 'Start clock'}</button><button onclick="setClockDialog()">Set</button>
    <div class="hc-sub" title="${arrow}">Ball<br><b style="font-size:15px;color:#fff">${poss === 'home' || poss === 'visitor' ? escapeHtml(hcName(poss)) : '?'}</b></div>
    <button onclick="hcUndo()">Undo</button><button onclick="hcToggleMenu()">Menu</button></div>
    ${teamBlock('home', true)}`;
}

function hcAskTitle(side) {
  const m = hc.mode, teamName = hcName(side).toUpperCase();
  if (m === 'shot') return side === hc.team ? 'WHO SHOT IT?' : '';
  if (m === 'assist') return side === hc.team ? 'ASSIST BY?' : '';
  if (m === 'rebound') return `REBOUND: ${teamName} (${side === hc.team ? 'OFF' : 'DEF'})`;
  if (m === 'rebound_any') return `REBOUND: ${teamName}`;
  if (m === 'block') return side !== hc.team ? 'BLOCKED BY?' : '';
  if (m === 'foul_on_shot') return side !== hc.team ? 'WHO FOULED?' : '';
  if (m === 'foul') return 'WHO FOULED?';
  if (m === 'ft_who') return side === hc.ft.team ? 'WHO IS SHOOTING?' : '';
  if (m === 'steal') return 'WHO STOLE IT?';
  if (m === 'stolen') return side !== hc.team ? 'STOLEN FROM?' : '';
  if (m === 'turnover') return 'WHO TURNED IT OVER?';
  if (m === 'sub_out') return side === hc.subSide ? 'WHO COMES OUT?' : '';
  if (m === 'sub_in_for') return side === hc.subSide ? 'TAP WHO COMES IN' : '';
  if (m === 'replace') return side === hc.benchCredit.side ? `WHO DID ${escapeHtml(hcLabel(hc.benchCredit.id).toUpperCase())} REPLACE?` : '';
  return '';
}

function hcPlayerButton(side, p, stats, options) {
  const fouls = Number(hoopsState().player_fouls?.[p.id] || 0);
  const out = (hoopsState().disqualified || []).includes(p.id);
  const pips = [0, 1, 2, 3, 4].map(i => `<i class="${i < fouls ? (fouls >= 4 ? 'd' : 'f') : ''}"></i>`).join('');
  const name = p.last_name || p.first_name || 'Player';
  return `<button class="hc-p ${options.pick ? 'pick' : ''} ${fouls >= 4 ? 'warn' : ''} ${out ? 'out' : ''}" data-id="${escapeHtml(p.id)}" onclick="${options.onclick}"><span class="n" style="background:${escapeHtml(hcColor(side))}">${escapeHtml(p.number || '?')}</span><span><span class="nm">${escapeHtml(name)}${out ? ' (out)' : ''}</span><span class="hc-pips">${pips}</span></span><span class="pts">${stats[p.id]?.pts ?? 0}</span></button>`;
}

function hcRenderSide(side) {
  const el = document.getElementById(side === 'home' ? 'hcHomeSide' : 'hcVisitorSide');
  const h = hoopsState();
  const roster = hoopsRosterPlayers(side);
  const onFloorIds = h[`${side}_on_floor`] || [];
  const started = hcEvents().some(e => e.event_type === 'GAME_START');
  const stats = hcStats();
  if (!roster.length) {
    el.className = 'hc-side';
    el.innerHTML = `<h4>${escapeHtml(hcName(side).toUpperCase())}</h4><div class="hc-sub">No active basketball roster matches this game. Add one under Rosters. Plays can still be saved with no player name.</div>`;
    return;
  }
  if (started && onFloorIds.length !== 5) {
    const picked = hcStarters[side];
    el.className = 'hc-side ask';
    el.innerHTML = `<h4>STARTING FIVE: ${escapeHtml(hcName(side).toUpperCase())} (${picked.length} of 5)</h4><div class="hc-list">${roster.map(p => hcPlayerButton(side, p, stats, { pick: picked.includes(p.id), onclick: `hcToggleStarter('${side}','${escapeHtml(p.id)}')` })).join('')}</div>`;
    return;
  }
  const byId = new Map(roster.map(p => [p.id, p]));
  const floor = onFloorIds.map(id => byId.get(id) || { id, number: '?', last_name: id });
  const bench = roster.filter(p => !onFloorIds.includes(p.id) && !(h.disqualified || []).includes(p.id));
  const title = hcAskTitle(side);
  const offWhileAsking = hc.mode !== 'idle' && !title;
  const benchLabel = title && !['sub_out', 'sub_in_for', 'replace'].includes(hc.mode) ? 'BENCH' : 'BENCH: TAP TO SUB IN';
  el.className = `hc-side ${title ? 'ask' : ''} ${offWhileAsking ? 'off' : ''}`;
  const picked = hc.mode === 'shot' ? hc.shooter : (hc.mode === 'sub_in_for' ? hc.subOut : (hc.mode === 'ft' ? hc.ft?.shooter : ''));
  const extra = (hc.mode === 'rebound' || hc.mode === 'rebound_any') ? `<button class="hc-chip" onclick="hcTeamRebound('${side}')">Team rebound</button>` : (hc.mode === 'turnover' ? `<button class="hc-chip" onclick="hcTeamTurnover('${side}')">Team turnover</button>` : (hc.mode === 'foul' ? `<button class="hc-chip" onclick="hcSaveFoul('${side}','')">No name</button>` : ''));
  el.innerHTML = `<h4>${title || `${escapeHtml(hcName(side).toUpperCase())} ON FLOOR`}</h4>${floor.map(p => hcPlayerButton(side, p, stats, { pick: picked === p.id, onclick: `hcPick('${side}','${escapeHtml(p.id)}')` })).join('')}${extra}<div class="hc-label" style="margin-top:4px">${benchLabel}</div><div class="hc-bench">${bench.map(p => `<button class="hc-chip ${hc.subIn === p.id || hc.benchCredit?.id === p.id ? 'pick' : ''}" title="${escapeHtml([p.first_name, p.last_name].filter(Boolean).join(' '))}" onclick="hcBench('${side}','${escapeHtml(p.id)}')">${escapeHtml(p.number || '?')}</button>`).join('')}</div>`;
}

function hcRenderCourt() { document.getElementById('hcCourtWrap').innerHTML = hcCourtSvg(); }

function hcRenderHead() {
  const el = document.getElementById('hcCourtHead');
  if (hc.mode === 'shot' && hc.screen) {
    const zone = HC_ZONE_NAMES[hcZone(hcToShooterView(hc.team, hc.screen))] || '';
    el.innerHTML = `<strong>${escapeHtml(hcName(hc.team))} · ${escapeHtml(zone)}</strong><span>Drag the pin to adjust · <a href="#" onclick="hcSwapTeam();return false" style="color:inherit">Wrong team?</a></span>`;
  } else if (hc.mode === 'steal_spot') {
    el.innerHTML = '<strong>Tap where the steal happened</strong><span></span>';
  } else {
    el.innerHTML = `<strong>${hcReady() ? 'Tap where the shot was taken' : 'Set up the game below'}</strong><span>Green dot made · white X missed · <a href="#" onclick="hcToggleMarks();return false" style="color:inherit">${hcHideMarks ? 'Show marks' : 'Hide marks'}</a></span>`;
  }
}

function hcRenderToast() {
  const el = document.getElementById('hcToast');
  el.innerHTML = hcToastData ? `<div class="hc-toast ${hcToastData.bad ? 'bad' : ''}"><div class="hc-grow"><b>${escapeHtml(hcToastData.text)}</b>${hcToastData.sub ? `<div class="hc-sub">${escapeHtml(hcToastData.sub)}</div>` : ''}</div><button onclick="hcUndo()">Undo</button></div>` : '';
}

const HC_ACTIONS = `<div class="hc-acts"><button onclick="hcStartFreeThrows()">Free throw</button><button onclick="hcMode('steal')">Steal</button><button onclick="hcMode('turnover')">Turnover</button><button onclick="hcMode('rebound_any')">Rebound</button><button onclick="hcMode('foul')">Foul</button><button onclick="hcJumpBall()">Jump ball</button><button onclick="hcMode('timeout')">Timeout</button><button onclick="hcMode('more')">More</button></div>`;

function hcFtRows(ft) {
  // One shot at a time keeps the buttons on screen with the court.
  const live = hc.mode === 'ft';
  return `<div class="hc-two"><span class="hc-label">Shot ${Math.min(ft.done + 1, ft.total)} of ${ft.total}</span><button class="hc-big made" ${live ? '' : 'disabled'} onclick="hcFtResult(true)">MADE</button><button class="hc-big miss" ${live ? '' : 'disabled'} onclick="hcFtResult(false)">MISSED</button></div>`;
}

function hcRenderPanel() {
  const el = document.getElementById('hcPanel');
  const started = hcEvents().some(e => e.event_type === 'GAME_START');
  const h = hoopsState();
  if (!started) {
    el.innerHTML = `<div class="hc-card hot"><div class="hc-row hc-between"><b>Ready to start this game?</b><button class="made" onclick="hcStartGame()">Start game</button></div></div>`;
    return;
  }
  const rostersThere = hoopsRosterPlayers('home').length || hoopsRosterPlayers('visitor').length;
  if (rostersThere && ((h.home_on_floor || []).length !== 5 || (h.visitor_on_floor || []).length !== 5)) {
    el.innerHTML = `<div class="hc-card hot"><b>Tap each team's five starters.</b><div class="hc-sub">Each team saves itself on the fifth player.</div></div>`;
    return;
  }
  const candidate = h.game_end_candidate;
  const finished = currentState.status === 'completed' || h.official_end_reason;
  if (candidate && !finished) {
    el.innerHTML = `<div class="hc-card hot"><div class="hc-row hc-between"><b>Regulation is over with a decided score.</b><button class="made" onclick="hcConfirmFinal()">Make it final</button></div></div>${HC_ACTIONS}`;
    return;
  }
  const noTip = !hcEvents().some(e => ['OPENING_TIP', 'SHOT', 'FREE_THROW', 'TURNOVER'].includes(e.event_type));
  if (noTip && hc.mode === 'idle') {
    el.innerHTML = `<div class="hc-card hot"><div class="hc-row hc-between"><b>Who won the opening tip?</b><div class="hc-row"><button onclick="hcTip('visitor')">${escapeHtml(hcName('visitor'))}</button><button onclick="hcTip('home')">${escapeHtml(hcName('home'))}</button><button onclick="hcSwapEnds()">Swap ends</button></div></div><div class="hc-sub" style="margin-top:6px">Make sure the court above matches the floor: ${escapeHtml(hcName(hcAttacks('home') === 'right' ? 'home' : 'visitor'))} shoots at the right-hand basket this half.</div></div>`;
    return;
  }
  const last = hcEvents()[hcEvents().length - 1];
  const quarterJustChanged = last?.event_type === 'PERIOD_TRANSITION' && hc.mode === 'idle';
  const clockOut = Number(currentState.clock_seconds) === 0 && hc.mode === 'idle';
  const banner = quarterJustChanged
    ? `<div class="hc-card hot" style="margin-bottom:8px"><div class="hc-row hc-between"><b>${escapeHtml(hcPeriodName())}: ball to ${escapeHtml(hcName(h.possession_arrow || 'home'))} on the arrow?</b><button onclick="hcJumpBall()">Yes, arrow</button></div><div class="hc-sub">${['3'].includes(String(currentState.period)) ? 'Teams switched ends. The court above has flipped.' : ''}</div></div>`
    : (clockOut ? `<div class="hc-card hot" style="margin-bottom:8px"><div class="hc-row hc-between"><b>The clock is at 0:00.</b><button onclick="hcEndPeriod()">End the quarter</button></div></div>` : '');

  switch (hc.mode) {
    case 'shot': {
      const spot = hcToShooterView(hc.team, hc.screen);
      const atRim = hcZone(spot) === 'rim';
      const types = atRim ? ['Layup', 'Dunk', 'Tip-in'].map(t => `<button class="${hc.shotType === t ? 'on' : ''}" onclick="hcSetType('${t}')">${t}</button>`).join('') : '';
      const otherPoints = hc.points === 3 ? 2 : 3;
      el.innerHTML = `<div class="hc-card hot"><div class="hc-row hc-between" style="margin-bottom:8px"><div class="hc-row"><span class="hc-tag">${hc.points}-pointer${hc.points === hc.autoPoints ? '' : ' (changed)'}</span><button onclick="hcSetPoints(${otherPoints})">Make it a ${otherPoints}</button>${types}</div><div class="hc-row"><button onclick="hc.shooter='none';hcTryCommitShot();render()">No name</button><button onclick="hcSkip()">Cancel</button></div></div><div class="hc-four"><button class="hc-big made ${hc.result === 'made' ? 'sel' : ''}" onclick="hcSetResult('made')">MADE</button><button class="hc-big plus ${hc.result === 'plus' ? 'sel' : ''}" onclick="hcSetResult('plus')">MADE +1</button><button class="hc-big miss ${hc.result === 'missed' ? 'sel' : ''}" onclick="hcSetResult('missed')">MISSED</button><button class="hc-big foul ${hc.result === 'fouled' ? 'sel' : ''}" onclick="hcSetResult('fouled')">FOULED</button></div></div>`;
      return;
    }
    case 'assist':
      el.innerHTML = `<div class="hc-card hot"><div class="hc-row hc-between"><span class="hc-label">Assist on the right, or add anything else. Or just keep going.</span><div class="hc-row"><button onclick="hcAddPlusOne()">Add +1</button><button class="${(hcNotesFor(hc.targetId).tags || []).includes('fast_break') ? 'on' : ''}" onclick="hcAddTag('fast_break')">Fast break</button><button class="${(hcNotesFor(hc.targetId).tags || []).includes('off_turnover') ? 'on' : ''}" onclick="hcAddTag('off_turnover')">Off a turnover</button><button onclick="hcSkip()">Done</button></div></div></div>${HC_ACTIONS}`;
      return;
    case 'rebound':
      el.innerHTML = `<div class="hc-card hot"><div class="hc-label" style="margin-bottom:7px">Who got the rebound? One tap on either team. Offensive or defensive is worked out for you.</div><div class="hc-row">${hc.targetId ? `<button onclick="hc.mode='block';render()">Blocked by...</button>` : ''}<button onclick="hcOutOfBounds('home')">Out of bounds, ${escapeHtml(hcName('home'))}</button><button onclick="hcOutOfBounds('visitor')">Out of bounds, ${escapeHtml(hcName('visitor'))}</button><button onclick="hcJumpBall()">Jump ball</button><button onclick="hcSkip()">Skip</button></div></div>`;
      return;
    case 'rebound_any':
      el.innerHTML = `<div class="hc-card hot"><div class="hc-row hc-between"><b>Tap who got the rebound.</b><button onclick="hcSkip()">Cancel</button></div></div>`;
      return;
    case 'block':
      el.innerHTML = `<div class="hc-card hot"><div class="hc-row hc-between"><b>Tap who blocked it.</b><button onclick="hc.mode='rebound';render()">Back</button></div></div>`;
      return;
    case 'foul_on_shot':
      el.innerHTML = `<div class="hc-card hot"><div class="hc-row hc-between"><b>Tap who fouled ${hc.shooter ? escapeHtml(hcLabel(hc.shooter)) : 'the shooter'}.</b><button onclick="hcSaveShootingFoul('${hcOther(hc.team)}','')">No name</button></div><div class="hc-sub" style="margin-top:6px">${hc.foulFrom?.andOne ? 'Then the +1.' : `Then ${hc.ft.total} free throws. The spot is kept, without counting as a missed shot.`}</div></div>`;
      return;
    case 'foul':
      el.innerHTML = `<div class="hc-card hot"><div class="hc-row hc-between"><div class="hc-row">${HC_FOUL_TYPES.map(([id, label]) => `<button class="${hc.foulType === id ? 'on' : ''}" onclick="hc.foulType='${id}';render()">${label}</button>`).join('')}</div><button onclick="hcSkip()">Cancel</button></div><div class="hc-sub" style="margin-top:6px">Pick the kind, then tap the player. On a shooting foul, tap the court instead and choose Fouled.</div></div>`;
      return;
    case 'ft_who':
    case 'ft':
      el.innerHTML = `<div class="hc-card hot"><div class="hc-row hc-between"><b>${hc.ft.shooter && hc.ft.shooter !== 'none' ? `${escapeHtml(hcLabel(hc.ft.shooter))} at the line` : `Free throws: ${escapeHtml(hcName(hc.ft.team))}${hc.mode === 'ft_who' ? '. Tap the shooter.' : ''}`}</b><div class="hc-row"><span class="hc-label">Shots</span>${[1, 2, 3].map(n => `<button class="${hc.ft.total === n ? 'on' : ''}" onclick="hcFtTotal(${n})">${n}</button>`).join('')}${hc.ft.done ? '' : `<button onclick="hcFtSwapTeam()">Other team</button>`}${hc.mode === 'ft_who' ? `<button onclick="hcFtNoName()">No name</button>` : ''}<button onclick="hcSkip()">Done</button></div></div>${hcFtRows(hc.ft)}</div>`;
      return;
    case 'steal':
      el.innerHTML = `<div class="hc-card hot"><div class="hc-row hc-between"><b>Tap who stole it, on either team.</b><button onclick="hcSkip()">Cancel</button></div></div>`;
      return;
    case 'stolen':
      el.innerHTML = `<div class="hc-card hot"><div class="hc-row hc-between"><span class="hc-label">Stolen from whom? One tap, or keep going. No name still counts as a team turnover.</span><div class="hc-row"><button onclick="hc.mode='steal_spot';render()">Mark the spot</button><button onclick="hcSkip()">Done</button></div></div></div>${HC_ACTIONS}`;
      return;
    case 'steal_spot':
      el.innerHTML = `<div class="hc-card hot"><div class="hc-row hc-between"><b>Tap the court where the steal happened.</b><button onclick="hcSkip()">Cancel</button></div></div>`;
      return;
    case 'turnover':
      el.innerHTML = `<div class="hc-card hot"><div class="hc-row hc-between"><b>Tap who turned it over.</b><button onclick="hcSkip()">Cancel</button></div></div>`;
      return;
    case 'timeout':
      el.innerHTML = `<div class="hc-card hot"><div class="hc-row hc-between"><b>Whose timeout?</b><div class="hc-row"><button onclick="hcTimeout('visitor')">${escapeHtml(hcName('visitor'))}</button><button onclick="hcTimeout('home')">${escapeHtml(hcName('home'))}</button><button onclick="hcSkip()">Cancel</button></div></div></div>`;
      return;
    case 'more':
      el.innerHTML = `<div class="hc-card hot"><div class="hc-row hc-between" style="margin-bottom:8px"><div class="hc-row"><button onclick="hcEndPeriod()">End the quarter</button><button onclick="hcSwapEnds()">Swap ends</button><button onclick="hcRedo()">Put back last undo</button><button onclick="openHoopsBoxScore()">Box score</button></div><button onclick="hcSkip()">Close</button></div><div class="hc-label" style="margin-bottom:5px">Violation: pick the team charged</div><div class="hc-row">${HC_VIOLATIONS.map(([id, label]) => `<button onclick="hc.violation=['${id}','${label}'];render()" class="${hc.violation?.[0] === id ? 'on' : ''}">${label}</button>`).join('')}</div>${hc.violation ? `<div class="hc-row" style="margin-top:8px"><button onclick="hcViolation('visitor','${hc.violation[0]}','${hc.violation[1]}')">${escapeHtml(hcName('visitor'))}</button><button onclick="hcViolation('home','${hc.violation[0]}','${hc.violation[1]}')">${escapeHtml(hcName('home'))}</button></div>` : ''}</div>`;
      return;
    case 'sub_out':
      el.innerHTML = `<div class="hc-card hot"><div class="hc-row hc-between"><b>${escapeHtml(hcLabel(hc.subIn))} coming in. Tap who comes out.</b><button onclick="hcSkip()">Cancel</button></div></div>`;
      return;
    case 'sub_in_for':
      el.innerHTML = `<div class="hc-card hot"><div class="hc-row hc-between"><b>${escapeHtml(hcLabel(hc.subOut))} coming out. Tap who comes in from the bench.</b><button onclick="hcSkip()">Cancel</button></div></div>`;
      return;
    case 'replace':
      el.innerHTML = `<div class="hc-card hot"><b>The console has ${escapeHtml(hcLabel(hc.benchCredit.id))} on the bench.</b><div class="hc-sub" style="margin:5px 0 8px">Tap who ${escapeHtml(hcLabel(hc.benchCredit.id))} replaced, and the sub goes in before this play.</div><div class="hc-row"><button onclick="hcCreditOnly()">Credit them, fix the lineup later</button><button onclick="hc.mode=hc.benchCredit.mode;hc.benchCredit=null;render()">Back</button></div></div>`;
      return;
    default:
      el.innerHTML = `${banner}${HC_ACTIONS}`;
  }
}

function hcEventText(e) {
  const p = e.payload || {};
  const team = p.team ? `<b>${escapeHtml(hcName(p.team).slice(0, 3).toUpperCase())}</b> ` : '';
  const who = id => (id ? escapeHtml(hcLabel(id)) : 'Team');
  const notes = hcNotesFor(e.event_id);
  switch (e.event_type) {
    case 'SHOT': {
      const where = p.zone ? ` (${HC_ZONE_NAMES[p.zone] || ''})` : '';
      const kind = (notes.shotType || p.shotType) || `${p.points}`;
      const assist = notes.assistId || p.assistId;
      const block = notes.blockPlayerId || p.blockPlayerId;
      return `${team}${who(p.shooterId)} ${p.made ? 'makes' : 'misses'} ${escapeHtml(kind)}${where}${assist ? `, assist ${who(assist)}` : ''}${block ? `, blocked by ${who(block)}` : ''}`;
    }
    case 'FREE_THROW': return `${team}${who(p.shooterId)} ${p.made ? 'makes' : 'misses'} free throw${p.ofAttempts ? ` ${p.attemptNumber} of ${p.ofAttempts}` : ''}`;
    case 'REBOUND': return `${team}${p.playerId ? who(p.playerId) : 'Team'} ${escapeHtml(p.kind === 'team' ? 'team' : p.kind)} rebound`;
    case 'FOUL': return `${team}Foul on ${who(p.playerId)}${p.foulType && p.foulType !== 'personal' ? ` (${escapeHtml(p.foulType.replace('_', ' '))})` : ''}`;
    case 'TURNOVER': return p.stealPlayerId ? `${who(p.stealPlayerId)} steal, turnover on ${escapeHtml(hcName(p.team))}${notes.turnoverPlayerId ? ` (${who(notes.turnoverPlayerId)})` : ''}` : `${team}Turnover ${who(p.playerId)}`;
    case 'SUBSTITUTION': return `${team}${who(p.inPlayerId)} in for ${who(p.outPlayerId)}`;
    case 'TIMEOUT': return `${team}Timeout`;
    case 'VIOLATION': return `${team}${escapeHtml(String(p.violationType || 'violation').replace(/_/g, ' '))}`;
    case 'HELD_BALL': return 'Jump ball, arrow';
    case 'OPENING_TIP': return `${team}won the tip`;
    case 'PERIOD_TRANSITION': return `Start of ${escapeHtml(p.nextPeriod === 'OT' ? 'overtime' : `Q${p.nextPeriod}`)}`;
    default: return '';
  }
}

function hcRenderFeed() {
  const position = {};
  const events = hcEvents();
  (hoopsState().hoops_events || []).forEach(e => { position[e.event_id] = e.corrects_event_id ? (position[e.corrects_event_id] ?? e.sequence) : e.sequence; });
  const rows = events.filter(e => !['GAME_START', 'LINEUP_SET', 'PLAY_NOTE', 'SET_VALUE', 'DIRECTION_SET', 'RULING'].includes(e.event_type))
    .sort((a, b) => position[b.event_id] - position[a.event_id] || b.sequence - a.sequence);
  document.getElementById('hcFeed').innerHTML = `<div class="hc-row hc-between"><div class="hc-label">Play by play</div><button onclick="openHoopsBoxScore()" style="min-height:30px;padding:3px 9px;font-size:12px">Box score</button></div>` + '<div class="hc-feed" style="max-height:236px;overflow:auto">' + rows.map(e => {
    const seconds = e.payload?.clockSeconds;
    const time = seconds == null ? '' : `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`;
    const fix = e.event_type === 'SHOT' ? `<button onclick="hcFixShot('${e.event_id}')">Fix</button>` : '';
    return `<div class="hc-ev"><span class="t">${time}</span><span>${hcEventText(e)}</span><span>${fix}<button onclick="hcDelete('${e.event_id}')">Delete</button></span></div>`;
  }).join('') + '</div>';
}

function renderHoopsConsole() {
  const root = document.getElementById('hoopsStatConsole');
  if (!root) return;
  const module = document.getElementById('statisticianModule');
  const active = hoopsIsActive();
  // Football's statistician panels make no sense for basketball, and its field slider
  // is what used to show here.
  [...module.children].forEach(child => { if (child !== root) child.classList.toggle('hoops-hidden-for-console', active); });
  root.classList.toggle('hidden', !active);
  hcSyncLiveLayout();
  if (!active || hcDragging) return;
  // The box score pop-up lives in the Command Center panel, which is hidden here.
  const box = document.getElementById('hoopsBoxScoreModal');
  if (box && box.parentElement !== document.body) document.body.appendChild(box);
  hcRenderTop();
  hcRenderSide('visitor');
  hcRenderSide('home');
  hcRenderHead();
  hcRenderCourt();
  hcBindCourt();
  hcRenderToast();
  hcRenderPanel();
  hcRenderFeed();
}

const hcHideFootball = document.createElement('style');
hcHideFootball.textContent = `.hoops-hidden-for-console{display:none !important}
  body.hc-live:not(.hc-show-menu) .suite-header,body.hc-live:not(.hc-show-menu) #moduleNav,body.hc-live .suite-footer{display:none !important}
  body.hc-live .shell{max-width:none !important;width:auto !important;padding:8px !important;margin:0 !important}`;
document.head.appendChild(hcHideFootball);

// Live entry gets the whole screen, so tapping the court never means scrolling to
// reach Made and Missed. The Menu button brings the app's header back.
function hcSyncLiveLayout() {
  const module = document.getElementById('statisticianModule');
  const live = Boolean(module && !module.classList.contains('hidden') && hoopsIsActive());
  document.body.classList.toggle('hc-live', live);
  if (!live) document.body.classList.remove('hc-show-menu');
}
function hcToggleMenu() { document.body.classList.toggle('hc-show-menu'); }
const hcModuleWatch = document.getElementById('statisticianModule');
if (hcModuleWatch) new MutationObserver(hcSyncLiveLayout).observe(hcModuleWatch, { attributes: true, attributeFilter: ['class'] });

setInterval(() => {
  const el = document.getElementById('hcClock');
  if (el && hoopsIsActive()) el.textContent = hcClockText();
}, 500);
