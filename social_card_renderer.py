from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable, Mapping

from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageOps


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
    def _text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> int:
        box = draw.textbbox((0, 0), text, font=font)
        return max(0, box[2] - box[0])

    @staticmethod
    def _line_height(draw: ImageDraw.ImageDraw, font: ImageFont.ImageFont) -> int:
        box = draw.textbbox((0, 0), "Ag", font=font)
        return max(1, box[3] - box[1])

    @classmethod
    def _fit_text(
        cls,
        draw: ImageDraw.ImageDraw,
        text: str,
        max_width: int,
        start_size: int,
        minimum: int,
        *,
        bold: bool = True,
    ) -> ImageFont.ImageFont:
        for size in range(start_size, minimum - 1, -2):
            font = cls._font(size, bold=bold)
            if cls._text_width(draw, text, font) <= max_width:
                return font
        return cls._font(minimum, bold=bold)

    @classmethod
    def _wrap(cls, draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
        words = str(text or "").split()
        if not words:
            return []
        lines: list[str] = []
        current = words[0]
        for word in words[1:]:
            candidate = f"{current} {word}"
            if cls._text_width(draw, candidate, font) <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
        return lines

    @classmethod
    def _fit_wrapped(
        cls,
        draw: ImageDraw.ImageDraw,
        text: str,
        *,
        max_width: int,
        max_height: int,
        start_size: int,
        minimum: int,
        max_lines: int,
        bold: bool,
    ) -> tuple[ImageFont.ImageFont, list[str], bool]:
        for size in range(start_size, minimum - 1, -2):
            font = cls._font(size, bold=bold)
            lines = cls._wrap(draw, text, font, max_width)
            line_height = cls._line_height(draw, font)
            if len(lines) <= max_lines and len(lines) * line_height <= max_height:
                return font, lines, False
        font = cls._font(minimum, bold=bold)
        lines = cls._wrap(draw, text, font, max_width)
        truncated = len(lines) > max_lines
        lines = lines[:max_lines]
        if truncated and lines:
            ellipsis = "…"
            last = lines[-1]
            while last and cls._text_width(draw, last + ellipsis, font) > max_width:
                last = last[:-1].rstrip()
            lines[-1] = (last + ellipsis) if last else ellipsis
        return font, lines, truncated

    @classmethod
    def _draw_lines(
        cls,
        draw: ImageDraw.ImageDraw,
        xy: tuple[int, int],
        lines: list[str],
        *,
        font: ImageFont.ImageFont,
        fill: str,
        spacing: int = 4,
    ) -> int:
        x, y = xy
        line_height = cls._line_height(draw, font)
        for line in lines:
            draw.text((x, y), line, font=font, fill=fill)
            y += line_height + spacing
        return y

    def _image(
        self,
        reference: Any,
        size: tuple[int, int],
        *,
        contain: bool = False,
        trim_uniform_border: bool = False,
    ) -> Image.Image | None:
        path = self._resolve_asset(self._safe(reference))
        if path is None or not Path(path).is_file():
            return None
        try:
            source = Image.open(path).convert("RGBA")
        except (OSError, ValueError):
            return None
        alpha_box = source.getchannel("A").getbbox()
        if alpha_box:
            source = source.crop(alpha_box)
        if trim_uniform_border and source.width > 8 and source.height > 8:
            # Many sponsor files are exported on a large solid-color canvas.
            # Remove that uniform border so the visible mark fills its panel.
            corners = [
                source.getpixel((0, 0)),
                source.getpixel((source.width - 1, 0)),
                source.getpixel((0, source.height - 1)),
                source.getpixel((source.width - 1, source.height - 1)),
            ]
            background = tuple(sum(pixel[index] for pixel in corners) // len(corners) for index in range(4))
            backdrop = Image.new("RGBA", source.size, background)
            difference = ImageChops.difference(source, backdrop).convert("L")
            mask = difference.point(lambda value: 255 if value > 18 else 0)
            visual_box = mask.getbbox()
            if visual_box:
                left, top, right, bottom = visual_box
                pad = max(2, int(min(source.size) * 0.03))
                source = source.crop((
                    max(0, left - pad), max(0, top - pad),
                    min(source.width, right + pad), min(source.height, bottom + pad),
                ))
        if contain:
            canvas = Image.new("RGBA", size, (0, 0, 0, 0))
            fitted = ImageOps.contain(source, size, Image.Resampling.LANCZOS)
            canvas.alpha_composite(fitted, ((size[0] - fitted.width) // 2, (size[1] - fitted.height) // 2))
            return canvas
        return ImageOps.fit(source, size, Image.Resampling.LANCZOS, centering=(0.5, 0.35))

    def _draw_sponsor_footer(
        self,
        image: Image.Image,
        draw: ImageDraw.ImageDraw,
        *,
        sponsor: Mapping[str, Any],
        sponsor_y: int,
        sponsor_bar_h: int,
        width: int,
        height: int,
        margin: int,
        primary: str,
        secondary: str,
        text_color: str,
        muted: str,
    ) -> tuple[bool, str, list[str]]:
        if not sponsor or sponsor_bar_h <= 0:
            return False, "none", []
        warnings: list[str] = []
        layout = "banner" if self._safe(sponsor.get("layout")).lower() == "banner" else "standard"
        draw.rectangle((0, sponsor_y, width, sponsor_y + sponsor_bar_h), fill=secondary)
        draw.rectangle((0, sponsor_y, width, sponsor_y + max(3, height // 170)), fill=primary)
        banner_logo = self._image(
            sponsor.get("banner_logo"),
            (max(1, width - 2 * max(10, margin // 3)), max(1, sponsor_bar_h - 14)),
            contain=True,
        )
        if layout == "banner":
            if banner_logo is None:
                warnings.append("sponsor_banner_asset_required")
                layout = "standard"
            else:
                x = (width - banner_logo.width) // 2
                y = sponsor_y + (sponsor_bar_h - banner_logo.height) // 2
                image.paste(banner_logo, (x, y), banner_logo)
                return True, "banner", warnings

        sponsor_name = self._safe(sponsor.get("name"))
        lead = self._safe(sponsor.get("lead_in"), "Presented by")

        # Standard mode is a sponsor-first commercial lockup. The mark receives
        # a large dedicated panel and the sponsor name occupies the remaining
        # footer width at mobile-readable scale.
        outer_y = max(10, sponsor_bar_h // 12)
        lockup_y = sponsor_y + outer_y
        lockup_h = max(1, sponsor_bar_h - 2 * outer_y)
        logo_panel_w = min(max(int(width * 0.30), lockup_h * 2), int(width * 0.38))
        logo_panel_x = margin
        logo_panel_radius = max(12, lockup_h // 10)
        draw.rounded_rectangle(
            (logo_panel_x, lockup_y, logo_panel_x + logo_panel_w, lockup_y + lockup_h),
            radius=logo_panel_radius, fill="#F4F5F7", outline="#D9DDE2",
            width=max(2, width // 600),
        )
        logo_inset_x = max(12, logo_panel_w // 18)
        logo_inset_y = max(8, lockup_h // 14)
        standard_logo = self._image(
            sponsor.get("logo"),
            (max(1, logo_panel_w - 2 * logo_inset_x), max(1, lockup_h - 2 * logo_inset_y)),
            contain=True, trim_uniform_border=True,
        )
        if standard_logo is not None:
            image.paste(
                standard_logo,
                (
                    logo_panel_x + (logo_panel_w - standard_logo.width) // 2,
                    lockup_y + (lockup_h - standard_logo.height) // 2,
                ),
                standard_logo,
            )
        else:
            warnings.append("sponsor_standard_logo_missing")

        text_x = logo_panel_x + logo_panel_w + max(24, width // 45)
        text_right = width - margin
        available = max(240, text_right - text_x)
        lead_font = self._fit_text(
            draw, lead.upper(), available,
            max(30, width // 40), max(22, width // 58), bold=True,
        )
        name_font = self._fit_text(
            draw, sponsor_name, available,
            max(58, width // 20), max(36, width // 32), bold=True,
        )
        lead_h = self._line_height(draw, lead_font)
        name_h = self._line_height(draw, name_font)
        gap = max(6, sponsor_bar_h // 32)
        text_h = lead_h + gap + name_h
        text_y = sponsor_y + max(8, (sponsor_bar_h - text_h) // 2)
        draw.text((text_x, text_y), lead.upper(), font=lead_font, fill=muted)
        draw.text((text_x, text_y + lead_h + gap), sponsor_name, font=name_font, fill=text_color)
        return True, "standard", warnings

    def _render_compact_score(
        self,
        draft: Mapping[str, Any],
        *,
        platform: str,
        theme: Mapping[str, Any],
    ) -> dict[str, Any]:
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
        draw.polygon([(0, 0), (int(width * 0.78), 0), (int(width * 0.62), height), (0, height)], fill=surface_alt)
        top_strip = max(18, height // 38)
        bottom_strip = max(18, height // 36)
        draw.rectangle((0, 0, width, top_strip), fill=primary)
        draw.rectangle((0, height - bottom_strip, width, height), fill=secondary)

        content = draft.get("content", {}) if isinstance(draft.get("content"), Mapping) else {}
        sponsor = draft.get("sponsor", {}) if isinstance(draft.get("sponsor"), Mapping) else {}
        sponsor_visible = bool(sponsor and not draft.get("sponsor_suppressed", False) and self._safe(sponsor.get("name")))
        layout = "banner" if self._safe(sponsor.get("layout")).lower() == "banner" else "standard"
        sponsor_bar_h = (max(92, height // 6) if layout == "banner" else max(168, int(height * 0.26))) if sponsor_visible else 0
        sponsor_y = height - bottom_strip - sponsor_bar_h
        body_bottom = sponsor_y if sponsor_visible else height - bottom_strip
        margin = int(width * 0.07)
        warnings: list[str] = []

        org = draft.get("organization", {}) if isinstance(draft.get("organization"), Mapping) else {}
        org_name = self._safe(org.get("short_name"), self._safe(org.get("name"), "CSRN"))
        draw.text((width - margin, top_strip + max(14, height // 70)), org_name, anchor="ra", font=self._font(max(24, width // 48), bold=True), fill=accent)

        eyebrow = self._safe(content.get("eyebrow"), "GAME UPDATE").upper()
        headline = self._safe(content.get("headline"), "SCORING UPDATE").upper()
        detail = self._safe(content.get("detail"))
        score = self._safe(content.get("score"))
        y = top_strip + max(42, height // 12)
        eyebrow_font = self._fit_text(draw, eyebrow, width - 2 * margin, max(32, width // 34), max(24, width // 50), bold=True)
        draw.text((margin, y), eyebrow, font=eyebrow_font, fill=primary)
        y += self._line_height(draw, eyebrow_font) + max(14, height // 45)

        headline_font, headline_lines, headline_truncated = self._fit_wrapped(
            draw, headline, max_width=width - 2 * margin, max_height=max(100, int(height * .25)),
            start_size=max(92, width // 9), minimum=max(60, width // 20), max_lines=2, bold=True,
        )
        if headline_truncated:
            warnings.append("headline_truncated")
        y = self._draw_lines(draw, (margin, y), headline_lines, font=headline_font, fill=text_color, spacing=max(4, height // 120))
        y += max(18, height // 35)

        detail_font, detail_lines, detail_truncated = self._fit_wrapped(
            draw, detail, max_width=width - 2 * margin, max_height=max(80, int(height * .18)),
            start_size=max(62, width // 16), minimum=max(42, width // 28), max_lines=2, bold=True,
        )
        if detail_truncated:
            warnings.append("detail_truncated")
        y = self._draw_lines(draw, (margin, y), detail_lines, font=detail_font, fill=accent, spacing=max(3, height // 140))

        score_font, score_lines, score_truncated = self._fit_wrapped(
            draw, score, max_width=width - 2 * margin, max_height=max(64, body_bottom - y - 28),
            start_size=max(38, width // 30), minimum=max(28, width // 42), max_lines=2, bold=True,
        )
        if score_truncated:
            warnings.append("score_truncated")
        score_y = max(y + 12, body_bottom - len(score_lines) * (self._line_height(draw, score_font) + 4) - max(22, height // 30))
        self._draw_lines(draw, (margin, score_y), score_lines, font=score_font, fill=muted, spacing=4)

        sponsor_rendered = False
        sponsor_layout = "none"
        if sponsor_visible:
            sponsor_rendered, sponsor_layout, sponsor_warnings = self._draw_sponsor_footer(
                image, draw, sponsor=sponsor, sponsor_y=sponsor_y, sponsor_bar_h=sponsor_bar_h,
                width=width, height=height, margin=margin, primary=primary, secondary=secondary,
                text_color=text_color, muted=muted,
            )
            warnings.extend(sponsor_warnings)

        draft_id = self._safe(draft.get("id"), "draft")
        safe_id = re.sub(r"[^A-Za-z0-9_.-]+", "-", draft_id).strip("-") or "draft"
        output = self.output_dir / f"{safe_id}-{platform}.png"
        image.save(output, "PNG", optimize=True)
        return {
            "path": str(output), "filename": output.name, "platform": platform,
            "width": width, "height": height, "theme_id": self._safe(theme.get("id"), "modern_network"),
            "layout": {
                "card_style": "compact_score", "headline_lines": headline_lines,
                "score_lines": score_lines, "detail_lines": detail_lines,
                "headshot_rendered": False, "sponsor_rendered": sponsor_rendered,
                "sponsor_layout": sponsor_layout,
                "minimum_mobile_font": min(getattr(headline_font, "size", 60), getattr(detail_font, "size", 42), getattr(score_font, "size", 28)),
                "warnings": warnings,
            },
        }

    def render(
        self,
        draft: Mapping[str, Any],
        *,
        platform: str,
        theme: Mapping[str, Any],
    ) -> dict[str, Any]:
        platform = str(platform or "x").lower()
        if self._safe(draft.get("card_style")).lower() == "compact_score":
            return self._render_compact_score(draft, platform=platform, theme=theme)
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
        draw.polygon([(0, 0), (int(width * 0.72), 0), (int(width * 0.56), height), (0, height)], fill=surface_alt)
        top_strip = max(16, height // 42)
        bottom_strip = max(18, height // 36)
        draw.rectangle((0, 0, width, top_strip), fill=primary)
        draw.rectangle((0, height - bottom_strip, width, height), fill=secondary)

        content = draft.get("content", {}) if isinstance(draft.get("content"), Mapping) else {}
        home = draft.get("home", {}) if isinstance(draft.get("home"), Mapping) else {}
        visitor = draft.get("visitor", {}) if isinstance(draft.get("visitor"), Mapping) else {}
        player = draft.get("player", {}) if isinstance(draft.get("player"), Mapping) else {}
        sponsor = draft.get("sponsor", {}) if isinstance(draft.get("sponsor"), Mapping) else {}
        org = draft.get("organization", {}) if isinstance(draft.get("organization"), Mapping) else {}
        sponsor_visible = bool(sponsor and not draft.get("sponsor_suppressed", False) and self._safe(sponsor.get("name")))

        margin = int(width * 0.055)
        sponsor_layout_requested = "banner" if self._safe(sponsor.get("layout")).lower() == "banner" else "standard"
        sponsor_bar_h = (max(92, height // 6) if sponsor_layout_requested == "banner" else max(168, int(height * 0.26))) if sponsor_visible else 0
        sponsor_y = height - bottom_strip - sponsor_bar_h
        body_bottom = sponsor_y if sponsor_visible else height - bottom_strip

        headshot_rendered = False
        player_width = int(width * 0.285) if player.get("headshot") else 0
        if player_width:
            headshot_top = top_strip + max(28, height // 24)
            headshot_bottom = body_bottom - max(22, height // 32)
            headshot_size = (player_width - 28, max(120, headshot_bottom - headshot_top))
            headshot = self._image(player.get("headshot"), headshot_size)
            if headshot is not None:
                image.paste(headshot.convert("RGB"), (margin, headshot_top))
                draw.rectangle(
                    (margin, headshot_top, margin + headshot_size[0], headshot_top + headshot_size[1]),
                    outline=accent,
                    width=max(2, width // 500),
                )
                headshot_rendered = True
            else:
                player_width = 0

        copy_left = margin + player_width
        copy_width = width - copy_left - margin
        warnings: list[str] = []

        eyebrow = self._safe(content.get("eyebrow"), self._safe(draft.get("kind"), "GAME UPDATE")).upper()
        headline = self._safe(content.get("headline"), "GAME UPDATE").upper()
        detail = self._safe(content.get("detail"), self._safe(draft.get("description")))
        score = self._safe(content.get("score"))

        org_name = self._safe(org.get("short_name"), self._safe(org.get("name"), "CSRN"))
        draw.text(
            (width - margin, top_strip + max(14, height // 70)),
            org_name,
            anchor="ra",
            font=self._font(max(22, width // 50), bold=True),
            fill=accent,
        )

        y = top_strip + max(34, height // 17)
        eyebrow_font = self._fit_text(draw, eyebrow, copy_width, max(25, width // 42), max(18, width // 64))
        draw.text((copy_left, y), eyebrow, font=eyebrow_font, fill=primary)
        y += self._line_height(draw, eyebrow_font) + max(10, height // 80)

        headline_font, headline_lines, headline_truncated = self._fit_wrapped(
            draw,
            headline,
            max_width=copy_width,
            max_height=max(80, int(height * 0.18)),
            start_size=max(54, width // 14),
            minimum=max(30, width // 34),
            max_lines=2,
            bold=True,
        )
        if headline_truncated:
            warnings.append("headline_truncated")
        y = self._draw_lines(draw, (copy_left, y), headline_lines, font=headline_font, fill=text_color, spacing=max(2, height // 180))
        y += max(8, height // 75)

        score_lines: list[str] = []
        if score:
            single_font = self._fit_text(
                draw,
                score,
                copy_width,
                max(58, width // 15),
                max(30, width // 36),
            )
            if self._text_width(draw, score, single_font) <= copy_width:
                score_font = single_font
                score_lines = [score]
            else:
                parts = [part.strip() for part in score.split("·") if part.strip()]
                candidate_lines = parts if len(parts) == 2 else self._wrap(draw, score, self._font(max(30, width // 36), bold=True), copy_width)
                combined = "\n".join(candidate_lines)
                score_font, score_lines, score_truncated = self._fit_wrapped(
                    draw,
                    combined.replace("\n", " "),
                    max_width=copy_width,
                    max_height=max(80, int(height * 0.17)),
                    start_size=max(50, width // 18),
                    minimum=max(28, width // 42),
                    max_lines=2,
                    bold=True,
                )
                if len(parts) == 2:
                    score_lines = parts
                    while any(self._text_width(draw, line, score_font) > copy_width for line in score_lines):
                        current_size = getattr(score_font, "size", max(28, width // 42))
                        if current_size <= max(28, width // 42):
                            break
                        score_font = self._font(current_size - 2, bold=True)
                if score_truncated:
                    warnings.append("score_truncated")
            y = self._draw_lines(draw, (copy_left, y), score_lines, font=score_font, fill=accent, spacing=max(2, height // 150))
            y += max(12, height // 60)

        team_line = f"{self._safe(home.get('name'), 'HOME')} vs {self._safe(visitor.get('name'), 'VISITOR')}"
        team_font, team_lines, team_truncated = self._fit_wrapped(
            draw,
            team_line,
            max_width=copy_width,
            max_height=max(54, int(height * 0.10)),
            start_size=max(26, width // 38),
            minimum=max(24, width // 52),
            max_lines=2,
            bold=True,
        )
        if team_truncated:
            warnings.append("team_line_truncated")
        y = self._draw_lines(draw, (copy_left, y), team_lines, font=team_font, fill=muted, spacing=max(2, height // 180))
        y += max(8, height // 80)

        logo_size = max(58, width // 13)
        logo_area_h = logo_size + max(16, height // 45)
        detail_bottom = body_bottom - logo_area_h
        detail_height = max(40, detail_bottom - y)
        detail_lines: list[str] = []
        if detail:
            detail_font, detail_lines, detail_truncated = self._fit_wrapped(
                draw,
                detail,
                max_width=copy_width,
                max_height=detail_height,
                start_size=max(28, width // 34),
                minimum=max(24, width // 52),
                max_lines=3,
                bold=False,
            )
            if detail_truncated:
                warnings.append("detail_truncated")
            self._draw_lines(draw, (copy_left, y), detail_lines, font=detail_font, fill=text_color, spacing=max(3, height // 150))

        featured = draft.get("featured_team", {}) if isinstance(draft.get("featured_team"), Mapping) else {}
        featured_logo = self._image(featured.get("logo"), (logo_size, logo_size), contain=True)
        logo_y = body_bottom - logo_size - max(12, height // 55)
        logo_x = copy_left
        if featured_logo is not None:
            image.paste(featured_logo, (logo_x, logo_y), featured_logo)

        sponsor_rendered = False
        sponsor_layout = "none"
        if sponsor_visible:
            sponsor_rendered, sponsor_layout, sponsor_warnings = self._draw_sponsor_footer(
                image,
                draw,
                sponsor=sponsor,
                sponsor_y=sponsor_y,
                sponsor_bar_h=sponsor_bar_h,
                width=width,
                height=height,
                margin=margin,
                primary=primary,
                secondary=secondary,
                text_color=text_color,
                muted=muted,
            )
            warnings.extend(sponsor_warnings)

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
            "layout": {
                "headline_lines": headline_lines,
                "score_lines": score_lines,
                "team_lines": team_lines,
                "detail_lines": detail_lines,
                "headshot_rendered": headshot_rendered,
                "sponsor_rendered": sponsor_rendered,
                "sponsor_layout": sponsor_layout,
                "minimum_mobile_font": min(
                    getattr(headline_font, "size", 30),
                    getattr(team_font, "size", 24),
                    getattr(detail_font, "size", 24) if detail else 24,
                ),
                "warnings": warnings,
            },
        }
