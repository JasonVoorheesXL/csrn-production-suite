from __future__ import annotations

import copy
import json
import re
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from threading import Lock
from typing import Any, Callable, Mapping

from social_card_renderer import SocialCardRenderer
from social_platforms import PlatformResult, SocialPlatformAdapter


LoadMapping = Callable[[], Mapping[str, Any]]
LoadList = Callable[[], list[dict[str, Any]]]
ActiveSponsor = Callable[[str], dict[str, Any] | None]
Clock = Callable[[], float]


@dataclass(frozen=True)
class SocialResult:
    code: str
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.code in {
            "OK",
            "ACCOUNT_SAVED",
            "ACCOUNT_REMOVED",
            "SETTINGS_UPDATED",
            "SPONSOR_RULES_UPDATED",
            "DRAFT_CREATED",
            "DRAFT_UPDATED",
            "DRAFT_APPROVED",
            "DRAFT_DELETED",
            "PUBLISHED",
            "PARTIALLY_PUBLISHED",
            "CORRECTION_CREATED",
            "PUBLICATION_RETRACTED",
            "EVENT_QUEUED",
            "AUTO_QUEUE_PROCESSED",
        }


class SocialPublishingService:
    """Persistent, preview-first social queue independent of Flask.

    No access token or client secret is accepted into this service. Account records
    store only a credential reference resolved by the platform adapter.
    """

    SCHEMA = 1
    MAX_ACCOUNTS = 8
    MAX_DRAFTS = 500
    MAX_AUDIT = 2000
    ACCOUNT_ID = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,47}$")
    CREDENTIAL_REF = re.compile(r"^[A-Z][A-Z0-9_]{2,127}$")
    SECRET_KEYS = {
        "token",
        "access_token",
        "refresh_token",
        "client_secret",
        "app_secret",
        "password",
        "bearer_token",
    }
    PLATFORMS = {"x", "facebook"}
    EVENT_KIND_MAP = {
        "TD": "TOUCHDOWN",
        "TURNOVER": "TURNOVER",
        "FG": "FIELD_GOAL",
    }
    KINDS = {
        "TOUCHDOWN",
        "TURNOVER",
        "FIELD_GOAL",
        "SAFETY",
        "LEAD_CHANGE",
        "HALFTIME",
        "FINAL",
        "MILESTONE",
        "PLAYER_OF_GAME",
        "WEATHER_DELAY",
        "GAME_RESUMPTION",
        "WEATHER_EMERGENCY",
    }
    EMERGENCY_KINDS = {"WEATHER_EMERGENCY"}
    KIND_HEADLINES = {
        "TOUCHDOWN": "TOUCHDOWN",
        "TURNOVER": "TURNOVER",
        "FIELD_GOAL": "FIELD GOAL",
        "SAFETY": "SAFETY",
        "LEAD_CHANGE": "NEW LEADER",
        "HALFTIME": "HALFTIME",
        "FINAL": "FINAL",
        "MILESTONE": "MILESTONE",
        "PLAYER_OF_GAME": "PLAYER OF THE GAME",
        "WEATHER_DELAY": "WEATHER DELAY",
        "GAME_RESUMPTION": "GAME RESUMING",
        "WEATHER_EMERGENCY": "SEVERE WEATHER ALERT",
    }
    DEFAULT_STATE: dict[str, Any] = {
        "schema": SCHEMA,
        "accounts": {},
        "settings": {
            "auto_create_drafts": False,
            "allow_auto_publish": False,
            "default_hashtags": ["#HighSchoolSports"],
            "include_broadcast_link": True,
        },
        "sponsor_rules": {
            "event_sponsors": {},
            "rotation": [],
            "rotation_index": 0,
        },
        "drafts": [],
        "audit": [],
        "updated_at": 0,
    }

    def __init__(
        self,
        *,
        state_file: Path,
        renderer: SocialCardRenderer,
        adapters: Mapping[str, SocialPlatformAdapter],
        load_broadcast_state: LoadMapping,
        load_config: LoadMapping,
        load_rosters: LoadList,
        load_sponsors: LoadList,
        active_sponsor_by_id: ActiveSponsor,
        get_theme_status: Callable[[], Any],
        clock: Clock = time.time,
    ) -> None:
        self.state_file = Path(state_file)
        self.renderer = renderer
        self.adapters = dict(adapters)
        self._load_broadcast_state = load_broadcast_state
        self._load_config = load_config
        self._load_rosters = load_rosters
        self._load_sponsors = load_sponsors
        self._active_sponsor = active_sponsor_by_id
        self._get_theme_status = get_theme_status
        self._clock = clock
        self._lock = Lock()
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _read(path: Path, default: Any) -> Any:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return copy.deepcopy(default)

    def _load(self) -> dict[str, Any]:
        payload = self._read(self.state_file, self.DEFAULT_STATE)
        if not isinstance(payload, dict):
            payload = {}
        state = copy.deepcopy(self.DEFAULT_STATE)
        state.update(payload)
        state["accounts"] = payload.get("accounts", {}) if isinstance(payload.get("accounts"), dict) else {}
        state["settings"] = {**self.DEFAULT_STATE["settings"], **(payload.get("settings", {}) if isinstance(payload.get("settings"), dict) else {})}
        state["sponsor_rules"] = {**self.DEFAULT_STATE["sponsor_rules"], **(payload.get("sponsor_rules", {}) if isinstance(payload.get("sponsor_rules"), dict) else {})}
        state["drafts"] = payload.get("drafts", []) if isinstance(payload.get("drafts"), list) else []
        state["audit"] = payload.get("audit", []) if isinstance(payload.get("audit"), list) else []
        return state

    def _write(self, state: Mapping[str, Any]) -> None:
        payload = copy.deepcopy(dict(state))
        payload["updated_at"] = int(self._clock())
        temporary = self.state_file.with_name(f".{self.state_file.name}.tmp")
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        temporary.replace(self.state_file)

    def _audit(self, state: dict[str, Any], action: str, **details: Any) -> None:
        rows = list(state.get("audit") or [])
        rows.append(
            {
                "id": f"AUD-{int(self._clock() * 1000)}-{len(rows) % 1000:03d}",
                "action": action,
                "created_at": int(self._clock()),
                **copy.deepcopy(details),
            }
        )
        state["audit"] = rows[-self.MAX_AUDIT :]

    @staticmethod
    def _account_public(account: Mapping[str, Any]) -> dict[str, Any]:
        result = copy.deepcopy(dict(account))
        result["credential_configured"] = bool(result.get("credential_ref"))
        return result

    def status(self) -> SocialResult:
        with self._lock:
            state = self._load()
        counts: dict[str, int] = {}
        for draft in state["drafts"]:
            status = str(draft.get("status", "DRAFT"))
            counts[status] = counts.get(status, 0) + 1
        return SocialResult(
            "OK",
            {
                "social": {
                    "accounts": [self._account_public(item) for item in state["accounts"].values()],
                    "settings": copy.deepcopy(state["settings"]),
                    "sponsor_rules": copy.deepcopy(state["sponsor_rules"]),
                    "draft_counts": counts,
                    "drafts": copy.deepcopy(state["drafts"][-100:]),
                    "audit": copy.deepcopy(state["audit"][-200:]),
                    "updated_at": int(state.get("updated_at", 0) or 0),
                }
            },
        )

    def configure_account(self, incoming: Mapping[str, Any] | None) -> SocialResult:
        data = dict(incoming or {})
        lowered = {str(key).casefold() for key in data}
        forbidden = sorted(lowered & self.SECRET_KEYS)
        if forbidden:
            return SocialResult("RAW_CREDENTIAL_REJECTED", {"fields": forbidden})
        platform = str(data.get("platform", "")).strip().lower()
        if platform not in self.PLATFORMS:
            return SocialResult("PLATFORM_UNSUPPORTED")
        account_id = str(data.get("id") or f"{platform}-primary").strip().lower()
        if not self.ACCOUNT_ID.fullmatch(account_id):
            return SocialResult("ACCOUNT_ID_INVALID")
        default_ref = "CSRN_X_ACCESS_TOKEN" if platform == "x" else "CSRN_FACEBOOK_PAGE_ACCESS_TOKEN"
        credential_ref = str(data.get("credential_ref") or default_ref).strip()
        if not self.CREDENTIAL_REF.fullmatch(credential_ref):
            return SocialResult("CREDENTIAL_REFERENCE_INVALID")
        try:
            text_limit = int(data.get("text_limit") or (280 if platform == "x" else 5000))
        except (TypeError, ValueError):
            return SocialResult("TEXT_LIMIT_INVALID")
        text_limit = max(80, min(25000, text_limit))
        account = {
            "id": account_id,
            "platform": platform,
            "display_name": str(data.get("display_name") or account_id).strip()[:120],
            "enabled": bool(data.get("enabled", True)),
            "auto_publish": bool(data.get("auto_publish", False)),
            "credential_ref": credential_ref,
            "username": str(data.get("username", "")).strip().lstrip("@")[:120],
            "page_id": str(data.get("page_id", "")).strip()[:120],
            "api_base": str(data.get("api_base") or ("https://api.x.com" if platform == "x" else "https://graph.facebook.com")).strip()[:300],
            "api_version": str(data.get("api_version") or ("" if platform == "x" else "v25.0")).strip()[:40],
            "text_limit": text_limit,
            "updated_at": int(self._clock()),
        }
        if platform == "facebook" and not account["page_id"]:
            return SocialResult("PAGE_ID_REQUIRED")
        with self._lock:
            state = self._load()
            if account_id not in state["accounts"] and len(state["accounts"]) >= self.MAX_ACCOUNTS:
                return SocialResult("ACCOUNT_LIMIT_REACHED")
            state["accounts"][account_id] = account
            self._audit(state, "ACCOUNT_SAVED", account_id=account_id, platform=platform)
            self._write(state)
        return SocialResult("ACCOUNT_SAVED", {"account": self._account_public(account)})

    def remove_account(self, account_id: Any, confirmation: Any) -> SocialResult:
        account_id = str(account_id or "").strip().lower()
        if str(confirmation or "") != "REMOVE SOCIAL ACCOUNT":
            return SocialResult("ACCOUNT_REMOVE_CONFIRMATION_REQUIRED")
        with self._lock:
            state = self._load()
            account = state["accounts"].pop(account_id, None)
            if account is None:
                return SocialResult("ACCOUNT_NOT_FOUND")
            self._audit(state, "ACCOUNT_REMOVED", account_id=account_id, platform=account.get("platform", ""))
            self._write(state)
        return SocialResult("ACCOUNT_REMOVED", {"account_id": account_id})

    def update_settings(self, incoming: Mapping[str, Any] | None) -> SocialResult:
        data = dict(incoming or {})
        allowed = {"auto_create_drafts", "allow_auto_publish", "default_hashtags", "include_broadcast_link"}
        unknown = sorted(set(data) - allowed)
        if unknown:
            return SocialResult("SETTINGS_INVALID", {"unknown": unknown})
        with self._lock:
            state = self._load()
            settings = state["settings"]
            for key in ("auto_create_drafts", "allow_auto_publish", "include_broadcast_link"):
                if key in data:
                    settings[key] = bool(data[key])
            if "default_hashtags" in data:
                values = data["default_hashtags"]
                if not isinstance(values, list):
                    return SocialResult("HASHTAGS_INVALID")
                tags: list[str] = []
                for value in values[:12]:
                    tag = re.sub(r"[^A-Za-z0-9_]", "", str(value).lstrip("#"))
                    if tag:
                        tags.append(f"#{tag}"[:80])
                settings["default_hashtags"] = tags
            self._audit(state, "SETTINGS_UPDATED")
            self._write(state)
        return SocialResult("SETTINGS_UPDATED", {"settings": copy.deepcopy(settings)})

    def update_sponsor_rules(self, incoming: Mapping[str, Any] | None) -> SocialResult:
        data = dict(incoming or {})
        event_sponsors = data.get("event_sponsors", {})
        rotation = data.get("rotation", [])
        if not isinstance(event_sponsors, dict) or not isinstance(rotation, list):
            return SocialResult("SPONSOR_RULES_INVALID")
        normalized: dict[str, str] = {}
        for kind, sponsor_id in event_sponsors.items():
            kind = str(kind).upper()
            sponsor_id = str(sponsor_id).strip()
            if kind not in self.KINDS or kind in self.EMERGENCY_KINDS:
                return SocialResult("SPONSOR_RULE_KIND_INVALID", {"kind": kind})
            if sponsor_id and self._active_sponsor(sponsor_id) is None:
                return SocialResult("SPONSOR_NOT_ACTIVE", {"sponsor_id": sponsor_id})
            if sponsor_id:
                normalized[kind] = sponsor_id
        normalized_rotation: list[str] = []
        for sponsor_id in rotation[:24]:
            sponsor_id = str(sponsor_id).strip()
            if sponsor_id and self._active_sponsor(sponsor_id) is None:
                return SocialResult("SPONSOR_NOT_ACTIVE", {"sponsor_id": sponsor_id})
            if sponsor_id and sponsor_id not in normalized_rotation:
                normalized_rotation.append(sponsor_id)
        with self._lock:
            state = self._load()
            state["sponsor_rules"] = {
                "event_sponsors": normalized,
                "rotation": normalized_rotation,
                "rotation_index": min(int(state["sponsor_rules"].get("rotation_index", 0) or 0), max(0, len(normalized_rotation) - 1)),
            }
            self._audit(state, "SPONSOR_RULES_UPDATED")
            self._write(state)
        return SocialResult("SPONSOR_RULES_UPDATED", {"sponsor_rules": copy.deepcopy(state["sponsor_rules"])})

    def _theme(self) -> dict[str, Any]:
        result = self._get_theme_status()
        data = getattr(result, "data", result)
        if isinstance(data, Mapping):
            theme = data.get("theme", data)
            if isinstance(theme, Mapping) and isinstance(theme.get("active"), Mapping):
                return copy.deepcopy(dict(theme["active"]))
            if isinstance(theme, Mapping) and "tokens" in theme:
                return copy.deepcopy(dict(theme))
        return {"id": "modern_network", "tokens": {}}

    @staticmethod
    def _identity(source: Any, fallback: str) -> dict[str, Any]:
        source = source if isinstance(source, Mapping) else {}
        return {
            "name": str(source.get("name") or fallback),
            "mascot": str(source.get("mascot") or ""),
            "logo": str(source.get("logo") or source.get("logo_url") or ""),
            "primary_color": str(source.get("primary_color") or ""),
        }

    def _player(self, event: Mapping[str, Any], payload: Mapping[str, Any]) -> dict[str, Any]:
        automation = event.get("automation", {}) if isinstance(event.get("automation"), Mapping) else {}
        player_id = str(payload.get("player_id") or automation.get("player_id") or "").strip()
        roster_id = str(payload.get("roster_id") or "").strip()
        player: dict[str, Any] = {}
        for roster in self._load_rosters():
            if roster_id and str(roster.get("id", "")) != roster_id:
                continue
            for candidate in roster.get("players", []) if isinstance(roster.get("players"), list) else []:
                if player_id and str(candidate.get("id", "")) == player_id:
                    player = copy.deepcopy(candidate)
                    break
            if player:
                break
        name = str(payload.get("player_name") or automation.get("player_name") or player.get("display_name") or player.get("full_name") or player.get("name") or "").strip()
        number = str(payload.get("player_number") or automation.get("player_number") or player.get("number") or "").strip()
        return {
            "id": player_id,
            "name": name,
            "number": number,
            "position": str(player.get("position") or ""),
            "headshot": str(player.get("headshot") or player.get("headshot_url") or ""),
        }

    def _select_sponsor(self, state: dict[str, Any], kind: str, explicit_id: str) -> tuple[dict[str, Any], bool]:
        if kind in self.EMERGENCY_KINDS:
            return {}, True
        rules = state["sponsor_rules"]
        sponsor_id = explicit_id or str(rules.get("event_sponsors", {}).get(kind, ""))
        if not sponsor_id:
            rotation = list(rules.get("rotation") or [])
            if rotation:
                index = int(rules.get("rotation_index", 0) or 0) % len(rotation)
                sponsor_id = str(rotation[index])
                rules["rotation_index"] = (index + 1) % len(rotation)
        sponsor = self._active_sponsor(sponsor_id) if sponsor_id else None
        if not sponsor:
            return {}, False
        lead_ins = sponsor.get("lead_ins", []) if isinstance(sponsor.get("lead_ins"), list) else []
        return {
            "id": str(sponsor.get("id", "")),
            "name": str(sponsor.get("name", "")),
            "logo": str(sponsor.get("logo_url", "")),
            "lead_in": str(lead_ins[0] if lead_ins else "Presented by"),
        }, False

    @staticmethod
    def _find_event(broadcast: Mapping[str, Any], event_id: str) -> dict[str, Any]:
        if not event_id:
            last = broadcast.get("last_event")
            return copy.deepcopy(dict(last)) if isinstance(last, Mapping) else {}
        for event in broadcast.get("events", []) if isinstance(broadcast.get("events"), list) else []:
            if str(event.get("id", "")) == event_id:
                return copy.deepcopy(event)
        return {}

    def _copy(self, kind: str, broadcast: Mapping[str, Any], event: Mapping[str, Any], payload: Mapping[str, Any]) -> dict[str, str]:
        home_name = str(broadcast.get("home_team") or "Home")
        visitor_name = str(broadcast.get("visitor_team") or "Visitor")
        home_score = int(broadcast.get("home_score", 0) or 0)
        visitor_score = int(broadcast.get("visitor_score", 0) or 0)
        score = f"{home_name} {home_score} · {visitor_name} {visitor_score}"
        headline = str(payload.get("headline") or self.KIND_HEADLINES[kind])[:160]
        detail = str(payload.get("detail") or payload.get("message") or event.get("description") or "").strip()[:500]
        quarter = str(event.get("quarter") or broadcast.get("quarter") or "")
        if kind == "HALFTIME" and not detail:
            detail = f"Halftime score: {score}"
        elif kind == "FINAL" and not detail:
            detail = f"Final score: {score}"
        elif kind == "WEATHER_DELAY" and not detail:
            detail = "The game is delayed due to weather. Follow school and venue instructions."
        elif kind == "GAME_RESUMPTION" and not detail:
            detail = "The game is resuming. Follow school and venue instructions."
        elif kind == "WEATHER_EMERGENCY" and not detail:
            detail = "Official severe-weather information is available from school and public-safety officials."
        eyebrow = str(payload.get("eyebrow") or (f"Q{quarter}" if quarter and kind not in {"HALFTIME", "FINAL"} else "GAME UPDATE"))[:80]
        return {"eyebrow": eyebrow, "headline": headline, "detail": detail, "score": score}

    def _platform_text(self, draft: Mapping[str, Any], platform: str, limit: int) -> str:
        content = draft["content"]
        lines = [content["headline"], content.get("detail", ""), content.get("score", "")]
        player = draft.get("player", {})
        if player and player.get("name") and player.get("name") not in " ".join(lines):
            prefix = f"#{player.get('number')} " if player.get("number") else ""
            lines.append(f"{prefix}{player.get('name')}")
        settings = draft.get("settings", {})
        if settings.get("include_broadcast_link") and draft.get("broadcast_link"):
            lines.append(str(draft["broadcast_link"]))
        hashtags = " ".join(settings.get("default_hashtags", []))
        if hashtags:
            lines.append(hashtags)
        text = "\n".join(line for line in lines if str(line).strip())
        if len(text) <= limit:
            return text
        suffix = "…"
        return text[: max(0, limit - len(suffix))].rstrip() + suffix

    def _render_cards(self, draft: dict[str, Any], accounts: Mapping[str, Mapping[str, Any]]) -> None:
        platforms = {str(account.get("platform")) for account in accounts.values() if account.get("enabled", True)} or self.PLATFORMS
        cards: dict[str, Any] = {}
        errors: dict[str, str] = {}
        for platform in sorted(platforms):
            try:
                cards[platform] = self.renderer.render(draft, platform=platform, theme=draft["theme"])
            except Exception as exc:  # Rendering failure must not corrupt the queue.
                errors[platform] = str(exc)[:300]
        draft["cards"] = cards
        draft["card_errors"] = errors

    def create_draft(
        self,
        kind: Any,
        *,
        event_id: Any = "",
        payload: Mapping[str, Any] | None = None,
        force_duplicate: bool = False,
    ) -> SocialResult:
        kind = str(kind or "").strip().upper()
        if kind not in self.KINDS:
            return SocialResult("DRAFT_KIND_INVALID")
        payload = dict(payload or {})
        broadcast = copy.deepcopy(dict(self._load_broadcast_state()))
        event_id = str(event_id or "").strip()
        event = self._find_event(broadcast, event_id)
        if event_id and not event:
            return SocialResult("EVENT_NOT_FOUND")
        if event and not event_id:
            event_id = str(event.get("id", ""))
        if event:
            derived = self.EVENT_KIND_MAP.get(str(event.get("event", "")).upper())
            if derived and kind != derived and not bool(payload.get("allow_kind_override")):
                return SocialResult("EVENT_KIND_MISMATCH", {"expected_kind": derived})
        if kind in {"MILESTONE", "PLAYER_OF_GAME", "WEATHER_EMERGENCY"} and not str(payload.get("message") or payload.get("detail") or "").strip():
            return SocialResult("GROUNDED_MESSAGE_REQUIRED")

        with self._lock:
            state = self._load()
            if event_id and not force_duplicate:
                duplicate = next((item for item in state["drafts"] if str(item.get("source_event_id", "")) == event_id and item.get("status") != "DELETED"), None)
                if duplicate:
                    return SocialResult("DUPLICATE_DRAFT", {"draft": copy.deepcopy(duplicate)})
            sponsor, suppressed = self._select_sponsor(state, kind, str(payload.get("sponsor_id", "")).strip())
            config = dict(self._load_config())
            organization = config.get("organization", {}) if isinstance(config.get("organization"), Mapping) else {}
            home = self._identity(broadcast.get("home_identity"), str(broadcast.get("home_team") or "Home"))
            visitor = self._identity(broadcast.get("visitor_identity"), str(broadcast.get("visitor_team") or "Visitor"))
            player = self._player(event, payload)
            content = self._copy(kind, broadcast, event, payload)
            now = int(self._clock())
            draft_id = f"SOC-{now}-{len(state['drafts']) % 1000:03d}"
            social_config = config.get("social", {}) if isinstance(config.get("social"), Mapping) else {}
            draft: dict[str, Any] = {
                "id": draft_id,
                "kind": kind,
                "status": "DRAFT",
                "revision": 1,
                "source_event_id": event_id,
                "broadcast_id": str(broadcast.get("broadcast_id", "")),
                "created_at": now,
                "updated_at": now,
                "approved_at": 0,
                "approved_by": "",
                "replaces_draft_id": "",
                "content": content,
                "description": content["detail"],
                "home": home,
                "visitor": visitor,
                "player": player,
                "organization": {
                    "name": str(organization.get("name") or ""),
                    "short_name": str(organization.get("short_name") or "CSRN"),
                    "logo": str(organization.get("logo_path") or ""),
                },
                "sponsor": sponsor,
                "sponsor_suppressed": suppressed,
                "theme": self._theme(),
                "settings": copy.deepcopy(state["settings"]),
                "broadcast_link": str(payload.get("broadcast_link") or social_config.get("website") or ""),
                "platform_copy": {},
                "cards": {},
                "card_errors": {},
                "publications": {},
                "attempts": [],
            }
            for account_id, account in state["accounts"].items():
                if account.get("enabled", True):
                    draft["platform_copy"][account_id] = self._platform_text(draft, str(account.get("platform")), int(account.get("text_limit", 280)))
            self._render_cards(draft, state["accounts"])
            state["drafts"] = (state["drafts"] + [draft])[-self.MAX_DRAFTS :]
            self._audit(state, "DRAFT_CREATED", draft_id=draft_id, kind=kind, source_event_id=event_id, sponsor_suppressed=suppressed)
            self._write(state)
        return SocialResult("DRAFT_CREATED", {"draft": copy.deepcopy(draft)})

    def queue_event(self, event: Mapping[str, Any]) -> SocialResult:
        event_code = str(event.get("event", "")).upper()
        kind = self.EVENT_KIND_MAP.get(event_code)
        if not kind:
            return SocialResult("EVENT_NOT_ELIGIBLE")
        with self._lock:
            settings = copy.deepcopy(self._load()["settings"])
        if not settings.get("auto_create_drafts", False):
            return SocialResult("AUTO_DRAFT_DISABLED")
        result = self.create_draft(kind, event_id=event.get("id"))
        if result.code == "DUPLICATE_DRAFT":
            return SocialResult("EVENT_QUEUED", result.data)
        return SocialResult("EVENT_QUEUED", result.data) if result.ok else result

    def eligible_events(self) -> SocialResult:
        broadcast = dict(self._load_broadcast_state())
        with self._lock:
            queued = {str(item.get("source_event_id", "")) for item in self._load()["drafts"] if item.get("status") != "DELETED"}
        events = []
        for event in broadcast.get("events", []) if isinstance(broadcast.get("events"), list) else []:
            kind = self.EVENT_KIND_MAP.get(str(event.get("event", "")).upper())
            if kind and str(event.get("id", "")) not in queued:
                events.append({"event": copy.deepcopy(event), "kind": kind})
        return SocialResult("OK", {"events": events[-100:]})

    @staticmethod
    def _draft_index(state: Mapping[str, Any], draft_id: str) -> int:
        for index, item in enumerate(state.get("drafts", [])):
            if str(item.get("id", "")) == draft_id:
                return index
        return -1

    def read_draft(self, draft_id: Any) -> SocialResult:
        draft_id = str(draft_id or "").strip()
        with self._lock:
            state = self._load()
            index = self._draft_index(state, draft_id)
            if index < 0:
                return SocialResult("DRAFT_NOT_FOUND")
            return SocialResult("OK", {"draft": copy.deepcopy(state["drafts"][index])})

    def update_draft(self, draft_id: Any, incoming: Mapping[str, Any] | None) -> SocialResult:
        draft_id = str(draft_id or "").strip()
        data = dict(incoming or {})
        allowed = {"headline", "detail", "eyebrow", "broadcast_link", "sponsor_id", "default_hashtags", "include_broadcast_link"}
        unknown = sorted(set(data) - allowed)
        if unknown:
            return SocialResult("DRAFT_UPDATE_INVALID", {"unknown": unknown})
        with self._lock:
            state = self._load()
            index = self._draft_index(state, draft_id)
            if index < 0:
                return SocialResult("DRAFT_NOT_FOUND")
            draft = state["drafts"][index]
            if draft.get("status") in {"PUBLISHED", "DELETED"}:
                return SocialResult("DRAFT_IMMUTABLE")
            for key in ("headline", "detail", "eyebrow"):
                if key in data:
                    draft["content"][key] = str(data[key]).strip()[:500 if key == "detail" else 160]
            if "broadcast_link" in data:
                draft["broadcast_link"] = str(data["broadcast_link"]).strip()[:500]
            if "default_hashtags" in data:
                values = data["default_hashtags"]
                if not isinstance(values, list):
                    return SocialResult("HASHTAGS_INVALID")
                draft["settings"]["default_hashtags"] = [f"#{re.sub(r'[^A-Za-z0-9_]', '', str(value).lstrip('#'))}" for value in values[:12] if re.sub(r"[^A-Za-z0-9_]", "", str(value).lstrip("#"))]
            if "include_broadcast_link" in data:
                draft["settings"]["include_broadcast_link"] = bool(data["include_broadcast_link"])
            if "sponsor_id" in data:
                sponsor, suppressed = self._select_sponsor(state, str(draft["kind"]), str(data["sponsor_id"]).strip())
                draft["sponsor"] = sponsor
                draft["sponsor_suppressed"] = suppressed
            draft["status"] = "DRAFT"
            draft["approved_at"] = 0
            draft["approved_by"] = ""
            draft["updated_at"] = int(self._clock())
            draft["platform_copy"] = {
                account_id: self._platform_text(draft, str(account.get("platform")), int(account.get("text_limit", 280)))
                for account_id, account in state["accounts"].items()
                if account.get("enabled", True)
            }
            self._render_cards(draft, state["accounts"])
            self._audit(state, "DRAFT_UPDATED", draft_id=draft_id)
            self._write(state)
        return SocialResult("DRAFT_UPDATED", {"draft": copy.deepcopy(draft)})

    def approve_draft(self, draft_id: Any, *, operator: Any, confirmation: Any) -> SocialResult:
        draft_id = str(draft_id or "").strip()
        if str(confirmation or "") != "APPROVE SOCIAL POST":
            return SocialResult("APPROVAL_CONFIRMATION_REQUIRED")
        operator = str(operator or "operator").strip()[:120]
        with self._lock:
            state = self._load()
            index = self._draft_index(state, draft_id)
            if index < 0:
                return SocialResult("DRAFT_NOT_FOUND")
            draft = state["drafts"][index]
            if draft.get("status") not in {"DRAFT", "PARTIAL", "FAILED", "CORRECTION"}:
                return SocialResult("DRAFT_NOT_APPROVABLE")
            if not draft.get("cards"):
                return SocialResult("CARD_RENDER_REQUIRED", {"errors": draft.get("card_errors", {})})
            draft["status"] = "APPROVED"
            draft["approved_at"] = int(self._clock())
            draft["approved_by"] = operator
            draft["updated_at"] = int(self._clock())
            self._audit(state, "DRAFT_APPROVED", draft_id=draft_id, operator=operator)
            self._write(state)
        return SocialResult("DRAFT_APPROVED", {"draft": copy.deepcopy(draft)})

    def _publish_one(self, account: Mapping[str, Any], draft: Mapping[str, Any]) -> PlatformResult:
        platform = str(account.get("platform", ""))
        adapter = self.adapters.get(platform)
        if adapter is None:
            return PlatformResult("ADAPTER_UNAVAILABLE")
        card = draft.get("cards", {}).get(platform, {})
        path = Path(str(card.get("path", "")))
        text = str(draft.get("platform_copy", {}).get(str(account.get("id", ""))) or self._platform_text(draft, platform, int(account.get("text_limit", 280))))
        return adapter.publish(account, text=text, image_path=path)

    def publish_draft(self, draft_id: Any, *, account_ids: list[Any] | None = None) -> SocialResult:
        draft_id = str(draft_id or "").strip()
        with self._lock:
            state = self._load()
            index = self._draft_index(state, draft_id)
            if index < 0:
                return SocialResult("DRAFT_NOT_FOUND")
            draft = copy.deepcopy(state["drafts"][index])
            if draft.get("status") not in {"APPROVED", "PARTIAL", "FAILED"}:
                return SocialResult("DRAFT_NOT_APPROVED")
            selected = {str(value) for value in account_ids or []}
            accounts = [copy.deepcopy(account) for account_id, account in state["accounts"].items() if account.get("enabled", True) and (not selected or account_id in selected)]
        if not accounts:
            return SocialResult("NO_ENABLED_ACCOUNTS")

        results: dict[str, Any] = {}
        for account in accounts:
            account_id = str(account["id"])
            result = self._publish_one(account, draft)
            results[account_id] = {
                "code": result.code,
                "post_id": result.post_id,
                "url": result.url,
                "retryable": result.retryable,
                "retry_after": result.retry_after,
                "details": copy.deepcopy(result.details),
            }

        with self._lock:
            state = self._load()
            index = self._draft_index(state, draft_id)
            if index < 0:
                return SocialResult("DRAFT_NOT_FOUND")
            stored = state["drafts"][index]
            succeeded = 0
            for account in accounts:
                account_id = str(account["id"])
                item = results[account_id]
                attempt = {
                    "id": f"ATT-{int(self._clock() * 1000)}-{account_id}",
                    "account_id": account_id,
                    "platform": account.get("platform", ""),
                    "code": item["code"],
                    "retryable": item["retryable"],
                    "retry_after": item["retry_after"],
                    "created_at": int(self._clock()),
                }
                stored["attempts"] = (list(stored.get("attempts") or []) + [attempt])[-100:]
                if item["code"] == "PUBLISHED":
                    succeeded += 1
                    stored["publications"][account_id] = {
                        "account_id": account_id,
                        "platform": account.get("platform", ""),
                        "post_id": item["post_id"],
                        "url": item["url"],
                        "published_at": int(self._clock()),
                        "retracted_at": 0,
                    }
                self._audit(state, "PUBLISH_ATTEMPT", draft_id=draft_id, account_id=account_id, code=item["code"], retryable=item["retryable"])
            if succeeded == len(accounts):
                stored["status"] = "PUBLISHED"
                code = "PUBLISHED"
            elif succeeded:
                stored["status"] = "PARTIAL"
                code = "PARTIALLY_PUBLISHED"
            else:
                stored["status"] = "FAILED"
                code = "PUBLISH_FAILED"
            stored["updated_at"] = int(self._clock())
            self._write(state)
        return SocialResult(code, {"draft": copy.deepcopy(stored), "results": results})

    def process_auto_queue(self, *, limit: int = 10) -> SocialResult:
        limit = max(1, min(25, int(limit)))
        with self._lock:
            state = self._load()
            if not state["settings"].get("allow_auto_publish", False):
                return SocialResult("AUTO_PUBLISH_DISABLED")
            auto_accounts = [account_id for account_id, account in state["accounts"].items() if account.get("enabled", True) and account.get("auto_publish", False)]
            candidates = [copy.deepcopy(draft) for draft in state["drafts"] if draft.get("status") == "APPROVED"][:limit]
        processed = []
        for draft in candidates:
            result = self.publish_draft(draft["id"], account_ids=auto_accounts)
            processed.append({"draft_id": draft["id"], "code": result.code})
        return SocialResult("AUTO_QUEUE_PROCESSED", {"processed": processed})

    def create_correction(self, draft_id: Any, incoming: Mapping[str, Any] | None) -> SocialResult:
        draft_id = str(draft_id or "").strip()
        data = dict(incoming or {})
        with self._lock:
            state = self._load()
            index = self._draft_index(state, draft_id)
            if index < 0:
                return SocialResult("DRAFT_NOT_FOUND")
            original = state["drafts"][index]
            if not original.get("publications"):
                return SocialResult("CORRECTION_REQUIRES_PUBLICATION")
            corrected = copy.deepcopy(original)
            corrected_id = f"SOC-{int(self._clock())}-{len(state['drafts']) % 1000:03d}"
            corrected.update({
                "id": corrected_id,
                "status": "CORRECTION",
                "revision": int(original.get("revision", 1) or 1) + 1,
                "replaces_draft_id": draft_id,
                "created_at": int(self._clock()),
                "updated_at": int(self._clock()),
                "approved_at": 0,
                "approved_by": "",
                "publications": {},
                "attempts": [],
            })
            for key in ("headline", "detail", "eyebrow"):
                if key in data:
                    corrected["content"][key] = str(data[key]).strip()[:500 if key == "detail" else 160]
            corrected["platform_copy"] = {
                account_id: self._platform_text(corrected, str(account.get("platform")), int(account.get("text_limit", 280)))
                for account_id, account in state["accounts"].items()
                if account.get("enabled", True)
            }
            self._render_cards(corrected, state["accounts"])
            original["status"] = "CORRECTION_PENDING"
            state["drafts"] = (state["drafts"] + [corrected])[-self.MAX_DRAFTS :]
            self._audit(state, "CORRECTION_CREATED", draft_id=corrected_id, replaces_draft_id=draft_id)
            self._write(state)
        return SocialResult("CORRECTION_CREATED", {"draft": copy.deepcopy(corrected)})

    def retract_publication(self, draft_id: Any, account_id: Any, confirmation: Any) -> SocialResult:
        draft_id = str(draft_id or "").strip()
        account_id = str(account_id or "").strip()
        if str(confirmation or "") != "RETRACT SOCIAL POST":
            return SocialResult("RETRACT_CONFIRMATION_REQUIRED")
        with self._lock:
            state = self._load()
            index = self._draft_index(state, draft_id)
            if index < 0:
                return SocialResult("DRAFT_NOT_FOUND")
            draft = copy.deepcopy(state["drafts"][index])
            publication = copy.deepcopy(draft.get("publications", {}).get(account_id))
            account = copy.deepcopy(state["accounts"].get(account_id))
        if not publication:
            return SocialResult("PUBLICATION_NOT_FOUND")
        if not account:
            return SocialResult("ACCOUNT_NOT_FOUND")
        adapter = self.adapters.get(str(account.get("platform", "")))
        if adapter is None:
            return SocialResult("ADAPTER_UNAVAILABLE")
        result = adapter.delete(account, post_id=str(publication.get("post_id", "")))
        if not result.ok:
            return SocialResult("RETRACT_FAILED", {"code": result.code, "retryable": result.retryable})
        with self._lock:
            state = self._load()
            index = self._draft_index(state, draft_id)
            if index < 0:
                return SocialResult("DRAFT_NOT_FOUND")
            stored = state["drafts"][index]
            stored["publications"][account_id]["retracted_at"] = int(self._clock())
            self._audit(state, "PUBLICATION_RETRACTED", draft_id=draft_id, account_id=account_id, post_id=publication.get("post_id", ""))
            self._write(state)
        return SocialResult("PUBLICATION_RETRACTED", {"draft": copy.deepcopy(stored), "account_id": account_id})

    def delete_draft(self, draft_id: Any, confirmation: Any) -> SocialResult:
        draft_id = str(draft_id or "").strip()
        if str(confirmation or "") != "DELETE SOCIAL DRAFT":
            return SocialResult("DRAFT_DELETE_CONFIRMATION_REQUIRED")
        with self._lock:
            state = self._load()
            index = self._draft_index(state, draft_id)
            if index < 0:
                return SocialResult("DRAFT_NOT_FOUND")
            draft = state["drafts"][index]
            if any(not int(item.get("retracted_at", 0) or 0) for item in draft.get("publications", {}).values()):
                return SocialResult("ACTIVE_PUBLICATION_EXISTS")
            draft["status"] = "DELETED"
            draft["updated_at"] = int(self._clock())
            self._audit(state, "DRAFT_DELETED", draft_id=draft_id)
            self._write(state)
        return SocialResult("DRAFT_DELETED", {"draft_id": draft_id})

    def card_path(self, draft_id: Any, platform: Any) -> SocialResult:
        result = self.read_draft(draft_id)
        if not result.ok:
            return result
        platform = str(platform or "").lower()
        card = result.data["draft"].get("cards", {}).get(platform)
        if not isinstance(card, Mapping):
            return SocialResult("CARD_NOT_FOUND")
        path = Path(str(card.get("path", "")))
        if not path.is_file():
            return SocialResult("CARD_NOT_FOUND")
        return SocialResult("OK", {"path": str(path), "filename": path.name})

    def postgame_handoff(self) -> SocialResult:
        state = copy.deepcopy(dict(self._load_broadcast_state()))
        events = [copy.deepcopy(event) for event in state.get("events", []) if isinstance(event, Mapping) and not event.get("undone")]
        plays = [copy.deepcopy(play) for play in state.get("plays", []) if isinstance(play, Mapping) and not play.get("undone")]
        return SocialResult(
            "OK",
            {
                "handoff": {
                    "broadcast_id": str(state.get("broadcast_id", "")),
                    "home_team": str(state.get("home_team", "")),
                    "visitor_team": str(state.get("visitor_team", "")),
                    "home_score": int(state.get("home_score", 0) or 0),
                    "visitor_score": int(state.get("visitor_score", 0) or 0),
                    "halftime_score": copy.deepcopy(state.get("halftime_score", {})) if isinstance(state.get("halftime_score"), Mapping) else {},
                    "events": events,
                    "plays": plays,
                    "statistics_available": bool(state.get("statistician_enabled")),
                    "generated_at": int(self._clock()),
                    "grounding_policy": "Use only recorded events and available statistics; omit missing data.",
                }
            },
        )
