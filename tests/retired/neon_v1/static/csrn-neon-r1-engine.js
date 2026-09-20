(() => {
  "use strict";
  const VERSION="1.0.0-r1";
  const PACKAGE_ID="digital_neon";
  const base=window.CSRNBroadcastLayoutEngine;
  if(!base)throw new Error("Neon R1 requires the Broadcast Layout Engine.");
  const ASSETS=Object.freeze({
    frame:"/static/neon-r1/neon-r1-frame.svg",
    football:"/static/neon-r1/neon-r1-football-clash.png",
    basketball:"/static/neon-r1/neon-r1-basketball-clash.png",
    baseball:"/static/neon-r1/neon-r1-baseball-clash.png",
    softball:"/static/neon-r1/neon-r1-softball-clash.png"
  });
  const MANIFEST=Object.freeze({id:PACKAGE_ID,name:"Neon Sports Network R1",styleClass:"package-neon-r1",sports:Object.freeze({football:true,basketball:true,baseball:true,softball:true})});
  const esc=v=>String(v??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[c]);
  const clean=(v,f="—")=>String(v??"").trim()||f;
  const safeColor=(v,f)=>/^#[0-9a-f]{6}$/i.test(String(v||""))?String(v):f;
  function initials(name){
    const words=clean(name,"TEAM").replace(/[^A-Za-z0-9 ]+/g," ").trim().split(/\s+/).filter(Boolean);
    if(words.length<=1)return (words[0]||"T").slice(0,1).toUpperCase();
    return words.slice(0,3).map(w=>w[0]).join("").toUpperCase();
  }
  function normalize(value={},sport="football"){
    const f=base.defaultState();
    const s={...f,...value,sport,home:{...f.home,...(value.home||{})},visitor:{...f.visitor,...(value.visitor||{})},game:{...f.game,...(value.game||{})},player:{...f.player,...(value.player||{})},sponsor:{...f.sponsor,...(value.sponsor||{})},highlight:{...f.highlight,...(value.highlight||{})},captions:{...f.captions,...(value.captions||{})},ticker:{...f.ticker,...(value.ticker||{})}};
    const requested=clean(value.broadcastPrimaryTeamName||value.primaryTeamName||value.primary_team_name,"").toLowerCase();
    s.featuredSide=requested&&clean(s.visitor.name,"").toLowerCase()===requested?"visitor":"home";
    if(requested&&clean(s.home.name,"").toLowerCase()!==requested&&clean(s.visitor.name,"").toLowerCase()!==requested)s.featuredSide="home";
    return s;
  }
  function teamVars(state){
    const hp=safeColor(state.home.primary,"#b5121b"),hs=safeColor(state.home.secondary,"#f5f5f5");
    const vp=safeColor(state.visitor.primary,"#2563eb"),vs=safeColor(state.visitor.secondary,"#f5f5f5");
    return `--nr-home:${hp};--nr-home2:${hs};--nr-visitor:${vp};--nr-visitor2:${vs};--nr-frame:url('${ASSETS.frame}');--nr-clash:url('${ASSETS[state.sport]}')`;
  }
  function diamondState(s){
    const g=s.game,half=clean(g.inningHalf,"TOP"),inn=clean(g.inning,"1");
    const bases=Array.isArray(g.bases)?g.bases:[false,false,false];
    return `<div class="nr-diamond-state"><b>${esc(half)} ${esc(inn)}</b><span>${esc(g.balls||0)} BALLS</span><span>${esc(g.strikes||0)} STRIKES</span><span>${esc(g.outs||0)} OUTS</span><i class="${bases[0]?"on":""}"></i><i class="${bases[1]?"on":""}"></i><i class="${bases[2]?"on":""}"></i></div>`;
  }
  function gameState(s){
    if(s.sport==="baseball"||s.sport==="softball")return diamondState(s);
    if(s.sport==="basketball")return `<div class="nr-clock"><strong>${esc(s.game.clock)}</strong><span>${esc(s.game.period)}</span><em>${esc(s.game.shotClock||"")}</em></div>`;
    return `<div class="nr-clock"><strong>${esc(s.game.clock)}</strong><span>${esc(s.game.period)}</span><b>${esc(s.game.downDistance)}</b></div>`;
  }
  function openingContent(s,active){
    if(active.includes("sponsor"))return `<div class="nr-feature nr-sponsor"><small>SPONSOR SPOTLIGHT</small><strong>${esc(s.sponsor.name)}</strong><span>${esc(s.sponsor.line)}</span></div>`;
    if(active.includes("playerCard"))return `<div class="nr-feature"><small>PLAYER SPOTLIGHT</small><strong>${esc(s.player.name)}</strong><span>${esc(s.player.position)} · ${esc(s.player.detail)}</span></div>`;
    if(active.includes("highlightVideo"))return `<div class="nr-feature nr-highlight"><small>${esc(s.highlight.title)}</small><strong>${esc(s.highlight.detail)}</strong></div>`;
    return `<div class="nr-live-label"><b>LIVE VIDEO OPENING</b><span>${esc(s.sport.toUpperCase())} CLASH PLATE</span></div>`;
  }
  function renderPackage(root,packageId,sport="football",value={},options={}){
    if(packageId!==PACKAGE_ID)throw new Error(`Neon R1 cannot render ${packageId}`);
    const s=normalize(value,sport),active=options.activeComponents||base.scenarios.baseline;
    const captions=active.includes("captions")?`<div class="nr-captions"><b>${esc(s.captions.speaker)}</b><span>${esc(s.captions.text)}</span></div>`:"";
    root.replaceChildren();root.className="csrn-broadcast-layout package-neon-r1";root.dataset.package=PACKAGE_ID;root.dataset.sport=sport;root.dataset.engineVersion=VERSION;root.dataset.ready="true";
    root.innerHTML=`<section class="nr-page" style="${teamVars(s)}" data-neon-r1="page">
      <div class="nr-frame" aria-hidden="true"></div>
      <header class="nr-ticker" data-component="ticker"><strong>NEON SPORTS NETWORK</strong><span>${esc(s.ticker.text)}</span></header>
      <aside class="nr-team nr-home"><div class="nr-initial">${esc(initials(s.home.name))}</div><h2>${esc(s.home.name)}</h2><h3>${esc(s.home.mascot)}</h3><p>${esc(s.home.record)}</p></aside>
      <main class="nr-opening" data-module="video.board"><div class="nr-clash"></div><div class="nr-colorwash"></div>${openingContent(s,active)}${captions}</main>
      <aside class="nr-team nr-visitor"><div class="nr-initial">${esc(initials(s.visitor.name))}</div><h2>${esc(s.visitor.name)}</h2><h3>${esc(s.visitor.mascot)}</h3><p>${esc(s.visitor.record)}</p></aside>
      <footer class="nr-scorebug" data-component="scorebug">
        <div class="nr-score-side nr-score-home"><span>${esc(initials(s.home.name))}</span><strong>${esc(s.home.score)}</strong><b>${esc(s.home.name)}</b></div>
        ${gameState(s)}
        <div class="nr-score-side nr-score-visitor"><strong>${esc(s.visitor.score)}</strong><span>${esc(initials(s.visitor.name))}</span><b>${esc(s.visitor.name)}</b></div>
      </footer>
    </section>`;
    return {packageId:PACKAGE_ID,sport,placements:{scorebug:{component:"scorebug",zone:"bottom",layer:100,rect:{x:40,y:818,w:1840,h:187}},ticker:{component:"ticker",zone:"top",layer:110,rect:{x:38,y:32,w:1844,h:69}}},components:[...new Set(["scorebug","ticker",...active]) ]};
  }
  function auditRenderedScorebug(root){const n=root?.querySelector?.(".nr-scorebug");return !n||n.getBoundingClientRect().height<150?["missing Neon R1 bottom scoreboard"]:[];}
  function validateManifests(){return Object.keys(MANIFEST.sports).length===4?[]:["Neon R1 sport contract"]}
  window.CSRNNeonR1Engine=Object.freeze({version:VERSION,packageId:PACKAGE_ID,manifests:Object.freeze({[PACKAGE_ID]:MANIFEST}),renderPackage,auditRenderedScorebug,validateManifests,assets:ASSETS});
})();
