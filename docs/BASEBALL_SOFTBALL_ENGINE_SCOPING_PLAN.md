# Baseball & Softball game engine — scoping plan

**Round:** `baseball-engine-scoping-20260907`, worktree
`C:/Users/Darth/CSRN-RoundWork/CSRN-Prod-baseball`, branched off `64ed45a`
(the same base the three pending branches — Round 26, Round 27, Phase C —
share). **Scoping only. No engine code, no ruleset JSON, no UI in this
round.** Same gate the original football-engine (Canadian) scoping round
used: audit → design → phased plan → doc for review before any build.

No season deadline drives this. Normal pacing.

---

## 1. Status audit — verified against the real tree at `64ed45a`

The prompt's summary is **correct**, with three precise corrections worth
recording before scoping.

### 1.1 Confirmed: there is no baseball rules engine

Grepped and read the real modules at `64ed45a`:

| Concern | State at `64ed45a` |
| --- | --- |
| Ruleset JSON for baseball / softball | **None.** `rulesets/` contains only `football/us-nfhs.json` and `football/us-ms-mhsaa.json`. |
| Inning / out / count / base state machine | **None.** `canonical_state_service.py` (`CanonicalStateFoundation`) is football-only — `CANONICAL_FIELDS` = down/distance/ball_spot/quarter/clock/possession/kicking-team…; mutators are `enter_pending_try` / `enter_kickoff` / `enter_free_kick` / `_apply_scrimmage_play`. |
| Base-running / scoring / errors logic | **None.** `rules_service.RulesService.play()` handles `run / pass / kickoff / punt` only. |
| Statistics engine | Football only. `statistics_service.StatisticsService.report()` derives TD/FG/XP/2PT, rush/pass yards, turnovers from the Play Register. No AB/H/RBI/IP/ER concept. |
| Operator entry UI | Football only. `templates/index.html` (7 362 lines) — `submitPlayEntry()` posts `run/pass/kickoff/punt` with football fields (ball carrier, passer, receiver, sacker, fumble, muffed punt…). |
| Lineup / batting order / substitution tracking | **None anywhere.** |
| Period / inning length, mercy, courtesy runners | Football `period_service.py` only (quarters, quarter length, OT format), sourced from the football ruleset with a frozen fallback. |
| Sport branching in the engine | **Zero.** `canonical_state_service.py:231` hard-pins `ruleset_service.resolve(country="US", region="MS", association="MHSAA", sport="football")`. No `if sport ==` anywhere in `canonical_state_service` / `rules_service` / `period_service` / `event_service` / `game_operations_service` / `statistics_service`. |

### 1.2 Correction 1 — `sport_families.py` and `is_engine_ready()` do **not** exist at `64ed45a`

They are **Round 27** work (unmerged). `git cat-file -e 64ed45a:sport_families.py` → *does not exist*. So the "baseball/softball gated as not-ready, same as hockey" behaviour the prompt describes is real **only on the Round 27 branch**, where:

```python
ENGINE_READY: frozenset[str] = frozenset({"football", "canadian_football"})
```

`base_family()` there collapses only `canadian_football → football`; `baseball` / `softball` are already distinct `SPORT_FAMILIES` with their own login icons, gated "coming soon" purely because they are absent from `ENGINE_READY`. **Turning baseball on is a one-line change to a Round 27 file** — see §10.

### 1.3 Correction 2 — the multi-ruleset / jurisdiction infrastructure is mostly **Round 26**, not base

At `64ed45a`, `ruleset_service.py` (186 lines) is deliberately football-only: `_CATALOG` has 3 football entries, `resolve(sport=…)` accepts the arg but always falls back to `DEFAULT_RULESET_ID = "football/us-nfhs"`, and `available_rulesets()` returns `{id, label, sport}` with **no jurisdiction fields**. Round 26 adds `ca-base.json` / `ca-cjfl-ofc.json`, the `_source_notes` convention, jurisdiction fields on `available_rulesets()`, `/api/rulesets`, and the `#rulesetJurisdiction` picker. The *mechanism* baseball needs (extends-chain deep-merge, `(country, region, association, sport)` catalog, `load_ruleset`) **is** in the base and is sport-agnostic already — but the operator-facing ruleset picker and the `_source_notes` pattern land with Round 26.

### 1.4 Correction 3 — `sport` already rides on the broadcast and on canonical state, unused by the engine

`broadcast_service.py` already stamps `sport` on every broadcast (id codes exist: `baseball → BSB`, `softball → SB`), filters record-inheritance by sport, and `game_operations_service.RESET_PRESERVED_FIELDS` includes `"sport"` — so `state["sport"]` is already present and preserved across resets. Nothing reads it to pick an engine. The hook is there; the switch is not.

### 1.5 Phase C is display-plumbing only — confirmed, and its contract is small

`csrn-production-theme-runtime.js` on the Phase C branch has `productionDiamondState(source, gameSource)` reading a fixed key set (§7). It ships **inert** — `mergeRuntimeState` populates baseball game fields only from a runtime payload that no backend produces yet. All five theme engines already *render* an inning/count/outs/bases/pitcher/batter/line-score layout (that was the pre-Phase-C finding). **Nothing on the display side is blocked on this engine; this engine must match the display's committed key names (§7) so there is no second reconciliation.**

---

## 2. The football engine as the template

Six services, each a Flask-independent, persistence-independent boundary,
composed by `routes/live_game_routes.py` and persisted by
`GameOperationsService`:

| Service | Role | Baseball analog |
| --- | --- | --- |
| `canonical_state_service.CanonicalStateFoundation` | Canonical field list; pure readers (`team_roles`, `field_state`, `snapshot`); **state-machine mutators** for phase changes (`enter_kickoff`, `_apply_scrimmage_play`, `rebuild`). No I/O. | **`diamond_state_service.py`** — canonical baseball fields; readers (`batting_roles`, `base_state`, `snapshot`); mutators (`apply_plate_appearance`, `advance_runners`, `record_out`, `end_half_inning`, `rebuild`). |
| `rules_service.RulesService` | Rules boundary. `play()` maps a play payload → state delta under football rules; `clock_control()`, `field_direction()`. | **`at_bat_rules_service.py`** — `plate_appearance()` maps an at-bat-outcome payload → state delta under baseball rules; `pitch()`, `baserunning()`, `pickoff()` / `steal()` / `wild_pitch()`. |
| `event_service.EventService` | Operator "what happened" boundary + corrections. `trigger()` (scoring), `quick_correction()`, `edit()`, `undo()`, `restore()`; builds Play Register records. | **`diamond_event_service.py`** — `record_at_bat()`, `record_baserunning()`, `record_pitching_change()`, plus `edit()` / `undo()` / `restore()` reusing `live_command_service` verbatim. |
| `period_service.PeriodService` | Period lifecycle reducer. `transition()` — quarter→quarter, halftime, OT; direction swap; clock reset. Structure from ruleset + frozen fallback. | **`inning_service.py`** — `transition()` — third-out → half flip; bottom-3rd-out → inning rollover; regulation-length check; extras entry (+ tiebreaker runner if ruleset); walk-off; mercy-rule check; game end. |
| `statistics_service.StatisticsService` | Read-only. Derives team + player rows from the Play Register. | **`box_score_service.py`** — derives the line score + batting box (AB R H RBI BB K AVG) + pitching box (IP H R ER BB K PC) from the at-bat log. Feeds the T1 rail stat fields. |
| `game_operations_service.GameOperationsService` | Persistence / history / source authority owner. `score()`, `set_values()` (manual overrides), `toggle_*`, `end_game()`, `reset_data()`, `new_broadcast()`. | **Extend the existing service** with baseball `ALLOWED_SET_FIELDS` (`inning`, `inning_half`, `balls`, `strikes`, `outs`, `base_1/2/3`) and a baseball `_default_state()` branch — do **not** fork it (it owns the transaction lock + revision chain for the whole app). |
| `ruleset_service` | `(country, region, association, sport)` → resolved JSON, extends-chain deep-merged. Already sport-agnostic. | Add `baseball/*` + `softball/*` documents and `_CATALOG` rows. No code change to the resolver. |
| — (no football analog) | | **`lineup_service.py`** — batting order, defensive positions, substitutions, courtesy runners, re-entry, due-up / on-deck / in-the-hole. §6. |

`live_command_service` (idempotent command dedup / revision chain) and
`eligibility_service` (roster/number resolution) are **sport-agnostic and
reused as-is**.

---

## 3. Proposed architecture

```
operator UI (index.html baseball panel)
        │  POST /api/diamond/at-bat, /pitch, /baserunning, /pitching-change,
        │       /lineup, /sub, /set-value, /inning-transition, /undo …
        ▼
routes/diamond_game_routes.py     ← new blueprint, mirrors live_game_routes.py
        ▼
 ┌─────────────────────────────────────────────────────────┐
 │ diamond_event_service ─ at_bat_rules_service ─ inning_service │
 │            │                    │                  │      │
 │            └──────► diamond_state_service ◄─────────┘      │
 │                     (canonical baseball state machine)     │
 │  lineup_service ────────────┘  (order / subs / due-up)     │
 └─────────────────────────────────────────────────────────┘
        │ persistence, revision chain, source authority
        ▼
 game_operations_service (shared, extended — not forked)
        │
        ▼  canonical state  { …, sport:"baseball", diamond:{…}, lineup:{…} }
 statistics: box_score_service.report(state)  → line score + boxes
        │
        ▼
 overlay state endpoint  →  csrn-production-theme-runtime.js (Phase C, already built)
```

**Engine dispatch.** One switch, at the boundary: `canonical_state_service`
(or a thin `engine_router`) reads `state["sport"]` (already preserved,
§1.4) and routes to the football foundation or the diamond foundation. The
football path is byte-for-byte unchanged when `sport` is absent or
`"football"`. `base_family()` (Round 27) collapses nothing for baseball, so
`"baseball"` and `"softball"` are distinct engine keys — but they **share
one implementation** parameterised by ruleset (§8).

---

## 4. Core game-state model (scoping question 1)

### 4.1 Canonical baseball fields

Proposed `DIAMOND_CANONICAL_FIELDS` (namespaced under `state["diamond"]` to
keep the football `CANONICAL_FIELDS` flat namespace untouched):

| Field | Type | Notes |
| --- | --- | --- |
| `inning` | int ≥ 1 | |
| `inning_half` | `"top"` / `"bottom"` | |
| `outs` | 0–3 (3 = side-retired, transient) | |
| `balls` / `strikes` | 0–3 / 0–2 | |
| `bases` | `[bool, bool, bool]` (1B, 2B, 3B) | matches Phase C order |
| `base_runners` | `[runnerRef|null × 3]` | lineup slot + player id per occupied base, for box score + courtesy-runner tracking |
| `home_runs` / `visitor_runs` | int | the score |
| `home_hits` / `visitor_hits` / `home_errors` / `visitor_errors` | int | RHE |
| `home_lob` / `visitor_lob` | int | left on base |
| `line_score` | `{home:[…], visitor:[…]}` runs per completed half-inning | Phase C reads `line_score` |
| `batting_team` / `fielding_team` | `"home"` / `"visitor"` | derived from `inning_half`; stored for convenience |
| `at_bat` | `{team, order_slot, player_id, name, position}` | current batter |
| `on_deck` / `in_the_hole` | same shape | computed by `lineup_service`; stored so the overlay needs no lineup logic |
| `pitcher` | `{team, player_id, name}` + running `pitch_count`, `bf` (batters faced) | current pitcher |
| `count_pitch_log` | list of `"B"/"S"/"F"/"X"` for the current PA (optional, P3+) | |
| `regulation_innings` | int, **from ruleset** | 7 or 9 |
| `game_status` | `"scheduled"/"in_progress"/"final"/"final_extras"/"final_mercy"` | |
| `last_play` | short structured description | Play Register hydration |

`state["sport"]`, `home_team`, `visitor_team`, identities, venue, date etc.
stay in the shared top-level canonical state exactly as today.

### 4.2 Ruleset-driven values (never hardcoded — mirror football)

Everything that varies by level/association goes in the ruleset JSON, read
once with a frozen fallback (the `period_service._QUARTER_SECONDS_FALLBACK`
pattern):

| Ruleset key (`period` / `scoring` / `rules` section) | Governs |
| --- | --- |
| `regulation_innings` | 7 (HS baseball & softball, NFHS) vs 9 |
| `extra_innings.tiebreaker` | `none` / `runner_on_second` (NFHS softball adopts it; NFHS baseball by state adoption) — **flag, see §8** |
| `extra_innings.tiebreaker_start_inning` | when the placed runner begins |
| `mercy_rule` | `{differential: 10, after_inning: 5, also: {differential: 15, after_inning: 4}}` — **numbers vary by state/association, flag** |
| `courtesy_runner` | `{for: ["pitcher","catcher"], with_two_outs_only: bool}` — NFHS-standard but adoption/《specifics》 vary — **flag** |
| `re_entry` | `{starters_may_reenter: true, once: true, same_slot: true}` (NFHS) vs none |
| `dh_rule` | `none` / `standard_dh` / `dh_for_pitcher_only` / `flex` (softball) |
| `pitching.balk_enforced` | bool (softball: no balk; illegal pitch instead) |
| `pitching.appearances_limit` | pitch-count / days-rest rules exist in NFHS baseball — **model as informational only in P1**, not enforced |
| `strikes_for_out` / `balls_for_walk` | 3 / 4 (constant, but keep in ruleset for symmetry) |
| `dropped_third_strike` | enabled (baseball) / disabled (fast-pitch softball — batter is out) |
| `bases_length_feet`, `pitching_distance_feet`, `mound` vs `circle` | field-graphic geometry, mirrors Round 26's `length_yards` approach |

### 4.3 Extra innings, walk-off, mercy, game-end — `inning_service.transition()`

- **Side retired** on the 3rd out → flip `inning_half`; carry the placed
  tiebreaker runner if `regulation_innings` exceeded and ruleset says so.
- **Bottom-half 3rd out** → `inning += 1`, `inning_half = "top"`, append
  both half-inning run totals to `line_score`.
- **Regulation reached** (`inning ≥ regulation_innings`, bottom half, home
  leads after top / any team leads after a completed bottom) → `final`.
- **Walk-off**: home takes the lead in the bottom of `≥ regulation` → game
  ends immediately, runs count per the walk-off scoring rule (only the
  winning run on a non-HR; all runs on a walk-off HR) — **rule detail to
  encode carefully; flag for rulebook confirmation.**
- **Mercy**: checked after every completed half-inning at or past
  `mercy_rule.after_inning`.

---

## 5. Play / event processing (scoping question 2)

### 5.1 Operator-entry granularity

Following football's `submitPlayEntry` (the operator picks a play *type*
then fills type-relevant fields), the realistic live-entry unit for
baseball is **one completed plate appearance**, entered after it ends, plus
a few between-PA events. Pitch-by-pitch is optional and P3+.

**Plate-appearance outcome (one dropdown + modifiers):**

| Outcome | Operator also supplies |
| --- | --- |
| Strikeout (swinging/looking) | — (dropped-3rd-strike → reached? then a base-running line) |
| Walk / Intentional walk / HBP | — (forces resolved automatically) |
| Single / Double / Triple | batted-ball location (optional), RBI count auto-suggested from runner advances the operator confirms |
| Home run | inside-the-park? RBI = runners + 1 |
| Groundout / Flyout / Lineout / Popout / Foul out | fielder(s) (for the box score putout/assist — optional in P1) |
| Fielder's choice | who's out (batter safe / lead runner out) |
| Sacrifice fly / Sacrifice bunt | run(s) / advance(s) scored |
| Reached on error | which fielder, which base reached; earned/unearned flag on any run |
| Double play / Triple play | runners retired |
| Catcher's interference / other award | base awarded |

**Between-PA events** (their own small forms, like football's clock /
penalty controls): stolen base / caught stealing, pickoff, wild pitch /
passed ball, balk, defensive indifference, pinch-hit / pinch-run,
pitching change, defensive substitution, courtesy runner in/out, pinch
runner, mound visit (cosmetic), inning-transition override, score/inning
manual `set_value`.

### 5.2 Responsibility split (mirrors football exactly)

| Layer | Owns | Football parallel |
| --- | --- | --- |
| `diamond_event_service` | Validates the operator payload, resolves player refs via `eligibility_service`, calls the rules service, writes the Play Register row, handles `edit`/`undo`/`restore` via `live_command_service`. Never computes base-running itself. | `event_service.trigger()` / `.edit()` / `.undo()` |
| `at_bat_rules_service` | The rules math: given `{outcome, batted_ball, explicit runner advances}` + current `diamond` state → `{outs_added, runs_scored, new bases, hit credited, error credited, earned/unearned, RBI}`. Pure. Ruleset-parameterised (dropped-3rd-strike, etc.). | `rules_service.play()` |
| `diamond_state_service` | Applies the delta to canonical state; owns `advance_runners`, `record_out`, `score_run`, `end_half_inning`; the only writer of `state["diamond"]`. Pure. | `canonical_state_service._apply_scrimmage_play` + mutators |
| `inning_service` | Half / inning / extras / mercy / walk-off / final transitions. | `period_service.transition()` |
| `box_score_service` | Read-only derivation of line score + batting/pitching boxes from the Play Register. | `statistics_service.report()` |
| `game_operations_service` (shared) | Persist, revision chain, source authority, `new_broadcast`, `reset_data`, manual `set_value`. | same |

### 5.3 Base-running model

Default: `at_bat_rules_service` proposes runner advances from the outcome
(walk = force only; single = batter→1B, runners +1 with the operator
confirming whether the runner from 2B scores; etc.). The operator can
**override every runner's ending base** before committing — same "propose
then let the operator correct" shape as football's spot fields. Errors and
the earned/unearned determination are operator-flagged, not inferred (ER
logic is genuinely hard and gets it wrong silently otherwise).

---

## 6. Lineup / batting order / substitutions (scoping question 3 — in scope)

New leaf-ish service `lineup_service.py`. Prerequisite for the T1
"On the Mound" / "At Bat" / "On Deck" rail panels and for a correct box
score.

### 6.1 State (`state["lineup"]`)

```
lineup: {
  home:   { batting_order: [ slot… ], bench: [ playerRef… ], pitcher_of_record: playerId },
  visitor:{ … },
}
slot: {
  order: 1..9 (or 1..10 with DH),
  player_id, name, number,
  position: "P"|"C"|"1B"|…|"DH"|"EH"|"FLEX",
  starter: bool,
  history: [ { event: "start"|"sub_in"|"sub_out"|"reenter"|"position_change"|"courtesy_in"|"courtesy_out",
              inning, half, player_id, position, ts } ]
}
```

### 6.2 Operations

| Op | Rules |
| --- | --- |
| `set_lineup(team, order)` | pre-game; 9 or 10 (DH) slots + bench; validates positions unique, one pitcher |
| `substitute(team, slot, incoming, position?)` | outgoing player marked done; if `re_entry` ruleset allows and outgoing is a *starter* who has not already re-entered, they remain eligible for their **original slot** only |
| `reenter(team, slot, player)` | ruleset-gated; once per starter |
| `position_change(team, slot, position)` | no batting-order effect (e.g. P↔1B double switch handling — flag the double-switch batting-slot swap as a P2 refinement) |
| `courtesy_runner(team, for_slot, runner)` | only for pitcher/catcher per ruleset; does not enter the batting order; auto-removed at end of the PA or when they'd bat |
| `pinch_run` / `pinch_hit` | a real substitution (uses `substitute`) |
| `due_up(team)` → `{at_bat, on_deck, in_the_hole}` | pure function of `batting_order` + last completed slot; written into `state["diamond"]` by `diamond_state_service` after each PA |

### 6.3 Explicitly deferred (noted, not built)

Pitch-count / innings-pitched eligibility enforcement and days-rest
tracking (NFHS baseball has real limits; softball does not). Model
`pitch_count` and `bf` as **displayed counters** in P1; enforcement is a
later round with its own association-specific ruleset values.

---

## 7. Data-contract cross-check vs Phase C (scoping question 4)

Phase C's `productionDiamondState(source, gameSource)` reads exactly these
keys off the overlay-state payload (snake preferred, camel accepted):

| Phase C key | Engine field that must produce it | Status |
| --- | --- | --- |
| `inning` | `diamond.inning` | ✅ direct |
| `inning_half` (`"TOP"`/`"BOTTOM"`) | `diamond.inning_half` (`"top"`/`"bottom"` → upper-cased by Phase C) | ✅ direct — engine stores lower, Phase C already normalises |
| `balls`, `strikes`, `outs` | `diamond.balls` / `.strikes` / `.outs` | ✅ direct |
| `bases` `[1B,2B,3B]` bool | `diamond.bases` | ✅ same order |
| `pitcher_name` | `diamond.pitcher.name` → flatten to `pitcher_name` in the overlay serializer | ✅ needs a flatten step |
| `batter_name` | `diamond.at_bat.name` → `batter_name` | ✅ flatten |
| `batter_position` | `diamond.at_bat.position` → `batter_position` | ✅ flatten |
| `home_hits` / `visitor_hits` / `home_errors` / `visitor_errors` | `diamond.*` direct | ✅ |
| `line_score` (`{home:[…],visitor:[…]}`) | `diamond.line_score` | ✅ same shape |
| `home_score` / `visitor_score` (read in `mergeRuntimeState`, not `productionDiamondState`) | `diamond.home_runs` / `.visitor_runs` → map to the existing top-level `home_score` / `visitor_score` canonical fields | ✅ reuse football's score fields |

**Gaps the engine must additionally emit for T1 rails (not in
`productionDiamondState` today — add to the overlay serializer now so the
T1 build needs no engine change):**

| New overlay key | Source |
| --- | --- |
| `on_deck_name`, `in_the_hole_name` | `lineup_service.due_up()` |
| `pitcher_pitch_count`, `pitcher_bf` | `diamond.pitcher.pitch_count` / `.bf` |
| `pitcher_line` (`IP-H-R-ER-BB-K` today) | `box_score_service` |
| `batter_line` (`today: 2-for-3, HR, 2 RBI`) | `box_score_service` |
| `batter_season` (AVG/OBP if roster carries it — else omit) | roster + box score |
| `last_play_text` | `diamond.last_play` |

**Recommendation:** land a tiny `docs/DIAMOND_OVERLAY_CONTRACT.md` (key
list, types, examples) in P1 and have both the engine serializer and any
future Phase-C-successor assert against it, so the two never drift.

---

## 8. Baseball vs softball — one family with overrides, or diverge? (scoping question 5)

**Recommendation: one shared engine, one shared ruleset base
(`bat-ball-base.json`), per-sport + per-association override documents** —
mirroring `football/us-nfhs.json → football/us-ms-mhsaa.json`. The two
sports share ~90% of the state machine (three outs, four balls, nine
defenders, force/tag, the line score, the box score). The differences are
all **ruleset values or a handful of ruleset booleans**, not structural:

| Difference | Handled by |
| --- | --- |
| 7 innings (both HS) vs 9 | `regulation_innings` |
| No balk in fast-pitch softball (illegal pitch instead) | `pitching.balk_enforced: false` + a label swap |
| No dropped-third-strike advance in fast-pitch softball | `dropped_third_strike: false` |
| DP/lookback/leadoff (softball runners can't leave early) | affects *base-running proposals*, a ruleset flag `leadoffs_allowed: false`; the operator override path is identical |
| "Circle" vs "mound"; base paths 60 ft vs 90 ft; pitching distance | field-graphic geometry keys (cosmetic, like Round 26's `length_yards`) |
| Courtesy runner norms | `courtesy_runner` block |
| Tiebreaker adoption | `extra_innings.tiebreaker` |

Proposed documents (names, not content — content is the build round):

```
rulesets/
  bat-ball-base.json              # shared: outs=3, balls=4, strikes=3, 9 defenders, line-score shape
  baseball/us-nfhs.json           # extends bat-ball-base: 7 innings, balk on, D3K on, leadoffs on
  baseball/us-ms-mhsaa.json       # extends baseball/us-nfhs: MS mercy numbers, timezone, classification
  softball/us-nfhs.json           # extends bat-ball-base: 7 innings, balk off, D3K off, tiebreaker on, no leadoffs
  softball/us-ms-mhsaa.json       # extends softball/us-nfhs
```

`ruleset_service._CATALOG` gains `(("US", "MS", "MHSAA", "baseball"), …)`
rows; the resolver code does not change.

### 8.1 Values to flag as unverified (`_source_notes`, Round 26 pattern)

Do **not** guess these — encode a best-effort default and a
`_source_notes` entry pointing at the rulebook, exactly as `ca-base.json`
does for `try_spot` / `no_yards_halo_yards`:

| Value | Why it's uncertain |
| --- | --- |
| `mercy_rule` differential + inning (10-after-5? 15-after-3? 8-after-5?) | Varies by state association and by regular-season vs tournament. NFHS gives a *recommended* 10-after-5; adoption differs. |
| `extra_innings.tiebreaker` for **baseball** | NFHS softball adopted the placed-runner tiebreaker; NFHS baseball leaves it to state adoption — MS specifically must be checked. |
| `courtesy_runner` scope (pitcher only? pitcher **and** catcher? two-out only?) | NFHS allows pitcher/catcher; some states restrict; "must be a non-substitute not in the game" detail. |
| `re_entry` specifics (starters only, once, original slot — and whether a **DH/FLEX** counts) | NFHS re-entry is well defined but the DH/FLEX interaction in softball is fiddly. |
| Walk-off run-counting on a non-home-run hit | The "only the winning run scores unless it's a HR" rule and its base-touching requirements. |
| `pitching.appearances_limit` numbers | NFHS baseball pitch-count rule is state-set (pitches per day + rest days). Informational-only in P1 regardless. |
| Base-path / pitching-distance figures per level (esp. softball 43 ft vs 40 ft; youth baseball 60 ft/46 ft) | Cosmetic (field graphic) but wrong looks wrong. |

---

## 9. Collision analysis (flag early, like the Collegiate field-slot)

### 9.1 Shared frozen files — **clean**

The five theme engines (`csrn-*-engine.js/.css`) and their SHA-256 gates
(`test_gate12/13/14/78/116/126/138/142`) are **not touched** by this work —
they already render the baseball layout (pre-Phase-C finding). This engine
produces *data*; the renderers are done. **Zero re-pins expected**, same as
Phase C.

### 9.2 Shared non-frozen files — **contended, manageable**

| File | Round 26 | Round 27 | Phase C | Baseball engine | Resolution |
| --- | --- | --- | --- | --- | --- |
| `sport_families.py` | — | **creates it**; `ENGINE_READY` | — | needs `+"baseball","softball"` in `ENGINE_READY` (1 line) | **Ordering dep: Round 27 merges first.** Baseball round adds the two entries as its final commit, or a trunk one-liner post-merge (the Round 27 jurisdiction-picker TODO precedent). |
| `canonical_state_service.py` | **+218** (CA field geometry, scoring block) | — | — | adds the `sport` dispatch + football path stays verbatim | Rebase baseball onto the post-Round-26 tree, or keep the dispatch in a **new** `engine_router.py` and have `canonical_state_service` call it — preferred, avoids the merge entirely. |
| `ruleset_service.py` | **+244** (jurisdiction fields, `_source_notes`, `/api/rulesets`) | — | — | adds `_CATALOG` rows only | Additive; `_CATALOG` is a tuple literal — trivial merge. Baseball should **consume** Round 26's `_source_notes` convention, so it wants Round 26 merged first too. |
| `event_service.py` / `rules_service.py` / `period_service.py` / `statistics_service.py` | **+54 / +260 / +27 / +14** | — | — | **not modified** — baseball gets parallel `diamond_*` services | No collision by design. |
| `game_operations_service.py` | — | — | — | extended (`ALLOWED_SET_FIELDS`, `_default_state` branch) | Clean — nobody else touches it. |
| `templates/index.html` | **+81** | **+77** | — | **+large** (new baseball operator panel) | **The real contention point.** 7 362-line monolith, already 2-way contended. Options: (a) accept a manual 3-way merge post-Friday; (b) put the baseball panel in a **separate template partial** `templates/_diamond_controls.html` included by `index.html` with a one-line `{% include %}` — recommended, shrinks the conflict to one line. |
| `app.py` | **+19** | **+several** | — | +blueprint registration | One-line additions each; low risk. |
| `phase5_architecture.py` (`EXPECTED_BLUEPRINTS`) | — | **+1** | — | **+1** (`diamond_game_routes`) | Trivial; append. |
| `broadcast_service.py` | **+21** | — | — | possibly none (BSB/SB codes already exist) | Likely clean. |

### 9.3 Ordering recommendation

This engine **should be built against a tree that already has Round 26 +
Round 27 merged** (it depends on the `_source_notes` convention, the
jurisdiction picker, `sport_families.ENGINE_READY`, and the Round-26
`ruleset_service` shape). Since none of those can merge before Friday, the
**scoping doc lands now; the build starts after the Friday-blocked
branches merge to trunk.** Branching off `64ed45a` today keeps the base
from forking further; the first build commit rebases onto the merged
trunk. This is called out here so it is a deliberate decision, not a
surprise.

---

## 10. Phased build plan (for the build round — not started)

Each phase = its own commits, full regression suite green, football live
rendering untouched, reviewed before the next.

| Phase | Deliverable | Gate |
| --- | --- | --- |
| **P0** | Rebase branch onto merged trunk (R26+R27+Phase C). `docs/DIAMOND_OVERLAY_CONTRACT.md`. `rulesets/bat-ball-base.json` + `baseball/us-nfhs.json` + `softball/us-nfhs.json` with `_source_notes` for every flagged value (§8.1). `ruleset_service._CATALOG` rows + golden tests. | Ruleset resolves; `_source_notes` present for all flagged keys; football rulesets byte-identical. |
| **P1** | `diamond_state_service` (canonical fields + pure mutators) + `at_bat_rules_service` (PA outcomes, operator-override base-running) + `inning_service` (half/inning/regulation/mercy/walk-off/extras). No UI. Unit tests mirror `test_canonical_state_service` / `test_rules_service` / `test_period_service`. | A scripted 9-inning game reaches a correct `final` state + line score purely through service calls. |
| **P2** | `lineup_service` (order, subs, re-entry, courtesy runner, due-up). `diamond_event_service` (operator boundary + Play Register rows + `edit`/`undo`/`restore` via `live_command_service`). `game_operations_service` baseball extensions. | Undo/redo parity with football; a sub mid-inning keeps the box score correct. |
| **P3** | `box_score_service` (line score + batting/pitching boxes). Overlay-state serializer emitting the §7 contract (incl. the T1 rail gaps). | `box_score_service.report(state)` matches a hand-scored test game; overlay payload validates against `DIAMOND_OVERLAY_CONTRACT.md`. |
| **P4** | `routes/diamond_game_routes.py` blueprint (mirror `live_game_routes.py`). `app.py` + `phase5_architecture.py` wiring. `engine_router` dispatch on `state["sport"]`. | Football routes untouched; new routes covered; architecture audit passes. |
| **P5** | Operator UI: `templates/_diamond_controls.html` partial — PA outcome entry, between-PA events, lineup editor, manual set-value. `sport_families.ENGINE_READY += {"baseball","softball"}`. | End-to-end: operator runs a full game from the UI; all five themes render it live (they already can). |
| **P6** | `baseball/us-ms-mhsaa.json` + `softball/us-ms-mhsaa.json` (MS mercy numbers, timezone, classification) once the flagged §8.1 values are rulebook-confirmed. Pitch-count **display** counters. | MHSAA values sourced + `_source_notes` updated/cleared. |
| **Later (not this engine)** | Pitch-by-pitch entry; pitch-count/rest **enforcement**; double-switch batting-slot automation; DH/FLEX edge cases; defensive putout/assist auto-attribution; automated ER determination. | — |

---

## 11. Open questions for review

1. **Ordering** (§9.3): confirm the build starts post-trunk-merge of
   R26+R27+Phase C, with P0 as the rebase. Alternative: build against
   `64ed45a` now and carry the merge pain — not recommended.
2. **`engine_router.py` vs editing `canonical_state_service`** (§3, §9.2):
   a new dispatch module keeps the football file untouched and dodges the
   Round 26 merge. Any objection to the extra indirection?
3. **`index.html` partial** (§9.2): move the baseball operator panel into
   `templates/_diamond_controls.html` (one-line `{% include %}`) to shrink
   the 3-way conflict. OK?
4. **DH policy scope**: model `dh_rule` in the ruleset from P1, but is the
   FLEX/DP softball model in scope for this engine or a later round?
   (Leaning: `standard_dh` + `none` in P1; FLEX later.)
5. **Earned/unearned runs**: operator-flagged in P1 (no automated ER).
   Acceptable, or is best-effort auto-ER wanted despite the accuracy risk?
6. **Base-running**: propose-then-override (§5.3) — confirm that's the
   right entry ergonomics vs a fuller structured base-by-base entry.
7. **The §8.1 flagged values**: who confirms the MS/NFHS mercy-rule,
   courtesy-runner, and tiebreaker specifics against a rulebook, and by
   when? P6 is blocked on it (P0–P5 ship with documented placeholders).
8. **Softball as its own `SPORT_FAMILIES` entry** already exists (Round
   27). Confirm one shared engine keyed by ruleset (§8) rather than a
   separate `softball_*` service set.

---

*Scoping only. No engine code, ruleset JSON, or UI written this round.
Awaiting review before P0.*
