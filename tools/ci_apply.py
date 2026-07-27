from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"
ARCHITECTURE = ROOT / "phase5_architecture.py"
VERSION = ROOT / "VERSION.txt"
ROADMAP = ROOT / "docs" / "PHASE_6_GAME_DAY_AND_COMMERCIAL_ROADMAP.md"
THEME_SERVICE = ROOT / "theme_service.py"
THEME_STATE = ROOT / "Data" / "Themes" / "theme_state.json"
OVERLAY_TEMPLATES = (
    ROOT / "templates" / "overlay.html",
    ROOT / "templates" / "captions.html",
    ROOT / "templates" / "weather.html",
)
THEME_LINK = '  <link rel="stylesheet" href="/themes/current.css">\n'


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"Phase 6.8 integration anchor missing: {label}")
    return text.replace(old, new, 1)


def patch_app() -> None:
    source = APP.read_text(encoding="utf-8")
    source = replace_once(
        source,
        "from deployment_service import DeploymentService\n",
        "from deployment_service import DeploymentService\n"
        "from theme_service import GraphicsThemeService\n",
        "theme service import",
    )
    source = replace_once(
        source,
        "from routes.deployment_routes import (\n"
        "    DeploymentRoutesDependencies,\n"
        "    create_deployment_blueprint,\n"
        ")\n",
        "from routes.deployment_routes import (\n"
        "    DeploymentRoutesDependencies,\n"
        "    create_deployment_blueprint,\n"
        ")\n"
        "from routes.theme_routes import (\n"
        "    ThemeRoutesDependencies,\n"
        "    create_theme_blueprint,\n"
        ")\n",
        "theme route imports",
    )
    source = replace_once(
        source,
        'RELEASE_MANIFEST_FILE = DATA_DIR / "Releases" / "game_day_release_manifest.json"\n',
        'RELEASE_MANIFEST_FILE = DATA_DIR / "Releases" / "game_day_release_manifest.json"\n'
        'THEME_STATE_FILE = DATA_DIR / "Themes" / "theme_state.json"\n',
        "theme state path",
    )
    source = replace_once(
        source,
        "RUNTIME_VERSION = (\n"
        "    \"Version 1.13.0-alpha.6g — Installer, Updates, and Licensing Foundation\"\n"
        ")\n"
        "RUNTIME_BUILD = \"V1.13A6G-INSTALLER-UPDATES-LICENSING\"\n",
        "RUNTIME_VERSION = (\n"
        "    \"Version 1.13.0-alpha.6h — Graphics Theme Engine\"\n"
        ")\n"
        "RUNTIME_BUILD = \"V1.13A6H-GRAPHICS-THEME-ENGINE\"\n",
        "runtime identity",
    )
    source = replace_once(
        source,
        '    "social": {\n',
        '    "graphics_theme": {\n'
        '        "active_preset": "modern_network",\n'
        '        "school_color_adaptation": True,\n'
        '        "season_lock": False,\n'
        '    },\n'
        '    "social": {\n',
        "theme configuration",
    )
    source = replace_once(
        source,
        '"Rehearsals", "Releases"):\n',
        '"Rehearsals", "Releases", "Themes"):\n',
        "theme data directory",
    )
    service_block = '''THEME_SERVICE: GraphicsThemeService | None = None


def get_theme_service() -> GraphicsThemeService:
    global THEME_SERVICE
    if THEME_SERVICE is None:
        THEME_SERVICE = GraphicsThemeService(
            state_file=THEME_STATE_FILE,
            load_state=load_state,
            load_config=load_config,
            clock=time.time,
        )
    return THEME_SERVICE


THEME_ROUTES_BLUEPRINT = create_theme_blueprint(
    ThemeRoutesDependencies(
        require_auth=require_auth,
        get_theme_service=lambda: get_theme_service(),
    )
)
APPLICATION_BLUEPRINTS.append(THEME_ROUTES_BLUEPRINT)


'''
    source = replace_once(
        source,
        "SUPPORT_MEDIA_SERVICE: SupportMediaService | None = None\n",
        service_block + "SUPPORT_MEDIA_SERVICE: SupportMediaService | None = None\n",
        "theme service registration",
    )
    APP.write_text(source, encoding="utf-8")


def patch_architecture() -> None:
    source = ARCHITECTURE.read_text(encoding="utf-8")
    source = replace_once(
        source,
        '    "system_routes",\n',
        '    "system_routes",\n    "theme_routes",\n',
        "theme blueprint audit",
    )
    source = replace_once(
        source,
        '    "system_routes.get_state",\n',
        '    "system_routes.get_state",\n'
        '    "theme_routes.current_theme_css",\n'
        '    "theme_routes.public_theme_state",\n',
        "theme public endpoints",
    )
    ARCHITECTURE.write_text(source, encoding="utf-8")


def patch_templates() -> None:
    for path in OVERLAY_TEMPLATES:
        source = path.read_text(encoding="utf-8")
        if "/themes/current.css" in source:
            continue
        if "</head>" not in source:
            raise RuntimeError(f"Phase 6.8 template head missing: {path.name}")
        path.write_text(source.replace("</head>", THEME_LINK + "</head>", 1), encoding="utf-8")


def patch_theme_service() -> None:
    source = THEME_SERVICE.read_text(encoding="utf-8")
    source = source.replace(
        "{self._rgba(tokens['surface'], 0.96) if False else tokens['surface']}",
        "{tokens['surface']}",
    )
    THEME_SERVICE.write_text(source, encoding="utf-8")


def create_theme_state() -> None:
    THEME_STATE.parent.mkdir(parents=True, exist_ok=True)
    if THEME_STATE.exists():
        return
    THEME_STATE.write_text(
        json.dumps(
            {
                "schema": 1,
                "active_preset": "modern_network",
                "overrides": {},
                "locked": False,
                "locked_at": 0,
                "variants": {},
                "updated_at": 0,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def patch_roadmap() -> None:
    source = ROADMAP.read_text(encoding="utf-8")
    marker = "Theme Engine implementation status: Phase 6.8 foundation integrated."
    if marker in source:
        return
    anchor = "Theme tokens control scorebugs, lower thirds, player/personnel cards, sponsor panels, captions, weather graphics, social graphics, typography, borders, textures, transitions, and school-color adaptation. Presets must be original genre-inspired designs and must not copy a television network package.\n"
    if anchor not in source:
        raise RuntimeError("Phase 6.8 roadmap anchor missing")
    source = source.replace(anchor, anchor + "\n" + marker + "\n", 1)
    ROADMAP.write_text(source, encoding="utf-8")


def append_release_notes() -> None:
    changelog = ROOT / "CHANGELOG.txt"
    note = (
        "\nPhase 6.8 - Graphics Theme Engine\n"
        "- Eight original presets through one shared token engine.\n"
        "- Controlled overrides, saved variants, and season locking.\n"
        "- Shared scorebug, lower-third, caption, weather, and social-card styling.\n"
    )
    if changelog.exists():
        source = changelog.read_text(encoding="utf-8")
        if "Phase 6.8 - Graphics Theme Engine" not in source:
            changelog.write_text(source.rstrip() + "\n" + note, encoding="utf-8")


def apply() -> None:
    patch_app()
    patch_architecture()
    patch_templates()
    patch_theme_service()
    create_theme_state()
    patch_roadmap()
    append_release_notes()
    VERSION.write_text("1.13.0-alpha.6h\n", encoding="utf-8")


if __name__ == "__main__":
    apply()
    print("Phase 6.8 graphics theme integration applied.")
