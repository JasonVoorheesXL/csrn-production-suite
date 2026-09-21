from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"
ARCHITECTURE = ROOT / "phase5_architecture.py"
INDEX = ROOT / "templates" / "index.html"
THEMES = ROOT / "templates" / "theme_manager.html"
SOCIAL = ROOT / "templates" / "social_manager.html"
ROADMAP = ROOT / "docs" / "PHASE_6_GAME_DAY_AND_COMMERCIAL_ROADMAP.md"
SOCIAL_ARCHITECTURE_TEST = ROOT / "tests" / "test_social_architecture.py"
VERSION = ROOT / "VERSION.txt"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"Phase 6.10 integration anchor missing: {label}")
    return text.replace(old, new, 1)


def apply_app() -> None:
    source = APP.read_text(encoding="utf-8")
    source = replace_once(
        source,
        "from social_platforms import default_adapter_registry\n",
        "from social_platforms import default_adapter_registry\n"
        "from credential_vault import WindowsDpapiVault\n"
        "from oauth_onboarding_service import OAuthOnboardingService\n"
        "from commercial_ux_service import CommercialUxService\n",
        "commercial UX service imports",
    )
    source = replace_once(
        source,
        "from routes.social_routes import (\n"
        "    SocialRoutesDependencies,\n"
        "    create_social_blueprint,\n"
        ")\n",
        "from routes.social_routes import (\n"
        "    SocialRoutesDependencies,\n"
        "    create_social_blueprint,\n"
        ")\n"
        "from routes.commercial_ux_routes import (\n"
        "    CommercialUxDependencies,\n"
        "    create_commercial_ux_blueprint,\n"
        ")\n",
        "commercial UX route imports",
    )
    source = replace_once(
        source,
        'SOCIAL_CARDS_DIR = DATA_DIR / "Social" / "Cards"\n',
        'SOCIAL_CARDS_DIR = DATA_DIR / "Social" / "Cards"\n'
        'OAUTH_STATE_FILE = DATA_DIR / "Settings" / "oauth_connections.json"\n'
        'OAUTH_VAULT_FILE = DATA_DIR / "Settings" / "oauth_credentials.dpapi.json"\n',
        "OAuth data paths",
    )
    source = replace_once(
        source,
        '    "Version 1.13.0-alpha.6i — Social Publishing Engine"\n'
        ")\n"
        'RUNTIME_BUILD = "V1.13A6I-SOCIAL-PUBLISHING-ENGINE"\n',
        '    "Version 1.13.0-alpha.6j — Commercial UX and Account Onboarding"\n'
        ")\n"
        'RUNTIME_BUILD = "V1.13A6J-COMMERCIAL-UX-ACCOUNT-ONBOARDING"\n',
        "runtime identity",
    )
    source = source.replace(
        '            "x_credential_ref": "CSRN_X_ACCESS_TOKEN",\n'
        '            "facebook_credential_ref": "CSRN_FACEBOOK_PAGE_ACCESS_TOKEN",\n',
        '            "connection_mode": "guided_oauth",\n'
        '            "facebook_broker_required": True,\n',
        1,
    )
    old_block = '''SOCIAL_SERVICE: SocialPublishingService | None = None


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
'''
    new_block = '''CREDENTIAL_VAULT = WindowsDpapiVault(OAUTH_VAULT_FILE)
OAUTH_SERVICE: OAuthOnboardingService | None = None
COMMERCIAL_UX_SERVICE: CommercialUxService | None = None
SOCIAL_SERVICE: SocialPublishingService | None = None


def get_oauth_service() -> OAuthOnboardingService:
    global OAUTH_SERVICE
    if OAUTH_SERVICE is None:
        OAUTH_SERVICE = OAuthOnboardingService(
            state_file=OAUTH_STATE_FILE,
            vault=CREDENTIAL_VAULT,
            configure_social_account=lambda payload: get_social_service().configure_account(payload),
            clock=time.time,
        )
    return OAUTH_SERVICE


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
            adapters=default_adapter_registry(
                credential_resolver=get_oauth_service().credential_resolver(),
            ),
            load_broadcast_state=load_state,
            load_config=load_config,
            load_rosters=load_rosters,
            load_sponsors=load_sponsors,
            active_sponsor_by_id=active_sponsor_by_id,
            get_theme_status=lambda: get_theme_service().status(),
            clock=time.time,
        )
    return SOCIAL_SERVICE


def get_commercial_ux_service() -> CommercialUxService:
    global COMMERCIAL_UX_SERVICE
    if COMMERCIAL_UX_SERVICE is None:
        COMMERCIAL_UX_SERVICE = CommercialUxService(
            load_config=load_config,
            theme_status=lambda: get_theme_service().status(),
            theme_catalog=lambda: get_theme_service().catalog(),
            oauth_status=lambda: get_oauth_service().status(),
            social_status=lambda: get_social_service().status(),
        )
    return COMMERCIAL_UX_SERVICE
'''
    source = replace_once(source, old_block, new_block, "OAuth and UX service wiring")
    anchor = '''SOCIAL_ROUTES_BLUEPRINT = create_social_blueprint(
    SocialRoutesDependencies(
        require_auth=require_auth,
        get_social_service=lambda: get_social_service(),
    )
)
APPLICATION_BLUEPRINTS.append(SOCIAL_ROUTES_BLUEPRINT)
'''
    replacement = anchor + '''

COMMERCIAL_UX_ROUTES_BLUEPRINT = create_commercial_ux_blueprint(
    CommercialUxDependencies(
        require_auth=require_auth,
        get_ux_service=lambda: get_commercial_ux_service(),
        get_oauth_service=lambda: get_oauth_service(),
        get_theme_service=lambda: get_theme_service(),
    )
)
APPLICATION_BLUEPRINTS.append(COMMERCIAL_UX_ROUTES_BLUEPRINT)
'''
    source = replace_once(source, anchor, replacement, "commercial UX blueprint registration")
    APP.write_text(source, encoding="utf-8")


def apply_architecture() -> None:
    source = ARCHITECTURE.read_text(encoding="utf-8")
    source = replace_once(
        source,
        '    "commissioning_routes",\n',
        '    "commissioning_routes",\n    "commercial_ux_routes",\n',
        "commercial UX blueprint audit",
    )
    ARCHITECTURE.write_text(source, encoding="utf-8")


def apply_index() -> None:
    source = INDEX.read_text(encoding="utf-8")
    source = replace_once(
        source,
        '      <button id="navOBS" onclick="showModule(\'obs\')">OBS Manager</button>\n'
        '      <button id="navSettings" onclick="showModule(\'settings\')">Settings</button>\n',
        '      <button id="navOBS" onclick="showModule(\'obs\')">OBS Manager</button>\n'
        '      <button id="navSetup" onclick="window.location.href=\'/setup\'">Setup &amp; Integrations</button>\n'
        '      <button id="navSettings" onclick="showModule(\'settings\')">Advanced Settings</button>\n',
        "discoverable setup navigation",
    )
    theme_options = (
        '<label>Theme<select id="cfgTheme">'
        '<option value="classic_1980s">Classic 1980s Broadcast</option>'
        '<option value="early_cable">Early Cable Sports</option>'
        '<option value="modern_network">Modern Network</option>'
        '<option value="minimal_radio">Minimal Radio</option>'
        '<option value="heritage_press_box">Heritage Press Box</option>'
        '<option value="friday_night_stadium">Friday Night Stadium</option>'
        '<option value="digital_neon">Digital Neon</option>'
        '<option value="collegiate_traditional">Collegiate Traditional</option>'
        '</select><small class="field-hint">Use Setup &amp; Integrations for visual previews.</small></label>'
    )
    source = replace_once(source, '<label>Theme<input id="cfgTheme"></label>', theme_options, "theme controlled selector")
    source = replace_once(
        source,
        "        <h2>CSRN Social Media</h2>\n",
        "        <div class=\"section-heading-row\"><div><h2>CSRN Social Media</h2><p class=\"section-note\">Public profile links are separate from publishing account connections.</p></div><button type=\"button\" onclick=\"window.location.href='/setup#social'\">Manage Publishing Accounts</button></div>\n",
        "social account navigation",
    )
    deep_link = '''
<script>
window.addEventListener('load', () => {
  const requested = new URLSearchParams(window.location.search).get('module');
  if (!requested) return;
  let attempts = 0;
  const openRequestedModule = () => {
    attempts += 1;
    if (typeof window.showModule === 'function' && document.getElementById(`${requested}Module`)) {
      window.showModule(requested);
      return;
    }
    if (attempts < 20) window.setTimeout(openRequestedModule, 150);
  };
  openRequestedModule();
});
</script>
'''
    if "openRequestedModule" not in source:
        source = source.replace("</body>", deep_link + "</body>", 1)
    INDEX.write_text(source, encoding="utf-8")


def add_return_links(path: Path, marker: str) -> None:
    source = path.read_text(encoding="utf-8")
    if marker in source:
        return
    links = f'<nav id="{marker}" style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px"><a href="/" style="color:white">Back to Command Center</a><a href="/setup" style="color:white">Setup &amp; Integrations</a></nav>'
    source = source.replace("<body>", "<body>\n" + links, 1)
    path.write_text(source, encoding="utf-8")


def apply_standalone_navigation() -> None:
    add_return_links(THEMES, "themeReturnNavigation")
    add_return_links(SOCIAL, "socialReturnNavigation")


def apply_roadmap() -> None:
    source = ROADMAP.read_text(encoding="utf-8")
    source = replace_once(
        source,
        "### 6.10 Grounded Game Recap Engine\n",
        "### 6.10 Commercial UX, Navigation, and Account Onboarding\n\n"
        "- unified Setup & Integrations hub reachable from Command Center;\n"
        "- customer-facing feature directory and return navigation;\n"
        "- controlled selectors for known choices instead of internal free-text names;\n"
        "- first-run readiness progress and plain-language setup status;\n"
        "- Connect X using OAuth 2.0 Authorization Code with PKCE;\n"
        "- Connect Facebook through a PossumFrog OAuth broker that keeps Meta application secrets out of the desktop client;\n"
        "- protected per-user Windows credential storage, connection testing, and disconnect controls;\n"
        "- accessibility, responsive layout, validation, and usability regression checks.\n\n"
        "### 6.11 Grounded Game Recap Engine\n",
        "commercial UX roadmap insertion",
    )
    ROADMAP.write_text(source, encoding="utf-8")


def apply_prior_guardrail() -> None:
    source = SOCIAL_ARCHITECTURE_TEST.read_text(encoding="utf-8")
    source = source.replace(
        "def test_phase_6_10_grounded_recap_requirement_remains() -> None:\n"
        "    roadmap = (ROOT / \"docs\" / \"PHASE_6_GAME_DAY_AND_COMMERCIAL_ROADMAP.md\").read_text(encoding=\"utf-8\")\n"
        "    assert \"### 6.10 Grounded Game Recap Engine\" in roadmap\n"
        "    assert \"must not invent\" in roadmap\n",
        "def test_grounded_recap_requirement_remains_after_commercial_ux() -> None:\n"
        "    roadmap = (ROOT / \"docs\" / \"PHASE_6_GAME_DAY_AND_COMMERCIAL_ROADMAP.md\").read_text(encoding=\"utf-8\")\n"
        "    assert \"### 6.10 Commercial UX, Navigation, and Account Onboarding\" in roadmap\n"
        "    assert \"### 6.11 Grounded Game Recap Engine\" in roadmap\n"
        "    assert \"must not invent\" in roadmap\n",
        1,
    )
    SOCIAL_ARCHITECTURE_TEST.write_text(source, encoding="utf-8")


def apply() -> None:
    apply_app()
    apply_architecture()
    apply_index()
    apply_standalone_navigation()
    apply_roadmap()
    apply_prior_guardrail()
    VERSION.write_text("1.13.0-alpha.6j\n", encoding="utf-8")


if __name__ == "__main__":
    apply()
