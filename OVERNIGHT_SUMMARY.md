# Overnight Session Summary — 2026-08-28 → 08-31

Round 12 branch: `round12-identity-profile-20260831`. Round 13 branch:
`round13-dehardcode-cleanup-20260831`. **Round 14 branch:
`round14-pywebview-scoping-20260831`** (off `round13-dehardcode-cleanup-20260831`
@ `d2498f8`, carries rounds 1-13).
Nothing deployed. Running CSRN process not touched. Review and merge is yours.

Full test suite (deterministic, `-p no:randomly`, run with
`.venv/Scripts/python.exe`) after **round 14**: **0 failed, 2341 passed**
(unchanged — Round 14 is investigate-only, no application code touched).
**0 real regressions across all fourteen rounds.**

---

## ROUND 14 — pywebview app-shell scoping (2026-08-31)

**Investigate-only. No production code, no packaging changes, no dependency
additions.** Deliverable is a written report:
[`docs/pywebview_shell_scoping.md`](docs/pywebview_shell_scoping.md).

`templates/index.html` and `broadcaster_print_service.py` **not touched**
(0 bytes changed — verified against the round-start capture, same as every
round since Round 11). Suite unchanged at 2341 passed.

| commit | task |
|---|---|
| `75b148b` | scoping report + summary section |

### What the report covers

- **Task A — launch & runtime survey.** Full double-click→running-app chain
  (`CSRN_GAME_DAY_LAUNCHER.ps1` 3-state DOWN/HEALTHY/HUNG triage → `cmd` →
  `RUN_CSRN_COMMAND_CENTER.bat` env-check + preflight + recovery-marker chain
  → `app.py` waitress:5050 + isolated media server:5051 + SIGINT clean-shutdown
  → Chrome tabs incl. the Round-12 Identity-Profile streaming-link override).
  Full runtime dependency inventory. Flagged: **`pronouncing`/`cmudict` are
  used by `roster_service.py` but missing from `requirements.txt`**; live
  captions are **GPU-only** (CUDA 12 + cuDNN 9, no CPU fallback in code); the
  `small.en` whisper model downloads from HuggingFace on first use; Playwright
  needs an out-of-band ~150 MB Chromium (roster print-sheet PDF + dragonfly);
  `ruleset_service` resolves `rulesets/` via `__file__` and the existing
  `.spec` does not bundle it; the `.spec` `datas` references a non-existent
  `Graphics/` dir.
- **Task B — integration shape.** pywebview owns ONE native window at
  `http://127.0.0.1:5050/?module=pregame`; Waitress still serves everything.
  Does NOT replace the OBS browser-source overlays (OBS hits 5050 directly)
  or LAN phone/iPad access (keep `host="0.0.0.0"`). Shell must own: health-gated
  window open, clean-shutdown on window-close (no signal is delivered — must
  call the recovery marker + state flush path itself), window chrome/sizing,
  and the "5051 fails → don't start" guard. Recommends the child-process model
  for the first cut.
- **Task C — packaging.** Keep PyInstaller onedir + Inno Setup (already
  scaffolded in `packaging/windows/`). Reserved: `product_paths` license /
  installation fields, `entitlement_service` dev-vs-unlicensed,
  `build_release_package.py` payload format, the per-user `.iss`. Undefined /
  gaps: first-run onboarding SCREEN (only the backend Identity Profile file +
  `/api/config` exist — biggest UX gap), `.spec` fixes, Playwright-Chromium
  strategy, whisper model + CUDA prerequisite handling, code-signing,
  external updater / update-check. **Confirmed:** `CSRN_INTERNAL_TOOLS`
  correctly resolves OFF in a frozen build (`sys.frozen` →
  `installed_mode` → `not installed_mode` = False) provided packaging doesn't
  set the env var and `run_core_foundation.py` is physically excluded.
- **Task D — risks / owner decisions.** Bundle size (~0.5–1 GB depending on
  model/Chromium bundling); unsigned-build SmartScreen/AV false-positives are
  a real risk (OV cert ≈ $200–500/yr, EV ≈ $300–700/yr); **no youth-tier /
  native-companion-app plans are documented in the repo** — assume no bearing
  unless the owner says otherwise; ctranslate2/onnxruntime are the known
  PyInstaller pain points.
- **Round 15 breakdown** — 8 tasks (15A–15H): add deps → `csrn_desktop.py`
  shell → frozen startup branch → first-run onboarding → `.spec` fixes →
  Chromium strategy → `.iss` updates → docs.

---

## ROUND 13 — finish the de-hardcoding pass (2026-08-31)

Continues Round 12: existing Caledonia install sees **zero behaviour/data
change** (proven by test at each step); everything identity-shaped now comes
from the Identity Profile; a fresh install is genuinely blank.

`templates/index.html` **not touched** (0 bytes `437815b..HEAD`).
`broadcaster_print_service.py` + `tests/test_broadcaster_print_service.py`
carry the owner's `ROWS_PER_COLUMN` roster WIP; Task C edited both, isolated
its changes hunk-by-hunk, and the WIP diff is verified **byte-identical** to
the round-start capture and still unstaged.

| commit | task | suite |
|---|---|---|
| `9ec3e87` | **A** — DEFAULT_STATE team/venue + csrn-logo fallback → Identity Profile | 2331 → 2333 |
| `0f33a72` | **B** — pregame Next Matchup genericized; drop the "Cavaliers" caption seed | 2333 → 2337 |
| `54fabca` | **C** — roster print order from `record_tracking`, not a "caledonia" name match | 2337 → 2340 |
| `a122043` | **D** — app.py vendor-path fragments → `product_paths.PRODUCT_VENDOR/NAME` | 2340 → 2341 |

### Task A — team/venue + logo fallback

`identity_service.py`: new `state_defaults` section (`home_team` / `venue` —
legacy Caledonia values for an existing install, `""` for a fresh one) plus a
`branding_logo(organization)` helper (configured logo path or `""`, never a
hard-coded `csrn-logo.png`). `app.py` `DEFAULT_STATE["home_team"]` / `["venue"]`
now read from it. The `csrn-logo.png` fallback is removed from
`diagnostics_service` (Logo-file check skipped when no logo configured),
`graphics_service` (personnel graphic with no school → injected org logo),
and `pregame_presentation._organization_branding`. Golden test: legacy seed ==
frozen historical copy; `app.DEFAULT_STATE` still "Caledonia" /
"Caledonia High School". Fresh test: blank, no "caledonia", no "csrn-logo".

### Task B — investigate + genericize

**Next Matchup** was *logic that could already derive from Identity Profile
data*: `_caledonia_school()` hard-coded a name lookup; the profile already
carries `broadcast_defaults.home_school_id`. Now `_primary_school()` resolves
by that id; `primary_team` / `_organization_branding` name/short_name
fallbacks → `""`. Zero change for Caledonia (all values are in its config).

**caption_worker**: `current_caption_prompt_terms()` in app.py already builds
the per-game vocabulary from live game state (both teams' names, mascots,
rosters, personnel); only a literal `"Cavaliers"` was seeded alongside the
generic football terms — dropped.

**Flagged, NOT changed** (more than a straightforward substitution):
- `templates/pregame_universal_overlay.html`: ~5 hard-coded "Caledonia Sports
  Radio Network" / "/CaledoniaSRN" branding fallbacks in the ribbon/social JS
  (live overlay, needs visual verification; the backend now feeds the real
  org name so these only surface on a blank fresh install).
- `caption_worker.py`: the `\bcaledoni\b` regex + `== "caledonia"` /
  `== "cavaliers"` branches are genuine team-tuned ASR misrecognition
  corrections, not derivable from Identity Profile data, inert on a
  non-Caledonia install. The `caption_initial_prompt` seed list + example
  sentence would need the primary-team name threaded through the caption
  subprocess boundary.

### Task C — roster print order

`broadcaster_print_service._render_document` decided roster page ORDER (CSRN's
own team first) via `"caledonia" in home_team/visitor_team`. It now keys off
`record_tracking.primary_side` — the same value already read two lines above
for the cover logo. **Provably zero output change**: all four reprintable
broadcasts in `broadcasts.json` carry `primary_side` and it matches the old
name test on every one; the one legacy `Caledonia`-as-visitor detail file
with no `record_tracking` is not in `broadcasts.json` so it is unreachable
via the print-sheet endpoint. Fresh install → plain home-first.

### Task D — vendor-path unification

`"PossumFrog" / "CSRN Production Suite"` was open-coded in three `app.py` path
builders + a banner; `product_paths.py` already exports `PRODUCT_VENDOR` /
`PRODUCT_NAME` with identical values. Pure literal substitution — verified
`CORE_BACKUP_ROOT` and the state-authority path still resolve to
`%LOCALAPPDATA%\PossumFrog\CSRN Production Suite\...` byte-for-byte. Left
deliberately: the non-LOCALAPPDATA `~/.possumfrog` fallback base (aligning it
to `product_paths` would relocate the file on non-Windows dev).

### Task E — MHSAA MS5A-001=caledonia (investigate only)

**Verdict: (a) — expected ruleset data with a legitimate safety fallback, NOT
a bug. No action taken.** The only code reference is `app.py:_five_a_
classification_rules()`, where `[("MS5A-001", "caledonia"), ("MS5A-002",
"new-hope")]` is assigned then **immediately overridden** by
`ruleset_service.resolve(...)["classification"]["reserved_ids"]` from
`rulesets/football/us-ms-mhsaa.json` (identical mapping). The `try/except`
keeps the literal only if the ruleset engine is unavailable — the exact
Round-7 consumer pattern (`PenaltyService`, `PeriodService`,
`CanonicalStateFoundation` all do this). Nothing else in live source
references those reserved IDs; the `MS5A-*` values in `Data/Schools`,
`Data/Logos`, `Data/Venues` are persisted reconciliation *output*, not a
bypass.

---

---

## ROUND 12 — Identity Profile + de-hardcoded launcher URLs + internal-surface flag (2026-08-31)

Preparing for an eventual packaged/commercial build (the pywebview shell is a
separate future round). **The existing Caledonia/CSRN install sees zero
behaviour or data change** -- proven by test. A new customer install starts
blank/template instead of inheriting Caledonia's identity.

`templates/index.html` **not touched** (0 bytes changed `7bba8d1..HEAD`);
`broadcaster_print_service.py` **not touched**.

| commit | task | suite |
|---|---|---|
| `4bd8c19` | **A** — external Identity Profile for organization + broadcast_defaults | 2317 → 2323 |
| `8ee9f74` | **B** — de-hardcode the launcher's Facebook/YouTube live URLs | 2323 → 2326 |
| `b228347` | **C** — runtime flag to exclude the internal-only surfaces | 2326 → 2331 |

### Task A — external Identity Profile

- `product_paths.py`: `ProductPaths.identity_file`
  (`runtime_root/identity_profile.json` installed, repo-colocated in dev --
  same pattern as `state_file` / `security_file`).
- `identity_service.py` (new): `load_identity_profile()` /
  `save_identity_profile()`. Seeds once on first run:
  * **existing install** (`state.json` OR `config.json` already present) →
    seeded with the exact former literals (`LEGACY_ORGANIZATION` /
    `LEGACY_BROADCAST_DEFAULTS` / `LEGACY_STREAMING`, moved verbatim out of
    `app.py` + the launcher);
  * **fresh install** → blank template (identity fields `""`, `sport` still
    `"Football"`, nothing Caledonia-identifying).
- `app.py`: evaluates `_EXISTING_INSTALL` BEFORE any repo auto-creates
  `config.json`, loads `IDENTITY_PROFILE`, and `DEFAULT_CONFIG` now reads
  `organization` / `broadcast_defaults` from it. `save_config()` mirrors those
  two sections back into `identity_profile.json`. The existing `/api/config`
  settings form already edits both -- **no new UI**. (A guided first-run
  wizard is flagged as future Layout-Builder-adjacent polish, not built.)
- **Zero-change proof:** the legacy seed equals a frozen golden copy of the
  historical literals; `DEFAULT_CONFIG` and `load_config()` still resolve
  exactly the Caledonia identity (on-disk `config.json` still wins the merge
  as before). A fresh-install test asserts a blank profile with no
  "caledonia" anywhere.
- **Flagged, NOT fixed** (Caledonia/CSRN still hard-coded outside the two
  blocks): `DEFAULT_STATE["home_team"]`/`["venue"]`; the `csrn-logo.png`
  fallback in diagnostics/graphics/pregame; `pregame_presentation`'s
  Caledonia-centric "Next Matchup"; `caption_worker` vocabulary;
  `broadcaster_print_service` `home_is_caledonia` branch; `app.py`
  PossumFrog/"CSRN Production Suite" vendor path fragments (Round 6 already
  flagged) and the MHSAA `MS5A-001=caledonia` reconcile.

### Task B — launcher live URLs

`CSRN_GAME_DAY_LAUNCHER.ps1` opened CSRN's own Facebook/YouTube producer
pages for every install. Those two URLs now live in the Identity Profile's
`streaming` block. `GET /api/identity/streaming-links` (public -- the launcher
has no operator session, same rationale as `/api/health`) serves them; the
`.ps1` keeps the two literals as a documented fallback that matches this
install's seed exactly, then overlays whatever the running app reports.
`phase5_architecture.PUBLIC_ENDPOINTS` whitelists the new endpoint.

### Task C — internal-only surface flag

`app.py:internal_tools_enabled()` resolves `CSRN_INTERNAL_TOOLS` -- explicit
`1`/`0` wins; **unset means ON in a dev/source checkout, OFF in an
installed/frozen build** (`product_paths.installed_mode`), so this dev
checkout is unaffected and a packaged build is safe by default.
`_install_internal_tools_gate()` adds an `app.before_request` hook that 404s
(`INTERNAL_TOOLS_DISABLED`) the catalogued paths -- `/api/diagnostics`,
`/api/runtime-diagnostics*`, `/api/game-day/rehearsals*`,
`/api/game-day/release-*`, `/api/deployment/{status,update/*,support-bundle}`
-- when the flag is off; the routes stay **registered** so the route
manifest / phase-5 audit don't move. `/api/config`, `/api/health`,
`/api/state`, `/api/licensing/*` and commissioning/recovery are NOT gated.
`run_core_foundation.py` got a header saying it must be excluded from a
bundle entirely (a whole entry point, not gateable). `docs/internal_only_
surfaces.json` gains a `runtime_enforcement` block. This round wires the flag
+ enforcement only; the packaging/bundling step is a separate future round.

---

## ROUND 11 — record inheritance UX + scrimmage filter + forward propagation (2026-08-31)

Follows the Caledonia-vs-Itawamba investigation from Round 10: the
primary-team pregame-record auto-carry works, but it only runs at broadcast
*create* time, counts non-record scrimmages, and never revisits a game
scheduled before the prior result is finalized — so operators re-type
records by hand.

**`templates/index.html` DID need editing this round** (Task A/C planning
form). The known "Start Broadcast (Go Live)" WIP (the `commandStartBroadcastButton`
button, `timeoutMs` 45000, `cmdStartButton`, `abort(),20000`) was isolated
out hunk-by-hunk and verified byte-identical and still unstaged at the end.
`broadcaster_print_service.py` + its test: 0 bytes changed.

| commit | task | suite |
|---|---|---|
| `eee9c6d` | **B** — inherit records from official, record-applied games only | 2308 → 2310 |
| `d452856` | **A** — pre-fill the planning form + inherited/override state | 2310 → 2315 |
| `51a54bb` | **C** — forward-propagate a finalized record to future games | 2315 → 2317 |

(Task B was done first — it is a prerequisite correctness fix that Task A's
read endpoint must reflect.)

### Task B — scrimmage filter

`_latest_primary_records()` accepted any `completed` broadcast. A scrimmage
(`record_policy: "non_record"`) is written a placeholder `*_postgame_record`
of 0-0-0 at completion, so the most-recently-finished scrimmage was inherited
over a real W/L. A candidate row now also needs `record_policy == "official"`
**and** `record_tracking_applied` truthy. Regression test: official-loss then
later-scrimmage still inherits the real 0-1.

### Task A — planning-form pre-fill + override state

- `broadcast_service.inherited_record(school_id, sport, season)` +
  `GET /api/broadcasts/inherited-record` (auth, static path ordered before
  `/api/broadcasts/<id>`): returns `{available, overall, region,
  source_broadcast_id, source_label}` — the same thing `create()` would carry.
- The form fetches it on school/contest change, pre-fills the primary side's
  Overall/Region boxes, and shows *"Primary team record pre-filled to 0-1 —
  inherited from Week 1 vs Itawamba. Edit any box to override."* Editing a box
  flips it to an explicit *"Overriding the inherited 0-1 …"* warning and sends
  `primary_record_source: "manual"` on save.
- **Override decision (Task C disambiguated it):** an explicit manual edit
  wins for that game and is remembered (`{side}_source = "manual"`);
  auto-managed values stay refreshable. `create()`/`update()` honour the
  `"manual"` hint; without it the existing automatic behaviour is unchanged.

### Task C — forward propagation

- `_propagate_record_forward()` runs after `update_linked_status` finalizes an
  official game: every other **`planned`** broadcast for the same primary
  school / sport / season whose primary-side source is `"automatic"` has its
  pregame (overall + region) record refreshed to the just-finalized value and
  a fresh detail write. `"manual"` rows are never touched; skipped if a later
  official game already owns the latest record.
- `create()` now marks the primary side `"automatic"` whenever the operator
  didn't override it — **even with nothing to inherit yet** — so a game
  created before the first official result is still caught by this later.
  (The "only scrimmages completed" create test flipped from asserting
  `"manual"` to `"automatic"` to match.)
- Test: schedule week-2 (auto) + week-3 (manual) before week-1 is played,
  finalize week-1, assert week-2 → 0-1 and week-3's manual 4-0 untouched;
  plus a scrimmage-completion-propagates-nothing test.

### Caledonia vs Itawamba — closed

The record *was* applied correctly (official, `record_tracking_applied`,
Caledonia 0-1). What the operator hit was: the Amory game's form showed a
blank 0-0 with no indication CSRN would fill it, so they typed the 0-1 by
hand — `create()`'s backend auto-carry then set the same 0-1 and tagged it
`"automatic"`. Round 11 makes that inheritance visible and adds the two
missing paths (scrimmage filter, forward propagation).

---

## ROUND 10 — dead-code sweep + game-statistics report fixes (2026-08-31)

`templates/index.html` **not touched** (0 bytes changed `190cf64..HEAD`).
`broadcaster_print_service.py` + its test (your roster WIP) **not touched**.
One commit per task.

| commit | task | suite |
|---|---|---|
| `1c606e4` | **A** — sweep the residual `layers-v10` dead-code cluster | 2298 passed (unchanged) |
| `4c6a76b` | **B** — fix the mojibake em-dash in the game-statistics report | 2298 → 2302 passed |
| `bd84de8` | **C** — "Player not entered" fallback for the report Play Register | 2302 → 2308 passed |

### Task A — dead-code sweep

Round 9 Task D removed 3 top-level symbols and flagged the rest. Confirmed
zero call sites, then deleted from `csrn-production-theme-runtime.js`
(−174 lines, brace balance re-verified): `tintFridayMask`,
`isFridayNeutralEquipmentPixel`, `compositeFridayMasks`,
`clipFridayDetailLayer`, `colorizeFridayUniform`, `fridayHexToRgb`,
`nearestFridayPaletteKey`, `const FRIDAY_PLAYER_PALETTE`, the post-`return`
`palette-v1` body of `paintFridayNightLayeredFootballClash`, and two stale
rollback-sentinel comments. Kept the pass-through shim + `fridayTeamColor` /
`loadFridayLayeredAsset` / the whole `paintFridayNightStandaloneFootballPlayers`
palette-v2 path (all live). `test_gate171_r2` / `test_gate172_r1` still green.
The Friday layered-clash dead-code swamp is now fully cleared.

### Task B — mojibake em-dash

**Root cause:** `rules_service.py`'s kickoff/punt/return phrasing built the
outcome suffix from a corrupted literal — `" <mojibake> touchback"` /
`" … fair catch"` / `" … blocked"` — where the mojibake is a UTF-8 em dash
(U+2014) once decoded as Windows-1252 and re-saved (`c3 a2 e2 82 ac e2 80 9d`).
Every other dash in the file, and `event_service.py`'s kickoff text, is a
correct em dash — hence the "inconsistent with nearby touchback lines".

- `rules_service.py`: the 3 mojibake sequences → real em dash. Whole-repo
  scan confirms this is the **only** live source file with the signature
  (every other hit is under `Data/` or a `*-backup`/`*rollback` dir — i.e.
  already-persisted play data downstream of this bug).
- `statistics_service.py`: `StatisticsService._repair_text()` maps the fixed
  cp1252←utf8 punctuation signatures back (em/en dash, curly quotes,
  apostrophe, ellipsis), applied to `play_register` `result`/`description`/
  `label` and `scoring_summary` `description`, so games **already recorded**
  with the bad bytes also export clean. Live-overlay text untouched.
- `tests/test_statistics_report_text_integrity.py` (4 tests): the report
  never emits `â€`; clean text is left alone.

### Task C — "Player not entered" in the Play Register

**Investigation:** a play's description is **one pre-rendered string**.
`rules_service` builds it (falling back to the opposing team's mascot name
when a run/pass has no player entered — the "Indians run for 0 yards" case),
stores it as `event["description"]` / `play["result"]`, and both the live
overlay and `StatisticsService.report()` reuse it verbatim. The report does
not regenerate it.

**Fix (report generator only):** in `report()`'s `normalized_plays` loop,
when a run play has no `player_number`/`player_name` (or a pass has no
`passer_number`/`passer_name`) — the exact condition under which
`rules_service` uses the mascot fallback — the Play Register row's
`result`/`description` become **"Player not entered"**. Every play is
deep-copied first, so `state["plays"]`/`state["events"]` (the overlay's
source) are not touched — the broadcast overlay still shows the mascot
fallback exactly as designed. Kickoffs/punts and any play with a number or
name keep their rendered text.

- `tests/test_statistics_report_play_register_fallback.py` (6 tests):
  run/pass with nothing entered → "Player not entered"; number-present,
  name-only, and kickoff cases untouched; explicit assertion that `report()`
  does not mutate the source play text.

### Side question — Caledonia vs Itawamba record (investigation only, no code change)

**The record DID apply correctly — you did flag it official.** On
`Data/Broadcasts/FB-2026-4A-W01-001.json` (Caledonia @ Itawamba, 2026-08-28,
final 10–42):

- `contest_type: "official"`, `record_policy: "official"`,
  `record_tracking_applied: true`, `record_tracking.primary_school_id: "caledonia"`.
- `visitor_postgame_record: {"wins": 0, "losses": 1, "ties": 0}` — **Caledonia is 0-1.**
- The two earlier Caledonia games (`FB-2026-4A-W00-001/002` vs Houston) are
  `contest_type: "scrimmage"` / `record_policy: "non_record"` and correctly
  did **not** count.
- The next scheduled Caledonia game (`FB-2026-OPEN-W00-001` vs Amory, 09-04,
  `planned`) already shows Caledonia's **pregame** record as `{"wins": 0,
  "losses": 1}` with `record_tracking.home_source: "automatic"` — the 0-1 was
  carried forward automatically.

CSRN has **no school-level aggregate standings record** — the W/L lives on
each broadcast as `*_pregame_record` / `*_postgame_record`. `schools.json`
has no `record` field. If you were looking at a scrimmage broadcast, or at
the W01 game's *pregame* record (correctly 0-0 going in), or expecting a
running total on the school record itself, that's why it looked like 0-0.
Nothing to fix.

---

## ROUND 9 — freeze re-pin, guard relax, factory fix, dead-code cleanup (2026-08-31)

`templates/index.html` **not touched** (verified: 0 bytes changed
`7c9fe14..HEAD`). `broadcaster_print_service.py` +
`tests/test_broadcaster_print_service.py` (your roster-page WIP) **not
touched**. One commit per task.

| commit | task | suite |
|---|---|---|
| `86c1013` | **A** — re-pin Neon + Friday-Night renderer freeze SHA-256 | 8→3 failed |
| `194b002` | **B** — relax gate166 to `{scorebug, captions}` | 3→2 failed |
| `07fccf5` | **C** — register `pregame_presentation` via the app factory | 2→0 failed |
| `05119a0` | **D** — delete the dead `layers-v10` Friday mask pipeline | 2301→2298 passed |

### Task A — freeze re-pin

Only the freeze *constants* and the BIBLE record moved — **no renderer code
changed** (verified). New hashes:

| file | new SHA-256 | why it moved |
|---|---|---|
| `csrn-broadcast-layout-engine.css` | `822755B7…A02C9` | Neon disabled as a selectable option (R6); shared engine extended for "Collegiate Tech" |
| `csrn-broadcast-layout-engine.js` | `CE29D87B…B2A2` | same |
| `csrn-friday-night-stadium-engine.js` | `E2B3872D…26CBB` | rebuilt for "Collegiate Tech" + `9064c67` |
| `csrn-friday-night-stadium-engine.css` | `766686DA…E689AF` | same |

8-Bit engine hashes + the 9 Friday-Night artwork hashes verified unchanged,
left as-is. Files touched: `test_gate116/126/12/13/14`, plus `test_gate142`
(its FROZEN dict pins the SHA-256 of `test_gate14` itself → re-pinned that
meta-hash), plus `CSRN_PROJECT_BIBLE.md` Gate 11.6 / 12.6 sections.

### Task B — gate166

`test_gate166_scorebug_remains_scorebug_only` →
`test_gate166_themed_scorebug_allows_only_scorebug_and_captions`. Assertions
now match `9064c67`'s contract:
`state.captionsActive ? ["scorebug","captions"] : ["scorebug"]` + a throw
guard rejecting anything else. Confirmed sole consumer — every other
reference to the old literals is under `Data/Backups` / `_gate184_*_rollback`.

### Task C — factory registration of `pregame_presentation`

`phase5_architecture.py` already expected it (`EXPECTED_BLUEPRINTS` +
`PUBLIC_ENDPOINTS` both list it); only the registration was missing.

- `pregame_presentation.py`: extracted
  `build_pregame_presentation_blueprint() -> Blueprint`. **Dropped the
  module-global `_INSTALLED` flag** — it permanently no-op'd every app after
  the first, which is exactly what stopped a 2nd factory instance from
  getting the blueprint. `install_pregame_presentation()` kept for legacy
  callers, now idempotent per-app.
- `app.py`: `APPLICATION_BLUEPRINTS.append(build_pregame_presentation_blueprint())`
  alongside every other blueprint; removed the post-`create_app()`
  `install_pregame_presentation(app)` call. No `@app.` decorators, no
  `app.register_blueprint(` in `app.py` — the phase-5 source audit stays clean.
- **Verified additive for both real launchers:** `app.py:app` and
  `run_core_foundation.application` both still carry `pregame_presentation`,
  with `.overlay` + `.status` public and the other 7 routes auth-required
  (matches `PUBLIC_ENDPOINTS` exactly).

### Task D — dead `layers-v10` pipeline

Confirmed zero call sites, then deleted from `csrn-production-theme-runtime.js`:
`FRIDAY_LAYERED_CLASH_ASSETS` (unread), `constrainFridayColorMask`,
`deriveFridayUniformReliefLayer` (−88 lines; brace balance re-verified).
Also removed `static/friday-night-stadium/clash/layers-v10/` (16 tracked
files + 2 `.bak` leftovers) and `tests/test_gate172_r3_friday_neutral_uniform_base.py`
(its 3 remaining tests only exercised this path).

**Kept** (still asserted by passing `test_gate171_r2` / `test_gate172_r1`):
the `paintFridayNightLayeredFootballClash` pass-through shim + its call site.

**Known residual dead code, flagged for a later dedicated pass** (all now
0–1 ref, unreachable, no runtime error): the post-`return` body of
`paintFridayNightLayeredFootballClash` and the helpers
`isFridayNeutralEquipmentPixel`, `compositeFridayMasks`,
`clipFridayDetailLayer`, `colorizeFridayUniform`, `tintFridayMask`,
`nearestFridayPaletteKey`, `FRIDAY_PLAYER_PALETTE`, `fridayHexToRgb`.

---

## ROUND 8 — pre-existing test-failure audit (2026-08-30)

`templates/index.html` **not touched**. `broadcaster_print_service.py` +
`tests/test_broadcaster_print_service.py` (your roster-page WIP) **not
touched**. No production code touched at all this round — only tests + docs.

Full analysis: **`docs/round8_test_failure_audit.md`** (51-row table).

| commit | step | |
|---|---|---|
| `7ab3041` | **1** — `docs/round8_test_failure_audit.md`: categorise all 51 | |
| `b5bf7ac` | **2a** — delete 34 obsolete overlay cache-bust / version-pin tests | |
| `4a46c63` | **2b** — delete 3 superseded-impl tests, fix 3 stale assertions | |
| `60a4f4b` | **2c** — delete 3 dead-subsystem tests (Friday `layers-v10` masks) | |
| (this)    | summary | |

### Interpreter note (matters for reproducing the baseline)

The machine's global `python` is 3.14 and lacks `pronouncing` (imported by
`roster_service.py`) → the suite fails to *collect* (58 errors). The real
baseline only reproduces under the project **`.venv`** (Python 3.13.14):
`51 failed, 2291 passed`. Every command this round used `.venv`.

### STEP 1 — categorisation (all 51)

| bucket | n | meaning | this round |
|---|--:|---|---|
| (a) obsolete | 40 | guards a version string / implementation / subsystem that has been intentionally superseded | **deleted** |
| (b) fixable test problem | 3 | one stale literal; the tested behaviour still holds | **assertion updated** |
| (c) flaky | 0 | — | — |
| (d) production looks wrong / needs your call | 8 | left failing, code untouched, documented | **STEP 4** |

**49 of the 51 trace to three already-shipped, intentional changes** whose
guard tests were never updated:
1. the themed-overlay runtime advanced from the "gate 16–17" era to
   `csrn-production-theme-runtime.js?v=19.6-r18-r8-passer-credit` — ~34 tests
   pinned the old `?v=` string;
2. the Friday-Night layered-clash compositor was rewritten (`v10` → `v11`)
   and its art regenerated;
3. `static/csrn-broadcast-layout-engine.*` and
   `csrn-friday-night-stadium-engine.js` (the frozen renderers) were rebuilt
   for the "Collegiate Tech" theme series and `9064c67`.

### STEP 2 — deletes + fixes

- **40 obsolete tests deleted** (3 whole files gone:
  `test_gate169_r4_r4_overlay_cache_patch_contract.py`,
  `test_gate169_r6_r3_cache_prefix_regression.py`,
  `test_gate172_r2_friday_color_clarity.py`). Every touched file keeps its
  passing siblings; the one lost pass (`test_old_r6_cache_is_not_authoritative`)
  was a tautology (`assert not 'v=18.5-r11'.endswith('v=16.9-r6')`).
- **3 assertions updated**, intent preserved:
  - `test_gate183 :: …authoritative_correction_boundary` — field slider now
    commits via `GameStateManager.mutate('/api/game-correction', …)` (same
    endpoint + payload as before; same wrapper the drive-direction control uses).
  - `test_gate4 :: …never_falls_back_to_csrn_branding` — preview fallback chain
    refactored to `p?.headshot ? rosterHeadshotDisplayUrl(p.headshot) :
    (teamLogo || silhouette)`; same order, still no `csrn-logo.png`.
  - `test_gate167_r9 :: …rearms_player_mode…` — re-arm key now composes from
    `graphic.player_id` / `graphic.roster_id` + timestamps, not the latest
    event's `id` (5 of 6 assertions were already valid).

### STEP 3 — flaky

**None.** Every one of the 51 is a deterministic assertion over file content,
a bundled PNG, or the blueprint set. Five consecutive full runs → identical
failure sets.

### STEP 4 — the 8 that remain (need your decision; code untouched)

**A. Renderer-freeze re-pin — 5 tests** (`test_gate116`, `test_gate126`,
`test_gate12`, `test_gate13`, `test_gate14`). `csrn-broadcast-layout-engine.css/.js`
(Gate 11.6 "Neon" freeze) and `csrn-friday-night-stadium-engine.js` (Gate 12.6)
were deliberately evolved after the freezes and never re-pinned; the BIBLE
freeze section is also stale. Per the tests' own change-control language this
is an **explicit owner "unfreeze → re-freeze at the new SHA" decision**. I did
not re-pin them or touch the renderers.

**B. `gate166` scorebug-only relaxation — 1 test**
(`test_gate166_scorebug_remains_scorebug_only`). Commit `9064c67` changed the
themed-scorebug activation to
`state.captionsActive ? ["scorebug","captions"] : ["scorebug"]` with a matching
`throw` guard permitting exactly `{scorebug, captions}`. Looks fully
intentional (captions belong with a themed scorebug). **Confirm and I'll relax
the guard test next round.**

**C. `pregame_presentation` not in the application factory — 2 tests**
(`test_phase_5_architecture`, `test_theme_architecture`).
`install_pregame_presentation()` runs on the module-level `app` only, not inside
`create_application()`. **Both real launchers (`app.py` → `serve(app)`,
`run_core_foundation.py` → `csrn_app.app`) are fine** — but factory-built app
instances lack the universal pregame-delay layer, and two architecture tests
already treat the factory as the expected owner. 2-part fix (register in the
factory + whitelist the two intentionally-public endpoints in
`audit_phase5_architecture`); low-risk but an init-order + audit-policy change,
so left for you.

### Follow-up this audit uncovered (not a test problem)

The Friday-Night **`layers-v10` mask-compositing pipeline is dead code**:
`paintFridayNightLayeredFootballClash()` in `csrn-production-theme-runtime.js`
`return`s `paintFridayNightStandaloneFootballPlayers(...)` on its first line
(live clash path uses pre-baked `players/palette-v2/*.png`), and
`constrainFridayColorMask` / `deriveFridayUniformReliefLayer` /
`FRIDAY_LAYERED_CLASH_ASSETS` have **zero call sites**. ~150 lines of dead
runtime code + the `static/friday-night-stadium/clash/layers-v10/` art dir.
Recommend a dedicated commit to delete both (plus the 3 remaining *passing*
`test_gate172_r3` siblings that only exercise it) — needs your OK, it edits
the live overlay runtime file.

---

## ROUND 7 — Facebook config + ruleset engine + internal-surface manifest (2026-08-30)

`templates/index.html` was **not touched this round** at all — verified. The
uncommitted "Start Broadcast" button and 45000/20000 values are untouched.

| commit | task | |
|---|---|---|
| `9a6d0d7` | **A** — drop the dead `local_oauth_test` Facebook sentinel | |
| `fa83a26` | **B1** — ruleset engine + `us-nfhs`/`us-ms-mhsaa` + golden test | |
| `fbc5462` | **B2** — consumer 1: `PenaltyService` catalog from the ruleset | |
| `e0058ae` | **B3** — consumer 2: `reconcile_5a_csrn_ids` reserved IDs from the ruleset | |
| `078b1e2` | **B4** — retire the dead `rules_edition` config stub | |
| `0ca8a39` | **B5** — consumer 3: kickoff / free-kick / try spots from the ruleset | |
| `1e22af7` | **B6** — consumer 4: quarter length + quarter set from the ruleset | |
| `d4cce8f` | **C** — `docs/internal_only_surfaces.json` manifest (documentation only) | |

### TASK A — Facebook config: DEFINITIVE

**`facebook_connection: "local_oauth_test"` is dead / always-dropped. Nothing
live could route through it.** Traced:
- The string `"local_oauth_test"` appeared **only** in the `DEFAULT_CONFIG`
  literal (`app.py`). Zero references in any live `.py`/`.js`/`.html`.
- **Nothing reads `config["social"]["publishing"]`.** The only consumer of
  the config `social` subtree is `social_service.py`, which reads
  `.get("website")` and nothing else.
- Any config save that touches `social` runs through
  `ConfigurationService.normalize_social_block()`, which returns only
  `{facebook, youtube, x, website, instagram}` — **the whole `publishing`
  block is dropped** on the first such save.
- Live Facebook behaviour is entirely in `facebook_connection.json`
  (`FacebookConnectionService`, `DEFAULT_API_VERSION = "v25.0"`) and
  `social_state.json` (`SocialService.DEFAULT_STATE["settings"]`).
  `facebook_connection_service.py` never imports `DEFAULT_CONFIG`.

**Cleanup:** `facebook_connection` `"local_oauth_test"` → `""` (matching
`facebook`/`youtube`/`x`/`website` `""` in the same block) + a comment that
the whole `publishing` sub-block is dead placeholder config. `facebook_api_
version: "v25.0"` left as-is — it's *also* the genuine live default on the
FB service, so redundant but not wrong. **Recommend removing the whole
`publishing` block wholesale in a future cleanup** — kept minimal this round.

### TASK B — ruleset engine

**`ruleset_service.py`** + `rulesets/football/us-nfhs.json` (base) +
`rulesets/football/us-ms-mhsaa.json` (`extends: football/us-nfhs`, adds only
MS classification + timezone/association; inherits NFHS rules unchanged).
`load_ruleset()` walks/deep-merges the `extends` chain (parent-then-child;
child dicts merge recursively, child scalars/lists/`null` replace;
cycle-guarded; cached). `resolve(country, region, association, sport)` maps a
jurisdiction via a small `_CATALOG`, **falling back to the generic base,
never a jurisdiction doc**. Helpers: `penalty_rules()`,
`field_spot_yardage()`, `available_rulesets()`. `CSRN_RULESETS_DIR` override.

**Golden test (`test_ruleset_golden.py`)** — proves the resolved
`us-ms-mhsaa` ruleset is byte-identical to the live constants **before any
consumer changed**: `penalty_rules(ruleset) == PenaltyService.RULES`
exactly; spots `own_40`/`own_20`/`opp_3` == the `canonical_state_service`
literals; period `720` == `PeriodService` reset == `DEFAULT_STATE
["clock_seconds"]`, quarters `["1".."4","OT"]`; classification `1A-7A` +
`{"MS5A-001":"caledonia","MS5A-002":"new-hope"}` + `{state}{class}-{seq:03d}`;
defaults `America/Chicago` + `MHSAA`.

**Consumers migrated — one per commit, each byte-identical, each with a
"fall back to the literal if the ruleset engine is unavailable" guard:**

| commit | consumer | now reads |
|---|---|---|
| `fbc5462` | `PenaltyService.enforce()` | `_penalty_rules()` → ruleset `penalties` (was `RULES` literal) |
| `e0058ae` | `app.reconcile_5a_csrn_ids()` | `_five_a_classification_rules()` → ruleset `classification.{reserved_ids,id_format}` (was Caledonia/"new hope" string special-cases + `f"MS5A-{n:03d}"`) |
| `0ca8a39` | `CanonicalStateFoundation.enter_kickoff/enter_free_kick/enter_pending_try` | `_field_yards()` → ruleset `field.*_spot` (was `40`/`20`/`3` inline) |
| `1e22af7` | `PeriodService._quarter()` + `_stop_clock(reset=True)` | `_period()` → ruleset `period.{quarters,quarter_length_seconds}` (was `{"1".."4","OT"}` + `720`) |

In every case the original literal is kept as a named `*_FALLBACK` and as
the golden anchor; the golden test guarantees they stay in sync.

**`rules_edition` retired (`078b1e2`).** It was `"NFHS"` in
`DEFAULT_CONFIG.application`, force-re-injected by
`CoreRepositoryRuntime.load_config()` every load, and **read by nothing**.
Removed from both. Chose *retire* over *repoint* — repointing would have
meant wiring a brand-new reader, out of scope. (`tools/apply_phase_2_4.py`
still sets it — a one-time phase-2.4 migrator, not run in normal operation;
left as historical.)

**Not migrated this round (flagged, your call):**
- `DEFAULT_CONFIG.broadcast_defaults.timezone = "America/Chicago"` and
  `dragonfly_service` / `dragonfly_sync_service`'s `association: str =
  "MHSAA"` default params. These are config-seed / broad-signature
  defaults, not game-logic constants; both values now *also* live in the
  ruleset `defaults` block and could be wired to seed from there in a
  later config-seeding pass.
- `DEFAULT_STATE["clock_seconds"] = 720` (the broadcast-create seed, separate
  from `PeriodService`) — same story, also in the ruleset now.
- **Bonus finding:** `app.py` has a second, divergent, `PENALTY_RULES` dict
  (line ~3254) — 19 entries with `replay_down` flags — that is **defined
  and referenced nowhere**. Dead. Not touched (out of scope); worth deleting.

**To add a real second jurisdiction later:** drop a JSON in `rulesets/`,
add one `_CATALOG` row in `ruleset_service.py`. No consumer changes.

### TASK C — internal-only surface manifest (documentation only)

`docs/internal_only_surfaces.json` — machine-readable, for the eventual
commercial packaging split. **Nothing removed, gated, or restricted.**
Lists:
- **`run_core_foundation.py`** — the debug Flask entry point
  (`application.run(debug=CSRN_DEBUG)`; real launcher is `app.py` →
  `waitress`).
- **`system_routes`** (partial): `/api/diagnostics`,
  `/api/runtime-diagnostics`, `/api/runtime-diagnostics/export` — the rest
  of that blueprint (`/api/state`, `/api/health`, …) stays customer.
- **`rehearsal_routes`** (whole blueprint): rehearsals + `release-readiness`
  + `release-freeze`/`-unfreeze` + `release-manifest`.
- **`deployment_routes`** (partial): `/api/deployment/{status,update/
  validate,update/prepare,support-bundle}`; the `/api/licensing/*` routes
  listed separately for your review.
- An `explicitly_not_listed` section (commissioning, recovery, upgrade,
  MHSAA/DragonFly) left for your decision.

Kept honest with `test_internal_only_surfaces_manifest.py` — every
referenced file exists and every listed route string is actually declared
in its module.

---

## ROUND 6 — settings audit, theme adjustments, rules-engine design (2026-08-30)

`templates/index.html`: verified before every commit that only my own hunk
was staged — the uncommitted "Start Broadcast (Go Live)" button and the
45000 / 20000 timeout values are **untouched** (`git diff HEAD --
templates/index.html` = exactly those 4 hunks).

| commit | task | |
|---|---|---|
| `e8fc176` | **B1** — hide "Neon" from the theme picker (reversibly) | code kept intact |
| `892bd60` | **B2** — rename customer-facing "Legacy" → "Basic Scorebug" | labels only |

Tasks **A** (settings inventory) and **C** (rules-engine design) are
investigation/proposal only — no code — and are the two big sections below.

### TASK B — theme adjustments (implemented)

**B1 — Neon hidden.** `production_template_service.py` gains
`DISABLED_PACKAGE_IDS = {"digital_neon"}` and
`SELECTABLE_PACKAGE_IDS = APPROVED - DISABLED`; `write_production_template_
state()` rejects a disabled id, `_normalize()` degrades a stale state file
that names one to `legacy`. The two client pickers
(`csrn-pregame-theme-selector.js` — the live one; `csrn-production-template-
menu.js` — the `/themes` page) get a matching `DISABLED` set that strips the
`<option>` and fails client-side validation. The static
`<option value="digital_neon">` is removed from `index.html`. **All Neon
engine code is untouched** (`csrn-neon-r1/r2-engine.js`, the `digital_neon`
entry in `csrn-broadcast-layout-engine.js`, `theme_service.py`'s
"Digital Neon" preset). **To re-enable:** delete `"digital_neon"` from
`DISABLED_PACKAGE_IDS` (production_template_service.py) **and** from
`DISABLED` (csrn-pregame-theme-selector.js) — two commented one-liners.

*Not touched, flag for you:* `theme_service.py`'s **`GraphicsThemeService`**
is a **separate** CSS-preset system (`/themes` catalog: Modern Network,
Minimal Radio, Classic 1980s, Heritage Press, …). It has its own
"Digital Neon" **colour preset** — unrelated to the Neon overlay renderer.
I left it alone. Tell me if you also want that preset hidden.

**B2 — "Legacy" → "Basic Scorebug".** Label/copy only, in all three picker
surfaces (`csrn-pregame-theme-selector.js` `LABELS.legacy`, the `/themes`
menu label + 3 fallback-copy strings, the `index.html` `<option>` text).
**Internal `"legacy"` id is unchanged** everywhere — `DEFAULT_PACKAGE_ID`,
`currentAlias`, the render-failure fallback, CSS classes, `#eventTicker`.
The asset-placement option "Flexible / Legacy" is a different concept and
was left alone.

---

## TASK A — settings / options inventory (for your review; nothing changed)

**Rec column** = my first-pass read of customer-visible vs
CSRN-internal-only. **This is a recommendation, not a decision — nothing is
hidden.**

### A.1 — Environment variables (all read in project source)

| Var | What it does | Where | First-pass rec |
|---|---|---|---|
| `CSRN_STATE_AUTHORITY_FILE` | Overrides the local state-authority path | `app.py:_local_state_authority_path` | Internal / advanced install |
| `CSRN_GAME_DAY_LOCAL_STATE` | Force on/off the local-authority + Drive-mirror split | `app.py:_drive_backed_game_day_state` | Internal / advanced install |
| `CSRN_CORE_BACKUP_ROOT` | Overrides where rolling snapshots + quarantine live (round 5) | `app.py:_core_backup_root` | Internal / advanced install |
| `CSRN_STATE_MIRROR_INTERVAL_SECONDS` | Drive-mirror coalesce interval (round 5, default 90) | `app.py` | Internal / advanced install |
| `CSRN_STATE_MIRROR_MAX_MUTATIONS` | Drive-mirror coalesce mutation cap (round 5, default 8) | `app.py` | Internal / advanced install |
| `CSRN_PRODUCTION_TEMPLATE_STATE_PATH` | Overrides the production-template state file (used by tests/sims) | `production_template_service.py` | Internal / test only |
| `CSRN_INSTALLED` / `CSRN_RUNTIME_ROOT` / `CSRN_DATA_ROOT` | Dev-vs-installed data-location resolution | `product_paths.py` | Internal (installer/packaging) |
| `CSRN_HOST` / `CSRN_PORT` / `CSRN_DEBUG` | Host/port/Flask-debug for the **alternate** launcher `run_core_foundation.py` | `run_core_foundation.py` | `CSRN_DEBUG` = **dev only**; host/port arguably customer |
| `CSRN_CUDA_DLL_PATHS` | Extra CUDA DLL search paths for the caption GPU worker | `caption_worker.py` | Customer (their GPU box) but niche |
| `CSRN_FACEBOOK_SECURE_PAGE_TOKEN` / `CSRN_FACEBOOK_PAGE_ACCESS_TOKEN` | Env refs for FB publishing credentials | `DEFAULT_CONFIG.social`, `facebook_connection_service` | Customer (their own FB creds) |
| `LOCALAPPDATA`, `ProgramFiles`, `USERPROFILE`, `PATH` | OS paths | various | n/a (OS) |
| launcher-only: `CSRN_COMMAND_CENTER`, `CSRN_ENVIRONMENT`, `CSRN_EXIT`, `CSRN_GAME_DAY_LAUNCHER` | Referenced only in `.bat`/`.ps1` launch scripts | launchers | Internal (packaging) |

*Note:* `run_core_foundation.py` is a **second entry point** with
`application.run(debug=CSRN_DEBUG)`. The real game-day launcher runs
`app.py` → `waitress.serve` (no debug). Worth deciding whether
`run_core_foundation.py` ships to customers at all.

### A.2 — Configuration Manager (`Settings` module, `DEFAULT_CONFIG`, `/api/config`)

All operator-editable in the in-app **Configuration Manager** unless noted.

| Setting | What | Code | First-pass rec |
|---|---|---|---|
| Organization: name, short_name, logo, primary/secondary/accent colour | Branding on overlays & pregame | `DEFAULT_CONFIG.organization`, `cfgOrg*` inputs | **Customer** |
| Default broadcast: venue, sport, timezone, home_school_id, visual_mode | Seeds new broadcasts | `DEFAULT_CONFIG.broadcast_defaults` | **Customer** |
| `broadcast_defaults.theme` = `"CSRN Dark"` | Legacy/unused theme string; `cfgTheme` input is **readonly** | `DEFAULT_CONFIG` | Internal / vestigial — recommend hide or wire up |
| Folders: graphics/assets/obs/archive/exports/backups | Path names | `DEFAULT_CONFIG.folders`, `cfg*` inputs | Customer (advanced) — mostly cosmetic now |
| OBS: websocket_enabled, controlled_commands, host, port, password, scene collection, profile, required scene, browser source, program-visual scene, graphic/camera source names | OBS integration wiring | `DEFAULT_CONFIG.obs`, `cfgObs*` | **Customer** (their OBS) |
| Weather: use_home_venue_address, alert_radius_miles, refresh_seconds, stale_after_seconds, user_agent | Weather widget behaviour | `DEFAULT_CONFIG.weather` (only `cfgRadius` is in the UI) | **Customer**; `user_agent` string is internal |
| Licensing: provider, enforcement_mode (`installed_only`), activation_endpoint | Licensing plumbing | `DEFAULT_CONFIG.licensing`, `entitlement_service` | **Internal / CSRN business** |
| `graphics_theme`: active_preset (`modern_network`), school_color_adaptation, season_lock | `GraphicsThemeService` CSS presets | `DEFAULT_CONFIG.graphics_theme`, `/themes` | Customer-facing feature, but see Task B note |
| Social: facebook/youtube/x/website + publishing block (preview_first, auto_create_drafts, allow_auto_publish, x_mode, x_oauth, x_api, facebook_api_version `v25.0`, facebook_connection `local_oauth_test`) | Social posting | `DEFAULT_CONFIG.social` | **Customer** for handles/toggles; `facebook_connection: "local_oauth_test"` and `facebook_api_version` look **internal/dev** |
| Application: version, build, **rules_edition `"NFHS"`**, automatic_backup, auto_save, operator_timeout_hours (12), upgrade_manager_enabled, last_migration_status | App behaviour | `DEFAULT_CONFIG.application`, `cfgAutoBackup/AutoSave/SessionHours` | `automatic_backup`/`auto_save`/`operator_timeout_hours` = **customer**; `version`/`build`/`last_migration_status` = read-only display; **`rules_edition` is a dead stub** (see Task C); `upgrade_manager_enabled` = internal |

### A.3 — `DEFAULT_STATE` fields an operator changes during a broadcast

These are game controls, not "settings" per se, but they are operator-set:
scores, quarter, down, distance, clock, possession, ball_spot,
`ticker_visible` / `ticker_speed` (very_slow…fast) / `ticker_pause`,
`ball_spot_visible`, `scorebug_visible`, `visual_mode` (graphic/camera),
`game_data_authority` (broadcaster ↔ statistician), `contest_type`
(official/…), `record_policy`, `region_game`, `production_type`,
`special_designations`, coin-toss, crew names, records, classifications.
**All customer.** (`classification` / `home_region` / `csrn_id`-style
fields carry MS-specific assumptions — see Task C.)

### A.4 — Caption settings (`caption_service.DEFAULT_PROFILE`, Caption Setup UI)

`caption_model` (small.en / medium.en / turbo / large-v3), `channel_mode`
(speaker_labeled / …), `speech_threshold` (0.00075), `audio_device` + host
API + channel count, per-channel speaker labels & enable flags,
live/preview toggles. **All customer** (their audio hardware & captions).

### A.5 — Theme / production-template selection

Production template picker (`legacy`→"Basic Scorebug", friday_night_stadium,
eight_bit_gameday, heritage_press, ~~digital_neon~~ now hidden,
collegiate_traditional). Server-authoritative via `/api/production-template`.
**Customer.**

### A.6 — Internal / development-and-evaluation tooling reachable in the app

These are **PIN-gated operator routes** but are clearly built for CSRN's own
release process, not for running a broadcast. **Strong first-pass rec:
gate behind an internal/dev flag or remove from customer builds.**

| Surface | Route(s) | What it is |
|---|---|---|
| **Diagnostics module** ("Football Release Readiness", "Technical Diagnostics", "Live Runtime Diagnostics", incident-bundle export) | `/api/diagnostics`, `runtime_diagnostics_service` | Release-readiness scoring + incident bundle export — CSRN release QA |
| **Rehearsals** | `/api/game-day/rehearsals*`, `/api/game-day/release-readiness`, `release-freeze`/`unfreeze`, `release-manifest` | Pre-release drill tracking & release freeze — CSRN release process |
| **Commissioning** | `/api/game-day/commissioning*`, `/commissioning/report` | New-install commissioning checklist + report — arguably customer onboarding, but report language is internal |
| **Deployment / Licensing** | `/api/deployment/*`, `/api/licensing/*`, `support-bundle`, `update/validate`, `update/prepare` | Update packaging, licence install/remove, support bundle — CSRN ops |
| **Recovery** | `/api/game-day/recovery/*` (snapshots, restore, rollback-plan, known-good, unclean-shutdown) | Disaster recovery tooling — **customer-relevant** but advanced |
| **Upgrade module** | `upgradeModule` in index.html, `upgrade_manager.py` / `upgrade_service.py` | In-app updater — customer-relevant if updates ship that way |
| **MHSAA import routes** | `/api/imports/mhsaa/5A*`, `mhsaa_division_routes` (`/api/associations`, division analyze/import) | Mississippi-specific school-data import — **CSRN/MS only** (see Task C) |
| **DragonFly roster/school sync** | `dragonfly_service`, `dragonfly_sync_service` (`association="MHSAA"` default) | External roster source integration, MHSAA-defaulted |
| Repo root `CSRN_GATE*_*.md` / `*_AUDIT*.txt` / `_gate*_rollback_*` dirs | not served | Dev artefacts on disk only — **not reachable from the running app** (checked: no "gate"/"audit" strings in operator UI) |

The one clearly-labelled "for iterating on this codebase" item **visible in
the operator UI** was the old `digital_neon` option text
"Neon — Deferred / Unvalidated" — removed in B1.

---

## TASK C — rules-engine investigation + design proposal (proposal only)

### C.1 — Honest inventory: what jurisdiction/sport-driven logic actually exists

**None.** Every rule value in CSRN today is a hardcoded constant assuming
**NFHS 11-man football** with **Mississippi MHSAA** identifiers. There is no
ruleset abstraction, no per-jurisdiction data, no sport parameter in the
game-logic layer. Specifics:

| Rule area | Where | Current state |
|---|---|---|
| **School ID / classification scheme** | `app.py:reconcile_5a_csrn_ids()` (the one you named) | Hardcodes `MS5A-001` = Caledonia, `MS5A-002` = New Hope, then alphabetical `MS5A-003+`; filters `state=="MS" and classification=="5A"`. Wired in as `SCHOOL_REPOSITORY`'s `collection_normalizer`, so it runs on **every school-list load**. |
| Classification names | `mhsaa_division_routes.py:SUPPORTED_CLASSES = ("1A".."7A")`; `/api/associations` hardcodes MHSAA + MAIS, `state:"MS"`, `sports:["Football"]` | MHSAA class names baked in |
| **Penalty yardage** | `penalty_service.py:PENALTY_CATALOG` (class attr) | ~30 fixed entries (5/10/15, loss-of-down, auto-first-down flags). NFHS-flavoured. **No jurisdiction key, no NFHS/NCAA/CFL/8-man variance.** `enforce()` takes a `yards` override arg but nothing selects a ruleset. |
| **Kickoff spot** | `canonical_state_service.py:enter_kickoff()` → `_team_own_yard_spot(state, kicking, 40)` | Own **40** hardcoded (NFHS post-2019; NCAA kicks from the 35). |
| **Free kick after safety** | `canonical_state_service.py:enter_free_kick()` → own **20** | Hardcoded. |
| **Try (PAT) spot** | `canonical_state_service.py:enter_pending_try()` → opponent **3** | Hardcoded (NFHS; NFL/NCAA differ). |
| **Quarter length** | `period_service.py` → `clock_seconds = 720` (12:00) | Hardcoded (NFHS; NCAA 15:00). |
| **Period structure** | `period_service.py:_quarter()` → `{"1","2","3","4","OT"}` | 4 quarters + single OT hardcoded; no halves-only, no running-clock/mercy rules, OT format not modelled. |
| **`rules_edition` config field** | `DEFAULT_CONFIG.application.rules_edition = "NFHS"`; **force-pinned** to `"NFHS"` in `core_repository_runtime.py:80` and `tools/apply_phase_2_4.py:35` | **Read by nothing.** Dead stub — the only existing "hook" for rules variance, and it drives zero logic. |
| Timezone default | `DEFAULT_CONFIG.broadcast_defaults.timezone = "America/Chicago"` | Mississippi default |
| Association default | `dragonfly_service` / `dragonfly_sync_service` — `association: str = "MHSAA"` in 8 signatures | MHSAA-defaulted |
| Sport in **game logic** | `rules_service`, `period_service`, `penalty_service`, `canonical_state_service`, `statistics_service`, `event_service`, `game_operations_service` | **Zero non-football branching** — grepped, confirmed. Sport only branches in the **overlay/theme JS** (scorebug layout: innings vs quarters), which is presentation, not rules. |

**Explicitly flagged (the "no yards-to-go" lesson):** I did **not** find a
partial or half-built ruleset system anywhere. `rules_service.py` +
`penalty_service.py` are the "rules engine", but they are procedural
football code with literal constants — not data-driven, not parameterised
by jurisdiction or sport. If you were told a ruleset layer exists, it does
not.

### C.2 — Proposed design: a `Ruleset` keyed by (jurisdiction, sport)

**Shape.** A ruleset is a plain data document (JSON), not code:

```
rulesets/
  football/
    us-ms-mhsaa.json        # CSRN's current behaviour, expressed as data
    us-ncaa.json
    us-nfhs.json            # generic NFHS (ms-mhsaa "extends" this)
    ca-cfl.json
  basketball/
    us-nfhs.json
  _schema.json
```

```jsonc
// rulesets/football/us-ms-mhsaa.json
{
  "id": "football/us-ms-mhsaa",
  "extends": "football/us-nfhs",
  "label": "Mississippi HS Football (MHSAA)",
  "jurisdiction": { "country": "US", "region": "MS", "association": "MHSAA" },
  "sport": "football",
  "period": { "count": 4, "length_seconds": 720, "overtime": "nfhs_10yard" },
  "kickoff": { "spot": "own_40", "touchback_spot": "own_20", "free_kick_spot": "own_20" },
  "try": { "spot": "opp_3" },
  "penalties": {
    "Defensive/Pass Interference": { "yards": 15, "automatic_first_down": true }
    // only deltas from the parent ruleset; everything else inherited
  },
  "classification": {
    "scheme": "letter_grade",           // 1A..7A
    "id_format": "MS{class}-{seq:03d}",  // MS5A-001
    "reserved_ids": { "MS5A-001": "caledonia", "MS5A-002": "new-hope" }
  }
}
```

**Where it lives.**
- `ruleset_service.py` — loads + merge-resolves `extends` chains, validates
  against `_schema.json`, exposes `get_ruleset(jurisdiction, sport) -> dict`.
- Files ship in `rulesets/` (read-only, packaged). A customer never edits
  JSON; they pick from a list.
- The resolved ruleset is attached to broadcast state once at
  broadcast-create time (`state["ruleset_id"]` + a resolved copy cached),
  so a mid-game rules change is deliberate, not incidental.

**How the game logic consumes it.** Replace the literal constants with
lookups, e.g.:
- `penalty_service.enforce(...)` takes `ruleset` (or reads
  `state["ruleset"]`); `PENALTY_CATALOG` becomes `ruleset["penalties"]`
  merged over a shipped default.
- `canonical_state_service.enter_kickoff()` reads
  `ruleset["kickoff"]["spot"]` (a symbolic spot like `own_40` resolved by
  the existing `_team_own_yard_spot` helper).
- `period_service` reads `ruleset["period"]["length_seconds"]` /
  `["count"]`.
- `reconcile_5a_csrn_ids()` → generalised
  `reconcile_classification_ids(schools, ruleset["classification"])`; the
  Caledonia/New Hope reservation becomes `reserved_ids` **data** in the
  MS-MHSAA ruleset, not a special-cased function.

**How the customer selects.** Pregame / Configuration Manager gets a
**Location** control (country → region/state → association) and the existing
**Sport** control. `(location, sport)` maps to a `ruleset_id`. Default for a
fresh install could be `football/us-nfhs` (generic) rather than the
MS-specific one. CSRN's own setup just picks "United States → Mississippi →
MHSAA / Football", which resolves to `football/us-ms-mhsaa` — **one entry
in the catalogue, no special-cased code.**

**Migration path (incremental, low-risk).**
1. Add `ruleset_service.py` + the schema + `football/us-nfhs.json` +
   `football/us-ms-mhsaa.json` that **exactly reproduces today's constants**.
   Add a golden test: resolved MS-MHSAA ruleset == current hardcoded values.
2. Point **one** consumer at it at a time (start with `period_service`
   quarter length — smallest blast radius), keeping the constant as the
   fallback when no ruleset is attached. Full suite green at each step.
3. Only after all consumers read the ruleset: add the Location UI and a
   second real ruleset (e.g. `us-ncaa`) to prove variance works.
4. `rules_edition` config field: either delete it or repurpose it as the
   `ruleset_id` selector.

**Open questions for you (design decisions, not mine to make):**
- Ruleset granularity: is "MHSAA" enough, or do you need per-classification
  overrides (e.g. 8-man vs 11-man within a state)?
- OT formats vary a lot (NFHS 10-yard, NCAA, GHSAA, etc.) — model as a
  named strategy (`"overtime": "nfhs_10yard"`) resolved in code, or fully
  data-drive it?
- Do customers ever need to author/override a ruleset, or is "pick from
  CSRN's catalogue" sufficient for v1?
- Non-football: basketball/baseball game logic doesn't exist yet at all —
  is (location, sport) the right key now, or is sport a bigger lift that
  should gate this?

---

---

## ROUND 5 — sponsor re-fire guard + Tier 2 storage (2026-08-30)

Branch `overnight-fixes-20260830`. Per-commit full-suite runs, failure-set
`diff`ed against the 51 baseline each time — **NONE moved.**
`templates/index.html`: verified before every commit that only my own hunk
was staged — the uncommitted "Start Broadcast (Go Live)" button and the
45000 / 20000 timeout WIP are **completely untouched** (`git diff HEAD --
templates/index.html` is exactly those 4 hunks and nothing else).

| commit | task | files |
|---|---|---|
| `ba744d4` | **A** — block rapid sponsor re-fire | `templates/index.html`, `tests/test_sponsor_trigger_feedback.py` |
| `e2baadf` | **B1** — core backups off the synced path | `app.py`, `tools/migrate_core_backups.py`, `tests/test_core_backup_relocation.py` |
| `b2d5182` | **B2** — coalesce the Drive mirror | `core_repositories.py`, `app.py`, `tests/test_core_repositories.py`, `tests/test_state_mirror_throttle.py` |
| `acbbfcc` | **B3** — break authority↔mirror hardlink | `app.py`, `tests/test_authority_mirror_hardlink_break.py` |
| `eac9c18` | **B4** — end-to-end layout scenarios | `tests/test_tier2_layout_scenarios.py` |

### TASK A — sponsor video trigger delay

**Most of Task A was already done in Round 4** (base branch): the 5-15 s was
traced to (1) a `sponsorAdvertisementDuration()` `<video>` metadata probe
running *on the Run click* — moved to selection time in `cb9f338` — and
(2) the overlay fetching + decoding the commercial cold every trigger,
because `mountCentralBoardMedia()` rebuilt the `<video>` each time — fixed
with a warm-preload cache in `8234893`. The instant "SUBMITTING · …" ack and
"Sponsor video triggered — starting…" panel line are also Round 4. "Sponsor
live" = the existing `#sadOnAirBadge` / `#spsOnAirBadge` "ON AIR" set from
state in `render()`.

**What this round adds (`ba744d4`):** nothing stopped the operator
re-clicking Run during the delay and firing the command twice. A shared
`sponsorTriggerBusy` flag + `setSponsorTriggerButtons()` — both
`runSponsorAdvertisement()` and `showSponsorSpotlight()` (they write the same
`sponsor_spotlight` state) bail early if a trigger is running, set the flag
and disable both Run buttons *before the first `await`*, and clear/re-enable
in `finally`. The two buttons got ids (`sadRunButton` / `spsShowButton`);
they sit outside the poll-driven `render()` button sweeps so the `finally`
is authoritative.

Answers to the numbered questions: (1) yes — no preload before Round 4, now
warm-cached; (2) overlay poll is 500 ms, not a factor; (3) the command
round-trip is **fully separate** from the Tier 1 state-write/lock path — the
delay is client-side asset loading only (server `update_sponsor_spotlight`
is pure dict work); (4) the duration probe on the click, now moved.

### TASK B — Tier 2: storage off the Drive sync path

**Layout before:** authority `state.json` at
`%LOCALAPPDATA%\PossumFrog\CSRN Production Suite\GameDay\` (local, good);
mirror at `<project>\state.json` (Drive-synced); `Data\Backups\Core`
(~205 MB, snapshot on every save) inside the Drive-synced project.

**B1 — `e2baadf` — core backups to a local root.** `app._core_backup_root()`
→ `%LOCALAPPDATA%\PossumFrog\CSRN Production Suite\Backups` by default
(override `CSRN_CORE_BACKUP_ROOT`); `CORE_BACKUP_DIR` / `CORE_QUARANTINE_DIR`
/ `CORE_PERSISTENCE` hang off it, so **new** snapshots leave the synced tree
immediately. Historical relocation is **not** automatic on the live save
path — `tools/migrate_core_backups.py` (dry-run default, `--apply` to move)
does per-file `shutil.move` (a file leaves the old spot only once fully
written to the new one; existing targets never overwritten), same pattern as
`tools/sweep_state_tmp.py`. `legacy_core_backup_notice()` prints a one-line
startup pointer while the old snapshots remain.

**B2 — `b2d5182` — coalesce the Drive mirror.** The authority write still
happens every mutation. The mirror background writer now holds the latest
pending snapshot and flushes it when **either** threshold trips:
`CSRN_STATE_MIRROR_INTERVAL_SECONDS` (**default 90 s**) since the last mirror
write, **or** `CSRN_STATE_MIRROR_MAX_MUTATIONS` (**default 8**) queued.
The recovery push *and the operator's first real mutation* still mirror
immediately (so it's never stuck on stale defaults at kickoff), then
throttling begins. `flush()` forces a write; it's registered with `atexit`
**and** called in the SIGINT/SIGTERM handler, so a clean exit pushes the
final plays. A force-kill loses only *mirror freshness* — the local
authority is the source of truth and recovery prefers it.

**B3 — `acbbfcc` — break a confirmed authority↔mirror hardlink at startup.**
`break_authority_mirror_hardlink()`: if the two paths resolve to the same
device+inode it rewrites the authority in place (temp + `fsync` +
`os.replace`) so they diverge — the same thing every save does, done eagerly.
Only a confirmed authority↔mirror pairing is touched; an authority whose
extra link is Drive's transient `.tmp.driveupload\<id>` is left for the
warning. Called from the serve path (drive-backed only) just before
`authority_state_hardlink_warning()`, which is **unchanged** and — per a new
test — returns `None` again once the break has run on a linked pair, and
**still fires** for a non-mirror extra link. **Goal 4 satisfied.**

**B4 — `eac9c18` — goal 5 verified by tests + walk-through:**
- *Fresh install* (no authority, no mirror, empty backup root): `_recover_
  authority()` sees both `None` → writes defaults to the authority + queues
  the mirror; `load()` returns defaults; first mutation persists to the
  authority and reaches the mirror immediately. No crash.
- *Existing hardlinked layout* (authority == mirror, mid-game rev 20):
  `break_authority_mirror_hardlink()` diverges the inodes (`st_nlink` → 1),
  then `LocalMirroredStateRepository` comes up and `load()` returns the
  **existing** game (rev 20, score 21 — not defaults); a later write lands
  in the now-independent authority and still mirrors promptly; the paths
  stay separate inodes. No data drop.
- *Existing layout, mirror newer than local*: recovery pulls the newer
  revision into the authority (unchanged behaviour, re-asserted under the
  throttle).

### JUDGMENT CALLS — please confirm

1. **Mirror throttle default: 90 s / 8 mutations.** A crash between mirror
   writes loses at most that much *mirror staleness* — never authority data
   (local authority is authoritative, recovery prefers it). Tighten/loosen
   via `CSRN_STATE_MIRROR_INTERVAL_SECONDS` / `CSRN_STATE_MIRROR_MAX_MUTATIONS`.
2. **Historical backup relocation is manual, not automatic.** `app.py` only
   changes where *new* snapshots go and prints a pointer;
   `tools/migrate_core_backups.py --apply` moves the ~205 MB when you run
   it. I chose manual to keep a 205 MB cross-volume move off the live
   startup path. If you'd rather it self-migrate on first run, say so.
3. **New backup root: `%LOCALAPPDATA%\PossumFrog\CSRN Production Suite\
   Backups`.** Sibling of the existing `GameDay\` state-authority dir.
   Override with `CSRN_CORE_BACKUP_ROOT` if you want it elsewhere (e.g. a
   second physical disk).
4. The hardlink break **rewrites the authority file** on startup when it
   detects the bad layout. It's `os.replace` of a byte-identical copy
   (same thing the first save would do) and fully guarded, but it *is* a
   write to the live authority at startup — flagging it explicitly.

---

## ROUND 4 — sponsor video trigger delay (2026-08-29)

Reproducible 5-15 s between clicking Run and a sponsor commercial appearing.
Traced, not guessed:

| hop | what | cost | fix |
|---|---|---|---|
| A | `sponsorAdvertisementDuration(asset)` — a hidden `<video>` metadata load with a 6 s timeout — ran **on the Run click** | 2-6 s on first trigger per page load (or a hard fail on timeout) | `cb9f338` — moved to selection time |
| B | `POST /api/graphics/sponsor-spotlight` | server does dict work only, ~50 ms | not the cause |
| C | overlay poll picks up the new `sponsor_spotlight` | `refresh()` runs every 500 ms | not the cause |
| **D** | **overlay fetches + decodes the video from scratch** — `mountCentralBoardMedia()` did `document.createElement("video") + src + play()` every trigger, and `host.replaceChildren()` destroyed the prior element so even re-runs were cold | **5-15 s** | `8234893` — warm-video preload cache |

### `cb9f338` — instant operator ack + probe off the trigger path (control page)

- `renderSponsorAdvertisementPreview()` (fires on sponsor/video select) now
  kicks off `sponsorAdvertisementDuration(asset)` so the cache is warm before
  Run is clicked; `runSponsorAdvertisement()` still probes inline as a
  cold-cache fallback.
- `runSponsorAdvertisement()` and `showSponsorSpotlight()` call
  `commandClientStatus('SUBMITTING · sponsor advertisement' / '… spotlight',
  'warning', 0)` **synchronously before any `await`** — same status surface
  the `LiveCommandClient` uses — plus a panel line "Sponsor video triggered —
  starting…". COMMITTED / failure states report on the same surface.
  `showSponsorSpotlight()` also gained a `try/catch` (was a silent throw).
- Staged as isolated hunks; the uncommitted `45000/20000` timeout WIP in
  `templates/index.html` is untouched.

### `8234893` — overlay preloads sponsor commercials (theme runtime)

- `sponsorVideoWarmCache: Map<url, detached <video preload="auto">>`, bounded
  to 6. Every poll warms `runtime.sponsor_spotlight.media_url` when it's a
  video. `graphics_service` keeps `media_url` in state after a **hide**, so
  between commercials the next one is already buffering.
- The sponsor board reuses the warm element
  (`takeWarmSponsorVideo(url) || document.createElement("video")`), resets
  `currentTime`, then `play()` — near-instant when buffered.
- **Effect:** the 2nd+ trigger of any sponsor video in a session (the common
  case) starts within ~1 s. **The first-ever trigger of a URL is still cold.**

### Still open — first-trigger cold load

Eliminating the very first trigger needs an **arm-on-select** signal: when the
operator picks a sponsor video, write `media_url`/`media_type` into
`sponsor_spotlight` at `visible:false` so the overlay preloads it during the
(seconds-to-minutes) gap before Run. That touches `graphics_service`
(new `action:"arm"` that sets media without `activate_primary`/`visible`),
both overlays, and the control page — a live-broadcast protocol change I did
not want to make unattended. ~1-2 hrs with tests; flagged for your call.

### Manual verification

1. Deploy, restart, hard-refresh the `/overlay` OBS source.
2. Run a sponsor ad. First run: still a few seconds (cold) — but the control
   page now says "Sponsor video triggered — starting…" **instantly**.
3. Stop, wait ~2-3 s (one poll warms it), Run the **same** sponsor again →
   appears within ~1 s.
4. Confirm a normal commercial still plays start-to-finish with audio, and
   the logo fallback still shows on a bad media URL.

---

## ROUND 3 — legacy bottom ticker + theme ticker speed (both done) (2026-08-29)

### 1. Legacy `#eventTicker` flashing back per-play — FIXED (`510ac9d`)

**What it is:** `templates/overlay.html` carries two tickers — the legacy
`#eventTicker` (bottom edge, driven by the inline `refresh()` in that file)
and the production theme's own ticker (top, rendered by
`csrn-production-theme-runtime.js`). The legacy one is hidden *only* by a CSS
rule gated on `html.csrn-production-theme-ticker-active`.

**Root cause (confirmed in source):** the runtime added that class only when
its ticker had something to scroll *on that tick*. `activateThemeTicker()`
returns `false` on a quiet play ("no new transient story and no persistent
scoring story: leave the ticker dark"), and the two call sites did
`classList.toggle(TICKER_ACTIVE_CLASS, <that boolean>)` — so on any routine
play the class came **off** and the legacy `#eventTicker` reappeared at the
bottom, then vanished again on the next scoring play. Two more sites inside
`mountScroller` removed the class when the theme scroller ran out of stories.
That is the per-play flash. The "too fast" look is the legacy track's
`animate()` restarting from offset 0 every play (signature change) so it
never settles.

**Fix:** 4 one-line changes, all one direction — an active production package
**owns** the ticker slot regardless of content (same as `SCORE_ACTIVE_CLASS`,
which was already handled this way). `patchThemeTicker()` and the full-render
path now `classList.add(TICKER_ACTIVE_CLASS)`; the `mountScroller` teardown
branches no longer remove it; `deactivate()` (theme → legacy fallback)
is now the **only** remover, so legacy-theme mode still shows `#eventTicker`.

**Also found:** `static/csrn-production-theme-adapter.js` (still
`<script>`-loaded in overlay.html, `?v=16.2-r1`) is **dead code** — its
`apply()` / `setLegacyVisible()` are never called by anything. Not touched;
flag for a future cleanup.

**Manual verify:** deploy, restart, hard-refresh `/overlay`; with a
production theme active run several plays incl. routine ones between scores —
the bottom edge must stay clear the whole time. Then switch the theme
selector to "Legacy / None" and confirm `#eventTicker` returns (unchanged
path).

### 2. Current theme's ticker is too slow — DONE, Option A / "fast" (`2e825df`)

You chose **Option A** with the **Fast** preset. `app.py`
`DEFAULT_STATE["ticker_speed"]`: `"slow"` (36 px/s) → **`"fast"` (189 px/s)**.
No scroll-math change. New broadcasts start on Fast; the Scroll Speed
control still offers all four presets.

**A game already in progress keeps its saved value** — flip the Scroll Speed
control to Fast to change it live. And the `Math.max(18, distance/speed)`
floor is untouched: a lone scoring line still takes ~18 s to cross (+4 s
pauses) on any preset; Fast only pulls clear of the floor once several
stories are queued (string wider than ~3,400 px). Lowering that floor was
Options B/C/D and was not taken.

<details><summary>Original analysis (options B/C/D, if you revisit)</summary>

`csrn-production-theme-runtime.js` → `tickerSpeed()`:
```js
({very_slow:24, slow:36, normal:84, fast:189})[runtime.ticker_speed] || 36   // px/sec
```
Live state has `ticker_speed:"slow"` → **36 px/s** (also the `app.py` default).
Scroll time per loop is `Math.max(18, distance / 36) + 2s pauses × 2`. The
**`Math.max(18, …)` floor** means any line under ~650 px still takes 18 s to
cross (+4 s pause) — most single scoring lines hit that floor. So both the
low px/s *and* the 18 s floor make it crawl.

Pick one (I'll implement + test whichever you choose):

| | Change | ~loop time, 900 px line | Notes |
|---|---|---|---|
| **A** | none — just set the Scroll Speed dropdown to **Normal** | ~22 s (floor still bites) | zero risk, instant, try it first |
| **B** | floor `18 → 10` only, keep presets | ~29 s | conservative |
| **C** | `slow: 36 → 55` **and** floor `18 → 10` | ~20 s | my lean — fixes the two real causes, only touches "slow" |
| **D** | presets `{very_slow:30, slow:52, normal:80, fast:150}` + floor `18 → 10` | ~21 s at "slow" | if you want all four presets retuned |

Don't want to copy the legacy ticker's feel — the legacy map is
`{very_slow:24, slow:36, normal:84, fast:189}` with the same 18 s floor, i.e.
identical. Option C/D deliberately diverge.

</details>

---

## ROUND 2 — your 4 decisions + the halftime correction (2026-08-29)

| Commit | Item | Notes |
|---|---|---|
| `6339675` | **1. Field position** | There is **no yards-to-go NUMBER** on the statistician page. What existed: the ball-spot label ("ITAWAMBA 30", correct) and a **RED ZONE flag in the Game Context box computed from the wrong reference** (`/VISITOR (1-20)$/ ‖ /HOME (1-20)$/` — near *either* goal line, ignoring drive direction — and mostly dead since ball_spot is stored `LEFT N`/`RIGHT N`). Built it per spec: `CanonicalStateFoundation.yards_to_goal()` (toward the end zone the offense drives to; correct across the halftime end-swap) + `field_state()` exposes `yards_to_goal`/`red_zone`; the Game Context box now shows "· N to goal" and derives RED ZONE / GOAL TO GO from it. 10 new tests incl. your exact Caledonia-30 example (30 vs 70) and the Q2-vs-Q3 flip. |
| `6e29854` | **2. Halftime sponsor area** + **the correction** | See below. |
| — | **3. nlink check** | Left warn-only as implemented (`6077eaa`). No change. |
| — | **4. tmp sweep `--apply`** | Ran it. **Deleted 29 orphaned `.state.json.*.tmp` files, 54.6 MB.** Nothing to commit (gitignored). The tool's 60-min age floor correctly left the running app's live temp file alone. |

### The halftime "PREGAME" bug — real root cause (correction accepted)

`0bc9486`'s verdict was wrong. It correctly rewired the `#stateBadge` pill,
the hero eyebrow, and the count label to the `halftime` phase — but there is
a **second on-screen "PREGAME"** it never touched: a hard-coded
`<strong class="brand-pregame">PREGAME</strong>` in the top-left brand
lockup. No JS ever changed it, so it stayed on screen through halftime and
delay. That is the literal "PREGAME" you saw after the restarts.

Every "pregame" that can render in `pregame_universal_overlay.html`:
1. **brand-lockup label** — hard-coded → **fixed** (now `id="brandStateLabel"`,
   set from the same `stateWord` as the pill → reads "HALFTIME" at halftime).
2. **empty-state** "Pregame information is loading." → **fixed** (halftime-aware).
3. **footer fallback** "CSRN Pregame" → **fixed** (halftime-aware).
4. **`<title>`** (browser tab only) → changed to "CSRN Broadcast State Overlay".
5. `storylinesCard()`'s "Pregame Storylines" `<h1>` — **already safe**, the
   halftime branch never includes that card.

Checked the other overlay too: `templates/overlay.html` and
`static/csrn-production-theme-runtime.js` render **no "PREGAME"** anywhere
(only `*_pregame_record` field names). So `/pregame-overlay` was the only
source that could show it.

**Why the test missed it:** `test_halftime_overlay.py` only asserted the
string `halftime?'HALFTIME':'PREGAME'` was *present in the file* — it never
checked the rendered halftime output is "pregame"-free.

**New test** `tests/test_halftime_overlay_no_pregame.py`: asserts each leak
point is fixed, re-derives the halftime card set from the template source and
asserts it excludes the pregame-only cards, and simulates `renderStatic()`'s
label logic for `phase='halftime'` asserting no output string contains
"pregame". (No JS runtime in this env — `node`/`dukpy`/`bs4` all absent —
so this is the strongest automated check possible here; the manual step
below is the real proof.)

### Sponsor area

There is **no automatic on-air sponsor rotation system** to hook into — both
existing on-air sponsor mechanisms (Sponsor Advertisement, Sponsor Spotlight)
are operator-triggered single shots, and `social_service`'s `sponsor_rules.
rotation` is for social-post attribution in a different state store. So I
used the **sponsor roster itself** (`SponsorService.list_payload()`, the same
list those two controls pick from), filtered to active sponsors that have a
logo, rendered as cards in the overlay's **existing** `cards[]`/`tick()`
rotation — no new list, pull, or rotation engine. On the real app this
resolves to 3 active sponsors right now. **If you meant a different source,
say so and it's a one-line change in `_halftime_sponsors()`.**

### MANUAL LIVE VERIFICATION for the halftime overlay (do this — tests aren't enough)

1. Merge, **restart CSRN**, and **hard-refresh the `/pregame-overlay` OBS
   browser source** (its right-click menu → "Refresh cache of current page").
2. Statistician page → Period Administration → **Start Halftime**.
3. On `/pregame-overlay` confirm: brand lockup top-left reads **"CSRN
   HALFTIME"** (not "CSRN PREGAME"); pill "HALFTIME"; eyebrow "Halftime";
   the big number is the score; label "Score at the Half".
4. Watch one full rotation: weather → any Q1/Q2 spotlight cards → one card
   per active sponsor. Nothing says "Pregame Storylines".
5. **End Halftime** → overlay hides. Then restart once more and repeat, to
   confirm it holds across restarts (the thing that failed last time).

Note: tonight's game recorded 6 spotlight events but all in Q3/Q4, so the
first-half spotlight rotation will be empty for *this* broadcast's data —
the data path itself is sound (those 6 events do carry
`after.player_graphic`). A real first-half TD/sack will populate it.

---

## TL;DR — read this first

1. **Most of tonight's list was already fixed on this branch on 2026-08-25/26**
   (halftime overlay, sacks spotlight, scoring-leader box, headshot resize,
   post-broadcast reporting, the QB-credit stopgap). Those commits (`3be429b`,
   `0bc9486`, `1325f2f`, `f3d7a4e`, `d6dc983`, `6b4c87d`, `b489c33`, `eba349a`,
   …) are **direct ancestors of the two commits you made 2026-08-28 afternoon**,
   so the fixed code was on disk during last night's Caledonia @ Itawamba game.
2. It did **not take effect live**. The most likely reason is that **the CSRN
   server process and/or the OBS browser sources were never restarted/refreshed**
   to load the new code after 08-25. This matches your reluctance to restart
   mid-cycle. I could not confirm this without touching the running system,
   which you told me not to do.
3. **I did not re-implement any of the already-fixed items.** Re-doing work that
   already exists on the branch is exactly how this repo accumulated its
   `_gate184_rNN_rollback_*` history. Instead I verified each existing fix is
   present and correct (details per-item below).
4. **What I actually built** is the genuinely-new, backend-only, fully-tested
   work that was *not* in the 08-25 pass: `/api/health`, launcher hardening,
   a temp-file janitor, and a startup hard-link warning. 5 commits.
5. **Your call needed on:** field-position bug (couldn't locate it — see below),
   finalizing last night's game so its recap/social generate, the halftime
   overlay's sponsor area (the one real gap), and whether the nlink check
   should hard-fault.

---

## Commits made this session (one fix = one commit)

| # | Commit | What | Tests |
|---|--------|------|-------|
| 1 | `ca28a6d` | **state_service: stop history snapshots embedding growing per-game arrays** (Tier 1 from the audit, carried over from earlier last night — it was uncommitted in your working tree). `push_history()` snapshot now also excludes `events/plays/redo_stack/correction_log/graphics_queue`; `public()` strips `history` from `/api/state`. | Full suite 51/51 identical; focused undo/redo/state set 121 passed. +21/−1 lines, 1 file. |
| 2 | `3663023` | **`/api/health` endpoint** — public, dependency-free liveness probe. No lock, never calls `load_state()`, so it answers 200 even when the write path is jammed. Registered in `phase5_architecture.PUBLIC_ENDPOINTS`. | New tests in `test_system_routes_blueprint.py` (registered, public, correct shape, does not hit any state loader). Full suite 51/51, 0 new. Smoke-tested on the real app. |
| 3 | `c243507` | **Launcher hardening** (`CSRN_GAME_DAY_LAUNCHER.ps1`) — `Get-CsrnHealth` returns HEALTHY / DOWN / HUNG instead of just "is 5050 listening". HUNG → names the PID and offers kill+restart, and does **not** open tabs at a dead instance. Readiness loop now requires a real HEALTHY `/api/health`. **HEALTHY path unchanged — still just opens the tabs.** | PowerShell `[Parser]::ParseFile` clean. **Not executed** (would launch OBS/Chrome, can kill processes). **Needs a real dry-run by you before first game-day use.** |
| 4 | `04a5c0e` | **`tools/sweep_state_tmp.py`** — standalone janitor for orphaned `.state.json.*.tmp` atomic-write debris. Dry-run by default; `--apply` to delete; `--min-age-minutes` floor (default 60) so an in-flight write is never touched; refuses to match the real `state.json`. | `test_sweep_state_tmp_tool.py` — 4 passed. Dry-run against the real repo root: **29 files / 54.6 MB** would be removed. **I did not run `--apply`** (deleting from the live Drive-synced folder unattended is your call). |
| 5 | `6077eaa` | **Startup hard-link warning** — `app.authority_state_hardlink_warning()` prints a `[WARN]` line at boot if the state authority file has `st_nlink > 1` (the Drive-sync-hardlink condition from the audit). **Warn-only, not a hard fault** — see "Your decisions" below. | `test_authority_state_hardlink_warning.py` — 4 passed (incl. real `os.link`, bad-type-returns-None). Verified against the real `STATE_AUTHORITY_PATH` → no warning (nlink=1, correct). |

To see them: `git log --oneline 0f1d67d..overnight-fixes-20260828`

---

## Per-item status

### FIX FIRST — Field position "ownership" is backwards → **NOT DONE. Needs you.**

I could not find the code you're describing. I searched every plausible term
(`territory`, `yards_to_go`, `yards_to_score`, `field_position`, `to_goal`,
`red_zone`, `scoring threat`, `own/opp`, …) across **all** Python, JS, HTML,
and the inline `index.html` / `temp-index-script.js` scripts.

**There is no "yards to go to score" / "N yards to the end zone" numeric
computation anywhere in the codebase.** The only possession/direction-relative
field-position logic that exists:

- `canonical_state_service.py` `_spot_to_coord` / `_coord_to_spot` /
  `_team_own_yard_spot` / `_opponent_yard_spot` — physical 0–100 field
  coordinate helpers, used for kickoff/touchback ball placement. I reviewed
  these against your Caledonia-30 example and they compute correctly.
- `csrn-production-theme-runtime.js` `collegiateFieldSpotLabel()` — turns a raw
  `LEFT 30` / `RIGHT 30` spot into a mascot-prefixed label ("Caledonia 30").
  This *is* a possession+direction-relative computation and *could* be what
  you saw inverted, but it produces a **label**, not a 30-vs-70 number.
- `csrn-production-theme-runtime.js` `productionFieldState()` `firstDownPct` —
  the first-down marker position (yards to first down, not to score).

**What I need from you:** where did the wrong 30/70 number actually appear
on screen last night? (which overlay/theme, which stat box). If it's a
number CSRN doesn't currently compute, this is a small new feature, not a
one-line inversion fix — and it's overlay-facing, so I want your spec before
building it, not a guess. If it's the `collegiateFieldSpotLabel` mascot
that was wrong, that's a 2-line fix in launcher-loaded JS that still needs
visual confirmation.

### NEW FEATURE — Halftime overlay → **ALREADY BUILT (08-25), except the sponsor area.**

Commit `0bc9486` "Build the actual halftime overlay" + `tests/test_halftime_overlay.py`
already deliver, in `templates/pregame_universal_overlay.html`:

- ✅ `HALFTIME` banner (`.statebadge.halftime`, follows the existing pattern)
- ✅ Score carried over ("Score at the Half", `home_score-visitor_score`)
- ✅ Weather (reuses `weatherCard()` / `VenueWeatherService`, no new tracking)
- ✅ Rotation through the half's real spotlight cards (TD/sack/turnover/first
  down) — `_first_half_spotlights()` in `pregame_presentation.py` reads
  already-resolved `state["events"][].after.player_graphic`, rendered via
  `spotlightCard()` wired into the page's existing `rebuildCards()/tick()`
- ✅ Pregame overlay no longer shows during halftime — `shouldShow()` now
  excludes `halftime`
- ✅ Pregame overlay no longer shows after a game ends — `shouldShow()` now
  also excludes `postgame` / `final`
- ✅ In-game delay uses this view with `WEATHER DELAY` vs `GAME DELAYED`
  badge text (not the pregame view)

**The one real gap: no sponsor display area.** Zero sponsor references in
`pregame_universal_overlay.html`, and `pregame_presentation.py`'s payload
carries no sponsor data. Adding it means a design decision (which sponsors —
all active? a rotation? the current `sponsor_spotlight`? the `sponsor_service`
list?) plus a new `pregame_presentation.py` helper + a `sponsorCard()` in the
overlay HTML/CSS wired into `rebuildCards()`, then visual review in OBS. I did
**not** build this blind — it's overlay-facing design work. Tell me which
sponsor source and I'll do it as a contained follow-up.

### 1. Verify last night's postgame stats/recap/social → **NOT GENERATED. Data is safe. Needs you to finalize the game.**

- `state.json` and `Data/Broadcasts/FB-2026-4A-W01-001.json` both show
  `status: "live"` — **the game was never formally ended.** No `recaps.json`
  entry, no social draft, no exports — because the postgame workflow never ran.
- This is **not** the `load_state_for_reporting()` guard bug (that bug is about
  a *completed* broadcast reading empty; that guard fix is present on this
  branch, commit `b489c33`). Here the game just stopped mid-4th-quarter
  (score 42–10, 117 plays) — consistent with the app freezing, as the audit
  predicted.
- **The data is fully intact and recoverable.** I ran `StatisticsService.report()`
  read-only against `state.json`: 117 plays/events, full team + 24 player
  rows, correct scoring summary (ITAWAMBA 42 — 6 TD / 6 XP / 2 sacks;
  Caledonia 10 — 1 TD / 1 FG / 1 XP). **No archive-fallback "recovery" was
  needed** — the live state itself has everything.
- Minor data-quality note: `reconciliation.all_reconciled == false` (team vs
  player rushing 341 vs 343, receiving 111 vs 66). Possibly from the mid-game
  write failures, possibly pre-existing. Not chased.

**What I need from you:** finalize `FB-2026-4A-W01-001` in the app (End Game),
which will archive it and let recap/social generate normally. I did not run
`end_game()` / generate a recap against the repo — finalizing a broadcast and
generating review content is your call, not an unattended one.

### 2. Sacks not firing the center spotlight → **ALREADY FIXED (08-25) for the statistician play form. One real gap remains in the quick-event path.**

- Commit `3be429b` added the missing `_show_player_spotlight(... graphic_type="sack" ...)`
  call to `RulesService.play()` (the statistician's detailed play form,
  `/api/rules-play`). `tests/test_rules_service.py::test_sack_shows_defensive_player_spotlight`
  covers it and passes. That is the path `submitPlayEntry()` in `index.html`
  actually posts to.
- Commit `1325f2f` fixed the related id-gate bug in `EventService.trigger()`
  that was blocking manual-entry spotlights generally.
- **Remaining gap I found (not fixed):** `EventService.trigger()`'s own sack
  branch (`event_service.py:571-635`, used by `/api/event-trigger` quick
  buttons, not the play form) fires the spotlight with `player` = the resolved
  *offensive* player (passer/ball-carrier), never the sacker — there is no
  `sacker_id` / `manual_sacker` plumbed into `EventService`. If a sack is ever
  entered via a quick-event button rather than the play form, it shows the
  wrong player or nothing. I did **not** patch this: it needs new payload
  plumbing into the live event pipeline (not a +21/−1 change), and I can't
  tell from here whether that path is used for sacks in practice.

**What I need from you:** if you still see this broken after a clean restart,
tell me *how* the sack was entered (detailed play form vs a quick button) and
ideally paste the recorded play/event JSON so I can reproduce it.

### 3. Scoring-leader stat box (kicker over TD / blank photo / clipped name) → **ALL THREE ALREADY FIXED (08-25).**

`static/csrn-production-theme-runtime.js` (commits `f3d7a4e`, `ce9dc8f`):

- **Kicker's 2 pts ranking over a TD:** `collegiatePlayerLeaders()` now dedupes
  to one candidate per title via `bestByTitle` (`~line 2697`). The point
  totals were always correct; the bug was one candidate *per player* per
  category. Fixed.
- **Blank instead of crest:** `patchCollegiateRails()` now does
  `textValue(leader.image, teamLogo)` — team crest fallback when no headshot
  (`~line 2748`). Fixed.
- **Name clips off-screen:** `fitPlayerLeaderName()` shrink-to-fit is now
  called on the leader name (`~line 2795`), same pattern as the main
  spotlight card. Fixed.

If you saw this last night, it's the stale-code situation (§ TL;DR #2).

### 4. Caledonia headshots imported as raw camera originals → **ALREADY FIXED (08-25).**

- `support_media_service.py` `_downscale_for_storage()` (commit `d6dc983`)
  re-encodes any upload over `MAX_HEADSHOT_DIMENSION = 1000`px with LANCZOS,
  called from `upload_headshot()`. New imports are safe.
- `reprocess_oversized_headshots.py` (commit `6b4c87d`) is the one-time
  backfill for the 37 already on disk, kept as a tracked re-runnable utility.
- Per `docs/WEEK_OF_2026-08-25_FIXES.md` it was already run against
  Caledonia's 37 oversized files, and every other roster was scanned (clean).

**Verify:** confirm Caledonia's headshots on disk are now ≤1000px
(`python reprocess_oversized_headshots.py` will report / re-fix if not).

### 5. Pregame "Storylines" contrast/sizing → **NOT DONE (visual design — your call).**

This is a pure broadcast-legibility judgement (contrast ratio, font size on a
1080 feed) that I shouldn't make unattended in a launcher-loaded template.
It's in `templates/pregame_universal_overlay.html` (storyline card CSS).
Tell me the target (e.g. "match the HALFTIME spotlight card's body size,
white on the dark scrim") and it's a quick contained CSS pass.

### 6. Tier 2 — state.json / Drive cleanup → **PARTIALLY DONE (the safe slices). Core relocation NOT done — your call.**

- ✅ **Startup hard-link warning** — commit `6077eaa` (warn-only, see below).
- ✅ **Temp-file janitor** — commit `04a5c0e` (`tools/sweep_state_tmp.py`).
  Dry-run shows **29 orphaned `.state.json.*.tmp` files, 54.6 MB** in the repo
  root. To actually delete them:
  ```bash
  python tools/sweep_state_tmp.py --apply
  ```
  I did **not** run this — deleting from the live Drive-synced folder while
  you're asleep isn't something I'll do unattended, even for junk.
- ❌ **NOT done: moving the Drive mirror target and `Data/Backups/Core/`
  (504 MB) out of the synced folder, and adding the throttled periodic Drive
  snapshot.** This changes the live write path in `app.py`
  (`STATE_REPOSITORY` / `CORE_BACKUP_DIR` wiring) and physically relocates
  500+ MB inside a Google-Drive-synced tree. If I get a path wrong, CSRN
  writes state to the wrong place or won't boot; if the move races Drive
  sync, you get conflicted copies. This is a "do it with you watching"
  change, not an overnight one. The exact plan is in the audit
  (`state.json` audit, Tier 2, items 5–8).

### 7. Launcher health-check → **DONE** (commits `3663023` + `c243507`). See the table above. Needs your dry-run before first game-day use, and it must ship together with `/api/health` (an older server without that route will make the readiness loop time out to the existing 60s warning box — safe, but not what you want).

### 8. Sequential dual-spotlight (QB card then receiver card) → **NOT DONE.**

Lower priority per your note, gated on "1–7 leave you time and tests all
green". Given how much of 1–7 turned out to be already-done-pending-verification
vs needs-your-decision, and that this is a new overlay animation sequence
(design + timing + the video-board rotation system), I'm leaving it for a
session where you can watch it render. The 08-25 stopgap ("pass from {name}"
text line on the receiver's card, commit `eba349a`) is present and is the
current behavior.

---

## Your decisions (blocking further work)

1. **Field position:** where did the wrong 30/70 number show on screen? (§ FIX FIRST)
2. **Last night's game:** finalize `FB-2026-4A-W01-001` in the app so recap/social
   generate. Data is intact; no recovery needed.
3. **Halftime sponsor area:** which sponsor source should it pull from
   (all active / rotation / `sponsor_spotlight` / `sponsor_service` list)?
4. **nlink check severity:** I made it **warn-only**. You asked for "faults".
   To make it fatal, add `raise SystemExit(1)` after the print in `app.py`'s
   `__main__` block (right after `_authority_hardlink_warning`). I'd keep it
   warn-only until the Tier 2 relocation is done, otherwise a Drive hiccup
   could block a broadcast start.
5. **Tmp sweep:** OK to `python tools/sweep_state_tmp.py --apply` (29 files /
   54.6 MB)?
6. **Storylines contrast (item 5):** give me the target and I'll do the CSS pass.

---

## What I deliberately did NOT touch

- **The running CSRN process** — not restarted, not interacted with.
- **`templates/index.html`** — it has *your* uncommitted changes in the working
  tree (the 45000/20000 emergency timeouts, and a new "Start Broadcast (Go
  Live)" button `commandStartBroadcastButton`). I left all of it exactly as-is.
  Not reverted, not committed, not built on.
- **The 45000 / 20000 timeout values** — untouched, per your instruction.
- **`static/*.js` and `static/*.css`** — no changes. Every overlay-facing
  item (2 rendering, 3, 5, halftime sponsor, 8) was either already fixed there
  or is a write-up. I did not make untested changes to launcher-loaded overlay
  code overnight.
- **MIC 2 / OBS Limiter device-label mismatch** — hardware/OBS config, flagged
  only.
- **Itawamba's 6 duplicate jersey numbers** — opposing-team roster data. Not
  touched. **Flag:** this is real and will misattribute stats/spotlights for
  Itawamba if those numbers collide on scoring plays. It's DragonFly-synced
  data, so it needs a data decision (dedupe at source, or a manual override
  layer), not a silent code change.
- **"Prep FB/YT" button and clock-control repositioning** — untouched.
- **The other pre-existing working-tree changes** at session start
  (`Data/Captions/caption_state.json`, `Data/Runtime/pregame_presentation.json`,
  `Data/production_template_state.json`, `broadcaster_print_service.py`,
  `tests/test_broadcaster_print_service.py`, and the untracked
  `Data/Captions/Transcripts/FB-2026-TEST-W00-001.json`) — not mine, not
  touched, not committed.

---

## Things that felt risky / uncertain

- **The stale-code hypothesis is unproven.** I'm inferring that last night's
  overlay bugs were old cached/loaded code because the fixes are demonstrably
  on the branch and were on disk during the game. I could be wrong — there
  could be a real regression in one of the 08-25 fixes that only shows under
  live conditions. The way to know: deploy this branch, restart CSRN, hard-
  refresh the OBS browser sources, and re-test each item. If something is
  *still* broken after that, it's a real bug and I need the live symptom.
- **OBS browser-source caching.** Even after a server restart, OBS caches
  overlay JS/CSS by URL. The overlay cache-bust token is currently
  `?v=19.6-r18-r8-passer-credit` (current, includes the 08-25 work), but OBS
  may need its browser sources refreshed / cache cleared to pick it up.
- **Launcher script** — logic-reviewed and parse-checked but never executed.
  Dry-run it before you rely on it on a game day.
- **`tools/sweep_state_tmp.py --apply`** — the 60-minute age floor should make
  it safe against in-flight writes, but it's still deleting files from a
  Drive-synced folder. Low risk, not zero.
- **I spent most of the session on forensics, not code.** That's the honest
  outcome of a list where ~5 items were already done and ~4 need your input.
  The alternative — re-implementing the already-fixed items — is what I was
  explicitly told to avoid, and it's what the rollback-folder history warns
  against.

---

## Suggested next steps (in order)

1. Skim this file + `git log -p 0f1d67d..overnight-fixes-20260828` (5 commits, all small).
2. Merge if you're happy. Then **restart CSRN from the merged code** and
   **refresh the OBS browser sources.**
3. Re-test items 2, 3, 5, and the halftime overlay live. Report anything still
   broken with the on-screen symptom — that's a real bug and I can act on it.
4. Finalize `FB-2026-4A-W01-001` → confirm recap/social generate.
5. Answer the 6 decisions above so I can pick up field position, the halftime
   sponsor area, storylines contrast, and Tier 2 relocation.
6. `python tools/sweep_state_tmp.py --apply` when you're ready.
