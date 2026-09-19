# Football incident FB-2026-5A-W04-001 (Caledonia vs. New Albany, 2026-09-18)

Branch `football-engine-incident-20260918`, off trunk `4bde8e9`. One commit per
bug so each can be re-verified independently. **Not merged.** Merge is gated on
Jason confirming there is no collision with in-flight football/basketball/
baseball work (see "Collision check").

Tests: `tests/test_football_incident_20260918.py` (128 tests, one section per
item). Full suite in the worktree: see the bottom of this file.

| # | Commit | Report's root cause | Verdict |
|---|--------|---------------------|---------|
| 1+2 | `5a4ed20` | `_swap_directions()` never mirrors `ball_spot` | Confirmed |
| 3 | `20e1fa0` | "Goal" is never produced by the backend | **Revised** |
| 4b | `c02b40f` | `edit()` rebuild snaps quarter/clock back | Confirmed by execution; **wider than reported** |
| 4a | `35bab5e` | edit modal uses live direction | Confirmed |
| 5 | (no code) | notes have no permanent home | **Premise wrong** |
| 6 | `4a5a4ae` | no own-team recovery attribution | Confirmed |
| 7 | `b59172a` | second-half direction is a forced mirror | Confirmed; operator choice added |
| 8 | (no code) | goal-to-go is automatic | Confirmed |
| 9a | `af3e15b` | live play log shows no game clock | Done, gated on `clock_visible` |
| 9b | `66990c3` | live play log shows no down & distance | Done; **no setting exists to gate on** |
| 10 | `a51e558` | pin goal-to-go through a penalty | Test only |

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

**Rendered and verified per package** (see "Theme rendering verification" at the
bottom). Note: there are five selectable packages, not eight.

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

Correction (round 2): an earlier draft of this doc claimed the archive's PENALTY
descriptions contain a mojibake em dash. That was wrong - it came from an
ASCII-replace in the inspection script. A byte-level read shows a proper U+2014
and 0 of 138 archived events contain mojibake or replacement characters.

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

## Item 7 - second-half kickoff direction is an operator choice

`start_second_half()` took the receiver as a choice but derived direction with
the same mechanical `_swap_directions()` as the in-half Q1->Q2 / Q3->Q4 breaks.
Correct there, wrong for a fresh decision that mirrors the opening coin toss.

Follows the coin toss pattern (`opening_drive_direction`, "the direction the
opening receiver's offense will drive", validated left/right):
`second_half_drive_direction` = the direction the **second-half receiving
team's** offense will drive. Empty or `"mirror"` keeps the historical mirror as
the default; anything else returns `SECOND_HALF_DIRECTION_INVALID` and changes
nothing. Wired through both entry points (`set_values` period action and
`toggle_halftime`; the latter also now passes an explicit receiver), with a
select in the statistician Period Administration card and beside the
broadcaster's halftime button.

The ball spot follows **whether the ends actually change**, not whether a choice
was made: `_set_directions()` mirrors exactly when the resulting directions
differ from the old ones, and never otherwise (choosing to keep the first-half
ends must not move the ball). `_swap_directions()` now goes through it, so the
in-half breaks are unchanged. The kickoff spot is recomputed by `enter_kickoff`
afterwards, so it is correct for every choice (tested for both receivers). A
non-mirrored Q3 also survives a later edit of a first-half play (bug 4b).

Known gap: `toggle_halftime`'s "receiver unknown" fallback still starts Q3
without touching directions (the choice is relative to the receiver, which that
path does not have).

## Item 8 - goal-to-go is automatic (no code)

Confirmed. `CanonicalStateFoundation.goal_to_go()` is derived on every read from
live ball spot, down, distance, possession and direction, so it applies at the
start of any set of downs at the 10 or closer *and* as the ball moves within a
series, not only at the start of a possession.

One edge noticed while tracing item 10: a defensive penalty enforced without the
half-distance flag can leave the ball exactly on the goal line (0 yards to go),
where `goal_to_go()` is false by design (`0 < yards_to_goal`), so the overlay
reads "1st & 10". That is the half-distance option's job, not a goal-to-go bug.

## Item 9 - live play log: game clock and down & distance

`templates/index.html`, the `eventLog` row builder (distinct from the post-game
`play_register`). Both helpers were executed in the browser pane against edge
cases, not just source-asserted.

**9a - clock (`af3e15b`).** `eventClockText()` renders `M:SS` from
`ev.after.clock_seconds` (512 -> `8:32`) in the `<time>` cell: `Q2 · 8:32 ·
10:42:31 PM`. Gated on **`clock_visible`**: confirmed as the right field - it is
what the "Clock Display: Hide/Show Clock" buttons set (`setState('clock_visible')`
/ `toggleClockVisibility()`) and defaults to hidden. The gate reads the value
recorded **with the event** (`ev.after.clock_visible`), live flag only as a
fallback for older events. Reason, from the real incident game: its first plays
were logged with the clock hidden and frozen at 720, which would otherwise show a
misleading `12:00` on every early row. `after.clock_seconds` is the live countdown
(`load_state` -> `StateService.load()` derives the running clock).

**9b - down & distance (`66990c3`).** Shown as a small line under the
description from `ev.after.down/distance` (fallback to the play's
`resulting_*`, which only replayed plays have). **No "down & distance enabled"
setting exists anywhere**: not in state defaults, `GameOperationsService`'s
settable fields, the rulesets, or `index.html`. Nearest siblings are
`ball_spot_visible` and the Layout Builder's overlay-only `game_fields`
visibility, both different things. So it is gated only on the engine's own
convention - a real down and a real distance; `Off`/empty (kickoffs, coin toss,
tries) is hidden - through one function, `eventDownDistanceEnabled()`. Own
commit so it can be dropped or re-gated independently. **Open question for
Jason:** is down/distance tracking optional per broadcast? If so this needs a
new setting rather than an existing one.

## Item 10 - goal-to-go through a penalty (test only)

At 2nd & Goal from the 8 (stored distance 10 - goal-to-go is display-only), a
10-yard offensive holding gives distance 20 at the 18 (18 to goal); 18 <= 20 so
it still reads Goal. Depends on `penalty_service` adding the same enforced yards
to `distance` that it moves the ball. Pinned with the exact case, the overlay
value, the full `EventService.trigger` path, a lockstep invariant across penalty
sizes and distances, a negative control, and three orientations. Mutation-checked:
breaking either half of the lockstep fails 15 tests.

## Collision check (for Jason's merge gate)

Files changed: `canonical_state_service.py`, `event_service.py`,
`period_service.py`, `rules_service.py`, `state_service.py`,
`statistics_service.py`, `static/csrn-production-theme-runtime.js`,
`templates/index.html`, `game_operations_service.py` (item 7), plus tests.

Nearly every recent round is already merged into trunk `4bde8e9`. The only
branches with unmerged work are `basketball-p5-ui-followup-20260914`
(`docs/BASKETBALL_ENGINE_SCOPING_PLAN.md`, `static/csrn-hoops-controls.js`,
`templates/_hoops_controls.html`, two basketball tests) and
`hockey-engine-scoping-20260907` (`docs/HOCKEY_ENGINE_SCOPING_PLAN.md`).
**No file overlap** with this branch. `templates/index.html` and
`csrn-production-theme-runtime.js` are the two shared surfaces, so re-run this
check if either branch lands first. The production folder's uncommitted WIP
(`Data/Runtime/pregame_presentation.json`) does not overlap either.

## Verification summary

Full suite in the worktree (with `CSRN_GAME_DAY_LOCAL_STATE=1` and an isolated
`CSRN_STATE_AUTHORITY_FILE`): **3094 passed, 1 skipped**. Trunk was still
`4bde8e9` when re-checked; still no file overlap with the only two branches that
have unmerged work (`basketball-p5-ui-followup-20260914`,
`hockey-engine-scoping-20260907`).

## Theme rendering verification (bug 3)

Run against the real app (source-checkout mode, isolated state/template files,
port 5071, no PIN or license bypass; the live install was not touched), with the
overlay at 1920x1080 in the browser pane. State: Q3, clock 8:32, home ball at the
opponent's 6, 1st & 10 stored. The selectable packages are `legacy` (classic
overlay), `friday_night_stadium`, `eight_bit_gameday`, `heritage_press` and
`collegiate_traditional`; `digital_neon` is hidden (see below).

| Package | Goal-to-go (1st & 10 @ opp 6) | Control (3rd & 7 @ LEFT 40) |
|---|---|---|
| Classic overlay (`legacy`) | "1ST & GOAL" | "3RD & 7" |
| Friday Night Stadium | DOWN 1, **TO GO 6**, BALL ON 6 | DOWN 3, TO GO 7, BALL ON 40 |
| Eight-Bit Gameday | DOWN 1, **TO GO 6**, BALL ON 6 | DOWN 3, TO GO 7, BALL ON 40 |
| Heritage Press | "1ST & GOAL" (header and Game State panel) | "3RD & 7" |
| Collegiate Traditional | "1st & Goal"; first-down marker on the goal line (95%), line to gain "...GOAL" | "3rd & 7"; line to gain "Cavaliers 47", marker 7 yds ahead |

Also checked: the exact boundary (2nd & 10 from the 10) reads "2nd & Goal" on
Collegiate (marker still on the goal line) and puts a **two-digit** number in the
Stadium LED cell, which fits. The LED cells show yards-to-goal, so a 10-yard
distance at the 6 now reads 6, not 10.

Observations, none caused by this change:
- The Collegiate LINE TO GAIN cell visually clips a long school name
  ("AMORY HIGH SCHOOL GO..."); the full text is "...GOAL". The old code clamped to
  the same goal-line position, so this is unchanged.
- The Eight-Bit board's POSSESSION cell shows a dash in this test state and
  its score digits render very small; neither involves down/distance.
- `digital_neon` fails to bind in this environment with "Theme scorebug render
  contract failed" and falls back to the classic scorebug. It fails identically on
  the **normal** down and with trunk's original `csrn-production-theme-runtime.js`
  swapped in, so it is pre-existing and unrelated (the package is hidden from the
  picker). Neon's goal-to-go rendering therefore could not be verified.

Still not covered by any test: the two second-half direction selects and the new
event-log row layout in a real operator session (items 7 and 9), and whether the
five packages' *other* boards (pregame/halftime scenes) are unaffected (they do
not read `distance`).
