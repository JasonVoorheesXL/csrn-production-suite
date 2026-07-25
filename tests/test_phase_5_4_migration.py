from __future__ import annotations

from pathlib import Path

from tools.apply_phase_5_4 import apply


LEGACY_APP = '''from routes.association_routes import (
    AssociationRoutesDependencies,
    create_association_blueprint,
)


@app.get("/api/broadcasters")
@require_auth
def list_broadcasters():
    pass


@app.get("/api/rosters")
@require_auth
def list_rosters():
    pass


SCHOOL_ROUTES_BLUEPRINT = create_school_blueprint(
    SchoolRoutesDependencies(require_auth=require_auth, get_school_service=get_school_service)
)
app.register_blueprint(SCHOOL_ROUTES_BLUEPRINT)


@app.get("/api/venues")
@require_auth
def list_venues():
    pass


@app.get("/api/logos")
@require_auth
def list_logos():
    pass
'''


def test_phase_5_4_migration_registers_blueprints_and_removes_routes(tmp_path: Path) -> None:
    target = tmp_path / "app.py"
    target.write_text(LEGACY_APP, encoding="utf-8")

    assert apply(target) is True
    migrated = target.read_text(encoding="utf-8")

    assert "from routes.personnel_routes import (" in migrated
    assert "from routes.roster_routes import (" in migrated
    assert "from routes.venue_routes import (" in migrated
    assert "PERSONNEL_ROUTES_BLUEPRINT = create_personnel_blueprint(" in migrated
    assert "ROSTER_ROUTES_BLUEPRINT = create_roster_blueprint(" in migrated
    assert "VENUE_ROUTES_BLUEPRINT = create_venue_blueprint(" in migrated
    assert "app.register_blueprint(PERSONNEL_ROUTES_BLUEPRINT)" in migrated
    assert "app.register_blueprint(ROSTER_ROUTES_BLUEPRINT)" in migrated
    assert "app.register_blueprint(VENUE_ROUTES_BLUEPRINT)" in migrated
    assert '@app.get("/api/broadcasters")' not in migrated
    assert '@app.get("/api/rosters")' not in migrated
    assert '@app.get("/api/venues")' not in migrated
    assert '@app.get("/api/logos")' in migrated
    assert apply(target) is False
