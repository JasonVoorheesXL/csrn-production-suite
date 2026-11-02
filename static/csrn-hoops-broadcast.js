// CSRN basketball on-air layer. It sits on top of the Collegiate basketball board and
// does nothing on any other sport: until the board is on the page it makes no requests
// and touches nothing, so a football overlay runs exactly as before.
(function () {
  const POLL_MS = 1000;
  const RAIL_SLOT_MS = 15000;
  const NOTE_SLOT_MS = 9000;
  const ALERT_MS = 12000;
  const LINE = "rgba(255,255,255,.88)";
  const esc = value => String(value == null ? "" : value).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);

  let data = null;
  let lastMarkerKey = "";
  let tickerOwned = "";
  let seenAlert = null;
  let alertUntil = 0;
  let alertData = null;
  let fetching = false;
  let lastFetch = 0;

  const FLOOR = '<defs><linearGradient id="hbFloor" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#6f4d2c"/><stop offset="1" stop-color="#4a321c"/></linearGradient></defs>';

  function basket(dir) {
    const lane = dir > 0 ? 0 : 65, cx = dir > 0 ? 19 : 65, rim = dir > 0 ? 5.25 : 78.75, edge = dir > 0 ? 0 : 84, sweep = dir > 0 ? 1 : 0, board = dir > 0 ? 4 : 80;
    return `<rect x="${lane}" y="19" width="19" height="12" fill="rgba(255,255,255,.07)" stroke="${LINE}" stroke-width=".4"/><circle cx="${cx}" cy="25" r="6" fill="none" stroke="${LINE}" stroke-width=".4"/><path d="M${edge} 5.25 L${rim} 5.25 A19.75 19.75 0 0 ${sweep} ${rim} 44.75 L${edge} 44.75" fill="none" stroke="${LINE}" stroke-width=".45"/><line x1="${board}" y1="22" x2="${board}" y2="28" stroke="${LINE}" stroke-width=".55"/><circle cx="${rim}" cy="25" r=".85" fill="none" stroke="#ff8a4c" stroke-width=".4"/>`;
  }

  function mark(x, y, kind, big) {
    const r = big ? 2.5 : 1.05;
    if (kind === "made") return `${big ? `<circle cx="${x}" cy="${y}" r="5" fill="none" stroke="#3ddc84" stroke-width=".7" opacity=".8"/>` : ""}<circle cx="${x}" cy="${y}" r="${r}" fill="#3ddc84" stroke="#fff" stroke-width=".4"/>`;
    if (kind === "miss") return `<g stroke="#fff" stroke-width="${big ? .9 : .5}" stroke-linecap="round"><line x1="${x - r}" y1="${y - r}" x2="${x + r}" y2="${y + r}"/><line x1="${x + r}" y1="${y - r}" x2="${x - r}" y2="${y + r}"/></g>`;
    if (kind === "fouled") return `<circle cx="${x}" cy="${y}" r="5" fill="none" stroke="#f0b429" stroke-width=".7" opacity=".8"/><circle cx="${x}" cy="${y}" r="${r}" fill="#f0b429" stroke="#fff" stroke-width=".4"/>`;
    if (kind === "steal") return `<circle cx="${x}" cy="${y}" r="5" fill="none" stroke="#5db7ff" stroke-width=".7" opacity=".8"/><path d="M${x} ${y - 2.6} L${x + 2.6} ${y} L${x} ${y + 2.6} L${x - 2.6} ${y} Z" fill="#5db7ff" stroke="#fff" stroke-width=".4"/>`;
    return "";
  }

  function fullCourt(markup) {
    return `<svg viewBox="0 0 84 50" preserveAspectRatio="xMidYMid meet">${FLOOR}<rect width="84" height="50" fill="url(#hbFloor)"/><rect x=".2" y=".2" width="83.6" height="49.6" fill="none" stroke="${LINE}" stroke-width=".4"/><line x1="42" y1="0" x2="42" y2="50" stroke="${LINE}" stroke-width=".4"/><circle cx="42" cy="25" r="6" fill="none" stroke="${LINE}" stroke-width=".4"/>${basket(1)}${basket(-1)}<g class="hb-mark">${markup}</g></svg>`;
  }

  // Half a court with the basket at the top; spots are stored from the shooter's view.
  function halfCourt(shots, style) {
    const marks = (shots || []).map(s => mark(s.x, s.y, s.made ? "made" : "miss", false)).join("");
    return `<svg viewBox="0 0 50 42" preserveAspectRatio="xMidYMid meet" style="${style}">${FLOOR}<rect width="50" height="42" fill="url(#hbFloor)"/><g transform="matrix(0 -1 1 0 0 84)">${basket(-1)}${marks}</g></svg>`;
  }

  function teamMascot(board, side) {
    return board.querySelector(`[data-court-row="${side}"] .bl-court-team b`)?.textContent?.trim() || side;
  }

  function patchBank(board) {
    const court = board.querySelector(".bl-college-court");
    if (!court) return;
    court.classList.add("hb-has-court");
    let box = court.querySelector(".hb-court");
    if (!box) {
      box = document.createElement("div");
      box.className = "hb-court";
      box.innerHTML = fullCourt("");
      court.appendChild(box);
      lastMarkerKey = "";
    }
    const m = data.broadcast?.marker;
    const key = m ? `${m.id}|${m.x}|${m.y}|${m.kind}` : "none";
    if (key !== lastMarkerKey) {
      box.querySelector(".hb-mark").innerHTML = m ? mark(m.x, m.y, m.kind, true) : "";
      lastMarkerKey = key;
    }
    const meta = board.querySelector(".bl-college-court-meta");
    if (!meta) return;
    let shot = meta.querySelector(".hb-cell-shot");
    if (!shot) {
      shot = document.createElement("span");
      shot.className = "hb-cell hb-cell-shot";
      shot.innerHTML = "<small></small><b></b>";
      meta.appendChild(shot);
    }
    let run = meta.querySelector(".hb-cell-run");
    if (!run) {
      run = document.createElement("span");
      run.className = "hb-cell hb-cell-run";
      run.innerHTML = "<small>Run</small><b></b>";
      meta.appendChild(run);
    }
    const last = data.last_basket;
    const lastText = last ? [last.number ? `#${last.number} ${String(last.name || "").split(" ").slice(-1)[0]}` : teamMascot(board, last.team), `${last.points} PT`].join(" · ") : "-";
    shot.querySelector("small").textContent = m ? m.label : "Last basket";
    shot.querySelector("b").textContent = m ? m.text : lastText;
    const r = data.broadcast?.run;
    run.querySelector("b").textContent = r ? `${teamMascot(board, r.team)} ${r.points}-0` : "-";
  }

  function railCard(rail, cls) {
    let card = rail.querySelector(`.${cls}`);
    if (!card) {
      card = document.createElement("div");
      card.className = `hb-rail-card ${cls}`;
      rail.appendChild(card);
    }
    return card;
  }

  function patchRails(board) {
    ["visitor", "home"].forEach((side, index) => {
      const rail = board.querySelector(`[data-college-rail="${side}"]`);
      if (!rail) return;
      const floor = data.broadcast?.on_floor?.[side] || [];
      const hot = data.broadcast?.hot_hand?.[side];
      const slots = ["native"];
      if (floor.length) slots.push("floor");
      if (hot) slots.push("hot");
      const shown = slots[(Math.floor(Date.now() / RAIL_SLOT_MS) + index) % slots.length];
      const floorCard = railCard(rail, "hb-floor");
      const hotCard = railCard(rail, "hb-hot");
      floorCard.classList.toggle("hb-show", shown === "floor");
      hotCard.classList.toggle("hb-show", shown === "hot");
      if (shown === "floor") {
        const html = `<div class="hb-label">On the floor</div>` + floor.map(p => {
          const pips = [0, 1, 2, 3, 4].map(i => `<u class="${i < p.fouls ? (p.fouls >= 4 ? "d" : "f") : ""}"></u>`).join("");
          return `<div class="hb-pl"><b>${esc(p.number)}</b><div><span>${esc(p.last)}</span><div class="hb-pips">${pips}</div></div><i>${Number(p.pts) || 0}</i></div>`;
        }).join("");
        if (floorCard.dataset.key !== html) { floorCard.innerHTML = html; floorCard.dataset.key = html; }
      }
      if (shown === "hot" && hot) {
        const key = JSON.stringify(hot);
        if (hotCard.dataset.key !== key) {
          hotCard.innerHTML = `<div class="hb-label">Hot hand</div><div class="hb-hot-title">${esc(hot.title)}</div><div class="hb-hot-line">${esc(hot.line)}</div><div class="hb-hot-court">${halfCourt(hot.shots, "display:block;width:100%")}</div>`;
          hotCard.dataset.key = key;
        }
      }
    });
  }

  function patchTicker(board) {
    const node = board.querySelector(".bl-college-ticker-copy");
    if (!node) return;
    const notes = data.broadcast?.notes || [];
    const text = node.textContent.trim();
    // A ticker line the operator typed always wins over the automatic notes.
    const operatorLine = text && text !== "CSRN LIVE" && text !== tickerOwned;
    if (operatorLine) return;
    if (!notes.length) {
      if (tickerOwned) { node.textContent = "CSRN LIVE"; tickerOwned = ""; }
      return;
    }
    const start = Math.floor(Date.now() / NOTE_SLOT_MS) % notes.length;
    const picked = notes.length > 2 ? [notes[start], notes[(start + 1) % notes.length]] : notes;
    const next = picked.join("  ·  ");
    if (node.textContent !== next) node.textContent = next;
    tickerOwned = next;
  }

  function stageBox(board) {
    const stage = board.querySelector(".bl-college-video-window") || board.querySelector(".bl-college-stage");
    let rect = stage && stage.getBoundingClientRect();
    if (!rect || rect.width < 100) rect = board.querySelector(".bl-college-stage")?.getBoundingClientRect();
    if (!rect || rect.width < 100) return null;
    let box = document.querySelector(".hb-box");
    if (!box) {
      box = document.createElement("div");
      box.className = "hb-box";
      document.body.appendChild(box);
    }
    box.style.left = `${rect.left}px`;
    box.style.top = `${rect.top}px`;
    box.style.width = `${rect.width}px`;
    box.style.height = `${rect.height}px`;
    return box;
  }

  function screenHtml(screen) {
    if (screen.kind === "shot_chart") {
      const zones = screen.zones.map(z => `<div class="hb-z"><span>${esc(z.label)}<br>${esc(z.line)}</span><b>${esc(z.pct)}</b></div>`).join("");
      return `<div class="hb-screen"><h2>${esc(screen.title)} <small>${esc(screen.sub)}</small></h2><div class="hb-chart"><div class="hb-chart-court">${halfCourt(screen.shots, "display:block;width:100%;height:100%")}</div><div class="hb-zones">${zones}</div></div></div>`;
    }
    if (screen.kind === "comparison") {
      const rows = screen.rows.map(r => `<div class="hb-row"><b>${esc(r.left)}</b><span>${esc(r.label)}</span><b>${esc(r.right)}</b></div>`).join("");
      const leader = l => (l ? `<div class="hb-z"><span>LEADER<br>${esc(l.who)}</span><b>${esc(l.pts)} pts</b></div>` : "<div></div>");
      return `<div class="hb-screen"><h2 class="hb-versus"><span>${esc(screen.left)}</span><small>${esc(screen.sub)}</small><span>${esc(screen.right)}</span></h2><div>${rows}</div><div class="hb-leaders">${leader(screen.leaders.left)}${leader(screen.leaders.right)}</div></div>`;
    }
    return "";
  }

  function alertHtml(a) {
    const color = a.side === "visitor" ? "#2f6fd0" : "#b5121b";
    return `<div class="hb-alert"><div class="hb-alert-num" style="background:${color}">${esc(a.number)}</div><div class="hb-alert-main"><b>${esc(a.name)}</b><em>${esc(a.line)}</em></div><div class="hb-alert-tag">${esc(a.tag)}${a.tag2 ? `<br>${esc(a.tag2)}` : ""}</div></div>`;
  }

  function patchWindow(board) {
    const screen = data.broadcast?.screen;
    const incoming = data.broadcast?.alert;
    // Only a foul newer than any seen goes on air, so a reload or an Undo never replays one.
    const sequence = incoming ? Number(incoming.sequence) || 0 : 0;
    if (incoming && !incoming.muted && seenAlert !== null && sequence > seenAlert) {
      alertData = incoming;
      alertUntil = Date.now() + ALERT_MS;
    }
    seenAlert = Math.max(seenAlert || 0, sequence);
    const showAlert = alertData && Date.now() < alertUntil;
    if (!screen && !showAlert) {
      document.querySelector(".hb-box")?.remove();
      return;
    }
    const box = stageBox(board);
    if (!box) return;
    const html = screen ? screenHtml(screen) : alertHtml(alertData);
    if (box.dataset.key !== html) { box.innerHTML = html; box.dataset.key = html; }
  }

  function clearAll() {
    document.querySelectorAll(".hb-box").forEach(n => n.remove());
    data = null;
    seenAlert = null;
    tickerOwned = "";
  }

  function apply(board) {
    board.classList.add("hb-on");
    patchBank(board);
    patchRails(board);
    patchTicker(board);
    patchWindow(board);
  }

  async function poll() {
    if (fetching) return;
    fetching = true;
    try {
      const response = await fetch("/api/hoops/panel-state", { cache: "no-store" });
      if (response.ok) {
        data = await response.json();
        const board = document.querySelector(".bl-collegiate-tech.bl-sport-basketball");
        if (board) apply(board);
      }
    } catch (err) {
      // A missed poll keeps the last picture on air.
    } finally {
      fetching = false;
      lastFetch = Date.now();
    }
  }

  setInterval(() => {
    const board = document.querySelector(".bl-collegiate-tech.bl-sport-basketball");
    if (!board) {
      if (data) clearAll();
      return;
    }
    if (Date.now() - lastFetch >= POLL_MS) poll();
    if (data) apply(board);
  }, 500);
})();
