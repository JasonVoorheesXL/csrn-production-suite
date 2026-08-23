(() => {
  "use strict";

  const VERSION = "2.3.0";
  const PACKAGE_ID = "heritage_press";
  const base = window.CSRNBroadcastLayoutEngine;
  if (!base) throw new Error("Heritage Press requires the Broadcast Layout Engine.");

  const MANIFEST = Object.freeze({
    id: PACKAGE_ID,
    name: "Heritage Press",
    styleClass: "package-heritage-newspaper",
    engine: "CSRNHeritagePressEngine",
    sports: Object.freeze({football:true,basketball:true,baseball:true,softball:true})
  });

  const ASSETS = Object.freeze({
    baseballPitcher: "/static/heritage/press-pitcher-1920s.png",
    baseballBatter: "/static/heritage/press-batter-1920s.png",
    softballPitcher: "/static/heritage/press-softball-pitcher-1920s.png",
    softballBatter: "/static/heritage/press-softball-batter-1920s.png",
    sponsorTruck: "/static/heritage/press-sponsor-truck.png",
    playerPlaceholder: "/static/heritage/press-player-placeholder.png",
    newsprintTexture: "/static/heritage/press-newsprint-texture.png"
  });

  const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (ch) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[ch]);
  const clone = (value) => JSON.parse(JSON.stringify(value));
  const score = (value) => String(Math.max(0, Math.min(999, Number(value) || 0)));
  const clean = (value, fallback = "—") => String(value ?? "").trim() || fallback;
  const sideName = (side) => side === "home" ? "HOME" : "VISITOR";
  const possessionName = (state) => state.game.possession === "visitor" ? state.visitor.name : state.game.possession === "home" ? state.home.name : "NONE";

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
      ticker:{...fallback.ticker,...(value.ticker || {})},
      heritageDispatch:{
        phase:"pregame",
        ...((value.heritageDispatch || value.heritage_dispatch || value.dispatch) || {})
      }
    };
    state.heritageDispatch.facts = {...((value.heritageDispatch || value.heritage_dispatch || value.dispatch)?.facts || {})};
    state.player.stats = {...(fallback.player?.stats || {}),...(value.player?.stats || {})};
    state.scheduledDate = value.scheduledDate || value.scheduled_date || value.gameDate || value.game_date || "";
    state.contestType = value.contestType || value.contest_type || "official";
    state.specialGameDesignations = value.specialGameDesignations || value.special_game_designations || [];
    return state;
  }

  const LIVELY_LINES = Object.freeze([
    Object.freeze({id:"pay-dirt",sports:["football"],events:["touchdown","touchdown_run","explosive_run"],text:"{player} found daylight and carried the leather all the way to pay dirt."}),
    Object.freeze({id:"shimmied-shook-cooked",sports:["football"],events:["touchdown","touchdown_run","explosive_run"],text:"{player} shimmied, shook, and cooked before the defense knew what struck it."}),
    Object.freeze({id:"grandstand-unhinged",sports:["football","basketball"],events:["touchdown","buzzer_beater","lead_change","scoring_run"],text:"The whole grandstand came unhinged when the play broke into the clear."}),
    Object.freeze({id:"coat-tails",sports:["football"],events:["touchdown","touchdown_run","explosive_run"],text:"The defenders were left chasing coat-tails and bad intentions."}),
    Object.freeze({id:"midnight-limited",sports:["football","basketball","baseball","softball"],events:["touchdown","field_goal","three_pointer","dunk","home_run","rbi_hit","double","triple"],text:"That play had more steam than the midnight limited."}),
    Object.freeze({id:"scoreboard-tune",sports:["football","basketball","baseball","softball"],events:["touchdown","field_goal","three_pointer","scoring_run","home_run","rbi_hit","double","triple"],text:"By the time the dust settled, the scoreboard had changed its tune."}),
    Object.freeze({id:"telegram-urgent",sports:["football","baseball","softball"],events:["touchdown_pass","home_run","double","triple"],text:"The ball sailed like a telegram marked urgent."}),
    Object.freeze({id:"far-reaches",sports:["baseball","softball"],events:["home_run","double","triple","rbi_hit"],text:"{player} sent the ball screaming toward the far reaches of the yard."}),
    Object.freeze({id:"swinging-shadows",sports:["baseball","softball"],events:["strikeout","pitching_escape"],text:"The hurler had them swinging at shadows."}),
    Object.freeze({id:"rafters-hardwood",sports:["basketball"],events:["three_pointer","dunk","buzzer_beater","lead_change","scoring_run"],text:"The gymnasium shook from the rafters to the hardwood."}),
    Object.freeze({id:"clerk-receipt",sports:["basketball"],events:["three_pointer","jump_shot","buzzer_beater"],text:"{player} dropped it through the hoop as neatly as a clerk stamping a receipt."}),
    Object.freeze({id:"baseball-mischief",sports:["baseball","softball"],events:["rbi_hit","double","triple","defensive_play","stolen_base"],text:"What looked like certain trouble became a first-class piece of diamond mischief."})
  ]);

  const isPresent = (value) => value !== undefined && value !== null && String(value).trim() !== "";
  const lastName = (value) => clean(value,"PLAYER").trim().split(/\s+/).slice(-1)[0].toUpperCase();
  const titleCase = (value) => clean(value,"").toLowerCase().replace(/\b\w/g,(letter)=>letter.toUpperCase());

  function teamForSide(state, side) {
    return side === "visitor" ? state.visitor : state.home;
  }

  function teamLabel(team) {
    return clean(team.mascot || team.shortName || team.name,"TEAM").toUpperCase();
  }

  function stableIndex(seed, length) {
    let value = 0;
    for (const char of String(seed || "heritage")) value = (value * 31 + char.charCodeAt(0)) >>> 0;
    return length ? value % length : 0;
  }

  function livelyLine(state, sport, eventType, playerName) {
    const dispatch = state.heritageDispatch || {};
    if (String(dispatch.livelyLineId || "").toLowerCase() === "none") return null;
    const eligible = LIVELY_LINES.filter((line)=>line.sports.includes(sport) && line.events.includes(eventType));
    if (!eligible.length) return null;
    const requested = String(dispatch.livelyLineId || dispatch.lively_line_id || "").trim();
    const selected = eligible.find((line)=>line.id === requested) || eligible[stableIndex(`${sport}|${eventType}|${playerName}|${state.game.clock}|${state.game.inning}`,eligible.length)];
    return {id:selected.id,text:selected.text.replaceAll("{player}",clean(playerName,"The playmaker"))};
  }

  function dispatchLabel(sport) {
    return ({football:"GRIDIRON DISPATCH",basketball:"COURTSIDE DISPATCH",baseball:"DIAMOND DISPATCH",softball:"DIAMOND DISPATCH"})[sport];
  }

  function phaseKicker(phase) {
    return ({pregame:"PRE-GAME EDITION",live:"LATEST FROM THE FIELD",halftime:"HALFTIME EDITION",final:"FINAL EDITION"})[phase] || "LATEST EDITION";
  }

  function sportMeetingName(sport) {
    return ({football:"football contest",basketball:"basketball meeting",baseball:"baseball game",softball:"softball game"})[sport];
  }

  function sportStartName(sport) {
    return sport === "football" ? "Kickoff" : sport === "basketball" ? "The opening tip" : "First pitch";
  }

  function pregameDispatch(state, sport) {
    const visitor = clean(state.visitor.name,"VISITOR");
    const home = clean(state.home.name,"HOME");
    const visitorMark = clean(state.visitor.record,"");
    const homeMark = clean(state.home.record,"");
    const venue = clean(state.game.venue || state.venue || state.location,"");
    const start = clean(state.game.startTime || state.game.start_time || state.startTime || state.start_time,"");
    const headline = `${teamLabel(state.visitor)} MEET ${teamLabel(state.home)} TONIGHT`;
    const body = [`${visitor} visits ${home} tonight for a ${sportMeetingName(sport)}.`];
    if (visitorMark && homeMark) body.push(`${visitor} enters at ${visitorMark}, while ${home} carries a ${homeMark} mark into the contest.`);
    if (venue || start) body.push(`${sportStartName(sport)} is set${start ? ` for ${start}` : ""}${venue ? ` at ${venue}` : ""}.`);
    return {label:dispatchLabel(sport),phase:"pregame",kicker:phaseKicker("pregame"),headline,body:body.join(" "),lively:null,meta:"MATCHUP PREVIEW"};
  }

  function scoreSnapshot(facts, state) {
    const after = facts.scoreAfter || facts.score_after || {};
    const home = isPresent(after.home) ? Number(after.home) : Number(state.home.score);
    const visitor = isPresent(after.visitor) ? Number(after.visitor) : Number(state.visitor.score);
    return {home:Number.isFinite(home)?home:0,visitor:Number.isFinite(visitor)?visitor:0};
  }

  function scoreConsequence(state, facts, side) {
    const snap = scoreSnapshot(facts,state);
    const team = teamForSide(state,side);
    const own = side === "visitor" ? snap.visitor : snap.home;
    const other = side === "visitor" ? snap.home : snap.visitor;
    if (own > other) return `${clean(team.name,"The scoring side")} held a ${own}–${other} lead after the play.`;
    if (own === other) return `The play drew the score even at ${own}–${other}.`;
    return `The scoreboard stood ${snap.home}–${snap.visitor} after the play.`;
  }

  function downPhrase(facts) {
    const down = Number(facts.down);
    const distance = Number(facts.distance);
    if (!Number.isFinite(down) || !Number.isFinite(distance)) return "";
    const names = ["","first","second","third","fourth"];
    return ` on ${names[down] || `${down}th`}-and-${distance}`;
  }

  function footballDispatch(state, eventType, facts) {
    const side = facts.teamSide === "visitor" ? "visitor" : "home";
    const team = teamForSide(state,side);
    const player = clean(facts.playerName || facts.player_name || state.player.name,"The ball carrier");
    const yards = Number(facts.yards);
    const yardText = Number.isFinite(yards) ? `${yards} yards` : "the distance";
    let headline = `${lastName(player)} MAKES THE PLAY!`;
    let first = clean(state.highlight.detail,"A major play changed the complexion of the game.");
    if (["touchdown","touchdown_run","touchdown_pass"].includes(eventType)) {
      headline = `${lastName(player)} SCORES!`;
      if (eventType === "touchdown_pass" || String(facts.playType || facts.play_type).toLowerCase() === "pass") first = `${player} hauled in a ${Number.isFinite(yards) ? `${yards}-yard` : "scoring"} pass for the touchdown.`;
      else first = `${player} took the handoff${downPhrase(facts)} and went ${yardText} for the touchdown.`;
    } else if (eventType === "field_goal") {
      headline = `${lastName(player)} SPLITS THE UPRIGHTS!`;
      first = `${player} booted a ${Number.isFinite(yards) ? `${yards}-yard` : "go-ahead"} field goal.`;
    } else if (eventType === "turnover") {
      headline = `${teamLabel(team)} TAKE IT AWAY!`;
      first = `${player} forced the turnover${isPresent(facts.returnYards) ? ` and returned it ${facts.returnYards} yards` : ""}.`;
    } else if (eventType === "explosive_run") {
      headline = `${lastName(player)} BREAKS LOOSE!`;
      first = `${player} escaped the defense for ${yardText}${downPhrase(facts)}.`;
    }
    const lively = livelyLine(state,"football",eventType,player);
    const sentences = [first];
    const conversion = facts.conversion || {};
    if (["touchdown","touchdown_run","touchdown_pass"].includes(eventType) && String(conversion.result || facts.conversionResult || facts.conversion_result || "").toLowerCase() === "good") {
      const kicker = clean(conversion.playerName || conversion.player_name || facts.conversionPlayer || facts.conversion_player,"");
      if (kicker) sentences.push(`${kicker} split the uprights on the extra point.`);
    }
    sentences.push(scoreConsequence(state,facts,side));
    return {headline,body:sentences.join(" "),lively,meta:[clean(facts.period || state.game.period,""),clean(facts.clock || state.game.clock,"")].filter(Boolean).join(" · ")};
  }

  function basketballDispatch(state, eventType, facts) {
    const side = facts.teamSide === "visitor" ? "visitor" : "home";
    const player = clean(facts.playerName || facts.player_name || state.player.name,"The shooter");
    const run = Number(facts.runSize || facts.run_size);
    let headline = `${lastName(player)} LIGHTS THE FUSE!`;
    let first = clean(state.highlight.detail,"A major basket shifted the momentum.");
    if (eventType === "three_pointer") first = `${player} buried a three-pointer${facts.location ? ` from ${facts.location}` : ""}${Number.isFinite(run) ? ` to finish a ${run}–0 run` : ""}.`;
    else if (eventType === "dunk") {headline = `${lastName(player)} ROCKS THE RIM!`;first = `${player} finished at the rim with authority${Number.isFinite(run) ? ` during a ${run}–0 burst` : ""}.`;}
    else if (eventType === "buzzer_beater") {headline = `${lastName(player)} BEATS THE HORN!`;first = `${player} connected as the horn sounded.`;}
    else if (eventType === "scoring_run" || eventType === "lead_change") first = `${player} capped ${Number.isFinite(run) ? `a ${run}–0 run` : "the scoring surge"}${facts.playType ? ` with ${facts.playType}` : ""}.`;
    const lively = livelyLine(state,"basketball",eventType,player);
    return {headline,body:`${first} ${scoreConsequence(state,facts,side)}`,lively,meta:[clean(facts.period || state.game.period,""),clean(facts.clock || state.game.clock,"")].filter(Boolean).join(" · ")};
  }

  function diamondDispatch(state, sport, eventType, facts) {
    const side = facts.teamSide === "visitor" ? "visitor" : "home";
    const player = clean(facts.playerName || facts.player_name || (eventType === "strikeout" ? state.game.pitcherName : state.game.batterName),"The player");
    const rbi = Number(facts.rbi || facts.runsBattedIn || facts.runs_batted_in);
    const location = clean(facts.location,"");
    let headline = `${lastName(player)} TURNS THE TIDE!`;
    let first = clean(state.highlight.detail,"A major play changed the inning.");
    if (eventType === "home_run") {headline = `${lastName(player)} SENDS ONE OUT!`;first = `${player} turned on the offering and drove it beyond the ${location || "outfield wall"}${Number.isFinite(rbi) && rbi > 0 ? ` for a ${rbi}-run homer` : ""}.`;}
    else if (["rbi_hit","single","double","triple"].includes(eventType)) {const hit = eventType === "rbi_hit" ? clean(facts.hitType || facts.hit_type,"base hit") : eventType;headline = `${lastName(player)} DELIVERS!`;first = `${player} drove a ${hit}${location ? ` into ${location}` : ""}${Number.isFinite(rbi) && rbi > 0 ? ` and brought home ${rbi === 1 ? "a run" : `${rbi} runs`}` : ""}.`;}
    else if (eventType === "strikeout" || eventType === "pitching_escape") {headline = `${lastName(player)} SLAMS THE DOOR!`;first = `${player} ${eventType === "strikeout" ? "recorded the strikeout" : "worked out of trouble"}${facts.outsRecorded ? ` for out number ${facts.outsRecorded}` : ""}.`;}
    else if (eventType === "defensive_play") {headline = `${lastName(player)} SAVES THE INNING!`;first = `${player} made the defensive play${location ? ` at ${location}` : ""}.`;}
    const lively = livelyLine(state,sport,eventType,player);
    const inning = `${String(facts.inningHalf || facts.inning_half || state.game.inningHalf || "TOP").toUpperCase().startsWith("B") ? "BOT" : "TOP"} ${clean(facts.inning || state.game.inning,"")}`.trim();
    return {headline,body:`${first} ${scoreConsequence(state,facts,side)}`,lively,meta:inning};
  }

  function buildDispatch(state, sport) {
    const dispatch = state.heritageDispatch || {};
    const phase = clean(dispatch.phase,"pregame").toLowerCase();
    const facts = dispatch.facts || {};
    const eventType = clean(dispatch.eventType || dispatch.event_type || facts.eventType || facts.event_type,"").toLowerCase();
    const explicitHeadline = clean(dispatch.headline,"");
    const explicitBody = clean(dispatch.body || dispatch.operatorOverride || dispatch.operator_override,"");
    if (explicitHeadline || explicitBody) {
      const lively = livelyLine(state,sport,eventType || "scoring_run",facts.playerName || facts.player_name || state.player.name);
      return {label:clean(dispatch.label,dispatchLabel(sport)),phase,kicker:phaseKicker(phase),headline:explicitHeadline || "LATEST DISPATCH",body:explicitBody || "No verified dispatch copy entered.",lively,meta:clean(dispatch.meta,"")};
    }
    if (!eventType || phase === "pregame") return pregameDispatch(state,sport);
    const generated = sport === "football" ? footballDispatch(state,eventType,facts) : sport === "basketball" ? basketballDispatch(state,eventType,facts) : diamondDispatch(state,sport,eventType,facts);
    return {label:dispatchLabel(sport),phase,kicker:phaseKicker(phase),...generated};
  }

  function dispatchMarkup(state, sport) {
    const article = buildDispatch(state,sport);
    return `<section class="hp-dispatch" data-dispatch-phase="${esc(article.phase)}" data-dispatch-line="${esc(article.lively?.id || "none")}">
      <h3>${esc(article.label)}</h3>
      <small>${esc(article.kicker)}</small>
      <strong>${esc(article.headline)}</strong>
      <p>${esc(article.body)}</p>
      ${article.lively ? `<blockquote>“${esc(article.lively.text)}”</blockquote>` : ""}
      <footer>${esc(article.meta || "HERITAGE SPORTS DESK")}</footer>
    </section>`;
  }

  function formatDate(value) {
    const raw = String(value || "").trim();
    if (!raw) return "GAME DAY EDITION";
    const parsed = new Date(`${raw}T12:00:00`);
    if (Number.isNaN(parsed.getTime())) return raw.toUpperCase();
    return parsed.toLocaleDateString("en-US",{weekday:"long",month:"long",day:"numeric",year:"numeric"}).toUpperCase();
  }

  function designation(state) {
    const labels = Array.isArray(state.specialGameDesignations) ? state.specialGameDesignations.filter(Boolean) : [];
    if (labels.length) return labels.map((item)=>String(item).replaceAll("_"," ")).join(" · ").toUpperCase();
    const type = String(state.contestType || "official").replaceAll("_"," ").trim();
    return type ? type.toUpperCase() : "OFFICIAL GAME";
  }

  function teamMark(team, side) {
    const label = team.shortName || team.name || sideName(side);
    return `<div class="hp-team-mark" data-module="${side}.logo" data-bind="${side}.logo">${team.logo ? `<img src="${esc(team.logo)}" alt="${esc(label)} logo">` : `<span>${esc(label.slice(0,1).toUpperCase())}</span>`}</div>`;
  }

  function teamCell(team, side) {
    return `<div class="hp-team hp-${side}" data-module="${side}.identity">
      ${side === "home" ? teamMark(team,side) : ""}
      <div class="hp-team-copy">
        <small>${sideName(side)} · <span data-bind="${side}.record">${esc(clean(team.record))}</span></small>
        <strong data-bind="${side}.name">${esc(clean(team.name,"TEAM"))}</strong>
        <span data-bind="${side}.mascot">${esc(clean(team.mascot,""))}</span>
      </div>
      ${side === "visitor" ? teamMark(team,side) : ""}
    </div>`;
  }

  function baseDiamond(bases = []) {
    const occupied = Array.isArray(bases) ? bases : [false,false,false];
    return `<div class="hp-bases" aria-label="Base occupancy"><i class="b2 ${occupied[1] ? "on" : ""}"></i><i class="b3 ${occupied[2] ? "on" : ""}"></i><i class="b1 ${occupied[0] ? "on" : ""}"></i></div>`;
  }

  function stateBox(state, sport) {
    const g = state.game;
    if (sport === "football") {
      return `<div class="hp-state-grid hp-football-state" data-module="game.state">
        <span><small>PERIOD</small><b>${esc(clean(g.period))}</b></span>
        <span><small>CLOCK</small><b>${esc(clean(g.clock))}</b></span>
        <span><small>DOWN</small><b>${esc(clean(g.downDistance))}</b></span>
        <span><small>PLAY</small><b>${esc(clean(g.playClock))}</b></span>
        <span class="wide"><small>POSSESSION</small><b>${esc(clean(possessionName(state)))}</b></span>
      </div>`;
    }
    if (sport === "basketball") {
      return `<div class="hp-state-grid hp-basketball-state" data-module="game.state">
        <span><small>PERIOD</small><b>${esc(clean(g.period))}</b></span>
        <span><small>CLOCK</small><b>${esc(clean(g.clock))}</b></span>
        <span><small>SHOT</small><b>${esc(clean(g.shotClock))}</b></span>
        <span><small>FOULS H–V</small><b>${esc(clean(g.homeFouls,"0"))}–${esc(clean(g.visitorFouls,"0"))}</b></span>
        <span class="wide"><small>POSSESSION</small><b>${esc(clean(possessionName(state)))}</b></span>
      </div>`;
    }
    const half = String(g.inningHalf || "TOP").toUpperCase().startsWith("B") ? "BOTTOM" : "TOP";
    return `<div class="hp-state-grid hp-diamond-state" data-module="game.state">
      <span><small>INNING</small><b>${half} ${esc(clean(g.inning))}</b></span>
      <span><small>COUNT</small><b>${esc(clean(g.balls,"0"))}–${esc(clean(g.strikes,"0"))}</b></span>
      <span><small>OUTS</small><b>${esc(clean(g.outs,"0"))}</b></span>
      <span class="wide"><small>RUNNERS</small>${baseDiamond(g.bases)}</span>
    </div>`;
  }

  function infoRows(rows) {
    return `<div class="hp-info-rows">${rows.map(([label,value]) => `<div><span>${esc(label)}</span><b>${esc(clean(value))}</b></div>`).join("")}</div>`;
  }

  function teamScoreRows(state) {
    return `<div class="hp-team-score-rows">
      <div><span>${esc(clean(state.home.shortName || state.home.name,"HOME"))}</span><b>${esc(score(state.home.score))}</b><small>${esc(clean(state.home.record))}</small></div>
      <div><span>${esc(clean(state.visitor.shortName || state.visitor.name,"VISITOR"))}</span><b>${esc(score(state.visitor.score))}</b><small>${esc(clean(state.visitor.record))}</small></div>
    </div>`;
  }

  function playerStats(state, sport) {
    const source = state.player?.stats?.[sport];
    if (!Array.isArray(source)) return [];
    return source.slice(0,4).filter((item)=>item && (item.label || item.value)).map((item)=>({label:clean(item.label,"STAT"),value:clean(item.value)}));
  }

  function playerWatch(state, sport) {
    const stats = playerStats(state,sport);
    return `<section class="hp-player-watch"><h3>Player Watch</h3><small>${esc(clean(state.home.name,"TEAM"))}</small><strong>${esc(clean(state.player.name,"PLAYER"))}</strong><span>${esc(clean(state.player.position,""))}${state.player.number ? ` · NO. ${esc(state.player.number)}` : ""}</span><p>${esc(clean(state.player.detail,"No verified player detail entered."))}</p>${stats.length ? `<div class="hp-watch-stats">${stats.map((item)=>`<i><b>${esc(item.value)}</b><small>${esc(item.label)}</small></i>`).join("")}</div>` : ""}</section>`;
  }

  function footballColumns(state) {
    return {
      left:`<section><h3>Score Summary</h3>${teamScoreRows(state)}</section><section><h3>Game State</h3>${infoRows([["Period",state.game.period],["Clock",state.game.clock],["Down & Distance",state.game.downDistance],["Play Clock",state.game.playClock],["Possession",possessionName(state)]])}</section>`,
      right:dispatchMarkup(state,"football")
    };
  }

  function basketballColumns(state) {
    return {
      left:`<section><h3>Score Summary</h3>${teamScoreRows(state)}</section><section><h3>Courtside State</h3>${infoRows([["Period",state.game.period],["Clock",state.game.clock],["Shot Clock",state.game.shotClock],[`${clean(state.home.shortName || state.home.name,"HOME")} Fouls`,state.game.homeFouls],[`${clean(state.visitor.shortName || state.visitor.name,"VISITOR")} Fouls`,state.game.visitorFouls],["Possession",possessionName(state)]])}</section>`,
      right:dispatchMarkup(state,"basketball")
    };
  }

  function roleBlock(kind, name, position, asset, detail = "") {
    return `<section class="hp-role"><h3>${esc(kind)}</h3><img src="${asset}" alt="" aria-hidden="true"><strong>${esc(clean(name,"NOT ENTERED"))}</strong><span>${esc(clean(position,""))}</span>${detail ? `<p>${esc(detail)}</p>` : ""}</section>`;
  }

  function diamondColumns(state, sport) {
    const softball = sport === "softball";
    const batterAsset = softball ? ASSETS.softballBatter : ASSETS.baseballBatter;
    const pitcherAsset = softball ? ASSETS.softballPitcher : ASSETS.baseballPitcher;
    const batter = roleBlock("At Bat",state.game.batterName,state.game.batterPosition,batterAsset,clean(state.game.batterDetail || state.game.batter_detail,""));
    const pitcher = roleBlock(softball ? "In The Circle" : "On The Mound",state.game.pitcherName,state.game.pitcherPosition || state.game.pitcher_position || "",pitcherAsset,clean(state.game.pitcherDetail || state.game.pitcher_detail,""));
    return {
      left:`<div class="hp-role-stack" data-role-stack="${sport}">${batter}${pitcher}</div>`,
      right:dispatchMarkup(state,sport),
      sport
    };
  }

  function lineScoreValues(state, side) {
    const game = state.game || {};
    const structured = game.lineScore || game.line_score || {};
    const direct = structured[side] || structured[`${side}Innings`] || structured[`${side}_innings`];
    const fallback = game[`${side}LineScore`] || game[`${side}_line_score`] || game[`${side}Innings`] || game[`${side}_innings`];
    const source = Array.isArray(direct) ? direct : Array.isArray(fallback) ? fallback : [];
    return source.map((value) => value === null || value === undefined || value === "" ? "—" : String(value));
  }

  function inningCount(state, home, visitor) {
    const current = Math.max(0, Number(state.game?.inning) || 0);
    return Math.max(9, Math.min(12, current, home.length, visitor.length));
  }

  function lineTotal(state, side, key) {
    const game = state.game || {};
    const structured = game.lineScore || game.line_score || {};
    const aliases = {
      hits:[`${side}Hits`,`${side}_hits`],
      errors:[`${side}Errors`,`${side}_errors`]
    };
    const nested = structured[`${side}${key[0].toUpperCase()}${key.slice(1)}`] ?? structured[side]?.[key];
    if (nested !== undefined && nested !== null && nested !== "") return String(nested);
    for (const alias of aliases[key] || []) {
      if (game[alias] !== undefined && game[alias] !== null && game[alias] !== "") return String(game[alias]);
    }
    return "—";
  }

  function lineScoreRow(label, innings, count, runs, hits, errors) {
    const cells = Array.from({length:count},(_,index)=>`<span>${esc(innings[index] ?? "—")}</span>`).join("");
    return `<div class="hp-line-row"><strong>${esc(label)}</strong>${cells}<b>${esc(runs)}</b><b>${esc(hits)}</b><b>${esc(errors)}</b></div>`;
  }

  function currentLine(state, sport) {
    const home = lineScoreValues(state,"home");
    const visitor = lineScoreValues(state,"visitor");
    const count = inningCount(state,home,visitor);
    const headers = Array.from({length:count},(_,index)=>`<b>${index+1}</b>`).join("");
    const homeLabel = clean(state.home.shortName || state.home.name,"HOME");
    const visitorLabel = clean(state.visitor.shortName || state.visitor.name,"VISITOR");
    return `<div class="hp-current-line" data-module="game.lineScore" style="--hp-inning-count:${count}">
      <div class="hp-line-row head"><strong>LINE SCORE</strong>${headers}<b>R</b><b>H</b><b>E</b></div>
      ${lineScoreRow(homeLabel,home,count,score(state.home.score),lineTotal(state,"home","hits"),lineTotal(state,"home","errors"))}
      ${lineScoreRow(visitorLabel,visitor,count,score(state.visitor.score),lineTotal(state,"visitor","hits"),lineTotal(state,"visitor","errors"))}
    </div>`;
  }

  function featureStats(state, sport) {
    const stats = playerStats(state,sport);
    return stats.length ? `<div class="hp-feature-stats">${stats.map((item)=>`<span><b>${esc(item.value)}</b><small>${esc(item.label)}</small></span>`).join("")}</div>` : "";
  }

  function openingContent(state, sport, mode) {
    if (mode === "player") {
      return `<section class="hp-opening-content hp-player-feature" data-video-mode="player">
        <div class="hp-player-image">${state.player.headshot ? `<img src="${esc(state.player.headshot)}" alt="">` : `<img src="${ASSETS.playerPlaceholder}" alt="">`}</div>
        <div class="hp-player-story"><small>PLAYER OF THE GAME · SPORTS EXTRA</small><h2>${esc(clean(state.player.name,"PLAYER"))}</h2><p class="subhead">${esc(clean(state.home.name,"TEAM"))} ${esc(clean(state.home.mascot,""))} · ${esc(clean(state.player.position,""))}${state.player.number ? ` · NO. ${esc(state.player.number)}` : ""}</p>${featureStats(state,sport)}<p class="detail">${esc(clean(state.player.detail,"No verified player detail entered."))}</p></div>
      </section>`;
    }
    if (mode === "highlight") {
      return `<section class="hp-opening-content hp-highlight-feature" data-video-mode="highlight"><div class="hp-feature-headline">${esc(clean(state.highlight.title,"GAME HIGHLIGHT"))}</div><div class="hp-highlight-window" data-module="video.board"><span>HIGHLIGHT VIDEO OPENING</span></div><p>${esc(clean(state.highlight.detail,"No verified highlight detail entered."))}</p></section>`;
    }
    if (mode === "sponsor") {
      return `<section class="hp-opening-content hp-sponsor-feature" data-video-mode="sponsor"><small>ADVERTISEMENT · COMMUNITY PARTNER</small>${state.sponsor.logo ? `<img src="${esc(state.sponsor.logo)}" alt="">` : `<img src="${ASSETS.sponsorTruck}" alt="">`}<h2>${esc(clean(state.sponsor.name,"COMMUNITY PARTNER"))}</h2><p>${esc(clean(state.sponsor.line,"Proud supporter of local athletics"))}</p><footer>SUPPORT LOCAL · INVEST LOCAL · CHEER LOCAL</footer></section>`;
    }
    if (mode === "feature") {
      return `<section class="hp-opening-content hp-combined-feature" data-video-mode="feature"><div class="hp-combined-video"><strong>${esc(clean(state.highlight.title,"GAME HIGHLIGHT"))}</strong><span>FEATURE VIDEO OPENING</span></div><div class="hp-combined-player"><small>PLAYER WATCH</small><strong>${esc(clean(state.player.name,"PLAYER"))}</strong><span>${esc(clean(state.player.position,""))} · ${esc(clean(state.player.detail,""))}</span></div></section>`;
    }
    return `<div class="hp-live-opening" data-video-mode="broadcast" data-module="video.board"><span>LIVE VIDEO OPENING</span><small>Transparent outside Layout Lab diagnostics</small></div>`;
  }

  function captionMarkup(state) {
    return `<div class="hp-caption"><b>${esc(clean(state.captions.speaker,"BROADCAST"))}</b><span>${esc(clean(state.captions.text,""))}</span></div>`;
  }

  function modeFor(activeComponents, requested) {
    if (["broadcast","highlight","sponsor","player","feature"].includes(requested)) return requested;
    if (activeComponents.includes("highlightVideo") && activeComponents.includes("playerCard")) return "feature";
    if (activeComponents.includes("highlightVideo")) return "highlight";
    if (activeComponents.includes("sponsor")) return "sponsor";
    if (activeComponents.includes("playerCard")) return "player";
    return "broadcast";
  }

  function pageLabels(sport) {
    return {
      football:["FRIDAY NIGHT FOOTBALL","GRIDIRON EDITION"],
      basketball:["COURT REPORT","COURTSIDE EDITION"],
      baseball:["DIAMOND REPORT","BASEBALL EDITION"],
      softball:["SOFTBALL REPORT","SOFTBALL EDITION"]
    }[sport];
  }

  function pageMarkup(state, sport, mode, captionsEnabled) {
    const labels = pageLabels(sport);
    const diamond = sport === "baseball" || sport === "softball";
    const columns = sport === "football" ? footballColumns(state) : sport === "basketball" ? basketballColumns(state) : diamondColumns(state,sport);
    return `<div class="bl-scorebug hp-stage hp-${sport}" data-scorebug-family="heritage-newspaper-r23" data-video-mode="${mode}" style="--hp-texture:url('${ASSETS.newsprintTexture}')">
      <article class="hp-page">
        <div class="hp-masthead">
          <div class="hp-brand"><span>THE</span><b>HERITAGE PRESS</b><em>Sports</em></div>
          <div class="hp-stars">✦ ✦ ✦</div>
          <div class="hp-edition">${esc(labels[1])}<br>${esc(formatDate(state.scheduledDate))}<br>${esc(designation(state))}</div>
        </div>
        <div class="hp-section-title">${esc(labels[0])}</div>
        <section class="hp-scorebox">
          ${teamCell(state.home,"home")}
          <div class="hp-score hp-home-score" data-module="home.score" data-bind="home.score">${esc(score(state.home.score))}</div>
          ${stateBox(state,sport)}
          <div class="hp-score hp-visitor-score" data-module="visitor.score" data-bind="visitor.score">${esc(score(state.visitor.score))}</div>
          ${teamCell(state.visitor,"visitor")}
        </section>
        <section class="hp-newsbody ${diamond ? "diamond" : ""}">
          <aside class="hp-column hp-left-column" data-module="editorial.left">${columns.left}</aside>
          <main class="hp-center-column">
            <div class="hp-opening">${openingContent(state,sport,mode)}${captionsEnabled ? captionMarkup(state) : ""}</div>
            ${diamond ? currentLine(state,sport) : ""}
          </main>
          <aside class="hp-column hp-right-column" data-module="editorial.right">${columns.right}</aside>
        </section>
        <footer class="hp-footer"><div class="hp-wire-title">SPORTS WIRE</div><div class="hp-wire-copy" data-bind="ticker.text">${esc(clean(state.ticker.text,"SPORTS WIRE"))}</div><div class="hp-page-id">LATE EDITION · PAGE 1</div></footer>
      </article>
    </div>`;
  }

  function componentNode(rect, markup) {
    const node = document.createElement("section");
    node.className = "bl-component bl-scorebug";
    node.dataset.component = "scorebug";
    node.dataset.zone = "heritage-full-page";
    Object.assign(node.style,{left:`${rect.x}px`,top:`${rect.y}px`,width:`${rect.w}px`,height:`${rect.h}px`,zIndex:"100"});
    node.innerHTML = markup;
    return node;
  }

  function renderPackage(root, packageId, sport = "football", value = {}, options = {}) {
    if (!root) throw new Error("Heritage Press layout root is required.");
    if (packageId !== PACKAGE_ID) throw new Error(`Unknown Heritage Press package: ${packageId}`);
    if (!MANIFEST.sports[sport]) throw new Error(`Unsupported Heritage Press sport: ${sport}`);
    const state = normalizeState(value,sport);
    const activeComponents = [...new Set(options.activeComponents || base.scenarios.baseline)];
    const mode = modeFor(activeComponents,options.videoMode);
    const captionsEnabled = activeComponents.includes("captions");
    const placements = {scorebug:{component:"scorebug",zone:"heritage-full-page",rect:{x:40,y:24,w:1840,h:1032},layer:100}};

    root.replaceChildren();
    root.className = "csrn-broadcast-layout package-heritage-newspaper";
    root.dataset.package = PACKAGE_ID;
    root.dataset.sport = sport;
    root.dataset.engineVersion = VERSION;
    root.dataset.videoMode = mode;
    root.classList.toggle("diagnostics",Boolean(options.diagnostics));
    root.appendChild(componentNode(placements.scorebug.rect,pageMarkup(state,sport,mode,captionsEnabled)));
    root.dataset.ready = "true";
    return {packageId:PACKAGE_ID,sport,placements,components:activeComponents,videoMode:mode};
  }

  function validateManifests() {
    const issues = [];
    for (const sport of ["football","basketball","baseball","softball"]) if (!MANIFEST.sports[sport]) issues.push(`missing ${sport}`);
    return issues;
  }

  window.CSRNHeritagePressEngine = Object.freeze({
    VERSION,
    packageId:PACKAGE_ID,
    manifests:Object.freeze({[PACKAGE_ID]:MANIFEST}),
    sports:base.sports,
    scenarios:base.scenarios,
    assets:ASSETS,
    livelyLines:LIVELY_LINES,
    defaultState:base.defaultState,
    normalizeState,
    buildDispatch,
    pageMarkup,
    renderPackage,
    validateManifests,
    auditRenderedScorebug:base.auditRenderedScorebug
  });
})();
