# Basketball panel parity — Collegiate Tech's basketball, rebuilt

**Round:** `basketball-panel-parity-20260921`, worktree `CSRN-Prod-bbpanel`, off `main` (`194fb8a`, which
already carries the Neon redesign). **Status:** built and verified live; full suite green apart from the two
known environment failures. **Not merged, not pushed** — for the owner to review.

Basketball was the one Collegiate Tech sport still on a thin compact strip. It now has football's and
baseball's structure: cabinet, live strip, score/period/clock row, team-snapshot rails either side of a
video board with a court-photo clash screen, and a bottom bank. Neon inherits all of it (and got the court
skin in the same round).

## 1. Audit — what was missing, and why

Basketball was **not** on a separate renderer. `SCOREBUG_RENDERERS.collegiate(state, sport, videoMode)` in
`static/csrn-broadcast-layout-engine.js` dispatches football to `collegiateFootballScorebug` and
baseball/softball to `collegiateBaseballScorebug`; **basketball fell through to a generic inline strip** —
`explicitTeam` + `genericScore` + `sportState`, the same generic pieces the Modern/Minimal/Classic themes use:
team circle, name, score, period, clock and a shot-clock cell, in a 1140×150 box on the bottom-centre zone.

| | football / baseball / softball | basketball (before) |
|---|---|---|
| scorebug | `bl-collegiate-tech` skeleton | inline generic strip |
| canvas zone | `full-safe` 1840×1000 | `bottom-center`, 1140×150 |
| team snapshot rails | yes (`collegiateTeamPanel`) | none |
| video board / clash screen | yes, sport photo behind it | none |
| video-mode support (transparent window, sidebars hidden) | yes | none |
| bottom bank + callout | field bar + Down & Distance / diamond + Count | none |
| Layout Builder `score_box` placement, mode masking | measurable | strip only (no board to measure) |

Three further findings from the audit, none of them in the brief:

1. **The court photo already existed** (`static/friday-night-stadium/clash/basketball-court-background.png`) but
   nothing on Collegiate used it.
2. **Fouls, bonus and timeouts never reached the overlay live.** The renderer reads flat `home_fouls`,
   `home_bonus`, `home_timeouts` (`docs/HOOPS_OVERLAY_CONTRACT.md` §1), but `/api/runtime-state` only carries
   the engine's own `state["hoops"]` block (`home_team_fouls` …); the flat "wire" fields were specified in P0 and
   never wired. On any theme they read blank in a real game. Fixed in this round (see §3).
3. **The overlay had no path to player names.** The hoops ledger records player *ids*; the roster is behind
   operator auth. So "who scored" and "who is playing" — the owner's stated basketball priority — could not
   be shown at all without a new read-only feed (see §3).

## 2. What was built

**Engine** (`static/csrn-broadcast-layout-engine.js`, `.css`)
- `collegiateBasketballScorebug` — the tech skeleton, reusing `collegiateScoreClockRow` and
  `collegiateMainDisplay`, so the rails, video board, video-mode transparency and sidebars-hidden mode come for free.
- `collegiateBasketballBank` — a **foul & timeout board** (the field/diamond's counterpart: one row per team, five
  foul pips + count, an `IN BONUS` tag, five timeout pips + count, and a ball dot on the team with possession) over
  the same **four-cell readout bar** football uses: `Possession · Last Basket · Fouls · Timeouts`.
- Basketball claims the `full-safe` 1840×1000 zone like the other three sports (the table is shared with Neon).
- Rail stats for basketball: `FG` (made/attempts), `3PT` (made), `REB`.
- Plain-Collegiate court clash screen: the existing photo behind the same team-colour tint the other sports use.

**Runtime** (`static/csrn-production-theme-runtime.js`)
- `productionBasketballState` falls back to `state["hoops"]` for fouls / bonus / timeouts (the flat wire field still
  wins when present).
- `patchCollegiateBasketballBoard` / `patchCollegiateBasketballRails` keep everything live on the same fast path
  football and baseball use (the render signature carries no game-state fields). Team names are read from the
  rendered board, so the patch cannot disagree with the markup.
- `fetchCollegiateHoopsPanel` polls the panel feed (2.5 s cache, in-flight de-duplication; **only** for basketball
  on the Collegiate family, so no other sport or theme pays for it).
- The Player Leader card rotates **Scoring Leader** and **On the Floor** (jersey numbers + surnames), on the same
  25 s rotation football uses; the empty state is football's "Awaiting Stats".

**Server** (`hoops_overlay_panel.py`, `routes/hoops_game_routes.py`, `app.py`, `phase5_architecture.py`)
- `GET /api/hoops/panel-state` — public and read-only like `/api/hoops/overlay-state` (the OBS overlay has no login).
  Derived from the rebuilt event ledger and the roster: `leaders`, `team_stats`, `last_basket`, `on_floor`. Roster
  reads are cached 30 s; a roster failure blanks names but never the numbers; a failure in the feed is never a 500.
  Undo/redo/correction are honoured because the ledger is rebuilt each time. The wire shape is recorded in
  `docs/HOOPS_OVERLAY_CONTRACT.md` §2.

**Neon** (`static/csrn-collegiate-neon.css`) — see §6.

## 3. Judgment call 1: the bottom bar / callout → **LAST BASKET**

The owner's basketball priority is *the score, who scored, who is playing* — not handbook-precision stats. What the
engine tracks (`hoops_state_service.py`): fouls, bonus, timeouts, possession, lineup, and a ledger of shots by player.

Candidates for the football-Down-&-Distance / baseball-Count slot (the pill in Neon):
- **Bonus** is the closest analogue by *rule* (it changes what happens next), but it is a rare, binary state that
  spends most of a game off, so a pill built on it would usually be empty.
- **Fouls / timeouts** are ambient counters, not events.
- **Possession** already has a cell and a ball dot; in a sport where it flips every 20 seconds it is not a callout.
- **Last basket** — *"Jalen Brooks · 3 PT"* — is the thing a viewer wants after every score and the only cell that
  answers "who scored" directly. It changes on every made shot, which is exactly what a callout is for.

Decision: **`LAST BASKET` is the callout** (second cell, the pill under Neon), with `Possession`, `Fouls` and
`Timeouts` in the other three cells, and bonus shown where it belongs, as an `IN BONUS` tag on the team that shoots
(the engine's own semantics: the fouling team's opponent is in the bonus). Under Neon the pill takes the neon of the
**team that scored**, not the possession team (possession has the cell and the ball dot). With no player attributed
it falls back to the team name; with no basket yet it shows a dash.

## 4. Judgment call 2: the "SHOT14/SHOT24" field → **a real shot clock; removed from Collegiate**

Confirmed from the source, not the screenshots. It is `.bl-shot-clock` (`<span>SHOT</span><b data-bind="game.shotClock">`)
emitted by `basketballState()` — the generic basketball state block shared by several renderers — and patched live by
`applyBasketballBoardOverrides`. It is a shot clock, so it contradicts the recorded 2026-09-14 product decision
(*no shot clock, ever*; `docs/BASKETBALL_ENGINE_SCOPING_PLAN.md` P6).

In real games it was already blank: the serializer publishes `shot_clock: ""` when the profile has it off (and, per the
audit above, the runtime never received it at all). It showed **`SHOT 14` in the Neon screenshots only because the
capture rig injected `shot_clock` into the runtime state.** So this was a latent contradiction, not a live bug.

Removed from **every Collegiate basketball path**: the new board has none; the fallthrough strip now calls
`sportState(..., includeAuxClock = false)`; the Collegiate runtime no longer patches `game.shotClock`. **Left as is:**
the other themes' basketball renderers (Modern, Classic, Minimal, Press, 8-Bit, Friday Night Stadium, Heritage) still
contain the cell and the engine's data field; they render blank for the same reason. Stripping it from those is the same
one-line change per theme and is the owner's call — flagged, not done, because the brief scoped this to Collegiate.

## 5. Verification (real browser, real game)

The rig (scratch, outside the repo) runs this worktree's real app and **seeds a real basketball game** through the
real operations service (`initialize_hoops`, `set_starting_five`, `shot`, `free_throw`, `rebound`, `foul`, `timeout`)
with a fabricated roster, then drives the overlay by real polling. Live-driven changes were checked, not just rendered:
posting a visitor 3-pointer, a home foul and a visitor rebound moved the score 6→9, the last basket to *"Ty Baker · 3 PT"*
(scoring team's colour), possession to the visitor, home fouls 2→3, FG `2/3`→`3/4`.

Screenshots (1920×1080): plain Collegiate and Neon — distinct saturated colours; possession + score change; the second
rail card (scoring leader / on the floor); a grey team (Neon's ice-white fallback) and a red one; on-air with the
video window.

**Layout Builder** (`tools/layout_builder_smoke.js`, helpers redefined per sport as in the Neon round because `__hide`
and `__place` hardcode `football`) — now runnable in full on basketball because it has a board to measure:

| | in-game override matrix | score_box placement | ticker |
|---|---|---|---|
| Collegiate Tech, basketball | 13/13 | 11/11 | clean no-op |
| Neon, basketball | 13/13 | 11/11 (a first-run transient in the first sponsor-mode rebuild; clean on rerun) | clean no-op |

`data-component="scorebug"` is stamped at 1840×1000 under both `package-collegiate` and
`package-collegiate package-collegiate-neon`; no `.bl-shot-clock` is present.

## 6. Neon

Neon already attached to the new board with no change to its shell, panels, rails, ring, halo, video-window
transparency or pill (they are keyed to Collegiate's own classes, and the new bank reuses `bl-college-field-meta`).
The compact-strip block (`:not(.bl-collegiate-tech)`, "palette + glow only") is retired. Added:
- **Court photo, blacklight.** The court's lines are *black on light wood* (football's and baseball's are white on
  dark turf), so the line-light layers first **invert** the photo (a white `difference` blend), grayscale it, then
  isolate and bloom it as the fields do (bloom re-tinted cyan-teal, `screen`-blended). The glow is masked to the floor
  (the dark stands would otherwise light) and to its middle (the far corner boxes are dark maroon and lit up as blocks).
  The floor is graded deep violet instead of the shared grade's red. Result: a cyan centre circle and midcourt line
  glowing on a violet floor, the towers' team-colour spill unchanged. The neon pass on the clash screen is **done**, not
  deferred.
- **Foul & timeout board**: rows in each team's neon with glowing pips, the ball dot, a neon `IN BONUS` tag.
- **LAST BASKET pill** in the scoring team's neon (`data-last-team` → `--callout`).

## 7. Known limits

- Leaders, totals, last basket and the on-floor list exist only when the operator **attributes plays to players**
  (shooter, rebounder, lineup). With only score adjustments the board shows dashes, not guesses.
- One "Player Leader" candidate per team: the top scorer. No rebound/assist leaders (kept simple by design).
- No per-quarter line score (the engine does not record points by period).
- Timeout pips show the remaining count against a fixed five-pip scale; foul pips cap at five (the count is exact).
- Collegiate's shared shell fill still dims the OBS video hole on **plain** Collegiate on-air (all sports; Neon's
  shell is transparent and unaffected) — a pre-existing Collegiate trait, deliberately not changed here.
- The legacy `#statBar` (football stats) can show through above plain Collegiate's translucent shell in the rig, as on
  football; Neon hides it. Not changed.
- The other themes' basketball renderers keep their (blank) shot-clock cell — see §4.
- Scratch capture artefacts that are **not** product: rail cards are pinned in screenshots (headless virtual time
  freezes Collegiate's 24 s crossfade at its midpoint), and the fabricated roster.
