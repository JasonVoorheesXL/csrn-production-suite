from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_FILE = ROOT / "app.py"


ROUTE_IMPORTS = '''from routes.personnel_routes import (
    PersonnelRoutesDependencies,
    create_personnel_blueprint,
)
from routes.roster_routes import (
    RosterRoutesDependencies,
    create_roster_blueprint,
)
from routes.venue_routes import (
    VenueRoutesDependencies,
    create_venue_blueprint,
)
'''

ROUTE_REGISTRATION = '''PERSONNEL_ROUTES_BLUEPRINT = create_personnel_blueprint(
    PersonnelRoutesDependencies(
        require_auth=require_auth,
        get_personnel_service=get_personnel_service,
        headshots_dir=PERSONNEL_HEADSHOTS_DIR,
        normalize_personnel_id=PersonnelService.normalize_id,
    )
)
app.register_blueprint(PERSONNEL_ROUTES_BLUEPRINT)

ROSTER_ROUTES_BLUEPRINT = create_roster_blueprint(
    RosterRoutesDependencies(
        require_auth=require_auth,
        get_roster_service=get_roster_service,
    )
)
app.register_blueprint(ROSTER_ROUTES_BLUEPRINT)

VENUE_ROUTES_BLUEPRINT = create_venue_blueprint(
    VenueRoutesDependencies(
        require_auth=require_auth,
        get_venue_service=get_venue_service,
    )
)
app.register_blueprint(VENUE_ROUTES_BLUEPRINT)


'''


def _remove_until(text: str, start_marker: str, end_marker: str) -> str:
    start = text.find(start_marker)
    if start < 0:
        raise RuntimeError(f"Missing route migration marker: {start_marker!r}")
    end = text.find(end_marker, start)
    if end < 0:
        raise RuntimeError(f"Missing route migration marker: {end_marker!r}")
    return text[:start] + text[end:]


def apply(path: Path = APP_FILE) -> bool:
    text = path.read_text(encoding="utf-8")
    if "PERSONNEL_ROUTES_BLUEPRINT = create_personnel_blueprint(" in text:
        return False

    import_marker = '''from routes.association_routes import (
    AssociationRoutesDependencies,
    create_association_blueprint,
)
'''
    if import_marker not in text:
        raise RuntimeError("Association route import marker was not found.")
    text = text.replace(import_marker, import_marker + ROUTE_IMPORTS, 1)

    text = _remove_until(
        text,
        '@app.get("/api/broadcasters")\n',
        "SCHOOL_ROUTES_BLUEPRINT = create_school_blueprint(\n",
    )

    school_marker = "SCHOOL_ROUTES_BLUEPRINT = create_school_blueprint(\n"
    text = text.replace(school_marker, ROUTE_REGISTRATION + school_marker, 1)

    text = _remove_until(
        text,
        '@app.get("/api/venues")\n',
        '@app.get("/api/logos")\n',
    )

    path.write_text(text, encoding="utf-8")
    return True


def main() -> None:
    changed = apply()
    if changed:
        print("Phase 5.4 roster, personnel, and venue route integration applied.")
    else:
        print("Phase 5.4 route integration was already present.")


if __name__ == "__main__":
    main()
