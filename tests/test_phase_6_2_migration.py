from __future__ import annotations

from pathlib import Path

from tools.apply_phase_6_2 import apply


LEGACY_APP = '''from game_day_safety_service import GameDaySafetyService
from routes.game_day_safety_routes import (
    GameDaySafetyRoutesDependencies,
    create_game_day_safety_blueprint,
)

GAME_DAY_BACKUP_DIR = DATA_DIR / "Backups" / "GameDay"

for _path in (SPONSORS_FILE.parent, SPONSOR_UPLOAD_DIR, PACKAGES_FILE.parent):
    _path.mkdir(parents=True, exist_ok=True)

SUPPORT_MEDIA_SERVICE: SupportMediaService | None = None
'''

LEGACY_ARCHITECTURE = '''EXPECTED_BLUEPRINTS = {
    "security_upgrade_routes",
    "sponsor_routes",
}
'''


def test_phase_6_2_migration_integrates_social_service_and_blueprint(
    tmp_path: Path,
) -> None:
    app_path = tmp_path / "app.py"
    architecture_path = tmp_path / "phase5_architecture.py"
    app_path.write_text(LEGACY_APP, encoding="utf-8")
    architecture_path.write_text(LEGACY_ARCHITECTURE, encoding="utf-8")

    assert apply(app_path, architecture_path) is True
    migrated = app_path.read_text(encoding="utf-8")
    architecture = architecture_path.read_text(encoding="utf-8")

    assert "from social_publishing_service import SocialPublishingService" in migrated
    assert "from routes.social_routes import (" in migrated
    assert 'SOCIAL_POSTS_FILE = DATA_DIR / "Social" / "social_posts.json"' in migrated
    assert "SOCIAL_POST_REPOSITORY = SocialPostRepository(" in migrated
    assert "def resolve_social_media(value: str)" in migrated
    assert "SOCIAL_ROUTES_BLUEPRINT = create_social_blueprint(" in migrated
    assert "APPLICATION_BLUEPRINTS.append(SOCIAL_ROUTES_BLUEPRINT)" in migrated
    assert '"social_routes"' in architecture
    assert apply(app_path, architecture_path) is False
