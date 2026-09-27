# Viewer/operator feedback - Caledonia vs. East Webster (2026-09-26)

Four items from viewer/operator feedback after the broadcast (`FB-2026-OPEN-W05-001`, Collegiate
Traditional live). Same discipline as `docs/FOOTBALL_INCIDENT_20260918.md`: each item was
investigated and, where possible, reproduced by execution before any fix landed - not diagnosed
from source alone. Branch `viewer-feedback-20260926`, worktree `CSRN-Prod-viewerfb`, off `main`
(`d240082`).

**Status: all four items investigated, one commit each** (`a921a97`, `dc03824`, `328a7e2`,
`07c5257`). Items 1, 3 and 4 shipped code fixes; item 2 found no defect (documented, not fixed).
Full suite: 3198 passed, the two known environment-only `test_state_mirror_throttle` failures.
**Not merged, not pushed** - for review.

**Known gap, not in this round's scope:** item 4's rules-engine change has no operator-facing
control yet. The crew cannot actually trigger `kick_out_of_bounds` from the live control panel
today - `rules_service.py` accepts and correctly enforces it, but nothing in `templates/index.html`'s
kickoff play-entry form submits it. A follow-up round is needed before this is usable on a real
broadcast; flagging this now rather than leaving it undiscovered.

## Item 1 - on-air Down & Distance too small on a phone screen

**Report's framing didn't hold up.** The report named `.bl-down` with "per-package font-size
overrides". Live inspection (a real seeded broadcast, DOM query on the running overlay) found
Collegiate Traditional's football board has **no `.bl-down` element at all** - that class belongs
to the retired standalone Neon engine (`.package-neon` / `.package-neon-approved`, archived per
`docs/NEON_REDESIGN.md`); no live package manifest selects it any more. Collegiate's real Down &
Distance value is `<b data-bind="game.downDistance">` inside `.bl-college-field-meta`
(`collegiateField()` in the engine), confirmed live at a computed **19px**.

**Reproduced the complaint.** Captured the overlay at 1920x1080 (its one fixed canvas - there is
no responsive breakpoint to hook into; OBS composites this canvas and a phone viewer just sees it
scaled down), then downscaled that same image to 390px wide (a real phone viewport). At that size
the readout-bar values, Down included, were essentially illegible while the header score stayed
readable (58-66px there vs. 19px in the bar).

**Fix.** `.bl-college-field-meta b` 19px -> 26px (matches this same board's own Team Snapshot
numbers, `.bl-college-stat-grid strong`, also 26px - the new size lands on an existing convention
in Collegiate's own UI rather than an arbitrary one); its label `small` 13px -> 15px. All four
readout cells (Possession, Down, Ball, Line to gain) share the one rule, so the bump is uniform
across the bar - Down does not become inconsistent with its own siblings. Neon's Down & Distance
callout pill (a separate override on the same cell, since Neon promotes it to a highlighted pill)
re-pinned 25px -> 32px so it stays the largest cell in the bar rather than falling behind its own
siblings after the base bump; verified live under Neon with no clipping in the fixed 50px-tall row.

Re-pinned the shared-engine hash chain (gate12/13/14 -> gate142).

Commit: `a921a97`.

## Item 2 - Down & Distance error at the start of the second quarter

**Jason wasn't sure what he saw; the archive shows no defect.** Reconstructed the exact play-by-
play at the Q1->Q2 boundary from `Data/Broadcasts/FB-2026-OPEN-W05-001.json`'s
`final_state_archive` (174 plays/events, each with a `before`/`after` state snapshot) and, once
that pointed at the guarded period-transition code, re-ran that exact transition live through the
real, unmodified `GameOperationsService.set_values(period_action="end_quarter")` to confirm it
byte-for-byte reproduces what the archive recorded.

**The lead ("only two `set_values:period:end_quarter` commands are logged").** True, but not what
it first looks like. `live_state.recent_commands` is a command idempotency ledger capped at
**200 entries** (`live_command_service.LEDGER_LIMIT = 200`, enforced by `compact_recent_commands`)
- an idempotency/de-dup cache, not a permanent audit log. This game logged well over 200 commands
total (80 `clock_control:*` alone, 145 `PLAY` events, 15 `PENALTY`s, 12 `quick_correction`s, etc.),
so by the time the broadcast was archived the ledger held only its most recent 200. The two
`set_values:period:end_quarter` entries actually present are timestamped to `Q3_TO_Q4` and
`Q4_COMPLETE` (confirmed by reading their own `result.period.transition` field) - the later two of
the three quarter-end transitions a 4-quarter game has. Q1->Q2's own `end_quarter` command was
issued around play #35/36 of 174, long before the ledger's retained window by the end of the game;
it is absent from `recent_commands` because it aged out, not because it took a different, unlogged
path.

**Reconstructed sequence at the real boundary** (play-by-play, `final_state_archive.events`):

| | quarter | down & distance | ball spot | home dir. / visitor dir. | clock |
|---|---|---|---|---|---|
| play #35 (Q1, last play) after | 1 | 2nd & 8 | `LEFT 19` (end spot) | right / left | 46s, stopped |
| play #36 (Q2, first play) before | **2** | **2nd & 8** | **`RIGHT 19`** | **left / right** | **720s**, stopped |

Down & distance carried over unchanged (correct - the same drive continues into the new quarter);
directions swapped and the ball spot correctly re-mirrored to the new frame of reference (`LEFT 19`
and `RIGHT 19` are the same physical yard line, just relabelled for the sides having changed ends -
NFHS football swaps ends at the end of *every* quarter, not only at halftime); the clock reset to a
full fresh quarter (720s = 12:00). This is exactly `PeriodService.transition("end_quarter")`'s
`Q1_TO_Q2` branch (`period_service.py`): `_swap_directions()` (which mirrors `ball_spot` via
`CanonicalStateFoundation.mirror_spot()` whenever the ends actually change) + `quarter = "2"` +
`_stop_clock(current, reset=True)`. Down/distance are untouched by that function by design, which
is why they read identically before and after.

**Ruled out the other write path.** `quick_correction` (`event_service.py`, used 12 times in this
game, all *after* this boundary per their timestamps) can also set `quarter` directly, but it only
ever touches `down`/`distance`/`ball_spot`/`possession`/`quarter` - never `home_direction` /
`visitor_direction` / `clock_seconds`. Had a `quick_correction` bumped the quarter instead of
`end_quarter`, direction and clock would have been left exactly as they were at end of Q1 (right/
left, 46s) instead of swapping and resetting. The archive shows both changed correctly, which only
the guarded transition produces.

**Ruled out an automatic/clock-hits-zero path.** Grepped every write to `state["quarter"]`: the
only ones are `PeriodService.transition()`'s four explicit branches (`end_quarter`,
`start_second_half`, `toggle_halftime`-adjacent) and `quick_correction`'s direct set, both gated
behind `GameOperationsService`'s control-source check and both requiring an explicit `period_action`
(or `quarter` key) in an incoming request. Unlike basketball (`hoops_rules_service.py` auto-closes
a period via `HoopsPeriodService.period_is_over()`/`close_period()` inline during a play), football
has no code path that advances the quarter on its own; a crew member must always trigger it.

**Live re-execution** (real `GameOperationsService`, real state file, no mocks): seeded the exact
end-of-Q1 state (`quarter=1, down=2nd, distance=8, ball_spot=LEFT 21, home_direction=right,
visitor_direction=left, clock_seconds=46`) and called `set_values({"period_action": "end_quarter"})`
through the unmodified service:

```
BEFORE: quarter=1 down=2nd distance=8 ball_spot=LEFT 21  home=right visitor=left  clock=46  running=False
AFTER:  quarter=2 down=2nd distance=8 ball_spot=RIGHT 21 home=left  visitor=right clock=720 running=False
```

Byte-for-byte the same shape as the real game's own transition (`LEFT 21 -> RIGHT 21` here,
`LEFT 19 -> RIGHT 19` there - the same `mirror_spot()` math on a different starting yard line).

**Conclusion: no defect.** Bug 4b from the 9/18 round (`edit()`/`undo()`/`restore()` snapping the
live period/clock/direction back to an earlier value because period transitions append no
replayable event) is already fixed on `main` and this game was played entirely after that fix
landed; none of this game's corrections or its one `event_edit` touch a Q1 play or occur before the
Q1->Q2 boundary, so that class of bug does not apply here regardless. No code change for this item.

## Item 3 - phantom scroll bar behind the overlay

**Located the only candidate surface-wide.** Grepped every `overflow:auto`/`overflow-y:auto`/`scroll`
rule in every template and stylesheet the codebase can serve: everything outside
`templates/pregame_universal_overlay.html` is an operator-facing control panel (Theme Manager, Layout
Builder, roster/statistics modals, `index.html`) that OBS never captures. `templates/overlay.html` (the
live game board) has none at all. The one hit on a broadcast-visible surface is `.content` in the
pregame/halftime/delay overlay (`/pregame-overlay`) - and it is the exact same element a prior bug
report already named (`tests/test_pregame_overlay_layout_fix.py`'s docstring: "a stray scrollbar behind
the opaque `.topbar`"), which is presumably why this is described as recurring: the earlier fix (`min-
height:0`, top-anchoring, `overflow-y:auto`) stopped a tall card from blowing the whole grid row past the
1920x1080 canvas, but left `.content` with a real native scrollbar for whenever a card is taller than the
panel - which is exactly what shows up as a bar sitting over the live broadcast.

**Could not reproduce with last night's own archived content.** Seeded the real, four-item storylines
list actually saved for `FB-2026-OPEN-W05-001` (`Data/Runtime/pregame_presentation.json`) and measured
all four pregame cards live: the tallest (Storylines, 595px) came nowhere near `.content`'s available
896px. So whatever a viewer saw last night, it was not this exact card with this exact data.

**Reproduced the underlying mechanism by execution anyway.** Forced the storylines card to genuinely
overflow `.content` (appended real DOM nodes live against the running instance, no mocking) and
confirmed a real, visible native scrollbar renders in that state - `content.scrollHeight` (1976) >
`content.clientHeight` (896), an actual scrollbar track reserving real layout width. Screenshots
(1920x1080, headless Chrome, native scrollbars **not** suppressed by the capture flags) of that exact
forced-overflow state:
- **Before** (`overflow-y:auto` alone): a light scrollbar track visible the full height of the canvas
  along the right edge, starting right at the top red border.
- **After** (this fix): the same overflowing card, same clipped last line - no scrollbar anywhere.

**Fix.** `.content` keeps `overflow-y:auto` (a too-tall card still clips instead of reintroducing the
original grid-overflow bug), but its native scrollbar chrome is hidden: `scrollbar-width:none` (Firefox),
`-ms-overflow-style:none` (old Edge), and a `.content::-webkit-scrollbar{display:none}` pseudo-element
for the WebKit-family engines Chrome/Safari/OBS's own Chromium browser source actually use. Confirmed
live post-fix: `getComputedStyle(content).scrollbarWidth === "none"` and
`content.offsetWidth - content.clientWidth === 0` (zero width reserved for a scrollbar track) while
`content.scrollHeight > content.clientHeight` stays `true` - the overflow is still really being clipped,
nothing about the layout behaviour changed, only the visible bar is gone. Nobody can scroll a live
broadcast on air, so removing the affordance costs nothing real.

Commit: `328a7e2`.

## Item 4 - kickoff out-of-bounds is not modeled by the rules engine

**Confirmed from the archive.** All 10 kickoffs in `FB-2026-OPEN-W05-001` were recorded as either a
return or a touchback; no play carries any out-of-bounds representation, matching the report.
Confirmed in the code too: `rules_service.py`'s shared kickoff/punt handler has `touchback`,
`fair_catch`, `blocked` and `muffed_punt`, and nothing else - there is no way to record a kickoff going
out of bounds untouched. (A separate, unrelated `out_of_bounds` field already exists for ordinary
run/pass plays - it just stops the clock; it isn't reachable from a kickoff and doesn't model the foul.)

**Rule, confirmed against real rule text, not guessed.** NFHS's free-kick-out-of-bounds rule (a state
association's NFHS/NCAA rules-differences summary, compiled by George Demetriou, an NFHS rules
interpreter - the same kind of source-checked citation the 9/18 round used):

> **Free Kick Out-of-Bounds.** NFHS: Place ball 25 yards from previous spot, **or** a 5-yard penalty and
> re-kick, **or** a five-yard penalty from where the ball belongs to R.

So a free kick (kickoff) that goes out of bounds between the goal lines untouched by the receiving team
is a foul on the kicking team, and **the receiving team chooses** one of three remedies. This is a
**free-kick-only** foul - it does not apply to punts (a scrimmage kick going out of bounds is ordinary,
no foul, no choice), so the fix is scoped to `kind == "kickoff"` only.

**Fix.** A new sibling branch in `rules_service.py`'s `play()` (`kind == "kickoff" and
incoming["kick_out_of_bounds"]`), deliberately kept separate from the existing ~120-line kickoff/punt
return branch rather than threaded into it, so the well-tested return/touchback/fair-catch/muffed-punt
logic is untouched. Two new fields: `landing_spot` (reused - the out-of-bounds spot) and
`out_of_bounds_choice` (`"25_yard_line"` | `"rekick"` | `"spot_plus_5"`), both required - missing either
returns a named refusal (`OUT_OF_BOUNDS_SPOT_REQUIRED` / `OUT_OF_BOUNDS_CHOICE_REQUIRED`) rather than
guessing, the same pattern the codebase already uses for other choice-requiring fouls (e.g. the
second-half kickoff direction). All three enforcement spots are computed from the existing
`spot_to_coord`/`coord_to_spot`/`team_direction` helpers (no new coordinate logic) and clamped to the
field so a foul deep in a team's own territory can't walk the ball past a goal line. `rekick` is the one
choice where possession never changes: it puts `special_game_phase` back to `"kickoff"` for the same
kicking team rather than flipping possession to the receiver, reusing the existing kickoff-phase gate
instead of adding a new one.

Verified live (real `RulesService`, no mocks) from the same start/landing spot for all three choices:

| choice | result |
| --- | --- |
| `25_yard_line` | kicked from `LEFT 40`, out at `LEFT 15` -> ball at `RIGHT 35`, R's possession, fresh 1st & 10 |
| `rekick` | -> ball at `LEFT 35` (5 yards behind the kick spot), possession and `kicking_team` unchanged, `special_game_phase` back to `"kickoff"` |
| `spot_plus_5` | -> ball at `LEFT 20` (5 yards past the out-of-bounds spot), R's possession |

A punt with the same `kick_out_of_bounds` flag set is confirmed inert (falls through to the ordinary,
unchanged punt-return branch) - the flag only ever fires for `kind == "kickoff"`.

**The specific kickoff Jason wasn't sure about.** Two kickoffs in the archive, plays **#24** (Q1) and
**#142** (Q4), both have `landing_spot == "LEFT 40"` - nowhere near either goal line, which a real
touchback requires reaching or crossing - and both are recorded as touchbacks, both placing the ball at
the receiving team's own 20. The same, goal-line-nowhere-near landing spot recorded on two separate
kicks is best explained by the operator using "touchback" as the only outcome available that gives a
clean placement, standing in for a kick that actually went out of bounds around the 40 - there was
nothing else to record it with before this round. I can't confirm this with certainty (`live_state.
recent_commands`, the only command-level log, is a 200-entry rolling ledger per item 2's finding, and
both kicks are long past its retained window by archival time), so this is reported as the likely
explanation, not a certainty. If it's right, the crew's workaround **shortchanged the receiving team
both times**: from a kick spot around the 40, the `25_yard_line` choice this round adds would typically
land well inside midfield, better field position than the own-20 a touchback gives.

*(in progress)*
