# Layout Builder — reconciliation pass + finalized Phase 0 kickoff

**Round:** `layout-builder-reconciliation-20260907`, worktree
`C:/Users/Darth/CSRN-RoundWork/CSRN-Prod-layoutbuilder`, off `64ed45a`.
**Doc only — no code.** Confirms the persisted "Layout Builder" plan still
holds against Round 26 (field geometry), Round 27 (sport-context /
gateway) and Phase C (per-theme sport dispatch + video-board contract),
resolves whether Phase 0 waits for the post-Friday trunk merge, and
delivers the finalized Phase 0 kickoff prompt (§7).

---

## 0. Source spec — recovered

The persisted plan only ever existed as an artifact from an earlier
session (never a file — hence absent from the checkout, memory store and
Drive). Full content, reproduced so this doc is self-contained:

> **Purpose.** Let customers rearrange their own scorebug / pregame /
> halftime overlays — position, size, toggle, re-skin — without touching
> code. **Presentation-layer only**; the data engine (event tracking,
> stats, spotlight logic) is completely untouched.
>
> **Scope — one system, three scenes:**
> - **In-Game:** home/visitor score, clock & period, down & distance
>   (sport-dependent), ticker/scorebug style, sponsor slot, spotlight
>   pop-in zone, video pop-in zone.
> - **Pregame:** matchup/logos, venue & weather, storylines text, sponsor
>   rotation, background image.
> - **Halftime:** score carry-over, spotlight rotation (reused from 1st
>   half, no new capture logic), sponsor rotation, background image.
>
> **Architecture — layout / content / style as three independent layers
> composing at render time:**
> - **Layout** (where + how big): per-scene position, size, visibility,
>   z-order, cycle timing for every element. *"New — currently implicit in
>   template markup."*
> - **Content** (the data engine): scores, stats, spotlight triggers.
>   Already exists, untouched by this project.
> - **Style** (colors + skin): theme palette, fonts, logo, background
>   image. Partially exists via the theme system; extends to arbitrary
>   customer colors / uploads.
> - **Video note:** OBS composites the live camera under a transparent
>   browser overlay, unchanged. The Builder only lets the customer
>   position/size the transparent scorebug region over whatever OBS shows
>   beneath — no video ingestion is built into CSRN. A literal background
>   image (pregame/halftime, or no-live-feed operators) is rendered
>   directly by the page — ordinary, low-complexity.
>
> **Element inventory** (element / scenes / behavior / notes):
> - `score_box` — in-game — static — home + visitor independently placeable
> - `clock_period` — in-game — static — often docked near score, not required
> - `down_distance` — in-game — static — field set varies by sport
> - `ticker` — in-game — rotating — style choice (incl. Basic Scorebug) lives here, not in layout
> - `sponsor_slot` — in-game/pregame/halftime — persistent or on-call — per-scene choice of behavior, not just position
> - `spotlight_zone` — in-game/halftime — triggered/rotating — halftime reuses 1st-half history
> - `video_zone` — in-game — triggered — position/size only, playback source unchanged
> - `logo` — in-game/pregame/halftime — static — customer upload from the Identity Profile
> - `background` — pregame/halftime — static — image only
>
> **Delivery — three phases:**
> - **P0 Foundation** (shared plumbing): formalize the layout/content/style
>   data model; layouts save into the customer's Identity Profile alongside
>   branding; **no customer-visible UI yet**.
> - **P1 Guided customization** (ship-blocking target): curated preset
>   positions/sizes per element, per-element on/off toggles, color pickers
>   against the existing theme system, logo/background upload. **No
>   freeform dragging or collision handling.**
> - **P2 Freeform builder** (post-launch, demand-driven): drag anywhere,
>   live WYSIWYG, real canvas-editor engineering.
>
> **Open questions from the original spec:**
> 1. One saved layout per customer, or named presets switchable mid-season
>    (e.g. a "senior night" look)?
> 2. `down_distance`'s sport-dependent field set — flagged against a
>    "Round 6 rules-engine proposal." **[Now resolved — see §5.]**
> 3. Preset boundaries for P1 — which positions/sizes to offer vs leave
>    fixed. **[First pass in §6; still needs a decision.]**
> 4. Resolution handling — one broadcast resolution, or account for
>    variation from the start? **[Still open — §6.]**

---

## 1. Current implementation at `64ed45a` — the spec is *mostly already built*

### 1.1 In-Game scene → `csrn-broadcast-layout-engine.js` + `csrn-production-theme-runtime.js`

`static/csrn-broadcast-layout-engine.js` (v1.7.0, **SHA-256 frozen** by
`test_gate116` + cross-refs `test_gate12/13/14`) already contains the
"Layout" layer the spec calls *"new — currently implicit in template
markup"*:

| Primitive | What it is | Spec layer |
| --- | --- | --- |
| `PACKAGE_MANIFESTS` | Per-theme manifest: `scorebugRenderer`, `componentRendererFamily`, `styleClass`, `sports` → per-sport **zone** profiles. | Layout + Style |
| `zone(name)` / `componentSize()` / `fitInZone()` / `rectsOverlap()` | Geometric **zone-placement system** on a fixed 1920×1080 canvas, coords as `%`. | Layout |
| `resolvePlacements(manifest, sport, activeComponents)` | The solver: theme + sport + component list → non-overlapping placements (or throws). | Layout |
| `PRESENTATION_SCENARIOS` | `baseline` = `["scorebug","ticker"]`, plus `captions` / `player` / `highlight` / `sponsor` / `feature`. | **In-Game component-set states** (not the spec's "scenes" — see §2) |
| `SPORT_CONTRACTS` | Per-sport `{required, gameFields, preferredScorebugZones}` for football / basketball / baseball / softball. | Content contract, sport-resolved |
| `SPORT_STATE_CONTRACTS` + `BASEBALL_FUTURE_COMPONENTS` | State-value enums + declared future components (`lineup`, `atBat`, `onDeck`, … `lineScore`). | Content contract |
| `csrn-production-theme-runtime.js` (Phase C, **not** frozen) | `productionSportFamily()`, per-family `mergeRuntimeState` blocks, `applyBoardOverrides` dispatch, the **video-board contract** (`nativeVideoBoardHost` → `data-module="video.board"` / `[data-video-mode]` per theme). | Content + Layout binding |
| `theme_service.py` + `templates/theme_manager.html` | Theme palette / skin management service + UI. | **Style** |
| `identity_service.py` + `identity_profile.json` | Per-customer org branding: `organization.{name, logo_path, primary/secondary/accent_color}`, `broadcast_defaults.{theme, sport, …}`. | **Style + the spec's chosen layout home** |

### 1.2 Pregame + Halftime scenes → `pregame_presentation.py` + `pregame_universal_overlay.html`

The spec's Pregame and Halftime scenes are a **different overlay
subsystem** from In-Game:

- `pregame_presentation.py` — a Flask blueprint + `Data/Runtime/pregame_presentation.json`
  state, driving `templates/pregame_universal_overlay.html`.
- Already has `_halftime_spotlights()` (**"real spotlight moments from the
  first half, for the halftime rotation"** — the spec's "reused from 1st
  half, no new capture logic" is *already implemented*) and
  `_halftime_sponsors()`.
- Weather (`_NWS_CACHE`), "Next Matchup" matchup card, storylines — all
  already there.

**Implication:** "one system, three scenes" spans **two existing overlay
codebases**. The Layout Builder's data model has to be the unifying layer
over both — the In-Game engine and the pregame/halftime presentation
module — not a new renderer.

### 1.3 Net: Phase 0 is "formalize + expose", not greenfield

Layout primitives: exist (frozen engine). Style: exists (theme +
identity). Content: exists, untouched (per spec). Halftime spotlight
reuse: exists. What's genuinely missing is a **single serializable
layout/content/style document per customer**, stored in the Identity
Profile, that both overlay subsystems read. That is P0.

---

## 2. Scenes vs `PRESENTATION_SCENARIOS` — orthogonal, both kept

| Spec "scene" | = | Engine concept |
| --- | --- | --- |
| **In-Game** | ⊃ | *all six* `PRESENTATION_SCENARIOS` (`baseline` / `captions` / `player` / `highlight` / `sponsor` / `feature`) — these are **component-set states within the In-Game scene**: which of `spotlight_zone` / `video_zone` / `sponsor_slot` / `captions` is currently popped in. |
| **Pregame** | = | `pregame_universal_overlay.html` render mode (no engine `PRESENTATION_SCENARIOS` equivalent). |
| **Halftime** | = | `pregame_universal_overlay.html` render mode with `_halftime_*` data sources. |

**Resolution:** the Builder's `scene` axis = **broadcast phase**
(In-Game / Pregame / Halftime). The engine's `PRESENTATION_SCENARIOS`
become the In-Game scene's **trigger states** — the layout document
stores, per In-Game element, a `behavior` (`static` / `rotating` /
`triggered`) and, for triggered elements, which scenario activates them.
Nothing about `PRESENTATION_SCENARIOS` changes; the layout doc just names
them.

---

## 3. Round 26 / 27 / Phase C deltas that change the spec

### 3.1 Round 26 — field geometry
`collegiateField()` (frozen engine) + `.bl-college-field-grid` CSS now
drive field length/end-zone from ruleset vars (`--csrn-ez` /
`--csrn-yl-count` / `--csrn-hash-count`). **Impact:** the `down_distance`
element's *field graphic geometry* is ruleset-owned; the Builder's Style
layer may re-skin it (colors, opacity) but must not set geometry. Minor —
one line in the element's editable-property list.

### 3.2 Round 27 — sport-context / gateway → **layouts are per-family**
`sport_families.py`: `base_family()` collapses `canadian_football →
football`; session carries `sport_context`; roster/sponsor scoping keys
off `base_family`. **Impact (significant):**
- A saved layout is scoped to a **`base_family`** (or `"all"`), exactly
  like rosters/sponsors. `canadian_football` and `football` **share one
  layout pool**.
- `sport_context` values with no engine (hockey, lacrosse, …) have no
  layout target yet — the Builder hides them / shows "coming soon",
  matching the gateway.
- The Identity Profile `layouts` section is therefore
  `layouts[scene][base_family]`, with a `"default"` family key for the
  all-sports fallback.

### 3.3 Phase C — per-family game fields + the video-board contract
- **`down_distance` is family-resolved.** `productionSportFamily(sport)` +
  `SPORT_CONTRACTS.*.gameFields` decide the field set (see §5).
- **`video_zone` IS an editable element (spec), and it IS the Phase C
  video-board contract region.** Correcting the earlier draft of this doc:
  the Builder **does** let the customer position/size `video_zone` (per the
  element inventory) — but the underlying markup must keep its
  `data-module="video.board"` + `[data-video-mode]` attributes so
  `nativeVideoBoardHost()` still resolves it and a future feed still
  composites there. The Builder **moves the region; it never strips the
  contract or deletes the region.** In-Game `video_zone` on/off toggles its
  *visibility*, not its existence in the DOM contract.
- Any Builder code in `csrn-production-theme-runtime.js` contends with
  Phase C's branch (unpinned, additive, but a coordination point — §4).

---

## 4. Phase 0 file scope — **self-contained; runs parallel to the engine builds**

The recovered spec settles the decision branch from the earlier draft:
**P0 = "formalize the data model + save into the Identity Profile + no
customer-visible UI."** That shape touches:

| File | Frozen? | Contended by | P0 touches it? |
| --- | --- | --- | --- |
| `csrn-broadcast-layout-engine.js` / `.css` | **SHA-256** | R26 (+re-pin), Phase C T1 (+re-pin) | **No.** P0 *reads* `PACKAGE_MANIFESTS` / `resolvePlacements` / `SPORT_CONTRACTS`; it does not edit them. **Zero re-pin.** |
| `csrn-production-theme-runtime.js` / `.css` | not frozen | Phase C owns it | **Yes — additively** (a resolve-and-apply hook). The one coordination point. |
| `identity_service.py` + `identity_profile.json` schema | not frozen | nobody | **Yes** — new `layouts` section. Clean. |
| `pregame_presentation.py` | not frozen | nobody | **Yes — additively** (read the layout doc for pregame/halftime element placement). Clean. |
| new `layout_builder_service.py` | — | nobody | **Yes.** Clean. |
| `templates/index.html` | not frozen | R26, R27 | **No — P0 has no UI.** (P1 adds `templates/_layout_builder.html`, a partial.) |
| `phase5_architecture.py` (`EXPECTED_BLUEPRINTS`) | — | R27 (+1) | **Maybe +1** if P0 adds a read-only API blueprint. Trivial. |

**Conclusions:**
- **No frozen-file edit. No SHA-256 re-pin.** (Unlike the sport engines,
  which all re-pin nothing either, but unlike T1 which does.)
- **P0 shares no files with the baseball / basketball / hockey engines**
  (`sport_families`, `ruleset_service`, `engine_router`, `*_game_routes`,
  `game_operations_service` — none of them). So Layout Builder P0 is **not
  on the engine build-sequence chain** (baseball → basketball → hockey,
  baseball scoping plan §9.4) — it can run **in parallel with baseball P0**
  once the trunk merge lands.
- The **only** pre-merge blocker is the additive hook in
  `csrn-production-theme-runtime.js` (Phase C's file). So: **P0 starts
  right after the R26+R27+Phase C merge** — no earlier, but no need to wait
  behind the engines. The data-model + Identity-Profile-schema work could
  technically begin pre-merge, but there's no schedule pressure (P1 is the
  ship-blocker, not P0) and starting post-merge avoids a rebase.

---

## 5. Field-by-field reconciliation

### 5.1 Element inventory → current implementation → deltas → P0 action

| Spec element | Current implementation at `64ed45a` | R26/R27/Phase C delta | P0 data-model action |
| --- | --- | --- | --- |
| **`score_box`** (home + visitor **independently placeable**) | The engine renders home & visitor score **inside one `scorebug` component** per theme; they are *not* independently placeable today. | — | **Gap.** The layout doc must model `score_home` and `score_visitor` as two placeable elements. P0 defines the schema; actually splitting the render is a P1/theme-runtime concern (the runtime can position two sub-nodes of the scorebug). Flag: some themes bond the two scores graphically (single cabinet) — those may only support "paired" placement even in P2. |
| **`clock_period`** (often docked near score, not required) | `game.state` component (clock + period) in the scorebug. `on/off` = drop from `activeComponents`. | Phase C: period label is family-resolved (`productionFootballPeriod` vs inning half vs quarter). | Model `clock_period` with `visible` + `dock` (`with_score` / `standalone`) + a zone ref for standalone. |
| **`down_distance`** (field set **varies by sport**) | Rendered by `SCOREBUG_RENDERERS` per theme; field content from `SPORT_CONTRACTS.<sport>.gameFields`. | **Phase C + `SPORT_CONTRACTS` resolve the old "Round 6 rules-engine" open question.** `productionSportFamily(sport)` → `football`: `["period","clock","downDistance","playClock","possession"]`; `baseball`/`softball`: `["inning","inningHalf","balls","strikes","outs","bases","pitcherName","batterName","batterPosition"]`; `basketball`: `["period","clock","shotClock","homeFouls","visitorFouls","possession"]`. `BASEBALL_FUTURE_COMPONENTS` + `SPORT_STATE_CONTRACTS` declare the rest. | **Model as `game_fields`, a *family-resolved* element**, not "down_distance". Its content = `SPORT_CONTRACTS[base_family].gameFields`; hockey/soccer declared-but-empty (populated when those engines land). Geometry stays ruleset-owned (§3.1). |
| **`ticker`** (style choice incl. "Basic Scorebug" lives **here**) | `ticker` component; the theme/package (`production_template_package_id`, read by `renderSelected`) is the skin. "Basic Scorebug" = the `legacy` package path. | Phase C: `PACKAGE_ALIASES` + `productionSportFamily` gate; "Modern Network" = `legacy`. | Model `ticker` with `visible`, `behavior: rotating`, `speed`, and **`skin` = the package/theme selection** (this is where Style's "skin" choice is surfaced per the spec — one element carries it). Reconcile `skin` values with `PACKAGE_ALIASES` + `legacy`. |
| **`sponsor_slot`** (per-scene **behavior** choice: persistent / on-call) | `sponsor` component; in-game via `PRESENTATION_SCENARIOS.sponsor`; pregame/halftime via `pregame_presentation._halftime_sponsors()` etc. | R27: sponsors now carry a `sport` field (Round 27 sponsor scoping). | Model `sponsor_slot` **per scene**: `{visible, behavior: persistent|on_call, zone, rotation_seconds}`. In-Game `on_call` binds to `PRESENTATION_SCENARIOS.sponsor`. |
| **`spotlight_zone`** (triggered / rotating; halftime reuses 1st-half history) | In-Game: `playerCard` component via `PRESENTATION_SCENARIOS.player` / `feature`; the theme runtime's player-spotlight path. Halftime: `pregame_presentation._halftime_spotlights()` — **already reuses first-half moments.** | Phase C: video-board contract + player-card placement per theme; `csrn-heritage-player-*` etc. | Model `spotlight_zone` per scene: In-Game `{visible, zone, behavior: triggered}`; Halftime `{visible, zone, behavior: rotating, rotation_seconds}` sourcing `_halftime_spotlights()`. No new capture logic (spec). |
| **`video_zone`** (position/size only; playback source unchanged) | The Phase C **video-board contract** region: `nativeVideoBoardHost()` → `.bl-fns-video-board` / `.bl-8bit-video-board` / `.bl-college-stage` / Heritage `.hp-opening`, carrying `data-module="video.board"` + `[data-video-mode]`. OBS composites the camera *under* the transparent overlay (spec's video note = exactly Phase C's model). | Phase C commits 7–8 + T1 "transparent-for-video": the region clears to transparent when a feed mounts. | Model `video_zone` as `{visible, zone}` **with the contract preserved** — the Builder writes a zone override; the theme runtime keeps emitting `data-module="video.board"` / `[data-video-mode]` on the (re-positioned) node. The Builder **cannot delete the region or strip its attributes**; `visible:false` hides, not removes. |
| **`logo`** (customer upload from the Identity Profile) | `identity_profile.json` → `organization.logo_path`; rendered in scorebug/pregame/halftime identity blocks. | — | Model `logo` per scene: `{visible, zone, size}`; source stays `identity_profile.organization.logo_path`. |
| **`background`** (pregame/halftime only; image) | `pregame_universal_overlay.html` supports a background; no In-Game background (transparent for OBS — spec confirms). | — | Model `background` for Pregame + Halftime scenes only: `{visible, image_ref, fit: cover|contain}`. Upload lands in the Identity Profile asset area. **Never** an In-Game element (transparency is load-bearing for OBS compositing). |

### 5.2 Layer mapping

| Spec layer | Owned by (P0) | Notes |
| --- | --- | --- |
| **Layout** | The new `layouts` section of `identity_profile.json` — `layouts[scene][base_family][element] = {visible, zone|rect, z, behavior, rotation_seconds, …}`. Coords as `%` of the 1920×1080 canvas (matches the engine's existing zone model → resolution-scaling comes free, §6). | The genuinely new artifact. |
| **Content** | Untouched. `csrn-broadcast-layout-engine.js` + the data engine + `pregame_presentation.py` data sources. | Per spec. |
| **Style** | `theme_service.py` / `theme_manager.html` (palette/skin) + `identity_profile.organization.*` colors + the `ticker.skin` element property (§5.1). P1 extends with color pickers + logo/bg upload. | Partially exists; P1 extends. |

### 5.3 Resolved / confirmed

- **Spec open Q2 (`down_distance` sport-dependent)** — **RESOLVED.** The
  "Round 6 rules-engine proposal" it was flagged against is superseded by
  `SPORT_CONTRACTS` / `SPORT_STATE_CONTRACTS` (already at `64ed45a`) plus
  Phase C's `productionSportFamily` dispatch. The element becomes
  `game_fields`, family-resolved. No open question remains.
- **Video model** — the spec's "OBS composites under a transparent overlay,
  no ingestion in CSRN" is **exactly** Phase C's video-board contract.
  Aligned, no change needed beyond §5.1's "preserve the contract" rule.
- **Halftime spotlight reuse** — already implemented
  (`_halftime_spotlights()`); P0 just points the layout doc at it.

---

## 6. Still-open questions — with first passes

1. **One layout per customer, or named switchable presets?** (spec Q1)
   *First pass / recommendation:* schema supports **named presets from
   P0** (`layouts` is a map keyed by preset name, with `"active"` pointing
   at one), but **P1's UI exposes only "edit your layout"** (one active).
   Named-preset *switching* UI ("senior night" look) is a small P1.5 / P2
   add once the storage already supports it. Cheap to build in now, costs
   nothing if the switching UI never ships. **Decision needed:** accept
   named-preset storage in P0?
2. **P1 preset boundaries — offer vs leave fixed.** (spec Q3) *First pass:*
   | Offer as presets in P1 | Leave fixed in P1 (P2 freeform only) |
   | --- | --- |
   | `score_box` — 4 corner + 2 edge anchors × {S,M,L} | `game_fields` position (bonded to the scorebug per theme) |
   | `clock_period` — dock-with-score / standalone-corner | `spotlight_zone` position (theme-designed, overlap-prone) |
   | `ticker` — bottom-full / lower-third / off; + `skin` | `video_zone` position (contract region — offer 2 sizes, not free position) |
   | `sponsor_slot` — 3 anchors × {persistent, on-call} | |
   | `logo` — 4 corner anchors × {S,M,L} | |
   | `background` (pregame/halftime) — cover / contain | |
   | every element: on/off toggle per scene | |
   **Decision needed:** ratify or adjust this split.
3. **Resolution handling.** (spec Q4) *First pass / recommendation:*
   **assume 1920×1080, store all coords as `%` of canvas** (the engine's
   zone model already works this way — `--ball-x:50%` etc.), so a
   different output resolution scales proportionally with no per-resolution
   layout. True multi-resolution (distinct layouts per target) is **P2+**.
   **Decision needed:** is proportional-scale-from-1080p acceptable for
   launch, or must P1 account for (e.g.) 720p streams explicitly?
4. **`score_box` independent placement vs bonded scorebugs** (§5.1) — some
   themes render home+visitor in one graphic cabinet. Does P1 allow
   independent placement only for themes that support it, or defer all
   independent score placement to P2? *Lean:* P2 for independent; P1
   treats `score_box` as one paired element with anchor presets.
5. **`ticker.skin` vs the Style layer** — the spec puts skin choice on the
   `ticker` element; the theme system also has skin selection. Confirm the
   Builder surfaces **one** skin control (on `ticker`) and it writes
   `production_template_package_id`, rather than two competing controls.

---

## 7. Finalized Phase 0 kickoff prompt

> **Layout Builder — Phase 0 (Foundation).** Isolated branch/worktree off
> the post-Friday **merged trunk** (Round 26 + Round 27 + Phase C). May run
> **in parallel with the baseball engine P0** — Layout Builder P0 shares no
> files with the sport engines (it does not touch `sport_families`,
> `ruleset_service`, `engine_router`, `game_operations_service`, or any
> `*_game_routes`).
>
> **Discipline:** full regression suite green each commit; **byte-identical
> football-live rendering** with no layout override present; **no edit to
> the SHA-256-frozen `csrn-broadcast-layout-engine.js` / `.css`** (P0
> *reads* `PACKAGE_MANIFESTS` / `resolvePlacements` / `SPORT_CONTRACTS`;
> overrides are applied by the unpinned `csrn-production-theme-runtime.js`);
> **no customer-visible UI in P0**; report commit-by-commit.
>
> **Deliverables — P0 only (P1 guided customization and P2 freeform are
> separate later rounds):**
>
> 1. **Layout/content/style data model.** Add a `layouts` section to
>    `identity_profile.json` (managed by `identity_service.py`):
>    `layouts[<preset_name>][<scene>][<base_family>][<element>] = {visible,
>    zone|rect (% of 1920×1080), z, behavior (static|rotating|triggered),
>    rotation_seconds?, dock?, skin?}`, plus `layouts.active = <preset_name>`.
>    - `scene` ∈ `in_game` / `pregame` / `halftime`.
>    - `base_family` per Round 27 (`canadian_football` shares `football`);
>      `"default"` key = all-sports fallback.
>    - `element` ∈ `score_box` (paired for now), `clock_period`,
>      `game_fields` (family-resolved from `SPORT_CONTRACTS`, hockey/soccer
>      declared-empty), `ticker` (+`skin`), `sponsor_slot`,
>      `spotlight_zone`, `video_zone`, `logo`, `background`
>      (pregame/halftime only).
>    - Named presets are stored from P0 (per §6.1 decision); P1 UI edits
>      one active preset.
> 2. **`layout_builder_service.py`** — Flask-independent. Reads the frozen
>    engine's `PACKAGE_MANIFESTS` / `resolvePlacements` / `SPORT_CONTRACTS`;
>    exposes, per `(theme × scene × base_family)`, the available elements,
>    their zones, and each zone's constraints — with the **`video_zone`
>    marked contract-bound** (movable/resizable, never removable, always
>    keeps `data-module="video.board"` + `[data-video-mode]`). Generates a
>    `default` preset from the current engine placement so an absent
>    override reproduces today's render exactly.
> 3. **In-Game application hook** — an *additive* function in
>    `csrn-production-theme-runtime.js`: resolve the active preset's
>    `in_game[base_family]` overrides and apply visibility / zone / z /
>    behavior on top of `renderPackage`'s output. Absent an override,
>    behaviour is byte-identical to today. Coordinate the merge with the
>    Phase C owner (same file).
> 4. **Pregame/Halftime application hook** — an *additive* read in
>    `pregame_presentation.py`: apply the `pregame` / `halftime` scene
>    overrides (element visibility, zone, `background`, `sponsor_slot`
>    behavior) to `pregame_universal_overlay.html`. Halftime `spotlight_zone`
>    continues to source `_halftime_spotlights()` — no new capture logic.
> 5. **Scene ↔ scenario reconciliation** — document (in code + a short doc)
>    that `scene` = broadcast phase and the engine's `PRESENTATION_SCENARIOS`
>    are the In-Game scene's trigger states; the layout doc's `behavior`
>    field names them for `triggered` elements. No change to
>    `PRESENTATION_SCENARIOS`.
> 6. **Tests:**
>    - The generated `default` preset, for **every `(theme × base_family)`**,
>      reproduces `resolvePlacements()` output exactly (golden).
>    - Layout-doc round-trips through `identity_service` load/save.
>    - An override that hides or repositions `video_zone` **keeps**
>      `data-module="video.board"` + `[data-video-mode]` in the rendered DOM
>      (`nativeVideoBoardHost()` still resolves).
>    - Football live overlay rendering is byte-identical with no `layouts`
>      section and with a `default` preset present.
>    - Pregame/Halftime overlays unchanged with no override.
>
> **Gate:** with a hand-authored `layouts` preset that moves the ticker to
> a lower-third and hides the sponsor slot in-game, the overlay renders
> accordingly across all five themes and all engine-ready sport contexts;
> with no `layouts` section, every overlay is byte-identical to trunk; no
> frozen file touched; suite green.
>
> **Explicitly deferred:** all editing UI, the curated preset library,
> color pickers, logo/background *upload* UI, drag-and-drop, independent
> `score_box` placement, per-resolution layouts, named-preset *switching*
> UI. Those are P1 / P1.5 / P2.
>
> **Decisions needed before P0 starts** (from §6): (1) accept named-preset
> storage in P0; (3) accept proportional-scale-from-1080p for launch.
> §6.2/§6.4/§6.5 are P1 decisions, not P0 blockers.

---

*Doc only. Reconciliation complete against the recovered spec. Layout
Builder P0 waits for the R26+R27+Phase C trunk merge (one additive hook in
Phase C's file), then runs in parallel with — not behind — the baseball
engine P0. Two P0-blocking decisions flagged in §6.*
