"""Live captions were removed (2026-10-31): Facebook and YouTube caption
natively. Nothing in the app serves, polls or controls captions any more."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_caption_feature_files_are_gone() -> None:
    for name in ("caption_service.py", "caption_worker.py", "routes/caption_routes.py", "templates/captions.html"):
        assert not (ROOT / name).exists(), name


def test_no_caption_routes_or_requests_remain() -> None:
    import app as app_module

    rules = {rule.rule for rule in app_module.app.url_map.iter_rules()}
    assert not any(rule.startswith("/api/captions") or rule == "/captions" for rule in rules)
    runtime = (ROOT / "static" / "csrn-production-theme-runtime.js").read_text(encoding="utf-8")
    assert "/api/captions" not in runtime
    html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    for gone in ("/api/captions", "toggleLiveCaptions", "loadCaptionControls", "/captions'"):
        assert gone not in html, gone
