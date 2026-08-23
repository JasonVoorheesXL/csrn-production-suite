from __future__ import annotations

import json
from pathlib import Path

from theme_service import GraphicsThemeService


def service(tmp_path: Path, now: int = 1000) -> GraphicsThemeService:
    return GraphicsThemeService(
        state_file=tmp_path / "Data" / "Themes" / "theme_state.json",
        load_state=lambda: {
            "home_identity": {"primary_color": "#112233"},
            "visitor_identity": {"primary_color": "#445566"},
        },
        load_config=lambda: {
            "organization": {
                "primary_color": "#AABBCC",
                "secondary_color": "#101010",
                "accent_color": "#FFFFFF",
            }
        },
        clock=lambda: now,
    )


def test_catalog_contains_exactly_eight_original_presets(tmp_path: Path) -> None:
    result = service(tmp_path).catalog()
    ids = {item["id"] for item in result.data["presets"]}
    assert result.data["count"] == 8
    assert ids == {
        "classic_1980s",
        "early_cable",
        "modern_network",
        "minimal_radio",
        "heritage_press_box",
        "friday_night_stadium",
        "digital_neon",
        "collegiate_traditional",
    }


def test_catalog_does_not_use_network_brand_names(tmp_path: Path) -> None:
    text = json.dumps(service(tmp_path).catalog().data).casefold()
    for forbidden in ("espn", "fox sports", "cbs sports", "nbc sports", "tnt sports"):
        assert forbidden not in text


def test_default_status_uses_modern_network(tmp_path: Path) -> None:
    result = service(tmp_path).status()
    assert result.code == "OK"
    assert result.data["theme"]["active"]["id"] == "modern_network"
    assert result.data["theme"]["locked"] is False


def test_school_colors_are_resolved_from_customer_data(tmp_path: Path) -> None:
    active = service(tmp_path).status().data["theme"]["active"]
    assert active["school_colors"]["organization_primary"] == "#AABBCC"
    assert active["school_colors"]["home_primary"] == "#112233"
    assert active["school_colors"]["visitor_primary"] == "#445566"
    assert active["tokens"]["primary_color"] == "#AABBCC"


def test_preview_does_not_persist(tmp_path: Path) -> None:
    instance = service(tmp_path)
    result = instance.preview("heritage_press_box", {"primary_color": "#123456"})
    assert result.code == "PREVIEW_READY"
    assert result.data["preview"]["tokens"]["primary_color"] == "#123456"
    assert instance.status().data["theme"]["active"]["id"] == "modern_network"
    assert not instance.state_file.exists()


def test_preview_rejects_unknown_preset(tmp_path: Path) -> None:
    assert service(tmp_path).preview("copied-network-package").code == "PRESET_NOT_FOUND"


def test_overrides_are_allowlisted(tmp_path: Path) -> None:
    result = service(tmp_path).preview("modern_network", {"raw_css": "body{display:none}"})
    assert result.code == "OVERRIDES_INVALID"
    assert "Unsupported override keys" in result.data["errors"][0]


def test_color_override_requires_six_digit_hex(tmp_path: Path) -> None:
    result = service(tmp_path).preview("modern_network", {"primary_color": "red"})
    assert result.code == "OVERRIDES_INVALID"


def test_font_override_is_allowlisted(tmp_path: Path) -> None:
    result = service(tmp_path).preview("modern_network", {"font_key": "Comic Sans"})
    assert result.code == "OVERRIDES_INVALID"


def test_numeric_overrides_are_bounded(tmp_path: Path) -> None:
    result = service(tmp_path).preview(
        "modern_network",
        {"radius_px": 100, "panel_opacity": 0.1, "motion_scale": 4},
    )
    assert result.code == "OVERRIDES_INVALID"
    assert len(result.data["errors"]) == 3


def test_activate_persists_theme_and_overrides(tmp_path: Path) -> None:
    instance = service(tmp_path)
    result = instance.activate(
        "classic_1980s",
        {"font_key": "condensed_sans", "radius_px": 0},
    )
    assert result.code == "THEME_ACTIVATED"
    stored = json.loads(instance.state_file.read_text(encoding="utf-8"))
    assert stored["active_preset"] == "classic_1980s"
    assert stored["overrides"]["radius_px"] == 0
    assert stored["updated_at"] == 1000


def test_lock_requires_exact_confirmation(tmp_path: Path) -> None:
    instance = service(tmp_path)
    result = instance.set_lock(True, "lock it")
    assert result.code == "LOCK_CONFIRMATION_REQUIRED"
    assert result.data["required_confirmation"] == "LOCK SEASON THEME"


def test_locked_theme_blocks_changes_without_override_phrase(tmp_path: Path) -> None:
    instance = service(tmp_path)
    assert instance.set_lock(True, "LOCK SEASON THEME").ok
    assert instance.activate("digital_neon").code == "LOCKED_THEME_CONFIRMATION_REQUIRED"
    result = instance.activate(
        "digital_neon",
        confirmation="CHANGE LOCKED SEASON THEME",
    )
    assert result.code == "THEME_ACTIVATED"


def test_unlock_requires_exact_confirmation(tmp_path: Path) -> None:
    instance = service(tmp_path)
    assert instance.set_lock(True, "LOCK SEASON THEME").ok
    assert instance.set_lock(False, "UNLOCK").code == "LOCK_CONFIRMATION_REQUIRED"
    assert instance.set_lock(False, "UNLOCK SEASON THEME").code == "THEME_UNLOCKED"


def test_reset_overrides_respects_lock(tmp_path: Path) -> None:
    instance = service(tmp_path)
    instance.activate("modern_network", {"primary_color": "#123456"})
    instance.set_lock(True, "LOCK SEASON THEME")
    assert instance.reset_overrides().code == "LOCKED_THEME_CONFIRMATION_REQUIRED"
    result = instance.reset_overrides(confirmation="CHANGE LOCKED SEASON THEME")
    assert result.code == "OVERRIDES_RESET"
    assert instance.status().data["theme"]["overrides"] == {}


def test_save_and_activate_variant(tmp_path: Path) -> None:
    instance = service(tmp_path)
    saved = instance.save_variant(
        "Home Broadcast",
        "collegiate_traditional",
        {"primary_color": "#990000"},
    )
    assert saved.code == "VARIANT_SAVED"
    activated = instance.activate_variant("home broadcast")
    assert activated.code == "VARIANT_ACTIVATED"
    assert instance.status().data["theme"]["active"]["id"] == "collegiate_traditional"


def test_variant_name_is_validated(tmp_path: Path) -> None:
    assert service(tmp_path).save_variant("../escape", "modern_network").code == "VARIANT_NAME_INVALID"


def test_delete_variant_requires_confirmation(tmp_path: Path) -> None:
    instance = service(tmp_path)
    instance.save_variant("Home", "modern_network")
    assert instance.delete_variant("Home", "delete").code == "VARIANT_DELETE_CONFIRMATION_REQUIRED"
    assert instance.delete_variant("Home", "DELETE THEME VARIANT").code == "VARIANT_DELETED"


def test_css_contains_shared_overlay_targets(tmp_path: Path) -> None:
    css = service(tmp_path).css().data["css"]
    for selector in (
        "#scorebug",
        "#lowerThird",
        "#playerGraphic",
        "#personnelGraphic",
        "#eventTicker",
        ".caption-line",
        ".bug",
        ".banner",
        ".fullscreen",
    ):
        assert selector in css
    assert "--csrn-theme-primary" in css


def test_public_state_omits_saved_variants_and_raw_overrides(tmp_path: Path) -> None:
    instance = service(tmp_path)
    instance.save_variant("Internal", "modern_network", {"primary_color": "#123456"})
    payload = instance.public_state().data["theme"]
    assert "variants" not in payload
    assert "overrides" not in payload


