from __future__ import annotations

from pathlib import Path

from tools.apply_phase_4_20 import apply


LEGACY_APP = '''from rules_service import RulesService


def canonical_team_key(state: dict[str, Any], value: Any) -> str:
    return str(value)


def canonical_team_name(state: dict[str, Any], value: Any) -> str:
    return str(value)


def resolve_game_roster_player(state: dict[str, Any], team: str, number: Any) -> dict[str, str]:
    return {"number": str(number)}


def build_statistics(state: dict[str, Any]) -> dict[str, Any]:
    teams = {}
    return {"teams": teams}


PENALTY_RULES: dict[tuple[str, str], dict[str, Any]] = {
    ("Offensive", "Holding"): {"yards": 10},
}
'''


def test_phase_4_20_migration_integrates_statistics_service(tmp_path: Path) -> None:
    target = tmp_path / "app.py"
    target.write_text(LEGACY_APP, encoding="utf-8")

    assert apply(target) is True
    migrated = target.read_text(encoding="utf-8")

    assert "from statistics_service import StatisticsService" in migrated
    assert "STATISTICS_SERVICE: StatisticsService | None = None" in migrated
    assert "get_statistics_service().report(state)" in migrated
    assert "StatisticsService.canonical_team_key(state, value)" in migrated
    assert "StatisticsService.canonical_team_name(state, value)" in migrated
    assert "teams = {}" not in migrated
    assert apply(target) is False
