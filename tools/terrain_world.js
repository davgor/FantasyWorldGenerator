/* New recipe UI; old snapshots retain the original controls and renderer. */
if (data.config.world_recipe >= 1) {
  const title = s => s.replaceAll('_', ' ').replace(/\b\w/g, c => c.toUpperCase());
  const make = (tag, text, parent) => { const e=document.createElement(tag); if(text!==undefined)e.textContent=text; if(parent)parent.append(e); return e; };
  const style=make('style', '#world-params label{display:block;font-size:12px}#world-params input,#world-params select{width:100%}.world-cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px}.world-card{padding:14px;background:#20313c;border-radius:8px}.world-controls{display:flex;flex-wrap:wrap;gap:12px}.world-controls label{margin:4px}.world-controls input[type=checkbox]{width:auto}#world-atlas{aspect-ratio:2;image-rendering:pixelated}#world-layers{max-height:250px;overflow:auto}#world-layers label{display:inline-flex;align-items:center;gap:5px;margin:4px 10px 4px 0}#world-layers input[type=range]{width:65px}#world-viewer{margin:24px 0;padding:18px;border:1px solid #405d68;border-radius:12px}');
  document.head.append(style);
  const aside=document.querySelector('aside');
  for(const e of [...aside.children])e.hidden=true;
  const head=make('div',undefined,aside);make('h2','World recipe',head);
  const baseline=make('details');make('summary','Ground-only baseline and legacy diagnostics',baseline);$('human-panel').before(baseline);baseline.append($('human-panel'));
  const mode=make('select',undefined,head);mode.id='world-mode';
  for(const [value,text] of [['random','Random'],['parameters','Parameters']]){const option=make('option',text,mode);option.value=value;}
  const generateButton=make('button','Generate random world',head);generateButton.id='world-generate';generateButton.disabled=!live;
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
  const status=make('p',`Seed ${data.config.seed} · recipe ${data.config.world_recipe}. Random generation uses defaults at the selected resolution.`,head);status.id='world-status';status.setAttribute('role','status');
  const advanceButton=make('button','Advance age',head);advanceButton.id='world-advance-age';advanceButton.hidden=data.config.world_recipe!==3;advanceButton.disabled=!live||!data.beast_nests;
  const exportButton=make('button','Export world JSON',head);exportButton.onclick=()=>$('download').click();
  refine.onclick=()=>{if(busy)return;mode.value='parameters';mode.onchange();explicit={...completeWorld.recipe.overrides,size:Number(resolution.value)};inputs.seed.value=completeWorld.config.seed;for(const [k,v]of Object.entries(explicit))if(inputs[k])inputs[k].value=v;generateButton.click();};
  mode.onchange=()=>{parameters.hidden=mode.value==='random';generateButton.textContent=mode.value==='random'?'Generate random world':'Generate with parameters';};
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
  const nestPanel=make('details',undefined,viewer);nestPanel.open=true;make('summary','Beast nests: dens, colonies, lairs and aquatic territories',nestPanel);
  const nestSummary=make('p','',nestPanel);nestSummary.id='world-nest-summary';
  const speciesLabel=make('label','Species ',nestPanel),speciesSelect=make('select',undefined,speciesLabel);speciesSelect.id='world-nest-species';
  const nestSelect=make('select',undefined,nestPanel);nestSelect.id='world-nest-select';nestSelect.setAttribute('aria-label','Nest location');
  const nestInfo=make('p','',nestPanel);nestInfo.id='world-nest-info';
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
  const colors={weave:[180,143,247],umbral:[109,103,176],infernal:[243,83,59],radiant:[255,220,126],fire:[207,86,37],water:[65,156,202],earth:[67,120,51],air:[176,210,213],holy:[255,220,126],primordial:[98,213,137],reef:[83,214,204],lagoon:[94,204,231],estuary:[118,160,101],kelp:[71,147,107],fjord:[92,160,189],boreal:[71,129,103],tundra:[178,188,149],ice_cap:[227,245,255],snow:[242,245,250],water_ice:[178,227,250]};
  let overlays={},nodePoints=[];
  const rgbFor=key=>colors[key.replace('ley_','').replace('zone_','')]||[216,166,110];
  const civilizationColor=index=>data.civilizations?.entities.find(e=>e.region_index===index)?.presentation?.map_color_rgb||[128,128,128];
  function rebuild(){
    advanceButton.disabled=busy||!live||!completeWorld.beast_nests;
    civilizationLegend.replaceChildren();
    if(data.civilizations){make('p','Civilization regions follow reachable city support areas; wilderness remains unassigned. Larger square pins are capitals.',civilizationLegend);for(const entity of data.civilizations.entities){const capital=data.settlements?.sites.find(s=>s.node===entity.capital_node);const label=make('span',`${entity.name}: ${entity.city_count} cities${capital?' · Capital: '+capital.name:''}. `,civilizationLegend);label.style.color=`rgb(${civilizationColor(entity.region_index).join(',')})`;}}
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
    if(data.build_stages){make('h3',data.phases.titles[stage-1],historyCards);make('p',`${data.settlements?.sites.length||0} active cities · ${data.ruins?.length||0} ruins.`,historyCards);for(const ruin of data.ruins||[]){const card=make('article',undefined,historyCards);card.className='world-card';make('strong',ruin.name+' — Ruins',card);make('p',`Age ${ruin.destroyed_age} · Source culture: ${ruin.source_culture}`,card);make('p',ruin.reason,card);if(ruin.new_node_school)make('p','Now a '+ruin.new_node_school+' leyline key point.',card);}}
    regionText.replaceChildren();for(const region of data.regions?.influences||[])make('p',`${title(region.id)}: ${region.reason} · ${region.area_km2.toFixed(2)} km² influence above display threshold`,regionText);
    const routes=data.transport?.routes||[];
    summary.textContent=`${data.fisheries?.ports.length||0} coastal hamlets · ${routes.filter(r=>r.mode==='sea').length} sea routes · ${routes.filter(r=>r.mode==='air').length} air routes. Fishing delivery ${(data.fisheries?.delivered_annual_food||0).toFixed(2)} / ${(data.fisheries?.potential_annual_food||0).toFixed(2)} potential units. Seed ${data.config.seed}.`;
    rebuildNests();drawAtlas();drawSky();
  }
  function values(key){return ['snow','water_ice'].includes(key)?data.seasonal_environment?.months[Number(month.value)]?.[key]:data.layers[key];}
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
    for(const s of data.settlements?.sites||[]){const p=project([s.x,s.z]),radius=s.city_class==='capital'?5:s.city_class==='medium'?4:3;ctx.fillStyle='#fff2bc';ctx.fillRect(p[0]-radius,p[1]-radius,2*radius,2*radius);if(s.city_class==='capital'){ctx.strokeStyle='#fff2bc';ctx.strokeRect(p[0]-8,p[1]-8,16,16);}}
    for(const ruin of data.ruins||[]){const [x,y]=project([ruin.x,ruin.z]);drawRuinIcon(ctx,x,y,16);}
    for(const p of data.fisheries?.ports||[]){const [x,y]=project([p.x,p.z]);ctx.strokeStyle='#8ff6ed';ctx.strokeRect(x-4,y-4,8,8);}
    if($('terrain-icons').checked)for(const f of data.terrain?.features||[]){const [x,y]=project([f.x,f.z]);terrainIcon(ctx,x,y,f.kind,7);}
    for(const landmark of data.regions?.landmarks||[]){const [x,y]=project([landmark.x,landmark.z]);ctx.fillStyle=landmark.kind==='witch_hut'?'#e2a7f1':'#edc17e';ctx.fillText(landmark.kind==='witch_hut'?'W':'T',x,y);}
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
  };
  atlas.onclick=e=>{const rect=atlas.getBoundingClientRect(),x=(e.clientX-rect.left)/rect.width*(data.config.size-1),z=(e.clientY-rect.top)/rect.height*(data.config.size-1);const nest=showNests.checked?[...visibleNests()].sort((a,b)=>Math.hypot(a.x-x,a.z-z)-Math.hypot(b.x-x,b.z-z))[0]:null;if(nest&&Math.hypot(nest.x-x,nest.z-z)<data.config.size*.018){speciesSelect.value=nest.species_id;rebuildNestLocations();nestSelect.value=nest.id;inspectNest();drawAtlas();return;}const island=[...(data.sky?.islands||[])].sort((a,b)=>Math.hypot(a.x-x,a.z-z)-Math.hypot(b.x-x,b.z-z))[0];if(island&&Math.hypot(island.x-x,island.z-z)<data.config.size*.035){skySelect.value=island.id;drawSky();}};
  month.onchange=()=>{drawAtlas();drawSky();draw();};field.onchange=showRoutes.onchange=drawAtlas;showSky.onchange=()=>{drawAtlas();draw();};skySelect.onchange=drawSky;
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
    busy=true;generateButton.disabled=true;status.textContent='Generating terrain, habitats and supply networks…';
    try{
      const randomMode=mode.value==='random';const seed=randomMode?crypto.getRandomValues(new Uint32Array(1))[0]:Number(inputs.seed.value);const overrides={size:Number(resolution.value)};
      if(!randomMode)for(const k of Object.keys(explicit)){if(!inputs[k])continue;overrides[k]=schema[k].type==='string'?inputs[k].value:Number(inputs[k].value);}
      overrides.size=Number(resolution.value);
      const response=await fetch('/world/generate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({seed,recipe_version:completeWorld.config.world_recipe,overrides})});const result=await response.json();if(!response.ok)throw Error(result.error||'Generation failed');
      data=result;explicit={...data.recipe.overrides};for(const [k,input] of Object.entries(inputs))input.value=data.recipe.resolved[k]??schema[k].default;
      for(const [k,v] of Object.entries(data.config))if($('controls').elements[k])$('controls').elements[k].value=v;
      patchData=null;patchRequest++;$('patch-canvas').hidden=true;$('patch-download').disabled=true;
      selectedRow=Math.floor(data.config.size/2);rebuild();refreshLayers();draw();
      status.textContent=`Generated seed ${seed} · recipe ${data.config.world_recipe} · ${Object.keys(overrides).length} explicit overrides. Switch to Parameters to reproduce or tweak it.`;
    }catch(error){status.textContent=error.message;}finally{busy=false;generateButton.disabled=false;}
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
  rebuild();draw();
}
