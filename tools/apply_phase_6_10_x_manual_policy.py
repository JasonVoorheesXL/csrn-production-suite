from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    source = path.read_text(encoding="utf-8")
    if new in source:
        return
    if old not in source:
        raise RuntimeError(f"X manual policy anchor missing: {label}")
    path.write_text(source.replace(old, new, 1), encoding="utf-8")


def apply_oauth_policy() -> None:
    path = ROOT / "oauth_onboarding_service.py"
    source = path.read_text(encoding="utf-8")
    source = source.replace(
        '    """Consumer-style account connection boundary for X and Facebook Pages.\n\n    X uses OAuth 2.0 Authorization Code with PKCE. Facebook uses a configured\n    PossumFrog OAuth broker so Meta application secrets are never distributed in\n    the desktop client.\n    """',
        '    """Consumer-style Facebook Page connection boundary.\n\n    X intentionally uses manual assisted publishing so customers do not need a\n    paid X developer account or API credits. Facebook uses a configured PossumFrog\n    OAuth broker so Meta application secrets are never distributed in the desktop client.\n    """',
    )
    source = source.replace(
        '        for provider, label in (("x", "X"), ("facebook", "Facebook Page")):',
        '        for provider, label in (("facebook", "Facebook Page"),):',
    )
    source = source.replace('        if provider not in {"x", "facebook"}:\n', '        if provider not in {"facebook"}:\n', 2)
    source = source.replace(
        '        result = self._complete_x(pending, code) if provider == "x" else self._complete_facebook(pending, code)',
        '        result = self._complete_facebook(pending, code)',
    )
    path.write_text(source, encoding="utf-8")


def apply_social_policy() -> None:
    path = ROOT / "social_service.py"
    source = path.read_text(encoding="utf-8")
    source = source.replace(
        '        if platform not in self.PLATFORMS:\n            return SocialResult("PLATFORM_UNSUPPORTED")\n',
        '        if platform == "x":\n            return SocialResult("X_MANUAL_ASSISTED_ONLY")\n        if platform not in self.PLATFORMS:\n            return SocialResult("PLATFORM_UNSUPPORTED")\n',
        1,
    )
    source = source.replace(
        '        platforms = {str(account.get("platform")) for account in accounts.values() if account.get("enabled", True)} or self.PLATFORMS\n',
        '        platforms = {str(account.get("platform")) for account in accounts.values() if account.get("enabled", True)}\n        platforms.add("x")  # Always render the no-fee manual X package.\n        if not platforms:\n            platforms = set(self.PLATFORMS)\n',
        1,
    )
    source = source.replace(
        '                if account.get("enabled", True)\n                and (not selection_requested or account_id in selected)\n',
        '                if account.get("enabled", True)\n                and str(account.get("platform", "")) != "x"\n                and (not selection_requested or account_id in selected)\n',
        1,
    )
    source = source.replace(
        '                if account.get("enabled", True)\n                and account.get("auto_publish", False)\n',
        '                if account.get("enabled", True)\n                and str(account.get("platform", "")) != "x"\n                and account.get("auto_publish", False)\n',
        1,
    )
    path.write_text(source, encoding="utf-8")


def apply_setup_hub() -> None:
    path = ROOT / "templates" / "setup_hub.html"
    source = path.read_text(encoding="utf-8")
    source = source.replace(
        '<h2>Social accounts</h2><p>Connect accounts through the provider sign-in flow. Customers do not copy access tokens into CSRN.</p>\n       <div id="providers" class="setup-list"></div>\n       <p class="note">X requires the PossumFrog X application client ID. Facebook requires the PossumFrog OAuth broker so Meta application secrets are never distributed with the desktop program.</p>\n       <a class="button secondary" href="/social">Open Social Publishing</a>',
        '<h2>Social accounts</h2><p>Connect Facebook through a guided sign-in. X uses a no-fee manual assisted workflow and never requires API credits.</p>\n       <div class="provider" style="margin-bottom:12px"><div class="provider-head"><div><strong>X</strong><div class="note">Manual assisted publishing: CSRN prepares the graphic and text, then opens X for the operator.</div></div><span class="status good">No API fees</span></div></div>\n       <div id="providers" class="setup-list"></div>\n       <p class="note">Facebook requires the PossumFrog OAuth broker so Meta application secrets are never distributed with the desktop program.</p>\n       <a class="button secondary" href="/social">Open Social Publishing</a>',
    )
    path.write_text(source, encoding="utf-8")


def apply_social_manager() -> None:
    path = ROOT / "templates" / "social_manager.html"
    source = path.read_text(encoding="utf-8")
    source = source.replace(
        '  <p>Preview and approve every post before publishing. Credentials are referenced externally and are never shown here.</p>',
        '  <p>Preview and approve every post. Facebook can publish through a connected Page; X uses a no-fee manual assisted workflow.</p>',
    )
    old_account = '''    <section class="panel">
       <h2>Account</h2>
       <div class="row">
         <select id="platform"><option value="x">X</option><option value="facebook">Facebook Page</option></select>
         <input id="accountId" value="x-primary" placeholder="Account ID">
       </div>
       <input id="displayName" placeholder="Display name" style="width:100%;margin-top:8px">
       <input id="credentialRef" value="CSRN_X_ACCESS_TOKEN" placeholder="Credential environment reference" style="width:100%;margin-top:8px">
       <input id="username" placeholder="X username" style="width:100%;margin-top:8px">
       <input id="pageId" placeholder="Facebook Page ID" style="width:100%;margin-top:8px">
       <div class="row" style="margin-top:10px"><label><input type="checkbox" id="accountEnabled" checked> Enabled</label><label><input type="checkbox" id="autoPublish"> Auto-publish approved queue</label></div>
       <button id="saveAccount" style="margin-top:10px">Save account</button>
       <div id="accounts" class="muted" style="margin-top:12px"></div>
     </section>'''
    new_account = '''    <section class="panel">
       <h2>Publishing Accounts</h2>
       <p><strong>Facebook:</strong> connect and manage the Page from Setup &amp; Integrations.</p>
       <button onclick="window.location.href='/setup#social'">Manage Facebook Connection</button>
       <p style="margin-top:16px"><strong>X:</strong> no API connection is used. Each draft includes copy, a downloadable X graphic, and an Open X button.</p>
       <div id="accounts" class="muted" style="margin-top:12px"></div>
     </section>'''
    source = source.replace(old_account, new_account)
    source = source.replace(
        "document.getElementById('accounts').innerHTML=(social.accounts||[]).map(a=>`<div>${escapeHtml(a.display_name)} · ${escapeHtml(a.platform)} · <code>${escapeHtml(a.credential_ref)}</code>${a.auto_publish?' · AUTO':''}</div>`).join('')||'No account configured.';",
        "document.getElementById('accounts').innerHTML=(social.accounts||[]).filter(a=>a.platform==='facebook').map(a=>`<div>${escapeHtml(a.display_name)} · Facebook Page${a.auto_publish?' · AUTO':''}</div>`).join('')||'No Facebook Page connected.';",
    )
    old_render = "function renderDraft(d){const cards=d.cards||{};const card=cards.x||cards.facebook;const pubs=Object.values(d.publications||{});return `<article class=\"draft\" data-draft=\"${escapeHtml(d.id)}\"><div class=\"row\"><strong>${escapeHtml(d.content?.headline||d.kind)}</strong><span class=\"badge\">${escapeHtml(d.status)}</span><span class=\"muted\">${escapeHtml(d.id)}</span></div><p>${escapeHtml(d.content?.detail||'')}</p><p class=\"muted\">${escapeHtml(d.content?.score||'')}${d.sponsor?.name?` · Presented by ${escapeHtml(d.sponsor.name)}`:''}${d.sponsor_suppressed?' · Sponsor suppressed for emergency':''}</p>${card?`<img class=\"card\" src=\"/api/social/drafts/${encodeURIComponent(d.id)}/cards/${encodeURIComponent(card.platform)}?t=${d.updated_at||0}\">`:''}<div class=\"row\"><button data-approve>Approve</button><button data-publish>Publish</button><button class=\"secondary\" data-correct>Correction</button></div>${pubs.map(p=>`<div class=\"muted\">${escapeHtml(p.platform)}: ${escapeHtml(p.post_id)} ${p.retracted_at?'(retracted)':''}</div>`).join('')}</article>`}"
    new_render = "function xText(d){const c=d.content||{};const lines=[c.headline,c.detail,c.score];const p=d.player||{};if(p.name)lines.push(`${p.number?'#'+p.number+' ':''}${p.name}`);if(d.settings?.include_broadcast_link&&d.broadcast_link)lines.push(d.broadcast_link);const tags=(d.settings?.default_hashtags||[]).join(' ');if(tags)lines.push(tags);const text=lines.filter(Boolean).join('\\n');return text.length<=280?text:text.slice(0,279).trimEnd()+'…'}\nfunction renderDraft(d){const cards=d.cards||{};const card=cards.x||cards.facebook;const pubs=Object.values(d.publications||{});return `<article class=\"draft\" data-draft=\"${escapeHtml(d.id)}\"><div class=\"row\"><strong>${escapeHtml(d.content?.headline||d.kind)}</strong><span class=\"badge\">${escapeHtml(d.status)}</span><span class=\"muted\">${escapeHtml(d.id)}</span></div><p>${escapeHtml(d.content?.detail||'')}</p><p class=\"muted\">${escapeHtml(d.content?.score||'')}${d.sponsor?.name?` · Presented by ${escapeHtml(d.sponsor.name)}`:''}${d.sponsor_suppressed?' · Sponsor suppressed for emergency':''}</p>${card?`<img class=\"card\" src=\"/api/social/drafts/${encodeURIComponent(d.id)}/cards/${encodeURIComponent(card.platform)}?t=${d.updated_at||0}\">`:''}<div class=\"row\"><button data-approve>Approve</button><button data-publish>Publish to Facebook</button><button data-copy-x>Copy X Text</button><a class=\"button secondary\" href=\"/api/social/drafts/${encodeURIComponent(d.id)}/cards/x\" download>Download X Graphic</a><button data-open-x>Open X</button><button class=\"secondary\" data-correct>Correction</button></div><textarea class=\"muted\" readonly>${escapeHtml(xText(d))}</textarea>${pubs.map(p=>`<div class=\"muted\">${escapeHtml(p.platform)}: ${escapeHtml(p.post_id)} ${p.retracted_at?'(retracted)':''}</div>`).join('')}</article>`}"
    source = source.replace(old_render, new_render)
    old_bind = "function bindDraftActions(){document.querySelectorAll('[data-draft]').forEach(card=>{const id=card.dataset.draft;card.querySelector('[data-approve]').onclick=async()=>{await api(`/api/social/drafts/${encodeURIComponent(id)}/approve`,{method:'POST',body:JSON.stringify({operator:'operator',confirmation:'APPROVE SOCIAL POST'})});message('Draft approved.');load()};card.querySelector('[data-publish]').onclick=async()=>{await api(`/api/social/drafts/${encodeURIComponent(id)}/publish`,{method:'POST',body:'{}'});message('Publish attempt completed.');load()};card.querySelector('[data-correct]').onclick=async()=>{const detail=prompt('Corrected detail:');if(detail===null)return;await api(`/api/social/drafts/${encodeURIComponent(id)}/corrections`,{method:'POST',body:JSON.stringify({detail})});message('Correction draft created.');load()}})}"
    new_bind = "function bindDraftActions(){document.querySelectorAll('[data-draft]').forEach(card=>{const id=card.dataset.draft;const draft=(window.socialDrafts||[]).find(row=>row.id===id);card.querySelector('[data-approve]').onclick=async()=>{await api(`/api/social/drafts/${encodeURIComponent(id)}/approve`,{method:'POST',body:JSON.stringify({operator:'operator',confirmation:'APPROVE SOCIAL POST'})});message('Draft approved.');load()};card.querySelector('[data-publish]').onclick=async()=>{await api(`/api/social/drafts/${encodeURIComponent(id)}/publish`,{method:'POST',body:'{}'});message('Facebook publish attempt completed.');load()};card.querySelector('[data-copy-x]').onclick=async()=>{await navigator.clipboard.writeText(xText(draft||{}));message('X post text copied.')};card.querySelector('[data-open-x]').onclick=()=>window.open(`https://x.com/intent/post?text=${encodeURIComponent(xText(draft||{}))}`,'_blank','noopener');card.querySelector('[data-correct]').onclick=async()=>{const detail=prompt('Corrected detail:');if(detail===null)return;await api(`/api/social/drafts/${encodeURIComponent(id)}/corrections`,{method:'POST',body:JSON.stringify({detail})});message('Correction draft created.');load()}})}"
    source = source.replace(old_bind, new_bind)
    source = source.replace("document.getElementById('drafts').innerHTML=(social.drafts||[]).slice().reverse().map(renderDraft).join('')", "window.socialDrafts=social.drafts||[];document.getElementById('drafts').innerHTML=window.socialDrafts.slice().reverse().map(renderDraft).join('')")
    start = source.find("document.getElementById('platform').onchange=")
    end = source.find("document.getElementById('createDraft').onclick=", start)
    if start >= 0 and end >= 0:
        source = source[:start] + source[end:]
    path.write_text(source, encoding="utf-8")


def apply_docs_and_tests() -> None:
    for relative in (
        "docs/PHASE_6_10_COMMERCIAL_UX_NAVIGATION_AND_ACCOUNT_ONBOARDING.md",
        "docs/PHASE_6_GAME_DAY_AND_COMMERCIAL_ROADMAP.md",
    ):
        path = ROOT / relative
        source = path.read_text(encoding="utf-8")
        source = source.replace("Connect X using OAuth 2.0 Authorization Code with PKCE", "Manual assisted X publishing with generated copy and graphics")
        source = source.replace("X OAuth 2.0 PKCE", "manual assisted X publishing")
        source = source.replace("X and Facebook OAuth", "Facebook OAuth and manual X assistance")
        source = source.replace("X uses OAuth 2.0 Authorization Code with PKCE.", "X uses manual assisted publishing and never requires API credits.")
        path.write_text(source, encoding="utf-8")

    path = ROOT / "tests" / "test_commercial_ux_architecture.py"
    source = path.read_text(encoding="utf-8")
    source = source.replace('assert "Connect ${escapeHtml(provider.label)}" in setup', 'assert "Manual assisted publishing" in setup\n    assert "No API fees" in setup')
    source = source.replace('assert "code_challenge_method" in oauth\n    assert "offline.access" in oauth\n', 'assert \"if provider not in {\\\"facebook\\\"}\" in oauth\n    assert \"manual assisted publishing\" in oauth\n')
    path.write_text(source, encoding="utf-8")

    path = ROOT / "tests" / "test_oauth_onboarding_service.py"
    source = path.read_text(encoding="utf-8")
    source = source.replace('def test_x_authorization_uses_pkce_and_no_client_secret', 'def test_x_is_intentionally_manual_assisted_and_has_no_oauth_start')
    marker = 'def test_x_is_intentionally_manual_assisted_and_has_no_oauth_start'
    if marker in source:
        start = source.index(marker)
        next_def = source.find('\ndef ', start + 5)
        replacement = '''def test_x_is_intentionally_manual_assisted_and_has_no_oauth_start(tmp_path: Path) -> None:\n    service, _ = build_service(tmp_path)\n    result = service.start("x", "http://127.0.0.1:5050/setup/oauth/x/callback")\n    assert result.code == "PROVIDER_UNSUPPORTED"\n\n'''
        source = source[:start] + replacement + (source[next_def + 1:] if next_def >= 0 else '')
    path.write_text(source, encoding="utf-8")

    path = ROOT / "tests" / "test_phase_6_10_migration.py"
    source = path.read_text(encoding="utf-8")
    source = source.replace('assert "Connect X" in setup', 'assert "No API fees" in setup')
    path.write_text(source, encoding="utf-8")


def apply() -> None:
    apply_oauth_policy()
    apply_social_policy()
    apply_setup_hub()
    apply_social_manager()
    apply_docs_and_tests()


if __name__ == "__main__":
    apply()
