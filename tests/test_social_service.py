from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from social_platforms import PlatformResult
from social_service import SocialPublishingService


class Renderer:
    def __init__(self, root: Path):
        self.root = root
        self.calls = []

    def render(self, draft, *, platform, theme):
        self.calls.append((draft["id"], platform, theme.get("id")))
        path = self.root / f"{draft['id']}-{platform}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"png")
        return {
            "path": str(path),
            "filename": path.name,
            "platform": platform,
            "width": 1600 if platform == "x" else 1200,
            "height": 900 if platform == "x" else 630,
            "theme_id": theme.get("id", ""),
        }


class Adapter:
    def __init__(self, platform: str, results=None):
        self.platform = platform
        self.results = list(results or [PlatformResult("PUBLISHED", post_id=f"{platform}-1")])
        self.published = []
        self.deleted = []

    def publish(self, account, *, text, image_path):
        self.published.append((dict(account), text, Path(image_path)))
        return self.results.pop(0) if self.results else PlatformResult("PUBLISHED", post_id=f"{self.platform}-next")

    def delete(self, account, *, post_id):
        self.deleted.append((dict(account), post_id))
        return PlatformResult("DELETED", post_id=post_id)


def broadcast_state() -> dict:
    event = {
        "id": "EV-1",
        "event": "TD",
        "description": "12-yard touchdown run by Alex Morgan",
        "quarter": "2",
        "broadcast_id": "GAME-1",
        "automation": {
            "player_id": "player-1",
            "player_name": "Alex Morgan",
            "player_number": "12",
        },
        "after": {"home_score": 14, "visitor_score": 7},
    }
    return {
        "broadcast_id": "GAME-1",
        "home_team": "Home School",
        "visitor_team": "Visitor School",
        "home_score": 14,
        "visitor_score": 7,
        "quarter": "2",
        "home_identity": {
            "name": "Home School",
            "logo": "/school-logos/home/round-master.png",
            "primary_color": "#B5121B",
        },
        "visitor_identity": {
            "name": "Visitor School",
            "logo": "/school-logos/visitor/round-master.png",
            "primary_color": "#223366",
        },
        "events": [event],
        "last_event": event,
        "plays": [{"play_id": "P-1", "event_id": "EV-1", "result": event["description"]}],
        "statistician_enabled": False,
    }


def active_sponsor(sponsor_id: str):
    if sponsor_id != "sponsor-1":
        return None
    return {
        "id": "sponsor-1",
        "name": "Local Bank",
        "logo_url": "/asset-files/bank.png",
        "lead_ins": ["Touchdown presented by"],
        "active": True,
    }


def service(tmp_path: Path, *, x_results=None, facebook_results=None):
    x = Adapter("x", x_results)
    facebook = Adapter("facebook", facebook_results)
    renderer = Renderer(tmp_path / "cards")
    state = broadcast_state()
    instance = SocialPublishingService(
        state_file=tmp_path / "social.json",
        renderer=renderer,
        adapters={"x": x, "facebook": facebook},
        load_broadcast_state=lambda: state,
        load_config=lambda: {
            "organization": {
                "name": "School Radio Network",
                "short_name": "SRN",
                "logo_path": "static/logo.png",
            },
            "social": {"website": "https://school.example/live"},
        },
        load_rosters=lambda: [
            {
                "id": "roster-1",
                "players": [
                    {
                        "id": "player-1",
                        "number": "12",
                        "display_name": "Alex Morgan",
                        "headshot": "/roster-headshots/alex.png",
                    }
                ],
            }
        ],
        load_sponsors=lambda: [],
        active_sponsor_by_id=active_sponsor,
        get_theme_status=lambda: SimpleNamespace(
            data={
                "theme": {
                    "active": {
                        "id": "modern_network",
                        "tokens": {
                            "primary_color": "#B5121B",
                            "secondary_color": "#111111",
                        },
                    }
                }
            }
        ),
        clock=lambda: 1_700_000_000,
    )
    return instance, renderer, x, facebook, state


def account_payload(platform="x"):
    payload = {
        "id": f"{platform}-primary",
        "platform": platform,
        "display_name": platform.upper(),
        "credential_ref": "CSRN_X_ACCESS_TOKEN" if platform == "x" else "CSRN_FACEBOOK_PAGE_ACCESS_TOKEN",
    }
    if platform == "facebook":
        payload["page_id"] = "page-1"
    return payload


def test_raw_credentials_are_rejected(tmp_path: Path) -> None:
    svc, *_ = service(tmp_path)
    result = svc.configure_account({**account_payload(), "access_token": "secret"})
    assert result.code == "RAW_CREDENTIAL_REJECTED"
    assert "access_token" in result.data["fields"]


def test_account_saves_reference_not_secret(tmp_path: Path) -> None:
    svc, *_ = service(tmp_path)
    result = svc.configure_account(account_payload())
    assert result.code == "ACCOUNT_SAVED"
    assert result.data["account"]["credential_ref"] == "CSRN_X_ACCESS_TOKEN"
    assert result.data["account"]["credential_configured"] is True


def test_facebook_requires_page_id(tmp_path: Path) -> None:
    svc, *_ = service(tmp_path)
    payload = account_payload("facebook")
    payload.pop("page_id")
    assert svc.configure_account(payload).code == "PAGE_ID_REQUIRED"


def test_remove_account_requires_exact_confirmation(tmp_path: Path) -> None:
    svc, *_ = service(tmp_path)
    svc.configure_account(account_payload())
    assert svc.remove_account("x-primary", "remove").code == "ACCOUNT_REMOVE_CONFIRMATION_REQUIRED"
    assert svc.remove_account("x-primary", "REMOVE SOCIAL ACCOUNT").code == "ACCOUNT_REMOVED"


def test_settings_reject_unknown_keys(tmp_path: Path) -> None:
    svc, *_ = service(tmp_path)
    assert svc.update_settings({"token": "x"}).code == "SETTINGS_INVALID"


def test_sponsor_rules_require_active_sponsor(tmp_path: Path) -> None:
    svc, *_ = service(tmp_path)
    assert svc.update_sponsor_rules({"event_sponsors": {"TOUCHDOWN": "missing"}, "rotation": []}).code == "SPONSOR_NOT_ACTIVE"


def test_emergency_kind_cannot_have_sponsor_rule(tmp_path: Path) -> None:
    svc, *_ = service(tmp_path)
    result = svc.update_sponsor_rules({"event_sponsors": {"WEATHER_EMERGENCY": "sponsor-1"}, "rotation": []})
    assert result.code == "SPONSOR_RULE_KIND_INVALID"


def test_touchdown_draft_uses_recorded_event_player_and_theme(tmp_path: Path) -> None:
    svc, renderer, *_ = service(tmp_path)
    result = svc.create_draft("TOUCHDOWN", event_id="EV-1")
    assert result.code == "DRAFT_CREATED"
    draft = result.data["draft"]
    assert draft["source_event_id"] == "EV-1"
    assert draft["content"]["detail"] == "12-yard touchdown run by Alex Morgan"
    assert draft["player"]["name"] == "Alex Morgan"
    assert draft["player"]["headshot"].endswith("alex.png")
    assert draft["theme"]["id"] == "modern_network"
    assert {item[1] for item in renderer.calls} == {"x", "facebook"}


def test_duplicate_event_draft_is_blocked(tmp_path: Path) -> None:
    svc, *_ = service(tmp_path)
    svc.create_draft("TOUCHDOWN", event_id="EV-1")
    assert svc.create_draft("TOUCHDOWN", event_id="EV-1").code == "DUPLICATE_DRAFT"


def test_recorded_event_kind_mismatch_is_blocked(tmp_path: Path) -> None:
    svc, *_ = service(tmp_path)
    result = svc.create_draft("TURNOVER", event_id="EV-1")
    assert result.code == "EVENT_KIND_MISMATCH"
    assert result.data["expected_kind"] == "TOUCHDOWN"


def test_emergency_requires_grounded_message_and_suppresses_sponsor(tmp_path: Path) -> None:
    svc, *_ = service(tmp_path)
    assert svc.create_draft("WEATHER_EMERGENCY").code == "GROUNDED_MESSAGE_REQUIRED"
    result = svc.create_draft(
        "WEATHER_EMERGENCY",
        payload={"message": "Tornado Warning for the venue until 8:45 PM.", "sponsor_id": "sponsor-1"},
    )
    draft = result.data["draft"]
    assert draft["sponsor"] == {}
    assert draft["sponsor_suppressed"] is True


def test_event_sponsor_is_applied_to_non_emergency_draft(tmp_path: Path) -> None:
    svc, *_ = service(tmp_path)
    svc.update_sponsor_rules({"event_sponsors": {"TOUCHDOWN": "sponsor-1"}, "rotation": []})
    draft = svc.create_draft("TOUCHDOWN", event_id="EV-1").data["draft"]
    assert draft["sponsor"]["name"] == "Local Bank"
    assert draft["sponsor_suppressed"] is False


def test_draft_approval_requires_exact_phrase(tmp_path: Path) -> None:
    svc, *_ = service(tmp_path)
    draft_id = svc.create_draft("TOUCHDOWN", event_id="EV-1").data["draft"]["id"]
    assert svc.approve_draft(draft_id, operator="Alex", confirmation="yes").code == "APPROVAL_CONFIRMATION_REQUIRED"
    approved = svc.approve_draft(draft_id, operator="Alex", confirmation="APPROVE SOCIAL POST")
    assert approved.code == "DRAFT_APPROVED"
    assert approved.data["draft"]["approved_by"] == "Alex"


def test_publish_requires_approval(tmp_path: Path) -> None:
    svc, *_ = service(tmp_path)
    svc.configure_account(account_payload())
    draft_id = svc.create_draft("TOUCHDOWN", event_id="EV-1").data["draft"]["id"]
    assert svc.publish_draft(draft_id).code == "DRAFT_NOT_APPROVED"


def test_approved_draft_publishes_and_records_audit(tmp_path: Path) -> None:
    svc, _, x, *_ = service(tmp_path)
    svc.configure_account(account_payload())
    draft_id = svc.create_draft("TOUCHDOWN", event_id="EV-1").data["draft"]["id"]
    svc.approve_draft(draft_id, operator="Alex", confirmation="APPROVE SOCIAL POST")
    result = svc.publish_draft(draft_id)
    assert result.code == "PUBLISHED"
    assert result.data["draft"]["publications"]["x-primary"]["post_id"] == "x-1"
    assert len(x.published) == 1
    assert any(item["action"] == "PUBLISH_ATTEMPT" for item in svc.status().data["social"]["audit"])


def test_partial_publish_preserves_success_and_retryable_failure(tmp_path: Path) -> None:
    svc, _, _, _, _ = service(
        tmp_path,
        facebook_results=[PlatformResult("POST_FAILED", retryable=True, retry_after=30)],
    )
    svc.configure_account(account_payload("x"))
    svc.configure_account(account_payload("facebook"))
    draft_id = svc.create_draft("TOUCHDOWN", event_id="EV-1").data["draft"]["id"]
    svc.approve_draft(draft_id, operator="Alex", confirmation="APPROVE SOCIAL POST")
    result = svc.publish_draft(draft_id)
    assert result.code == "PARTIALLY_PUBLISHED"
    assert result.data["results"]["facebook-primary"]["retryable"] is True
    assert result.data["draft"]["status"] == "PARTIAL"


def test_explicit_empty_account_selection_does_not_publish_all(tmp_path: Path) -> None:
    svc, _, x, *_ = service(tmp_path)
    svc.configure_account(account_payload())
    draft_id = svc.create_draft("TOUCHDOWN", event_id="EV-1").data["draft"]["id"]
    svc.approve_draft(draft_id, operator="Alex", confirmation="APPROVE SOCIAL POST")
    assert svc.publish_draft(draft_id, account_ids=[]).code == "NO_ENABLED_ACCOUNTS"
    assert x.published == []


def test_auto_queue_requires_global_and_account_opt_in(tmp_path: Path) -> None:
    svc, *_ = service(tmp_path)
    assert svc.process_auto_queue().code == "AUTO_PUBLISH_DISABLED"
    svc.update_settings({"allow_auto_publish": True})
    svc.configure_account(account_payload())
    assert svc.process_auto_queue().code == "NO_AUTO_PUBLISH_ACCOUNTS"


def test_auto_draft_event_handoff_is_disabled_by_default(tmp_path: Path) -> None:
    svc, *_ , state = service(tmp_path)
    event = state["events"][0]
    assert svc.queue_event(event).code == "AUTO_DRAFT_DISABLED"
    svc.update_settings({"auto_create_drafts": True})
    assert svc.queue_event(event).code == "EVENT_QUEUED"


def test_eligible_events_excludes_already_queued_event(tmp_path: Path) -> None:
    svc, *_ = service(tmp_path)
    assert len(svc.eligible_events().data["events"]) == 1
    svc.create_draft("TOUCHDOWN", event_id="EV-1")
    assert svc.eligible_events().data["events"] == []


def test_correction_requires_published_original(tmp_path: Path) -> None:
    svc, *_ = service(tmp_path)
    draft_id = svc.create_draft("TOUCHDOWN", event_id="EV-1").data["draft"]["id"]
    assert svc.create_correction(draft_id, {"detail": "corrected"}).code == "CORRECTION_REQUIRES_PUBLICATION"


def test_published_post_can_create_correction_and_retract(tmp_path: Path) -> None:
    svc, _, x, *_ = service(tmp_path)
    svc.configure_account(account_payload())
    draft_id = svc.create_draft("TOUCHDOWN", event_id="EV-1").data["draft"]["id"]
    svc.approve_draft(draft_id, operator="Alex", confirmation="APPROVE SOCIAL POST")
    svc.publish_draft(draft_id)
    correction = svc.create_correction(draft_id, {"detail": "Corrected touchdown detail"})
    assert correction.code == "CORRECTION_CREATED"
    assert correction.data["draft"]["replaces_draft_id"] == draft_id
    assert svc.retract_publication(draft_id, "x-primary", "wrong").code == "RETRACT_CONFIRMATION_REQUIRED"
    retracted = svc.retract_publication(draft_id, "x-primary", "RETRACT SOCIAL POST")
    assert retracted.code == "PUBLICATION_RETRACTED"
    assert x.deleted[0][1] == "x-1"


def test_active_publication_blocks_draft_deletion(tmp_path: Path) -> None:
    svc, *_ = service(tmp_path)
    svc.configure_account(account_payload())
    draft_id = svc.create_draft("TOUCHDOWN", event_id="EV-1").data["draft"]["id"]
    svc.approve_draft(draft_id, operator="Alex", confirmation="APPROVE SOCIAL POST")
    svc.publish_draft(draft_id)
    assert svc.delete_draft(draft_id, "DELETE SOCIAL DRAFT").code == "ACTIVE_PUBLICATION_EXISTS"


def test_postgame_handoff_contains_only_recorded_game_data(tmp_path: Path) -> None:
    svc, *_ = service(tmp_path)
    handoff = svc.postgame_handoff().data["handoff"]
    assert handoff["home_score"] == 14
    assert handoff["visitor_score"] == 7
    assert handoff["events"][0]["id"] == "EV-1"
    assert handoff["grounding_policy"].startswith("Use only recorded events")
    assert handoff["statistics_available"] is False
