from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_migration_module():
    path = ROOT / "tools" / "apply_phase_4_12.py"
    spec = importlib.util.spec_from_file_location("phase_4_12_migration", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_phase_4_12_migration_integrates_logo_service_and_is_idempotent(
    tmp_path: Path,
) -> None:
    target = tmp_path / "app.py"
    target.write_text(
        (ROOT / "app.py").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    module = load_migration_module()
    module.APP_PATH = target

    module.main()
    first = target.read_text(encoding="utf-8")
    module.main()
    second = target.read_text(encoding="utf-8")

    assert first == second
    assert "from logo_service import LogoService" in first
    assert "LOGO_SERVICE: LogoService | None = None" in first
    assert "get_logo_service().process_candidate(" in first
    assert "get_logo_service().list_records(" in first
    assert "return LogoService.extract_colors(image)" in first
    assert "return jsonify(load_logos())" not in first
