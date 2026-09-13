# Hoops overlay contract

Basketball engine P0 deliverable (`docs/BASKETBALL_ENGINE_SCOPING_PLAN.md`).
Reconciles the field-level shape the **rendering layer already ships and
consumes today** (Phase C's `productionBasketballState()` groundwork)
against what the **basketball engine** (P1 onward: `engine_router.py`,
`hoops_state_service.py`, `hoops_rules_service.py`, `hoops_period_service.py`)
must publish onto the live runtime-state payload. Mirrors
`docs/DIAMOND_OVERLAY_CONTRACT.md`'s role for baseball/softball — this is
the interface both sides code against.

**Authority note.** Same discipline as the diamond contract: this document
only fixes the *wire-format field names* the already-shipped renderer
hardcodes. The engine must produce this shape; P1+ does not get to
redesign these field names for its own convenience.

## 1. What the renderer already reads (frozen contract, P1+ must produce)

Source of truth: `productionBasketballState(source, gameSource)` in
`static/csrn-production-theme-runtime.js`, called from `mergeRuntimeState()`
for `sportFamily === "basketball"`. `source` is the raw runtime state
(`state.json`'s own flat shape, or whatever P4's routes layer publishes
there); `gameSource` is `source.game`/`source.game_state`/`source.gameState`
if present, checked as a fallback for each key.

| Wire field (either `snake_case` or `camelCase` accepted) | Type | Notes |
| --- | --- | --- |
| `shot_clock` / `shotClock` | string (already formatted, e.g. `"24"` or `""`) | Blank/absent when the active profile's `shot_clock.enabled` is `false` — the renderer does not itself know the profile, it just shows whatever string it's given. Do not publish a stale/zero value when the profile has the shot clock off; publish `""`. |
| `home_fouls` / `homeFouls` | string (already formatted, e.g. `"3"`) | Per-period (quarter/half) team foul count per the active profile's `fouls.team_foul_scope`. |
| `visitor_fouls` / `visitorFouls` | string | Same, visiting team. |
| `home_bonus` / `homeBonus` | string, one of `NONE` / `ONE_AND_ONE` / `DOUBLE` | **Fixed 3-value enum, pinned here** — no rendering-side mapping exists yet (checked directly: no theme currently maps these to a badge/label), so this engine's serializer is the FIRST and ONLY producer of this value; the 3 strings above are the contract. A theme that later adds a bonus badge maps these 3 strings, not something else. |
| `visitor_bonus` / `visitorBonus` | string, same 3-value enum | Same, visiting team. |
| `home_timeouts` / `homeTimeouts` | string (already formatted, e.g. `"2"`) | Remaining, not used. |
| `visitor_timeouts` / `visitorTimeouts` | string | Same, visiting team. |

Shared with football (already correct, no P1 action needed — read via the
same `mergeRuntimeState()` fields every sport uses):

| Wire field | Notes |
| --- | --- |
| `period` / `quarter` | `"1".."4"` for `period.format: "quarters"`; the engine's own `HOOPS_CANONICAL_FIELDS.period` supports `"H1"/"H2"` for halves-format profiles too, but the wire field itself is just whatever period label the engine resolves — same field name football already publishes, not a new one. |
| `clock` | Same field name/format football's own game clock already uses (counts down, `MM:SS` or seconds — matches whatever `clock_seconds`/`clock` convention football's own `mergeRuntimeState` branch already established; P1 must reuse it, not invent a second clock field). |
| `possession` | `"home"` / `"visitor"` — Phase C explicitly keeps `possession` meaningful for basketball (`hasPossession = family === "football" || family === "basketball"`). The engine's own `possession_arrow` (alternating-possession) is a *different*, engine-internal field with no wire-contract equivalent yet (see Sec.3, out of contract). |
| `home_score` / `visitor_score` | Reuses football's existing top-level score fields — no new basketball-specific score field. |

## 2. What the renderer does NOT yet read (explicitly out of contract)

Per the scoping doc's own Sec.7 gap list — these are real future rail-panel
fields, not required for the P3 scorebug serializer to ship:

- `home_in_foul_trouble[]` / `visitor_in_foul_trouble[]`
- Leading scorer + line (e.g. "12 PTS, 4 REB")
- Team `fg_pct` / `3p_pct`
- `run` tracker (e.g. "12-2 run")
- `last_basket_text`
- `possession_arrow` (alternating-possession indicator) — engine-internal
  today; add a wire field here if/when a theme wants to show it.

Do not invent wire names for these ahead of a rail-panel round actually
consuming them — add them to this document when that round starts, the
same discipline `DIAMOND_OVERLAY_CONTRACT.md` Sec.3 uses.

## 3. Sport-family dispatch (already correct, no P0 action needed)

`static/csrn-production-theme-runtime.js`'s `productionSportFamily()` +
per-theme `applyBasketballBoardOverrides` patchers already dispatch
basketball correctly across FNS / 8-Bit / Heritage / Collegiate. Phase C's
own work; nothing here changes it.

## 4. Effective profile stamp (P0, this round)

Same mechanism baseball P0 built, already fully generic
(`ruleset_service.resolve_id(..., sport=...)`,
`BroadcastLifecycleService._effective_profile_fields()`) — basketball needs
**zero code changes** to get `effective_profile_id`/`effective_profile_version`
stamped at broadcast load, only the new `ruleset_service._CATALOG` rows
(this round) resolving to a real document.

## 5. Traceability

| Renderer piece | File | Landed |
| --- | --- | --- |
| `productionBasketballState()`, basketball `mergeRuntimeState` branch | `static/csrn-production-theme-runtime.js` | Phase C |
| `applyBasketballBoardOverrides` (per-theme clock/period/shot-clock patchers) | `static/csrn-production-theme-runtime.js` | Phase C |
| `basketball/us-nfhs.json`, `basketball/us-nfhs-subvarsity.json`, `basketball/us-ms-mhsaa.json`, `_CATALOG` rows | `rulesets/`, `ruleset_service.py` | This round (P0) |
