(() => {
  "use strict";

  const VERSION = "1.7.0";

  const SPORT_CONTRACTS = Object.freeze({
    football: Object.freeze({
      required: ["home", "visitor", "game"],
      gameFields: ["period", "clock", "downDistance", "playClock", "possession"],
      preferredScorebugZones: ["bottom-center", "top-center", "top-left"]
    }),
    basketball: Object.freeze({
      required: ["home", "visitor", "game"],
      gameFields: ["period", "clock", "shotClock", "homeFouls", "visitorFouls", "possession"],
      preferredScorebugZones: ["bottom-center", "top-center"]
    }),
    baseball: Object.freeze({
      required: ["home", "visitor", "game"],
      gameFields: ["inning", "inningHalf", "balls", "strikes", "outs", "bases", "pitcherName", "batterName", "batterPosition"],
      preferredScorebugZones: ["top-left", "top-right"]
    }),
    softball: Object.freeze({
      required: ["home", "visitor", "game"],
      gameFields: ["inning", "inningHalf", "balls", "strikes", "outs", "bases", "pitcherName", "batterName", "batterPosition"],
      preferredScorebugZones: ["top-left", "top-right"]
    })
  });

  const BASEBALL_FUTURE_COMPONENTS = Object.freeze([
    "lineup", "atBat", "onDeck", "inTheHole", "defensiveAlignment",
    "pitcherCard", "batterCard", "baserunnerState", "inningSummary", "lineScore"
  ]);

  const SPORT_STATE_CONTRACTS = Object.freeze({
    football: Object.freeze({possessionValues: Object.freeze(["home", "visitor", "none"])}),
    baseball: Object.freeze({inningHalfValues: Object.freeze(["TOP", "BOTTOM"]), futureComponents: BASEBALL_FUTURE_COMPONENTS}),
    softball: Object.freeze({inningHalfValues: Object.freeze(["TOP", "BOTTOM"]), futureComponents: BASEBALL_FUTURE_COMPONENTS})
  });

  const DEFAULT_STATE = Object.freeze({
    sport: "football",
    home: Object.freeze({
      name: "NORTHWOOD",
      shortName: "NORTHWOOD",
      mascot: "KNIGHTS",
      record: "5-1",
      score: 13,
      primary: "#0A2342",
      secondary: "#BFC9D4",
      logo: ""
    }),
    visitor: Object.freeze({
      name: "PINE VALLEY",
      shortName: "PINE VALLEY",
      mascot: "PANTHERS",
      record: "4-2",
      score: 11,
      primary: "#064624",
      secondary: "#B8C7BC",
      logo: ""
    }),
    game: Object.freeze({
      period: "Q3",
      clock: "12:00",
      downDistance: "1ST & 10",
      playClock: "25",
      possession: "home",
      shotClock: "24",
      homeFouls: "4",
      visitorFouls: "5",
      inning: "5",
      inningHalf: "TOP",
      balls: "2",
      strikes: "1",
      outs: "1",
      bases: Object.freeze([true, false, true]),
      pitcherName: "RYAN LITHERS",
      batterName: "TOMMY GUNNS",
      batterPosition: "2B",
      ballSpot: "LEFT 42",
      driveStart: "LEFT 25",
      firstDownSpot: "RIGHT 48",
      fieldDirection: "right",
      field: Object.freeze({
        ballSpot: "LEFT 42",
        ballPct: 42,
        driveStart: "LEFT 25",
        driveStartPct: 25,
        firstDownSpot: "RIGHT 48",
        firstDownPct: 52,
        direction: "right",
        possession: "home",
        downDistance: "1ST & 10",
        visible: true
      })
    }),
    player: Object.freeze({
      name: "ALEX CARTER",
      number: "12",
      position: "QB",
      detail: "18/24 · 244 YDS · 2 TD",
      headshot: "",
      stats: Object.freeze({
        football: Object.freeze([
          Object.freeze({label:"COMP/ATT", value:"18/24"}),
          Object.freeze({label:"PASS YDS", value:"244"}),
          Object.freeze({label:"PASS TD", value:"2"}),
          Object.freeze({label:"INT", value:"0"})
        ]),
        basketball: Object.freeze([
          Object.freeze({label:"PTS", value:"24"}),
          Object.freeze({label:"REB", value:"8"}),
          Object.freeze({label:"AST", value:"6"}),
          Object.freeze({label:"STL", value:"3"})
        ]),
        baseball: Object.freeze([
          Object.freeze({label:"H", value:"3"}),
          Object.freeze({label:"RBI", value:"2"}),
          Object.freeze({label:"R", value:"2"}),
          Object.freeze({label:"HR", value:"1"})
        ]),
        softball: Object.freeze([
          Object.freeze({label:"H", value:"3"}),
          Object.freeze({label:"RBI", value:"3"}),
          Object.freeze({label:"R", value:"2"}),
          Object.freeze({label:"SB", value:"1"})
        ])
      })
    }),
    sponsor: Object.freeze({
      name: "COMMUNITY PARTNER",
      line: "Proud supporter of local athletics",
      logo: ""
    }),
    highlight: Object.freeze({
      title: "PLAYER HIGHLIGHT",
      detail: "42-yard touchdown reception"
    }),
    captions: Object.freeze({
      speaker: "PLAY-BY-PLAY",
      text: "First down at the visitor thirty-two."
    }),
    ticker: Object.freeze({
      text: "NORTHWOOD TOUCHDOWN · PINE VALLEY FIELD GOAL · HALFTIME REPORT"
    })
  });

  const COMPONENT_TYPES = Object.freeze([
    "scorebug",
    "ticker",
    "playerCard",
    "highlightVideo",
    "sponsor",
    "captions"
  ]);


  const PRESENTATION_SCENARIOS = Object.freeze({
    baseline: Object.freeze(["scorebug", "ticker"]),
    captions: Object.freeze(["scorebug", "ticker", "captions"]),
    player: Object.freeze(["scorebug", "ticker", "playerCard"]),
    highlight: Object.freeze(["scorebug", "ticker", "highlightVideo"]),
    sponsor: Object.freeze(["scorebug", "ticker", "sponsor"]),
    feature: Object.freeze(["scorebug", "ticker", "playerCard", "highlightVideo"])
  });

  const ZONES = Object.freeze({
    "top-left": {x: 40, y: 36, w: 760, h: 240},
    "top-center": {x: 330, y: 30, w: 1260, h: 250},
    "top-full": {x: 40, y: 30, w: 1840, h: 280},
    "top-right": {x: 1120, y: 36, w: 760, h: 280},
    "left-center": {x: 50, y: 335, w: 650, h: 430},
    "center": {x: 450, y: 300, w: 1020, h: 520},
    "right-center": {x: 1220, y: 335, w: 650, h: 430},
    "bottom-left": {x: 45, y: 735, w: 760, h: 250},
    "bottom-center": {x: 255, y: 765, w: 1410, h: 245},
    "bottom-right": {x: 1115, y: 735, w: 760, h: 250},
    "full-safe": {x: 40, y: 30, w: 1840, h: 1000}
  });

  const COMPONENT_DEFAULT_SIZES = Object.freeze({
    scorebug: Object.freeze({w: 1140, h: 150}),
    ticker: Object.freeze({w: 1410, h: 55}),
    playerCard: Object.freeze({w: 610, h: 330}),
    highlightVideo: Object.freeze({w: 640, h: 360}),
    sponsor: Object.freeze({w: 520, h: 180}),
    captions: Object.freeze({w: 1200, h: 70})
  });

  const AUTO_FALLBACK_ZONES = Object.freeze({
    scorebug: Object.freeze(["bottom-center", "top-center", "top-left", "top-right"]),
    ticker: Object.freeze(["bottom-center", "top-center"]),
    playerCard: Object.freeze(["left-center", "bottom-left", "top-left"]),
    highlightVideo: Object.freeze(["right-center", "top-right", "center", "left-center"]),
    sponsor: Object.freeze(["top-left", "top-right", "left-center", "right-center"]),
    captions: Object.freeze(["top-center", "bottom-center", "top-right", "top-left"])
  });

  function componentSize(component, rule = {}) {
    const fallback = COMPONENT_DEFAULT_SIZES[component];
    if (!fallback) throw new Error(`Missing default size for ${component}.`);
    return {
      w: Number(rule.width || fallback.w),
      h: Number(rule.height || fallback.h)
    };
  }

  function fitInZone(zoneName, component, rule = {}) {
    const bounds = zone(zoneName);
    const size = componentSize(component, rule);
    if (size.w > bounds.w || size.h > bounds.h) {
      return null;
    }

    let x = bounds.x + (bounds.w - size.w) / 2;
    let y = bounds.y + (bounds.h - size.h) / 2;

    if (zoneName.endsWith("-left")) x = bounds.x;
    if (zoneName.endsWith("-right")) x = bounds.x + bounds.w - size.w;
    if (zoneName.startsWith("top-")) y = bounds.y;
    if (zoneName.startsWith("bottom-")) y = bounds.y + bounds.h - size.h;

    if (component === "scorebug" && zoneName.startsWith("bottom-")) y = bounds.y;
    if (component === "ticker" && zoneName.startsWith("bottom-")) y = bounds.y + bounds.h - size.h;
    if (component === "captions" && zoneName.startsWith("top-")) y = bounds.y;
    if (component === "captions" && zoneName.startsWith("bottom-")) {
      const configuredStackHeight = Number(rule.stackAboveHeight);
      const tickerHeight = Number.isFinite(configuredStackHeight) && configuredStackHeight > 0
        ? configuredStackHeight
        : COMPONENT_DEFAULT_SIZES.ticker.h;
      const laneGap = 12;
      y = bounds.y + bounds.h - size.h - tickerHeight - laneGap;
    }

    x += Number(rule.offsetX || 0);
    y += Number(rule.offsetY || 0);

    return {x, y, w: size.w, h: size.h};
  }


  const clone = (value) => JSON.parse(JSON.stringify(value));
  const esc = (value) => String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");

  function mergeState(value = {}) {
    const base = clone(DEFAULT_STATE);
    for (const key of Object.keys(value || {})) {
      if (value[key] && typeof value[key] === "object" && !Array.isArray(value[key])) {
        base[key] = {...base[key], ...value[key]};
      } else {
        base[key] = value[key];
      }
    }
    return base;
  }

  function zone(name) {
    const item = ZONES[name];
    if (!item) throw new Error(`Unknown layout zone: ${name}`);
    return {...item};
  }

  function rectsOverlap(a, b, margin = 0) {
    return !(
      a.x + a.w + margin <= b.x ||
      b.x + b.w + margin <= a.x ||
      a.y + a.h + margin <= b.y ||
      b.y + b.h + margin <= a.y
    );
  }

  function resolvePlacements(manifest, sport, activeComponents = PRESENTATION_SCENARIOS.baseline) {
    const profile = manifest.sports[sport] || manifest.sports.football;
    if (!profile) throw new Error(`${manifest.id} does not support ${sport}.`);

    const placed = {};
    const occupied = [];

    const requested = [...new Set(activeComponents)];
    for (const component of requested) {
      if (!COMPONENT_TYPES.includes(component)) {
        throw new Error(`Unknown active component: ${component}`);
      }
      const rule = profile.components[component];
      if (!rule || rule.enabled === false) continue;

      const choices = [
        rule.zone,
        ...(rule.fallbackZones || []),
        ...(AUTO_FALLBACK_ZONES[component] || [])
      ].filter((value, index, values) => value && values.indexOf(value) === index);

      let selected = null;

      for (const choice of choices) {
        const candidate = fitInZone(choice, component, rule);
        if (!candidate) continue;

        const collision = occupied.some((item) => {
          if ((rule.allowOverlapWith || []).includes(item.component)) return false;
          if ((item.allowOverlapWith || []).includes(component)) return false;
          return rectsOverlap(candidate, item.rect, rule.margin || 8);
        });

        if (!collision) {
          selected = {zone: choice, rect: candidate};
          break;
        }
      }

      if (!selected) {
        if (rule.collisionPolicy === "suspend") continue;
        const firstUsable = choices
          .map((choice) => ({zone: choice, rect: fitInZone(choice, component, rule)}))
          .find((item) => item.rect);
        if (!firstUsable) {
          throw new Error(`${manifest.id}/${sport}/${component} cannot fit in any configured zone.`);
        }
        selected = {...firstUsable, colliding: true};
      }

      placed[component] = {
        ...rule,
        ...selected,
        component
      };
      occupied.push({
        component,
        rect: selected.rect,
        allowOverlapWith: rule.allowOverlapWith || []
      });
    }

    return placed;
  }

  function identity(team, side, options = {}) {
    const logo = options.logo === false ? "" :
      `<div class="bl-logo" data-bind="${side}.logo">${team.logo ? `<img src="${esc(team.logo)}" alt="">` : `<span>${esc(team.shortName.slice(0,1))}</span>`}</div>`;
    const mascot = options.mascot === false ? "" :
      `<div class="bl-mascot" data-bind="${side}.mascot">${esc(team.mascot)}</div>`;
    const record = options.record === false ? "" :
      `<div class="bl-record" data-bind="${side}.record">${esc(team.record)}</div>`;
    return `${logo}<div class="bl-team-copy"><div class="bl-team-name" data-bind="${side}.name">${esc(team.name)}</div>${mascot}${record}</div>`;
  }


  function normalizedTeamColor(value) {
    const raw = String(value || "").trim();
    const match = raw.match(/^#([0-9a-f]{6})$/i);
    return match ? `#${match[1].toUpperCase()}` : "";
  }

  function isNearBlackColor(value) {
    const color = normalizedTeamColor(value);
    if (!color) return true;
    const red = parseInt(color.slice(1,3),16);
    const green = parseInt(color.slice(3,5),16);
    const blue = parseInt(color.slice(5,7),16);
    return Math.max(red,green,blue) < 48;
  }

  function modernPossessionAccent(team) {
    const primary = normalizedTeamColor(team && team.primary);
    const secondary = normalizedTeamColor(team && team.secondary);
    if (primary && !isNearBlackColor(primary)) return primary;
    if (secondary && !isNearBlackColor(secondary)) return secondary;
    return "#B5121B";
  }

  function modernTeamStyle(team) {
    const primary = normalizedTeamColor(team && team.primary);
    const panel = primary && !isNearBlackColor(primary) ? primary : "#192532";
    return `style="--team:${panel};--possession-accent:${modernPossessionAccent(team)}"`;
  }

  function neonTeamAccent(team, fallback) {
    const primary = normalizedTeamColor(team && team.primary);
    const secondary = normalizedTeamColor(team && team.secondary);
    if (primary && hasNeonChroma(primary)) return boostNeonColor(primary, fallback);
    if (secondary && hasNeonChroma(secondary)) return boostNeonColor(secondary, fallback);
    return fallback;
  }

  function hasNeonChroma(value) {
    const color = normalizedTeamColor(value);
    if (!color) return false;
    const channels = [
      parseInt(color.slice(1,3),16),
      parseInt(color.slice(3,5),16),
      parseInt(color.slice(5,7),16)
    ];
    return Math.max(...channels) >= 24 && Math.max(...channels) - Math.min(...channels) >= 18;
  }

  function boostNeonColor(value, fallback) {
    const color = normalizedTeamColor(value);
    if (!color || !hasNeonChroma(color)) return fallback;
    const channels = [
      parseInt(color.slice(1,3),16),
      parseInt(color.slice(3,5),16),
      parseInt(color.slice(5,7),16)
    ];
    const peak = Math.max(...channels);
    const scale = peak < 208 ? 255 / peak : 1;
    const boosted = channels.map((channel) => Math.max(0, Math.min(255, Math.round(channel * scale))));
    return `#${boosted.map((channel) => channel.toString(16).padStart(2,"0")).join("").toUpperCase()}`;
  }

  function neonTeamStyle(team, side) {
    const fallback = side === "home" ? "#24D8FF" : "#FF2DAA";
    const accent = neonTeamAccent(team, fallback);
    const secondary = normalizedTeamColor(team && team.secondary);
    const secondaryAccent = secondary && hasNeonChroma(secondary) ? boostNeonColor(secondary, accent) : accent;
    return `style="--neon-team:${accent};--neon-team-rgb:${hexToRgbChannels(accent)};--neon-team-secondary:${secondaryAccent};--neon-team-secondary-rgb:${hexToRgbChannels(secondaryAccent)}"`;
  }

  function neonPackageStyle(state) {
    const home = neonTeamAccent(state && state.home, "#24D8FF");
    const visitor = neonTeamAccent(state && state.visitor, "#FF2DAA");
    const homeSecondaryRaw = normalizedTeamColor(state && state.home && state.home.secondary);
    const visitorSecondaryRaw = normalizedTeamColor(state && state.visitor && state.visitor.secondary);
    const homeSecondary = homeSecondaryRaw && hasNeonChroma(homeSecondaryRaw) ? boostNeonColor(homeSecondaryRaw, home) : home;
    const visitorSecondary = visitorSecondaryRaw && hasNeonChroma(visitorSecondaryRaw) ? boostNeonColor(visitorSecondaryRaw, visitor) : visitor;
    return `style="--neon-home:${home};--neon-home-rgb:${hexToRgbChannels(home)};--neon-home-secondary:${homeSecondary};--neon-home-secondary-rgb:${hexToRgbChannels(homeSecondary)};--neon-visitor:${visitor};--neon-visitor-rgb:${hexToRgbChannels(visitor)};--neon-visitor-secondary:${visitorSecondary};--neon-visitor-secondary-rgb:${hexToRgbChannels(visitorSecondary)}"`;
  }

  function hexToRgbChannels(value) {
    const color = normalizedTeamColor(value) || "#FFFFFF";
    return `${parseInt(color.slice(1,3),16)},${parseInt(color.slice(3,5),16)},${parseInt(color.slice(5,7),16)}`;
  }

  function neonNameClass(value) {
    const text = String(value || "").trim().toUpperCase();
    let widthUnits = 0;
    for (const char of text) {
      if ("MW".includes(char)) widthUnits += 1.45;
      else if ("IJLT1".includes(char)) widthUnits += 0.72;
      else if (char === " ") widthUnits += 0.48;
      else widthUnits += 1;
    }
    if (widthUnits >= 17.5) return "bl-neon-name-xl";
    if (widthUnits >= 13.5) return "bl-neon-name-lg";
    if (widthUnits >= 8.5) return "bl-neon-name-md";
    return "bl-neon-name-sm";
  }

  function neonFootballSvg(side) {
    return `<svg class="bl-neon-football-svg" viewBox="0 0 88 52" aria-hidden="true">
      <defs>
        <linearGradient id="neonFootball-${side}" x1="0" x2="1">
          <stop offset="0" stop-color="var(--neon-team)"/>
          <stop offset=".55" stop-color="#FFFFFF"/>
          <stop offset="1" stop-color="var(--neon-team)"/>
        </linearGradient>
      </defs>
      <path d="M8 26C18 7 65 1 80 26C66 50 20 47 8 26Z" fill="rgba(2,5,12,.92)" stroke="url(#neonFootball-${side})" stroke-width="3"/>
      <path d="M44 10V42M31 22H57M34 17L39 22M44 17V22M54 17L49 22" fill="none" stroke="#fff" stroke-width="2.4" stroke-linecap="round"/>
    </svg>`;
  }

  function neonLogoMarkup(team, side) {
    const logo = team.logo
      ? `<img src="${esc(team.logo)}" alt="">`
      : `<span>${esc(team.shortName.slice(0,1))}</span>`;
    return `<div class="bl-neon-logo-bay" data-module="${side}.logo">
      <div class="bl-neon-logo-halo" aria-hidden="true"></div>
      <div class="bl-logo" data-bind="${side}.logo">${logo}</div>
    </div>`;
  }

  function neonIdentityMarkup(team, side) {
    return `<div class="bl-neon-identity ${neonNameClass(team.name)}" data-module="${side}.identity">
      <div class="bl-neon-team-name" data-bind="${side}.name">${esc(team.name)}</div>
      <div class="bl-neon-mascot" data-bind="${side}.mascot">${esc(team.mascot)}</div>
      <div class="bl-neon-record" data-bind="${side}.record">${esc(team.record)}</div>
    </div>`;
  }

  function neonGeometryAsset(kind, side = "") {
    const sideClass = side ? ` bl-neon-geometry-${side}` : "";
    return `<div class="bl-neon-geometry bl-neon-geometry-${kind}${sideClass}" aria-hidden="true"></div>`;
  }

  function neonLogoEndcap(team, side) {
    return `<section class="bl-neon-logo-endcap bl-neon-${side}-logo" data-module="${side}.identity" ${neonTeamStyle(team,side)}>
      <div class="bl-neon-chassis-asset bl-neon-asset-logo bl-neon-asset-${side}" aria-hidden="true"></div>
      ${neonLogoMarkup(team,side)}
    </section>`;
  }

  function neonIdentityPanel(team, side) {
    return `<section class="bl-neon-identity-panel bl-neon-identity-wing bl-neon-${side}-identity" data-module="${side}.identity" ${neonTeamStyle(team,side)}>
      <div class="bl-neon-chassis-asset bl-neon-asset-wing bl-neon-asset-${side}" aria-hidden="true"></div>
      <div class="bl-neon-identity-shell" aria-hidden="true"></div>
      ${neonIdentityMarkup(team,side)}
      <div class="bl-neon-feature-strip" aria-hidden="true"><span></span><span></span><span></span></div>
    </section>`;
  }

  function neonScoreBay(team, side, possessionActive, sport) {
    const possession = sport === "football" && possessionActive
      ? `<div class="bl-neon-possession-badge bl-neon-possession-${side}" aria-label="${side} possession">${neonFootballSvg(side)}</div>`
      : "";
    return `<section class="bl-neon-score-bay bl-neon-score-crystal bl-neon-${side}-score" data-module="${side}.score" ${neonTeamStyle(team,side)}>
      <div class="bl-neon-chassis-asset bl-neon-asset-score bl-neon-asset-${side}" aria-hidden="true"></div>
      <div class="bl-neon-score-shell" aria-hidden="true"></div>
      ${genericScore(team,side)}
      ${possession}
    </section>`;
  }

  function neonCorePanel(state, sport) {
    if (sport === "baseball" || sport === "softball") {
      return `<section class="bl-neon-command-core bl-neon-command-diamond">
        <div class="bl-neon-core-shell" aria-hidden="true"></div>
        ${baseballState(state).replace('class="bl-baseball-state"','class="bl-baseball-state bl-neon-state"')}
      </section>`;
    }
    return `<section class="bl-neon-command-core">
      <div class="bl-neon-core-shell" aria-hidden="true"></div>
      ${sportState(state,sport,"bl-neon-state",false).replace(' data-module="game.state"','')}
    </section>`;
  }

  function normalizePossession(value) {
    const possession = String(value || "none").toLowerCase();
    return ["home", "visitor"].includes(possession) ? possession : "none";
  }

  function normalizeInningHalf(value) {
    const half = String(value || "TOP").trim().toUpperCase();
    return half === "BOTTOM" || half === "BOT" || half === "B" ? "BOTTOM" : "TOP";
  }

  function footballState(state, className = "", includeAuxClock = true) {
    const possession = normalizePossession(state.game.possession);
    const possessionLabel = possession === "home" ? "HOME POS" : possession === "visitor" ? "VISITOR POS" : "POSSESSION";
    return `<div class="bl-game-state ${className}" data-possession="${possession}">
      <div class="bl-period" data-bind="game.period">${esc(state.game.period)}</div>
      <div class="bl-clock" data-bind="game.clock">${esc(state.game.clock)}</div>
      ${includeAuxClock ? `<div class="bl-play-clock"><span>PLAY</span><b data-bind="game.playClock">${esc(state.game.playClock)}</b></div>` : ""}
      <div class="bl-down" data-bind="game.downDistance">${esc(state.game.downDistance)}</div>
      <div class="bl-possession bl-possession-${possession}" data-bind="game.possession"><span aria-hidden="true"></span><b>${possessionLabel}</b></div>
    </div>`;
  }

  function baseballState(state) {
    const bases = state.game.bases || [false, false, false];
    const inningHalf = normalizeInningHalf(state.game.inningHalf);
    const inningShort = inningHalf === "BOTTOM" ? "BOT" : "TOP";
    const inningArrow = inningHalf === "BOTTOM" ? "▼" : "▲";
    return `<div class="bl-baseball-state" data-inning-half="${inningHalf.toLowerCase()}">
      <div class="bl-inning"><span class="bl-inning-arrow" aria-hidden="true">${inningArrow}</span><span data-bind="game.inningHalf">${inningShort}</span> <span data-bind="game.inning">${esc(state.game.inning)}</span></div>
      <div class="bl-count">B ${esc(state.game.balls)} · S ${esc(state.game.strikes)} · O ${esc(state.game.outs)}</div>
      <div class="bl-diamond" aria-label="Base occupancy">
        <i class="${bases[1] ? "on" : ""}"></i>
        <i class="${bases[2] ? "on" : ""}"></i>
        <i class="${bases[0] ? "on" : ""}"></i>
      </div>
    </div>`;
  }

  function genericScore(team, side) {
    return `<div class="bl-score" data-module="${side}.score" data-bind="${side}.score">${esc(team.score)}</div>`;
  }

  function logoMarkup(team, side) {
    return `<div class="bl-logo" data-module="${side}.logo" data-bind="${side}.logo">${team.logo ? `<img src="${esc(team.logo)}" alt="">` : `<span>${esc(team.shortName.slice(0,1))}</span>`}</div>`;
  }

  function copyMarkup(team, side, options = {}) {
    const mascot = options.mascot === false ? "" : `<div class="bl-mascot" data-bind="${side}.mascot">${esc(team.mascot)}</div>`;
    const record = options.record === false ? "" : `<div class="bl-record" data-bind="${side}.record">${esc(team.record)}</div>`;
    return `<div class="bl-team-copy" data-module="${side}.identity"><div class="bl-team-name" data-bind="${side}.name">${esc(team.name)}</div>${mascot}${record}</div>`;
  }

  function explicitTeam(team, side, options = {}) {
    const score = `<div class="bl-score" data-module="${side}.score" data-bind="${side}.score">${esc(team.score)}</div>`;
    const logo = options.logo === false ? "" : logoMarkup(team, side);
    const copy = copyMarkup(team, side, options);
    const order = options.order || (side === "home" ? ["logo","copy","score"] : ["score","copy","logo"]);
    const parts = {logo, copy, score};
    return order.map((key)=>parts[key] || "").join("");
  }

  function basketballState(state, className = "", includeAuxClock = true) {
    return `<div class="bl-game-state bl-basketball-state ${className}" data-module="game.state">
      <div class="bl-period" data-bind="game.period">${esc(state.game.period)}</div>
      <div class="bl-clock" data-bind="game.clock">${esc(state.game.clock)}</div>
      ${includeAuxClock ? `<div class="bl-shot-clock"><span>SHOT</span><b data-bind="game.shotClock">${esc(state.game.shotClock)}</b></div>` : ""}
    </div>`;
  }

  function sportState(state, sport, className = "", includeAuxClock = true) {
    if (sport === "baseball" || sport === "softball") return baseballState(state).replace('class="bl-baseball-state"','class="bl-baseball-state" data-module="game.state"');
    if (sport === "basketball") return basketballState(state, className, includeAuxClock);
    return footballState(state, className, includeAuxClock).replace('class="bl-game-state','data-module="game.state" class="bl-game-state');
  }

  function clampPercent(value, fallback = 50) {
    const numeric = Number(value);
    return Number.isFinite(numeric) ? Math.max(0, Math.min(100, numeric)) : fallback;
  }

  function collegiateInitials(team) {
    return String(team.name || team.shortName || "TEAM")
      .replace(/[^A-Za-z0-9 ]+/g, " ")
      .trim()
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 3)
      .map((word) => word.slice(0, 1))
      .join("")
      .toUpperCase() || "T";
  }

  function collegiateLogo(team, side) {
    const logo = team.logo ? `<img src="${esc(team.logo)}" alt="">` : `<span>${esc(collegiateInitials(team))}</span>`;
    return `<div class="bl-college-clean-logo" data-module="${side}.logo" data-bind="${side}.logo">${logo}</div>`;
  }

  function collegiateTeamPanel(team, side) {
    return `<section class="bl-college-team bl-${side}" data-module="${side}.team">
      <div class="bl-college-side-label">${side === "home" ? "HOME" : "VISITOR"}</div>
      <strong class="bl-college-score" data-module="${side}.score" data-bind="${side}.score">${esc(team.score)}</strong>
      ${collegiateLogo(team, side)}
      <div class="bl-college-identity" data-module="${side}.identity">
        <span data-bind="${side}.name">${esc(team.shortName || team.name)}</span>
        <small data-bind="${side}.mascot">${esc(team.mascot)}</small>
      </div>
    </section>`;
  }

  function collegiateVenueName(state) {
    const school = String(state.home.name || state.home.shortName || "HOME").trim();
    const mascot = String(state.home.mascot || "").trim();
    return `${[school, mascot].filter(Boolean).join(" ")} STADIUM`;
  }

  function collegiateStageSide(team, side) {
    return `<div class="bl-college-stage-side bl-${side}">
      ${collegiateLogo(team, side)}
      <strong>${esc(team.shortName || team.name)}</strong>
      <span>${esc(team.mascot)}</span>
    </div>`;
  }

  function collegiateStage(state) {
    return `<section class="bl-college-stage" data-module="video.board">
      <div class="bl-college-stage-field" aria-hidden="true"></div>
      ${collegiateStageSide(state.visitor, "visitor")}
      <div class="bl-college-vs">VS</div>
      ${collegiateStageSide(state.home, "home")}
    </section>`;
  }

  function collegiateThemeVars(state) {
    const visitor = normalizedTeamColor(state.visitor && state.visitor.primary) || "#064624";
    const home = normalizedTeamColor(state.home && state.home.primary) || "#0A2342";
    return `style="--visitor-primary:${visitor};--home-primary:${home}"`;
  }

  function collegiateField(state) {
    const field = state.game.field || {};
    const ballPct = clampPercent(field.ballPct, 50);
    const drivePct = clampPercent(field.driveStartPct, ballPct);
    const firstPct = clampPercent(field.firstDownPct, ballPct);
    const direction = String(field.direction || state.game.fieldDirection || "right").toLowerCase() === "left" ? "left" : "right";
    const possession = String(field.possession || state.game.possession || "home").toLowerCase();
    const visible = field.visible !== false;
    const ballSpot = visible ? (field.ballSpot || state.game.ballSpot || "-") : "-";
    const driveStart = field.driveStart || state.game.driveStart || "-";
    const firstDownSpot = field.firstDownSpot || state.game.firstDownSpot || "-";
    const downDistance = field.downDistance || state.game.downDistance || "-";
    const hasFirstDown = firstDownSpot !== "-";
    const yardNumbers = ["10","20","30","40","50","40","30","20","10"].map((yard) => `<span>${yard}</span>`).join("");
    return `<section class="bl-college-field" data-module="game.field" data-direction="${esc(direction)}" data-possession="${esc(possession)}" data-has-drive-start="${driveStart !== "-" ? "true" : "false"}" data-has-first-down="${hasFirstDown ? "true" : "false"}" data-field-visible="${visible ? "true" : "false"}" style="--ball-x:${ballPct}%;--drive-x:${drivePct}%;--first-x:${firstPct}%">
      <div class="bl-college-field-grid" aria-hidden="true">
        <div class="bl-college-yard-numbers">${yardNumbers}</div>
        <i class="bl-college-drive-start"></i>
        <i class="bl-college-line-scrimmage"></i>
        <i class="bl-college-first-down"></i>
        <i class="bl-college-ball-marker"><span></span></i>
        <b class="bl-college-direction-arrow"></b>
      </div>
      <div class="bl-college-field-meta">
        <span><small>Drive</small><b data-bind="game.driveStart">${esc(driveStart)}</b></span>
        <span><small>Down</small><b data-bind="game.downDistance">${esc(downDistance)}</b></span>
        <span><small>Ball</small><b data-bind="game.ballSpot">${esc(ballSpot)}</b></span>
        <span><small>Line</small><b data-bind="game.firstDownSpot">${esc(firstDownSpot)}</b></span>
      </div>
    </section>`;
  }

  function collegiateFootballScorebug(state, sport) {
    return `<div class="bl-scorebug bl-collegiate bl-collegiate-tech bl-sport-${sport}" data-possession="${esc(state.game.possession || "home")}" ${collegiateThemeVars(state)}>
      <div class="bl-college-cabinet" aria-hidden="true"></div>
      <div class="bl-college-live-strip"><b>LIVE</b><span class="bl-college-ticker-copy">${esc(state.ticker.text || "CSRN LIVE")}</span><em>CSRN</em></div>
      <header class="bl-college-venue"><i></i><strong>${esc(collegiateVenueName(state))}</strong><i></i></header>
      <main class="bl-college-main-display">${collegiateTeamPanel(state.visitor, "visitor")}${collegiateStage(state)}${collegiateTeamPanel(state.home, "home")}</main>
      <section class="bl-college-control-bank" data-module="game.state">
        <div class="bl-college-clock-row"><span>Q<span data-bind="game.period">${esc(state.game.period)}</span></span><strong data-bind="game.clock">${esc(state.game.clock)}</strong></div>
        ${collegiateField(state)}
      </section>
    </div>`;
  }


  function baseballRoleState(state) {
    const half = normalizeInningHalf(state.game.inningHalf);
    const battingSide = half === "TOP" ? "visitor" : "home";
    const fieldingSide = battingSide === "home" ? "visitor" : "home";
    return Object.freeze({half, battingSide, fieldingSide});
  }

  function baseballContextMarkup(state, side) {
    const roles = baseballRoleState(state);
    if (side === roles.battingSide) {
      const position = String(state.game.batterPosition || "").trim();
      const batter = String(state.game.batterName || "").trim();
      const detail = [position, batter].filter(Boolean).join(" ");
      return `<div class="bl-baseball-context bl-context-at-bat" data-role="at-bat"><b>AB:</b> <span data-bind="game.batterName">${esc(detail || "BATTER")}</span></div>`;
    }
    if (side === roles.fieldingSide) {
      const pitcher = String(state.game.pitcherName || "").trim();
      return `<div class="bl-baseball-context bl-context-pitcher" data-role="pitcher"><b>P:</b> <span data-bind="game.pitcherName">${esc(pitcher || "PITCHER")}</span></div>`;
    }
    return "";
  }

  function modernBaseballTeam(state, team, side) {
    const label = side === "home" ? "HOME" : "VISITOR";
    return `<section class="bl-baseball-team bl-${side}" data-module="${side}.team" data-team-side="${side}" ${modernTeamStyle(team)}>
      <div class="bl-modern-run-cell" data-module="${side}.score">
        <span class="bl-run-label">${label}</span>
        <strong class="bl-score" data-bind="${side}.score">${esc(team.score)}</strong>
      </div>
      ${logoMarkup(team,side)}
      <div class="bl-team-copy" data-module="${side}.identity">
        <div class="bl-team-name" data-bind="${side}.name">${esc(team.name)}</div>
        <div class="bl-mascot" data-bind="${side}.mascot">${esc(team.mascot)}</div>
      </div>
      <div class="bl-modern-baseball-role" data-module="${side}.role">${baseballContextMarkup(state,side)}</div>
    </section>`;
  }

  function modernBaseballScore(state) {
    return `<div class="bl-scorebug bl-baseball-board bl-modern bl-modern-baseball bl-sport-${state.sport}" data-scorebug-family="modern" data-inning-half="${normalizeInningHalf(state.game.inningHalf).toLowerCase()}">
      ${modernBaseballTeam(state,state.home,"home")}
      ${modernBaseballTeam(state,state.visitor,"visitor")}
      ${baseballState(state).replace('class="bl-baseball-state"','class="bl-baseball-state" data-module="game.state"')}
    </div>`;
  }

  function baseballLineScore(state, family) {
    return `<div class="bl-scorebug bl-baseball-board bl-${family} bl-sport-${state.sport}" data-scorebug-family="${family}">
      <section class="bl-baseball-team bl-home" data-module="home.team">${explicitTeam(state.home,"home",{order:["logo","copy","score"],record:false})}</section>
      <section class="bl-baseball-team bl-visitor" data-module="visitor.team">${explicitTeam(state.visitor,"visitor",{order:["score","copy","logo"],record:false})}</section>
      ${baseballState(state).replace('class="bl-baseball-state"','class="bl-baseball-state" data-module="game.state"')}
    </div>`;
  }


  function pressLogo(team, side) {
    return `<div class="bl-logo bl-press-logo" data-module="${side}.logo" data-bind="${side}.logo">${team.logo ? `<img src="${esc(team.logo)}" alt="">` : `<span>${esc(team.shortName.slice(0,1))}</span>`}</div>`;
  }

  function pressTeamIdentity(team, side, options = {}) {
    const record = options.record === false ? "" : `<span class="bl-record" data-bind="${side}.record">${esc(team.record)}</span>`;
    const heading = `<div class="bl-press-meta"><span class="bl-press-side-label">${side === "home" ? "HOME" : "VISITOR"}</span>${record}</div>`;
    const copy = `<div class="bl-team-copy">
      ${heading}
      <div class="bl-team-name" data-bind="${side}.name">${esc(team.name)}</div>
      <div class="bl-mascot" data-bind="${side}.mascot">${esc(team.mascot)}</div>
    </div>`;
    const logo = pressLogo(team,side);
    return `<div class="bl-press-identity bl-press-identity-${side}" data-module="${side}.identity">
      ${side === "visitor" ? `${copy}${logo}` : `${logo}${copy}`}
    </div>`;
  }


  const HERITAGE_PRESS_ASSETS = Object.freeze({
    pitcher: "/static/heritage/press-pitcher-1920s.png",
    batter: "/static/heritage/press-batter-1920s.png",
    sponsorTruck: "/static/heritage/press-sponsor-truck.png",
    playerPlaceholder: "/static/heritage/press-player-placeholder.png"
  });

  const PRESS_WIRE_TIMERS = new WeakMap();

  function pressRoleIcon(kind) {
    const source = kind === "pitcher" ? HERITAGE_PRESS_ASSETS.pitcher : HERITAGE_PRESS_ASSETS.batter;
    return `<span class="bl-press-role-icon bl-press-role-${kind}"><img src="${source}" alt="" aria-hidden="true"></span>`;
  }

  function pressRoleDetail(kind, name, position = "") {
    const detail = [position, name].filter(Boolean).join(" ");
    return `<span class="bl-press-role" data-role="${kind}">${pressRoleIcon(kind)}<b>${esc(detail)}</b></span>`;
  }

  function heritagePlayerStats(state, sport) {
    const source = state.player?.stats?.[sport];
    if (Array.isArray(source) && source.length) {
      return source.slice(0, 4).map((item) => ({
        label: esc(item?.label ?? ""),
        value: esc(item?.value ?? "")
      }));
    }

    const fallbacks = {
      football: [["COMP/ATT","18/24"],["PASS YDS","244"],["PASS TD","2"],["INT","0"]],
      basketball: [["PTS","24"],["REB","8"],["AST","6"],["STL","3"]],
      baseball: [["H","3"],["RBI","2"],["R","2"],["HR","1"]],
      softball: [["H","3"],["RBI","3"],["R","2"],["SB","1"]]
    };

    return (fallbacks[sport] || fallbacks.football).map(([label,value]) => ({label,value}));
  }

  function pressPlayerCard(state, sport) {
    const stats = heritagePlayerStats(state, sport);
    const headshot = state.player?.headshot || HERITAGE_PRESS_ASSETS.playerPlaceholder;
    return `<article class="bl-player-card bl-family-press bl-press-gum-card bl-sport-${sport}">
      <div class="bl-press-card-banner">★★★★★ SPORTS EXTRA ★★★★★<span class="bl-sr-only">PLAYER OF THE GAME</span></div>
      <div class="bl-press-card-main">
        <img class="bl-press-card-photo" src="${esc(headshot)}" alt="">
        <div class="bl-press-card-copy">
          <h2>${esc(state.player.name)}</h2>
          <p>${esc(state.player.position)} · No. ${esc(state.player.number)}</p>
          <small>${esc(state.home.name)} ${esc(state.home.mascot)}</small>
        </div>
      </div>
      <div class="bl-press-card-tonight">TONIGHT</div>
      <div class="bl-press-card-stats">${stats.map((item) => `<span><b>${item.value}</b><small>${item.label}</small></span>`).join("")}</div>
    </article>`;
  }

  function splitPressWireStories(value) {
    const stories = String(value || "")
      .split(/\s*(?:·|•|\||\n)\s*/g)
      .map((story) => story.trim())
      .filter(Boolean);
    return stories.length ? stories : ["SPORTS WIRE"];
  }

  function clearPressWire(root) {
    const timer = PRESS_WIRE_TIMERS.get(root);
    if (timer) clearTimeout(timer);
    PRESS_WIRE_TIMERS.delete(root);
  }

  function hydratePressWire(root, options = {}) {
    clearPressWire(root);
    const wire = root?.querySelector?.(".bl-press-wire");
    if (!wire) return;

    let stories = [];
    try {
      stories = JSON.parse(wire.dataset.stories || "[]");
    } catch (_) {
      stories = [];
    }
    if (!Array.isArray(stories) || !stories.length) stories = ["SPORTS WIRE"];

    const copy = wire.querySelector(".bl-wire-copy");
    if (!copy) return;

    const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches;
    let storyIndex = 0;
    let characterIndex = 0;

    wire.dataset.wireReady = "true";
    wire.dataset.wireStories = String(stories.length);

    if (reduced || options.staticWire) {
      copy.textContent = stories[0];
      wire.dataset.wirePhase = "hold";
      return;
    }

    const schedule = (fn, delay) => {
      const timer = setTimeout(fn, delay);
      PRESS_WIRE_TIMERS.set(root, timer);
    };

    const typeNext = () => {
      const story = stories[storyIndex];
      wire.dataset.wirePhase = "type";
      wire.classList.remove("is-advancing");
      copy.textContent = story.slice(0, characterIndex + 1);
      characterIndex += 1;

      if (characterIndex < story.length) {
        const current = story[characterIndex - 1] || "";
        const punctuationPause = /[.,:;!?]/.test(current) ? 145 : 0;
        const mechanicalVariation = (current.charCodeAt(0) || 0) % 4 * 9;
        schedule(typeNext, 48 + mechanicalVariation + punctuationPause);
        return;
      }

      wire.dataset.wirePhase = "hold";
      schedule(() => {
        wire.dataset.wirePhase = "advance";
        wire.classList.add("is-advancing");
        schedule(() => {
          storyIndex = (storyIndex + 1) % stories.length;
          characterIndex = 0;
          copy.textContent = "";
          typeNext();
        }, 460);
      }, 1050);
    };

    typeNext();
  }

  function pressFootballPanel(state) {
    const possession = normalizePossession(state.game.possession);
    const possessionTeam = possession === "home" ? state.home.name : possession === "visitor" ? state.visitor.name : "NO POSSESSION";
    return `<div class="bl-scorebug bl-press bl-press-football bl-sport-football" data-possession="${possession}">
      <div class="bl-press-section-line bl-press-masthead">GAME NIGHT EDITION</div>
      <section class="bl-press-row bl-home" data-module="home.team">${pressTeamIdentity(state.home,"home")}<strong class="bl-score" data-bind="home.score">${esc(state.home.score)}</strong></section>
      <section class="bl-press-row bl-visitor" data-module="visitor.team"><strong class="bl-score" data-bind="visitor.score">${esc(state.visitor.score)}</strong>${pressTeamIdentity(state.visitor,"visitor")}</section>
      <aside class="bl-press-state-column" data-module="game.state">
        <div class="bl-press-clock"><span>QTR</span><b>${esc(state.game.period.replace(/^Q/i,""))}</b><strong>${esc(state.game.clock)}</strong></div>
        <div class="bl-press-down">${esc(state.game.downDistance)}</div>
        <div class="bl-press-possession" data-possession="${possession}"><span aria-hidden="true">◖</span><b>${esc(possessionTeam)} BALL</b></div>
      </aside>
    </div>`;
  }

  function pressBasketballPanel(state) {
    const possession = normalizePossession(state.game.possession);
    return `<div class="bl-scorebug bl-press bl-press-basketball bl-sport-basketball" data-possession="${possession}">
      <div class="bl-press-section-line bl-press-masthead">COURTSIDE EDITION</div>
      <section class="bl-press-row bl-home" data-module="home.team">${pressTeamIdentity(state.home,"home")}<strong class="bl-score" data-bind="home.score">${esc(state.home.score)}</strong></section>
      <section class="bl-press-row bl-visitor" data-module="visitor.team"><strong class="bl-score" data-bind="visitor.score">${esc(state.visitor.score)}</strong>${pressTeamIdentity(state.visitor,"visitor")}</section>
      <aside class="bl-press-state-column" data-module="game.state">
        <div class="bl-press-clock"><span>QTR</span><b>${esc(state.game.period.replace(/^Q/i,""))}</b><strong>${esc(state.game.clock)}</strong></div>
        <div class="bl-press-down">SHOT ${esc(state.game.shotClock)}</div>
        <div class="bl-press-fouls"><strong>FOULS</strong><span>HOME <b>${esc(state.game.homeFouls)}</b></span><span>VIS <b>${esc(state.game.visitorFouls)}</b></span></div>
      </aside>
    </div>`;
  }

  function pressDiamondPanel(state, sport) {
    const bases = state.game.bases || [false,false,false];
    const half = normalizeInningHalf(state.game.inningHalf);
    const inning = `${half === "BOTTOM" ? "BOTTOM" : "TOP"} ${esc(state.game.inning)}`;
    const homeRole = half === "TOP"
      ? pressRoleDetail("pitcher", state.game.pitcherName)
      : pressRoleDetail("batter", state.game.batterName, state.game.batterPosition);
    const visitorRole = half === "TOP"
      ? pressRoleDetail("batter", state.game.batterName, state.game.batterPosition)
      : pressRoleDetail("pitcher", state.game.pitcherName);

    return `<div class="bl-scorebug bl-press bl-press-boxscore bl-press-diamond bl-sport-${sport}" data-inning-half="${half.toLowerCase()}">
      <div class="bl-press-section-line bl-press-masthead">SPORTS PAGE · ${sport.toUpperCase()}</div>
      <section class="bl-press-row bl-home" data-module="home.team">
        ${pressTeamIdentity(state.home,"home")}
        ${homeRole}
        <strong class="bl-score" data-bind="home.score">${esc(state.home.score)}</strong>
      </section>
      <section class="bl-press-row bl-visitor" data-module="visitor.team">
        <strong class="bl-score" data-bind="visitor.score">${esc(state.visitor.score)}</strong>
        ${visitorRole}
        ${pressTeamIdentity(state.visitor,"visitor")}
      </section>
      <aside class="bl-press-diamond-state" data-module="game.state">
        <div class="bl-press-inning">${inning}</div>
        <div class="bl-press-diamond-bases" aria-label="Base occupancy"><i class="${bases[1]?"on":""}"></i><i class="${bases[2]?"on":""}"></i><i class="${bases[0]?"on":""}"></i></div>
        <div class="bl-press-count"><span>BALLS <b>${esc(state.game.balls)}</b></span><span>STRIKES <b>${esc(state.game.strikes)}</b></span><span>OUTS <b>${esc(state.game.outs)}</b></span></div>
      </aside>
    </div>`;
  }

  const SCOREBUG_RENDERERS = Object.freeze({
    modern(state, sport) {
      if (sport === "baseball" || sport === "softball") return modernBaseballScore(state);
      const possession = sport === "football" ? normalizePossession(state.game.possession) : "none";
      return `<div class="bl-scorebug bl-modern bl-sport-${sport}" data-possession="${possession}">
        <section class="bl-team bl-home" ${modernTeamStyle(state.home)}>${explicitTeam(state.home,"home")}</section>
        ${sportState(state,sport)}
        <section class="bl-team bl-visitor" ${modernTeamStyle(state.visitor)}>${explicitTeam(state.visitor,"visitor")}</section>
      </div>`;
    },

    pixel(state, sport) {
      if (sport === "baseball" || sport === "softball") {
        return `<div class="bl-scorebug bl-pixel bl-pixel-diamond bl-sport-${sport}">
          <div class="bl-pixel-title">8-BIT ${sport.toUpperCase()}</div>
          <section class="bl-team bl-home">${explicitTeam(state.home,"home",{record:false})}</section>
          ${baseballState(state).replace('class="bl-baseball-state"','class="bl-baseball-state" data-module="game.state"')}
          <section class="bl-team bl-visitor">${explicitTeam(state.visitor,"visitor",{record:false})}</section>
          <div class="bl-pixel-sport-rail" aria-hidden="true"></div>
        </div>`;
      }
      return `<div class="bl-scorebug bl-pixel bl-sport-${sport}">
        <div class="bl-pixel-title">8-BIT GAMEDAY</div>
        <section class="bl-team bl-home">${explicitTeam(state.home,"home")}</section>
        ${sportState(state,sport,"bl-pixel-state")}
        <section class="bl-team bl-visitor">${explicitTeam(state.visitor,"visitor")}</section>
        <div class="bl-pixel-sport-rail" aria-hidden="true"></div>
      </div>`;
    },

    minimal(state, sport) {
      const stateMarkup = sportState(state,sport,"bl-minimal-state");
      return `<div class="bl-scorebug bl-minimal bl-sport-${sport}">
        <div class="bl-minimal-teams" data-module="teams">
          <div><span data-bind="home.name">${esc(state.home.name)}</span>${genericScore(state.home,"home")}</div>
          <div><span data-bind="visitor.name">${esc(state.visitor.name)}</span>${genericScore(state.visitor,"visitor")}</div>
        </div>${stateMarkup}
      </div>`;
    },

    press(state, sport) {
      if (sport === "football") return pressFootballPanel(state);
      if (sport === "basketball") return pressBasketballPanel(state);
      return pressDiamondPanel(state,sport);
    },

    stadium(state, sport) {
      if (sport === "baseball" || sport === "softball") {
        return `<div class="bl-scorebug bl-stadium bl-stadium-baseball bl-sport-${sport}">
          <div class="bl-stadium-title">BALLPARK SCOREBOARD</div>
          <div class="bl-stadium-label bl-visitor-label">VISITOR</div><div class="bl-stadium-label bl-home-label">HOME</div>
          ${genericScore(state.visitor,"visitor")}${genericScore(state.home,"home")}
          ${baseballState(state).replace('class="bl-baseball-state"','class="bl-baseball-state" data-module="game.state"')}
          <div class="bl-stadium-name" data-module="visitor.identity" data-bind="visitor.name">${esc(state.visitor.name)}</div>
          <div class="bl-stadium-name" data-module="home.identity" data-bind="home.name">${esc(state.home.name)}</div>
        </div>`;
      }
      return `<div class="bl-scorebug bl-stadium bl-sport-${sport}">
        <div class="bl-stadium-title">FRIDAY NIGHT SCOREBOARD</div>
        <div class="bl-stadium-label bl-visitor-label">GUEST</div><div class="bl-stadium-label bl-home-label">HOME</div>
        ${genericScore(state.visitor,"visitor")}
        <div class="bl-stadium-clock" data-module="game.clock"><small>TIME</small><strong data-bind="game.clock">${esc(state.game.clock)}</strong></div>
        ${genericScore(state.home,"home")}
        <div class="bl-stadium-name" data-module="visitor.identity" data-bind="visitor.name">${esc(state.visitor.name)}</div>
        <div class="bl-stadium-detail" data-module="game.state"><span>${esc(state.game.period)}</span><span>${esc(state.game.downDistance)}</span></div>
        <div class="bl-stadium-name" data-module="home.identity" data-bind="home.name">${esc(state.home.name)}</div>
      </div>`;
    },

    neon(state, sport) {
      const possession = normalizePossession(state.game.possession);
      const homePossession = possession === "home";
      const visitorPossession = possession === "visitor";
      const diamond = sport === "baseball" || sport === "softball";
      return `<div class="bl-scorebug bl-neon-five-zone bl-neon-true-chassis ${diamond ? "bl-neon-five-zone-diamond" : "bl-neon-five-zone-field"} bl-sport-${sport}" data-neon-package="sports-network" data-neon-compositor="true-chassis-v1" data-neon-convergence="approved-v2" data-neon-renderer="approved-concept-v1" data-possession="${possession}" data-inning-half="${diamond ? normalizeInningHalf(state.game.inningHalf).toLowerCase() : ""}" ${neonPackageStyle(state)}>
        <div class="bl-neon-backplane" aria-hidden="true"></div>
        <div class="bl-neon-chassis-rail bl-neon-chassis-rail-top" aria-hidden="true"></div>
        <div class="bl-neon-chassis-rail bl-neon-chassis-rail-bottom" aria-hidden="true"></div>
        ${neonLogoEndcap(state.home,"home")}
        ${neonIdentityPanel(state.home,"home")}
        ${neonScoreBay(state.home,"home",homePossession,sport)}
        ${neonCorePanel(state,sport)}
        ${neonScoreBay(state.visitor,"visitor",visitorPossession,sport)}
        ${neonIdentityPanel(state.visitor,"visitor")}
        ${neonLogoEndcap(state.visitor,"visitor")}
      </div>`;
    },

    collegiate(state, sport) {
      if (sport === "baseball" || sport === "softball") return baseballLineScore(state,"collegiate");
      if (sport === "football") return collegiateFootballScorebug(state, sport);
      return `<div class="bl-scorebug bl-collegiate bl-sport-${sport}">
        <section class="bl-college-team bl-home">${explicitTeam(state.home,"home",{order:["logo","copy"],record:true})}</section>
        ${genericScore(state.home,"home")}${sportState(state,sport,"bl-college-state")}${genericScore(state.visitor,"visitor")}
        <section class="bl-college-team bl-visitor">${explicitTeam(state.visitor,"visitor",{order:["copy","logo"],record:true})}</section>
      </div>`;
    },

    classic(state, sport) {
      if (sport === "baseball" || sport === "softball") return baseballLineScore(state,"classic");
      return `<div class="bl-scorebug bl-classic bl-sport-${sport}">
        <section>${explicitTeam(state.home,"home",{order:["logo","copy"],record:false})}</section>
        ${genericScore(state.home,"home")}${sportState(state,sport,"bl-classic-state")}${genericScore(state.visitor,"visitor")}
        <section>${explicitTeam(state.visitor,"visitor",{order:["copy","logo"],record:false})}</section>
      </div>`;
    }
  });

  function baseComponentData(state) {
    return {
      ticker: esc(state.ticker.text),
      playerNumber: esc(state.player.number),
      playerName: esc(state.player.name),
      playerPosition: esc(state.player.position),
      playerDetail: esc(state.player.detail),
      playerHeadshot: esc(state.player.headshot || ""),
      highlightTitle: esc(state.highlight.title),
      highlightDetail: esc(state.highlight.detail),
      sponsorName: esc(state.sponsor.name),
      sponsorLine: esc(state.sponsor.line),
      sponsorLogo: esc(state.sponsor.logo || ""),
      captionSpeaker: esc(state.captions.speaker),
      captionText: esc(state.captions.text)
    };
  }

  function familyRenderers(family) {
    const classes = `bl-family-${family}`;
    const data = (state) => baseComponentData(state);

    const standard = {
      ticker(state) {
        const d = data(state);
        return `<div class="bl-ticker ${classes}"><span>${d.ticker}</span></div>`;
      },
      playerCard(state) {
        const d = data(state);
        return `<div class="bl-player-card ${classes}">
          <div class="bl-eyebrow">PLAYER SPOTLIGHT</div>
          <div class="bl-player-number">#${d.playerNumber}</div>
          <div class="bl-player-name">${d.playerName}</div>
          <div class="bl-player-detail">${d.playerPosition} · ${d.playerDetail}</div>
        </div>`;
      },
      highlightVideo(state) {
        const d = data(state);
        return `<div class="bl-highlight ${classes}">
          <div class="bl-video-placeholder">VIDEO</div>
          <div><strong>${d.highlightTitle}</strong><span>${d.highlightDetail}</span></div>
        </div>`;
      },
      sponsor(state) {
        const d = data(state);
        return `<div class="bl-sponsor ${classes}"><strong>${d.sponsorName}</strong><span>${d.sponsorLine}</span></div>`;
      },
      captions(state) {
        const d = data(state);
        return `<div class="bl-captions ${classes}"><strong>${d.captionSpeaker}</strong><span>${d.captionText}</span></div>`;
      }
    };

    if (family === "pixel") {
      return {
        ticker(state){const d=data(state);return `<div class="bl-ticker ${classes}"><span>▶ ${d.ticker}</span></div>`;},
        playerCard(state){const d=data(state);return `<div class="bl-player-card ${classes}"><div class="bl-pixel-window-title">PLAYER DATA</div><div class="bl-pixel-player-grid"><b>#${d.playerNumber}</b><strong>${d.playerName}</strong><span>${d.playerPosition}</span><small>${d.playerDetail}</small></div></div>`;},
        highlightVideo(state){const d=data(state);return `<div class="bl-highlight ${classes}"><div class="bl-pixel-window-title">${d.highlightTitle}</div><div class="bl-video-placeholder">REPLAY</div><p>${d.highlightDetail}</p></div>`;},
        sponsor(state){const d=data(state);return `<div class="bl-sponsor ${classes}"><div class="bl-pixel-window-title">POWER-UP PARTNER</div><strong>${d.sponsorName}</strong><span>${d.sponsorLine}</span></div>`;},
        captions(state){const d=data(state);return `<div class="bl-captions ${classes}"><strong>[${d.captionSpeaker}]</strong><span>${d.captionText}</span></div>`;}
      };
    }
    if (family === "press") {
      return {
        ticker(state){
          const stories = splitPressWireStories(state.ticker.text);
          const encoded = esc(JSON.stringify(stories));
          return `<div class="bl-ticker ${classes} bl-press-wire" data-stories="${encoded}">
            <span class="bl-wire-kicker">SPORTS WIRE</span>
            <span class="bl-wire-copy" aria-live="polite"></span>
            <span class="bl-wire-cursor" aria-hidden="true">▌</span>
          </div>`;
        },
        playerCard(state, sport){return pressPlayerCard(state, sport);},
        highlightVideo(state){const d=data(state);return `<figure class="bl-highlight ${classes} bl-press-feature"><div class="bl-video-placeholder">PHOTO / VIDEO</div><figcaption><small>SPORTS EXTRA</small><strong>${d.highlightTitle}</strong><span>${d.highlightDetail}</span></figcaption></figure>`;},
        sponsor(state){const d=data(state);return `<aside class="bl-sponsor ${classes} bl-press-advert">
          <small class="bl-press-advert-label">ADVERTISEMENT</small>
          <img class="bl-press-advert-art" src="${HERITAGE_PRESS_ASSETS.sponsorTruck}" alt="">
          <div class="bl-press-advert-copy"><strong>${d.sponsorName}</strong><i></i><span>${d.sponsorLine}</span><i></i><small>SUPPORT LOCAL · INVEST LOCAL · CHEER LOCAL</small></div>
        </aside>`;},
        captions(state){const d=data(state);return `<blockquote class="bl-captions ${classes}"><span>“${d.captionText}”</span><cite>— ${d.captionSpeaker}</cite></blockquote>`;}
      };
    }
    if (family === "minimal") {
      return {
        ticker(state){const d=data(state);return `<div class="bl-ticker ${classes}"><span>${d.ticker}</span></div>`;},
        playerCard(){return "";},
        highlightVideo(state){const d=data(state);return `<div class="bl-highlight ${classes}"><div class="bl-video-placeholder"></div><div><strong>${d.highlightTitle}</strong><span>${d.highlightDetail}</span></div></div>`;},
        sponsor(state){const d=data(state);return `<div class="bl-sponsor ${classes}"><strong>${d.sponsorName}</strong></div>`;},
        captions(state){const d=data(state);return `<div class="bl-captions ${classes}"><span>${d.captionText}</span></div>`;}
      };
    }
    if (family === "stadium") {
      return {
        ticker(state){const d=data(state);return `<div class="bl-ticker ${classes}"><span>MESSAGE BOARD · ${d.ticker}</span></div>`;},
        playerCard(state){const d=data(state);return `<div class="bl-player-card ${classes}"><div class="bl-stadium-panel-label">PLAYER</div><div class="bl-led-number">#${d.playerNumber}</div><strong>${d.playerName}</strong><span>${d.playerPosition} · ${d.playerDetail}</span></div>`;},
        highlightVideo(state){const d=data(state);return `<div class="bl-highlight ${classes}"><div class="bl-stadium-panel-label">INSTANT REPLAY</div><div class="bl-video-placeholder">VIDEO BOARD</div><span>${d.highlightDetail}</span></div>`;},
        sponsor(state){const d=data(state);return `<div class="bl-sponsor ${classes}"><div class="bl-stadium-panel-label">PRESENTED BY</div><strong>${d.sponsorName}</strong><span>${d.sponsorLine}</span></div>`;},
        captions(state){const d=data(state);return `<div class="bl-captions ${classes}"><strong>${d.captionSpeaker}</strong><span>${d.captionText}</span></div>`;}
      };
    }
    if (family === "neon") {
      return {
        ticker(state){
          const d=data(state);
          return `<div class="bl-ticker ${classes} bl-neon-native-ticker" data-neon-surface="dark-system" ${neonPackageStyle(state)}>
            <div class="bl-neon-component-shell" aria-hidden="true"></div>
            <span class="bl-neon-live-capsule"><i aria-hidden="true"></i>LIVE</span>
            <span class="bl-neon-ticker-divider" aria-hidden="true"></span>
            <span class="bl-neon-ticker-copy">${d.ticker}</span>
            <span class="bl-neon-ticker-pulses" aria-hidden="true"><i></i><i></i><i></i></span>
          </div>`;
        },
        playerCard(state,sport){
          const d=data(state);
          const stats = heritagePlayerStats(state,sport).map((item)=>`<span><small>${esc(item.label)}</small><b>${esc(item.value)}</b></span>`).join("");
          const portrait = d.playerHeadshot
            ? `<img src="${d.playerHeadshot}" alt="${d.playerName}">`
            : `<div class="bl-neon-player-silhouette" aria-hidden="true"></div>`;
          return `<article class="bl-player-card ${classes} bl-neon-native-card bl-neon-native-player" data-neon-surface="dark-system" ${neonPackageStyle(state)}>
            <div class="bl-neon-component-shell" aria-hidden="true"></div>
            <div class="bl-neon-card-kicker">PLAYER PROFILE</div>
            <div class="bl-neon-portrait-bay">${portrait}<div class="bl-neon-number-node">#${d.playerNumber}</div></div>
            <div class="bl-neon-player-copy"><strong>${d.playerName}</strong><span>${d.playerPosition} // ${d.playerDetail}</span></div>
            <div class="bl-neon-stat-grid">${stats}</div>
          </article>`;
        },
        highlightVideo(state){
          const d=data(state);
          return `<article class="bl-highlight ${classes} bl-neon-native-card bl-neon-native-highlight" data-neon-surface="dark-system" ${neonPackageStyle(state)}>
            <div class="bl-neon-component-shell" aria-hidden="true"></div>
            <div class="bl-neon-video-bay"><div class="bl-neon-video-reticle" aria-hidden="true"></div><span>LIVE FEED</span></div>
            <div class="bl-neon-highlight-copy"><small>HIGHLIGHT NODE</small><strong>${d.highlightTitle}</strong><span>${d.highlightDetail}</span></div>
          </article>`;
        },
        sponsor(state){
          const d=data(state);
          const sponsorMark = d.sponsorLogo
            ? `<img class="bl-neon-sponsor-logo" src="${d.sponsorLogo}" alt="${d.sponsorName}">`
            : `<strong>${d.sponsorName}</strong>`;
          return `<aside class="bl-sponsor ${classes} bl-neon-native-card bl-neon-native-sponsor" data-neon-surface="dark-system" ${neonPackageStyle(state)}>
            <div class="bl-neon-component-shell" aria-hidden="true"></div>
            <div class="bl-neon-card-kicker">PRESENTED BY</div>
            ${sponsorMark}<span>${d.sponsorLine}</span><i aria-hidden="true"></i>
          </aside>`;
        },
        captions(state){
          const d=data(state);
          return `<div class="bl-captions ${classes} bl-neon-native-captions" data-neon-surface="dark-system" ${neonPackageStyle(state)}>
            <div class="bl-neon-component-shell" aria-hidden="true"></div>
            <strong>${d.captionSpeaker}</strong><span>${d.captionText}</span>
          </div>`;
        }
      };
    }
    if (family === "collegiate") {
      return {
        ...standard,
        playerCard(state){const d=data(state);return `<div class="bl-player-card ${classes}"><div class="bl-college-banner">STUDENT-ATHLETE SPOTLIGHT</div><div class="bl-player-number">#${d.playerNumber}</div><div class="bl-player-name">${d.playerName}</div><div class="bl-player-detail">${d.playerPosition} · ${d.playerDetail}</div></div>`;}
      };
    }
    if (family === "classic") {
      return {
        ...standard,
        playerCard(state){const d=data(state);return `<div class="bl-player-card ${classes}"><div class="bl-classic-label">PLAYER</div><div class="bl-player-number">#${d.playerNumber}</div><div class="bl-player-name">${d.playerName}</div><div class="bl-player-detail">${d.playerPosition} · ${d.playerDetail}</div></div>`;}
      };
    }
    return standard;
  }

  const PACKAGE_COMPONENT_RENDERERS = Object.freeze({
    modern: familyRenderers("modern"),
    pixel: familyRenderers("pixel"),
    minimal: familyRenderers("minimal"),
    press: familyRenderers("press"),
    stadium: familyRenderers("stadium"),
    neon: familyRenderers("neon"),
    collegiate: familyRenderers("collegiate"),
    classic: familyRenderers("classic")
  });

  function componentFrame(component, manifest, state, sport) {
    if (component === "scorebug") {
      const renderer = SCOREBUG_RENDERERS[manifest.scorebugRenderer];
      if (!renderer) throw new Error(`Missing scorebug renderer: ${manifest.scorebugRenderer}`);
      return renderer(state, sport);
    }

    const family = PACKAGE_COMPONENT_RENDERERS[manifest.componentRendererFamily];
    if (!family) {
      throw new Error(`Missing component renderer family: ${manifest.componentRendererFamily}`);
    }
    const renderer = family[component];
    if (typeof renderer !== "function") {
      throw new Error(`${manifest.id} does not define ${component} markup.`);
    }
    return renderer(state, sport);
  }

  const PACKAGE_MANIFESTS = Object.freeze({
    modern_network: {
      id: "modern_network",
      name: "Modern Network",
      scorebugRenderer: "modern",
      styleClass: "package-modern",
      componentRendererFamily: "modern",
      sports: {
        football: {components: {
          scorebug:{zone:"bottom-center", layer:100},
          ticker:{zone:"bottom-center", layer:110, allowOverlapWith:["scorebug"]},
          playerCard:{zone:"bottom-left", fallbackZones:["left-center"], layer:80},
          highlightVideo:{zone:"top-right", fallbackZones:["right-center"], layer:70},
          sponsor:{zone:"top-left", fallbackZones:["left-center"], layer:60},
          captions:{zone:"top-center", fallbackZones:["top-right","top-left"], layer:120}
        }},
        basketball: {components: {
          scorebug:{zone:"bottom-center", layer:100},
          ticker:{zone:"bottom-center", layer:110, allowOverlapWith:["scorebug"]},
          playerCard:{zone:"bottom-left", fallbackZones:["left-center"], layer:80},
          highlightVideo:{zone:"top-right", fallbackZones:["right-center"], layer:70},
          sponsor:{zone:"top-left", layer:60},
          captions:{zone:"top-center", fallbackZones:["top-right","top-left"], layer:120}
        }},
        baseball: {components: {
          scorebug:{zone:"top-left", layer:100},
          ticker:{zone:"bottom-center", layer:110},
          playerCard:{zone:"bottom-left", layer:80},
          highlightVideo:{zone:"right-center", layer:70},
          sponsor:{zone:"top-right", layer:60},
          captions:{zone:"bottom-center", fallbackZones:["top-center"], layer:120}
        }},
        softball: {components: {
          scorebug:{zone:"top-left", layer:100},
          ticker:{zone:"bottom-center", layer:110},
          playerCard:{zone:"bottom-left", layer:80},
          highlightVideo:{zone:"right-center", layer:70},
          sponsor:{zone:"top-right", layer:60},
          captions:{zone:"bottom-center", fallbackZones:["top-center"], layer:120}
        }}
      }
    },

    pixel_gameday: {
      id:"pixel_gameday", name:"8-Bit Gameday", scorebugRenderer:"pixel", styleClass:"package-pixel",
      componentRendererFamily: "pixel",
      sports:{
        football:{components:{
          scorebug:{zone:"top-center",layer:100},
          ticker:{zone:"bottom-center",layer:110},
          playerCard:{zone:"bottom-left",layer:80},
          highlightVideo:{zone:"right-center",layer:70},
          sponsor:{zone:"top-left",fallbackZones:["left-center"],layer:60},
          captions:{zone:"top-right",fallbackZones:["top-left","top-center"],layer:120}
        }},
        basketball:{components:{
          scorebug:{zone:"top-center",layer:100},ticker:{zone:"bottom-center",layer:110},
          playerCard:{zone:"bottom-left",layer:80},highlightVideo:{zone:"right-center",layer:70},
          sponsor:{zone:"top-left",layer:60},captions:{zone:"top-center",fallbackZones:["top-right","top-left"],layer:120}
        }},
        baseball:{components:{
          scorebug:{zone:"top-left",layer:100},ticker:{zone:"bottom-center",layer:110},
          playerCard:{zone:"bottom-left",layer:80},highlightVideo:{zone:"right-center",layer:70},
          sponsor:{zone:"top-right",layer:60},captions:{zone:"top-center",fallbackZones:["top-right","top-left"],layer:120}
        }},
        softball:{components:{
          scorebug:{zone:"top-left",layer:100},ticker:{zone:"bottom-center",layer:110},
          playerCard:{zone:"bottom-left",layer:80},highlightVideo:{zone:"right-center",layer:70},
          sponsor:{zone:"top-right",layer:60},captions:{zone:"top-center",fallbackZones:["top-right","top-left"],layer:120}
        }}
      }
    },

    minimal_radio: {
      id:"minimal_radio", name:"Minimal Radio", scorebugRenderer:"minimal", styleClass:"package-minimal",
      componentRendererFamily: "minimal",
      sports:{
        football:{components:{
          scorebug:{zone:"top-right",layer:100},ticker:{zone:"bottom-center",layer:110},
          playerCard:{enabled:false},highlightVideo:{zone:"left-center",layer:70},
          sponsor:{zone:"top-left",layer:60},captions:{zone:"top-center",fallbackZones:["top-right","top-left"],layer:120}
        }},
        basketball:{components:{
          scorebug:{zone:"top-right",layer:100},ticker:{zone:"bottom-center",layer:110},
          playerCard:{enabled:false},highlightVideo:{zone:"left-center",layer:70},
          sponsor:{zone:"top-left",layer:60},captions:{zone:"top-center",fallbackZones:["top-right","top-left"],layer:120}
        }},
        baseball:{components:{
          scorebug:{zone:"top-left",layer:100},ticker:{zone:"bottom-center",layer:110},
          playerCard:{enabled:false},highlightVideo:{zone:"right-center",layer:70},
          sponsor:{zone:"top-right",layer:60},captions:{zone:"top-center",fallbackZones:["top-right","top-left"],layer:120}
        }},
        softball:{components:{
          scorebug:{zone:"top-left",layer:100},ticker:{zone:"bottom-center",layer:110},
          playerCard:{enabled:false},highlightVideo:{zone:"right-center",layer:70},
          sponsor:{zone:"top-right",layer:60},captions:{zone:"top-center",fallbackZones:["top-right","top-left"],layer:120}
        }}
      }
    },

    heritage_press: {
      id:"heritage_press", name:"Heritage Press", scorebugRenderer:"press", styleClass:"package-press",
      componentRendererFamily: "press",
      sports:{
        football:{components:{
          scorebug:{zone:"top-center",width:1140,height:234,layer:100},ticker:{zone:"bottom-center",layer:110},
          playerCard:{zone:"bottom-left",layer:80},highlightVideo:{zone:"right-center",layer:70},
          sponsor:{zone:"left-center",fallbackZones:["top-left"],layer:60},
          captions:{zone:"top-center",fallbackZones:["top-right","top-left"],layer:120}
        }},
        basketball:{components:{
          scorebug:{zone:"top-center",width:1140,height:234,layer:100},ticker:{zone:"bottom-center",layer:110},
          playerCard:{zone:"bottom-left",layer:80},highlightVideo:{zone:"right-center",layer:70},
          sponsor:{zone:"left-center",layer:60},captions:{zone:"top-center",fallbackZones:["top-right","top-left"],layer:120}
        }},
        baseball:{components:{
          scorebug:{zone:"top-center",width:1140,height:234,layer:100},ticker:{zone:"bottom-center",layer:110},
          playerCard:{zone:"bottom-left",layer:80},highlightVideo:{zone:"right-center",layer:70},
          sponsor:{zone:"left-center",layer:60},captions:{zone:"top-center",fallbackZones:["top-right","top-left"],layer:120}
        }},
        softball:{components:{
          scorebug:{zone:"top-center",width:1140,height:234,layer:100},ticker:{zone:"bottom-center",layer:110},
          playerCard:{zone:"bottom-left",layer:80},highlightVideo:{zone:"right-center",layer:70},
          sponsor:{zone:"left-center",layer:60},captions:{zone:"top-center",fallbackZones:["top-right","top-left"],layer:120}
        }}
      }
    },

    friday_night_stadium: {
      id:"friday_night_stadium", name:"Friday Night Stadium", scorebugRenderer:"stadium", styleClass:"package-stadium",
      componentRendererFamily: "stadium",
      sports:{
        football:{components:{
          scorebug:{zone:"top-center",layer:100},ticker:{zone:"bottom-center",layer:110},
          playerCard:{zone:"bottom-left",layer:80},highlightVideo:{zone:"right-center",layer:70},
          sponsor:{zone:"left-center",layer:60},captions:{zone:"top-center",fallbackZones:["top-right","top-left"],layer:120}
        }},
        basketball:{components:{
          scorebug:{zone:"top-center",layer:100},ticker:{zone:"bottom-center",layer:110},
          playerCard:{zone:"bottom-left",layer:80},highlightVideo:{zone:"right-center",layer:70},
          sponsor:{zone:"left-center",layer:60},captions:{zone:"top-center",fallbackZones:["top-right","top-left"],layer:120}
        }},
        baseball:{components:{
          scorebug:{zone:"top-center",layer:100},ticker:{zone:"bottom-center",layer:110},
          playerCard:{zone:"bottom-left",layer:80},highlightVideo:{zone:"right-center",layer:70},
          sponsor:{zone:"left-center",layer:60},captions:{zone:"top-center",fallbackZones:["top-right","top-left"],layer:120}
        }},
        softball:{components:{
          scorebug:{zone:"top-center",layer:100},ticker:{zone:"bottom-center",layer:110},
          playerCard:{zone:"bottom-left",layer:80},highlightVideo:{zone:"right-center",layer:70},
          sponsor:{zone:"left-center",layer:60},captions:{zone:"top-center",fallbackZones:["top-right","top-left"],layer:120}
        }}
      }
    },

    digital_neon: {
      id:"digital_neon", name:"Neon Sports Network", scorebugRenderer:"neon", styleClass:"package-neon-approved",
      componentRendererFamily: "neon",
      sports:{
        football:{components:{
          scorebug:{zone:"top-full",width:1840,height:250,layer:100},
          ticker:{zone:"bottom-center",height:64,layer:110},
          playerCard:{zone:"left-center",width:610,height:390,layer:80},
          highlightVideo:{zone:"right-center",layer:70},
          sponsor:{zone:"right-center",width:520,height:180,layer:60},
          captions:{zone:"bottom-center",height:56,stackAboveHeight:64,layer:120}
        }},
        basketball:{components:{
          scorebug:{zone:"top-full",width:1840,height:250,layer:100},
          ticker:{zone:"bottom-center",height:64,layer:110},
          playerCard:{zone:"left-center",width:610,height:390,layer:80},
          highlightVideo:{zone:"right-center",layer:70},
          sponsor:{zone:"right-center",width:520,height:180,layer:60},
          captions:{zone:"bottom-center",height:56,stackAboveHeight:64,layer:120}
        }},
        baseball:{components:{
          scorebug:{zone:"top-full",width:1840,height:250,layer:100},
          ticker:{zone:"bottom-center",height:64,layer:110},
          playerCard:{zone:"left-center",width:610,height:390,layer:80},
          highlightVideo:{zone:"right-center",layer:70},
          sponsor:{zone:"right-center",width:520,height:180,layer:60},
          captions:{zone:"bottom-center",height:56,stackAboveHeight:64,layer:120}
        }},
        softball:{components:{
          scorebug:{zone:"top-full",width:1840,height:250,layer:100},
          ticker:{zone:"bottom-center",height:64,layer:110},
          playerCard:{zone:"left-center",width:610,height:390,layer:80},
          highlightVideo:{zone:"right-center",layer:70},
          sponsor:{zone:"right-center",width:520,height:180,layer:60},
          captions:{zone:"bottom-center",height:56,stackAboveHeight:64,layer:120}
        }}
      }
    },

    collegiate_traditional: {
      id:"collegiate_traditional", name:"Collegiate Traditional", scorebugRenderer:"collegiate", styleClass:"package-collegiate",
      componentRendererFamily: "collegiate",
      sports:{
        football:{components:{
          scorebug:{zone:"full-safe",width:1840,height:1000,layer:100},ticker:{zone:"top-center",height:58,layer:110,allowOverlapWith:["scorebug"]},
          playerCard:{zone:"bottom-left",fallbackZones:["left-center"],layer:80},
          highlightVideo:{zone:"top-right",layer:70},sponsor:{zone:"top-left",layer:60},
          captions:{zone:"top-center",fallbackZones:["top-right","top-left"],layer:120}
        }},
        basketball:{components:{
          scorebug:{zone:"bottom-center",layer:100},ticker:{zone:"bottom-center",layer:110,allowOverlapWith:["scorebug"]},
          playerCard:{zone:"bottom-left",fallbackZones:["left-center"],layer:80},
          highlightVideo:{zone:"top-right",layer:70},sponsor:{zone:"top-left",layer:60},
          captions:{zone:"top-center",fallbackZones:["top-right","top-left"],layer:120}
        }},
        baseball:{components:{
          scorebug:{zone:"top-left",layer:100},ticker:{zone:"bottom-center",layer:110},
          playerCard:{zone:"bottom-left",layer:80},highlightVideo:{zone:"right-center",layer:70},
          sponsor:{zone:"top-right",layer:60},captions:{zone:"top-center",fallbackZones:["top-right","top-left"],layer:120}
        }},
        softball:{components:{
          scorebug:{zone:"top-left",layer:100},ticker:{zone:"bottom-center",layer:110},
          playerCard:{zone:"bottom-left",layer:80},highlightVideo:{zone:"right-center",layer:70},
          sponsor:{zone:"top-right",layer:60},captions:{zone:"top-center",fallbackZones:["top-right","top-left"],layer:120}
        }}
      }
    },

    classic_broadcast: {
      id:"classic_broadcast", name:"Classic Broadcast", scorebugRenderer:"classic", styleClass:"package-classic",
      componentRendererFamily: "classic",
      sports:{
        football:{components:{
          scorebug:{zone:"bottom-center",layer:100},ticker:{zone:"bottom-center",layer:110,allowOverlapWith:["scorebug"]},
          playerCard:{zone:"bottom-left",fallbackZones:["left-center"],layer:80},
          highlightVideo:{zone:"top-right",layer:70},sponsor:{zone:"top-left",layer:60},
          captions:{zone:"top-center",fallbackZones:["top-right","top-left"],layer:120}
        }},
        basketball:{components:{
          scorebug:{zone:"bottom-center",layer:100},ticker:{zone:"bottom-center",layer:110,allowOverlapWith:["scorebug"]},
          playerCard:{zone:"bottom-left",fallbackZones:["left-center"],layer:80},
          highlightVideo:{zone:"top-right",layer:70},sponsor:{zone:"top-left",layer:60},
          captions:{zone:"top-center",fallbackZones:["top-right","top-left"],layer:120}
        }},
        baseball:{components:{
          scorebug:{zone:"top-left",layer:100},ticker:{zone:"bottom-center",layer:110},
          playerCard:{zone:"bottom-left",layer:80},highlightVideo:{zone:"right-center",layer:70},
          sponsor:{zone:"top-right",layer:60},captions:{zone:"top-center",fallbackZones:["top-right","top-left"],layer:120}
        }},
        softball:{components:{
          scorebug:{zone:"top-left",layer:100},ticker:{zone:"bottom-center",layer:110},
          playerCard:{zone:"bottom-left",layer:80},highlightVideo:{zone:"right-center",layer:70},
          sponsor:{zone:"top-right",layer:60},captions:{zone:"top-center",fallbackZones:["top-right","top-left"],layer:120}
        }}
      }
    }
  });

  function applyRect(node, placement) {
    const rect = placement.rect;
    node.style.left = `${rect.x}px`;
    node.style.top = `${rect.y}px`;
    node.style.width = `${rect.w}px`;
    node.style.height = `${rect.h}px`;
    node.style.zIndex = String(placement.layer || 1);
    node.dataset.zone = placement.zone;
    node.dataset.component = placement.component;
    if (placement.colliding) node.dataset.collision = "true";
  }


  function fitNeonTeamNames(root) {
    for (const node of root.querySelectorAll(".bl-neon-team-name")) {
      node.style.fontSize = "";
      node.style.letterSpacing = "";
      const available = node.clientWidth;
      if (!available) continue;
      let size = parseFloat(getComputedStyle(node).fontSize) || 36;
      let spacing = parseFloat(getComputedStyle(node).letterSpacing);
      if (!Number.isFinite(spacing)) spacing = 0;
      let guard = 0;
      while (node.scrollWidth > available + 1 && size > 22 && guard < 40) {
        size -= 1;
        if (spacing > 0 && size < 34) spacing = Math.max(0, spacing - 0.15);
        node.style.fontSize = `${size}px`;
        node.style.letterSpacing = `${spacing}px`;
        guard += 1;
      }
      node.dataset.fitFontSize = String(size);
      node.dataset.fitOverflow = node.scrollWidth > available + 1 ? "true" : "false";
    }
  }

  function renderPackage(root, packageId, sport = "football", value = {}, options = {}) {
    if (!root) throw new Error("Broadcast layout root is required.");
    clearPressWire(root);
    const manifest = PACKAGE_MANIFESTS[packageId];
    if (!manifest) throw new Error(`Unknown broadcast package: ${packageId}`);
    if (!SPORT_CONTRACTS[sport]) throw new Error(`Unsupported sport: ${sport}`);

    const state = mergeState({...value, sport});
    const activeComponents = options.activeComponents || PRESENTATION_SCENARIOS.baseline;
    const placements = resolvePlacements(manifest, sport, activeComponents);

    root.replaceChildren();
    root.className = `csrn-broadcast-layout ${manifest.styleClass}`;
    root.dataset.package = manifest.id;
    root.dataset.sport = sport;
    root.dataset.engineVersion = VERSION;
    root.classList.toggle("diagnostics", Boolean(options.diagnostics));

    for (const component of activeComponents) {
      const placement = placements[component];
      if (!placement) continue;
      const node = document.createElement("section");
      node.className = `bl-component bl-${component}`;
      applyRect(node, placement);
      node.innerHTML = componentFrame(component, manifest, state, sport);
      root.appendChild(node);
    }

    if (manifest.componentRendererFamily === "neon") {
      fitNeonTeamNames(root);
    }
    root.dataset.ready = "true";
    if (manifest.componentRendererFamily === "press") {
      hydratePressWire(root, options);
    }
    return {
      packageId: manifest.id,
      sport,
      placements: clone(placements),
      components: [...root.querySelectorAll(".bl-component")].map((node) => node.dataset.component)
    };
  }

  function auditRenderedScorebug(root) {
    const issues = [];
    const warnings = [];
    const component = root?.querySelector?.('.bl-component.bl-scorebug');
    const scorebug = component?.querySelector?.('.bl-scorebug');
    if (!component || !scorebug) return ['missing scorebug'];

    const componentRect = component.getBoundingClientRect();
    const scorebugRect = scorebug.getBoundingClientRect();
    const tolerance = 4;

    if (scorebugRect.width <= 0 || scorebugRect.height <= 0) {
      issues.push('scorebug: zero-size');
    }

    const rootOutside = (
      scorebugRect.left < componentRect.left - tolerance ||
      scorebugRect.right > componentRect.right + tolerance ||
      scorebugRect.top < componentRect.top - tolerance ||
      scorebugRect.bottom > componentRect.bottom + tolerance
    );
    if (rootOutside) issues.push('scorebug: outside component footprint');

    for (const node of scorebug.querySelectorAll('[data-module]')) {
      const rect = node.getBoundingClientRect();
      if (rect.width <= 0 || rect.height <= 0) {
        issues.push(`${node.dataset.module}: zero-size`);
        continue;
      }

      const parentModule = node.parentElement?.closest?.('[data-module]');
      if (parentModule && scorebug.contains(parentModule)) continue;

      const intersectionWidth = Math.max(0, Math.min(rect.right, scorebugRect.right) - Math.max(rect.left, scorebugRect.left));
      const intersectionHeight = Math.max(0, Math.min(rect.bottom, scorebugRect.bottom) - Math.max(rect.top, scorebugRect.top));
      const visibleArea = intersectionWidth * intersectionHeight;
      const moduleArea = rect.width * rect.height;
      const visibleRatio = moduleArea > 0 ? visibleArea / moduleArea : 0;

      if (visibleRatio < 0.65) {
        issues.push(`${node.dataset.module}: materially outside scorebug`);
      } else if (visibleRatio < 0.98) {
        warnings.push(`${node.dataset.module}: edge overflow`);
      }
    }

    for (const node of scorebug.querySelectorAll('.bl-team-name')) {
      if (node.scrollWidth > node.clientWidth + 2) {
        node.dataset.textOverflow = 'true';
      } else {
        delete node.dataset.textOverflow;
      }
    }

    root.dataset.scorebugAuditWarnings = warnings.join(' | ');
    return issues;
  }

  function validateManifests() {
    const errors = [];
    for (const manifest of Object.values(PACKAGE_MANIFESTS)) {
      if (!SCOREBUG_RENDERERS[manifest.scorebugRenderer]) {
        errors.push(`${manifest.id}: unknown scorebug renderer ${manifest.scorebugRenderer}`);
      }
      const family = PACKAGE_COMPONENT_RENDERERS[manifest.componentRendererFamily];
      if (!family) {
        errors.push(`${manifest.id}: unknown component renderer family ${manifest.componentRendererFamily}`);
      } else {
        for (const component of COMPONENT_TYPES.filter((name) => name !== "scorebug")) {
          if (typeof family[component] !== "function") {
            errors.push(`${manifest.id}: component renderer family ${manifest.componentRendererFamily} is missing ${component}`);
          }
        }
      }
      for (const sport of Object.keys(manifest.sports)) {
        if (!SPORT_CONTRACTS[sport]) errors.push(`${manifest.id}: unknown sport ${sport}`);
        const components = manifest.sports[sport].components || {};
        if (!components.scorebug) errors.push(`${manifest.id}/${sport}: scorebug is required`);
        for (const [name, rule] of Object.entries(components)) {
          if (!COMPONENT_TYPES.includes(name)) errors.push(`${manifest.id}/${sport}: unknown component ${name}`);
          if (rule.enabled !== false && !ZONES[rule.zone]) errors.push(`${manifest.id}/${sport}/${name}: invalid zone ${rule.zone}`);
          for (const fallback of rule.fallbackZones || []) {
            if (!ZONES[fallback]) errors.push(`${manifest.id}/${sport}/${name}: invalid fallback ${fallback}`);
          }
        }
      }
    }
    return errors;
  }

  window.CSRNBroadcastLayoutEngine = Object.freeze({
    version: VERSION,
    manifests: PACKAGE_MANIFESTS,
    sports: SPORT_CONTRACTS,
    sportStateContracts: SPORT_STATE_CONTRACTS,
    futureBaseballComponents: BASEBALL_FUTURE_COMPONENTS,
    zones: ZONES,
    componentSizes: COMPONENT_DEFAULT_SIZES,
    autoFallbackZones: AUTO_FALLBACK_ZONES,
    componentTypes: COMPONENT_TYPES,
    scenarios: PRESENTATION_SCENARIOS,
    defaultState: () => clone(DEFAULT_STATE),
    validateManifests,
    auditRenderedScorebug,
    resolvePlacements,
    HERITAGE_PRESS_ASSETS,
    splitPressWireStories,
    hydratePressWire,
    clearPressWire,
    renderPackage
  });
})();
