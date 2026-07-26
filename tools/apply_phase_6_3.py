from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_FILE = ROOT / "app.py"
PHASE5_ARCHITECTURE_FILE = ROOT / "phase5_architecture.py"

SERVICE_IMPORT = (
    "from commissioning_service import HardwareOBSCommissioningService\n"
)
ROUTE_IMPORT = '''from routes.commissioning_routes import (
    CommissioningRoutesDependencies,
    create_commissioning_blueprint,
)
'''
CONSTANT = (
    'COMMISSIONING_FILE = DATA_DIR / "Settings" / "hardware_commissioning.json"\n'
)

SERVICE_AND_ROUTES = '''COMMISSIONING_SERVICE: HardwareOBSCommissioningService | None = None


def get_commissioning_service() -> HardwareOBSCommissioningService:
    global COMMISSIONING_SERVICE
    if COMMISSIONING_SERVICE is None:
        COMMISSIONING_SERVICE = HardwareOBSCommissioningService(
            profile_file=COMMISSIONING_FILE,
            load_config=load_config,
            validate_obs=lambda: get_obs_service().test_connection().data["obs"],
            clock=time.time,
        )
    return COMMISSIONING_SERVICE


COMMISSIONING_ROUTES_BLUEPRINT = create_commissioning_blueprint(
    CommissioningRoutesDependencies(
        require_auth=require_auth,
        get_commissioning_service=lambda: get_commissioning_service(),
    )
)
APPLICATION_BLUEPRINTS.append(COMMISSIONING_ROUTES_BLUEPRINT)


'''


def apply_app(path: Path = APP_FILE) -> bool:
    text = path.read_text(encoding="utf-8")
    if "COMMISSIONING_ROUTES_BLUEPRINT = " in text:
        return False

    service_marker = "from recovery_service import RecoveryService\n"
    if service_marker not in text:
        raise RuntimeError("RecoveryService import marker was not found.")
    text = text.replace(service_marker, service_marker + SERVICE_IMPORT, 1)

    route_marker = '''from routes.recovery_routes import (
    RecoveryRoutesDependencies,
    create_recovery_blueprint,
)
'''
    if route_marker not in text:
        raise RuntimeError("Recovery route import marker was not found.")
    text = text.replace(route_marker, route_marker + ROUTE_IMPORT, 1)

    constant_marker = 'GAME_DAY_RECOVERY_DIR = DATA_DIR / "Backups" / "Recovery"\n'
    if constant_marker not in text:
        raise RuntimeError("Recovery directory marker was not found.")
    text = text.replace(constant_marker, constant_marker + CONSTANT, 1)

    registration_marker = "SUPPORT_MEDIA_SERVICE: SupportMediaService | None = None\n"
    if registration_marker not in text:
        raise RuntimeError("Support-media service marker was not found.")
    text = text.replace(
        registration_marker,
        SERVICE_AND_ROUTES + registration_marker,
        1,
    )

    path.write_text(text, encoding="utf-8")
    return True


def apply_phase5_audit(path: Path = PHASE5_ARCHITECTURE_FILE) -> bool:
    text = path.read_text(encoding="utf-8")
    if '    "commissioning_routes",\n' in text:
        return False
    marker = '    "broadcast_routes",\n'
    if marker not in text:
        raise RuntimeError("Phase 5 Blueprint audit marker was not found.")
    text = text.replace(
        marker,
        marker + '    "commissioning_routes",\n',
        1,
    )
    path.write_text(text, encoding="utf-8")
    return True


def apply() -> bool:
    changed = False
    changed = apply_app() or changed
    changed = apply_phase5_audit() or changed
    return changed


def main() -> None:
    if apply():
        print("Phase 6.3 hardware and OBS commissioning integration applied.")
    else:
        print("Phase 6.3 commissioning integration was already present.")


if __name__ == "__main__":
    main()
