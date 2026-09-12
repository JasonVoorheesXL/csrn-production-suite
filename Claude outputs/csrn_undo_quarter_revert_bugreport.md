# CSRN Production Suite — Bug Report: Undo/Redo State Corruption (Caledonia @ Lamar, 9/11/2026)

Found during post-game review of the Caledonia @ Lamar broadcast. Three issues, ranked by severity. All three have exact code locations and a proposed fix direction — no further repro needed before starting the fix, but see "How to verify the fix" at the bottom for a test to run once patched.

---

## 1. CRITICAL — "Undo Last" can wipe the entire play list and snap game state back to the 1st quarter

**File:** `event_service.py`, `EventService.undo()`
**Location:** the `if not remaining_events:` block that runs immediately after the `CanonicalStateFoundation.rebuild(...)` call (currently ~10 lines, right before `revision = assign_next_revision(state)`).

### What happened in the game
During the 3rd quarter, after a couple of "Undo Last" / "edit previous plays" actions in a row, the broadcast state reverted to the 1st quarter (score, clock, down/distance, and the play list all went with it), requiring a manual fix back to Q3.

### Root cause
Every play (run/pass/kickoff/punt) *and* every manual event (penalty, XP, 2‑pt, TD, FG, turnover, first down) is appended to `state["events"]` with a `before`/`after` snapshot of canonical game fields — `quarter`, `home_score`, `visitor_score`, `down`, `distance`, `possession`, clock fields, `broadcast_phase`, etc. (see `CANONICAL_FIELDS` in `canonical_state_service.py` and `RulesService.SNAPSHOT_FIELDS` in `rules_service.py`).

"Undo Last" finds the most recent not-yet-undone entry in `state["events"]` and calls `CanonicalStateFoundation.rebuild(state, remaining_events, remaining_plays, baseline=...)` to replay everything else. **This part is correct** — it already recomputes canonical fields from the right baseline and already keeps the plays that aren't tied to the undone event.

The bug is what happens *after* that rebuild, specifically when `remaining_events` comes back empty — i.e., the event just undone was the last one still marked not-undone (this happens naturally after a couple of consecutive undos, since each one removes an entry). In that case the code:

1. Loops over **every key** in the undone event's `before` snapshot and writes it straight onto live state (`state[key] = ...`), overwriting quarter, score, clock, down/distance, possession, broadcast_phase, etc. with whatever those were right before the *oldest surviving tracked event* happened — which for most games is early in the 1st quarter.
2. Then unconditionally sets `state["events"] = []` **and** `state["plays"] = []` — throwing away the correctly-filtered play list that `rebuild()` had already computed one line earlier, and deleting every play in the game, not just the one being undone.

So the observed sequence lines up exactly: a couple of undos in the 3rd quarter drained `state["events"]` down to one old surviving entry (e.g., an early penalty or the opening kickoff play); the next "Undo Last" hit that entry, found nothing left behind it, and the special-case block clobbered the whole game state back to its pre-game/Q1 baseline and blanked the play list. This is a real data write, not a display glitch — which is why it needed a manual correction rather than resolving itself.

### Proposed fix
This special-case block is redundant with — and actively undoes the correctness of — the `rebuild()` call directly above it. `rebuild()` already:
- seeds canonical fields from `baseline` (the same `target.get("before")`) when `ordered_events` is empty, and
- correctly sets `rebuilt["plays"]` to the filtered remaining-plays list (not empty, unless every play really is gone).

Recommend deleting the `if not remaining_events:` block's field-copy loop and the `state["events"] = []` / `state["plays"] = []` lines, and just letting `rebuild()`'s own output stand (keep the `redo_stack`/`correction_log` bookkeeping and `next_play_number` reset that's already there — those look fine on their own).

### Secondary, related issue (same feature)
"Undo Last" has no confirmation or preview of what it's about to undo. Because the target search walks backward through `state["events"]` for the first not-undone entry — which is not necessarily "the last thing the operator did" if some other event in between was already undone — an operator can press "Undo Last" expecting to undo their most recent play and instead undo something much older, with zero on-screen indication. Worth adding a confirmation showing the label/quarter/play description of what's about to be undone before committing.

---

## 2. MEDIUM — Manual events (Penalty/XP/2‑pt) leave the play register blank until the next poll

**File:** `templates/index.html`
**Location:** `submitPenalty()` (~line 3036) and the XP/2‑pt submit handlers nearby — none of them call `refreshPlayRegister(..., true)` after a successful commit.

### What happened in the game
A touchdown that hadn't actually occurred appeared to be pending, locking the operator into an XP-resolution screen.

### Root cause
`finishCommittedPlayEntry()` (the run/pass play-entry flow, ~line 3134) force-refreshes the play register after every commit (`refreshPlayRegister(reason, true)`), so the UI's play list and pending-action state stay in sync immediately. The manual-event flow (penalty, XP, 2‑pt) commits successfully server-side but skips that force-refresh call. The client's `poll()` loop does eventually call `refreshPlayRegister('runtime-revision', false)` (line ~4948), but with `force=false` it's frequently a no-op (guarded by `playRegisterLastFetchRevision >= revision`), so the UI can sit showing stale pending state — e.g. an XP that was already resolved server-side still shown as awaiting resolution — until something else happens to force a refresh.

### Proposed fix
Add the same `refreshPlayRegister(reason, true)` force-refresh call to `submitPenalty()` and the XP/2‑pt submit handlers, mirroring what `finishCommittedPlayEntry()` already does for run/pass plays.

---

## 3. LOW — "Fumble lost" checkbox is disabled until "Fumble" is checked, with no explanation

**File:** `templates/index.html`
**Location:** `turnoverEntryChanged()` (~line 3130)

### What happened in the game
A fumble-lost rush kept possession with the offense instead of turning it over; the operator had to manually enter the turnover from the defense's side afterward (this shows up as play #32 in the archived play-by-play — a standalone Turnover-event workaround rather than a fumble-lost play, so no game data was permanently lost).

### Root cause
This is a usability trap, not a data bug: `turnoverEntryChanged()` disables the "Fumble lost" checkbox until "Fumble" is checked first. If the operator checks "Fumble lost" directly (a natural click order — "the ball was fumbled and lost"), the click has no effect and there's no visual feedback explaining why, so the play can be submitted without the turnover ever being flagged. Confirmed on the backend: `RulesService.play()`'s turnover logic (rules_service.py ~line 615) correctly flips possession when `fumble_lost` is set — the mechanism itself works, it's just never triggered because the checkbox never actually got checked.

### Proposed fix
Either auto-check "Fumble" when "Fumble lost" is checked directly, or remove the dependency and let "Fumble lost" imply "Fumble," and/or show a brief inline hint on the disabled checkbox explaining the required order.

---

## How to verify the fix (item 1)

1. Start a test broadcast, enter 2–3 plays, then trigger a couple of manual events (e.g., two penalties).
2. Press "Undo Last" repeatedly until only one tracked event remains, then press it once more.
3. Confirm: quarter, score, clock, and down/distance stay at their pre-undo values (not reset to game-start), and the play list still contains every play not tied to the undone event — not an empty list.
4. Repeat with a run/pass play as the last surviving event (not just manual events), since those also live in `state["events"]` via the `"event": "PLAY"` records in `rules_service.py`.
