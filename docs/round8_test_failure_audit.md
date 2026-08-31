# Round 8 — Pre-existing Test Failure Audit

**Branch:** `round8-test-audit-20260830` (from `round7-ruleset-engine-20260830`)
**Runner:** `.venv/Scripts/python.exe -m pytest -q -p no:randomly` (Python 3.13.14)
**Baseline at start of round:** `51 failed, 2291 passed`

> Note on the interpreter: the machine's global `python` is 3.14 and is missing
> `pronouncing` (imported by `roster_service.py`), which makes the suite fail to
> collect entirely (58 collection errors). The real baseline only reproduces
> under the project `.venv`. This audit and every commit in the round use `.venv`.

---

## STEP 1 — Categorisation of all 51

Buckets (from the round brief):

- **(a)** obsolete / removed functionality — safe to delete
- **(b)** fixable test-infrastructure problem — safe to fix
- **(c)** flaky / non-deterministic — needs redesign
- **(d)** the test is CORRECT and current production behaviour is actually wrong
  — **do not fix the code this round; flag loudly**

### Bucket tally

| Bucket | Count | Disposition this round |
|---|---|---|
| (a) obsolete | **40** | deleted (STEP 2) |
| (b) fixable test problem | **3** | assertions updated (STEP 2) |
| (c) flaky | **0** | — |
| (d) production looks wrong / needs owner decision | **8** | documented only (STEP 4), left failing |
| **Total** | **51** | |

> Two reclassifications made during STEP 2 (both after deeper code-tracing):
>
> - `test_gate167_r9_rearms_player_mode_after_undo_or_new_event` (row 35): (a) → (b).
>   5 of its 6 assertions still hold; only the `latest.id` token is stale (the
>   re-arm key now composes from `graphic.player_id` / `graphic.roster_id` /
>   timestamps instead of the latest event's id). One-line update, not a dead test.
> - `test_gate172_r2` / `test_gate172_r3` mask-art failures (rows 47–49): (d) → (a).
>   Reachability analysis proved the `layers-v10` mask-compositing pipeline is
>   **dead code** — `paintFridayNightLayeredFootballClash()` unconditionally
>   `return`s `paintFridayNightStandaloneFootballPlayers(...)` on its first line,
>   and `constrainFridayColorMask` / `deriveFridayUniformReliefLayer` /
>   `FRIDAY_LAYERED_CLASH_ASSETS` have zero call sites. The regenerated masks
>   cannot affect any broadcast output, so these are obsolete, not a bug. (The
>   dead runtime code + `layers-v10/` art itself is flagged for a follow-up
>   cleanup — see STEP 4.)

There are **zero** flaky tests in the 51. Every failure is a deterministic
assertion over static file content, a bundled image, or the blueprint set —
no timing, threads, network, sleeps, or unseeded randomness anywhere. Re-running
the suite five times produced the identical 51.

---

### The three root causes behind 49 of the 51

Almost all of the noise traces to **three** deliberate, already-shipped changes
that the owner made after these guard tests were written, without updating the
guards:

1. **The themed-overlay runtime was advanced far past the "gate 16.x–17.x" era.**
   `templates/overlay.html` now cache-busts the theme runtime at
   `csrn-production-theme-runtime.css?v=19.6-r18-r5-caption-sticky` /
   `...js?v=19.6-r18-r8-passer-credit`. ~34 "gate167–172" tests each pinned the
   *then-current* `?v=` string (`?v=18.5-r11`, `?v=16.9-r3`, …) as a one-shot
   "this round shipped" check. Later gate rounds **and** later owner commits
   (`caption-sticky`, `passer-credit`, the whole "Collegiate Tech" theme series)
   legitimately moved the string on. Several of these tests are already *named*
   `…_superseded_by_gate168` / `…_superseded_by_r23`.

2. **The Friday-Night layered-clash compositor was rewritten (`friday-football-v10`
   → `v11`) and its mask/texture art was regenerated.** Tests pinned to the v10
   schema label, the old `tintFridayMask(...)` compositor calls, `?v=18.5-r12`
   asset strings, mask dimensions `1672×941`, and white-RGB mask encoding now
   fail. The live assets are `1536×1024` and black-RGB + alpha.

3. **The frozen renderer files were intentionally evolved.**
   `static/csrn-broadcast-layout-engine.css/.js` (the file the Gate 11.6 "Neon"
   freeze hashes) was rebuilt by the "Collegiate Tech" feature commits
   (`4265230`, `2da5616`, `a6da878`, `452cc6c`, `85ce8e4`, `eba349a`, …);
   `static/csrn-friday-night-stadium-engine.js` was changed by `9064c67`
   ("R18 R3 Friday Night Stadium test broadcast readiness"). The SHA-256 freeze
   guards were never re-pinned and the BIBLE freeze section was never updated.

---

### Full 51-row table

`Test` column is `file :: test`. All paths under `tests/`.

#### (a) — obsolete, deleted this round

**(a-1) Overlay cache-bust / runtime-version pins — 34**
Each asserts `templates/overlay.html` (or the runtime JS) still contains an old
`csrn-production-theme-runtime` `?v=` string / `binding-vNN` marker. Current
authoritative pin is `19.6-r18-*`. Non-version assertions in the same test
functions (host-id presence, `binding-v46`, shim presence, …) still pass and are
covered by sibling tests that keep passing.

| # | Test | Pinned value it asserts | Why obsolete |
|--:|---|---|---|
| 1 | test_gate167_r10_player_transition_continuity.py :: test_gate167_r11_cache_bust | `?v=18.5-r11` | overlay now `19.6-r18-*` |
| 2 | test_gate167_r11_player_presentation_legibility.py :: test_gate167_r11_cache_bust | `?v=18.5-r11` | " |
| 3 | test_gate167_r12_player_text_scale.py :: test_gate167_r12_cache_bust | `?v=18.5-r11` | " |
| 4 | test_gate167_r13_player_text_scale_iphone.py :: test_gate167_r13_cache_bust | `?v=18.5-r11` | " |
| 5 | test_gate167_r14_player_text_selector_correction.py :: test_r14_cache_bust | `?v=18.5-r11` | " |
| 6 | test_gate167_r15_player_text_final_tuning.py :: test_gate167_r15_cache_bust | `?v=18.5-r11` | " |
| 7 | test_gate167_r17_manual_spotlight_show_update_bridge.py :: test_gate167_r17_cache_bust | `?v=18.5-r11` | " |
| 8 | test_gate167_r18_central_video_board_media_binding.py :: test_gate167_r18_cache_bust | `?v=18.5-r11` | " |
| 9 | test_gate167_r19_central_video_board_media_polish.py :: test_r19_cache_bust_superseded_by_gate168 | `?v=18.5-r11` | self-labelled superseded |
| 10 | test_gate167_r20_central_video_board_boundary.py :: test_r20_cache_bust_superseded_by_gate168 | `?v=18.5-r11` | self-labelled superseded |
| 11 | test_gate167_r21_central_board_layer_ownership.py :: test_r21_cache_bust_superseded_by_r23 | `?v=18.5-r11` | self-labelled superseded |
| 12 | test_gate167_r23_native_8bit_video_board_binding.py :: test_r23_cache_bust_is_superseded_by_gate168 | `?v=18.5-r11` | self-labelled superseded |
| 13 | test_gate167_r4_live_event_ticker_and_themed_player.py :: test_gate167_r4_overlay_has_player_host_and_updated_runtime_version | `?v=18.5-r11` (+ host ids, which pass) | overlay now `19.6-r18-*` |
| 14 | test_gate167_r5_game_state_semantics.py :: test_gate167_r5_overlay_cache_busts_runtime | `?v=18.5-r11` | " |
| 15 | test_gate167_r8_deterministic_state_binding.py :: test_gate167_r8_overlay_cache_version | `?v=18.5-r11` | " |
| 16 | test_gate167_r9_player_event_reliability.py :: test_gate167_r9_cache_bust | `?v=18.5-r11` | " |
| 17 | test_gate168_r2_native_friday_night_production_binding.py :: test_gate168_r2_cache_bust | `?v=18.5-r11` | " |
| 18 | test_gate168_r3_identity_authority_strict_native_media.py :: test_r3_cache_bust | `?v=18.5-r11` | " |
| 19 | test_gate169_r2_heritage_native_binding_and_clash_foundation.py :: test_gate169_r2_cache_bust | `?v=18.5-r11` | " |
| 20 | test_gate169_r3_heritage_native_spotlight_media_finish.py :: test_cache_bust | `?v=18.5-r11` | " |
| 21 | test_gate169_r4_heritage_player_spotlight_layout_finish.py :: test_r4_cache_bust | `?v=18.5-r11` | " |
| 22 | test_gate169_r4_r4_overlay_cache_patch_contract.py :: test_r4_r4_overlay_is_expected_at_target_cache_version | `?v=18.5-r11` (whole file) | file deleted |
| 23 | test_gate169_r6_heritage_standard_neutral_clash.py :: test_r6_r4_cache_bust | `?v=18.5-r11` | overlay now `19.6-r18-*` |
| 24 | test_gate169_r6_r3_cache_prefix_regression.py :: test_historical_cache_contract_tracks_authoritative_r1_r3_pin | `?v=18.5-r11` (sibling is a tautology) | file deleted |
| 25 | test_gate169_r7_heritage_highlight_grayscale_finish.py :: test_r8_cache_bust | `?v=18.5-r11` | overlay now `19.6-r18-*` |
| 26 | test_gate169_r8_heritage_newsprint_media_tone_finish.py :: test_r8_cache_bust | `?v=18.5-r11` | " |
| 27 | test_gate169_r9_heritage_readability_finish.py :: test_r9_cache_bust | `?v=18.5-r11` | " |
| 28 | test_gate170_r1_8bit_dynamic_clash_production_binding.py :: test_r1_cache_bust | `?v=18.5-r11` | " |
| 29 | test_gate170_r1_r3_8bit_athlete_asset_path_fix.py :: test_r1_r3_history_is_superseded_by_r2_cache_pin | `?v=18.5-r11` | self-labelled superseded |
| 30 | test_gate170_r2_8bit_lower_data_readability_polish.py :: test_r2_runtime_binding_and_cache_advance | `?v=18.5-r11` | overlay now `19.6-r18-*` |
| 31 | test_gate171_r1_friday_night_dynamic_clash_production_ready.py :: test_gate171_cache_pin | `?v=18.5-r11` | " |
| 32 | test_gate171_r1_r2_superseded_8bit_runtime_version_contracts.py :: test_friday_night_r1_cache_and_readiness_contract_remain_authoritative | `?v=18.5-r11` | self-labelled superseded |
| 33 | test_gate171_r2_friday_night_layered_dynamic_clash_players.py :: test_runtime_and_cache_advance_to_gate171_r3 | `?v=18.5-r11` | overlay now `19.6-r18-*` |
| 34 | test_gate172_r2_friday_color_clarity.py :: test_r2_advances_only_runtime_and_cache_contract | `?v=18.5-r11` + `friday-football-v10` label | overlay `19.6-r18-*`, schema now `v11` |

**(a-2) Superseded implementation-detail contracts — 3**
Assert exact JS tokens / schema labels from an implementation that has since been
rewritten. The *behaviour* each gate cared about is still present (and still
covered by passing sibling tests); only the frozen literal is stale. Unlike
row 35, these have no clean 1:1 assertion update — they pin whole blocks of a
superseded implementation — so they are deleted rather than patched.

| # | Test | Stale literal | Current reality |
|--:|---|---|---|
| 36 | test_gate171_r7_clean_layered_visual_rollback.py :: test_r7_restores_r2_compositor_treatment_without_losing_current_binding | `layeredSchema="friday-football-v10"`, `tintFridayMask(...)`, `globalAlpha=.54`, `secondaryAlpha=.68` | compositor rewritten to `friday-football-v11` / `constrainFridayColorMask`; sibling `test_r7_restores_clean_r2_layer_population` (R2 layer-art rollback) still passes |
| 37 | test_gate172_r1_friday_new_player_layer_system.py :: test_gate172_preserves_r7_fallback_and_protected_theme_boundaries | `String(state.sport \|\| "football").toLowerCase() !== "football"` and the rest of the v10 guard block | guard refactored for v11; sibling `test_gate172_r11_*` tests cover the v11 system |
| 38 | test_gate172_r1_friday_new_player_layer_system.py :: test_gate172_runtime_uses_v4_assets_and_selected_game_colors | ~25 tokens pinned to `layeredSchema="friday-football-v10"`, `layers-v10/…?v=18.5-r12`, `?v=18.5-r11` | schema now `v11`; `binding-v46` sub-assertion still passes. **Note:** this test also covered "protected theme boundaries" and "selected game colours" — if you want those re-asserted against v11, that is a follow-up. |

**(b, moved from a-2) — 1**

| # | Test | Failing assertion | Fix |
|--:|---|---|---|
| 35 | test_gate167_r9_player_event_reliability.py :: test_gate167_r9_rearms_player_mode_after_undo_or_new_event | `"latest.id" in js` | re-arm is still implemented (`playerActivationKey`, `lastPlayerActivationKey = ""`, `graphic.updated_at`, `graphic.expires_at` all still asserted and present). The key now composes from `graphic.player_id` / `graphic.roster_id` instead of the latest event's `id`. Replace the one `latest.id` line with `graphic.player_id` / `graphic.roster_id`. |

**(a-3) Dead-subsystem tests — 3** (reclassified from (d) after reachability analysis)
Test the `layers-v10` Friday-Night mask-compositing pipeline, which is
unreachable (see the reclassification note above). The regenerated black-RGB /
weak-alpha `layers-v10/*.png` cannot influence any rendered graphic.

| # | Test | Pins | Why dead |
|--:|---|---|---|
| 47 | test_gate172_r2_friday_color_clarity.py :: test_r2_uses_color_clarity_texture_without_changing_player_masks | `football-uniform-color-clarity-texture.png` is `1672×941`; `ctx.globalAlpha=.54` etc. in the runtime | the `globalAlpha` tokens live in the dead `deriveFridayUniformReliefLayer` / post-`return` body; the texture is a `layers-v10` asset |
| 48 | test_gate172_r3_friday_neutral_uniform_base.py :: test_friday_v10_semantic_masks_are_rgba_alpha_masks | each `layers-v10/*-mask.png` has RGB white (255) + varying alpha | inspects dead art only |
| 49 | test_gate172_r3_friday_neutral_uniform_base.py :: test_friday_v10_neutral_base_has_zero_baked_chroma_under_strong_masks | masks have pixels with alpha ≥192 and the base is greyscale under them | inspects dead art only; the "no strong semantic pixels" failure has no runtime consequence |

#### (b) — fixable test problem, assertions updated this round — 3

| # | Test | Failing assertion | Fix |
|--:|---|---|---|
| 35 | test_gate167_r9_player_event_reliability.py :: test_gate167_r9_rearms_player_mode_after_undo_or_new_event | `"latest.id" in js` | see the (b, moved from a-2) row above — `latest.id` → `graphic.player_id` / `graphic.roster_id` |
| 39 | test_gate183_field_position_controller.py :: test_field_controller_commits_through_authoritative_correction_boundary | `"api('/api/game-correction'" in INDEX` | field slider was refactored to commit via `GameStateManager.mutate('/api/game-correction', …)` — same authoritative endpoint, same `source`/`down`/`note:'Field position controller'` payload (those two assertions already pass). Update the one call-shape literal. Sibling `test_drive_direction_is_integrated_with_field_controller` already asserts the `GameStateManager.mutate` shape. |
| 40 | test_gate4_identity_ui.py :: test_player_identity_never_falls_back_to_csrn_branding | `"p?.headshot\|\|teamLogo\|\|'/static/player-silhouette.svg'" in preview` | `renderPlayerGraphicPreview()` fallback chain was refactored to `photo.src = p?.headshot ? rosterHeadshotDisplayUrl(p.headshot) : (teamLogo \|\| '/static/player-silhouette.svg')` with a matching `onerror`. Same order (headshot → team logo → neutral silhouette), still **no** `csrn-logo.png` / CSRN branding — the test's actual intent holds. Update the literal to the current expression. |

#### (d) — production looks wrong OR needs an owner decision; NOT fixed this round — 8

| # | Test | What it guards | Assessment | Confidence |
|--:|---|---|---|---|
| 41 | test_gate116_neon_visual_freeze.py :: test_gate116_freezes_exact_approved_neon_renderer | SHA-256 of `csrn-broadcast-layout-engine.css/.js` == Gate 11.6 "Neon" freeze | File was deliberately rebuilt by the "Collegiate Tech" theme series (7+ commits). The freeze was never formally lifted per its own BIBLE change-control ("explicit unfreeze decision"). **Needs an owner re-freeze / BIBLE update — not something I should silently re-pin.** | High that the change was intentional; the *re-pin* is your call |
| 42 | test_gate126_friday_night_stadium_visual_freeze.py :: test_gate126_friday_night_stadium_renderer_and_art_are_frozen | SHA-256 of `csrn-friday-night-stadium-engine.js/.css` + 9 art files == Gate 12.6 freeze | `csrn-friday-night-stadium-engine.js` changed in `9064c67`. Same as #41 — owner re-freeze decision. | High / your call |
| 43 | test_gate12_friday_night_stadium_engine.py :: test_gate12_isolated_engine_exists_and_preserves_frozen_neon | re-hashes the Neon freeze as a precondition | Same root cause as #41. | " |
| 44 | test_gate13_eight_bit_gameday_engine.py :: test_gate13_is_isolated_and_preserves_both_frozen_renderers | re-hashes Neon + Friday freezes | Same root cause as #41/#42 (the 8-bit engine's own hash still matches). | " |
| 45 | test_gate14_heritage_press_engine.py :: test_gate14_isolated_engine_preserves_all_frozen_renderers | re-hashes Neon + Friday + 8-bit freezes | Same root cause as #41/#42. | " |
| 46 | test_gate166_production_render_binding.py :: test_gate166_scorebug_remains_scorebug_only | themed scorebug package must activate `["scorebug"]` only and reject any other component | `9064c67` **relaxed** this on purpose: `activeComponents: state.captionsActive ? ["scorebug","captions"] : ["scorebug"]`. Captions may now ride with the themed scorebug. Sibling `test_gate166_scorebug_suppression_contract_survives` still passes. **Confirm captions-with-scorebug was intended** (looks deliberate) and I'll delete/relax this guard next round. | ~High it's intended; flagging because the round brief says to |
| 47 | test_phase_5_architecture.py :: test_application_factory_returns_distinct_equivalent_instances | `set(create_app(...).blueprints) == EXPECTED_BLUEPRINTS`, which now includes `pregame_presentation` | `pregame_presentation` is installed **after** `create_app()` returns, directly on the module-level `app` (`app.py:3495-3496 install_pregame_presentation(app)`), not inside `create_application()` (which takes an explicit `blueprints=` list). Both real launchers (`app.py:__main__ → serve(app)` and `run_core_foundation.py → csrn_app.app`) use that module-level `app`, so **production is fine** — but any factory-built instance (tests, a hypothetical alternate launcher) silently lacks the universal pregame-delay layer. Fix is 2 parts: call `install_pregame_presentation(application)` inside `create_application()`, and add `pregame_presentation.overlay` / `.status` to `audit_phase5_architecture`'s intentionally-public list. Low-risk, but it changes app-init order and audit policy. | High on the diagnosis; leaving the fix to you |
| 48 | test_theme_architecture.py :: test_completed_phase5_architecture_remains_clean | `audit_phase5_architecture()` — same `pregame_presentation` expectation | Identical root cause to #47 (`Missing Blueprints: pregame_presentation`). The same 2-part fix resolves both. | " |

---

## STEP 2 — actions taken

See `OVERNIGHT_SUMMARY.md` (Round 8 section) for the commit-by-commit log and the
running failure count. In summary:

- **40 obsolete test functions deleted:**
  - 34 overlay cache-bust / version pins (commit `STEP 2a`, 2 whole files removed:
    `test_gate169_r4_r4_overlay_cache_patch_contract.py`,
    `test_gate169_r6_r3_cache_prefix_regression.py`).
  - 3 superseded-implementation contracts (commit `STEP 2b`):
    `test_gate171_r7 :: test_r7_restores_r2_compositor_treatment…`,
    `test_gate172_r1 :: test_gate172_preserves_r7_fallback…`,
    `test_gate172_r1 :: test_gate172_runtime_uses_v4_assets…`.
  - 3 dead-subsystem tests (commit `STEP 2c`):
    `test_gate172_r2 :: test_r2_uses_color_clarity_texture…`,
    `test_gate172_r3 :: test_friday_v10_semantic_masks_are_rgba_alpha_masks`,
    `test_gate172_r3 :: test_friday_v10_neutral_base_has_zero_baked_chroma…`.
  - Passing sibling tests in every touched file are untouched.
- **3 stale assertions updated** (commit `STEP 2b`: `test_gate183`, `test_gate4`,
  `test_gate167_r9 :: …rearms_player_mode…`) to the current equivalent code,
  preserving each test's original intent.

## STEP 3 — flaky tests

**None.** Nothing in the 51 is non-deterministic — every failure is a static
assertion over file content, a bundled PNG, or the blueprint set. No timing,
threads, sockets, sleeps, or unseeded randomness. Five consecutive full runs
produced byte-identical failure sets.

## STEP 4 — production-behaviour concerns left for you (8 failing, code untouched)

**A. Renderer-freeze re-pin — rows 41–45 (5 tests).**
`static/csrn-broadcast-layout-engine.css/.js` (the Gate 11.6 "Neon" freeze) and
`static/csrn-friday-night-stadium-engine.js` (Gate 12.6) were deliberately
evolved after the freezes — the "Collegiate Tech" theme series and commit
`9064c67` respectively. The SHA-256 guards and the `CSRN_PROJECT_BIBLE.md` freeze
section were never updated. Per the tests' own change-control language this needs
an **explicit owner "unfreeze → re-freeze at the new hash" pass**; I did not
re-pin them or touch the renderers.

**B. `gate166` scorebug-only contract was relaxed — row 46 (1 test).**
`9064c67` changed the themed-scorebug activation to
`activeComponents: state.captionsActive ? ["scorebug","captions"] : ["scorebug"]`,
with a matching `throw` guard that now permits exactly `{scorebug, captions}`.
This looks entirely intentional (captions belong with a themed scorebug). If you
confirm, the guard test should be relaxed to match; I left it failing pending
your word.

**C. `pregame_presentation` blueprint is not in the application factory — rows
47–48 (2 tests).** `install_pregame_presentation()` runs on the module-level
`app` only, not inside `create_application()`. **Both real launchers are fine**,
but factory-built app instances lack the universal pregame-delay layer, and two
architecture tests already encode the factory as the expected owner. 2-part fix
(register in the factory + whitelist the two intentionally-public endpoints in
`audit_phase5_architecture`); low-risk but an init-order + audit-policy change,
so left for you.

### Follow-up cleanup this audit uncovered (not a test problem)

The Friday-Night **`layers-v10` mask-compositing pipeline is dead code**:
`paintFridayNightLayeredFootballClash()` in `static/csrn-production-theme-runtime.js`
unconditionally `return`s `paintFridayNightStandaloneFootballPlayers(...)` on its
first line (the live path uses pre-baked `players/palette-v2/*.png`), and
`constrainFridayColorMask`, `deriveFridayUniformReliefLayer`, and
`FRIDAY_LAYERED_CLASH_ASSETS` have **zero call sites**. That's ~150 lines of dead
runtime code plus the `static/friday-night-stadium/clash/layers-v10/` art
directory. Recommend a dedicated commit to delete both (and the 3 remaining
*passing* `test_gate172_r3` siblings that also only exercise it) — needs your OK
because it edits the live overlay runtime file.
