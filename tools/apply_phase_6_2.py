from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_FILE = ROOT / "app.py"
ARCHITECTURE_FILE = ROOT / "phase5_architecture.py"


SERVICE_IMPORTS = '''from social_card_renderer import SocialCardRenderer
from social_post_repository import SocialPostRepository
from social_publishers import FacebookPagePublisher, XPublisher
from social_publishing_service import SocialPublishingService
'''

ROUTE_IMPORTS = '''from routes.social_routes import (
    SocialRoutesDependencies,
    create_social_blueprint,
)
'''

SOCIAL_BLOCK = '''SOCIAL_POST_REPOSITORY = SocialPostRepository(
    CORE_PERSISTENCE,
    SOCIAL_POSTS_FILE,
)


def load_social_posts() -> list[dict[str, Any]]:
    ensure_data_architecture()
    return SOCIAL_POST_REPOSITORY.load()


def save_social_posts(items: list[dict[str, Any]]) -> None:
    ensure_data_architecture()
    SOCIAL_POST_REPOSITORY.save(items)


def resolve_social_media(value: str) -> Path | None:
    text = str(value or "").split("?", 1)[0].strip()
    if not text or text.startswith(("http://", "https://")):
        return None
    normalized = text.replace("\\", "/")
    candidate: Path | None = None
    allowed_root: Path | None = None
    if normalized.startswith("/roster-headshots/"):
        allowed_root = HEADSHOTS_DIR
        candidate = allowed_root / Path(normalized).name
    elif normalized.startswith("/asset-files/"):
        allowed_root = ASSET_UPLOAD_DIR
        candidate = allowed_root / Path(normalized).name
    elif normalized.startswith("/sponsor-logos/"):
        allowed_root = SPONSOR_UPLOAD_DIR
        candidate = allowed_root / Path(normalized).name
    elif normalized.startswith("/school-logos/"):
        parts = [part for part in normalized.split("/") if part]
        if len(parts) == 3:
            allowed_root = DATA_DIR / "Logos" / normalize_school_id(parts[1])
            candidate = allowed_root / Path(parts[2]).name
    elif "/" not in normalized:
        allowed_root = HEADSHOTS_DIR
        candidate = allowed_root / Path(normalized).name
    if candidate is None or allowed_root is None:
        return None
    try:
        resolved = candidate.resolve()
        resolved.relative_to(allowed_root.resolve())
    except (OSError, ValueError):
        return None
    return resolved if resolved.is_file() else None


SOCIAL_CARD_RENDERER = SocialCardRenderer(
    output_dir=SOCIAL_CARDS_DIR,
    resolve_media=resolve_social_media,
)

SOCIAL_PUBLISHING_SERVICE: SocialPublishingService | None = None


def get_social_publishing_service() -> SocialPublishingService:
    global SOCIAL_PUBLISHING_SERVICE
    if SOCIAL_PUBLISHING_SERVICE is None:
        SOCIAL_PUBLISHING_SERVICE = SocialPublishingService(
            load_posts=load_social_posts,
            save_posts=save_social_posts,
            load_state=load_state,
            load_rosters=load_rosters,
            sponsor_service=get_sponsor_service(),
            renderer=SOCIAL_CARD_RENDERER,
            cards_dir=SOCIAL_CARDS_DIR,
            publishers={
                "x": XPublisher(
                    access_token=os.environ.get("CSRN_X_USER_ACCESS_TOKEN", ""),
                    api_base=os.environ.get("CSRN_X_API_BASE", "https://api.x.com"),
                ),
                "facebook": FacebookPagePublisher(
                    page_id=os.environ.get("CSRN_FACEBOOK_PAGE_ID", ""),
                    page_access_token=os.environ.get(
                        "CSRN_FACEBOOK_PAGE_ACCESS_TOKEN",
                        "",
                    ),
                    api_base=os.environ.get(
                        "CSRN_FACEBOOK_API_BASE",
                        "https://graph.facebook.com",
                    ),
                ),
            },
            clock=time.time,
        )
    return SOCIAL_PUBLISHING_SERVICE


SOCIAL_ROUTES_BLUEPRINT = create_social_blueprint(
    SocialRoutesDependencies(
        require_auth=require_auth,
        get_social_service=lambda: get_social_publishing_service(),
        get_cards_dir=lambda: SOCIAL_CARDS_DIR,
    )
)
APPLICATION_BLUEPRINTS.append(SOCIAL_ROUTES_BLUEPRINT)


'''


def apply(
    app_path: Path = APP_FILE,
    architecture_path: Path = ARCHITECTURE_FILE,
) -> bool:
    app_text = app_path.read_text(encoding="utf-8")
    architecture_text = architecture_path.read_text(encoding="utf-8")
    if "SOCIAL_ROUTES_BLUEPRINT = create_social_blueprint(" in app_text:
        return False

    service_marker = "from game_day_safety_service import GameDaySafetyService\n"
    if service_marker not in app_text:
        raise RuntimeError("Game-day service import marker was not found.")
    app_text = app_text.replace(
        service_marker,
        service_marker + SERVICE_IMPORTS,
        1,
    )

    route_marker = '''from routes.game_day_safety_routes import (
    GameDaySafetyRoutesDependencies,
    create_game_day_safety_blueprint,
)
'''
    if route_marker not in app_text:
        raise RuntimeError("Game-day route import marker was not found.")
    app_text = app_text.replace(route_marker, route_marker + ROUTE_IMPORTS, 1)

    constant_marker = "GAME_DAY_BACKUP_DIR = DATA_DIR / \"Backups\" / \"GameDay\"\n"
    if constant_marker not in app_text:
        raise RuntimeError("Game-day backup constant marker was not found.")
    app_text = app_text.replace(
        constant_marker,
        constant_marker
        + 'SOCIAL_POSTS_FILE = DATA_DIR / "Social" / "social_posts.json"\n'
        + 'SOCIAL_CARDS_DIR = DATA_DIR / "Social" / "Cards"\n',
        1,
    )

    directory_marker = (
        "for _path in (SPONSORS_FILE.parent, SPONSOR_UPLOAD_DIR, PACKAGES_FILE.parent):\n"
    )
    if directory_marker not in app_text:
        raise RuntimeError("Startup directory marker was not found.")
    app_text = app_text.replace(
        directory_marker,
        "for _path in (\n"
        "    SPONSORS_FILE.parent,\n"
        "    SPONSOR_UPLOAD_DIR,\n"
        "    PACKAGES_FILE.parent,\n"
        "    SOCIAL_POSTS_FILE.parent,\n"
        "    SOCIAL_CARDS_DIR,\n"
        "):\n",
        1,
    )

    support_marker = "SUPPORT_MEDIA_SERVICE: SupportMediaService | None = None\n"
    if support_marker not in app_text:
        raise RuntimeError("Support media service marker was not found.")
    app_text = app_text.replace(
        support_marker,
        SOCIAL_BLOCK + support_marker,
        1,
    )

    architecture_marker = '    "security_upgrade_routes",\n    "sponsor_routes",\n'
    if architecture_marker not in architecture_text:
        raise RuntimeError("Blueprint architecture marker was not found.")
    architecture_text = architecture_text.replace(
        architecture_marker,
        '    "security_upgrade_routes",\n    "social_routes",\n    "sponsor_routes",\n',
        1,
    )

    app_path.write_text(app_text, encoding="utf-8")
    architecture_path.write_text(architecture_text, encoding="utf-8")
    return True


def main() -> None:
    changed = apply()
    print(
        "Phase 6.2 social event publishing integration applied."
        if changed
        else "Phase 6.2 integration was already present."
    )


if __name__ == "__main__":
    main()
