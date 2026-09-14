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
`pitch_count` and `bf` as **displayed counters** only — P4 permanently
descoped any eligibility/rest-band engine (§12's "Pitch count" row):
that determination belongs to the coaching staff, not the broadcast
platform. If a future round ever revisits this, it would need its own
explicit request rather than falling out of "later."

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

### 9.4 Cross-engine build sequence — CONFIRMED 2026-09-07 (this doc is the tracker)

Baseball, basketball and hockey engines all edit the same three shared
touch points (`sport_families.ENGINE_READY`, `ruleset_service._CATALOG`,
the new shared `engine_router.py`), so their **P0+ builds cannot land on
trunk in parallel.** Confirmed order:

1. **Baseball** (this round) — first. Furthest along: spec reconciled
   (§12), rules-verification checklist already with the owner, self-service
   rules page already scoped as P5b (§13).
2. **Basketball** (`basketball-engine-scoping-20260907`) — second. Only
   three clean MHSAA unknowns to verify (shot clock / bonus rule /
   timeouts); no structural blockers.
3. **Hockey** (`hockey-engine-scoping-20260907`) — last. Still has an open
   governing-body question (which association governs Sault College's
   hockey) that needs Jay's input before real rule content can be written;
   building it first would stall on that.

This sequences the **builds** only — all three stay **scoped in parallel**
(already done). It does not change any scoping. Each later engine's P0
rebases onto the trunk state that includes the earlier engine(s), and
*appends* its case to `engine_router.py` / its rows to `_CATALOG` / its
entry to `ENGINE_READY` rather than creating them.

---

## 10. Phased build plan (for the build round — not started)

Each phase = its own commits, full regression suite green, football live
rendering untouched, reviewed before the next.

Table reconciled with §12 (the approved spec is the authority where they
differ).

| Phase | Deliverable | Gate |
| --- | --- | --- |
| **P0** | Rebase branch onto merged trunk (R26+R27+Phase C). `docs/DIAMOND_OVERLAY_CONTRACT.md`. `RulesProfile`-shaped `rulesets/bat-ball-base.json` + `baseball/us-nfhs.json` + `softball/us-nfhs.json` with `_source_notes` for every flagged value (§8.1). `ruleset_service._CATALOG` rows + golden tests. Per-game `effectiveProfileId` + `effectiveProfileVersion` stamped at `new_broadcast`. | Ruleset resolves; `_source_notes` present for all flagged keys; football rulesets byte-identical. |
| **P1** | `diamond_state_service` (canonical fields + pure mutators + `stateHash`) + append-only event reducer with start-of-game / end-of-half-inning snapshots + `at_bat_rules_service` (PA outcomes, `runnerOutcomes[]`, operator-override base-running, `UmpireRulingPayload` / `NEEDS_RULING` path) + `inning_service` + `game_end_evaluator` (regulation / run-rule / walk-off / time-limit / tiebreaker, `TIEBREAKER_RUNNER_PLACED` as a first-class event) + `rules_validator` (HARD_ERROR / SOFT_WARNING / NEEDS_RULING / INFO). No UI. | A scripted 9-inning game reaches a correct `final` state + line score through service calls; spec §19 `END-*`, `RUL-01` and the §19.1 replay/void invariants pass. |
| **P2** | `lineup_service` — **baseball sub-engine** (starter-centric re-entry, NONE / TRADITIONAL_DH / PLAYER_DH, `PLAYER_DEFENSIVE_MEETING` vs `CHARGED_CONFERENCE`) and **softball sub-engine** (any-player re-entry, full DP/FLEX transition table + guided wizard, HARD invariant *DP+FLEX never both on offense*); courtesy runners (role-at-time snapshot); batting-out-of-order `BattingOrderAlert` + `AppealRuling` (detection ≠ enforcement); due-up. `diamond_event_service` (operator boundary; `EVENT_VOIDED` / `EVENT_CORRECTED` ledger events). Suspension snapshot / resume (spec §11.4). `game_operations_service` baseball extensions. | Spec §19 `BB-01…BB-06`, `SB-01…SB-06`, `CR-01/02`, `BOO-01/02`, `SUS-01`, `COR-01` pass; undo/redo parity with football. |
| **P3** | `box_score_service` (line score + batting/pitching boxes from the ledger). Overlay-state serializer emitting the §7 contract (incl. the T1 rail gaps). | `box_score_service.report(state)` matches a hand-scored test game; overlay payload validates against `DIAMOND_OVERLAY_CONTRACT.md`. |
| **P4** | `routes/diamond_game_routes.py` blueprint (mirror `live_game_routes.py`). `app.py` + `phase5_architecture.py` wiring. `engine_router` dispatch on `state["sport"]`. `game_operations_service` baseball extension (deferred from P2). | Football routes untouched; new routes covered; architecture audit passes. |

### Phase status

- **P0 — DONE.** `docs/DIAMOND_OVERLAY_CONTRACT.md`, `rulesets/bat-ball-base.json` + `baseball/us-nfhs.json` + `softball/us-nfhs.json`, `ruleset_service._CATALOG` rows, `effective_profile_id`/`effective_profile_version` stamped in `BroadcastLifecycleService.load()`. Gate passed; football byte-identical throughout.
- **P1 — DONE.** `diamond_state_service.py`, `at_bat_rules_service.py`, `inning_service.py`, `game_end_evaluator.py`, `rules_validator.py`. Gate passed: `tests/test_baseball_engine_p1_reducer.py`'s scripted regulation-length game (the real 7-inning ruleset, not a hardcoded 9), `END-01`–`END-04`, `RUL-01`, and the §19.1 replay/void/suspend invariants.
- **P2 — DONE.** `lineup_service.py` (baseball + softball sub-engines, courtesy runners, batting-order alerts), `diamond_event_service.py` (undo/redo, `EVENT_VOIDED`/`EVENT_CORRECTED`), `game_suspension_service.py` (`SUS-01`). Gate passed: `tests/test_baseball_engine_p2_lineup.py` (`BB-01`–`BB-06`, `SB-01`–`SB-06`, `CR-01`/`CR-02`, `BOO-01`/`BOO-02`) and `tests/test_baseball_engine_p2_corrections_and_suspension.py` (`SUS-01`, `COR-01`, undo/redo parity). **Scoping note:** "`game_operations_service` baseball extensions" from this row's own deliverable list is deferred to P4 — `GameOperationsService`'s `DEFAULT_STATE`/reset machinery has no baseball/lineup fields to extend until P4's own `app.py` wiring puts them there; extending it now would be dead code with nothing to call it.
- **P3 — DONE.** `box_score_service.py` (line score + batting/pitching boxes from the ledger, earned-runs deliberately left unmodeled with an explicit note), `overlay_serializer.py` (`OverlaySerializer.serialize()` emitting the §7/`DIAMOND_OVERLAY_CONTRACT.md` wire shape; closes the `regulation_innings` gap that doc flagged as a P1 leftover, now resolved from the real ruleset instead of the renderer's hardcoded 9). Gate passed: `tests/test_baseball_engine_p3_box_score.py` (hand-scored half-inning match, stability/non-mutation, voided-event exclusion, full wire-field conformance). `diamond_state_service.py::apply_plate_appearance` gained an additive `batterId`/`pitcherId` passthrough (no-op unless a caller supplies them) to make per-player attribution possible.
- **P4 — DONE.** `engine_router.py` (`state["sport"]` dispatch; the `diamond_view()`/`commit_diamond_view()` adapter that lets `state["diamond"]` stay a namespaced sub-key while every P0-P3 service keeps working against the flat dict shape it was built and tested against). `diamond_game_operations_service.py` (the "`game_operations_service` baseball extensions" deferred from P2 — a separate module, not an edit to `game_operations_service.py`, reusing the same `load_state`/`save_state`/`transaction_lock` plumbing; a single generic `dispatch()` covers all ~28 P1/P2 mutators rather than one hand-written wrapper per action). `routes/diamond_game_routes.py` (new `/api/diamond/...` URLs, zero edits to football's own routes). `app.py` + `phase5_architecture.py` wiring (blueprint registered, allowlisted, one public overlay-state endpoint allowlisted). **Pitch-count eligibility engine descoped** (owner decision — see §12's "Pitch count" row): pitch count stays an informational post-game stat only, nothing enforced or flagged live. Gate passed: `tests/test_baseball_engine_p4_engine_router.py`, `tests/test_baseball_engine_p4_diamond_game_operations_service.py`, `tests/test_diamond_game_routes_blueprint.py`; full suite at the known baseline (zero regressions); `test_phase_5_architecture.py`/`test_theme_architecture.py`/`test_deployment_architecture.py` pass with the new blueprint allowlisted.
- **P5 — DONE.** `sport_families.ENGINE_READY += {"baseball","softball"}` (the flag that makes the already-built diamond engine reachable through the operator UI's existing sport-context switcher and family/other-sport tiles — both already sport-count-agnostic, so no route/template change was needed for the tiles themselves). `broadcast_lifecycle_service.py::_state_from_record()` stamps a fresh `state["diamond"]` onto a newly-loaded baseball/softball broadcast (same standard as every other field it sets fresh at load time). `templates/index.html`'s Sport dropdown offers real Baseball/Softball options (no longer "(future)"); a new `diamondControlPanel` section (`static/csrn-diamond-controls.js`) covers every deliverable this row originally scoped: starting-lineup builder (roster-driven, DH-mode-aware), plate-appearance entry, a guided lineup-change wizard (substitution / re-entry / position-change / DH / DP-FLEX / courtesy-runner / team-level actions — all 15 `lineup_service` transitions reachable), a batting-order-check panel (P2's `record_batter`/`apply_appeal_ruling`/`dismiss_alert_no_appeal`, not originally called out in this row but exposed since P2 built it), an umpire-ruling form matching `apply_ruling()`'s real `baseAwards`/`outsAwarded`/`ballStatus` payload shape, undo/redo/suspend/resume/confirm-game-end, and a box-score modal. `render()` branches on `state["sport"]` and returns before any football-specific rendering runs for a diamond broadcast — football's own code path is provably unchanged (a test asserts `/api/score`/`/api/set` never touched). Gate passed: `tests/test_baseball_engine_p5_operator_ui.py` (11 tests, including a cross-file consistency check pinning every UI action name against `diamond_game_operations_service.ACTIONS` so a typo can never silently 404) plus a full manual browser smoke test (PIN setup, sport-tile licensing, broadcast creation with live ruleset re-scoping, starting lineup, a scripted home run correctly updating the rendered scoreboard and box score, undo reverting it, suspend/resume toggling the phase badge). Void/correct-event (arbitrary ledger corrections beyond undo/redo) were deliberately left out of this round's UI scope — undo/redo already covers "operator runs a full game," and targeted event correction is a power-user feature for a later pass.
| **P5** | Operator UI: `templates/_diamond_controls.html` partial — PA outcome entry, between-PA events, ruling workflow, substitution **wizard** (shows slot / starter-sub / prior exits / special role / pitcher-catcher status; picks substitution vs re-entry vs position-change vs DH/DP-FLEX vs courtesy runner vs correction), lineup editor, manual set-value. `sport_families.ENGINE_READY += {"baseball","softball"}`. | End-to-end: operator runs a full game from the UI; all five themes render it live. |

- **P2 followup — DONE (2026-09-14).** Four owner-directed changes to
  already-merged P1/P2 code, each preceded by an investigation reported
  back and independently re-verified by the owner against the live
  source before any code was touched.
  1. **Mercy-rule/game-end ledger fix (a real bug, not a feature gap).**
     `at_bat_rules_service.confirm_game_end()` used to set
     `state["status"]`/`state["official_game_end_reason"]` directly,
     completely outside the event ledger -- undo/void_event had nothing
     to act on, and any unrelated rebuild (voiding an earlier, unrelated
     play) silently wiped `official_game_end_reason` back to `None`
     (a CANONICAL_FIELDS entry, reset every rebuild) while `status`
     stayed stuck at `"completed"` (not a CANONICAL_FIELDS entry,
     untouched by rebuild) -- an inconsistent, strand-able state.
     Fixed by making `GAME_END_CONFIRMED` a real, voidable ledger event:
     `diamond_state_service.apply_game_end_confirmed()` is the new
     structural interpreter (sets both fields together, live-apply and
     replay share the same code, per this module's own discipline).
     `status` deliberately did **not** join `CANONICAL_FIELDS` outright --
     `game_suspension_service.py` also owns `status` transitions
     ("suspended" / restored) entirely outside this ledger, and a blanket
     per-rebuild reset would have clobbered a suspended game on every
     unrelated undo. Instead, `rebuild()` derives `status` back to
     `"live"` narrowly, only when no non-voided `GAME_END_CONFIRMED`
     event survives a replay -- correct for the game-end case, inert for
     every other status value. Net effect: "reopen a game ended by
     mistake" is just `DiamondEventService.void_event()`/`undo()` on
     that event -- no separate reopen method. Walk-off and regulation
     confirms are unchanged (same `confirm_game_end()` call, any
     `reason` string, always was and remains un-gated) -- verified with a
     dedicated test plus a live browser confirm-then-undo round trip.
  2. **Courtesy runner: universal, not association-gated.**
     `lineup_service.enter_courtesy_runner()`'s hardcoded
     `if for_role_at_time not in {"PITCHER", "CATCHER"}: raise
     ValueError(...)` is gone -- any operator can enter a courtesy
     runner for any player, any game, any association, any time. The
     ruleset's own `courtesyRunnerPolicy.enabled`/`roles` fields were
     never actually read by any code path (confirmed before touching
     anything) -- they're left in the ruleset JSON, `false`/informational
     only, with `_source_notes` rewritten to say so explicitly rather
     than describing a jurisdiction-gated policy that no longer exists
     in the engine. Special-role modeling (role-at-time snapshot, not
     ordinary substitution) is unchanged -- confirmed live for a
     `SHORTSTOP` courtesy runner, a role the old code would have
     rejected outright.
  3. **International tiebreaker: wired up, operator-chosen inning.**
     `game_end_evaluator.seed_tiebreaker_runner()` was previously
     **absent from `diamond_game_operations_service.ACTIONS` entirely** --
     unreachable by any operator, not just ruleset-gated on its inning
     number. Both gaps closed together: the action is now dispatchable,
     a new "International Tiebreaker" panel exists in the operator UI
     (`tbPlayerId` / `tbStartingInning`), and `starting_inning` is now a
     **required** parameter -- the method no longer falls back to the
     ruleset's own `tieBreaker.startsAtInning` internally. The UI's
     pre-filled `8` is a static, sensible default, not read from the live
     ruleset (kept simple, per the owner's own "if convenient" framing);
     whatever the operator confirms is what gets recorded in the
     `TIEBREAKER_RUNNER_PLACED` event's `startingInning` field, every
     time. The `RUNNER_ON_SECOND` mode gate itself is unchanged. No
     shipped ruleset has this mode active yet (only an MHSAA overlay
     would, and that's P6, not built) -- confirmed live that the wiring
     itself returns a real `TIEBREAKER_NOT_ACTIVE` domain response, not
     an unknown-action error.
  4. **Regulation length: narrow per-broadcast override.** A new
     `regulation_innings_override` field -- set at broadcast creation or
     edit (`broadcast_service.py`, a plain optional number field on the
     Create/Edit Broadcast form), stamped onto live state
     (`broadcast_lifecycle_service.py`), threaded through
     `engine_router.diamond_view()`'s existing shared-field passthrough
     (same treatment as `effective_profile_id`) -- that
     `game_end_evaluator._scheduled_innings()` checks before falling back
     to the resolved ruleset's own `regulation.scheduledInnings`. Not the
     full P5b self-service `RulesProfile` editor (P0 already landed the
     general baseline→state→competition→game override *schema*; the
     operator-facing editing *workflow* for it is P5b's own larger scope,
     confirmed still not built when investigated) -- this is a standalone
     field for just this one value, exactly as scoped. Verified live: a
     broadcast created with the override correctly drove both the
     walk-off and regulation game-end candidates off the overridden
     inning, not the ruleset's.
  - Gate passed: `tests/test_baseball_engine_p2_followup.py` (23 tests
    covering all four items, including the ledger-event/rebuild replay
    and void invariants for item 1 specifically) plus updates to
    `tests/test_baseball_engine_p1_reducer.py` (the tiebreaker signature
    change). A real manual browser smoke test drove all four through
    the actual dispatched actions against a real broadcast: confirm →
    undo reopened the game (status `"live"`, reason `null`, the original
    event still in the ledger marked voided) with `regulation_innings_
    override` visible on live state throughout; a `SHORTSTOP` courtesy
    runner and a `seed_tiebreaker_runner` dispatch both round-tripped
    correctly through the real API.
  - Full suite: 2965 passed (2942 + 23 new), 2 known-environmental
    failures, zero regressions.
| **P5b** | **Self-service `RulesProfile` editor** — see §13. | An operator creates a working profile for a *new* state/league from a form + clones the pre-loaded MHSAA template, with no CSRN-side profile build. |
| **P6** | `baseball/us-ms-mhsaa.json` + `softball/us-ms-mhsaa.json` shipped as **pre-loaded clonable seed templates** (MS pitch bands, run rule, courtesy runner, softball double-first-base + international tiebreaker; timezone; classification) once the §8.1 / spec §17 values are rulebook-confirmed by the owner. Handbook revision/effective date stored on the profile. | MHSAA values owner-confirmed; `_source_notes` updated/cleared; seed templates load in the P5b editor. |
| **Later (not this engine)** | Pitch-by-pitch entry; double-switch batting-slot automation; defensive putout/assist auto-attribution; automated earned-run determination; any **auto-forfeit / administrative penalty** inference (permanently out — always human-declared). | — |

---

## 11. Open questions — resolved 2026-09-07

1. **Ordering** — **Confirmed.** No P0+ work on this branch until Round 26 +
   Round 27 + Phase C merge to trunk post-Friday; then rebase
   `baseball-engine-scoping-20260907` onto merged trunk and proceed. Same
   cross-branch-collision reasoning applied everywhere this arc.
2. **`engine_router.py` vs editing `canonical_state_service`** —
   **Confirmed: dispatch module.** Football's files stay untouched; same
   pattern Phase C used (new dispatch layer, not a rewrite of a contended
   file).
3. **`index.html` partial** — accepted as the plan of record (see §9.2);
   confirm at P5.
4. **DH / DP-FLEX scope** — **superseded by the approved spec (§12 below):
   all three baseball DH modes and the full softball DP/FLEX state machine
   are in scope**, P2.
5. **Earned/unearned runs** — operator-flagged, no automated ER (matches
   the spec's "record the ruling, don't officiate" principle).
6. **Base-running** — propose-then-override retained; the spec's
   `runnerOutcomes[]` PA-output contract (spec §7.2) is the structured form.
7. **P6 rulebook values** — **owner: the user**, sourcing NFHS/MHSAA
   baseball + softball rulebooks directly (the role Jay played for Canadian
   football). The approved spec (§17) already supplies best-effort MHSAA
   2026-27 values *with* `authorityRef` citations; P6 stays blocked until
   the user confirms them against the licensed books, and every unconfirmed
   value ships with a `_source_notes` entry as before.
8. **Softball as its own family** — confirmed: one shared *event* engine,
   **sport-specific lineup/substitution state machines** (spec bottom line,
   §16), jurisdiction-specific profiles.

---

## 12. Reconciliation with the approved implementation spec (2026-09-07)

`docs/CSRN_NFHS_Baseball_Softball_Rules_Engine_Spec_2026.docx` (v1.0,
Sept 2026) is now **the governing design reference** for the build. It is
consistent with this scoping plan's architecture and *extends* it in the
following places — the build (P0+) follows the spec where the two differ:

| Area | This plan said | Spec adds / changes | Effect on the phased plan |
| --- | --- | --- | --- |
| **Authority model** | errors / ER operator-flagged, not inferred | Pervasive principle: **"record reality first, validate second."** Engine auto-determines only deterministic mechanics (count, outs, next slot, base occupancy, score arithmetic, run-rule *threshold met*, lineup-history facts). Everything judgment-based (obstruction, interference, balk/illegal pitch, catch/no-catch, batting-out-of-order penalty, illegal-player enforcement, official termination/forfeit) is **recorded from a human** via a generic `UmpireRulingPayload`. Validator severity is `HARD_ERROR` / `SOFT_WARNING` / `NEEDS_RULING` / `INFO` — never a single "illegal" boolean; it may block only internal impossibilities. | P1 `at_bat_rules_service` gains the `NEEDS_RULING` path + `UmpireRulingPayload` reducer input. New: a `rules_validator` producing severity-tagged messages. |
| **Event sourcing** | lean on `live_command_service` revision chain + Play Register | Formal **append-only event ledger**; `AuthoritativeState = reduce(snapshot, eventsAfter)`; `EVENT_VOIDED` / `EVENT_CORRECTED` reference the original, never destroy it; snapshots at **start of game, end of every half-inning, immediately before suspension**, plus periodic. `stateHash` for deterministic-replay tests. | P1 builds the reducer + snapshot cadence explicitly; P2 corrections are ledger events, not `live_command_service` undo alone. |
| **Rules profile** | ruleset JSON + `_source_notes`, `extends` chain | `RulesProfile` object (spec §3): `regulation`, `runRules[]` (array, each with `authorityRef` + `effectiveDate` + `appliesTo:[POSTSEASON]`), `timeLimit`, `tieBreaker`, `suspendedGame`, `lineup{reentry,dh,dpFlex,courtesyRunner}`, `pitching{pitchCount,...}`, `field{doubleFirstBase,...}`, `communications`. **Profile version is persisted on the game at creation** (`effectiveProfileId` + `effectiveProfileVersion`); a later master-profile edit never changes a historical game. | P0 ruleset JSON adopts this shape (still `extends`-chained, still `_source_notes` for unverified values). `game_operations_service` stamps the resolved profile id+version onto canonical state at `new_broadcast`. |
| **Baseball DH** | `standard_dh` + `none` in P1, "player/DH later" | **All three modes in scope**: `NONE` / `TRADITIONAL_DH` / `PLAYER_DH`; player/DH = one player, **one** re-entry entitlement; locked after lineup acceptance (correction workflow to change). | P2 `lineup_service` (baseball sub-engine). |
| **Softball DP/FLEX** | "later round" | **In scope**: full transition table (spec §9.3), HARD invariant *DP and FLEX never both on offense*, guided transition **wizard** (no free-form position picker), 9/10 living-lineup count. | P2 `lineup_service` (softball sub-engine — genuinely separate from baseball). |
| **Courtesy runner** | ruleset flag, temporary role | Same, plus: store **role-at-time snapshot** (PITCHER/CATCHER) on entry, never derive later; do not close the pitcher/catcher lineup appearance; `eligibilitySnapshot`; **version the first-inning/first-batter conditions** (NFHS softball changes this for 2027). | P2. |
| **Game-ending engine** | walk-off / mercy / extras in `inning_service.transition()` | Add: `timeLimit` policy (expiry ≠ result unless profile defines the follow-on), **suspension/resumption** with an exact restoration snapshot (spec §11.4), `TIEBREAKER_RUNNER_PLACED` as a **first-class event** (not a silent 2B mutation). Evaluation order fixed (spec §11.1). | P1 `inning_service` + a `game_end_evaluator`; P2 suspension snapshot/restore. |
| **Pitch count** | display-only counters; enforcement "later" | **Descoped (owner decision, P4).** Rest-band eligibility (`ELIGIBLE`/`WARNING`/`INELIGIBLE_BY_PROFILE`/`UNKNOWN_HISTORY`) is a coaching decision, not something CSRN adjudicates or warns on — building an "eligibility" signal risks reading as the platform making that call. Pitch count stays exactly what P3 already gives it: a raw per-pitcher counter reported in the post-game box score (`box_score_service.py`), nothing enforced or flagged live. | **Removed from P4.** No `PitchCountPolicy`, no rest-band engine, no prior-history import. `pitching.appearances_limit` in the rulesets stays informational-only metadata, same as P0/P1 already had it. |
| **Batting out of order / appeals** | not covered | `BattingOrderAlert` (detection ≠ enforcement — no auto-out, no cursor advance on detection) + `AppealRuling` (BOO / missed base / left early). | P2. |
| **2026 rule specifics** | — | `PLAYER_DEFENSIVE_MEETING` vs `CHARGED_CONFERENCE` are distinct events (baseball 2026); softball one-way coach→catcher comms (2026). | P1 event taxonomy; mostly cosmetic/counter state. |
| **Acceptance tests** | "mirror the football test files" | Spec §19 is a ready **30-scenario matrix** (BB-01…MS-02, SUS-01, BOO-*, RUL-01, COR-01) + §19.1 property tests (deterministic replay by `stateHash`, void-and-replay equivalence, profile-version immutability, no-two-runners-one-base, DP/FLEX offensive exclusivity, suspend/resume equivalence). | Adopt verbatim as the P1–P5 acceptance gate. |
| **MHSAA 2026-27 values** | flagged, unsourced | Spec §17 supplies them **with citations**: varsity pitch bands 1-25/26-50/51-75/76-105/106-120 → 0/1/2/3/4 days, max 120; MS baseball postseason run-rule 10 after 5 (or 4½ if trailing team completed its turn); MHSAA softball **double first base required 2026-27**, international tiebreaker on, 10-run-after-5 championship rule; JV baseball 1½ hr / 5 innings. **Still pending the user's licensed-book confirmation** (the spec itself carries a "Mississippi profile caution" — store the handbook revision date). | P6 inputs, still `_source_notes`-flagged until confirmed. |
| **2027 future-proofing** | noted lineup/subs deferrals | Spec §18: double first base, dugout→pitcher/catcher one-way comms, softball courtesy-runner first-batter removal, softball comms expansion — **version, never retrofit** into a 2026 game. | Post-engine; profile-version feature flags. |

**Net scope change:** P2 gains softball DP/FLEX, all baseball DH modes,
batting-out-of-order/appeals, and suspension snapshot/restore. P4's
pitch-count scope was walked back down from an eligibility engine to
informational-only stats (owner decision — see the Pitch count row
above): no `PitchCountPolicy`, no rest-band status, no prior-history
import. The architecture (§2–§3, the `diamond_*` parallel services,
`engine_router` dispatch, zero football-file edits, zero theme re-pins)
is unchanged. The spec's §19 test matrix replaces "mirror the football
tests" as the P1–P5 gate, minus the `MS-*` pitch-eligibility scenarios,
which do not apply now that eligibility isn't built.

---

## 13. Self-service rules page (P5b — added 2026-09-07)

**Requirement.** The operator edits **every `RulesProfile` field directly** —
pitch-count bands, run-rule thresholds, courtesy-runner policy, tiebreaker
policy, DH modes, regulation length, time limit, suspended-game policy,
field flags, comms — from a form. A new state or league is supported by an
operator filling out that form, **not** by CSRN building and verifying a
profile first. CSRN ships *starting templates*, not a locked list.

**Why it's an add-on, not a schema change.** The approved spec's model is
already built for this: NFHS baseline → state overlay → competition profile
→ game override, serializable and versioned (spec §1.1, §3, §3.2). P0
already lands that schema. P5b is a **UI-exposure + editing workflow** on
top of it — no new engine or ruleset-model work.

**P5b deliverables:**

| Piece | Detail |
| --- | --- |
| Profile CRUD UI | Create / clone / edit / archive a `RulesProfile`. Every field from spec §3 editable, grouped (regulation, run rules, tiebreaker, time limit, suspended-game, lineup, pitching/pitch-count, field, communications). |
| Overlay layering shown explicitly | The editor shows which layer a value comes from (NFHS baseline / state / competition / this profile) and lets the operator override only at their layer — mirrors the spec's overlay-not-fork model. |
| Pre-loaded seed templates | The P6 MHSAA baseball + softball profiles ship **as clonable templates**, not the only options. "New profile" always offers *Clone a template* or *Start from NFHS baseline* — nobody starts from a blank form. |
| `runRules[]` / `restBands[]` array editors | Add / remove / reorder threshold rows; each row carries its own `authorityRef` + `effectiveDate` + `appliesTo` (spec §3.1). |
| Version pinning preserved | Editing a profile creates a **new version**; games already in progress keep the `effectiveProfileVersion` they were created with (spec §3.2, §11.4, §19.1). The UI must make "this changes future games only" explicit. |
| Validator feedback inline | Save surfaces `HARD_ERROR` (block) / `SOFT_WARNING` / `INFO` from the same `rules_validator` the live engine uses — e.g. a run-rule with `earliestCompletedInning` past `scheduledInnings`. |
| `_source_notes` carry-through | A cloned template keeps its `_source_notes`; the operator can clear a note when they've confirmed a value against their own rulebook — same convention as everywhere else this arc. |

**Sequencing.** After P5 (needs the operator-UI framework and the P0
schema); does **not** block on P6's rulebook confirmation (the seed
template can ship with its values still `_source_notes`-flagged and the
operator edits from there). Sized as its own phase because it is a full
CRUD surface + version-management UX, distinct from P5's live
game-operation controls.

---

*P0 through P5, plus the P2-followup round (mercy-rule ledger fix,
courtesy-runner de-gating, tiebreaker wiring, regulation-length
override), done and merged to trunk. Governing design reference:
`docs/CSRN_NFHS_Baseball_Softball_Rules_Engine_Spec_2026.docx`. P5b
(self-service RulesProfile editor, §13) and P6 (MHSAA seed templates,
owner handbook confirmation) remain not started.*
