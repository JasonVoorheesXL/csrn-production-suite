# Layout Builder P1 — guided customization

**Round:** `layout-builder-p1-20260919`, worktree
`C:/Users/Darth/CSRN-RoundWork/CSRN-Prod-layoutp1`, off `main` (`ae1393c`).
Follows P0 (`docs/LAYOUT_BUILDER_RECONCILIATION.md` §8). P0 shipped the data
model and a read-only runtime hook with no editing UI; two live bugs found in
its 2026-09-14 smoke test had been reverted rather than shipped. P1 fixes
both, then builds the guided editor on top. **Not** freeform drag-and-drop
(that is P2).

Everything below was checked in a real browser against an isolated app
instance, on all four selectable board themes (Friday Night Stadium, 8-Bit
Gameday, Heritage Press, Collegiate Traditional). `tools/layout_builder_smoke.js`
is that smoke test made repeatable.

## Part A — the two P0 stubs

### A1. sponsor_slot / spotlight_zone / video_zone visibility

The sponsor / player / highlight video-board modes **replace** the board's
content in the theme markup, so hiding their host leaves a blank hole. The fix
is upstream, as P0's note said:

- `layoutMaskedRuntimeR1()` turns a layout-hidden element's trigger inert
  (`sponsor_slot`→`sponsor_spotlight`, `spotlight_zone`→`player_graphic`,
  `video_zone`→`player_highlight`). `themeVideoModeFor()` masks first, so the
  mode falls through in the same order (highlight > sponsor > player) to the
  theme's idle board. `renderSelected()` masks once at the seam, so the
  pending/fallback flags, the render signature (mode change still forces a full
  rebuild) and media mounting all agree. No layouts → the same object comes
  back: the default preset is byte-for-byte the old behaviour.
- **Found live, not in the P0 note:** once the mode fell through, the *legacy*
  overlay (`overlay.html`) released its own highlight card and it appeared on
  top of the themed board — `overlay.html` only suppresses a legacy node while
  the themed mode owns that content. `syncLayoutSuppressionR1()` + three CSS
  rules keep the matching legacy node hidden while the layout hides the element.
- `applyLayoutOverrides()` deliberately does **not** re-add DOM `display:none`
  of mode hosts (the brief said to re-enable DOM hiding): with mode selection
  fixed there is no hidden-mode host left to blank, and re-adding it would
  recreate the blank-hole bug.

### A2. score_box placement

Measured live: in every board theme the bonded `data-component="scorebug"` node
is the theme's **whole full-canvas board** (FNS/8-Bit 1888×958, Heritage
1840×1032, Collegiate 1840×1000 — scoreboard + video board + rails; Heritage and
Collegiate also carry the ticker), absolutely laid out in px. Resizing that box
crushes it. What works, with no per-theme code, is a uniform
`transform: translate() scale()` of the node, computed from its own `offset*`
box (unaffected by transforms → idempotent every poll). The zone/rect is a box
to **fit into**, never upscaled, aligned by zone name.

**Legibility floor (0.5).** The engine's compact zones (top-left, bottom-center,
…) would need scale ≈0.25 (6 px text at 1080p). Below 0.5 the placement is
refused — the board stays where the theme put it and the node is marked
`data-csrn-layout-score-box="too-small"`. In practice only `center` (≈0.52–0.54)
and `full-safe` (≈0.97–1.0) and explicit rects pass, which is what the builder
offers ("Theme default / Fit to safe area / Centered, reduced size").

**Not done — a true corner scorebug.** Themes ship one big-board design per
sport; a compact strip variant would be new per-theme × per-sport markup, a
separate and much larger piece of work.

### B0. Ticker placement made reversible (found while building on it)

P0's `setNodeZonePxR0()` wrote the inline box with no undo, so removing or
changing an override left the ticker stranded (live: after clearing, FNS ticker
kept `top:30px;height:280px` instead of `top:20px;height:62px`), and it
stretched the 62 px bar to the zone's 245–280 px height. Replaced by
`applyTickerPlacementR1()`: remembers the inline box before the first write and
restores it verbatim; the zone gives x + width, the bar keeps its own height and
aligns to the zone's top/bottom. `applyLayoutOverrides()` now always calls the
visibility/placement setters (a null override means "visible, unplaced"), so
deleting an override also un-hides. Live preset switching needs both.

## Part B — the builder

`/layouts` (linked from the Command Center's theme card; `@require_auth`).

- **Presets:** stored presets (the P0 model already supported names), "Use on
  air", duplicate, rename, delete (`default` is permanent), and five curated
  starters — *Theme as designed*, *No ticker*, *Centered board*, *Scoreboard
  only*, *No sponsors*.
- **Editing:** per scene (In game / Pregame / Halftime), per element, with
  **Applies to: All sports** or a sport family (football, basketball, baseball,
  softball). A sport's override replaces the All-sports one for that element
  (`resolve_override`'s existing order); the sport view shows what is inherited
  and lets the owner opt an element out.
- **Placement pickers** use `window.CSRNBroadcastLayoutEngine.zones` for the
  ticker; the scoreboard offers only the sizes that stay legible (A2).
- **Only live controls are offered.** `layout_builder_service.LIVE_CONTROLS` is
  the single source and tests pin each entry to the consumer that implements it:

| Scene | Element | Display | Placement | Implemented by |
|---|---|---|---|---|
| In game | Scoreboard | ✓ | zone (center / full-safe / rect) | `applyScoreBoxPlacementR1` |
| In game | Ticker | ✓ | zone / rect (FNS, 8-Bit only) | `applyTickerPlacementR1` |
| In game | Sponsor / Player spotlight / Highlight video | ✓ | fixed | `themeVideoModeFor` (A1) |
| Pregame | Sponsor, Background | ✓ | fixed | `pregame_universal_overlay.html` |
| Halftime | Sponsor, Player spotlight, Background | ✓ | fixed | `pregame_universal_overlay.html` |

`clock_period`, `game_fields`, `logo` stay schema-only (no addressable node in
the themes yet); `game_fields`/spotlight/video *positions* stay fixed, as the
reconciliation doc's P1 boundary table said.

### Write path and live vs restart

`POST /api/layouts` validates the **whole** document with
`sanitize_layouts_document()` (strict: unknown scene/family/element/field,
element not valid in a scene such as `background` in-game, bad types, rects off
the canvas, bad names, >12 presets, missing `default`, `active` not a preset →
400 with every error, nothing saved) and canonicalizes it (empty overrides
dropped, so an untouched document round-trips to the same bytes). This is the
first writer of the identity profile's `layouts` section:
`save_layouts_document()` does a read-modify-write of `identity_profile.json`
(other sections preserved; a Configuration Manager save does not wipe layouts —
tested), rebinds `IDENTITY_PROFILE`, and invalidates the runtime-state cache.

**Decision: a save is live — no restart.** The production overlay polls
`/api/runtime-state` (which serves `IDENTITY_PROFILE["layouts"]` on every poll)
and the pregame/halftime payload is built per request, so a change reaches an
already-open overlay within one poll (≈0.3–0.9 s). Verified: overlay tab left
open and never reloaded; Save in the builder hid the ticker, then swapping
presets restored it and centered the board, then moved the ticker to
bottom-center, all within a poll or two. P0's "requires restart" note no longer
applies.

## Known gaps and behaviour worth knowing

- **Themed packages only.** The classic (legacy) overlay has no layout hook; the
  builder edits the document regardless. The page states this per scene.
- **Ticker placement** only takes effect on Friday Night Stadium and 8-Bit
  Gameday (the themes with an isolated ticker component); Heritage / Collegiate
  keep their built-in ticker position (verified clean no-op). Ticker
  *visibility* works everywhere.
- **Neon** (`digital_neon`) is hidden from selection and fails to bind even on
  trunk; it also never stamps `data-component`, so score_box overrides no-op.
- An unparseable `identity_profile.json` silently falls back to the Caledonia
  seed (pre-existing; noticed, not changed).
- The builder shows no live preview; the header links open the real overlays.
  A scaled preview would be a natural P2 companion to freeform placement.

## Re-running the smoke test

Select a theme, open `/overlay` at 1920×1080 in an isolated instance, paste
`tools/layout_builder_smoke.js`, then `await __matrix(idle)`,
`await __placementMatrix()`, `await __tickerMatrix()` — every line must start
`PASS`. Run it on all four themes after any change to `applyLayoutOverrides`,
`themeVideoModeFor`, `layoutMaskedRuntimeR1` or `syncLayoutSuppressionR1`.
