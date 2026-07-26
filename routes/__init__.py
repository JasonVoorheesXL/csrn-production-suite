"""HTTP route blueprints for the CSRN Production Suite."""

from routes.asset_routes import AssetRoutesDependencies, create_asset_blueprint
from routes.association_routes import (
    AssociationRoutesDependencies,
    create_association_blueprint,
)
from routes.broadcast_lifecycle_routes import (
    BroadcastLifecycleRoutesDependencies,
    create_broadcast_lifecycle_blueprint,
)
from routes.broadcast_package_routes import (
    BroadcastPackageRoutesDependencies,
    create_broadcast_package_blueprint,
)
from routes.broadcast_routes import BroadcastRoutesDependencies, create_broadcast_blueprint
from routes.game_day_safety_routes import (
    GameDaySafetyRoutesDependencies,
    create_game_day_safety_blueprint,
)
from routes.graphics_routes import GraphicsRoutesDependencies, create_graphics_blueprint
from routes.live_game_routes import LiveGameRoutesDependencies, create_live_game_blueprint
from routes.logo_routes import LogoRoutesDependencies, create_logo_blueprint
from routes.obs_routes import OBSRoutesDependencies, create_obs_blueprint
from routes.page_routes import PageRoutesDependencies, create_page_blueprint
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
from routes.support_routes import SupportRoutesDependencies, create_support_blueprint
from routes.system_routes import SystemRoutesDependencies, create_system_blueprint
from routes.venue_routes import VenueRoutesDependencies, create_venue_blueprint

__all__ = [
    "AssetRoutesDependencies",
    "AssociationRoutesDependencies",
    "BroadcastLifecycleRoutesDependencies",
    "BroadcastPackageRoutesDependencies",
    "BroadcastRoutesDependencies",
    "GameDaySafetyRoutesDependencies",
    "GraphicsRoutesDependencies",
    "LiveGameRoutesDependencies",
    "LogoRoutesDependencies",
    "OBSRoutesDependencies",
    "PageRoutesDependencies",
    "PersonnelRoutesDependencies",
    "RosterRoutesDependencies",
    "SchoolRoutesDependencies",
    "SecurityUpgradeRoutesDependencies",
    "SponsorRoutesDependencies",
    "SupportRoutesDependencies",
    "SystemRoutesDependencies",
    "VenueRoutesDependencies",
    "create_asset_blueprint",
    "create_association_blueprint",
    "create_broadcast_blueprint",
    "create_broadcast_lifecycle_blueprint",
    "create_broadcast_package_blueprint",
    "create_game_day_safety_blueprint",
    "create_graphics_blueprint",
    "create_live_game_blueprint",
    "create_logo_blueprint",
    "create_obs_blueprint",
    "create_page_blueprint",
    "create_personnel_blueprint",
    "create_roster_blueprint",
    "create_school_blueprint",
    "create_security_upgrade_blueprint",
    "create_sponsor_blueprint",
    "create_support_blueprint",
    "create_system_blueprint",
    "create_venue_blueprint",
]
