from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_FILE = ROOT / "app.py"


def _replace_block(
    text: str,
    start_marker: str,
    end_marker: str,
    replacement: str,
) -> str:
    start = text.find(start_marker)
    if start < 0:
        raise RuntimeError(f"Missing integration marker: {start_marker!r}")
    end = text.find(end_marker, start)
    if end < 0:
        raise RuntimeError(f"Missing integration marker: {end_marker!r}")
    return text[:start] + replacement + text[end:]


def apply(path: Path = APP_FILE) -> bool:
    text = path.read_text(encoding="utf-8")
    if "STATISTICS_SERVICE: StatisticsService | None = None" in text:
        return False

    import_marker = "from rules_service import RulesService\n"
    if import_marker not in text:
        raise RuntimeError("RulesService import marker was not found.")
    text = text.replace(
        import_marker,
        import_marker + "from statistics_service import StatisticsService\n",
        1,
    )

    team_helpers = '''def canonical_team_key(state: dict[str, Any], value: Any) -> str:
    return StatisticsService.canonical_team_key(state, value)


def canonical_team_name(state: dict[str, Any], value: Any) -> str:
    return StatisticsService.canonical_team_name(state, value)


'''
    text = _replace_block(
        text,
        "def canonical_team_key(state: dict[str, Any], value: Any) -> str:\n",
        "def resolve_game_roster_player(state: dict[str, Any], team: str, number: Any) -> dict[str, str]:\n",
        team_helpers,
    )

    statistics_block = '''STATISTICS_SERVICE: StatisticsService | None = None


def get_statistics_service() -> StatisticsService:
    global STATISTICS_SERVICE
    if STATISTICS_SERVICE is None:
        STATISTICS_SERVICE = StatisticsService()
    return STATISTICS_SERVICE


def build_statistics(state: dict[str, Any]) -> dict[str, Any]:
    return get_statistics_service().report(state).data["statistics"]


'''
    text = _replace_block(
        text,
        "def build_statistics(state: dict[str, Any]) -> dict[str, Any]:\n",
        "PENALTY_RULES: dict[tuple[str, str], dict[str, Any]] = {\n",
        statistics_block,
    )

    path.write_text(text, encoding="utf-8")
    return True


def main() -> None:
    changed = apply()
    if changed:
        print("Phase 4.20 StatisticsService integration applied.")
    else:
        print("Phase 4.20 StatisticsService integration was already present.")


if __name__ == "__main__":
    main()
