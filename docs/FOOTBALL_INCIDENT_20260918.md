# Football incident FB-2026-5A-W04-001 (Caledonia vs. New Albany, 2026-09-18)

Branch `football-engine-incident-20260918`, off trunk `4bde8e9`. One commit per
bug so each can be re-verified independently. **Not merged.** Merge is gated on
Jason confirming there is no collision with in-flight football/basketball/
baseball work (see "Collision check").

Tests: `tests/test_football_incident_20260918.py` (86 tests, one section per
bug). Full suite in the worktree: **3052 passed, 1 skipped**.

| # | Commit | Report's root cause | Verdict |
|---|--------|---------------------|---------|
| 1+2 | `5a4ed20` | `_swap_directions()` never mirrors `ball_spot` | Confirmed |
| 3 | `20e1fa0` | "Goal" is never produced by the backend | **Revised** |
| 4b | `c02b40f` | `edit()` rebuild snaps quarter/clock back | Confirmed by execution; **wider than reported** |
| 4a | `35bab5e` | edit modal uses live direction | Confirmed |
| 5 | (no code) | notes have no permanent home | **Premise wrong** |
| 6 | `4a5a4ae` | no own-team recovery attribution | Confirmed |

## Bugs 1 & 2 - ball spot follows the change of ends

`ball_spot` is a screen-fixed LEFT/RIGHT label. Teams change goals at the end of
Q1 and Q3 (and at the second-half start) with the ball keeping its position
*relative to the teams*, which in that frame is the mirror image.
`CanonicalStateFoundation.mirror_spot()` (coord -> length - coord, field-length
aware, leaves empty/unparseable spots alone) is called from
`PeriodService._swap_directions()`, the one place all three transitions share.
`yards_to_goal()` is now invariant across the swap.

Two assertions in `test_gate184_r6_period_lifecycle.py` pinned the old
`LEFT 34 -> LEFT 34` behaviour ("preserves ... physical spot"); they were
updated to `RIGHT 34`. The pure-function test in `test_yards_to_goal.py`
("same physical spot ... now 60 to score") calls no period code and is unchanged.

## Bug 3 - "1st & Goal"

Differs from the report in three ways:

1. The operator panel already derived goal-to-go (`dNum >= toGoal`). The missing
   piece was the **on-air overlay**, which renders `distance` verbatim.
2. `_apply_scrimmage_play` is only the *replay* path used by `rebuild()`. Live
   plays go through `RulesService.play()`, and ~10 other sites set down/distance
   (returns, turnovers, penalties, FIRST_DOWN, corrections). Stamping "Goal"
   into stored state would go stale on any manual spot correction or change of
   ends, and existing readers treat a stored "Goal" as "unknown -> 10", losing
   the real distance.
3. **Boundary.** The report asked that `yards_to_goal == distance` *not* read as
   Goal. That is not football: 1st & 10 from the opponent's 10 is "1st & Goal",
   and it is what the operator panel already does. The boundary here is
   inclusive (`0 < yards_to_goal <= distance`). If the inclusive rule is not
   what Jason wants, it is one comparison in `CanonicalStateFoundation.goal_to_go`.

So goal-to-go is derived on read: `field_state()` gains `goal_to_go` /
`distance_display`; the overlay-only `StateService.runtime_view()` serves
`distance: "Goal"` (numeric kept as `distance_yards`); the operator UI's public
state stays numeric (it posts `currentState.distance` back on a spot
correction). `productionDownDistance()` keeps the text "1st & Goal" but shows
yards-to-goal digits in LED cells (Stadium glyph set has no "A").

**Not visually verified** on any of the eight themes: no Node/browser render
was done. The eight-bit and stadium engines parse `downDistance` with a
digits-only regex and fall back to demo values, but `applyBoardOverrides()` runs
after each render and replaces those cells. Worth one look at a goal-to-go state
on each theme before game day.

## Bug 4b - edit/undo/restore reset period, clock, ends

Reproduced by execution, not just source reading: after Q1->Q2, editing play 1
snapped Q2 -> Q1, clock 301 -> 720, direction left -> right, and put the ball on
the wrong side. Period transitions append no event, so `rebuild()` had nothing
to replay them from.

**Wider than reported:** the report assumed `undo()` had an analogous fix to
copy. It does not - that fix only removed a redundant clobber after `rebuild()`.
`undo()` and `restore()` reproduced the identical snap-back after a quarter
break, so all three go through one fix.

`rebuild(..., preserve_live=False)` (opt-in; default stays the pure
baseline+events reducer that existing tests pin). With it: each event replays
under its **recorded** direction; the running ball spot mirrors when the ends
changed between events; recorded before/after `LIVE_PERIOD_FIELDS` are no longer
overwritten; live quarter/clock/direction are restored at the end. `edit()` and
`restore()` use it; `undo()` uses it whenever history remains.

The report's option (i) (append replayable period events) was rejected: it
would not fix the clock (a mid-quarter edit would still reset to quarter start)
and would make "Undo Last" undo a quarter break.

Known limitations:
- Undoing the **only** tracked event still snaps to its pre-event state (pinned
  by `test_undo_redo_corruption_fix`). Only matters if a period break happened
  between the game's sole logged play and the undo.
- `quick_correction` / the field slider write `ball_spot` without an event, so a
  later rebuild forgets a manual spot correction. Pre-existing, not touched.
- `RulesService.field_direction` (manual direction toggle) does not mirror the
  ball. `GameOperationsService.toggle_halftime`'s "receiver unknown" fallback
  starts Q3 without swapping directions at all. Both pre-existing, out of scope.

## Bug 4a - edit modal direction

`playDirection(ev, team)` reads `ev.before.<team>_direction`, falling back to
live only for events that predate it. This is only trustworthy because 4b
stopped `rebuild()` overwriting every event's `before` with the first play's
direction. JS is covered by source assertions only (no JS runtime in the test
environment).

## Bug 5 - play notes retention (no code)

The premise does not hold. Completed broadcasts **are** archived:
`app.write_broadcast_final_archive()` writes `final_state_archive` into
`Data/Broadcasts/<id>.json` (verified by read-back) *before* `state.json` is
cleared. For this broadcast the archive holds 138 plays and 138 events; play
`notes` are retained. There is no retention gap.

The "ball spot penalty" text is not in the archive: only one play has a note
(play 66, Q2: "recovered by Medcalf" - the operator working around bug 6), the
9 PENALTY events carry no such text, and the only correction-log note is
"Field position controller". It was most likely on a play that was later undone
(undone events are dropped, redo stack keeps 20) or was never saved.

Unrelated, noticed in passing: PENALTY event descriptions in the archive contain
a mojibake em dash (`Penalty, New Albany, 5 yards ? False Start`).
`StatisticsService._repair_text` repairs the known signature on the
report path, but the stored text is still corrupt.

## Bug 6 - own-team fumble recovery

New optional `recoverer_number` / `recoverer_name` / `recovery_spot` on a
run/pass with Fumble checked and Fumble lost unchecked. Ball movement,
down/distance and possession are unchanged. The recoverer is validated like the
other offensive roles; a touchdown's scorer is the recoverer; the play record's
`player_*` still names the original carrier.

Stats (`StatisticsService`): carrier keeps yards up to the fumble; recoverer gets
the rest (rushing yards on a run, receiving yards on a pass, no attempt or
reception) plus the touchdown; no touchdown pass for the passer; new
`own_fumble_recoveries` player stat. Team totals count the play once, and the
carrier's share is derived (`yards - recovery_yards`) so a yardage edit keeps
every reconciliation check green.

**Product decisions to confirm:** yardage after recovery is counted as the
recoverer's *rushing/receiving* yards (keeps player/team reconciliation) rather
than a separate "fumble return yards" category; and `own_fumble_recoveries` is a
new field rather than reusing `fumble_recoveries` (which means defensive
recoveries and feeds the leader rails).

Audited for single-credited-player assumptions: `statistics_service`,
`state_service._enrich_play` (now keeps the recovery in the rewritten text),
`social_service` (reads event `automation.player_*`, which is the TD scorer).
`box_score_service` and `recap_service` never read per-play credit.

## Collision check (for Jason's merge gate)

Files changed: `canonical_state_service.py`, `event_service.py`,
`period_service.py`, `rules_service.py`, `state_service.py`,
`statistics_service.py`, `static/csrn-production-theme-runtime.js`,
`templates/index.html`, plus tests.

Nearly every recent round is already merged into trunk `4bde8e9`. The only
branches with unmerged work are `basketball-p5-ui-followup-20260914`
(`docs/BASKETBALL_ENGINE_SCOPING_PLAN.md`, `static/csrn-hoops-controls.js`,
`templates/_hoops_controls.html`, two basketball tests) and
`hockey-engine-scoping-20260907` (`docs/HOCKEY_ENGINE_SCOPING_PLAN.md`).
**No file overlap** with this branch. `templates/index.html` and
`csrn-production-theme-runtime.js` are the two shared surfaces, so re-run this
check if either branch lands first. The production folder's uncommitted WIP
(`Data/Runtime/pregame_presentation.json`) does not overlap either.
