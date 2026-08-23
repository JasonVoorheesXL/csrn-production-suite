(() => {
"use strict";

const EXPECTED = Object.freeze([
  Object.freeze({
    packageId: "friday_night_stadium",
    globalName: "CSRNFridayNightStadiumEngine",
    renderCandidates: ["renderPackage", "render", "mount"]
  }),
  Object.freeze({
    packageId: "eight_bit_gameday",
    globalName: "CSRNEightBitGamedayEngine",
    renderCandidates: ["renderPackage", "render", "mount"]
  }),
  Object.freeze({
    packageId: "digital_neon",
    globalName: "CSRNNeonR2Engine",
    renderCandidates: ["renderPackage", "render", "mount"]
  }),
  Object.freeze({
    packageId: "heritage_press",
    globalName: "CSRNHeritagePressEngine",
    renderCandidates: ["renderPackage", "render", "mount"]
  })
]);

function inspectOne(spec) {
  const api = window[spec.globalName];
  const renderEntry = api
    ? spec.renderCandidates.find(name => typeof api[name] === "function") || ""
    : "";
  return Object.freeze({
    packageId: spec.packageId,
    globalName: spec.globalName,
    loaded: Boolean(api),
    renderEntry,
    ready: Boolean(api && renderEntry)
  });
}

function inspect() {
  const engines = EXPECTED.map(inspectOne);
  const baseReady = Boolean(window.CSRNBroadcastLayoutEngine);
  const ready = baseReady && engines.every(item => item.ready);
  const result = Object.freeze({
    schema: "csrn-production-theme-readiness-v1",
    isolated: true,
    liveOverlayUntouched: true,
    baseReady,
    engines,
    ready
  });

  window.CSRNProductionThemeReadiness = result;
  window.dispatchEvent(new CustomEvent("csrn:production-theme-readiness", {
    detail: result
  }));

  const overall = document.getElementById("overall");
  if (overall) {
    overall.textContent = ready ? "READY" : "BLOCKED";
    overall.dataset.ready = String(ready);
  }

  const body = document.getElementById("results");
  if (body) {
    body.textContent = "";
    for (const item of engines) {
      const row = document.createElement("tr");
      const values = [
        item.packageId,
        item.globalName,
        item.renderEntry || "missing",
        item.ready ? "yes" : "no"
      ];
      values.forEach((value, index) => {
        const cell = document.createElement("td");
        cell.textContent = value;
        if (index === 3) cell.dataset.ready = String(item.ready);
        row.appendChild(cell);
      });
      body.appendChild(row);
    }
  }

  const json = document.getElementById("json");
  if (json) json.textContent = JSON.stringify(result, null, 2);
  return result;
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", inspect, {once: true});
} else {
  inspect();
}

window.CSRNProductionThemeProbe = Object.freeze({EXPECTED, inspect});
})();