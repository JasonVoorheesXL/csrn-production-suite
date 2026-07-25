from __future__ import annotations

import copy

from configuration_service import ConfigurationService


def build_service():
    config = {
        "organization": {
            "name": "Caledonia Sports Radio Network",
            "short_name": "CSRN",
        },
        "obs": {
            "host": "127.0.0.1",
            "port": 4455,
        },
        "social": {
            "facebook": "https://facebook.com/csrn",
            "x": "https://x.com/csrn",
            "instagram": "",
            "youtube": "",
            "website": "https://example.com",
        },
        "application": {
            "version": "old-version",
            "build": "old-build",
            "auto_save": True,
        },
    }
    saved: list[dict] = []

    def load_config():
        return copy.deepcopy(config)

    def save_config(value):
        config.clear()
        config.update(copy.deepcopy(value))
        saved.append(copy.deepcopy(value))

    service = ConfigurationService(
        load_config=load_config,
        save_config=save_config,
        runtime_version="Version 1.13.0-alpha.4n — Configuration Service",
        runtime_build="V1.13A4N-CONFIGURATION-SERVICE",
    )
    return service, config, saved


def test_read_returns_copy() -> None:
    service, config, _ = build_service()
    result = service.read()
    result.data["config"]["organization"]["name"] = "Changed"
    assert result.ok
    assert config["organization"]["name"] == "Caledonia Sports Radio Network"


def test_normalize_empty_social_url() -> None:
    value, valid, message = ConfigurationService.normalize_social_url(
        "facebook",
        "",
    )
    assert value == ""
    assert valid is True
    assert message == ""


def test_normalize_social_handles_username_shortcuts() -> None:
    assert ConfigurationService.normalize_social_url(
        "facebook",
        "@csrn",
    )[0] == "https://facebook.com/csrn"
    assert ConfigurationService.normalize_social_url(
        "x",
        "csrn",
    )[0] == "https://x.com/csrn"
    assert ConfigurationService.normalize_social_url(
        "youtube",
        "csrn",
    )[0] == "https://youtube.com/@csrn"


def test_normalize_website_adds_https() -> None:
    value, valid, message = ConfigurationService.normalize_social_url(
        "website",
        "example.com",
    )
    assert value == "https://example.com"
    assert valid is True
    assert message == ""


def test_normalize_social_rejects_wrong_platform_domain() -> None:
    value, valid, message = ConfigurationService.normalize_social_url(
        "facebook",
        "https://example.com/csrn",
    )
    assert value == "https://example.com/csrn"
    assert valid is False
    assert message == "Expected a valid facebook URL"


def test_normalize_social_block_fills_all_supported_fields() -> None:
    normalized, errors = ConfigurationService.normalize_social_block(
        {"instagram": "@caledonia"}
    )
    assert errors == {}
    assert normalized == {
        "facebook": "",
        "x": "",
        "instagram": "https://instagram.com/caledonia",
        "youtube": "",
        "website": "",
    }


def test_update_merges_known_sections_and_ignores_unknown_sections() -> None:
    service, config, saved = build_service()
    result = service.update(
        {
            "organization": {"short_name": "PFN"},
            "obs": {"port": 4456},
            "unknown": {"enabled": True},
        }
    )
    assert result.ok
    assert config["organization"] == {
        "name": "Caledonia Sports Radio Network",
        "short_name": "PFN",
    }
    assert config["obs"] == {"host": "127.0.0.1", "port": 4456}
    assert "unknown" not in config
    assert len(saved) == 1


def test_update_protects_runtime_identity() -> None:
    service, config, _ = build_service()
    result = service.update(
        {
            "application": {
                "version": "tampered",
                "build": "tampered",
                "auto_save": False,
            }
        }
    )
    assert result.ok
    assert config["application"]["version"] == (
        "Version 1.13.0-alpha.4n — Configuration Service"
    )
    assert config["application"]["build"] == (
        "V1.13A4N-CONFIGURATION-SERVICE"
    )
    assert config["application"]["auto_save"] is False


def test_update_normalizes_social_and_preserves_response_contract() -> None:
    service, config, _ = build_service()
    result = service.update(
        {
            "social": {
                "facebook": "newpage",
                "website": "csrn.example",
            }
        }
    )
    assert result.ok
    assert result.data["config"] == config
    assert config["social"] == {
        "facebook": "https://facebook.com/newpage",
        "x": "",
        "instagram": "",
        "youtube": "",
        "website": "https://csrn.example",
    }


def test_invalid_social_does_not_save() -> None:
    service, config, saved = build_service()
    before = copy.deepcopy(config)
    result = service.update(
        {"social": {"youtube": "https://example.com/not-youtube"}}
    )
    assert result.code == "INVALID_SOCIAL_URL"
    assert result.data["fields"] == {
        "youtube": "Expected a valid youtube URL"
    }
    assert config == before
    assert saved == []


def test_non_mapping_payload_and_social_block_are_rejected() -> None:
    service, config, saved = build_service()
    assert service.update([]).code == "CONFIG_PAYLOAD_REQUIRED"
    result = service.update({"social": "not-an-object"})
    assert result.code == "INVALID_SOCIAL_URL"
    assert result.data["fields"] == {
        "social": "Expected a social settings object"
    }
    assert config["application"]["version"] == "old-version"
    assert saved == []
