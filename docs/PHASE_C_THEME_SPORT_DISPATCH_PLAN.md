# Phase C — per-sport dispatch for the production theme runtime

**Plan only. No theme code touched in this pass.** Audit of every shipped
visual theme for sport-specific visual elements, and a design for a real
per-sport-family dispatch mechanism to replace today's binary
`sport !== "football"` gate.

Read against production tip `64ed45a` (the Round 27 worktree). Where
Round 26 (`5ba5948`, unmerged) already touched a theme file, it is noted.

---

## 1. The headline finding — the gap is narrower than it looks

The five theme **engines already render full baseball / basketball /
softball layouts.** They were built multi-sport speculatively, ahead of a
non-football game engine:

| Engine (file) | Multi-sport render today |
| --- | --- |
| `csrn-broadcast-layout-engine.js` (Collegiate Tech + shared base) | `SPORT_CONTRACTS` for all 4; `sportState()` / `baseballState()` / `basketballState()`; `modernBaseballScore()`; `resolvePlacements(manifest, sport)`; baseball at-bat/pitcher roles (gate 74b). |
| `csrn-friday-night-stadium-engine.js` | `normalizeState(value, sport)`; `basketballTower` / `basketballControls`; `diamondControls` + `baseDiamond(game.bases)` + RHE; per-sport `CLASH_ART` / `CLASH_BACKDROPS`; `venueName` → ARENA/BALLPARK/STADIUM; `possessionBall(sport)`. |
| `csrn-eight-bit-gameday-engine.js` | Same shape: `footballTower` / `basketballTower` / `diamondTower` dispatch; `basketballControls` / `diamondControls`; per-sport keyed-athlete recolor. |
| `csrn-heritage-press-engine.js` | `footballDispatch` / `basketballDispatch` / `diamondDispatch`; per-sport 1920s pitcher/batter art; "GRIDIRON / COURTSIDE / DIAMOND DISPATCH" headers; sport-tagged wire commentary. |
| `csrn-neon-r2-engine.js` (Digital Neon) | Fully multi-sport: `renderPackage(root, id, sport, …)`; `footballState` / `basketballState` / `diamondState`; `bottomExtra` → `footballField` / `basketballCourt` / `diamondInningBoard`; per-sport clash-art layers; per-sport CSS-var artwork `/static/neon-r2/${sport}-*.png`. Plus two thin **driver files** (`csrn-neon-baseball-r43-driver.js`, `csrn-neon-softball-r42-driver.js`) that decorate the frozen engine post-render. |

**The football-only bottleneck lives entirely in one file:**
`static/csrn-production-theme-runtime.js` — the layer that (a) normalises
canonical game state into the runtime shape and (b) live-patches the
rendered DOM on every poll. It never feeds the engines anything but
football, and its per-theme DOM patcher bails for other sports.

### 1a. The deeper blocker (flag)

There is **no non-football canonical game state.**
`canonical_state_service.py`, `event_service.py`, `statistics_service.py`
and the Command Center operator UI are football-only. So even a perfect
theme dispatch has no `inning` / `balls` / `strikes` / `shotClock` /
`fouls` to bind — the engines would render their built-in **demo
defaults** ("5 TOP · 2-1 · 1 out"), not a live game.

**Phase C implementation is inert until a non-football game engine +
operator controls exist.** Phase C should still land the theme-layer
dispatch (it's real, contained work and unblocks the rest), but it cannot
be exercised end-to-end alone. This mirrors Round 27's `canadian_football`
situation: the context/plumbing can exist before the thing it drives.

---

## 2. Architecture as-is (3 layers)

```
canonical game state  ──►  csrn-production-theme-runtime.js  ──►  package engine (…-engine.js)
(football only)            • mergeRuntimeState()  = football fields    (renders any of 4 sports
                           • applyFootballBoardOverrides()  = football   from normalizeState(value, sport))
                             DOM patch, `sport!=="football" return`
                           • productionFieldState/DownDistance/…
```

Plus a **scorebug composer** (`csrn-broadcast-layout-engine.js` /
`csrn-scorebug-engine.js`) that is already fully multi-sport for the small
score strip in every theme skin (`test_gate7_sport_state_contracts.py`
locks this contract).

### The eight `theme_service.py` presets vs the "five shipped themes"

`_PRESETS` holds eight token skins, each with a `layouts.scorebug` value:
`classic_1980s` (classic), `early_cable` = **8-Bit Gameday** (pixel),
`modern_network` = **Modern Network** (modern, the default
`active_preset`), `minimal_radio` (minimal), `heritage_press_box` =
**Heritage Press** (press), `friday_night_stadium` = **Friday Night
Stadium** (stadium), `digital_neon` = **Digital Neon** (neon),
`collegiate_traditional` = **Collegiate Tech** (collegiate).

Only **five** have a full-screen production **package** in
`PACKAGE_ALIASES` (`csrn-production-theme-runtime.js`):
friday_night_stadium, eight_bit_gameday, heritage_press, digital_neon,
collegiate_traditional. "Modern Network" / Classic / Minimal run the
`legacy` path — scorebug + generic overlays only, no themed full-screen
engine.

---

## 3. Per-theme audit

For each: **agnostic** (safe as-is) · **football-specific** (needs a
dispatch point) · **baseball/basketball variant** (what the slot needs, or
whether it just hides).

### 3.1 Collegiate Tech (`collegiate_traditional`)

* **Agnostic:** team identity rail, score chips, logo chamber, sponsor
  lock-up, ticker copy, caption lane, the cabinet/frame chrome.
* **Football-specific:** the **field-position graphic** — yard-line strip,
  10-yd guide lines, hash marks, end zones, `--ball-x` / `--drive-x` /
  `--first-x`, direction arrow, "1ST DOWN" marker, ball-spot / drive-start
  / line-to-gain readouts, possession-logo-on-field. This is
  `collegiateField()` in the engine + the `applyFootballBoardOverrides`
  `collegiate_traditional` branch in the runtime (both re-pinned by
  Round 26 Phase B). Also DOWN / TO GO / QUARTER text binds.
* **Baseball variant of that slot:** a **diamond** — bases occupied,
  inning + half, outs, count, at-bat / on-deck. The engine already has
  `modernBaseballScore()` + at-bat/pitcher roles (gate 74b) but **no
  collegiate-styled diamond graphic** — this is the one genuinely new
  visual to build for this theme.
* **Basketball variant:** the field graphic **hides**; the slot shows a
  possession arrow + team-fouls / bonus / shot-clock strip. Small.
* **Softball:** identical to baseball.

### 3.2 Friday Night Stadium (`friday_night_stadium`)

* **Agnostic:** stadium frame, LED clock host, team towers' identity half,
  ticker LED, clash-art backdrop mechanism, sponsor + caption lanes.
* **Football-specific:** `footballControls()` (DOWN / TO GO / BALL ON /
  QUARTER LED cells), `possessionBall(football)` on the score, the
  `bl-fns-clash-football` art path. Runtime side:
  `applyFootballBoardOverrides` FNS branch pushes clock + QUARTER + DOWN +
  TO GO + BALL ON as stadium LED SVGs.
* **Baseball variant — already built in the engine:** `diamondControls()`
  (BOT/TOP INNING LED, `baseDiamond(game.bases)`, RHE via `rheMarkup`),
  `diamondTower()` roles (AT BAT / PITCHER), `bl-fns-clash-baseball` +
  `baseball-ballpark-background.png`. Needs: the **runtime** to supply
  `inning / inningHalf / balls / strikes / outs / bases / batterName /
  pitcherName` and a `applyBoardOverrides` diamond branch to keep them
  live.
* **Basketball variant — already built:** `basketballTower()`,
  `basketballControls()` (clock + period + fouls + bonus), 3-digit score
  LED, `basketball-court-background.png`. Needs runtime `shotClock /
  homeFouls / visitorFouls / bonus`.
* **Softball:** engine has a softball keyed-art carve-out; otherwise = baseball.

### 3.3 8-Bit Gameday (`eight_bit_gameday`)

* **Agnostic:** pixel window chrome, LED palette, ticker LED band, athlete
  sprite frame, sponsor + caption lanes.
* **Football-specific:** `footballControls`, `footballTower` possession
  pip, the runtime's 8-bit branch (CLOCK / QUARTER / DOWN / TO GO / BALL
  ON LED cells) + POSSESSION LED in `patchThemeScoresAndPossession`.
* **Baseball / basketball / softball — already built in the engine:**
  `footballTower` / `basketballTower` / `diamondTower` dispatch (lines
  299-301), `basketballControls`, `diamondControls` (`{half} INNING` LED).
  Same runtime need as FNS: supply the per-sport game fields and add
  diamond/basketball branches to the board patcher.
* **Note:** the 8-bit engine label cells are matched by
  `labeledCell(root, "DOWN")` etc. — a diamond/basketball board patcher
  keys off the *engine's* label text ("INNING", "COUNT", "FOULS"), so the
  patcher and the engine's cell labels must be designed together.

### 3.4 Heritage Press (`heritage_press`)

* **Agnostic:** newspaper masthead, column grid, wire-copy ticker, score
  summary rows, byline / dateline, sponsor + caption lanes, the
  newsprint-tone media frame.
* **Football-specific:** the **"GRIDIRON DISPATCH"** commentary generator
  (`footballDispatch`), football wire lines, `possessionName`, the
  `mountHeritageFootballClash` broadcast-clash artwork (runtime,
  `sport !== "football" return false` at line 2331), and the runtime's
  heritage branch (period / clock / down-distance text binds).
* **Baseball / basketball — already built in the engine:**
  `basketballDispatch` / `diamondDispatch`, "COURTSIDE / DIAMOND
  DISPATCH" headers, 1920s pitcher/batter art
  (`press-pitcher-1920s.png`, `press-softball-*`), sport-tagged wire
  lines with per-sport event vocab (`home_run`, `three_pointer`, …).
* **Baseball variant of the score/state block:** a boxscore-style
  line ("BOT 7 · 2 OUT · 3-2") set in the press typeface, plus RHE in the
  score-summary rows. Engine has the copy generator; the **live state
  block** is the new bit.
* **Basketball:** period + team-fouls line; clash art swaps to
  `basketball` path.
* **`mountHeritageFootballClash`** must become `mountHeritageClash` with a
  per-sport artwork/vocabulary switch, or explicitly no-op (fall back to
  the generic media frame) for sports without clash art commissioned.

### 3.5 Digital Neon (`digital_neon`, currently hidden)

* **Agnostic:** neon frame + bloom, team panels, ticker, score footer
  shell, lower assembly.
* **Fully multi-sport already** (see §1). `renderPackage(root, id, sport,
  …)` branches to `footballState` / `basketballState` / `diamondState`;
  `bottomExtra` → `footballField` / `basketballCourt` /
  `diamondInningBoard`; `scoreSide` shows FOULS/BONUS only for basketball;
  `teamPanelDetail` shows pitcher/batter for baseball/softball.
* **Football-specific bits that still hard-branch:** `footballField()`
  (yard strip + BALL ON), the R40 football clash-art layer stack, the
  possession badge.
* **Prior-art driver pattern:** `csrn-neon-baseball-r43-driver.js` /
  `csrn-neon-softball-r42-driver.js` — each `= (base) => { call
  base.renderPackage; if (my sport) prepend my decorative layers into
  `.n2-opening`; re-freeze `window.CSRNNeonR2Engine` }`. They add **art
  layers only**; the real per-sport logic (linescore, court, pitcher
  panel) is in the base engine.
* **Runtime side:** `digital_neon` is `playerSupported: false` and the
  runtime does not currently call a neon board patcher — Neon re-renders
  the whole package on signature change rather than live-patching cells.
  So Neon needs the **least** runtime work: just feed `mergeRuntimeState`
  the per-sport fields and let the full re-render pick them up.

### 3.6 Modern Network + Classic + Minimal (`legacy` path)

* No full-screen package. They render the **scorebug composer** (already
  multi-sport — `modernBaseballScore`, `baseballState`, `basketballState`)
  plus generic overlays. `test_gate74b_modern_sport_state_panel.py`
  already locks a "modern baseball" renderer and inning-half roles.
* **Football-specific:** nothing structural beyond the scorebug's own
  football path, which already coexists with the baseball/basketball paths.
* **Action for Phase C:** essentially none in the theme layer — these are
  the one set that already works per-sport at the scorebug level. They
  just need the upstream game state.

---

## 4. Does the Neon prior-art pattern generalise?

**Two patterns, and the answer is "one generalises, one is a
freeze-workaround."**

1. **Engine-internal `sport` branch** (`renderPackage(sport)` /
   `normalizeState(value, sport)` → per-sport sub-renderers). This is
   **already universal** — every one of the five engines does it. Nothing
   to generalise; it's the established shape.

2. **Thin per-sport driver file that decorates a frozen engine.** This is
   **Neon-specific and exists because Neon R2 was frozen**
   (`test_gate151_*`, a SHA/marker pin) before baseball/softball were
   added — so the sports went in as separate files to avoid re-pinning the
   frozen engine. FNS / 8-bit / Heritage were **not** frozen when their
   sports were added, so their sports are inline.

   → **It does not need to be applied to the other four now.** It **is**
   the right template for adding a *future* sport (e.g. volleyball) to any
   engine that is by then frozen: ship a `csrn-<theme>-<sport>-driver.js`
   that wraps the engine's render and re-exports the global, rather than
   editing the pinned file. Worth writing this up as a standing "how to
   add a sport to a frozen theme" note.

---

## 5. Proposed dispatch mechanism

All in `static/csrn-production-theme-runtime.js`. No engine files change
(they already accept the data) except where a genuinely new visual is
listed in §3 (collegiate diamond, heritage live-state block).

### 5.1 Runtime state — `mergeRuntimeState()`

Add a per-family game-field block after the football block, driven by
`base.sport`:

```
football   → down, distance, downDistance, field{…}, ballSpot, driveStart,
             firstDownSpot, fieldDirection            (as today)
basketball → shotClock, homeFouls, visitorFouls, homeBonus, visitorBonus,
             possession
baseball   → inning, inningHalf, balls, strikes, outs, bases[3],
softball      pitcherName, batterName, batterPosition, homeHits/Errors,
             visitorHits/Errors
```

Keep `base.game.period` fallback-to-`inning` as-is. Football fields stay
populated even for other sports (harmless; the engines ignore them) OR
gate them — **open question 6.1**.

### 5.2 Board patcher — replace `applyFootballBoardOverrides()`

`applyBoardOverrides(root, alias, runtime)` → dispatch on
`base_family(runtime.sport)`:

```
football   → applyFootballBoardOverrides   (rename, unchanged body)
basketball → applyBasketballBoardOverrides  (clock, period, fouls, bonus,
                                             shot clock, possession arrow)
baseball   → applyDiamondBoardOverrides     (inning+half, count, outs,
softball                                      bases, at-bat/pitcher, RHE)
```

Each sport-branch is small — it targets the *same per-theme cells* the
football branch does, keyed off the engine's label text
(`labeledCell(root,"INNING")` etc.). One function, four internal alias
branches × three sport branches, but most cells are shared.

Call sites (1518, 2701) call `applyBoardOverrides` unconditionally; the
`sport !== "football" return` guard is deleted.

### 5.3 Football-only feature gates

* `mountHeritageFootballClash` (≈line 2329-2331, two `sport !== "football"`
  guards in one function) → `mountHeritageClash` with a per-sport artwork
  map (`press-pitcher-1920s.png` / `press-softball-*` already exist), or an
  explicit no-op that leaves the generic media frame.
* Line ≈1945 football clash-art asset check → per-sport asset key
  (`baseball-ballpark-background.png` etc. already committed).
* Sweep for any remaining `String(runtime.sport …) !== "football"` in the
  file — as of `64ed45a` the only ones are `applyFootballBoardOverrides`
  (§5.2) and the two Heritage-clash guards above.

### 5.4 Scorebug composer

No change — already multi-sport. Confirm the `theme_service.py`
`layouts.scorebug` value + `csrn-scorebug-engine.js` variant renders the
right per-sport strip for each of the eight skins (`test_gate7` covers the
contract; a per-skin visual check is worth adding).

### 5.5 Frozen-gate impact

* Touching **only** `csrn-production-theme-runtime.js` + its CSS: those
  are pinned by `test_gate116` (`JS_SHA256`/`CSS_SHA256` + `… in BIBLE`)
  and the gate12/13/14 digests — **re-pin once**, exactly as Round 26
  Phase B did (documented procedure in `CSRN_PROJECT_BIBLE.md`).
* If a **new engine visual** is needed (collegiate diamond, heritage
  live-state block) that edits `csrn-broadcast-layout-engine.js/.css` or a
  `…-engine.js`, the relevant `test_gate12[6]` / `test_gate13[8]` /
  `test_gate14[2]` / `test_gate116` visual-freeze pins re-trigger. Prefer
  the **driver-file pattern (§4.2)** for anything added to an engine
  that's frozen, to keep the pinned file byte-stable.

---

## 6. Open questions (flag before implementation)

1. **Football fields on non-football state.** Keep `mergeRuntimeState`
   writing football `down/field/…` for all sports (simple, engines ignore
   them) or gate them out (clean, but more branching)? Recommend: keep,
   gate only `productionFieldState`'s expensive work.

2. **Collegiate diamond graphic.** Collegiate Tech is the one theme with
   no baseball state visual at all. Build a collegiate-styled diamond, or
   have Collegiate Tech fall back to the plain scorebug for baseball and
   be "a football/basketball theme"? Owner call — it's a design
   commission, not just wiring.

3. **Heritage live-state block.** The Heritage engine generates baseball
   *commentary* but has no live boxscore/inning block in the press
   typeface. New visual — commission or defer?

4. **Basketball possession vs football possession.** Both use
   `game.possession`. Basketball also wants shot-clock + team-fouls +
   bonus. `patchThemeScoresAndPossession` currently frames the 8-bit
   "POSSESSION" LED as HOME/VISITOR — fine for basketball, meaningless for
   baseball (should read count/outs instead). Confirm per-theme.

5. **Clash artwork quality.** The per-sport assets **exist and are
   committed** — `static/friday-night-stadium/clash/` has
   `{football,basketball,baseball,softball}-{athletes-keyed,*-background}.png`;
   `static/heritage/` has `press-{,softball-}{pitcher,batter}-1920s.png`;
   8-bit has `athletes/` + `environments/`. Open point is only whether
   they are finished art or first-pass placeholders — a visual review, not
   a build gap.

6. **Which sport families does Phase C target?** Round 27's model has
   `basketball / baseball / softball / soccer` as licensable families but
   only football engine-ready. The theme engines cover football /
   basketball / baseball / softball — **not soccer**. Soccer would be a
   from-scratch per-theme build. Recommend Phase C scope =
   {basketball, baseball, softball} (match the engines), soccer explicitly
   out.

7. **Upstream sequencing.** Phase C theme dispatch is inert without a
   non-football canonical state + operator controls + scoring engine (§1a).
   Land Phase C's runtime dispatch anyway (contained, unblocks), but the
   owner should decide whether it ships dark or waits for the game-engine
   round.

8. **"Modern Network" default.** It's the `active_preset` and has no
   package — a non-football broadcast on the default theme gets the
   scorebug-only `legacy` path. Acceptable, or should Modern Network get a
   full package as part of this? (Separate, larger piece of work.)

---

## 7. Suggested commit shape (for the implementation round, not now)

1. `mergeRuntimeState` — per-family game-field block + tests.
2. `applyBoardOverrides` dispatch — rename + basketball branch + tests
   (football byte-identical).
3. `applyBoardOverrides` — diamond (baseball/softball) branch + tests.
4. `mountHeritageClash` / clash-asset per-sport keys + line 2330 feature.
5. Re-pin `test_gate116` / gate12/13/14 + BIBLE (one commit, documented
   procedure).
6. Any commissioned new visual (collegiate diamond / heritage block) —
   its own commit, driver-file pattern if the target engine is frozen.
7. Per-skin scorebug visual check + `docs` update ("how to add a sport to
   a frozen theme").

Each commit: full suite green, football rendering byte-identical
(scorebug + all five themes), the two pre-existing
`test_state_mirror_throttle` env failures excepted.
