"""Round 27: legacy sponsor records get a `sport` family on first load."""

from __future__ import annotations

import pytest

import app as app_module


@pytest.fixture(autouse=True)
def _football_install(monkeypatch: pytest.MonkeyPatch):
    # Pin the install default so the test does not depend on the dev
    # environment's identity profile.
    monkeypatch.setattr(app_module, "_default_onboarding_sport", lambda: "Football")


def test_legacy_records_are_backfilled_with_the_install_sport() -> None:
    items = [
        {"id": "a", "name": "Legacy A"},              # no sport key -> backfill
        {"id": "b", "name": "Legacy B", "sport": ""}, # explicit "" -> leave alone
        {"id": "c", "name": "Tagged C", "sport": "basketball"},
    ]

    changed = app_module._normalize_sponsors(items)

    assert changed is True
    assert items[0]["sport"] == "football"
    assert items[1]["sport"] == ""
    assert items[2]["sport"] == "basketball"


def test_normalizer_is_idempotent() -> None:
    items = [{"id": "a", "name": "Legacy A"}]
    assert app_module._normalize_sponsors(items) is True
    assert app_module._normalize_sponsors(items) is False
    assert items[0]["sport"] == "football"


def test_install_default_sport_family_collapses_canadian_football(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(app_module, "_default_onboarding_sport", lambda: "canadian_football")
    assert app_module._install_default_sport_family() == "football"


def test_install_default_sport_family_falls_back_to_football(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(app_module, "_default_onboarding_sport", lambda: "")
    assert app_module._install_default_sport_family() == "football"
