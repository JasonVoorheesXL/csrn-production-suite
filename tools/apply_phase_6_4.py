from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class MigrationError(RuntimeError):
    pass


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise MigrationError(f"Expected one {label} anchor; found {count}.")
    return text.replace(old, new, 1)


def apply(root: Path = ROOT) -> None:
    app_path = root / "app.py"
    architecture_path = root / "phase5_architecture.py"
    app_text = app_path.read_text(encoding="utf-8")
    architecture_text = architecture_path.read_text(encoding="utf-8")

    if "def get_caption_service()" in app_text:
        print("Phase 6.4 caption integration is already applied.")
        return

    app_text = replace_once(
        app_text,
        "from commissioning_service import HardwareOBSCommissioningService\n",
        "from commissioning_service import HardwareOBSCommissioningService\nfrom caption_service import CaptionService\n",
        "caption service import",
    )
    app_text = replace_once(
        app_text,
        "from routes.commissioning_routes import (\n    CommissioningRoutesDependencies,\n    create_commissioning_blueprint,\n)\n",
        "from routes.commissioning_routes import (\n    CommissioningRoutesDependencies,\n    create_commissioning_blueprint,\n)\nfrom routes.caption_routes import (\n    CaptionRoutesDependencies,\n    create_caption_blueprint,\n)\n",
        "caption route import",
    )
    app_text = replace_once(
        app_text,
        'COMMISSIONING_FILE = DATA_DIR / "Settings" / "hardware_commissioning.json"\n',
        'COMMISSIONING_FILE = DATA_DIR / "Settings" / "hardware_commissioning.json"\nCAPTION_PROFILE_FILE = DATA_DIR / "Settings" / "caption_profile.json"\nCAPTION_STATE_FILE = DATA_DIR / "Captions" / "caption_state.json"\nCAPTION_TRANSCRIPTS_DIR = DATA_DIR / "Captions" / "Transcripts"\n',
        "caption storage constants",
    )

    commissioning_block = '''COMMISSIONING_ROUTES_BLUEPRINT = create_commissioning_blueprint(
    CommissioningRoutesDependencies(
        require_auth=require_auth,
        get_commissioning_service=lambda: get_commissioning_service(),
    )
)
APPLICATION_BLUEPRINTS.append(COMMISSIONING_ROUTES_BLUEPRINT)
'''
    caption_block = commissioning_block + '''

CAPTION_SERVICE: CaptionService | None = None


def get_caption_service() -> CaptionService:
    global CAPTION_SERVICE
    if CAPTION_SERVICE is None:
        CAPTION_SERVICE = CaptionService(
            profile_file=CAPTION_PROFILE_FILE,
            state_file=CAPTION_STATE_FILE,
            transcripts_dir=CAPTION_TRANSCRIPTS_DIR,
            clock=time.time,
        )
    return CAPTION_SERVICE


CAPTION_ROUTES_BLUEPRINT = create_caption_blueprint(
    CaptionRoutesDependencies(
        require_auth=require_auth,
        get_caption_service=lambda: get_caption_service(),
    )
)
APPLICATION_BLUEPRINTS.append(CAPTION_ROUTES_BLUEPRINT)
'''
    app_text = replace_once(
        app_text,
        commissioning_block,
        caption_block,
        "caption service composition",
    )

    architecture_text = replace_once(
        architecture_text,
        '    "broadcast_routes",\n    "commissioning_routes",\n',
        '    "broadcast_routes",\n    "caption_routes",\n    "commissioning_routes",\n',
        "caption blueprint audit",
    )
    architecture_text = replace_once(
        architecture_text,
        'PUBLIC_ENDPOINTS = {\n    "asset_routes.asset_file",\n',
        'PUBLIC_ENDPOINTS = {\n    "asset_routes.asset_file",\n    "caption_routes.caption_overlay",\n    "caption_routes.caption_overlay_state",\n',
        "caption public route audit",
    )

    app_path.write_text(app_text, encoding="utf-8")
    architecture_path.write_text(architecture_text, encoding="utf-8")
    print("Phase 6.4 channel captioning integration applied.")


if __name__ == "__main__":
    apply()
