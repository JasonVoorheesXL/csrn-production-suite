# Retired: the standalone Neon build ("neon_v1")

**Not collected, not run.** `tests/conftest.py` sets `collect_ignore = ["retired"]`.
Kept for project history, not deleted.

## What this is

Between gates 116 and 153 (roughly forty sub-rounds) Neon was built as its own
engine: a standalone renderer (`csrn-neon-r1-engine.js`, `csrn-neon-r2-engine.js`,
per-sport softball / baseball drivers) with glow tuning, a transparent chassis,
per-sport passes, and a masked-compositing pipeline for putting neon-coloured
uniforms on the players in the video-board clash screen. It never reached
shippable quality and was hidden from the theme pickers (`DISABLED_PACKAGE_IDS`
plus the matching JS `DISABLED` sets).

The 2026-09-20 redesign (`docs/NEON_REDESIGN.md`) **replaces it** with a bold,
team-tinted neon *skin over Collegiate Tech*: same renderer, same DOM, same data
bindings, one extra stylesheet. The old approach is a retired attempt, not a
foundation. In particular the player-uniform recolour pipeline
(`paintFridayNightLayeredFootballClash` and the "layers-v10" mask compositing)
is **out of scope and stays retired**.

## What was archived here

| Location | Contents |
|---|---|
| `static/` | the eight standalone engine files: `csrn-neon-r1-engine.{js,css}`, `csrn-neon-r2-engine.{js,css}`, `csrn-neon-softball-r42-driver.{js,css}`, `csrn-neon-baseball-r43-driver.{js,css}` (moved out of the live `static/`) |
| `tests/` | 32 test files that pin the old architecture or its frozen-pixel checkpoints: `test_gate116_neon_visual_freeze.py`, `test_gate11_approved_concept_renderer.py`, `test_gate150_*`, `test_gate151_*` (all R-suffixed sub-rounds), `test_gate152_*`, `test_gate153_*` |
| `tests/test_gate78_heritage_press_design__retired_neon_manifest_tests.py` | ten tests extracted verbatim from `test_gate78_heritage_press_design.py`, which pin the old Neon manifest (top-full 1840x250 lane). The rest of that file (Heritage Press) still runs. |

The Neon **image assets** (`static/neon/`, `static/neon-r1/`, `static/neon-r2/`) were
left where they are; nothing live references them.

## Why they cannot simply be re-enabled

They assert the old standalone architecture: the `neon` scorebug renderer, the
`package-neon-approved` style class, a `top-full` scoreboard lane, the
`CSRNNeonR2Engine` global, and (gate116) byte hashes of the shared layout engine
that a Collegiate-based build necessarily changes. The new build has its own
suite (`tests/test_neon_collegiate_skin.py`).

## Other tests that were edited rather than archived

Tests that cover *live* behaviour but happened to mention Neon were updated in
place, not archived: `test_gate12/13/14` and `test_gate142` (shared-engine hash
re-pins, per their own re-pin convention), `test_gate143` (the layout lab no
longer loads a standalone Neon engine), `test_gate163` (readiness page engine
list), `test_gate165` (engines are archived, not left in `static/`), `test_gate167`
(Neon's ticker target is Collegiate's), and the Collegiate tests that pinned the
literal `alias === "collegiate_traditional"` comparison.

## To resurrect the old build (not recommended)

Move `static/*` back to the live `static/`, move `tests/*` back to `tests/`, remove
the `collect_ignore` entry, and restore the old `digital_neon` manifest from git
history (`git log -S'id:"digital_neon", name:"Neon Sports Network"'`).
