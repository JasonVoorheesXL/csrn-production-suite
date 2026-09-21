# Neon redesign — a team-tinted neon skin over Collegiate Tech

**Round:** `neon-redesign-20260920`, worktree `CSRN-Prod-neon`, off `main` (`5c60393`).
**Status:** all four checkpoints built and live-verified. Neon is **re-enabled** in every
picker (checkpoint 4). Not merged, not pushed: awaiting the owner's sign-off.

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

## Checkpoint 3: the other sports, and the field art

**Baseball / softball** keep Collegiate's skeleton (line score left, diamond right). The line
score's rows are each in their team's neon; the diamond and its runners take the **batting**
team's neon (`--poss`, the same variable football uses for the team in possession), so it
swaps to the home colour in the bottom half. **Count** is the callout: the same `999px` pill as
football's Down & Distance, the second cell of the Batting / Count / Outs bar. Collegiate's 320px
diamond column truncated "2–1" inside a pill, so Neon widens it to 430px.

**Basketball** is Collegiate's older compact strip (no readout bar, no video board), so by decision
it gets palette + glow only, no callout: dark glass, the gradient ring and team halo, each side
in its own neon, glowing digits and clocks. That strip puts **home on the left** (football's
board has the visitor there), so its ring and halo run home → visitor.

**Field art (owner direction, revised twice after live review).** Two drawn-CSS versions were
rejected: mowed daylight turf with plain white lines clashed with the package, and a drawn
receding plane "looked like a radar image". The owner's reference was neon/blacklight stadium art
and "Cosmic Baseball": a picture of a real field under blacklight.
- *Clash screen:* Collegiate's own photographs (football field, baseball and softball ballparks),
  re-graded. The stage is multiplied into ultraviolet blue (turf near-black violet, dirt magenta),
  each tower spills its team's neon down from the top corners, and the photo's own white lines and
  stadium lights are re-lit in mint: `::before` is a contrast-isolated copy of the brights (crisp
  core), `::after` the same copy blurred (bloom), both `screen`-blended. The softball sky is bright
  enough to pass the isolation, so its glow layers are masked to the ground. No animation. The only
  photos named are those three; the keyed player layers stay retired.
- *Field bar and in-game diamond* (functional strips, not photographs): "blacklight turf", near-black
  green with a faint mow, and every line (yard lines, hashes, numbers, foul lines, basepaths) drawn as a
  thin bright core with a soft mint bloom (`--turf-core` / `--turf-bloom`, the same technique as the panel
  borders and the Down / Count pills). Football's ball marker is a neon leaf in the possession
  team's colour with its initials upright.

## What full-resolution captures caught

The 800×450 previews hid four real defects that 1920×1080 captures (headless Chrome against a
scenario-driven scratch server, real polling) exposed:
1. **The video window was blurred.** Collegiate's shell carries `backdrop-filter: blur(8px)`; Neon's
   is `none`, so an on-air camera feed is sharp.
2. **The legacy stats ribbon (`#statBar`) showed through** the now-transparent shell as a readable
   strip across the top. Neon sets `csrn-production-theme-neon-active` while rendering and hides it
   (Collegiate Traditional still has a sliver of it above its opaque shell; not changed here).
3. **The readout pills were clipped** at the bottom: the bank is a fixed-height stack that
   Collegiate's 1px borders just fit; Neon's 2px borders on those two containers cost 3px. They keep
   1px (the glow carries the weight) with a few px of padding reclaimed.
4. **Complementary team colours blended to grey** (gold + blue) for the shared centre colour. `--mn`
   is now the blend pushed toward white (a neon tube's hot core), still tinted by both teams.

Captures use two rig-only adjustments that do not affect the product: rail cards are pinned to
their first card (headless virtual time freezes Collegiate's 24s CSS crossfade at its midpoint), and
a backdrop page supplies a dark arena or a bright "camera feed" behind the transparent overlay.

## Checkpoint 4: the final pass

**Re-enabled.** `DISABLED_PACKAGE_IDS` (production_template_service.py) and the `DISABLED` sets in
`static/csrn-pregame-theme-selector.js` and `static/csrn-production-template-menu.js` are now empty,
and `templates/index.html`'s Production Theme select gained `<option value="digital_neon">Neon</option>`
(the hide had removed it from the markup, not just from the script). The hide mechanism is kept, so any
package can be hidden again by adding its id to the three lists. A Neon selection round-trips through
the authoritative template-state file. Flipped tests: `test_theme_picker_neon_disabled.py` became
`test_theme_picker_neon_enabled.py`; gate165's "disabled cannot be selected" test now proves Neon
persists and that the hide mechanism still works for any other id.

**Theme Manager.** The `digital_neon` preset in `theme_service.py` is now named "Neon" with a new
description and Collegiate-family tokens, and its scorebug preview layout is `collegiate` (in the
preset and in `static/csrn-scorebug-engine.js`'s `PRESET_LAYOUTS`), not the retired angular-wings
`neon` renderer. That renderer stays defined (the layout-coverage tests need it) but no preset uses it.

**Layout Builder, verified live on all four sports** (headless-free real browser against the scratch
server, real polling; `tools/layout_builder_smoke.js`): `data-component="scorebug"` is stamped on the
bonded board in every sport (through `applyRect()`; the other components are stamped as they appear).
The in-game override matrix (hide sponsor / spotlight / video, fall-through, no legacy leak) passes 13/13
on football, baseball and softball, and the score_box placement matrix 11/11 on all three; the ticker matrix
is a clean no-op (Neon, like Collegiate, has no isolated ticker component). **Basketball** is Collegiate's
compact strip (1140x150, no themed video board), so there is no board for the mode matrix to
measure; placement passes 9/11 and the two "failures" are the football-sized expectation that a
top-left / bottom-center zone must refuse a fit scale under 0.5: the small strip legitimately fits those zones
(scale 0.67 and 1.0), so it is placed inside the zone, which is the correct behaviour. The smoke file's
`__hide` / `__place` helpers hardcode `football` in the layouts document; for the other sports they
were redefined for the sport under test in the console (the tool itself is unchanged).

**Shared-engine hash pins** were not touched: checkpoint 4 changed no engine JS.

## Known limits

- Neon inherits Collegiate's limits: no isolated ticker component (so no ticker placement), and
  basketball has no themed video board or readout bar.
- The softball photo is a bright sunset, so its glow layers are masked to the ground and the
  sky reads hot pink/orange under the blacklight grade. Grade values are a few lines in
  `static/csrn-collegiate-neon.css` if the owner wants it darker.
- The in-game diamond and the football field bar are drawn graphics (near-black turf with glowing
  linework), not photographs.
