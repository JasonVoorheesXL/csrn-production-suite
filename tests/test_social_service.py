from __future__ import annotations

import json
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
    platform = "facebook"

    def __init__(self, results=None):
        self.results = list(results or [PlatformResult("PUBLISHED", post_id="facebook-1")])
        self.published = []
        self.deleted = []

    def publish(self, account, *, text, image_path):
        self.published.append((dict(account), text, Path(image_path)))
        return self.results.pop(0) if self.results else PlatformResult("PUBLISHED", post_id="facebook-next")

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


def service(tmp_path: Path, *, facebook_results=None):
    facebook = Adapter(facebook_results)
    renderer = Renderer(tmp_path / "cards")
    state = broadcast_state()
    instance = SocialPublishingService(
        state_file=tmp_path / "social.json",
        renderer=renderer,
        adapters={"facebook": facebook},
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
                        "first_name": "Alex",
                        "last_name": "Morgan",
                        "preferred_name": "",
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
    return instance, renderer, facebook, state


def account_payload(account_id="facebook-primary", *, auto_publish=False):
    return {
        "id": account_id,
        "platform": "facebook",
        "display_name": "Facebook Page",
        "credential_ref": "CSRN_FACEBOOK_PAGE_ACCESS_TOKEN",
        "page_id": f"page-{account_id}",
        "auto_publish": auto_publish,
    }


def test_raw_credentials_are_rejected(tmp_path: Path) -> None:
    svc, *_ = service(tmp_path)
    result = svc.configure_account({**account_payload(), "access_token": "secret"})
    assert result.code == "RAW_CREDENTIAL_REJECTED"
    assert "access_token" in result.data["fields"]


def test_x_account_configuration_is_manual_only(tmp_path: Path) -> None:
    svc, *_ = service(tmp_path)
    result = svc.configure_account({"id": "x-primary", "platform": "x"})
    assert result.code == "X_MANUAL_ONLY"
    assert "No X OAuth" in result.data["message"]


def test_old_x_account_is_removed_during_schema_migration(tmp_path: Path) -> None:
    state_file = tmp_path / "social.json"
    state_file.write_text(
        json.dumps(
            {
                "schema": 1,
                "accounts": {
                    "x-primary": {
                        "id": "x-primary",
                        "platform": "x",
                        "credential_ref": "CSRN_X_ACCESS_TOKEN",
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    svc, *_ = service(tmp_path)
    status = svc.status().data["social"]
    assert status["accounts"] == []
    assert status["platform_policy"]["x_oauth"] is False
    saved = json.loads(state_file.read_text(encoding="utf-8"))
    assert saved["schema"] == 3
    assert saved["accounts"] == {}


def test_facebook_account_saves_reference_not_secret(tmp_path: Path) -> None:
    svc, *_ = service(tmp_path)
    result = svc.configure_account(account_payload())
    assert result.code == "ACCOUNT_SAVED"
    assert result.data["account"]["credential_ref"] == "CSRN_FACEBOOK_PAGE_ACCESS_TOKEN"
    assert result.data["account"]["credential_configured"] is True


def test_facebook_requires_page_id(tmp_path: Path) -> None:
    svc, *_ = service(tmp_path)
    payload = account_payload()
    payload.pop("page_id")
    assert svc.configure_account(payload).code == "PAGE_ID_REQUIRED"


def test_remove_account_requires_exact_confirmation(tmp_path: Path) -> None:
    svc, *_ = service(tmp_path)
    svc.configure_account(account_payload())
    assert svc.remove_account("facebook-primary", "remove").code == "ACCOUNT_REMOVE_CONFIRMATION_REQUIRED"
    assert svc.remove_account("facebook-primary", "REMOVE SOCIAL ACCOUNT").code == "ACCOUNT_REMOVED"


def test_settings_support_manual_x_without_credentials(tmp_path: Path) -> None:
    svc, *_ = service(tmp_path)
    result = svc.update_settings({"x_manual_enabled": True, "x_username": "@csrn"})
    assert result.code == "SETTINGS_UPDATED"
    assert result.data["settings"]["x_username"] == "csrn"
    assert "x_credential_ref" not in result.data["settings"]


def test_settings_reject_unknown_keys(tmp_path: Path) -> None:
    svc, *_ = service(tmp_path)
    assert svc.update_settings({"token": "x"}).code == "SETTINGS_INVALID"



def test_player_name_policy_rejects_unknown_value(tmp_path: Path) -> None:
    svc, *_ = service(tmp_path)
    assert svc.update_settings({"player_name_policy": "nickname_only"}).code == "PLAYER_NAME_POLICY_INVALID"


def test_preferred_first_last_and_pick_six_headline(tmp_path: Path) -> None:
    svc, _, _, state = service(tmp_path)
    event = state["events"][0]
    event["event"] = "TURNOVER"
    event["description"] = "Jazz interception returned for a touchdown"
    event["automation"] = {"player_id": "player-1", "player_name": "Jazz", "player_number": "2", "play_type": "interception"}
    svc._load_rosters = lambda: [{"id": "roster-1", "players": [{"id": "player-1", "number": "2", "first_name": "Jasper", "last_name": "Johnson", "preferred_name": "Jazz", "display_name": "Jazz", "headshot": "/roster-headshots/jazz.png"}]}]
    result = svc.create_draft("TURNOVER", event_id="EV-1")
    draft = result.data["draft"]
    assert draft["player"]["name"] == "Jazz Johnson"
    assert draft["content"]["detail"] == "Jazz Johnson interception returned for a touchdown"
    assert draft["content"]["headline"] == "PICK SIX"


def test_roster_full_name_policy_uses_official_name(tmp_path: Path) -> None:
    svc, _, _, state = service(tmp_path)
    event = state["events"][0]
    event["event"] = "TURNOVER"
    event["description"] = "Jazz interception returned for a touchdown"
    event["automation"] = {"player_id": "player-1", "player_name": "Jazz", "player_number": "2", "play_type": "interception"}
    svc._load_rosters = lambda: [{"id": "roster-1", "players": [{"id": "player-1", "number": "2", "first_name": "Jasper", "last_name": "Johnson", "preferred_name": "Jazz", "display_name": "Jazz"}]}]
    svc.update_settings({"player_name_policy": "roster_full_name"})
    draft = svc.create_draft("TURNOVER", event_id="EV-1").data["draft"]
    assert draft["player"]["name"] == "Jasper Johnson"
    assert draft["content"]["detail"].startswith("Jasper Johnson interception")


def test_explicit_active_sponsor_is_embedded_in_draft(tmp_path: Path) -> None:
    svc, *_ = service(tmp_path)
    result = svc.create_draft("TOUCHDOWN", event_id="EV-1", payload={"sponsor_id": "sponsor-1"})
    draft = result.data["draft"]
    assert draft["sponsor"]["name"] == "Local Bank"
    assert draft["sponsor"]["lead_in"] == "Touchdown presented by"

def test_sponsor_rules_require_active_sponsor(tmp_path: Path) -> None:
    svc, *_ = service(tmp_path)
    assert svc.update_sponsor_rules({"event_sponsors": {"TOUCHDOWN": "missing"}, "rotation": []}).code == "SPONSOR_NOT_ACTIVE"


def test_emergency_kind_cannot_have_sponsor_rule(tmp_path: Path) -> None:
    svc, *_ = service(tmp_path)
    result = svc.update_sponsor_rules({"event_sponsors": {"WEATHER_EMERGENCY": "sponsor-1"}, "rotation": []})
    assert result.code == "SPONSOR_RULE_KIND_INVALID"


def test_touchdown_draft_uses_recorded_event_player_and_both_card_sizes(tmp_path: Path) -> None:
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
    assert "x-manual" in draft["platform_copy"]


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


def test_draft_approval_requires_exact_phrase(tmp_path: Path) -> None:
    svc, *_ = service(tmp_path)
    draft_id = svc.create_draft("TOUCHDOWN", event_id="EV-1").data["draft"]["id"]
    assert svc.approve_draft(draft_id, operator="Alex", confirmation="yes").code == "APPROVAL_CONFIRMATION_REQUIRED"
    approved = svc.approve_draft(draft_id, operator="Alex", confirmation="APPROVE SOCIAL POST")
    assert approved.code == "DRAFT_APPROVED"


def test_manual_x_package_is_available_for_fresh_draft_and_never_calls_adapter(tmp_path: Path) -> None:
    svc, _, facebook, _ = service(tmp_path)
    draft_id = svc.create_draft("TOUCHDOWN", event_id="EV-1").data["draft"]["id"]
    result = svc.manual_package(draft_id)
    assert result.code == "MANUAL_PACKAGE_READY"
    package = result.data["package"]
    assert package["mode"] == "assisted_manual"
    assert package["oauth_used"] is False
    assert package["api_used"] is False
    assert package["automatic_posting"] is False
    assert package["compose_url"].startswith("https://x.com/intent/post?")
    assert package["download_url"].endswith("?download=1")
    assert facebook.published == []


def test_publish_requires_approval(tmp_path: Path) -> None:
    svc, *_ = service(tmp_path)
    svc.configure_account(account_payload())
    draft_id = svc.create_draft("TOUCHDOWN", event_id="EV-1").data["draft"]["id"]
    assert svc.publish_draft(draft_id).code == "DRAFT_NOT_APPROVED"


def test_approved_draft_publishes_to_facebook_only(tmp_path: Path) -> None:
    svc, _, facebook, _ = service(tmp_path)
    svc.configure_account(account_payload())
    draft_id = svc.create_draft("TOUCHDOWN", event_id="EV-1").data["draft"]["id"]
    svc.approve_draft(draft_id, operator="Alex", confirmation="APPROVE SOCIAL POST")
    result = svc.publish_draft(draft_id)
    assert result.code == "PUBLISHED"
    assert result.data["draft"]["publications"]["facebook-primary"]["post_id"] == "facebook-1"
    assert len(facebook.published) == 1
    assert set(result.data["results"]) == {"facebook-primary"}


def test_partial_publish_between_facebook_pages_preserves_success(tmp_path: Path) -> None:
    svc, _, facebook, _ = service(
        tmp_path,
        facebook_results=[
            PlatformResult("PUBLISHED", post_id="fb-1"),
            PlatformResult("POST_FAILED", retryable=True, retry_after=30),
        ],
    )
    svc.configure_account(account_payload("facebook-one"))
    svc.configure_account(account_payload("facebook-two"))
    draft_id = svc.create_draft("TOUCHDOWN", event_id="EV-1").data["draft"]["id"]
    svc.approve_draft(draft_id, operator="Alex", confirmation="APPROVE SOCIAL POST")
    result = svc.publish_draft(draft_id)
    assert result.code == "PARTIALLY_PUBLISHED"
    assert result.data["results"]["facebook-two"]["retryable"] is True
    assert result.data["draft"]["status"] == "PARTIAL"
    assert len(facebook.published) == 2


def test_explicit_empty_account_selection_does_not_publish_all(tmp_path: Path) -> None:
    svc, _, facebook, _ = service(tmp_path)
    svc.configure_account(account_payload())
    draft_id = svc.create_draft("TOUCHDOWN", event_id="EV-1").data["draft"]["id"]
    svc.approve_draft(draft_id, operator="Alex", confirmation="APPROVE SOCIAL POST")
    assert svc.publish_draft(draft_id, account_ids=[]).code == "NO_ENABLED_ACCOUNTS"
    assert facebook.published == []


def test_auto_queue_requires_global_and_facebook_account_opt_in(tmp_path: Path) -> None:
    svc, *_ = service(tmp_path)
    assert svc.process_auto_queue().code == "AUTO_PUBLISH_DISABLED"
    svc.update_settings({"allow_auto_publish": True})
    svc.configure_account(account_payload(auto_publish=False))
    assert svc.process_auto_queue().code == "NO_AUTO_PUBLISH_ACCOUNTS"


def test_auto_draft_event_handoff_is_disabled_by_default(tmp_path: Path) -> None:
    svc, *_, state = service(tmp_path)
    event = state["events"][0]
    assert svc.queue_event(event).code == "AUTO_DRAFT_DISABLED"
    svc.update_settings({"auto_create_drafts": True})
    assert svc.queue_event(event).code == "EVENT_QUEUED"


def test_published_post_can_create_correction_and_retract(tmp_path: Path) -> None:
    svc, _, facebook, _ = service(tmp_path)
    svc.configure_account(account_payload())
    draft_id = svc.create_draft("TOUCHDOWN", event_id="EV-1").data["draft"]["id"]
    svc.approve_draft(draft_id, operator="Alex", confirmation="APPROVE SOCIAL POST")
    svc.publish_draft(draft_id)
    correction = svc.create_correction(draft_id, {"detail": "Corrected touchdown detail"})
    assert correction.code == "CORRECTION_CREATED"
    assert "x-manual" in correction.data["draft"]["platform_copy"]
    assert svc.retract_publication(draft_id, "facebook-primary", "wrong").code == "RETRACT_CONFIRMATION_REQUIRED"
    retracted = svc.retract_publication(draft_id, "facebook-primary", "RETRACT SOCIAL POST")
    assert retracted.code == "PUBLICATION_RETRACTED"
    assert facebook.deleted[0][1] == "facebook-1"


def test_postgame_handoff_contains_only_recorded_game_data(tmp_path: Path) -> None:
    svc, *_ = service(tmp_path)
    handoff = svc.postgame_handoff().data["handoff"]
    assert handoff["home_score"] == 14
    assert handoff["visitor_score"] == 7
    assert handoff["events"][0]["id"] == "EV-1"
    assert handoff["grounding_policy"].startswith("Use only recorded events")
    assert handoff["statistics_available"] is False

def test_touchdown_copy_includes_recorded_extra_point(tmp_path: Path) -> None:
    svc, *_rest, state = service(tmp_path)
    touchdown = state["events"][0]
    touchdown["team"] = "home"
    state["events"].append({
        "id": "EV-XP",
        "event": "XP",
        "team": "home",
        "description": "Extra point by Alex Morgan",
        "quarter": "2",
        "after": {"home_score": 15, "visitor_score": 7},
    })
    result = svc.create_draft("TOUCHDOWN", event_id="EV-1")
    assert result.code == "DRAFT_CREATED"
    draft = result.data["draft"]
    assert "Extra point good." in draft["content"]["detail"]
    assert draft["content"]["score"] == "Home School 15 · Visitor School 7"


def test_only_attachable_sponsors_are_offered(tmp_path: Path) -> None:
    facebook = Adapter()
    renderer = Renderer(tmp_path / "cards")
    state = broadcast_state()
    instance = SocialPublishingService(
        state_file=tmp_path / "social.json",
        renderer=renderer,
        adapters={"facebook": facebook},
        load_broadcast_state=lambda: state,
        load_config=lambda: {},
        load_rosters=lambda: [],
        load_sponsors=lambda: [
            {"id": "sponsor-1", "name": "Local Bank", "active": True},
            {"id": "expired", "name": "Expired Sponsor", "active": True},
        ],
        active_sponsor_by_id=active_sponsor,
        get_theme_status=lambda: SimpleNamespace(data={"theme": {"active": {"id": "modern_network", "tokens": {}}}}),
        clock=lambda: 1_700_000_000,
    )
    offered = instance.status().data["social"]["available_sponsors"]
    assert [item["id"] for item in offered] == ["sponsor-1"]


def test_extra_point_event_creates_compact_mobile_update(tmp_path: Path) -> None:
    svc, *_rest, state = service(tmp_path)
    state["events"].append({
        "id": "EV-XP",
        "event": "XP",
        "team": "home",
        "description": "Extra point by Home School",
        "quarter": "2",
        "after": {"home_score": 15, "visitor_score": 7},
    })
    result = svc.create_draft("EXTRA_POINT", event_id="EV-XP")
    assert result.code == "DRAFT_CREATED"
    draft = result.data["draft"]
    assert draft["card_style"] == "compact_score"
    assert draft["content"]["headline"] == "XP GOOD"
    assert draft["content"]["detail"] == "Home School 15"
    assert draft["content"]["score"] == "Home School 15 · Visitor School 7"


def test_two_point_event_is_eligible_for_standalone_post(tmp_path: Path) -> None:
    svc, *_rest, state = service(tmp_path)
    state["events"].append({
        "id": "EV-2PT",
        "event": "2PT",
        "team": "visitor",
        "description": "Two-point conversion by Visitor School",
        "quarter": "2",
        "after": {"home_score": 14, "visitor_score": 9},
    })
    eligible = svc.eligible_events().data["events"]
    row = next(item for item in eligible if item["event"]["id"] == "EV-2PT")
    assert row["kind"] == "TWO_POINT_CONVERSION"
    draft = svc.create_draft("TWO_POINT_CONVERSION", event_id="EV-2PT").data["draft"]
    assert draft["content"]["headline"] == "2-POINT GOOD"
    assert draft["content"]["detail"] == "Visitor School 9"


def test_sponsor_banner_layout_is_preserved_in_create_update_and_correction(tmp_path: Path) -> None:
    svc, *_ = service(tmp_path)
    created = svc.create_draft(
        "TOUCHDOWN",
        event_id="EV-1",
        payload={"sponsor_id": "sponsor-1", "sponsor_layout": "banner"},
    ).data["draft"]
    assert created["sponsor"]["layout"] == "banner"
    updated = svc.update_draft(created["id"], {"sponsor_layout": "standard"}).data["draft"]
    assert updated["sponsor"]["layout"] == "standard"


def test_unpublished_draft_can_be_discarded_with_audit_retained(tmp_path: Path) -> None:
    svc, *_ = service(tmp_path)
    draft_id = svc.create_draft("TOUCHDOWN", event_id="EV-1").data["draft"]["id"]
    assert svc.discard_draft(draft_id, "wrong").code == "DRAFT_DISCARD_CONFIRMATION_REQUIRED"
    result = svc.discard_draft(draft_id, "DISCARD SOCIAL DRAFT")
    assert result.code == "DRAFT_DISCARDED"
    assert result.data["draft"]["status"] == "DISCARDED"
    status = svc.status().data["social"]
    stored = next(item for item in status["drafts"] if item["id"] == draft_id)
    assert stored["status"] == "DISCARDED"
    assert any(row["action"] == "DRAFT_DISCARDED" and row["draft_id"] == draft_id for row in status["audit"])


def test_published_draft_requires_retraction_then_can_be_archived(tmp_path: Path) -> None:
    svc, _, facebook, _ = service(tmp_path)
    svc.configure_account(account_payload())
    draft_id = svc.create_draft("TOUCHDOWN", event_id="EV-1").data["draft"]["id"]
    svc.approve_draft(draft_id, operator="Alex", confirmation="APPROVE SOCIAL POST")
    svc.publish_draft(draft_id)
    assert svc.discard_draft(draft_id, "DISCARD SOCIAL DRAFT").code == "PUBLISHED_DRAFT_REQUIRES_RETRACTION"
    assert svc.archive_draft(draft_id, "ARCHIVE SOCIAL DRAFT").code == "ACTIVE_PUBLICATION_EXISTS"
    retracted = svc.retract_publication(draft_id, "facebook-primary", "RETRACT SOCIAL POST")
    assert retracted.data["draft"]["status"] == "RETRACTED"
    assert facebook.deleted[0][1] == "facebook-1"
    archived = svc.archive_draft(draft_id, "ARCHIVE SOCIAL DRAFT")
    assert archived.code == "DRAFT_ARCHIVED"
    assert archived.data["draft"]["status"] == "ARCHIVED"
    assert archived.data["draft"]["previous_status"] == "RETRACTED"


def test_discarded_or_archived_event_can_create_a_fresh_draft(tmp_path: Path) -> None:
    svc, *_ = service(tmp_path)
    first = svc.create_draft("TOUCHDOWN", event_id="EV-1").data["draft"]
    svc.discard_draft(first["id"], "DISCARD SOCIAL DRAFT")
    second = svc.create_draft("TOUCHDOWN", event_id="EV-1")
    assert second.code == "DRAFT_CREATED"
    assert second.data["draft"]["id"] != first["id"]

