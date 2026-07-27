from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable, Mapping

from PIL import Image, ImageDraw, ImageFont, ImageOps


AssetResolver = Callable[[str], Path | None]


class SocialCardRenderer:
    """Render deterministic, platform-sized social cards from grounded draft data."""

    PLATFORM_SIZES = {
        "x": (1600, 900),
        "facebook": (1200, 630),
    }

    def __init__(
        self,
        *,
        output_dir: Path,
        asset_resolver: AssetResolver | None = None,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._resolve_asset = asset_resolver or (lambda _value: None)

    @staticmethod
    def _safe(value: Any, fallback: str = "") -> str:
        return str(value or fallback).strip()

    @staticmethod
    def _hex(value: Any, fallback: str) -> str:
        candidate = str(value or "").strip()
        return candidate.upper() if re.fullmatch(r"#[0-9A-Fa-f]{6}", candidate) else fallback

    @staticmethod
    def _font(size: int, *, bold: bool = False) -> ImageFont.ImageFont:
        candidates = [
            Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"),
        ]
        for candidate in candidates:
            try:
                if candidate.is_file():
                    return ImageFont.truetype(str(candidate), size=size)
            except OSError:
                continue
        return ImageFont.load_default()

    @staticmethod
    def _fit_text(
        draw: ImageDraw.ImageDraw,
        text: str,
        max_width: int,
        start_size: int,
        minimum: int,
        *,
        bold: bool = True,
    ) -> ImageFont.ImageFont:
        for size in range(start_size, minimum - 1, -2):
            font = SocialCardRenderer._font(size, bold=bold)
            box = draw.textbbox((0, 0), text, font=font)
            if box[2] - box[0] <= max_width:
                return font
        return SocialCardRenderer._font(minimum, bold=bold)

    def _image(self, reference: Any, size: tuple[int, int], *, contain: bool = False) -> Image.Image | None:
        path = self._resolve_asset(self._safe(reference))
        if path is None or not Path(path).is_file():
            return None
        try:
            source = Image.open(path).convert("RGBA")
        except (OSError, ValueError):
            return None
        if contain:
            canvas = Image.new("RGBA", size, (0, 0, 0, 0))
            fitted = ImageOps.contain(source, size, Image.Resampling.LANCZOS)
            canvas.alpha_composite(fitted, ((size[0] - fitted.width) // 2, (size[1] - fitted.height) // 2))
            return canvas
        return ImageOps.fit(source, size, Image.Resampling.LANCZOS, centering=(0.5, 0.35))

    def render(
        self,
        draft: Mapping[str, Any],
        *,
        platform: str,
        theme: Mapping[str, Any],
    ) -> dict[str, Any]:
        platform = str(platform or "x").lower()
        width, height = self.PLATFORM_SIZES.get(platform, self.PLATFORM_SIZES["x"])
        tokens = theme.get("tokens", {}) if isinstance(theme, Mapping) else {}
        primary = self._hex(tokens.get("primary_color"), "#C9203B")
        secondary = self._hex(tokens.get("secondary_color"), "#111111")
        accent = self._hex(tokens.get("accent_color"), "#FFFFFF")
        surface = self._hex(tokens.get("surface"), "#101318")
        surface_alt = self._hex(tokens.get("surface_alt"), "#242A33")
        text_color = self._hex(tokens.get("text"), "#FFFFFF")
        muted = self._hex(tokens.get("muted"), "#C8D0DB")

        image = Image.new("RGB", (width, height), surface)
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, width, height), fill=surface)
        draw.polygon([(0, 0), (width * 0.72, 0), (width * 0.56, height), (0, height)], fill=surface_alt)
        draw.rectangle((0, 0, width, max(16, height // 42)), fill=primary)
        draw.rectangle((0, height - max(18, height // 36), width, height), fill=secondary)

        content = draft.get("content", {}) if isinstance(draft.get("content"), Mapping) else {}
        home = draft.get("home", {}) if isinstance(draft.get("home"), Mapping) else {}
        visitor = draft.get("visitor", {}) if isinstance(draft.get("visitor"), Mapping) else {}
        player = draft.get("player", {}) if isinstance(draft.get("player"), Mapping) else {}
        sponsor = draft.get("sponsor", {}) if isinstance(draft.get("sponsor"), Mapping) else {}
        org = draft.get("organization", {}) if isinstance(draft.get("organization"), Mapping) else {}

        margin = int(width * 0.055)
        player_width = int(width * 0.30) if player.get("headshot") else 0
        copy_left = margin + player_width
        copy_width = width - copy_left - margin

        if player_width:
            headshot = self._image(player.get("headshot"), (player_width - 28, height - 120))
            if headshot is not None:
                image.paste(headshot.convert("RGB"), (margin, 56))
                draw.rectangle((margin, 56, margin + player_width - 28, height - 64), outline=accent, width=max(2, width // 500))

        eyebrow = self._safe(content.get("eyebrow"), self._safe(draft.get("kind"), "GAME UPDATE")).upper()
        headline = self._safe(content.get("headline"), "GAME UPDATE").upper()
        detail = self._safe(content.get("detail"), self._safe(draft.get("description")))
        score = self._safe(content.get("score"))

        draw.text((copy_left, int(height * 0.10)), eyebrow, font=self._font(max(24, width // 42), bold=True), fill=primary)
        headline_font = self._fit_text(draw, headline, copy_width, max(54, width // 14), max(30, width // 28))
        draw.text((copy_left, int(height * 0.17)), headline, font=headline_font, fill=text_color)

        if score:
            score_font = self._fit_text(draw, score, copy_width, max(70, width // 10), max(42, width // 20))
            draw.text((copy_left, int(height * 0.34)), score, font=score_font, fill=accent)

        team_line = f"{self._safe(home.get('name'), 'HOME')} vs {self._safe(visitor.get('name'), 'VISITOR')}"
        draw.text((copy_left, int(height * 0.58)), team_line, font=self._font(max(24, width // 38), bold=True), fill=muted)
        if detail:
            detail_font = self._fit_text(draw, detail, copy_width, max(28, width // 34), max(18, width // 58), bold=False)
            draw.text((copy_left, int(height * 0.66)), detail, font=detail_font, fill=text_color)

        logo_size = max(64, width // 11)
        home_logo = self._image(home.get("logo"), (logo_size, logo_size), contain=True)
        visitor_logo = self._image(visitor.get("logo"), (logo_size, logo_size), contain=True)
        logo_y = height - logo_size - int(height * 0.08)
        if home_logo is not None:
            image.alpha_composite(home_logo, (copy_left, logo_y)) if image.mode == "RGBA" else image.paste(home_logo, (copy_left, logo_y), home_logo)
        if visitor_logo is not None:
            x = copy_left + logo_size + 22
            image.paste(visitor_logo, (x, logo_y), visitor_logo)

        org_name = self._safe(org.get("short_name"), self._safe(org.get("name"), "CSRN"))
        draw.text((width - margin, 34), org_name, anchor="ra", font=self._font(max(22, width // 50), bold=True), fill=accent)

        if sponsor and not draft.get("sponsor_suppressed", False):
            bar_h = max(58, height // 10)
            y = height - bar_h - max(18, height // 36)
            draw.rectangle((0, y, width, y + bar_h), fill=secondary)
            sponsor_name = self._safe(sponsor.get("name"))
            lead = self._safe(sponsor.get("lead_in"), "Presented by")
            draw.text((margin, y + bar_h // 2), f"{lead}: {sponsor_name}", anchor="lm", font=self._font(max(22, width // 48), bold=True), fill=text_color)
            sponsor_logo = self._image(sponsor.get("logo"), (bar_h - 10, bar_h - 10), contain=True)
            if sponsor_logo is not None:
                image.paste(sponsor_logo, (width - margin - sponsor_logo.width, y + 5), sponsor_logo)

        draft_id = self._safe(draft.get("id"), "draft")
        safe_id = re.sub(r"[^A-Za-z0-9_.-]+", "-", draft_id).strip("-") or "draft"
        output = self.output_dir / f"{safe_id}-{platform}.png"
        image.save(output, "PNG", optimize=True)
        return {
            "path": str(output),
            "filename": output.name,
            "platform": platform,
            "width": width,
            "height": height,
            "theme_id": self._safe(theme.get("id"), "modern_network"),
        }
