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
| **P6** | MHSAA overlay values finalised: no shot clock (permanent product decision, not a handbook lookup) + bonus rule/timeouts shipped on the NFHS-generic default (deliberately not independently confirmed for MHSAA); `_source_notes` updated to reflect both as settled, not open. | Owner-confirmed; no further handbook confirmation pending. |
| **Later (not this engine)** | Play-by-play win-probability; shot-location / heat-map analytics; automated +/- attribution; lineup-plus-minus; possession-count / pace metrics. | — |

---

## 11. Open questions for review

1. ~~**Shot clock, bonus rule, timeouts** (§4.2) — owner to confirm MHSAA's
   current stance on all three against the handbook. P1 ships with the
   NFHS baseline behind `_source_notes`; P6 finalises.~~ **Resolved in P6
   (2026-09-13), not by handbook lookup but by owner decision:** no shot
   clock, ever (permanent product decision, independent of MHSAA's actual
   rule); bonus rule and timeouts ship on the NFHS-generic default,
   explicitly not independently confirmed for MHSAA and not worth chasing
   for a broadcast-only product. See the P6 phase-status entry and this
   ruleset's own `_source_notes`.
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
- **P1 — DONE (2026-09-13).** `engine_router.py` decision resolved first
  (separate round, `basketball-engine-router-p0-20260913`): extracted the
  one genuinely sport-agnostic sliver (get-or-create a namespaced
  sub-state) into `_ensure_namespaced_state()`, then added
  `hoops_view()`/`commit_hoops_view()` alongside the existing diamond pair
  in the same file -- neither a whole-module generalization nor a
  separate adapter module, per the owner's explicit decision. `hoops_view()`
  keeps period/clock/possession/scores SHARED with football (never
  namespaced under `state["hoops"]`), unlike diamond's home_score/
  visitor_score -- basketball's own contract never moved those off the top
  level, so there is nothing to project back out the way diamond's
  `sync_shared_fields()` does.
  - `hoops_state_service.py`: `HOOPS_CANONICAL_FIELDS` (Sec.3, minus the
    shared fields above) + `_SHARED_CANONICAL_FIELDS` (the outer-state
    fields the reducer also mutates -- a real architectural difference
    from diamond_state_service, which has no such split since all of its
    fields live in one flat namespace); pure mutators; `bonus_for_fouls()`
    (Sec.3.1's "pure function of team fouls + the profile bonus rule");
    seven structural event interpreters (`SHOT`, `FREE_THROW`, `REBOUND`,
    `FOUL`, `HELD_BALL`, `TURNOVER`, `PERIOD_TRANSITION`); `state_hash()` /
    `snapshot()` spanning both namespaces; the append-only reducer
    (`rebuild()`).
  - `hoops_period_service.py`: `start_game()` (seeds period/clock/shot-clock/
    timeouts from the active ruleset -- timeouts modeled as one combined
    remaining-count per team, full+short summed, since the wire contract
    only ever wants one number per team; flagged as a deliberate
    simplification), `close_period()` (quarters/halves -> OT, per-period
    foul reset per `fouls.team_foul_scope`, shot-clock reset). Refuses to
    propose a next period when the game should actually end (raises,
    rather than guessing) -- see below.
  - `hoops_rules_service.py`: `shot()`, `free_throw()`, `rebound()`,
    `foul()` (resolves counts-toward-team/personal from foul type + the
    ruleset, proposes -- never applies -- a free-throw count per Sec.5.1's
    "engine proposes, operator confirms"), `held_ball()`, `turnover()`,
    `evaluate_game_end()` / `confirm_game_end()` (mirrors baseball's
    GameEndEvaluator: proposes a candidate, never finalizes on its own).
    `TIMEOUT`/`VIOLATION`/`SUBSTITUTION` are deliberately NOT first-class
    ledger events this phase -- the doc's own P1/P2 split puts the
    operator-entry event boundary (`hoops_event_service`) in P2, and these
    three are exactly that boundary's job, not the pure reducer's.
  - **Correctness note, not a mere style choice:** bonus is charged to the
    fouling team's OPPONENT (a team's own fouls send the other team to the
    line), not to the fouling team itself -- caught and fixed during
    development, verified by the scripted test asserting `home_bonus`
    reaches `DOUBLE` from the VISITOR's fifth foul.
  - **Game-end ordering differs from baseball on purpose:** baseball's
    `at_bat_rules_service` closes the half-inning first, then evaluates
    game-end candidacy (using the already-advanced inning). Basketball
    evaluates game-end candidacy BEFORE attempting to close the period:
    once the clock reaches 0 in the final period (or an OT period) with a
    decided score, there is no well-defined "next period" to transition
    to at all, so `hoops_period_service.close_period()` deliberately
    raises rather than guess at one -- `hoops_rules_service._after_play()`
    checks for a terminal candidate first and only closes the period when
    there isn't one.
  - Gate passed exactly as specified: `tests/test_basketball_engine_p1.py`
    (11 tests) scripts a full 4-quarter game reaching the DOUBLE bonus, a
    foul-out, a held-ball arrow flip, and a tied-at-regulation trip to
    overtime ending on a decided score; replay-by-hash and
    void-and-replay invariants both hold. Additional tests cover the
    halves-format period path, the OT-cap and mismatched-period-count
    guard rails, the unrecognized-bonus-rule-type guard, and the
    shot-clock reset on period transition -- none of which any shipped
    ruleset exercises yet, so these would otherwise have zero coverage.
  - Full suite: 2869 passed (2858 + 11 new), 2 known-environmental
    failures, zero regressions.
  - **Flagged, not resolved this phase (genuinely open, not guessed at):**
    free-throw proposal for the old NFHS one-and-one/double-bonus model
    (`bonus_for_fouls()` raises on any `bonus_rule.type` other than
    `TWO_SHOT_ON_FIFTH_FOUL`, since no shipped ruleset uses the other
    shape yet -- see Sec.4.2); `fouls.team_foul_scope` values other than
    `"quarter"` are read generically but never exercised against a real
    ruleset; flagrant/intentional foul ejection handling and
    `double_technical_ejection` are not implemented (Sec.4.3, deferred to
    P2's `hoops_event_service`); the OT-cap-reached situation raises
    rather than modeling what happens next, since the scoping doc itself
    never specifies it.

- **P2 — DONE (2026-09-13).** `hoops_event_service.py` (operator
  correction boundary), `hoops_lineup_service.py` (lightweight, per Sec.6),
  `hoops_box_score_service.py` (PTS/REB/AST/STL/BLK/TO/PF, FG/3P/FT
  splits, team totals).
  - **A real P1 gap found and closed as part of this phase:**
    `hoops_period_service.start_game()` used to mutate period/clock/
    shot-clock/timeouts directly rather than through a replayable event.
    That's invisible until you build the thing that actually needs full
    replay-from-ledger -- `hoops_event_service`'s undo()/redo() -- which
    exposed it immediately: undoing back past the first real play reset
    those ruleset-derived values to zero/blank, since
    `HoopsStateFoundation.default_state()`'s structural defaults don't
    know the ruleset at all. Fixed by giving `start_game()` a proper
    `GAME_START` structural interpreter (`apply_game_start()`) and having
    it append that as the ledger's own first event, same as every other
    mutation -- `hoops_event_service.undo()`/`void_event()`/
    `correct_event()` all explicitly refuse to touch `GAME_START` itself
    (there's nothing before it to return to). Substitutions and the
    starting-five call also got the same treatment (`LINEUP_SET` /
    `SUBSTITUTION` structural interpreters + ledger events) rather than
    being left as unlogged mutations, once the pattern was clear.
  - `hoops_event_service.py`: `undo()`/`redo()` (void the most recent
    contributing event / un-void the most recently voided one, full
    rebuild each time -- same contract as `diamond_event_service.py`),
    `void_event()` (a specific, not-necessarily-latest event),
    `correct_event()` (voids the original, appends a replacement of the
    same type referencing it, rebuilds).
  - `hoops_rules_service.correct_event_for_foul()`: a foul-specific
    wrapper around `correct_event()` that re-resolves
    countsTowardTeam/countsTowardPersonal/bonusRule/foulOutThreshold
    through the SAME resolution helper (`_resolve_foul_payload()`,
    extracted from `foul()`) the original call used -- a corrected foul
    is never a hand-patched approximation of the original's bookkeeping.
  - `hoops_lineup_service.py`: `set_starting_five()` (exactly 5 distinct,
    none disqualified), `substitute()` (free/unlimited, gated only by
    structural checks -- out-player actually on the floor, in-player not
    already on it, a disqualified player can never re-enter),
    `players_needing_substitution()` (surfaces Sec.3.1's "must sub for a
    disqualified player before resuming" without itself gating the
    clock -- that stays a caller/UI responsibility).
  - `hoops_box_score_service.py`: team totals straight from
    `hoops_state_service`'s own canonical fields; per-player PTS/REB/AST/
    TO/PF from each event's own payload. STL/BLK ride as optional,
    additive `stealPlayerId`/`blockPlayerId` fields on TURNOVER/SHOT
    payloads rather than new event types (Sec.5.1 groups "turnover / steal
    / block" as one operator-entry row, and a steal/block has no
    canonical-state effect beyond the turnover/missed-shot itself) --
    same "additive attribution field, not a new event type" pattern
    baseball's own box score uses for batterId/pitcherId/resultCode.
    Always rebuilds from the ledger first, so a box score is correct
    whether requested mid-game or after a correction.
  - Gate passed exactly as specified:
    `tests/test_basketball_engine_p2.py` (12 tests) -- undo/redo/void
    behavior structurally identical to `diamond_event_service`'s (itself
    already football-EventService-shaped); a foul entered late, corrected
    to the right player, keeps team fouls/bonus/disqualification correct
    both immediately and across LATER fouls building on the corrected
    attribution; lineup starting-five/substitution/DQ-gating; a full
    box-score scenario covering every stat category plus a
    correction-reflected-in-the-box-score case.
  - Full suite: 2882 passed (2869 + 1 P1 no-baseline-rebuild test + 12 P2
    tests), 2 known-environmental failures, zero regressions.
  - **Flagged, not resolved this phase:** flagrant-2-ejection and
    two-technicals-ejection are not modeled as automatic disqualification
    triggers (Sec.4.3's `double_technical_ejection` ruleset flag is read
    by no code yet) -- P1's `apply_foul()` only auto-disqualifies via the
    personal-foul-count threshold; an explicit ejection event/pathway is
    real, additional scope, not silently folded into the foul-count
    mechanism, and deferred to whichever round actually wires the
    operator-facing foul-entry UI (P5) and can settle what an ejection
    payload should look like.

- **P3 — DONE (2026-09-13).** `hoops_overlay_serializer.py` +
  `engine_router.hoops_overlay_payload()`/`hoops_box_score_report()`.
  - Narrower than baseball's P3 by design: docs/HOOPS_OVERLAY_CONTRACT.md
    Sec.1's own "shared with football" table means period/clock/
    possession/scores are already correct on the flat state with zero
    engine action needed -- this serializer only projects the fields
    basketball alone produces (shot_clock, home/visitor_fouls, home/
    visitor_bonus, home/visitor_timeouts) onto the wire's
    already-formatted-string shape, and a dedicated test confirms it
    does NOT also emit the shared fields (a second, driftable source for
    something the renderer already reads directly would be a real risk,
    not a convenience).
  - Cross-checked the serializer's own output keys directly against
    `productionBasketballState()`'s actual source (a regex read of the
    real, already-shipped JS function, not a re-transcription of the
    contract doc) -- confirmed exact match, both directions.
  - The bonus enum is enforced, not just documented: `serialize()` raises
    if `home_bonus`/`visitor_bonus` is ever anything outside
    `{NONE, ONE_AND_ONE, DOUBLE}` -- this engine is the enum's first and
    only producer (Sec.1), so a value outside it is a real upstream bug,
    not something to coerce or pass through to a renderer with no badge
    for it.
  - **P3 finding, worth flagging plainly (not an action needed now):**
    `engine_router.hoops_view()`/`commit_hoops_view()` (built in the P0
    engine_router addendum) turn out to be unused by every one of
    hoops_state_service/hoops_rules_service/hoops_period_service/
    hoops_event_service/hoops_lineup_service/hoops_box_score_service --
    all of P1/P2 was designed from day one to take `(state, hoops)` as
    two explicit parameters and operate on the nested
    `state["hoops"]` shape directly, unlike baseball's diamond_view(),
    which is a genuinely necessary adapter reconciling namespaced storage
    with P0-P3 modules that predate the namespacing decision. Not
    deleted -- a future P4 routes layer may still want a flat single-dict
    view -- but flagged rather than silently left looking load-bearing
    when it isn't yet.
  - Gate passed: `tests/test_basketball_engine_p3.py` (8 tests) --
    field-name cross-check against the real renderer source, shot-clock
    blank-when-disabled and formatted-when-enabled, fouls/timeouts as
    formatted strings, the bonus-enum guard (both the pinned-3-values
    case and the reaches-DOUBLE-and-serializes-correctly case), the
    engine_router dispatch functions producing identical payloads to
    calling the services directly, and the shared-fields-untouched check.
  - Full suite: 2890 passed (2882 + 8 new), 2 known-environmental
    failures, zero regressions.

- **P4 — DONE (2026-09-13).** `hoops_game_operations_service.py` (new),
  `routes/hoops_game_routes.py` (new blueprint, `/api/hoops/...`),
  `app.py` + `phase5_architecture.py` wiring. First basketball work to
  touch shared/live `app.py` code paths, mirroring baseball's own P4
  exactly in shape.
  - **Confirms, rather than reopens, the P3 finding**: baseball's
    `diamond_game_operations_service.dispatch()` routes every action
    through `engine_router.diamond_view()`/`commit_diamond_view()` --
    the genuinely necessary flattening adapter for P0-P3 modules built
    before the `state["diamond"]` namespacing decision. Basketball's own
    `dispatch()` does not: every P1/P2 classmethod already takes the full
    outer `state` dict directly and mutates it in place, so there is
    nothing to flatten or fold back. `hoops_view()`/`commit_hoops_view()`
    remain unused after P4 too -- not because this phase forgot to wire
    them in, but because the P1 architecture never needed them. This is
    now a settled fact, not an open question.
  - `game_operations_service.py` (the SHARED, football-owned persistence
    boundary) was deliberately NOT extended in this phase -- despite
    Sec.2's own comparison table listing `ALLOWED_SET_FIELDS`
    gaining basketball fields. Checked directly: baseball's actual P4
    never touched that file either (its own generic "set an individual
    field" escape hatch stayed football-only), and this phase's own gate
    (Sec.10) doesn't call for it. Left for whichever round actually needs
    a manual single-field override outside the structured ACTIONS set --
    not guessed at here just because a broader architecture-comparison
    table mentioned it in passing.
  - `hoops_game_operations_service.py`: `initialize_hoops()` (unlike
    baseball's `initialize_diamond()`, this calls
    `hoops_period_service.start_game()` -- not just a bare default-state
    assignment -- since basketball's initial period length/shot clock/
    timeouts are ruleset-derived, not structural constants); `dispatch()`
    (13 ACTIONS: shot/free_throw/rebound/foul/held_ball/turnover/
    correct_foul/confirm_game_end from hoops_rules_service,
    undo/redo/void_event/correct_event from hoops_event_service,
    set_starting_five/substitute from hoops_lineup_service).
  - A real naming collision caught and fixed:
    `hoops_rules_service.correct_event_for_foul()`'s third parameter was
    originally named `payload`, which `_bind_kwargs()`'s whole-payload
    special case (built for shot/foul/etc., which take exactly one
    `payload: Mapping` argument) would have silently matched -- swallowing
    `event_id`/`reason` entirely. Renamed to `replacement_payload`
    (matching `hoops_event_service.correct_event()`'s own naming) so it
    falls through to plain by-name binding instead. Caught by exercising
    the actual dispatch path in a test, not by inspection alone.
  - `routes/hoops_game_routes.py`: `/api/hoops/initialize`,
    `/api/hoops/action/<action>`, `/api/hoops/overlay-state`
    (unauthenticated, OBS has no operator session),
    `/api/hoops/box-score` -- new URLs only, football's and baseball's own
    routes untouched (verified both by a blueprint test and by starting
    the real app and confirming `/api/hoops/overlay-state` /
    `/api/diamond/overlay-state` both correctly 409 on the current
    football broadcast, and the auth-gated action/initialize endpoints
    both correctly 401 with no session).
  - Gate passed: `tests/test_basketball_engine_p4_game_operations_service.py`
    (10 tests) + `tests/test_hoops_game_routes_blueprint.py` (10 tests) --
    generic dispatch (including the whole-payload binding for shot/foul
    and the by-name binding for correct_foul in the same scenario), undo
    reversing a shot, a late foul corrected through the full dispatch
    path keeping team fouls/personal fouls right, confirm_game_end
    propagating the shared status field, idempotent duplicate-command
    handling, and the Flask blueprint (auth requirements, football/
    baseball route non-collision, error-code-to-HTTP-status mapping).
    Football + baseball routes and the architecture audit (`phase5_
    architecture.py`'s own tests) all still pass untouched.
  - Full suite: 2910 passed (2890 + 20 new), 2 known-environmental
    failures, zero regressions.
  - **Not done in this phase, deliberately** (matches baseball's own P4
    scope, and this phase's own gate): `sport_families.ENGINE_READY`
    stays WITHOUT `"basketball"` -- routes exist and are fully tested, but
    nothing in the existing UI can reach them yet; per Sec.10's own P5
    row, turning that on is a P5, not P4, step.

- **P5 — DONE (2026-09-13).** `sport_families.ENGINE_READY += {"basketball"}`,
  `broadcast_lifecycle_service.py` auto-init, and the full operator UI
  (`templates/_hoops_controls.html` + `static/csrn-hoops-controls.js`).
  Full scoping-doc fidelity, not an MVP subset -- confirmed via
  AskUserQuestion with the owner before starting.
  - **A real gap found before any UI was written**: the scoping doc's own
    P5 row calls for "violation entry, ruling workflow, manual set-value,"
    but none of the three had backing engine support anywhere in P1-P4 --
    `hoops_state_service.py` had no `apply_violation`/`apply_ruling`/
    `apply_set_value` interpreters, and `hoops_rules_service.py` had no
    matching orchestration methods. Rather than guess at UI wired to
    nonexistent actions, this was raised to the owner (AskUserQuestion)
    and resolved as: design and build the missing engine methods first,
    with the same P1-P4 discipline, then build UI on top of a tested
    foundation. A fourth gap (timeout entry) was noticed in the same pass
    and built alongside the other three.
    - Committed separately as the "P5 engine addendum" (`4aee656`) before
      any UI code: `apply_violation()` (applies only the `possessionTo`
      the caller supplies -- goaltending/basket-interference scoring is
      deliberately NOT modeled; a ruling that awards points needs a
      separate `shot()` call), `apply_ruling()` (documented as
      basketball's own general-purpose score/possession/clock correction,
      not a transcription of an existing spec section the way baseball's
      `apply_ruling()` mirrors one), `apply_timeout()`, and
      `apply_set_value()` (`_SETTABLE_SHARED_FIELDS` /
      `_SETTABLE_HOOPS_FIELDS`, split by namespace). All four registered
      as real structural interpreters and replayable through `rebuild()`,
      matching every prior phase's event-sourcing discipline -- not a
      shortcut taken because P5 is "just the UI phase."
    - `game_operations_service.py` (the shared, football-owned boundary)
      was again deliberately left untouched for `set_value`, consistent
      with the P4 decision on the same question.
    - Gate passed: `tests/test_basketball_engine_p5_violation_ruling_
      timeout_setvalue.py` (14 tests) -- all four new interpreters/
      orchestration methods, unknown-violation-type and unsettable-field
      guards, zero-timeout HARD_ERROR, bonus recomputation on
      `set_value`, and full replay reconstruction of all four new event
      types.
  - **UI structure deliberately follows this phase's own scoping doc
    (Sec.9.2's collision-avoidance plan) rather than blindly mirroring
    baseball's own P5 choice.** Baseball's P5 built its diamond panel as
    ~200 lines inlined directly into `templates/index.html` plus a
    separate JS file. This phase instead uses a genuine
    `{% include "_hoops_controls.html" %}` partial -- confirmed viable
    first (this app's `templates/index.html` is rendered through Jinja2's
    `render_template()`, so `{% include %}` works even though no other
    template in the app currently uses it) -- keeping `index.html`'s own
    diff to a small handful of lines: the sport-dropdown enable, the
    `render()` branch, the include, and the script tag.
  - `templates/index.html`: `<option>Basketball</option>` replaces the
    disabled `(future)` placeholder; `render()` gains an `isHoopsSport`
    branch (mirroring `isDiamondSport`'s placement and hide-list) placed
    before any football-only rendering runs, so a basketball state
    (missing `quarter`/`down`/`distance`/`possession`/`coin_toss`/...)
    is never run through football-specific code that assumes those
    fields exist.
  - `static/csrn-diamond-controls.js`: a real, necessary fix to
    baseball's own file -- `syncCreateBroadcastRulesetOptions()`
    hardcoded `['baseball', 'softball']` as the only sports it re-scopes
    the Create Broadcast form's ruleset dropdown for. Basketball would
    have silently kept whatever ruleset options were left over from
    the previous sport selection. Added `'basketball'` to the array;
    confirmed live in a manual browser session that selecting Basketball
    correctly narrows the dropdown to the 3 basketball rulesets.
  - `static/csrn-hoops-controls.js` (new, mirrors
    `csrn-diamond-controls.js`'s conventions -- no build step, shares
    globals): starting five, shot, free throw, rebound, foul (with
    shooting-foul sub-fields), substitution, turnover/held ball,
    violation, timeout, ruling, manual set-value, undo/redo, confirm
    game end, and a box score modal. `correct_foul`/`void_event`/
    `correct_event` deliberately have no dedicated form -- the same
    scope cut baseball's own P5 made for `void_event`/`correct_event`
    ("undo/redo covers the 'runs a full game' bar; targeted correction
    is a power-user feature for later").
  - Gate passed: `tests/test_basketball_engine_p5_operator_ui.py` (new,
    15 tests, mirroring `test_baseball_engine_p5_operator_ui.py`'s own
    structure) -- sport dropdown, partial inclusion, every engine-backed
    deliverable present in the partial, `render()` branching before
    football-only sections, every UI action name cross-checked against
    `hoops_game_operations_service.ACTIONS` (catches a typo'd action
    name that would otherwise 404 silently in the browser), the
    `correct_foul`/`void_event`/`correct_event` scope cut asserted
    explicitly (not just absent by omission), and each form's payload
    shape cross-checked against its engine method's actual parameters
    (shot, foul, violation, ruling, set-value). Also fixed
    `test_baseball_engine_p5_operator_ui.py::test_sport_dropdown_offers_
    baseball_and_softball`, stale after this round's `ENGINE_READY` flip.
  - **A real manual browser smoke test was run** (not skipped, matching
    baseball's own explicit P5 precedent and Layout Builder P0's own
    "manual smoke test caught 2 real bugs" precedent) -- created a real
    school/roster/broadcast end to end, logged in, confirmed the
    Basketball tile shows enabled at login (Soccer still "SOON"),
    confirmed the Create Broadcast form's ruleset dropdown re-scopes
    correctly, loaded the broadcast, and confirmed the Basketball
    Control Panel renders in place of football's controls with a
    correct auto-initialized scoreboard (period/clock/timeouts). Drove
    starting five for both teams, a shot, several fouls (confirming
    bonus is correctly attributed to the *fouled-against* team, not the
    fouling team), a free throw, undo, redo, and the box score modal --
    each action's effect confirmed in both the raw dispatched state and
    the rendered UI.
    - Two real bugs caught and fixed during the smoke test, neither
      visible from static-source tests alone:
      1. The Create Broadcast form's own "Sport" field on the Roster
         Setup panel defaults to Football independent of the page's
         top-level sport filter -- a roster created while that filter
         showed "Basketball" was silently saved as a Football roster,
         and the two P5 tests can't catch this because they only assert
         static HTML/JS content, not a live create-then-list round trip.
         Not a code bug (working as designed), but exactly the kind of
         real-workflow trap only a live click-through surfaces -- noted
         here for whoever tests P6 against the live app.
      2. Confirmed (not a bug) that `home_school_id`/`visitor_school_id`
         only populate when a broadcast's teams are selected from the
         School Database dropdown, not typed as free-text "manual
         entry" -- a manual-entry broadcast has genuinely no roster to
         resolve, matching baseball's own diamond-controls convention
         exactly (`hoopsRosterPlayers()` mirrors `diamondRosterPlayers()`
         to the field name).
    - All local-only smoke-test artifacts (a manually-set test PIN in
      this worktree's gitignored `security.json`, the test broadcast and
      its schools/rosters, the smoke-test broadcast's incidental
      `pregame_presentation.json` entry, this worktree's `state.json`
      authority file) were reverted / cleaned up before this commit --
      none of it is part of this change.
  - Full suite: 2942 passed (2927 + 15 new), 2 known-environmental
    failures, zero regressions.

- **P6 — DONE (2026-09-13).** `rulesets/basketball/us-ms-mhsaa.json`
  `_source_notes` only -- no ruleset *values* changed, since the P0
  placeholders already happened to match what the owner decided to ship
  (confirmed by direct comparison against `basketball/us-nfhs.json`
  before touching anything: `shot_clock.enabled: false`,
  `fouls.bonus_rule` (5th-foul/two-shot/quarter-scope), and `timeouts`
  (3 full + 2 short, 1 carryover OT) were already byte-identical between
  the two documents).
  - **Two owner decisions closed out this phase, neither resolved by an
    actual MHSAA handbook lookup:**
    1. **No shot clock, ever** -- a permanent product decision, not
       conditioned on MHSAA's actual on-court rule: running one
       accurately live is operationally impractical for a broadcast
       crew, and CSRN doesn't officiate the game. `_source_notes.
       shot_clock.enabled` rewritten to say this plainly (`PERMANENT
       PRODUCT DECISION`), replacing the old "P0 placeholder, needs
       owner confirmation" language, so nobody revisits this later
       thinking it's still open. The shot-clock state fields and the
       overlay serializer's blank-when-off behavior (P3,
       `test_shot_clock_is_blank_not_stale_zero_when_the_profile_has_
       it_disabled`) are deliberately left in place, untouched, exactly
       as instructed -- confirmed still passing, not ripped out just
       because MHSAA will never turn it on.
    2. **Bonus rule and timeouts ship on the NFHS-generic default,
       not independently confirmed for MHSAA** -- the owner's call:
       chasing the exact current MHSAA handbook wording isn't worth it
       for a broadcast-only product that doesn't officiate. Both
       `_source_notes` entries rewritten from "needs owner confirmation
       against the current MHSAA handbook" to an explicit "using
       NFHS-generic default, not independently confirmed for MHSAA --
       revisit only if this ever turns out to matter for broadcast
       accuracy," per the owner's own wording.
  - `tests/test_basketball_engine_p0_rulesets.py`: module docstring and
    `test_basketball_us_ms_mhsaa_extends_nfhs_with_unconfirmed_
    placeholders` (renamed to `..._with_settled_p6_values`) updated to
    stop describing these three values as open/unconfirmed -- the
    assertions themselves were already correct (they check the
    resolved numeric/structural values and `_source_notes` key
    presence, never the note text), so only the framing needed fixing,
    not the test logic.
  - Section 11 (open questions) item 1 struck through with a resolution
    note; the P6 phase-table row (Sec.10) updated to describe what was
    actually decided instead of "pending owner confirmation against the
    handbook."
  - Full suite: 2942 passed, 2 known-environmental failures, zero
    regressions (no behavioral code changed -- ruleset values were
    already correct, only `_source_notes`/doc/test-comment text moved).

---

*P0 through P6 done, matching this phase's own original scope exactly
(MHSAA shot-clock/bonus-rule/timeouts settled, `_source_notes` no longer
describes them as pending). Next up, per the owner's own priority
stated alongside P6: a UX friction investigation of the P5 operator UI
(stat-entry speed -- taps/clicks per action, sensible defaults, on-floor-
only player lists) to inform a redesign, not yet built pending that
investigation's findings.*
