(() => {
  "use strict";

  const API = "/api/production-template";
  const SELECT_ID = "csrnPregameThemeSelect";
  const APPLY_ID = "csrnPregameThemeApply";
  const REFRESH_ID = "csrnPregameThemeRefresh";
  const MESSAGE_ID = "csrnPregameThemeMessage";
  const BADGE_ID = "csrnPregameThemeBadge";

  const LABELS = Object.freeze({
    legacy: "Legacy",
    friday_night_stadium: "Friday Night Stadium",
    eight_bit_gameday: "8-Bit Gameday",
    heritage_press: "Heritage Press",
    digital_neon: "Neon",
    collegiate_traditional: "Collegiate Tech"
  });

  // Temporarily hidden from selection -- Neon code is kept, it comes back.
  // TO RE-ENABLE NEON: remove "digital_neon" here (and from
  // DISABLED_PACKAGE_IDS in production_template_service.py). Nothing else.
  const DISABLED = new Set(["digital_neon"]);

  const APPROVED = new Set(
    Object.keys(LABELS).filter(id => !DISABLED.has(id))
  );

  function pruneDisabledOptions() {
    const select = document.getElementById(SELECT_ID);
    if (!select) return;
    for (const option of Array.from(select.options)) {
      if (DISABLED.has(option.value)) option.remove();
    }
  }
  let activePackageId = "legacy";
  let loading = false;

  function byId(id) {
    return document.getElementById(id);
  }

  function valid(value) {
    return APPROVED.has(String(value || "").trim());
  }

  function setMessage(text, state = "") {
    const node = byId(MESSAGE_ID);
    if (!node) return;
    node.textContent = text;
    if (state) node.dataset.state = state;
    else delete node.dataset.state;
  }

  function renderState(packageId, authoritative = true, binding = true) {
    const select = byId(SELECT_ID);
    const badge = byId(BADGE_ID);
    const safe = valid(packageId) ? packageId : "legacy";
    activePackageId = safe;
    if (select) select.value = safe;
    if (badge) {
      badge.textContent = LABELS[safe] || safe;
      badge.dataset.state = authoritative && binding ? "ready" : "staged";
    }
    setMessage(
      `${LABELS[safe] || safe} is the authoritative production theme.` +
      (binding ? " OBS render binding is enabled." : " OBS render binding is not enabled."),
      authoritative && binding ? "ready" : "warning"
    );
  }

  async function loadThemeState() {
    if (loading) return;
    loading = true;
    try {
      const response = await fetch(API, {
        cache: "no-store",
        credentials: "same-origin"
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(payload.error || `Theme state failed (${response.status})`);
      }
      renderState(
        valid(payload.package_id) ? payload.package_id : "legacy",
        payload.authoritative === true,
        payload.render_binding_enabled === true
      );
    } catch (error) {
      setMessage(`Unable to load production theme: ${error.message}`, "error");
      const badge = byId(BADGE_ID);
      if (badge) badge.textContent = "ERROR";
    } finally {
      loading = false;
    }
  }

  async function applyTheme() {
    if (loading) return;
    const select = byId(SELECT_ID);
    const button = byId(APPLY_ID);
    if (!select) return;

    const packageId = String(select.value || "").trim();
    if (!valid(packageId)) {
      setMessage("Select an approved production theme.", "error");
      return;
    }

    if (packageId === activePackageId) {
      setMessage(`${LABELS[packageId]} is already active.`, "ready");
      return;
    }

    const liveLike =
      window.currentState &&
      ["live", "halftime", "postgame"].includes(String(window.currentState.phase || "").toLowerCase());

    if (
      liveLike &&
      !window.confirm(`Change the live production theme from ${LABELS[activePackageId]} to ${LABELS[packageId]}?`)
    ) {
      select.value = activePackageId;
      return;
    }

    loading = true;
    if (button) button.disabled = true;
    setMessage(`Applying ${LABELS[packageId]}…`, "staged");

    try {
      const response = await fetch(API, {
        method: "POST",
        credentials: "same-origin",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({package_id: packageId})
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(payload.error || `Apply failed (${response.status})`);
      }
      renderState(
        valid(payload.package_id) ? payload.package_id : packageId,
        payload.authoritative === true,
        payload.render_binding_enabled === true
      );
      setMessage(
        `${LABELS[packageId]} applied. The production overlay will switch on its next theme-state poll.`,
        "ready"
      );
    } catch (error) {
      select.value = activePackageId;
      setMessage(`Theme apply failed: ${error.message}`, "error");
    } finally {
      loading = false;
      if (button) button.disabled = false;
    }
  }

  function bind() {
    const select = byId(SELECT_ID);
    const apply = byId(APPLY_ID);
    const refresh = byId(REFRESH_ID);
    if (!select || !apply || !refresh) return false;

    pruneDisabledOptions();
    apply.addEventListener("click", applyTheme);
    refresh.addEventListener("click", loadThemeState);
    select.addEventListener("change", () => {
      const chosen = valid(select.value) ? select.value : activePackageId;
      if (chosen === activePackageId) {
        setMessage(`${LABELS[activePackageId]} is currently active.`, "ready");
      } else {
        setMessage(`${LABELS[chosen]} selected. Click Apply Theme to change the production overlay.`, "staged");
      }
    });

    loadThemeState();
    return true;
  }

  function start() {
    if (bind()) return;
    const observer = new MutationObserver(() => {
      if (bind()) observer.disconnect();
    });
    observer.observe(document.documentElement, {childList: true, subtree: true});
  }

  window.CSRNPregameThemeSelector = Object.freeze({
    loadThemeState,
    applyTheme
  });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start, {once: true});
  } else {
    start();
  }
})();
