# Basketball game engine — scoping plan

**Round:** `basketball-engine-scoping-20260907`, worktree
`C:/Users/Darth/CSRN-RoundWork/CSRN-Prod-basketball`, branched off `64ed45a`
(same base as Round 26, Round 27, Phase C, baseball scoping, hockey
scoping). **Scoping only. No engine code, no ruleset JSON, no UI.** Same
gate as the football and baseball scoping rounds.

**Authority target: MHSAA / NFHS**, first target, mirroring how the
baseball round scoped Mississippi first. NFHS boys' and girls' basketball
run one rule set, so `basketball` is not gender-split.

**Domain note.** NFHS basketball has had meaningful recent rule changes
(quarter-based team fouls from 2023-24; state-optional shot clock from
2022-23). Wherever an MHSAA-specific number is unverified it is flagged
for the owner to confirm against the current MHSAA handbook — the same
`_source_notes` discipline the baseball spec uses, and the same role the
owner is taking for the baseball P6 values.

---

## 1. Status audit — verified against the real tree at `64ed45a`

### 1.1 No basketball rules engine

| Concern | State at `64ed45a` |
| --- | --- |
| Basketball ruleset JSON | **None.** `rulesets/` = football only. |
| Period / clock / foul / bonus state machine | **None.** `canonical_state_service.py` is football-only. |
| Made/missed shots, rebounds, fouls, bonus, foul-out logic | **None.** |
| Statistics engine | Football only. |
| Operator entry UI | Football only. |
| Sport branching in the engine | **Zero** — `canonical_state_service.py:231` hard-pins `sport="football"`; no `if sport ==` in any of the six football services. |
| `broadcast_service` sport code | `basketball → "BB"` **already present** (dict also has FB/BSB/SB). |
| DragonFly roster import | `SPORT_CODES["basketball"] = "BB"`, `NCAA_SPORT_CODES["BB"] = {"MBB","WBB"}` — roster import is already basketball-aware. |

### 1.2 Basketball's place in the Round 27 model — a real `SPORT_FAMILIES` icon

Round 27's `sport_families.py` (unmerged):

```python
SPORT_FAMILIES = ("football", "basketball", "baseball", "softball", "soccer")   # each a login icon
ENGINE_READY   = frozenset({"football", "canadian_football"})
```

So — exactly like baseball — `basketball` is a **top-level licensable
family with its own login icon**, gated "coming soon" only because it is
absent from `ENGINE_READY`. Turning it on is `ENGINE_READY += {"basketball"}`
(one line) + the engine. This is the **same Round 27 file** the baseball
engine touches — ordering dep, §9.

### 1.3 Phase C already built the basketball **display** contract

`csrn-production-theme-runtime.js` (Phase C branch) has:

```js
function productionBasketballState(source, gameSource) {
  return {
    shotClock, homeFouls, visitorFouls, homeBonus, visitorBonus,
    homeTimeouts, visitorTimeouts
  };
}
```

plus a `mergeRuntimeState` basketball branch (`possession` kept — Phase C
commit 3: `hasPossession = family === "football" || family === "basketball"`),
and per-theme `applyBasketballBoardOverrides` patchers for clock / period /
shot-clock across FNS / 8-Bit / Heritage / Collegiate. **The five theme
engines already render a basketball scorebug.** So — like baseball, unlike
hockey — the display side is done; this engine only has to produce the
data in the committed key names (§7). No Phase-C-successor round needed.

---

## 2. The football engine as the template

Same six-service decomposition + `engine_router` dispatch used by the
baseball and hockey scoping plans:

| Football service | Basketball analog | Owns |
| --- | --- | --- |
| `canonical_state_service.CanonicalStateFoundation` | **`hoops_state_service.py`** | Canonical basketball fields; pure readers (`team_fouls`, `bonus_state`, `snapshot`); mutators (`apply_made_shot`, `apply_foul`, `apply_free_throws`, `apply_rebound`, `end_period`, `rebuild`). No I/O. |
| `rules_service.RulesService` | **`hoops_rules_service.py`** | `shot()` (2/3, made/missed → score + possession), `foul()` (type + shooter → team-foul accumulation, bonus check, foul-out check, FT award), `free_throw()`, `possession()` (incl. alternating-possession arrow). Pure, ruleset-parameterised. |
| `event_service.EventService` | **`hoops_event_service.py`** | Operator "what happened" boundary + `edit`/`undo`/`restore` via `live_command_service`; writes the Play Register / event ledger. |
| `period_service.PeriodService` | **`hoops_period_service.py`** | Period lifecycle: quarters **or** halves (profile-driven) → OT periods; period-foul reset (NFHS quarter fouls); clock reset; end-of-period possession-arrow handling. |
| `statistics_service.StatisticsService` | **`box_score_service.py`** | Read-only: PTS/REB/AST/STL/BLK/TO/PF per player, FG/3P/FT splits, team totals, +/- if entered. Feeds future rail panels. |
| `game_operations_service` | **shared, extended** | `ALLOWED_SET_FIELDS` gains `period`, `home_score`, `visitor_score`, `home_fouls`, `visitor_fouls`, `shot_clock`; `_default_state` branch. Never forked. |
| `ruleset_service` | **+ `basketball/*` documents + `_CATALOG` rows** | Resolver code unchanged. |

`live_command_service` + `eligibility_service` reused as-is. Dispatch on
`state["sport"]` via `engine_router.py` (same decision as baseball / hockey
— do not edit `canonical_state_service`).

---

## 3. Canonical basketball game state

Proposed `HOOPS_CANONICAL_FIELDS` (namespaced under `state["hoops"]`,
leaving football's flat `CANONICAL_FIELDS` untouched):

| Group | Fields | Notes |
| --- | --- | --- |
| Period | `period` (`"1".."4"` or `"H1"/"H2"`, `"OT"`, `"OT2"`…), `period_format` (`quarters`/`halves`, from profile), `period_length_seconds` | |
| Clock | `clock_seconds` (counts **down**), `clock_running`, `clock_started_at` | reuse football's clock plumbing |
| Shot clock | `shot_clock_seconds`, `shot_clock_visible`, `shot_clock_running` | **present only if the profile enables it** — see §4.2 |
| Score | `home_score` / `visitor_score` | |
| Team fouls | `home_team_fouls` / `visitor_team_fouls` (**per period** under NFHS quarter fouls; reset by `hoops_period_service`) | |
| Bonus | `home_bonus` / `visitor_bonus` ∈ `NONE` / `ONE_AND_ONE` / `DOUBLE` — **derived** from team fouls + the profile's bonus rule | Phase C reads `home_bonus` / `visitor_bonus` |
| Player fouls | `player_fouls: {player_id: count}`, `disqualified: [player_id…]` | foul-out threshold from profile (5 HS) |
| Possession | `possession` (`"home"`/`"visitor"`), `possession_arrow` (`"home"`/`"visitor"` — alternating possession) | Phase C keeps `possession` for basketball |
| Timeouts | `home_timeouts` / `visitor_timeouts` (remaining) | Phase C reads these |
| Players on floor | `home_on_floor` / `visitor_on_floor` (5 player_ids each) | for the box score + foul-trouble panels |
| Control | `tv_timeout` (bool), `game_status` (`scheduled`/`in_progress`/`final`/`final_ot`), `official_end_reason` | |
| Audit | `state_hash`, `profile_version`, `last_snapshot_event_id` | event-sourced, same as the baseball spec §2.1 |

### 3.1 State invariants

- `0 ≤ player_fouls[p] ≤ foul_out_threshold`; reaching it appends `p` to
  `disqualified` and requires a substitution before play resumes.
- `bonus` is a **pure function** of `{home,visitor}_team_fouls` + the
  profile bonus rule — never set directly.
- `possession_arrow` flips on every alternating-possession situation (held
  ball, simultaneous violation, etc. — recorded by the operator as a
  `HELD_BALL` event; the engine flips the arrow and assigns possession).
- Exactly 5 `*_on_floor` per team while `clock_running`.

### 3.2 Auto vs recorded (the baseball spec's "record the ruling" principle)

| Engine determines automatically | Engine records from the official / scorer |
| --- | --- |
| Score arithmetic; team-foul accumulation + **bonus threshold reached**; player-foul accumulation + **foul-out reached**; FT count implied by foul type + game situation; shot-clock/game-clock; period rollover + period-foul reset; possession-arrow flip. | Every foul call (personal / shooting / offensive / loose-ball / technical / flagrant / intentional) and *how many FTs it awards*; every violation (traveling, carry, double-dribble, 3-sec, 5-sec, 10-sec backcourt, out-of-bounds, goaltending, basket interference, kicked ball); made-vs-missed and 2-vs-3; whether a basket counts; any technical on a coach/bench; ejections. |

Validator severity: `HARD_ERROR` (6 players on the floor with the clock
running; negative timeouts), `SOFT_WARNING` (a 6th team foul in a period
with `bonus == NONE` — profile mismatch), `NEEDS_RULING` (consequence
depends on an official's call), `INFO`.

---

## 4. Ruleset-driven values (profile) — MHSAA numbers flagged

### 4.1 Structure — the profile shape (mirrors the baseball `RulesProfile`)

```
period: { format: "quarters"|"halves", count, length_seconds, ot_length_seconds, ot_count_cap }
fouls:  { team_foul_scope: "quarter"|"half"|"game", bonus_rule: <see 4.2>,
          personal_foul_disqualification: 5, technical_counts_toward_personal: bool,
          double_technical_ejection: bool }
shot_clock: { enabled: bool, length_seconds: 30|35|null, reset_offensive_rebound_seconds: 20|null }
timeouts: { full, short, carryover_ot, media_format }
overtime: { length_seconds, untimed_final_period: false }
technical: { shots_awarded, possession_after, administrative_vs_contact_distinction: bool }
```

### 4.2 The three values most likely to differ for MHSAA — **flag, don't assume**

| Value | NFHS current baseline | Why it's uncertain for MHSAA |
| --- | --- | --- |
| **Shot clock** | NFHS made a **35-second shot clock a state-adoption option** (2022-23). Many states have **not** adopted it. | MHSAA's adoption status must be confirmed. The engine models `shot_clock.enabled` either way; the *default MHSAA profile* value is the open question. Phase C already renders a shot-clock field — it simply stays blank/hidden when `enabled = false`. |
| **Bonus / one-and-one** | NFHS 2023-24: **team fouls reset each quarter; bonus (two shots) on the opponent's 5th foul of the quarter; the 1-and-1 was eliminated.** | Confirm MHSAA follows the current NFHS quarter-foul bonus and has not retained the old **7th-foul 1-and-1 / 10th-foul double bonus (half scope)**. The `bonus_rule` field supports both; the MHSAA default is the question. |
| **Timeouts** | NFHS: commonly **3 full + 2 60/30-second** per game (varies with broadcast format). | Confirm MHSAA's allotment and OT carry-over, and whether a broadcast/"media timeout" format applies. |

### 4.3 Lower-risk but still confirm

- Period format: **NFHS varsity = four 8-minute quarters**; sub-varsity /
  middle-school levels often use **6-minute quarters or halves** — a
  separate MHSAA sub-varsity profile, like the baseball JV profile.
- OT length: **NFHS = 4 minutes**; confirm.
- Personal-foul disqualification: **5** (HS) — confirm MHSAA hasn't
  deviated.
- Technical-foul shots + possession: NFHS = **2 shots + ball at
  division line**; confirm and confirm whether administrative technicals
  differ.
- Flagrant / intentional foul FT + possession handling.
- Closely-guarded 5-second count applicability (front-court only, etc.) —
  recorded as a violation ruling regardless; no engine math.

---

## 5. Play / event processing

### 5.1 Operator-entry granularity

The realistic live unit is the **possession outcome**, entered as discrete
events (comparable to football's play-by-play, finer than baseball's PA):

| Event | Operator supplies |
| --- | --- |
| Made field goal | shooter, 2 or 3, assist (optional), and-one flag |
| Missed field goal | shooter, 2 or 3 → usually followed by a rebound event |
| Free throw | shooter, made/missed, which attempt of how many |
| Rebound | player, offensive/defensive (or "team") |
| Foul | fouler, type (personal / shooting / offensive / loose-ball / technical / flagrant-1 / flagrant-2 / intentional), fouled player, **FTs awarded** (engine proposes from type + bonus, operator confirms), and whether it counts toward the team-foul total |
| Turnover / steal / block | player(s) |
| Violation | type + team (traveling, 3-sec, backcourt, shot-clock, lane, etc.) |
| Substitution | out / in, per team |
| Timeout | team, full/short |
| Held ball / jump situation | → engine flips `possession_arrow`, assigns possession |
| Period start / end | engine-driven; operator confirms |

### 5.2 Responsibility split (identical shape to football / baseball / hockey)

`hoops_event_service` validates + resolves players + calls the rules
service + writes the ledger row + owns undo/redo. `hoops_rules_service`
does the rules math (pure). `hoops_state_service` applies the delta and is
the only writer of `state["hoops"]`. `hoops_period_service` owns
period/OT transitions + per-period foul reset. `box_score_service` derives
stats read-only. `game_operations_service` (shared) persists.

---

## 6. Lineup — lightweight (contrast with baseball)

Basketball has no batting order, no re-entry limit (players sub freely),
no DH/DP-FLEX. `lineup_service` for basketball is just:

- Pre-game: 5 starters + bench per team.
- `substitute(team, out, in)` — free, any number, only gated by "must sub
  for a disqualified player before resuming."
- `*_on_floor` maintained for the box score and the "foul trouble" panel.
- Disqualification tracking (foul-out; flagrant-2 ejection; two
  technicals).

No separate phase — folded into P2 with the event service. (This is the
main structural way basketball is *simpler* than baseball.)

---

## 7. Data-contract cross-check vs Phase C

Phase C's `productionBasketballState` + `mergeRuntimeState` basketball
branch read these keys:

| Phase C key | Engine field | Status |
| --- | --- | --- |
| `shot_clock` / `shotClock` | `hoops.shot_clock_seconds` (blank when `enabled = false`) | ✅ |
| `home_fouls` / `visitor_fouls` | `hoops.home_team_fouls` / `visitor_team_fouls` | ✅ |
| `home_bonus` / `visitor_bonus` | `hoops.home_bonus` / `visitor_bonus` (`NONE`/`ONE_AND_ONE`/`DOUBLE` → theme maps to a label/badge) | ✅ |
| `home_timeouts` / `visitor_timeouts` | `hoops.*` | ✅ |
| `period` / `quarter` | `hoops.period` | ✅ (read in `mergeRuntimeState`) |
| `clock` | `hoops.clock_seconds` | ✅ |
| `possession` | `hoops.possession` | ✅ (Phase C keeps possession for basketball) |
| `home_score` / `visitor_score` | reuse football's top-level score fields | ✅ |

**Zero contract gaps for the scorebug** — Phase C already covers
everything a basketball scorebug shows. **Gaps for future rail / feature
panels** (add to the serializer when those are built, not required for
launch): `home_in_foul_trouble[]` / `visitor_in_foul_trouble[]`, leading
scorer + line, team `fg_pct` / `3p_pct`, `run` tracker (e.g. "12-2 run"),
`last_basket_text`.

**Recommendation:** a `docs/HOOPS_OVERLAY_CONTRACT.md` in P0 pinning the
key list + the `bonus` enum → label mapping, so the engine serializer and
any future rail round agree.

---

## 8. One ruleset family or divergent? (the baseball §8 question)

**Recommendation: one shared engine + one `basketball/*` ruleset family
with per-association and per-level overlays** — same as football and the
proposed baseball model:

```
rulesets/
  basketball/us-nfhs.json          # NFHS varsity baseline: 4x8 quarters, quarter fouls,
                                   #   5th-foul bonus (2 shots), 5 PF DQ, OT 4:00, shot clock OFF by default
  basketball/us-nfhs-subvarsity.json  # extends: 6-min quarters / halves, timeout differences
  basketball/us-ms-mhsaa.json      # extends us-nfhs: MHSAA shot-clock stance, bonus rule, timeout
                                   #   allotment, classification + timezone
  basketball/us-ms-mhsaa-subvarsity.json
```

Boys and girls share the profile (NFHS rules are identical). Future
college/other-association targets are new overlays, not a new engine.
`ruleset_service._CATALOG` gains
`(("US","MS","MHSAA","basketball"), "basketball/us-ms-mhsaa")` rows; the
resolver is unchanged.

### 8.1 Values flagged for owner confirmation (`_source_notes` stubs in P0)

| Value | Note |
| --- | --- |
| **Shot clock adoption** (MHSAA yes/no; if yes, 30 vs 35, reset rule) | §4.2 |
| **Bonus rule** (current NFHS quarter-foul 5th-foul two-shot bonus vs retained 7th-foul 1-and-1 / 10th double) | §4.2 |
| **Timeout allotment** + OT carry-over + media-timeout format | §4.2 |
| Sub-varsity period format (6-min quarters? halves? middle-school length) | §4.3 |
| OT length (assume 4:00 — confirm) | §4.3 |
| Personal-foul DQ count (assume 5 — confirm) | §4.3 |
| Technical-foul procedure (shots + possession spot; administrative vs contact distinction) | §4.3 |
| Flagrant / intentional foul FT + possession handling | §4.3 |
| Classification scheme + reserved school IDs for MS basketball (mirrors the football `us-ms-mhsaa.json` `classification` block) | needed for the MHSAA overlay |

---

## 9. Collision analysis (flag early, same as baseball §9)

### 9.1 Shared frozen files — **clean**

The five theme SHA-256 engine gates are **not touched** — this engine
produces data, and Phase C already built the basketball display. **Zero
re-pins**, same as the baseball round. Unlike hockey, basketball needs
**no** theme-runtime work.

### 9.2 Shared non-frozen files

| File | R26 | R27 | Phase C | Basketball | Resolution |
| --- | --- | --- | --- | --- | --- |
| `sport_families.py` | — | **creates it** | — | `ENGINE_READY += {"basketball"}` (1 line) | Ordering dep: R27 first. Final basketball commit or a trunk one-liner. **Same file baseball touches — coordinate the two additions.** |
| `canonical_state_service.py` | **+218** | — | — | **not edited** — `engine_router.py` dispatch | No collision. |
| `ruleset_service.py` | **+244** | — | — | `_CATALOG` rows only | Additive; wants R26's `_source_notes` convention merged first. **Baseball adds baseball rows to the same tuple — coordinate.** |
| `csrn-production-theme-runtime.js/.css` | — | — | Phase C owns | **not edited** — Phase C already did basketball | No collision. |
| `templates/index.html` | **+81** | **+77** | — | **+ basketball operator panel** | `templates/_hoops_controls.html` partial, one-line `{% include %}` — same fix as baseball/hockey. |
| `broadcast_service.py` | **+21** | — | — | **none** — `"BB"` code already present | Clean. |
| `app.py` / `phase5_architecture.py` | small | small | — | + blueprint reg + `EXPECTED_BLUEPRINTS` | Trivial appends. |
| `engine_router.py` | — | — | — | **shared with baseball + hockey** — same new file | The three sport engines all add a branch to one `engine_router`. Whichever lands first creates it; the others append a case. Coordinate. |

### 9.3 Ordering

Build **after** R26 + R27 + Phase C merge to trunk (depends on R26's
`ruleset_service` shape + `_source_notes`, R27's `sport_families`, and
Phase C's already-merged basketball display). P0 = rebase onto merged
trunk.

**Confirmed cross-engine build sequence (2026-09-07): baseball → basketball
→ hockey.** Basketball is **second**. Its P0 rebases onto the trunk state
that already includes the baseball engine and *appends* its rows to
`ruleset_service._CATALOG`, its case to `engine_router.py`, and its entry
to `sport_families.ENGINE_READY` rather than creating them. Full rationale
+ the tracker for this sequence live in the baseball scoping plan §9.4
(`baseball-engine-scoping-20260907`). Scoping stays parallel; only the
builds sequence.

---

## 10. Phased build plan (not started)

| Phase | Deliverable | Gate |
| --- | --- | --- |
| **P0** | Rebase onto merged trunk. `docs/HOOPS_OVERLAY_CONTRACT.md`. `rulesets/basketball/us-nfhs.json` (+ sub-varsity) + `basketball/us-ms-mhsaa.json` with `_source_notes` on every §8.1 value. `ruleset_service._CATALOG` rows + golden tests. Per-game `effective_profile_version` stamped at `new_broadcast`. | Ruleset resolves; every flagged value has a `_source_notes` entry; football rulesets byte-identical. |
| **P1** | `hoops_state_service` (canonical fields, mutators, `state_hash`) + `hoops_rules_service` (`shot`, `foul` w/ bonus + foul-out detection, `free_throw`, `possession` + AP arrow) + `hoops_period_service` (quarters/halves → OT, per-period foul reset). Append-only event ledger + period-boundary snapshots. No UI. | A scripted 4-quarter game (incl. reaching bonus, a foul-out, a held-ball arrow flip, an OT) reaches a correct `final` state through service calls; replay-by-hash + void-and-replay invariants hold. |
| **P2** | `hoops_event_service` (operator boundary, `edit`/`undo`/`restore`, `EVENT_VOIDED`/`EVENT_CORRECTED`). Lightweight `lineup` (5 + bench, free subs, DQ tracking). `box_score_service` (PTS/REB/AST/STL/BLK/TO/PF, FG/3P/FT splits, team totals). `game_operations_service` basketball extensions. | Undo/redo parity with football; a foul entered late and corrected keeps team fouls + bonus + DQ right. |
| **P3** | Overlay-state serializer emitting the §7 keys (all already consumed by Phase C). | Payload drives a live basketball scorebug across all five themes with no theme change; bonus enum → badge mapping verified. |
| **P4** | `routes/hoops_game_routes.py` blueprint (mirror `live_game_routes.py`). `engine_router` dispatch. `app.py` + `phase5_architecture.py` wiring. | Football + baseball + hockey routes untouched; architecture audit passes. |
| **P5** | Operator UI: `templates/_hoops_controls.html` partial — shot / foul / FT / rebound / turnover / violation / sub / timeout entry, ruling workflow, manual set-value. `sport_families.ENGINE_READY += {"basketball"}`. | End-to-end: operator runs a full game from the UI; all five themes render it live (they already can). |
| **P6** | MHSAA overlay values finalised once the owner confirms shot-clock stance / bonus rule / timeouts / classification against the current handbook; `_source_notes` cleared; handbook revision date stored. | Owner-confirmed; sub-varsity profile added if needed. |
| **Later (not this engine)** | Play-by-play win-probability; shot-location / heat-map analytics; automated +/- attribution; lineup-plus-minus; possession-count / pace metrics. | — |

---

## 11. Open questions for review

1. **Shot clock, bonus rule, timeouts** (§4.2) — owner to confirm MHSAA's
   current stance on all three against the handbook. P1 ships with the
   NFHS baseline behind `_source_notes`; P6 finalises.
2. **Sub-varsity scope** — is a middle-school / JV MHSAA basketball
   profile needed day one, or varsity-only first (baseball did varsity
   first, JV noted)?
3. **Event-entry depth** — full possession-by-possession (shot + rebound +
   assist every trip) vs a lighter "score / foul / timeout" mode for
   operators who can't keep pace? Recommend building the full model and
   letting the UI expose a reduced entry set.
4. **Shared touch points** (§9.2) — confirm baseball / basketball / hockey
   engines are **sequenced** onto trunk (or coordinated) given they all
   edit `sport_families.ENGINE_READY`, `ruleset_service._CATALOG`, and
   `engine_router.py`.
5. **Girls/boys** — confirmed identical (one profile)? Any MHSAA
   girls-specific administrative difference to capture?

---

### Phase status

- **P0 — DONE.** Rebased onto merged trunk (baseball P0-P5 + video-mode,
  2026-09-13) -- confirmed clean: `sport_families.ENGINE_READY`,
  `ruleset_service._CATALOG`, and Phase C's basketball display contract
  (`productionBasketballState()`) all still exactly as this doc's own
  audit described. `docs/HOOPS_OVERLAY_CONTRACT.md` (pins the wire fields
  `productionBasketballState()` already reads, plus the `home_bonus`/
  `visitor_bonus` 3-value enum -- the first and only producer of that
  enum, since no theme currently maps it to anything). `rulesets/
  basketball/us-nfhs.json` + `basketball/us-nfhs-subvarsity.json` +
  `basketball/us-ms-mhsaa.json` (unlike baseball P0, an MHSAA overlay
  ships now per this doc's own P0 row -- its 3 flagged values carried as
  unconfirmed `_source_notes` placeholders, not omitted).
  `ruleset_service._CATALOG` rows appended cleanly (baseball's rows
  already there, exactly the shape this doc expected to append onto).
  `effective_profile_id`/`effective_profile_version` stamping needed zero
  code changes -- already fully generic from baseball P0.
  Gate passed: `tests/test_basketball_engine_p0_rulesets.py` (6 tests) +
  `test_ruleset_golden.py`'s `available_rulesets()` golden updated for
  the 3 new documents. Full suite: 2836 passed (2830 + 6 new), 2 known
  environmental failures, zero regressions.
  **Flagged, not resolved this phase:** `engine_router.py` (built by
  baseball P4) turned out to be a baseball/softball-specific `state
  ["diamond"]` namespacing adapter, not the generic "one file, each sport
  appends a case" dispatch table this doc's Sec.9.2 assumed -- this
  doc's own Sec.3 already independently proposed the same `state["hoops"]`
  namespacing pattern, so the *architecture* still fits, but the actual
  *file* isn't shared generic infrastructure. Needs a decision before P1
  (not a P0 blocker): generalize `engine_router.py`, add parallel
  basketball-specific functions alongside baseball's in the same file, or
  give basketball its own adapter module.
- **P1 onward — not started.**

---

*P0 done. First real build phase (P1: `hoops_state_service`/
`hoops_rules_service`/`hoops_period_service`) is next. MHSAA-specific
numbers (shot clock, bonus rule, timeouts) still pending owner
confirmation against the current handbook -- shipped as `_source_notes`
placeholders in P0, to be finalized in P6.*
