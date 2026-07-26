from __future__ import annotations

from pathlib import Path

from PIL import Image

from social_card_renderer import SocialCardRenderer


def context() -> dict:
    return {
        "event_label": "Touchdown",
        "team_name": "Caledonia",
        "description": "Jason Runner 42-yard touchdown run",
        "quarter": "3",
        "home_team": "Caledonia",
        "visitor_team": "Visitor",
        "home_score": 21,
        "visitor_score": 14,
        "player_name": "Jason Runner",
        "player_number": "7",
        "player_headshot": "/roster-headshots/player.png",
        "sponsor_name": "Local Sponsor",
        "sponsor_logo": "/asset-files/sponsor.png",
        "primary_color": "#B5121B",
        "secondary_color": "#111111",
    }


def test_social_card_renderer_creates_expected_canvas(tmp_path: Path) -> None:
    headshot = tmp_path / "player.png"
    sponsor = tmp_path / "sponsor.png"
    Image.new("RGB", (200, 300), "white").save(headshot)
    Image.new("RGB", (300, 100), "white").save(sponsor)

    def resolve(value: str) -> Path | None:
        return {
            "/roster-headshots/player.png": headshot,
            "/asset-files/sponsor.png": sponsor,
        }.get(value)

    renderer = SocialCardRenderer(
        output_dir=tmp_path / "cards",
        resolve_media=resolve,
    )
    output = renderer.render(context(), "social-1")
    assert output.is_file()
    with Image.open(output) as image:
        assert image.size == (1200, 675)
        assert image.mode == "RGB"


def test_social_card_renderer_handles_missing_media(tmp_path: Path) -> None:
    renderer = SocialCardRenderer(
        output_dir=tmp_path / "cards",
        resolve_media=lambda value: None,
    )
    output = renderer.render(context(), "social/missing")
    assert output.name == "social-missing.png"
    assert output.is_file()
