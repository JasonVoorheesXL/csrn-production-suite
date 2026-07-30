from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = (
    ROOT / "Data" / "TestFixtures" / "Northwood-vs-Pine-Valley"
)


def _tracked_paths(*paths: str) -> list[str]:
    result = subprocess.run(
        [
            "git",
            "-c",
            f"safe.directory={ROOT}",
            "-C",
            str(ROOT),
            "ls-files",
            "--",
            *paths,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def test_runtime_social_state_is_not_tracked() -> None:
    assert _tracked_paths("Data/Social/social_state.json") == []


def test_obsolete_root_utilities_are_not_tracked_or_present() -> None:
    obsolete = (
        "index.html",
        "MANAGE_PLAYER_HEADSHOTS.cmd",
        "START_FACEBOOK_TEST_TUNNEL.cmd",
        "tools/manage_player_headshots.py",
    )
    assert _tracked_paths(*obsolete) == []
    for relative_path in obsolete:
        assert not (ROOT / relative_path).exists()


def test_fictional_assets_reside_in_the_fixture_tree() -> None:
    fixture = json.loads(
        (FIXTURE_ROOT / "fixture_data.json").read_text(encoding="utf-8")
    )

    referenced_assets: list[str] = []
    referenced_assets.extend(
        school["primary_logo"] for school in fixture["schools"]
    )
    for roster in fixture["rosters"]:
        referenced_assets.extend(
            player["headshot"] for player in roster["players"]
        )
    referenced_assets.extend(
        sponsor["logo_url"] for sponsor in fixture["sponsors"]
    )

    assert referenced_assets
    assert all(path.startswith("assets/") for path in referenced_assets)
    assert all((FIXTURE_ROOT / path).is_file() for path in referenced_assets)


def test_fictional_venues_do_not_leak_into_production_data() -> None:
    venues = json.loads(
        (ROOT / "Data" / "Venues" / "venues.json").read_text(
            encoding="utf-8"
        )
    )
    assert all(
        "CSRN-FICTIONAL-TEST" not in str(venue) for venue in venues
    )


def test_runtime_directories_are_ignored() -> None:
    ignore_text = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "Data/Social/" in ignore_text
    assert "Data/Recaps/" in ignore_text
