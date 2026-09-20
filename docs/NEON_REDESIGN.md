# Neon redesign — a team-tinted neon skin over Collegiate Tech

**Round:** `neon-redesign-20260920`, worktree `CSRN-Prod-neon`, off `main` (`5c60393`).
**Status:** checkpoint 2 (football) built and live-verified. Not yet done:
checkpoint 3 (baseball / softball / basketball look), checkpoint 4 (final pass and
**re-enable in the pickers**). Neon is still hidden from the pickers.

## Why a redesign, not a fix

Gates 116–153 (about forty sub-rounds) built Neon as a standalone engine (glow
tuning, transparent chassis, per-sport passes, and a masked-compositing pipeline to
put neon uniforms on the players in the clash screen). It never reached shippable
quality and was hidden. This round replaces it with a lower-risk idea from the
owner: **Collegiate Tech's structure, in a bright neon colour scheme**, including
the football down/distance and a glass-panel look with a neon-glow outline around
the video board. The old approach is a retired attempt (see "Retired" below); the
player-uniform recolour pipeline stays out of scope.

## Decisions (owner)

- Neon stays its **own picker entry** (`digital_neon`), not a Collegiate toggle.
- **Team-tinted colour:** each school's configured colours, electrified, per game.
  Not a fixed cyan/magenta palette, not one accent on every game.
- **Bold, static glow.** Thick, high-intensity, not tied to game state, and **no
  animation** (a pulsing glow was ruled out as distracting on air).
- **Football Down & Distance:** a small rounded neon **pill**, same cell footprint as
  today's bar; the same pill shape for baseball/softball's Count (checkpoint 3).
- **Basketball:** palette + glow only, no callout (Collegiate's basketball strip has
  no readout bar).
- Old Neon code/tests are **archived**, not deleted.

## How it works

**One structure, two skins.** Collegiate lives inside the shared
`csrn-broadcast-layout-engine.js` as the `collegiate` renderer family. The
`digital_neon` manifest is now a thin entry over it: `scorebugRenderer:"collegiate"`,
`componentRendererFamily:"collegiate"`, `styleClass:"package-collegiate
package-collegiate-neon"`. Its per-sport component placement is the **same constant**
as Collegiate's (`COLLEGIATE_SPORT_COMPONENTS`, lifted out so there is one copy), so
the two cannot drift apart the way the old build drifted from its frozen tests.

**Runtime.** About a dozen `alias === "collegiate_traditional"` branches (rails,
leaders, statistics, baseball diamond, field, video board audit, video-window guide)
now key on `isCollegiateFamily(alias)`, so Neon inherits all of them instead of
forking them.

**Skin.** `static/csrn-collegiate-neon.css`, every rule scoped under
`.package-collegiate-neon` (tested), so Collegiate Traditional cannot change.

**Team tint.** `neonElectrify(primary, secondary)` in the engine: keep the school's
hue, push saturation to 100%, set lightness per hue (blues/violets 0.70, reds 0.62,
golds 0.56, greens 0.55, else 0.60). If the primary is black/white/grey it uses the
secondary, then ice-white. Computed per game from the teams actually on air and set
as `--visitor-neon` / `--home-neon` on the root. Verified on 17 school colour pairs
in a real browser (navy→#338EFF, gold→#FFBF33, purple→#9A66FF, green→#1AFFA1,
black/gold→gold, grey→ice). A visitor whose configured colours are all grey therefore
reads ice-white, which is honest rather than invented.

**Look.** Dark glass panels with a 2px neon outline and a four-layer glow in the
panel's team colour; a visitor→home gradient ring plus a team-coloured halo around the
whole board and around the video board ("the glass screen"); glowing score digits;
turf and yard numbers electrified; the possession team's colour on the line of
scrimmage, ball and direction arrow; a first-down yellow line. **Down & Distance** is
the second cell of the bottom bar restyled as a `999px` pill in the possession
team's neon (`--poss` follows the live-patched `data-possession`).

## Two things found by looking at it live

1. **The video window must be a true hole.** Collegiate's shell paints a
   semi-transparent dark gradient *behind* the transparent video stage, which dims
   the OBS picture. Neon's shell and main display are transparent (every panel carries
   its own dark fill), the team tint is confined to the rail zones, and in on-air mode
   the stage keeps its ring and outer halo but drops every inner tint. Checked against a
   bright test gradient: it passes through untouched. (Collegiate Traditional itself
   still has its dimming fill; not changed here.)
2. **Achromatic school colours** needed the secondary/ice fallback above.

## Layout Builder contract

The old Neon never stamped `data-component` because it rendered through its own
engine (`CSRNNeonR2Engine`), so `score_box` overrides no-oped (see
`docs/LAYOUT_BUILDER_P1.md`). Through the shared engine, `applyRect()` stamps every
component, including the bonded `data-component="scorebug"` board (1840×1000, as
Collegiate). Live-verified on Neon: in-game matrix **12/12** (sponsor / player /
highlight modes, hide, fall-through, no legacy leak), placement matrix **11/11**
(centre fit 0.52, full-safe, explicit rect, too-small refusal, survives rebuilds),
ticker matrix a clean no-op (no isolated ticker component, as on Collegiate).

## Retired (archived, not deleted)

`tests/retired/neon_v1/` (README explains everything): the eight standalone engine
files (`csrn-neon-r1/r2-engine`, softball/baseball drivers), 32 test files pinning the
old architecture (gate 116, 11, 150–153), and ten Neon-manifest tests extracted from
`test_gate78_heritage_press_design.py`. `tests/conftest.py` has
`collect_ignore = ["retired"]`. Tests that cover live behaviour but mention Neon were
**edited, not archived**: gate 12/13/14/142 (shared-engine hash re-pins, per their own
convention), 143 (layout lab), 163 (readiness page), 165, 167 (Neon's ticker target),
and the Collegiate tests that pinned the literal alias comparison.

## Verification

Live, isolated instance, 1920×1080, real server polling (`tools/neon_smoke.js`):
per-game colours (navy/gold, purple/green, red/grey), possession and down/distance
changing with no reload (pill and line of scrimmage switch team colour), on-air mode
(transparent window over a bright test backdrop), plus the Layout Builder matrices
above. Fresh suite: `tests/test_neon_collegiate_skin.py` (23 tests, including a Python
port of the tint checked against the browser's own outputs).

## Not yet done

- Checkpoint 3: baseball/softball (Count pill), basketball palette/glow, per-sport
  stage art tint.
- Checkpoint 4: theme catalog entry / Theme Manager preview for `digital_neon`, final
  `data-component` audit on all four sports, **re-enable** (`DISABLED_PACKAGE_IDS` and
  both JS `DISABLED` sets), final shared-engine hash re-pin, suite, docs.
