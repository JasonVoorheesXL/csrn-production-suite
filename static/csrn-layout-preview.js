/*
 * Layout Builder P2: live preview shim.
 *
 * Lets the builder page (/layouts) show the REAL overlay -- same JS, DOM and CSS
 * as on air -- rendering an in-progress, unsaved layouts document, without the
 * document ever leaving the operator's browser tab and without the server, the
 * saved `layouts` section, the runtime-state cache, or any other overlay
 * (including the one OBS is showing) ever knowing about it.
 *
 * How: the builder embeds /overlay?layout_preview=1 (or /pregame-overlay?...)
 * in an iframe and postMessages the working document into it. This shim, inside
 * that iframe, wraps fetch() so the overlay's own reads of /api/runtime-state
 * and /api/pregame-presentation come back with the preview document (and,
 * optionally, forced sponsor/player/highlight triggers) merged in.
 *
 * Why it is inert to everything live -- every one of these is independently
 * enough, and there is a test for each:
 *   1. The overlay routes only include this script when the request itself has
 *      ?layout_preview=1, so the real overlay's HTML (what OBS loads) does not
 *      even reference this file.
 *   2. Even if it is loaded, it does nothing unless the page is EMBEDDED
 *      (window.parent !== window) AND the URL asks for it.
 *   3. It only accepts messages from its own parent frame and same origin.
 *   4. The preview document is applied only to responses inside this iframe;
 *      nothing is sent to the server. Every non-GET request the embedded overlay
 *      attempts is blocked -- in particular POST /api/overlay-health, which would
 *      otherwise make the preview masquerade as the OBS overlay in the operator's
 *      overlay-health signal -- and sendBeacon is a no-op.
 */
(function () {
  "use strict";

  var embedded;
  try { embedded = window.parent !== window; } catch (_) { embedded = true; }
  if (!embedded || new URLSearchParams(window.location.search).get("layout_preview") !== "1") return;

  var ORIGIN = window.location.origin;
  var state = { layouts: null, force: [], scene: "in_game" };

  // Realistic trigger payloads, so a hidden/shown sponsor, player card or
  // highlight can be seen without waiting for the operator to fire one live.
  var FORCE = {
    sponsor: { sponsor_spotlight: { sponsor_name: "ACME Auto", lead_in: "SPONSOR SPOTLIGHT", caption: "Thanks for watching", media_type: "image" } },
    player: { player_graphic: { full_name: "Caleb Lang", display_name: "Caleb Lang", number: "7", position: "RB", graphic_type: "touchdown", eyebrow: "TOUCHDOWN", team_name: "Caledonia", play_detail: "70-yard run" } },
    highlight: { player_highlight: { full_name: "Caleb Lang", display_name: "Caleb Lang", number: "7", detail: "70-yard run", eyebrow: "PLAYER HIGHLIGHT", media_type: "video" } }
  };

  // Same mapping as csrn-production-theme-runtime.js productionSportFamily()
  // and sport_families.base_family().
  function family(sport) {
    var raw = String(sport || "").trim().toLowerCase().replace(/[\s-]+/g, "_");
    if (raw === "canadian_football" || raw === "cfl") return "football";
    if (raw === "basketball" || raw === "baseball" || raw === "softball") return raw;
    return "football";
  }

  // Same resolution as layout_builder_service.scene_overrides_for_family():
  // the family's own override for an element, else the "default" key's.
  function sceneOverrides(doc, scene, fam) {
    var out = {};
    var preset = doc && doc.presets && doc.presets[doc.active];
    var sceneDoc = preset && preset[scene];
    if (!sceneDoc || typeof sceneDoc !== "object") return out;
    [sceneDoc.default, sceneDoc[fam]].forEach(function (group) {
      if (group && typeof group === "object") {
        Object.keys(group).forEach(function (element) {
          if (group[element] && typeof group[element] === "object") out[element] = group[element];
        });
      }
    });
    return out;
  }

  var lastSeen = { sport: "", family: "" };

  function inject(url, payload) {
    if (!payload || typeof payload !== "object") return payload;
    if (url === "/api/runtime-state") {
      lastSeen.sport = String(payload.sport || "");
      lastSeen.family = family(payload.sport);
      if (state.layouts) payload.layouts = state.layouts;
      // A board that is not switched on yet would preview as nothing.
      payload.scorebug_visible = true;
      state.force.forEach(function (name) {
        var group = FORCE[name] || {};
        Object.keys(group).forEach(function (key) {
          payload[key] = Object.assign({}, payload[key] || {}, group[key], { visible: true });
        });
      });
    } else if (url === "/api/pregame-presentation") {
      var game = payload.game = Object.assign({}, payload.game || {});
      lastSeen.sport = String(game.sport || "");
      lastSeen.family = family(game.sport);
      if (state.layouts) {
        payload.layout = {
          pregame: sceneOverrides(state.layouts, "pregame", lastSeen.family),
          halftime: sceneOverrides(state.layouts, "halftime", lastSeen.family)
        };
      }
      // Show the scene being edited regardless of what the live game is doing.
      payload.settings = Object.assign({}, payload.settings || {}, { mode: "pregame" });
      if (!game.broadcast_id) game.broadcast_id = "layout-preview";
      game.broadcast_phase = state.scene === "halftime" ? "halftime" : "scheduled";
    }
    return payload;
  }

  var pregameCache = null;
  var realFetch = window.fetch.bind(window);
  window.fetch = function (input, init) {
    var raw = typeof input === "string" ? input : (input && input.url) || "";
    var path;
    try { path = new URL(raw, window.location.href).pathname; } catch (_) { path = raw; }
    var method = String((init && init.method) || (input && input.method) || "GET").toUpperCase();

    if (method !== "GET" && method !== "HEAD") {
      // Never write anything from a preview (overlay-health, telemetry, ...).
      return Promise.resolve(new Response(JSON.stringify({ preview: true, blocked: path }), {
        status: 200, headers: { "content-type": "application/json" }
      }));
    }
    if (path !== "/api/runtime-state" && path !== "/api/pregame-presentation") return realFetch(input, init);

    // The pregame payload is slow to build (weather etc., ~1-2 s) and the overlay
    // only polls it every 2.5 s, so an edit would take several seconds to show.
    // Serve it from a recent copy of the REAL response and re-apply the current
    // preview on every poll instead; the copy is refreshed at most every 8 s.
    if (path === "/api/pregame-presentation" && pregameCache && Date.now() - pregameCache.at < 8000) {
      return Promise.resolve(new Response(JSON.stringify(inject(path, JSON.parse(pregameCache.text))), {
        status: 200, headers: { "content-type": "application/json" }
      }));
    }

    return realFetch(input, init).then(function (response) {
      if (path === "/api/pregame-presentation" && response.ok) {
        return response.clone().text().then(function (text) {
          pregameCache = { text: text, at: Date.now() };
          return new Response(JSON.stringify(inject(path, JSON.parse(text))), {
            status: 200, headers: { "content-type": "application/json" }
          });
        }, function () { return response; });
      }
      return response.clone().json().then(function (json) {
        return new Response(JSON.stringify(inject(path, json)), {
          status: response.status, headers: { "content-type": "application/json" }
        });
      }, function () { return response; });
    });
  };
  if (navigator.sendBeacon) navigator.sendBeacon = function () { return true; };

  window.addEventListener("message", function (event) {
    if (event.source !== window.parent || event.origin !== ORIGIN) return;
    var data = event.data;
    if (!data || data.type !== "csrn-layout-preview") return;
    state.layouts = data.layouts && typeof data.layouts === "object" ? data.layouts : null;
    state.force = Array.isArray(data.force) ? data.force.filter(function (n) { return FORCE[n]; }) : [];
    state.scene = data.scene === "pregame" || data.scene === "halftime" ? data.scene : "in_game";
  });

  function report() {
    var binding = window.CSRNProductionThemeBindingState;
    try {
      window.parent.postMessage({
        type: "csrn-layout-preview-status",
        sport: lastSeen.sport,
        family: lastSeen.family,
        // pregame/halftime overlays are not theme-bound; in-game layouts only
        // apply to a themed package (the classic overlay has no layout hook).
        themed: state.scene === "in_game" ? Boolean(binding && binding.active) : true,
        scene: state.scene,
        applied: Boolean(state.layouts)
      }, ORIGIN);
    } catch (_) { /* parent gone */ }
  }

  window.parent.postMessage({ type: "csrn-layout-preview-ready" }, ORIGIN);
  window.setInterval(report, 1000);
})();
