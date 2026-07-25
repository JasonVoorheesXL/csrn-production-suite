"""HTTP route blueprints for the CSRN Production Suite."""

from routes.security_upgrade_routes import (
    SecurityUpgradeRoutesDependencies,
    create_security_upgrade_blueprint,
)
from routes.system_routes import SystemRoutesDependencies, create_system_blueprint

__all__ = [
    "SecurityUpgradeRoutesDependencies",
    "SystemRoutesDependencies",
    "create_security_upgrade_blueprint",
    "create_system_blueprint",
]
