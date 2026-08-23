# CSRN Theme Development Continuity Handoff

Purpose: authoritative new-chat handoff for the Broadcast Layout Lab theme program.  
Prepared after approval of 8-Bit Gameday Gate 13.7 and its Gate 13.8 visual freeze.  
Repository: `CSRN-Production-Suite`  
Working branch: `gate6/final-visual-matrix`  
Expected HEAD during the theme-lab gates: `a97bef4fd72211c66b6899256cb0051cf8a3f796`

## Non-negotiable operating state

- The production overlay and OBS remain on Gate 6. Theme-lab work does not authorize production migration.
- Frozen visual packages may not be edited incidentally. A future change requires an explicit user-authorized unfreeze gate.
- Every theme must keep football, basketball, baseball, and softball structurally distinct.
- Highlight, sponsor, player, and broadcast modes replace only the theme-owned video opening. Captions remain inside that opening.
- Concept approval comes before implementation. Actual rendered screenshots must be reviewed before a visual freeze.
- Installers require exact source hashes, Chromium runtime validation, focused and full authoritative tests, and automatic hash-verified rollback.

## Completed packages

### 8-Bit Gameday — COMPLETE AND FROZEN

- Accepted visual baseline: Gate 13.7 R16.
- Authoritative visual freeze: Gate 13.8.
- Layout Lab route: `v=13.7`; package id: `pixel_gameday`.
- Visual language: premium unreleased 1980s sports video game, baseball-family pixel stadium cabinet, CRT wells, pixel environments, and central clash/video board.
- Generated graphics package includes a cabinet frame, four sport environments, and four sport-specific athlete masters.
- Athlete uniforms use runtime primary/secondary team-color compositing while preserving neutral gray/black shadows, fixed details, racial diversity, and jersey numbers where appropriate.
- Football: no timeouts and no play clock. Lower bank order is Clock, Quarter, Down, To Go, Possession, Ball On. Possession reads `HOME` or `VISITOR` using the frozen amber dot-matrix LED alphabet.
- Basketball: three-digit scores, enlarged fouls/bonus/timeouts, indoor court with no stadium-light treatment.
- Baseball and softball: separate athlete masters and environments, AT BAT/PITCHING name wells, R/H/E, count, inning, bases, and outs. Softball pitcher holds the ball in her hand and throws toward the batter; softball field has no dugouts.
- The scheduled date and structured special-game designation occupy the cabinet marquee.
- Eleven visual files are SHA-256 locked by `tests/test_gate138_eight_bit_gameday_visual_freeze.py`.

### Friday Night Stadium — COMPLETE AND FROZEN

- User shorthand may call this Friday Night Lights; canonical package name is Friday Night Stadium.
- Accepted visual baseline: Gate 12.5.
- Authoritative visual freeze: Gate 12.6.
- Layout Lab route: `v=12.6`.
- Protected renderer, stylesheet, silver lightning VS artwork, four athlete masters, and four sport environment plates.
- Uses professional layered athlete artwork with runtime team-color uniforms and retained painted shading/highlights.
- Football, basketball, baseball, and softball use separate scoreboard instruments and separate environments.
- Existing Gate 12.6 hash test remains authoritative. Do not alter Stadium files while working on another theme.

## Next theme work — approved direction

### 1. Heritage Press — COMPLETE AND FROZEN

Status: Gate 14.1 R5 is the accepted visual baseline and Gate 14.2 is the authoritative no-visual-change freeze. The historical label `Heritage Press — R2.3 dispatch implementation candidate` is superseded. Gate 14.0 R2 is installed and retained as the exact correction fallback. The shared-engine R1 fallback remains byte-for-byte available.

- The isolated package remains in `csrn-heritage-press-engine.js` and `.css`; it does not rewrite the shared renderer.
- The page uses a masthead, section headline, integrated score box, real-data editorial columns, transparent central live-video opening, Sports Wire footer, monochrome media, and generated newsprint texture.
- Football and basketball use the fact-bound right-column dispatch. Baseball and softball stack batter and pitcher roles on the left, reserve the right for the dispatch, and use an inning-by-inning line score.
- The final softball role assets are the exact approved full-body female engravings with transparent backgrounds, allowing the Heritage newsprint texture to show through. Baseball artwork remains unchanged.
- Highlight, sponsor, player, feature, and broadcast modes replace only the central opening. Captions stay inside that opening.
- A deterministic twelve-line period-inspired phrase library may add one compatible lively line. Articles use verified event fields or operator overrides; missing facts are omitted and inning data displays em dashes until the future stats engine supplies it.
- Gate 14.3 shared-catalog amendment retains an exact Heritage-owned ten-file visual hash freeze while protecting the shared Layout Lab registration semantically. No Heritage visual pixel changed.
- No production migration is authorized by the freeze.

### 2. Neon Sports Network — GATE 15.0 R1 CANDIDATE

Status: the user approved the revised concept and explicitly authorized the isolated Gate 15.0 R1 candidate. Gate 11.6 remains the exact fallback and is not overwritten.

Goal: use generated graphics framing/compositing to approach the previously approved Neon concept more faithfully than the current vector/CSS chassis.

- Recover and compare the approved concept against actual rendered screenshots.
- Determine which chassis, glass, light-channel, and environment elements should become protected graphics assets.
- Keep team-color lighting controlled and readable; neon bloom must not obscure scores, names, ticker, captions, or state.
- Preserve sport separation and three-digit basketball capacity.
- R1 uses new isolated renderer/style files, one protected frame, and four sport-specific clash plates. The frozen Gate 11.6 files remain untouched.

### 3. Remaining catalog

After Neon:

1. Collegiate — concept review, graphics strategy, sport separation, implementation, visual approval, freeze.
2. Classic — this is the canonical repository name for the user's “Class” reference; follow the same workflow.
3. Modern — reassess its existing accepted structure against the higher visual standard established by Stadium and 8-Bit.
4. Minimal — likely near its natural endpoint; prioritize disciplined spacing, typography, contrast, and data hierarchy rather than adding decorative graphics merely to make it busier.

## Proven workflow for every remaining theme

1. Inspect the current renderer, manifest, tests, and Project Bible contract.
2. Render all four sports and compare them with the previously approved concepts.
3. Produce revised concepts before implementation when fidelity is insufficient.
4. Decide the asset architecture: generated frame/environment plates, athlete masters, masks, live HTML/SVG/Canvas layers, and team-color ownership.
5. Obtain explicit visual approval.
6. Build an isolated renderer without changing frozen packages or Gate 6 production.
7. Validate the shared 192-case matrix, isolated sport/mode matrix, captions, contrast, clipping, asset loading, and screenshots.
8. Have the user install and visually inspect the real Layout Lab output.
9. Apply only approved cleanup corrections.
10. Freeze renderer, stylesheet, protected assets, route, tests, and Bible hashes with a no-visual-change gate.

## Immediate new-chat instruction

Gate 14.3 amends only the Heritage shared-catalog freeze boundary, with no visual change. Install and inspect the isolated Gate 15.0 Neon R1 candidate in the four-sport Layout Lab. Preserve Gate 11.6 as the exact fallback. Do not start production migration or alter Friday Night Stadium, 8-Bit Gameday, or Heritage Press.

## Gate 15.1 Neon R2 candidate

The user approved the R2 chassis and all four sport clash structures. R2 uses runtime-recolorable neon frame layers and uniform masks over neutral shading. Football removes Top Performers and adds the possession chevron/statistician field view. Baseball and softball use three bases and AT BAT. Basketball is approved unchanged. No production migration, commit, or push is authorized.

## Gate 14.3A shared Neon registration amendment

The Gate 14.3 shared-catalog test now protects Heritage exactly while permitting one active isolated Neon revision at a time. It no longer hard-codes the rejected R1 route names. Gate 15.1 R2 visual content is unchanged.

## Gate 15.0A R1 fallback-contract amendment

R1 remains preserved as isolated fallback evidence, but its route names are no longer required to remain active after an approved later Neon revision replaces it. Exactly one active Neon revision remains required.

## Gate 15.1 R10 transparent chassis rebuild

The failed opaque frame conversion is replaced with sparse transparent chassis, narrow left/right tube masks, controlled bloom, and explicit alpha-coverage tests. The approved Neon R2 design remains the target.

## Gate 15.1 R15 RGBA mask repair

Browser-incompatible grayscale masks are replaced by true RGBA alpha masks with transparent perimeters. The central clash artwork and frame now use an explicit safe stacking order.

## Gate 15.1 R16 glow repair

Dark raw team colors remain on athlete masks. Separate bright neon variables now drive the tube cores, bloom halos, initials, and score values.

## Gate 15.1 R17 football field-position module

The football lower chassis now contains an overhead field with neon ball spot and offensive direction. The feature is football-only. Basketball remains collapsed and diamond sports retain their information strip.

## Gate 15.1 R18 football field contract amendment

The R17 field-position module remains intact. The legacy statisticianMode compatibility hook is restored for existing state payloads and approval tests.

## Gate 15.1 R20 sport lower-deck correction

Football uses a brighter field, basketball a decorative court, and diamond sports a full inning scoreboard without IN THE HOLE. Lower geometry is contained inside the canvas and clash team color is substantially more visible.

## Gate 15.1 R21 glow contract amendment

The glow test now validates the intended raw-team-color versus bright-display-neon separation. R20 visual content is unchanged.

## Gate 15.1 R22 glow test file split

Raw color variables are tested in JavaScript and display-neon recolor rules in CSS. R20 visual content remains unchanged.

## Gate 15.1 R23 sport-data correction

Football numbers are larger/upright and clipping is reduced. Basketball now carries fouls, bonus, and possession. Diamond inning boards are simplified and raised. Nonfootball clash color is intensified.

## Gate 15.1 R24 stale-test amendment

Tests now match the R23 football, basketball, and diamond lower-deck geometry and the title-free inning board. Visual content is unchanged.

## Gate 15.1 R25 commercial lower assembly

The generic lower chassis is removed. Score and sport deck now form one bounded assembly. Football field, basketball court, and baseball/softball tables share fixed geometry. The next decision is visual approval or rejection; this gate does not freeze Neon.

## Gate 15.1 R26 commercial visual convergence

R26 resolves the football number-row implementation defect, restores the diamond base display, strengthens authored nonfootball recolor masks, and aligns the clash opening directly with the shared lower assembly. This remains a visual candidate, not a freeze.

## Gate 15.1 R27 approved clash integration

The four approved precolored clash scenes are now direct renderer assets. Runtime left/right player recolor masks are transparent and disabled to prevent corruption. This is a Layout Lab candidate only.

## Gate 15.1 R28 release layout correction

Diamond tables are full width and readable; player context is in team panels. Basketball removes possession and shot clock. Football uses a field image layer, larger ball-position marker, and non-neon end-zone logos. Baseball pitching mechanics are replaced without altering the other clash assets.

## Gate 15.1 R29 final sport corrections

Football field and typography are corrected. Full-opening highlight video is contracted. Basketball and softball remain locked to their R28 assets. Baseball alone receives the softball-composition male overhand pitcher correction.

## Gate 15.1 R30 baseball-only and field cleanup

Only baseball clash art changes. Other sport clashes remain hash-locked. Diamond side-panel text and football field rendering receive the requested cleanup.

## Gate 15.1 R31 baseball rerender and field alignment

Basketball remains locked. Baseball is replaced, softball changes only at the ball, football numbers are graphic-owned, and diamond text glow is removed.

## Gate 15.1 R32 swap and visual cleanup

Basketball and football clashes remain locked. Softball returns to the approved integrated-ball asset. The Lab now supports team swapping, with clash mirroring.

## Gate 15.1 R33 commercial art and color validation

Swap Teams now changes data only. Color-test controls drive the dynamic Neon chassis independently. Static football/baseball team marks are removed.

## Gate 15.1 R34 adaptive clash-color pipeline

Neon returns to the Standard B adaptive-art contract. Four neutral clash bases and eight constrained alpha masks are active. Color controls now affect the chassis and player uniforms. Friday Night Stadium remains a known adaptive-art retrofit gap.

## Gate 15.1 R35 football layered-color proof

Football is the sole layered proof sport. It uses primary, secondary, shadow, and highlight layers derived from one frozen geometry. No other sport is migrated by R35.

## Gate 15.1 R36 football alpha-cutout proof

Football now uses actual transparent garment openings over team-color planes. The smoke halo is separately authored and low-opacity. No other sport is migrated by this gate.

## Gate 15.1 R37 football luminance cap

Football alpha cutouts now use an opaque luminosity texture cap and stronger neutral detail exclusions. No other sport is migrated.

## Gate 15.1 R38 new-render exact-pixel football cutout

Football now uses a new purpose-rendered clash rather than the legacy colored image. Uniform checker pixels and team smoke pixels are the only recolorable openings.

## Gate 15.1 R39 neutral smoke texture cutout

Football smoke is now hue-neutral in every stored raster. Its only runtime color source is the home or visitor team-color variable. Dedicated luminance and texture overlays preserve wispy form.


Gate 15.1 R40 — Adaptive blacklight football clash opening installed as a Neon R2 candidate.
No production migration is authorized by this package.


Gate 15.1 R40A — Full-opacity player occlusion underlay prevents blacklight field lines from showing through the players. No production migration is authorized.


Gate 15.1 R40B — Removed the misaligned adaptive secondary uniform stripe masks from the Neon football clash. Primary uniform recoloring, player opacity, field glows, chassis, geometry, and other sports remain unchanged. No production migration is authorized by this package.


Gate 15.1 R40C — Removed the two baked molded center grooves from the ball-carrier and defender helmet shells across the neutral master, opaque occlusion underlay, luminance, shadow, and highlight layers. Helmet contours, facemasks, visors, team-color masks, field, chassis, geometry, and other sports remain unchanged. No production migration is authorized by this package.


Gate 15.1 R40D — Corrected the actual deployed helmet-center stripe coordinates on both football players. The stripe pixels were rebuilt across the neutral master, opaque underlay, luminance, shadow, and highlight layers. Uniform color masks, player silhouettes, facemasks, visors, field, chassis, geometry, and other sports remain unchanged. No production migration is authorized by this package.


Gate 15.1 R40E — Filled the transparent center gaps in the current R40A-hardened primary helmet masks. This prevents the neutral underlay from appearing as a contrasting helmet stripe. Secondary masks remain disabled. No other visual or runtime systems changed.


Gate 15.2 R41E — Installed adaptive basketball clash layers while preserving the frozen R40 version, manifest string, and Layout Lab cache contract required by existing authoritative tests. Includes full split-team neon court paint, rim/net glows, home-colored ball channels, exact player recoloring, and player occlusion. Football R40E, baseball, softball, chassis, and score modules remain unchanged.


## Gate 15.2 R41G continuity note
Basketball is now visually frozen at R41F. Continue Neon development with baseball next, then softball. Do not revisit basketball unless Jason explicitly authorizes an unfreeze.


Gate 15.3 R42A — Installed the accepted Neon softball template-driver stack as a supplemental renderer. The seven 1208×840 RGBA assets preserve the accepted V6 jersey masks and recolor only the home batter jersey and visible visitor catcher jersey fabric. The frozen football R40E and basketball R41G renderer files and assets remain unchanged. This gate is Layout Lab validation only; no production overlay migration, commit, or push is authorized.

## Gate 15.3 R43A continuity — Neon Baseball

Baseball now uses the approved V2 mask-correction package through `csrn-neon-baseball-r43-driver.js` and `.css`. Load order is frozen Neon R2 engine, Softball R42 supplemental driver, then Baseball R43 supplemental driver. Baseball and softball remain independent sport branches. The exact approved source ZIP is retained in the installer package. Football R40E and Basketball R41G remain frozen.

## Gate 15.3 R43B Current-State Neon Four-Sport Freeze

Neon is frozen in its currently accepted four-sport development state. Football, basketball, softball, baseball, their runtime drivers, Layout Lab integration, and supporting contracts are hash-protected. Visual cleanup before commercial release remains deferred. No commit, push, or production migration was performed by this gate.

## Gate 16.0 Production Overlay Resumption

Friday Night Stadium and Neon are frozen for now rather than commercially final. CSRN Cartoon is reserved as a future CSRN-exclusive theme. Modern remains in the commercial library. Theme work is paused while the project resumes production-overlay and operational integration. The next implementation must begin from the active overlay route and preserve all current theme freezes.
## Gate 16.1 R1 — Production Theme Integration Boundary Audit

- Compared the real OBS overlay loader with Layout Lab.
- Confirmed approved themes remain isolated from the production overlay.
- Established Gate 16.2 as a production-only theme host plus state-adapter slice.
- Frozen theme files remain untouched.
- Audit record: `CSRN_GATE161_PRODUCTION_THEME_INTEGRATION_BOUNDARY_AUDIT.md`.
## Gate 16.2 R1 — Production Theme Host and Adapter

- Added a production-only theme host beside the existing legacy overlay DOM.
- Added deterministic normalization for runtime and public theme state.
- Activation requires an explicit approved package identifier.
- Missing or invalid package state retains the legacy production overlay.
- Frozen theme engines and assets were not modified.
- This gate establishes the integration boundary only; approved engine rendering remains disabled pending Gate 16.3 validation.
## Gate 16.3 R2 — Isolated Theme Engine Readiness Probe

- Preserved the Gate 7 prohibition against loading Layout Lab engines in the live production overlay.
- Added an isolated static readiness page at `/static/csrn-production-theme-readiness.html`.
- The page loads approved engines by reference and reports browser globals and render entry points.
- It performs no polling, state mutation, theme activation, rendering, or production-overlay suppression.
- The live OBS route remains on the Gate 6 renderer.
- Frozen theme engines and visual assets were not modified.
## Gate 16.4 R1 — Selectable Production Template Menu

- Added a production-template selector to the existing Graphics Theme Manager.
- Menu choices: Legacy, Friday Night Stadium, 8-Bit Gameday, Heritage Press, and Neon.
- The staged selection persists in the operator browser.
- The interface explicitly marks the selection as not on air.
- No server state, OBS route, production renderer, or frozen theme asset is changed by this gate.
- Gate 16.5 will add authoritative persistence and production binding.
## Gate 16.5 R4 — Authoritative Production Template State

- Production-template state is implemented through the existing Phase 5 Blueprint route layer.
- No new endpoint is registered directly on `app.py`.
- The installer discovers the Blueprint that already owns `/api/themes/public-state` and reuses its existing authenticated POST-route decorator.
- Added authenticated `GET/POST /api/production-template` endpoints inside that Blueprint.
- Existing public theme state is enriched with the authoritative production-template identifier without adding a new public endpoint.
- Legacy remains the state fallback and production render binding remains disabled.
- Gate 7 production-overlay isolation remains intact.
## Gate 16.6 R1 — Production Render Binding

- Authoritative production-template selection now drives the OBS overlay.
- `templates/overlay.html` loads only a generic production-theme runtime; frozen Layout Lab engine filenames remain absent from the overlay template.
- The runtime dynamically loads the selected approved engine and invokes its established `renderPackage(target, packageId, sport, state, options)` contract.
- Menu aliases are translated through each loaded engine's authoritative `packageId` rather than duplicating frozen package identifiers.
- Runtime state is mapped onto the broadcast engine's own `defaultState()` contract.
- The themed package replaces only the legacy scorebug after a successful render; ticker, lower-third, player, personnel, sponsor, and event systems remain on the existing production path.
- Legacy scorebug remains automatic fallback for Legacy selection, invalid selection, load failure, or render failure.
- Production render binding is now reported as enabled.
- Frozen engine files and visual assets were not modified.
## Gate 16.6 R2 — Scorebug-Only Production Binding Correction

- Gate 16.6 R1 runtime behavior was visually rejected because the generic runtime passed the complete baseline scenario to `renderPackage()`, causing the selected theme's full package to render over production.
- Production binding is now explicitly constrained to `activeComponents: ["scorebug"]`.
- A successful render is rejected unless the engine reports exactly the `scorebug` component.
- Legacy `#scorebug` suppression now uses an explicit production-active root class plus `display:none!important` so existing overlay CSS cannot override the handoff.
- Deactivation clears the themed host and removes the suppression class, restoring Legacy immediately.
- Ticker, lower-third, player, personnel, sponsor, event, and all other production graphics remain on the legacy production path.
- Frozen theme engines and visual assets remain unchanged.
## Gate 16.7 R2 — Theme-Owned Live Ticker Binding

- The selected production theme now owns both the live scorebug and live ticker presentation.
- Friday Night Stadium, 8-Bit Gameday, and Neon render their frozen `ticker` component in a dedicated production ticker host.
- Heritage Press uses a production wrapper built from its frozen `hp-footer`, `hp-wire-title`, and `hp-wire-copy` classes because its frozen engine binds `ticker.text` inside the newspaper footer rather than exposing a standalone ticker component.
- Live ticker text is mapped from the production state into `state.ticker.text`.
- The legacy `#eventTicker` is suppressed only after both themed scorebug and themed ticker render successfully.
- Any selection/load/render failure removes both production-active classes, clears the theme hosts, and restores the legacy scorebug and ticker.
- Frozen engine files and visual assets were not modified.
- Heritage clash-screen concept remains a deferred enhancement; no Heritage clash asset is introduced by this gate.
## Gate 16.7 R4 — Live Event Ticker and Themed Player Correction

- The themed ticker now derives from the same authoritative `/api/state.events` collection as the legacy production ticker.
- Undone events are excluded; event description/label, team name, quarter, score snapshot, ticker speed, and ticker pause settings are honored.
- Theme ticker text is written into `state.ticker.text` before scorebug rendering.
- The runtime mounts a real scrolling track inside each theme's frozen ticker location: Friday Night Stadium LED strip, 8-Bit top marquee, Heritage Sports Wire, and Neon ticker.
- The separate Gate 16.7 ticker host is deprecated and no longer used.
- The legacy `#eventTicker` is suppressed only when the themed scrolling ticker is successfully mounted.
- A dedicated themed-player host was added.
- Friday Night Stadium, 8-Bit Gameday, and Heritage Press render their frozen `player` component from `/api/state.player_graphic` when that graphic is visible.
- The legacy `#playerGraphic` is suppressed only after a themed player component renders successfully.
- Neon does not expose a frozen player component and therefore intentionally retains the legacy player graphic until a Neon-specific player treatment is designed.
- Player Highlight remains a separate production graphic and is not migrated by this gate.
- Frozen theme engines and visual assets were not modified.
## Gate 16.7 R5 — Game-State Semantics Correction

- Production football period state now synchronizes `period`, `quarter`, and period-label aliases so `OT` cannot fall back to a frozen numeric fixture in approved themes.
- Clock visibility is authoritative. A hidden clock renders `-` instead of a frozen fixture clock.
- Down and Distance are independently authoritative.
- If Down is disabled/Off, the designed Down box displays `-`.
- If Distance is disabled/Off, the designed Distance/To-Go box displays `-`.
- If both are disabled, both structural boxes remain present and display `-`.
- `downDistance` is always explicitly populated from production values to prevent frozen defaults such as `3RD & 7` from leaking into production.
- The working live-event themed ticker and R4 themed-player behavior remain unchanged.
- Heritage-specific masthead, clash-screen, and visual corrections remain deferred for a single Heritage correction package.
- Frozen theme engines and visual assets were not modified.
## Gate 16.7 R8 — Deterministic Game-State Binding

- Gate 16.7 R7 proved that 8-Bit Gameday and Friday Night Stadium internally reduce football period to digits and default to quarter 2, and parse Down/Distance with a numeric-only regular expression that defaults to 3 and 7.
- R8 preserves the frozen engines and applies production-only post-render overrides to their structural CLOCK, QUARTER, DOWN, and TO GO cells.
- OT therefore displays as `OT` without modifying frozen engine source.
- Disabled Down and/or Distance display `-` in their existing boxes without modifying frozen engine source.
- Visible game clock derives from the production `clock`/`game_clock` value or authoritative `clock_seconds`; hidden clock displays `-`.
- Production `date` / `scheduled_start` is mapped to theme `scheduledDate` so the 8-Bit venue header no longer falls back to `TBD` when a date is available.
- 8-Bit and Friday Night player events now activate their existing integrated `videoMode: player` presentation inside the main themed board instead of attempting a nonexistent standalone `player` component.
- The legacy player card is suppressed only while that integrated player mode is active.
- The working live-event themed ticker remains unchanged.
- Heritage-specific visual corrections remain deferred to the consolidated Heritage correction package.
- Frozen theme engines and approved visual assets were not modified.
## Gate 16.7 R9 — Player Event Reliability

- 8-Bit Gameday and Friday Night Stadium continue to use their frozen integrated `videoMode: player` presentation.
- Player media is preflighted before render. A valid headshot is preferred; a valid team logo is the secondary fallback; otherwise the frozen theme's number-based player placeholder is used.
- Broken player-media URLs no longer intentionally reach the frozen player renderer. A post-render image error guard also replaces a failed player image with the player's number.
- A production `player-pending` state suppresses the legacy `#playerGraphic` before themed rendering completes, preventing the modern player card from flashing ahead of the themed presentation.
- Player activation identity includes `player_graphic.updated_at`, `expires_at`, player identity, and the latest active event identity so a subsequent event can re-arm player mode even when it involves the same player.
- Undo/inactive player state clears both pending and active player suppression and returns the themed board to clash mode on the next render.
- Player Highlight remains explicitly outside this gate.
- Date, OT, clock, Down/Distance, ticker, and other Gate 16.7 R8 behavior are not changed.
- Frozen engines and approved visual assets were not modified.
## Gate 16.7 R10 — Player Transition Continuity

- The approved themed player presentation from Gate 16.7 R9 is unchanged.
- When themed player mode becomes pending, all legacy `#playerGraphic` Web Animations, CSS transitions, and CSS animations are cancelled before the themed presentation is rendered.
- The legacy player card is forced fully hidden during both themed-player pending and active ownership so no slide-in or slide-out remnant can cross the themed board.
- Before themed ownership is released, the legacy card is synchronously placed at its normal `hidden` endpoint with motion disabled.
- Its normal legacy transition/animation properties are restored only after the themed pending/active classes are gone and the hidden endpoint has been committed.
- This prevents the modern player card from appearing during either the incoming or outgoing themed-player handoff.
- Player media fallback, player-event re-arm behavior, date, OT, clock, Down/Distance, ticker, and all other R8/R9 behavior are preserved.
- Player Highlight remains outside this gate.
- Frozen engines and approved visual assets were not modified.
## Gate 16.7 R11 — Player Presentation Legibility

- The integrated themed player presentation from Gates 16.7 R9/R10 remains structurally and behaviorally unchanged.
- Production-only CSS increases the `PLAYER SPOTLIGHT` label, player name, and play-detail text for broadcast readability.
- Player name is increased to 34 px; play detail to 20 px; spotlight label to 18 px.
- Text wrapping width is expanded without changing the existing portrait proportions or main themed-board geometry.
- Number-placeholder fallback is enlarged for better readability when no usable player image or team logo exists.
- Player duration/timing remains controlled by the existing production player-graphic system.
- Player transition suppression, media fallback, Undo/re-arm behavior, date, OT, clock, Down/Distance, and ticker behavior are preserved.
- Player Highlight remains outside this gate.
- Frozen engines and approved visual assets were not modified.
## Gate 16.7 R12 — Player Text Scale

- The Gate 16.7 R11 integrated player presentation text is increased by approximately 75 percent at the user's request.
- Production-only CSS now renders the spotlight label at 32 px, player name at 60 px, and play-detail line at 35 px.
- Player text wrapping allowance is expanded while preserving portrait geometry and the main themed-board structure.
- Number-placeholder fallback is enlarged to 96 px.
- Player event lifecycle, duration, media fallback, transition continuity, date, OT, clock, Down/Distance, and ticker behavior are unchanged.
- Manual Show/Update failures for Player Spotlight, Player Highlight, and Sponsor Spotlight are recorded as a separate functional follow-up and are not modified by this visual-only gate.
- Frozen engines and approved visual assets were not modified.
## Gate 16.7 R13 — Player Text Scale iPhone Follow-up

- The integrated production player presentation receives a second legibility pass for small-screen and iPhone viewing.
- Player Spotlight label is increased to 44 px.
- Player name is increased to 86 px.
- Play-detail line is increased to 52 px.
- Number placeholder fallback is increased to 116 px.
- This gate is visual-only and does not change player-event timing, ticker behavior, OT/date/clock binding, or manual Show/Update channel behavior.
## Gate 16.7 R14 — Player Text Selector Correction

- R11-R13 typography overrides targeted the Friday Night-specific player replacement selector and therefore did not reliably reach the 8-Bit integrated player presentation.
- R14 targets the shared `[data-video-mode="player"]` contract used by the frozen themed player presentation.
- Intended iPhone-scale typography remains 44 px spotlight label, 86 px player name, and 52 px play detail.
- No player-event behavior, timing, transition logic, image fallback, ticker, OT/date/clock, or manual Show/Update channel behavior is changed.
## Gate 16.7 R15 — Player Text Final Tuning

- The corrected shared `[data-video-mode="player"]` selector from R14 remains authoritative.
- Player typography is reduced approximately 30 percent from R14 after visual review.
- Production player spotlight label is 31 px.
- Player name is 60 px.
- Play detail is 36 px.
- Number-placeholder fallback is 82 px.
- No player-event lifecycle, duration, transition, media fallback, ticker, OT/date/clock, Down/Distance, or manual spotlight channel behavior is changed.
- Manual Show/Update failures for Player Spotlight, Player Highlight, and Sponsor Spotlight remain the next functional audit target.
## Gate 16.7 R17 — Manual Spotlight Show/Update Bridge

- Gate 16.7 R16 confirmed that Player Spotlight, Player Highlight, and Sponsor Spotlight are independent primary graphic channels with valid authenticated routes and persisted visible/expiry state.
- Program Visual Player Spotlight Show/Update now explicitly posts `action: show` and `visible: true` to `/api/graphics/player` so the service cannot interpret an update-only payload as hidden.
- Player Spotlight continues to use the selected production theme's integrated player presentation where supported.
- Player Highlight and Sponsor Spotlight continue using their existing validated legacy overlay presentations for this bridge gate.
- While a production theme is active, visible `#playerHighlight` and `#sponsorSpotlight` are elevated above the themed board so Show/Update can actually be seen.
- The graphics service remains authoritative for primary-channel arbitration: activating one primary graphic hides the other primary channels.
- No fake themed Player Highlight or Sponsor Spotlight component was introduced.
- The eventual themed visual treatment of Player Highlight and Sponsor Spotlight remains a separate design/integration task.
- Frozen theme engines and approved visual assets were not modified.
## Gate 16.7 R18 R2 — Superseded Contract Correction

- R18 R1 correctly introduced native multi-mode central video-board ownership for Player Highlight and Sponsor Spotlight.
- R18 R1 failed focused validation because inherited R8-R17 tests still required the older player-only `videoMode:playerModeFor(...)` contract and prohibited runtime access to manual highlight/sponsor state.
- R18 R2 explicitly supersedes those stale assertions with the new `themeVideoModeFor` / `activeVideoMode` contract.
- Historical player transition, player fallback, typography, game-state, and explicit Player Spotlight activation protections remain tested.
- All test files modified by this installer are included in the rollback set.
- Runtime behavior is otherwise unchanged from R18 R1.
## Gate 16.7 R19 — Central Video-Board Media Polish

- Player Highlight now replaces the entire central video-board content opening with the selected video rather than retaining frozen placeholder copy beside a nested media box.
- Highlight video uses full board width and height with contain scaling and autoplay-safe muted playback.
- Sponsor Spotlight now uses a production-owned central-board composition with larger theme-appropriate typography.
- Sponsor media fallback order is selected media, sponsor logo, then text-only sponsor identity; failed media cannot intentionally leave a broken image.
- Player Spotlight, ticker, scores, date, OT, clock, and other R18 behavior remain unchanged.
- Frozen theme engines and approved visual assets were not modified.
## Gate 16.7 R20 — Central Video-Board Boundary Correction

- Gate 16.7 R19 proved highlight media playback but mounted 8-Bit production media too broadly, covering the full themed composition.
- The approved 8-Bit media boundary is the physical central video-board opening only.
- 8-Bit Highlight and Sponsor now mount into a dedicated production overlay constrained to that center-board geometry.
- The themed ticker, date panel, visitor/home score towers, and bottom clock/quarter/down/to-go/possession/ball-on instruments remain visible.
- Highlight video uses `object-fit: contain` inside the bounded center board.
- Sponsor Spotlight uses the same bounded board while retaining the R19 media/logo/text fallback chain and production typography.
- Friday Night Stadium retains its existing native theme host behavior in this gate; R20's geometry correction is specific to the visually verified 8-Bit board.
- Frozen theme engines and approved visual assets were not modified.
## Gate 16.7 R21 — Central Board Layer Ownership + Sponsor Scale

- R20 established the correct 8-Bit center-board geometry, but visual testing showed the production media overlay was not reliably winning the frozen engine's internal stacking order.
- R21 applies the approved center-board geometry directly to the production overlay at runtime and raises that bounded overlay above the frozen center-board content.
- The overlay remains constrained to left 22.5%, top 23.5%, width 55%, height 57.5%.
- Highlight video remains `object-fit: contain` inside that exact boundary.
- Sponsor Spotlight uses the same bounded production layer.
- Sponsor lead-in and caption are increased to 44 px; sponsor name to 84 px, approximately 45 percent larger than the prior R20 targets.
- Sponsor copy is explicitly centered horizontally and vertically.
- R19 sponsor media -> logo -> text-only fallback behavior is retained.
- Ticker, date panel, side score towers, and bottom game-state instruments remain outside the production media layer.
- Frozen theme engines and approved visual assets were not modified.
## Gate 16.7 R23 — Native 8-Bit Video-Board Binding

- Gate 16.7 R22 proved the frozen 8-Bit center-board owner is `.bl-8bit-video-board` inside `.bl-8bit-main-display`.
- The frozen engine inserts the active `clash`, `highlight`, `sponsor`, `player`, or `broadcast` mode directly inside that native video-board section.
- R23 removes the R20/R21 percentage-positioned production overlay approach from active runtime behavior.
- For 8-Bit Highlight and Sponsor, production now locates `.bl-8bit-video-board` and populates its existing direct `[data-video-mode]` child.
- Highlight replaces the native `VIDEO` placeholder and title/detail children with the actual highlight video inside the exact frozen video-board geometry.
- Sponsor replaces the native sponsor placeholder contents in the same mode element, preserving media -> logo -> text fallback.
- Sponsor lead-in/caption remain 44 px and sponsor name 84 px, centered using the 8-Bit Courier-style typography.
- Highlight/Sponsor production mode transitions are neutralized on the native mode node to prevent legacy transition remnants.
- Player Spotlight remains on its existing proven native player mode.
- Frozen theme engines, frozen engine CSS, approved assets, ticker, date panel, team towers, and bottom game-state instruments were not modified.
## Gate 16.8 R2 — Native Friday Night Stadium Production Binding

- Gate 16.8 R1 proved Friday Night Stadium uses `.bl-fns-video-board` as its native center media host.
- The active `clash`, `highlight`, `sponsor`, `player`, or `broadcast` element is a direct child of that native board.
- Gate 16.8 R2 extends the accepted Gate 16.7 R23 native-host architecture to Friday Night Stadium.
- Production Highlight and Sponsor now populate the existing Friday Night mode element rather than relying on generic or secondary overlay geometry.
- Highlight video remains `object-fit: contain` inside the native board.
- Sponsor media/logo/text fallback remains intact and centered.
- Highlight and Sponsor transition/animation transforms are neutralized only on the active native media mode.
- Existing shared Player Spotlight typography and fallback behavior remain unchanged.
- Existing theme-owned ticker and production game-state binding remain unchanged.
- Frozen Friday Night engine JS/CSS and approved visual assets were not modified.
## Gate 16.8 R3 — Production Identity Authority + Strict Native Media Host

- Selected-game identity is now authoritative for the production theme runtime.
- The runtime consumes the actual broadcast identity schema: `broadcast_name`, `official_name`, mascot/nickname, primary/secondary colors, certified/generated logo, and school ID.
- `home_team` / `visitor_team`, school IDs, full identity objects, venue, and venue ID are included in the render signature so changing the selected matchup forces an immediate theme rerender even when scores and clock are unchanged.
- Venue data is preserved in normalized production theme state.
- 8-Bit and Friday Night Highlight/Sponsor media are fail-closed to their audited native hosts: `.bl-8bit-video-board` and `.bl-fns-video-board`.
- The audited stadium themes cannot fall through to a broad outer `[data-video-mode]` target.
- Legacy full-screen `#playerHighlight` and `#sponsorSpotlight` layers are suppressed by both runtime enforcement and CSS while the theme owns Highlight/Sponsor presentation.
- Suppression is enforced on every production-state poll, including unchanged render signatures.
- Existing 8-Bit and Friday Night ticker, game-state, OT, Player Spotlight, and cabinet behavior remain unchanged.
- Frozen 8-Bit/Friday Night engine JS/CSS and approved visual assets were not modified.
- Clash player recoloring remains deferred.
## Gate 16.9 R2 — Heritage Native Production Binding + Clash Foundation

- Gate 16.9 R1 proved Heritage Press is a full-page newspaper engine with a native `.hp-opening` story/media region.
- Highlight production media now mounts only inside `.hp-highlight-window[data-module="video.board"]`.
- Sponsor production media now owns only the native `.hp-sponsor-feature[data-video-mode="sponsor"]` opening.
- Heritage Player Spotlight is promoted to the accepted integrated player path.
- Football OT, clock visibility, and Down/Distance state receive the same production-authoritative override semantics used by accepted themes.
- Selected-game identity continues to use the Gate 16.8 R3 production authority path.
- The Sports Wire remains theme-owned through `.hp-wire-copy` and the existing live-event ticker feed.
- Football neutral/broadcast mode now uses the native `.hp-live-opening` as a Heritage clash foundation with live team marks and names.
- The foundation reserves the center artwork layer for the approved black-and-white leather-helmet newspaper engraving in a later visual gate.
- The clash foundation is football-only; basketball/baseball/softball remain on their frozen Heritage broadcast opening pending separate visual authorization.
- Frozen Heritage engine JS/CSS and approved Heritage visual assets were not modified.
## Gate 16.9 R3 — Heritage Native Spotlight Ownership + Newspaper Media Finish

- Heritage Player Spotlight now repopulates and owns the native player opening after every render, eliminating the transient flash/drop behavior.
- Player imagery is grayscale with a restrained press treatment.
- Highlight video remains in the native Heritage highlight frame and is grayscale for newspaper continuity.
- Sponsor artwork remains full color while the surrounding frame, typography, rules, and paper treatment remain Heritage-native.
- Legacy player/highlight/sponsor layers are suppressed whenever Heritage-native modes own presentation.
- Existing selected-game identity, Sports Wire, OT/game-state behavior, and clash foundation are preserved.
- Frozen Heritage engine JS/CSS and approved assets were not modified.
## Gate 16.9 R4 — Heritage Native Spotlight Ownership + Newspaper Media Finish

- Heritage Player Spotlight now repopulates and owns the native player opening after every render, eliminating the transient flash/drop behavior.
- Player imagery is grayscale with a restrained press treatment.
- Highlight video remains in the native Heritage highlight frame and is grayscale for newspaper continuity.
- Sponsor artwork remains full color while the surrounding frame, typography, rules, and paper treatment remain Heritage-native.
- Legacy player/highlight/sponsor layers are suppressed whenever Heritage-native modes own presentation.
- Existing selected-game identity, Sports Wire, OT/game-state behavior, and clash foundation are preserved.
- Frozen Heritage engine JS/CSS and approved assets were not modified.
## Gate 16.9 R6 — Heritage Standard Neutral Clash Build

- The prior logo-driven Heritage clash direction is rejected and superseded.
- Heritage football clash now uses one reusable neutral black-and-white leather-helmet football illustration for every school.
- No team logo, mascot artwork, helmet mark, or school-specific image is used in the clash.
- Visitor/home identity is communicated entirely through live team name, mascot, record, and role typography.
- The clash remains inside the native `.hp-live-opening[data-video-mode="broadcast"]` Heritage story region.
- Venue metadata remains live-bound when available.
- Accepted Heritage Player Spotlight, Sponsor, Highlight, Sports Wire, score/game-state, and selected-game identity behavior are unchanged.
- Frozen Heritage engine JS/CSS remain untouched.
## Gate 16.9 R6 R2 — Heritage Full Video-Box Clash Build

- The prior logo-driven and text-heavy Heritage clash directions are rejected and superseded.
- Heritage football clash now uses one reusable neutral black-and-white leather-helmet football illustration as a full-frame plate inside the video box.
- No team logo, mascot artwork, helmet mark, or school-specific image is used in the clash.
- Visitor/home identity is no longer rendered inside the clash; the surrounding Heritage newspaper rails already carry matchup information.
- The clash remains inside the native `.hp-live-opening[data-video-mode="broadcast"]` Heritage story region.
- No interior venue or matchup copy is rendered inside the clash plate.
- Accepted Heritage Player Spotlight, Sponsor, Highlight, Sports Wire, score/game-state, and selected-game identity behavior are unchanged.
- Frozen Heritage engine JS/CSS remain untouched.
## Gate 16.9 R6 R4 — Heritage Clash Matches Player Highlight Frame

- Heritage Clash no longer maintains independent media geometry.
- The neutral clash artwork is mounted inside the exact accepted Heritage Player Highlight media-frame classes: `hp-highlight-window`, `csrn-production-native-video-mode`, and `csrn-production-heritage-highlight-window`.
- The clash image also inherits the accepted `csrn-production-highlight-video` media contract, with a clash-specific `object-fit: cover` override.
- No team names, logos, records, captions, or venue copy are rendered inside the clash.
- The Gridiron Dispatch / surrounding Heritage newspaper rails continue to carry matchup information.
- Accepted Player Spotlight, Sponsor, Highlight, Sports Wire, and game-state behavior are unchanged.
- Frozen Heritage engine JS/CSS remain untouched.
## Gate 16.9 R7 — Heritage Highlight Grayscale Finish

- Heritage Player Highlight video is now forced to black-and-white in the browser with CSS `grayscale(100%)` and a restrained `contrast(1.05)` adjustment.
- The change is scoped to the Heritage Press highlight window only.
- No video transcoding, duplicated media, codec changes, or source-file conversion is required.
- Heritage Clash, Player Spotlight, Sponsor, Sports Wire, game state, and frozen Heritage engine files are unchanged.
## Gate 16.9 R8 — Heritage Newsprint Media Tone Finish

- Heritage Player Spotlight image, Player Highlight video, and neutral Clash artwork now use a common paper-toned newsprint treatment.
- Media is converted in-browser with grayscale plus restrained sepia/contrast/brightness and `mix-blend-mode: multiply` against the Heritage paper background.
- The result preserves dark ink while shifting white/light regions toward the page's cream newsprint color instead of hard digital white.
- Player Highlight still requires no transcoding, media duplication, or codec changes.
- Sponsor artwork remains full color and normal blend.
- Clash geometry, Player Spotlight layout, Sponsor geometry, Sports Wire, score/game state, and frozen Heritage engine files are unchanged.
## Gate 16.9 R9 — Heritage Readability Finish

- Increased Gridiron Dispatch editorial copy size and line height for better readability in OBS preview and Facebook/mobile playback.
- Increased Sports Wire title, ticker copy, and page-id text size while preserving the approved Heritage newspaper structure.
- Preserved the approved Heritage clash frame, spotlight layout, sponsor layout, and R8 newsprint media tone.
- No frozen engine files, geometry foundations, or non-Heritage themes were changed.
## Gate 17.0 R1 R2 — 8-Bit Dynamic Clash Production Binding

- The frozen 8-Bit football clash renderer remains the visual source of truth; no replacement clash artwork was introduced.
- Production now explicitly preserves 8-Bit `clash` as the native idle/default center-board mode.
- The existing frozen 8-Bit material recoloring continues to bind the visitor player to visitor team colors and the home player to home team colors from the selected broadcast identity.
- Highlight, Sponsor, and Player modes continue to temporarily own the native center board and return to Clash when dismissed.
- Production runtime does not duplicate or mutate the frozen 8-Bit `paintClash` / material-decomposition implementation.
- No frozen 8-Bit engine or asset files were modified.
- R2 supersedes the stale Heritage Gate 16.9 R2 ternary-expression assertion with the equivalent explicit per-theme default-mode contract.
## Gate 17.0 R1 R3 — 8-Bit Athlete Asset Path Fix

- Corrected the production-only URL resolution mismatch for frozen 8-Bit JavaScript athlete image loads.
- Document-relative 8bit-gameday/... image URLs are normalized to Flask's /static/8bit-gameday/... tree by the generic production runtime.
- Frozen 8-Bit engine code, recolor masks/thresholds, geometry, and canonical athlete art remain unchanged.
- Canonical football, basketball, baseball, and softball athlete PNGs are guarded and recovered only if absent.
## Gate 17.0 R2 — 8-Bit Lower Data Readability Polish

- Increased the production 8-Bit football Clock value from 44 px to 66 px and Quarter/Down/To Go values from 38 px to 57 px.
- Tightened the production LED glow to improve crispness after OBS and social-media compression.
- Possession, Ball On, team scores, dynamic clash players/recoloring, athlete asset routing, frozen engine geometry, and other themes are unchanged.
## Gate 17.1 R1 — Friday Night Stadium Dynamic Clash Production Ready

- Production now waits for the frozen Friday Night Stadium dynamic clash render to finish before accepting the clash board.
- The native football athlete canvas must report art-ready and continue using the frozen visitor/home primary-color recolor pipeline.
- Existing football keyed-athlete, field-background, and VS assets are required but are not modified.
- Highlight, Sponsor, Player Spotlight, ticker, scorebug, and game-state geometry remain unchanged.
## Gate 17.1 R2 R2 — Friday Night Layered Dynamic Clash Players

- Replaces the production-visible keyed cyan/magenta uniform recolor result with a production-owned layered compositor while preserving the frozen Friday Night Stadium engine and geometry.
- Football clash athletes are decomposed into neutral anatomical/equipment detail, visitor/home primary uniform masks, visitor/home secondary helmet masks, and a shared grayscale uniform texture layer.
- Visitor and home primary and secondary team colors are applied only through the masks, then neutral texture/detail is restored so fabric contours and lighting remain intact.
- Highlight, Sponsor, Player Spotlight, ticker, scorebug, field background, VS mark, team labels, and frozen Stadium engine files are unchanged.
## Gate 17.1 R3 — Friday Night Uniform Detail Polish

- Preserves the production-owned layered Friday Night clash compositor while enhancing the secondary-color masks with visible trim detail.
- Adds secondary-color shoulder/sleeve stripes, pant striping, and generic jersey-number treatment to reduce the flat solid-color look.
- Keeps the frozen Friday Night Stadium engine, geometry, field background, and clash host unchanged.
- Advances runtime binding to v40 and cache pins to 17.1-r3 so the refreshed layer assets are loaded.
## Gate 17.1 R4 — Friday Night Integrated Uniform Detail Polish

- Preserves the production-owned layered Friday Night clash compositor while refining the secondary-color trim so it reads as part of the fabric rather than a pasted decal.
- Narrows and softens the generic jersey numbers and stripe accents, and slightly reduces trim intensity for better visual integration at Facebook/mobile viewing sizes.
- Keeps the frozen Friday Night Stadium engine, geometry, field background, and clash host unchanged.
- Advances runtime binding to v41 and cache pins to 17.1-r4 so the refreshed layered assets are loaded.
## Gate 17.1 R5 — Friday Night Perspective Uniform Remap

- Preserves the production-owned layered Friday Night clash compositor while remapping the secondary-color trim to more natural shoulder, chest, and side-seam locations.
- Re-centers the generic jersey numbers and differentiates visitor and home accent placement so both uniforms feel intentionally designed instead of identically templated.
- Keeps the frozen Friday Night Stadium engine, geometry, field background, and clash host unchanged.
- Advances runtime binding to v42 and cache pins to 17.1-r5 so the refreshed layered assets are loaded.
## Gate 17.1 R6 — Friday Night Reference Placement Rebuild

- Rebuilds Friday Night secondary-detail placement from the supplied football-uniform references: sleeve/shoulder bands, true outer pant seams, and chest-centered numbers.
- Uses different visitor and home stripe layouts so the two players no longer look like the same template recolored twice.
- Keeps the frozen Friday Night Stadium engine, geometry, field background, and clash host unchanged.
- Advances runtime binding to v43 and cache pins to 17.1-r6 so the refreshed layered assets are loaded.
## Gate 17.1 R7 — Friday Night Clean Layered Visual Rollback

- Restores the accepted Gate 17.1 R2 clean layered football player masks and compositor presentation.
- Removes the R3-R6 stripe/number visual experiments while preserving the later production binding, asset loading, and native media ownership work.
- Keeps the frozen Friday Night Stadium engine, geometry, field background, VS treatment, and other production media modes unchanged.
- Advances runtime binding to v44 and cache pins to 17.1-r7 to force the restored visual assets to reload.
