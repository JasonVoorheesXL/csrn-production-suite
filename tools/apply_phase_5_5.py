from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_FILE = ROOT / "app.py"


ROUTE_IMPORTS = '''from routes.asset_routes import (
    AssetRoutesDependencies,
    create_asset_blueprint,
)
from routes.logo_routes import (
    LogoRoutesDependencies,
    create_logo_blueprint,
)
from routes.sponsor_routes import (
    SponsorRoutesDependencies,
    create_sponsor_blueprint,
)
'''

MEDIA_REGISTRATION = '''SPONSOR_ROUTES_BLUEPRINT = create_sponsor_blueprint(
    SponsorRoutesDependencies(
        require_auth=require_auth,
        get_sponsor_service=get_sponsor_service,
        load_sponsors=lambda: load_sponsors(),
        load_assets=lambda: load_assets(),
        save_assets=lambda items: save_assets(items),
        clean_asset_record=lambda payload, asset_id: clean_asset_record(
            payload,
            asset_id,
        ),
        asset_file_hash=lambda path: asset_file_hash(path),
        get_asset_upload_dir=lambda: ASSET_UPLOAD_DIR,
        get_sponsor_upload_dir=lambda: SPONSOR_UPLOAD_DIR,
        clock=lambda: time.time(),
        token_hex=lambda length: secrets.token_hex(length),
    )
)
app.register_blueprint(SPONSOR_ROUTES_BLUEPRINT)

ASSET_ROUTES_BLUEPRINT = create_asset_blueprint(
    AssetRoutesDependencies(
        require_auth=require_auth,
        get_asset_service=get_asset_service,
        get_upload_dir=lambda: ASSET_UPLOAD_DIR,
        extension_allowed=AssetService.extension_allowed,
        normalize_asset_id=AssetService.normalize_id,
        clock=lambda: time.time(),
        token_hex=lambda length: secrets.token_hex(length),
    )
)
app.register_blueprint(ASSET_ROUTES_BLUEPRINT)


'''

LOGO_REGISTRATION = '''LOGO_ROUTES_BLUEPRINT = create_logo_blueprint(
    LogoRoutesDependencies(
        require_auth=require_auth,
        get_logo_service=get_logo_service,
        get_base_dir=lambda: BASE_DIR,
        get_school_logo_dir=lambda school_id: (
            DATA_DIR / "Logos" / normalize_school_id(school_id)
        ),
        normalize_school_id=normalize_school_id,
    )
)
app.register_blueprint(LOGO_ROUTES_BLUEPRINT)


'''


def _remove_until(text: str, start_marker: str, end_marker: str) -> str:
    start = text.find(start_marker)
    if start < 0:
        raise RuntimeError(f"Missing route migration marker: {start_marker!r}")
    end = text.find(end_marker, start)
    if end < 0:
        raise RuntimeError(f"Missing route migration marker: {end_marker!r}")
    return text[:start] + text[end:]


def apply(path: Path = APP_FILE) -> bool:
    text = path.read_text(encoding="utf-8")
    if "SPONSOR_ROUTES_BLUEPRINT = create_sponsor_blueprint(" in text:
        return False

    import_marker = '''from routes.venue_routes import (
    VenueRoutesDependencies,
    create_venue_blueprint,
)
'''
    if import_marker not in text:
        raise RuntimeError("Venue route import marker was not found.")
    text = text.replace(import_marker, import_marker + ROUTE_IMPORTS, 1)

    text = _remove_until(
        text,
        '@app.get("/api/sponsors")\n',
        '@app.get("/overlay")\n',
    )
    overlay_marker = '@app.get("/overlay")\n'
    text = text.replace(
        overlay_marker,
        MEDIA_REGISTRATION + overlay_marker,
        1,
    )

    text = _remove_until(
        text,
        '@app.get("/school-logos/<school_id>/<filename>")\n',
        "UPGRADE_SERVICE: UpgradeService | None = None\n",
    )
    upgrade_marker = "UPGRADE_SERVICE: UpgradeService | None = None\n"
    text = text.replace(
        upgrade_marker,
        LOGO_REGISTRATION + upgrade_marker,
        1,
    )

    path.write_text(text, encoding="utf-8")
    return True


def main() -> None:
    changed = apply()
    if changed:
        print("Phase 5.5 sponsor, asset, and logo route integration applied.")
    else:
        print("Phase 5.5 route integration was already present.")


if __name__ == "__main__":
    main()
