from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def apply() -> None:
    path = ROOT / "tests" / "test_social_service.py"
    source = path.read_text(encoding="utf-8")
    source = source.replace('def account_payload(platform="x"):', 'def account_payload(platform="facebook"):')
    source = source.replace('assert result.data["account"]["credential_ref"] == "CSRN_X_ACCESS_TOKEN"', 'assert result.data["account"]["credential_ref"] == "CSRN_FACEBOOK_PAGE_ACCESS_TOKEN"')
    source = source.replace('svc.remove_account("x-primary", "remove")', 'svc.remove_account("facebook-primary", "remove")')
    source = source.replace('svc.remove_account("x-primary", "REMOVE SOCIAL ACCOUNT")', 'svc.remove_account("facebook-primary", "REMOVE SOCIAL ACCOUNT")')
    source = source.replace('assert {item[1] for item in renderer.calls} == {"x", "facebook"}', 'assert {item[1] for item in renderer.calls} == {"x"}')
    source = source.replace('svc, _, x, *_ = service(tmp_path)\n    svc.configure_account(account_payload())', 'svc, _, _, facebook, _ = service(tmp_path)\n    svc.configure_account(account_payload())', 1)
    source = source.replace('assert result.data["draft"]["publications"]["x-primary"]["post_id"] == "x-1"\n    assert len(x.published) == 1', 'assert result.data["draft"]["publications"]["facebook-primary"]["post_id"] == "facebook-1"\n    assert len(facebook.published) == 1')
    old_partial = '''def test_partial_publish_preserves_success_and_retryable_failure(tmp_path: Path) -> None:\n    svc, _, _, _, _ = service(\n        tmp_path,\n        facebook_results=[PlatformResult("POST_FAILED", retryable=True, retry_after=30)],\n    )\n    svc.configure_account(account_payload("x"))\n    svc.configure_account(account_payload("facebook"))\n    draft_id = svc.create_draft("TOUCHDOWN", event_id="EV-1").data["draft"]["id"]\n    svc.approve_draft(draft_id, operator="Alex", confirmation="APPROVE SOCIAL POST")\n    result = svc.publish_draft(draft_id)\n    assert result.code == "PARTIALLY_PUBLISHED"\n    assert result.data["results"]["facebook-primary"]["retryable"] is True\n    assert result.data["draft"]["status"] == "PARTIAL"\n'''
    new_partial = '''def test_x_account_configuration_is_blocked_and_facebook_failures_remain_retryable(tmp_path: Path) -> None:\n    svc, _, _, _, _ = service(\n        tmp_path,\n        facebook_results=[PlatformResult("POST_FAILED", retryable=True, retry_after=30)],\n    )\n    assert svc.configure_account(account_payload("x")).code == "X_MANUAL_ASSISTED_ONLY"\n    svc.configure_account(account_payload("facebook"))\n    draft_id = svc.create_draft("TOUCHDOWN", event_id="EV-1").data["draft"]["id"]\n    svc.approve_draft(draft_id, operator="Alex", confirmation="APPROVE SOCIAL POST")\n    result = svc.publish_draft(draft_id)\n    assert result.code == "PUBLISH_FAILED"\n    assert result.data["results"]["facebook-primary"]["retryable"] is True\n    assert result.data["draft"]["status"] == "FAILED"\n'''
    source = source.replace(old_partial, new_partial)
    source = source.replace('svc, _, x, *_ = service(tmp_path)\n    svc.configure_account(account_payload())\n    draft_id = svc.create_draft', 'svc, _, _, facebook, _ = service(tmp_path)\n    svc.configure_account(account_payload())\n    draft_id = svc.create_draft', 1)
    source = source.replace('assert x.published == []', 'assert facebook.published == []')
    source = source.replace('svc, _, x, *_ = service(tmp_path)\n    svc.configure_account(account_payload())\n    draft_id = svc.create_draft', 'svc, _, _, facebook, _ = service(tmp_path)\n    svc.configure_account(account_payload())\n    draft_id = svc.create_draft', 1)
    source = source.replace('svc.retract_publication(draft_id, "x-primary", "wrong")', 'svc.retract_publication(draft_id, "facebook-primary", "wrong")')
    source = source.replace('svc.retract_publication(draft_id, "x-primary", "RETRACT SOCIAL POST")', 'svc.retract_publication(draft_id, "facebook-primary", "RETRACT SOCIAL POST")')
    source = source.replace('assert x.deleted[0][1] == "x-1"', 'assert facebook.deleted[0][1] == "facebook-1"')
    path.write_text(source, encoding="utf-8")

    oauth_test = ROOT / "tests" / "test_oauth_onboarding_service.py"
    source = oauth_test.read_text(encoding="utf-8")
    source = source.replace('    if url.endswith("/me"):\n', '    if "graph.facebook.com" in url:\n')
    oauth_test.write_text(source, encoding="utf-8")


if __name__ == "__main__":
    apply()
