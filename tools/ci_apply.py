from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"
EVENT_SERVICE = ROOT / "event_service.py"
ARCHITECTURE = ROOT / "phase5_architecture.py"
VERSION = ROOT / "VERSION.txt"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"Phase 6.9 integration anchor missing: {label}")
    return text.replace(old, new, 1)


def apply_event_callback() -> None:
    source = EVENT_SERVICE.read_text(encoding="utf-8")
    source = replace_once(
        source,
        "        default_player_graphic: Callable[[], Mapping[str, Any]],\n"
        "        transaction_lock: Any | None = None,\n",
        "        default_player_graphic: Callable[[], Mapping[str, Any]],\n"
        "        on_event: Callable[[Mapping[str, Any]], Any] | None = None,\n"
        "        transaction_lock: Any | None = None,\n",
        "event callback parameter",
    )
    source = replace_once(
        source,
        "        self._default_player_graphic = default_player_graphic\n"
        "        self._transaction_lock = transaction_lock\n",
        "        self._default_player_graphic = default_player_graphic\n"
        "        self._on_event = on_event\n"
        "        self._transaction_lock = transaction_lock\n",
        "event callback storage",
    )
    source = replace_once(
        source,
        "            self._save_state(state)\n\n"
        "        return EventResult(\n"
        "            \"OK\",\n"
        "            {\n"
        "                \"state\": copy.deepcopy(dict(self._public_state(state))),\n"
        "                \"trigger\": copy.deepcopy(payload),\n",
        "            self._save_state(state)\n\n"
        "        if self._on_event is not None:\n"
        "            try:\n"
        "                self._on_event(copy.deepcopy(payload))\n"
        "            except Exception:\n"
        "                # Social draft creation can never invalidate the game event.\n"
        "                pass\n\n"
        "        return EventResult(\n"
        "            \"OK\",\n"
        "            {\n"
        "                \"state\": copy.deepcopy(dict(self._public_state(state))),\n"
        "                \"trigger\": copy.deepcopy(payload),\n",
        "event callback invocation",
    )
    EVENT_SERVICE.write_text(source, encoding="utf-8")


def apply_social_service_fixes() -> None:
    path = ROOT / "social_service.py"
    source = path.read_text(encoding="utf-8")
    source = replace_once(
        source,
        "            selected = {str(value) for value in account_ids or []}\n"
        "            accounts = [copy.deepcopy(account) for account_id, account in state[\"accounts\"].items() if account.get(\"enabled\", True) and (not selected or account_id in selected)]\n",
        "            selection_requested = account_ids is not None\n"
        "            selected = {str(value) for value in account_ids or []}\n"
        "            accounts = [\n"
        "                copy.deepcopy(account)\n"
        "                for account_id, account in state[\"accounts\"].items()\n"
        "                if account.get(\"enabled\", True)\n"
        "                and (not selection_requested or account_id in selected)\n"
        "            ]\n",
        "explicit empty account selection",
    )
    source = replace_once(
        source,
        "            auto_accounts = [account_id for account_id, account in state[\"accounts\"].items() if account.get(\"enabled\", True) and account.get(\"auto_publish\", False)]\n"
        "            candidates = [copy.deepcopy(draft) for draft in state[\"drafts\"] if draft.get(\"status\") == \"APPROVED\"][:limit]\n"
        "        processed = []\n",
        "            auto_accounts = [\n"
        "                account_id\n"
        "                for account_id, account in state[\"accounts\"].items()\n"
        "                if account.get(\"enabled\", True)\n"
        "                and account.get(\"auto_publish\", False)\n"
        "            ]\n"
        "            candidates = [\n"
        "                copy.deepcopy(draft)\n"
        "                for draft in state[\"drafts\"]\n"
        "                if draft.get(\"status\") == \"APPROVED\"\n"
        "            ][:limit]\n"
        "        if not auto_accounts:\n"
        "            return SocialResult(\"NO_AUTO_PUBLISH_ACCOUNTS\")\n"
        "        processed = []\n",
        "auto-publish account guard",
    )
    path.write_text(source, encoding="utf-8")


def apply_app() -> None:
    source = APP.read_text(encoding="utf-8")
    source = replace_once(
        source,
        "from theme_service import GraphicsThemeService\n",
        "from theme_service import GraphicsThemeService\n"
        "from social_service import SocialPublishingService\n"
        "from social_card_renderer import SocialCardRenderer\n"
        "from social_asset_resolver import SocialAssetResolver\n"
        "from social_platforms import default_adapter_registry\n",
        "social service imports",
    )
    source = replace_once(
        source,
        "from routes.theme_routes import (\n"
        "    ThemeRoutesDependencies,\n"
        "    create_theme_blueprint,\n"
        ")\n",
        "from routes.theme_routes import (\n"
        "    ThemeRoutesDependencies,\n"
        "    create_theme_blueprint,\n"
        ")\n"
        "from routes.social_routes import (\n"
        "    SocialRoutesDependencies,\n"
        "    create_social_blueprint,\n"
        ")\n",
        "social route imports",
    )
    source = replace_once(
        source,
        "THEME_STATE_FILE = DATA_DIR / \"Themes\" / \"theme_state.json\"\n",
        "THEME_STATE_FILE = DATA_DIR / \"Themes\" / \"theme_state.json\"\n"
        "SOCIAL_STATE_FILE = DATA_DIR / \"Social\" / \"social_state.json\"\n"
        "SOCIAL_CARDS_DIR = DATA_DIR / \"Social\" / \"Cards\"\n",
        "social data paths",
    )
    source = replace_once(
        source,
        "    \"Version 1.13.0-alpha.6h — Graphics Theme Engine\"\n"
        ")\n"
        "RUNTIME_BUILD = \"V1.13A6H-GRAPHICS-THEME-ENGINE\"\n",
        "    \"Version 1.13.0-alpha.6i — Social Publishing Engine\"\n"
        ")\n"
        "RUNTIME_BUILD = \"V1.13A6I-SOCIAL-PUBLISHING-ENGINE\"\n",
        "runtime identity",
    )
    source = replace_once(
        source,
        '        "website": "",\n'
        "    },\n"
        "    \"application\": {\n",
        '        "website": "",\n'
        '        "publishing": {\n'
        '            "preview_first": True,\n'
        '            "auto_create_drafts": False,\n'
        '            "allow_auto_publish": False,\n'
        '            "x_credential_ref": "CSRN_X_ACCESS_TOKEN",\n'
        '            "facebook_credential_ref": "CSRN_FACEBOOK_PAGE_ACCESS_TOKEN",\n'
        '            "facebook_api_version": "v25.0",\n'
        '        },\n'
        "    },\n"
        "    \"application\": {\n",
        "social defaults",
    )
    source = replace_once(
        source,
        '"Releases", "Themes"):\n',
        '"Releases", "Themes", "Social"):\n',
        "social data architecture",
    )
    source = replace_once(
        source,
        "    SPONSOR_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)\n",
        "    SPONSOR_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)\n"
        "    SOCIAL_CARDS_DIR.mkdir(parents=True, exist_ok=True)\n",
        "social cards directory",
    )
    social_block = '''SOCIAL_SERVICE: SocialPublishingService | None = None


def get_social_service() -> SocialPublishingService:
    global SOCIAL_SERVICE
    if SOCIAL_SERVICE is None:
        resolver = SocialAssetResolver(
            base_dir=BASE_DIR,
            data_dir=DATA_DIR,
            asset_upload_dir=ASSET_UPLOAD_DIR,
            headshots_dir=HEADSHOTS_DIR,
        )
        SOCIAL_SERVICE = SocialPublishingService(
            state_file=SOCIAL_STATE_FILE,
            renderer=SocialCardRenderer(
                output_dir=SOCIAL_CARDS_DIR,
                asset_resolver=resolver,
            ),
            adapters=default_adapter_registry(),
            load_broadcast_state=load_state,
            load_config=load_config,
            load_rosters=load_rosters,
            load_sponsors=load_sponsors,
            active_sponsor_by_id=active_sponsor_by_id,
            get_theme_status=lambda: get_theme_service().status(),
            clock=time.time,
        )
    return SOCIAL_SERVICE


SOCIAL_ROUTES_BLUEPRINT = create_social_blueprint(
    SocialRoutesDependencies(
        require_auth=require_auth,
        get_social_service=lambda: get_social_service(),
    )
)
APPLICATION_BLUEPRINTS.append(SOCIAL_ROUTES_BLUEPRINT)


'''
    source = replace_once(
        source,
        "SUPPORT_MEDIA_SERVICE: SupportMediaService | None = None\n",
        social_block + "SUPPORT_MEDIA_SERVICE: SupportMediaService | None = None\n",
        "social service registration",
    )
    source = replace_once(
        source,
        "            default_player_graphic=lambda: copy.deepcopy(\n"
        "                DEFAULT_STATE[\"player_graphic\"]\n"
        "            ),\n"
        "            transaction_lock=lock,\n",
        "            default_player_graphic=lambda: copy.deepcopy(\n"
        "                DEFAULT_STATE[\"player_graphic\"]\n"
        "            ),\n"
        "            on_event=lambda event: get_social_service().queue_event(event),\n"
        "            transaction_lock=lock,\n",
        "event-to-social handoff",
    )
    APP.write_text(source, encoding="utf-8")


def apply_architecture() -> None:
    source = ARCHITECTURE.read_text(encoding="utf-8")
    source = replace_once(
        source,
        '    "sponsor_routes",\n',
        '    "social_routes",\n    "sponsor_routes",\n',
        "social blueprint audit",
    )
    ARCHITECTURE.write_text(source, encoding="utf-8")


def apply() -> None:
    apply_event_callback()
    apply_social_service_fixes()
    apply_app()
    apply_architecture()
    VERSION.write_text("1.13.0-alpha.6i\n", encoding="utf-8")


if __name__ == "__main__":
    apply()
