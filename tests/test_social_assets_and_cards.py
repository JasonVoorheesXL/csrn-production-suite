from __future__ import annotations

from pathlib import Path

from PIL import Image

from social_asset_resolver import SocialAssetResolver
from social_card_renderer import SocialCardRenderer


def make_png(path: Path, size=(160, 160)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", size, (220, 20, 40, 255)).save(path)
    return path


def resolver(tmp_path: Path) -> SocialAssetResolver:
    base = tmp_path / "app"
    data = tmp_path / "customer" / "Data"
    assets = data / "Assets" / "Files"
    headshots = data / "Rosters" / "Headshots"
    for path in (base / "static", assets, headshots, data / "Logos"):
        path.mkdir(parents=True, exist_ok=True)
    return SocialAssetResolver(
        base_dir=base,
        data_dir=data,
        asset_upload_dir=assets,
        headshots_dir=headshots,
    )


def test_resolver_maps_static_asset(tmp_path: Path) -> None:
    service = resolver(tmp_path)
    path = make_png(tmp_path / "app" / "static" / "logo.png")
    assert service("/static/logo.png") == path.resolve()


def test_resolver_maps_sponsor_asset(tmp_path: Path) -> None:
    service = resolver(tmp_path)
    path = make_png(tmp_path / "customer" / "Data" / "Assets" / "Files" / "sponsor.png")
    assert service("/asset-files/sponsor.png") == path.resolve()


def test_resolver_maps_roster_headshot(tmp_path: Path) -> None:
    service = resolver(tmp_path)
    path = make_png(tmp_path / "customer" / "Data" / "Rosters" / "Headshots" / "player.png")
    assert service("/roster-headshots/player.png") == path.resolve()


def test_resolver_maps_school_logo(tmp_path: Path) -> None:
    service = resolver(tmp_path)
    path = make_png(tmp_path / "customer" / "Data" / "Logos" / "school-one" / "round-master.png")
    assert service("/school-logos/school-one/round-master.png") == path.resolve()


def test_resolver_rejects_remote_urls_and_traversal(tmp_path: Path) -> None:
    service = resolver(tmp_path)
    assert service("https://example.com/logo.png") is None
    assert service("/asset-files/../secret.png") is None
    assert service("../../secret.png") is None


def draft(*, sponsor=True, headshot=True) -> dict:
    return {
        "id": "SOC-1",
        "kind": "TOUCHDOWN",
        "content": {
            "eyebrow": "Q2",
            "headline": "TOUCHDOWN",
            "detail": "12-yard touchdown run by Alex Morgan",
            "score": "Home 14 · Visitor 7",
        },
        "home": {"name": "Home", "logo": "/school-logos/home/round-master.png"},
        "visitor": {"name": "Visitor", "logo": "/school-logos/visitor/round-master.png"},
        "player": {
            "name": "Alex Morgan",
            "number": "12",
            "headshot": "/roster-headshots/player.png" if headshot else "",
        },
        "organization": {"name": "School Radio", "short_name": "SRN"},
        "sponsor": {"name": "Local Bank", "logo": "/asset-files/sponsor.png", "lead_in": "Presented by"} if sponsor else {},
        "sponsor_suppressed": False,
    }


def theme() -> dict:
    return {
        "id": "modern_network",
        "tokens": {
            "primary_color": "#B5121B",
            "secondary_color": "#111111",
            "accent_color": "#FFFFFF",
            "surface": "#101318",
            "surface_alt": "#242A33",
            "text": "#FFFFFF",
            "muted": "#C8D0DB",
        },
    }


def prepared_renderer(tmp_path: Path) -> SocialCardRenderer:
    service = resolver(tmp_path)
    make_png(tmp_path / "customer" / "Data" / "Logos" / "home" / "round-master.png")
    make_png(tmp_path / "customer" / "Data" / "Logos" / "visitor" / "round-master.png")
    make_png(tmp_path / "customer" / "Data" / "Rosters" / "Headshots" / "player.png", (300, 500))
    make_png(tmp_path / "customer" / "Data" / "Assets" / "Files" / "sponsor.png")
    return SocialCardRenderer(output_dir=tmp_path / "cards", asset_resolver=service)


def test_renderer_creates_x_card_at_platform_size(tmp_path: Path) -> None:
    renderer = prepared_renderer(tmp_path)
    result = renderer.render(draft(), platform="x", theme=theme())
    path = Path(result["path"])
    assert path.is_file()
    assert Image.open(path).size == (1600, 900)
    assert result["theme_id"] == "modern_network"


def test_renderer_creates_facebook_card_at_platform_size(tmp_path: Path) -> None:
    renderer = prepared_renderer(tmp_path)
    result = renderer.render(draft(), platform="facebook", theme=theme())
    assert Image.open(result["path"]).size == (1200, 630)


def test_renderer_handles_missing_optional_assets(tmp_path: Path) -> None:
    renderer = SocialCardRenderer(output_dir=tmp_path / "cards", asset_resolver=lambda _value: None)
    result = renderer.render(draft(sponsor=False, headshot=False), platform="x", theme=theme())
    assert Path(result["path"]).is_file()


def test_emergency_sponsor_suppression_still_renders(tmp_path: Path) -> None:
    renderer = prepared_renderer(tmp_path)
    payload = draft()
    payload["kind"] = "WEATHER_EMERGENCY"
    payload["sponsor_suppressed"] = True
    result = renderer.render(payload, platform="facebook", theme=theme())
    assert Path(result["path"]).is_file()
