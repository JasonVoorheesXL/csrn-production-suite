from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

from phase4_architecture import (
    FINAL_DELEGATION_MARKERS,
    FORBIDDEN_APP_IMPLEMENTATION_MARKERS,
    SERVICE_BOUNDARIES,
    audit_phase_4,
)


ROOT = Path(__file__).resolve().parents[1]


def test_phase_4_manifest_contains_all_service_boundaries() -> None:
    assert len(SERVICE_BOUNDARIES) == 27
    assert len({module for module, _ in SERVICE_BOUNDARIES}) == 27
    assert len({class_name for _, class_name in SERVICE_BOUNDARIES}) == 27


def test_phase_4_architecture_audit_passes() -> None:
    result = audit_phase_4(ROOT)
    assert result.ok, "\n".join(result.errors)
    assert result.services_checked == 27
    assert result.app_lines > 1000


def test_every_service_module_is_flask_independent() -> None:
    for module_name, _ in SERVICE_BOUNDARIES:
        source = (ROOT / f"{module_name}.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported_roots: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_roots.update(
                    alias.name.split(".", 1)[0] for alias in node.names
                )
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_roots.add(node.module.split(".", 1)[0])
        assert "flask" not in imported_roots, module_name
        assert "werkzeug" not in imported_roots, module_name


def test_app_imports_every_service_class() -> None:
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.setdefault(node.module, set()).update(
                alias.name for alias in node.names
            )
    for module_name, class_name in SERVICE_BOUNDARIES:
        assert class_name in imported.get(module_name, set()), (
            module_name,
            class_name,
        )


def test_final_operational_routes_delegate_to_services() -> None:
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    missing = [marker for marker in FINAL_DELEGATION_MARKERS if marker not in source]
    assert missing == []


def test_extracted_implementations_do_not_leak_back_into_app() -> None:
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    leaked = [
        marker
        for marker in FORBIDDEN_APP_IMPLEMENTATION_MARKERS
        if marker in source
    ]
    assert leaked == []


def test_service_modules_expose_result_contract_classes() -> None:
    for module_name, _ in SERVICE_BOUNDARIES:
        source = (ROOT / f"{module_name}.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        class_names = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef)
        }
        assert any(name.endswith("Result") for name in class_names), module_name


def test_architecture_audit_cli_succeeds() -> None:
    result = subprocess.run(
        [sys.executable, "phase4_architecture.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert '"ok": true' in result.stdout
    assert '"services_checked": 27' in result.stdout
