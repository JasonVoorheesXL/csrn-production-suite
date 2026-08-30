(() => {
"use strict";

const MENU_ID = "csrnProductionTemplateSelect";
const PANEL_ID = "csrnProductionTemplatePanel";
const API = "/api/production-template";

const OPTIONS = Object.freeze([
  // Customer-facing name for the built-in scorebug. Internal id stays "legacy".
  Object.freeze({id:"legacy", label:"Basic Scorebug"}),
  Object.freeze({id:"friday_night_stadium", label:"Friday Night Stadium"}),
  Object.freeze({id:"eight_bit_gameday", label:"8-Bit Gameday"}),
  Object.freeze({id:"heritage_press", label:"Heritage Press"}),
  Object.freeze({id:"digital_neon", label:"Neon"}),
  Object.freeze({id:"collegiate_traditional", label:"Collegiate"})
]);

// Temporarily hidden from selection (Neon code kept; it comes back).
// TO RE-ENABLE NEON: remove "digital_neon" here + in
// production_template_service.py's DISABLED_PACKAGE_IDS.
const DISABLED = Object.freeze(new Set(["digital_neon"]));
const SELECTABLE_OPTIONS = Object.freeze(OPTIONS.filter(option => !DISABLED.has(option.id)));

function valid(value) {
  return SELECTABLE_OPTIONS.some(option => option.id === value);
}

function optionLabel(packageId) {
  return OPTIONS.find(option => option.id === packageId)?.label || OPTIONS[0].label;
}

async function getState() {
  const response = await fetch(API, {cache:"no-store", credentials:"same-origin"});
  if (!response.ok) throw new Error(`Production template state ${response.status}`);
  const payload = await response.json();
  return {
    packageId: valid(payload.package_id) ? payload.package_id : "legacy",
    authoritative: payload.authoritative === true,
    renderBindingEnabled: payload.render_binding_enabled === true
  };
}

async function saveSelection() {
  const menu = document.getElementById(MENU_ID);
  const button = document.getElementById("csrnProductionTemplateSave");
  if (!menu) return;

  const packageId = valid(menu.value) ? menu.value : "legacy";
  if (button) button.disabled = true;
  setMessage("Saving authoritative production selection…");

  try {
    const response = await fetch(API, {
      method:"POST",
      credentials:"same-origin",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify({package_id:packageId})
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.error || `Save failed (${response.status})`);
    renderStatus({
      packageId:valid(payload.package_id) ? payload.package_id : "legacy",
      authoritative:payload.authoritative === true,
      renderBindingEnabled:payload.render_binding_enabled === true
    });
    setMessage(
      packageId === "legacy"
        ? "Basic Scorebug selected."
        : "Production selection saved. The OBS overlay will render this approved package with automatic Basic Scorebug fallback on any render failure."
    );
  } catch (error) {
    setMessage(`Save failed: ${error.message}`);
  } finally {
    if (button) button.disabled = false;
  }
}

function setMessage(text) {
  const node = document.getElementById("csrnProductionTemplateMessage");
  if (node) node.textContent = text || "";
}

function renderStatus(state) {
  const menu = document.getElementById(MENU_ID);
  const chosen = document.getElementById("csrnProductionTemplateChosen");
  const authority = document.getElementById("csrnProductionTemplateAuthority");
  const binding = document.getElementById("csrnProductionTemplateBinding");

  if (menu) menu.value = state.packageId;
  if (chosen) {
    chosen.textContent = `Production: ${optionLabel(state.packageId)}`;
    chosen.dataset.state = "ready";
  }
  if (authority) {
    authority.textContent = state.authoritative ? "Server state: authoritative" : "Server state: unavailable";
    authority.dataset.state = state.authoritative ? "ready" : "blocked";
  }
  if (binding) {
    binding.textContent = state.renderBindingEnabled ? "OBS binding: enabled" : "OBS binding: disabled";
    binding.dataset.state = state.renderBindingEnabled ? "ready" : "blocked";
  }
}

async function loadState() {
  try {
    const state = await getState();
    renderStatus(state);
    setMessage("Selection is persisted by the CSRN server and is now connected to the production renderer.");
  } catch (error) {
    renderStatus({packageId:"legacy", authoritative:false, renderBindingEnabled:false});
    setMessage(`Unable to load authoritative state: ${error.message}`);
  }
}

function buildPanel() {
  if (document.getElementById(PANEL_ID)) return;
  const main = document.querySelector("main");
  if (!main) return;

  const section = document.createElement("section");
  section.id = PANEL_ID;
  section.className = "csrn-production-template-panel";
  section.innerHTML = `
    <h2>Production Template Selection</h2>
    <p>Choose the approved template used by the production OBS overlay. Basic Scorebug remains the automatic fallback if a selected package cannot load or render.</p>
    <div class="csrn-production-template-grid">
      <label for="${MENU_ID}">
        Approved production template
        <select id="${MENU_ID}"></select>
      </label>
      <button id="csrnProductionTemplateSave" type="button">Save Production Selection</button>
    </div>
    <div class="csrn-production-template-status">
      <span id="csrnProductionTemplateChosen" class="csrn-production-template-chip" data-state="staged">Production: loading…</span>
      <span id="csrnProductionTemplateAuthority" class="csrn-production-template-chip" data-state="staged">Server state: loading…</span>
      <span id="csrnProductionTemplateBinding" class="csrn-production-template-chip" data-state="staged">OBS binding: loading…</span>
    </div>
    <p id="csrnProductionTemplateMessage" class="csrn-production-template-note">Loading authoritative state…</p>
  `;
  main.insertBefore(section, main.firstChild);

  const menu = document.getElementById(MENU_ID);
  for (const option of SELECTABLE_OPTIONS) {
    const node = document.createElement("option");
    node.value = option.id;
    node.textContent = option.label;
    menu.appendChild(node);
  }

  document.getElementById("csrnProductionTemplateSave")
    ?.addEventListener("click", saveSelection);
  loadState();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", buildPanel, {once:true});
} else {
  buildPanel();
}

window.CSRNProductionTemplateMenu = Object.freeze({API, OPTIONS, getState, saveSelection, loadState});
})();
