/* New recipe UI; old snapshots retain the original controls and renderer. */
if (data.config.world_recipe >= 1) {
  const title = s => s.replaceAll('_', ' ').replace(/\b\w/g, c => c.toUpperCase());
  const make = (tag, text, parent) => { const e=document.createElement(tag); if(text!==undefined)e.textContent=text; if(parent)parent.append(e); return e; };
  const style=make('style', '#world-params label{display:block;font-size:12px}#world-params input,#world-params select{width:100%}.world-cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px}.world-card{padding:14px;background:#20313c;border-radius:8px}.world-controls{display:flex;flex-wrap:wrap;gap:12px}.world-controls label{margin:4px}.world-controls input[type=checkbox]{width:auto}#world-atlas{aspect-ratio:2;image-rendering:pixelated}#world-layers{max-height:250px;overflow:auto}#world-layers label{display:inline-flex;align-items:center;gap:5px;margin:4px 10px 4px 0}#world-layers input[type=range]{width:65px}#world-viewer{margin:24px 0;padding:18px;border:1px solid #405d68;border-radius:12px}#world-controls{margin:0 0 22px;padding:16px 18px;border:1px solid #405d68;border-radius:12px;background:#1a2732;display:flex;flex-wrap:wrap;gap:10px 14px;align-items:center}#world-controls h2{width:100%;margin:0 0 2px;font-size:17px}#world-controls label{display:inline-flex;align-items:center;gap:6px;margin:0;font-size:13px}#world-controls #world-status{width:100%;margin:2px 0 0}#world-controls #world-params,#world-controls>details,#world-controls>p{width:100%}#world-controls #world-generate{font-weight:600;background:#31647d;border-color:#8ed9ed}');
  document.head.append(style);
  const svgEl=(tag,attrs,parent)=>{const e=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const [k,v] of Object.entries(attrs||{}))e.setAttribute(k,v);if(parent)parent.append(e);return e;};
  document.head.append(make('style','.story-card svg{display:block;margin:6px auto;max-width:100%}.story-histogram{display:grid;gap:3px;margin:6px 0}.story-bar{display:grid;grid-template-columns:220px 1fr;align-items:center;gap:8px;font-size:12px}.story-bar-fill{display:block;height:10px;background:#ffd67e;border-radius:3px}'));
  const aside=document.querySelector('aside');
  for(const e of [...aside.children])e.hidden=true;
  // Above the layout, not inside the sidebar. The sidebar is the left column of a
  // two-column grid that collapses to `order:-1` on the map below 750px, which put the
  // only control that starts a simulation underneath a page tens of thousands of pixels
  // tall. A run is the first thing anyone comes here to do, so it goes first.
  const head=make('section');head.id='world-controls';
  document.querySelector('.layout').before(head);
  make('h2','New simulation',head);
  const baseline=make('details');make('summary','Ground-only baseline and legacy diagnostics',baseline);$('human-panel').before(baseline);baseline.append($('human-panel'));
  const mode=make('select',undefined,head);mode.id='world-mode';
  for(const [value,text] of [['random','Random'],['parameters','Parameters']]){const option=make('option',text,mode);option.value=value;}
  const generateButton=make('button','Run simulation',head);generateButton.id='world-generate';generateButton.disabled=!live;
  const resolutionLabel=make('label','Simulation resolution ',head),resolution=make('select',undefined,resolutionLabel);resolution.id='world-resolution';
  for(const size of [17,33,65,129]){const option=make('option',`${size-1} × ${size-1} cells${size===65?' · detailed':''}`,resolution);option.value=size;}
  resolution.value=String(data.config.size);if(!resolution.value)resolution.value='65';
  const refine=make('button','Regenerate this seed at selected resolution',head);refine.id='world-refine';refine.disabled=!live;
  make('p','Higher resolution recomputes terrain and founding from the same seed. It adds sampled detail and can change city locations; zoom alone does not.',head);
  const parameters=make('form',undefined,head);parameters.id='world-params';parameters.hidden=true;
  const reset=make('button','Reset parameters to defaults',parameters);reset.type='button';
  const inputs={};const groups={};let busy=false;
  const schema=data.recipe.parameters;
  let explicit={...data.recipe.overrides};
  for(const [key,s] of Object.entries(schema)){
    if(['shape','tectonics'].includes(key)||s.group==='Sky')continue;
    let group=groups[s.group];if(!group){group=make('details',undefined,parameters);make('summary',s.group,group);groups[s.group]=group;}
    const label=make('label',title(key)+(s.units?' · '+s.units:''),group);label.title=s.description;
    const input=make(s.choices?'select':'input',undefined,label);input.name=key;
    if(s.choices){for(const v of s.choices){const opt=make('option',s.choice_labels?.[v]||title(v),input);opt.value=v;}}
    else {input.type=s.type==='string'?'text':'number';input.step=s.type==='integer'?'1':'any';if(s.min!==undefined)input.min=s.min;if(s.max!==undefined)input.max=s.max;}
    input.required=true;input.value=data.recipe.resolved[key]??s.default;inputs[key]=input;
    input.onchange=()=>{
      if(key!=='seed')explicit[key]=s.type==='string'?input.value:Number(input.value);
      if(key==='world_size'&&!Object.hasOwn(explicit,'globe_radius'))inputs.globe_radius.value=10000*({small:1,medium:2,large:3}[input.value]);
    };
  }
  const status=make('p',(sample?`Prebuilt sample: seed ${data.config.seed} · recipe ${data.config.world_recipe} · ${data.config.size-1} × ${data.config.size-1} cells. Nothing was generated to show this. Run simulation builds a new world and times it.`:`Seed ${data.config.seed} · recipe ${data.config.world_recipe}. Random generation uses defaults at the selected resolution.`),head);status.id='world-status';status.setAttribute('role','status');
  const advanceButton=make('button','Advance age',head);advanceButton.id='world-advance-age';advanceButton.hidden=data.config.world_recipe!==3;advanceButton.disabled=!live||!data.beast_nests;
  const exportButton=make('button','Export world JSON',head);exportButton.onclick=()=>$('download').click();
  refine.onclick=()=>{if(busy)return;mode.value='parameters';mode.onchange();explicit={...completeWorld.recipe.overrides,size:Number(resolution.value)};inputs.seed.value=completeWorld.config.seed;for(const [k,v]of Object.entries(explicit))if(inputs[k])inputs[k].value=v;generateButton.click();};
  mode.onchange=()=>{parameters.hidden=mode.value==='random';generateButton.textContent=mode.value==='random'?'Run simulation':'Run simulation with parameters';};
  reset.onclick=()=>{explicit={};for(const [k,e] of Object.entries(inputs))e.value=schema[k].default;};
  parameters.onsubmit=e=>{e.preventDefault();generateButton.click();};
  const foundingLog=make('details',undefined,head);make('summary','Founding rounds',foundingLog);const foundingText=make('pre','',foundingLog);
  const viewer=make('section');viewer.id='world-viewer';document.querySelector('.layout').after(viewer);
  make('h2','Layered world atlas',viewer);
  make('p','2D view of the selected stage. Natural biome colors remain visible beneath magic outlines. Sky islands are disabled.',viewer);
  const controls=make('div',undefined,viewer);controls.className='world-controls';
  const monthLabel=make('label','Month ',controls),month=make('select',undefined,monthLabel);month.id='world-month';
  for(let m=0;m<12;m++){const opt=make('option',new Date(2000,m,1).toLocaleString('en',{month:'long'}),month);opt.value=m;}
  const layerLabel=make('label','Inspect field ',controls),field=make('select',undefined,layerLabel);field.id='world-field';
  const skyLabel=make('label',undefined,controls),showSky=make('input',undefined,skyLabel);showSky.type='checkbox';showSky.checked=false;skyLabel.hidden=true;skyLabel.append(' Sky islands');
  const routeLabel=make('label',undefined,controls),showRoutes=make('input',undefined,routeLabel);showRoutes.type='checkbox';showRoutes.checked=true;routeLabel.append(' Trade routes');
  const nestLabel=make('label',undefined,controls),showNests=make('input',undefined,nestLabel);showNests.type='checkbox';showNests.checked=true;showNests.id='world-show-nests';nestLabel.append(' Beast nests');
  const keyLabel=make('label',undefined,controls),showKeyLocations=make('input',undefined,keyLabel);showKeyLocations.type='checkbox';showKeyLocations.checked=true;showKeyLocations.id='world-show-key-locations';keyLabel.append(' Key locations');
  const keyFamilyLabel=make('label',undefined,controls),keyFamily=make('select',undefined,keyFamilyLabel);keyFamily.id='world-key-family';keyFamilyLabel.prepend('Family ');
  const nestPanel=make('details',undefined,viewer);nestPanel.open=true;make('summary','Beast nests: dens, colonies, lairs and aquatic territories',nestPanel);
  const nestSummary=make('p','',nestPanel);nestSummary.id='world-nest-summary';
  const speciesLabel=make('label','Species ',nestPanel),speciesSelect=make('select',undefined,speciesLabel);speciesSelect.id='world-nest-species';
  const nestSelect=make('select',undefined,nestPanel);nestSelect.id='world-nest-select';nestSelect.setAttribute('aria-label','Nest location');
  const nestInfo=make('p','',nestPanel);nestInfo.id='world-nest-info';
  // The moon: phase, rise hour, leaning and the month's surges, from the exported formulas.
  const moonPanel=make('details',undefined,viewer);moonPanel.open=true;make('summary','The moon: phase, surges and the almanac',moonPanel);
  const moonInfo=make('p','',moonPanel);moonInfo.id='world-moon-info';
  const moonlitLabel=make('label',undefined,moonPanel),moonlit=make('input',undefined,moonlitLabel);moonlit.type='checkbox';moonlit.id='world-moonlit';moonlitLabel.append(' Moonlit magic: scale ley fields by this month\'s mean tide and lunar sensitivity');
  const moonEvents=make('p','',moonPanel);moonEvents.id='world-moon-events';
  // Gods stay dormant until the orchestrator summons one; the lab is one such orchestrator.
  const godPanel=make('details',undefined,viewer);make('summary','Gods and faiths (dormant until summoned)',godPanel);
  const godInfo=make('div',undefined,godPanel);godInfo.id='world-gods';godInfo.className='world-cards';
  const summonRow=make('div',undefined,godPanel);summonRow.className='world-controls';
  const godLabel=make('label','God ',summonRow),godSelect=make('select',undefined,godLabel);godSelect.id='world-god-select';
  const targetLabel=make('label','At city ',summonRow),targetSelect=make('select',undefined,targetLabel);targetSelect.id='world-summon-target';
  const wrathLabel=make('label','Wrath ',summonRow),wrath=make('input',undefined,wrathLabel);wrath.type='range';wrath.min=0;wrath.max=1;wrath.step=.05;wrath.value=.5;wrath.id='world-wrath';
  const summonButton=make('button','Summon',summonRow);summonButton.id='world-summon';
  const departButton=make('button','Send the walking god home',summonRow);departButton.id='world-depart';
  function moonTide(moon,t){
    const frac=k=>(((t+moon.offsets[k])%moon.periods[k])+moon.periods[k])%moon.periods[k]/moon.periods[k];
    const alpha=2*Math.PI*frac('synodic'),beta=2*Math.PI*frac('spin'),gamma=moon.tilt_max_degrees*Math.sin(2*Math.PI*frac('nod'))*Math.PI/180;
    const out={};
    for(const [school,c] of Object.entries(moon.regions)){
      let [x,y,z]=c;[x,z]=[x*Math.cos(beta)+z*Math.sin(beta),-x*Math.sin(beta)+z*Math.cos(beta)];[x,y]=[x*Math.cos(gamma)+y*Math.sin(gamma),-x*Math.sin(gamma)+y*Math.cos(gamma)];
      const visible=Math.max(0,x),lit=Math.max(0,x*Math.cos(alpha)+z*Math.sin(alpha));
      out[school]=Math.min(1.8,Math.max(.5,.7+1.1*visible*lit));
    }
    return out;
  }
  function renderMoon(){
    moonPanel.hidden=!data.astrology;if(!data.astrology)return;
    const moon=data.astrology.moon,almanac=data.lunar_almanac,m=Number(month.value),head=almanac?.months?.[m];
    if(!head){moonInfo.textContent='The almanac appears once the moon is seeded at the Leylines stage.';moonEvents.textContent='';return;}
    const top=Object.entries(head.mean_tide).sort((a,b)=>b[1]-a[1])[0];
    moonInfo.textContent=`Year ${almanac.reported_year}, ${month.options[m].textContent}: ${(head.illumination*100).toFixed(0)}% lit at the month's first day, moonrise ${head.moonrise_hour.toFixed(1)} h after sunrise, leaning ${head.leaning}. Strongest school this month: ${title(top[0])} (mean tide ${top[1].toFixed(2)}). Cycles ${moon.periods.synodic}/${moon.periods.spin}/${moon.periods.nod} days; great year ${moon.great_year_days} days${almanac.next_grand_alignment_day!=null?`; next grand alignment day ${almanac.next_grand_alignment_day}`:''}. Tide now: ${Object.entries(moonTide(moon,almanac.now.day)).map(([k,v])=>title(k)+' '+v.toFixed(2)).join(', ')}.`;
    const events=(almanac.events||[]).filter(e=>e.day>=m*30&&e.day<(m+1)*30);
    moonEvents.textContent=events.length?'Events: '+events.map(e=>`day ${e.day+1} ${title(e.kind)}${e.school?' of '+title(e.school):''}`).join(' · '):'No notable nights this month.';
  }
  function renderGods(){
    godPanel.hidden=!data.religion;if(!data.religion)return;
    const religion=data.religion;godInfo.replaceChildren();
    make('p',`Cosmology: ${religion.cosmology.name}. ${religion.cosmology.arrangement}`,godInfo);
    for(const status of ['walking','manifest','sleeping']){
      const gods=religion.gods.filter(g=>g.status===status);if(!gods.length)continue;
      make('p',`${title(status)}: `+gods.map(g=>`${g.aspect_name||g.name}${g.saint_of?' (saint of '+g.saint_of.replace('god_','')+')':''}`).join(' · '),godInfo);
    }
    for(const [civ,faith] of Object.entries(religion.faiths||{})){
      const card=make('article',undefined,godInfo);card.className='world-card';make('strong',title(civ),card);
      make('p',`Patron ${faith.names?.[faith.patron]||faith.patron||'none'} · worships ${faith.gods.map(g=>faith.names?.[g]||g).join(', ')}${faith.conversion?' · converted by a visitation':''}${faith.sects?.length?' · '+faith.sects.length+' sect(s)':''}${faith.fear?.length?' · fears '+faith.fear.map(f=>f.god_id.replace('god_','')).join(', '):''}`,card);
    }
    for(const v of religion.visitations||[])make('p',`Visitation ${v.index+1}: ${v.god_id.replace('god_','')} at node ${v.node} on day ${v.day}, wrath ${v.wrath}; ${v.ruins.length} ruins, ${v.purged_nests.length} nests driven out, ${v.converted.length} peoples converted${v.departed_age!=null?'; departed in age '+v.departed_age:'; still walking'}.`,godInfo);
    godSelect.replaceChildren();for(const g of religion.gods.filter(g=>g.status==='manifest'||g.status==='sleeping'))make('option',`${g.aspect_name||g.name} (${g.status})`,godSelect).value=g.id;
    targetSelect.replaceChildren();for(const s of data.settlements?.sites||[])make('option',s.name,targetSelect).value=s.uid;
    const walking=religion.gods.some(g=>g.status==='walking');
    summonButton.disabled=busy||!live||!godSelect.options.length||!targetSelect.options.length;departButton.disabled=busy||!live||!walking;
  }
  // Animals and monsters are two independent passes; the atlas shows both at once.
  const TIERS=['','harmless','can hurt you','kills the careless','kills the prepared','campaign threat'];
  function habitat(){return [data.wildlife,data.beast_nests].filter(Boolean);}
  function allNests(){return habitat().flatMap(h=>h.sites||[]);}
  function allProfiles(){return habitat().flatMap(h=>h.profiles||[]);}
  function allDiagnostics(){return habitat().flatMap(h=>h.diagnostics||[]);}
  function visibleNests(){return allNests().filter(s=>!speciesSelect.value||s.species_id===speciesSelect.value);}
  function inspectNest(){
    const nest=allNests().find(s=>s.id===nestSelect.value);
    const profile=allProfiles().find(p=>p.id===(nest?.species_id||speciesSelect.value));
    const diagnostic=allDiagnostics().find(d=>d.species_id===profile?.id);
    const tier=nest?.tier??profile?.tier;
    const danger=tier?` Tier ${tier} (${TIERS[tier]}).`:'';
    nestInfo.textContent=profile?`${profile.name} / ${profile.role||profile.family} / ${profile.kind}.${danger} Habitat: ${profile.medium}; ${profile.temperature.join(' to ')} C; required fields: ${Object.entries(profile.requires).map(([k,v])=>title(k)+' >= '+v).join(', ')||'none'}. ${nest?`${nest.layer}: suitability ${(nest.suitability*100).toFixed(0)}%; ${nest.den?'den':'range'} over ${nest.range_m.toFixed(0)} m.`:`no habitat placed (${diagnostic?.placed??0} anchors).`}`:'Select a species or map marker. Cyan circles: animals; coral: monsters. Habitat anchors are static proposals, not a simulated population; recipe 3 age transitions apply explicit local fantasy-threat rules.';
  }
  function heroSite(p){if(!p?.presence)return null;const k=p.presence.site_kind,u=p.presence.uid;const s=k==='nest'?(data.beast_nests?.sites||[]).find(n=>n.id===u):k==='ruin'?(data.ruins||[]).find(r=>r.uid===u):k==='camp'?(data.heroes?.camps||[]).find(c=>c.uid===u):k==='college'?(data.magic?.colleges||[]).find(c=>c.id===u):k==='hamlet'?(data.humans?.hamlets||[]).find(c=>(c.uid||c.id)===u):k==='fortress'?(data.humans?.fortresses||[]).find(c=>(c.uid||c.id)===u):k==='port'?(data.fisheries?.ports||[]).find(c=>c.id===u):k==='key_location'?(data.key_locations?.sites||[]).find(c=>c.id===u):k==='shrine'?(()=>{const site=(data.religion?.sites||[]).find(c=>c.id===u);const ruin=site&&(data.ruins||[]).find(r=>r.id===site.ruin_id);return ruin?{...ruin,name:p.site_name||ruin.name}:null;})():(data.settlements?.sites||[]).find(c=>c.uid===u);return s&&s.x!=null?s:null;}
  function heroCast(){const h=data.heroes;return h?.status==='ok'?[...h.people,...h.dreads]:[];}
  function heroColor(p){const g=p.alignment?.good??0;return g>.34?'rgb(255,220,126)':g<-.34?'rgb(214,64,64)':'rgb(186,192,204)';}
  function drawHeroPin(ctx,x,y,p,offset){const r=p.role==='dread'?8:6;x+=offset;ctx.beginPath();ctx.moveTo(x,y-r);ctx.lineTo(x+r,y);ctx.lineTo(x,y+r);ctx.lineTo(x-r,y);ctx.closePath();ctx.fillStyle=heroColor(p);ctx.fill();ctx.lineWidth=p.role==='dread'?2:1;ctx.strokeStyle=p.role==='dread'?'#3b0d0d':'#111';ctx.stroke();}
  function renderHeroes(){
    heroCards.replaceChildren();heroPanel.hidden=!data.heroes;if(!data.heroes)return;const h=data.heroes;
    if(h.status!=='ok'){const p=make('p',`Hero generator failed: ${h.error}`,heroCards);p.style.color='#d64040';return;}
    make('p',`${h.summary.precipitated} of ${h.summary.candidates} candidates precipitated · ${h.summary.living} living · ${h.summary.legends} legends · ${h.summary.dreads} dreads · ${h.summary.orgs??0} orgs · ${h.summary.camps??0} camps · ${h.summary.hooks??0} hooks · ${h.summary.realms} realms · policy revisions ${Object.values(h.policy_revision).join('/')}`,heroCards).style.gridColumn='1 / -1';
    const civName=id=>data.civilizations?.entities.find(e=>e.id===id)?.name||title(id||'');const nameOf=uid=>heroCast().find(p=>p.uid===uid)?.display_name||uid;
    const sections=[['Living cast',h.people.filter(p=>p.status==='living')],['Legends',h.people.filter(p=>p.status==='legend')],['Dreads',h.dreads]];
    for(const [label,list] of sections){
      if(!list.length||(label==='Legends'&&hideLegends.checked)||(label==='Dreads'&&hideDreads.checked))continue;
      const heading=make('h3',label,heroCards);heading.style.gridColumn='1 / -1';heading.style.margin='8px 0 0';
      for(const p of list){
        const card=make('article',undefined,heroCards);card.className='world-card';if(p.status==='legend')card.style.opacity='.65';
        make('strong',p.display_name,card);
        if((p.faces||[]).length>1){const mask=make('p',`Appears as: ${p.faces[0].label} face, a ${p.faces[0].apparent_role} (${p.faces[0].alignment.label})`,card);mask.style.color='#e7caff';}
        const who=p.role==='dread'?`${title(p.family||'beast')} · nest tier ${p.nest_tier}`:`${civName(p.civilization_id)} (${title(p.race_id)})${p.school?' · '+p.school:''}${p.seat?' · '+title(p.seat):''}`;
        make('p',`${who} · ${title(p.role)} · ${p.archetype_name||'No archetype'} · ${p.alignment.label} · ${title(p.tier)}, fame ${p.fame}`,card);
        const site=heroSite(p);const realm=h.realms.find(r=>r.uid===p.realm_uid);
        make('p',p.presence?`Position: ${title(p.presence.situation)} at ${site?.name||p.presence.uid}${realm?' · '+realm.name:''}`:`Legend of Age ${p.born_age??p.deeds[0]?.age} · no presence in the world`,card);
        make('p',`Now: ${p.situation}`,card);
        const deeds=make('details',undefined,card);make('summary','Event log and bonds',deeds);for(const e of p.log)make('p',`Age ${e.age} · ${e.event_id}: ${e.text}`,deeds);
        if(p.claim)make('p',`Claim: ${p.claim.verb} ${p.claim.target_name}`,deeds);if(p.rivals?.length)make('p','Rivals: '+p.rivals.map(nameOf).join(', '),deeds);if(p.kin?.length)make('p','Kin: '+p.kin.map(nameOf).join(', '),deeds);if(p.allies?.length)make('p','Allies: '+p.allies.map(nameOf).join(', '),deeds);if(p.predecessor_uid)make('p','Inherits from '+nameOf(p.predecessor_uid),deeds);
        const offered=(h.quest_hooks||[]).filter(q=>q.giver_uid===p.uid);for(const q of offered)make('p',`Asks: “${q.stated_purpose}”`,deeds);if(p.companion?.eligible)make('p',`Would join the player once ${p.companion.join_condition}.`,deeds);
        if(p.persona){const persona=make('details',undefined,card);make('summary','Persona',persona);for(const [k,v] of [['Belief',p.persona.belief],['Wants',p.persona.wants],['Fears',p.persona.fears],['Manner',p.persona.manner],['Voice',p.persona.voice],['Tells',p.persona.tells],['Toward a stranger',p.persona.toward_player],['Lies',p.persona.lies],['Cornered',p.persona.cornered],['Never',p.persona.never.join('; ')]])make('p',`${k}: ${v}`,persona);const line=make('p',`“${p.persona.line}”`,persona);line.style.fontStyle='italic';}
        if(showTruth.checked){const truth=make('details',undefined,card);truth.open=true;make('summary','Truth',truth);make('p',`Faces: ${(p.faces||[]).map(f=>`${f.label} (${f.alignment.label}, ${f.claim.verb} ${f.claim.target_name})`).join(', ')||'one face'}`,truth);make('p',`Alignment ${p.alignment.law.toFixed(2)} law / ${p.alignment.good.toFixed(2)} good${p.alignment.drift?` · drift ${p.alignment.drift.law}/${p.alignment.drift.good} per age`:''} · selection features: ${(p.selectable||[]).join(', ')}`,truth);for(const q of (h.quest_hooks||[]).filter(q=>q.giver_uid===p.uid))make('p',`${q.unwitting?'⚠ unwitting':'honest'} · “${q.stated_purpose}” → ${q.actual_effect.kind} ${q.actual_effect.node_id||q.actual_effect.uid||''} ${q.actual_effect.action||(q.actual_effect.intensity_delta>0?'+':'')+(q.actual_effect.intensity_delta??'')} ${q.actual_effect.school||''}`,truth);}
      }
    }
    if(h.orgs?.length){const line=make('p','Orgs: '+h.orgs.map(o=>`${o.name} (${o.kind}${o.charter?.against?', against the '+o.charter.against:''}, ${o.members.length} ${o.members.length===1?'member':'members'})`).join(' · '),heroCards);line.style.gridColumn='1 / -1';}
    if(h.camps?.length){const line=make('p','Camps: '+h.camps.map(c=>`${c.name}${c.leader_uid?' led by '+nameOf(c.leader_uid):''}`).join(' · '),heroCards);line.style.gridColumn='1 / -1';}
    if(h.relics?.length){const line=make('p','Relics resting in ruins: '+h.relics.map(r=>r.name).join(' · '),heroCards);line.style.gridColumn='1 / -1';}
    if(h.realms.length)make('p','Realms: '+h.realms.map(r=>`${r.name} (${r.civilization_name}, ${r.city_uids.length} ${r.city_uids.length===1?'city':'cities'})`).join(' · '),heroCards).style.gridColumn='1 / -1';
    if(showTruth.checked&&h.rolls?.length){const ledger=make('details',undefined,heroCards);ledger.style.gridColumn='1 / -1';make('summary','Precipitation rolls (every candidate, precipitated or not)',ledger);for(const r of h.rolls)make('p',`${r.precipitated?'✓':'✗'} ${r.kind} · ${r.event_id} (Age ${r.age}) · chance ${r.chance} · roll ${r.roll}`,ledger);}
    if(h.mantles.length)make('p','Open mantles: '+h.mantles.map(m=>`${m.claim.verb} ${m.claim.target_name}, vacant since Age ${m.vacant_since_age}`).join(' · '),heroCards).style.gridColumn='1 / -1';
  }
  const webOf=uid=>data.story_web?.status==='ok'?data.story_web.webs.find(w=>w.uid===uid):null;
  function drawWeb(web,size){
    const width=Math.round(size*1.3),cx=width/2,cy=size/2;
    const s=svgEl('svg',{viewBox:`0 0 ${width} ${size}`,width,height:size,class:'story-web'});
    const c=cy,rings=[c*.24,c*.44,c*.64],rim=c*.76;
    const angles=Object.fromEntries((data.story_web.tropes||[]).map(t=>[t.id,t]));
    const at=(id,r)=>{const a=(angles[id]?.angle||0)*Math.PI/180;return [cx+Math.cos(a)*r,cy-Math.sin(a)*r];};
    for(const r of rings)svgEl('circle',{cx,cy,r,fill:'none',stroke:'#3a4b58','stroke-width':.8},s);
    svgEl('circle',{cx,cy,r:rim,fill:'none',stroke:'#5b6f7d','stroke-width':1.2},s);
    const stack={};for(const sp of web.spokes){const k=String(angles[sp.trope_id]?.angle||0);stack[k]=(stack[k]||[]).concat(sp.trope_id);}
    const fan=id=>{const g=stack[String(angles[id]?.angle||0)]||[id];return (g.indexOf(id)-(g.length-1)/2)*6;};
    const atf=(id,r)=>{const a=((angles[id]?.angle||0)+fan(id))*Math.PI/180;return [cx+Math.cos(a)*r,cy-Math.sin(a)*r];};
    const eligible=new Set(web.spokes.map(sp=>sp.trope_id));
    web.acts.forEach((act,i)=>{const [x1,y1]=atf(web.offered,rings[i]);for(const th of web.threads){const [x2,y2]=atf(th.to,eligible.has(th.to)?rings[i]:rim);const open=th.condition.kind==='open';svgEl('line',{x1,y1,x2,y2,stroke:th.cut?'#d85a30':open?'#9fb3c4':'#5f7382','stroke-width':th.cut?1.2:open?1:.7,'stroke-dasharray':open&&!th.cut?'':'4 3'},s);}});
    for(const sp of web.spokes){const [x,y]=atf(sp.trope_id,rim);const on=sp.trope_id===web.offered;svgEl('line',{x1:cx,y1:cy,x2:x,y2:y,stroke:on?'#ffd67e':'#7f93a3','stroke-width':on?2.4:Math.max(.6,Math.min(2.2,sp.weight/2))},s);const [lx,ly]=atf(sp.trope_id,rim+8);const t=svgEl('text',{x:lx,y:ly,'font-size':8.5,fill:on?'#ffd67e':'#b8c6d1','text-anchor':lx<cx-3?'end':lx>cx+3?'start':'middle','dominant-baseline':'middle'},s);t.textContent=sp.name;}
    web.acts.forEach((act,i)=>{const [x,y]=atf(web.offered,rings[i]);svgEl('circle',{cx:x,cy:y,r:4.5,fill:'#ffd67e',stroke:'#20313c'},s);});
    const a=web.alignment.angle*Math.PI/180,mag=Math.min(1,Math.hypot(web.alignment.law,web.alignment.good));
    svgEl('circle',{cx:cx+Math.cos(a)*rim*mag,cy:cy-Math.sin(a)*rim*mag,r:5,fill:heroColor({alignment:web.alignment}),stroke:'#111','stroke-width':1.2},s);
    svgEl('circle',{cx,cy,r:3,fill:'#b8c6d1'},s);
    return s;
  }
  function renderStoryWebs(){
    webCards.replaceChildren();webPanel.hidden=!data.story_web;if(!data.story_web)return;const w=data.story_web;
    if(w.status!=='ok'){const p=make('p',`Story web failed: ${w.error}`,webCards);p.style.color='#d64040';return;}
    const s=w.summary;make('p',`${s.woven} woven · ${s.unwoven} unwoven · ${s.reachable_tropes} of ${s.tropes} tropes reachable · mean ${s.mean_spokes} spokes per hero · policy revisions ${Object.values(w.policy_revision).join('/')}`,webCards).style.gridColumn='1 / -1';
    const shown=w.webs.filter(web=>!(web.role==='dread'&&hideDreads.checked));const offered={};for(const web of shown)offered[web.offered]=(offered[web.offered]||0)+1;
    const hist=make('div',undefined,webCards);hist.style.gridColumn='1 / -1';hist.className='story-histogram';const max=Math.max(1,...Object.values(offered));
    for(const [id,count] of Object.entries(offered).sort((a,b)=>b[1]-a[1]||a[0].localeCompare(b[0]))){const row=make('div',undefined,hist);row.className='story-bar';const label=make('span',(w.tropes.find(t=>t.id===id)?.name||id)+' '+count,row);const bar=make('span',undefined,row);bar.className='story-bar-fill';bar.style.width=`${Math.round(100*count/max)}%`;}
    const condText=th=>th.condition.kind==='open'?'open':th.condition.kind==='alignment'?`if ${th.condition.axis} moves ${th.condition.toward}`:th.condition.kind==='feature'?`needs ${th.condition.facts.join(' + ')}`:`needs claim ${th.condition.verb}`;
    for(const web of shown){
      const card=make('article',undefined,webCards);card.className='world-card story-card';
      make('strong',`${web.display_name} → ${web.spokes[0].name}`,card);
      make('p',`${title(web.role)} · ${web.archetype||'no archetype'} · ${web.alignment.code} (${web.alignment.law.toFixed(2)} law / ${web.alignment.good.toFixed(2)} good) · claim ${web.claim} · ${web.spokes.length} ${web.spokes.length===1?'spoke':'spokes'}`,card);
      card.append(drawWeb(web,300));
      make('p',web.rest.hook.prompt?`Hook: “${web.rest.hook.prompt}”`:'Hook: silent; the world starts this arc.',card);
      make('p',`Armed: ${web.rest.armed.map(a=>`${a.trope_id} ${a.weight}`).join(', ')||'nothing else'} · initiative day ${web.rest.initiative_day}`,card);
      const acts=make('details',undefined,card);make('summary','Acts, options and threads',acts);
      for(const act of web.acts){make('p',`Act ${act.ring}, ${act.title}: “${act.prompt||'…'}” · completes when ${act.completion.target} is ${act.completion.state} · abandons after ${act.abandonment.days} days`,acts);for(const o of act.options)make('p',`   ${o.text} (${o.delta.law>=0?'+':''}${o.delta.law} law, ${o.delta.good>=0?'+':''}${o.delta.good} good; ${o.effect})`,acts);}
      make('p','Threads at any act exit: '+(web.threads.map(th=>`${th.to} [${condText(th)}${th.cut?'; CUT: '+th.cut:''}]`).join(' · ')||'none'),acts);
      if(showTruth.checked){const truth=make('details',undefined,card);truth.open=true;make('summary','Weights and considered tropes',truth);for(const sp of web.spokes)make('p',`${sp.trope_id} = ${sp.weight}: boosts ${sp.breakdown.boosts} [${sp.breakdown.boosted_by.join(', ')}] × alignment ${sp.breakdown.alignment_fit} × archetype ${sp.breakdown.archetype_fit} × claim ${sp.breakdown.claim_fit}`,truth);make('p','Facts: '+web.facts.join(', '),truth);make('p','Constraints: '+JSON.stringify(web.constraints),truth);make('p','Nearest refused: '+web.considered.slice(0,6).map(cn=>`${cn.trope_id} (missing ${cn.missing.join(', ')||'nothing'})`).join(' · '),truth);}
    }
    if(w.unwoven.length){const line=make('p','Unwoven: '+w.unwoven.map(u=>`${u.display_name} (${u.archetype||'no archetype'}; nearest ${u.nearest.map(n=>n.trope_id+' missing '+n.missing.join('+')).join(', ')})`).join(' · '),webCards);line.style.gridColumn='1 / -1';line.style.color='#f0c36b';}
    if(w.unreachable_tropes.length)make('p','Unreachable tropes (need facts no well computes yet): '+w.unreachable_tropes.join(', '),webCards).style.gridColumn='1 / -1';
  }
  function renderNpcRoster(){
    npcCards.replaceChildren();npcPanel.hidden=!data.npcs;if(!data.npcs)return;const r=data.npcs;
    if(r.status!=='ok'){const p=make('p',`NPC roster failed: ${r.error}`,npcCards);p.style.color='#d64040';return;}
    const s=r.summary,wide=el=>{el.style.gridColumn='1 / -1';return el;};
    wide(make('p',`${s.total.toLocaleString()} people across ${s.sites} sites · ${s.alive.toLocaleString()} alive · ${s.dead} dead · ${s.important} earmarked (${(100*s.important_fraction).toFixed(1)}%) · ${s.heroes_linked} linked to the cast · policy revisions ${Object.values(r.policy_revision).join('/')}`,npcCards));
    const notes=Object.entries(s).filter(([k,v])=>v&&['unresolved_parent_race','unanchored_sites','roster_mismatches','duplicate_site_keys','important_capped_out','cast_outside_a_planned_site'].includes(k));
    if(notes.length)wide(make('p','Reported: '+notes.map(([k,v])=>`${k.replace(/_/g,' ')} ${v}`).join(' · '),npcCards)).style.color='#f0c36b';
    const bySite={};for(const p of r.people){(bySite[p.site_uid]=bySite[p.site_uid]||[]).push(p);}
    const table=wide(make('details',undefined,npcCards));make('summary',`Posts by site (${r.sites.length})`,table);
    for(const site of r.sites)make('p',`${site.name} — ${title(site.kind)}${site.city_class?', '+site.city_class:''} · ${site.posts} posts · ${site.civilization_id||'unknown people'}${site.plan_status&&site.plan_status!=='complete'?' · plan '+site.plan_status:''}`,table);
    for(const site of r.sites){
      const flagged=(bySite[site.uid]||[]).filter(p=>p.important);if(!flagged.length)continue;
      const card=make('article',undefined,npcCards);card.className='world-card';
      make('strong',site.name,card);
      make('p',`${title(site.kind)}${site.city_class?' · '+site.city_class:''} · ${site.posts} posts · ${site.civilization_id||'unknown people'}`,card);
      for(const p of flagged){
        const verbs=(r.post_verbs||{})[p.post]||[];
        const line=make('p',`${p.name} — ${p.post.replace(/_/g,' ')}${p.hero_uid?' (cast)':''}${p.status==='dead'?' · dead':''}${verbs.length?' · offers '+verbs.join(', '):''}`,card);
        if(p.status==='dead')line.style.color='#9aa0a6';
      }
    }
    const loose=(bySite['null']||bySite[null]||[]).filter(p=>p.important);
    if(loose.length)wide(make('p','Cast standing outside a planned site: '+loose.map(p=>`${p.name} (${p.presence_kind||'no presence'}${p.status==='dead'?', dead':''})`).join(' · '),npcCards)).style.color='#9aa0a6';
  }
  function visibleKeyLocations(){
    const sites=data.key_locations?.status==='ok'?data.key_locations.sites:[];
    return keyFamily.value==='all'||!keyFamily.value?sites:sites.filter(s=>s.family===keyFamily.value);
  }
  function keyColor(site){
    const rgb=data.key_locations?.families?.[site.family]?.color;
    return rgb?`rgb(${rgb[0]},${rgb[1]},${rgb[2]})`:'#d8d2c4';
  }
  function renderKeyLocations(){
    keyCards.replaceChildren();keyPanel.hidden=!data.key_locations;if(!data.key_locations)return;
    const block=data.key_locations;
    if(block.status!=='ok'){const p=make('p',`Key locations failed: ${block.error}`,keyCards);p.style.color='#d64040';return;}
    const s=block.summary,wide=el=>{el.style.gridColumn='1 / -1';return el;};
    const tiers=Object.entries(s.by_tier).sort().map(([t,n])=>`T${t} ${n}`).join(' · ');
    wide(make('p',`${s.sites} locations (${tiers}) · ${s.dungeons} occupied complexes · ${block.catalogue_count} archetypes, catalogue revision ${block.catalogue_revision}`,keyCards));
    if(block.chains.length||block.clusters.length){
      const runs=block.chains.map(c=>`${c.name.toLowerCase()} \u00d7${c.members.length}`).join(', ');
      wide(make('p',`${block.chains.length} chains (${runs}) \u00b7 ${block.clusters.length} clusters`,keyCards)).style.color='#9ab8c4';
    }
    const absent=block.diagnostics.filter(d=>d.placed===0);
    if(absent.length)wide(make('p',`This world grew none of: ${absent.map(d=>d.archetype.replace(/_/g,' ')).join(', ')}`,keyCards)).style.color='#9aa0a6';
    const byFamily={};for(const site of visibleKeyLocations())(byFamily[site.family]=byFamily[site.family]||[]).push(site);
    for(const family of Object.keys(byFamily).sort()){
      const rows=byFamily[family].slice().sort((a,b)=>b.tier-a.tier||b.threat-a.threat||a.name.localeCompare(b.name));
      const card=make('article',undefined,keyCards);card.className='world-card';
      const head=make('h3',`${block.families[family]?.name||family} — ${rows.length}`,card);head.style.color=keyColor(rows[0]);head.style.margin='0 0 8px';
      for(const site of rows.slice(0,14)){
        const was=site.succession?` · was ${site.succession.from_occupant}`:'';
        const inside=site.interior?` · ${site.interior.levels} levels, ${site.interior.chambers.length} chambers`:'';
        const line=make('p',`${site.name} — ${site.kind.replace(/_/g,' ')} · T${site.tier} threat ${site.threat} · ${site.state}, ${site.occupant}${was}${inside}`,card);
        line.style.margin='4px 0';if(site.occupant==='none')line.style.color='#9aa0a6';
      }
      if(rows.length>14)make('p',`… and ${rows.length-14} more`,card).style.color='#9aa0a6';
    }
  }
  function rebuildKeyFamilies(){
    const block=data.key_locations?.status==='ok'?data.key_locations:null;
    const chosen=keyFamily.value||'all';keyFamily.replaceChildren();
    const all=make('option','All families',keyFamily);all.value='all';
    for(const family of Object.keys(block?.families||{}).sort()){
      const counted=block.sites.filter(s=>s.family===family).length;if(!counted)continue;
      const option=make('option',`${block.families[family].name} (${counted})`,keyFamily);option.value=family;
    }
    keyFamily.value=[...keyFamily.options].some(o=>o.value===chosen)?chosen:'all';
  }
  keyFamily.onchange=()=>{renderKeyLocations();drawAtlas();};showKeyLocations.onchange=drawAtlas;
  function rebuildNests(){
    const animals=data.wildlife,monsters=data.beast_nests;
    nestSummary.textContent=monsters?`${animals?.sites.length||0} animal hunting grounds and ${monsters.sites.length} monster territories over ${allDiagnostics().length} candidate species. ${monsters.limits}`:data.build_stages?'Beasties and animals appear at stage 13.':'Nests appear from settlement stage 7 onward.';
    const old=speciesSelect.value;speciesSelect.replaceChildren();make('option','All species',speciesSelect).value='';
    for(const d of allDiagnostics())make('option',`${d.name} t${d.tier} (${d.placed})`,speciesSelect).value=d.species_id;
    if([...speciesSelect.options].some(o=>o.value===old))speciesSelect.value=old;
    rebuildNestLocations();
  }
  function rebuildNestLocations(){
    nestSelect.replaceChildren();make('option','Select a nest location',nestSelect).value='';
    for(const n of visibleNests())make('option',`${n.name}: ${n.layer}, ${n.x}, ${n.z}`,nestSelect).value=n.id;
    inspectNest();drawAtlas();
  }
  speciesSelect.onchange=rebuildNestLocations;nestSelect.onchange=()=>{inspectNest();drawAtlas();};showNests.onchange=drawAtlas;
  const details=make('details',undefined,viewer);make('summary','Independent overlays and opacity',details);const layers=make('div',undefined,details);layers.id='world-layers';
  const atlas=make('canvas',undefined,viewer);atlas.id='world-atlas';atlas.width=1000;atlas.height=500;
  const civilizationLegend=make('div',undefined,viewer);civilizationLegend.id='world-civilizations';
  const inspect=make('p','Move over the atlas for field values and overlapping influences.',viewer);inspect.id='world-inspect';
  const skySelect=make('select',undefined,viewer);skySelect.id='world-sky-select';skySelect.hidden=true;
  const skyCanvas=make('canvas',undefined,viewer);skyCanvas.width=850;skyCanvas.height=260;skyCanvas.id='world-sky-mesh';
  const skyInfo=make('p','',viewer);const summary=make('p','',viewer);summary.id='world-summary';
  const cards=make('div',undefined,viewer);cards.className='world-cards';
  const regions=make('details',undefined,viewer);make('summary','Regional presence and limiting conditions',regions);const regionText=make('div',undefined,regions);
  const historyCards=make('div',undefined,viewer);historyCards.id='world-history';historyCards.className='world-cards';
  const heroPanel=make('section',undefined,viewer);heroPanel.id='world-heroes-panel';heroPanel.hidden=true;make('h2','The cast',heroPanel);make('p','Larger-than-life people precipitated from this world\'s history by the separate hero generator: heirs of ruins, victors of wars, named beasts. Race, alignment, archetype and position come from the exported record; nothing here is rolled from a template.',heroPanel);
  const heroFilters=make('p',undefined,heroPanel);const heroFilter=(label)=>{const l=make('label',undefined,heroFilters);l.style.display='inline-flex';l.style.alignItems='center';l.style.gap='6px';l.style.marginRight='18px';const c=make('input',undefined,l);c.type='checkbox';l.append(label);return c;};const hideLegends=heroFilter('Hide legends'),hideDreads=heroFilter('Hide dreads'),showTruth=heroFilter('Show true faces and selection features');
  const heroCards=make('div',undefined,heroPanel);heroCards.id='world-heroes';heroCards.className='hero-cards';heroCards.style.display='grid';heroCards.style.gridTemplateColumns='repeat(auto-fit,minmax(300px,1fr))';heroCards.style.gap='12px';heroCards.style.alignItems='start';hideLegends.onchange=hideDreads.onchange=showTruth.onchange=()=>{renderHeroes();renderStoryWebs();};
  const webPanel=make('section',undefined,viewer);webPanel.id='world-story-webs-panel';webPanel.hidden=true;make('h2','Story webs',webPanel);make('p','Every living hero\'s web, compiled by the separate story-web package from the cast and the world: the spokes their record admits, weighted deterministically (no draw, no model), the offered resting hook on the heaviest spoke, three bound acts with options, and the threads each act can exit along. Angle is alignment (good right, lawful up), rings are acts, the rim is the next rest.',webPanel);
  const webCards=make('div',undefined,webPanel);webCards.id='world-story-webs';webCards.style.display='grid';webCards.style.gridTemplateColumns='repeat(auto-fit,minmax(340px,1fr))';webCards.style.gap='12px';webCards.style.alignItems='start';
  const keyPanel=make('section',undefined,viewer);keyPanel.id='world-key-locations-panel';keyPanel.hidden=true;make('h2','Key locations',keyPanel);make('p','The charged places between the settlements, from the separate key-locations package: caves, mines, barrows, shrines, watchtowers, lairs, drowned ruins and wonders. A location is an archetype plus a derived state and occupant, so a ruined fortress nobody holds is a forgotten fortress and an occupied tier-2 complex is a dungeon - neither is an archetype. Tier is physical scale, never danger; threat is danger, on the 1-5 creature rubric.',keyPanel);
  const keyCards=make('div',undefined,keyPanel);keyCards.id='world-key-locations';keyCards.className='world-cards';keyCards.style.alignItems='start';
  const npcPanel=make('section',undefined,viewer);npcPanel.id='world-npcs-panel';npcPanel.hidden=true;make('h2','The people',npcPanel);make('p','One record per staffed post in every planned city, hamlet and castle, from the separate npc-roster package, with the cast folded in by uid. Thousands of people, so only the earmarked few are listed: those are the ones a quest generator may offer as givers, and the earmark is capped per site so the set stays bounded. Everyone else is counted by site below.',npcPanel);
  const npcCards=make('div',undefined,npcPanel);npcCards.id='world-npcs';npcCards.style.display='grid';npcCards.style.gridTemplateColumns='repeat(auto-fit,minmax(320px,1fr))';npcCards.style.gap='12px';npcCards.style.alignItems='start';
  const colors={weave:[180,143,247],umbral:[109,103,176],infernal:[243,83,59],radiant:[255,220,126],fire:[207,86,37],water:[65,156,202],earth:[67,120,51],air:[176,210,213],holy:[255,220,126],primordial:[98,213,137],reef:[83,214,204],lagoon:[94,204,231],estuary:[118,160,101],kelp:[71,147,107],fjord:[92,160,189],boreal:[71,129,103],tundra:[178,188,149],ice_cap:[227,245,255],snow:[242,245,250],water_ice:[178,227,250]};
  let overlays={},nodePoints=[];
  const rgbFor=key=>colors[key.replace('ley_','').replace('zone_','')]||[216,166,110];
  const civilizationColor=index=>data.civilizations?.entities.find(e=>e.region_index===index)?.presentation?.map_color_rgb||[128,128,128];
  function rebuild(){
    advanceButton.disabled=busy||!live||!completeWorld.beast_nests;
    civilizationLegend.replaceChildren();
    if(data.civilizations){make('p','Civilization regions follow reachable city support areas; wilderness remains unassigned. Larger square pins are capitals; small dots are hamlets (green farming, amber resource, cyan coastal), slate keeps are fortresses and stone walls with a gap are ruins.',civilizationLegend);for(const entity of data.civilizations.entities){const capital=data.settlements?.sites.find(s=>s.node===entity.capital_node);const label=make('span',`${entity.name}: ${entity.city_count} cities${capital?' · Capital: '+capital.name:''}. `,civilizationLegend);label.style.color=`rgb(${civilizationColor(entity.region_index).join(',')})`;}}
    nodePoints=[];for(let z=0;z<data.config.size;z++)for(let x=0;x<(z===0||z===data.config.size-1?1:data.config.size-1);x++)nodePoints.push([x,z]);
    for(const key of Object.keys(data.layers))if(!layerInfo[key])layerInfo[key]=[title(key),'relative'];
    const old=field.value;field.replaceChildren();
    for(const key of [...Object.keys(data.layers).filter(k=>!data.build_stages||!['ley_holy','ley_primordial'].includes(k)),'snow','water_ice']){const opt=make('option',title(key),field);opt.value=key;}
    field.value=old&&[...field.options].some(o=>o.value===old)?old:data.layers.biome_variant?'biome_variant':data.layers.natural_biome?'natural_biome':data.layers.biome?'biome':'height';
    layers.replaceChildren();overlays={};
    for(const key of [...Object.keys(data.layers).filter(k=>(k.startsWith('ley_')&&(!data.build_stages||!['ley_holy','ley_primordial'].includes(k)))||k.startsWith('zone_')||(data.habitats?.aquatic||[]).includes(k)||['boreal','tundra','ice_cap'].includes(k)),'snow','water_ice']){
      const label=make('label',undefined,layers),check=make('input',undefined,label);check.type='checkbox';label.append(title(key));
      const alpha=make('input',undefined,label);alpha.type='range';alpha.min=0;alpha.max=1;alpha.step=.05;alpha.value=.55;alpha.setAttribute('aria-label',title(key)+' opacity');
      overlays[key]={check,alpha};check.onchange=alpha.oninput=drawAtlas;
    }
    skySelect.replaceChildren();make('option','Select a floating island',skySelect).value='';
    for(const island of data.sky?.islands||[]){const opt=make('option',`${island.id} · ${island.altitude_m.toFixed(0)} m altitude`,skySelect);opt.value=island.id;}
    cards.replaceChildren();
    for(const s of data.world_economy?.sites||[]){
      const card=make('article',undefined,cards);card.className='world-card';make('strong',s.name,card);
      make('p',`${s.layer} · Food coverage ${(s.food_coverage*100).toFixed(0)}% · Annual shortage ${s.annual_shortage.toFixed(2)} · Lean months ${s.lean_months.join(', ')||'none'}`,card);
      const source=(data.settlements?.sites||[]).find(site=>site.id===s.site_id);
      if(source){const civilization=data.civilizations?.entities.find(e=>e.id===source.civilization_id);make('p',`${civilization?.name||title(source.population_profile)} · ${title(source.city_class)} · Suitability ${source.suitability.toFixed(2)}`,card);}
      if(source?.suitability_factors){const why=make('details',undefined,card);make('summary','Why this location?',why);make('p',Object.entries(source.suitability_factors).map(([k,v])=>`${title(k)} ${v>=0?'+':''}${v.toFixed(2)}`).join(' · '),why);make('p',`Community traits: ${source.community_traits?.join(', ')||'settled'}. ${source.reason}`,why);}
      const ports=(data.fisheries?.ports||[]).filter(p=>p.core_id===s.site_id);
      for(const p of ports)make('p',`${p.id}: ${p.role}; harbor ${p.harbor_quality.toFixed(2)}, ${p.worked_area_km2.toFixed(2)} km² exclusive fishing grounds, ${p.delivered_food.toFixed(2)} annual food units.`,card);
    }
    historyCards.replaceChildren();
    if(data.build_stages){make('h3',data.phases.titles[stage-1],historyCards);make('p',`${data.settlements?.sites.length||0} active cities · ${data.ruins?.length||0} ruins.`,historyCards);for(const ruin of data.ruins||[]){const card=make('article',undefined,historyCards);card.className='world-card';make('strong',ruin.name+' — Ruins',card);make('p',`Age ${ruin.destroyed_age} · Source culture: ${ruin.source_culture}`,card);make('p',ruin.reason,card);if(ruin.new_node_school)make('p',`Now a ${ruin.new_node_school} leyline key point${ruin.legacy?` (intensity ${ruin.legacy.intensity}, by ${ruin.legacy.basis})`:''}.${ruin.evidence?.moon_tide!=null?` The moon's ${ruin.cause} tide that day was ${ruin.evidence.moon_tide.toFixed(2)}.`:''}`,card);}}
    regionText.replaceChildren();for(const region of data.regions?.influences||[])make('p',`${title(region.id)}: ${region.reason} · ${region.area_km2.toFixed(2)} km² influence above display threshold`,regionText);
    const routes=data.transport?.routes||[];
    summary.textContent=`${data.fisheries?.ports.length||0} coastal hamlets · ${routes.filter(r=>r.mode==='sea').length} sea routes · ${routes.filter(r=>r.mode==='air').length} air routes. Fishing delivery ${(data.fisheries?.delivered_annual_food||0).toFixed(2)} / ${(data.fisheries?.potential_annual_food||0).toFixed(2)} potential units. Seed ${data.config.seed}.`;
    rebuildNests();renderMoon();renderGods();renderHeroes();renderStoryWebs();renderNpcRoster();rebuildKeyFamilies();renderKeyLocations();drawAtlas();drawSky();
  }
  function values(key){
    if(['snow','water_ice'].includes(key))return data.seasonal_environment?.months[Number(month.value)]?.[key];
    const grid=data.layers[key];
    const school=key.startsWith('ley_')&&!['ley_holy','ley_primordial'].includes(key)?key.slice(4):null;
    if(!moonlit.checked||!grid||!data.lunar_almanac?.months||!data.layers.lunar_sensitivity||!(school||key==='magic_density'))return grid;
    const head=data.lunar_almanac.months[Number(month.value)],tides=Object.values(head.mean_tide);
    const tide=school?head.mean_tide[school]:tides.reduce((a,b)=>a+b,0)/tides.length,sway=data.layers.lunar_sensitivity;
    return grid.map((row,z)=>row.map((v,x)=>v*(1+sway[z][x]*(tide-1))));
  }
  function drawAtlas(){
    const founding=data.settlements?.founding;
    foundingLog.hidden=!founding;
    const cultureName=id=>data.civilizations?.entities.find(e=>e.id===id)?.name||id;
    foundingText.textContent=founding?`${founding.placed_cities} / ${founding.target_cities} cities · ${founding.turns} rounds · ${founding.years_per_round||250} years per round · years ${founding.start_year||0}–${founding.end_year??0} · ${founding.stop_reason.replaceAll('_',' ')}\n`+founding.events.map(e=>`Year ${e.founding_year??((founding.start_year||0)+(e.turn-1)*(founding.years_per_round||250))} · Turn ${e.turn} · ${e.parent_race_id} · ${e.status.replaceAll('_',' ')}${e.population_profile?' · '+cultureName(e.population_profile):''}${e.migration_source_node!=null?' · from node '+e.migration_source_node+' ('+cultureName(e.source_civilization_id)+')':''}${e.cultural_branch?' · cultural branch':''}${e.diaspora_reason?' · '+e.diaspora_reason.replaceAll('_',' '):''}${e.diaspora_bonus?' · parent bonus city':''} · ${e.founding_capital?'separate parent origin':'reach '+Math.round(e.radius_m)+' m'}`).join('\n'):'';

    const n=data.config.size,key=field.value,grid=values(key);if(!grid)return;
    const small=document.createElement('canvas');small.width=n;small.height=n;const c=small.getContext('2d'),im=c.createImageData(n,n);
    let lo=Infinity,hi=-Infinity;for(const row of grid)for(const v of row){lo=Math.min(lo,v);hi=Math.max(hi,v);}
    for(let z=0;z<n;z++)for(let x=0;x<n;x++){
      const v=grid[z][x];let color=key==='biome_variant'?data.terrain.biomes.find(b=>b.id===data.layers.natural_biome[z][x]).color:['biome','natural_biome'].includes(key)?data.terrain.biomes.find(b=>b.id===v).color:[45+170*(v-lo)/(hi-lo||1),70+145*(v-lo)/(hi-lo||1),90+125*(v-lo)/(hi-lo||1)];
      if(key==='civilization_region')color=v<0?[44,55,64]:civilizationColor(v);
      for(const [name,{check,alpha}] of Object.entries(overlays))if(check.checked){const value=values(name)?.[z]?.[x]||0,a=Math.min(1,Math.max(0,value))*Number(alpha.value),t=rgbFor(name);color=color.map((v,i)=>v*(1-a)+t[i]*a);}
      if(window.debugBiomeFilter!=null&&data.layers.natural_biome?.[z]?.[x]!==window.debugBiomeFilter)color=[36,44,49];
      const at=(z*n+x)*4;im.data.set([...color.map(Math.round),255],at);
    }
    c.putImageData(im,0,0);const ctx=atlas.getContext('2d');ctx.imageSmoothingEnabled=false;ctx.drawImage(small,0,0,atlas.width,atlas.height);
    if(key==='biome_variant'){ctx.lineWidth=1;for(let z=0;z<n;z++)for(let x=0;x<n;x++)if(grid[z][x]>=0){ctx.strokeStyle=magicOutline(grid[z][x]);ctx.strokeRect(x*atlas.width/n+.5,z*atlas.height/n+.5,atlas.width/n-1,atlas.height/n-1);}}
    const project=([x,z])=>[x/(n-1)*atlas.width,z/(n-1)*atlas.height];
    if(showRoutes.checked)for(const route of data.transport?.routes||[]){
      const path=route.mode==='air'?route.path:(route.nodes||[]).map(i=>nodePoints[i]);ctx.strokeStyle=route.mode==='air'?'#e7caff':route.mode==='sea'?'#7ff2e5':'#f5cf91';ctx.globalAlpha=route.capacity[Number(month.value)]>0?.85:.2;ctx.lineWidth=1.4;ctx.beginPath();
      for(let i=1;i<path.length;i++){const a=project(path[i-1]),b=project(path[i]);if(Math.abs(a[0]-b[0])<atlas.width/2){ctx.moveTo(...a);ctx.lineTo(...b);}}ctx.stroke();
    }ctx.globalAlpha=1;
    // Rural sites draw under the city pins: they are numerous and the cities are the
    // landmarks. Without these the hinterland reads as empty, though a default world
    // places dozens of hamlets and a dozen fortresses in it.
    for(const h of data.humans?.hamlets||[]){const [x,y]=project([h.x,h.z]),role=h.role||'';ctx.fillStyle=/harbor|fishing|landing/.test(role)?'#8ff6ed':role==='resource'?'#edc17e':'#9fd79a';ctx.beginPath();ctx.arc(x,y,2.5,0,Math.PI*2);ctx.fill();}
    // A crenellated keep, the same silhouette and slate the globe already uses for a
    // fortress. It was a thin outlined triangle, which at four pixels beside a filled
    // hamlet dot was one small pale mark next to another.
    for(const f of data.humans?.fortresses||[]){const [x,y]=project([f.x,f.z]);ctx.fillStyle='#c7c6d1';ctx.strokeStyle='#202b35';ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(x-4,y+4);ctx.lineTo(x-4,y-4);ctx.lineTo(x-1.5,y-4);ctx.lineTo(x-1.5,y-1.5);ctx.lineTo(x+1.5,y-1.5);ctx.lineTo(x+1.5,y-4);ctx.lineTo(x+4,y-4);ctx.lineTo(x+4,y+4);ctx.closePath();ctx.fill();ctx.stroke();}
    for(const s of data.settlements?.sites||[]){const p=project([s.x,s.z]),radius=s.city_class==='capital'?5:s.city_class==='medium'?4:3;ctx.fillStyle='#fff2bc';ctx.fillRect(p[0]-radius,p[1]-radius,2*radius,2*radius);if(s.city_class==='capital'){ctx.strokeStyle='#fff2bc';ctx.strokeRect(p[0]-8,p[1]-8,16,16);}}
    for(const ruin of data.ruins||[]){const [x,y]=project([ruin.x,ruin.z]);drawRuinIcon(ctx,x,y,6);}
    {const seen={};for(const p of heroCast()){if(p.status!=='living')continue;const s=heroSite(p);if(!s)continue;const key=s.x+','+s.z;const offset=(seen[key]=(seen[key]||0)+1)-1;const [x,y]=project([s.x,s.z]);drawHeroPin(ctx,x,y,p,offset*7);}}
    for(const p of data.fisheries?.ports||[]){const [x,y]=project([p.x,p.z]);ctx.strokeStyle='#8ff6ed';ctx.strokeRect(x-4,y-4,8,8);}
    if($('terrain-icons').checked)for(const f of data.terrain?.features||[]){const [x,y]=project([f.x,f.z]);terrainIcon(ctx,x,y,f.kind,7);}
    for(const landmark of data.regions?.landmarks||[]){const [x,y]=project([landmark.x,landmark.z]);ctx.fillStyle=landmark.kind==='witch_hut'?'#e2a7f1':'#edc17e';ctx.fillText(landmark.kind==='witch_hut'?'W':'T',x,y);}
    if(showKeyLocations.checked&&data.key_locations?.status==='ok'){
      const shown={};for(const s of visibleKeyLocations())shown[s.id]=s;
      const wrap=atlas.width/2;
      for(const chain of data.key_locations.chains||[]){
        const run=chain.members.map(m=>shown[m]).filter(Boolean);
        if(run.length<2)continue;
        ctx.strokeStyle=keyColor(run[0]);ctx.globalAlpha=.4;ctx.lineWidth=1;
        let previous=null;
        ctx.beginPath();
        for(const site of run){
          const [x,y]=project([site.x,site.z]);
          // A run that crosses the seam would otherwise draw a line back across the whole map.
          if(previous===null||Math.abs(x-previous)>wrap)ctx.moveTo(x,y);else ctx.lineTo(x,y);
          previous=x;
        }
        ctx.stroke();ctx.globalAlpha=1;
      }
    }
    if(showKeyLocations.checked)for(const site of visibleKeyLocations()){
      const [x,y]=project([site.x,site.z]);const glyph=data.key_locations.families[site.family]?.glyph||'?';
      ctx.fillStyle=keyColor(site);ctx.globalAlpha=site.tier>=2?1:site.tier===1?.8:.55;
      ctx.font=`${site.tier>=3?15:site.tier===2?12:9}px sans-serif`;ctx.fillText(glyph,x,y);ctx.globalAlpha=1;
    }
    ctx.font='10px sans-serif';
    if(showNests.checked)for(const nest of visibleNests()){
      const [x,y]=project([nest.x,nest.z]);ctx.strokeStyle=nest.layer!=='surface'?'#dbb6ff':nest.real?'#75f3cf':'#ff9c83';ctx.lineWidth=nest.id===nestSelect.value?3:1.5;ctx.beginPath();ctx.arc(x,y,nest.id===nestSelect.value?8:4,0,Math.PI*2);ctx.stroke();
    }
    if(showSky.checked)for(const island of data.sky?.islands||[]){const [x,y]=project([island.x,island.z]);ctx.fillStyle='#decaff';ctx.beginPath();ctx.moveTo(x,y-8);ctx.lineTo(x+9,y);ctx.lineTo(x,y+5);ctx.lineTo(x-9,y);ctx.closePath();ctx.fill();}
  }
  function drawSky(){
    const island=(data.sky?.islands||[]).find(i=>i.id===skySelect.value);skyCanvas.hidden=!island;skyInfo.hidden=!island;if(!island)return;
    const c=skyCanvas.getContext('2d');c.clearRect(0,0,850,260);const scale=250/island.radius_m;
    const project=v=>[425+(v[0]-.4*v[2])*scale,140+(v[2]*.4-(v[1]-island.altitude_m))*scale];
    for(const t of island.mesh.triangles){c.beginPath();t.forEach((i,j)=>{const p=project(island.mesh.vertices[i]);j?c.lineTo(...p):c.moveTo(...p);});c.closePath();c.fillStyle=island.months[Number(month.value)].snow>.5?'#dbe9f1':'#668878';c.fill();c.strokeStyle='#364c56';c.stroke();}
    skyInfo.textContent=`${island.id}: ${island.area_km2.toFixed(3)} km² independent land at ${island.altitude_m.toFixed(0)} m; this month ${island.months[Number(month.value)].temperature.toFixed(1)}°C. Rain capture capacity ${island.freshwater_capacity.toFixed(1)} residents-equivalent; annual food potential ${island.food_potential.toFixed(2)}. ${island.cold_habitat||'Temperate habitat'}.`;
  }
  atlas.onmousemove=e=>{const rect=atlas.getBoundingClientRect(),n=data.config.size,x=Math.min(n-1,Math.max(0,Math.round((e.clientX-rect.left)/rect.width*(n-1)))),z=Math.min(n-1,Math.max(0,Math.round((e.clientY-rect.top)/rect.height*(n-1))));
    const active=Object.keys(overlays).map(k=>[k,values(k)?.[z]?.[x]||0]).filter(([k,v])=>v>.05).sort((a,b)=>b[1]-a[1]);
    const variant=data.layers.biome_variant?.[z]?.[x];const core=data.terrain?.natural_biomes?.find(b=>b.id===data.layers.natural_biome?.[z]?.[x]);const mutation=variant>=0?data.terrain.magical_biomes[variant]:null;
    inspect.textContent=(core?`Natural: ${core.name} · ${mutation?mutation.name+' / '+mutation.magic_school:'No dominant magical mutation'} · `:'')+`${(-180+360*x/(n-1)).toFixed(1)}°, ${(90-180*z/(n-1)).toFixed(1)}° · ${title(field.value)}: ${(values(field.value)?.[z]?.[x]||0).toFixed(3)} · ${active.map(([k,v])=>title(k)+' '+v.toFixed(2)).join(' · ')||'No strong overlay'}`;
    if(field.value==='civilization_region'){const entity=data.civilizations?.entities.find(c=>c.region_index===values(field.value)?.[z]?.[x]);inspect.textContent+=` · ${entity?.name||'Unassigned wilderness'}`;}
    const heroesHere=heroCast().filter(p=>p.status==='living').map(p=>[p,heroSite(p)]).filter(([p,s])=>s&&Math.abs(s.x-x)<1&&Math.abs(s.z-z)<1);if(heroesHere.length)inspect.textContent+=' · '+heroesHere.map(([p])=>`${p.display_name} (${p.archetype_name||title(p.role)}, ${p.alignment.label}${webOf(p.uid)?' → '+webOf(p.uid).spokes[0].name:''})`).join(', ');
  };
  atlas.onclick=e=>{const rect=atlas.getBoundingClientRect(),x=(e.clientX-rect.left)/rect.width*(data.config.size-1),z=(e.clientY-rect.top)/rect.height*(data.config.size-1);const nest=showNests.checked?[...visibleNests()].sort((a,b)=>Math.hypot(a.x-x,a.z-z)-Math.hypot(b.x-x,b.z-z))[0]:null;if(nest&&Math.hypot(nest.x-x,nest.z-z)<data.config.size*.018){speciesSelect.value=nest.species_id;rebuildNestLocations();nestSelect.value=nest.id;inspectNest();drawAtlas();return;}const island=[...(data.sky?.islands||[])].sort((a,b)=>Math.hypot(a.x-x,a.z-z)-Math.hypot(b.x-x,b.z-z))[0];if(island&&Math.hypot(island.x-x,island.z-z)<data.config.size*.035){skySelect.value=island.id;drawSky();}};
  month.onchange=()=>{renderMoon();drawAtlas();drawSky();draw();};moonlit.onchange=drawAtlas;field.onchange=showRoutes.onchange=drawAtlas;showSky.onchange=()=>{drawAtlas();draw();};skySelect.onchange=drawSky;
  const groundGlobe=drawGlobe;
  drawGlobe=()=>{
    groundGlobe();if(!showSky.checked||stage<6)return;
    const ctx=$('globe').getContext('2d'),r=data.effective_config.globe_radius,scale=230*Number($('zoom').value),relief=Number($('relief').value);
    const yaw=Number($('yaw').value)*Math.PI/180,pitch=Number($('pitch').value)*Math.PI/180,cy=Math.cos(yaw),sy=Math.sin(yaw),cp=Math.cos(pitch),sp=Math.sin(pitch);
    const project=p=>{const xx=p[0]*cy+p[2]*sy,zz=-p[0]*sy+p[2]*cy;return[360+xx*scale,310-(p[1]*cp-zz*sp)*scale,p[1]*sp+zz*cp];};
    const triangles=[];
    for(const island of data.sky?.islands||[]){
      const center=island.direction;if(project(center)[2]<.12)continue;
      const lon=Math.atan2(center[2],center[0]),lat=Math.asin(center[1]);
      const east=[-Math.sin(lon),0,Math.cos(lon)],north=[-Math.sin(lat)*Math.cos(lon),Math.cos(lat),-Math.sin(lat)*Math.sin(lon)];
      const vertices=island.mesh.vertices.map(v=>project(center.map((c,i)=>c*(1+relief*v[1]/r)+east[i]*v[0]/r+north[i]*v[2]/r)));
      for(const t of island.mesh.triangles)triangles.push({p:t.map(i=>vertices[i]),snow:island.months[Number(month.value)].snow});
    }
    triangles.sort((a,b)=>a.p.reduce((s,p)=>s+p[2],0)-b.p.reduce((s,p)=>s+p[2],0));
    for(const triangle of triangles){ctx.beginPath();triangle.p.forEach((p,i)=>i?ctx.lineTo(p[0],p[1]):ctx.moveTo(p[0],p[1]));ctx.closePath();ctx.fillStyle=triangle.snow>.5?'#e3edf4':'#a0bfa3';ctx.fill();ctx.strokeStyle='#81729b';ctx.lineWidth=.35;ctx.stroke();}
  };
  const legacyDraw=draw;
  let shownStage=null;
  draw=()=>{
    legacyDraw();
    if(data.build_stages&&shownStage!==data){shownStage=data;rebuild();}
    if(data.magic?.networks)$('magic-summary').textContent=data.magic.version>=3?data.magic.groups.join(' · ')+'. '+data.magic.method:'Five independent magical networks: Weave, Umbral, Infernal, Holy and Primordial.';
    if(data.population?.id==='mixed')$('profile-note').textContent='Mixed humans, dwarves, elves, gnomes and Tidekin sea elves.';
    if(data.config.world_recipe&&$('legend').textContent.includes('magical ecology'))$('legend').textContent='Underlying terrain and climate. Fantasy regions remain independent overlays in the layered atlas.';
  };
  generateButton.onclick=async()=>{
    if(busy||!live||mode.value==='parameters'&&!parameters.reportValidity())return;
    busy=true;generateButton.disabled=true;
    // What is being timed is the run, not the server's share of it: the clock starts on
    // the click and stops when the new world is on screen, so transfer and redraw are
    // inside the number. A world takes minutes, so it also ticks while it waits --
    // a button that goes quiet for three minutes reads as a hang.
    const started=performance.now(),elapsed=since=>((performance.now()-since)/1000).toFixed(1);
    const running=()=>{status.textContent=`Running simulation… ${elapsed(started)} s · terrain, habitats, civilizations and supply networks`;};
    running();const ticking=setInterval(running,100);
    try{
      const randomMode=mode.value==='random';const seed=randomMode?crypto.getRandomValues(new Uint32Array(1))[0]:Number(inputs.seed.value);const overrides={size:Number(resolution.value)};
      if(!randomMode)for(const k of Object.keys(explicit)){if(!inputs[k])continue;overrides[k]=schema[k].type==='string'?inputs[k].value:Number(inputs[k].value);}
      overrides.size=Number(resolution.value);
      const response=await fetch('/world/generate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({seed,recipe_version:completeWorld.config.world_recipe,overrides})});const result=await response.json();if(!response.ok)throw Error(result.error||'Generation failed');
      const answered=performance.now();
      data=result;explicit={...data.recipe.overrides};for(const [k,input] of Object.entries(inputs))input.value=data.recipe.resolved[k]??schema[k].default;
      for(const [k,v] of Object.entries(data.config))if($('controls').elements[k])$('controls').elements[k].value=v;
      patchData=null;patchRequest++;$('patch-canvas').hidden=true;$('patch-download').disabled=true;
      selectedRow=Math.floor(data.config.size/2);rebuild();refreshLayers();draw();
      const finished=performance.now();
      status.textContent=`Simulation complete in ${((finished-started)/1000).toFixed(1)} s · ${((answered-started)/1000).toFixed(1)} s generating and transferring, ${((finished-answered)/1000).toFixed(1)} s drawing. Seed ${seed} · recipe ${data.config.world_recipe} · ${data.config.size-1} × ${data.config.size-1} cells · ${Object.keys(overrides).length} explicit overrides. Switch to Parameters to reproduce or tweak it.`;
    }catch(error){status.textContent=`${error.message} (after ${elapsed(started)} s)`;}finally{clearInterval(ticking);busy=false;generateButton.disabled=false;}
  };
  advanceButton.onclick=async()=>{
    if(busy||!live)return;
    busy=true;advanceButton.disabled=true;generateButton.disabled=true;status.textContent='Advancing age: creatures, city fates, leylines, biomes and civilization…';
    try{
      const response=await fetch('/world/advance-age',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({api_version:1,world:completeWorld,steps:1})});
      const result=await response.json();if(!response.ok)throw Error(result.error||'Age advancement failed');
      data=result;patchData=null;patchRequest++;$('patch-canvas').hidden=true;$('patch-download').disabled=true;
      refreshLayers();rebuild();draw();status.textContent=`Age ${data.history.ages.length} complete. Creature nests, cities and their supporting regions were recalculated.`;
    }catch(error){status.textContent=error.message;}finally{busy=false;generateButton.disabled=false;advanceButton.disabled=!completeWorld.beast_nests;}
  };
  async function visitation(body,message){
    if(busy||!live)return;
    busy=true;summonButton.disabled=departButton.disabled=generateButton.disabled=true;status.textContent=message;
    try{
      const response=await fetch('/world/summon',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({api_version:1,world:completeWorld,...body})});
      const result=await response.json();if(!response.ok)throw Error(result.error||'Visitation failed');
      data=result;patchData=null;patchRequest++;$('patch-canvas').hidden=true;$('patch-download').disabled=true;
      refreshLayers();rebuild();draw();
      const last=data.religion.visitations[data.religion.visitations.length-1];
      status.textContent=body.depart?`${last.god_id.replace('god_','')} has gone home; a footprint key point remains.`:`${last.god_id.replace('god_','')} walks the world: ${last.ruins.length} ruins, ${last.purged_nests.length} nests driven out, ${last.converted.length} peoples converted.`;
    }catch(error){status.textContent=error.message;}finally{busy=false;generateButton.disabled=false;renderGods();}
  }
  summonButton.onclick=()=>visitation({god_id:godSelect.value,target:{city_uid:targetSelect.value},wrath:Number(wrath.value)},'Summoning: avatar, divine lottery, purge, conversion…');
  departButton.onclick=()=>visitation({god_id:data.religion.gods.find(g=>g.status==='walking')?.id,depart:true},'The god departs…');
  rebuild();draw();
}
