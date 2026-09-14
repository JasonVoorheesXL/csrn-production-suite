// CSRN basketball operator controls (P5: docs/BASKETBALL_ENGINE_SCOPING_
// PLAN.md). Loaded after the main inline <script> in templates/index.html
// (and after csrn-diamond-controls.js), so it shares that script's
// top-level globals (currentState, api(), render(), escapeHtml(),
// playerGraphicRosters, authenticated) the same way csrn-diamond-controls.js
// already does -- no build step, no module system.
//
// render()'s own sport branch (templates/index.html) calls
// renderHoopsControlPanel() whenever currentState.sport is basketball, and
// returns before running any of the football-specific rendering below it --
// this file never runs for a football (or baseball/softball) broadcast.

function hoopsIsActive() {
  return currentState && String(currentState.sport || '').toLowerCase() === 'basketball';
}

function hoopsState() {
  return (currentState && currentState.hoops) || {};
}

function hoopsSetStatus(elementId, message, isError = false) {
  const el = document.getElementById(elementId);
  if (!el) return;
  el.textContent = message;
  el.className = isError ? 'status error' : 'status';
}

async function hoopsAction(action, payload, statusElementId) {
  try {
    currentState = await api(`/api/hoops/action/${encodeURIComponent(action)}`, payload || {});
    if (statusElementId) hoopsSetStatus(statusElementId, 'Done.');
    render();
    return currentState;
  } catch (err) {
    const message = (err.data && (err.data.message || (err.data.messages || []).map(m => m.message || m).join(' '))) || err.message || 'Action failed.';
    if (statusElementId) hoopsSetStatus(statusElementId, message, true);
    else alert(message);
    throw err;
  }
}

// --- roster helpers -----------------------------------------------------

function hoopsRosterPlayers(side) {
  const schoolId = side === 'home' ? currentState?.home_school_id : currentState?.visitor_school_id;
  if (!schoolId || typeof playerGraphicRosters === 'undefined') return [];
  const roster = playerGraphicRosters.find(r => r.school_id === schoolId && String(r.sport || '').toLowerCase() === 'basketball');
  const players = (roster?.players || []).filter(p => p.status !== 'inactive');
  return players.slice().sort((a, b) => (Number(a.number) || 999) - (Number(b.number) || 999));
}

// The players actually on the floor for `side` -- Sec.3.1's invariant
// ("exactly 5 *_on_floor per team while clock_running") is what a live
// broadcast should have, so shot/FT/rebound/foul/turnover selects are
// scoped to these once a starting five has been saved, falling back to
// the full roster before that (so the panel isn't empty pre-tip-off).
function hoopsOnFloorPlayers(side) {
  const onFloorIds = hoopsState()[`${side}_on_floor`] || [];
  const roster = hoopsRosterPlayers(side);
  if (!onFloorIds.length) return roster;
  const byId = new Map(roster.map(p => [p.id, p]));
  return onFloorIds.map(id => byId.get(id) || { id, number: '', first_name: '', last_name: id });
}

function hoopsPlayerOptionsHtml(players, selected) {
  if (!players.length) return '<option value="">No active roster players</option>';
  return players.map(p => {
    const label = `${p.number || '—'} · ${[p.first_name, p.last_name].filter(Boolean).join(' ')}`;
    return `<option value="${escapeHtml(p.id)}"${p.id === selected ? ' selected' : ''}>${escapeHtml(label)}</option>`;
  }).join('');
}

// --- main render ----------------------------------------------------------

function renderHoopsControlPanel() {
  if (!hoopsIsActive()) return;
  const h = hoopsState();

  document.getElementById('hoopsHomeName').textContent = currentState.home_team || 'HOME';
  document.getElementById('hoopsVisitorName').textContent = currentState.visitor_team || 'VISITOR';
  document.getElementById('hoopsHomeScore').textContent = currentState.home_score ?? 0;
  document.getElementById('hoopsVisitorScore').textContent = currentState.visitor_score ?? 0;
  document.getElementById('hoopsPeriod').textContent = `Period ${currentState.period || '1'}`;
  const clockSeconds = Number(currentState.clock_seconds || 0);
  document.getElementById('hoopsClock').textContent = `${Math.floor(clockSeconds / 60)}:${String(clockSeconds % 60).padStart(2, '0')}`;
  const shotClockEl = document.getElementById('hoopsShotClock');
  if (shotClockEl) {
    shotClockEl.textContent = h.shot_clock_visible && h.shot_clock_seconds != null ? `Shot clock: ${h.shot_clock_seconds}` : '';
  }
  const arrowEl = document.getElementById('hoopsPossessionArrow');
  if (arrowEl) arrowEl.textContent = h.possession_arrow ? `Arrow: ${h.possession_arrow.toUpperCase()}` : '';
  document.getElementById('hoopsHomeFoulsBonus').textContent = `Fouls: ${h.home_team_fouls ?? 0} · Bonus: ${h.home_bonus || 'NONE'} · TO: ${h.home_timeouts ?? 0}`;
  document.getElementById('hoopsVisitorFoulsBonus').textContent = `Fouls: ${h.visitor_team_fouls ?? 0} · Bonus: ${h.visitor_bonus || 'NONE'} · TO: ${h.visitor_timeouts ?? 0}`;

  const badge = document.getElementById('hoopsPhaseBadge');
  if (badge) badge.textContent = currentState.status === 'completed' ? 'FINAL' : 'LIVE';

  hoopsRenderLineupBuilder();
  hoopsPopulateOnFloorSelects();
  hoopsPopulateSubstituteSelects();
  hoopsSyncShotFields();
  hoopsSyncFoulFields();
}

// --- starting five ----------------------------------------------------------

function hoopsRenderLineupBuilder() {
  if (!hoopsIsActive()) return;
  const side = document.getElementById('hlSide')?.value || 'home';
  const onFloor = new Set(hoopsState()[`${side}_on_floor`] || []);
  const roster = hoopsRosterPlayers(side);
  const rows = [1, 2, 3, 4, 5].map((slot, index) => {
    const currentId = [...onFloor][index] || '';
    return `<div class="setup-grid" style="grid-template-columns:60px 1fr">
      <label>Starter ${slot}</label>
      <label>Player<select id="hlPlayer${slot}">${hoopsPlayerOptionsHtml(roster, currentId)}</select></label>
    </div>`;
  });
  const container = document.getElementById('hoopsLineupRows');
  if (container) container.innerHTML = rows.join('');
}

async function hoopsSetStartingFive() {
  const side = document.getElementById('hlSide')?.value || 'home';
  const playerIds = [1, 2, 3, 4, 5]
    .map(slot => document.getElementById(`hlPlayer${slot}`)?.value || '')
    .filter(Boolean);
  if (playerIds.length !== 5 || new Set(playerIds).size !== 5) {
    hoopsSetStatus('hoopsLineupStatus', 'Select 5 distinct players before saving.', true);
    return;
  }
  await hoopsAction('set_starting_five', { team: side, player_ids: playerIds }, 'hoopsLineupStatus');
}

// --- on-floor-scoped selects for shot/FT/rebound/foul/turnover --------------

function hoopsPopulateOnFloorSelects() {
  if (!hoopsIsActive()) return;
  const fill = (teamSelectId, playerSelectId, includeNone) => {
    const team = document.getElementById(teamSelectId)?.value || 'home';
    const select = document.getElementById(playerSelectId);
    if (!select) return;
    const current = select.value;
    const options = hoopsPlayerOptionsHtml(hoopsOnFloorPlayers(team), current);
    select.innerHTML = includeNone ? `<option value="">(unspecified)</option>${options}` : options;
    if (current && [...select.options].some(o => o.value === current)) select.value = current;
  };
  fill('shTeam', 'shShooter', false);
  fill('shTeam', 'shAssist', true);
  fill('shTeam', 'shBlocker', true); // opponent would actually block -- kept simple: same-roster picker, operator picks correctly
  fill('ftTeam', 'ftShooter', false);
  fill('rbTeam', 'rbPlayer', true);
  fill('flTeam', 'flPlayer', false);
  fill('toTeam', 'toPlayer', true);
  fill('toTeam', 'toStealer', true);
}

function hoopsSyncShotFields() {
  const made = document.getElementById('shMade')?.value !== 'false';
  document.querySelectorAll('.shot-field-made').forEach(el => el.classList.toggle('hidden', !made));
  document.querySelectorAll('.shot-field-missed').forEach(el => el.classList.toggle('hidden', made));
}

function hoopsSyncFoulFields() {
  const isShooting = document.getElementById('flType')?.value === 'shooting';
  document.querySelectorAll('.foul-field-shooting').forEach(el => el.classList.toggle('hidden', !isShooting));
}

// --- shot / free throw / rebound ---------------------------------------------

async function hoopsRecordShot() {
  const team = document.getElementById('shTeam')?.value || 'home';
  const made = document.getElementById('shMade')?.value === 'true';
  const payload = {
    team, made,
    points: Number(document.getElementById('shPoints')?.value || 2),
    shooterId: document.getElementById('shShooter')?.value || '',
  };
  if (made) {
    const assistId = document.getElementById('shAssist')?.value || '';
    if (assistId) payload.assistId = assistId;
    payload.andOne = document.getElementById('shAndOne')?.value === 'true';
  } else {
    const blockPlayerId = document.getElementById('shBlocker')?.value || '';
    if (blockPlayerId) payload.blockPlayerId = blockPlayerId;
  }
  await hoopsAction('shot', payload, 'hoopsShotStatus');
}

async function hoopsRecordFreeThrow() {
  await hoopsAction('free_throw', {
    team: document.getElementById('ftTeam')?.value || 'home',
    made: document.getElementById('ftMade')?.value === 'true',
    shooterId: document.getElementById('ftShooter')?.value || '',
  }, 'hoopsFreeThrowStatus');
}

async function hoopsRecordRebound() {
  const playerId = document.getElementById('rbPlayer')?.value || '';
  const payload = { team: document.getElementById('rbTeam')?.value || 'home', kind: document.getElementById('rbKind')?.value || 'defensive' };
  if (playerId) payload.playerId = playerId;
  await hoopsAction('rebound', payload, 'hoopsReboundStatus');
}

// --- foul --------------------------------------------------------------------

async function hoopsRecordFoul() {
  const foulType = document.getElementById('flType')?.value || 'personal';
  const payload = {
    team: document.getElementById('flTeam')?.value || 'home',
    playerId: document.getElementById('flPlayer')?.value || '',
    foulType,
  };
  if (foulType === 'shooting') {
    payload.isShootingFoul = true;
    payload.shotPoints = Number(document.getElementById('flShotPoints')?.value || 2);
    payload.andOne = document.getElementById('flAndOne')?.value === 'true';
  }
  // free_throws_proposed (the engine's "engine proposes, operator
  // confirms" suggestion -- hoops_rules_service.foul()'s own docstring)
  // is not surfaced here: routes/hoops_game_routes.py's action endpoint
  // returns only result.data["state"] to the browser, same as every
  // diamond action's response shape -- there is no extra-data channel to
  // read it from client-side. The operator judges the free-throw count
  // from the recorded foul type/bonus (shown in the scoreboard strip)
  // and records each attempt via the Free Throw form above.
  await hoopsAction('foul', payload, 'hoopsFoulStatus');
}

// --- substitution --------------------------------------------------------------

function hoopsPopulateSubstituteSelects() {
  if (!hoopsIsActive()) return;
  const side = document.getElementById('suSide')?.value || 'home';
  const onFloor = hoopsOnFloorPlayers(side);
  const roster = hoopsRosterPlayers(side);
  const onFloorIds = new Set((hoopsState()[`${side}_on_floor`] || []));
  const bench = roster.filter(p => !onFloorIds.has(p.id));
  const outSelect = document.getElementById('suOut');
  const inSelect = document.getElementById('suIn');
  if (outSelect) outSelect.innerHTML = hoopsPlayerOptionsHtml(onFloor, outSelect.value);
  if (inSelect) inSelect.innerHTML = hoopsPlayerOptionsHtml(bench.length ? bench : roster, inSelect.value);
}

async function hoopsSubstitute() {
  await hoopsAction('substitute', {
    team: document.getElementById('suSide')?.value || 'home',
    out_player_id: document.getElementById('suOut')?.value || '',
    in_player_id: document.getElementById('suIn')?.value || '',
  }, 'hoopsSubstituteStatus');
}

// --- turnover / held ball --------------------------------------------------------

async function hoopsRecordTurnover() {
  const playerId = document.getElementById('toPlayer')?.value || '';
  const stealPlayerId = document.getElementById('toStealer')?.value || '';
  const payload = { team: document.getElementById('toTeam')?.value || 'home' };
  if (playerId) payload.playerId = playerId;
  if (stealPlayerId) payload.stealPlayerId = stealPlayerId;
  await hoopsAction('turnover', payload, 'hoopsTurnoverStatus');
}

async function hoopsRecordHeldBall() {
  await hoopsAction('held_ball', {}, 'hoopsTurnoverStatus');
}

// --- violation ---------------------------------------------------------------

async function hoopsRecordViolation() {
  const possessionTo = document.getElementById('vlPossessionTo')?.value || '';
  const payload = {
    team: document.getElementById('vlTeam')?.value || 'home',
    violationType: document.getElementById('vlType')?.value || 'traveling',
  };
  if (possessionTo) payload.possessionTo = possessionTo;
  await hoopsAction('violation', payload, 'hoopsViolationStatus');
}

// --- timeout -------------------------------------------------------------------

async function hoopsTimeout(team) {
  await hoopsAction('timeout', { team }, 'hoopsTimeoutStatus');
}

// --- ruling / manual set-value ----------------------------------------------------

async function hoopsRecordRuling() {
  const payload = {};
  const scoreTeam = document.getElementById('rlScoreTeam')?.value || '';
  const scorePoints = Number(document.getElementById('rlScorePoints')?.value || 0);
  if (scoreTeam && scorePoints) payload.scoreAdjustment = { team: scoreTeam, points: scorePoints };
  const possessionTo = document.getElementById('rlPossessionTo')?.value || '';
  if (possessionTo) payload.possessionTo = possessionTo;
  const clockAdjustment = Number(document.getElementById('rlClockAdjustment')?.value || 0);
  if (clockAdjustment) payload.clockSecondsAdjustment = clockAdjustment;
  await hoopsAction('ruling', payload, 'hoopsRulingStatus');
}

async function hoopsSetValue() {
  const field = document.getElementById('svField')?.value || '';
  const raw = document.getElementById('svValue')?.value ?? '';
  const value = raw === '' ? null : raw;
  // {field, value} as top-level payload keys -- set_value(state, field,
  // value) takes two plain arguments, not a single `payload` Mapping, so
  // hoops_game_operations_service._bind_kwargs() binds them by name
  // directly (same generic path hoopsAction() already posts through).
  await hoopsAction('set_value', { field, value }, 'hoopsSetValueStatus');
}

// --- undo / redo / confirm game end / box score ------------------------------------

async function hoopsUndo() { await hoopsAction('undo', {}, 'hoopsActionStatus'); }
async function hoopsRedo() { await hoopsAction('redo', {}, 'hoopsActionStatus'); }

async function hoopsConfirmGameEnd() {
  if (!confirm('Confirm the official end of this game? This marks the broadcast completed.')) return;
  await hoopsAction('confirm_game_end', { reason: 'OFFICIAL' }, 'hoopsActionStatus');
}

async function openHoopsBoxScore() {
  const modal = document.getElementById('hoopsBoxScoreModal');
  const content = document.getElementById('hoopsBoxScoreContent');
  if (!modal || !content) return;
  content.innerHTML = 'Loading…';
  modal.classList.remove('hidden');
  try {
    const report = await api('/api/hoops/box-score');
    const totals = report.team_totals || {};
    const players = report.players || {};
    const rows = Object.entries(players).map(([playerId, line]) => {
      const home = hoopsRosterPlayers('home').find(p => p.id === playerId);
      const visitor = hoopsRosterPlayers('visitor').find(p => p.id === playerId);
      const player = home || visitor;
      const label = player ? `${player.number || '—'} · ${[player.first_name, player.last_name].filter(Boolean).join(' ')}` : playerId;
      return `<tr><td>${escapeHtml(label)}</td><td>${line.pts}</td><td>${line.reb}</td><td>${line.ast}</td><td>${line.stl}</td><td>${line.blk}</td><td>${line.to}</td><td>${line.pf}</td><td>${line.fgm}/${line.fga}</td><td>${line.fg3m}/${line.fg3a}</td><td>${line.ftm}/${line.fta}</td></tr>`;
    }).join('');
    content.innerHTML = `
      <p><strong>${escapeHtml(currentState.home_team || 'Home')}</strong> ${totals.home?.score ?? 0} · Fouls ${totals.home?.team_fouls ?? 0} · Bonus ${totals.home?.bonus ?? 'NONE'}</p>
      <p><strong>${escapeHtml(currentState.visitor_team || 'Visitor')}</strong> ${totals.visitor?.score ?? 0} · Fouls ${totals.visitor?.team_fouls ?? 0} · Bonus ${totals.visitor?.bonus ?? 'NONE'}</p>
      <table class="diamond-lineup-table"><tr><td>Player</td><td>PTS</td><td>REB</td><td>AST</td><td>STL</td><td>BLK</td><td>TO</td><td>PF</td><td>FG</td><td>3P</td><td>FT</td></tr>${rows || '<tr><td colspan="11">No plays recorded yet.</td></tr>'}</table>
    `;
  } catch (err) {
    content.innerHTML = `<p class="status error">${escapeHtml(err.message || 'Failed to load box score.')}</p>`;
  }
}

function closeHoopsBoxScore() {
  document.getElementById('hoopsBoxScoreModal')?.classList.add('hidden');
}
