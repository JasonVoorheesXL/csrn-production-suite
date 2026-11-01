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

import postgame_card
import postgame_story
import pregame_story


Record = dict[str, Any]
ObjectLoader = Callable[[], list[Record]]
StateLoader = Callable[[], dict[str, Any]]
MappingLoader = Callable[[], Mapping[str, Any]]
SchoolLogoResolver = Callable[[str, str], Path]

MAX_SPONSOR_LOGOS = 6  # keeps each chip legible in a single row on a 1080px-wide card
MAX_HIGHLIGHTS = 5
MAX_STORYLINES = 5

AI_FALLBACK_MESSAGES = {
    "AI_NOT_CONFIGURED": "No Anthropic API key is saved, so the app wrote this one itself.",
    "AI_KEY_INVALID": "Anthropic did not accept the saved API key, so the app wrote this one itself. Check the key in AI writer settings.",
    "AI_UNREACHABLE": "The AI writer could not be reached (check the internet connection), so the app wrote this one itself.",
    "AI_BUSY": "The AI writer is busy right now, so the app wrote this one itself. Try again in a minute.",
    "AI_NO_CREDIT": "Your Anthropic credit is used up, so the app wrote this one itself. Add credit at console.anthropic.com under Billing, then try again.",
    "AI_REFUSED": "The AI writer declined this one, so the app wrote it itself.",
    "AI_EMPTY": "The AI writer came back empty, so the app wrote this one itself.",
    "AI_UNAVAILABLE": "The AI writer is not installed in this copy of the app, so the app wrote this one itself.",
    "AI_FAILED": "The AI writer ran into a problem, so the app wrote this one itself.",
}


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
        load_live_state: Callable[[str], dict[str, Any] | None] | None = None,
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
        load_rosters: ObjectLoader | None = None,
        get_ai_writer: Callable[[], Any] | None = None,
    ) -> None:
        self._load_broadcasts = load_broadcasts
        self._load_state = load_state
        self._load_final_state_archive = load_final_state_archive
        self._load_live_state = load_live_state
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
        self._load_rosters = load_rosters
        self._get_ai_writer = get_ai_writer
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

    def _live_mirror(self, broadcast: Mapping[str, Any], broadcast_id: str) -> Any:
        # Index rows no longer embed live_state (it lives in the broadcast's
        # detail file); an older row that still carries one is used as is.
        live_mirror = broadcast.get("live_state")
        if live_mirror is None and self._load_live_state is not None:
            try:
                live_mirror = self._load_live_state(broadcast_id)
            except Exception:
                live_mirror = None
        return live_mirror

    def _resolve_game_state(self, broadcast: Mapping[str, Any]) -> dict[str, Any]:
        broadcast_id = str(broadcast.get("broadcast_id", ""))
        try:
            live = self._load_state()
        except Exception:
            live = {}
        live_is_this_broadcast = isinstance(live, dict) and str(live.get("broadcast_id", "")) == broadcast_id
        # A broadcast_id match alone isn't enough: end_game() clears events/plays from the live
        # state once the archive is written, but leaves broadcast_id and status behind. Trusting
        # that empty state would blank the stat highlights for a finished game.
        if live_is_this_broadcast and (live.get("events") or live.get("plays")):
            return live
        live_mirror = self._live_mirror(broadcast, broadcast_id)
        if isinstance(live_mirror, dict) and (live_mirror.get("events") or live_mirror.get("plays")):
            return live_mirror
        try:
            archive = self._load_final_state_archive(broadcast_id)
        except Exception:
            archive = None
        if isinstance(archive, dict):
            return archive
        if live_is_this_broadcast:
            return live
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

    def _active_sponsors(self) -> list[dict[str, Any]]:
        try:
            sponsors = self._get_sponsor_service().list_payload().get("sponsors", [])
        except Exception:
            sponsors = []
        return [
            sponsor
            for sponsor in sponsors
            if sponsor.get("active", True)
            and sponsor.get("effective_status") != "Expired"
            and str(sponsor.get("name", "")).strip()
        ]

    def _select_sponsors(self) -> list[dict[str, Any]]:
        active = self._active_sponsors()
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

    def _stage_side_html(
        self, *, name: str, mascot: str, logo_uri: str, align: str,
        score_html: str = "", winner: bool = False,
    ) -> str:
        monogram = self._text(name)[:1].upper() or "?"
        logo_html = (
            f'<img src="{logo_uri}" alt="">'
            if logo_uri
            else f'<span class="stage-logo-fallback">{monogram}</span>'
        )
        mascot_html = f'<span class="stage-mascot">{self._text(mascot)}</span>' if mascot else ""
        winner_class = " final-winner" if winner else ""
        return (
            f'<div class="stage-side stage-side-{align}{winner_class}">'
            f'<div class="stage-logo">{logo_html}</div>'
            f'<strong class="stage-name">{self._text(name, "TEAM")}</strong>'
            f'{mascot_html}'
            f'{score_html}'
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

    # Football only: these three per-player categories are the ones statistics_service
    # aggregates for every football game. Other sports have no confirmed mapping here, so
    # they get no highlights block rather than invented categories.
    FINAL_HIGHLIGHT_SPORTS = frozenset({"football"})
    _FINAL_HIGHLIGHT_CATEGORIES = (
        ("rushing_yards", "rushing_attempts", "rushing_touchdowns", "rush yds"),
        ("passing_yards", "pass_attempts", "passing_touchdowns", "pass yds"),
        ("receiving_yards", "receptions", "receiving_touchdowns", "rec yds"),
    )

    @staticmethod
    def _final_int(value: Any) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    @classmethod
    def _final_jersey_sort(cls, player: Mapping[str, Any]) -> int:
        number = str(player.get("number", "") or "")
        return int(number) if number.isdigit() else 999999

    @staticmethod
    def _final_short_name(player: Mapping[str, Any]) -> str:
        name = str(player.get("name", "") or "").strip()
        if not name or name.startswith("Player "):
            number = str(player.get("number", "") or "").strip()
            return f"#{number}" if number else "Unknown"
        parts = name.split()
        if len(parts) == 1:
            return parts[0]
        return f"{parts[0][0]}. {parts[-1]}"

    @classmethod
    def _final_highlight_lines(cls, players: list[Mapping[str, Any]], sport: str) -> list[str]:
        """Up to four lines for one team: the leading rusher, passer, and receiver by yardage
        (ties broken by touchdowns, then lower jersey number), then the longest made field
        goal if any kicker on the team has a recorded distance. The three core categories
        always come first, so a long field goal never displaces them."""
        if str(sport or "").strip().lower() not in cls.FINAL_HIGHLIGHT_SPORTS:
            return []
        lines: list[str] = []
        for yards_key, usage_key, td_key, unit in cls._FINAL_HIGHLIGHT_CATEGORIES:
            eligible = [p for p in players if cls._final_int(p.get(usage_key)) > 0]
            if not eligible:
                continue
            leader = max(
                eligible,
                key=lambda p: (
                    cls._final_int(p.get(yards_key)),
                    cls._final_int(p.get(td_key)),
                    -cls._final_jersey_sort(p),
                ),
            )
            line = f"{cls._final_short_name(leader)} — {cls._final_int(leader.get(yards_key))} {unit}"
            touchdowns = cls._final_int(leader.get(td_key))
            if touchdowns:
                line += f", {touchdowns} TD"
            lines.append(line)
        made_fgs: list[tuple[int, Mapping[str, Any]]] = []
        for player in players:
            for distance in player.get("field_goal_distances") or []:
                if cls._final_int(distance) > 0:
                    made_fgs.append((cls._final_int(distance), player))
        if made_fgs:
            distance, kicker = max(made_fgs, key=lambda c: (c[0], -cls._final_jersey_sort(c[1])))
            lines.append(f"{cls._final_short_name(kicker)} — {distance}-yd FG")
        return lines

    def _final_players(self, state: Mapping[str, Any]) -> list[Mapping[str, Any]]:
        if not state:
            return []
        try:
            statistics = self._build_statistics(dict(state)) or {}
        except Exception:
            return []
        return [p for p in (statistics.get("players") or []) if isinstance(p, Mapping)]

    def _final_highlights_html(
        self, *, visitor_name: str, home_name: str, visitor_lines: list[str], home_lines: list[str],
    ) -> str:
        if not visitor_lines and not home_lines:
            return ""

        def column(name: str, lines: list[str], side: str) -> str:
            items = "".join(f'<li>{self._text(line)}</li>' for line in lines) or '<li class="final-highlight-empty">—</li>'
            return (
                f'<div class="final-highlight-col final-highlight-{side}">'
                f'<div class="final-highlight-team">{self._text(name, "TEAM")}</div>'
                f'<ul>{items}</ul></div>'
            )

        return (
            '<div class="final-highlights">'
            f'{column(visitor_name, visitor_lines, "visitor")}'
            f'{column(home_name, home_lines, "home")}'
            '</div>'
        )

    def _render_final_score_document(
        self,
        *,
        broadcast: Mapping[str, Any],
        state: Mapping[str, Any],
        theme: Mapping[str, Any],
        sponsors: list[dict[str, Any]],
        players: list[Mapping[str, Any]] | None = None,
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

        visitor_wins = visitor_score > home_score
        home_wins = home_score > visitor_score
        home_side = self._stage_side_html(
            name=home_name,
            mascot=home_identity.get("mascot", ""),
            logo_uri=self._team_logo_uri(home_identity, broadcast.get("home_school_id")),
            align="home",
            score_html=f'<div class="stage-final-score">{home_score}</div>',
            winner=home_wins,
        )
        visitor_side = self._stage_side_html(
            name=visitor_name,
            mascot=visitor_identity.get("mascot", ""),
            logo_uri=self._team_logo_uri(visitor_identity, broadcast.get("visitor_school_id")),
            align="visitor",
            score_html=f'<div class="stage-final-score">{visitor_score}</div>',
            winner=visitor_wins,
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

        sport = broadcast.get("sport", "")
        all_players = list(players or [])
        highlights = self._final_highlights_html(
            visitor_name=visitor_name,
            home_name=home_name,
            visitor_lines=self._final_highlight_lines(
                [p for p in all_players if str(p.get("team", "")) == "visitor"], sport,
            ),
            home_lines=self._final_highlight_lines(
                [p for p in all_players if str(p.get("team", "")) == "home"], sport,
            ),
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
  .final-tag {{
    position: absolute; top: 16px; left: 50%; transform: translateX(-50%); z-index: 4;
    padding: 6px 22px; border-radius: 999px;
    background: var(--primary); color: #fff; font-size: 22px; font-weight: 950; letter-spacing: .22em;
    box-shadow: 0 8px 20px rgba(0,0,0,.35);
  }}
  .stage-final-score {{
    font-size: 84px; font-weight: 950; line-height: 1; color: var(--text);
    font-variant-numeric: tabular-nums; margin-top: 4px;
  }}
  .final-winner .stage-final-score {{ color: var(--accent); text-shadow: 0 0 24px color-mix(in srgb, var(--accent) 55%, transparent); }}
  .final-winner .stage-name {{ color: var(--accent); }}
  .final-highlights {{
    display: grid; grid-template-columns: minmax(0,1fr) minmax(0,1fr); gap: 24px; margin-bottom: 24px;
  }}
  .final-highlight-col {{
    background: rgba(0,0,0,.22); border: 1px solid var(--border); border-radius: var(--radius);
    padding: 14px 22px;
  }}
  .final-highlight-team {{ font-size: 18px; font-weight: 900; letter-spacing: .1em; color: var(--primary); margin-bottom: 6px; text-transform: uppercase; }}
  .final-highlight-col ul {{ list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 5px; }}
  .final-highlight-col li {{ font-size: 22px; line-height: 1.25; color: var(--text); }}
  .final-highlight-empty {{ color: var(--muted); }}
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
    <div class="final-tag">FINAL</div>
    {visitor_side}
    <div class="stage-vs">{f'<img src="{org_logo_uri}" alt="{org_name}">' if org_logo_uri else org_name}</div>
    {home_side}
  </div>
  {highlights}
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
        players = self._final_players(state)

        document = self._render_final_score_document(
            broadcast=broadcast,
            state=state,
            theme=theme,
            sponsors=sponsors,
            players=players,
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

    # -- postgame story ----------------------------------------------------------

    POSTGAME_WIDTH = postgame_card.WIDTH
    POSTGAME_HEIGHT = postgame_card.HEIGHT

    def _roster_lookup(self, broadcast: Mapping[str, Any]) -> Callable[[str], list[Mapping[str, Any]]]:
        cache: list[list[Record]] = []

        def rosters() -> list[Record]:
            if not cache:
                try:
                    cache.append(list(self._load_rosters() or []) if self._load_rosters else [])
                except Exception:
                    cache.append([])
            return cache[0]

        def lookup(team: str) -> list[Mapping[str, Any]]:
            school_id = str(broadcast.get(f"{team}_school_id", "") or "").strip()
            if not school_id:
                return []
            return [
                player
                for roster in rosters()
                if str(roster.get("school_id", "") or "") == school_id
                for player in roster.get("players") or []
                if isinstance(player, Mapping)
            ]

        return lookup

    def _postgame_facts(self, broadcast: Mapping[str, Any]) -> dict[str, Any]:
        state = self._resolve_game_state(broadcast)
        try:
            statistics = self._build_statistics(dict(state)) if state else {}
        except Exception:
            statistics = {}
        return postgame_story.build_facts(
            broadcast=broadcast,
            state=state or {},
            statistics=statistics or {},
            roster_for_team=self._roster_lookup(broadcast),
        )

    def _postgame_sponsor(self, broadcast_id: str, sponsor_id: str = "") -> dict[str, Any] | None:
        """The sponsor the station picked ("none" for no sponsor). With no pick,
        one sponsor per game, the same every time, so the written credit and
        the logo on the card always match."""
        choice = str(sponsor_id or "").strip()
        if choice == "none":
            return None
        active = sorted(self._active_sponsors(), key=lambda s: str(s.get("name", "")).casefold())
        picked = next((s for s in active if str(s.get("id", "")) == choice), None) if choice else None
        if picked is not None or not active:
            return picked
        return active[sum(ord(ch) for ch in str(broadcast_id)) % len(active)]

    def _station(self) -> tuple[str, str]:
        """(station name, station logo data URI). No links: on a monetized
        Facebook Page a link in the post costs reach."""
        try:
            config = self._load_config() or {}
        except Exception:
            config = {}
        organization = dict(config.get("organization") or {})
        name = str(organization.get("short_name") or organization.get("name") or "").strip()
        return name, self._station_logo_uri(organization)

    def _station_logo_uri(self, organization: Mapping[str, Any]) -> str:
        """Settings saves logo_path first (and logo too); read it the same way."""
        raw = str(organization.get("logo_path") or organization.get("logo") or "").strip()
        if raw.startswith("data:"):
            return raw
        relative = raw.lstrip("/")
        if relative.startswith("static/"):
            uri = self._data_uri_from_file(self._get_static_dir() / relative[len("static/"):])
            if uri:
                return uri
        if relative.startswith("asset-files/"):
            name = relative[len("asset-files/"):]
            if name and Path(name).name == name:
                uri = self._data_uri_from_file(self._get_asset_upload_dir() / name)
                if uri:
                    return uri
        return self._org_logo_uri(organization)

    def _card_art_uri(self, path: Path) -> str:
        """Theme art scaled to the card and sent as JPEG: the originals run past
        2 MB, which Chromium will not load as a data URI."""
        try:
            with Image.open(path) as image:
                image = image.convert("RGB")
                image.thumbnail((self.POSTGAME_WIDTH, self.POSTGAME_HEIGHT * 2))
                buffer = io.BytesIO()
                image.save(buffer, format="JPEG", quality=84)
            return "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
        except (OSError, ValueError):
            return ""

    def _theme_assets(self, theme: str) -> dict[str, str]:
        assets = {}
        for key, relative in postgame_card.THEMES[postgame_card.theme_id(theme)]["assets"].items():
            path = self._get_static_dir() / relative
            if key == "art":
                assets[key] = self._card_art_uri(path)
                continue
            uri = self._data_uri_from_file(path)
            if uri and relative.endswith(".woff2"):
                uri = uri.replace("data:application/octet-stream", "data:font/woff2", 1)
                if not uri.startswith("data:font/woff2"):
                    uri = "data:font/woff2;base64," + uri.split(",", 1)[1]
            assets[key] = uri
        return assets

    def postgame_story(
        self, broadcast_id: str, variant: int = 0, *, sponsor_id: str = "", player_of_game: str = "",
    ) -> SocialMediaPreviewResult:
        broadcast = self._find_broadcast(broadcast_id)
        if broadcast is None:
            return SocialMediaPreviewResult("BROADCAST_NOT_FOUND")
        facts = self._postgame_facts(broadcast)
        if not facts["has_plays"]:
            return SocialMediaPreviewResult("NO_GAME_DATA")
        sponsor = self._postgame_sponsor(broadcast_id, sponsor_id)
        station_name, _ = self._station()
        written = postgame_story.write_story(
            facts,
            variant=variant,
            sponsor_name=str((sponsor or {}).get("name", "") or ""),
            station_name=station_name,
            player_of_game=player_of_game,
        )
        written.pop("player_of_game", None)
        return SocialMediaPreviewResult(
            "OK",
            {
                "broadcast_id": broadcast_id,
                "story": written,
                "line_score": facts["line_score"],
                "key_plays": [
                    f"{postgame_story.quarter_tag(p['quarter'])} {facts['teams'][p['team']]['name']}: "
                    f"{postgame_story.big_play_line(p)}"
                    for p in facts["big_plays"]
                ],
                "sponsor_id": str((sponsor or {}).get("id", "") or ("none" if sponsor_id == "none" else "")),
                "sponsor_name": (sponsor or {}).get("name", ""),
                "sponsors": [{"id": str(s.get("id", "")), "name": s.get("name", "")}
                             for s in sorted(self._active_sponsors(), key=lambda s: str(s.get("name", "")).casefold())],
                "players": [{"id": c["id"], "label": c["label"]} for c in facts["players"]],
                "themes": [{"id": key, "label": value["label"]} for key, value in postgame_card.THEMES.items()],
                "logo_styles": [{"id": key, "label": label} for key, label in postgame_card.LOGO_STYLES.items()],
                "scores_reliable": facts["scores_reliable"],
                "unnamed_players": [f"{facts['teams'][team]['name']} No. {number}" for team, number in facts["unnamed"]],
            },
        )

    @staticmethod
    def _rasterize(document: str, width: int, height: int) -> bytes:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={"width": width, "height": height})
                page.set_content(document, wait_until="load")
                try:
                    page.wait_for_function("window.__cardFitted === true", timeout=5000)
                except Exception:
                    pass  # an unfitted card is still better than none
                return page.screenshot(type="png")
            finally:
                browser.close()

    def postgame_card_document(
        self,
        broadcast_id: str,
        *,
        variant: int = 0,
        headline: str = "",
        sponsor_id: str = "",
        player_of_game: str = "",
        theme: str = postgame_card.DEFAULT_THEME,
        logo_style: str = postgame_card.DEFAULT_LOGO_STYLE,
    ) -> str | None:
        broadcast = self._find_broadcast(broadcast_id)
        if broadcast is None:
            return None
        facts = self._postgame_facts(broadcast)
        sponsor = self._postgame_sponsor(broadcast_id, sponsor_id)
        sponsor_logo = self._sponsor_logo_uri(sponsor)[0] if sponsor else ""
        station_name, station_logo = self._station()
        lede = postgame_story.write_story(facts, variant=variant)["paragraphs"][0] if facts["has_plays"] else ""
        logos = {
            team: self._team_logo_uri(
                broadcast.get(f"{team}_identity") if isinstance(broadcast.get(f"{team}_identity"), Mapping) else {},
                broadcast.get(f"{team}_school_id"),
            )
            for team in postgame_story.TEAMS
        }
        return postgame_card.render_card_html(
            facts,
            headline=headline.strip()[:160] or postgame_story.headline(facts, variant),
            deck=lede,
            station_name=station_name,
            station_logo_uri=station_logo,
            logos=logos,
            sponsor_name=str((sponsor or {}).get("name", "") or ""),
            sponsor_logo_uri=sponsor_logo,
            theme=theme,
            station_logo_style=logo_style,
            assets=self._theme_assets(theme),
            player_of_game=postgame_story.players_of_the_game(facts, player_of_game),
        )

    def generate_postgame_card(
        self,
        broadcast_id: str,
        *,
        variant: int = 0,
        headline: str = "",
        sponsor_id: str = "",
        player_of_game: str = "",
        theme: str = postgame_card.DEFAULT_THEME,
        logo_style: str = postgame_card.DEFAULT_LOGO_STYLE,
    ) -> SocialMediaPreviewResult:
        """The graphic that goes with the postgame story, in the chosen theme."""
        document = self.postgame_card_document(
            broadcast_id, variant=variant, headline=headline, sponsor_id=sponsor_id,
            player_of_game=player_of_game, theme=theme, logo_style=logo_style,
        )
        if document is None:
            return SocialMediaPreviewResult("BROADCAST_NOT_FOUND")
        try:
            image_bytes = self._rasterize(document, self.POSTGAME_WIDTH, self.POSTGAME_HEIGHT)
        except Exception as exc:
            return SocialMediaPreviewResult("IMAGE_GENERATION_FAILED", {"message": str(exc)})
        safe_id = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(broadcast_id)).strip("-") or "broadcast"
        filename = f"{safe_id}-postgame-story.png"
        try:
            (self.output_dir / filename).write_bytes(image_bytes)
        except OSError:
            pass
        return SocialMediaPreviewResult("OK", {"image": image_bytes, "filename": filename})


    # -- pregame story and the AI writer -------------------------------------------

    def _statistics_for_game(self, game: Mapping[str, Any]) -> dict[str, Any] | None:
        state = self._resolve_game_state(game)
        if not state or not (state.get("events") or state.get("plays")):
            return None
        try:
            return self._build_statistics(dict(state))
        except Exception:
            return None

    def _pregame_facts(self, broadcast: Mapping[str, Any]) -> dict[str, Any]:
        try:
            games = [g for g in self._load_broadcasts() or [] if isinstance(g, Mapping)]
        except Exception:
            games = []
        return pregame_story.build_facts(
            broadcast=broadcast,
            games=games,
            storylines=self._storylines(str(broadcast.get("broadcast_id", ""))),
            statistics_for=self._statistics_for_game,
            roster_for_team=self._roster_lookup(broadcast),
        )

    def _sponsor_payload(self, sponsor: Mapping[str, Any] | None, sponsor_id: str) -> dict[str, Any]:
        return {
            "sponsor_id": str((sponsor or {}).get("id", "") or ("none" if sponsor_id == "none" else "")),
            "sponsor_name": (sponsor or {}).get("name", ""),
            "sponsors": [{"id": str(s.get("id", "")), "name": s.get("name", "")}
                         for s in sorted(self._active_sponsors(), key=lambda s: str(s.get("name", "")).casefold())],
        }

    def pregame_story(self, broadcast_id: str, variant: int = 0, *, sponsor_id: str = "") -> SocialMediaPreviewResult:
        broadcast = self._find_broadcast(broadcast_id)
        if broadcast is None:
            return SocialMediaPreviewResult("BROADCAST_NOT_FOUND")
        facts = self._pregame_facts(broadcast)
        sponsor = self._postgame_sponsor(broadcast_id, sponsor_id)
        station_name, _ = self._station()
        written = pregame_story.write_story(
            facts, variant=variant, sponsor_name=str((sponsor or {}).get("name", "") or ""), station_name=station_name,
        )
        return SocialMediaPreviewResult("OK", {"broadcast_id": broadcast_id, "kind": "pregame", "story": written,
                                               **self._sponsor_payload(sponsor, sponsor_id)})

    def ai_story(
        self,
        kind: str,
        broadcast_id: str,
        *,
        sponsor_id: str = "",
        player_of_game: str = "",
        previous: str = "",
        notes: list[str] | None = None,
        instructions: str = "",
    ) -> SocialMediaPreviewResult:
        """The AI writer's version of the pregame or postgame story. When it can't
        write one (no key, no internet, a refusal), the built-in story comes back
        with a note saying why, so there is always something to post.

        With instructions, the AI revises `previous` (the story as the station
        has it now) using the station's answers to its notes. A failed revision
        comes back as an error so the station's text is never replaced."""
        revising = bool(str(instructions or "").strip())
        kind = "pregame" if kind == "pregame" else "postgame"
        if kind == "pregame":
            builtin = self.pregame_story(broadcast_id, sponsor_id=sponsor_id)
        else:
            builtin = self.postgame_story(broadcast_id, sponsor_id=sponsor_id, player_of_game=player_of_game)
        if not builtin.ok:
            return builtin
        data = dict(builtin.data)
        data["kind"] = kind
        broadcast = self._find_broadcast(broadcast_id) or {}
        station_name, _ = self._station()
        if kind == "pregame":
            facts = self._pregame_facts(broadcast)
            sheet = pregame_story.fact_sheet(facts)
            home, visitor = facts["teams"]["home"], facts["teams"]["visitor"]
            # The opponent is the team the station knows least about.
            opponent = visitor if len(visitor["results"]) <= len(home["results"]) else home
            names = {"home": home["name"], "visitor": visitor["name"], "opponent": opponent["name"]}
        else:
            facts = self._postgame_facts(broadcast)
            sheet = postgame_story.fact_sheet(facts, postgame_story.write_story(facts))
            names = {"home": facts["teams"]["home"]["name"], "visitor": facts["teams"]["visitor"]["name"], "opponent": ""}
        writer = self._get_ai_writer() if self._get_ai_writer else None
        if writer is None:
            result_code, result_data = "AI_UNAVAILABLE", {}
        elif revising:
            # The app owns the Player of the Game line: the AI never sees or writes it.
            earlier = "\n\n".join(p for p in str(previous or "").split("\n\n") if "Player of the Game:" not in p)
            result = writer.revise(kind, sheet, previous=earlier, notes=list(notes or []), instructions=instructions,
                                   station=station_name, **names)
            result_code, result_data = result.code, result.data
        else:
            result = writer.write(kind, sheet, station=station_name, **names)
            result_code, result_data = result.code, result.data
        if result_code != "OK" and revising:
            return SocialMediaPreviewResult(result_code, {"message": AI_FALLBACK_MESSAGES.get(
                result_code, AI_FALLBACK_MESSAGES["AI_FAILED"]).split(", so the app")[0] + ". Your story was left as it was."})
        if result_code != "OK":
            data["fallback"] = {"code": result_code, "message": AI_FALLBACK_MESSAGES.get(result_code, AI_FALLBACK_MESSAGES["AI_FAILED"])}
            return SocialMediaPreviewResult("OK", data)
        builtin_story = dict(data["story"])
        paragraphs = [p.strip() for p in result_data["story"].split("\n\n") if p.strip()]
        # The app, not the AI, adds the Player of the Game line.
        paragraphs += [p for p in builtin_story.get("paragraphs", []) if "Player of the Game:" in p]
        story_text = "\n\n".join(paragraphs)
        headline = result_data["headline"] or builtin_story.get("headline", "")
        blocks = [headline, story_text]
        if builtin_story.get("scoring"):
            blocks.append("SCORING\n" + "\n".join(builtin_story["scoring"]))
        if builtin_story.get("closing"):
            blocks.append(" ".join(builtin_story["closing"]))
        blocks.append(" ".join(builtin_story.get("hashtags") or []))
        data["story"] = {**builtin_story, "headline": headline, "paragraphs": paragraphs, "story": story_text,
                         "post_text": "\n\n".join(b for b in blocks if b), "word_count": len(story_text.split()),
                         "writer": "ai", "model": result_data.get("model", "")}
        data["sources"] = result_data.get("sources", [])
        data["notes"] = result_data.get("notes", [])
        data["search"] = result_data.get("search", {})
        data["cost_usd"] = result_data.get("cost_usd")
        data["revised"] = revising
        return SocialMediaPreviewResult("OK", data)
