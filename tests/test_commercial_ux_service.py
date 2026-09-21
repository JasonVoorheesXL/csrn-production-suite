from __future__ import annotations

from dataclasses import dataclass

from commercial_ux_service import CommercialUxService


@dataclass
class Result:
    data: dict
    ok: bool = True


def build_service(*, organization_name="Demo Sports", connected=True):
    return CommercialUxService(
        load_config=lambda: {
            "organization": {"name": organization_name},
            "broadcast_defaults": {"timezone": "America/Chicago"},
            "application": {"automatic_backup": True},
        },
        theme_status=lambda: Result({"theme": {"active": {"id": "modern_network", "name": "Modern Network"}, "locked": False}}),
        theme_catalog=lambda: Result({"presets": [{"id": "modern_network", "name": "Modern Network", "description": "Clean"}]}),
        oauth_status=lambda: Result({"providers": [{"id": "x", "connected": connected}]}),
        social_status=lambda: Result({"social": {"accounts": [], "drafts": [{"id": "one"}]}}),
    )


def test_options_include_controlled_theme_and_time_zone_choices() -> None:
    result = build_service().options()
    assert result.ok
    assert result.data["themes"][0]["id"] == "modern_network"
    assert "America/Chicago" in result.data["timezones"]
    assert "Play-by-Play" in result.data["caption_channel_roles"]


def test_options_include_every_customer_feature_in_directory() -> None:
    modules = {row["id"]: row for row in build_service().options().data["modules"]}
    for required in ("command", "games", "themes", "social", "captions", "weather", "obs", "recovery", "licensing", "settings"):
        assert required in modules
        assert modules[required]["href"].startswith("/")


def test_status_reports_plain_language_setup_progress() -> None:
    result = build_service().status()
    assert result.ok
    setup = result.data["setup"]
    assert setup["percent"] == 100
    assert setup["completed"] == setup["required"]
    labels = {row["label"] for row in setup["checks"]}
    assert "Organization identity" in labels
    assert "Graphics theme selected" in labels


def test_social_connection_is_optional_for_required_progress() -> None:
    setup = build_service(connected=False).status().data["setup"]
    assert setup["percent"] == 100
    social = next(row for row in setup["checks"] if row["id"] == "social")
    assert social["optional"] is True
    assert social["complete"] is False


def test_missing_organization_reduces_setup_progress() -> None:
    setup = build_service(organization_name="").status().data["setup"]
    assert setup["percent"] < 100
    organization = next(row for row in setup["checks"] if row["id"] == "organization")
    assert organization["complete"] is False
