from __future__ import annotations

import copy
import re
import secrets
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping


Post = dict[str, Any]
LoadPosts = Callable[[], list[Post]]
SavePosts = Callable[[list[Post]], None]
LoadState = Callable[[], Mapping[str, Any]]
LoadRosters = Callable[[], list[dict[str, Any]]]


@dataclass(frozen=True)
class SocialPublishingResult:
    code: str
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.code == "OK"


class SocialPublishingService:
    """Preview-first social drafting, approval, publishing, and audit behavior."""

    SUPPORTED_PLATFORMS = ("x", "facebook")
    SUPPORTED_EVENT_CODES = {"TD", "TURNOVER", "FG"}

    def __init__(
        self,
        *,
        load_posts: LoadPosts,
        save_posts: SavePosts,
        load_state: LoadState,
        load_rosters: LoadRosters,
        sponsor_service: Any,
        renderer: Any,
        cards_dir: Path,
        publishers: Mapping[str, Any],
        clock: Callable[[], float] = time.time,
        token_factory: Callable[[], str] | None = None,
    ) -> None:
        self._load_posts = load_posts
        self._save_posts = save_posts
        self._load_state = load_state
        self._load_rosters = load_rosters
        self._sponsor_service = sponsor_service
        self._renderer = renderer
        self._cards_dir = Path(cards_dir)
        self._publishers = dict(publishers)
        self._clock = clock
        self._token_factory = token_factory or (lambda: secrets.token_hex(4))

    @staticmethod
    def _find(items: list[Post], post_id: str) -> Post | None:
        target = str(post_id or "").strip()
        return next(
            (item for item in items if str(item.get("id", "")) == target),
            None,
        )

    @staticmethod
    def _clean_platforms(value: Any) -> list[str]:
        if value is None:
            candidates = list(SocialPublishingService.SUPPORTED_PLATFORMS)
        elif isinstance(value, str):
            candidates = [part.strip().lower() for part in value.split(",")]
        elif isinstance(value, list):
            candidates = [str(part).strip().lower() for part in value]
        else:
            candidates = []
        result: list[str] = []
        for platform in candidates:
            if platform in SocialPublishingService.SUPPORTED_PLATFORMS and platform not in result:
                result.append(platform)
        return result

    @staticmethod
    def _trim_x(text: str) -> str:
        text = " ".join(str(text or "").split())
        return text if len(text) <= 280 else text[:277].rstrip() + "..."

    def platform_status(self) -> SocialPublishingResult:
        platforms: list[dict[str, Any]] = []
        for name in self.SUPPORTED_PLATFORMS:
            publisher = self._publishers.get(name)
            if publisher is None:
                platforms.append(
                    {
                        "platform": name,
                        "configured": False,
                        "supports_text": True,
                        "supports_image": False,
                    }
                )
            else:
                platforms.append(copy.deepcopy(dict(publisher.status())))
        return SocialPublishingResult(
            "OK",
            {
                "platforms": platforms,
                "preview_required": True,
                "automatic_publishing": False,
            },
        )

    def list_posts(
        self,
        *,
        status: str = "",
        broadcast_id: str = "",
        event_id: str = "",
    ) -> SocialPublishingResult:
        posts = self._load_posts()
        if status:
            posts = [item for item in posts if str(item.get("status", "")) == status]
        if broadcast_id:
            posts = [
                item
                for item in posts
                if str(item.get("broadcast_id", "")) == str(broadcast_id)
            ]
        if event_id:
            posts = [
                item for item in posts if str(item.get("event_id", "")) == str(event_id)
            ]
        posts.sort(key=lambda item: int(item.get("created_at", 0) or 0), reverse=True)
        return SocialPublishingResult("OK", {"posts": copy.deepcopy(posts)})

    def read(self, post_id: str) -> SocialPublishingResult:
        item = self._find(self._load_posts(), post_id)
        if item is None:
            return SocialPublishingResult("SOCIAL_POST_NOT_FOUND")
        return SocialPublishingResult("OK", {"post": copy.deepcopy(item)})

    def _resolve_event(self, event_id: str) -> tuple[dict[str, Any], dict[str, Any]] | None:
        state = copy.deepcopy(dict(self._load_state()))
        events = [
            event
            for event in list(state.get("events") or [])
            if isinstance(event, dict) and not event.get("undone")
        ]
        if event_id:
            event = next(
                (row for row in events if str(row.get("id", "")) == str(event_id)),
                None,
            )
        else:
            event = events[-1] if events else None
        return (state, copy.deepcopy(event)) if event else None

    def _resolve_player(
        self,
        state: Mapping[str, Any],
        event: Mapping[str, Any],
    ) -> dict[str, Any]:
        automation = event.get("automation", {})
        if not isinstance(automation, Mapping):
            automation = {}
        player_id = str(automation.get("player_id", "")).strip()
        team = str(event.get("team", ""))
        school_id = str(
            state.get("home_school_id") if team == "home" else state.get("visitor_school_id")
        )
        for roster in self._load_rosters():
            if school_id and str(roster.get("school_id", "")) != school_id:
                continue
            for player in list(roster.get("players") or []):
                if player_id and str(player.get("id", "")) == player_id:
                    return copy.deepcopy(player)
        return {
            "id": player_id,
            "preferred_name": str(automation.get("player_name", "")),
            "number": str(automation.get("player_number", "")),
            "headshot": "",
        }

    @staticmethod
    def _identity(state: Mapping[str, Any], team: str) -> dict[str, Any]:
        value = state.get("home_identity" if team == "home" else "visitor_identity", {})
        return copy.deepcopy(value) if isinstance(value, dict) else {}

    def _context(
        self,
        state: Mapping[str, Any],
        event: Mapping[str, Any],
        sponsor_id: str,
    ) -> dict[str, Any]:
        team = str(event.get("team", ""))
        after = event.get("after", {}) if isinstance(event.get("after"), Mapping) else {}
        player = self._resolve_player(state, event)
        sponsor = self._sponsor_service.active_sponsor_by_id(sponsor_id) if sponsor_id else None
        identity = self._identity(state, team)
        return {
            "event_id": str(event.get("id", "")),
            "event_code": str(event.get("event", "")),
            "event_label": str(event.get("label", "")),
            "description": str(event.get("description", "")),
            "team": team,
            "team_name": str(event.get("team_name", "")),
            "quarter": str(event.get("quarter", state.get("quarter", ""))),
            "home_team": str(state.get("home_team", "Home")),
            "visitor_team": str(state.get("visitor_team", "Visitor")),
            "home_score": int(after.get("home_score", state.get("home_score", 0)) or 0),
            "visitor_score": int(
                after.get("visitor_score", state.get("visitor_score", 0)) or 0
            ),
            "player_id": str(player.get("id", "")),
            "player_name": str(
                player.get("preferred_name")
                or " ".join(
                    part
                    for part in (
                        str(player.get("first_name", "")).strip(),
                        str(player.get("last_name", "")).strip(),
                    )
                    if part
                )
            ).strip(),
            "player_number": str(player.get("number", "")),
            "player_headshot": str(player.get("headshot", "")),
            "sponsor_id": str((sponsor or {}).get("id", "")),
            "sponsor_name": str((sponsor or {}).get("name", "")),
            "sponsor_logo": str((sponsor or {}).get("logo_url", "")),
            "primary_color": str(
                identity.get("primary_color")
                or identity.get("primary")
                or "#B5121B"
            ),
            "secondary_color": str(
                identity.get("secondary_color")
                or identity.get("secondary")
                or "#111111"
            ),
        }

    def _copy(self, context: Mapping[str, Any]) -> dict[str, str]:
        description = str(context.get("description", "")).strip()
        score = (
            f"{context.get('visitor_team')} {context.get('visitor_score')}, "
            f"{context.get('home_team')} {context.get('home_score')}"
        )
        sponsor = str(context.get("sponsor_name", "")).strip()
        sponsor_line = f" Presented by {sponsor}." if sponsor else ""
        x_text = self._trim_x(
            f"{context.get('event_label')}: {description}. {score}."
            f"{sponsor_line} #HighSchoolFootball"
        )
        facebook_text = (
            f"{context.get('event_label')} — {description}\n\n"
            f"Score: {score}\nQuarter: {context.get('quarter')}"
            f"{sponsor_line}"
        ).strip()
        return {"x": x_text, "facebook": facebook_text}

    def create_event_draft(
        self,
        incoming: Mapping[str, Any] | None,
    ) -> SocialPublishingResult:
        data = dict(incoming or {})
        resolved = self._resolve_event(str(data.get("event_id", "")))
        if resolved is None:
            return SocialPublishingResult("EVENT_NOT_FOUND")
        state, event = resolved
        event_code = str(event.get("event", "")).upper()
        automation = event.get("automation", {})
        derived_turnover = bool(
            isinstance(automation, Mapping) and automation.get("turnover")
        )
        if event_code not in self.SUPPORTED_EVENT_CODES and not derived_turnover:
            return SocialPublishingResult(
                "EVENT_NOT_SOCIAL_ELIGIBLE",
                {"event": copy.deepcopy(event)},
            )

        platforms = self._clean_platforms(data.get("platforms"))
        if not platforms:
            return SocialPublishingResult("SOCIAL_PLATFORM_REQUIRED")

        posts = self._load_posts()
        event_id = str(event.get("id", ""))
        existing = next(
            (
                item
                for item in posts
                if str(item.get("event_id", "")) == event_id
                and str(item.get("status", "")) != "cancelled"
            ),
            None,
        )
        if existing is not None and not bool(data.get("replace_existing", False)):
            return SocialPublishingResult(
                "SOCIAL_DRAFT_EXISTS",
                {"post": copy.deepcopy(existing)},
            )

        sponsor_id = str(data.get("sponsor_id", "")).strip()
        context = self._context(state, event, sponsor_id)
        if sponsor_id and not context.get("sponsor_id"):
            return SocialPublishingResult("SPONSOR_NOT_ACTIVE")

        now = int(self._clock())
        post_id = f"social-{now}-{self._token_factory()}"
        copy_by_platform = self._copy(context)
        record: Post = {
            "id": post_id,
            "kind": "event",
            "status": "draft",
            "broadcast_id": str(event.get("broadcast_id", state.get("broadcast_id", ""))),
            "event_id": event_id,
            "event_code": event_code,
            "platforms": platforms,
            "text": {platform: copy_by_platform[platform] for platform in platforms},
            "context": context,
            "card_file": "",
            "card_url": "",
            "approved_by": "",
            "approved_at": 0,
            "attempts": [],
            "created_at": now,
            "updated_at": now,
        }
        card_path = Path(self._renderer.render(context, post_id))
        record["card_file"] = card_path.name
        record["card_url"] = f"/social-cards/{card_path.name}"
        if existing is not None:
            posts = [item for item in posts if item is not existing]
            existing["status"] = "cancelled"
            existing["updated_at"] = now
            posts.append(existing)
        posts.append(record)
        self._save_posts(posts)
        return SocialPublishingResult("OK", {"post": copy.deepcopy(record)})

    def update(self, post_id: str, incoming: Mapping[str, Any] | None) -> SocialPublishingResult:
        data = dict(incoming or {})
        posts = self._load_posts()
        record = self._find(posts, post_id)
        if record is None:
            return SocialPublishingResult("SOCIAL_POST_NOT_FOUND")
        if str(record.get("status", "")) not in {"draft", "failed", "partial"}:
            return SocialPublishingResult("SOCIAL_POST_LOCKED")
        if "platforms" in data:
            platforms = self._clean_platforms(data.get("platforms"))
            if not platforms:
                return SocialPublishingResult("SOCIAL_PLATFORM_REQUIRED")
            record["platforms"] = platforms
        if "text" in data:
            incoming_text = data.get("text")
            if not isinstance(incoming_text, Mapping):
                return SocialPublishingResult("SOCIAL_TEXT_INVALID")
            text = dict(record.get("text") or {})
            for platform in record.get("platforms", []):
                if platform in incoming_text:
                    value = str(incoming_text.get(platform, "")).strip()
                    text[platform] = self._trim_x(value) if platform == "x" else value[:5000]
            record["text"] = text
        record["updated_at"] = int(self._clock())
        self._save_posts(posts)
        return SocialPublishingResult("OK", {"post": copy.deepcopy(record)})

    def _publish_platforms(
        self,
        record: Post,
        platforms: list[str],
        approved_by: str,
    ) -> SocialPublishingResult:
        now = int(self._clock())
        media_path = self._cards_dir / str(record.get("card_file", ""))
        attempts = list(record.get("attempts") or [])
        successes = 0
        failures = 0
        for platform in platforms:
            publisher = self._publishers.get(platform)
            if publisher is None:
                result_code = "PLATFORM_NOT_CONFIGURED"
                result_data: dict[str, Any] = {"platform": platform}
            else:
                result = publisher.publish(
                    text=str((record.get("text") or {}).get(platform, "")),
                    media_path=media_path if media_path.is_file() else None,
                )
                result_code = result.code
                result_data = copy.deepcopy(result.data)
            ok = result_code == "OK"
            successes += int(ok)
            failures += int(not ok)
            attempts.append(
                {
                    "platform": platform,
                    "status": "published" if ok else "failed",
                    "code": result_code,
                    "external_id": str(result_data.get("external_id", "")),
                    "message": str(result_data.get("message", ""))[:500],
                    "attempted_at": now,
                    "approved_by": approved_by,
                }
            )
        record["attempts"] = attempts[-100:]
        record["approved_by"] = approved_by
        record["approved_at"] = now
        record["updated_at"] = now
        record["status"] = (
            "published"
            if successes and not failures
            else "partial"
            if successes and failures
            else "failed"
        )
        return SocialPublishingResult(
            "OK",
            {
                "post": copy.deepcopy(record),
                "published": successes,
                "failed": failures,
            },
        )

    def publish(
        self,
        post_id: str,
        incoming: Mapping[str, Any] | None,
    ) -> SocialPublishingResult:
        data = dict(incoming or {})
        if data.get("confirm") is not True:
            return SocialPublishingResult("PUBLISH_CONFIRMATION_REQUIRED")
        approved_by = str(data.get("approved_by", "")).strip()
        if not approved_by:
            return SocialPublishingResult("APPROVER_REQUIRED")
        posts = self._load_posts()
        record = self._find(posts, post_id)
        if record is None:
            return SocialPublishingResult("SOCIAL_POST_NOT_FOUND")
        if str(record.get("status", "")) not in {"draft", "failed", "partial"}:
            return SocialPublishingResult("SOCIAL_POST_LOCKED")
        platforms = self._clean_platforms(data.get("platforms") or record.get("platforms"))
        if not platforms:
            return SocialPublishingResult("SOCIAL_PLATFORM_REQUIRED")
        result = self._publish_platforms(record, platforms, approved_by)
        self._save_posts(posts)
        return result

    def retry(
        self,
        post_id: str,
        incoming: Mapping[str, Any] | None,
    ) -> SocialPublishingResult:
        data = dict(incoming or {})
        posts = self._load_posts()
        record = self._find(posts, post_id)
        if record is None:
            return SocialPublishingResult("SOCIAL_POST_NOT_FOUND")
        failed_platforms = [
            str(item.get("platform", ""))
            for item in record.get("attempts", [])
            if str(item.get("status", "")) == "failed"
        ]
        data["platforms"] = list(dict.fromkeys(failed_platforms))
        data.setdefault("confirm", True)
        if not data["platforms"]:
            return SocialPublishingResult("NO_FAILED_PLATFORMS")
        return self.publish(post_id, data)

    def cancel(self, post_id: str) -> SocialPublishingResult:
        posts = self._load_posts()
        record = self._find(posts, post_id)
        if record is None:
            return SocialPublishingResult("SOCIAL_POST_NOT_FOUND")
        if str(record.get("status", "")) == "published":
            return SocialPublishingResult("SOCIAL_POST_LOCKED")
        record["status"] = "cancelled"
        record["updated_at"] = int(self._clock())
        self._save_posts(posts)
        return SocialPublishingResult("OK", {"post": copy.deepcopy(record)})
