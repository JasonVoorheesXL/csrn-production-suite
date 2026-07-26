from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Mapping

from PIL import Image, ImageDraw, ImageFont, ImageOps


MediaResolver = Callable[[str], Path | None]


class SocialCardRenderer:
    """Render a dependable first-generation social event card."""

    WIDTH = 1200
    HEIGHT = 675

    def __init__(
        self,
        *,
        output_dir: Path,
        resolve_media: MediaResolver,
    ) -> None:
        self._output_dir = Path(output_dir)
        self._resolve_media = resolve_media

    @staticmethod
    def _color(value: Any, fallback: str) -> str:
        text = str(value or "").strip()
        if len(text) == 7 and text.startswith("#"):
            try:
                int(text[1:], 16)
                return text
            except ValueError:
                pass
        return fallback

    @staticmethod
    def _fit_text(
        draw: ImageDraw.ImageDraw,
        text: str,
        box_width: int,
        *,
        maximum: int = 64,
        minimum: int = 20,
    ) -> ImageFont.ImageFont:
        del maximum, minimum
        font = ImageFont.load_default()
        return font

    @staticmethod
    def _load_image(path: Path | None, size: tuple[int, int]) -> Image.Image | None:
        if path is None or not path.is_file():
            return None
        try:
            with Image.open(path) as source:
                image = source.convert("RGBA")
                return ImageOps.contain(image, size, Image.Resampling.LANCZOS)
        except (OSError, ValueError):
            return None

    @staticmethod
    def _paste_center(
        canvas: Image.Image,
        image: Image.Image,
        box: tuple[int, int, int, int],
    ) -> None:
        left, top, right, bottom = box
        x = left + max(0, (right - left - image.width) // 2)
        y = top + max(0, (bottom - top - image.height) // 2)
        canvas.alpha_composite(image, (x, y))

    def render(self, context: Mapping[str, Any], post_id: str) -> Path:
        self._output_dir.mkdir(parents=True, exist_ok=True)
        safe_id = "".join(
            character if character.isalnum() or character in "-_" else "-"
            for character in str(post_id or "social-card")
        ).strip("-") or "social-card"
        output = self._output_dir / f"{safe_id}.png"

        primary = self._color(context.get("primary_color"), "#B5121B")
        secondary = self._color(context.get("secondary_color"), "#111111")
        canvas = Image.new("RGBA", (self.WIDTH, self.HEIGHT), secondary)
        draw = ImageDraw.Draw(canvas)

        draw.rectangle((0, 0, self.WIDTH, 100), fill=primary)
        draw.rectangle((0, self.HEIGHT - 84, self.WIDTH, self.HEIGHT), fill=primary)
        draw.rectangle((0, 100, 390, self.HEIGHT - 84), fill="#171717")

        headshot_path = self._resolve_media(str(context.get("player_headshot", "")))
        headshot = self._load_image(headshot_path, (330, 430))
        if headshot is not None:
            self._paste_center(canvas, headshot, (30, 125, 360, 570))
        else:
            draw.ellipse((95, 180, 295, 380), fill="#303030", outline="#FFFFFF", width=4)
            draw.rectangle((125, 360, 265, 520), fill="#303030", outline="#FFFFFF", width=4)

        event_label = str(context.get("event_label", "BIG PLAY") or "BIG PLAY").upper()
        team_name = str(context.get("team_name", "") or "TEAM").upper()
        description = str(context.get("description", "") or "")
        quarter = str(context.get("quarter", "") or "")
        home_team = str(context.get("home_team", "Home") or "Home")
        visitor_team = str(context.get("visitor_team", "Visitor") or "Visitor")
        home_score = int(context.get("home_score", 0) or 0)
        visitor_score = int(context.get("visitor_score", 0) or 0)

        title_font = self._fit_text(draw, event_label, 730)
        body_font = ImageFont.load_default()
        draw.text((430, 135), event_label, fill="#FFFFFF", font=title_font)
        draw.text((430, 195), team_name, fill=primary, font=title_font)

        player_name = str(context.get("player_name", "") or "").strip()
        player_number = str(context.get("player_number", "") or "").strip()
        player_line = " ".join(
            part for part in (f"#{player_number}" if player_number else "", player_name) if part
        )
        if player_line:
            draw.text((430, 255), player_line, fill="#FFFFFF", font=title_font)

        wrapped: list[str] = []
        words = description.split()
        line = ""
        for word in words:
            candidate = f"{line} {word}".strip()
            if len(candidate) > 54 and line:
                wrapped.append(line)
                line = word
            else:
                line = candidate
        if line:
            wrapped.append(line)
        for index, text in enumerate(wrapped[:3]):
            draw.text((430, 330 + index * 34), text, fill="#E8E8E8", font=body_font)

        score_line = f"{visitor_team} {visitor_score}   —   {home_team} {home_score}"
        draw.text((430, 470), score_line, fill="#FFFFFF", font=title_font)
        if quarter:
            draw.text((430, 525), f"Quarter {quarter}", fill="#D0D0D0", font=body_font)

        sponsor_name = str(context.get("sponsor_name", "") or "").strip()
        sponsor_logo_path = self._resolve_media(str(context.get("sponsor_logo", "")))
        sponsor_logo = self._load_image(sponsor_logo_path, (180, 60))
        if sponsor_name:
            draw.text((430, 603), f"Presented by {sponsor_name}", fill="#FFFFFF", font=body_font)
        if sponsor_logo is not None:
            self._paste_center(canvas, sponsor_logo, (950, 592, 1175, 660))

        canvas.convert("RGB").save(output, format="PNG", optimize=True)
        return output
