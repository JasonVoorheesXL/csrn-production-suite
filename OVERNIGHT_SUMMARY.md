# Overnight Session Summary — 2026-08-28 → 08-30

Rounds 1-4 branch: **`overnight-fixes-20260828`** (off `gate6/final-visual-matrix`
@ `0f1d67d`). **Round 5 branch: `overnight-fixes-20260830`** (off
`overnight-fixes-20260828` @ `0c96780`, so it carries rounds 1-4).
Nothing deployed. Running CSRN process not touched. Review and merge is yours.

Full test suite (deterministic, `-p no:randomly`) after **round 5**: **51 failed,
2249 passed** (round-5 baseline 51 / 2222; original baseline 51 / 2175). The 51
failures are **byte-identical to baseline on every single commit** (verified by
`diff` of the sorted failure list — flagged loudly if it ever moved; it never
did). Pre-existing static-asset / theme-cache-version pins. **0 regressions.**

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
