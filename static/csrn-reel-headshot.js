// The reel headshot editor on the player form: place an oval over the head, see the
// cut-out on a paper figure, and save only what looks right. Uses the page's
// currentRoster, currentPlayer, loadRosters(), openRoster() and editRosterPlayer().

const REEL_HEAD_DEFAULT = { x: 0.5, y: 0.3, width: 0.4, height: 0.4, tolerance: 30 };
let reelHead = null;

document.head.insertAdjacentHTML('beforeend', '<style>.reel-head-field{border:1px solid #333;border-radius:8px;padding:10px}.reel-head-row{display:flex;align-items:center;gap:12px;flex-wrap:wrap}.reel-head-row>div{flex:1;min-width:180px}.reel-head-row img{width:64px;height:64px;object-fit:contain;background:#2f6b33;border-radius:8px}</style>');

function reelHeadMessage(text, kind) {
  const el = document.getElementById('playerMessage');
  if (el) { el.textContent = text; el.className = `status ${kind}`; }
}

function reelHeadShow() {
  const url = (typeof currentPlayer !== 'undefined' && currentPlayer && currentPlayer.reel_headshot) || '';
  const thumb = document.getElementById('reelHeadThumb');
  thumb.classList.toggle('hidden', !url);
  if (url) thumb.src = `${url}?v=${Date.now()}`;
  document.getElementById('reelHeadRemove').classList.toggle('hidden', !url);
}

function reelHeadBuild() {
  let shell = document.getElementById('reelHeadEditor');
  if (shell) return shell;
  shell = document.createElement('div');
  shell.id = 'reelHeadEditor';
  shell.className = 'modal-shell hidden';
  shell.setAttribute('role', 'dialog');
  shell.setAttribute('aria-modal', 'true');
  shell.innerHTML = `<style>
    #reelHeadEditor{position:fixed;inset:0;z-index:10000;background:rgba(0,0,0,.7);overflow:auto}#reelHeadEditor.hidden{display:none}
    #reelHeadEditor .rh-card{background:#14171b;color:#eef2f6;border:1px solid #3a4048;border-radius:12px;padding:16px;width:min(920px,calc(100vw - 32px));max-height:calc(100vh - 32px);overflow:auto;margin:16px auto}
    #reelHeadEditor .rh-grid{display:grid;grid-template-columns:minmax(0,3fr) minmax(0,2fr);gap:16px}@media(max-width:700px){#reelHeadEditor .rh-grid{grid-template-columns:1fr}}
    #reelHeadEditor .rh-photo{position:relative;line-height:0;touch-action:none;user-select:none;background:#000}#reelHeadEditor .rh-photo img{width:100%;display:block;pointer-events:none}
    #rhOval{position:absolute;border:3px dashed #ffe45c;border-radius:50%;box-shadow:0 0 0 2000px rgba(0,0,0,.45);cursor:move;box-sizing:border-box}#reelHeadEditor .rh-photo{overflow:hidden}
    #rhStage{position:relative;height:300px;background:#d9a860;border-radius:8px;overflow:hidden}#rhBody{position:absolute;left:50%;bottom:-6px;transform:translateX(-50%);width:190px}#rhCut{position:absolute;left:50%;bottom:94px;transform:translateX(-50%);height:172px}
    #reelHeadEditor label{display:block;margin-top:10px;font-weight:700}#reelHeadEditor input[type=range]{width:100%}#reelHeadEditor .rh-actions{display:flex;gap:10px;justify-content:flex-end;margin-top:14px}
  </style>
  <div class="rh-card"><h2 style="margin-top:0">Reel Headshot</h2>
    <div class="rh-grid">
      <div><div class="rh-photo" id="rhPhoto"><img id="rhImage" alt="The photo"><div id="rhOval"></div></div><small>Drag the oval over the head, with the chin at the bottom of it.</small></div>
      <div><div id="rhStage"><svg id="rhBody" viewBox="0 0 190 170" aria-hidden="true"><path d="M30 60 L160 60 L172 170 L18 170 Z" fill="#810909" stroke="#6b4a26" stroke-width="3"/><path d="M78 56 L95 76 L112 56 Z" fill="#2b2b2e"/><text x="95" y="135" text-anchor="middle" font-size="58" font-weight="900" fill="#fff" font-family="Arial Black,Impact,sans-serif">1</text></svg><img id="rhCut" alt="The cut-out on a figure"></div>
        <label>Size<input type="range" id="rhSize" min="0.05" max="1" step="0.005"></label>
        <label>Narrower or wider<input type="range" id="rhShape" min="0.6" max="1.5" step="0.01" value="1"></label>
        <label>Remove background <span id="rhToleranceText"></span><input type="range" id="rhTolerance" min="0" max="120" step="2"></label>
        <small id="rhNote"></small>
      </div>
    </div>
    <div class="rh-actions"><button type="button" onclick="reelHeadClose()">Cancel</button><button type="button" class="primary" id="rhSave" onclick="reelHeadSave()">Save Reel Headshot</button></div>
  </div>`;
  document.body.appendChild(shell);
  document.getElementById('rhSize').addEventListener('input', event => { reelHead.size = Number(event.target.value); reelHeadOval(); reelHeadPreviewSoon(); });
  document.getElementById('rhShape').addEventListener('input', event => { reelHead.shape = Number(event.target.value); reelHeadOval(); reelHeadPreviewSoon(); });
  document.getElementById('rhTolerance').addEventListener('input', event => { reelHead.tolerance = Number(event.target.value); reelHeadOval(); reelHeadPreviewSoon(); });
  const oval = document.getElementById('rhOval');
  oval.addEventListener('pointerdown', event => {
    oval.setPointerCapture(event.pointerId);
    reelHead.drag = { px: event.clientX, py: event.clientY, x: reelHead.x, y: reelHead.y };
  });
  oval.addEventListener('pointermove', event => {
    if (!reelHead.drag) return;
    const box = document.getElementById('rhPhoto').getBoundingClientRect();
    reelHead.x = Math.max(0, Math.min(1, reelHead.drag.x + (event.clientX - reelHead.drag.px) / box.width));
    reelHead.y = Math.max(0, Math.min(1, reelHead.drag.y + (event.clientY - reelHead.drag.py) / box.height));
    reelHeadOval();
  });
  const end = () => { if (reelHead && reelHead.drag) { reelHead.drag = null; reelHeadPreview(); } };
  oval.addEventListener('pointerup', end);
  oval.addEventListener('pointercancel', end);
  return shell;
}

// The oval's size follows the photo's width, so it stays the same shape on any photo.
function reelHeadBox() {
  const image = document.getElementById('rhImage');
  const ratio = image.naturalWidth / (image.naturalHeight || 1);
  const width = reelHead.size * reelHead.shape;
  return { width, height: reelHead.size * 1.28 * ratio };
}

function reelHeadOval() {
  const { width, height } = reelHeadBox();
  const oval = document.getElementById('rhOval');
  oval.style.left = `${(reelHead.x - width / 2) * 100}%`;
  oval.style.top = `${(reelHead.y - height / 2) * 100}%`;
  oval.style.width = `${width * 100}%`;
  oval.style.height = `${height * 100}%`;
  document.getElementById('rhToleranceText').textContent = reelHead.tolerance ? '' : '(off: keeps the plain oval)';
}

function reelHeadForm() {
  const { width, height } = reelHeadBox();
  const form = new FormData();
  form.append('photo', reelHead.file);
  form.append('x', reelHead.x);
  form.append('y', reelHead.y);
  form.append('width', width);
  form.append('height', height);
  form.append('tolerance', reelHead.tolerance);
  return form;
}

let reelHeadTimer = 0, reelHeadTurn = 0;
function reelHeadPreviewSoon() {
  clearTimeout(reelHeadTimer);
  reelHeadTimer = setTimeout(reelHeadPreview, 220);
}

async function reelHeadPreview() {
  if (!reelHead) return;
  const turn = ++reelHeadTurn;
  const note = document.getElementById('rhNote');
  try {
    const response = await fetch('/api/reel-headshot/preview', { method: 'POST', credentials: 'same-origin', body: reelHeadForm() });
    const data = await response.json().catch(() => ({}));
    if (turn !== reelHeadTurn || !reelHead) return;
    if (!response.ok) { note.textContent = data.error === 'INVALID_IMAGE' ? 'That photo could not be cut here. Move the oval onto the head.' : (data.message || data.error || 'The cut-out could not be made.'); return; }
    document.getElementById('rhCut').src = data.image;
    note.textContent = data.low_resolution ? 'The head is small in this photo, so it will look soft. A closer photo will look better.' : 'If the hair or face is being eaten, lower Remove background. If background is left, raise it.';
  } catch (error) {
    if (turn === reelHeadTurn) note.textContent = error.message || 'The cut-out could not be made.';
  }
}

function reelHeadOpen(file) {
  const input = document.getElementById('reelHeadFile');
  if (!file) return;
  if (!currentRoster || !currentPlayer || !currentPlayer.id) {
    reelHeadMessage('Save the player record before adding a reel headshot.', 'error');
    if (input) input.value = '';
    return;
  }
  const shell = reelHeadBuild();
  reelHead = { file, x: REEL_HEAD_DEFAULT.x, y: REEL_HEAD_DEFAULT.y, size: 0.4, shape: 1, tolerance: REEL_HEAD_DEFAULT.tolerance, drag: null };
  document.getElementById('rhSize').value = reelHead.size;
  document.getElementById('rhShape').value = 1;
  document.getElementById('rhTolerance').value = reelHead.tolerance;
  document.getElementById('rhCut').removeAttribute('src');
  const image = document.getElementById('rhImage');
  image.onload = () => { reelHeadOval(); reelHeadPreview(); };
  if (image.src) URL.revokeObjectURL(image.src);
  image.src = URL.createObjectURL(file);
  shell.classList.remove('hidden');
  if (input) input.value = '';
}

function reelHeadClose() {
  reelHead = null;
  document.getElementById('reelHeadEditor')?.classList.add('hidden');
}

async function reelHeadAfterChange(message) {
  const rosterId = currentRoster.id, playerId = currentPlayer.id;
  await loadRosters();
  openRoster(rosterId);
  editRosterPlayer(playerId);
  reelHeadMessage(message, 'success');
}

async function reelHeadSave() {
  if (!reelHead) return;
  const button = document.getElementById('rhSave');
  button.disabled = true;
  try {
    const url = `/api/rosters/${encodeURIComponent(currentRoster.id)}/players/${encodeURIComponent(currentPlayer.id)}/reel-headshot`;
    const response = await fetch(url, { method: 'POST', credentials: 'same-origin', body: reelHeadForm() });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) { document.getElementById('rhNote').textContent = data.message || data.error || 'The reel headshot could not be saved.'; return; }
    reelHeadClose();
    await reelHeadAfterChange('Reel headshot saved.');
  } finally {
    button.disabled = false;
  }
}

async function reelHeadRemove() {
  if (!currentRoster || !currentPlayer || !confirm('Remove this reel headshot? Reels will use a generic figure for this player.')) return;
  const url = `/api/rosters/${encodeURIComponent(currentRoster.id)}/players/${encodeURIComponent(currentPlayer.id)}/reel-headshot`;
  const response = await fetch(url, { method: 'DELETE', credentials: 'same-origin' });
  if (!response.ok) { reelHeadMessage('The reel headshot could not be removed.', 'error'); return; }
  await reelHeadAfterChange('Reel headshot removed.');
}
