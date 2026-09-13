# Video-mode support

Source spec: `CSRN_VIDEO_MODE_BUILD_PROMPT.md` (owner-authored, untracked at
the repo root at the time this was built — see this doc's own history note
below). Shipped concretely on Collegiate Tech; the mechanism itself is
generic and cross-theme.

## The architecture decision

**CSRN does not ingest video.** No `getUserMedia`, no capture-card-as-webcam,
no RTMP/WebRTC/`<video>` tag pulling a live camera feed into the browser
page. The camera/program feed stays entirely inside the broadcast software
(OBS or whatever the truck runs) — CSRN's job is to render its normal
graphics with a transparent hole where the video shows through, exactly the
way `obs_service.py`/`obs_client.py` already treat OBS: something CSRN
remotely controls, never a video source CSRN pulls frames from.

Because CSRN never touches the video itself, different themes can have
different video-window sizes/positions with no video ever flowing through
CSRN's renderer — the compositing tool (OBS) is what actually places the
camera there. The cost of that split is alignment: the operator's OBS scene
has to know where each theme's transparent window is. Two mitigations:

1. A **calibration guide mode** (below) that swaps the true-transparent hole
   for a highly visible guide box with its pixel rect labeled on screen.
2. **This document** — the written per-theme rect, so an operator can build
   an OBS scene from scratch without launching the guide first.

## The three broadcast-level fields

All three are plain, live-mutable fields on the game state (`app.py`
`DEFAULT_STATE`, `game_operations_service.py` `ALLOWED_SET_FIELDS`, same as
`scorebug_visible`/`ticker_visible`/`visual_mode`) — settable via
`POST /api/set` at any point in a broadcast, on or off, same as every other
broadcast-level display toggle. `False` (off) is the default for every
existing broadcast, so nothing changes until an operator turns one on.

| Field | Purpose |
| --- | --- |
| `video_mode` | Turns the theme's designated video-board region transparent instead of its normal idle "clash" art. An active Program Visual graphic (Player Spotlight, Sponsor Spotlight, Player Highlight) still renders opaquely over the window regardless — only the *idle* clash fallback is affected. |
| `sidebars_hidden` | Independent of `video_mode` — collapses the theme's player/stat side rails so the video-board region can go full width. Kept as its own flag on purpose: video-mode-on-with-sidebars-still-visible is a valid, supported combination. |
| `video_calibration_guide` | Swaps real transparency for a highly visible guide box (magenta/black stripes) with its live-measured pixel rect labeled on screen, for OBS scene alignment. Only meaningful when `video_mode` is on. |

Top and bottom scorebug overlays (the score/clock bar, the bottom control
bank) are never affected by any of these three fields, on any theme —
verified by test (`test_video_mode_support.py`).

### Naming note — two different "video modes"

The codebase already had an unrelated `videoMode` concept before this
feature: the per-component dispatch parameter (`highlight`/`sponsor`/
`player`/`clash`) that decides what's currently showing in a theme's video
board (`csrn-production-theme-runtime.js`'s `polledVideoMode`, threaded
through `renderPackage`/`componentFrame`/`collegiateStage`). To avoid a
second, confusing meaning for the same identifier, this feature's own state
is named distinctly throughout the JS: `state.videoWindowActive`,
`state.sidebarsHidden`, `state.videoCalibrationGuide` — never `videoMode`.
(One coincidental collision survives from before this feature: the
diagnostic label array `CSRN_SIGNATURE_FIELDS_R4` already had a `"video_mode"`
entry at the position that actually corresponds to the *other* concept,
`polledVideoMode` — discovered, not introduced, while wiring this in. See
the code comment there.)

## Collegiate Tech: the shipped implementation

- **Video window**: the idle "clash" fallback
  (`collegiateVideoBoardContent()` in `static/csrn-broadcast-layout-engine.js`,
  the pinned engine) returns a transparent `.bl-college-video-window` div
  instead of `collegiateClashStage()`'s VS lockup whenever
  `state.videoWindowActive` is true. `collegiateStage()` also strips the
  stage's own opaque background/border/field-art for that same state
  (`.bl-college-stage-video-active`), so the window sits on a truly clean
  transparent stage, not a transparent div over an opaque backdrop.
- **Sidebar hide**: a shared `collegiateMainDisplay()` helper (called
  identically by both `collegiateFootballScorebug()` and
  `collegiateBaseballScorebug()`) omits both `.bl-college-team` rail panels
  and switches `.bl-college-main-display`'s CSS grid from
  `330px minmax(0,1fr) 330px` to a single `minmax(0,1fr)` column when
  `state.sidebarsHidden` is true — the video-board region actually reflows
  into the freed width, rather than leaving two blank 330px gutters.
- **Calibration guide**: `.bl-college-video-window-guide` (magenta/black
  diagonal stripes) with a `.bl-college-video-window-label` filled in by
  `patchVideoWindowGuide()` in the *unpinned* `csrn-production-theme-runtime.js`
  — a live `getBoundingClientRect()` measurement belongs in the mutable
  runtime, not the SHA-256-pinned engine, which only declares the guide's
  markup/class.

### Measured video-window rect (reference resolution 1920×1080)

Measured live in a running browser (not hand-computed from CSS — see the
calibration guide screenshots taken during this feature's own verification),
football, Collegiate Tech:

| Sidebars | Position (x, y) | Size (w × h) |
| --- | --- | --- |
| Visible (default) | `(414, 222)` | `1091 × 527` |
| Hidden (`sidebars_hidden: true`) | `(72, 222)` | `1775 × 527` |

These are the numbers to give an operator sizing an OBS camera source
against Collegiate Tech's board without launching the calibration guide
first. If the engine's layout ever changes, re-measure with the guide
rather than trusting this table blindly — it's a snapshot, not a contract
the way `docs/DIAMOND_OVERLAY_CONTRACT.md`'s wire fields are.

Baseball/softball share the exact same `.bl-college-stage`/
`collegiateMainDisplay()` mechanism (already built structurally in T1), so
`video_mode`/`sidebars_hidden`/`video_calibration_guide` work identically
for those sports on Collegiate Tech — not separately re-verified pixel-by-
pixel this round, but no sport-specific branching exists in any of the
new code to make them behave differently.

## Other themes

The three fields exist on every broadcast regardless of theme (`app.py`
`DEFAULT_STATE`), and the operator-facing toggle buttons
(`templates/index.html`, "Video Mode" panel) are always visible. Friday
Night Stadium, 8-Bit Gameday, and Heritage Press have **no video-window
geometry declared** yet — toggling `video_mode` for a broadcast on one of
those themes is currently inert (no `.bl-*-video-window` exists for them to
render into). Adding one is a per-theme follow-up, not a redesign: declare
that theme's own video-board region's transparent-state CSS/markup the same
way Collegiate Tech's was added here.

## Explicitly out of scope this round

- Actually ingesting or displaying any video inside CSRN itself — stays
  entirely OBS's job.
- Baseball/basketball-specific video-board work beyond what Collegiate
  Tech's existing shared mechanism already covers for baseball/softball.
  Basketball has no Collegiate Tech video-board region at all yet
  (pre-dates this feature, unrelated to it).
- Any new OBS-side automation (auto-sizing an OBS source via the websocket
  API) — the calibration guide is a manual-alignment aid, not automatic
  scene setup.

## Investigation findings this build started from

Before writing any code, the actual current behavior was confirmed (not
assumed from the memory/docs trail):

1. **Collegiate football's clash screen did not already go transparent under
   any mode.** A prior attempt (`c083aba`, "Phase C R8 item 2") was built
   and then explicitly reverted (`0774642`, "Phase C R9") on the owner's own
   call, folded into "T1" instead — but T1 (`abecadd`/`15f5363`/`648b1e3`)
   only shipped structural parity (scoreboard/diamond layout, rail content),
   never the transparency behavior. Confirmed by diff inspection of both
   commits and a full re-grep of the shipped code: no transparency logic
   existed anywhere for any theme prior to this feature.
2. **`video_mode` was genuinely inert plumbing** before this feature — the
   only prior reference anywhere in the codebase was a diagnostic label
   name coincidentally reusing the string (see the naming note above); the
   actual `runtime.video_mode` field was read nowhere.
3. **The player/stat side rail lives in `.bl-college-rail`**
   (`collegiateTeamPanel()`), and the parent grid
   (`.bl-college-main-display{grid-template-columns:330px minmax(0,1fr) 330px}`)
   does **not** reflow on its own when the rails are hidden — the grid
   template itself has to change, which is exactly what `sidebars_hidden`'s
   implementation does (see above). Confirmed by inspecting the CSS grid
   definition directly, not assumed.
4. **Baseball/softball already had the full `.bl-college-stage` video-board
   region** (T1 gave `collegiateStage()`/`collegiateTeamPanel()` a `sport`
   parameter and per-sport ballpark backgrounds) — this feature's mechanism
   applies to them with zero extra code. Basketball has no Collegiate Tech
   support of any kind and isn't relevant this round (no engine yet).
