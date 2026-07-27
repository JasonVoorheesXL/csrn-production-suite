from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_rehearsal_service_does_not_import_flask() -> None:
    source = (ROOT / "operational_rehearsal_service.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    from_imports = {
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    assert "flask" not in imports
    assert all(not module.startswith("flask") for module in from_imports)


def test_rehearsal_policy_requires_two_full_rehearsals() -> None:
    from operational_rehearsal_service import OperationalRehearsalService

    assert OperationalRehearsalService.REQUIRED_REHEARSALS == 2
    assert any(item["required_each"] for item in OperationalRehearsalService.DRILLS)
    assert any(item["required_series"] for item in OperationalRehearsalService.DRILLS)


def test_release_freeze_uses_exact_confirmation_phrases() -> None:
    from operational_rehearsal_service import OperationalRehearsalService

    assert OperationalRehearsalService.FREEZE_CONFIRMATION == "FREEZE GAME DAY RELEASE"
    assert OperationalRehearsalService.UNFREEZE_CONFIRMATION == "UNFREEZE GAME DAY RELEASE"
    assert OperationalRehearsalService.COMPLETE_CONFIRMATION == "COMPLETE REHEARSAL"


def test_phase_6_6_documentation_retains_social_publishing_requirement() -> None:
    document = (
        ROOT / "docs" / "PHASE_6_6_OPERATIONAL_REHEARSAL_AND_RELEASE_FREEZE.md"
    ).read_text(encoding="utf-8")
    assert "two operator-recorded" in document
    assert "Phase 6.9 — Social Publishing Engine" in document
    assert "Facebook and X" in document
    assert "player headshots" in document
    assert "approved sponsors" in document


def test_game_day_roadmap_keeps_social_ux_and_recap_sequence() -> None:
    roadmap = (
        ROOT / "docs" / "PHASE_6_GAME_DAY_AND_COMMERCIAL_ROADMAP.md"
    ).read_text(encoding="utf-8")
    assert "### 6.6 Operational Rehearsal and Release Freeze" in roadmap
    assert "### 6.9 Social Publishing Engine" in roadmap
    assert "### 6.10 Commercial UX, Navigation, and Account Onboarding" in roadmap
    assert "### 6.11 Grounded Game Recap Engine" in roadmap
    assert "player headshots" in roadmap
    assert "approved sponsor assets" in roadmap
