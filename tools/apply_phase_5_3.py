from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_FILE = ROOT / "app.py"


ROUTE_IMPORTS = '''from routes.school_routes import (
    SchoolRoutesDependencies,
    create_school_blueprint,
)
from routes.association_routes import (
    AssociationRoutesDependencies,
    create_association_blueprint,
)
'''

ROUTE_REGISTRATION = '''SCHOOL_ROUTES_BLUEPRINT = create_school_blueprint(
    SchoolRoutesDependencies(
        require_auth=require_auth,
        get_school_service=get_school_service,
    )
)
app.register_blueprint(SCHOOL_ROUTES_BLUEPRINT)

ASSOCIATION_ROUTES_BLUEPRINT = create_association_blueprint(
    AssociationRoutesDependencies(
        require_auth=require_auth,
        get_profile_service=get_association_profile_service,
        get_workflow_service=get_association_workflow_service,
        get_import_service=get_association_import_service,
        get_supplement_service=get_association_supplement_service,
        load_mhsaa_profile=lambda: load_json(MHSAA_5A_PROFILE_FILE, {}),
        load_mhsaa_manifest=lambda: load_json(
            MHSAA_5A_FILE,
            {"schools": []},
        ),
        load_mhsaa_branding_manifest=lambda: load_json(
            MHSAA_5A_BRANDING_FILE,
            {"schools": []},
        ),
        load_mhsaa_enrichment_manifest=lambda: load_json(
            MHSAA_5A_ENRICHMENT_FILE,
            {"schools": []},
        ),
    )
)
app.register_blueprint(ASSOCIATION_ROUTES_BLUEPRINT)


'''


def apply(path: Path = APP_FILE) -> bool:
    text = path.read_text(encoding="utf-8")
    if "SCHOOL_ROUTES_BLUEPRINT = create_school_blueprint(" in text:
        return False

    import_marker = '''from routes.security_upgrade_routes import (
    SecurityUpgradeRoutesDependencies,
    create_security_upgrade_blueprint,
)
'''
    if import_marker not in text:
        raise RuntimeError("Security/upgrade route import marker was not found.")
    text = text.replace(import_marker, import_marker + ROUTE_IMPORTS, 1)

    start_marker = '@app.get("/api/schools")\n'
    end_marker = "def _hex(rgb: tuple[int, int, int]) -> str:\n"
    start = text.find(start_marker)
    if start < 0:
        raise RuntimeError("School route migration start marker was not found.")
    end = text.find(end_marker, start)
    if end < 0:
        raise RuntimeError("Association route migration end marker was not found.")

    text = text[:start] + ROUTE_REGISTRATION + text[end:]
    path.write_text(text, encoding="utf-8")
    return True


def main() -> None:
    changed = apply()
    if changed:
        print("Phase 5.3 school and association Blueprint integration applied.")
    else:
        print("Phase 5.3 school and association Blueprint integration was already present.")


if __name__ == "__main__":
    main()
