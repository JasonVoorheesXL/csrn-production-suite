"""HTTP route blueprints for the CSRN Production Suite."""

from routes.system_routes import SystemRoutesDependencies, create_system_blueprint

__all__ = ["SystemRoutesDependencies", "create_system_blueprint"]
