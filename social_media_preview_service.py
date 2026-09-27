from __future__ import annotations

import base64
import html
import io
import mimetypes
import random
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping

from PIL import Image, ImageChops, ImageFilter
from playwright.sync_api import sync_playwright


Record = dict[str, Any]
ObjectLoader = Callable[[], list[Record]]
StateLoader = Callable[[], dict[str, Any]]
MappingLoader = Callable[[], Mapping[str, Any]]
SchoolLogoResolver = Callable[[str, str], Path]

MAX_SPONSOR_LOGOS = 6  # keeps each chip legible in a single row on a 1080px-wide card
MAX_HIGHLIGHTS = 5
MAX_STORYLINES = 5


@dataclass(frozen=True)
class SocialMediaPreviewResult:
    code: str
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.code == "OK"


class SocialMediaPreviewService:
    """Render a themed social-media matchup/highlight graphic for a broadcast.

    Mirrors BroadcasterPrintService's approach: build a self-contained HTML
    document (team logos embedded as data URIs, no external network
    dependency) and rasterize it with the same bundled headless Chromium
    (Playwright) already used for the broadcaster print sheet, so this adds
    no new runtime dependency to the packaged desktop build.

    The visual style is driven by whichever GraphicsThemeService preset is
    currently active (colors, font, panel opacity, radius) rather than a
    hard-coded look, so the image tracks "whichever theme is selected" -- the
    Collegiate Tech preset in particular resolves to the dark glass panel
    look used on the live broadcast overlay.
    """

    WIDTH = 1080
    HEIGHT = 1080

    # Reused from the live Collegiate Tech "clash stage" (see
    # csrn-broadcast-layout-engine.css .bl-college-stage-field) so the promo
    # graphic's stadium art matches what viewers already see on the overlay.
    SPORT_BACKGROUNDS = {
        "football": "football-field-background.png",
        "basketball": "basketball-court-background.png",
        "baseball": "baseball-ballpark-background.png",
        "softball": "softball-ballpark-background.png",
    }

    def __init__(
        self,
        *,
        load_broadcasts: ObjectLoader,
        load_state: StateLoader,
        load_final_state_archive: Callable[[str], dict[str, Any] | None],
        get_school_logo_file: SchoolLogoResolver,
        get_asset_upload_dir: Callable[[], Path],
        get_sponsor_service: Callable[[], Any],
        get_theme_service: Callable[[], Any],
        build_statistics: Callable[[dict[str, Any]], dict[str, Any]],
        load_config: MappingLoader,
        get_storylines: Callable[[str], list[str]],
        get_static_dir: Callable[[], Path],
        output_dir: Path,
        rng: random.Random | None = None,
    ) -> None:
        self._load_broadcasts = load_broadcasts
        self._load_state = load_state
        self._load_final_state_archive = load_final_state_archive
        self._get_school_logo_file = get_school_logo_file
        self._get_asset_upload_dir = get_asset_upload_dir
        self._get_sponsor_service = get_sponsor_service
        self._get_theme_service = get_theme_service
        self._build_statistics = build_statistics
        self._load_config = load_config
        self._get_storylines = get_storylines
        self._get_static_dir = get_static_dir
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._rng = rng or random.Random()
        self._background_cache: dict[str, str] = {}

    # -- lookups -----------------------------------------------------

    def _find_broadcast(self, broadcast_id: str) -> Record | None:
        target = str(broadcast_id or "").strip()
        return next(
            (
                item
                for item in self._load_broadcasts()
                if str(item.get("broadcast_id", "")) == target
                and not item.get("archived")
            ),
            None,
        )

    def _resolve_game_state(self, broadcast: Mapping[str, Any]) -> dict[str, Any]:
        broadcast_id = str(broadcast.get("broadcast_id", ""))
        try:
            live = self._load_state()
        except Exception:
            live = {}
        if isinstance(live, dict) and str(live.get("broadcast_id", "")) == broadcast_id:
            return live
        live_mirror = broadcast.get("live_state")
        if isinstance(live_mirror, dict) and (live_mirror.get("events") or live_mirror.get("plays")):
            return live_mirror
        try:
            archive = self._load_final_state_archive(broadcast_id)
        except Exception:
            archive = None
        if isinstance(archive, dict):
            return archive
        return live_mirror if isinstance(live_mirror, dict) else {}

    # -- image helpers -------------------------------------------------

    @staticmethod
    def _text(value: Any, fallback: str = "") -> str:
        return html.escape(str(value if value is not None else fallback).strip())

    _HEX_PATTERN = re.compile(r"#[0-9A-Fa-f]{6}")

    @classmethod
    def _hex(cls, value: Any, fallback: str) -> str:
        candidate = str(value or "").strip()
        return candidate if cls._HEX_PATTERN.fullmatch(candidate) else fallback

    _ORDINAL_SUFFIXES = {1: "st", 2: "nd", 3: "rd"}

    @classmethod
    def _ordinal(cls, day: int) -> str:
        if 10 <= day % 100 <= 20:
            return f"{day}th"
        return f"{day}{cls._ORDINAL_SUFFIXES.get(day % 10, 'th')}"

    @classmethod
    def _format_kickoff(cls, *, date: Any, scheduled_start: Any, venue: Any) -> str:
        """Render kickoff info in natural language, e.g. "Friday September 11th at 7pm"."""
        date_str = str(date or "").strip()
        time_str = str(scheduled_start or "").strip()
        venue_str = str(venue or "").strip()

        formatted_date = ""
        if date_str:
            try:
                parsed_date = datetime.strptime(date_str[:10], "%Y-%m-%d")
                formatted_date = f"{parsed_date.strftime('%A')} {parsed_date.strftime('%B')} {cls._ordinal(parsed_date.day)}"
            except ValueError:
                formatted_date = date_str

        formatted_time = ""
        if time_str:
            parsed_time = None
            for fmt in ("%I:%M %p", "%I:%M%p", "%I %p", "%H:%M"):
                try:
                    parsed_time = datetime.strptime(time_str, fmt)
                    break
                except ValueError:
                    continue
            if parsed_time is not None:
                hour12 = parsed_time.hour % 12 or 12
                period = "am" if parsed_time.hour < 12 else "pm"
                formatted_time = (
                    f"{hour12}{period}" if parsed_time.minute == 0 else f"{hour12}:{parsed_time.minute:02d}{period}"
                )
            else:
                formatted_time = time_str

        if formatted_date and formatted_time:
            headline = f"{formatted_date} at {formatted_time}"
        elif formatted_date:
            headline = formatted_date
        elif formatted_time:
            headline = f"Kickoff at {formatted_time}"
        else:
            headline = ""

        pieces = [piece for piece in (headline, venue_str) if piece]
        return html.escape(" · ".join(pieces))

    @staticmethod
    def _data_uri_from_file(path: Path) -> str:
        try:
            if not path.is_file():
                return ""
            mime = mimetypes.guess_type(path.name)[0] or "image/png"
            payload = base64.b64encode(path.read_bytes()).decode("ascii")
            return f"data:{mime};base64,{payload}"
        except (OSError, ValueError):
            return ""

    def _team_logo_uri(self, identity: Any, fallback_school_id: Any) -> str:
        if not isinstance(identity, Mapping):
            identity = {}
        logo_route = str(identity.get("logo", "") or "").strip()
        if logo_route.startswith("data:"):
            # Already a self-contained data URI (e.g. the generated
            # monogram fallback from broadcast_identity()) -- pass through.
            return logo_route
        school_id = str(identity.get("school_id") or fallback_school_id or "").strip()
        filename = Path(logo_route).name if logo_route else ""
        if not school_id or not filename:
            return ""
        try:
            path = self._get_school_logo_file(school_id, filename)
        except Exception:
            return ""
        return self._data_uri_from_file(path)

    @staticmethod
    def _trim_uniform_border(image: "Image.Image") -> "Image.Image":
        """Crop a solid-color canvas down to the visible mark.

        Mirrors SocialCardRenderer's sponsor-logo handling: many sponsor
        exports are a small logo centered on a large white (or black)
        canvas, which renders illegibly small in a fixed-size chip unless
        that padding is trimmed away first.
        """
        if image.width <= 8 or image.height <= 8:
            return image
        corners = [
            image.getpixel((0, 0)),
            image.getpixel((image.width - 1, 0)),
            image.getpixel((0, image.height - 1)),
            image.getpixel((image.width - 1, image.height - 1)),
        ]
        channels = len(corners[0])
        background = tuple(sum(pixel[index] for pixel in corners) // len(corners) for index in range(channels))
        backdrop = Image.new(image.mode, image.size, background)
        difference = ImageChops.difference(image, backdrop).convert("L")
        mask = difference.point(lambda value: 255 if value > 18 else 0)
        box = mask.getbbox()
        if not box:
            return image
        left, top, right, bottom = box
        pad = max(2, int(min(image.size) * 0.03))
        return image.crop((
            max(0, left - pad), max(0, top - pad),
            min(image.width, right + pad), min(image.height, bottom + pad),
        ))

    @classmethod
    def _cropped_logo_data_uri(cls, path: Path) -> str:
        """Like _data_uri_from_file, but trims a uniform-color canvas down
        to the visible mark first (see _trim_uniform_border)."""
        try:
            if not path.is_file():
                return ""
            with Image.open(path) as source:
                image = source.convert("RGBA")
            alpha_box = image.getchannel("A").getbbox()
            if alpha_box:
                image = image.crop(alpha_box)
            image = cls._trim_uniform_border(image)
            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            payload = base64.b64encode(buffer.getvalue()).decode("ascii")
            return f"data:image/png;base64,{payload}"
        except Exception:
            return cls._data_uri_from_file(path)

    @staticmethod
    def _sample_background_color(image: "Image.Image", inset: int = 6, patch: int = 3) -> tuple:
        """Median-sample a small patch inset from each corner.

        Many real-world sponsor exports carry a 1-2px scan/print border a
        shade off from the actual background (e.g. light gray around a
        white field), so reading the bare corner pixel picks up that
        border instead of the true background. Sampling a small patch a
        few pixels in, and taking the median, is robust to that plus
        ordinary JPEG compression noise.
        """
        width, height = image.size
        corners = [
            (inset, inset), (width - 1 - inset, inset),
            (inset, height - 1 - inset), (width - 1 - inset, height - 1 - inset),
        ]
        samples = []
        for cx, cy in corners:
            for dx in range(-patch, patch + 1):
                for dy in range(-patch, patch + 1):
                    x = min(max(cx + dx, 0), width - 1)
                    y = min(max(cy + dy, 0), height - 1)
                    samples.append(image.getpixel((x, y)))
        channels = len(samples[0])
        result = []
        for index in range(channels):
            values = sorted(sample[index] for sample in samples)
            result.append(values[len(values) // 2])
        return tuple(result)

    @staticmethod
    def _chip_variant_for(image: "Image.Image") -> str:
        """Decide whether a keyed-transparent logo needs a light or dark
        glass chip behind it so its own ink stays readable: light-colored
        marks (e.g. white line art) go on a dark chip, dark ink (e.g.
        black text) goes on a light chip."""
        sample = image.copy()
        sample.thumbnail((80, 80))
        red, green, blue, alpha = sample.convert("RGBA").split()
        pixels = zip(red.getdata(), green.getdata(), blue.getdata(), alpha.getdata())
        opaque = [(r, g, b) for r, g, b, a in pixels if a > 100]
        if not opaque:
            return "dark"
        average_luminance = sum(0.299 * r + 0.587 * g + 0.114 * b for r, g, b in opaque) / len(opaque)
        return "dark" if average_luminance >= 140 else "light"

    @classmethod
    def _keyed_sponsor_logo(cls, path: Path) -> tuple[str, str]:
        """Key a sponsor logo's flat background out to transparent and
        report which glass-chip variant ("light"/"dark") keeps its ink
        readable.

        Most sponsor exports are a small mark on a large solid-color
        canvas. Rather than boxing that canvas in a card (which just
        reproduces the sponsor's own white/black rectangle), this softly
        keys the background to transparent -- with a feathered threshold
        and a touch of blur to stay robust against JPEG compression noise
        -- so only the mark itself floats on the card's glass chip.
        """
        try:
            if not path.is_file():
                return "", "dark"
            with Image.open(path) as source:
                image = source.convert("RGB")
            width, height = image.size
            if width <= 16 or height <= 16:
                return cls._data_uri_from_file(path), "dark"
            shave = max(2, int(min(width, height) * 0.01))
            image = image.crop((shave, shave, width - shave, height - shave))
            background = cls._sample_background_color(image)
            backdrop = Image.new("RGB", image.size, background)
            distance = ImageChops.difference(image, backdrop).convert("L")
            low, high = 22, 60
            lookup = [
                0 if value <= low else 255 if value >= high else int(255 * (value - low) / (high - low))
                for value in range(256)
            ]
            alpha = distance.point(lookup).filter(ImageFilter.GaussianBlur(1.0))
            rgba = image.convert("RGBA")
            rgba.putalpha(alpha)
            box = alpha.getbbox()
            if box:
                pad = max(4, int(min(rgba.size) * 0.03))
                left, top, right, bottom = box
                rgba = rgba.crop((
                    max(0, left - pad), max(0, top - pad),
                    min(rgba.width, right + pad), min(rgba.height, bottom + pad),
                ))
            variant = cls._chip_variant_for(rgba)
            buffer = io.BytesIO()
            rgba.save(buffer, format="PNG")
            payload = base64.b64encode(buffer.getvalue()).decode("ascii")
            return f"data:image/png;base64,{payload}", variant
        except Exception:
            return cls._data_uri_from_file(path), "dark"

    def _sponsor_logo_uri(self, sponsor: Mapping[str, Any]) -> tuple[str, str]:
        logo_url = str(sponsor.get("logo_url", "") or "").strip()
        if not logo_url:
            return "", "dark"
        if logo_url.startswith("data:"):
            return logo_url, "dark"
        if logo_url.startswith("/asset-files/"):
            filename = logo_url[len("/asset-files/"):]
            if filename and Path(filename).name == filename:
                return self._keyed_sponsor_logo(self._get_asset_upload_dir() / filename)
            return "", "dark"
        # External/absolute URLs are intentionally not fetched here -- the
        # rendered card must not depend on network access being available
        # mid-broadcast. Such sponsors still appear via the text fallback.
        return "", "dark"

    def _select_sponsors(self) -> list[dict[str, Any]]:
        try:
            sponsors = self._get_sponsor_service().list_payload().get("sponsors", [])
        except Exception:
            sponsors = []
        active = [
            sponsor
            for sponsor in sponsors
            if sponsor.get("active", True)
            and sponsor.get("effective_status") != "Expired"
            and str(sponsor.get("name", "")).strip()
        ]
        if len(active) > MAX_SPONSOR_LOGOS:
            return self._rng.sample(active, MAX_SPONSOR_LOGOS)
        return active

    def _recent_scoring_plays(self, state: Mapping[str, Any]) -> list[dict[str, Any]]:
        if not state:
            return []
        try:
            statistics = self._build_statistics(dict(state))
        except Exception:
            return []
        scoring = list(statistics.get("scoring_summary") or [])
        return scoring[-MAX_HIGHLIGHTS:]

    def _storylines(self, broadcast_id: str) -> list[str]:
        try:
            lines = self._get_storylines(broadcast_id) or []
        except Exception:
            return []
        return [str(line).strip() for line in lines if str(line).strip()][:MAX_STORYLINES]

    def _org_logo_uri(self, organization: Mapping[str, Any]) -> str:
        logo_path = str(organization.get("logo") or "").strip() or "/static/csrn-logo.png"
        if logo_path.startswith("data:"):
            return logo_path
        try:
            if logo_path.startswith("/static/"):
                return self._data_uri_from_file(self._get_static_dir() / logo_path[len("/static/"):])
            return self._data_uri_from_file(self._get_static_dir() / "csrn-logo.png")
        except Exception:
            return ""

    def _background_uri(self, sport: str) -> str:
        key = self.SPORT_BACKGROUNDS.get(str(sport or "").strip().lower(), self.SPORT_BACKGROUNDS["football"])
        if key in self._background_cache:
            return self._background_cache[key]
        try:
            path = self._get_static_dir() / "friday-night-stadium" / "clash" / key
            uri = self._data_uri_from_file(path)
        except Exception:
            uri = ""
        self._background_cache[key] = uri
        return uri

    def _theme_tokens(self) -> dict[str, Any]:
        try:
            theme = self._get_theme_service().status().data["theme"]["active"]
        except Exception:
            theme = {}
        tokens = dict(theme.get("tokens", {})) if isinstance(theme, Mapping) else {}
        return {
            "name": theme.get("name", "Modern Network") if isinstance(theme, Mapping) else "Modern Network",
            "primary": tokens.get("primary_color", "#C9203B"),
            "secondary": tokens.get("secondary_color", "#111111"),
            "accent": tokens.get("accent_color", "#FFFFFF"),
            "surface": tokens.get("surface", "#101318"),
            "surface_alt": tokens.get("surface_alt", "#242A33"),
            "text": tokens.get("text", "#FFFFFF"),
            "muted": tokens.get("muted", "#C8D0DB"),
            "border": tokens.get("border", "#BFC9D4"),
            "font_stack": tokens.get(
                "font_stack",
                '"Segoe UI", Arial, sans-serif',
            ),
            "radius_px": int(tokens.get("radius_px", 8)),
            "panel_opacity": float(tokens.get("panel_opacity", 0.94)),
            "shadow": tokens.get("shadow", "0 18px 38px rgba(0,0,0,.5)"),
        }

    # -- rendering -------------------------------------------------------

    def _stage_side_html(self, *, name: str, mascot: str, logo_uri: str, align: str) -> str:
        monogram = self._text(name)[:1].upper() or "?"
        logo_html = (
            f'<img src="{logo_uri}" alt="">'
            if logo_uri
            else f'<span class="stage-logo-fallback">{monogram}</span>'
        )
        mascot_html = f'<span class="stage-mascot">{self._text(mascot)}</span>' if mascot else ""
        return (
            f'<div class="stage-side stage-side-{align}">'
            f'<div class="stage-logo">{logo_html}</div>'
            f'<strong class="stage-name">{self._text(name, "TEAM")}</strong>'
            f'{mascot_html}'
            f'</div>'
        )

    def _live_stream_badge_html(self, *, streaming: Mapping[str, Any], org_name: str) -> str:
        icons = []
        if str(streaming.get("youtube_live", "") or "").strip():
            icons.append('<span class="platform-icon platform-youtube" aria-hidden="true">&#9654;</span>')
        if str(streaming.get("facebook_live", "") or "").strip():
            icons.append('<span class="platform-icon platform-facebook" aria-hidden="true">f</span>')
        icon_html = "".join(icons)
        return f'<div class="stage-live-badge">{icon_html}<span>LIVE STREAM</span></div>'

    def _storylines_html(self, storylines: list[str]) -> str:
        if not storylines:
            return ""
        items = "".join(f'<li>{self._text(line)}</li>' for line in storylines)
        return f'<div class="storylines"><div class="storylines-title">Game Preview</div><ul>{items}</ul></div>'

    def _score_line_html(self, *, status: str, visitor_name: str, home_name: str, visitor_score: Any, home_score: Any) -> str:
        if status not in {"live", "completed"}:
            return ""
        return (
            '<div class="score-line">'
            f'<span>{self._text(visitor_name)} {self._text(visitor_score, "0")}</span>'
            '<span class="score-line-sep">–</span>'
            f'<span>{self._text(home_name)} {self._text(home_score, "0")}</span>'
            '</div>'
        )

    def _sponsors_html(self, sponsors: list[dict[str, Any]]) -> str:
        if not sponsors:
            return ""
        chips = []
        for sponsor in sponsors:
            uri, variant = self._sponsor_logo_uri(sponsor)
            if uri:
                chips.append(
                    f'<div class="sponsor-chip chip-{variant}">'
                    f'<img src="{uri}" alt="{self._text(sponsor.get("name"))}"></div>'
                )
            else:
                chips.append(f'<div class="sponsor-chip chip-dark sponsor-chip-text">{self._text(sponsor.get("name"))}</div>')
        return (
            '<div class="sponsors"><div class="sponsors-title">Thanks to the following sponsors</div>'
            f'<div class="sponsors-grid">{"".join(chips)}</div></div>'
        )

    def _render_document(
        self,
        *,
        broadcast: Mapping[str, Any],
        state: Mapping[str, Any],
        theme: Mapping[str, Any],
        storylines: list[str],
        sponsors: list[dict[str, Any]],
    ) -> str:
        home_identity = broadcast.get("home_identity") if isinstance(broadcast.get("home_identity"), Mapping) else {}
        visitor_identity = broadcast.get("visitor_identity") if isinstance(broadcast.get("visitor_identity"), Mapping) else {}

        home_name = broadcast.get("home_team") or "Home"
        visitor_name = broadcast.get("visitor_team") or "Visitor"
        home_score = state.get("home_score", broadcast.get("home_score", 0)) if state else broadcast.get("home_score", 0)
        visitor_score = state.get("visitor_score", broadcast.get("visitor_score", 0)) if state else broadcast.get("visitor_score", 0)

        status = str(broadcast.get("status", "planned")).lower()

        organization = {}
        streaming = {}
        try:
            config = self._load_config() or {}
            organization = dict(config.get("organization") or {})
            streaming = dict(config.get("streaming") or {})
        except Exception:
            pass
        org_name = self._text(organization.get("short_name") or organization.get("name") or "CSRN")
        org_logo_uri = self._org_logo_uri(organization)

        kickoff_line = self._format_kickoff(
            date=broadcast.get("date"),
            scheduled_start=broadcast.get("scheduled_start"),
            venue=broadcast.get("venue"),
        )

        home_side = self._stage_side_html(
            name=home_name,
            mascot=home_identity.get("mascot", ""),
            logo_uri=self._team_logo_uri(home_identity, broadcast.get("home_school_id")),
            align="home",
        )
        visitor_side = self._stage_side_html(
            name=visitor_name,
            mascot=visitor_identity.get("mascot", ""),
            logo_uri=self._team_logo_uri(visitor_identity, broadcast.get("visitor_school_id")),
            align="visitor",
        )

        visitor_primary = self._hex(visitor_identity.get("primary_color"), "#064624")
        home_primary = self._hex(home_identity.get("primary_color"), "#0A2342")
        background_uri = self._background_uri(broadcast.get("sport", "football"))
        background_layer = (
            f"linear-gradient(90deg, {visitor_primary}66, transparent 44% 56%, {home_primary}66),"
            f"url('{background_uri}') center 58%/cover no-repeat"
            if background_uri
            else f"linear-gradient(90deg, {visitor_primary}, {home_primary})"
        )

        score_line = self._score_line_html(
            status=status, visitor_name=visitor_name, home_name=home_name,
            visitor_score=visitor_score, home_score=home_score,
        )

        return f"""<!doctype html>
<html><head><meta charset="utf-8">
<style>
  :root {{
    --primary: {theme['primary']};
    --secondary: {theme['secondary']};
    --accent: {theme['accent']};
    --surface: {theme['surface']};
    --surface-alt: {theme['surface_alt']};
    --text: {theme['text']};
    --muted: {theme['muted']};
    --border: {theme['border']};
    --radius: {theme['radius_px'] * 2}px;
    --shadow: {theme['shadow']};
    --font: {theme['font_stack']};
  }}
  * {{ box-sizing: border-box; }}
  html, body {{ margin: 0; padding: 0; }}
  body {{
    width: {self.WIDTH}px; height: {self.HEIGHT}px; overflow: hidden;
    font-family: var(--font); color: var(--text);
    background: linear-gradient(155deg, var(--surface) 0%, var(--surface-alt) 100%);
    display: flex; flex-direction: column; padding: 48px;
  }}
  .stage {{
    position: relative; flex: 0 0 420px; display: grid;
    grid-template-columns: minmax(0,1fr) 170px minmax(0,1fr); align-items: center;
    border: 1px solid var(--border); border-radius: var(--radius); overflow: hidden;
    box-shadow: var(--shadow); margin-bottom: 16px;
  }}
  .stage-field {{ position: absolute; inset: 0; background: {background_layer}; opacity: .78; filter: saturate(.85) brightness(.68); }}
  .stage::after {{ content: ""; position: absolute; inset: 0; background: linear-gradient(180deg, rgba(255,255,255,.14), transparent 25% 75%, rgba(0,0,0,.25)); pointer-events: none; }}
  .stage-live-badge {{
    position: absolute; top: 14px; left: 12px; right: 12px; z-index: 4;
    display: flex; align-items: center; justify-content: center; gap: 8px;
    color: #fff; font-size: 22px; font-weight: 900; letter-spacing: .1em;
    text-shadow: 0 2px 8px rgba(0,0,0,.85);
  }}
  .platform-icon {{
    display: inline-grid; place-items: center; width: 26px; height: 26px; border-radius: 50%;
    background: rgba(255,255,255,.16); border: 1px solid rgba(255,255,255,.5);
    font-size: 13px; font-weight: 900; line-height: 1;
  }}
  .platform-youtube {{ color: #FF3B30; }}
  .platform-facebook {{ color: #6E9BFF; font-family: Georgia, "Times New Roman", serif; }}
  .stage-side {{
    position: relative; z-index: 2; display: grid; justify-items: center; gap: 8px;
    padding: 48px 20px 24px; text-align: center; text-transform: uppercase; color: #fff; text-shadow: 0 3px 10px rgba(0,0,0,.7);
  }}
  .stage-logo {{ width: 168px; height: 168px; border-radius: 18px; background: rgba(0,0,0,.28); border: 1px solid rgba(255,255,255,.3); display: grid; place-items: center; overflow: hidden; }}
  .stage-logo img {{ width: 84%; height: 84%; object-fit: contain; }}
  .stage-logo-fallback {{ font-size: 72px; font-weight: 950; color: #fff; }}
  .stage-name {{ font-size: 40px; font-weight: 950; line-height: 1.05; max-width: 100%; white-space: nowrap; }}
  .stage-mascot {{ font-size: 22px; font-weight: 800; letter-spacing: .1em; color: #e3edf9; }}
  .stage-vs {{
    position: relative; z-index: 3; justify-self: center; display: grid; place-items: center;
    width: 140px; height: 140px; border-radius: 50%; border: 1px solid rgba(255,255,255,.45);
    background: rgba(4,12,20,.6); box-shadow: 0 0 26px rgba(180,220,255,.25), inset 0 1px 0 rgba(255,255,255,.28);
    font-size: 44px; font-weight: 950; color: #fff; overflow: hidden;
  }}
  .stage-vs img {{ width: 100%; height: 100%; object-fit: cover; }}
  .kickoff-line {{ text-align: center; color: var(--text); font-size: 28px; font-weight: 800; margin: 0 0 10px; }}
  .score-line {{ text-align: center; color: var(--accent); font-size: 32px; font-weight: 900; margin-bottom: 8px; }}
  .score-line-sep {{ margin: 0 14px; color: var(--muted); }}
  .storylines {{
    background: rgba(0,0,0,.22); border: 1px solid var(--border); border-radius: var(--radius);
    padding: 14px 26px; margin-bottom: 16px; max-height: 280px; overflow: hidden; flex: 0 0 auto;
  }}
  .storylines-title {{ font-size: 18px; font-weight: 900; letter-spacing: .1em; color: var(--primary); margin-bottom: 6px; text-transform: uppercase; }}
  .storylines ul {{ list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 5px; }}
  .storylines li {{ font-size: 20px; line-height: 1.25; color: var(--text); }}
  .flex-spacer {{ flex: 1 1 auto; min-height: 0; }}
  .sponsors {{ flex: 0 0 auto; }}
  .sponsors-title {{ text-align: center; font-size: 20px; color: var(--muted); letter-spacing: .12em; text-transform: uppercase; margin-bottom: 12px; }}
  .sponsors-grid {{ display: flex; flex-wrap: nowrap; gap: 16px; justify-content: center; align-items: stretch; }}
  .sponsor-chip {{
    position: relative; border-radius: 20px; padding: 14px 18px;
    -webkit-backdrop-filter: blur(10px); backdrop-filter: blur(10px);
    display: flex; align-items: center; justify-content: center; overflow: hidden;
    flex: 1 1 0; min-width: 150px; max-width: 280px; height: 190px;
  }}
  /* Sponsor logos are keyed transparent so only the mark shows (see
     _keyed_sponsor_logo) -- the chip picks a light or dark glass tint,
     per logo, so that mark stays readable either way. */
  .sponsor-chip.chip-dark {{
    background: rgba(255,255,255,.08); border: 1px solid rgba(255,255,255,.22);
    box-shadow: 0 10px 26px rgba(0,0,0,.4), inset 0 1px 0 rgba(255,255,255,.12);
  }}
  .sponsor-chip.chip-dark img {{ filter: drop-shadow(0 2px 6px rgba(0,0,0,.5)); }}
  .sponsor-chip.chip-light {{
    background: rgba(255,255,255,.85); border: 1px solid rgba(255,255,255,.7);
    box-shadow: 0 10px 26px rgba(0,0,0,.35), inset 0 1px 0 rgba(255,255,255,.6);
  }}
  .sponsor-chip img {{ position: relative; z-index: 1; max-width: 100%; max-height: 100%; object-fit: contain; }}
  .sponsor-chip-text {{
    color: var(--text); font-weight: 700; font-size: 22px; text-align: center;
  }}
</style></head>
<body>
  <div class="stage">
    <div class="stage-field"></div>
    {self._live_stream_badge_html(streaming=streaming, org_name=org_name)}
    {visitor_side}
    <div class="stage-vs">{f'<img src="{org_logo_uri}" alt="{org_name}">' if org_logo_uri else "VS"}</div>
    {home_side}
  </div>
  <div class="kickoff-line">{kickoff_line}</div>
  {score_line}
  {self._storylines_html(storylines)}
  <div class="flex-spacer"></div>
  {self._sponsors_html(sponsors)}
  <script>
  (function() {{
    var minFont = 22;
    document.querySelectorAll('.stage-name').forEach(function(el) {{
      var container = el.closest('.stage-side');
      if (!container) return;
      var maxWidth = container.clientWidth - 8;
      var fontSize = parseFloat(window.getComputedStyle(el).fontSize);
      while (el.scrollWidth > maxWidth && fontSize > minFont) {{
        fontSize -= 2;
        el.style.fontSize = fontSize + 'px';
      }}
      if (el.scrollWidth > maxWidth) {{
        el.style.whiteSpace = 'normal';
        el.style.fontSize = minFont + 'px';
      }}
    }});
  }})();
  </script>
</body></html>"""

    # -- public API --------------------------------------------------

    def generate(self, broadcast_id: str) -> SocialMediaPreviewResult:
        broadcast = self._find_broadcast(broadcast_id)
        if broadcast is None:
            return SocialMediaPreviewResult("BROADCAST_NOT_FOUND")

        state = self._resolve_game_state(broadcast)
        theme = self._theme_tokens()
        storylines = self._storylines(broadcast_id)
        sponsors = self._select_sponsors()

        document = self._render_document(
            broadcast=broadcast,
            state=state,
            theme=theme,
            storylines=storylines,
            sponsors=sponsors,
        )

        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                try:
                    page = browser.new_page(viewport={"width": self.WIDTH, "height": self.HEIGHT})
                    page.set_content(document, wait_until="load")
                    image_bytes = page.screenshot(type="png")
                finally:
                    browser.close()
        except Exception as exc:
            return SocialMediaPreviewResult(
                "IMAGE_GENERATION_FAILED",
                {"message": str(exc)},
            )

        safe_id = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(broadcast_id)).strip("-") or "broadcast"
        filename = f"{safe_id}-social-preview.png"
        try:
            (self.output_dir / filename).write_bytes(image_bytes)
        except OSError:
            pass

        return SocialMediaPreviewResult(
            "OK",
            {
                "image": image_bytes,
                "filename": filename,
                "theme_id": theme.get("name", ""),
                "sponsor_count": len(sponsors),
                "storyline_count": len(storylines),
            },
        )

    # -- final score graphic -----------------------------------------------

    @staticmethod
    def _final_record_text(record: Any) -> str:
        """Formats a *_postgame_record value (either the flat {wins,losses,ties} shape
        normalize_record()/_record_dict() use elsewhere, or that same dict nested one level
        under "overall", the shape broadcast_service.py stores it in) as "W-L", or "W-L-T"
        only when there actually is a tie -- ties are rare enough that always showing a
        trailing "-0" would read as a typo rather than a real 3-number record."""
        if not isinstance(record, Mapping):
            return ""
        overall = record.get("overall") if isinstance(record.get("overall"), Mapping) else record
        try:
            wins = max(0, int(overall.get("wins", 0) or 0))
            losses = max(0, int(overall.get("losses", 0) or 0))
            ties = max(0, int(overall.get("ties", 0) or 0))
        except (TypeError, ValueError):
            return ""
        if wins == 0 and losses == 0 and ties == 0:
            return ""
        return f"{wins}-{losses}-{ties}" if ties else f"{wins}-{losses}"

    def _final_score_banner_html(
        self, *, visitor_name: str, home_name: str, visitor_score: int, home_score: int,
    ) -> str:
        # The winner's name gets the accent treatment; a tie leaves both sides equal
        # weight rather than guessing a "winner". Order stays visitor-then-home,
        # matching every other scoreboard in the product (the live overlay, the
        # pregame graphic's own score-line).
        visitor_win = visitor_score > home_score
        home_win = home_score > visitor_score
        return (
            '<div class="final-banner">'
            f'<span class="final-tag">FINAL</span>'
            '<div class="final-score-row">'
            f'<span class="final-team{" final-winner" if visitor_win else ""}">{self._text(visitor_name)}</span>'
            f'<span class="final-score{" final-winner" if visitor_win else ""}">{self._text(visitor_score, "0")}</span>'
            '<span class="final-score-dash">–</span>'
            f'<span class="final-score{" final-winner" if home_win else ""}">{self._text(home_score, "0")}</span>'
            f'<span class="final-team{" final-winner" if home_win else ""}">{self._text(home_name)}</span>'
            '</div></div>'
        )

    def _final_records_html(self, *, visitor_record: str, home_record: str) -> str:
        if not visitor_record and not home_record:
            return ""
        return (
            '<div class="final-records">'
            f'<span>{self._text(visitor_record, "—")}</span>'
            '<span class="final-records-sep">FINAL RECORD</span>'
            f'<span>{self._text(home_record, "—")}</span>'
            '</div>'
        )

    def _render_final_score_document(
        self,
        *,
        broadcast: Mapping[str, Any],
        state: Mapping[str, Any],
        theme: Mapping[str, Any],
        sponsors: list[dict[str, Any]],
    ) -> str:
        home_identity = broadcast.get("home_identity") if isinstance(broadcast.get("home_identity"), Mapping) else {}
        visitor_identity = broadcast.get("visitor_identity") if isinstance(broadcast.get("visitor_identity"), Mapping) else {}

        home_name = broadcast.get("home_team") or "Home"
        visitor_name = broadcast.get("visitor_team") or "Visitor"
        # Prefer the frozen final_*_score fields (written once at game completion) over the
        # generic, possibly-still-live home_score/visitor_score -- this graphic's whole job is
        # to be the correct, final number, not whatever the in-progress score last was.
        home_score = broadcast.get("final_home_score")
        if home_score is None:
            home_score = state.get("home_score", broadcast.get("home_score", 0)) if state else broadcast.get("home_score", 0)
        visitor_score = broadcast.get("final_visitor_score")
        if visitor_score is None:
            visitor_score = state.get("visitor_score", broadcast.get("visitor_score", 0)) if state else broadcast.get("visitor_score", 0)
        try:
            home_score = int(home_score or 0)
            visitor_score = int(visitor_score or 0)
        except (TypeError, ValueError):
            home_score, visitor_score = 0, 0

        organization = {}
        try:
            config = self._load_config() or {}
            organization = dict(config.get("organization") or {})
        except Exception:
            pass
        org_name = self._text(organization.get("short_name") or organization.get("name") or "CSRN")
        org_logo_uri = self._org_logo_uri(organization)

        home_side = self._stage_side_html(
            name=home_name,
            mascot=home_identity.get("mascot", ""),
            logo_uri=self._team_logo_uri(home_identity, broadcast.get("home_school_id")),
            align="home",
        )
        visitor_side = self._stage_side_html(
            name=visitor_name,
            mascot=visitor_identity.get("mascot", ""),
            logo_uri=self._team_logo_uri(visitor_identity, broadcast.get("visitor_school_id")),
            align="visitor",
        )

        visitor_primary = self._hex(visitor_identity.get("primary_color"), "#064624")
        home_primary = self._hex(home_identity.get("primary_color"), "#0A2342")
        background_uri = self._background_uri(broadcast.get("sport", "football"))
        background_layer = (
            f"linear-gradient(90deg, {visitor_primary}66, transparent 44% 56%, {home_primary}66),"
            f"url('{background_uri}') center 58%/cover no-repeat"
            if background_uri
            else f"linear-gradient(90deg, {visitor_primary}, {home_primary})"
        )

        final_banner = self._final_score_banner_html(
            visitor_name=visitor_name, home_name=home_name,
            visitor_score=visitor_score, home_score=home_score,
        )
        final_records = self._final_records_html(
            visitor_record=self._final_record_text(broadcast.get("visitor_postgame_record")),
            home_record=self._final_record_text(broadcast.get("home_postgame_record")),
        )

        return f"""<!doctype html>
<html><head><meta charset="utf-8">
<style>
  :root {{
    --primary: {theme['primary']};
    --secondary: {theme['secondary']};
    --accent: {theme['accent']};
    --surface: {theme['surface']};
    --surface-alt: {theme['surface_alt']};
    --text: {theme['text']};
    --muted: {theme['muted']};
    --border: {theme['border']};
    --radius: {theme['radius_px'] * 2}px;
    --shadow: {theme['shadow']};
    --font: {theme['font_stack']};
  }}
  * {{ box-sizing: border-box; }}
  html, body {{ margin: 0; padding: 0; }}
  body {{
    width: {self.WIDTH}px; height: {self.HEIGHT}px; overflow: hidden;
    font-family: var(--font); color: var(--text);
    background: linear-gradient(155deg, var(--surface) 0%, var(--surface-alt) 100%);
    display: flex; flex-direction: column; padding: 48px;
  }}
  /* .stage / .stage-side / .stage-logo / .sponsor* below are byte-identical to the pregame
     graphic's own rules (_render_document) -- same look, same team-art system; only the
     center badge and the content below the stage are final-score specific. */
  .stage {{
    position: relative; flex: 0 0 460px; display: grid;
    grid-template-columns: minmax(0,1fr) 170px minmax(0,1fr); align-items: center;
    border: 1px solid var(--border); border-radius: var(--radius); overflow: hidden;
    box-shadow: var(--shadow); margin-bottom: 28px;
  }}
  .stage-field {{ position: absolute; inset: 0; background: {background_layer}; opacity: .78; filter: saturate(.85) brightness(.68); }}
  .stage::after {{ content: ""; position: absolute; inset: 0; background: linear-gradient(180deg, rgba(255,255,255,.14), transparent 25% 75%, rgba(0,0,0,.25)); pointer-events: none; }}
  .stage-side {{
    position: relative; z-index: 2; display: grid; justify-items: center; gap: 8px;
    padding: 48px 20px 24px; text-align: center; text-transform: uppercase; color: #fff; text-shadow: 0 3px 10px rgba(0,0,0,.7);
  }}
  .stage-logo {{ width: 168px; height: 168px; border-radius: 18px; background: rgba(0,0,0,.28); border: 1px solid rgba(255,255,255,.3); display: grid; place-items: center; overflow: hidden; }}
  .stage-logo img {{ width: 84%; height: 84%; object-fit: contain; }}
  .stage-logo-fallback {{ font-size: 72px; font-weight: 950; color: #fff; }}
  .stage-name {{ font-size: 40px; font-weight: 950; line-height: 1.05; max-width: 100%; white-space: nowrap; }}
  .stage-mascot {{ font-size: 22px; font-weight: 800; letter-spacing: .1em; color: #e3edf9; }}
  .stage-vs {{
    position: relative; z-index: 3; justify-self: center; display: grid; place-items: center;
    width: 140px; height: 140px; border-radius: 50%; border: 1px solid rgba(255,255,255,.45);
    background: rgba(4,12,20,.6); box-shadow: 0 0 26px rgba(180,220,255,.25), inset 0 1px 0 rgba(255,255,255,.28);
    font-size: 44px; font-weight: 950; color: #fff; overflow: hidden;
  }}
  .stage-vs img {{ width: 60%; height: 60%; object-fit: contain; }}
  .final-banner {{ text-align: center; margin-bottom: 18px; }}
  .final-tag {{
    display: inline-block; padding: 6px 22px; border-radius: 999px; margin-bottom: 14px;
    background: var(--primary); color: #fff; font-size: 22px; font-weight: 950; letter-spacing: .22em;
    box-shadow: 0 8px 20px rgba(0,0,0,.35);
  }}
  .final-score-row {{ display: flex; align-items: baseline; justify-content: center; gap: 18px; }}
  .final-team {{ font-size: 30px; font-weight: 800; letter-spacing: .04em; color: var(--muted); text-transform: uppercase; }}
  .final-score {{ font-size: 92px; font-weight: 950; line-height: 1; color: var(--text); font-variant-numeric: tabular-nums; }}
  .final-score-dash {{ font-size: 48px; color: var(--muted); }}
  .final-winner.final-team {{ color: var(--text); }}
  .final-winner.final-score {{ color: var(--accent); text-shadow: 0 0 24px color-mix(in srgb, var(--accent) 55%, transparent); }}
  .final-records {{
    display: flex; align-items: center; justify-content: center; gap: 18px; margin-bottom: 20px;
    font-size: 24px; font-weight: 800; color: var(--muted);
  }}
  .final-records-sep {{ font-size: 15px; letter-spacing: .16em; text-transform: uppercase; color: var(--primary); }}
  .flex-spacer {{ flex: 1 1 auto; min-height: 0; }}
  .sponsors {{ flex: 0 0 auto; }}
  .sponsors-title {{ text-align: center; font-size: 20px; color: var(--muted); letter-spacing: .12em; text-transform: uppercase; margin-bottom: 12px; }}
  .sponsors-grid {{ display: flex; flex-wrap: nowrap; gap: 16px; justify-content: center; align-items: stretch; }}
  .sponsor-chip {{
    position: relative; border-radius: 20px; padding: 14px 18px;
    -webkit-backdrop-filter: blur(10px); backdrop-filter: blur(10px);
    display: flex; align-items: center; justify-content: center; overflow: hidden;
    flex: 1 1 0; min-width: 150px; max-width: 280px; height: 190px;
  }}
  .sponsor-chip.chip-dark {{
    background: rgba(255,255,255,.08); border: 1px solid rgba(255,255,255,.22);
    box-shadow: 0 10px 26px rgba(0,0,0,.4), inset 0 1px 0 rgba(255,255,255,.12);
  }}
  .sponsor-chip.chip-dark img {{ filter: drop-shadow(0 2px 6px rgba(0,0,0,.5)); }}
  .sponsor-chip.chip-light {{
    background: rgba(255,255,255,.85); border: 1px solid rgba(255,255,255,.7);
    box-shadow: 0 10px 26px rgba(0,0,0,.35), inset 0 1px 0 rgba(255,255,255,.6);
  }}
  .sponsor-chip img {{ position: relative; z-index: 1; max-width: 100%; max-height: 100%; object-fit: contain; }}
  .sponsor-chip-text {{
    color: var(--text); font-weight: 700; font-size: 22px; text-align: center;
  }}
</style></head>
<body>
  <div class="stage">
    <div class="stage-field"></div>
    {visitor_side}
    <div class="stage-vs">{f'<img src="{org_logo_uri}" alt="{org_name}">' if org_logo_uri else org_name}</div>
    {home_side}
  </div>
  {final_banner}
  {final_records}
  <div class="flex-spacer"></div>
  {self._sponsors_html(sponsors)}
  <script>
  (function() {{
    var minFont = 22;
    document.querySelectorAll('.stage-name').forEach(function(el) {{
      var container = el.closest('.stage-side');
      if (!container) return;
      var maxWidth = container.clientWidth - 8;
      var fontSize = parseFloat(window.getComputedStyle(el).fontSize);
      while (el.scrollWidth > maxWidth && fontSize > minFont) {{
        fontSize -= 2;
        el.style.fontSize = fontSize + 'px';
      }}
      if (el.scrollWidth > maxWidth) {{
        el.style.whiteSpace = 'normal';
        el.style.fontSize = minFont + 'px';
      }}
    }});
  }})();
  </script>
</body></html>"""

    def generate_final_score(self, broadcast_id: str) -> SocialMediaPreviewResult:
        """Same rendering system as generate() (Playwright, theme tokens, team art, sponsor
        row) -- a dedicated card for after the game instead of before it: a prominent FINAL
        score with the winner picked out, the postgame records if the broadcast has them, no
        kickoff time or pregame storylines."""
        broadcast = self._find_broadcast(broadcast_id)
        if broadcast is None:
            return SocialMediaPreviewResult("BROADCAST_NOT_FOUND")

        state = self._resolve_game_state(broadcast)
        theme = self._theme_tokens()
        sponsors = self._select_sponsors()

        document = self._render_final_score_document(
            broadcast=broadcast,
            state=state,
            theme=theme,
            sponsors=sponsors,
        )

        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                try:
                    page = browser.new_page(viewport={"width": self.WIDTH, "height": self.HEIGHT})
                    page.set_content(document, wait_until="load")
                    image_bytes = page.screenshot(type="png")
                finally:
                    browser.close()
        except Exception as exc:
            return SocialMediaPreviewResult(
                "IMAGE_GENERATION_FAILED",
                {"message": str(exc)},
            )

        safe_id = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(broadcast_id)).strip("-") or "broadcast"
        filename = f"{safe_id}-final-score.png"
        try:
            (self.output_dir / filename).write_bytes(image_bytes)
        except OSError:
            pass

        return SocialMediaPreviewResult(
            "OK",
            {
                "image": image_bytes,
                "filename": filename,
                "theme_id": theme.get("name", ""),
                "sponsor_count": len(sponsors),
            },
        )
