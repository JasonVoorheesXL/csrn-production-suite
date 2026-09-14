// CSRN baseball/softball operator controls (P5: docs/BASEBALL_SOFTBALL_
// ENGINE_SCOPING_PLAN.md). Loaded after the main inline <script> in
// templates/index.html, so it shares that script's top-level globals
// (currentState, api(), render(), escapeHtml(), playerGraphicRosters,
// authenticated) the same way any two classic <script> tags on one page
// share a lexical scope -- no build step, no module system, matching this
// file's own established convention (see csrn-pregame-theme-selector.js).
//
// render()'s own sport branch (templates/index.html) calls
// renderDiamondControlPanel() whenever currentState.sport is baseball/
// softball, and returns before running any of the football-specific
// rendering below it -- this file never runs for a football broadcast.

function diamondIsActive() {
  return currentState && ['baseball', 'softball'].includes(String(currentState.sport || '').toLowerCase());
}

function diamondState() {
  return (currentState && currentState.diamond) || {};
}

function diamondSetStatus(elementId, message, isError = false) {
  const el = document.getElementById(elementId);
  if (!el) return;
  el.textContent = message;
  el.className = isError ? 'status error' : 'status';
}

async function diamondAction(action, payload, statusElementId) {
  try {
    currentState = await api(`/api/diamond/action/${encodeURIComponent(action)}`, payload || {});
    if (statusElementId) diamondSetStatus(statusElementId, 'Done.');
    render();
    return currentState;
  } catch (err) {
    const message = (err.data && (err.data.message || (err.data.messages || []).map(m => m.message || m).join(' '))) || err.message || 'Action failed.';
    if (statusElementId) diamondSetStatus(statusElementId, message, true);
    else alert(message);
    throw err;
  }
}

// --- roster helpers -----------------------------------------------------

function diamondRosterPlayers(side) {
  const schoolId = side === 'home' ? currentState?.home_school_id : currentState?.visitor_school_id;
  if (!schoolId || typeof playerGraphicRosters === 'undefined') return [];
  const sport = String(currentState?.sport || '').toLowerCase();
  const roster = playerGraphicRosters.find(r => r.school_id === schoolId && String(r.sport || '').toLowerCase() === sport);
  const players = (roster?.players || []).filter(p => p.status !== 'inactive');
  return players.slice().sort((a, b) => (Number(a.number) || 999) - (Number(b.number) || 999));
}

function diamondPlayerOptionsHtml(side, selected) {
  const players = diamondRosterPlayers(side);
  if (!players.length) return '<option value="">No active roster players</option>';
  return players.map(p => {
    const label = `${p.number || '—'} · ${[p.first_name, p.last_name].filter(Boolean).join(' ')}`;
    return `<option value="${escapeHtml(p.id)}"${p.id === selected ? ' selected' : ''}>${escapeHtml(label)}</option>`;
  }).join('');
}

function diamondPlayerLabel(side, playerId) {
  if (!playerId) return '(none)';
  const player = diamondRosterPlayers(side).find(p => p.id === playerId);
  if (!player) return playerId;
  return `${player.number || '—'} · ${[player.first_name, player.last_name].filter(Boolean).join(' ')}`;
}

// --- main render ----------------------------------------------------------

function renderDiamondControlPanel() {
  if (!diamondIsActive()) return;
  const d = diamondState();

  document.getElementById('diamondHomeName').textContent = currentState.home_team || 'HOME';
  document.getElementById('diamondVisitorName').textContent = currentState.visitor_team || 'VISITOR';
  document.getElementById('diamondHomeScore').textContent = currentState.home_score ?? d.home_score ?? 0;
  document.getElementById('diamondVisitorScore').textContent = currentState.visitor_score ?? d.visitor_score ?? 0;
  document.getElementById('diamondInning').textContent = `${(d.inning_half || 'TOP')} ${d.inning || 1}`;
  document.getElementById('diamondCount').textContent = `${d.balls || 0}-${d.strikes || 0} · ${d.outs || 0} OUT`;
  const bases = d.base_runners || {};
  document.querySelectorAll('#diamondBases span').forEach(span => {
    span.classList.toggle('occupied', Boolean(bases[span.dataset.base]));
  });
  const badge = document.getElementById('diamondPhaseBadge');
  if (badge) {
    const suspended = Boolean(d.suspension && d.suspension.suspended);
    badge.textContent = suspended ? 'SUSPENDED' : (currentState.status === 'completed' ? 'FINAL' : 'LIVE');
  }

  diamondRenderLineupBuilder();
  diamondRenderSlotInfo();
  diamondRenderWizardFields();
  diamondPopulatePaSelects();
  diamondPopulateRulingSelects();
  diamondRenderBattingOrderAlerts();
}

// --- starting lineups -----------------------------------------------------

function diamondRenderLineupBuilder() {
  if (!diamondIsActive()) return;
  const side = document.getElementById('dlSide')?.value || 'home';
  const d = diamondState();
  const sideState = (d.lineup || {})[side] || { slots: {}, dh_mode: 'NONE' };
  const dhSelect = document.getElementById('dlDhMode');
  if (dhSelect) dhSelect.value = sideState.dh_mode || 'NONE';
  const slotCount = String(currentState?.sport || '').toLowerCase() === 'softball' ? 10 : 9;
  const positions = ['P', 'C', '1B', '2B', '3B', 'SS', 'LF', 'CF', 'RF'];
  const rows = [];
  for (let slot = 1; slot <= slotCount; slot++) {
    const current = (sideState.slots || {})[String(slot)] || {};
    rows.push(`<div class="setup-grid" style="grid-template-columns:60px 1fr 100px">
      <label>Slot ${slot}</label>
      <label>Player<select id="dlPlayer${slot}">${diamondPlayerOptionsHtml(side, current.active_player_id)}</select></label>
      <label>Position<select id="dlPosition${slot}">${positions.map(p => `<option value="${p}"${p === (current.position || '') ? ' selected' : ''}>${p}</option>`).join('')}</select></label>
    </div>`);
  }
  const container = document.getElementById('diamondLineupRows');
  if (container) container.innerHTML = rows.join('');
}

async function diamondStartLineup() {
  const side = document.getElementById('dlSide')?.value || 'home';
  const slotCount = String(currentState?.sport || '').toLowerCase() === 'softball' ? 10 : 9;
  const starters = {};
  const defense = {};
  for (let slot = 1; slot <= slotCount; slot++) {
    const playerId = document.getElementById(`dlPlayer${slot}`)?.value || '';
    const position = document.getElementById(`dlPosition${slot}`)?.value || '';
    if (playerId) {
      starters[slot] = playerId;
      if (position) defense[position] = playerId;
    }
  }
  if (!Object.keys(starters).length) {
    diamondSetStatus('diamondLineupStatus', 'Assign at least one player before saving.', true);
    return;
  }
  const dhMode = document.getElementById('dlDhMode')?.value || 'NONE';
  await diamondAction('start_lineup', {
    side, starters, defense,
    sport: String(currentState?.sport || 'baseball').toLowerCase(),
    dh_mode: dhMode,
  }, 'diamondLineupStatus');
}

// --- lineup-change wizard --------------------------------------------------

function diamondRenderSlotInfo() {
  if (!diamondIsActive()) return;
  const side = document.getElementById('lwSide')?.value || 'home';
  const slotSelect = document.getElementById('lwSlot');
  if (slotSelect && !slotSelect.options.length) {
    const slotCount = String(currentState?.sport || '').toLowerCase() === 'softball' ? 10 : 9;
    slotSelect.innerHTML = Array.from({ length: slotCount }, (_, i) => `<option value="${i + 1}">${i + 1}</option>`).join('');
  }
  diamondPopulateLineupChangeSelects(side);

  const slot = slotSelect?.value || '1';
  const d = diamondState();
  const sideState = (d.lineup || {})[side] || {};
  const slotState = (sideState.slots || {})[slot] || {};
  const history = (slotState.entry_history || []).map(entry =>
    `${entry.entry_type}: ${diamondPlayerLabel(side, entry.player_id)}${entry.exited_event_id ? ' (exited)' : ' (active)'}`
  ).join('\n');
  const info = document.getElementById('diamondSlotInfo');
  if (info) {
    info.textContent = [
      `Starter: ${diamondPlayerLabel(side, slotState.starter_player_id)}`,
      `Currently active: ${diamondPlayerLabel(side, slotState.active_player_id)}`,
      `DH mode: ${sideState.dh_mode || 'NONE'}${sideState.dp_flex ? ' · DP/FLEX active' : ''}`,
      history ? `History:\n${history}` : 'No substitutions yet this game.',
    ].join('\n');
  }
}

function diamondPopulateLineupChangeSelects(side) {
  const options = diamondPlayerOptionsHtml(side);
  ['lwIncomingPlayer', 'lwDpPlayer', 'lwFlexPlayer', 'lwRunnerFor', 'lwRunnerPlayer'].forEach(id => {
    const el = document.getElementById(id);
    if (el && el.dataset.side !== side) {
      el.innerHTML = options;
      el.dataset.side = side;
    }
  });
}

function diamondRenderWizardFields() {
  if (!diamondIsActive()) return;
  const action = document.getElementById('lwAction')?.value || 'substitute';
  document.querySelectorAll('#diamondControlPanel .diamond-wizard-field').forEach(field => {
    field.classList.toggle('shown', fieldAppliesToAction(field, action));
  });
}

function fieldAppliesToAction(field, action) {
  const fields = (field.dataset.fields || '').split(',').map(s => s.trim());
  return fields.includes(action);
}

function diamondActivePlayerInSlot(side, slot) {
  const d = diamondState();
  const slotState = ((d.lineup || {})[side]?.slots || {})[String(slot)] || {};
  return slotState.active_player_id || '';
}

async function diamondSubmitLineupAction() {
  const action = document.getElementById('lwAction')?.value || 'substitute';
  const side = document.getElementById('lwSide')?.value || 'home';
  const slot = Number(document.getElementById('lwSlot')?.value || 1);
  const incomingPlayer = document.getElementById('lwIncomingPlayer')?.value || '';
  const reason = document.getElementById('lwReason')?.value || '';
  const sport = String(currentState?.sport || 'baseball').toLowerCase();

  const payloadBySide = { side };
  let payload;
  switch (action) {
    case 'substitute':
      payload = { ...payloadBySide, slot, incoming_player_id: incomingPlayer, sport };
      break;
    case 'reenter':
      payload = { ...payloadBySide, slot, player_id: incomingPlayer };
      break;
    case 'position_change':
      // position_change(side, position, player_id) has no slot argument --
      // it names the PLAYER whose position is changing directly. The
      // wizard's slot selector still drives which player that is (the
      // slot's current active occupant), so the operator picks a slot as
      // the natural way to find them, but "Player" (lwIncomingPlayer) is
      // what actually gets sent, defaulting to the slot's own occupant.
      payload = {
        ...payloadBySide,
        position: document.getElementById('lwPosition')?.value || '',
        player_id: incomingPlayer || diamondActivePlayerInSlot(side, slot),
      };
      break;
    case 'replace_on_defense_only':
      payload = {
        ...payloadBySide,
        position: document.getElementById('lwPosition')?.value || '',
        incoming_player_id: incomingPlayer,
      };
      break;
    case 'terminate_player_dh_role': {
      // reason is REQUIRED by this action (no default) -- lwReasonRequired
      // is its own dedicated field so a blank "Reason (optional)" input
      // used by other actions can never be mistaken for satisfying it.
      const requiredReason = document.getElementById('lwReasonRequired')?.value || '';
      if (!requiredReason.trim()) {
        diamondSetStatus('diamondLineupActionStatus', 'A reason is required to end a player/DH role.', true);
        return;
      }
      payload = {
        ...payloadBySide,
        player_id: incomingPlayer || diamondActivePlayerInSlot(side, slot),
        reason: requiredReason,
      };
      await diamondAction(action, payload, 'diamondLineupActionStatus');
      diamondRenderSlotInfo();
      return;
    }
    case 'start_dp_flex':
      payload = {
        ...payloadBySide,
        dp_player_id: document.getElementById('lwDpPlayer')?.value || '',
        flex_player_id: document.getElementById('lwFlexPlayer')?.value || '',
        dp_slot: slot,
      };
      break;
    case 'dp_plays_defense_for_flex':
    case 'flex_bats_for_dp':
      payload = { ...payloadBySide };
      break;
    case 'dp_reenters':
      payload = {
        ...payloadBySide,
        flex_resulting_state: document.getElementById('lwFlexResultingState')?.value || 'ON_BASE',
      };
      break;
    case 'substitute_for_dp':
    case 'substitute_for_flex':
      payload = { ...payloadBySide, incoming_player_id: incomingPlayer };
      break;
    case 'enter_courtesy_runner':
      payload = {
        ...payloadBySide,
        runner_player_id: incomingPlayer,
        for_player_id: document.getElementById('lwRunnerFor')?.value || '',
        for_role_at_time: document.getElementById('lwRoleAtTime')?.value || 'PITCHER',
      };
      break;
    case 'return_courtesy_runner':
      payload = { ...payloadBySide, runner_player_id: document.getElementById('lwRunnerPlayer')?.value || incomingPlayer };
      break;
    case 'record_defensive_meeting':
    case 'record_charged_conference':
      payload = { side };
      break;
    default:
      payload = { ...payloadBySide };
  }
  if (reason) payload.reason = reason;
  await diamondAction(action, payload, 'diamondLineupActionStatus');
  diamondRenderSlotInfo();
}

// --- plate appearance -------------------------------------------------------

function diamondPopulatePaSelects() {
  const d = diamondState();
  const battingTeam = document.getElementById('paBattingTeam');
  if (battingTeam && !battingTeam.dataset.touched) {
    battingTeam.value = (d.inning_half || 'TOP').toUpperCase().startsWith('T') ? 'visitor' : 'home';
  }
  const battingSide = battingTeam?.value || 'visitor';
  const fieldingSide = battingSide === 'home' ? 'visitor' : 'home';

  const batter = document.getElementById('paBatter');
  if (batter) batter.innerHTML = diamondPlayerOptionsHtml(battingSide);
  const pitcher = document.getElementById('paPitcher');
  if (pitcher) {
    const fieldingSlots = (d.lineup || {})[fieldingSide]?.defense || {};
    pitcher.innerHTML = diamondPlayerOptionsHtml(fieldingSide, fieldingSlots.P);
  }

  const bases = d.base_runners || {};
  document.querySelectorAll('#paRunnerOutcomes select[data-from]').forEach(select => {
    const base = select.dataset.from;
    if (base === 'batter') return;
    select.disabled = !bases[base];
    if (!bases[base]) select.value = '';
  });
}

async function diamondRecordPlateAppearance() {
  const battingTeam = document.getElementById('paBattingTeam')?.value || 'visitor';
  const batterId = document.getElementById('paBatter')?.value || '';
  const pitcherId = document.getElementById('paPitcher')?.value || '';
  const resultCode = document.getElementById('paResultCode')?.value || '';
  const outsRecorded = Number(document.getElementById('paOutsRecorded')?.value || 0);
  const hits = Number(document.getElementById('paHits')?.value || 0);
  const errors = Number(document.getElementById('paErrors')?.value || 0);

  const runnerOutcomes = [];
  document.querySelectorAll('#paRunnerOutcomes select[data-from]').forEach(select => {
    const to = select.value;
    if (!to) return;
    const outcome = { from: select.dataset.from, to };
    if (select.dataset.from === 'batter') outcome.playerId = batterId;
    runnerOutcomes.push(outcome);
  });

  if (!batterId) {
    diamondSetStatus('diamondPaStatus', 'Select a batter first.', true);
    return;
  }

  await diamondAction('record_plate_appearance', {
    battingTeam, batterId, pitcherId, resultCode,
    outsRecorded, hits, errors, runnerOutcomes,
  }, 'diamondPaStatus');

  // Reset for the next batter -- battingTeam stays (may flip on inning-half
  // change, re-synced by diamondPopulatePaSelects on the next render()).
  const battingTeamEl = document.getElementById('paBattingTeam');
  if (battingTeamEl) battingTeamEl.dataset.touched = '';
  document.querySelectorAll('#paRunnerOutcomes select[data-from]').forEach(select => { select.value = ''; });
  document.getElementById('paOutsRecorded').value = '0';
  document.getElementById('paHits').value = '0';
  document.getElementById('paErrors').value = '0';
}

// --- batting-order check (spec Sec.15.1: detection != enforcement) -------

function diamondRenderBattingOrderAlerts() {
  if (!diamondIsActive()) return;
  const side = document.getElementById('boSide')?.value || 'visitor';
  const d = diamondState();
  const sideState = (d.lineup || {})[side] || {};

  const slotSelect = document.getElementById('boExpectedSlot');
  if (slotSelect) {
    const slotCount = String(currentState?.sport || '').toLowerCase() === 'softball' ? 10 : 9;
    slotSelect.innerHTML = Array.from({ length: slotCount }, (_, i) => `<option value="${i + 1}">${i + 1}</option>`).join('');
  }
  const actualBatter = document.getElementById('boActualBatter');
  if (actualBatter) actualBatter.innerHTML = diamondPlayerOptionsHtml(side);

  const alerts = sideState.batting_order_alerts || [];
  const container = document.getElementById('diamondBattingOrderAlerts');
  if (!container) return;
  const open = alerts.map((alert, index) => ({ alert, index })).filter(({ alert }) => alert.status === 'OPEN');
  if (!open.length) {
    container.innerHTML = '<p class="section-note">No open batting-order alerts.</p>';
    return;
  }
  container.innerHTML = open.map(({ alert, index }) => `
    <div class="status warning">
      Slot ${alert.expected_slot} expected ${escapeHtml(diamondPlayerLabel(side, alert.expected_player_id))},
      ${escapeHtml(diamondPlayerLabel(side, alert.actual_batter_id))} batted instead.
      <div class="setup-grid">
        <label>Appeal Type<input id="boAppealType${index}" placeholder="e.g. batting out of order"></label>
        <label>Ruling<select id="boRulingResult${index}"><option value="UPHELD">Appeal Upheld (batter out)</option><option value="DENIED">Appeal Denied</option></select></label>
        <label>Next Batter Slot<input id="boNextSlot${index}" type="number" min="1" value="${alert.expected_slot}"></label>
      </div>
      <div class="button-row">
        <button class="warning" onclick="diamondApplyAppealRuling(${index})">Apply Appeal Ruling</button>
        <button onclick="diamondDismissAlert(${index})">Dismiss (No Appeal)</button>
      </div>
    </div>
  `).join('');
}

async function diamondRecordBatter() {
  const side = document.getElementById('boSide')?.value || 'visitor';
  const expectedSlot = Number(document.getElementById('boExpectedSlot')?.value || 1);
  const actualBatterId = document.getElementById('boActualBatter')?.value || '';
  if (!actualBatterId) {
    diamondSetStatus('diamondBattingOrderStatus', 'Select the actual batter.', true);
    return;
  }
  await diamondAction('record_batter', { side, expected_slot: expectedSlot, actual_batter_id: actualBatterId }, 'diamondBattingOrderStatus');
  diamondRenderBattingOrderAlerts();
}

async function diamondApplyAppealRuling(alertIndex) {
  const side = document.getElementById('boSide')?.value || 'visitor';
  const appealType = document.getElementById(`boAppealType${alertIndex}`)?.value || '';
  const rulingResult = document.getElementById(`boRulingResult${alertIndex}`)?.value || 'DENIED';
  const nextBatterSlot = Number(document.getElementById(`boNextSlot${alertIndex}`)?.value || 1);
  await diamondAction('apply_appeal_ruling', {
    side, alert_index: alertIndex,
    appeal_type: appealType, ruling_result: rulingResult, next_batter_slot: nextBatterSlot,
  }, 'diamondBattingOrderStatus');
  diamondRenderBattingOrderAlerts();
}

async function diamondDismissAlert(alertIndex) {
  const side = document.getElementById('boSide')?.value || 'visitor';
  await diamondAction('dismiss_alert_no_appeal', { side, alert_index: alertIndex }, 'diamondBattingOrderStatus');
  diamondRenderBattingOrderAlerts();
}

// --- ruling / undo / redo / suspend / resume / confirm-end ---------------

function diamondPopulateRulingSelects() {
  const d = diamondState();
  const battingSide = document.getElementById('paBattingTeam')?.value || 'visitor';
  const batter = document.getElementById('rulingBatter');
  if (batter) batter.innerHTML = diamondPlayerOptionsHtml(battingSide);
  const bases = d.base_runners || {};
  document.querySelectorAll('#rulingBaseAwards select[data-from]').forEach(select => {
    const base = select.dataset.from;
    if (base === 'batter') return;
    select.disabled = !bases[base];
    if (!bases[base]) select.value = '';
  });
}

async function diamondRecordRuling() {
  // Sec.6.2 UmpireRulingPayload -- diamond_state_service.apply_ruling()
  // reads baseAwards (each {fromBase, toBase, playerId?}), outsAwarded
  // (a list; only its length is used), and ballStatus. Applied exactly as
  // recorded -- this form never infers a "deserved" outcome.
  const batterId = document.getElementById('rulingBatter')?.value || '';
  const baseAwards = [];
  document.querySelectorAll('#rulingBaseAwards select[data-from]').forEach(select => {
    const toBase = select.value;
    if (!toBase) return;
    const award = { fromBase: select.dataset.from, toBase };
    if (select.dataset.from === 'batter') award.playerId = batterId;
    baseAwards.push(award);
  });
  const outsCount = Number(document.getElementById('rulingOutsAwarded')?.value || 0);
  const outsAwarded = Array.from({ length: outsCount }, (_, i) => ({ index: i }));
  const ballStatus = document.getElementById('rulingBallStatus')?.value || 'LIVE';

  if (!baseAwards.length && !outsAwarded.length) {
    diamondSetStatus('diamondRulingStatus', 'Award at least one base or out before recording a ruling.', true);
    return;
  }

  await diamondAction('record_ruling', { baseAwards, outsAwarded, ballStatus }, 'diamondRulingStatus');
}

async function diamondUndo() { await diamondAction('undo', {}, 'diamondActionStatus'); }
async function diamondRedo() { await diamondAction('redo', {}, 'diamondActionStatus'); }
async function diamondSuspend() {
  if (!confirm('Suspend this game? Play can be resumed later from this exact state.')) return;
  await diamondAction('suspend', { reason: prompt('Reason for suspension (optional):', '') || '' }, 'diamondActionStatus');
}
async function diamondResume() { await diamondAction('resume', {}, 'diamondActionStatus'); }
async function diamondConfirmGameEnd() {
  if (!confirm('Confirm the official end of this game per the umpire/scorer\'s determination?')) return;
  await diamondAction('confirm_game_end', { reason: prompt('Reason (e.g. regulation, run rule, walk-off):', '') || '' }, 'diamondActionStatus');
}

// --- box score modal --------------------------------------------------------

async function openDiamondBoxScore() {
  const modal = document.getElementById('diamondBoxScoreModal');
  const content = document.getElementById('diamondBoxScoreContent');
  if (!modal || !content) return;
  modal.classList.remove('hidden');
  content.textContent = 'Loading…';
  try {
    const report = await api('/api/diamond/box-score');
    content.innerHTML = diamondBoxScoreHtml(report);
  } catch (err) {
    content.textContent = 'Unable to load box score.';
  }
}

function closeDiamondBoxScore() {
  document.getElementById('diamondBoxScoreModal')?.classList.add('hidden');
}

function diamondAnyRosterLabel(playerId) {
  // box_score_service only knows player ids (its own module docstring: name
  // resolution against a roster is the caller's job) -- this checks both
  // teams' rosters since a box score line doesn't say which side a batter/
  // pitcher was on, only their id.
  return diamondPlayerLabel('home', playerId) !== playerId
    ? diamondPlayerLabel('home', playerId)
    : diamondPlayerLabel('visitor', playerId);
}

function diamondBoxScoreHtml(report) {
  const line = report.line_score || {};
  const battingRows = Object.entries(report.batting || {}).map(([playerId, line]) =>
    `<tr><td>${escapeHtml(diamondAnyRosterLabel(playerId))}</td><td>${line.ab}</td><td>${line.h}</td><td>${line.r}</td><td>${line.rbi}</td><td>${line.bb}</td><td>${line.so}</td><td>${line.hbp}</td></tr>`
  ).join('');
  const pitchingRows = Object.entries(report.pitching || {}).map(([playerId, line]) =>
    `<tr><td>${escapeHtml(diamondAnyRosterLabel(playerId))}</td><td>${line.ip}</td><td>${line.h}</td><td>${line.r}</td><td>${line.bb}</td><td>${line.so}</td></tr>`
  ).join('');
  return `
    <p><strong>Visitor</strong> ${line.visitor?.runs ?? 0} R · ${line.visitor?.hits ?? 0} H · ${line.visitor?.errors ?? 0} E</p>
    <p><strong>Home</strong> ${line.home?.runs ?? 0} R · ${line.home?.hits ?? 0} H · ${line.home?.errors ?? 0} E</p>
    <h4>Batting</h4>
    <table class="diamond-lineup-table"><tr><td>Player</td><td>AB</td><td>H</td><td>R</td><td>RBI</td><td>BB</td><td>SO</td><td>HBP</td></tr>${battingRows || '<tr><td colspan="8">No plate appearances yet.</td></tr>'}</table>
    <h4>Pitching</h4>
    <table class="diamond-lineup-table"><tr><td>Player</td><td>IP</td><td>H</td><td>R</td><td>BB</td><td>SO</td></tr>${pitchingRows || '<tr><td colspan="5">No pitching appearances yet.</td></tr>'}</table>
    <p class="section-note">${(report.notes || {}).earned_runs || ''}</p>
  `;
}

// --- create-broadcast ruleset scoping ---------------------------------------

async function syncCreateBroadcastRulesetOptions() {
  const select = document.getElementById('rulesetJurisdiction');
  const sportField = document.getElementById('sport');
  if (!select || !sportField) return;
  const sport = sportField.value.toLowerCase();
  // basketball (P5) reuses this same generic re-scoping -- it's not
  // baseball/softball-specific despite the file it lives in (this
  // function predates hoops_controls.js and there was no reason to
  // duplicate it there).
  if (!['baseball', 'softball', 'basketball'].includes(sport)) return; // football keeps its existing static option
  try {
    const rows = (await api('/api/rulesets'))?.rulesets;
    if (!Array.isArray(rows)) return;
    const applicable = rows.filter(r => (r.sport || '') === sport);
    if (!applicable.length) return;
    select.innerHTML = applicable.map(r => {
      const c = r.country || '', reg = r.region || '', assoc = r.association || '';
      return `<option value="${escapeHtml(r.id)}" data-country="${escapeHtml(c)}" data-region="${escapeHtml(reg)}" data-association="${escapeHtml(assoc)}">${escapeHtml(r.label || r.id)}</option>`;
    }).join('');
    if (typeof syncRulesetJurisdictionDataset === 'function') syncRulesetJurisdictionDataset();
  } catch (_) {
    // keep whatever options are already there
  }
}
