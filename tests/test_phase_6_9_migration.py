from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_phase_6_9_runtime_identity_is_applied() -> None:
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "Version 1.13.0-alpha.6i — Social Publishing Engine" in source
    assert "V1.13A6I-SOCIAL-PUBLISHING-ENGINE" in source
    assert (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip() == "1.13.0-alpha.6i"


def test_phase_6_9_services_and_routes_are_integrated() -> None:
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "SOCIAL_STATE_FILE" in source
    assert "SOCIAL_CARDS_DIR" in source
    assert "get_social_service" in source
    assert "create_social_blueprint" in source
    assert "default_adapter_registry" in source


def test_phase_6_9_event_handoff_is_integrated() -> None:
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    event = (ROOT / "event_service.py").read_text(encoding="utf-8")
    assert "on_event=lambda event: get_social_service().queue_event(event)" in app
    assert "self._on_event(copy.deepcopy(payload))" in event


def test_phase_6_9_social_blueprint_is_audited() -> None:
    architecture = (ROOT / "phase5_architecture.py").read_text(encoding="utf-8")
    assert '"social_routes"' in architecture


def test_phase_6_10_remains_next() -> None:
    roadmap = (ROOT / "docs" / "PHASE_6_GAME_DAY_AND_COMMERCIAL_ROADMAP.md").read_text(encoding="utf-8")
    assert "### 6.9 Social Publishing Engine" in roadmap
    assert "### 6.10 Grounded Game Recap Engine" in roadmap
