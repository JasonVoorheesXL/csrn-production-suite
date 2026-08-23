(() => {
  "use strict";

  const VERSION = "1.5.0";
  const PACKAGE_ID = "friday_night_stadium";
  const base = window.CSRNBroadcastLayoutEngine;
  if (!base) throw new Error("Friday Night Stadium requires the Broadcast Layout Engine.");

  const MANIFEST = Object.freeze({
    id: PACKAGE_ID,
    name: "Friday Night Stadium",
    styleClass: "package-stadium-approved",
    engine: "CSRNFridayNightStadiumEngine",
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
    return `<svg class="bl-fns-led ${esc(className)}" viewBox="0 0 ${width} 7" role="img" aria-label="${esc(text.trim())}" preserveAspectRatio="${options.stretch ? "none" : "xMidYMid meet"}"><g>${dots.join("")}</g></svg>`;
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
    return state;
  }

  function teamLogo(team, side, large = false) {
    const label = team.shortName || team.name || side;
    return `<div class="bl-fns-logo ${large ? "bl-fns-logo-large" : ""}" data-module="${side}.logo">${team.logo ? `<img src="${esc(team.logo)}" alt="${esc(label)} logo">` : `<span>${esc(label.slice(0,1).toUpperCase())}</span>`}</div>`;
  }

  function teamDisplayName(team, limit = 16) {
    const full = String(team.name || team.shortName || "TEAM").trim();
    const short = String(team.shortName || "").trim();
    return full.length <= limit ? full : short && short.length < full.length ? short : full;
  }

  function venueName(home, sport) {
    const school = String(home.name || home.shortName || "HOME").trim();
    const mascot = String(home.mascot || "").trim();
    const combined = [school, mascot].filter(Boolean).join(" ");
    const suffix = sport === "basketball" ? "ARENA" : sport === "baseball" || sport === "softball" ? "BALLPARK" : "STADIUM";
    return `${combined.length <= 24 ? combined : school} ${suffix}`;
  }

  function identityPlate(team, side) {
    return `<div class="bl-fns-identity-plate" data-module="${side}.identity"><strong>${esc(teamDisplayName(team))}</strong><span>${esc(team.mascot || team.shortName)}</span></div>`;
  }

  function possessionBall(sport, active) {
    if (!active) return `<span class="bl-fns-possession-ball is-empty" aria-hidden="true"></span>`;
    if (sport === "basketball") return `<span class="bl-fns-possession-ball bl-fns-basketball-possession" aria-label="Possession"><svg viewBox="0 0 64 64" aria-hidden="true"><circle cx="32" cy="32" r="27"/><path d="M5 32h54M32 5c-12 12-12 42 0 54M32 5c12 12 12 42 0 54M12 15c13 8 27 8 40 0M12 49c13-8 27-8 40 0"/></svg></span>`;
    return `<span class="bl-fns-possession-ball bl-fns-football-possession" aria-label="Possession"><svg viewBox="0 0 72 44" aria-hidden="true"><path d="M4 22C13 3 55 3 68 22 55 41 13 41 4 22Z"/><path d="M36 7v30M25 22h22M29 16l14 12M43 16 29 28"/></svg></span>`;
  }

  function scoreDisplay(team, side, sport, state, role = "") {
    const scoreText = clampScore(team.score);
    const fixedScore = sport === "basketball" ? scoreText.padStart(3," ") : scoreText.padStart(2," ");
    const possession = state.game.possession === side;
    const marker = sport === "football" ? possessionBall(sport,possession) : "";
    return `<div class="bl-fns-score" data-module="${side}.score" data-led-capacity="${sport === "basketball" ? "3" : "2"}">${ledSvg(fixedScore,"bl-fns-score-led")}${marker}${role}</div>`;
  }

  function footballTower(state, side) {
    const team=state[side];
    return `<aside class="bl-fns-team-tower bl-fns-football-tower bl-fns-${side}" data-module="${side}.team">
      <div class="bl-fns-side-label">${side === "home" ? "HOME" : "VISITOR"}</div>
      ${scoreDisplay(team,side,"football",state)}
      ${identityPlate(team,side)}
      ${teamLogo(team,side)}
    </aside>`;
  }

  function basketballTower(state, side) {
    const team=state[side];
    return `<aside class="bl-fns-team-tower bl-fns-basketball-tower bl-fns-${side}" data-module="${side}.team">
      <div class="bl-fns-side-label">${side === "home" ? "HOME" : "VISITOR"}</div>
      ${scoreDisplay(team,side,"basketball",state)}
      ${identityPlate(team,side)}
      ${teamLogo(team,side)}
    </aside>`;
  }

  function diamondTower(state, side) {
    const team=state[side];
    return `<aside class="bl-fns-team-tower bl-fns-diamond-tower bl-fns-${side}" data-module="${side}.team">
      <div class="bl-fns-side-label">${side === "home" ? "HOME" : "VISITOR"}</div>
      ${scoreDisplay(team,side,state.sport,state,`<span class="bl-fns-diamond-role"><small>${side === "visitor" ? "AT BAT" : "PITCHER"}</small><b>${esc(side === "visitor" ? state.game.batterName : state.game.pitcherName)}</b></span>`)}
      ${identityPlate(team,side)}
      ${teamLogo(team,side)}
    </aside>`;
  }

  function rheMarkup(state, side) {
    const team=state[side];
    return `<div class="bl-fns-rhe bl-fns-rhe-${side}" data-rhe-side="${side}"><span>R<b>${ledSvg(clampScore(team.score),"bl-fns-rhe-led")}</b></span><span>H<b>${ledSvg(state.game[`${side}Hits`],"bl-fns-rhe-led")}</b></span><span>E<b>${ledSvg(state.game[`${side}Errors`],"bl-fns-rhe-led")}</b></span></div>`;
  }

  const CLASH_ART = Object.freeze({
    football:"/static/friday-night-stadium/clash/football-athletes-keyed.png",
    basketball:"/static/friday-night-stadium/clash/basketball-athletes-keyed.png",
    baseball:"/static/friday-night-stadium/clash/baseball-athletes-keyed.png",
    softball:"/static/friday-night-stadium/clash/softball-athletes-keyed.png"
  });

  const CLASH_BACKDROPS = Object.freeze({
    football:"/static/friday-night-stadium/clash/football-field-background.png",
    basketball:"/static/friday-night-stadium/clash/basketball-court-background.png",
    baseball:"/static/friday-night-stadium/clash/baseball-ballpark-background.png",
    softball:"/static/friday-night-stadium/clash/softball-ballpark-background.png"
  });

  const FOOTBALL_PLAYER_BASE = "/static/friday-night-stadium/players/palette-v2";
  const FOOTBALL_PLAYER_PALETTES = Object.freeze([
    {slug:"scarlet",hex:"#c1121f"},{slug:"maroon",hex:"#7f1d1d"},{slug:"orange",hex:"#f97316"},
    {slug:"gold",hex:"#d4a017"},{slug:"yellow",hex:"#facc15"},{slug:"kelly-green",hex:"#16a34a"},
    {slug:"dark-green",hex:"#14532d"},{slug:"royal-blue",hex:"#2563eb"},{slug:"navy",hex:"#1e3a8a"},
    {slug:"columbia-blue",hex:"#7dd3fc"},{slug:"purple",hex:"#7e22ce"},{slug:"black",hex:"#111827"},
    {slug:"charcoal",hex:"#374151"},{slug:"white",hex:"#f8fafc"}
  ]);

  function rgbFromHex(value, fallback) {
    const match=String(value||"").trim().match(/^#([0-9a-f]{6})$/i);
    const hex=match ? match[1] : fallback.replace("#","");
    return [parseInt(hex.slice(0,2),16),parseInt(hex.slice(2,4),16),parseInt(hex.slice(4,6),16)];
  }

  function footballPaletteSlug(team, fallback) {
    const color=safeColor(team?.primary,fallback);
    const [r,g,b]=rgbFromHex(color,fallback);
    const secondary=String(team?.secondary||team?.accent||team?.trim||"").toLowerCase();
    if(r<36&&g<36&&b<36&&/(gold|yellow|#d4a017|#facc15|#ffb000|#ffd700)/i.test(secondary))return "black-gold";
    return FOOTBALL_PLAYER_PALETTES.reduce((best,palette)=>{
      const [pr,pg,pb]=rgbFromHex(palette.hex,"#111827");
      const distance=(r-pr)**2+(g-pg)**2+(b-pb)**2;
      return distance<best.distance?{slug:palette.slug,distance}:best;
    },{slug:"navy",distance:Infinity}).slug;
  }

  function loadClashImage(src) {
    return new Promise((resolve,reject)=>{
      const image=new Image();
      image.onload=()=>resolve(image);
      image.onerror=()=>reject(new Error(`Clash artwork failed: ${src}`));
      image.src=src;
    });
  }

  function visibleImageBounds(image) {
    const width=image.naturalWidth || image.width,height=image.naturalHeight || image.height;
    const probe=document.createElement("canvas");
    probe.width=width;probe.height=height;
    const probeContext=probe.getContext("2d",{willReadFrequently:true});
    probeContext.drawImage(image,0,0);
    const pixels=probeContext.getImageData(0,0,width,height).data;
    let left=width,top=height,right=0,bottom=0;
    for(let y=0;y<height;y+=1){
      for(let x=0;x<width;x+=1){
        if(pixels[(y*width+x)*4+3]<12)continue;
        if(x<left)left=x;if(x>right)right=x;if(y<top)top=y;if(y>bottom)bottom=y;
      }
    }
    if(left>right||top>bottom)return {x:0,y:0,width,height};
    const pad=Math.round(Math.max(width,height)*.035);
    left=Math.max(0,left-pad);top=Math.max(0,top-pad);right=Math.min(width-1,right+pad);bottom=Math.min(height-1,bottom+pad);
    return {x:left,y:top,width:right-left+1,height:bottom-top+1};
  }

  function drawPlayerAt(context, image, placement) {
    const source=visibleImageBounds(image);
    const targetHeight=placement.height,targetWidth=targetHeight*(source.width/source.height);
    context.drawImage(image,source.x,source.y,source.width,source.height,placement.centerX-targetWidth/2,placement.bottomY-targetHeight,targetWidth,targetHeight);
  }

  function paintFootballPlayers(canvas, state) {
    canvas.width=1920;canvas.height=1080;
    const visitorSlug=footballPaletteSlug(state.visitor,"#16a34a");
    const homeSlug=footballPaletteSlug(state.home,"#1e3a8a");
    const visitorSrc=`${FOOTBALL_PLAYER_BASE}/visitor/visitor-28-${visitorSlug}.png`;
    const homeSrc=`${FOOTBALL_PLAYER_BASE}/home/home-31-${homeSlug}.png`;
    canvas.dataset.clashAsset=`${visitorSrc}|${homeSrc}`;
    return Promise.all([loadClashImage(visitorSrc),loadClashImage(homeSrc)]).then(([visitorImage,homeImage])=>{
      const context=canvas.getContext("2d");
      context.clearRect(0,0,canvas.width,canvas.height);
      const playerHeight=canvas.height*.76;
      drawPlayerAt(context,visitorImage,{centerX:canvas.width*.178,bottomY:canvas.height*.76,height:playerHeight});
      drawPlayerAt(context,homeImage,{centerX:canvas.width*.822,bottomY:canvas.height*.76,height:playerHeight});
      canvas.dataset.artReady="true";
    });
  }

  function recolorUniformPixels(data, visitorColor, homeColor) {
    const visitor=rgbFromHex(visitorColor,"#16ff83"),home=rgbFromHex(homeColor,"#2787ff");
    for(let index=0;index<data.length;index+=4){
      if(data[index+3]===0)continue;
      const r=data[index],g=data[index+1],b=data[index+2];
      const cyan=b>90&&g>75&&b>r*1.28&&g>r*1.22&&b/g>.68&&b/g<2.35;
      const magenta=r>95&&b>70&&r>g*1.28&&b>g*1.22&&r/b>.62&&r/b<2.25;
      if(!cyan&&!magenta)continue;
      const source=cyan?[0,174,239]:[255,0,255],target=cyan?visitor:home;
      const sourceLuma=.2126*source[0]+.7152*source[1]+.0722*source[2];
      const pixelLuma=.2126*r+.7152*g+.0722*b;
      const scale=Math.max(.22,Math.min(1.9,pixelLuma/Math.max(sourceLuma,1)));
      for(let channel=0;channel<3;channel++){
        const base=target[channel]*Math.min(scale,1);
        const highlight=scale>1?(255-target[channel])*(scale-1)*.72:0;
        data[index+channel]=Math.max(0,Math.min(255,Math.round(base+highlight)));
      }
    }
    return data;
  }

  function paintClash(root, state) {
    const canvas=root.querySelector(".bl-fns-clash-art");
    if(!canvas)return Promise.resolve();
    canvas.dataset.artReady="pending";
    if(state.sport==="football"){
      return paintFootballPlayers(canvas,state).catch(error=>{canvas.dataset.artReady="false";throw error});
    }
    return new Promise((resolve,reject)=>{
      const image=new Image();
      image.onload=()=>{
        try{
          canvas.width=image.naturalWidth;canvas.height=image.naturalHeight;
          const context=canvas.getContext("2d",{willReadFrequently:true});
          context.clearRect(0,0,canvas.width,canvas.height);context.drawImage(image,0,0);
          const pixels=context.getImageData(0,0,canvas.width,canvas.height);
          recolorUniformPixels(pixels.data,displayColor(safeColor(state.visitor.primary,"#16ff83"),"#16ff83"),displayColor(safeColor(state.home.primary,"#2787ff"),"#2787ff"));
          context.putImageData(pixels,0,0);canvas.dataset.artReady="true";resolve();
        }catch(error){canvas.dataset.artReady="false";reject(error)}
      };
      image.onerror=()=>{canvas.dataset.artReady="false";reject(new Error(`Clash artwork failed: ${state.sport}`))};
      image.src=CLASH_ART[state.sport];
    });
  }

  function clashContent(state) {
    const sport=state.sport;
    return `<div class="bl-fns-clash bl-fns-clash-${sport}" data-video-mode="clash" data-clash-sport="${sport}">
      <img class="bl-fns-field-art" src="${CLASH_BACKDROPS[sport]}" data-field-asset="${CLASH_BACKDROPS[sport]}" alt="" aria-hidden="true">
      <canvas class="bl-fns-clash-art" data-clash-asset="${CLASH_ART[sport]}" aria-label="${esc(state.visitor.name)} versus ${esc(state.home.name)}"></canvas>
      <div class="bl-fns-clash-side bl-fns-clash-visitor"><strong>${esc(state.visitor.name)}</strong><span>${esc(state.visitor.mascot)}</span></div>
      <div class="bl-fns-versus"><img src="/static/friday-night-stadium/vs-lightning-silver.png" alt="versus"></div>
      <div class="bl-fns-clash-side bl-fns-clash-home"><strong>${esc(state.home.name)}</strong><span>${esc(state.home.mascot)}</span></div>
    </div>`;
  }

  function videoContent(state, mode) {
    if (mode === "highlight") return `<div class="bl-fns-video-replacement" data-video-mode="highlight"><div class="bl-fns-video-feed">VIDEO</div><strong>${esc(state.highlight.title)}</strong><span>${esc(state.highlight.detail)}</span></div>`;
    if (mode === "sponsor") return `<div class="bl-fns-video-replacement bl-fns-sponsor-replacement" data-video-mode="sponsor">${state.sponsor.logo ? `<img src="${esc(state.sponsor.logo)}" alt="">` : ""}<small>PRESENTED BY</small><strong>${esc(state.sponsor.name)}</strong><span>${esc(state.sponsor.line)}</span></div>`;
    if (mode === "player") return `<div class="bl-fns-video-replacement bl-fns-player-replacement" data-video-mode="player"><div class="bl-fns-player-portrait">${state.player.headshot ? `<img src="${esc(state.player.headshot)}" alt="">` : `<b>#${esc(state.player.number)}</b>`}</div><small>PLAYER SPOTLIGHT</small><strong>${esc(state.player.name)}</strong><span>${esc(state.player.position)} · ${esc(state.player.detail)}</span></div>`;
    if (mode === "broadcast") return `<div class="bl-fns-video-replacement bl-fns-broadcast-replacement" data-video-mode="broadcast"><div class="bl-fns-video-feed">LIVE VIDEO</div></div>`;
    return clashContent(state);
  }

  function timeoutDots(value) {
    const count = Math.max(0, Math.min(5, Number(value) || 0));
    return `<span class="bl-fns-timeouts" aria-label="${count} timeouts">${Array.from({length:4},(_,i)=>`<i class="${i<count?"on":""}"></i>`).join("")}</span>`;
  }

  function footballControls(state) {
    const match=String(state.game.downDistance||"").match(/(\d+)[A-Z]*\s*&\s*(\d+)/i);
    const down=match?.[1]||"3";const toGo=match?.[2]||"7";
    return `<div class="bl-fns-football-control-bank">
      <div class="bl-fns-primary-clock">${ledSvg(state.game.clock,"bl-fns-clock-led")}</div>
      <div class="bl-fns-football-bottom">
        <span><small>DOWN</small>${ledSvg(down,"bl-fns-small-led")}</span><span><small>TO GO</small>${ledSvg(toGo,"bl-fns-small-led")}</span><span><small>BALL ON</small>${ledSvg(state.game.ballOn||"28","bl-fns-small-led")}</span><span><small>QUARTER</small>${ledSvg(String(state.game.period).replace(/\D/g,"")||"2","bl-fns-small-led")}</span>
      </div>
    </div>`;
  }

  function basketballControls(state) {
    return `<div class="bl-fns-basketball-control-bank">
      <div class="bl-fns-basketball-clock">${ledSvg(state.game.clock,"bl-fns-clock-led")}<strong>${esc(state.game.period)}</strong></div>
      <div class="bl-fns-basketball-bottom">
        <span><small>FOULS</small>${ledSvg(state.game.visitorFouls,"bl-fns-small-led")}</span><span><small>BONUS</small><b>${esc(state.game.visitorBonus||"—")}</b></span><span class="bl-fns-timeout-cell bl-fns-timeout-visitor"><small>◀ TIMEOUTS</small>${timeoutDots(state.game.visitorTimeouts)}</span><span class="bl-fns-timeout-cell bl-fns-timeout-home">${timeoutDots(state.game.homeTimeouts)}<small>TIMEOUTS ▶</small></span><span><small>DOUBLE BONUS</small><b>${esc(state.game.homeBonus||"—")}</b></span><span><small>FOULS</small>${ledSvg(state.game.homeFouls,"bl-fns-small-led")}</span>
      </div>
    </div>`;
  }

  function baseDiamond(bases) {
    const occupied = Array.isArray(bases) ? bases : [false,false,false];
    return `<span class="bl-fns-bases" aria-label="Base occupancy"><i class="${occupied[1]?"on":""}"></i><i class="${occupied[2]?"on":""}"></i><i class="${occupied[0]?"on":""}"></i></span>`;
  }

  function diamondControls(state) {
    const game = state.game;
    const half = String(game.inningHalf || "TOP").toUpperCase().startsWith("B") ? "BOT" : "TOP";
    return `<div class="bl-fns-diamond-control-bank">
      <div class="bl-fns-diamond-center">${rheMarkup(state,"visitor")}<strong aria-label="INNING">${ledSvg(`${half} ${game.inning}`,"bl-fns-inning-led")}</strong><span class="bl-fns-role-bases">${baseDiamond(game.bases)}</span>${rheMarkup(state,"home")}</div>
      <div class="bl-fns-diamond-bottom"><span><small>BALLS</small>${ledSvg(game.balls,"bl-fns-small-led")}</span><span><small>STRIKES</small>${ledSvg(game.strikes,"bl-fns-small-led")}</span><span><small>OUTS</small>${ledSvg(game.outs,"bl-fns-small-led")}</span></div>
    </div>`;
  }

  function boardMarkup(state, videoMode) {
    const sport = state.sport;
    const diamond = sport === "baseball" || sport === "softball";
    const visitorTower = sport === "football" ? footballTower(state,"visitor") : sport === "basketball" ? basketballTower(state,"visitor") : diamondTower(state,"visitor");
    const homeTower = sport === "football" ? footballTower(state,"home") : sport === "basketball" ? basketballTower(state,"home") : diamondTower(state,"home");
    const controls = sport === "football" ? footballControls(state) : sport === "basketball" ? basketballControls(state) : diamondControls(state);
    return `<div class="bl-scorebug bl-fns-board bl-fns-${sport}" data-scorebug-family="friday-night-stadium" data-video-mode="${videoMode}">
      <div class="bl-fns-cabinet" aria-hidden="true"></div>
      <header class="bl-fns-venue"><i></i><strong>${esc(venueName(state.home,sport))}</strong><i></i></header>
      <main class="bl-fns-main-display">${visitorTower}<section class="bl-fns-video-board" data-module="video.board">${videoContent(state,videoMode)}${state.captionsEnabled ? captionMarkup(state) : ""}</section>${homeTower}</main>
      ${controls}
    </div>`;
  }

  function tickerMarkup(state) {
    return `<div class="bl-fns-top-ticker"><span class="bl-fns-live">● LIVE</span>${ledSvg(state.ticker.text,"bl-fns-ticker-led",{stretch:true})}<span class="bl-fns-ticker-bug">CSRN</span></div>`;
  }

  function captionMarkup(state) {
    return `<div class="bl-fns-caption"><strong>${esc(state.captions.speaker)}</strong><span>${esc(state.captions.text)}</span></div>`;
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
    if (!root) throw new Error("Friday Night Stadium layout root is required.");
    if (packageId !== PACKAGE_ID) throw new Error(`Unknown Friday Night Stadium package: ${packageId}`);
    if (!MANIFEST.sports[sport]) throw new Error(`Unsupported Friday Night Stadium sport: ${sport}`);
    const state = normalizeState(value,sport);
    const activeComponents = [...new Set(options.activeComponents || base.scenarios.baseline)];
    const videoMode = videoModeFor(activeComponents,options.videoMode);
    const placements = {
      ticker:{component:"ticker",zone:"stadium-top-ticker",rect:{x:40,y:20,w:1840,h:62},layer:130},
      scorebug:{component:"scorebug",zone:"stadium-board",rect:{x:16,y:90,w:1888,h:958},layer:100}
    };
    state.captionsEnabled=activeComponents.includes("captions");
    root.replaceChildren();
    root.className = "csrn-broadcast-layout package-stadium-approved";
    root.dataset.package = PACKAGE_ID;
    root.dataset.sport = sport;
    root.dataset.engineVersion = VERSION;
    root.dataset.videoMode = videoMode;
    root.classList.toggle("diagnostics",Boolean(options.diagnostics));
    const homeColor=safeColor(state.home.primary,"#2787ff");
    const visitorColor=safeColor(state.visitor.primary,"#16ff83");
    root.style.setProperty("--fns-home",homeColor);
    root.style.setProperty("--fns-visitor",visitorColor);
    root.style.setProperty("--fns-home-display",displayColor(homeColor,"#2787ff"));
    root.style.setProperty("--fns-visitor-display",displayColor(visitorColor,"#16ff83"));
    root.appendChild(componentNode("ticker",placements.ticker.rect,tickerMarkup(state),130));
    root.appendChild(componentNode("scorebug",placements.scorebug.rect,boardMarkup(state,videoMode),100));
    const clashReady=videoMode==="clash"
      ? paintClash(root,state).catch(error=>{root.dataset.clashError=error.message||String(error);throw error})
      : Promise.resolve();
    root.dataset.ready = "true";
    return {packageId:PACKAGE_ID,sport,placements,components:activeComponents,videoMode,ready:clashReady};
  }

  function validateManifests() {
    const issues = [];
    for (const sport of ["football","basketball","baseball","softball"]) if (!MANIFEST.sports[sport]) issues.push(`missing ${sport}`);
    return issues;
  }

  window.CSRNFridayNightStadiumEngine = Object.freeze({
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
