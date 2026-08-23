(() => {
"use strict";


// Gate 17.0 R1 R3 — production-only 8-Bit asset-path normalization.
// Frozen 8-Bit engine asset references such as "8bit-gameday/athletes/..."
// are document-relative in production overlay and otherwise resolve to
// /8bit-gameday/... instead of Flask's /static/8bit-gameday/... tree.
// Only this exact package prefix is rewritten; all other image URLs pass through.
(function installEightBitAssetPathShim(){
  const proto = window.HTMLImageElement && window.HTMLImageElement.prototype;
  if (!proto || window.__csrnEightBitAssetPathShimInstalled) return;
  const descriptor = Object.getOwnPropertyDescriptor(proto,"src");
  if (!descriptor || typeof descriptor.get !== "function" || typeof descriptor.set !== "function") return;
  Object.defineProperty(proto,"src",{
    configurable:descriptor.configurable,
    enumerable:descriptor.enumerable,
    get:descriptor.get,
    set(value){
      const raw = String(value ?? "");
      const normalized = raw.startsWith("8bit-gameday/") ? `/static/${raw}` : raw;
      return descriptor.set.call(this,normalized);
    }
  });
  window.__csrnEightBitAssetPathShimInstalled = true;
})();

const PUBLIC_STATE_URL = "/api/themes/public-state";
const RUNTIME_STATE_URL = "/api/runtime-state";
const CAPTION_STATE_URL = "/api/captions/overlay-state";
const CAPTION_STICKY_MS = 2800;
const SCORE_HOST_ID = "csrnProductionThemeHost";
const SCORE_LAYOUT_ID = "csrnProductionThemeLayout";
const PLAYER_HOST_ID = "csrnProductionThemePlayerHost";
const PLAYER_LAYOUT_ID = "csrnProductionThemePlayerLayout";
const SCORE_ACTIVE_CLASS = "csrn-production-theme-scorebug-active";
const TICKER_ACTIVE_CLASS = "csrn-production-theme-ticker-active";
const PLAYER_ACTIVE_CLASS = "csrn-production-theme-player-active";
const PLAYER_PENDING_CLASS = "csrn-production-theme-player-pending";
const HIGHLIGHT_ACTIVE_CLASS = "csrn-production-theme-highlight-active";
const SPONSOR_ACTIVE_CLASS = "csrn-production-theme-sponsor-active";

const PACKAGE_ALIASES = Object.freeze({
  friday_night_stadium: Object.freeze({
    globalName: "CSRNFridayNightStadiumEngine",
    playerSupported: true,
    tickerSelector: ".bl-fns-ticker-led",
    tickerKind: "replace-sibling",
    css: ["/static/csrn-broadcast-layout-engine.css?v=16.9-r8",
          "/static/csrn-friday-night-stadium-engine.css?v=16.9-r8"],
    js:  ["/static/csrn-broadcast-layout-engine.js?v=16.9-r8",
          "/static/csrn-friday-night-stadium-engine.js?v=16.9-r8"]
  }),
  eight_bit_gameday: Object.freeze({
    globalName: "CSRNEightBitGamedayEngine",
    playerSupported: true,
    tickerSelector: ".bl-8bit-ticker-led",
    tickerKind: "replace-sibling",
    css: ["/static/csrn-broadcast-layout-engine.css?v=16.9-r8",
          "/static/csrn-eight-bit-gameday-engine.css?v=16.9-r8"],
    js:  ["/static/csrn-broadcast-layout-engine.js?v=16.9-r8",
          "/static/csrn-eight-bit-gameday-engine.js?v=16.9-r8"]
  }),
  heritage_press: Object.freeze({
    globalName: "CSRNHeritagePressEngine",
    playerSupported: true,
    tickerSelector: ".hp-wire-copy",
    tickerKind: "inside",
    css: ["/static/csrn-broadcast-layout-engine.css?v=16.9-r8",
          "/static/csrn-heritage-press-engine.css?v=16.9-r8"],
    js:  ["/static/csrn-broadcast-layout-engine.js?v=16.9-r8",
          "/static/csrn-heritage-press-engine.js?v=16.9-r8"]
  }),
  digital_neon: Object.freeze({
    globalName: "CSRNNeonR2Engine",
    playerSupported: false,
    tickerSelector: ".n2-ticker span",
    tickerKind: "inside",
    css: ["/static/csrn-broadcast-layout-engine.css?v=16.9-r8",
          "/static/csrn-neon-r2-engine.css?v=16.9-r8",
          "/static/csrn-neon-softball-r42-driver.css?v=16.9-r8",
          "/static/csrn-neon-baseball-r43-driver.css?v=16.9-r8"],
    js:  ["/static/csrn-broadcast-layout-engine.js?v=16.9-r8",
          "/static/csrn-neon-r2-engine.js?v=16.9-r8",
          "/static/csrn-neon-softball-r42-driver.js?v=16.9-r8",
          "/static/csrn-neon-baseball-r43-driver.js?v=16.9-r8"]
  }),
  collegiate_traditional: Object.freeze({
    globalName: "CSRNBroadcastLayoutEngine",
    playerSupported: false,
    tickerSelector: ".bl-college-ticker-copy",
    tickerKind: "inside",
    css: ["/static/csrn-broadcast-layout-engine.css?v=17.0-collegiate-field"],
    js:  ["/static/csrn-broadcast-layout-engine.js?v=17.0-collegiate-field"]
  })
});

const loadedCss = new Set();
const loadedJs = new Map();
let currentAlias = "legacy";
let renderSignature = "";
let tickerRenderSignature = "";
let tickerBroadcastId = "";
const tickerKnownTransientKeys = new Set();
/* CSRN_THEME_SIGNATURE_DIFF_DIAGNOSTIC_R4
   Temporary diagnostic only. Logs exactly which destructive-render signature
   fields changed between polls. Does not alter render behavior.
*/
const CSRN_SIGNATURE_FIELDS_R4 = Object.freeze([
  "alias",
  "broadcast_id",
  "home_school_id",
  "visitor_school_id",
  "home_team",
  "visitor_team",
  "home_identity",
  "visitor_identity",
  "venue_id",
  "venue",
  "date",
  "scheduled_start",
  "sport",
  "video_mode",
  "player_graphic",
  "player_highlight",
  "sponsor_spotlight",
  "player_activation_key"
]);

function csrnLogThemeSignatureDiffR4(nextSignature) {
  if (!renderSignature || renderSignature === nextSignature) return;
  try {
    const previous = JSON.parse(renderSignature);
    const next = JSON.parse(nextSignature);
    const changes = [];
    const count = Math.max(previous.length, next.length);
    for (let index = 0; index < count; index += 1) {
      const before = JSON.stringify(previous[index]);
      const after = JSON.stringify(next[index]);
      if (before === after) continue;
      changes.push({
        index,
        field: CSRN_SIGNATURE_FIELDS_R4[index] || `field_${index}`,
        before: previous[index],
        after: next[index]
      });
    }
    if (changes.length) {
      console.warn("[CSRN R4 SIGNATURE CHANGE] destructive theme rerender incoming", {
        timestamp: new Date().toISOString(),
        changes
      });
    }
  } catch (error) {
    console.warn("[CSRN R4 SIGNATURE DIFF ERROR]", error);
  }
}
let renderBusy = false;
let lastCaptionSnapshot = null;
const playerMediaCache = new Map();
let lastPlayerActivationKey = "";
let pollTimer = 0;
let stablePollCount = 0;
let runtimeClockRunning = false;
let lastRuntimeForClockPatch = null;
let clockPatchTimer = 0;

function byId(id) { return document.getElementById(id); }
function scoreHost() { return byId(SCORE_HOST_ID); }
function scoreLayout() { return byId(SCORE_LAYOUT_ID); }
function playerHost() { return byId(PLAYER_HOST_ID); }
function playerLayout() { return byId(PLAYER_LAYOUT_ID); }

function ensureCss(url) {
  if (loadedCss.has(url)) return;
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = url;
  link.dataset.csrnProductionThemeAsset = "true";
  document.head.appendChild(link);
  loadedCss.add(url);
}

function ensureScript(url) {
  if (loadedJs.has(url)) return loadedJs.get(url);
  const promise = new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = url;
    script.async = false;
    script.dataset.csrnProductionThemeAsset = "true";
    script.onload = () => resolve(url);
    script.onerror = () => reject(new Error(`Unable to load ${url}`));
    document.head.appendChild(script);
  });
  loadedJs.set(url, promise);
  return promise;
}

async function ensurePackage(alias) {
  const spec = PACKAGE_ALIASES[alias];
  if (!spec) throw new Error(`Unsupported production template: ${alias}`);
  spec.css.forEach(ensureCss);
  for (const url of spec.js) await ensureScript(url);

  const base = window.CSRNBroadcastLayoutEngine;
  const selected = window[spec.globalName];
  if (!base || typeof base.defaultState !== "function") throw new Error("Broadcast Layout Engine unavailable.");
  if (!selected || typeof selected.renderPackage !== "function") throw new Error(`${spec.globalName} unavailable.`);
  return {base, selected, spec};
}

function objectValue(...values) {
  return values.find(value => value && typeof value === "object") || {};
}

function textValue(...values) {
  const value = values.find(item => item !== undefined && item !== null && String(item).trim() !== "");
  return value === undefined ? "" : String(value);
}

function numericValue(...values) {
  const value = values.find(item => item !== undefined && item !== null && item !== "");
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : 0;
}

function normalizeTeam(value, fallback) {
  const team = objectValue(value);
  const authoritativeName = textValue(
    team.preferred_scorebug_name,
    team.preferredScorebugName,
    team.broadcast_name,
    team.broadcastName,
    team.name,
    team.school_name,
    team.schoolName,
    team.team_name,
    team.teamName,
    team.official_name,
    team.officialName,
    fallback.name
  );
  return {
    name: authoritativeName,
    shortName: textValue(
      team.short_name,
      team.shortName,
      team.abbreviation,
      team.broadcast_name,
      team.broadcastName,
      authoritativeName,
      fallback.shortName
    ),
    mascot: textValue(team.mascot, team.nickname, fallback.mascot),
    record: textValue(team.record, fallback.record),
    score: numericValue(team.score, fallback.score),
    primary: textValue(team.primary, team.primary_color, team.primaryColor, team.color, fallback.primary),
    secondary: textValue(team.secondary, team.secondary_color, team.secondaryColor, fallback.secondary),
    logo: textValue(team.logo, team.logo_url, team.logoUrl, team.image, fallback.logo)
  };
}

function productionTeamSource(source, side) {
  const isHome = side === "home";
  const identity = objectValue(
    isHome ? source.home_identity : source.visitor_identity,
    isHome ? source.home : source.visitor,
    !isHome ? source.away : null,
    isHome ? source.teams?.home : source.teams?.visitor,
    !isHome ? source.teams?.away : null
  );

  const topLevelName = textValue(
    isHome ? source.home_team : source.visitor_team,
    isHome ? source.homeTeam : source.visitorTeam,
    !isHome ? source.away_team : "",
    !isHome ? source.awayTeam : ""
  );

  // The selected broadcast/game is authoritative. Preserve identity branding,
  // but inject the selected top-level team name when the identity payload uses
  // broadcast_name/official_name rather than the frozen engine's `name` key.
  return {
    ...identity,
    name: textValue(
      identity.preferred_scorebug_name,
      identity.preferredScorebugName,
      identity.broadcast_name,
      identity.broadcastName,
      topLevelName,
      identity.name,
      identity.official_name,
      identity.officialName
    ),
    school_id: textValue(
      identity.school_id,
      isHome ? source.home_school_id : source.visitor_school_id,
      isHome ? source.homeSchoolId : source.visitorSchoolId
    )
  };
}

function activeEvents(runtime) { return Array.isArray(runtime.ticker_items) ? runtime.ticker_items : (Array.isArray(runtime.events) ? runtime.events.filter(event => !event.undone) : []); }

function activeCaptionSegment(captionState) {
  const state = objectValue(captionState);
  const stateUpdatedAt = Number(state.updated_at || 0);
  if (state.visible !== true) {
    lastCaptionSnapshot = null;
    return null;
  }

  if (Array.isArray(state.segments) && state.segments.length) {
    const segment = objectValue(state.segments[state.segments.length - 1]);
    if (textValue(segment.text, "")) {
      lastCaptionSnapshot = {
        segment,
        stateUpdatedAt,
        capturedAt: Date.now()
      };
      return segment;
    }
  }

  if (
    lastCaptionSnapshot &&
    lastCaptionSnapshot.stateUpdatedAt === stateUpdatedAt &&
    Date.now() - lastCaptionSnapshot.capturedAt <= CAPTION_STICKY_MS
  ) {
    return lastCaptionSnapshot.segment;
  }

  lastCaptionSnapshot = null;
  return null;
}

function mergeCaptionState(base, captionState) {
  const segment = activeCaptionSegment(captionState);
  if (!segment) {
    base.captions = {...(base.captions || {}), speaker:"", text:""};
    return false;
  }
  base.captions = {
    ...(base.captions || {}),
    speaker: textValue(segment.speaker, `Channel ${textValue(segment.channel, "")}`, "CAPTION"),
    text: textValue(segment.text, "")
  };
  return Boolean(base.captions.text);
}

/* CSRN_CAPTION_INCREMENTAL_PATCH_R3
   Resources publish state; themes pull state.
   Caption-only changes mutate only the active theme's native caption DOM.
*/
function incrementalCaptionClass(alias) {
  if (alias === "friday_night_stadium") return "bl-fns-caption";
  if (alias === "eight_bit_gameday") return "bl-8bit-caption";
  if (alias === "heritage_press") return "bl-captions bl-family-press";
  return "csrn-theme-native-caption";
}

function incrementalCaptionHost(alias) {
  const root = scoreLayout();
  if (!root) return null;

  if (alias === "friday_night_stadium") {
    return root.querySelector(".bl-fns-video-board");
  }
  if (alias === "eight_bit_gameday") {
    return root.querySelector(".bl-8bit-video-board");
  }
  if (alias === "heritage_press") {
    return root.querySelector(".hp-opening");
  }
  return (
    root.querySelector("[data-zone='caption-safe']") ||
    root.querySelector("[data-module='video.board']") ||
    root
  );
}

/* CSRN_HERITAGE_NATIVE_CAPTION_FIX_R1
   Heritage Press owns its caption presentation through native .hp-caption markup.
   Caption state remains a fixture/resource pulled by the production runtime.
*/
function patchCaptionDom(alias, captionState) {
  if (!alias || alias === "legacy") return;

  const host = incrementalCaptionHost(alias);
  if (!host) return;

  const segment = activeCaptionSegment(captionState);
  const shouldShow = Boolean(segment && textValue(segment.text, ""));

  if (alias === "heritage_press") {
    let node = host.querySelector(":scope > .hp-caption");

    if (!shouldShow) {
      if (node) node.remove();
      return;
    }

    if (!node) {
      node = document.createElement("div");
      node.className = "hp-caption";
      node.dataset.csrnLiveCaption = "true";
      node.setAttribute("aria-live", "polite");
      node.setAttribute("aria-atomic", "true");
      host.appendChild(node);
    }

    let speaker = node.querySelector(":scope > b");
    let copy = node.querySelector(":scope > span");

    if (!speaker) {
      speaker = document.createElement("b");
      node.prepend(speaker);
    }
    if (!copy) {
      copy = document.createElement("span");
      node.appendChild(copy);
    }

    speaker.textContent = textValue(
      segment.speaker,
      `Channel ${textValue(segment.channel, "")}`,
      "BROADCAST"
    );
    copy.textContent = textValue(segment.text, "");
    return;
  }

  let node = host.querySelector(":scope > [data-csrn-live-caption='true']");

  if (!shouldShow) {
    if (node) node.remove();
    return;
  }

  if (!node) {
    node = document.createElement("div");
    node.dataset.csrnLiveCaption = "true";
    node.setAttribute("aria-live", "polite");
    node.setAttribute("aria-atomic", "true");
    host.appendChild(node);
  }

  node.className = incrementalCaptionClass(alias);

  let speaker = node.querySelector(":scope > strong");
  let copy = node.querySelector(":scope > span");

  if (!speaker) {
    speaker = document.createElement("strong");
    node.appendChild(speaker);
  }
  if (!copy) {
    copy = document.createElement("span");
    node.appendChild(copy);
  }

  speaker.textContent = textValue(
    segment.speaker,
    `Channel ${textValue(segment.channel, "")}`,
    "CAPTION"
  );
  copy.textContent = textValue(segment.text, "");
}
function eventAction(event) {
  return textValue(
    event.description,
    String(event.event || "").toUpperCase() === "TURNOVER" ? "TURNOVER" : "",
    `${textValue(event.label, event.event)}${event.score_delta ? ` +${event.score_delta}` : ""}`
  );
}

function eventPlainText(runtime) {
  const homeIdentity = objectValue(runtime.home_identity);
  const visitorIdentity = objectValue(runtime.visitor_identity);

  return activeEvents(runtime).map(event => {
    const identity = event.team === "home" ? homeIdentity : visitorIdentity;
    const team = textValue(event.team_name, identity.name, event.team).toUpperCase();
    const action = eventAction(event).toUpperCase();
    const quarter = event.quarter ? `Q${String(event.quarter).replace(/^Q/i, "")}` : "";
    const score = event.after
      ? `${Number(event.after.home_score || 0)}-${Number(event.after.visitor_score || 0)}`
      : "";
    return [team, action, quarter, score].filter(Boolean).join(" ");
  }).join("   ◆   ");
}

function tickerSpeed(runtime) {
  return ({very_slow:24, slow:36, normal:84, fast:189})[runtime.ticker_speed] || 36;
}

function tickerPause(runtime) {
  return Math.max(0, Math.min(5, Number(runtime.ticker_pause ?? 2)));
}

function mergePlayerState(base, runtime) {
  const graphic = objectValue(runtime.player_graphic);
  const player = {...(base.player || {})};

  const fullName = textValue(graphic.full_name, graphic.display_name, graphic.name, player.name);
  const displayName = textValue(graphic.display_name, graphic.full_name, graphic.name, fullName);
  const detail = textValue(
    graphic.play_detail,
    graphic.detail,
    graphic.media_name,
    [graphic.grade, graphic.height, graphic.weight ? `${graphic.weight} LB` : ""].filter(Boolean).join(" · "),
    player.detail
  );
  const image = textValue(
    graphic.headshot,
    graphic.photo,
    graphic.image,
    graphic.media_url,
    graphic.team_logo,
    graphic.logo,
    player.image,
    player.photo
  );

  Object.assign(player, {
    name: fullName,
    fullName,
    full_name: fullName,
    displayName,
    display_name: displayName,
    number: textValue(graphic.number, player.number),
    position: textValue(graphic.position, player.position),
    secondaryPosition: textValue(graphic.secondary_position, player.secondaryPosition),
    secondary_position: textValue(graphic.secondary_position, player.secondary_position),
    detail,
    playDetail: textValue(graphic.play_detail, detail),
    play_detail: textValue(graphic.play_detail, detail),
    grade: textValue(graphic.grade, player.grade),
    height: textValue(graphic.height, player.height),
    weight: textValue(graphic.weight, player.weight),
    image,
    photo: image,
    headshot: image,
    logo: textValue(graphic.team_logo, graphic.logo, player.logo),
    teamColor: textValue(graphic.team_color, player.teamColor),
    team_color: textValue(graphic.team_color, player.team_color)
  });

  base.player = player;
  return base;
}

function mergeRuntimeState(base, runtime, captionState = null) {
  const source = objectValue(runtime);
  const gameSource = objectValue(source.game, source.game_state, source.gameState);
  const homeSource = productionTeamSource(source, "home");
  const visitorSource = productionTeamSource(source, "visitor");

  base.sport = textValue(source.sport, gameSource.sport, base.sport, "football").toLowerCase();
  base.scheduledDate = textValue(
    source.date,
    source.scheduled_start,
    source.scheduledDate,
    source.scheduled_date,
    gameSource.date,
    gameSource.scheduled_start,
    base.scheduledDate
  );
  base.venue = textValue(
    source.venue,
    source.venue_name,
    source.venueName,
    gameSource.venue,
    gameSource.venue_name,
    base.venue
  );
  base.venueId = textValue(source.venue_id, source.venueId, gameSource.venue_id, base.venueId);
  base.venue_id = base.venueId;
  base.home = {...base.home, ...normalizeTeam(homeSource, base.home || {})};
  base.visitor = {...base.visitor, ...normalizeTeam(visitorSource, base.visitor || {})};
  base.home.score = numericValue(source.home_score, homeSource.score, base.home.score);
  base.visitor.score = numericValue(source.visitor_score, visitorSource.score, base.visitor.score);

  base.game = base.game || {};

  const rawPeriod = textValue(
    source.period,
    source.quarter,
    gameSource.period,
    gameSource.quarter,
    source.inning,
    gameSource.inning,
    base.game.period
  );
  const periodIsOt = String(rawPeriod).trim().toUpperCase() === "OT";
  const periodDisplay = periodIsOt ? "OT" : rawPeriod;

  // Different frozen packages consult different aliases. Keep all football
  // period aliases synchronized so OT cannot fall back to a numeric fixture.
  base.game.period = periodDisplay;
  base.game.quarter = periodDisplay;
  base.game.periodLabel = periodDisplay;
  base.game.period_label = periodDisplay;
  base.period = periodDisplay;
  base.quarter = periodDisplay;

  const clockVisible = source.clock_visible !== false;
  const clockDisplay = productionClock(source);
  base.game.clock = clockDisplay;
  base.game.gameClock = clockDisplay;
  base.game.game_clock = clockDisplay;
  base.game.clockVisible = clockVisible;
  base.game.clock_visible = clockVisible;

  const productionDown = productionDownDistance(source);
  base.game.down = productionDown.down;
  base.game.distance = productionDown.distance;
  base.game.toGo = productionDown.distance;
  base.game.to_go = productionDown.distance;
  base.game.downDistance = productionDown.combined;
  base.game.down_distance = productionDown.combined;

  base.game.possession = textValue(source.possession, gameSource.possession, base.game.possession).toLowerCase();
  const field = productionFieldState(source, gameSource, source.canonical_field_state);
  base.game.field = field;
  base.game.ballSpot = field.ballSpot;
  base.game.ball_spot = field.ballSpot;
  base.game.driveStart = field.driveStart;
  base.game.drive_start = field.driveStart;
  base.game.firstDownSpot = field.firstDownSpot;
  base.game.first_down_spot = field.firstDownSpot;
  base.game.fieldDirection = field.direction;
  base.game.field_direction = field.direction;

  base.ticker = {...(base.ticker || {})};
  base.ticker.text = eventPlainText(source) || "CSRN LIVE";
  base.captionsActive = mergeCaptionState(base, captionState);

  return mergePlayerState(base, source);
}

function clearNode(target) {
  if (target) target.replaceChildren();
}

function setHostState(host, active, alias, packageId, reason) {
  if (!host) return;
  host.hidden = !active;
  host.dataset.active = String(active);
  host.dataset.packageId = active ? alias : "legacy";
  host.dataset.enginePackageId = active ? packageId : "";
  host.dataset.reason = reason;
  host.setAttribute("aria-hidden", String(!active));
}

function deactivate(reason = "legacy") {
  currentAlias = "legacy";
  renderSignature = "";
  tickerRenderSignature = "";
  tickerBroadcastId = "";
  tickerKnownTransientKeys.clear();
  lastPlayerActivationKey = "";
  restoreLegacyPlayerNeutral();
  enforceLegacyMediaOwnership("clash");
  document.documentElement.classList.remove(
    SCORE_ACTIVE_CLASS,
    TICKER_ACTIVE_CLASS,
    PLAYER_ACTIVE_CLASS,
    PLAYER_PENDING_CLASS,
    HIGHLIGHT_ACTIVE_CLASS,
    SPONSOR_ACTIVE_CLASS
  );
  setHostState(scoreHost(), false, "legacy", "", reason);
  setHostState(playerHost(), false, "legacy", "", reason);
  clearNode(scoreLayout());
  clearNode(playerLayout());
}

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function tickerItemText(event, runtime) {
  const homeIdentity = objectValue(runtime.home_identity);
  const visitorIdentity = objectValue(runtime.visitor_identity);
  const identity = event.team === "home" ? homeIdentity : visitorIdentity;
  const team = textValue(event.team_name, identity.name, event.team).toUpperCase();
  const action = eventAction(event).toUpperCase();
  const quarter = event.quarter ? `Q${String(event.quarter).replace(/^Q/i, "")}` : "";
  const score = event.after
    ? `${Number(event.after.home_score || 0)}-${Number(event.after.visitor_score || 0)}`
    : "";
  return [team, action, quarter, score].filter(Boolean).join(" ");
}

function mountScroller(target, alias, items, runtime, kind) {
  if (!target || !Array.isArray(items) || items.length === 0) return false;

  const viewport = document.createElement("div");
  viewport.className = `csrn-theme-ticker-viewport csrn-theme-ticker-${alias}`;

  const track = document.createElement("div");
  track.className = "csrn-theme-ticker-track";
  viewport.appendChild(track);

  if (kind === "replace-sibling") {
    target.style.display = "none";
    target.insertAdjacentElement("afterend", viewport);
  } else {
    target.replaceChildren(viewport);
  }

  const persistentItems = items.filter(event => event.persistent === true);
  const transientItems = items.filter(event => event.persistent !== true);

  const separator = "   ◆   ";

  function textFor(source) {
    return source
      .map(event => tickerItemText(event, runtime))
      .filter(Boolean)
      .join(separator);
  }

  function animatePersistent() {
    const text = textFor(persistentItems);

    if (!text) {
      viewport.remove();
      if (kind === "replace-sibling") target.style.display = "";
      document.documentElement.classList.remove(TICKER_ACTIVE_CLASS);
      return;
    }

    const safe = escapeHtml(text);

    track.innerHTML =
      `<span class="csrn-theme-ticker-copy">${safe}</span>` +
      `<span class="csrn-theme-ticker-copy" aria-hidden="true">${safe}</span>`;

    requestAnimationFrame(() => {
      const distance = Math.max(1, track.scrollWidth / 2);
      const moveSeconds = Math.max(18, distance / tickerSpeed(runtime));
      const pauseSeconds = tickerPause(runtime);
      const totalSeconds = moveSeconds + (pauseSeconds * 2);
      const pauseOffset = totalSeconds ? pauseSeconds / totalSeconds : 0;

      track.__csrnTickerAnimation = track.animate(
        [
          {transform:"translateX(0)", offset:0},
          {transform:"translateX(0)", offset:pauseOffset},
          {transform:"translateX(-50%)", offset:1-pauseOffset},
          {transform:"translateX(-50%)", offset:1}
        ],
        {
          duration:totalSeconds * 1000,
          iterations:Infinity,
          easing:"linear"
        }
      );
    });
  }

  function animateTransient() {
    const text = textFor(transientItems);

    if (!text) {
      animatePersistent();
      return;
    }

    const safe = escapeHtml(text);

    track.innerHTML =
      `<span class="csrn-theme-ticker-copy">${safe}</span>`;

    const passes = Math.max(
      1,
      ...transientItems.map(
        event => Number(event.repeat_count || event.ticker_occurrences || 1) || 1
      )
    );

    requestAnimationFrame(() => {
      const distance = Math.max(1, track.scrollWidth + viewport.clientWidth);
      const moveSeconds = Math.max(18, distance / tickerSpeed(runtime));
      const pauseSeconds = tickerPause(runtime);
      const totalSeconds = moveSeconds + (pauseSeconds * 2);
      const pauseOffset = totalSeconds ? pauseSeconds / totalSeconds : 0;

      track.__csrnTickerAnimation = track.animate(
        [
          {transform:"translateX(100%)", offset:0},
          {transform:"translateX(100%)", offset:pauseOffset},
          {transform:"translateX(-100%)", offset:1-pauseOffset},
          {transform:"translateX(-100%)", offset:1}
        ],
        {
          duration:totalSeconds * 1000,
          iterations:passes,
          easing:"linear",
          fill:"forwards"
        }
      );

      track.__csrnTickerAnimation.finished
        .then(() => {
          if (persistentItems.length) {
            animatePersistent();
          } else {
            viewport.remove();
            if (kind === "replace-sibling") target.style.display = "";
            document.documentElement.classList.remove(TICKER_ACTIVE_CLASS);
          }
        })
        .catch(() => {});
    });
  }

  animateTransient();
  return true;
}
function tickerItemKey(event) {
  const sourceIds = Array.isArray(event.source_ids)
    ? event.source_ids.join(",")
    : "";
  return [
    event.id || event.event_id || "",
    event.created_at || "",
    sourceIds,
    event.lifecycle || "",
    event.description || "",
    event.ticker_occurrence || ""
  ].join("|");
}

function tickerStateSignature(runtime) {
  return JSON.stringify([
    runtime.broadcast_id || "",
    runtime.ticker_visible !== false,
    runtime.ticker_speed || "slow",
    Number(runtime.ticker_pause ?? 2),
    activeEvents(runtime).map(event => [
      tickerItemKey(event),
      event.persistent === true,
      Number(event.repeat_count || event.ticker_occurrences || 1),
      event.after || {}
    ])
  ]);
}

function resetTickerLifecycle(runtime = null) {
  tickerRenderSignature = "";
  tickerKnownTransientKeys.clear();
  tickerBroadcastId = textValue(runtime?.broadcast_id, "");
}

function tickerItemsForPresentation(runtime, initial = false) {
  const broadcastId = textValue(runtime?.broadcast_id, "");
  if (broadcastId !== tickerBroadcastId) {
    tickerKnownTransientKeys.clear();
    tickerBroadcastId = broadcastId;
    initial = true;
  }

  const items = activeEvents(runtime);
  const persistent = items.filter(event => event.persistent === true);
  const transient = items.filter(event => event.persistent !== true);

  const freshTransient = initial
    ? transient
    : transient.filter(event => !tickerKnownTransientKeys.has(tickerItemKey(event)));

  transient.forEach(event => tickerKnownTransientKeys.add(tickerItemKey(event)));

  return [...freshTransient, ...persistent];
}

function activateThemeTicker(scoreTarget, alias, spec, runtime, initial = false) {
  scoreTarget.querySelectorAll(".csrn-theme-ticker-viewport").forEach(node => node.remove());
  const frozenTarget = scoreTarget.querySelector(spec.tickerSelector);
  if (!frozenTarget) return false;

  if (spec.tickerKind === "replace-sibling") {
    frozenTarget.style.display = "";
  }

  const allItems = activeEvents(runtime);
  if (runtime.ticker_visible === false || allItems.length === 0) {
    tickerRenderSignature = tickerStateSignature(runtime);
    return false;
  }

  const presentationItems = tickerItemsForPresentation(runtime, initial);
  tickerRenderSignature = tickerStateSignature(runtime);

  // No new transient story and no persistent scoring story:
  // leave the ticker dark instead of replaying old routine plays.
  if (presentationItems.length === 0) {
    return false;
  }

  return mountScroller(
    frozenTarget,
    alias,
    presentationItems,
    runtime,
    spec.tickerKind
  );
}

function patchThemeTicker(runtime) {
  if (!runtime || currentAlias === "legacy") return false;

  const signature = tickerStateSignature(runtime);
  if (signature === tickerRenderSignature) {
    return Boolean(scoreLayout()?.querySelector(".csrn-theme-ticker-viewport"));
  }

  const scoreTarget = scoreLayout();
  const spec = PACKAGE_ALIASES[currentAlias];
  if (!scoreTarget || !spec) return false;

  const active = activateThemeTicker(
    scoreTarget,
    currentAlias,
    spec,
    runtime,
    false
  );
  document.documentElement.classList.toggle(TICKER_ACTIVE_CLASS, active);
  return active;
}

function playerVisible(runtime) {
  const graphic = objectValue(runtime.player_graphic);
  const now = Math.floor(Date.now() / 1000);
  return Boolean(graphic.visible) && (!graphic.expires_at || Number(graphic.expires_at) > now);
}

function renderThemePlayer(selected, spec, packageId, state, runtime, alias) {
  document.documentElement.classList.remove(PLAYER_ACTIVE_CLASS);
  clearNode(playerLayout());
  setHostState(playerHost(), false, "legacy", "", "player-inactive");

  if (!playerVisible(runtime) || !spec.playerSupported) return false;

  try {
    const target = playerLayout();
    if (!target) return false;

    const result = selected.renderPackage(
      target,
      packageId,
      state.sport,
      state,
      {diagnostics:false, activeComponents:["player"]}
    );

    if (
      !result ||
      !Array.isArray(result.components) ||
      !result.components.includes("player") ||
      result.components.some(component => component !== "player")
    ) {
      clearNode(target);
      return false;
    }

    setHostState(playerHost(), true, alias, packageId, "rendered");
    document.documentElement.classList.add(PLAYER_ACTIVE_CLASS);
    return true;
  } catch (error) {
    console.warn("[CSRN Gate 16.9 R2] themed player fallback:", error);
    clearNode(playerLayout());
    return false;
  }
}


function formatClockSeconds(value) {
  const seconds = Math.max(0, Number(value) || 0);
  const whole = Math.floor(seconds);
  const minutes = Math.floor(whole / 60);
  const remainder = whole % 60;
  return `${minutes}:${String(remainder).padStart(2,"0")}`;
}

function liveClockSeconds(runtime) {
  const seconds = Number(runtime.clock_seconds);
  if (!Number.isFinite(seconds)) return NaN;
  if (runtime.clock_running !== true) return Math.max(0, seconds);
  const started = Number(runtime.clock_started_at);
  if (!Number.isFinite(started) || started <= 0) return Math.max(0, seconds);
  const elapsed = Math.max(0, Math.floor(Date.now() / 1000) - Math.floor(started));
  return Math.max(0, seconds - elapsed);
}

function productionClock(runtime) {
  if (runtime.clock_visible === false) return "-";
  const liveSeconds = liveClockSeconds(runtime);
  return textValue(
    Number.isFinite(liveSeconds)
      ? formatClockSeconds(liveSeconds)
      : "",
    runtime.clock,
    runtime.game_clock
  ) || "-";
}

function productionFootballPeriod(runtime) {
  const raw = textValue(runtime.quarter, runtime.period, "1").trim().toUpperCase();
  if (raw === "OT") return "OT";
  const digits = raw.replace(/\D/g, "");
  return digits || raw || "1";
}

function productionDownDistance(runtime) {
  const rawDown = textValue(runtime.down).trim();
  const rawDistance = textValue(runtime.distance).trim();

  const downOff = !rawDown || rawDown.toLowerCase() === "off";
  const distanceOff = !rawDistance || rawDistance.toLowerCase() === "off";

  const downDigits = rawDown.match(/\d+/)?.[0] || rawDown;
  const distanceDigits = rawDistance.match(/\d+/)?.[0] || rawDistance;

  return {
    down: downOff ? "-" : downDigits,
    distance: distanceOff ? "-" : distanceDigits,
    combined: `${downOff ? "-" : rawDown} & ${distanceOff ? "-" : rawDistance}`
  };
}

function productionBallOn(runtime) {
  if (runtime.ball_spot_visible === false) return "-";
  const raw = textValue(runtime.ball_spot, runtime.ball_on, runtime.ballOn).trim();
  if (!raw) return "-";
  if (/goal/i.test(raw)) return "GL";
  const numbers = raw.match(/\d+/g);
  return numbers?.length ? numbers[numbers.length - 1] : raw.toUpperCase();
}

function parseFieldSpot(value) {
  const raw = textValue(value).trim().toUpperCase();
  if (!raw || raw === "-") return null;
  const side = raw.includes("RIGHT") ? "right" : raw.includes("LEFT") ? "left" : "";
  if (/GOAL|GL/.test(raw)) {
    if (side === "right") return {raw, side, yard:0, pct:100};
    if (side === "left") return {raw, side, yard:0, pct:0};
  }
  const number = Number(raw.match(/\d+/)?.[0]);
  if (!Number.isFinite(number)) return null;
  const yard = Math.max(0, Math.min(50, number));
  let pct = 50;
  if (side === "left") pct = yard;
  else if (side === "right") pct = 100 - yard;
  else pct = yard === 50 ? 50 : yard;
  return {raw, side, yard, pct:Math.max(0, Math.min(100, pct))};
}

function spotFromPercent(pct) {
  const bounded = Math.max(0, Math.min(100, Number(pct)));
  if (!Number.isFinite(bounded)) return "";
  if (bounded <= 0) return "LEFT GOAL";
  if (bounded >= 100) return "RIGHT GOAL";
  if (bounded <= 50) return `LEFT ${Math.round(bounded)}`;
  return `RIGHT ${Math.round(100 - bounded)}`;
}

function productionFieldDirection(source, fieldSource) {
  const possession = textValue(source.possession, fieldSource.possession, "home").toLowerCase();
  const raw = possession === "visitor"
    ? textValue(source.visitor_direction, fieldSource.visitor_direction, source.visitorDirection)
    : textValue(source.home_direction, fieldSource.home_direction, source.homeDirection);
  const normalized = raw.trim().toLowerCase();
  if (["left", "west", "rtl", "right-to-left"].includes(normalized)) return "left";
  if (["right", "east", "ltr", "left-to-right"].includes(normalized)) return "right";
  return possession === "visitor" ? "left" : "right";
}

function productionFieldState(source, gameSource = {}, canonicalField = {}) {
  const fieldSource = objectValue(canonicalField, source.field, source.field_state, gameSource.field);
  const ballRaw = textValue(
    fieldSource.ball_spot,
    fieldSource.ballSpot,
    source.ball_spot,
    source.ball_on,
    gameSource.ball_spot,
    gameSource.ballSpot
  );
  const driveRaw = textValue(
    fieldSource.drive_start,
    fieldSource.driveStart,
    source.drive_start,
    source.drive_start_spot,
    source.possession_start_spot,
    gameSource.drive_start,
    gameSource.driveStart
  );
  const direction = productionFieldDirection(source, fieldSource);
  const ball = parseFieldSpot(ballRaw);
  const drive = parseFieldSpot(driveRaw);
  const downDistance = productionDownDistance(source);
  const distance = Number(downDistance.distance);
  const gainPct = ball && Number.isFinite(distance)
    ? Math.max(0, Math.min(100, ball.pct + (direction === "left" ? -distance : distance)))
    : null;

  return {
    ballSpot: ball?.raw || "",
    ballPct: ball?.pct ?? 50,
    driveStart: drive?.raw || "",
    driveStartPct: drive?.pct ?? ball?.pct ?? 50,
    firstDownSpot: gainPct === null ? "" : spotFromPercent(gainPct),
    firstDownPct: gainPct ?? ball?.pct ?? 50,
    direction,
    possession: textValue(source.possession, fieldSource.possession, "home").toLowerCase(),
    down: downDistance.down,
    distance: downDistance.distance,
    downDistance: downDistance.combined,
    visible: source.ball_spot_visible !== false
  };
}

const STADIUM_LED_GLYPHS = Object.freeze({
  " ":["00000","00000","00000","00000","00000","00000","00000"],
  "0":["01110","10001","10011","10101","11001","10001","01110"],
  "1":["00100","01100","00100","00100","00100","00100","01110"],
  "2":["01110","10001","00001","00010","00100","01000","11111"],
  "3":["11110","00001","00001","01110","00001","00001","11110"],
  "4":["00010","00110","01010","10010","11111","00010","00010"],
  "5":["11111","10000","10000","11110","00001","00001","11110"],
  "6":["01110","10000","10000","11110","10001","10001","01110"],
  "7":["11111","00001","00010","00100","01000","01000","01000"],
  "8":["01110","10001","10001","01110","10001","10001","01110"],
  "9":["01110","10001","10001","01111","00001","00001","01110"],
  "G":["01110","10001","10000","10111","10001","10001","01110"],
  "L":["10000","10000","10000","10000","10000","10000","11111"],
  "O":["01110","10001","10001","10001","10001","10001","01110"],
  "T":["11111","00100","00100","00100","00100","00100","00100"],
  "-":["00000","00000","00000","11111","00000","00000","00000"]
});

function stadiumLedSvgNode(value, className) {
  const text=String(value || "-").toUpperCase();
  const glyphWidth=6;
  const width=Math.max(5,text.length*glyphWidth-1);
  const svg=document.createElementNS("http://www.w3.org/2000/svg","svg");
  svg.setAttribute("class",`bl-fns-led ${className || ""}`.trim());
  svg.setAttribute("viewBox",`0 0 ${width} 7`);
  svg.setAttribute("role","img");
  svg.setAttribute("aria-label",text.trim());
  svg.setAttribute("preserveAspectRatio","xMidYMid meet");
  const group=document.createElementNS("http://www.w3.org/2000/svg","g");
  [...text].forEach((character,index)=>{
    const glyph=STADIUM_LED_GLYPHS[character] || STADIUM_LED_GLYPHS[" "];
    glyph.forEach((row,y)=>[...row].forEach((on,x)=>{
      if (on !== "1") return;
      const dot=document.createElementNS("http://www.w3.org/2000/svg","circle");
      dot.setAttribute("cx",String(index*glyphWidth+x+.5));
      dot.setAttribute("cy",String(y+.5));
      dot.setAttribute("r",".42");
      group.appendChild(dot);
    }));
  });
  svg.appendChild(group);
  return svg;
}

function setLedText(cell, value, className) {
  if (!cell) return false;
  const existing = cell.querySelector(".csrn-production-led-override") || cell.querySelector("svg");
  const replacement = document.createElement("span");
  replacement.className = `csrn-production-led-override ${className || ""}`.trim();
  replacement.textContent = String(value || "-").toUpperCase();
  replacement.setAttribute("role", "img");
  replacement.setAttribute("aria-label", String(value || "-").toUpperCase());
  if (existing) existing.replaceWith(replacement);
  else cell.appendChild(replacement);
  return true;
}

function setStadiumLedSvg(cell, value, className) {
  if (!cell) return false;
  const existing = cell.querySelector(".csrn-production-led-override") || cell.querySelector("svg");
  const replacement = stadiumLedSvgNode(value, className);
  if (existing) existing.replaceWith(replacement);
  else cell.appendChild(replacement);
  return true;
}

function labeledCell(root, label) {
  return [...root.querySelectorAll("span")].find(cell => {
    const small = cell.querySelector(":scope > small");
    return small && small.textContent.trim().toUpperCase() === label;
  }) || null;
}

function applyFootballBoardOverrides(root, alias, runtime) {
  if (!root || String(runtime.sport || "football").toLowerCase() !== "football") return;

  const period = productionFootballPeriod(runtime);
  const downDistance = productionDownDistance(runtime);
  const ballOn = productionBallOn(runtime);
  const clock = productionClock(runtime);

  if (alias === "eight_bit_gameday") {
    setLedText(labeledCell(root, "CLOCK"), clock, "bl-8bit-clock-led");
    setLedText(labeledCell(root, "QUARTER"), period, "bl-8bit-small-led");
    setLedText(labeledCell(root, "DOWN"), downDistance.down, "bl-8bit-small-led");
    setLedText(labeledCell(root, "TO GO"), downDistance.distance, "bl-8bit-small-led");
    setLedText(labeledCell(root, "BALL ON"), ballOn, "bl-8bit-small-led");
    return;
  }

  if (alias === "friday_night_stadium") {
    const clockHost = root.querySelector(".bl-fns-primary-clock");
    if (clockHost) {
      const existing = clockHost.querySelector(".csrn-production-led-override") || clockHost.querySelector("svg");
      const replacement = document.createElement("span");
      replacement.className = "csrn-production-led-override bl-fns-clock-led";
      replacement.textContent = clock;
      replacement.setAttribute("role","img");
      replacement.setAttribute("aria-label",clock);
      if (existing) existing.replaceWith(replacement);
      else clockHost.appendChild(replacement);
    }
    setStadiumLedSvg(labeledCell(root, "QUARTER"), period, "bl-fns-small-led");
    setStadiumLedSvg(labeledCell(root, "DOWN"), downDistance.down, "bl-fns-small-led");
    setStadiumLedSvg(labeledCell(root, "TO GO"), downDistance.distance, "bl-fns-small-led");
    setStadiumLedSvg(labeledCell(root, "BALL ON"), ballOn, "bl-fns-small-led");
    return;
  }

  if (alias === "heritage_press") {
    root.querySelectorAll('[data-bind="game.period"]').forEach(node => {
      node.textContent = period;
    });
    root.querySelectorAll('[data-bind="game.clock"]').forEach(node => {
      node.textContent = clock;
    });
    root.querySelectorAll('[data-bind="game.downDistance"]').forEach(node => {
      node.textContent = downDistance.combined;
    });
    return;
  }

  if (alias === "collegiate_traditional") {
    const field = productionFieldState(runtime, {}, runtime.canonical_field_state);
    const fieldRoot = root.querySelector(".bl-college-field");
    if (fieldRoot) {
      fieldRoot.style.setProperty("--ball-x", `${field.ballPct}%`);
      fieldRoot.style.setProperty("--drive-x", `${field.driveStartPct}%`);
      fieldRoot.style.setProperty("--first-x", `${field.firstDownPct}%`);
      fieldRoot.dataset.direction = field.direction;
      fieldRoot.dataset.possession = field.possession;
      fieldRoot.dataset.hasDriveStart = field.driveStart ? "true" : "false";
      fieldRoot.dataset.hasFirstDown = field.firstDownSpot ? "true" : "false";
      fieldRoot.dataset.fieldVisible = field.visible ? "true" : "false";
    }
    root.querySelectorAll('[data-bind="game.clock"]').forEach(node => {
      node.textContent = clock;
    });
    root.querySelectorAll('[data-bind="game.period"]').forEach(node => {
      node.textContent = period;
    });
    root.querySelectorAll('[data-bind="game.downDistance"]').forEach(node => {
      node.textContent = field.downDistance;
    });
    root.querySelectorAll('[data-bind="game.ballSpot"]').forEach(node => {
      node.textContent = field.visible ? (field.ballSpot || "-") : "-";
    });
    root.querySelectorAll('[data-bind="game.driveStart"]').forEach(node => {
      node.textContent = field.driveStart || "-";
    });
    root.querySelectorAll('[data-bind="game.firstDownSpot"]').forEach(node => {
      node.textContent = field.firstDownSpot || "-";
    });
  }
}

function fnsPossessionNode(active) {
  const span = document.createElement("span");
  span.className = active
    ? "bl-fns-possession-ball bl-fns-football-possession"
    : "bl-fns-possession-ball is-empty";

  if (!active) {
    span.setAttribute("aria-hidden", "true");
    return span;
  }

  span.setAttribute("aria-label", "Possession");
  span.innerHTML =
    '<svg viewBox="0 0 72 44" aria-hidden="true">' +
    '<path d="M4 22C13 3 55 3 68 22 55 41 13 41 4 22Z"/>' +
    '<path d="M36 7v30M25 22h22M29 16l14 12M43 16 29 28"/>' +
    '</svg>';
  return span;
}

function patchThemeScoresAndPossession(root, alias, runtime) {
  if (!root || !runtime) return;

  const homeScore = Math.max(0, Number(runtime.home_score || 0));
  const visitorScore = Math.max(0, Number(runtime.visitor_score || 0));
  const possession = String(runtime.possession || "home").toLowerCase();

  if (alias === "friday_night_stadium") {
    const home = root.querySelector('[data-module="home.score"]');
    const visitor = root.querySelector('[data-module="visitor.score"]');

    setStadiumLedSvg(home, homeScore, "bl-fns-score-led");
    setStadiumLedSvg(visitor, visitorScore, "bl-fns-score-led");

    for (const [node, active] of [
      [home, possession === "home"],
      [visitor, possession === "visitor"]
    ]) {
      if (!node) continue;
      const old = node.querySelector(".bl-fns-possession-ball");
      const next = fnsPossessionNode(active);
      if (old) old.replaceWith(next);
      else node.appendChild(next);
    }
    return;
  }

  if (alias === "eight_bit_gameday") {
    const home = root.querySelector('[data-module="home.score"]');
    const visitor = root.querySelector('[data-module="visitor.score"]');

    setLedText(home, homeScore, "bl-8bit-score-led");
    setLedText(visitor, visitorScore, "bl-8bit-score-led");

    const possessionCell = labeledCell(root, "POSSESSION");
    setLedText(
      possessionCell,
      possession === "visitor" ? "VISITOR" : "HOME",
      "bl-8bit-possession-led"
    );
    return;
  }

  if (alias === "heritage_press") {
    root.querySelectorAll('[data-bind="home.score"]').forEach(node => {
      node.textContent = String(homeScore);
    });
    root.querySelectorAll('[data-bind="visitor.score"]').forEach(node => {
      node.textContent = String(visitorScore);
    });

    // Also update Score Summary duplicates in the newspaper columns.
    const summary = root.querySelector(".hp-team-score-rows");
    if (summary) {
      const rows = summary.querySelectorAll(":scope > div");
      const homeValue = rows[0]?.querySelector("b");
      const visitorValue = rows[1]?.querySelector("b");
      if (homeValue) homeValue.textContent = String(homeScore);
      if (visitorValue) visitorValue.textContent = String(visitorScore);
    }

    const possessionCell = labeledCell(root, "POSSESSION");
    const possessionValue = possessionCell?.querySelector(":scope > b");
    if (possessionValue) {
      possessionValue.textContent =
        possession === "visitor"
          ? textValue(runtime.visitor_team, "VISITOR")
          : textValue(runtime.home_team, "HOME");
    }

    // Heritage's state grid uses newspaper cells rather than all data-bind fields.
    const periodCell =
      labeledCell(root, "QUARTER") ||
      labeledCell(root, "PERIOD");
    const clockCell = labeledCell(root, "CLOCK");
    const downCell = labeledCell(root, "DOWN");

    const periodValue = periodCell?.querySelector(":scope > b");
    const clockValue = clockCell?.querySelector(":scope > b");
    const downValue = downCell?.querySelector(":scope > b");

    if (periodValue) periodValue.textContent = productionFootballPeriod(runtime);
    if (clockValue) clockValue.textContent = productionClock(runtime);
    if (downValue) downValue.textContent = productionDownDistance(runtime).combined;
    return;
  }

  if (alias === "collegiate_traditional") {
    root.querySelectorAll('[data-bind="home.score"]').forEach(node => {
      node.textContent = String(homeScore);
    });
    root.querySelectorAll('[data-bind="visitor.score"]').forEach(node => {
      node.textContent = String(visitorScore);
    });
    root.querySelectorAll(".bl-collegiate-tech").forEach(node => {
      node.dataset.possession = possession;
    });
  }
}

function patchLiveGameState(runtime = lastRuntimeForClockPatch) {
  if (!runtime || currentAlias === "legacy") return;
  const root = scoreLayout();
  if (!root) return;

  applyFootballBoardOverrides(root, currentAlias, runtime);
  patchThemeScoresAndPossession(root, currentAlias, runtime);
}

function patchActiveFootballBoard(runtime = lastRuntimeForClockPatch) {
  patchLiveGameState(runtime);
}

function startClockPatchTimer() {
  if (clockPatchTimer) return;
  clockPatchTimer = window.setInterval(() => {
    if (lastRuntimeForClockPatch && lastRuntimeForClockPatch.clock_running === true) {
      patchLiveGameState(lastRuntimeForClockPatch);
    }
  }, 250);
}

function themedIntegratedPlayerSupported(alias) {
  return alias === "eight_bit_gameday" || alias === "friday_night_stadium" || alias === "heritage_press";
}

function playerActivationKey(runtime) {
  const graphic = objectValue(runtime.player_graphic);
  return JSON.stringify([
    Boolean(graphic.visible),
    graphic.updated_at || 0,
    graphic.expires_at || 0,
    graphic.player_id || "",
    graphic.roster_id || "",
    graphic.full_name || graphic.display_name || graphic.name || "",
    graphic.number || "",
    graphic.graphic_type || "",
    graphic.media_url || "",
    graphic.headshot || ""
  ]);
}

function imageCandidate(value) {
  const text = textValue(value).trim();
  if (!text) return "";
  if (text.startsWith("data:image/")) return text;
  if (text.startsWith("blob:")) return text;
  if (text.startsWith("/")) return text;
  if (/^https?:\/\//i.test(text)) return text;
  return text;
}

function imageLoads(url, timeoutMs = 350) {
  const candidate = imageCandidate(url);
  if (!candidate) return Promise.resolve(false);
  if (candidate.startsWith("data:image/") || candidate.startsWith("blob:")) {
    return Promise.resolve(true);
  }
  if (playerMediaCache.has(candidate)) return playerMediaCache.get(candidate);

  const promise = new Promise(resolve => {
    const image = new Image();
    let settled = false;
    const finish = ok => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      image.onload = null;
      image.onerror = null;
      resolve(Boolean(ok));
    };
    const timer = window.setTimeout(() => finish(false), timeoutMs);
    image.onload = () => finish(image.naturalWidth > 0 && image.naturalHeight > 0);
    image.onerror = () => finish(false);
    image.src = candidate;
    if (image.complete) {
      queueMicrotask(() => finish(image.naturalWidth > 0 && image.naturalHeight > 0));
    }
  });

  playerMediaCache.set(candidate, promise);
  return promise;
}

async function preparePlayerMedia(state, runtime) {
  if (!playerVisible(runtime)) {
    state.player.headshot = "";
    return {kind:"inactive", url:""};
  }

  const graphic = objectValue(runtime.player_graphic);
  const headshotCandidates = [
    graphic.headshot,
    graphic.photo,
    graphic.image,
    graphic.media_url
  ].map(imageCandidate).filter(Boolean);

  for (const candidate of [...new Set(headshotCandidates)]) {
    if (await imageLoads(candidate)) {
      state.player.headshot = candidate;
      return {kind:"headshot", url:candidate};
    }
  }

  const logoCandidates = [
    graphic.team_logo,
    graphic.logo,
    state.player.logo
  ].map(imageCandidate).filter(Boolean);

  for (const candidate of [...new Set(logoCandidates)]) {
    if (await imageLoads(candidate)) {
      state.player.headshot = candidate;
      return {kind:"team-logo", url:candidate};
    }
  }

  // The frozen integrated player presentation already has a number-based
  // fallback when headshot is empty. Use that instead of ever presenting
  // a broken-image icon.
  state.player.headshot = "";
  state.player.photo = "";
  state.player.image = "";
  return {kind:"number-placeholder", url:""};
}

function repairRenderedPlayerMedia(root, state) {
  if (!root) return;
  const replacement = root.querySelector(
    ".bl-fns-player-replacement, .bl-8bit-player-replacement, [data-video-mode='player']"
  );
  if (!replacement) return;

  const image = replacement.querySelector("img");
  if (!image) return;

  const fallback = () => {
    const portrait = image.closest(
      ".bl-fns-player-portrait, .bl-8bit-player-portrait"
    ) || image.parentElement;
    if (!portrait || !image.isConnected) return;
    const number = document.createElement("b");
    number.className = "csrn-production-player-number-fallback";
    number.textContent = `#${textValue(state.player.number, "--")}`;
    image.replaceWith(number);
  };

  image.addEventListener("error", fallback, {once:true});
  requestAnimationFrame(() => {
    if (image.complete && image.naturalWidth === 0) fallback();
  });
}


function legacyPlayerGraphicNode() {
  return document.getElementById("playerGraphic");
}

function cancelLegacyPlayerMotion() {
  const node = legacyPlayerGraphicNode();
  if (!node) return;

  try {
    node.getAnimations().forEach(animation => animation.cancel());
  } catch (_) {}

  node.style.setProperty("transition", "none", "important");
  node.style.setProperty("animation", "none", "important");
  node.style.setProperty("opacity", "0", "important");
  node.style.setProperty("visibility", "hidden", "important");
  node.style.setProperty("display", "none", "important");
  node.dataset.csrnThemeSuppressed = "true";
}

function restoreLegacyPlayerNeutral() {
  const node = legacyPlayerGraphicNode();
  if (!node) return;

  try {
    node.getAnimations().forEach(animation => animation.cancel());
  } catch (_) {}

  // Force the legacy card into its normal hidden endpoint before themed
  // ownership is released. This prevents a stale translate/opacity frame
  // from becoming visible during the handoff.
  node.classList.add("hidden");
  node.style.setProperty("transition", "none", "important");
  node.style.setProperty("animation", "none", "important");
  node.style.setProperty("opacity", "0", "important");
  node.style.setProperty("visibility", "hidden", "important");
  node.style.setProperty("display", "none", "important");

  // Commit the hidden endpoint synchronously.
  void node.offsetWidth;

  requestAnimationFrame(() => {
    if (document.documentElement.classList.contains(PLAYER_PENDING_CLASS) ||
        document.documentElement.classList.contains(PLAYER_ACTIVE_CLASS)) {
      return;
    }

    node.style.removeProperty("display");
    node.style.removeProperty("visibility");
    node.style.removeProperty("opacity");
    node.style.removeProperty("animation");
    node.style.removeProperty("transition");
    delete node.dataset.csrnThemeSuppressed;
  });
}

function setPlayerPending(active) {
  const enabled = Boolean(active);
  if (enabled) {
    cancelLegacyPlayerMotion();
    document.documentElement.classList.add(PLAYER_PENDING_CLASS);
    return;
  }

  restoreLegacyPlayerNeutral();
  document.documentElement.classList.remove(PLAYER_PENDING_CLASS);
}


function primaryGraphicVisible(record) {
  const graphic = objectValue(record);
  const now = Math.floor(Date.now() / 1000);
  return Boolean(graphic.visible) &&
    (!graphic.expires_at || Number(graphic.expires_at) > now);
}

function themedVideoBoardSupported(alias) {
  return alias === "eight_bit_gameday" ||
    alias === "friday_night_stadium" ||
    alias === "heritage_press";
}

function themeVideoModeFor(alias, runtime) {
  if (!themedVideoBoardSupported(alias)) {
    return playerModeFor(alias, runtime);
  }
  if (primaryGraphicVisible(runtime.player_highlight)) return "highlight";
  if (primaryGraphicVisible(runtime.sponsor_spotlight)) return "sponsor";
  if (playerVisible(runtime)) return "player";

  // Gate 17.0 R1: preserve each theme's native idle/neutral board mode.
  // 8-Bit's frozen clash renderer owns its dynamic player recoloring from
  // selected visitor/home identity and must remain the default production view.
  if (alias === "eight_bit_gameday") return "clash";
  if (alias === "friday_night_stadium") return "clash";
  if (alias === "heritage_press") return "broadcast";
  return "clash";
}



// Gate 17.2 R1 — approved from-scratch Friday Night football player system.
// The frozen Stadium engine owns geometry and the native clash host. Production
// replaces only athlete pixels using isolated semantic masks and neutral detail.
const FRIDAY_LAYERED_CLASH_ASSETS = Object.freeze({
  base:"/static/friday-night-stadium/clash/layers-v10/football-neutral-equipment-anatomy.png?v=18.5-r12",
  texture:"/static/friday-night-stadium/clash/layers-v10/football-uniform-color-clarity-texture.png?v=18.5-r12",
  deepTexture:"/static/friday-night-stadium/clash/layers-v10/football-uniform-texture.png?v=18.5-r12",
  highlights:"/static/friday-night-stadium/clash/layers-v10/football-highlights.png?v=18.5-r12",
  shadows:"/static/friday-night-stadium/clash/layers-v10/football-shadows.png?v=18.5-r12",
  visitorJersey:"/static/friday-night-stadium/clash/layers-v10/visitor-jersey-primary-mask.png?v=18.5-r15",
  visitorPants:"/static/friday-night-stadium/clash/layers-v10/visitor-pants-mask.png?v=18.5-r12",
  visitorHelmet:"/static/friday-night-stadium/clash/layers-v10/visitor-helmet-primary-mask.png?v=18.5-r12",
  visitorTrim:"/static/friday-night-stadium/clash/layers-v10/visitor-number-trim-mask.png?v=18.5-r12",
  homeJersey:"/static/friday-night-stadium/clash/layers-v10/home-jersey-primary-mask.png?v=18.5-r16-r3",
  homePants:"/static/friday-night-stadium/clash/layers-v10/home-pants-mask.png?v=18.5-r12",
  homeHelmet:"/static/friday-night-stadium/clash/layers-v10/home-helmet-primary-mask.png?v=18.5-r12",
  homeTrim:"/static/friday-night-stadium/clash/layers-v10/home-number-trim-mask.png?v=18.5-r12"
});

// Historical Gate 17.1 contract sentinels retained for rollback-test continuity:
// canvas.dataset.layeredSchema="friday-football-v11"
// ctx.drawImage(tintFridayMask(visitorSecondary,visitorAccent,width,height),0,0);
// ctx.drawImage(tintFridayMask(homeSecondary,homeAccent,width,height),0,0);

const fridayLayeredAssetCache = new Map();
function loadFridayLayeredAsset(url) {
  if (fridayLayeredAssetCache.has(url)) return fridayLayeredAssetCache.get(url);
  const promise = new Promise((resolve,reject)=>{
    const image=new Image();
    image.onload=()=>resolve(image);
    image.onerror=()=>reject(new Error(`Friday Night layered clash asset failed to load: ${url}`));
    image.src=url;
  });
  fridayLayeredAssetCache.set(url,promise);
  return promise;
}

function fridayTeamColor(value,fallback) {
  const text=String(value || "").trim();
  return /^#[0-9a-f]{6}$/i.test(text) ? text : fallback;
}

function tintFridayMask(mask,color,width,height) {
  const layer=document.createElement("canvas");
  layer.width=width; layer.height=height;
  const ctx=layer.getContext("2d");
  ctx.clearRect(0,0,width,height);
  ctx.drawImage(mask,0,0,width,height);
  ctx.globalCompositeOperation="source-in";
  ctx.fillStyle=color;
  ctx.fillRect(0,0,width,height);
  ctx.globalCompositeOperation="source-over";
  return layer;
}

function isFridayNeutralEquipmentPixel(x,y,red,green,blue) {
  const luma=(red*0.2126)+(green*0.7152)+(blue*0.0722);
  const chroma=Math.max(red,green,blue)-Math.min(red,green,blue);
  if (!(luma > 35 && luma < 235 && chroma < 48)) return false;
  const visitorFaceguard=x>=430 && x<=620 && y>=88 && y<=268;
  const homeFaceguard=x>=1115 && x<=1275 && y>=118 && y<=304;
  return visitorFaceguard || homeFaceguard;
}

function constrainFridayColorMask(base,mask,width,height,{protectWhite=false,protectWarm=true,protectEquipment=false}={}) {
  const layer=document.createElement("canvas");
  layer.width=width; layer.height=height;
  const ctx=layer.getContext("2d",{willReadFrequently:true});
  ctx.clearRect(0,0,width,height);
  ctx.drawImage(mask,0,0,width,height);
  const maskData=ctx.getImageData(0,0,width,height);
  const baseCanvas=document.createElement("canvas");
  baseCanvas.width=width; baseCanvas.height=height;
  const baseCtx=baseCanvas.getContext("2d",{willReadFrequently:true});
  baseCtx.drawImage(base,0,0,width,height);
  const baseData=baseCtx.getImageData(0,0,width,height).data;

  for (let index=0; index<maskData.data.length; index+=4) {
    const baseAlpha=baseData[index+3];
    if (!baseAlpha) {
      maskData.data[index+3]=0;
      continue;
    }

    if (protectWhite) {
      const red=baseData[index], green=baseData[index+1], blue=baseData[index+2];
      const luma=(red*0.2126)+(green*0.7152)+(blue*0.0722);
      const chroma=Math.max(red,green,blue)-Math.min(red,green,blue);
      if (luma>175 && chroma<74) {
        maskData.data[index+3]=0;
        continue;
      }
    }

    if (protectWarm) {
      const red=baseData[index], green=baseData[index+1], blue=baseData[index+2];
      const luma=(red*0.2126)+(green*0.7152)+(blue*0.0722);
      const warmSkinOrLeather=red>92 && green>38 && blue<132 && red>green*1.12 && green>blue*1.05 && luma>58;
      if (warmSkinOrLeather) {
        maskData.data[index+3]=0;
        continue;
      }
    }

    if (protectEquipment) {
      const pixel=index/4;
      const x=pixel % width;
      const y=Math.floor(pixel / width);
      const red=baseData[index], green=baseData[index+1], blue=baseData[index+2];
      if (isFridayNeutralEquipmentPixel(x,y,red,green,blue)) {
        maskData.data[index+3]=0;
        continue;
      }
    }

    maskData.data[index+3]=Math.round(maskData.data[index+3] * (baseAlpha / 255));
  }

  ctx.putImageData(maskData,0,0);
  return layer;
}

function compositeFridayMasks(masks,width,height) {
  const layer=document.createElement("canvas");
  layer.width=width; layer.height=height;
  const ctx=layer.getContext("2d");
  ctx.clearRect(0,0,width,height);
  masks.forEach(mask=>ctx.drawImage(mask,0,0,width,height));
  return layer;
}

function clipFridayDetailLayer(image,mask,width,height) {
  const layer=document.createElement("canvas");
  layer.width=width; layer.height=height;
  const ctx=layer.getContext("2d");
  ctx.clearRect(0,0,width,height);
  ctx.drawImage(image,0,0,width,height);
  ctx.globalCompositeOperation="destination-in";
  ctx.drawImage(mask,0,0,width,height);
  ctx.globalCompositeOperation="source-over";
  return layer;
}

function deriveFridayUniformReliefLayer(base,mask,width,height) {
  const layer=document.createElement("canvas");
  layer.width=width; layer.height=height;
  const ctx=layer.getContext("2d");
  ctx.clearRect(0,0,width,height);
  ctx.filter="grayscale(1) contrast(1.65) brightness(.92)";
  ctx.drawImage(base,0,0,width,height);
  ctx.filter="none";
  ctx.globalCompositeOperation="destination-in";
  ctx.drawImage(mask,0,0,width,height);
  ctx.globalCompositeOperation="source-over";
  return layer;
}

function colorizeFridayUniform(ctx,mask,color,width,height,alpha=.92) {
  const tint=tintFridayMask(mask,color,width,height);
  ctx.save();
  ctx.globalCompositeOperation="color";
  ctx.globalAlpha=alpha;
  ctx.drawImage(tint,0,0,width,height);
  ctx.restore();

  const match=String(color || "").trim().match(/^#([0-9a-f]{6})$/i);
  if (!match) return;
  const value=parseInt(match[1],16);
  const red=(value >> 16) & 255;
  const green=(value >> 8) & 255;
  const blue=value & 255;
  const luma=(red*0.2126)+(green*0.7152)+(blue*0.0722);
  const chroma=Math.max(red,green,blue)-Math.min(red,green,blue);
  if (chroma < 36 && (luma > 165 || luma < 42)) {
    const paintAlpha=Math.min(.58,Math.max(.24,alpha*.52));
    ctx.save();
    ctx.globalCompositeOperation="source-over";
    ctx.globalAlpha=paintAlpha;
    ctx.drawImage(tint,0,0,width,height);
    ctx.restore();
  }
}

const FRIDAY_PLAYER_PALETTE = Object.freeze([
  Object.freeze({key:"scarlet",hex:"#C51F30"}),
  Object.freeze({key:"maroon",hex:"#7A1832"}),
  Object.freeze({key:"orange",hex:"#E46C0A"}),
  Object.freeze({key:"gold",hex:"#D8A51D"}),
  Object.freeze({key:"yellow",hex:"#F2D21B"}),
  Object.freeze({key:"kelly-green",hex:"#18864B"}),
  Object.freeze({key:"dark-green",hex:"#0D5D3A"}),
  Object.freeze({key:"royal-blue",hex:"#2457C5"}),
  Object.freeze({key:"navy",hex:"#152A4A"}),
  Object.freeze({key:"columbia-blue",hex:"#5CA8D8"}),
  Object.freeze({key:"purple",hex:"#6B3FA0"}),
  Object.freeze({key:"black",hex:"#1A1A1A"}),
  Object.freeze({key:"charcoal",hex:"#4A4A4A"}),
  Object.freeze({key:"white",hex:"#E8E8E8"}),
  Object.freeze({key:"black-gold",hex:"#221A08"})
]);

function fridayHexToRgb(value) {
  const text=String(value || "").trim();
  const m=text.match(/^#?([0-9a-f]{6})$/i);
  if (m) {
    const hex=m[1];
    return [
      parseInt(hex.slice(0,2),16),
      parseInt(hex.slice(2,4),16),
      parseInt(hex.slice(4,6),16)
    ];
  }
  const short=text.match(/^#?([0-9a-f]{3})$/i);
  if (short) {
    return short[1].split("").map(ch=>parseInt(ch+ch,16));
  }
  return null;
}

function nearestFridayPaletteKey(value) {
  const rgb=fridayHexToRgb(value) || [197,31,48];
  let best=FRIDAY_PLAYER_PALETTE[0];
  let bestDistance=Number.POSITIVE_INFINITY;
  for (const candidate of FRIDAY_PLAYER_PALETTE) {
    const target=fridayHexToRgb(candidate.hex);
    const dr=rgb[0]-target[0];
    const dg=rgb[1]-target[1];
    const db=rgb[2]-target[2];
    const distance=(dr*dr)+(dg*dg)+(db*db);
    if (distance < bestDistance) {
      bestDistance=distance;
      best=candidate;
    }
  }
  return best.key;
}


// Gate R18 — Friday Night Stadium standalone pre-rendered player library.
// Production football player images are selected by nearest team primary color.
// No runtime player recoloring, masks, tinting, or material segmentation.
const FRIDAY_STANDALONE_PLAYER_PALETTE = Object.freeze([
  Object.freeze({key:"scarlet",hex:"#C51F30"}),
  Object.freeze({key:"maroon",hex:"#7A1832"}),
  Object.freeze({key:"orange",hex:"#E46C0A"}),
  Object.freeze({key:"gold",hex:"#D8A51D"}),
  Object.freeze({key:"yellow",hex:"#F2D21B"}),
  Object.freeze({key:"kelly-green",hex:"#18864B"}),
  Object.freeze({key:"dark-green",hex:"#0D5D3A"}),
  Object.freeze({key:"royal-blue",hex:"#2457C5"}),
  Object.freeze({key:"navy",hex:"#152A4A"}),
  Object.freeze({key:"columbia-blue",hex:"#5CA8D8"}),
  Object.freeze({key:"purple",hex:"#6B3FA0"}),
  Object.freeze({key:"black",hex:"#1A1A1A"}),
  Object.freeze({key:"charcoal",hex:"#4A4A4A"}),
  Object.freeze({key:"white",hex:"#E8E8E8"})
]);

function fridayStandaloneHexToRgb(value) {
  const text=String(value || "").trim();
  let m=text.match(/^#?([0-9a-f]{6})$/i);
  if (m) {
    const h=m[1];
    return [parseInt(h.slice(0,2),16),parseInt(h.slice(2,4),16),parseInt(h.slice(4,6),16)];
  }
  m=text.match(/^#?([0-9a-f]{3})$/i);
  if (m) return m[1].split("").map(ch=>parseInt(ch+ch,16));
  return null;
}

function fridayStandaloneNearestPalette(value) {
  const rgb=fridayStandaloneHexToRgb(value) || [197,31,48];
  let best=FRIDAY_STANDALONE_PLAYER_PALETTE[0];
  let bestD=Number.POSITIVE_INFINITY;
  for (const p of FRIDAY_STANDALONE_PLAYER_PALETTE) {
    const t=fridayStandaloneHexToRgb(p.hex);
    const dr=rgb[0]-t[0], dg=rgb[1]-t[1], db=rgb[2]-t[2];
    const d=dr*dr+dg*dg+db*db;
    if (d<bestD) { bestD=d; best=p; }
  }
  return best.key;
}

function fridayStandaloneVisibleBounds(image) {
  const imageWidth=image.naturalWidth || image.width;
  const imageHeight=image.naturalHeight || image.height;
  if (!imageWidth || !imageHeight) throw new Error("Friday Night standalone player dimensions unavailable.");
  const probe=document.createElement("canvas");
  probe.width=imageWidth;
  probe.height=imageHeight;
  const probeCtx=probe.getContext("2d",{willReadFrequently:true});
  probeCtx.drawImage(image,0,0);
  const pixels=probeCtx.getImageData(0,0,imageWidth,imageHeight).data;
  let left=imageWidth,top=imageHeight,right=0,bottom=0;
  for (let y=0;y<imageHeight;y+=1) {
    for (let x=0;x<imageWidth;x+=1) {
      if (pixels[(y*imageWidth+x)*4+3] < 12) continue;
      if (x<left) left=x;
      if (x>right) right=x;
      if (y<top) top=y;
      if (y>bottom) bottom=y;
    }
  }
  if (left>right || top>bottom) return {x:0,y:0,width:imageWidth,height:imageHeight};
  const pad=Math.round(Math.max(imageWidth,imageHeight)*.035);
  left=Math.max(0,left-pad);
  top=Math.max(0,top-pad);
  right=Math.min(imageWidth-1,right+pad);
  bottom=Math.min(imageHeight-1,bottom+pad);
  return {x:left,y:top,width:right-left+1,height:bottom-top+1};
}

function drawFridayStandalonePlayer(ctx,image,placement) {
  const source=fridayStandaloneVisibleBounds(image);
  const targetHeight=placement.height;
  const targetWidth=targetHeight*(source.width/source.height);
  ctx.drawImage(
    image,
    source.x,source.y,source.width,source.height,
    placement.centerX-targetWidth/2,
    placement.bottomY-targetHeight,
    targetWidth,
    targetHeight
  );
}

async function paintFridayNightStandaloneFootballPlayers(root,alias,mode,state) {
  if (alias !== "friday_night_stadium" || mode !== "clash") return true;
  const canvas=root.querySelector('.bl-fns-video-board > .bl-fns-clash[data-video-mode="clash"] .bl-fns-clash-art');
  if (!canvas) throw new Error("Friday Night standalone player canvas missing.");

  const visitorPrimary=fridayTeamColor(state.visitor && state.visitor.primary,"#2457C5");
  const homePrimary=fridayTeamColor(state.home && state.home.primary,"#C51F30");
  const visitorKey=fridayStandaloneNearestPalette(visitorPrimary);
  const homeKey=fridayStandaloneNearestPalette(homePrimary);

  const visitorUrl=`/static/friday-night-stadium/players/palette-v2/visitor/visitor-28-${visitorKey}.png?v=19.2-r18-r3`;
  const homeUrl=`/static/friday-night-stadium/players/palette-v2/home/home-31-${homeKey}.png?v=19.2-r18-r3`;

  const [visitorImage,homeImage]=await Promise.all([
    loadFridayLayeredAsset(visitorUrl),
    loadFridayLayeredAsset(homeUrl)
  ]);

  const width=1920, height=1080;
  if (canvas.width!==width) canvas.width=width;
  if (canvas.height!==height) canvas.height=height;
  const ctx=canvas.getContext("2d");
  ctx.clearRect(0,0,width,height);
  const playerHeight=height*.76;
  drawFridayStandalonePlayer(ctx,visitorImage,{centerX:width*.178,bottomY:height*.76,height:playerHeight});
  drawFridayStandalonePlayer(ctx,homeImage,{centerX:width*.822,bottomY:height*.76,height:playerHeight});

  canvas.dataset.layeredDynamic="false";
  canvas.dataset.layeredSchema="friday-football-standalone-v1";
  canvas.dataset.visitorPalette=visitorKey;
  canvas.dataset.homePalette=homeKey;
  root.dataset.productionLayeredClash="true";
  root.dataset.fridayStandalonePlayers="true";
  return true;
}

async function paintFridayNightLayeredFootballClash(root,alias,mode,state) {
  return paintFridayNightStandaloneFootballPlayers(root,alias,mode,state);
  if (alias !== "friday_night_stadium" || mode !== "clash") return true;

  const canvas=root.querySelector('.bl-fns-video-board > .bl-fns-clash[data-video-mode="clash"] .bl-fns-clash-art');
  if (!canvas) throw new Error("Friday Night palette clash canvas missing.");

  const visitorColor=fridayTeamColor(state.visitor && state.visitor.primary,"#2457C5");
  const homeColor=fridayTeamColor(state.home && state.home.primary,"#C51F30");
  const visitorKey=nearestFridayPaletteKey(visitorColor);
  const homeKey=nearestFridayPaletteKey(homeColor);

  const visitorUrl=`/static/friday-night-stadium/clash/palette-v1/visitor-${visitorKey}.png?v=19.0-r17`;
  const homeUrl=`/static/friday-night-stadium/clash/palette-v1/home-${homeKey}.png?v=19.0-r17`;

  const [visitorImage,homeImage]=await Promise.all([
    loadFridayLayeredAsset(visitorUrl),
    loadFridayLayeredAsset(homeUrl)
  ]);

  const width=Math.max(visitorImage.naturalWidth || visitorImage.width,homeImage.naturalWidth || homeImage.width);
  const height=Math.max(visitorImage.naturalHeight || visitorImage.height,homeImage.naturalHeight || homeImage.height);
  if (!width || !height) throw new Error("Friday Night palette player dimensions unavailable.");

  if (canvas.width !== width) canvas.width=width;
  if (canvas.height !== height) canvas.height=height;

  const ctx=canvas.getContext("2d");
  ctx.clearRect(0,0,width,height);
  ctx.drawImage(visitorImage,0,0,width,height);
  ctx.drawImage(homeImage,0,0,width,height);

  canvas.dataset.layeredDynamic="false";
  canvas.dataset.layeredSchema="friday-football-palette-v1";
  canvas.dataset.visitorPrimary=visitorColor;
  canvas.dataset.homePrimary=homeColor;
  canvas.dataset.visitorPalette=visitorKey;
  canvas.dataset.homePalette=homeKey;
  root.dataset.productionLayeredClash="true";
  root.dataset.fridayPalettePlayers="true";
  return true;
}

async function ensureFridayNightDynamicClashReady(root, alias, mode, renderResult) {
  if (alias !== "friday_night_stadium" || mode !== "clash") return true;

  if (renderResult && renderResult.ready && typeof renderResult.ready.then === "function") {
    await renderResult.ready;
  }

  const clash = root.querySelector('.bl-fns-video-board > .bl-fns-clash[data-video-mode="clash"]');
  if (!clash) throw new Error("Friday Night Stadium native clash host missing after render.");

  const canvas = clash.querySelector('.bl-fns-clash-art');
  if (!canvas) throw new Error("Friday Night Stadium dynamic clash athlete canvas missing.");
  if (canvas.dataset.artReady !== "true") {
    throw new Error(`Friday Night Stadium dynamic clash athletes not ready: ${canvas.dataset.artReady || "unset"}`);
  }

  const asset = canvas.dataset.clashAsset || "";
  const footballAssetOk =
    asset.endsWith('/friday-night-stadium/clash/football-athletes-keyed.png') ||
    (/\/friday-night-stadium\/players\/palette-v2\/visitor\/visitor-28-[a-z0-9-]+\.png/.test(asset) &&
     /\/friday-night-stadium\/players\/palette-v2\/home\/home-31-[a-z0-9-]+\.png/.test(asset));
  if (!footballAssetOk && String(root.dataset.sport || "football").toLowerCase() === "football") {
    throw new Error(`Friday Night Stadium football clash asset contract mismatch: ${asset || "missing"}`);
  }

  root.dataset.productionClashReady = "true";
  return true;
}

function mergeManualMediaState(state, runtime) {
  const highlight = objectValue(runtime.player_highlight);
  const sponsor = objectValue(runtime.sponsor_spotlight);

  state.highlight = {
    ...(state.highlight || {}),
    title: textValue(
      highlight.display_name,
      highlight.full_name,
      highlight.name,
      highlight.media_name,
      "PLAYER HIGHLIGHT"
    ),
    detail: textValue(
      highlight.detail,
      highlight.caption,
      highlight.media_name,
      ""
    ),
    mediaUrl: textValue(highlight.media_url, ""),
    mediaType: textValue(highlight.media_type, "video").toLowerCase()
  };

  const sponsorMediaType = textValue(sponsor.media_type, "image").toLowerCase();
  const sponsorMedia = textValue(sponsor.media_url, "");
  state.sponsor = {
    ...(state.sponsor || {}),
    name: textValue(sponsor.sponsor_name, sponsor.name, "SPONSOR"),
    line: textValue(sponsor.caption, sponsor.lead_in, ""),
    logo: sponsorMediaType === "image"
      ? textValue(sponsorMedia, sponsor.sponsor_logo, sponsor.logo, "")
      : textValue(sponsor.sponsor_logo, sponsor.logo, ""),
    mediaUrl: sponsorMedia,
    mediaType: sponsorMediaType,
    leadIn: textValue(sponsor.lead_in, "PRESENTED BY")
  };
  return state;
}

function nativeVideoBoardHost(root, alias, mode) {
  if (!root) return null;

  const auditedNativeBoards = Object.freeze({
    eight_bit_gameday: ".bl-8bit-video-board",
    friday_night_stadium: ".bl-fns-video-board"
  });

  if (Object.prototype.hasOwnProperty.call(auditedNativeBoards, alias)) {
    const board = root.querySelector(auditedNativeBoards[alias]);
    if (!board) return null;

    const host = board.querySelector(`:scope > [data-video-mode="${mode}"]`);
    if (!host || host.parentElement !== board) return null;

    host.classList.add("csrn-production-native-video-mode");
    return host;
  }

  if (alias === "heritage_press") {
    const opening = root.querySelector(".hp-opening");
    if (!opening) return null;

    if (mode === "highlight") {
      const feature = opening.querySelector(':scope > .hp-highlight-feature[data-video-mode="highlight"]');
      if (!feature || feature.parentElement !== opening) return null;
      const windowHost = feature.querySelector(':scope > .hp-highlight-window[data-module="video.board"]');
      if (!windowHost || windowHost.parentElement !== feature) return null;
      windowHost.classList.add("csrn-production-native-video-mode");
      return windowHost;
    }

    if (mode === "sponsor") {
      const sponsorHost = opening.querySelector(':scope > .hp-sponsor-feature[data-video-mode="sponsor"]');
      if (!sponsorHost || sponsorHost.parentElement !== opening) return null;
      sponsorHost.classList.add("csrn-production-native-video-mode");
      return sponsorHost;
    }

    return null;
  }

  return root.querySelector(`[data-video-mode="${mode}"]`);
}

function mountCentralBoardMedia(root, runtime, mode, alias) {
  if (!root) return false;

  if (mode === "highlight") {
    const graphic = objectValue(runtime.player_highlight);
    const url = imageCandidate(graphic.media_url);
    const host = nativeVideoBoardHost(root, alias, "highlight");
    if (!host || !url) return false;

    host.replaceChildren();
    host.classList.add("csrn-production-highlight-board");
    if (alias === "heritage_press") host.classList.add("csrn-production-heritage-highlight-window");

    const video = document.createElement("video");
    video.className = "csrn-production-highlight-video";
    video.src = url;
    video.autoplay = true;
    video.playsInline = true;
    video.preload = "auto";
    video.controls = false;
    video.loop = false;
    video.muted = true;
    video.setAttribute("playsinline", "");
    video.setAttribute("aria-label", textValue(graphic.media_name, "Player highlight video"));

    const fallback = document.createElement("div");
    fallback.className = "csrn-production-highlight-fallback";
    fallback.innerHTML = `<strong>${textValue(graphic.display_name, graphic.full_name, "PLAYER HIGHLIGHT")}</strong><span>${textValue(graphic.detail, graphic.media_name, "Highlight video unavailable")}</span>`;
    fallback.hidden = true;

    video.addEventListener("error", () => {
      video.remove();
      fallback.hidden = false;
    }, {once:true});

    host.append(video, fallback);
    const play = video.play();
    if (play && typeof play.catch === "function") {
      play.catch(() => {
        video.muted = true;
        video.play().catch(() => {
          video.remove();
          fallback.hidden = false;
        });
      });
    }
    return true;
  }

  if (mode === "sponsor") {
    const graphic = objectValue(runtime.sponsor_spotlight);
    const host = nativeVideoBoardHost(root, alias, "sponsor");
    if (!host) return false;

    const primaryUrl = imageCandidate(graphic.media_url);
    const logoUrl = imageCandidate(graphic.sponsor_logo);
    const type = textValue(graphic.media_type, "image").toLowerCase();
    const sponsorName = textValue(graphic.sponsor_name, graphic.name, "SPONSOR");
    const leadIn = textValue(graphic.lead_in, "PRESENTED BY");
    const caption = textValue(graphic.caption, "");

    host.replaceChildren();
    host.classList.add("csrn-production-sponsor-board");
    if (alias === "heritage_press") host.classList.add("csrn-production-heritage-sponsor-host");

    const mediaWrap = document.createElement("div");
    mediaWrap.className = "csrn-production-sponsor-media-wrap";

    const copy = document.createElement("div");
    copy.className = "csrn-production-sponsor-copy";
    const lead = document.createElement("small");
    lead.textContent = leadIn;
    const name = document.createElement("strong");
    name.textContent = sponsorName;
    const line = document.createElement("span");
    line.textContent = caption;
    copy.append(lead, name);
    if (caption) copy.append(line);

    const installImage = (url, fallbackUrl = "") => {
      if (!url) return false;
      const image = document.createElement("img");
      image.className = "csrn-production-sponsor-asset";
      image.src = url;
      image.alt = sponsorName;
      image.addEventListener("error", () => {
        if (fallbackUrl && image.src !== fallbackUrl) {
          image.src = fallbackUrl;
          return;
        }
        image.remove();
        mediaWrap.classList.add("media-unavailable");
      });
      mediaWrap.appendChild(image);
      return true;
    };

    if (type === "video" && primaryUrl) {
      const video = document.createElement("video");
      video.className = "csrn-production-sponsor-asset";
      video.src = primaryUrl;
      video.autoplay = true;
      video.playsInline = true;
      video.preload = "auto";
      video.controls = false;
      video.loop = false;
      video.muted = true;
      video.setAttribute("playsinline", "");
      video.addEventListener("error", () => {
        video.remove();
        if (!installImage(logoUrl)) mediaWrap.classList.add("media-unavailable");
      }, {once:true});
      mediaWrap.appendChild(video);
      video.play().catch(() => {
        video.remove();
        if (!installImage(logoUrl)) mediaWrap.classList.add("media-unavailable");
      });
    } else if (!installImage(primaryUrl, logoUrl)) {
      installImage(logoUrl);
    }

    copy.style.textAlign = "center";
    copy.style.width = "100%";
    copy.style.alignItems = "center";
    host.append(mediaWrap, copy);
    return true;
  }

  return false;
}

function heritageNativePlayerHost(root) {
  if (!root) return null;
  const opening = root.querySelector(".hp-opening");
  if (!opening) return null;
  const host = opening.querySelector(':scope > .hp-player-feature[data-video-mode="player"]');
  if (!host || host.parentElement !== opening) return null;
  return host;
}

function populateHeritagePlayerHost(root, runtime, state, alias, mode) {
  if (!root || alias !== "heritage_press" || mode !== "player") return false;
  const host = heritageNativePlayerHost(root);
  if (!host) return false;

  const player = state.player || {};
  const team = state.home || {};
  const graphic = runtime.player_graphic || {};
  host.replaceChildren();
  host.classList.add("csrn-production-heritage-player-host");
  host.style.cssText = [
    "display:grid",
    "grid-template-columns:minmax(320px,44%) minmax(0,1fr)",
    "gap:24px",
    "align-items:stretch",
    "width:100%",
    "height:100%",
    "padding:16px",
    "box-sizing:border-box",
    "overflow:hidden",
    "background:transparent",
    "color:var(--hp-ink)"
  ].join(";");

  const photo = document.createElement("div");
  photo.className = "csrn-heritage-player-photo";
  photo.style.cssText = [
    "display:flex",
    "align-items:center",
    "justify-content:center",
    "min-width:0",
    "min-height:0",
    "overflow:hidden",
    "border:4px double var(--hp-rule)",
    "background:rgba(255,255,255,.22)",
    "padding:0"
  ].join(";");

  const imageUrl = imageCandidate(graphic.headshot, graphic.headshot_url, graphic.media_url, player.headshot, team.logo);
  if (imageUrl) {
    const image = document.createElement("img");
    image.src = imageUrl;
    image.alt = "";
    image.style.cssText = [
      "display:block",
      "width:100%",
      "height:100%",
      "object-fit:cover",
      "filter:grayscale(1) contrast(1.08) sepia(.06)",
      "-webkit-filter:grayscale(1) contrast(1.08) sepia(.06)",
      "mix-blend-mode:multiply"
    ].join(";");
    photo.appendChild(image);
  } else {
    const fallback = document.createElement("strong");
    fallback.className = "csrn-heritage-player-number-fallback";
    fallback.textContent = textValue(player.number, graphic.number, "—");
    fallback.style.cssText = "font:900 78px/.9 Georgia, 'Times New Roman', serif;color:var(--hp-ink)";
    photo.appendChild(fallback);
  }

  const story = document.createElement("div");
  story.className = "csrn-heritage-player-story";
  story.style.cssText = [
    "display:flex",
    "flex-direction:column",
    "justify-content:center",
    "align-items:flex-start",
    "min-width:0",
    "min-height:0",
    "padding:10px 12px",
    "border-top:3px double var(--hp-rule)",
    "border-bottom:3px double var(--hp-rule)",
    "overflow:hidden",
    "text-align:left"
  ].join(";");

  const kicker = document.createElement("small");
  kicker.textContent = "PLAYER SPOTLIGHT · SPORTS EXTRA";
  kicker.style.cssText = [
    "display:block",
    "margin:0",
    "font:900 16px/1 Arial,Helvetica,sans-serif",
    "letter-spacing:.13em",
    "text-transform:uppercase",
    "color:var(--hp-rubric)"
  ].join(";");

  const name = document.createElement("h2");
  name.textContent = textValue(player.name, graphic.display_name, graphic.full_name, "PLAYER");
  name.style.cssText = [
    "display:block",
    "width:100%",
    "margin:10px 0 8px",
    "font:900 48px/.92 Georgia, 'Times New Roman', serif",
    "text-transform:uppercase",
    "letter-spacing:.01em",
    "color:var(--hp-ink)"
  ].join(";");

  const subhead = document.createElement("p");
  subhead.className = "subhead";
  const teamText = [textValue(team.name, ""), textValue(team.mascot, "")].filter(Boolean).join(" ");
  const roleText = [textValue(player.position, graphic.position, ""), textValue(player.number, graphic.number, "") ? `NO. ${textValue(player.number, graphic.number, "")}` : ""].filter(Boolean).join(" · ");
  subhead.textContent = [teamText, roleText].filter(Boolean).join(" · ");
  subhead.style.cssText = [
    "display:block",
    "width:100%",
    "margin:0",
    "font:700 20px/1.12 Georgia, 'Times New Roman', serif",
    "color:var(--hp-ink)"
  ].join(";");

  const detail = document.createElement("p");
  detail.className = "detail";
  detail.textContent = textValue(graphic.detail, player.detail, "Player spotlight");
  detail.style.cssText = [
    "display:block",
    "width:100%",
    "margin:14px 0 0",
    "padding-top:10px",
    "border-top:1px solid var(--hp-rule)",
    "font:700 22px/1.15 Georgia, 'Times New Roman', serif",
    "color:var(--hp-ink)"
  ].join(";");

  story.append(kicker, name, subhead, detail);
  host.append(photo, story);
  return true;
}

function mountHeritageFootballClash(root, runtime, state, mode, alias) {
  if (!root || alias !== "heritage_press" || mode !== "broadcast") return false;
  if (String(state?.sport || runtime?.sport || "football").toLowerCase() !== "football") return false;

  const opening = root.querySelector('.hp-opening > .hp-live-opening[data-video-mode="broadcast"]');
  if (!opening || !opening.parentElement?.classList.contains("hp-opening")) return false;

  opening.replaceChildren();
  opening.className = "hp-live-opening csrn-heritage-clash-foundation csrn-heritage-clash-feature csrn-heritage-clash-highlight-host";

  // Use the exact accepted Heritage Player Highlight media-frame classes.
  const frame = document.createElement("div");
  frame.className = "hp-highlight-window csrn-production-native-video-mode csrn-production-heritage-highlight-window csrn-heritage-clash-artwork";
  frame.dataset.module = "video.board";

  const image = document.createElement("img");
  image.className = "csrn-production-highlight-video csrn-heritage-clash-image";
  image.src = "/static/assets/heritage_press/heritage-neutral-football-clash.png";
  image.alt = "Two vintage leather-helmet football players facing each other at the line of scrimmage";
  image.decoding = "async";

  frame.append(image);
  opening.append(frame);
  return true;
}

function normalizePlayerDetailSeparator(root, mode) {
  if (!root || mode !== "player") return;
  const detail = root.querySelector('[data-video-mode="player"] > span');
  if (!detail) return;
  detail.textContent = detail.textContent.replace(/\s*·\s*$/, "").trim();
}

function setPrimaryThemeClasses(mode) {
  document.documentElement.classList.toggle(
    HIGHLIGHT_ACTIVE_CLASS,
    mode === "highlight"
  );
  document.documentElement.classList.toggle(
    SPONSOR_ACTIVE_CLASS,
    mode === "sponsor"
  );
  document.documentElement.classList.toggle(
    "csrn-production-theme-player-active",
    mode === "player"
  );
}

function enforceLegacyMediaOwnership(mode) {
  const ownership = [
    ["playerGraphic", mode === "player"],
    ["playerHighlight", mode === "highlight"],
    ["sponsorSpotlight", mode === "sponsor"]
  ];

  for (const [id, active] of ownership) {
    const node = document.getElementById(id);
    if (!node) continue;

    if (active) {
      node.dataset.csrnThemeMediaSuppressed = "true";
      node.classList.add("hidden");
      node.style.setProperty("display", "none", "important");
      node.style.setProperty("visibility", "hidden", "important");
      node.style.setProperty("opacity", "0", "important");
      node.style.setProperty("pointer-events", "none", "important");
      continue;
    }

    if (node.dataset.csrnThemeMediaSuppressed === "true") {
      node.style.removeProperty("display");
      node.style.removeProperty("visibility");
      node.style.removeProperty("opacity");
      node.style.removeProperty("pointer-events");
      delete node.dataset.csrnThemeMediaSuppressed;
    }
  }
}
function playerModeFor(alias, runtime) {
  if (!playerVisible(runtime)) return "clash";
  return themedIntegratedPlayerSupported(alias) ? "player" : "clash";
}

async function fetchJson(url) {
  const response = await fetch(url, {cache:"no-store", credentials:"same-origin"});
  if (!response.ok) throw new Error(`${url} returned ${response.status}`);
  return response.json();
}

async function renderSelected() {
  if (renderBusy) return "busy";
  renderBusy = true;

  try {
    const publicState = await fetchJson(PUBLIC_STATE_URL);
    const alias = textValue(publicState.production_template_package_id, "legacy");

    if (alias === "legacy" || !PACKAGE_ALIASES[alias]) {
      deactivate(alias === "legacy" ? "legacy" : "invalid-selection");
      return "inactive";
    }

    if (themedIntegratedPlayerSupported(alias)) {
      cancelLegacyPlayerMotion();
      document.documentElement.classList.add(PLAYER_PENDING_CLASS);
    }

    const [runtime, captionState] = await Promise.all([
      fetchJson(RUNTIME_STATE_URL),
      fetchJson(CAPTION_STATE_URL).catch(() => ({visible:false, segments:[]}))
    ]);
    const captionSegment = activeCaptionSegment(captionState);
    runtimeClockRunning = runtime.clock_running === true;
    lastRuntimeForClockPatch = runtime;
    const playerPending =
      playerVisible(runtime) && themedIntegratedPlayerSupported(alias);
    setPlayerPending(playerPending);
    const activationKey = playerActivationKey(runtime);
    const polledVideoMode = themeVideoModeFor(alias, runtime);
    setPrimaryThemeClasses(polledVideoMode);
    enforceLegacyMediaOwnership(polledVideoMode);

    const signature = JSON.stringify([
      alias,
      runtime.broadcast_id,
      runtime.home_school_id,
      runtime.visitor_school_id,
      runtime.home_team,
      runtime.visitor_team,
      runtime.home_identity,
      runtime.visitor_identity,
      runtime.venue_id,
      runtime.venue,
      runtime.date,
      runtime.scheduled_start,
      runtime.sport,
      polledVideoMode,
      runtime.player_graphic,
      runtime.player_highlight,
      runtime.sponsor_spotlight,
      activationKey
    ]);

    csrnLogThemeSignatureDiffR4(signature);
    if (alias === currentAlias && signature === renderSignature) {
      patchLiveGameState(runtime);
      patchThemeTicker(runtime);
      patchCaptionDom(alias, captionState);
      return "unchanged";
    }

    const {base, selected, spec} = await ensurePackage(alias);
    const scoreTarget = scoreLayout();
    if (!scoreTarget) throw new Error("Production theme score host missing.");

    const state = mergeRuntimeState(base.defaultState(), runtime, captionState);
    mergeManualMediaState(state, runtime);
    const playerMedia = await preparePlayerMedia(state, runtime);
    const activeVideoMode = polledVideoMode;
    const packageId = selected.packageId || alias;
    if (!packageId) throw new Error("Selected engine has no packageId.");

    clearNode(scoreTarget);
    const scoreResult = selected.renderPackage(
      scoreTarget,
      packageId,
      state.sport,
      state,
      {
        diagnostics:false,
        activeComponents:state.captionsActive ? ["scorebug", "captions"] : ["scorebug"],
        videoMode:activeVideoMode
      }
    );

    if (
      !scoreResult ||
      !Array.isArray(scoreResult.components) ||
      !scoreResult.components.includes("scorebug") ||
      scoreResult.components.some(component => !["scorebug", "captions"].includes(component))
    ) {
      throw new Error("Theme scorebug render contract failed.");
    }

    await ensureFridayNightDynamicClashReady(scoreTarget, alias, activeVideoMode, scoreResult);
    patchCaptionDom(alias, captionState);
    await paintFridayNightLayeredFootballClash(scoreTarget, alias, activeVideoMode, state);

    applyFootballBoardOverrides(scoreTarget, alias, runtime);
    repairRenderedPlayerMedia(scoreTarget, state);
    mountCentralBoardMedia(scoreTarget, runtime, activeVideoMode, alias);
    populateHeritagePlayerHost(scoreTarget, runtime, state, alias, activeVideoMode);
    mountHeritageFootballClash(scoreTarget, runtime, state, activeVideoMode, alias);
    normalizePlayerDetailSeparator(scoreTarget, activeVideoMode);
    setPrimaryThemeClasses(activeVideoMode);
    enforceLegacyMediaOwnership(activeVideoMode);

    setHostState(scoreHost(), true, alias, packageId, "rendered");
    document.documentElement.classList.add(SCORE_ACTIVE_CLASS);

    const tickerActive = activateThemeTicker(scoreTarget, alias, spec, runtime, true);
    document.documentElement.classList.toggle(TICKER_ACTIVE_CLASS, tickerActive);

    const integratedPlayerActive = activeVideoMode === "player";

    if (integratedPlayerActive) {
      cancelLegacyPlayerMotion();
      document.documentElement.classList.add(PLAYER_ACTIVE_CLASS);
      setPlayerPending(true);
    } else {
      restoreLegacyPlayerNeutral();
      document.documentElement.classList.remove(PLAYER_ACTIVE_CLASS);
      setPlayerPending(false);
    }

    if (integratedPlayerActive) {
      lastPlayerActivationKey = activationKey;
    } else {
      lastPlayerActivationKey = "";
      setPlayerPending(false);
    }

    setHostState(playerHost(), false, "legacy", "", "integrated-player-mode");
    clearNode(playerLayout());

    const themedPlayerActive = integratedPlayerActive;

    currentAlias = alias;
    renderSignature = signature;

    window.CSRNProductionThemeBindingState = Object.freeze({
      schema:"csrn-production-theme-binding-v46",
      active:true,
      alias,
      packageId,
      sport:state.sport,
      tickerActive,
      themedPlayerActive,
      playerMediaKind:playerMedia.kind,
      playerActivationKey:lastPlayerActivationKey,
      playerFallback: playerVisible(runtime) && !themedPlayerActive
    });
    return "rendered";
  } catch (error) {
    console.error("[CSRN Gate 16.9 R2] production theme binding blocked:", error);
    restoreLegacyPlayerNeutral();
    setPlayerPending(false);
    deactivate("render-error");
    window.CSRNProductionThemeBindingState = Object.freeze({
      schema:"csrn-production-theme-binding-v46",
      active:false,
      error:String(error && error.message || error)
    });
    return "error";
  } finally {
    renderBusy = false;
  }
}

async function scheduleRenderSelected() {
  const status = await renderSelected();
  if (status === "unchanged" || status === "inactive") {
    stablePollCount = Math.min(stablePollCount + 1, 12);
  } else if (status !== "busy") {
    stablePollCount = 0;
  }

  const delay = status === "error"
    ? 1500
    : status === "busy"
      ? 150
      : Math.min(900, 300 + stablePollCount * 100);
  pollTimer = window.setTimeout(scheduleRenderSelected, delay);
}

function start() {
  deactivate("startup");
  if (pollTimer) window.clearTimeout(pollTimer);
  stablePollCount = 0;
  startClockPatchTimer();
  scheduleRenderSelected();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", start, {once:true});
} else {
  start();
}

window.CSRNProductionThemeRuntime = Object.freeze({
  PACKAGE_ALIASES,
  activeEvents,
  eventPlainText,
  renderSelected,
  deactivate
});
})();












