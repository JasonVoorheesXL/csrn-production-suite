# Final Score Graphic redesign

Branch `final-score-graphic-redesign-20261004`, off `main` at `e6f3128`. Not merged. Awaiting review.

## What changed

**Layout (`social_media_preview_service.py`, `generate_final_score()` only; pregame graphic untouched)**

1. **Score is part of the hero.** Each team's score now sits directly under its name and mascot inside `.stage-side`, not in a band below the stage. The winner keeps the existing `final-winner` treatment (accent color and glow) on both name and score. A tie marks neither side.
2. **FINAL tag** moved to the top center of the hero as an absolute-positioned pill.
3. **Stat highlights** take the space the old `.final-banner` occupied. Two columns, visitor left and home right, each listing up to four lines (see selection logic below).
4. **Final record line removed.** `_final_record_text()`, `_final_records_html()`, `_final_score_banner_html()`, their CSS rules (`.final-banner`, `.final-score-row`, `.final-team`, `.final-score`, `.final-score-dash`, `.final-records`, `.final-records-sep`) and the call site are deleted. Nothing else referenced them. Their tests were removed or rewritten. Deleted outright, not archived, matching the codebase's dead-code convention.
5. `_stage_side_html()` gained two optional keyword arguments, `score_html` and `winner`. Both default to empty, so the pregame graphic's output is byte-identical.

**Stat highlight selection (football only)**

Source: `StatisticsService.report(state)`'s existing per-player rows, obtained through the already-injected `build_statistics`. No new stat tracking.

For each team, three core categories, each only if at least one player has usage in it:

| Category | Eligibility | Sort | Line format |
|---|---|---|---|
| Rushing | `rushing_attempts > 0` | rushing yards, then rushing TDs, then lower jersey | `J. Smith — 142 rush yds, 2 TD` |
| Passing | `pass_attempts > 0` | passing yards, then passing TDs, then lower jersey | `D. Carter — 168 pass yds, 2 TD` |
| Receiving | `receptions > 0` | receiving yards, then receiving TDs, then lower jersey | `T. Brooks — 96 rec yds, 1 TD` |

- The TD suffix appears only when the count is nonzero.
- Names render as first initial plus last name. A bare fallback name like `Player 22` renders as `#22`.
- **Tiebreak:** yardage, then touchdowns, then the lower jersey number. The brief asked me to flag if another tiebreak reads better. Jersey is deterministic and needs no judgment call. It is the one I would change first if reviewers prefer something else.

**Field goal add-on (fourth line, decision to review)**

- A fourth line appears only when one of the team's kickers has a made field goal with a recorded distance: `O. Hale — 41-yd FG`. It shows the longest made distance.
- It never displaces the three core categories. They always come first.
- If no made FG has a recorded distance, no line appears. Nothing is guessed.

**Sport gating**

- **Football:** highlights shown.
- **Basketball, baseball, softball, hockey, Canadian football:** highlights block omitted entirely. No per-player category mapping for these sports has been confirmed for this graphic. Canadian football shares the stats engine but its field support was not verified, so it is omitted rather than assumed.

## FG distance capture (end to end)

- **Operator UI** (`templates/index.html`): an optional "Distance (yds)" number input, visible only for FG events in the event modal. Both the broadcaster and statistician entry points share this modal. The value resets on each open and is sent as `fg_distance` only for FG.
- **Event service** (`event_service.py`): stored as `fg_distance` on the event (top level and in `automation`) and on the play record, mirroring the existing `kick_outcome` pattern. The event label reads `38-yard field goal by …` when a distance is present and `… field goal` when blank.
- **Why a new field instead of `yards`:** the generic `yards` value is only read from the payload when `statistician_mode` is on (`event_service.py` around line 571), and the FG form never sent it. Reusing `yards` would have silently dropped the value on the normal entry path.
- **Statistics** (`statistics_service.py`): each made FG (delta 3) with a valid distance appends it to the kicker's new `field_goal_distances` list. Values are sanitized to integers 1–99. Blank, zero, out-of-range, non-numeric, and missed kicks are ignored.
- **MaxPreps export:** untouched. MaxPreps' schema has no FG distance field.

## Related fix (same root cause as the MaxPreps export bug)

`_resolve_game_state` in this file had the same bug fixed earlier for MaxPreps. It matched the live state by `broadcast_id` alone, so a completed game whose live state had been cleared by `end_game()` resolved to an empty state. The highlights would then silently disappear for exactly the finished games they are meant for. The fix matches the MaxPreps version: only trust the live state when it still carries events or plays, otherwise fall through to the live-state mirror and the archive. Covered by `test_resolve_game_state_falls_back_to_archive_when_live_state_was_cleared_post_game`.

## Verification

**Tests**
- `tests/test_social_media_preview_service.py`: 24 passed. New coverage: winner marking, tie handling, record line absent, leader selection per category, yardage tie → TD → jersey ordering, longest-FG selection, sport omission, empty-stats omission, FG-without-distance omission, and the cleared-live-state regression.
- `tests/test_final_score_fg_distance.py` (new): 5 passed. Covers a made FG with distance through the real `EventService` path, storage on the event, label text, the kicker's stat row, a missed FG not counting, a blank distance rendering gracefully, and invalid values being ignored.
- Event and statistics suites (`test_event_service.py`, `test_statistics_*`, `test_gate184_*`, `test_event_routes.py`): 85 passed, unchanged.
- **Full suite:** 3228 passed, plus the 2 known environment-only `test_state_mirror_throttle` failures.

**Screenshots** (real Playwright renders, real PNGs, in `scratchpad/final_score_shots/`)

1. `shot1_football_with_highlights.png`: football game with real rushing, passing, receiving, and FG data. Highlights match the seeded source rows (M. Johnson 142 rush yds / 2 TD, D. Carter 168 pass yds / 2 TD, T. Brooks 96 rec yds / 1 TD, O. Hale 41-yd FG). The lower-scoring team's column shows only its one rushing line.
2. `shot2_basketball_no_highlights.png`: same data, basketball sport. The highlights block is omitted and the hero stays intact.
3. `shot3_thin_stat_line.png`: football with one line on the visitor side and none on the home side. The home column shows a muted dash. No broken layout.

**Caveat on the screenshots:** the test theme's accent color is white, so the winner treatment is not visibly distinct in these renders. It uses the same `--accent` variable as before, so it will show with a real theme color, but I did not verify that visually here.

**Empty-gap check:** the old banner's margin and the final-record row are gone from the CSS. The new highlights block sits directly under the hero with its own margin. Shot 2 confirms the layout with no highlights leaves no broken gap.

## Open questions for review

- Is the fourth FG line the right call, or should FG be a category that competes with the three core ones?
- Jersey as the final tiebreak versus alternatives such as total touches.
- Should Canadian football get highlights? It needs its own field confirmation first.
- A possible follow-up: the live operator scoreboard and the CSRN Game Statistics report are also FG-aware now only in the sense that distances are stored. They do not display distances yet. Flagged, not built, per scope.
