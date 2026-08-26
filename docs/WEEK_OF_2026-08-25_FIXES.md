# Week of 2026-08-25 — Fix Log

Working notes from the pre-Friday hardening pass on `gate6/final-visual-matrix`,
covering the Caledonia mock-broadcast test cycle. Written for anyone
picking this branch back up who wasn't in the room for the investigations.

Each entry: what broke, the real root cause (as traced, not assumed), the
fix, and the commit.

## Player-spotlight graphics

- **Defensive/turnover TD spotlight** (missing graphic, wrong label, wrong
  credited player). `rules_service.py`'s `_show_touchdown_graphic()` (now
  `_show_player_spotlight()`) never had a call site for interception/fumble
  return touchdowns at all — only run/pass and punt/kickoff-return TDs.
  Commit `5fec6fb`.
- **Manual-entry headshot backfill** — `manual_automation_player()` always
  built `headshot=""` for a typed-jersey-number entry, even when that player
  has a real photo on file. Fixed to look the player up by number+school.
  Commit `b9b8f97`. A follow-up simulation (`headshot_backfill_sim.py`,
  commit `80c3e93`) found the fix had **no observable effect** through
  `EventService.trigger()`'s automatic branch, because that branch also
  required `player.get("id")` to be truthy — which a manual entry can never
  satisfy by construction. That gate bug was tracked separately and fixed
  this week (see below).
- **Sack/turnover spotlight never fired via the statistician's play form.**
  Confirmed against a real sack tonight (Jaraylon Washington) that updated
  the stats-based sidebar correctly but never showed the center card:
  `RulesService.play()` never called the spotlight function for sacks or
  plain (non-TD) turnovers at all — only touchdowns. Fixed by generalizing
  `_show_player_spotlight()` and adding both missing call sites.
- **The id-gate bug** — `EventService.trigger()`'s automatic branch required
  `player.get("id")`, which `manual_automation_player()` never sets (`id=""`
  by design). A manually-typed jersey number could never satisfy this gate,
  so the graphic silently never fired for one — confirmed against a real
  production TURNOVER event whose `player_graphic` snapshot came back
  completely empty. Fixed to accept `player.get("number")` too, which both
  the roster-resolved and manual paths always guarantee.
- **QB credit on the passing-TD spotlight card** — added a "pass from
  {name}" text line, reusing the already-resolved `refs["passer"]`; the
  receiver stays the card's photo/headline.

## Photos and asset hygiene

- **Oversized roster headshots.** 37 of Caledonia's 38 headshots were
  unprocessed camera originals (25–31MB, 7000×8400px) — one of them
  (Ja'kylen Sherrod's) was too large to load within the frontend's 350ms
  image-load timeout during a live broadcast, so the TD spotlight silently
  fell back to the team crest. `support_media_service.py`'s
  `upload_headshot()` now downscales anything over 1000px on upload;
  `reprocess_oversized_headshots.py` (kept as a tracked, re-runnable
  utility) fixed the 37 already on disk. Scanned every other roster in the
  system — none of them had the same problem.
- **Stat-rail leader box flicker.** `patchCollegiateRails()` ran on a 250ms
  clock timer and unconditionally tore down/rebuilt the leader `<img>` every
  tick, forcing a fresh network fetch of the headshot ~4x/second even when
  nothing had changed. Made idempotent (only touches the DOM when the
  rendered image actually changes). Rotation interval also doubled
  (12s → 25s) per operator feedback.
- **"Scoring Leader" could show a kicker's 2 points over a real touchdown
  scorer.** Not a bad calculation — confirmed the point totals were always
  correct. `collegiatePlayerLeaders()` generated a separate candidate per
  player per category instead of just the category leader; deduped to one
  candidate per title.

## Reporting after a broadcast ends

- **Statistics Engine / printed PDF / recap all showed empty results**
  after tonight's game was finalized, despite a correct 20-7 final score.
  The archive (`Data/Broadcasts/<id>.json`'s `final_state_archive`) had all
  16 real events/plays intact the whole time — this was never a data-loss
  bug. `app.load_state_for_reporting()`'s guard checked
  `history or events or plays`, and a single stray leftover `history` entry
  (from `set_control_source()` running 17 seconds after `end_game()` had
  already cleared the live state) made that `or` trip and skip the archive
  fallback. Fixed the guard to check `events`/`plays` specifically, and
  fixed `StateService.push_history()` to no-op once a broadcast is
  `completed`, so the debris stops accumulating in the first place.
  ("The printed PDF" turned out to be a client-side `window.print()` of the
  same `/api/statistics` payload, not a separate server bug.)

## Halftime overlay

Previously the halftime break showed the same stale PREGAME countdown
screen — `shouldShow()` in `pregame_universal_overlay.html` only excluded
`live`/`completed`, so `halftime` (and `postgame`/`final`) fell through.
Built the actual intended halftime view: a `HALFTIME` badge (reusing the
existing `.statebadge` pattern), the existing weather card reused as-is
(sourced from `VenueWeatherService`, no new tracking), and a rotation
through the real first-half spotlight events — sourced directly from
`state["events"][].after.player_graphic` (already-resolved snapshots, no
re-resolution needed), rendered in this page's own native card markup
rather than importing the separate video-board component system. Also
extended delay-mode handling: `GAME DELAYED` vs `WEATHER DELAY` badge text,
and fixed `shouldShow()`'s missing `postgame`/`final` exclusion.

## Test suite health

Fixed every instance found of three recurring pre-existing-failure
categories that had been showing up in every regression check:
- `nullcontext()` used as a lock stub where `RulesService.play()` calls
  `.acquire()`/`.release()` directly — swap for `threading.Lock()`.
- A stray UTF-8 BOM at the start of several source files
  (`roster_routes.py`, `roster_service.py`, `rules_service.py`,
  `broadcaster_print_service.py`, `dragonfly_service.py`,
  `dragonfly_sync_service.py`, `ticker_policy_service.py`,
  `tests/test_gate184_r10_ticker_lifecycle.py`) breaking `ast.parse()` for
  any test that source-scans those files.
- Stub/fixture classes and dataclasses (`StubGameOperationsService`,
  `StubEventService`, `AssociationRoutesDependencies`,
  `BroadcastRoutesDependencies`) whose constructor signatures had drifted
  out of sync with the real service classes as those gained parameters over
  time.

Running the **full** suite (not the filtered subsets used all week)
surfaced a much larger baseline than the "~7" understanding: 62 failed + 24
errored. Fixing all instances of the three categories above brought that to
51 failed, 0 errored. The remaining 51 split into two groups, neither
touched this week:
- ~40 are historical cache-bust/version-pin assertions in old `test_gateNNN_*`
  files, each frozen to its own now-superseded `?v=` string from an earlier
  gate. Confirmed via repeated git-stash comparisons this week that these
  are unaffected by current work — they're accurate historical snapshots,
  not live regressions.
- A handful (`test_gate183_field_position_controller`,
  `test_gate4_identity_ui`, part of `test_gate167_r9_player_event_reliability`)
  assert exact hardcoded JS/HTML strings against code that has since evolved
  — a real but separate category from tonight's three, needing case-by-case
  investigation into what actually changed.
- One confirmed **real architecture gap**, not a test problem:
  `create_app()` doesn't register the `pregame_presentation` blueprint (or
  the state/runtime/theme public-state caches) the way the module-level `app`
  singleton does — `install_pregame_presentation(app)` and the cache
  installers run as post-processing on the singleton, outside `create_app()`
  itself. A second call to `create_app()` produces an incomplete app.
  (`test_phase_5_architecture.py::test_application_factory_returns_distinct_equivalent_instances`,
  `test_theme_architecture.py::test_completed_phase5_architecture_remains_clean`)

See the session's overnight report for full detail and confidence levels.
