# Diamond overlay contract

Baseball engine P0 deliverable (docs/BASEBALL_SOFTBALL_ENGINE_SCOPING_PLAN.md).
Reconciles the field-level shape the **rendering layer already ships and
consumes today** (Phase C's `productionDiamondState()` groundwork, T1's
Collegiate baseball/softball structural-parity work) against what the
**baseball/softball engine** (P1 onward: `engine_router.py`, `diamond_*`
services, `lineup_service.py`) must publish onto the live runtime-state
payload. This is the interface both sides code against; treat it as load-
bearing the same way `docs/PHASE_C_THEME_SPORT_DISPATCH_PLAN.md` is for the
theme runtime.

**Authority note.** Where this contract and
`docs/CSRN_NFHS_Baseball_Softball_Rules_Engine_Spec_2026.docx` overlap, the
spec's terminology/shape wins (per the owner's own reconciliation); this
document only fixes the *wire-format field names* the already-shipped
renderer hardcodes, which the spec (correctly) does not concern itself with.

## Why this exists now, before the engine

The rendering layer was built ahead of the engine (Phase C, then T1) against
a *guessed* field shape, because the broadcast visual design needed to ship
independently of the rules/lineup engine. That guess is now load-bearing:
`csrn-production-theme-runtime.js` is unfrozen but working, and
`csrn-broadcast-layout-engine.js`/`.css` are SHA-256 gate-frozen. **The
engine must produce the shape below, not the other way around** — the P1+
work does not get to redesign these field names for its own convenience;
if a field genuinely needs to change shape, that is a renderer change with
its own re-pin, coordinated explicitly, not a silent engine-side choice.

## 1. What the renderer already reads (frozen contract, P1 must produce)

Source of truth: `productionDiamondState(source, gameSource)` in
`static/csrn-production-theme-runtime.js`, called from `mergeRuntimeState()`
for `sportFamily === "baseball" | "softball"`. `source` is the raw
`/api/runtime-state` (or equivalent live-state) payload; `gameSource` is
that payload's nested `game`/`game_state`/`gameState` object when present
(both are checked, snake_case preferred, camelCase accepted as a fallback
via the same `pick()` helper football's own fields use).

| Wire field (snake_case, camelCase fallback) | Type | Consumed by | Notes |
| --- | --- | --- | --- |
| `inning` | string/number | Score-clock-row inning number, diamond meta, line-score current-inning column | Coerced to a string for display; `Number(inning)` drives `baseballLineScorePlan`'s column math. |
| `inning_half` / `inningHalf` | `"TOP"` \| `"BOTTOM"` (also accepts `"BOT"`/`"B"`/case-insensitive, normalized) | Batting-side derivation (`half.startsWith("B")`), score-clock-row arrow, diamond `data-inning-half` | Whichever side is batting flips every half-inning; nothing else derives it independently — this is the single source. |
| `balls`, `strikes` | string/number | Diamond count (`bl-cd-count`) | Displayed as `"{balls}–{strikes}"`, defaulting to `"0"` each when absent. |
| `outs` | string/number | Diamond outs (`bl-cd-outs`), clamped `0..3` | `●`/`○` glyphs, not raw text. |
| `bases` | `[bool, bool, bool]` (1st, 2nd, 3rd) | Diamond runner highlight | Non-array/missing -> `[false, false, false]`. Order is **first, second, third** — do not confuse with `baseDiamond()`'s internal visual-order quirk noted in `test_phasec_r3_diamond_board.py` (`[bases[1], bases[2], bases[0]]`), which is a separate, older widget. |
| `pitcher_name` / `pitcherName` | string | Rail "ON THE MOUND" card (T1 item 4) | No position prefix — pitcher is always the same defensive role. |
| `batter_name` / `batterName` | string | Rail "AT BAT" card (T1 item 4) | |
| `batter_position` / `batterPosition` | string (e.g. `"SS"`) | Rail "AT BAT" card, prefixed to the name (`"SS T. Reyes"`) | Empty is fine; the prefix is simply omitted. |
| `home_hits` / `homeHits`, `visitor_hits` / `visitorHits` | number/string | Line-score R/H/E column (H), rail (not yet — see Sec.3) | `"–"` when null/empty, never `0` unless the source says so. |
| `home_errors` / `homeErrors`, `visitor_errors` / `visitorErrors` | number/string | Line-score R/H/E column (E) | Same null-vs-zero handling as hits. |
| `line_score` / `lineScore` | `{home: number[], visitor: number[]}` | Per-inning line-score cells (`baseballLineScorePlan`, `collegiateBaseballLineScoreRow`) | **0-indexed per inning** (`array[0]` = inning 1). A missing/short array reads as "not yet played" (`–`) for future innings, `"0"` for past innings with no recorded runs — see Sec.2. |
| `home_score` / `visitor_score` | number | Line-score R column, score-clock-row chips | Already the existing top-level score fields every sport uses — no baseball-specific name. |

Fields NOT read from a nested `line_score.{home,visitor}_innings` variant —
that shape was the R9 throwaway prototype's own reading
(`objectValue(runtime.line_score)[side] || objectValue(runtime.line_score)[
`${side}_innings`]`) and was removed with the prototype in T1. Only
`line_score.home` / `line_score.visitor` are live.

## 2. Column-count / open-ended-innings contract (T1, theme-runtime-wide)

The renderer does not ask the engine "how many innings should I draw." It
derives the count itself from three inputs, per `baseballInningPlan()` in
`static/csrn-broadcast-layout-engine.js` (full render) and
`baseballLineScorePlan()` in `static/csrn-production-theme-runtime.js` (live
fast-path — the two are intentionally duplicated, see the code comment on
either):

```
played = max(regulation, current_inning, len(line_score.home), len(line_score.visitor))
```

- `regulation` -- **FIXED (P3).** Both renderer copies still default it to
  `9` when `game.regulationInnings` / `runtime.regulation_innings` is
  absent, but that fallback is no longer reached once the engine publishes
  state: `overlay_serializer.py`'s `OverlaySerializer.regulation_innings()`
  resolves `active_ruleset(state, sport=...)["regulation"]
  ["scheduledInnings"]` (`7` for both baseball and softball per
  `rulesets/bat-ball-base.json`) and `OverlaySerializer.serialize()` stamps
  it onto every payload as `regulation_innings`, so the shrink/roll math
  uses the real regulation length from the first live payload onward. When
  `engine_router.py` wires this (P4), it should publish
  `OverlaySerializer.serialize(state, ...)` verbatim rather than
  reassembling these fields by hand.
- `current_inning` = `Number(inning)` from Sec.1.
- Columns beyond `played` are simply not drawn (not "drawn as empty") --
  the plan object's `innings` array has exactly `played - start + 1`
  entries.
- Past a 12-column cap the window rolls to the most recent 9 (see the CAP/
  WINDOW constants in either file) with a `⋯` cue; R/H/E are separate,
  fixed-width, and never affected by rolling.

**P1 must not** pre-truncate or pre-pad `line_score.home`/`.visitor` to a
fixed length -- publish exactly one entry per inning actually played (a
game in the top of the 3rd publishes 2-element arrays, not 9-element
arrays padded with nulls). The renderer's own math handles everything past
that.

## 3. What the renderer does NOT yet read (explicitly out of contract)

Checked in with the owner during T1 item 4 (see that round's "Rail content
scope" decision) before building anything here:

- **Live pitching/batting stats** (IP/ER/K for the pitcher, AVG/H/RBI for
  the batter) -- the rail currently renders fixed placeholder text
  (`"IP – · ER – · K –"` / `"AVG – · H – · RBI –"`), not read from any wire
  field. `statistics_service.py` has no baseball stat fields today.
- **"On Deck" (next batter)** -- not rendered at all. Requires a batting-
  order/lineup concept this scoping doc's own "Explicitly NOT in T1 (future
  round)" section (and this engine's own P0-deferred lineup work) does not
  yet provide.
- **Team Snapshot's `batting_avg`/`hits`/`rbi` keys** (the rail's *other*
  card, `.bl-team-snapshot`, distinct from the pitcher/batter card above) --
  these ARE wired to read `statistics.teams[side].{batting_avg,hits,rbi}`
  from the `/api/collegiate-statistics`-equivalent endpoint (`statDisplay()`
  in `patchCollegiateBaseballRails`), but nothing currently populates that
  endpoint with baseball data -- `statistics_service.py` is football-only.
  This is real, live wiring waiting on real data, not a placeholder string.

When P1+ adds pitching/batting stats and/or lineup/on-deck data, this is a
**contract revision**, not a silent addition: update this document's Sec.1
table, and file a matching runtime-side commit (new wire fields, rail
markup update) alongside the engine change, the same two-sided discipline
this section itself was written under.

## 4. Sport-family dispatch (already correct, no P1 action needed)

`productionSportFamily(sport)` in `static/csrn-production-theme-runtime.js`
already maps `"baseball"` and `"softball"` (case-insensitive, `-`/` `
normalized) to themselves, and anything else unrecognised to `"football"`
(the byte-identical-behavior guarantee for every non-diamond sport). P1's
engine must publish `sport: "baseball"` or `sport: "softball"` (lowercase or
not -- normalized) on the live-state payload; no other value routes to the
diamond family.

## 5. Effective profile stamp (P0, this round)

Unrelated to the wire fields above, but the other P0 deliverable: every
broadcast now carries `effective_profile_id` / `effective_profile_version`
on canonical state, stamped once at `BroadcastLifecycleService.load()` (see
`broadcast_lifecycle_service.py`, `_effective_profile_fields()`) from
`ruleset_service.resolve_id(...)` / `ruleset_service.load_ruleset(...)
.get("version", 1)`. A resumed live-state snapshot is never re-stamped.
P1's engine should read `ruleset_service.active_ruleset(state, sport=...)`
(or, for values that must never drift mid-game even if the underlying
ruleset file changes, resolve once via `effective_profile_id` instead of
re-resolving from `country`/`region`/`association` every time) rather than
inventing a second resolution path.

## 6. Traceability

| Renderer piece | File | Landed |
| --- | --- | --- |
| `productionDiamondState`, `mergeRuntimeState` baseball/softball branch | `static/csrn-production-theme-runtime.js` | Phase C |
| `applyDiamondBoardOverrides` (fast-path dispatch, all 5 diamond-family themes) | `static/csrn-production-theme-runtime.js` | Phase C R3 |
| `collegiateBaseballScorebug`, `baseballInningPlan`, `collegiateBaseballDiamond`, `collegiateBaseballLineScore*` | `static/csrn-broadcast-layout-engine.js` | T1 |
| `patchCollegiateBaseballDiamond`, `patchCollegiateBaseballLineScore*`, `baseballLineScorePlan` | `static/csrn-production-theme-runtime.js` | T1 |
| `patchCollegiateBaseballRails`, `baseballBattingSide` (rail content) | `static/csrn-production-theme-runtime.js` | T1 item 4 |
| `effective_profile_id`/`effective_profile_version` stamp | `broadcast_lifecycle_service.py` | This round (P0) |
| `bat-ball-base` / `baseball/us-nfhs` / `softball/us-nfhs` rulesets, `_CATALOG` rows | `rulesets/`, `ruleset_service.py` | This round (P0) |
| Wire-shape overlay payload (Sec.1 fields), `regulation_innings` fix | `overlay_serializer.py` | This round (P3) |
| Line score / batting box / pitching box (Sec.2 "Stat Engine") | `box_score_service.py` | This round (P3) |
