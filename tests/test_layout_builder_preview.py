"""Layout Builder P2, Part A: the builder's live preview.

The preview is the REAL overlay in an iframe reading the operator's unsaved
edit. Its whole safety case is that the edit never leaves the browser tab and
that the embedded overlay cannot write anything. The shim's behaviour was
verified live in a real browser (docs/LAYOUT_BUILDER_P1.md, "P2"): edits show
in the preview while an already-open live overlay and the saved document stay
unchanged, and with only the preview running the server's overlay-health signal
does not move. This repo has no JS runner, so the JS is pinned here by
source assertions; everything the SERVER does about it is exercised for real.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SHIM = "static/csrn-layout-preview.js"
TAG = '<script src="/static/csrn-layout-preview.js"></script>'


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


# --- the live overlay is untouched ---------------------------------------------------


@pytest.fixture()
def client():
    import app as app_module

    app_module.app.config.update(TESTING=True)
    with app_module.app.test_client() as c:
        yield c


def test_the_real_overlay_page_is_byte_identical_and_never_references_the_shim(client) -> None:
    body = client.get("/overlay").get_data()
    assert b"layout-preview" not in body and b"layout_preview" not in body
    # exactly the template with the conditional tag absent: not even a blank line added
    template = (ROOT / "templates" / "overlay.html").read_bytes()
    stripped = re.sub(rb"\{% if request\.args\.get\('layout_preview'\) == '1' %\}.*?\{% endif %\}", b"", template)
    # Jinja normalises line endings and drops one trailing newline; nothing else may differ
    def norm(data: bytes) -> bytes:
        return data.replace(bytes([13, 10]), bytes([10])).rstrip()

    assert norm(body) == norm(stripped)


def test_the_real_pregame_overlay_page_is_byte_identical(client) -> None:
    body = client.get("/pregame-overlay").get_data()
    assert b"layout-preview" not in body
    assert body == _read("templates/pregame_universal_overlay.html").encode("utf-8")


def test_only_an_explicit_request_gets_the_shim_and_it_loads_first(client) -> None:
    for path, marker in (("/overlay?layout_preview=1", b"<head>"), ("/pregame-overlay?layout_preview=1", b"<head>")):
        html = client.get(path).get_data()
        assert TAG.encode() in html
        # before any of the overlay's own scripts, so its fetch wrapper is in place first
        assert html.index(TAG.encode()) < html.index(b"<script", html.index(TAG.encode()) + 1)
    for path in ("/overlay?layout_preview=0", "/overlay?layout_preview=true", "/overlay?other=1",
                 "/pregame-overlay?layout_preview=0", "/pregame-overlay?layout_preview=yes"):
        assert b"layout-preview" not in client.get(path).get_data(), path


def test_the_shim_is_served_as_a_static_file(client) -> None:
    response = client.get("/static/csrn-layout-preview.js")
    assert response.status_code == 200 and b"csrn-layout-preview" in response.get_data()


def test_loading_the_preview_pages_never_touches_the_saved_document_or_profile_file(client) -> None:
    import app as app_module

    before_doc = app_module.get_layouts_document()
    profile = Path(app_module.IDENTITY_FILE)
    before_stat = profile.stat().st_mtime_ns if profile.exists() else None
    for path in ("/overlay?layout_preview=1", "/pregame-overlay?layout_preview=1",
                 "/api/runtime-state?layout_preview=1", "/api/pregame-presentation?layout_preview=1"):
        assert client.get(path).status_code == 200
    assert app_module.get_layouts_document() == before_doc
    assert (profile.stat().st_mtime_ns if profile.exists() else None) == before_stat


def test_the_server_ignores_the_preview_flag_on_its_data_endpoints(client) -> None:
    """There is no server-side preview channel to leak: the query parameter is
    only honoured by the shim in the iframe, never by /api/runtime-state."""
    import runtime_state_cache

    runtime_state_cache._cached = None
    plain = client.get("/api/runtime-state").get_json()
    flagged = client.get("/api/runtime-state?layout_preview=1").get_json()
    assert flagged["layouts"] == plain["layouts"]
    assert {k: v for k, v in flagged.items() if k not in {"server_time", "server_now"}} == \
           {k: v for k, v in plain.items() if k not in {"server_time", "server_now"}}


# --- the shim: gates ------------------------------------------------------------------


def test_the_shim_does_nothing_unless_embedded_and_explicitly_requested() -> None:
    js = _read(SHIM)
    gate = js.split('(function () {')[1].split("var ORIGIN")[0]
    assert "window.parent !== window" in gate
    assert 'get("layout_preview") !== "1"' in gate
    assert "if (!embedded ||" in gate and ") return;" in gate
    # nothing before the gate installs anything
    assert "window.fetch =" not in gate and "addEventListener" not in gate


def test_the_shim_only_listens_to_its_own_parent_on_the_same_origin() -> None:
    js = _read(SHIM)
    handler = js.split('window.addEventListener("message"')[1].split("});")[0]
    assert "event.source !== window.parent || event.origin !== ORIGIN" in handler
    assert 'data.type !== "csrn-layout-preview"' in handler
    # every message it sends is addressed to its own origin, never "*"
    assert 'postMessage(' in js and '"*"' not in js
    assert js.count(", ORIGIN)") >= 2


# --- the shim: it can only READ ---------------------------------------------------------


def test_every_non_get_request_from_the_embedded_overlay_is_blocked() -> None:
    js = _read(SHIM)
    block = js.split('if (method !== "GET" && method !== "HEAD") {')[1].split("}\n    if (path")[0]
    assert "return Promise.resolve(new Response(" in block and "realFetch" not in block  # never forwarded
    assert "preview: true" in block and "blocked: path" in block
    assert "navigator.sendBeacon = function () { return true; }" in js


def test_only_two_read_endpoints_are_rewritten_and_everything_else_passes_through_unchanged() -> None:
    js = _read(SHIM)
    assert 'path !== "/api/runtime-state" && path !== "/api/pregame-presentation") return realFetch(input, init);' in js
    assert js.count("realFetch(") == 2  # the pass-through, and the one refresh path for the two rewritten endpoints
    assert "method:" not in js.replace("method: ", "").replace('"method"', "")  # the shim never builds a request itself


def test_the_overlay_pages_have_no_network_write_channel_other_than_fetch() -> None:
    """The shim blocks fetch() writes and sendBeacon; that is only complete if
    nothing the overlays load uses another channel."""
    overlay = _read("templates/overlay.html")
    served = ["templates/overlay.html", "templates/pregame_universal_overlay.html", "static/csrn-scorebug-engine.js",
              "static/csrn-production-theme-adapter.js", "static/csrn-production-theme-runtime.js",
              "static/csrn-broadcast-layout-engine.js"]
    served += [f"static/{m}" for m in re.findall(r"/static/(csrn-[\w.-]*engine[\w.-]*\.js)", overlay + _read(
        "static/csrn-production-theme-runtime.js"))]
    for relative in sorted(set(served)):
        source = _read(relative)
        for primitive in ("XMLHttpRequest", "new WebSocket", "new EventSource", "navigator.sendBeacon", "serviceWorker"):
            assert primitive not in source, (relative, primitive)
    # and the operator-only scripts that DO POST are not loaded by the overlay
    assert "csrn-production-template-menu.js" not in overlay and "csrn-pregame-theme-selector.js" not in overlay
    # the one write the real overlay makes is the health report the shim blocks
    assert "/api/overlay-health" in overlay and "method:'POST'" in overlay


def test_the_shim_rewrites_the_layout_only_inside_the_iframe_response() -> None:
    js = _read(SHIM)
    inject = js.split("function inject(url, payload) {")[1].split("\n  var pregameCache")[0]
    assert "payload.layouts = state.layouts" in inject               # in-game reads runtime.layouts
    assert "payload.layout = {" in inject and 'sceneOverrides(state.layouts, "pregame"' in inject  # pregame reads data.layout
    assert 'sceneOverrides(state.layouts, "halftime"' in inject
    # the scene being edited is what the pregame overlay shows
    assert 'state.scene === "halftime" ? "halftime" : "scheduled"' in inject
    # resolution matches layout_builder_service.scene_overrides_for_family: default key first, family key wins
    assert "[sceneDoc.default, sceneDoc[fam]]" in js


def test_the_sport_family_mapping_matches_the_runtime_and_python() -> None:
    import sport_families

    js = _read(SHIM)
    body = js.split("function family(sport) {")[1].split("\n  }")[0]
    for expected in ('"canadian_football"', '"cfl"', '"basketball"', '"baseball"', '"softball"', 'return "football"'):
        assert expected in body
    runtime = _read("static/csrn-production-theme-runtime.js")
    assert 'raw === "canadian_football" || raw === "cfl"' in runtime
    for sport, family in (("canadian_football", "football"), ("basketball", "basketball"),
                          ("baseball", "baseball"), ("softball", "softball"), ("football", "football")):
        assert sport_families.base_family(sport) == family


# --- the builder page ----------------------------------------------------------------------


def test_the_builder_previews_by_postmessage_into_a_same_origin_iframe_and_never_by_the_server() -> None:
    html = _read("templates/layout_builder.html")
    assert '<iframe id="previewFrame"' in html
    assert "layout_preview=1" in html and '"/overlay"' in html and '"/pregame-overlay"' in html
    post = html.split("function postPreview() {")[1].split("\n  }")[0]
    assert "frame.contentWindow.postMessage(" in post and "window.location.origin" in post
    assert "fetch(" not in post                      # posting a preview is never a network request
    assert "doc.active = selected" in post and "clone(work)" in post  # previews the edited preset, from a copy
    # the ONLY request the page makes with a body is Save
    assert html.count('method: "POST"') == 1
    save = html.split('$("save").addEventListener("click"')[1].split("});")[0]
    assert 'method: "POST"' in save


def test_the_builder_only_trusts_messages_from_its_own_preview_frame() -> None:
    html = _read("templates/layout_builder.html")
    handler = html.split('window.addEventListener("message"')[1].split("});")[0]
    assert "event.source !== frame.contentWindow || event.origin !== window.location.origin" in handler


def test_the_preview_follows_the_scene_tab_and_only_forces_triggers_in_game() -> None:
    html = _read("templates/layout_builder.html")
    assert 'scene === "in_game" ? "/overlay" : "/pregame-overlay"' in html
    assert 'if (scene !== "in_game") return [];' in html
    assert '$("forceBox").hidden = scene !== "in_game"' in html
    # rendering (which runs on every edit) re-syncs the preview
    render = html.split("function render() {")[1].split("\n  }")[0]
    assert "syncPreview();" in render


def test_the_builder_is_honest_about_what_the_preview_cannot_show() -> None:
    html = _read("templates/layout_builder.html")
    assert "does not use layouts" in html                      # classic theme: in-game layouts do nothing
    assert "those edits are not visible in this preview" in html  # editing a sport other than the loaded game's
    assert "Nothing is saved or sent, and no other overlay changes, until you press Save." in html
    assert "[hidden]{display:none!important}" in html
