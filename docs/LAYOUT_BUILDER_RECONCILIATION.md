# Layout Builder — reconciliation pass

**Round:** `layout-builder-reconciliation-20260907`, worktree
`C:/Users/Darth/CSRN-RoundWork/CSRN-Prod-layoutbuilder`, off `64ed45a`.
**Doc only — no code.** Goal: confirm the persisted "Layout Builder" plan
(3-scene scope; layout / content / style architecture; 3-phase delivery —
Phase 0 foundation, Phase 1 curated-preset customization, Phase 2 freeform
drag-and-drop deferred) still holds against everything that has landed
since it was written (Round 26 field geometry, Round 27 sport-context /
gateway, Phase C per-theme sport dispatch + video-board contract), decide
whether Phase 0 must wait for the post-Friday trunk merge, and produce an
updated Phase 0 kickoff prompt.

---

## 0. Blocker — the source spec was not locatable in this environment

Searched the repo (`git grep`, `docs/`, `docs/foundation/`), the memory
store, and the Drive `CSRN/` tree: **the persisted Layout Builder plan is
not present as a file here.** It appears to live in a prior conversation /
artifact, not the checkout.

**What this doc can and cannot do without it:**

| Can do now (below) | Needs the spec pasted in |
| --- | --- |
| Audit what R26 / R27 / Phase C changed that a Layout Builder must account for (§2). | The **field-by-field reconciliation table** — going through the spec's actual component list, scene definitions, and Phase 0 task list line by line. |
| Establish that the layout engine is **already sport-aware** and what that means for the spec's component model (§3). | Whether the spec's "3 scenes" are the same as the engine's existing `PRESENTATION_SCENARIOS` or a different partition. |
| Phase 0 **file-contention analysis** and the wait-for-merge vs start-sooner call, with the decision branch that depends on one unknown (§4). | Resolving that unknown: **does Phase 0 as spec'd edit `csrn-broadcast-layout-engine.js`, or only additive/new files?** |
| The list of reconciliation questions the spec now has to answer (§5). | The **updated Phase 0 kickoff prompt** (§6 is a skeleton; it can't be finalised against a spec I can't read). |

**Ask:** paste the Layout Builder plan (or point to the artifact) and this
doc gets its §6 finished and a real reconciliation table added.

---

## 1. Current layout-engine architecture at `64ed45a` (what a Layout Builder builds on)

`static/csrn-broadcast-layout-engine.js` (v1.7.0, **SHA-256 frozen** by
`test_gate116` + cross-refs `test_gate12/13/14`) already contains most of
the primitives a Layout Builder needs:

| Primitive | What it is |
| --- | --- |
| `PACKAGE_MANIFESTS` | Per-theme manifest: `scorebugRenderer`, `componentRendererFamily`, `styleClass`, and a `sports` map of per-sport **zone** profiles. |
| `zone(name)` / `componentSize()` / `fitInZone()` / `rectsOverlap()` | A geometric **zone-placement system** on a fixed canvas. |
| `resolvePlacements(manifest, sport, activeComponents)` | The solver: given a theme + sport + a component list, returns non-overlapping placements or throws. |
| `PRESENTATION_SCENARIOS` | Named component sets already shipped: `baseline` = `["scorebug","ticker"]`, plus `captions` / `player` / `highlight` / `sponsor` / `feature`. **These may be what the spec calls "scenes."** |
| `SPORT_CONTRACTS` | Per-sport `{required, gameFields, preferredScorebugZones}` for **football / basketball / baseball / softball**. |
| `SPORT_STATE_CONTRACTS` + `BASEBALL_FUTURE_COMPONENTS` | Per-sport state-value enums and a declared future-component list: `["lineup","atBat","onDeck","inTheHole","defensiveAlignment","pitcherCard","batterCard","baserunnerState","inningSummary","lineScore"]`. |
| `theme_service.py` + `templates/theme_manager.html` | An existing theme-management service + UI — the natural host or sibling for a Layout Builder UI. |

**Implication:** "Phase 0 foundation" is not greenfield. The manifest +
zone + scenario + sport-contract model already exists; Phase 0 is more
*expose and make editable* than *build from scratch*. The spec should be
read with that in mind.

---

## 2. What landed since the spec — and why each matters to a Layout Builder

### 2.1 Round 26 (`5ba5948`, unmerged) — field geometry

- Edits **`collegiateField()`** in the frozen engine + `.bl-college-field-grid`
  CSS: field length/end-zone driven by `--csrn-ez` / `--csrn-yl-count` /
  `--csrn-hash-count` from the ruleset (100/10 US → 110/20 CA).
- Re-pins `test_gate116` / `test_gate12/13/14/142` to new hashes.
- **Layout Builder impact:** the "field" component is now **ruleset-
  parametrised**, not a fixed graphic. If the Builder's `style` layer lets
  an operator tweak field appearance, it must not fight the ruleset-driven
  CSS variables. Low structural impact, but a note for the component's
  editable-property list.

### 2.2 Round 27 (`20ee515`, unmerged) — sport-context / gateway

- New `sport_families.py`: `SPORT_FAMILIES` (football/basketball/baseball/
  softball/soccer), `GATEWAY = "all_others"`, `OTHER_CONTEXTS`
  (canadian_football/hockey/lacrosse/tennis/swimming), `base_family()`,
  `ENGINE_READY`.
- Session carries `sport_context`; roster/sponsor scoping keys off
  `base_family(sport_context)`.
- **Layout Builder impact — the significant one.** A layout is now
  **per-sport-context**, not global. The Builder must:
  - Scope a saved layout/preset to a `base_family` (or offer "all sports"),
    the way rosters/sponsors are now scoped.
  - Understand that `canadian_football` and `football` share a layout pool
    (both `base_family == "football"`), mirroring the roster/sponsor rule.
  - Handle `sport_context` values that have **no engine yet** (hockey,
    lacrosse, …) — the Builder either hides them or shows a "no layout
    target yet" state, consistent with the gateway's "coming soon."

### 2.3 Phase C (`c66f6d2`, unmerged) — per-theme sport dispatch + video-board contract

- `csrn-production-theme-runtime.js` (**not** frozen) gained
  `productionSportFamily()`, per-family `mergeRuntimeState` game-field
  blocks, `applyBoardOverrides` dispatching to football / basketball /
  diamond patchers, and the **video-board contract**: `nativeVideoBoardHost`
  resolves a `data-module="video.board"` / `[data-video-mode]` region per
  theme (`.bl-fns-video-board`, `.bl-8bit-video-board`, `.bl-college-stage`,
  Heritage `.hp-opening`).
- Gated football-specific labels (down/distance, possession) out of
  non-football boards.
- Deferred **T1** (Collegiate baseball structural parity) — will edit the
  frozen `csrn-broadcast-layout-engine.js` and re-pin, post-merge.
- **Layout Builder impact:**
  - The Builder's `content` layer must treat **game fields as
    per-sport-family** — `productionSportFamily(sport)` decides whether a
    slot shows `down/distance` or `inning/count/outs` or `shotClock/fouls`.
    The engine's `SPORT_CONTRACTS.*.gameFields` (§1) is the canonical list;
    the spec's component list must be reconciled against it (§3).
  - The **video-board region is a first-class, contract-bound zone**. If
    the Builder lets an operator move/resize components, it must not let
    them overlap or evict the `data-module="video.board"` region — that
    region is reserved for a future live feed (Phase C commit 7/8 + the
    T1 "transparent-for-video" work). Treat it as a locked zone in Phase 0.
  - Any Builder Phase that edits `csrn-production-theme-runtime.js` now
    contends with Phase C's branch (unpinned file, additive merges, but
    still a coordination point).

---

## 3. The sport-awareness question — **answered: yes, and the engine already models it**

The user's specific worry: *"does its component list need to become
sport-aware now that 'down/distance' isn't the only game-field type
anymore?"*

**Yes — and the layout engine at `64ed45a` already encodes this**, independent
of the Builder spec:

- `SPORT_CONTRACTS.football.gameFields` = `["period","clock","downDistance","playClock","possession"]`
- `SPORT_CONTRACTS.basketball.gameFields` = `["period","clock","shotClock","homeFouls","visitorFouls","possession"]`
- `SPORT_CONTRACTS.baseball.gameFields` / `softball` = `["inning","inningHalf","balls","strikes","outs","bases","pitcherName","batterName","batterPosition"]`
- `BASEBALL_FUTURE_COMPONENTS` = the ten `lineup / atBat / onDeck / … / lineScore` slots.
- `preferredScorebugZones` differs per sport (`bottom-center` for football,
  `top-left`/`top-right` for baseball).

**Reconciliation finding (spec-independent):** the Builder's component
model must be **keyed by `base_family` (Round 27) and driven by
`SPORT_CONTRACTS` / `SPORT_STATE_CONTRACTS` / `BASEBALL_FUTURE_COMPONENTS`
(the engine), not by a flat football-centric component list.** If the
persisted spec's component enumeration predates these structures (likely —
`SPORT_CONTRACTS` reads as post-spec scaffolding), that enumeration is the
main thing the reconciliation must rewrite. A "game state" component in the
spec becomes a *family-resolved* component: it renders `downDistance` for
`football`, `inning/count/outs/bases` for `baseball`, `shotClock/fouls` for
`basketball`, and (once those engines land) hockey/soccer field sets.

Also fold in, per §2.3: the **video-board region** as a reserved,
non-editable zone in the component model, and hockey/soccer game-field
sets as *declared-but-empty* now (like `BASEBALL_FUTURE_COMPONENTS`) so the
model doesn't need re-architecting when those engines ship.

---

## 4. Phase 0 file-contention analysis — and the wait-for-merge call

The contended files this whole arc has been coordinating around:

| File | Frozen? | Who touches it (unmerged) | If Layout Builder Phase 0 edits it |
| --- | --- | --- | --- |
| `csrn-broadcast-layout-engine.js` | **SHA-256 (`test_gate116` + refs)** | R26 (`collegiateField` + re-pin); Phase C **T1** (post-merge, Collegiate baseball skeleton + re-pin) | **Must wait for merge.** A third independent re-pin of this file across three branches is exactly the entanglement flagged for the baseball engine and for T1. |
| `csrn-broadcast-layout-engine.css` | **SHA-256** | R26 (`.bl-college-field-grid` + re-pin) | **Must wait for merge.** Same reason. |
| `csrn-production-theme-runtime.js/.css` | not frozen | Phase C owns it; hockey engine P3.5 will add to it | **Can proceed pre-merge only if additive**, but still a rebase/coordination cost against Phase C. Prefer post-merge. |
| `templates/index.html` | not frozen | R26 (+81), R27 (+77) | **3-way contended already.** A Builder UI here = 4-way. Use a `templates/_layout_builder.html` partial + one-line `{% include %}`, same fix adopted for the sport-engine operator panels. |
| `theme_service.py` / `templates/theme_manager.html` | not frozen | nobody else | **Clean.** A Builder that lives here or as a sibling service is self-contained. |
| new files (`layout_builder_service.py`, a `rulesets/`-style `layouts/` store, a new route, the partial) | — | nobody | **Clean.** |

### The decision branch (needs the spec to resolve)

- **If Phase 0 as spec'd is "expose the existing manifest/zone model as an
  editable `layouts/` override + a read-only preset browser," touching
  only new files + `theme_service.py` + a template partial** → it is
  **genuinely self-contained and can start before the merge.** The engine's
  `resolvePlacements` / `PACKAGE_MANIFESTS` are *read*; a saved layout is a
  new manifest-shaped JSON the **theme runtime** (unpinned) applies at
  render time. No frozen-file edit.
- **If Phase 0 as spec'd modifies `csrn-broadcast-layout-engine.js`** (new
  zones, a changed `resolvePlacements` signature, manifest-schema changes
  in the engine itself) → it **must wait for the post-Friday merge** and
  take a coordinated re-pin, joining the R26 / T1 queue on that file.

**Recommendation:** aim the Phase 0 kickoff at the **self-contained
shape** — read the frozen engine's manifest/zone model, write layout
overrides applied by the unpinned runtime, UI in a partial. That keeps
Layout Builder off the critical path and lets Phase 0 start as soon as the
kickoff is approved, not gated on the merge. Confirm against the spec that
this is achievable; if the spec assumes engine edits, re-scope Phase 0 to
the additive shape or accept the wait.

---

## 5. Reconciliation questions the spec now has to answer

1. **Scenes vs `PRESENTATION_SCENARIOS`** — are the spec's "3 scenes" the
   same partition as the engine's `baseline` / `player` / `highlight` /
   `sponsor` / `feature` / `captions` scenarios, a subset, or an
   orthogonal concept? If different, which wins?
2. **Component list vs `SPORT_CONTRACTS`** (§3) — rewrite the spec's
   component enumeration as family-resolved, driven by
   `SPORT_CONTRACTS.*.gameFields` + `BASEBALL_FUTURE_COMPONENTS`, with
   hockey/soccer declared-but-empty.
3. **Layout scoping** (§2.2) — a saved layout/preset is scoped to a
   `base_family` (or "all"), following the Round 27 roster/sponsor rule;
   `canadian_football` shares `football`'s pool.
4. **Video-board zone** (§2.3) — locked, non-editable in Phase 0 /
   Phase 1; the Builder must refuse placements that overlap it.
5. **Style layer vs ruleset-driven CSS** (§2.1) — the field component's
   geometry is now ruleset-driven (`--csrn-ez` etc.); the Builder's style
   layer edits presentation only, not geometry.
6. **Phase 0 file scope** (§4) — self-contained (recommended) or
   engine-editing (waits for merge + re-pin)?
7. **Phase 1 "curated presets"** — are the curated presets per-theme,
   per-family, or per-(theme × family)? Given Phase C's per-theme dispatch,
   `(theme × family)` is the natural unit.
8. **Where does the layout override live and who applies it** — proposed:
   a `layouts/<theme>/<family>/<name>.json` store (manifest-shaped),
   resolved alongside the package manifest and applied by
   `csrn-production-theme-runtime.js`. Confirm vs the spec's persistence
   model.

---

## 6. Updated Phase 0 kickoff prompt — **skeleton, pending the spec**

> *(Fill the bracketed parts from the persisted spec once provided.)*

**Round:** Layout Builder Phase 0 — foundation. Isolated branch/worktree
off the post-Friday merged trunk (R26 + R27 + Phase C). Same discipline as
every round this arc: full regression suite green each commit,
**byte-identical football-live rendering**, **no edit to the SHA-256-frozen
`csrn-broadcast-layout-engine.js/.css`** (Phase 0 reads the manifest/zone
model; layout overrides are applied by the unpinned
`csrn-production-theme-runtime.js`), operator UI in a
`templates/_layout_builder.html` partial (one-line `{% include %}`),
report commit-by-commit.

**Scope (Phase 0 only — Phase 1 preset customization and Phase 2 freeform
drag-and-drop are separate, later rounds):**

1. `layout_builder_service.py` — reads `PACKAGE_MANIFESTS` + `resolvePlacements`
   from the frozen engine; enumerates, per `(theme × base_family)`, the
   available components (from `SPORT_CONTRACTS` / `BASEBALL_FUTURE_COMPONENTS`)
   and zones, with the **video-board region marked locked**.
2. `layouts/<theme>/<base_family>/<name>.json` store — manifest-shaped
   layout overrides; `<theme>/<family>/default.json` = the current shipped
   placement, generated from the engine so nothing regresses.
3. Runtime application — `csrn-production-theme-runtime.js` resolves the
   active `(theme × family)` layout override and passes its
   `activeComponents` / zone overrides into `renderPackage`; absent an
   override, behaviour is identical to today.
4. Read-only preset browser in the `_layout_builder.html` partial — pick a
   theme + sport-context, see the resolved layout, no editing yet.
5. `[scene model]` — reconcile the spec's 3 scenes against
   `PRESENTATION_SCENARIOS`; `[decision from §5.1]`.
6. Tests: layout-override round-trips; `default.json` for every
   `(theme × family)` reproduces the frozen engine's placement exactly;
   an override that would overlap the video-board zone is rejected;
   football live rendering unchanged with and without overrides.

**Gate:** operator opens the browser, picks e.g. *Heritage Press ×
baseball*, sees the current layout rendered from a generated
`default.json`; no frozen file touched; suite green.

**Explicitly deferred to Phase 1 / Phase 2:** any editing UI, curated
preset library, drag-and-drop, per-component style controls.

---

*Doc only. §6 is a skeleton until the persisted Layout Builder spec is
supplied; §2–§5 stand on their own. Branch holds until the spec is in hand
and (for any engine-touching scope) the trunk merge.*
