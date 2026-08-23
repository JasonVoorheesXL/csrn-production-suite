(() => {
  "use strict";

  const VERSION = "1.7.0";
  const PACKAGE_ID = "pixel_gameday";
  const base = window.CSRNBroadcastLayoutEngine;
  if (!base) throw new Error("8-Bit Gameday requires the Broadcast Layout Engine.");

  const MANIFEST = Object.freeze({
    id: PACKAGE_ID,
    name: "8-Bit Gameday",
    styleClass: "package-8bit-approved",
    engine: "CSRNEightBitGamedayEngine",
    sports: Object.freeze({football:true,basketball:true,baseball:true,softball:true})
  });

  const LED_GLYPHS = Object.freeze({
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
    "A":["01110","10001","10001","11111","10001","10001","10001"],
    "B":["11110","10001","10001","11110","10001","10001","11110"],
    "C":["01111","10000","10000","10000","10000","10000","01111"],
    "D":["11110","10001","10001","10001","10001","10001","11110"],
    "E":["11111","10000","10000","11110","10000","10000","11111"],
    "F":["11111","10000","10000","11110","10000","10000","10000"],
    "G":["01111","10000","10000","10111","10001","10001","01111"],
    "H":["10001","10001","10001","11111","10001","10001","10001"],
    "I":["01110","00100","00100","00100","00100","00100","01110"],
    "J":["00001","00001","00001","00001","10001","10001","01110"],
    "K":["10001","10010","10100","11000","10100","10010","10001"],
    "L":["10000","10000","10000","10000","10000","10000","11111"],
    "M":["10001","11011","10101","10101","10001","10001","10001"],
    "N":["10001","11001","10101","10011","10001","10001","10001"],
    "O":["01110","10001","10001","10001","10001","10001","01110"],
    "P":["11110","10001","10001","11110","10000","10000","10000"],
    "Q":["01110","10001","10001","10001","10101","10010","01101"],
    "R":["11110","10001","10001","11110","10100","10010","10001"],
    "S":["01111","10000","10000","01110","00001","00001","11110"],
    "T":["11111","00100","00100","00100","00100","00100","00100"],
    "U":["10001","10001","10001","10001","10001","10001","01110"],
    "V":["10001","10001","10001","10001","10001","01010","00100"],
    "W":["10001","10001","10001","10101","10101","10101","01010"],
    "X":["10001","10001","01010","00100","01010","10001","10001"],
    "Y":["10001","10001","01010","00100","00100","00100","00100"],
    "Z":["11111","00001","00010","00100","01000","10000","11111"],
    ":":["00000","00100","00100","00000","00100","00100","00000"],
    "-":["00000","00000","00000","11111","00000","00000","00000"],
    "/":["00001","00010","00010","00100","01000","01000","10000"],
    ".":["00000","00000","00000","00000","00000","00110","00110"],
    "&":["01100","10010","10100","01000","10101","10010","01101"]
  });

  const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (ch) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[ch]);
  const clampScore = (value) => String(Math.max(0, Math.min(999, Number(value) || 0)));
  const safeColor = (value, fallback) => /^#[0-9a-f]{6}$/i.test(String(value || "")) ? value : fallback;

  function displayColor(value, fallback) {
    const source=safeColor(value,fallback).slice(1);
    const [r,g,b]=[0,2,4].map(index=>parseInt(source.slice(index,index+2),16)/255);
    const max=Math.max(r,g,b),min=Math.min(r,g,b),delta=max-min;
    let hue=0;
    if(delta){if(max===r)hue=((g-b)/delta)%6;else if(max===g)hue=(b-r)/delta+2;else hue=(r-g)/delta+4;hue=Math.round(hue*60);if(hue<0)hue+=360;}
    const light=(max+min)/2;
    const saturation=delta===0?0:delta/(1-Math.abs(2*light-1));
    return `hsl(${hue} ${Math.round(Math.max(.76,saturation)*100)}% ${Math.round(Math.min(.68,Math.max(.58,light))*100)}%)`;
  }

  function ledSvg(value, className = "", options = {}) {
    const text = String(value ?? "").toUpperCase();
    const glyphWidth = 6;
    const width = Math.max(5, text.length * glyphWidth - 1);
    const dots = [];
    [...text].forEach((character, index) => {
      const glyph = LED_GLYPHS[character] || LED_GLYPHS[" "];
      glyph.forEach((row, y) => [...row].forEach((on, x) => {
        if (on === "1") dots.push(`<circle cx="${index * glyphWidth + x + .5}" cy="${y + .5}" r=".42"/>`);
      }));
    });
    return `<svg class="bl-8bit-led ${esc(className)}" viewBox="0 0 ${width} 7" role="img" aria-label="${esc(text.trim())}" preserveAspectRatio="${options.stretch ? "none" : "xMidYMid meet"}"><g>${dots.join("")}</g></svg>`;
  }

  function normalizeState(value = {}, sport = "football") {
    const fallback = base.defaultState();
    const state = {
      ...fallback,
      ...value,
      sport,
      home:{...fallback.home,...(value.home || {})},
      visitor:{...fallback.visitor,...(value.visitor || {})},
      game:{...fallback.game,...(value.game || {})},
      player:{...fallback.player,...(value.player || {})},
      sponsor:{...fallback.sponsor,...(value.sponsor || {})},
      highlight:{...fallback.highlight,...(value.highlight || {})},
      captions:{...fallback.captions,...(value.captions || {})},
      ticker:{...fallback.ticker,...(value.ticker || {})}
    };
    const sportDefaults = {
      football:{period:"2ND",clock:"07:42",downDistance:"3RD & 7",ballOn:"28",homeTimeouts:3,visitorTimeouts:2},
      basketball:{period:"2ND",clock:"07:42",homeFouls:4,visitorFouls:5,homeBonus:"BONUS",visitorBonus:"",homeTimeouts:3,visitorTimeouts:2},
      baseball:{inning:"5",inningHalf:"TOP",balls:"2",strikes:"1",outs:"1",bases:[true,false,true],homeHits:7,visitorHits:9,homeErrors:1,visitorErrors:0,batterName:"A. CARTER",pitcherName:"J. RIVERA"},
      softball:{inning:"5",inningHalf:"TOP",balls:"2",strikes:"1",outs:"1",bases:[true,false,true],homeHits:6,visitorHits:8,homeErrors:0,visitorErrors:1,batterName:"A. CARTER",pitcherName:"J. RIVERA"}
    };
    state.game = {...sportDefaults[sport],...state.game};
    state.scheduledDate=value.scheduledDate||value.scheduled_date||value.gameDate||value.game_date||value.date||value.scheduledStart||value.scheduled_start||state.game.scheduledDate||state.game.scheduled_date||state.game.gameDate||state.game.game_date||state.game.date||state.game.scheduledStart||state.game.scheduled_start||"";
    state.contestType=value.contestType||value.contest_type||state.game.contestType||state.game.contest_type||"official";
    state.specialGameDesignations=value.specialGameDesignations||value.special_game_designations||value.specialDesignations||value.special_designations||state.game.specialGameDesignations||state.game.special_game_designations||state.game.specialDesignations||state.game.special_designations||[];
    return state;
  }

  function playerPortrait(sport, side) {
    return `<canvas class="bl-8bit-mini-player" data-mini-player="${esc(side)}" role="img" aria-label="${esc(side)} ${esc(sport)} player"></canvas>`;
  }

  function teamDisplayName(team, limit = 16) {
    const full = String(team.name || team.shortName || "TEAM").trim();
    const short = String(team.shortName || "").trim();
    return full.length <= limit ? full : short && short.length < full.length ? short : full;
  }

  function identityPlate(team, side, marker = "") {
    return `<div class="bl-8bit-identity-plate" data-module="${side}.identity"><span class="bl-8bit-identity-copy"><strong>${esc(teamDisplayName(team))}</strong><span>${esc(team.mascot || team.shortName)}</span></span>${marker}</div>`;
  }

  function possessionBall(sport, active) {
    if (!active) return `<span class="bl-8bit-possession-ball is-empty" aria-hidden="true"></span>`;
    if (sport === "basketball") return `<span class="bl-8bit-possession-ball bl-8bit-basketball-possession" aria-label="Possession"><svg viewBox="0 0 64 64" aria-hidden="true"><circle cx="32" cy="32" r="27"/><path d="M5 32h54M32 5c-12 12-12 42 0 54M32 5c12 12 12 42 0 54M12 15c13 8 27 8 40 0M12 49c13-8 27-8 40 0"/></svg></span>`;
    return `<span class="bl-8bit-possession-ball bl-8bit-football-possession" aria-label="Possession"><svg viewBox="0 0 72 44" aria-hidden="true"><path d="M4 22C13 3 55 3 68 22 55 41 13 41 4 22Z"/><path d="M36 7v30M25 22h22M29 16l14 12M43 16 29 28"/></svg></span>`;
  }

  function scoreDisplay(team, side, sport, state, role = "") {
    const scoreText = clampScore(team.score);
    const fixedScore = sport === "basketball" ? scoreText.padStart(3," ") : scoreText.padStart(2," ");
    return `<div class="bl-8bit-score" data-module="${side}.score" data-led-capacity="${sport === "basketball" ? "3" : "2"}">${ledSvg(fixedScore,"bl-8bit-score-led")}${role}</div>`;
  }

  function footballTower(state, side) {
    const team=state[side];
    return `<aside class="bl-8bit-team-tower bl-8bit-football-tower bl-8bit-${side}" data-module="${side}.team">
      <div class="bl-8bit-side-label">${side === "home" ? "HOME" : "VISITOR"}</div>
      ${scoreDisplay(team,side,"football",state)}
      ${identityPlate(team,side)}
      ${playerPortrait("football",side)}
    </aside>`;
  }

  function basketballTower(state, side) {
    const team=state[side];
    return `<aside class="bl-8bit-team-tower bl-8bit-basketball-tower bl-8bit-${side}" data-module="${side}.team">
      <div class="bl-8bit-side-label">${side === "home" ? "HOME" : "VISITOR"}</div>
      ${scoreDisplay(team,side,"basketball",state)}
      ${identityPlate(team,side)}
      ${playerPortrait("basketball",side)}
    </aside>`;
  }

  function diamondTower(state, side) {
    const team=state[side];
    const role=side === "visitor" ? "AT BAT" : "PITCHING";
    const player=side === "visitor" ? state.game.batterName : state.game.pitcherName;
    return `<aside class="bl-8bit-team-tower bl-8bit-diamond-tower bl-8bit-${side}" data-module="${side}.team">
      <div class="bl-8bit-side-label">${side === "home" ? "HOME" : "VISITOR"}</div>
      ${scoreDisplay(team,side,state.sport,state)}
      ${identityPlate(team,side)}
      <div class="bl-8bit-diamond-player-role" data-diamond-role="${esc(side)}"><strong>${role}</strong><b>${esc(player)}</b></div>
    </aside>`;
  }

  function formatGameDate(value) {
    const raw=String(value||"").trim();if(!raw)return"DATE TBD";
    const simple=raw.match(/^(\d{4})-(\d{2})-(\d{2})/),date=simple?new Date(Number(simple[1]),Number(simple[2])-1,Number(simple[3])):new Date(raw);
    return Number.isNaN(date.getTime())?raw.toUpperCase():date.toLocaleDateString("en-US",{month:"short",day:"numeric",year:"numeric"}).toUpperCase();
  }

  function gameDesignation(state) {
    const raw=Array.isArray(state.specialGameDesignations)?state.specialGameDesignations:[state.specialGameDesignations];
    const designations=raw.map(item=>typeof item==="string"?item:item?.label||item?.name||item?.type||item?.designation||"").map(item=>String(item).trim()).filter(Boolean);
    if(designations.length)return designations[0].replace(/[_-]+/g," ").toUpperCase();
    const contest=String(state.contestType||"official").replace(/[_-]+/g," ").trim().toUpperCase();
    return contest==="OFFICIAL"||contest==="OFFICIAL GAME"?"REGULAR SEASON":contest;
  }

  function rheMarkup(state, side) {
    const team=state[side];
    return `<div class="bl-8bit-rhe bl-8bit-rhe-${side}" data-rhe-side="${side}"><span>R<b>${ledSvg(clampScore(team.score),"bl-8bit-rhe-led")}</b></span><span>H<b>${ledSvg(state.game[`${side}Hits`],"bl-8bit-rhe-led")}</b></span><span>E<b>${ledSvg(state.game[`${side}Errors`],"bl-8bit-rhe-led")}</b></span></div>`;
  }

  function versusMark(){return `<svg class="bl-8bit-vs-art" viewBox="0 0 220 260" aria-label="versus"><path d="M128 4 52 126h51L73 256l102-151h-55Z"/><text x="110" y="158">VS</text></svg>`;}

  const ATHLETE_ASSETS=Object.freeze({football:"8bit-gameday/athletes/football-athletes.png",basketball:"8bit-gameday/athletes/basketball-athletes.png",baseball:"8bit-gameday/athletes/baseball-athletes.png",softball:"8bit-gameday/athletes/softball-athletes.png"});
  const imageCache=new Map();
  function loadImage(src){
    if(imageCache.has(src))return imageCache.get(src);
    const pending=new Promise((resolve,reject)=>{const image=new Image();image.onload=()=>resolve(image);image.onerror=()=>reject(new Error(`8-Bit asset failed to load: ${src}`));image.src=src;});
    imageCache.set(src,pending);return pending;
  }

  function rgb(hex){const value=parseInt(String(hex).replace("#",""),16);return[(value>>16)&255,(value>>8)&255,value&255];}
  function hsv(r,g,b){r/=255;g/=255;b/=255;const max=Math.max(r,g,b),min=Math.min(r,g,b),d=max-min;let h=0;if(d){if(max===r)h=60*((g-b)/d%6);else if(max===g)h=60*((b-r)/d+2);else h=60*((r-g)/d+4);}if(h<0)h+=360;return[h,max?d/max:0,max];}
  function keyedMaterial(h,s,v){if(s<.42||v<.16)return null;if(h>=174&&h<=205)return"visitorPrimary";if(h>=206&&h<=252)return"visitorSecondary";if(h>=292&&h<=345)return"homePrimary";if(h>=35&&h<=70)return"homeSecondary";return null;}
  function shadePixel(target,v){if(v<.46){const q=Math.round(18+v*92);return[q,q,q];}const strength=.9+(v-.46)*.18;return target.map(c=>Math.max(0,Math.min(255,Math.round(c*strength))));}
  async function paintClash(root,state) {
    const visibleCanvas=root.querySelector(".bl-8bit-clash-art"),src=ATHLETE_ASSETS[state.sport];if(!src)return;
    const canvas=visibleCanvas||document.createElement("canvas");
    if(visibleCanvas)visibleCanvas.dataset.artReady="pending";
    const image=await loadImage(src),ctx=canvas.getContext("2d",{willReadFrequently:true});canvas.width=image.naturalWidth;canvas.height=image.naturalHeight;ctx.clearRect(0,0,canvas.width,canvas.height);ctx.drawImage(image,0,0);
    const frame=ctx.getImageData(0,0,canvas.width,canvas.height),p=frame.data,colors={visitorPrimary:rgb(state.visitor.primary),visitorSecondary:rgb(state.visitor.secondary),homePrimary:rgb(state.home.primary),homeSecondary:rgb(state.home.secondary)};let recolored=0,neutralShadows=0;
    for(let i=0;i<p.length;i+=4){if(p[i+3]===0)continue;const pixel=i/4,x=pixel%canvas.width,y=Math.floor(pixel/canvas.width),[h,s,v]=hsv(p[i],p[i+1],p[i+2]),key=keyedMaterial(h,s,v);if(!key)continue;if(state.sport==="softball"&&x>canvas.width*.86&&y<canvas.height*.2&&h>=35&&h<=70)continue;const out=shadePixel(colors[key],v);p[i]=out[0];p[i+1]=out[1];p[i+2]=out[2];recolored++;if(out[0]===out[1]&&out[1]===out[2])neutralShadows++;}
    ctx.putImageData(frame,0,0);
    root.querySelectorAll(".bl-8bit-mini-player").forEach((portrait)=>{
      const visitor=portrait.dataset.miniPlayer==="visitor",sourceX=visitor?0:canvas.width/2;
      portrait.width=320;portrait.height=220;
      const portraitContext=portrait.getContext("2d");
      portraitContext.clearRect(0,0,portrait.width,portrait.height);
      portraitContext.drawImage(canvas,sourceX,0,canvas.width/2,canvas.height,0,0,portrait.width,portrait.height);
      portrait.dataset.portraitReady="true";
    });
    if(visibleCanvas){visibleCanvas.dataset.artReady="true";visibleCanvas.dataset.recoloredPixels=String(recolored);visibleCanvas.dataset.neutralShadowPixels=String(neutralShadows);}
    if(recolored<5000||neutralShadows<250)throw new Error(`8-Bit material decomposition failed: ${state.sport}`);
  }

  function clashContent(state) {
    const sport=state.sport;
    return `<div class="bl-8bit-clash bl-8bit-clash-${sport}" data-video-mode="clash" data-clash-sport="${sport}">
      <div class="bl-8bit-field-art" data-field-kind="${sport}" aria-hidden="true"></div>
      <canvas class="bl-8bit-clash-art" data-art-ready="pending" aria-label="${esc(state.visitor.name)} versus ${esc(state.home.name)}"></canvas>
      <div class="bl-8bit-clash-side bl-8bit-clash-visitor"><strong>${esc(state.visitor.name)}</strong><span>${esc(state.visitor.mascot)}</span></div>
      <div class="bl-8bit-versus">${versusMark()}</div>
      <div class="bl-8bit-clash-side bl-8bit-clash-home"><strong>${esc(state.home.name)}</strong><span>${esc(state.home.mascot)}</span></div>
    </div>`;
  }

  function videoContent(state, mode) {
    if (mode === "highlight") return `<div class="bl-8bit-video-replacement" data-video-mode="highlight"><div class="bl-8bit-video-feed">VIDEO</div><strong>${esc(state.highlight.title)}</strong><span>${esc(state.highlight.detail)}</span></div>`;
    if (mode === "sponsor") return `<div class="bl-8bit-video-replacement bl-8bit-sponsor-replacement" data-video-mode="sponsor">${state.sponsor.logo ? `<img src="${esc(state.sponsor.logo)}" alt="">` : ""}<small>PRESENTED BY</small><strong>${esc(state.sponsor.name)}</strong><span>${esc(state.sponsor.line)}</span></div>`;
    if (mode === "player") return `<div class="bl-8bit-video-replacement bl-8bit-player-replacement" data-video-mode="player"><div class="bl-8bit-player-portrait">${state.player.headshot ? `<img src="${esc(state.player.headshot)}" alt="">` : `<b>#${esc(state.player.number)}</b>`}</div><small>PLAYER SPOTLIGHT</small><strong>${esc(state.player.name)}</strong><span>${esc(state.player.position)} · ${esc(state.player.detail)}</span></div>`;
    if (mode === "broadcast") return `<div class="bl-8bit-video-replacement bl-8bit-broadcast-replacement" data-video-mode="broadcast"><div class="bl-8bit-video-feed">LIVE VIDEO</div></div>`;
    return clashContent(state);
  }

  function timeoutDots(value) {
    const count = Math.max(0, Math.min(5, Number(value) || 0));
    return `<span class="bl-8bit-timeouts" aria-label="${count} timeouts">${Array.from({length:4},(_,i)=>`<i class="${i<count?"on":""}"></i>`).join("")}</span>`;
  }

  function footballControls(state) {
    const match=String(state.game.downDistance||"").match(/(\d+)[A-Z]*\s*&\s*(\d+)/i);
    const down=match?.[1]||"3";const toGo=match?.[2]||"7";
    return `<div class="bl-8bit-football-control-bank">
      <span><small>CLOCK</small>${ledSvg(state.game.clock,"bl-8bit-clock-led")}</span>
      <span><small>QUARTER</small>${ledSvg(String(state.game.period).replace(/\D/g,"")||"2","bl-8bit-small-led")}</span>
      <span><small>DOWN</small>${ledSvg(down,"bl-8bit-small-led")}</span>
      <span><small>TO GO</small>${ledSvg(toGo,"bl-8bit-small-led")}</span>
      <span class="bl-8bit-possession-cell"><small>POSSESSION</small>${ledSvg(state.game.possession==="visitor"?"VISITOR":"HOME","bl-8bit-possession-led")}</span>
      <span><small>BALL ON</small>${ledSvg(state.game.ballOn||"28","bl-8bit-small-led")}</span>
    </div>`;
  }

  function basketballControls(state) {
    return `<div class="bl-8bit-basketball-control-bank">
      <span><small>VISITOR FOULS</small>${ledSvg(state.game.visitorFouls,"bl-8bit-small-led")}</span>
      <span><small>BONUS</small><b>${esc(state.game.visitorBonus||"—")}</b></span>
      <span><small>CLOCK · ${esc(state.game.period)}</small>${ledSvg(state.game.clock,"bl-8bit-clock-led")}</span>
      <span class="bl-8bit-combined-timeouts"><small>TIMEOUTS</small><i>V ${timeoutDots(state.game.visitorTimeouts)}</i><i>H ${timeoutDots(state.game.homeTimeouts)}</i></span>
      <span><small>HOME BONUS</small><b>${esc(state.game.homeBonus||"—")}</b></span>
      <span><small>HOME FOULS</small>${ledSvg(state.game.homeFouls,"bl-8bit-small-led")}</span>
    </div>`;
  }

  function baseDiamond(bases) {
    const occupied = Array.isArray(bases) ? bases : [false,false,false];
    return `<span class="bl-8bit-bases" aria-label="Base occupancy"><i class="${occupied[1]?"on":""}"></i><i class="${occupied[2]?"on":""}"></i><i class="${occupied[0]?"on":""}"></i></span>`;
  }

  function diamondControls(state) {
    const game = state.game;
    const half = String(game.inningHalf || "TOP").toUpperCase().startsWith("B") ? "BOT" : "TOP";
    return `<div class="bl-8bit-diamond-control-bank">
      <span>${rheMarkup(state,"visitor")}</span>
      <span class="bl-8bit-count-pair"><small>BALLS</small>${ledSvg(game.balls,"bl-8bit-small-led")}<small>STRIKES</small>${ledSvg(game.strikes,"bl-8bit-small-led")}</span>
      <span><small>${half} INNING</small>${ledSvg(game.inning,"bl-8bit-inning-led")}</span>
      <span><small>BASES</small>${baseDiamond(game.bases)}</span>
      <span>${rheMarkup(state,"home")}</span>
      <span><small>OUTS</small>${ledSvg(game.outs,"bl-8bit-small-led")}</span>
    </div>`;
  }

  function boardMarkup(state, videoMode) {
    const sport = state.sport;
    const diamond = sport === "baseball" || sport === "softball";
    const visitorTower = sport === "football" ? footballTower(state,"visitor") : sport === "basketball" ? basketballTower(state,"visitor") : diamondTower(state,"visitor");
    const homeTower = sport === "football" ? footballTower(state,"home") : sport === "basketball" ? basketballTower(state,"home") : diamondTower(state,"home");
    const controls = sport === "football" ? footballControls(state) : sport === "basketball" ? basketballControls(state) : diamondControls(state);
    return `<div class="bl-scorebug bl-8bit-board bl-8bit-${sport}" data-scorebug-family="8-bit-gameday" data-video-mode="${videoMode}">
      <div class="bl-8bit-cabinet" aria-hidden="true"></div>
      <header class="bl-8bit-venue"><strong><b>${esc(formatGameDate(state.scheduledDate))}</b><span>${esc(gameDesignation(state))}</span></strong></header>
      <main class="bl-8bit-main-display">${visitorTower}<section class="bl-8bit-video-board" data-module="video.board">${videoContent(state,videoMode)}${state.captionsEnabled ? captionMarkup(state) : ""}</section>${homeTower}</main>
      ${controls}
    </div>`;
  }

  function tickerMarkup(state) {
    return `<div class="bl-8bit-top-ticker"><span class="bl-8bit-live">● LIVE</span>${ledSvg(state.ticker.text,"bl-8bit-ticker-led",{stretch:true})}<span class="bl-8bit-ticker-bug">CSRN</span></div>`;
  }

  function captionMarkup(state) {
    return `<div class="bl-8bit-caption"><strong>${esc(state.captions.speaker)}</strong><span>${esc(state.captions.text)}</span></div>`;
  }

  function videoModeFor(activeComponents, requested) {
    if (["clash","highlight","sponsor","player","broadcast"].includes(requested)) return requested;
    if (activeComponents.includes("highlightVideo")) return "highlight";
    if (activeComponents.includes("sponsor")) return "sponsor";
    if (activeComponents.includes("playerCard")) return "player";
    return "clash";
  }

  function componentNode(name, rect, markup, layer) {
    const node = document.createElement("section");
    node.className = `bl-component bl-${name}`;
    node.dataset.component = name;
    node.dataset.zone = name === "ticker" ? "stadium-top-ticker" : name === "captions" ? "caption-safe" : "stadium-board";
    Object.assign(node.style,{left:`${rect.x}px`,top:`${rect.y}px`,width:`${rect.w}px`,height:`${rect.h}px`,zIndex:String(layer)});
    node.innerHTML = markup;
    return node;
  }

  function renderPackage(root, packageId, sport = "football", value = {}, options = {}) {
    if (!root) throw new Error("8-Bit Gameday layout root is required.");
    if (packageId !== PACKAGE_ID) throw new Error(`Unknown 8-Bit Gameday package: ${packageId}`);
    if (!MANIFEST.sports[sport]) throw new Error(`Unsupported 8-Bit Gameday sport: ${sport}`);
    const state = normalizeState(value,sport);
    const activeComponents = [...new Set(options.activeComponents || base.scenarios.baseline)];
    const videoMode = videoModeFor(activeComponents,options.videoMode);
    const placements = {
      ticker:{component:"ticker",zone:"stadium-top-ticker",rect:{x:40,y:20,w:1840,h:62},layer:130},
      scorebug:{component:"scorebug",zone:"stadium-board",rect:{x:16,y:90,w:1888,h:958},layer:100}
    };
    state.captionsEnabled=activeComponents.includes("captions");
    root.replaceChildren();
    root.className = "csrn-broadcast-layout package-8bit-approved";
    root.dataset.package = PACKAGE_ID;
    root.dataset.sport = sport;
    root.dataset.engineVersion = VERSION;
    root.dataset.videoMode = videoMode;
    root.classList.toggle("diagnostics",Boolean(options.diagnostics));
    const homeColor=safeColor(state.home.primary,"#2787ff");
    const visitorColor=safeColor(state.visitor.primary,"#16ff83");
    const homeSecondary=safeColor(state.home.secondary,"#d7e8ff");
    const visitorSecondary=safeColor(state.visitor.secondary,"#f2f5f7");
    root.style.setProperty("--pixel-home",homeColor);
    root.style.setProperty("--pixel-visitor",visitorColor);
    root.style.setProperty("--pixel-home-secondary",homeSecondary);
    root.style.setProperty("--pixel-visitor-secondary",visitorSecondary);
    root.style.setProperty("--pixel-home-display",displayColor(homeColor,"#2787ff"));
    root.style.setProperty("--pixel-visitor-display",displayColor(visitorColor,"#16ff83"));
    root.appendChild(componentNode("ticker",placements.ticker.rect,tickerMarkup(state),130));
    root.appendChild(componentNode("scorebug",placements.scorebug.rect,boardMarkup(state,videoMode),100));
    const clashReady=paintClash(root,state).catch(error=>{root.dataset.clashError=error.message||String(error);throw error});
    root.dataset.ready = "true";
    return {packageId:PACKAGE_ID,sport,placements,components:activeComponents,videoMode,ready:clashReady};
  }

  function validateManifests() {
    const issues = [];
    for (const sport of ["football","basketball","baseball","softball"]) if (!MANIFEST.sports[sport]) issues.push(`missing ${sport}`);
    return issues;
  }

  window.CSRNEightBitGamedayEngine = Object.freeze({
    VERSION,
    packageId:PACKAGE_ID,
    manifests:Object.freeze({[PACKAGE_ID]:MANIFEST}),
    sports:base.sports,
    scenarios:base.scenarios,
    LED_GLYPHS,
    defaultState:base.defaultState,
    normalizeState,
    ledSvg,
    boardMarkup,
    renderPackage,
    validateManifests,
    auditRenderedScorebug:base.auditRenderedScorebug
  });
})();
