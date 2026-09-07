# Adding a sport to a frozen theme

Every shipped theme engine (`csrn-broadcast-layout-engine.js`,
`csrn-friday-night-stadium-engine.js`, `csrn-eight-bit-gameday-engine.js`,
`csrn-heritage-press-engine.js`, `csrn-neon-r2-engine.js`) already takes
`sport` and branches internally to `football` / `basketball` /
`baseball` / `softball`. Most of these files carry a **SHA-256 visual
freeze** (`test_gate12/13/14/78/116/126/138/142`), so a new sport must not
edit them.

There are two established patterns; use whichever fits.

## 1. Runtime injection (Phase C's approach)

`csrn-production-theme-runtime.js` and `.css` are **not** frozen. Add the
new sport's live behaviour there:

- extend `productionSportFamily()` and `mergeRuntimeState`'s per-family
  block with the new sport's game fields;
- add a `apply<Sport>BoardOverrides()` branch to `applyBoardOverrides()`;
- inject any new visual (e.g. `ensureCollegiateDiamond`) into the board
  the engine already rendered, and style it in
  `csrn-production-theme-runtime.css`.

Best when the engine already renders a usable layout for the sport and you
only need to keep it live or add a graphic overlay.

## 2. Driver-file decorator (Digital Neon's approach)

`csrn-neon-baseball-r43-driver.js` / `csrn-neon-softball-r42-driver.js`
show the pattern for a frozen *engine*:

```js
(() => {
  "use strict";
  const base = window.CSRNNeonR2Engine;                 // the frozen engine
  function renderPackage(root, id, sport = "football", value = {}, opts = {}) {
    const result = base.renderPackage(root, id, sport, value, opts);
    if (sport !== "<my-sport>") return result;          // no-op for others
    /* mutate `root` -- add decorative layers into an existing container */
    return result;
  }
  window.CSRNMy<Sport>Driver = Object.freeze({ version, renderPackage });
  window.CSRNNeonR2Engine = Object.freeze({ ...base, renderPackage }); // re-export
})();
```

Load the driver file **after** the engine (and after any earlier drivers)
in that theme's `PACKAGE_ALIASES` entry in
`csrn-production-theme-runtime.js`. The frozen engine file is never
touched, so its fingerprint holds; add a `test_gate*` for the driver
itself.

Use this when you need to change what the *engine* emits (extra art
layers, a different container) rather than just patch live values.

## Checklist

- [ ] Engine already branches on the sport? (all five do today)
- [ ] Live values wired in `applyBoardOverrides` per package theme
- [ ] Any new visual injected by the runtime OR by a driver file — never
      by editing a frozen engine
- [ ] Possession / down / period labels gated so nothing football-shaped
      leaks (`hasPossession`, `family === "football"`)
- [ ] Central video-board region present for the sport — the engine emits
      `data-module="video.board"` + a `[data-video-mode]` host, or the
      runtime injects one (see `ensureCollegiateVideoStage`) so
      `nativeVideoBoardHost()` resolves and a future feed has a home
      (Gate 16.7). Heritage video inherits `csrn-production-highlight-video`
      for the Gate 16.9 decolorize filter automatically (keyed on
      alias + mode, not sport).
- [ ] `static/csrn-phasec-dispatch-lab.html` extended to exercise it
- [ ] Full suite green; frozen `test_gate*` fingerprints unchanged (or
      re-pinned + `CSRN_PROJECT_BIBLE.md` updated if a frozen file really
      had to change)
