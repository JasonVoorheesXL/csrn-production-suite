from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from social_publishing_service import SocialPublishingService


@dataclass(frozen=True)
class StubPublishResult:
    code: str
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.code == "OK"


class StubPublisher:
    def __init__(self, platform: str, result: StubPublishResult | None = None) -> None:
        self.platform = platform
        self.result = result or StubPublishResult(
            "OK",
            {"platform": platform, "external_id": f"{platform}-1"},
        )
        self.calls: list[dict[str, Any]] = []

    def status(self) -> dict[str, Any]:
        return {
            "platform": self.platform,
            "configured": self.result.code != "PLATFORM_NOT_CONFIGURED",
            "supports_text": True,
            "supports_image": True,
        }

    def publish(self, *, text: str, media_path: Path | None = None) -> StubPublishResult:
        self.calls.append({"text": text, "media_path": media_path})
        return self.result


class StubRenderer:
    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.contexts: list[dict[str, Any]] = []

    def render(self, context: dict[str, Any], post_id: str) -> Path:
        self.contexts.append(dict(context))
        self.output_dir.mkdir(parents=True, exist_ok=True)
        output = self.output_dir / f"{post_id}.png"
        output.write_bytes(b"card")
        return output


class StubSponsorService:
    def __init__(self) -> None:
        self.active = {
            "sponsor-1": {
                "id": "sponsor-1",
                "name": "Local Sponsor",
                "logo_url": "/asset-files/sponsor.png",
            }
        }

    def active_sponsor_by_id(self, sponsor_id: str):
        return self.active.get(sponsor_id)


def state(event_code: str = "TD") -> dict[str, Any]:
    return {
        "broadcast_id": "broadcast-1",
        "home_team": "Caledonia",
        "visitor_team": "Visitor",
        "home_school_id": "school-home",
        "visitor_school_id": "school-visitor",
        "home_score": 21,
        "visitor_score": 14,
        "quarter": "3",
        "home_identity": {
            "primary_color": "#B5121B",
            "secondary_color": "#111111",
        },
        "events": [
            {
                "id": "event-1",
                "broadcast_id": "broadcast-1",
                "team": "home",
                "team_name": "Caledonia",
                "event": event_code,
                "label": "Touchdown" if event_code == "TD" else "Penalty",
                "description": "Jason Runner touchdown run",
                "quarter": "3",
                "after": {"home_score": 21, "visitor_score": 14},
                "automation": {
                    "player_id": "player-1",
                    "player_name": "Jason Runner",
                    "player_number": "7",
                    "turnover": event_code == "TURNOVER",
                },
            }
        ],
    }


def build_service(tmp_path: Path, *, event_code: str = "TD"):
    posts: list[dict[str, Any]] = []
    current_state = state(event_code)
    cards_dir = tmp_path / "cards"
    renderer = StubRenderer(cards_dir)
    publishers = {
        "x": StubPublisher("x"),
        "facebook": StubPublisher("facebook"),
    }
    service = SocialPublishingService(
        load_posts=lambda: [dict(item) for item in posts],
        save_posts=lambda items: posts.__setitem__(slice(None), [dict(item) for item in items]),
        load_state=lambda: current_state,
        load_rosters=lambda: [
            {
                "school_id": "school-home",
                "players": [
                    {
                        "id": "player-1",
                        "preferred_name": "Jason Runner",
                        "number": "7",
                        "headshot": "/roster-headshots/player.png",
                    }
                ],
            }
        ],
        sponsor_service=StubSponsorService(),
        renderer=renderer,
        cards_dir=cards_dir,
        publishers=publishers,
        clock=lambda: 1000.0,
        token_factory=lambda: "token",
    )
    return service, posts, renderer, publishers


def test_create_event_draft_includes_player_sponsor_score_and_card(tmp_path: Path) -> None:
    service, posts, renderer, _ = build_service(tmp_path)
    result = service.create_event_draft(
        {"event_id": "event-1", "sponsor_id": "sponsor-1"}
    )
    assert result.ok is True
    post = result.data["post"]
    assert post["status"] == "draft"
    assert post["platforms"] == ["x", "facebook"]
    assert post["context"]["player_name"] == "Jason Runner"
    assert post["context"]["sponsor_name"] == "Local Sponsor"
    assert post["context"]["home_score"] == 21
    assert post["card_file"] == "social-1000-token.png"
    assert posts[0]["id"] == "social-1000-token"
    assert renderer.contexts[0]["player_headshot"] == "/roster-headshots/player.png"


def test_create_event_draft_rejects_noneligible_event(tmp_path: Path) -> None:
    service, _, _, _ = build_service(tmp_path, event_code="PENALTY")
    result = service.create_event_draft({"event_id": "event-1"})
    assert result.code == "EVENT_NOT_SOCIAL_ELIGIBLE"


def test_create_event_draft_blocks_duplicate_without_replacement(tmp_path: Path) -> None:
    service, _, _, _ = build_service(tmp_path)
    assert service.create_event_draft({"event_id": "event-1"}).ok
    result = service.create_event_draft({"event_id": "event-1"})
    assert result.code == "SOCIAL_DRAFT_EXISTS"


def test_create_event_draft_rejects_inactive_sponsor(tmp_path: Path) -> None:
    service, _, _, _ = build_service(tmp_path)
    result = service.create_event_draft(
        {"event_id": "event-1", "sponsor_id": "missing"}
    )
    assert result.code == "SPONSOR_NOT_ACTIVE"


def test_update_draft_edits_platform_text(tmp_path: Path) -> None:
    service, _, _, _ = build_service(tmp_path)
    post = service.create_event_draft({"event_id": "event-1"}).data["post"]
    result = service.update(
        post["id"],
        {"text": {"x": "Edited X post", "facebook": "Edited Facebook post"}},
    )
    assert result.ok
    assert result.data["post"]["text"]["x"] == "Edited X post"


def test_publish_requires_explicit_confirmation_and_approver(tmp_path: Path) -> None:
    service, _, _, _ = build_service(tmp_path)
    post_id = service.create_event_draft({"event_id": "event-1"}).data["post"]["id"]
    assert service.publish(post_id, {"approved_by": "Jason"}).code == "PUBLISH_CONFIRMATION_REQUIRED"
    assert service.publish(post_id, {"confirm": True}).code == "APPROVER_REQUIRED"


def test_publish_sends_card_to_both_platforms_and_records_audit(tmp_path: Path) -> None:
    service, posts, _, publishers = build_service(tmp_path)
    post_id = service.create_event_draft({"event_id": "event-1"}).data["post"]["id"]
    result = service.publish(post_id, {"confirm": True, "approved_by": "Jason"})
    assert result.ok
    assert result.data["published"] == 2
    assert result.data["post"]["status"] == "published"
    assert len(result.data["post"]["attempts"]) == 2
    assert publishers["x"].calls[0]["media_path"].is_file()
    assert posts[0]["approved_by"] == "Jason"


def test_partial_publish_records_failed_platform(tmp_path: Path) -> None:
    service, _, _, publishers = build_service(tmp_path)
    publishers["facebook"].result = StubPublishResult(
        "PUBLISH_REJECTED",
        {"platform": "facebook", "message": "Denied"},
    )
    post_id = service.create_event_draft({"event_id": "event-1"}).data["post"]["id"]
    result = service.publish(post_id, {"confirm": True, "approved_by": "Jason"})
    assert result.data["post"]["status"] == "partial"
    assert result.data["published"] == 1
    assert result.data["failed"] == 1


def test_retry_only_republishes_failed_platforms(tmp_path: Path) -> None:
    service, _, _, publishers = build_service(tmp_path)
    publishers["facebook"].result = StubPublishResult("PUBLISH_REJECTED")
    post_id = service.create_event_draft({"event_id": "event-1"}).data["post"]["id"]
    service.publish(post_id, {"confirm": True, "approved_by": "Jason"})
    publishers["facebook"].result = StubPublishResult(
        "OK", {"platform": "facebook", "external_id": "facebook-2"}
    )
    result = service.retry(post_id, {"approved_by": "Jason"})
    assert result.ok
    assert len(publishers["x"].calls) == 1
    assert len(publishers["facebook"].calls) == 2


def test_cancel_and_platform_status(tmp_path: Path) -> None:
    service, _, _, _ = build_service(tmp_path)
    post_id = service.create_event_draft({"event_id": "event-1"}).data["post"]["id"]
    cancelled = service.cancel(post_id)
    assert cancelled.data["post"]["status"] == "cancelled"
    status = service.platform_status().data
    assert status["preview_required"] is True
    assert {item["platform"] for item in status["platforms"]} == {"x", "facebook"}
