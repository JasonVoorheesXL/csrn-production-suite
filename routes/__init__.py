"""HTTP route blueprints for the CSRN Production Suite."""

from routes.asset_routes import AssetRoutesDependencies, create_asset_blueprint
from routes.association_routes import (
    AssociationRoutesDependencies,
    create_association_blueprint,
)
from routes.logo_routes import LogoRoutesDependencies, create_logo_blueprint
from routes.personnel_routes import (
    PersonnelRoutesDependencies,
    create_personnel_blueprint,
)
from routes.roster_routes import RosterRoutesDependencies, create_roster_blueprint
from routes.school_routes import SchoolRoutesDependencies, create_school_blueprint
from routes.security_upgrade_routes import (
    SecurityUpgradeRoutesDependencies,
    create_security_upgrade_blueprint,
)
from routes.sponsor_routes import SponsorRoutesDependencies, create_sponsor_blueprint
from routes.system_routes import SystemRoutesDependencies, create_system_blueprint
from routes.venue_routes import VenueRoutesDependencies, create_venue_blueprint

__all__ = [
    "AssetRoutesDependencies",
    "AssociationRoutesDependencies",
    "LogoRoutesDependencies",
    "PersonnelRoutesDependencies",
    "RosterRoutesDependencies",
    "SchoolRoutesDependencies",
    "SecurityUpgradeRoutesDependencies",
    "SponsorRoutesDependencies",
    "SystemRoutesDependencies",
    "VenueRoutesDependencies",
    "create_asset_blueprint",
    "create_association_blueprint",
    "create_logo_blueprint",
    "create_personnel_blueprint",
    "create_roster_blueprint",
    "create_school_blueprint",
    "create_security_upgrade_blueprint",
    "create_sponsor_blueprint",
    "create_system_blueprint",
    "create_venue_blueprint",
]
