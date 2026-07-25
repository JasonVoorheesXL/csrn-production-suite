"""HTTP route blueprints for the CSRN Production Suite."""

from routes.association_routes import (
    AssociationRoutesDependencies,
    create_association_blueprint,
)
from routes.school_routes import SchoolRoutesDependencies, create_school_blueprint
from routes.security_upgrade_routes import (
    SecurityUpgradeRoutesDependencies,
    create_security_upgrade_blueprint,
)
from routes.system_routes import SystemRoutesDependencies, create_system_blueprint

__all__ = [
    "AssociationRoutesDependencies",
    "SchoolRoutesDependencies",
    "SecurityUpgradeRoutesDependencies",
    "SystemRoutesDependencies",
    "create_association_blueprint",
    "create_school_blueprint",
    "create_security_upgrade_blueprint",
    "create_system_blueprint",
]
