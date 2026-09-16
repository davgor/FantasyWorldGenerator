/* Final-stage city inspector; works in live lab and exported HTML. */

(() => {

  const make=(tag,text,parent)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(parent)parent.append(e);return e;};

  const dialog=make('dialog',undefined,document.body);dialog.id='city-layout-dialog';

  dialog.style.cssText='width:min(1200px,94vw);max-height:94vh;background:#14232c;color:#edf4f5;border:1px solid #70959b;border-radius:10px;padding:18px;overflow:auto';

  const close=make('button','Close city view',dialog);close.style.float='right';close.onclick=()=>dialog.close();

  const title=make('h2','City layout',dialog),summary=make('p','',dialog),details=make('p','Select a building for details.',dialog);

  const controls=make('div',undefined,dialog);controls.style.cssText='display:flex;gap:18px;align-items:center;flex-wrap:wrap';

  const phaseLabel=make('label','Placement pass ',controls),phase=make('select',undefined,phaseLabel);

  for(const [v,t] of [['high','3 · High priority'],['high_housing','4 · Their houses'],['low','5 · Low priority'],['low_housing','6 · Their houses']]){const o=make('option',t,phase);o.value=v;}

  phase.value='low_housing';

  const viewLabel=make('label','View ',controls),view=make('select',undefined,viewLabel);

  for(const [v,t]of [['3d','3D terrain'],['2d','2D plan']]){const o=make('option',t,view);o.value=v;}

  const reset=make('button','Reset camera',controls),labelControl=make('label','Building labels ',controls),labels=make('input',undefined,labelControl);labels.type='checkbox';

  const buildingLabel=make('label','Inspect building ',controls),buildingSelect=make('select',undefined,buildingLabel);

  const zoomLabel=make('label','Zoom ',controls),zoom=make('input',undefined,zoomLabel);zoom.type='range';zoom.min=1;zoom.max=4;zoom.step=.25;zoom.value=1;

  make('p','Gold: core services · Purple: other services · Blue: worker houses · Gray: streets · Dark green: land · Blue terrain: water · Red terrain: steep/flood-prone. Outlined plots include setbacks.',dialog);

  const viewport=make('div',undefined,dialog);viewport.style.cssText='overflow:auto;max-height:65vh;background:#172d28;border:1px solid #526473';

  const ns='http://www.w3.org/2000/svg',svg=document.createElementNS(ns,'svg');svg.setAttribute('role','img');svg.setAttribute('aria-label','Labeled city layout');viewport.append(svg);

  const sceneContainer=make('div',undefined,viewport);

  const inspect=b=>{details.textContent=`${b.name} · ${b.building_id} · ${b.workers} workers · ${b.beds} beds · ${b.dimensions_m.width} × ${b.dimensions_m.depth} × ${b.dimensions_m.height} m (width × depth × height) · plot ${b.plot_m.width} × ${b.plot_m.depth} m · angle ${(b.rotation_degrees||0).toFixed(1)}° · floor ${(b.ground_elevation_m||0).toFixed(1)} m elevation · ${b.phase.replaceAll('_',' ')}`;buildingSelect.value=b.id;renderer?.select(b.id);};

  let renderer=null;try{renderer=window.createCity3D?.(sceneContainer,inspect);}catch(error){sceneContainer.remove();console.warn('City 3D unavailable',error);}

  if(!renderer){view.value='2d';view.options[0].disabled=true;}

  make('p',renderer?'Drag to orbit · Scroll to zoom · Building heights and terrain use the same metre scale. Gray plinths show provisional foundations.':'3D is unavailable in this browser. Showing the 2D plan.',dialog);

  reset.onclick=()=>{zoom.value=1;renderer?.reset();};labels.onchange=()=>renderer?.labels(labels.checked);

  const failures=make('details',undefined,dialog);make('summary','Unplaced buildings and limitations',failures);const failList=make('ul',undefined,failures);

  let current=null;

  const order=['high','high_housing','low','low_housing'];

  function drawCity(){

    if(!current)return;svg.replaceChildren();const p=current,lo=p.bounds_m[0],span=p.bounds_m[2]-lo;

    svg.setAttribute('viewBox',`${lo} ${lo} ${span} ${span}`);svg.style.width=(900*Number(zoom.value))+'px';svg.style.height=svg.style.width;

    const terrain=document.createElement('canvas');terrain.width=terrain.height=p.terrain.size;const ctx=terrain.getContext('2d'),im=ctx.createImageData(terrain.width,terrain.height);

    for(let z=0;z<terrain.height;z++)for(let x=0;x<terrain.width;x++)im.data.set([[37,65,48,255],[38,89,118,255],[97,57,51,255]][p.terrain.codes[z][x]],(z*terrain.width+x)*4);

    for(const [x,z] of p.roads)im.data.set([135,137,125,255],(z*terrain.width+x)*4);ctx.putImageData(im,0,0);

    const image=document.createElementNS(ns,'image');image.setAttribute('href',terrain.toDataURL());for(const [k,v]of Object.entries({x:lo,y:lo,width:span,height:span}))image.setAttribute(k,v);svg.append(image);

    const shown=p.plots.filter(b=>order.indexOf(b.phase)<=order.indexOf(phase.value)).map(b=>b.housing_upgrade&&order.indexOf(b.housing_upgrade.phase)>order.indexOf(phase.value)?{...b,...b.housing_upgrade.previous}:b);

    buildingSelect.replaceChildren();make('option','Select a building…',buildingSelect).value='';

    for(const b of shown){const o=make('option',`${b.name} (${b.id})`,buildingSelect);o.value=b.id;}

    buildingSelect.onchange=()=>{const b=shown.find(b=>b.id===buildingSelect.value);if(b)inspect(b);};

    viewport.style.maxHeight=view.value==='3d'?'none':'65vh';sceneContainer.style.display=view.value==='3d'?'block':'none';svg.style.display=view.value==='2d'?'block':'none';

    if(renderer&&view.value==='3d')renderer.setScene(p,shown);

    for(const b of shown){

      const g=document.createElementNS(ns,'g');g.setAttribute('tabindex','0');g.setAttribute('role','button');g.setAttribute('aria-label',b.name+' '+b.id);g.style.cursor='pointer';

      const rect=document.createElementNS(ns,'rect');const color=b.kind==='housing'?'#76b4d0':b.phase==='high'?'#d9b35f':'#bd98cc';

      for(const [k,v]of Object.entries({x:b.x_m-b.plot_m.width/2,y:b.z_m-b.plot_m.depth/2,width:b.plot_m.width,height:b.plot_m.depth,fill:color,stroke:'#101b20','stroke-width':.7}))rect.setAttribute(k,v);

      g.setAttribute('transform',`rotate(${b.rotation_degrees||0} ${b.x_m} ${b.z_m})`);

      g.append(rect);const footprint=document.createElementNS(ns,'rect');for(const[k,v]of Object.entries({x:b.x_m-b.dimensions_m.width/2,y:b.z_m-b.dimensions_m.depth/2,width:b.dimensions_m.width,height:b.dimensions_m.depth,fill:'none',stroke:'#fff','stroke-width':.4}))footprint.setAttribute(k,v);g.append(footprint);

      const text=document.createElementNS(ns,'text');text.setAttribute('x',b.x_m);text.setAttribute('y',b.z_m);text.setAttribute('font-size',Math.min(4,b.plot_m.width/5));text.setAttribute('text-anchor','middle');text.setAttribute('fill','#112029');

      const words=(b.kind==='housing'?(b.building_id==='building.worker_apartment'?'Apartments ':'House ')+b.id.slice(5):b.name).split(' ');let line='',lines=[];for(const w of words){if((line+' '+w).length>14&&line){lines.push(line);line=w;}else line+=(line?' ':'')+w;}if(line)lines.push(line);

      lines.forEach((line,i)=>{const t=document.createElementNS(ns,'tspan');t.setAttribute('x',b.x_m);t.setAttribute('dy',i?4:-(lines.length-1)*2);t.textContent=line;text.append(t);});g.append(text);

      g.onclick=()=>inspect(b);g.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();inspect(b);}};svg.append(g);

    }

    const s=p.stats;summary.textContent=`${p.city_class} · ${p.shape.shape_id?.replaceAll('_',' ')||'No suitable shape'} · ${p.status} · Shown: ${shown.filter(b=>b.kind==='service').length} services, ${shown.filter(b=>b.building_id==='building.worker_house').length} houses, ${shown.filter(b=>b.building_id==='building.worker_apartment').length} apartment buildings, ${shown.reduce((a,b)=>a+b.workers,0)} workers / ${shown.reduce((a,b)=>a+b.beds,0)} beds. Final housing shortfall: ${s.housing_shortfall}. Simulation urban population: ${s.simulation_population??'unavailable'} (separate estimate). World sample spacing: ${p.source_resolution_m} m.`;

  }

  phase.onchange=drawCity;view.onchange=drawCity;zoom.oninput=()=>{if(view.value==='3d')renderer?.zoom(Number(zoom.value));else drawCity();};

  window.openCityPlan=site=>{

    current=data.city_plans?.cities.find(p=>p.city_uid===site.uid||p.site_id===site.id)||null;

    title.textContent=site.name+' — City layout';failList.replaceChildren();details.textContent='Select a building or use the building list for staffing and dimensions.';renderer?.reset();

    if(current){phase.value='low_housing';zoom.value=1;for(const row of current.unplaced)make('li',`${row.count} × ${row.building_id}: ${row.reason}`,failList);for(const warning of current.warnings)make('li',warning,failList);drawCity();}

    else{svg.replaceChildren();sceneContainer.style.display='none';buildingSelect.replaceChildren();summary.textContent='City filling is available after Simulation complete. Generate all 16 stages and inspect the final stage.';}

    if(!dialog.open)dialog.showModal();renderer?.redraw();

  };

  function nearest(event,canvas,globe=false){

    const rect=canvas.getBoundingClientRect(),mx=(event.clientX-rect.left)*canvas.width/rect.width,my=(event.clientY-rect.top)*canvas.height/rect.height,n=data.config.size;

    let best=null,distance=16*canvas.width/rect.width;

    for(const site of data.settlements?.sites||[]){let x=site.x/(n-1)*canvas.width,y=site.z/(n-1)*canvas.height;

      if(globe){const lat=Math.PI/2-site.z/(n-1)*Math.PI,lon=site.x/(n-1)*2*Math.PI-Math.PI,p=[Math.cos(lat)*Math.cos(lon),Math.sin(lat),Math.cos(lat)*Math.sin(lon)],yaw=Number(document.getElementById('yaw').value)*Math.PI/180,pitch=Number(document.getElementById('pitch').value)*Math.PI/180,xx=p[0]*Math.cos(yaw)+p[2]*Math.sin(yaw),zz=-p[0]*Math.sin(yaw)+p[2]*Math.cos(yaw),yy=p[1]*Math.cos(pitch)-zz*Math.sin(pitch),depth=p[1]*Math.sin(pitch)+zz*Math.cos(pitch);if(depth<.08)continue;const r=(data.effective_config||data.config).globe_radius,rad=1+Number(document.getElementById('relief').value)*(data.layers.water_surface?.[site.z]?.[site.x]||0)/r,scale=230*Number(document.getElementById('zoom').value);x=360+xx*rad*scale;y=310-yy*rad*scale;}

      const d=Math.hypot(x-mx,y-my);if(d<distance){distance=d;best=site;}

    }return best;

  }

  document.addEventListener('click',e=>{

    const canvas=e.target;if(canvas.tagName==='CANVAS'&&['map','world-atlas'].includes(canvas.id)){const site=nearest(e,canvas);if(site){e.stopImmediatePropagation();window.openCityPlan(site);}}

    const button=e.target.closest('button');if(button&&!dialog.contains(button)){const site=data.settlements?.sites.find(s=>s.uid===button.dataset.cityUid||s.name===button.textContent);if(site){e.stopImmediatePropagation();window.openCityPlan(site);}}

  },true);

  const globe=document.getElementById('globe');let down=null;

  globe.addEventListener('pointerdown',e=>{down=[e.clientX,e.clientY];});

  globe.addEventListener('pointerup',e=>{if(down&&Math.hypot(e.clientX-down[0],e.clientY-down[1])<5){const site=nearest(e,globe,true);if(site){e.stopImmediatePropagation();window.openCityPlan(site);}}down=null;});

  globe.addEventListener('pointercancel',()=>{down=null;});

})();

