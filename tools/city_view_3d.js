/* Dependency-free metre-scale terrain and cuboids. WebGL depth testing handles occlusion. */
(() => {
  const radians=d=>d*Math.PI/180;
  function terrainColor(plan,x,z){return plan.terrain.biome_catalogue?.find(b=>b.id===plan.terrain.natural_biome?.[z]?.[x])?.color||[[59,99,71],[41,89,120],[110,66,59]][plan.terrain.codes[z][x]];}
  function magicColor(plan,x,z){const v=plan.terrain.biome_variant?.[z]?.[x];if(!(v>=0))return null;const school=plan.terrain.magical_catalogue?.[v]?.magic_school;return plan.terrain.magic_colors?.[school]||null;}
  function heightAt(plan,x,z){
    const surface=plan.terrain.surface;if(!surface)return 0;
    const n=surface.size,lo=plan.bounds_m[0],step=surface.step_m;
    const gx=Math.max(0,Math.min(n-1,(x-lo)/step)),gz=Math.max(0,Math.min(n-1,(z-lo)/step));
    const i=Math.min(n-2,Math.floor(gx)),j=Math.min(n-2,Math.floor(gz)),u=gx-i,v=gz-j,h=surface.heights_m;
    return (h[j][i]*(1-u)+h[j][i+1]*u)*(1-v)+(h[j+1][i]*(1-u)+h[j+1][i+1]*u)*v;
  }
  function boxVertices(b,datum=0,bottom=b.ground_elevation_m||0,top=bottom+b.dimensions_m.height){
    const a=radians(b.rotation_degrees||0),c=Math.cos(a),s=Math.sin(a),w=b.dimensions_m.width/2,d=b.dimensions_m.depth/2;
    return [bottom,top].flatMap(y=>[[-w,-d],[w,-d],[w,d],[-w,d]].map(([x,z])=>[b.x_m+x*c-z*s,y-datum,b.z_m+x*s+z*c]));
  }
  const faces=[[0,3,2,1],[4,5,6,7],[0,1,5,4],[1,2,6,5],[2,3,7,6],[3,0,4,7]];
  /** Collect curtain/wall segments from city fortifications or castle wall_networks. */
  function wallSegments(plan){
    const rows=[];
    for(const seg of plan.fortifications?.segments||[])rows.push(seg);
    for(const network of plan.wall_networks||[])for(const seg of network.segments||[])rows.push(seg);
    return rows;
  }
  function segmentPlot(seg){
    const a=seg.from_m,b=seg.to_m,dx=b[0]-a[0],dz=b[1]-a[1],len=Math.hypot(dx,dz)||seg.length_m||1;
    const thickness=seg.thickness_m??3,height=seg.height_m??7;
    const heading=Math.atan2(dz,dx)*180/Math.PI;
    // Authored curtain depth runs along the wall; box +Z must follow from_m→to_m or the box becomes a giant spike.
    const angle=heading-90;
    return {x_m:(a[0]+b[0])/2,z_m:(a[1]+b[1])/2,rotation_degrees:angle,
      dimensions_m:{width:thickness,depth:len,height},
      ground_elevation_m:seg.ground_elevation_m,foundation_bottom_m:seg.foundation_bottom_m};
  }
  function geometry(plan,plots){
    const datum=heightAt(plan,0,0),positions=[],colors=[];
    function triangle(a,b,c,color){
      const u=b.map((v,i)=>v-a[i]),v=c.map((v,i)=>v-a[i]);
      let normal=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]];
      const len=Math.hypot(...normal)||1;normal=normal.map(v=>v/len);
      const shade=.6+.4*Math.max(0,normal[0]*-.35+Math.abs(normal[1])*.8+normal[2]*.45);
      for(const p of [a,b,c]){positions.push(...p);colors.push(...color.map(v=>v*shade));}
    }
    const lo=plan.bounds_m[0],step=plan.terrain.cell_m,n=plan.terrain.size,roads=new Set((plan.roads||[]).map(c=>c.join(',')));
    for(let j=0;j<n;j++)for(let i=0;i<n;i++){
      const x=lo+i*step,z=lo+j*step;
      const points=[[x,z],[x+step,z],[x+step,z+step],[x,z+step]].map(([x,z])=>[x,heightAt(plan,x,z)-datum,z]);
      const color=roads.has(`${i},${j}`)?[.53,.54,.49]:terrainColor(plan,i,j).map(v=>v/255);
      triangle(points[0],points[2],points[1],color);triangle(points[0],points[3],points[2],color);
      const magic=magicColor(plan,i,j),variant=plan.terrain.biome_variant?.[j]?.[i];
      if(magic)for(const [dx,dz,a,b]of [[0,-1,[x,z],[x+step,z]],[1,0,[x+step,z],[x+step,z+step]],[0,1,[x+step,z+step],[x,z+step]],[-1,0,[x,z+step],[x,z]]]){
        if(plan.terrain.biome_variant?.[j+dz]?.[i+dx]===variant)continue;
        strip(a,b,1.4,[.8,.85,.8],.14);strip(a,b,.7,magic.map(v=>v/255),.18);
      }
    }
    function strip(a,b,width,color,lift=.1){const length=Math.hypot(b[0]-a[0],b[1]-a[1]);if(!length)return;const dx=-(b[1]-a[1])/length*width/2,dz=(b[0]-a[0])/length*width/2;
      const q=[[a[0]+dx,a[1]+dz],[b[0]+dx,b[1]+dz],[b[0]-dx,b[1]-dz],[a[0]-dx,a[1]-dz]].map(([x,z])=>[x,heightAt(plan,x,z)-datum+lift,z]);triangle(q[0],q[2],q[1],color);triangle(q[0],q[3],q[2],color);}
    for(const c of plan.road_connections||[])if(c.status==='connected')for(let i=1;i<(c.local_path_m||[]).length;i++)strip(c.local_path_m[i-1],c.local_path_m[i],4,[.93,.65,.32]);
    function box(b,bottom,top,color){const v=boxVertices(b,datum,bottom,top);for(const [a,c,d,e]of faces){triangle(v[a],v[c],v[d],color);triangle(v[a],v[d],v[e],color);}}
    // Curtain / city-wall segments as extruded metre boxes (brown).
    for(const seg of wallSegments(plan)){
      const b=segmentPlot(seg);
      const floor=b.ground_elevation_m??heightAt(plan,b.x_m,b.z_m);
      box(b,floor+.02,floor+Math.max(.5,b.dimensions_m.height),[.42,.29,.18]);
    }
    for(const b of plots){
      const floor=b.ground_elevation_m??heightAt(plan,b.x_m,b.z_m),base=b.foundation_bottom_m??floor;
      if(floor>base+.01)box(b,base,floor,[.4,.41,.4]);
      const color=b.kind==='housing'?[.46,.71,.82]:b.kind==='gate'||b.kind==='tower'||b.kind==='stair'?[.55,.45,.28]:
        b.kind==='court'?[.35,.42,.32]:b.kind==='landmark'?[.72,.58,.32]:b.phase==='high'||b.phase==='landmarks'?[.85,.70,.37]:[.74,.60,.80];
      box(b,floor+.03,floor+Math.max(.03,b.dimensions_m.height||.03),color);
    }
    return {positions:new Float32Array(positions),colors:new Float32Array(colors),datum,wall_segment_count:wallSegments(plan).length};
  }
  const api={heightAt,boxVertices,geometry,terrainColor,magicColor,wallSegments,segmentPlot};
  if(typeof window!=='undefined')window.cityTerrainStyle={terrainColor,magicColor};
  if(typeof module!=='undefined')module.exports=api;
  if(typeof window==='undefined')return;
  window.CityGeometry=api;
  window.createCity3D=(container,onInspect)=>{
    const canvas=document.createElement('canvas'),overlay=document.createElement('canvas');
    container.style.cssText='position:relative;width:100%;height:min(52vh,560px);min-height:320px;background:#101f28;touch-action:none';
    for(const c of [canvas,overlay]){c.style.cssText='position:absolute;width:100%;height:100%;left:0;top:0';container.append(c);}
    overlay.style.pointerEvents='none';overlay.style.background='transparent';canvas.setAttribute('aria-label','3D settlement terrain and buildings. Drag to orbit; scroll to zoom. Select a building from the list for keyboard access.');
    const gl=canvas.getContext('webgl',{antialias:true,alpha:false});if(!gl){container.remove();return null;}
    function shader(type,source){const s=gl.createShader(type);gl.shaderSource(s,source);gl.compileShader(s);if(!gl.getShaderParameter(s,gl.COMPILE_STATUS))throw Error(gl.getShaderInfoLog(s));return s;}
    const program=gl.createProgram();
    gl.attachShader(program,shader(gl.VERTEX_SHADER,`attribute vec3 position;attribute vec3 color;varying vec3 shade;uniform vec4 camera;uniform vec4 lens;
      void main(){float cy=cos(camera.x),sy=sin(camera.x),cp=cos(camera.y),sp=sin(camera.y);
      float x=position.x*cy+position.z*sy,z=-position.x*sy+position.z*cy;
      float y=position.y*cp-z*sp,depth=camera.z-(position.y*sp+z*cp);
      gl_Position=vec4(x*lens.x/lens.y,y*lens.x,lens.z*depth+lens.w,depth);shade=color;}`));
    gl.attachShader(program,shader(gl.FRAGMENT_SHADER,'precision mediump float;varying vec3 shade;void main(){gl_FragColor=vec4(shade,1.0);}'));
    gl.linkProgram(program);if(!gl.getProgramParameter(program,gl.LINK_STATUS))throw Error(gl.getProgramInfoLog(program));
    const buffers=[gl.createBuffer(),gl.createBuffer()],attributes=['position','color'].map(n=>gl.getAttribLocation(program,n));
    const cam=gl.getUniformLocation(program,'camera'),lens=gl.getUniformLocation(program,'lens');
    let plan=null,plots=[],datum=0,count=0,yaw=-.6,pitch=.8,zoom=1,labels=false,selected=null,drag=null;
    function project(p){const cy=Math.cos(yaw),sy=Math.sin(yaw),cp=Math.cos(pitch),sp=Math.sin(pitch),span=plan.bounds_m[2]-plan.bounds_m[0],distance=span*1.65/zoom;
      const x=p[0]*cy+p[2]*sy,z=-p[0]*sy+p[2]*cy,y=p[1]*cp-z*sp,depth=distance-(p[1]*sp+z*cp);
      return [canvas.width/2+x*1.9/depth*canvas.height/2,canvas.height/2-y*1.9/depth*canvas.height/2,depth];}
    function draw(){
      if(!plan)return;
      const rect=container.getBoundingClientRect(),scale=Math.min(2,window.devicePixelRatio||1);if(!rect.width)return;
      const w=Math.round(rect.width*scale),h=Math.round(rect.height*scale);
      if(canvas.width!==w||canvas.height!==h){canvas.width=overlay.width=w;canvas.height=overlay.height=h;}
      gl.viewport(0,0,w,h);gl.clearColor(.06,.12,.16,1);gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);gl.enable(gl.DEPTH_TEST);gl.useProgram(program);
      const span=plan.bounds_m[2]-plan.bounds_m[0],near=.5,far=span*12;
      gl.uniform4f(cam,yaw,pitch,span*1.65/zoom,0);gl.uniform4f(lens,1.9,w/h,(far+near)/(far-near),-2*far*near/(far-near));
      buffers.forEach((b,i)=>{gl.bindBuffer(gl.ARRAY_BUFFER,b);gl.enableVertexAttribArray(attributes[i]);gl.vertexAttribPointer(attributes[i],3,gl.FLOAT,false,0,0);});
      gl.drawArrays(gl.TRIANGLES,0,count);
      const ctx=overlay.getContext('2d');ctx.clearRect(0,0,w,h);ctx.font=`${11*scale}px sans-serif`;ctx.textAlign='center';
      for(const b of plots){if(!labels&&b.id!==selected)continue;const v=boxVertices(b,datum),p=project([b.x_m,v[4][1],b.z_m]);if(p[2]<=0)continue;
        if(b.id===selected){ctx.strokeStyle='#fff';ctx.lineWidth=2*scale;ctx.beginPath();[4,5,6,7,4].forEach((i,k)=>{const q=project(v[i]);k?ctx.lineTo(q[0],q[1]):ctx.moveTo(q[0],q[1]);});ctx.stroke();}
        ctx.strokeStyle='#101b20';ctx.lineWidth=3*scale;ctx.strokeText(b.name,p[0],p[1]-5*scale);ctx.fillStyle='#fff';ctx.fillText(b.name,p[0],p[1]-5*scale);
      }
    }
    function pick(event){
      if(!plan)return;const rect=canvas.getBoundingClientRect(),x=(event.clientX-rect.left)*canvas.width/rect.width,y=(event.clientY-rect.top)*canvas.height/rect.height;
      let hit=null,depth=Infinity;
      function inside(points){let yes=false;for(let i=0,j=points.length-1;i<points.length;j=i++){const a=points[i],b=points[j];if((a[1]>y)!==(b[1]>y)&&x<(b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0])yes=!yes;}return yes;}
      for(const b of plots){const v=boxVertices(b,datum).map(project);for(const face of faces){const ps=face.map(i=>v[i]);if(ps.some(p=>p[2]<=0))continue;const d=ps.reduce((s,p)=>s+p[2],0)/4;if(d<depth&&inside(ps)){depth=d;hit=b;}}}
      if(hit){selected=hit.id;onInspect(hit);draw();}
    }
    canvas.onpointerdown=e=>{drag={x:e.clientX,y:e.clientY,startX:e.clientX,startY:e.clientY,moved:false};canvas.setPointerCapture(e.pointerId);};
    canvas.onpointermove=e=>{if(!drag)return;const dx=e.clientX-drag.x,dy=e.clientY-drag.y;drag.moved ||= Math.hypot(e.clientX-drag.startX,e.clientY-drag.startY)>4;yaw+=dx*.007;pitch=Math.max(.12,Math.min(1.5,pitch+dy*.007));drag.x=e.clientX;drag.y=e.clientY;draw();};
    canvas.onpointerup=e=>{if(drag&&!drag.moved)pick(e);drag=null;};canvas.onpointercancel=()=>{drag=null;};
    canvas.addEventListener('wheel',e=>{e.preventDefault();zoom=Math.max(.7,Math.min(4,zoom*Math.exp(-e.deltaY*.001)));draw();},{passive:false});
    new ResizeObserver(draw).observe(container);
    return {setScene(p,shown){plan=p;plots=shown;const g=geometry(p,shown);datum=g.datum;count=g.positions.length/3;
      [g.positions,g.colors].forEach((v,i)=>{gl.bindBuffer(gl.ARRAY_BUFFER,buffers[i]);gl.bufferData(gl.ARRAY_BUFFER,v,gl.STATIC_DRAW);});draw();},
      zoom(v){zoom=v;draw();},labels(v){labels=v;draw();},select(id){selected=id;draw();},reset(){yaw=-.6;pitch=.8;zoom=1;selected=null;draw();},redraw:draw};
  };
})();
