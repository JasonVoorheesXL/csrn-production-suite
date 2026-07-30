from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_recap_service_declares_recorded_data_only_boundary() -> None:
    source = (ROOT / "recap_service.py").read_text(encoding="utf-8")
    assert "Deterministic recap generation from recorded CSRN game data only" in source
    assert "Missing" in source
    assert "source_hash" in source
    assert "operator_edited_fields" in source


def test_recap_service_filters_undone_events_and_plays() -> None:
    source = (ROOT / "recap_service.py").read_text(encoding="utf-8")
    assert "not row.get(\"undone\")" in source
    assert "_clean_rows" in source


def test_recap_approval_and_stale_guard_are_required() -> None:
    source = (ROOT / "recap_service.py").read_text(encoding="utf-8")
    assert "APPROVE GROUNDED RECAP" in source
    assert "RECAP_STALE" in source
    assert "regenerate" in source


def test_recap_routes_are_integrated_and_authenticated_by_design() -> None:
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    architecture = (ROOT / "phase5_architecture.py").read_text(encoding="utf-8")
    routes = (ROOT / "routes" / "recap_routes.py").read_text(encoding="utf-8")
    assert "create_recap_blueprint" in app
    assert "get_recap_service" in app
    assert '"recap_routes"' in architecture
    assert routes.count("@routes.") == routes.count("@dependencies.require_auth")


def test_phase_6_10_document_preserves_no_invention_rule() -> None:
    source = (ROOT / "docs" / "PHASE_6_10_GROUNDED_GAME_RECAP_ENGINE.md").read_text(encoding="utf-8")
    assert "not permitted to fill gaps" in source
    assert "Missing information" in source
    assert "APPROVE GROUNDED RECAP" in source


def test_x_manual_only_boundary_remains_after_recap_integration() -> None:
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    platforms = (ROOT / "social_platforms.py").read_text(encoding="utf-8")
    assert '"x_mode": "assisted_manual"' in app
    assert '"x_oauth": False' in app
    assert "XPlatformAdapter" not in platforms
    assert "/2/tweets" not in platforms


def test_command_center_navigation_exposes_social_and_recaps() -> None:
    source = (ROOT / "static" / "csrn-navigation.js").read_text(encoding="utf-8")
    assert "['social', 'Social Publishing', '/social']" in source
    assert "['recaps', 'Game Recaps', '/recaps']" in source


def test_release_freeze_document_uses_manual_x_boundary() -> None:
    source = (ROOT / "docs" / "PHASE_6_6_OPERATIONAL_REHEARSAL_AND_RELEASE_FREEZE.md").read_text(encoding="utf-8")
    assert "assisted-manual X packages" in source
    assert "X does not use OAuth" in source
    assert "Facebook and X publishing" not in source
