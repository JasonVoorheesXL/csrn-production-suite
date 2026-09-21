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
- ~~**Neon** (`digital_neon`) is hidden from selection, fails to bind, and never stamps
  `data-component`.~~ **Closed by the Neon redesign** (`docs/NEON_REDESIGN.md`): Neon now
  renders through the shared engine, so `applyRect()` stamps it, and it is selectable
  again. The in-game matrix and score_box placement matrix pass on all four sports.
- ~~An unparseable `identity_profile.json` silently falls back to the Caledonia
  seed.~~ **Closed in P2 (Part B, below):** still survivable, no longer silent.
- ~~The builder shows no live preview.~~ **Closed in P2 (Part A, below):** the
  builder previews the real overlay with your unsaved edits.
- **Still open:** Freeform drag-and-drop placement (the real P2 of
  the original plan) and a compact corner scorebug are untouched.
- **Preview limits (P2):** it previews the *loaded game's* sport, so an edit under
  another sport's scope is not visible until such a game is loaded (the page says
  so); the in-game preview forces the scorebug on so the board is visible even
  when the operator has not switched it on yet.

## Re-running the smoke test

Select a theme, open `/overlay` at 1920×1080 in an isolated instance, paste
`tools/layout_builder_smoke.js`, then `await __matrix(idle)`,
`await __placementMatrix()`, `await __tickerMatrix()` — every line must start
`PASS`. Run it on all four themes after any change to `applyLayoutOverrides`,
`themeVideoModeFor`, `layoutMaskedRuntimeR1` or `syncLayoutSuppressionR1`.

---

# P2 — live preview and an honest fallback

Round `layout-builder-p2-20260920`, worktree `CSRN-Prod-layoutp2`, off `main`
(`fbb7b2a`). Closes two of P1's three gaps; Neon is deliberately a separate
effort.

## Part A — a real rendered preview

### The decision: real overlay in an iframe, not a schematic

Investigated first. The high-fidelity option is workable *and* can be made
strictly safer than the server-side "preview channel" the brief sketched, so it
was built; the schematic (zone boxes over a placeholder) was not needed.

The builder embeds `/overlay?layout_preview=1` (or `/pregame-overlay?...`,
following the scene tab) in a same-origin iframe and `postMessage`s the working
document into it. `static/csrn-layout-preview.js`, running inside that iframe,
wraps `fetch()` so the overlay's own reads of `/api/runtime-state` and
`/api/pregame-presentation` come back with the preview document merged in (and,
optionally, forced sponsor / player card / highlight triggers, so a hide/show is
visible without firing one live). **The edit never leaves the browser tab.** There
is no server-side preview state at all, so there is nothing that could reach the
saved `layouts` document, the runtime-state cache, or another operator's or OBS's
overlay. That is stronger than a query-param honoured by the server, which would
have needed per-request scoping to be safe.

### Why it is inert to everything live (each is tested)

1. The routes include the shim only when the request itself has
   `?layout_preview=1`. The real `/overlay` and `/pregame-overlay` responses are
   byte-identical to before (asserted), so OBS's page does not even reference it.
2. The shim does nothing unless the page is embedded **and** asked for; it accepts
   messages only from its own parent, same origin, and posts only to its own origin.
3. **It blocks every non-GET request the embedded overlay makes.** This was found
   by reading what the overlay does: `overlay.html` POSTs `/api/overlay-health`
   (a process-wide singleton, unauthenticated, last writer wins). An unblocked
   preview would have masqueraded as the OBS overlay in the operator's
   overlay-health signal and could mask a real outage. Verified live: with only
   the preview running, the server's overlay-health timestamp did not move and the
   preview's own POST returned `{"preview": true, "blocked": ...}`.
4. Everything the overlays load has no other write channel (no XHR / WebSocket /
   EventSource / `sendBeacon`; asserted), and `sendBeacon` is a no-op anyway.

Nothing in the preview path writes the saved document or invalidates the
runtime-state cache; only **Save** does (unchanged from P1).

### Behaviour

- Preview panel above the scene tabs: **Show** toggle, forced-trigger toggles (in
  game only), a status line naming the preset being previewed and the loaded game's
  sport, and warnings when the preview cannot show an edit (classic theme has no
  layout hook; editing a sport other than the loaded game's).
- It previews the preset **being edited**, not just the one on air.
- Pregame/halftime: the shim forces the scene being edited (`settings.mode`,
  `broadcast_phase`) and serves the ~1.7 s payload from a short-lived copy of the
  real response, re-applied on every poll, so an edit shows in ~1.8 s instead of ~4.
- The transparent overlay backdrop shows as a checkerboard (needs `color-scheme:
  light` on the iframe, otherwise the browser paints it opaque white).

### A P1 defect the preview exposed (fixed, A0)

With the scorebug on and stats present, the legacy `#statBar` is normally covered
by the themed ticker; hiding the ticker exposed it. P1's live checks missed it
because the isolated instance had the scorebug off. Fixed with the same pattern as
A1's legacy suppression (`csrn-production-layout-hide-ticker` + CSS).

### Live verification (real browser, isolated instance, FNS)

Live overlay open in one tab, builder in another: edit board→centered and
ticker→hidden ⇒ preview changes, live overlay and saved document do **not**; Save
⇒ live overlay changes within a poll. Sponsor forced + sponsor hidden ⇒ idle
board, no legacy leak; highlight forced ⇒ highlight. Pregame and halftime scenes
reflect unsaved edits (background transparent; halftime view; forced-scene
phase). Health-signal test above.

## Part B — an unusable `identity_profile.json` is loud, not silent

`load_identity_profile()` still never raises — this runs live broadcasts, and a
startup crash on a corrupted file is worse than a fallback. What changed:

- **Logged** at ERROR (`csrn.identity`) with the path, kind (unreadable / invalid
  JSON with line and column / invalid UTF-8 / top level not an object), size, which
  seed is now in use ("existing-install seed (Caledonia values)" or blank), and
  where a copy was kept. Once per distinct problem, not once per load.
- **The bad file is kept aside** as `identity_profile.json.corrupt-<hash>` (now
  gitignored): a later Configuration Manager save would otherwise overwrite it
  with the fallback.
- **Surfaced where the operator already looks:** `/api/diagnostics` gains
  `identity_profile {ok, path, issue}` (Command Center Diagnostics panel shows an
  "Identity profile" row, red when unusable), and `/api/readiness` gains a failing
  "Identity profile" check **only when there is a problem** (healthy payloads are
  unchanged), which flows into the Release Readiness gate.
- **Reports what the running app is using.** `app.IDENTITY_PROFILE_ISSUE` is
  captured when `IDENTITY_PROFILE` is bound (startup, onboarding, the builder's
  save), so fixing the file on disk does not turn diagnostics green until the app
  is actually running on it (other code re-reads the file at runtime and would
  otherwise clear a file-level flag; there is a test for that trap).
- A UTF-8 BOM is now accepted (it used to trigger the silent fallback for a valid
  file saved by a Windows editor).
- Scope kept to `identity_profile.json`; a malformed `layouts` *section* inside a
  valid profile keeps the P0 default-layouts behaviour.

Live-verified: a profile with a trailing comma → startup ERROR line, diagnostics
and readiness report it (line 3, column 30, backup path, fallback), and the
Command Center panel shows the red row first.
