(() => {
"use strict";

const HOST_ID = "csrnProductionThemeHost";
const LEGACY_IDS = [
  "scorebug",
  "eventTicker",
  "lowerThird",
  "playerGraphic",
  "personnelGraphic"
];
const APPROVED_PACKAGES = new Set([
  "friday_night_stadium",
  "eight_bit_gameday",
  "digital_neon",
  "heritage_press",
  "collegiate_traditional"
]);

function text(value, fallback = "") {
  return value === null || value === undefined ? fallback : String(value);
}

function integer(value, fallback = 0) {
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function bool(value, fallback = false) {
  if (typeof value === "boolean") return value;
  if (value === 1 || value === "1" || value === "true") return true;
  if (value === 0 || value === "0" || value === "false") return false;
  return fallback;
}

function identity(source = {}, side = "") {
  return Object.freeze({
    side,
    name: text(source.name || source.team_name || source.school_name),
    mascot: text(source.mascot),
    abbreviation: text(source.abbreviation || source.short_name),
    logo: text(source.logo || source.logo_url),
    primaryColor: text(source.primary_color || source.primaryColor, "#777777"),
    secondaryColor: text(source.secondary_color || source.secondaryColor, "#FFFFFF"),
    record: text(source.record)
  });
}

function normalizeSport(value) {
  const sport = text(value, "football").trim().toLowerCase();
  return ["football", "basketball", "baseball", "softball"].includes(sport)
    ? sport
    : "football";
}

function normalizePackage(publicState = {}) {
  const candidates = [
    publicState.package_id,
    publicState.packageId,
    publicState.active_package_id,
    publicState.activePackageId,
    publicState.theme_package_id
  ];
  const selected = candidates.map(v => text(v).trim()).find(Boolean) || "";
  return APPROVED_PACKAGES.has(selected) ? selected : "";
}

function mapState(runtimeState = {}, publicState = {}) {
  const home = runtimeState.home_identity || runtimeState.home || {};
  const visitor = runtimeState.visitor_identity || runtimeState.visitor || {};
  const sport = normalizeSport(
    runtimeState.sport ||
    runtimeState.sport_key ||
    publicState.sport ||
    publicState.sport_key
  );

  return Object.freeze({
    schema: "csrn-production-theme-state-v1",
    packageId: normalizePackage(publicState),
    sport,
    home: identity(home, "home"),
    visitor: identity(visitor, "visitor"),
    homeScore: integer(runtimeState.home_score ?? runtimeState.homeScore, 0),
    visitorScore: integer(runtimeState.visitor_score ?? runtimeState.visitorScore, 0),
    period: text(runtimeState.period || runtimeState.quarter || runtimeState.inning),
    clock: text(runtimeState.clock || runtimeState.game_clock),
    down: text(runtimeState.down),
    distance: text(runtimeState.distance),
    possession: text(runtimeState.possession).toLowerCase(),
    scorebugVisible: bool(runtimeState.scorebug_visible, true),
    tickerVisible: bool(runtimeState.ticker_visible, true),
    revision: text(
      publicState.revision ||
      publicState.theme_revision ||
      runtimeState.overlay_revision
    )
  });
}

function host() {
  return document.getElementById(HOST_ID);
}

function setLegacyVisible(visible) {
  for (const id of LEGACY_IDS) {
    const node = document.getElementById(id);
    if (!node) continue;
    node.dataset.productionThemeSuppressed = visible ? "false" : "true";
    node.style.visibility = visible ? "" : "hidden";
  }
}

function renderPlaceholder(state) {
  const node = host();
  if (!node) return false;
  node.dataset.packageId = state.packageId;
  node.dataset.sport = state.sport;
  node.dataset.active = "true";
  node.hidden = false;

  const detail = node.querySelector("[data-csrn-production-theme-status]");
  if (detail) {
    detail.textContent = `${state.packageId} · ${state.sport}`;
  }

  node.dispatchEvent(new CustomEvent("csrn:production-theme-state", {
    detail: state
  }));
  return true;
}

function deactivate(reason = "fallback") {
  const node = host();
  if (node) {
    node.hidden = true;
    node.dataset.active = "false";
    node.dataset.reason = reason;
    delete node.dataset.packageId;
    delete node.dataset.sport;
  }
  setLegacyVisible(true);
}

function apply(runtimeState, publicState) {
  const state = mapState(runtimeState, publicState);
  if (!state.packageId) {
    deactivate("missing-or-unapproved-package");
    return Object.freeze({active: false, state});
  }

  if (!renderPlaceholder(state)) {
    deactivate("missing-host");
    return Object.freeze({active: false, state});
  }

  setLegacyVisible(false);
  return Object.freeze({active: true, state});
}

window.CSRNProductionThemeAdapter = Object.freeze({
  HOST_ID,
  APPROVED_PACKAGES,
  mapState,
  apply,
  deactivate
});
})();
