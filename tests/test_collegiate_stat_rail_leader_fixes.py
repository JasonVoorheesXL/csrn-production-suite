"""Regression coverage for four issues found in the 2026-08-25 evening mock
broadcast, all in the collegiate stat-rail "leader" box
(patchCollegiateRails/collegiatePlayerLeaders in
static/csrn-production-theme-runtime.js):

1. "Scoring Leader" could show a kicker's own low point total instead of
   the side's actual top scorer -- every player with a nonzero stat in a
   category generated their own same-titled candidate, and the rotation
   eventually reached the low ones. Confirmed via real game-state
   computation (see td_spotlight/statistics work this session) that the
   underlying point *values* were always correct; the bug was the rotation
   including every player's own entry per category instead of just the
   category leader.
2. A leader with no headshot on file rendered blank instead of falling
   back to the team crest, unlike the TD spotlight and roster pages.
3. A long leader name (e.g. "Finn Stubbendorff") could clip inside the
   rail's fixed, overflow:hidden box.
4. (No code change -- confirmed working, not tested here) a passing
   touchdown already credits the QB's own passing_yards/passing_touchdowns
   independently of the receiver's stats, per statistics_service.py's
   plays-loop; see the investigation notes in this session's summary.

This project has no JS execution harness (no node/execjs/playwright in the
test suite) -- other gate tests for this file follow the same static
source-assertion pattern used here.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_leader_candidates_are_deduped_to_one_per_category() -> None:
    js = read("static/csrn-production-theme-runtime.js")
    assert "const bestByTitle = new Map();" in js
    assert "candidate.weight > existing.weight" in js
    assert "return Array.from(bestByTitle.values()).sort((a, b) => b.weight - a.weight);" in js


def test_leader_box_falls_back_to_team_crest() -> None:
    js = read("static/csrn-production-theme-runtime.js")
    assert 'const teamLogo = textValue(identity.logo, runtime?.[`${side}_logo`]);' in js
    assert "const nextImage = leader ? textValue(leader.image, teamLogo) : \"\";" in js


def test_leader_name_uses_shrink_to_fit() -> None:
    js = read("static/csrn-production-theme-runtime.js")
    assert "function fitPlayerLeaderName(node)" in js
    assert "fitPlayerLeaderName(name);" in js


def test_leader_rotation_interval_at_least_doubled() -> None:
    js = read("static/csrn-production-theme-runtime.js")
    assert "const COLLEGIATE_LEADER_ROTATION_MS = 25000;" in js
    assert "Date.now() / COLLEGIATE_LEADER_ROTATION_MS" in js
    # The old 12s rotation must no longer drive the leader index.
    assert "Date.now() / 12000" not in js
