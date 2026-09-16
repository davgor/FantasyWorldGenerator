/* Compact laboratory: views first, then measured tables and diagnostics. */

if(data.config.world_recipe===3){

  const make=(tag,text,parent)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(parent)parent.append(e);return e;};

  const main=document.querySelector('main'),layout=document.querySelector('.layout'),view=layout.querySelector('section');

  const settings=make('details',undefined,main);make('summary','Generator settings and advanced tools',settings);settings.append(layout.querySelector('aside'));

  layout.style.display='block';

  const stageLabel=make('label','Generation stage '),stageSelect=make('select',undefined,stageLabel);stageSelect.id='debug-stage';view.prepend(stageLabel);

  $('stages').hidden=true;$('stage-navigation').hidden=true;

  stageSelect.onchange=()=>{const buttons=$('stages').querySelectorAll('button');buttons[Number(stageSelect.value)]?.click();};

  const filters=make('div',undefined);filters.id='biome-filters';stageLabel.after(filters);

  const globeTitle=make('h2','3D globe');$('globe-controls').before(globeTitle);
  $('view').value='globe';$('view').closest('label').hidden=true;
  const globeOptions=make('details');make('summary','Globe controls and measurements',globeOptions);
  $('globe').after(globeOptions);
  for(const e of [$('globe-controls'),$('mesh-density').closest('label'),$('relief-control'),$('area-summary'),$('legend'),$('world-notes'),$('color-key')])globeOptions.append(e);
  const nestDetails=$('world-nest-summary').closest('details');nestDetails.open=false;$('world-atlas').after(nestDetails);


  const atlas=$('world-viewer');layout.after(atlas);

  const diagnostics=make('section',undefined);diagnostics.id='world-debug';atlas.after(diagnostics);

  const tables=make('div',undefined,diagnostics),raw=make('details',undefined,diagnostics);make('summary','Raw diagnostic JSON',raw);const rawText=make('pre','',raw);

  const extra=make('details',undefined,main);make('summary','Advanced local terrain patch',extra);extra.append($('local-lab'));

  const css=make('style',`#world-debug table{border-collapse:collapse;width:100%;font-size:13px}#world-debug th,#world-debug td{padding:7px 10px;text-align:left;border-bottom:1px solid #354653}#world-debug th{position:sticky;top:0;background:#24333f}#world-debug .scroll{max-height:420px;overflow:auto;margin-bottom:24px}#world-debug svg{width:100%;max-height:350px;background:#18242f}#biome-filters{display:flex;gap:6px;flex-wrap:wrap;margin:14px 0}#globe{max-width:800px;margin:auto}.world-cards,#settlement-panel,#magic-panel{display:none!important}#world-nest-summary{font-size:13px}#world-debug h3{margin-top:28px}`);document.head.append(css);

  const oldColor=colorFor;window.debugBiomeFilter=null;

  colorFor=(key,value,...args)=>['biome','natural_biome'].includes(key)&&window.debugBiomeFilter!==null&&Math.round(value)!==window.debugBiomeFilter?[36,44,49]:oldColor(key,value,...args);

  function table(title,headers,rows){make('h3',title,tables);const wrap=make('div',undefined,tables);wrap.className='scroll';const t=make('table',undefined,wrap),h=make('tr',undefined,make('thead',undefined,t));headers.forEach(s=>make('th',s,h));const body=make('tbody',undefined,t);for(const values of rows){const tr=make('tr',undefined,body);for(const value of values){const td=make('td',undefined,tr);if(value instanceof Node)td.append(value);else td.textContent=value??'—';}}}

  const number=v=>typeof v==='number'?v.toLocaleString(undefined,{maximumFractionDigits:1}):'—';

  function chart(title,rows,key){make('h3',title,tables);if(!rows.length){make('p','No data at this stage.',tables);return;}const ns='http://www.w3.org/2000/svg',svg=document.createElementNS(ns,'svg');svg.setAttribute('viewBox',`0 0 900 ${rows.length*27+8}`);svg.setAttribute('role','img');svg.setAttribute('aria-label',title);tables.append(svg);const max=Math.max(1,...rows.map(r=>r[key]||0));for(const [i,r]of rows.entries()){const text=document.createElementNS(ns,'text');text.setAttribute('x',6);text.setAttribute('y',i*27+19);text.setAttribute('fill','#dce8ee');text.textContent=r.name||r.id||r.title;svg.append(text);const rect=document.createElementNS(ns,'rect');rect.setAttribute('x',240);rect.setAttribute('y',i*27+4);rect.setAttribute('width',560*(r[key]||0)/max);rect.setAttribute('height',18);rect.setAttribute('fill','#62b8c1');svg.append(rect);const val=text.cloneNode();val.setAttribute('x',810);val.textContent=number(r[key]);svg.append(val);}}

  let shown=null;

  function render(){

    $('view').value='globe';

    if(shown===data)return;shown=data;

    stageSelect.replaceChildren();for(const [i,b]of [...$('stages').querySelectorAll('button')].entries()){const o=make('option',b.textContent,stageSelect);o.value=i;}stageSelect.value=String(stage-1);

    filters.replaceChildren();const all=make('button','All biomes',filters);all.onclick=()=>{window.debugBiomeFilter=null;all.setAttribute('aria-pressed','true');for(const b of filters.querySelectorAll('button'))if(b!==all)b.setAttribute('aria-pressed','false');$('world-field')?.onchange();draw();};

    for(const biome of data.terrain?.biomes||[]){const b=make('button',biome.name,filters);b.style.borderBottom=`3px solid rgb(${biome.color.join(',')})`;b.onclick=()=>{window.debugBiomeFilter=biome.id;for(const button of filters.querySelectorAll('button'))button.setAttribute('aria-pressed',String(button===b));$('layer').value=data.layers.natural_biome?'natural_biome':'biome';const f=$('world-field');if(f&&[...f.options].some(o=>o.value==='natural_biome')){f.value='natural_biome';f.onchange();}draw();};}

    tables.replaceChildren();const d=completeWorld.debug_stats;

    make('h2','Graphs and data',tables);make('p',`Tables use selected stage ${stage}. Debug summaries describe the final generated world; they do not change when you inspect earlier stages.`,tables);

    const sites=data.settlements?.sites||[];

    table('Cities — selected stage',['City','Parent race','Civilization','Class','Urban population'],sites.map(s=>{const b=make('button',s.name);b.onclick=()=>window.openCityPlan(s);return[b,s.parent_race_id,s.population_profile,s.city_class,number(s.urban_population_estimate??s.population_estimate)];}));

    table('Food supply — selected stage',['City','Layer','Food coverage %','Annual shortage','Lean months'],(data.world_economy?.sites||[]).map(s=>[s.name,s.layer,number(s.food_coverage*100),number(s.annual_shortage),s.lean_months.join(', ')||'none']));
    table('Colleges — selected stage',['College','Civilization','Magic density','Hazard','Access cost (m)'],(data.magic?.colleges||[]).map(c=>[c.id,c.population_profile,number(c.density),number(c.hazard),number(c.access_cost)]));

    table('Ruins — selected stage',['Name','Civilization','Destroyed age','Cause'],(data.ruins||[]).map(r=>[r.name,r.population_profile,r.destroyed_age,r.reason]));

    table('Landmarks — selected stage',['Kind','Label','Grid x','Grid z'],[...(data.terrain?.features||[]),...(data.regions?.landmarks||[])].map(f=>[f.kind,f.label||f.id,f.x,f.z]));

    if(!d){make('p','Regenerate this world to populate the new diagnostics.',tables);return;}

    make('p',d.scope,tables);chart('Urban population by civilization',d.civilizations,'urban_population');

    table('Parent races — final state',['Race','Cities','Urban population','Placed workers','Worker beds'],d.parent_races.map(r=>[r.id,r.cities,number(r.urban_population),r.workers,r.beds]));

    chart('City count through founding and ages',d.timeline.map(r=>({...r,name:`${r.stage}. ${r.title}`})),'cities');

    table('Founding outcomes — final history',['Outcome','Count'],Object.entries(d.founding_outcomes));

    table('Diaspora — final history',['Founded','Surviving','Destroyed'],[[d.diaspora.founded,d.diaspora.surviving,d.diaspora.destroyed]]);

    chart('Nearest city distance (metres)',d.cities.filter(c=>c.nearest_city_m!==null),'nearest_city_m');

    table('City housing and constraints — final state',['City','Workers','Beds','Houses','Apartments','Shortfall','Vacant safe cells','Housing frontage candidates','Failed buildings'],d.cities.map(c=>[c.name,c.stats.workers,c.stats.worker_beds,c.stats.houses,c.stats.apartments,c.stats.housing_shortfall,c.placement.vacant_shape_cells,c.placement.housing_frontage_candidates,c.stats.unplaced_total]));

    make('p','Vacant cells are not necessarily usable plots: measured buildings require contiguous safe ground and a clear connection to a street. Houses are attempted first; apartments upgrade those houses only after legal plots run out. Beds represent facility workers, not every resident.',tables);

    table('Leyline distribution — final state',['School','Nodes','Lines','Clusters','Spread','Model'],d.leylines.map(l=>[l.id,l.nodes,l.lines,l.distribution?.clusters,number(l.distribution?.spread),l.distribution?.model]));

    chart('Natural biome coverage (% of globe surface)',d.biome_coverage,'percent_world');

    rawText.textContent=JSON.stringify(d,null,2);

  }

  const previousDraw=draw;draw=()=>{previousDraw();render();};draw();

}

