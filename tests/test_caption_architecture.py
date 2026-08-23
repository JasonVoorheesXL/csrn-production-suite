from __future__ import annotations

from pathlib import Path

import app
from application_factory import build_route_manifest


ROOT = Path(__file__).resolve().parents[1]


def test_caption_blueprint_registered() -> None:
    assert "caption_routes" in app.app.blueprints


def test_caption_public_routes_are_explicit() -> None:
    manifest = {entry.endpoint: entry for entry in build_route_manifest(app.app)}
    assert manifest["caption_routes.caption_overlay"].auth_required is False
    assert manifest["caption_routes.caption_overlay_state"].auth_required is False
    assert manifest["caption_routes.caption_status"].auth_required is True
    assert manifest["caption_routes.caption_audio_devices"].auth_required is True
    assert manifest["caption_routes.ingest_caption_segment"].auth_required is True


def test_caption_route_does_not_import_app() -> None:
    source = (ROOT / "routes" / "caption_routes.py").read_text(encoding="utf-8")
    assert "import app" not in source
    assert "from app import" not in source


def test_caption_worker_keeps_optional_dependencies_out_of_base_imports() -> None:
    source = (ROOT / "caption_worker.py").read_text(encoding="utf-8")
    assert "import sounddevice as sd" in source
    assert source.index("def _optional_dependencies") < source.index("import sounddevice as sd")


def test_weather_and_social_roadmap_requirements_are_retained() -> None:
    roadmap = (
        ROOT / "docs" / "PHASE_6_GAME_DAY_AND_COMMERCIAL_ROADMAP.md"
    ).read_text(encoding="utf-8")
    assert "6.5 Venue Weather Monitoring and Alert Overlay" in roadmap
    assert "6.9 Social Publishing Engine" in roadmap
    assert "player headshots" in roadmap
    assert "weather delays" in roadmap


