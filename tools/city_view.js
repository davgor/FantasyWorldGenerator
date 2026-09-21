/* Final-stage settlement inspector (city / hamlet / castle); works in live lab and exported HTML. */

(() => {

  const make=(tag,text,parent)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(parent)parent.append(e);return e;};

  const dialog=make('dialog',undefined,document.body);dialog.id='city-layout-dialog';

  dialog.style.cssText='width:min(1200px,94vw);max-height:94vh;background:#14232c;color:#edf4f5;border:1px solid #70959b;border-radius:10px;padding:18px;overflow:auto';

  const close=make('button','Close layout view',dialog);close.style.float='right';close.onclick=()=>dialog.close();

  const title=make('h2','Settlement layout',dialog),summary=make('p','',dialog),details=make('p','Select a building for details.',dialog);

  const controls=make('div',undefined,dialog);controls.style.cssText='display:flex;gap:18px;align-items:center;flex-wrap:wrap';

  const phaseLabel=make('label','Placement pass ',controls),phase=make('select',undefined,phaseLabel);

  const viewLabel=make('label','View ',controls),view=make('select',undefined,viewLabel);

  for(const [v,t]of [['3d','3D terrain'],['2d','2D plan']]){const o=make('option',t,view);o.value=v;}

  const reset=make('button','Reset camera',controls),labelControl=make('label','Building labels ',controls),labels=make('input',undefined,labelControl);labels.type='checkbox';

  const buildingLabel=make('label','Inspect building ',controls),buildingSelect=make('select',undefined,buildingLabel);

  const zoomLabel=make('label','Zoom ',controls),zoom=make('input',undefined,zoomLabel);zoom.type='range';zoom.min=1;zoom.max=4;zoom.step=.25;zoom.value=1;

  make('p','Gold: core / landmarks · Purple: other services · Blue: housing · Gray: streets · Brown: wall segments · Terrain: natural biome colors · Magic: colored outlines · Orange: world-road junctions. Outlined plots include setbacks.',dialog);

  const viewport=make('div',undefined,dialog);viewport.style.cssText='overflow:auto;max-height:65vh;background:#172d28;border:1px solid #526473';

  const ns='http://www.w3.org/2000/svg',svg=document.createElementNS(ns,'svg');svg.setAttribute('role','img');svg.setAttribute('aria-label','Labeled settlement layout');viewport.append(svg);

  const sceneContainer=make('div',undefined,viewport);

  const inspect=b=>{details.textContent=`${b.name} · ${b.building_id} · ${b.workers||0} workers · ${b.beds||0} beds · ${b.dimensions_m.width} × ${b.dimensions_m.depth} × ${b.dimensions_m.height} m (width × depth × height) · plot ${b.plot_m.width} × ${b.plot_m.depth} m · angle ${(b.rotation_degrees||0).toFixed(1)}° · floor ${(b.ground_elevation_m||0).toFixed(1)} m elevation · ${(b.phase||'').replaceAll('_',' ')}`;buildingSelect.value=b.id;renderer?.select(b.id);};

  let renderer=null;try{renderer=window.createCity3D?.(sceneContainer,inspect);}catch(error){sceneContainer.remove();console.warn('City 3D unavailable',error);}

  if(!renderer){view.value='2d';view.options[0].disabled=true;}

  make('p',renderer?'Drag to orbit · Scroll to zoom · Building heights and terrain use the same metre scale. Gray plinths show provisional foundations. Brown boxes are curtain / city-wall segments.':'3D is unavailable in this browser. Showing the 2D plan.',dialog);

  reset.onclick=()=>{zoom.value=1;renderer?.reset();};labels.onchange=()=>renderer?.labels(labels.checked);

  const failures=make('details',undefined,dialog);make('summary','Unplaced buildings and limitations',failures);const failList=make('ul',undefined,failures);

  let current=null,phaseOrder=['fortification','high','high_housing','low','low_housing'];

  const CITY_PHASES=[['fortification','2 · Walls and gates'],['high','3 · High priority'],['high_housing','4 · Their houses'],['low','5 · Low priority'],['low_housing','6 · Their houses']];
  const HAMLET_PHASES=[['high','3 · High priority'],['high_housing','4 · Cottages'],['low','5 · Conditional'],['low_housing','6 · Their cottages']];
  const CASTLE_PHASES=[['perimeter','3 · Walls and gates'],['courts','4 · Bailey courts'],['landmarks','5 · Keep'],['services','6 · Bailey services']];

  function setPhaseOptions(kind){
    const rows=kind==='castle'?CASTLE_PHASES:kind==='hamlet'?HAMLET_PHASES:CITY_PHASES;
    phaseOrder=rows.map(r=>r[0]);phase.replaceChildren();
    for(const [v,t] of rows){const o=make('option',t,phase);o.value=v;}
    phase.value=phaseOrder[phaseOrder.length-1];
  }

  function wallSegments(plan){
    const rows=[];
    for(const seg of plan.fortifications?.segments||[])rows.push(seg);
    for(const network of plan.wall_networks||[])for(const seg of network.segments||[])rows.push(seg);
    return rows;
  }

  function drawWallSegment2d(seg){
    const a=seg.from_m,b=seg.to_m,dx=b[0]-a[0],dz=b[1]-a[1],len=Math.hypot(dx,dz)||1;
    const thickness=seg.thickness_m??3,nx=-dz/len*thickness/2,nz=dx/len*thickness/2;
    const poly=document.createElementNS(ns,'polygon');
    const pts=[[a[0]+nx,a[1]+nz],[b[0]+nx,b[1]+nz],[b[0]-nx,b[1]-nz],[a[0]-nx,a[1]-nz]];
    poly.setAttribute('points',pts.map(p=>p.join(',')).join(' '));
    poly.setAttribute('fill','#6b4a2e');poly.setAttribute('stroke','#2a1a0c');poly.setAttribute('stroke-width','.4');
    svg.append(poly);
  }

  function drawCity(){

    if(!current)return;svg.replaceChildren();const p=current,lo=p.bounds_m[0],span=p.bounds_m[2]-lo;

    svg.setAttribute('viewBox',`${lo} ${lo} ${span} ${span}`);svg.style.width=(900*Number(zoom.value))+'px';svg.style.height=svg.style.width;

    const terrain=document.createElement('canvas');terrain.width=terrain.height=p.terrain.size;const ctx=terrain.getContext('2d'),im=ctx.createImageData(terrain.width,terrain.height);

    for(let z=0;z<terrain.height;z++)for(let x=0;x<terrain.width;x++)im.data.set([...window.cityTerrainStyle.terrainColor(p,x,z),255],(z*terrain.width+x)*4);

    for(const [x,z] of (p.roads||[]))im.data.set([135,137,125,255],(z*terrain.width+x)*4);ctx.putImageData(im,0,0);

    const image=document.createElementNS(ns,'image');image.setAttribute('href',terrain.toDataURL());for(const [k,v]of Object.entries({x:lo,y:lo,width:span,height:span}))image.setAttribute(k,v);svg.append(image);
    const line=(a,b,color,width)=>{const e=document.createElementNS(ns,'line');for(const [k,v]of Object.entries({x1:a[0],y1:a[1],x2:b[0],y2:b[1],stroke:color,'stroke-width':width}))e.setAttribute(k,v);svg.append(e);};
    const cell=p.terrain.cell_m;
    for(let z=0;z<p.terrain.size;z++)for(let x=0;x<p.terrain.size;x++){const c=window.cityTerrainStyle.magicColor(p,x,z),v=p.terrain.biome_variant?.[z]?.[x];if(!c)continue;const a=lo+x*cell,b=lo+z*cell;
      for(const [dx,dz,u,w]of [[0,-1,[a,b],[a+cell,b]],[1,0,[a+cell,b],[a+cell,b+cell]],[0,1,[a+cell,b+cell],[a,b+cell]],[-1,0,[a,b+cell],[a,b]]])if(p.terrain.biome_variant?.[z+dz]?.[x+dx]!==v){line(u,w,'#dde6dd',1.4);line(u,w,`rgb(${c.join(',')})`,.7);}}
    for(const c of p.road_connections||[])if(c.status==='connected'&&c.local_path_m)for(let i=1;i<c.local_path_m.length;i++)line(c.local_path_m[i-1],c.local_path_m[i],'#edbc83',4);

    // Prefer measured wall segments (city fortifications or castle wall_networks); fall back to ring polylines.
    const segments=wallSegments(p);
    if(segments.length)for(const seg of segments)drawWallSegment2d(seg);
    else for(const ring of [...(p.fortifications?.rings||[]),...(p.wall_networks||[])]){
      const pts=ring.polyline_m||[];
      for(let i=0;i<pts.length;i++)line(pts[i],pts[(i+1)%pts.length],'#6b4a2e',3.2);
    }
    for(const gate of [...(p.fortifications?.gates||[]),...(p.wall_networks||[]).flatMap(n=>n.gates||[])]){
      const m=document.createElementNS(ns,'circle');
      for(const [k,v]of Object.entries({cx:gate.position_m[0],cy:gate.position_m[1],r:3.5,fill:'#c4a35a',stroke:'#2a1a0c','stroke-width':.6}))m.setAttribute(k,v);
      svg.append(m);
    }

    const phaseIdx=phaseOrder.indexOf(phase.value);
    const shown=p.plots.filter(b=>{
      const idx=phaseOrder.indexOf(b.phase);
      return idx>=0?idx<=phaseIdx:true;
    }).map(b=>b.housing_upgrade&&phaseOrder.indexOf(b.housing_upgrade.phase)>phaseIdx?{...b,...b.housing_upgrade.previous}:b);

    buildingSelect.replaceChildren();make('option','Select a building…',buildingSelect).value='';

    for(const b of shown){const o=make('option',`${b.name} (${b.id})`,buildingSelect);o.value=b.id;}

    buildingSelect.onchange=()=>{const b=shown.find(b=>b.id===buildingSelect.value);if(b)inspect(b);};

    viewport.style.maxHeight=view.value==='3d'?'none':'65vh';sceneContainer.style.display=view.value==='3d'?'block':'none';svg.style.display=view.value==='2d'?'block':'none';

    if(renderer&&view.value==='3d')renderer.setScene(p,shown);

    for(const b of shown){

      const g=document.createElementNS(ns,'g');g.setAttribute('tabindex','0');g.setAttribute('role','button');g.setAttribute('aria-label',b.name+' '+b.id);g.style.cursor='pointer';

      const rect=document.createElementNS(ns,'rect');
      const color=b.kind==='housing'?'#76b4d0':b.kind==='gate'||b.kind==='tower'||b.kind==='stair'?'#8a6a3e':
        b.kind==='court'?'#5a6e52':b.kind==='landmark'||b.phase==='landmarks'||b.phase==='high'?'#d9b35f':'#bd98cc';

      for(const [k,v]of Object.entries({x:b.x_m-b.plot_m.width/2,y:b.z_m-b.plot_m.depth/2,width:b.plot_m.width,height:b.plot_m.depth,fill:color,stroke:'#101b20','stroke-width':.7}))rect.setAttribute(k,v);

      g.setAttribute('transform',`rotate(${b.rotation_degrees||0} ${b.x_m} ${b.z_m})`);

      g.append(rect);const footprint=document.createElementNS(ns,'rect');for(const[k,v]of Object.entries({x:b.x_m-b.dimensions_m.width/2,y:b.z_m-b.dimensions_m.depth/2,width:b.dimensions_m.width,height:b.dimensions_m.depth,fill:'none',stroke:'#fff','stroke-width':.4}))footprint.setAttribute(k,v);g.append(footprint);

      const text=document.createElementNS(ns,'text');text.setAttribute('x',b.x_m);text.setAttribute('y',b.z_m);text.setAttribute('font-size',Math.min(4,b.plot_m.width/5));text.setAttribute('text-anchor','middle');text.setAttribute('fill','#112029');

      const words=(b.kind==='housing'?(b.building_id==='building.worker_apartment'?'Apartments ':b.building_id==='building.hamlet_house'?'Cottage ':'House ')+b.id.slice(5):b.name).split(' ');let line='',lines=[];for(const w of words){if((line+' '+w).length>14&&line){lines.push(line);line=w;}else line+=(line?' ':'')+w;}if(line)lines.push(line);

      lines.forEach((line,i)=>{const t=document.createElementNS(ns,'tspan');t.setAttribute('x',b.x_m);t.setAttribute('dy',i?4:-(lines.length-1)*2);t.textContent=line;text.append(t);});g.append(text);

      g.onclick=()=>inspect(b);g.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();inspect(b);}};svg.append(g);

    }

    const s=p.stats||{};
    if(p.kind==='castle'||p.fortress_id){
      const segs=wallSegments(p).length;
      summary.textContent=`Castle ${p.kit_name||p.kit_id||''} · ${p.status} · Wall segments: ${segs} · Shown: ${shown.length} plots · Workers: ${shown.reduce((a,b)=>a+(b.workers||0),0)}. Rings closed: ${s.wall_rings_closed??'—'}. Local terrain: ${p.terrain.cell_m} m.`;
    }else if(p.hamlet_id){
      const houseId='building.hamlet_house';
      summary.textContent=`Hamlet ${p.role||''} · ${p.shape?.shape_id?.replaceAll('_',' ')||'compact'} · ${p.status} · Shown: ${shown.filter(b=>b.kind==='service').length} services, ${shown.filter(b=>b.building_id===houseId).length} cottages, ${shown.reduce((a,b)=>a+b.workers,0)} workers / ${shown.reduce((a,b)=>a+b.beds,0)} beds. Final housing shortfall: ${s.housing_shortfall}. Parent city: ${p.core_city_uid}. Regional sample spacing: ${p.source_resolution_m} m · Local terrain: ${p.terrain.cell_m} m.`;
    }else{
      const houseId='building.worker_house',aptId='building.worker_apartment';
      summary.textContent=`${p.city_class} · ${p.shape?.shape_id?.replaceAll('_',' ')||'No suitable shape'} · ${p.status} · Shown: ${shown.filter(b=>b.kind==='service').length} services, ${shown.filter(b=>b.building_id===houseId).length} houses, ${shown.filter(b=>b.building_id===aptId).length} apartment buildings, ${shown.reduce((a,b)=>a+b.workers,0)} workers / ${shown.reduce((a,b)=>a+b.beds,0)} beds. Final housing shortfall: ${s.housing_shortfall}. Wall segments: ${wallSegments(p).length}. Urban population estimate: ${s.urban_population_estimate??'unavailable'} (a demographic estimate, not these beds). Regional sample spacing: ${p.source_resolution_m} m · Local terrain: ${p.terrain.cell_m} m.`;
    }

  }

  phase.onchange=drawCity;view.onchange=drawCity;zoom.oninput=()=>{if(view.value==='3d')renderer?.zoom(Number(zoom.value));else drawCity();};

  function showPlan(plan,heading,missingMessage,kind){
    current=plan;title.textContent=heading;failList.replaceChildren();details.textContent='Select a building or use the building list for staffing and dimensions.';renderer?.reset();
    setPhaseOptions(kind||(plan?.kind==='castle'?'castle':plan?.hamlet_id?'hamlet':'city'));
    if(current){zoom.value=1;for(const row of current.unplaced||[])make('li',`${row.count??1} × ${row.building_id}: ${row.reason}`,failList);for(const warning of current.warnings||[])make('li',warning,failList);drawCity();}
    else{svg.replaceChildren();sceneContainer.style.display='none';buildingSelect.replaceChildren();summary.textContent=missingMessage;}
    if(!dialog.open)dialog.showModal();renderer?.redraw();
  }

  window.openCityPlan=site=>{
    showPlan(data.city_plans?.cities.find(p=>p.city_uid===site.uid||p.site_id===site.id)||null,
             (site.name||'City')+' — City layout',
             'City filling is available after Simulation complete. Generate all 16 stages and inspect the final stage.',
             'city');
  };

  window.openHamletPlan=site=>{
    showPlan(data.hamlet_plans?.hamlets.find(p=>p.hamlet_id===site.id||p.node===site.node)||null,
             `${site.id} · ${site.role||'hamlet'} — Hamlet layout`,
             'Hamlet filling is available after Simulation complete. Generate all 16 stages and inspect the final stage.',
             'hamlet');
  };

  window.openCastlePlan=site=>{
    showPlan(data.castle_plans?.castles.find(p=>p.fortress_id===site.id||p.x===site.x&&p.z===site.z)||null,
             `${site.id} — Castle layout`,
             'Castle filling is available after Simulation complete. Generate all 16 stages and inspect the final stage.',
             'castle');
  };

  function nearest(event,canvas,globe=false){

    const rect=canvas.getBoundingClientRect(),mx=(event.clientX-rect.left)*canvas.width/rect.width,my=(event.clientY-rect.top)*canvas.height/rect.height,n=data.config.size;

    let best=null,distance=16*canvas.width/rect.width;

    function projectSite(site){
      let x=site.x/(n-1)*canvas.width,y=site.z/(n-1)*canvas.height;
      if(globe){const lat=Math.PI/2-site.z/(n-1)*Math.PI,lon=site.x/(n-1)*2*Math.PI-Math.PI,p=[Math.cos(lat)*Math.cos(lon),Math.sin(lat),Math.cos(lat)*Math.sin(lon)],yaw=Number(document.getElementById('yaw').value)*Math.PI/180,pitch=Number(document.getElementById('pitch').value)*Math.PI/180,xx=p[0]*Math.cos(yaw)+p[2]*Math.sin(yaw),zz=-p[0]*Math.sin(yaw)+p[2]*Math.cos(yaw),yy=p[1]*Math.cos(pitch)-zz*Math.sin(pitch),depth=p[1]*Math.sin(pitch)+zz*Math.cos(pitch);if(depth<.08)return null;const r=(data.effective_config||data.config).globe_radius,rad=1+Number(document.getElementById('relief').value)*(data.layers.water_surface?.[site.z]?.[site.x]||0)/r,scale=230*Number(document.getElementById('zoom').value);x=360+xx*rad*scale;y=310-yy*rad*scale;}
      return [x,y];
    }

    for(const site of data.settlements?.sites||[]){const xy=projectSite(site);if(!xy)continue;const d=Math.hypot(xy[0]-mx,xy[1]-my);if(d<distance){distance=d;best={kind:'city',site};}}
    for(const site of data.humans?.hamlets||[]){const xy=projectSite(site);if(!xy)continue;const d=Math.hypot(xy[0]-mx,xy[1]-my);if(d<distance){distance=d;best={kind:'hamlet',site};}}
    for(const site of data.humans?.fortresses||[]){const xy=projectSite(site);if(!xy)continue;const d=Math.hypot(xy[0]-mx,xy[1]-my);if(d<distance){distance=d;best={kind:'castle',site};}}
    return best;

  }

  function openNearest(hit){
    if(!hit)return;
    if(hit.kind==='hamlet')window.openHamletPlan(hit.site);
    else if(hit.kind==='castle')window.openCastlePlan(hit.site);
    else window.openCityPlan(hit.site);
  }

  document.addEventListener('click',e=>{

    const canvas=e.target;if(canvas.tagName==='CANVAS'&&['map','world-atlas'].includes(canvas.id)){const hit=nearest(e,canvas);if(hit){e.stopImmediatePropagation();openNearest(hit);}}

    const button=e.target.closest('button');if(button&&!dialog.contains(button)){const site=data.settlements?.sites.find(s=>s.uid===button.dataset.cityUid||s.name===button.textContent);if(site){e.stopImmediatePropagation();window.openCityPlan(site);}}

  },true);

  const globe=document.getElementById('globe');let down=null;

  globe.addEventListener('pointerdown',e=>{down=[e.clientX,e.clientY];});

  globe.addEventListener('pointerup',e=>{if(down&&Math.hypot(e.clientX-down[0],e.clientY-down[1])<5){const hit=nearest(e,globe,true);if(hit){e.stopImmediatePropagation();openNearest(hit);}}down=null;});

  globe.addEventListener('pointercancel',()=>{down=null;});

})();
