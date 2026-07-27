from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_migration():
    path = ROOT / "tools" / "apply_phase_6_10.py"
    spec = importlib.util.spec_from_file_location("apply_phase_6_10", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_phase_6_10_migration_is_idempotent() -> None:
    watched = [
        ROOT / "app.py",
        ROOT / "phase5_architecture.py",
        ROOT / "templates" / "index.html",
        ROOT / "templates" / "theme_manager.html",
        ROOT / "templates" / "social_manager.html",
        ROOT / "docs" / "PHASE_6_GAME_DAY_AND_COMMERCIAL_ROADMAP.md",
        ROOT / "tests" / "test_social_architecture.py",
        ROOT / "VERSION.txt",
    ]
    before = {path: path.read_text(encoding="utf-8") for path in watched}
    load_migration().apply()
    after = {path: path.read_text(encoding="utf-8") for path in watched}
    assert after == before


def test_phase_6_10_migration_keeps_customer_data_outside_templates() -> None:
    source = (ROOT / "tools" / "apply_phase_6_10.py").read_text(encoding="utf-8")
    assert 'OAUTH_STATE_FILE = DATA_DIR / "Settings"' in source
    assert 'OAUTH_VAULT_FILE = DATA_DIR / "Settings"' in source
    assert "Jason" not in (ROOT / "templates" / "setup_hub.html").read_text(encoding="utf-8")
    assert "Caledonia" not in (ROOT / "templates" / "setup_hub.html").read_text(encoding="utf-8")
