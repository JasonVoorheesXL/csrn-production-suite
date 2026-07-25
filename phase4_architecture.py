from __future__ import annotations

import ast
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SERVICE_BOUNDARIES: tuple[tuple[str, str], ...] = (
    ("security_service", "SecurityService"),
    ("broadcast_package_service", "BroadcastPackageService"),
    ("school_service", "SchoolService"),
    ("roster_service", "RosterService"),
    ("sponsor_service", "SponsorService"),
    ("venue_service", "VenueService"),
    ("broadcast_service", "BroadcastService"),
    ("personnel_service", "PersonnelService"),
    ("asset_service", "AssetService"),
    ("graphics_service", "GraphicsService"),
    ("logo_service", "LogoService"),
    ("obs_service", "OBSService"),
    ("configuration_service", "ConfigurationService"),
    ("state_service", "StateService"),
    ("diagnostics_service", "DiagnosticsService"),
    ("upgrade_service", "UpgradeService"),
    ("event_service", "EventService"),
    ("rules_service", "RulesService"),
    ("statistics_service", "StatisticsService"),
    ("game_operations_service", "GameOperationsService"),
    ("support_media_service", "SupportMediaService"),
    ("broadcast_lifecycle_service", "BroadcastLifecycleService"),
    ("association_import_service", "AssociationImportService"),
    ("association_supplement_service", "AssociationSupplementService"),
    ("association_profile_service", "AssociationProfileService"),
    ("association_source_service", "AssociationSourceService"),
    ("association_workflow_service", "AssociationWorkflowService"),
)

FINAL_DELEGATION_MARKERS: tuple[str, ...] = (
    "get_broadcast_lifecycle_service().load(",
    "get_broadcast_lifecycle_service().initialize(",
    "get_broadcast_lifecycle_service().start(",
    "get_broadcast_lifecycle_service().resume(",
    "get_game_operations_service().score(",
    "get_game_operations_service().set_values(",
    "get_game_operations_service().toggle_scorebug(",
    "get_game_operations_service().toggle_halftime(",
    "get_game_operations_service().end_game(",
    "get_game_operations_service().reset_data(",
    "get_game_operations_service().new_broadcast(",
    "get_support_media_service().upload_headshot(",
    "get_support_media_service().connection_info(",
    "get_support_media_service().qr_svg(",
    "get_rules_service().clock_control(",
    "get_rules_service().field_direction(",
    "get_rules_service().play(",
    "get_event_service().trigger(",
    "get_event_service().quick_correction(",
    "get_event_service().edit(",
    "get_event_service().corrections(",
    "get_statistics_service().report(",
)

FORBIDDEN_APP_IMPLEMENTATION_MARKERS: tuple[str, ...] = (
    "qrcode.make(",
    "socket.getaddrinfo(",
    "Image.open(io.BytesIO(raw))",
)

FORBIDDEN_SERVICE_IMPORT_ROOTS = {"flask", "werkzeug"}


@dataclass(frozen=True)
class ArchitectureAuditResult:
    ok: bool
    errors: tuple[str, ...]
    services_checked: int
    app_lines: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "errors": list(self.errors),
            "services_checked": self.services_checked,
            "app_lines": self.app_lines,
        }


def _import_roots(tree: ast.AST) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".", 1)[0])
    return roots


def _class_names(tree: ast.AST) -> set[str]:
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef)
    }


def audit_phase_4(root: Path) -> ArchitectureAuditResult:
    root = Path(root)
    errors: list[str] = []
    app_path = root / "app.py"
    if not app_path.is_file():
        return ArchitectureAuditResult(False, ("app.py is missing",), 0, 0)

    app_source = app_path.read_text(encoding="utf-8")
    app_tree = ast.parse(app_source, filename=str(app_path))
    imported_classes: dict[str, set[str]] = {}
    for node in ast.walk(app_tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported_classes.setdefault(node.module, set()).update(
                alias.name for alias in node.names
            )

    for module_name, class_name in SERVICE_BOUNDARIES:
        service_path = root / f"{module_name}.py"
        if not service_path.is_file():
            errors.append(f"missing service module: {service_path.name}")
            continue
        source = service_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(service_path))
        roots = _import_roots(tree)
        forbidden = sorted(roots & FORBIDDEN_SERVICE_IMPORT_ROOTS)
        if forbidden:
            errors.append(
                f"{service_path.name} imports web-framework boundary: "
                + ", ".join(forbidden)
            )
        classes = _class_names(tree)
        if class_name not in classes:
            errors.append(f"{service_path.name} does not define {class_name}")
        if not any(name.endswith("Result") for name in classes):
            errors.append(f"{service_path.name} has no result-contract class")
        if class_name not in imported_classes.get(module_name, set()):
            errors.append(f"app.py does not import {class_name} from {module_name}")

    for marker in FINAL_DELEGATION_MARKERS:
        if marker not in app_source:
            errors.append(f"missing route delegation marker: {marker}")

    for marker in FORBIDDEN_APP_IMPLEMENTATION_MARKERS:
        if marker in app_source:
            errors.append(f"business implementation leaked into app.py: {marker}")

    app_import_roots = _import_roots(app_tree)
    for stale_root in ("qrcode", "socket"):
        if stale_root in app_import_roots:
            errors.append(f"obsolete app.py import remains: {stale_root}")

    return ArchitectureAuditResult(
        ok=not errors,
        errors=tuple(errors),
        services_checked=len(SERVICE_BOUNDARIES),
        app_lines=len(app_source.splitlines()),
    )


def main() -> int:
    root = Path(__file__).resolve().parent
    result = audit_phase_4(root)
    print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
