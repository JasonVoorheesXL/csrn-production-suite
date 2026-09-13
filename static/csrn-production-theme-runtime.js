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
const STATISTICS_URL = "/api/statistics/overlay-state";
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

// --- Sponsor video warm cache ------------------------------------------------
// The 5-15s gap between the operator clicking Run and a sponsor commercial
// appearing is a cold fetch+decode: mountCentralBoardMedia() built a brand
// new <video src> every trigger. Sponsor videos are configured in advance,
// so keep a hidden preloaded <video> per URL and hand that warm element to
// the board on trigger. media_url persists in runtime state after a hide, so
// warmSponsorVideo() (called every poll) has the next commercial buffered
// well before Run is clicked again. First-ever trigger of a URL is still
// cold -- eliminating that needs an arm-on-select signal (see summary).
const sponsorVideoWarmCache = new Map(); // url -> detached HTMLVideoElement
const SPONSOR_WARM_CACHE_MAX = 6;

function warmSponsorVideo(url) {
  if (typeof url !== "string" || !url) return null;
  const existing = sponsorVideoWarmCache.get(url);
  if (existing) return existing;
  const el = document.createElement("video");
  el.preload = "auto";
  el.muted = true;
  el.loop = false;
  el.playsInline = true;
  el.setAttribute("playsinline", "");
  el.src = url;
  try { el.load(); } catch (_) {}
  sponsorVideoWarmCache.set(url, el);
  while (sponsorVideoWarmCache.size > SPONSOR_WARM_CACHE_MAX) {
    const oldestUrl = sponsorVideoWarmCache.keys().next().value;
    const oldest = sponsorVideoWarmCache.get(oldestUrl);
    sponsorVideoWarmCache.delete(oldestUrl);
    try { oldest.removeAttribute("src"); oldest.load(); } catch (_) {}
  }
  return el;
}

function takeWarmSponsorVideo(url) {
  const el = warmSponsorVideo(url);
  sponsorVideoWarmCache.delete(url); // the board fully owns it now
  return el;
}

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
    css: ["/static/csrn-broadcast-layout-engine.css?v=17.1-passer-credit"],
    js:  ["/static/csrn-broadcast-layout-engine.js?v=17.1-passer-credit"]
  })
});

const loadedCss = new Set();
const loadedJs = new Map();
let currentAlias = "legacy";
let renderSignature = "";
let tickerRenderSignature = "";
let tickerBroadcastId = "";
const tickerKnownTransientKeys = new Set();
const collegiateStatisticsCache = {broadcastId:"", fetchedAt:0, data:null, promise:null};
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
  "player_activation_key",
  // Video-mode support (CSRN_VIDEO_MODE_BUILD_PROMPT.md). NOTE: the
  // "video_mode" label above (index 13) is the pre-existing, unrelated
  // per-component highlight/sponsor/player/clash dispatch value
  // (polledVideoMode in the real signature array below) -- a coincidental
  // name reuse discovered while wiring this feature, not a mislabel this
  // change introduced. These three are the actual new state fields.
  "raw_video_mode",
  "sidebars_hidden",
  "video_calibration_guide"
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
  // 2026-09: slowed ~10% from {24, 36, 84, 189} per broadcaster feedback
  // (mirrors templates/overlay.html's legacy ticker so both stay in sync).
  return ({very_slow:22, slow:32, normal:76, fast:170})[runtime.ticker_speed] || 32;
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
    team_color: textValue(graphic.team_color, player.team_color),
    eyebrow: textValue(graphic.eyebrow, player.eyebrow, "PLAYER SPOTLIGHT"),
    // Pass-reception touchdowns only -- text credit alongside the
    // receiver's card, never the passer's own photo/card.
    passerName: textValue(graphic.passer_name, player.passerName),
    passer_name: textValue(graphic.passer_name, player.passer_name),
    sponsorId: textValue(graphic.sponsor_id, player.sponsorId),
    sponsor_id: textValue(graphic.sponsor_id, player.sponsor_id),
    sponsorName: textValue(graphic.sponsor_name, player.sponsorName),
    sponsor_name: textValue(graphic.sponsor_name, player.sponsor_name),
    sponsorLogo: textValue(graphic.sponsor_logo, player.sponsorLogo),
    sponsor_logo: textValue(graphic.sponsor_logo, player.sponsor_logo),
    sponsorLeadIn: textValue(graphic.sponsor_lead_in, player.sponsorLeadIn, "Presented by"),
    sponsor_lead_in: textValue(graphic.sponsor_lead_in, player.sponsor_lead_in, "Presented by")
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

  // Phase C: dispatch the game-state block by sport family. The football
  // branch is verbatim from before; non-football families get their own
  // fields and the football-only keys are stripped so no stale down /
  // field / ball-spot data can leak onto a baseball or basketball board.
  const sportFamily = productionSportFamily(base.sport);
  base.game.sportFamily = sportFamily;
  const FOOTBALL_GAME_KEYS = [
    "down", "distance", "toGo", "to_go", "downDistance", "down_distance",
    "field", "ballSpot", "ball_spot", "driveStart", "drive_start",
    "firstDownSpot", "first_down_spot", "fieldDirection", "field_direction"
  ];

  if (sportFamily === "football") {
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
  } else {
    FOOTBALL_GAME_KEYS.forEach(key => { delete base.game[key]; });
    if (sportFamily === "basketball") {
      base.game.possession = textValue(source.possession, gameSource.possession, base.game.possession).toLowerCase();
      Object.assign(base.game, productionBasketballState(source, gameSource));
    } else {
      // baseball / softball -- no possession concept
      delete base.game.possession;
      Object.assign(base.game, productionDiamondState(source, gameSource));
    }
  }

  base.ticker = {...(base.ticker || {})};
  base.ticker.text = eventPlainText(source) || "CSRN LIVE";
  base.captionsActive = mergeCaptionState(base, captionState);

  // Video-mode support (CSRN_VIDEO_MODE_BUILD_PROMPT.md). Named
  // "videoWindowActive"/etc, NOT "videoMode", to stay clearly distinct from
  // this file's own videoMode (the highlight/sponsor/player/clash per-
  // component dispatch parameter threaded through renderPackage/
  // componentFrame/collegiateStage below) -- same word, unrelated concept.
  base.videoWindowActive = Boolean(source.video_mode);
  base.sidebarsHidden = Boolean(source.sidebars_hidden);
  base.videoCalibrationGuide = Boolean(source.video_calibration_guide);

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
      // Nothing persistent left to loop -- clear the theme ticker visually,
      // but keep TICKER_ACTIVE_CLASS so the legacy #eventTicker stays
      // suppressed. The active package still owns this slot.
      viewport.remove();
      if (kind === "replace-sibling") target.style.display = "";
      return;
    }

    const safe = escapeHtml(text);

    track.innerHTML =
      `<span class="csrn-theme-ticker-copy">${safe}</span>` +
      `<span class="csrn-theme-ticker-copy" aria-hidden="true">${safe}</span>`;

    requestAnimationFrame(() => {
      const distance = Math.max(1, track.scrollWidth / 2);
      // Crawl speed must stay constant (== tickerSpeed(runtime)) regardless
      // of how much ticker content has piled up -- flooring the SCROLL
      // duration itself (the old `Math.max(18, ...)` here) silently sped the
      // crawl up as content grew instead of just taking longer per pass.
      // Keep a minimum on-screen cycle time by extending the pause dwell at
      // each end instead (mirrors templates/overlay.html's legacy ticker).
      const moveSeconds = distance / tickerSpeed(runtime);
      const pauseSeconds = tickerPause(runtime);
      const minCycleSeconds = 18;
      const totalSeconds = Math.max(minCycleSeconds, moveSeconds + (pauseSeconds * 2));
      const pauseOffset = totalSeconds ? ((totalSeconds - moveSeconds) / 2) / totalSeconds : 0;

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
      // See the matching comment in animatePersistent(): keep the crawl at
      // a constant tickerSpeed(runtime) regardless of story length, and
      // enforce the minimum on-screen cycle via extra pause dwell instead.
      const moveSeconds = distance / tickerSpeed(runtime);
      const pauseSeconds = tickerPause(runtime);
      const minCycleSeconds = 18;
      const totalSeconds = Math.max(minCycleSeconds, moveSeconds + (pauseSeconds * 2));
      const pauseOffset = totalSeconds ? ((totalSeconds - moveSeconds) / 2) / totalSeconds : 0;

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
            // Transient stories finished scrolling and nothing persistent
            // follows: clear the visual, but keep TICKER_ACTIVE_CLASS so the
            // legacy #eventTicker stays suppressed while this package is active.
            viewport.remove();
            if (kind === "replace-sibling") target.style.display = "";
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
  // A production theme OWNS the ticker slot for as long as it is the active
  // package, even on a quiet play when activateThemeTicker() has nothing new
  // to scroll and returns false. Toggling the class off here was letting the
  // legacy #eventTicker flash back in at the bottom of the screen on
  // individual plays. Only deactivate() (theme -> legacy fallback) releases it.
  document.documentElement.classList.add(TICKER_ACTIVE_CLASS);
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

// Phase C: collapse a raw sport value to its family. canadian_football rides
// the football board/graphics; everything unrecognised falls back to
// "football" so today's football-only pipeline is byte-identical.
function productionSportFamily(sport) {
  const raw = String(sport || "").trim().toLowerCase().replace(/[\s-]+/g, "_");
  if (raw === "canadian_football" || raw === "cfl") return "football";
  if (raw === "basketball" || raw === "baseball" || raw === "softball") return raw;
  return "football";
}

function productionBasketballState(source, gameSource) {
  const pick = (...k) => textValue(...k.flatMap(name => [source[name], gameSource[name]]));
  return {
    shotClock: pick("shot_clock", "shotClock"),
    homeFouls: pick("home_fouls", "homeFouls"),
    visitorFouls: pick("visitor_fouls", "visitorFouls"),
    homeBonus: pick("home_bonus", "homeBonus"),
    visitorBonus: pick("visitor_bonus", "visitorBonus"),
    homeTimeouts: pick("home_timeouts", "homeTimeouts"),
    visitorTimeouts: pick("visitor_timeouts", "visitorTimeouts")
  };
}

function productionDiamondState(source, gameSource) {
  const pick = (...k) => textValue(...k.flatMap(name => [source[name], gameSource[name]]));
  const rawBases = source.bases ?? gameSource.bases;
  const bases = Array.isArray(rawBases)
    ? [Boolean(rawBases[0]), Boolean(rawBases[1]), Boolean(rawBases[2])]
    : [false, false, false];
  const half = pick("inning_half", "inningHalf").toUpperCase();
  return {
    inning: pick("inning"),
    inningHalf: half.startsWith("B") ? "BOTTOM" : half.startsWith("T") ? "TOP" : half,
    balls: pick("balls"),
    strikes: pick("strikes"),
    outs: pick("outs"),
    bases,
    pitcherName: pick("pitcher_name", "pitcherName"),
    batterName: pick("batter_name", "batterName"),
    batterPosition: pick("batter_position", "batterPosition"),
    homeHits: pick("home_hits", "homeHits"),
    visitorHits: pick("visitor_hits", "visitorHits"),
    homeErrors: pick("home_errors", "homeErrors"),
    visitorErrors: pick("visitor_errors", "visitorErrors"),
    lineScore: objectValue(source.line_score, source.lineScore, gameSource.line_score, gameSource.lineScore)
  };
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

// lengthYards is the goal-line-to-goal-line distance of the active ruleset
// (100 US / 110 Canadian). pct is always 0..100 (% of field width), so the
// field graphic stays a fixed box; only the yards<->pct conversion scales.
function parseFieldSpot(value, lengthYards = 100) {
  const raw = textValue(value).trim().toUpperCase();
  if (!raw || raw === "-") return null;
  const length = Number(lengthYards) > 0 ? Number(lengthYards) : 100;
  const mid = length / 2;
  const side = raw.includes("RIGHT") ? "right" : raw.includes("LEFT") ? "left" : "";
  if (/GOAL|GL/.test(raw)) {
    if (side === "right") return {raw, side, yard:0, pct:100};
    if (side === "left") return {raw, side, yard:0, pct:0};
  }
  const number = Number(raw.match(/\d+/)?.[0]);
  if (!Number.isFinite(number)) return null;
  const yard = Math.max(0, Math.min(mid, number));
  let pct = 50;
  if (side === "left") pct = (yard / length) * 100;
  else if (side === "right") pct = 100 - (yard / length) * 100;
  else pct = yard === mid ? 50 : (yard / length) * 100;
  return {raw, side, yard, pct:Math.max(0, Math.min(100, pct))};
}

function spotFromPercent(pct, lengthYards = 100) {
  const bounded = Math.max(0, Math.min(100, Number(pct)));
  if (!Number.isFinite(bounded)) return "";
  if (bounded <= 0) return "LEFT GOAL";
  if (bounded >= 100) return "RIGHT GOAL";
  const length = Number(lengthYards) > 0 ? Number(lengthYards) : 100;
  if (bounded <= 50) return `LEFT ${Math.round((bounded / 100) * length)}`;
  return `RIGHT ${Math.round(length - (bounded / 100) * length)}`;
}

// Sets the field-graphic's geometry CSS vars from the active ruleset. The
// end-zone-depth ratio is anchored so the historical US look (10-yd end
// zone on a 100-yd field) is exactly --csrn-ez:5%; a 20-yd Canadian end
// zone on a 110-yd field scales to ~9.1%. Yard-number count is 9 (US) or
// 11 (Canadian, which shows the centre "C").
function applyFieldGeometry(root, lengthYards, endZoneDepthYards) {
  if (!root || !root.style) return;
  const length = Number(lengthYards) > 0 ? Number(lengthYards) : 100;
  const ez = Number(endZoneDepthYards) > 0 ? Number(endZoneDepthYards) : 10;
  root.style.setProperty("--csrn-ez", `${(ez / length) * 50}%`);
  root.style.setProperty("--csrn-yardnum-count", length >= 110 ? "11" : "9");
  // 5-yard-line count and per-yard hashmark count. Every playing-field
  // marking (5-yd lines, 10-yd lines, hashmarks, numbers) is spaced from
  // these so they line up. length 100 -> 20 / 100 (today's values).
  root.style.setProperty("--csrn-yl-count", String(Math.max(2, Math.round(length / 5))));
  root.style.setProperty("--csrn-hash-count", String(Math.max(2, Math.round(length))));
}

// The collegiate field graphic only draws the actual playing surface across
// a 5%-95% window of its container (5% reserved for each end zone graphic --
// see .bl-college-endzone/.bl-college-yard-numbers/.bl-college-five-yard-lines
// in csrn-broadcast-layout-engine.css). ballPct/driveStartPct/firstDownPct
// are computed on a raw 0-100 "goal line to goal line" scale, so applying
// them directly as a CSS percent placed any spot within ~5 yards of a goal
// line visually past the true goal line (into the end zone graphic). Rescale
// only at this final render boundary -- gainPct/parseFieldSpot must stay on
// the self-consistent raw 0-100 domain internally so the first-down spot
// label round-trips correctly.
function renderPctFromRaw(pct) {
  const bounded = Math.max(0, Math.min(100, Number(pct)));
  if (!Number.isFinite(bounded)) return 50;
  return 5 + (bounded / 100) * 90;
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
  // Field geometry from the active ruleset (canonical_state_service.
  // field_state). Absent (US game / older state) -> 100 / 10, i.e. today.
  const lengthYards = Number(
    fieldSource.length_yards ?? fieldSource.lengthYards ?? source.field_length_yards
  ) || 100;
  const endZoneDepthYards = Number(
    fieldSource.end_zone_depth_yards ?? fieldSource.endZoneDepthYards
  ) || 10;
  const direction = productionFieldDirection(source, fieldSource);
  const ball = parseFieldSpot(ballRaw, lengthYards);
  const drive = parseFieldSpot(driveRaw, lengthYards);
  const downDistance = productionDownDistance(source);
  const distance = Number(downDistance.distance);
  // distance is a yardage; convert to % of field width before offsetting.
  const distancePct = Number.isFinite(distance) ? (distance / lengthYards) * 100 : NaN;
  const gainPct = ball && Number.isFinite(distancePct)
    ? Math.max(0, Math.min(100, ball.pct + (direction === "left" ? -distancePct : distancePct)))
    : null;

  return {
    ballSpot: ball?.raw || "",
    ballPct: renderPctFromRaw(ball?.pct ?? 50),
    driveStart: drive?.raw || "",
    driveStartPct: renderPctFromRaw(drive?.pct ?? ball?.pct ?? 50),
    firstDownSpot: gainPct === null ? "" : spotFromPercent(gainPct, lengthYards),
    firstDownPct: renderPctFromRaw(gainPct ?? ball?.pct ?? 50),
    direction,
    possession: textValue(source.possession, fieldSource.possession, "home").toLowerCase(),
    down: downDistance.down,
    distance: downDistance.distance,
    downDistance: downDistance.combined,
    lengthYards,
    endZoneDepthYards,
    visible: source.ball_spot_visible !== false
  };
}

function collegiateMascotForSide(runtime, side) {
  const identity = objectValue(runtime[`${side}_identity`]);
  return textValue(
    identity.mascot,
    runtime[`${side}_mascot`],
    runtime[`${side}_team`],
    side === "visitor" ? "Visitor" : "Home"
  ).trim();
}

function collegiateFieldSpotLabel(runtime, field, rawSpot) {
  const text = String(rawSpot || "").trim();
  const match = text.match(/^(LEFT|RIGHT)\s+(.+)$/i);
  if (!match) return text || "-";
  const ownSide = field.direction === "left" ? "RIGHT" : "LEFT";
  const offenseSide = field.possession === "visitor" ? "visitor" : "home";
  const defenseSide = offenseSide === "visitor" ? "home" : "visitor";
  const teamSide = match[1].toUpperCase() === ownSide ? offenseSide : defenseSide;
  return `${collegiateMascotForSide(runtime, teamSide)} ${match[2]}`;
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

// Phase C: dispatch the per-poll live board patch by sport family. The
// football path is unchanged; basketball patches its running clock/period,
// and baseball/softball have no sub-second board (their state moves on
// discrete events, which re-render the whole package).
function applyBoardOverrides(root, alias, runtime) {
  if (!root) return;
  const family = productionSportFamily(runtime && runtime.sport);
  if (family === "basketball") return applyBasketballBoardOverrides(root, alias, runtime);
  if (family === "baseball" || family === "softball") return applyDiamondBoardOverrides(root, alias, runtime);
  return applyFootballBoardOverrides(root, alias, runtime);
}

function applyBasketballBoardOverrides(root, alias, runtime) {
  if (!root) return;
  const clock = productionClock(runtime);
  const period = textValue(runtime.period, runtime.quarter, "").trim();
  const shotClock = textValue(runtime.shot_clock, runtime.shotClock, "").trim();

  if (alias === "eight_bit_gameday") {
    const cell = root.querySelector(".bl-8bit-basketball-control-bank .bl-8bit-clock-led")?.closest("span");
    if (cell) setLedText(cell, clock, "bl-8bit-clock-led");
    return;
  }
  if (alias === "friday_night_stadium") {
    const host = root.querySelector(".bl-fns-basketball-clock");
    if (!host) return;
    const led = host.querySelector(".csrn-production-led-override") || host.querySelector("svg");
    const replacement = document.createElement("span");
    replacement.className = "csrn-production-led-override bl-fns-clock-led";
    replacement.textContent = clock;
    replacement.setAttribute("role", "img");
    replacement.setAttribute("aria-label", clock);
    if (led) led.replaceWith(replacement);
    else host.appendChild(replacement);
    const strong = host.querySelector("strong");
    if (strong && period) strong.textContent = period;
    return;
  }
  if (alias === "heritage_press") {
    const clockValue = labeledCell(root, "CLOCK")?.querySelector(":scope > b");
    if (clockValue) clockValue.textContent = clock;
    const periodValue = labeledCell(root, "PERIOD")?.querySelector(":scope > b");
    if (periodValue && period) periodValue.textContent = period;
    return;
  }
  if (alias === "collegiate_traditional") {
    root.querySelectorAll('[data-bind="game.clock"]').forEach(node => { node.textContent = clock; });
    if (period) root.querySelectorAll('[data-bind="game.period"]').forEach(node => { node.textContent = period; });
    if (shotClock) root.querySelectorAll('[data-bind="game.shotClock"]').forEach(node => { node.textContent = shotClock; });
  }
}

function applyDiamondBoardOverrides(root, alias, runtime) {
  if (!root) return;
  // The render signature carries no game-state fields, so the diamond board
  // is kept live here on the fast path -- same contract as the football
  // board. All lookups are guarded: a partly-rendered board is left alone.
  const half = textValue(runtime.inning_half, runtime.inningHalf, "TOP").toUpperCase().startsWith("B") ? "BOT" : "TOP";
  const inning = textValue(runtime.inning, "").trim();
  const balls = textValue(runtime.balls, "").trim();
  const strikes = textValue(runtime.strikes, "").trim();
  const outs = textValue(runtime.outs, "").trim();
  const rawBases = runtime.bases;
  const bases = Array.isArray(rawBases)
    ? [Boolean(rawBases[0]), Boolean(rawBases[1]), Boolean(rawBases[2])]
    : null;

  const setLed = (node, value, cls) => {
    if (!node) return;
    const span = document.createElement("span");
    span.className = `csrn-production-led-override ${cls || ""}`.trim();
    span.textContent = String(value || "-").toUpperCase();
    span.setAttribute("role", "img");
    span.setAttribute("aria-label", span.textContent);
    node.replaceWith(span);
  };
  const leds = (scope) => scope ? [...scope.querySelectorAll(".csrn-production-led-override, svg")] : [];
  // baseDiamond() renders its <i> pips in the visual order [2nd, 3rd, 1st].
  const paintBases = (host) => {
    if (!host || !bases) return;
    const order = [bases[1], bases[2], bases[0]];
    host.querySelectorAll("i").forEach((pip, i) => pip.classList.toggle("on", Boolean(order[i])));
  };
  const inningCellOf = (scope) => [...(scope ? scope.querySelectorAll("span") : [])]
    .find(s => /INNING$/.test((s.querySelector("small")?.textContent || "").trim().toUpperCase())) || null;

  if (alias === "eight_bit_gameday") {
    const bank = root.querySelector(".bl-8bit-diamond-control-bank");
    if (!bank) return;
    const count = leds(bank.querySelector(".bl-8bit-count-pair"));
    setLed(count[0], balls, "bl-8bit-small-led");
    setLed(count[1], strikes, "bl-8bit-small-led");
    const inningCell = inningCellOf(bank);
    setLed(leds(inningCell)[0], inning, "bl-8bit-inning-led");
    const inningSmall = inningCell && inningCell.querySelector("small");
    if (inningSmall) inningSmall.textContent = `${half} INNING`;
    setLed(leds(labeledCell(bank, "OUTS"))[0], outs, "bl-8bit-small-led");
    paintBases(labeledCell(bank, "BASES"));
    return;
  }
  if (alias === "friday_night_stadium") {
    const center = root.querySelector(".bl-fns-diamond-center");
    setLed(leds(center && center.querySelector('strong[aria-label="INNING"]'))[0], `${half} ${inning}`.trim(), "bl-fns-inning-led");
    paintBases(center && center.querySelector(".bl-fns-role-bases"));
    const bottom = root.querySelector(".bl-fns-diamond-bottom");
    setLed(leds(labeledCell(bottom, "BALLS"))[0], balls, "bl-fns-small-led");
    setLed(leds(labeledCell(bottom, "STRIKES"))[0], strikes, "bl-fns-small-led");
    setLed(leds(labeledCell(bottom, "OUTS"))[0], outs, "bl-fns-small-led");
    return;
  }
  if (alias === "heritage_press") {
    const inningB = labeledCell(root, "INNING") && labeledCell(root, "INNING").querySelector(":scope > b");
    if (inningB) inningB.textContent = `${half === "BOT" ? "BOTTOM" : "TOP"} ${inning}`.trim();
    const countB = labeledCell(root, "COUNT") && labeledCell(root, "COUNT").querySelector(":scope > b");
    if (countB) countB.textContent = `${balls || "0"}–${strikes || "0"}`;
    const outsB = labeledCell(root, "OUTS") && labeledCell(root, "OUTS").querySelector(":scope > b");
    if (outsB) outsB.textContent = outs || "0";
    paintBases(labeledCell(root, "RUNNERS"));
    patchHeritageBoxscore(root, runtime);
    return;
  }
  if (alias === "collegiate_traditional") {
    root.querySelectorAll('[data-bind="game.inning"]').forEach(node => { node.textContent = inning; });
    root.querySelectorAll('[data-bind="game.inningHalf"]').forEach(node => {
      node.textContent = `${half === "BOT" ? "▼" : "▲"} ${half === "BOT" ? "BOT" : "TOP"}`;
    });
    patchCollegiateBaseballDiamond(root, {half, inning, balls, strikes, outs, bases}, runtime);
    patchCollegiateBaseballLineScore(root, runtime);
  }
}

// Phase C (commissioned): keep Heritage Press's newspaper line-score box
// (.hp-current-line, built and styled by the engine) live -- R/H/E totals
// and the current at-bat / pitcher name -- on the fast path. The
// per-inning columns are structural and change with the whole board.
function patchHeritageBoxscore(root, runtime) {
  const homeScore = Math.max(0, Number(runtime.home_score || 0));
  const visitorScore = Math.max(0, Number(runtime.visitor_score || 0));
  const line = root.querySelector('.hp-current-line[data-module="game.lineScore"]');
  if (line) {
    const rows = [...line.querySelectorAll(".hp-line-row:not(.head)")];
    const rhe = (row, runs, hits, errors) => {
      if (!row) return;
      const cells = [...row.querySelectorAll(":scope > b")];
      const last3 = cells.slice(-3);
      if (last3[0]) last3[0].textContent = String(runs);
      if (last3[1] && hits != null && hits !== "") last3[1].textContent = String(hits);
      if (last3[2] && errors != null && errors !== "") last3[2].textContent = String(errors);
    };
    rhe(rows[0], homeScore, textValue(runtime.home_hits, runtime.homeHits), textValue(runtime.home_errors, runtime.homeErrors));
    rhe(rows[1], visitorScore, textValue(runtime.visitor_hits, runtime.visitorHits), textValue(runtime.visitor_errors, runtime.visitorErrors));
  }
  const roles = [...root.querySelectorAll(".hp-role-stack .hp-role")];
  const nameOf = (section) => section && section.querySelector("strong");
  const batter = roles.find(s => /AT BAT/i.test(s.querySelector("h3")?.textContent || ""));
  const pitcher = roles.find(s => /(MOUND|CIRCLE)/i.test(s.querySelector("h3")?.textContent || ""));
  const batterName = textValue(runtime.batter_name, runtime.batterName);
  const pitcherName = textValue(runtime.pitcher_name, runtime.pitcherName);
  if (batterName && nameOf(batter)) nameOf(batter).textContent = batterName;
  if (pitcherName && nameOf(pitcher)) nameOf(pitcher).textContent = pitcherName;
}

// T1 (docs/PHASE_C_THEME_SPORT_DISPATCH_PLAN.md): the diamond field-position
// graphic and the inning line score are now rendered natively by the frozen
// engine (collegiateBaseballDiamond / collegiateBaseballLineScore) as part
// of the structurally-prominent control bank, so these are find-and-patch
// fast paths -- no DOM injection -- mirroring the football board's own
// live-patch contract (applyFootballBoardOverrides). Supersedes the R4/R5/
// R9 runtime-injected prototype (ensureCollegiateDiamond /
// ensureCollegiateBaseballBottomBar / patchCollegiateLineScore) entirely.
function patchCollegiateBaseballDiamond(root, d, runtime) {
  const host = root.querySelector(".bl-college-diamond");
  if (!host) return;
  const half = d.half === "BOT" ? "bottom" : "top";
  host.dataset.inningHalf = half;
  const battingSide = half === "bottom" ? "home" : "visitor";
  const setText = (sel, text) => { const n = host.querySelector(sel); if (n) n.textContent = text; };
  setText(".bl-cd-batting", collegiateMascotForSide(runtime, battingSide));
  setText(".bl-cd-count", `${d.balls || "0"}–${d.strikes || "0"}`);
  const outsN = Math.max(0, Math.min(3, Number(d.outs) || 0));
  setText(".bl-cd-outs", `${"● ".repeat(outsN).trim()}${outsN < 3 ? ` ${"○ ".repeat(3 - outsN).trim()}` : ""}`);
  const arrowNode = host.querySelector(".bl-cd-inning-arrow");
  if (arrowNode) arrowNode.textContent = d.half === "BOT" ? "▼" : "▲";
  const runner = d.bases || [false, false, false];
  ["first", "second", "third"].forEach((base, i) => {
    const node = host.querySelector(`.bl-cd-runner.${base}`);
    if (node) node.classList.toggle("on", Boolean(runner[i]));
  });
}

// Same open-ended-columns / shrink / roll-window contract as the full render
// (baseballInningPlan in the frozen engine), computed here in parallel for
// the live fast path -- the two files can't share code (separate script
// tags), so this mirrors the field-geometry helpers' existing duplication
// pattern (applyFieldGeometry/spotFromPercent vs. collegiateField's own
// independent math). Keep both in sync if the column-planning rule changes.
function baseballLineScorePlan(runtime) {
  const num = (v) => { const n = Number(v); return Number.isFinite(n) ? n : null; };
  const current = Math.max(1, num(runtime.inning) || 1);
  const lineScore = objectValue(runtime.line_score);
  const homeRuns = Array.isArray(lineScore.home) ? lineScore.home : [];
  const visitorRuns = Array.isArray(lineScore.visitor) ? lineScore.visitor : [];
  const regulation = Math.max(1, num(runtime.regulation_innings) || 9);
  const played = Math.max(regulation, current, homeRuns.length, visitorRuns.length);
  const CAP = 12;
  const WINDOW = 9;
  const rolled = played > CAP;
  const start = rolled ? played - WINDOW + 1 : 1;
  const innings = [];
  for (let i = start; i <= played; i += 1) innings.push(i);
  return {innings, rolled, hiddenCount: rolled ? start - 1 : 0, played, current};
}

function patchCollegiateBaseballLineScoreRow(root, side, plan, runtime) {
  const row = root.querySelector(`.bl-cls-row.bl-${side}`);
  if (!row) return;
  const innings = row.querySelector(".bl-cls-innings");
  if (innings && Number(innings.dataset.inningCount) !== plan.innings.length) {
    const cells = plan.innings.map((n) => `<span data-inning="${n}"></span>`).join("");
    innings.innerHTML = (plan.rolled ? '<span class="bl-cls-rolled" aria-hidden="true"></span>' : "") + cells;
    innings.dataset.inningCount = String(plan.innings.length);
  }
  if (innings) {
    const rolledNode = innings.querySelector(".bl-cls-rolled");
    if (rolledNode) rolledNode.title = `${plan.hiddenCount} earlier innings scrolled off`;
    const lineScore = objectValue(runtime.line_score);
    const runsArr = Array.isArray(lineScore[side]) ? lineScore[side] : [];
    innings.querySelectorAll("[data-inning]").forEach((cell) => {
      const n = Number(cell.dataset.inning);
      const value = runsArr[n - 1];
      cell.textContent = (value === 0 || value) ? String(value) : (n < plan.current ? "0" : "–");
      cell.classList.toggle("is-current", n === plan.current);
    });
  }
  const hits = textValue(runtime[`${side}_hits`], runtime[`${side}Hits`]);
  const errors = textValue(runtime[`${side}_errors`], runtime[`${side}Errors`]);
  const hitsNode = row.querySelector(`[data-bind="${side}.hits"]`);
  const errorsNode = row.querySelector(`[data-bind="${side}.errors"]`);
  if (hitsNode) hitsNode.textContent = hits === "" ? "–" : hits;
  if (errorsNode) errorsNode.textContent = errors === "" ? "–" : errors;
}

function patchCollegiateBaseballLineScore(root, runtime) {
  const container = root.querySelector(".bl-college-line-score");
  if (!container) return;
  const plan = baseballLineScorePlan(runtime);
  if (Number(container.dataset.inningCount) !== plan.innings.length) {
    const head = container.querySelector(".bl-cls-head .bl-cls-innings");
    if (head) {
      const headCells = plan.innings.map((n) => `<span>${n}</span>`).join("");
      head.innerHTML = (plan.rolled ? '<span class="bl-cls-rolled"></span>' : "") + headCells;
    }
    container.style.setProperty("--csrn-inning-count", String(plan.innings.length + (plan.rolled ? 1 : 0)));
    container.dataset.inningCount = String(plan.innings.length);
  }
  const headCells = container.querySelectorAll(".bl-cls-head .bl-cls-innings > span:not(.bl-cls-rolled)");
  headCells.forEach((node, i) => { node.classList.toggle("is-current", plan.innings[i] === plan.current); });
  patchCollegiateBaseballLineScoreRow(root, "visitor", plan, runtime);
  patchCollegiateBaseballLineScoreRow(root, "home", plan, runtime);
}

function applyFootballBoardOverrides(root, alias, runtime) {
  if (!root || productionSportFamily(runtime && runtime.sport) !== "football") return;

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
      applyFieldGeometry(fieldRoot, field.lengthYards, field.endZoneDepthYards);
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
      node.textContent = field.visible ? collegiateFieldSpotLabel(runtime, field, field.ballSpot) : "-";
    });
    root.querySelectorAll('[data-bind="game.driveStart"]').forEach(node => {
      node.textContent = field.driveStart || "-";
    });
    root.querySelectorAll('[data-bind="game.firstDownSpot"]').forEach(node => {
      node.textContent = collegiateFieldSpotLabel(runtime, field, field.firstDownSpot);
    });
    root.querySelectorAll('[data-bind="game.possessionText"]').forEach(node => {
      const side = field.possession === "visitor" ? "visitor" : "home";
      node.textContent = collegiateMascotForSide(runtime, side);
    });
    root.querySelectorAll('[data-bind="game.possessionLogo"]').forEach(node => {
      const side = field.possession === "visitor" ? "visitor" : "home";
      const identity = objectValue(runtime[`${side}_identity`]);
      const logo = textValue(identity.logo, runtime[`${side}_logo`]);
      const name = textValue(runtime[`${side}_team`], side).trim();
      node.replaceChildren();
      if (logo) {
        const image = document.createElement("img");
        image.src = logo;
        image.alt = "";
        node.appendChild(image);
        return;
      }
      const fallback = document.createElement("span");
      fallback.textContent = name.slice(0, 3).toUpperCase() || side.slice(0, 1).toUpperCase();
      node.appendChild(fallback);
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
  // Phase C: scores are universal; a possession indicator is football/
  // basketball only -- baseball/softball have no possession, so never stamp
  // one onto a diamond board.
  const family = productionSportFamily(runtime.sport);
  const hasPossession = family === "football" || family === "basketball";

  if (alias === "friday_night_stadium") {
    const home = root.querySelector('[data-module="home.score"]');
    const visitor = root.querySelector('[data-module="visitor.score"]');

    setStadiumLedSvg(home, homeScore, "bl-fns-score-led");
    setStadiumLedSvg(visitor, visitorScore, "bl-fns-score-led");

    // The football score marker (fnsPossessionNode) is a football; the
    // basketball tower carries its own possession cue, and a diamond board
    // has none. Only decorate the football score.
    if (family === "football") {
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
    }
    return;
  }

  if (alias === "eight_bit_gameday") {
    const home = root.querySelector('[data-module="home.score"]');
    const visitor = root.querySelector('[data-module="visitor.score"]');

    setLedText(home, homeScore, "bl-8bit-score-led");
    setLedText(visitor, visitorScore, "bl-8bit-score-led");

    if (hasPossession) {
      setLedText(
        labeledCell(root, "POSSESSION"),
        possession === "visitor" ? "VISITOR" : "HOME",
        "bl-8bit-possession-led"
      );
    }
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
    if (possessionValue && hasPossession) {
      possessionValue.textContent =
        possession === "visitor"
          ? textValue(runtime.visitor_team, "VISITOR")
          : textValue(runtime.home_team, "HOME");
    }

    // Heritage's state grid uses newspaper cells rather than all data-bind
    // fields. QUARTER / DOWN are football-only; PERIOD / CLOCK for a
    // non-football board are owned by applyBoardOverrides, so leave them.
    if (family === "football") {
      const periodValue = (labeledCell(root, "QUARTER") || labeledCell(root, "PERIOD"))?.querySelector(":scope > b");
      const clockValue = labeledCell(root, "CLOCK")?.querySelector(":scope > b");
      const downValue = labeledCell(root, "DOWN")?.querySelector(":scope > b");
      if (periodValue) periodValue.textContent = productionFootballPeriod(runtime);
      if (clockValue) clockValue.textContent = productionClock(runtime);
      if (downValue) downValue.textContent = productionDownDistance(runtime).combined;
    }
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
      if (hasPossession) node.dataset.possession = possession;
      else delete node.dataset.possession;
    });
  }
}

function patchLiveGameState(runtime = lastRuntimeForClockPatch) {
  if (!runtime || currentAlias === "legacy") return;
  const root = scoreLayout();
  if (!root) return;

  applyBoardOverrides(root, currentAlias, runtime);
  patchThemeScoresAndPossession(root, currentAlias, runtime);
  patchCollegiateRails(root, runtime, collegiateStatisticsCache.data);
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
    alias === "heritage_press" ||
    alias === "collegiate_traditional";
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
// replaces only athlete pixels using pre-rendered palette-v2 player images
// (see paintFridayNightStandaloneFootballPlayers). No runtime masking/tinting.

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
  // Retained as a thin pass-through: the live Friday Night clash renderer is
  // paintFridayNightStandaloneFootballPlayers (pre-rendered palette-v2 players).
  return paintFridayNightStandaloneFootballPlayers(root,alias,mode,state);
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
    friday_night_stadium: ".bl-fns-video-board",
    collegiate_traditional: ".bl-college-stage"
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
      // Reuse the hidden element that has been buffering this URL since the
      // last poll -- .play() on it starts near-instantly instead of the
      // 5-15s cold fetch+decode of a freshly created <video>.
      const video = takeWarmSponsorVideo(primaryUrl) || document.createElement("video");
      video.className = "csrn-production-sponsor-asset";
      if (video.getAttribute("src") !== primaryUrl) video.src = primaryUrl;
      try { video.currentTime = 0; } catch (_) {}
      video.autoplay = true;
      video.playsInline = true;
      video.preload = "auto";
      video.controls = false;
      video.loop = false;
      // Sole sponsor renderer now that the legacy #sponsorSpotlight panel is gated
      // off whenever a themed board is active — so this element carries the audio
      // for approved advertisement commercials.
      const wantsAudio = textValue(graphic.presentation_mode, "").toLowerCase() === "advertisement" && graphic.audio_enabled === true;
      video.muted = !wantsAudio;
      video.volume = 1;
      video.setAttribute("playsinline", "");
      video.addEventListener("error", () => {
        video.remove();
        if (!installImage(logoUrl)) mediaWrap.classList.add("media-unavailable");
      }, {once:true});
      mediaWrap.appendChild(video);
      video.play().catch(() => {
        // Unmuted autoplay can be blocked without a user gesture; fall back to a
        // muted commercial rather than dropping the video entirely.
        if (!video.muted) {
          video.muted = true;
          video.play().catch(() => {
            video.remove();
            if (!installImage(logoUrl)) mediaWrap.classList.add("media-unavailable");
          });
          return;
        }
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

// Player Spotlight names are shown large by design (see the "player" branch
// of collegiateVideoBoardContent) -- long names need to shrink to fit the
// copy column instead of just truncating with an ellipsis. Runs after every
// full re-render (a Player Spotlight change always re-renders, per the
// signature check above), starting from the CSS base size each time so a
// later shorter name isn't left stuck at a previously-shrunk size.
function fitCollegiatePlayerSpotlightName(root) {
  if (!root) return;
  const el = root.querySelector('.bl-college-player [data-role="spotlight-name"]');
  const container = el && el.parentElement;
  if (!el || !container) return;
  const baseSize = Number(el.dataset.csrnBaseFontPx) || parseFloat(getComputedStyle(el).fontSize) || 64;
  el.dataset.csrnBaseFontPx = String(baseSize);
  const minSize = 26;
  let size = baseSize;
  el.style.fontSize = `${size}px`;
  let guard = 0;
  while (el.scrollWidth > container.clientWidth && size > minSize && guard < 40) {
    size -= 2;
    el.style.fontSize = `${size}px`;
    guard += 1;
  }
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

async function fetchCollegiateStatistics(runtime, alias) {
  if (alias !== "collegiate_traditional") return null;
  const broadcastId = textValue(runtime?.broadcast_id, "");
  if (!broadcastId) return null;
  const now = Date.now();
  if (
    collegiateStatisticsCache.data &&
    collegiateStatisticsCache.broadcastId === broadcastId &&
    now - collegiateStatisticsCache.fetchedAt < 5000
  ) {
    return collegiateStatisticsCache.data;
  }
  if (collegiateStatisticsCache.promise) return collegiateStatisticsCache.promise;
  collegiateStatisticsCache.promise = fetchJson(STATISTICS_URL)
    .then(data => {
      collegiateStatisticsCache.broadcastId = broadcastId;
      collegiateStatisticsCache.fetchedAt = Date.now();
      collegiateStatisticsCache.data = data;
      return data;
    })
    .catch(() => collegiateStatisticsCache.data)
    .finally(() => {
      collegiateStatisticsCache.promise = null;
    });
  return collegiateStatisticsCache.promise;
}

function statDisplay(value) {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? String(numeric) : "-";
}

function playerImage(player) {
  return textValue(player.headshot, player.photo, player.image, player.image_url, player.media_url);
}

function playerDisplayName(player) {
  const name = textValue(player.name, "Player");
  const number = textValue(player.number, "");
  return name.trim() && name.trim() !== number ? name.trim() : (number ? `#${number}` : "Player");
}

function leaderCandidate(player, title, value, label, detail, weight) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric) || numeric <= 0) return null;
  return {
    title,
    name: playerDisplayName(player),
    line: `${numeric} ${label}`,
    detail,
    image: playerImage(player),
    weight: numeric * weight
  };
}

function collegiatePlayerLeaders(statistics, side) {
  const players = Array.isArray(statistics?.players) ? statistics.players : [];
  const candidates = [];
  players
    .filter(player => String(player.team || "").toLowerCase() === side)
    .forEach(player => {
      [
        leaderCandidate(player, "QB Leader", player.passing_yards, "PASS YDS", Number(player.passing_touchdowns || 0) > 0 ? `${player.passing_touchdowns} PASS TD` : `${statDisplay(player.completions)}/${statDisplay(player.pass_attempts)}`, 1),
        leaderCandidate(player, "Rush Leader", player.rushing_yards, "RUSH YDS", Number(player.rushing_touchdowns || 0) > 0 ? `${player.rushing_touchdowns} RUSH TD` : `${statDisplay(player.rushing_attempts)} ATT`, 2.2),
        leaderCandidate(player, "Receiving Leader", player.receiving_yards, "REC YDS", Number(player.receptions || 0) > 0 ? `${player.receptions} REC` : "", 2.1),
        leaderCandidate(player, "Defensive Leader", player.sacks, "SACKS", "", 45),
        leaderCandidate(player, "Takeaway Leader", player.interceptions, "INT", "", 55),
        leaderCandidate(player, "Takeaway Leader", player.fumble_recoveries, "FR", "", 45),
        leaderCandidate(player, "Scoring Leader", player.points, "PTS", Number(player.touchdowns || 0) > 0 ? `${player.touchdowns} TD` : "", 8)
      ].forEach(candidate => {
        if (candidate) candidates.push(candidate);
      });
    });

  // Each title (QB Leader, Scoring Leader, etc.) must surface only the one
  // player who actually leads that category. Without this, every player
  // with a nonzero stat generated their own same-titled candidate -- e.g. a
  // kicker's 2-point XP became its own "Scoring Leader" entry alongside a
  // receiver's 6-point touchdown -- and the rotation eventually reached it,
  // looking like a ranking bug when the point totals themselves were
  // correct all along.
  const bestByTitle = new Map();
  candidates.forEach(candidate => {
    const existing = bestByTitle.get(candidate.title);
    if (!existing || candidate.weight > existing.weight) {
      bestByTitle.set(candidate.title, candidate);
    }
  });

  return Array.from(bestByTitle.values()).sort((a, b) => b.weight - a.weight);
}

// How long each rotating leader stays on screen. Was 12000 -- too quick to
// read on a live broadcast; doubled (plus a little) per operator feedback.
const COLLEGIATE_LEADER_ROTATION_MS = 25000;

function fitPlayerLeaderName(node) {
  if (!node) return;
  node.style.fontSize = "";
  const available = node.clientWidth;
  if (!available) return;
  const base = parseFloat(getComputedStyle(node).fontSize) || 26;
  const floor = Math.max(15, base * 0.6);
  let size = base;
  let guard = 0;
  while (node.scrollWidth > available + 1 && size > floor && guard < 40) {
    size -= 1;
    node.style.fontSize = `${size}px`;
    guard += 1;
  }
}

// T1 item 3 (docs/PHASE_C_THEME_SPORT_DISPATCH_PLAN.md): which side is
// batting flips every half-inning -- TOP bats visitor, BOTTOM bats home.
function baseballBattingSide(runtime) {
  return textValue(runtime.inning_half, runtime.inningHalf, "TOP").toUpperCase().startsWith("B") ? "home" : "visitor";
}

// T1 item 3: "On the Mound" / "At Bat" live rail content, built on the same
// persistent .bl-college-rail system football's leaders use. Names come
// from the fields productionDiamondState already plumbs (pitcher_name /
// batter_name / batter_position); live pitching/batting stats and "On Deck"
// are left as placeholders -- statistics_service.py has no baseball stat
// fields yet, and On Deck needs a batting order, which the T1 spec itself
// defers ("Explicitly NOT in T1 (future round)"). Names now, not fake data.
function patchCollegiateBaseballRails(root, runtime, statistics) {
  const battingSide = baseballBattingSide(runtime);
  ["visitor", "home"].forEach((side) => {
    const rail = root.querySelector(`[data-college-rail="${side}"]`);
    if (!rail) return;
    const team = objectValue(statistics?.teams?.[side]);
    const avgNode = rail.querySelector('[data-stat="batting_avg"]');
    const hitsNode = rail.querySelector('[data-stat="hits"]');
    const rbiNode = rail.querySelector('[data-stat="rbi"]');
    if (avgNode) avgNode.textContent = statDisplay(team.batting_avg);
    if (hitsNode) hitsNode.textContent = statDisplay(team.hits);
    if (rbiNode) rbiNode.textContent = statDisplay(team.rbi);

    const leaderNode = rail.querySelector(".bl-player-leader");
    if (!leaderNode) return;
    const isBatting = side === battingSide;
    const rawName = isBatting
      ? textValue(runtime.batter_name, runtime.batterName)
      : textValue(runtime.pitcher_name, runtime.pitcherName);
    const position = isBatting ? textValue(runtime.batter_position, runtime.batterPosition) : "";
    const displayName = [position, rawName].filter(Boolean).join(" ").trim();

    // Same crest-fallback path the football leader card uses -- there is no
    // per-player headshot source for baseball yet, so this always falls
    // back to the team logo.
    const identity = objectValue(runtime?.[`${side}_identity`]);
    const teamLogo = textValue(identity.logo, runtime?.[`${side}_logo`]);
    if (leaderNode.dataset.renderedImage !== teamLogo) {
      leaderNode.querySelectorAll("img").forEach(node => node.remove());
      if (teamLogo) {
        const image = document.createElement("img");
        image.src = teamLogo;
        image.alt = "";
        leaderNode.prepend(image);
      }
      leaderNode.dataset.renderedImage = teamLogo;
    }
    leaderNode.classList.toggle("is-empty", !rawName);
    leaderNode.classList.toggle("has-photo", Boolean(teamLogo));
    const titleNode = leaderNode.querySelector("span");
    const nameNode = leaderNode.querySelector('[data-player="name"]');
    const lineNode = leaderNode.querySelector('[data-player="line"]');
    if (titleNode) titleNode.textContent = isBatting ? "AT BAT" : "ON THE MOUND";
    if (nameNode) nameNode.textContent = displayName || "Awaiting Lineup";
    if (lineNode) lineNode.textContent = isBatting ? "AVG – · H – · RBI –" : "IP – · ER – · K –";
    if (nameNode) fitPlayerLeaderName(nameNode);
  });
}

function patchCollegiateRails(root, runtime, statistics) {
  if (currentAlias !== "collegiate_traditional" || !root) return;
  const sport = productionSportFamily(runtime && runtime.sport);
  if (sport === "baseball" || sport === "softball") {
    patchCollegiateBaseballRails(root, runtime, statistics);
    return;
  }
  if (!statistics) return;
  ["visitor", "home"].forEach((side, sideIndex) => {
    const rail = root.querySelector(`[data-college-rail="${side}"]`);
    if (!rail) return;
    const team = objectValue(statistics.teams?.[side]);
    const passingYards = rail.querySelector('[data-stat="passing_yards"]');
    const rushingYards = rail.querySelector('[data-stat="rushing_yards"]');
    const turnovers = rail.querySelector('[data-stat="turnovers_gained"]');
    if (passingYards) passingYards.textContent = statDisplay(team.passing_yards);
    if (rushingYards) rushingYards.textContent = statDisplay(team.rushing_yards);
    if (turnovers) turnovers.textContent = statDisplay(team.turnovers_gained);

    const leaderNode = rail.querySelector(".bl-player-leader");
    if (!leaderNode) return;
    const leaders = collegiatePlayerLeaders(statistics, side);
    const leader = leaders.length
      ? leaders[(Math.floor(Date.now() / COLLEGIATE_LEADER_ROTATION_MS) + sideIndex) % leaders.length]
      : null;

    // Same crest fallback the TD spotlight and roster pages already use --
    // a leader with no headshot on file used to render blank instead of the
    // team logo.
    const identity = objectValue(runtime?.[`${side}_identity`]);
    const teamLogo = textValue(identity.logo, runtime?.[`${side}_logo`]);
    const nextImage = leader ? textValue(leader.image, teamLogo) : "";

    // This runs on a 250ms clock timer. Unconditionally tearing down and
    // recreating the <img> every tick forced a fresh, uncached fetch of the
    // headshot ~4x/second even when the leader hadn't changed -- visible as
    // reload/flicker on the live broadcast feed. Only touch the DOM when the
    // rendered image actually needs to change.
    if (leaderNode.dataset.renderedImage !== nextImage) {
      leaderNode.querySelectorAll("img").forEach(node => node.remove());
      if (nextImage) {
        const image = document.createElement("img");
        image.src = nextImage;
        image.alt = "";
        leaderNode.prepend(image);
      }
      leaderNode.dataset.renderedImage = nextImage;
    }

    leaderNode.classList.toggle("is-empty", !leader);
    leaderNode.classList.toggle("has-photo", Boolean(nextImage));
    const title = leaderNode.querySelector("span");
    const name = leaderNode.querySelector('[data-player="name"]');
    const line = leaderNode.querySelector('[data-player="line"]');
    if (!leader) {
      if (title) title.textContent = "Player Leader";
      if (name) name.textContent = "Awaiting Stats";
      if (line) line.textContent = "Live leaders rotate here";
      return;
    }
    if (title) title.textContent = leader.title;
    if (name) name.textContent = leader.name;
    if (line) line.textContent = [leader.line, leader.detail].filter(Boolean).join(" · ");
    // Same shrink-to-fit approach as the main player-spotlight card's name
    // (fitCollegiatePlayerName in csrn-broadcast-layout-engine.js) -- a long
    // name like "Finn Stubbendorff" could overflow the rail's fixed,
    // overflow:hidden box and get clipped mid-word.
    fitPlayerLeaderName(name);
  });
}

// Video-mode support (CSRN_VIDEO_MODE_BUILD_PROMPT.md): the calibration
// guide's on-screen pixel-rect label is a live DOM measurement
// (getBoundingClientRect(), relative to the canvas root's own 1920x1080
// coordinate space), so it belongs in this unpinned runtime rather than
// the frozen engine, which only declares the guide's markup/class
// (collegiateVideoWindow() in csrn-broadcast-layout-engine.js). Called
// from the same patch cadence as patchCollegiateRails()/patchThemeTicker()
// so the label stays current across the lightweight patch-only path too,
// not just a full re-render.
function patchVideoWindowGuide(root, runtime) {
  if (currentAlias !== "collegiate_traditional" || !root) return;
  const label = root.querySelector(".bl-college-video-window-guide .bl-college-video-window-label");
  if (!label) return;
  const canvas = root.closest(".csrn-broadcast-layout") || root;
  const canvasRect = canvas.getBoundingClientRect();
  const windowRect = label.closest(".bl-college-video-window").getBoundingClientRect();
  const scale = canvasRect.width ? 1920 / canvasRect.width : 1;
  const x = Math.round((windowRect.left - canvasRect.left) * scale);
  const y = Math.round((windowRect.top - canvasRect.top) * scale);
  const w = Math.round(windowRect.width * scale);
  const h = Math.round(windowRect.height * scale);
  label.textContent = `VIDEO WINDOW\n${w}×${h} @ (${x}, ${y})\nreference: 1920×1080`;
}

// Layout Builder P0 (docs/LAYOUT_BUILDER_RECONCILIATION.md) -- the In-Game
// application hook (kickoff prompt deliverable 3). Additive: resolves the
// active preset's in_game[base_family] overrides out of runtime.layouts
// (the layouts document app.py's runtime_state() now includes on every
// poll -- see identity_service.py / layout_builder_service.py) and applies
// visibility / zone on top of whatever renderPackage() or the lightweight
// patch-only path already produced. Absent an override for an element,
// this function touches nothing -- byte-identical to today, exactly as
// the kickoff prompt requires. Called from both the "signature unchanged"
// fast path and the full-render path below, same cadence as
// patchCollegiateRails()/patchVideoWindowGuide().
//
// P0 scope (revised 2026-09-14 after a real manual browser smoke test --
// see docs/LAYOUT_BUILDER_RECONCILIATION.md Sec.8 for the full account.
// The scope below is what was actually LIVE-VERIFIED to render correctly,
// not what was originally assumed; two real bugs were caught and fixed/
// walked back rather than shipped):
//   - `visible:false` is honored for `score_box` (the whole bonded
//     `.bl-component[data-component="scorebug"]` node -- clock_period/
//     game_fields are NOT independently addressable inside it yet, same
//     as the reconciliation doc's own "actually splitting the render is a
//     P1/theme-runtime concern" note, Sec.5.1) and for `ticker`
//     (resolveTickerHostR0()) -- both plain display:none/restore toggles,
//     live-verified safe. Confirmed: friday_night_stadium /
//     eight_bit_gameday / heritage_press / collegiate_traditional all
//     stamp dataset.component="scorebug" on their rendered node;
//     digital_neon does not (its own engine file never sets a
//     bl-component/data-component convention), so a score_box override
//     silently no-ops there -- a real, partial-coverage gap, not a hidden
//     assumption.
//   - `zone`/`rect` repositioning is honored ONLY for `ticker`, and only
//     via the isolated `.bl-component[data-component="ticker"]` node
//     (resolveIsolatedTickerComponentR0()), never the broader visibility
//     host (resolveTickerHostR0()). Live-verified: the broader host is an
//     internal flex/grid row shared with the LIVE badge and CSRN "ticker
//     bug" -- forcing IT to position:absolute at a small fixed size
//     collapsed shared layout. Only friday_night_stadium and
//     eight_bit_gameday place ticker as its own isolated top-level
//     component; heritage_press bundles it inside the single whole-board
//     scorebug component (no isolated node to reposition, so a zone/rect
//     override is a no-op there); collegiate_traditional and digital_neon
//     have no data-component="ticker" node either.
//   - `zone`/`rect` on `score_box` is explicitly NOT applied (reverted
//     after live-verification): the bonded scorebug component is nearly
//     canvas-sized, not tightly fitted, so forcing it into a smaller
//     target zone visually crushes the whole board illegible rather than
//     resizing it. See the code comment at its call site below.
//   - `sponsor_slot` / `spotlight_zone` / `video_zone` are SCHEMA-ONLY --
//     no DOM effect at all, for both visibility and zone/rect. This is
//     narrower than the kickoff prompt's stated gate ("hides the sponsor
//     slot"), which the first pass of this hook DID implement -- and which
//     the live smoke test caught as actually producing a blank hole where
//     the whole scoreboard should be, not a graceful hide. See the code
//     comment at its (now-removed) call site below for the full root
//     cause and the real fix this needs (upstream of this hook, in
//     themeVideoModeFor()) -- flagged for a P1/Phase-C-owner decision, not
//     guessed at or shipped broken here.
//   - `clock_period` / `game_fields` / `logo` overrides are schema-only in
//     P0: no independently addressable DOM node exists for them yet.
//   - `video_zone`'s data-module="video.board" / [data-video-mode] markup
//     is untouched by this hook entirely now (see above) -- the contract
//     (CONTRACT_BOUND_ELEMENTS in layout_builder_service.py) was never at
//     risk, since nothing here removes a node or its attributes.
const LAYOUT_DEFAULT_FAMILY_KEY_R0 = "default";

function resolveLayoutOverrideR0(layouts, family, element) {
  if (!layouts || typeof layouts !== "object") return null;
  const presets = layouts.presets;
  const active = layouts.active;
  if (!presets || typeof presets !== "object" || !active) return null;
  const preset = presets[active];
  if (!preset || typeof preset !== "object") return null;
  const scene = preset.in_game;
  if (!scene || typeof scene !== "object") return null;

  const familyDoc = scene[family];
  if (familyDoc && typeof familyDoc === "object" && Object.prototype.hasOwnProperty.call(familyDoc, element)) {
    const value = familyDoc[element];
    return (value && typeof value === "object") ? value : null;
  }
  const fallbackDoc = scene[LAYOUT_DEFAULT_FAMILY_KEY_R0];
  if (fallbackDoc && typeof fallbackDoc === "object" && Object.prototype.hasOwnProperty.call(fallbackDoc, element)) {
    const value = fallbackDoc[element];
    return (value && typeof value === "object") ? value : null;
  }
  return null;
}

function layoutTargetPxR0(override) {
  if (!override || typeof override !== "object") return null;
  const rect = override.rect;
  if (rect && typeof rect === "object") {
    const x = Number(rect.x), y = Number(rect.y), w = Number(rect.w), h = Number(rect.h);
    if ([x, y, w, h].every(Number.isFinite)) {
      return {x: (x / 100) * 1920, y: (y / 100) * 1080, w: (w / 100) * 1920, h: (h / 100) * 1080};
    }
  }
  const zoneName = override.zone;
  if (typeof zoneName === "string" && zoneName) {
    const engine = window.CSRNBroadcastLayoutEngine;
    const zone = engine && engine.zones && engine.zones[zoneName];
    if (zone) return {x: zone.x, y: zone.y, w: zone.w, h: zone.h};
  }
  return null;
}

function setNodeVisibilityR0(node, visible) {
  if (!node) return;
  if (visible === false) {
    if (node.style.display !== "none") {
      if (node.dataset.csrnLayoutPrevDisplay === undefined) {
        node.dataset.csrnLayoutPrevDisplay = node.style.display || "";
      }
      node.style.display = "none";
    }
  } else if (node.dataset.csrnLayoutPrevDisplay !== undefined) {
    node.style.display = node.dataset.csrnLayoutPrevDisplay;
    delete node.dataset.csrnLayoutPrevDisplay;
  }
}

// Repositions `node` to `targetPx` (1920x1080-basis px) using the browser's
// own layout (getBoundingClientRect() / offsetParent) rather than assuming
// any particular theme's DOM nesting or which ancestor is CSS-positioned --
// this is what lets one function reposition both a direct canvas child
// (the scorebug component) and a deeply-nested per-theme ticker node
// correctly.
function setNodeZonePxR0(node, canvasRoot, targetPx) {
  if (!node || !canvasRoot || !targetPx) return;
  const canvasRect = canvasRoot.getBoundingClientRect();
  if (!canvasRect.width || !canvasRect.height) return;
  const scaleX = canvasRect.width / 1920;
  const scaleY = canvasRect.height / 1080;
  const onScreen = {
    left: canvasRect.left + targetPx.x * scaleX,
    top: canvasRect.top + targetPx.y * scaleY,
    width: targetPx.w * scaleX,
    height: targetPx.h * scaleY
  };
  const parent = node.offsetParent || canvasRoot;
  const parentRect = parent.getBoundingClientRect();
  node.style.position = "absolute";
  node.style.left = (onScreen.left - parentRect.left) + "px";
  node.style.top = (onScreen.top - parentRect.top) + "px";
  node.style.width = onScreen.width + "px";
  node.style.height = onScreen.height + "px";
}

// tickerKind "replace-sibling" hides the tickerSelector node and mounts the
// live scroller as its sibling (mountScroller()); tickerKind "inside"
// mounts the scroller as its child. Either way, the node identified here
// is what a visibility toggle should hide -- see
// resolveIsolatedTickerComponentR0() below for why REPOSITIONING needs a
// different, stricter host.
function resolveTickerHostR0(root, alias) {
  const spec = PACKAGE_ALIASES[alias];
  if (!spec) return null;
  const frozenTarget = root.querySelector(spec.tickerSelector);
  if (!frozenTarget) return null;
  if (spec.tickerKind === "replace-sibling") {
    return frozenTarget.parentElement || frozenTarget;
  }
  return frozenTarget;
}

// Repositioning needs a STRICTER host than visibility does. Live-verified
// (2026-09-14 manual smoke test, friday_night_stadium): resolveTickerHostR0()
// above returns an internal flex/grid row (".bl-fns-top-ticker" /
// ".bl-8bit-top-ticker") that also holds the LIVE badge and CSRN "ticker
// bug" -- forcing THAT node to position:absolute at a small fixed size
// collapsed the shared layout hard enough to zero out the scorebug's own
// score digits elsewhere on the page. The frozen engine already places
// ticker as its OWN independent top-level component
// (`.bl-component[data-component="ticker"]`) for friday_night_stadium and
// eight_bit_gameday -- THAT node is what's actually safe to reposition,
// since applyRect() already governs its box independently of any sibling.
// heritage_press bundles its ticker text inside the single whole-board
// scorebug component (one `.bl-component` for everything) -- there is no
// isolated ticker node to reposition there, so a `zone`/`rect` override is
// a no-op for that theme rather than risking the entire board; visibility
// (hiding just the LED text) is unaffected and still works via
// resolveTickerHostR0() above.
function resolveIsolatedTickerComponentR0(root, alias) {
  const spec = PACKAGE_ALIASES[alias];
  if (!spec) return null;
  const frozenTarget = root.querySelector(spec.tickerSelector);
  if (!frozenTarget) return null;
  // The exact-value attribute selector only matches an ancestor whose
  // data-component is literally "ticker" -- a heritage_press-style board
  // (whose only data-component ancestor is "scorebug") correctly yields
  // null here rather than matching the wrong, much larger node.
  return frozenTarget.closest('[data-component="ticker"]') || null;
}

function applyLayoutOverrides(root, runtime) {
  if (!root || !runtime) return;
  const layouts = runtime.layouts;
  if (!layouts || typeof layouts !== "object") return; // no section -> untouched
  const family = productionSportFamily(runtime.sport);
  const alias = currentAlias;
  const canvas = root.closest(".csrn-broadcast-layout") || root;

  // score_box: visibility only (clock_period/game_fields are schema-only
  // in P0 -- see module note above). Repositioning is deliberately NOT
  // applied here: live-verified (2026-09-14), the bonded scorebug
  // component is nearly canvas-sized (it's a loose hit-area wrapper, not
  // a tightly-fitted box), so forcing it into a smaller target zone (e.g.
  // "top-left") visually crushes the whole board into an illegible strip
  // rather than resizing it sensibly. A real fix needs theme-aware
  // internal scaling, not a naive left/top/width/height override -- P1/
  // theme-runtime work, not guessed at here.
  const scorebugOverride = resolveLayoutOverrideR0(layouts, family, "score_box");
  if (scorebugOverride) {
    const scorebugNode = root.querySelector('.bl-component[data-component="scorebug"]');
    if (scorebugNode) {
      setNodeVisibilityR0(scorebugNode, scorebugOverride.visible !== false);
    }
  }

  // ticker: visibility uses the broader host (safe -- a display toggle
  // doesn't disturb shared layout); repositioning uses ONLY the isolated
  // top-level ticker component, when the theme has one (see
  // resolveIsolatedTickerComponentR0()'s module note -- forcing the
  // broader host to position:absolute at a fixed size was live-verified
  // to collapse shared sibling layout).
  const tickerOverride = resolveLayoutOverrideR0(layouts, family, "ticker");
  if (tickerOverride) {
    const tickerNode = resolveTickerHostR0(root, alias);
    if (tickerNode) {
      setNodeVisibilityR0(tickerNode, tickerOverride.visible !== false);
    }
    const px = layoutTargetPxR0(tickerOverride);
    if (px) {
      const isolatedTicker = resolveIsolatedTickerComponentR0(root, alias);
      if (isolatedTicker) setNodeZonePxR0(isolatedTicker, canvas, px);
    }
  }

  // sponsor_slot / spotlight_zone / video_zone: SCHEMA-ONLY in P0 -- no
  // DOM effect. Round-trips correctly through identity_service (P0
  // deliverables 1/2/6) but is deliberately not applied here.
  //
  // This was NOT the original plan -- P0 first shipped with a
  // display:none toggle on nativeVideoBoardHost(root, alias, mode), and
  // that is what the kickoff prompt's stated gate ("hides the sponsor
  // slot") assumed would work. Live-verified (2026-09-14, friday_night_
  // stadium, sponsor mode forced active): hiding it left a BLANK HOLE
  // where the entire scoreboard should be, not a graceful fallback to the
  // normal board. Root cause: these three modes (sponsor/player/highlight)
  // REPLACE the video-board region's visible content in this theme's
  // markup (class "bl-fns-video-replacement") rather than overlaying on
  // top of an always-present scoreboard -- when sponsor mode is active,
  // the normal board simply isn't concurrently rendered underneath, so
  // display:none on the sponsor host reveals nothing.
  //
  // The real fix is upstream of this hook: themeVideoModeFor() (which
  // picks "sponsor"/"player"/"highlight" purely from game state --
  // runtime.player_highlight / runtime.sponsor_spotlight / playerVisible())
  // would need to also treat a hidden layout element as unavailable, so
  // mode selection falls through to the theme's own idle/neutral mode
  // (which DOES show the normal board) instead of picking a mode this
  // hook then has to blank out after the fact. themeVideoModeFor()'s
  // return value feeds the render SIGNATURE array (`polledVideoMode`)
  // that gates full-rebuild-vs-patch-only, so changing its selection
  // logic is real, correctness-sensitive surgery on an already-tested,
  // high-blast-radius function -- deliberately NOT attempted in this
  // additive P0 hook. Flagged for a P1/Phase-C-owner decision, not
  // guessed at here (docs/LAYOUT_BUILDER_RECONCILIATION.md Sec.8).
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
    const collegiateStatistics = await fetchCollegiateStatistics(runtime, alias);
    const captionSegment = activeCaptionSegment(captionState);
    runtimeClockRunning = runtime.clock_running === true;
    lastRuntimeForClockPatch = runtime;
    // Buffer the next sponsor commercial ahead of the Run click. media_url
    // survives a hide in state, so this warms the element between commercials.
    const warmSpot = objectValue(runtime.sponsor_spotlight);
    if (String(warmSpot.media_type || "").toLowerCase() === "video") {
      warmSponsorVideo(imageCandidate(warmSpot.media_url));
    }
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
      activationKey,
      // Video-mode support: these change the rendered DOM structure itself
      // (opaque clash <-> transparent window, 3-column <-> full-width
      // grid), so a toggle must force a full renderPackage() rebuild, not
      // just the lightweight patch-only path below (that path never calls
      // mergeRuntimeState()/renderPackage() again, so a signature that
      // didn't include these would silently ignore the toggle entirely).
      runtime.video_mode,
      runtime.sidebars_hidden,
      runtime.video_calibration_guide
    ]);

    csrnLogThemeSignatureDiffR4(signature);
    if (alias === currentAlias && signature === renderSignature) {
      patchLiveGameState(runtime);
      patchCollegiateRails(scoreLayout(), runtime, collegiateStatistics);
      patchVideoWindowGuide(scoreLayout(), runtime);
      applyLayoutOverrides(scoreLayout(), runtime);
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

    applyBoardOverrides(scoreTarget, alias, runtime);
    patchCollegiateRails(scoreTarget, runtime, collegiateStatistics);
    patchVideoWindowGuide(scoreTarget, runtime);
    repairRenderedPlayerMedia(scoreTarget, state);
    mountCentralBoardMedia(scoreTarget, runtime, activeVideoMode, alias);
    populateHeritagePlayerHost(scoreTarget, runtime, state, alias, activeVideoMode);
    mountHeritageFootballClash(scoreTarget, runtime, state, activeVideoMode, alias);
    // Layout Builder P0: applied after the video-board/player/sponsor
    // mounts above so a `visible:false` override on sponsor_slot/
    // spotlight_zone/video_zone can actually find and hide whatever mode
    // host just got mounted this render.
    applyLayoutOverrides(scoreTarget, runtime);
    normalizePlayerDetailSeparator(scoreTarget, activeVideoMode);
    fitCollegiatePlayerSpotlightName(scoreTarget);
    setPrimaryThemeClasses(activeVideoMode);
    enforceLegacyMediaOwnership(activeVideoMode);

    setHostState(scoreHost(), true, alias, packageId, "rendered");
    document.documentElement.classList.add(SCORE_ACTIVE_CLASS);

    // Capture the result: renderSelected() reports it as
    // CSRNProductionThemeBindingState.tickerActive below. Referencing an
    // undeclared `tickerActive` there threw a ReferenceError that the catch
    // swallowed as "theme binding blocked" -> the overlay stayed a white
    // screen. (2026-09-02 hotfix.)
    const tickerActive = activateThemeTicker(scoreTarget, alias, spec, runtime, true);
    // Own the ticker slot whenever the theme rendered, same as SCORE_ACTIVE_CLASS
    // above -- a dark theme ticker must not hand the slot back to the legacy
    // #eventTicker. Released only by deactivate().
    document.documentElement.classList.add(TICKER_ACTIVE_CLASS);

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
  deactivate,
  // Phase C: exposed for isolated DOM tests of the per-sport board patch.
  // Not part of the runtime's operational contract.
  __phaseC: Object.freeze({
    productionSportFamily,
    mergeRuntimeState,
    applyBoardOverrides,
    applyBasketballBoardOverrides,
    applyDiamondBoardOverrides
  })
});
})();


