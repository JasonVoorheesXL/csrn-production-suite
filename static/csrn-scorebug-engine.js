(() => {
  "use strict";

  const PRESET_LAYOUTS = Object.freeze({
    classic_1980s: "classic",
    early_cable: "pixel",
    modern_network: "modern",
    minimal_radio: "minimal",
    heritage_press_box: "press",
    friday_night_stadium: "stadium",
    digital_neon: "neon",
    collegiate_traditional: "collegiate"
  });
  const RUNTIME_IDS = Object.freeze(["homeLogo","visitorLogo","homeName","visitorName","homeMascot","visitorMascot","homeRecord","visitorRecord","homeScore","visitorScore","quarter","clock","down","homePos","visitorPos"]);
  const SAMPLE = Object.freeze({
    home:{name:"HOME TEAM",mascot:"WILDCATS",record:"5-1",score:"21",logo:""},
    visitor:{name:"VISITOR",mascot:"PANTHERS",record:"4-2",score:"14",logo:""},
    quarter:"Q3",clock:"7:42",down:"1ST & 10"
  });
  const esc=(v)=>String(v??"").replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;").replaceAll("'","&#039;");
  const merge=(v={})=>({home:{...SAMPLE.home,...(v.home||{})},visitor:{...SAMPLE.visitor,...(v.visitor||{})},quarter:v.quarter??SAMPLE.quarter,clock:v.clock??SAMPLE.clock,down:v.down??SAMPLE.down});
  function current(root){
    const txt=(id,f)=>root.querySelector(`#${id}`)?.textContent?.trim()||f;
    const src=(id)=>root.querySelector(`#${id}`)?.getAttribute("src")||"";
    return merge({home:{name:txt("homeName",SAMPLE.home.name),mascot:txt("homeMascot",SAMPLE.home.mascot),record:txt("homeRecord",SAMPLE.home.record),score:txt("homeScore",SAMPLE.home.score),logo:src("homeLogo")},visitor:{name:txt("visitorName",SAMPLE.visitor.name),mascot:txt("visitorMascot",SAMPLE.visitor.mascot),record:txt("visitorRecord",SAMPLE.visitor.record),score:txt("visitorScore",SAMPLE.visitor.score),logo:src("visitorLogo")},quarter:txt("quarter",SAMPLE.quarter),clock:txt("clock",SAMPLE.clock),down:txt("down",SAMPLE.down)});
  }
  function logo(t,side,extra=""){
    const visible=Boolean(t.logo);
    return `<div class="logo-wrap ${extra}"><img id="${side}Logo" class="team-logo${visible?"":" hidden"}" src="${esc(t.logo)}" alt=""><span class="sb-monogram${visible?" hidden":""}">${esc(t.name.slice(0,1)||side.slice(0,1))}</span></div>`;
  }
  function identity(t,side,extra=""){
    return `<div class="name-wrap ${extra}"><div id="${side}Name" class="name">${esc(t.name)}</div><div id="${side}Mascot" class="mascot">${esc(t.mascot)}</div><div id="${side}Record" class="team-record">${esc(t.record)}</div></div>`;
  }
  const score=(t,side,extra="")=>`<div id="${side}Score" class="score ${extra}">${esc(t.score)}</div>`;
  const ball=(side)=>`<span id="${side}Pos" class="possession-ball hidden" aria-label="${side} possession">🏈</span>`;
  const game=(d,extra="")=>`<div class="center ${extra}"><div class="topline"><div id="quarter" class="quarter">${esc(d.quarter)}</div><div id="clock" class="clock">${esc(d.clock)}</div></div><div id="down" class="down">${esc(d.down)}</div></div>`;

  function modern(d){return `<section class="team home modern-team">${logo(d.home,"home")}${identity(d.home,"home")}${score(d.home,"home")}${ball("home")}</section>${game(d,"modern-center")}<section class="team visitor modern-team">${score(d.visitor,"visitor")}${identity(d.visitor,"visitor","align-right")}${logo(d.visitor,"visitor")}${ball("visitor")}</section>`;}
  function classic(d){return `<section class="team home classic-team">${identity(d.home,"home")}${logo(d.home,"home")}${ball("home")}</section>${score(d.home,"home","classic-score")}${game(d,"classic-center")}${score(d.visitor,"visitor","classic-score")}<section class="team visitor classic-team">${logo(d.visitor,"visitor")}${identity(d.visitor,"visitor","align-right")}${ball("visitor")}</section>`;}
  function pixel(d){return `<div class="pixel-board"><div class="pixel-title">8-BIT GAMEDAY</div><section class="pixel-team pixel-home">${logo(d.home,"home","pixel-logo")}${identity(d.home,"home")}${score(d.home,"home","pixel-score")}${ball("home")}</section><div class="pixel-state">${game(d,"pixel-center")}</div><section class="pixel-team pixel-visitor">${score(d.visitor,"visitor","pixel-score")}${identity(d.visitor,"visitor","align-right")}${logo(d.visitor,"visitor","pixel-logo")}${ball("visitor")}</section><div class="pixel-turf" aria-hidden="true"></div></div>`;}
  function minimalIdentity(t,side){return `<div class="name-wrap minimal-identity"><div id="${side}Name" class="name">${esc(t.name)}</div><div id="${side}Mascot" class="mascot hidden"></div><div id="${side}Record" class="team-record hidden"></div></div>`;}
  function minimal(d){return `<div class="minimal-stack"><section class="minimal-row home">${minimalIdentity(d.home,"home")}${score(d.home,"home")}${ball("home")}</section><section class="minimal-row visitor">${minimalIdentity(d.visitor,"visitor")}${score(d.visitor,"visitor")}${ball("visitor")}</section></div>${game(d,"minimal-center")}<img id="homeLogo" class="team-logo hidden" alt=""><img id="visitorLogo" class="team-logo hidden" alt="">`;}
  function press(d){return `<div class="press-sheet"><div class="press-kicker">GAME NIGHT EDITION</div><section class="press-team press-home">${logo(d.home,"home")}${identity(d.home,"home")}${ball("home")}</section><div class="press-scoreline">${score(d.home,"home")}<div class="press-versus">FINAL<br>EDITION</div>${score(d.visitor,"visitor")}</div><section class="press-team press-visitor">${identity(d.visitor,"visitor","align-right")}${logo(d.visitor,"visitor")}${ball("visitor")}</section>${game(d,"press-center")}</div>`;}
  function stadium(d){return `<div class="stadium-board"><div class="stadium-brand">FRIDAY NIGHT SCOREBOARD</div><div class="stadium-label home-caption">HOME</div><div class="stadium-label visitor-caption">GUEST</div>${score(d.home,"home","stadium-score home-led")}${score(d.visitor,"visitor","stadium-score visitor-led")}<div class="stadium-clock-label">TIME</div><div class="stadium-clock" id="clock">${esc(d.clock)}</div><div class="stadium-quarter-label">QTR</div><div class="stadium-quarter" id="quarter">${esc(String(d.quarter).replace(/^Q/i,""))}</div><div class="stadium-down-label">DOWN / TO GO</div><div class="stadium-down" id="down">${esc(d.down)}</div><div id="homeName" class="stadium-name home-name">${esc(d.home.name)}</div><div id="visitorName" class="stadium-name visitor-name">${esc(d.visitor.name)}</div><div id="homeMascot" class="mascot hidden"></div><div id="visitorMascot" class="mascot hidden"></div><div id="homeRecord" class="team-record hidden"></div><div id="visitorRecord" class="team-record hidden"></div><img id="homeLogo" class="team-logo hidden" alt=""><img id="visitorLogo" class="team-logo hidden" alt="">${ball("home")}${ball("visitor")}</div>`;}
  function neon(d){return `<section class="neon-wing neon-home">${score(d.home,"home","neon-score")}${identity(d.home,"home")}${logo(d.home,"home","neon-logo")}${ball("home")}</section>${game(d,"neon-center")}<section class="neon-wing neon-visitor">${logo(d.visitor,"visitor","neon-logo")}${identity(d.visitor,"visitor","align-right")}${score(d.visitor,"visitor","neon-score")}${ball("visitor")}</section>`;}
  function collegiate(d){return `<section class="college-crest college-home">${logo(d.home,"home","college-logo")}${identity(d.home,"home")}${ball("home")}</section>${score(d.home,"home","college-score")}${game(d,"college-center")}${score(d.visitor,"visitor","college-score")}<section class="college-crest college-visitor">${identity(d.visitor,"visitor","align-right")}${logo(d.visitor,"visitor","college-logo")}${ball("visitor")}</section>`;}
  const RENDERERS=Object.freeze({modern,classic,pixel,minimal,press,stadium,neon,collegiate});
  function normalize(layout){const x=PRESET_LAYOUTS[layout]||layout||"modern";return RENDERERS[x]?x:"modern";}
  function render(root,layout,value=null){if(!root)throw new Error("Scorebug root is required.");const data=value?merge(value):current(root);const keep=[...root.classList].filter(x=>x==="hidden"||x==="graphic-mode");const resolved=normalize(layout);root.className=["csrn-scorebug",`layout-${resolved}`,...keep].join(" ");root.dataset.layout=resolved;root.innerHTML=RENDERERS[resolved](data);root.dataset.rendered="true";return resolved;}
  window.CSRNScorebugEngine=Object.freeze({render,normalize,sample:()=>merge(),presetLayouts:PRESET_LAYOUTS,runtimeIds:RUNTIME_IDS});
})();