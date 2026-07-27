from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"
ARCHITECTURE = ROOT / "phase5_architecture.py"
VERSION = ROOT / "VERSION.txt"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"Phase 6.7 integration anchor missing: {label}")
    return text.replace(old, new, 1)


def apply() -> None:
    source = APP.read_text(encoding="utf-8")
    source = replace_once(source, "import os\n", "import os\nimport sys\n", "sys import")
    source = replace_once(
        source,
        "from operational_rehearsal_service import OperationalRehearsalService\n",
        "from operational_rehearsal_service import OperationalRehearsalService\n"
        "from product_paths import resolve_product_paths\n"
        "from entitlement_service import EntitlementService\n"
        "from deployment_service import DeploymentService\n",
        "deployment service imports",
    )
    source = replace_once(
        source,
        "from routes.rehearsal_routes import (\n"
        "    RehearsalRoutesDependencies,\n"
        "    create_rehearsal_blueprint,\n"
        ")\n",
        "from routes.rehearsal_routes import (\n"
        "    RehearsalRoutesDependencies,\n"
        "    create_rehearsal_blueprint,\n"
        ")\n"
        "from routes.deployment_routes import (\n"
        "    DeploymentRoutesDependencies,\n"
        "    create_deployment_blueprint,\n"
        ")\n",
        "deployment route imports",
    )
    source = replace_once(
        source,
        "BASE_DIR = Path(__file__).resolve().parent\n"
        "STATE_FILE = BASE_DIR / \"state.json\"\n"
        "SECURITY_FILE = BASE_DIR / \"security.json\"\n"
        "DATA_DIR = BASE_DIR / \"Data\"\n",
        "BASE_DIR = Path(__file__).resolve().parent\n"
        "PRODUCT_PATHS = resolve_product_paths(\n"
        "    BASE_DIR,\n"
        "    frozen=bool(getattr(sys, \"frozen\", False) or \"--installed\" in sys.argv),\n"
        ")\n"
        "PRODUCT_PATHS.ensure()\n"
        "STATE_FILE = PRODUCT_PATHS.state_file\n"
        "SECURITY_FILE = PRODUCT_PATHS.security_file\n"
        "DATA_DIR = PRODUCT_PATHS.data_dir\n",
        "stable product paths",
    )
    source = replace_once(
        source,
        "RUNTIME_VERSION = (\n"
        "    \"Version 1.13.0-alpha.6f — Operational Rehearsal and Release Freeze\"\n"
        ")\n"
        "RUNTIME_BUILD = \"V1.13A6F-OPERATIONAL-REHEARSAL-RELEASE-FREEZE\"\n",
        "RUNTIME_VERSION = (\n"
        "    \"Version 1.13.0-alpha.6g — Installer, Updates, and Licensing Foundation\"\n"
        ")\n"
        "RUNTIME_BUILD = \"V1.13A6G-INSTALLER-UPDATES-LICENSING\"\n",
        "runtime identity",
    )
    source = replace_once(
        source,
        "    \"social\": {\n",
        "    \"licensing\": {\n"
        "        \"provider\": \"\",\n"
        "        \"enforcement_mode\": \"installed_only\",\n"
        "        \"activation_endpoint\": \"\",\n"
        "    },\n"
        "    \"social\": {\n",
        "licensing configuration",
    )
    service_block = '''ENTITLEMENT_SERVICE: EntitlementService | None = None


def get_entitlement_service() -> EntitlementService:
    global ENTITLEMENT_SERVICE
    if ENTITLEMENT_SERVICE is None:
        ENTITLEMENT_SERVICE = EntitlementService(
            paths=PRODUCT_PATHS,
            verifier=None,
            clock=time.time,
        )
    return ENTITLEMENT_SERVICE


DEPLOYMENT_SERVICE: DeploymentService | None = None


def get_deployment_service() -> DeploymentService:
    global DEPLOYMENT_SERVICE
    if DEPLOYMENT_SERVICE is None:
        DEPLOYMENT_SERVICE = DeploymentService(
            paths=PRODUCT_PATHS,
            version_file=VERSION_FILE,
            entitlement_service=get_entitlement_service(),
            create_snapshot=lambda **kwargs: get_game_day_safety_service().create_snapshot(**kwargs),
            clock=time.time,
        )
    return DEPLOYMENT_SERVICE


DEPLOYMENT_ROUTES_BLUEPRINT = create_deployment_blueprint(
    DeploymentRoutesDependencies(
        require_auth=require_auth,
        get_deployment_service=lambda: get_deployment_service(),
        get_entitlement_service=lambda: get_entitlement_service(),
    )
)
APPLICATION_BLUEPRINTS.append(DEPLOYMENT_ROUTES_BLUEPRINT)


'''
    source = replace_once(
        source,
        "SUPPORT_MEDIA_SERVICE: SupportMediaService | None = None\n",
        service_block + "SUPPORT_MEDIA_SERVICE: SupportMediaService | None = None\n",
        "deployment service registration",
    )
    APP.write_text(source, encoding="utf-8")

    architecture = ARCHITECTURE.read_text(encoding="utf-8")
    architecture = replace_once(
        architecture,
        '    "commissioning_routes",\n',
        '    "commissioning_routes",\n    "deployment_routes",\n',
        "deployment blueprint audit",
    )
    ARCHITECTURE.write_text(architecture, encoding="utf-8")
    VERSION.write_text("1.13.0-alpha.6g\n", encoding="utf-8")

    changelog = ROOT / "CHANGELOG.txt"
    marker = "Phase 6.7 - Installer, Updates, and Licensing Foundation"
    if changelog.exists():
        content = changelog.read_text(encoding="utf-8")
        if marker not in content:
            changelog.write_text(
                content.rstrip()
                + "\n\n"
                + marker
                + "\n- External installed-mode customer data paths.\n"
                + "- Hash-validated staged updates and customer-safe support bundles.\n"
                + "- Provider-verified licensing and feature/sport entitlement boundaries.\n",
                encoding="utf-8",
            )


if __name__ == "__main__":
    apply()
