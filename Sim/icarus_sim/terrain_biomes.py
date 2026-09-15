"""Inspectable artistic climate proxies and terrain labels, not weather simulation."""
import math
import heapq
from time import perf_counter
from .terrain_globe import direction, perlin3
from .terrain_tectonics import child_seed

BIOMES=[('Submerged',[42,102,147]),('Tundra',[156,164,126]),
        ('Desert',[218,184,120]),('Grassland',[139,176,99]),
        ('Forest',[65,135,80]),('Exposed rock',[145,143,139]),('Snow',[230,240,241]),
        ('Rainforest',[22,83,58]),('Lake',[68,160,185]),('Desolation',[82,65,67]),('Fungal forest',[139,103,169]),('Crystalline desert',[174,190,215]),('Enchanted forest',[40,145,132]),('Marsh',[105,135,101]),('Haunted marsh',[100,119,143])]
LANDFORMS=['Submerged','Plain / hillside','Mountain / ridge','Valley']


def marsh_suitable(wet,temp,slope,water_distance,height_above_water):
    return wet>=.55 and temp>0 and slope<6 and 0<=water_distance<=180 and 0<=height_above_water<=4


def wetland_access(result,cfg):
    """Nearest mapped water on the sphere, limited to a 180 metre wetland margin."""
    from .terrain_erosion import sphere_grid
    from .terrain_climate import node_grid
    n=cfg.size;points,_,graph=sphere_grid(n,result['effective_config']['globe_radius']);l=result['layers']
    distance=[math.inf]*len(points);source=[-1]*len(points);queue=[]
    river=l.get('rain_river',l.get('river'))
    for i,(x,z) in enumerate(points):
        if l['water_type'][z][x] or (river and river[z][x]):
            distance[i]=0;source[i]=i;heapq.heappush(queue,(0,i))
    while queue:
        d,i=heapq.heappop(queue)
        if d!=distance[i]:continue
        for j,edge in graph[i]:
            candidate=d+edge
            if candidate<=180 and candidate<distance[j]:
                distance[j]=candidate;source[j]=source[i];heapq.heappush(queue,(candidate,j))
    relief=[]
    for i,(x,z) in enumerate(points):
        sx,sz=points[source[i]] if source[i]>=0 else (x,z)
        relief.append(l['height'][z][x]-l['water_surface'][sz][sx])
    return node_grid([d if math.isfinite(d) else -1 for d in distance],points,n),node_grid(relief,points,n)

def classify(above_sea,slope,temperature,moisture):
    if above_sea<=0: return 0
    if temperature<=0: return 6
    if slope>=38: return 5
    if temperature<5: return 1
    if moisture<.3: return 2
    if temperature>=20 and moisture>=.78: return 7
    if moisture>=.55: return 4
    return 3

def add_terrain_labels(result,cfg):
    if cfg.shape!='globe' or (cfg.tectonics and cfg.phase<2): return result
    started=perf_counter(); layers=result['layers']; n=cfg.size
    sea=result['effective_config']['sea_level']; seed=child_seed(cfg.seed,'climate')
    from .terrain_magic import magic_biome
    magical='magic_density' in layers
    wetland=wetland_access(result,cfg) if 'water_type' in layers else None
    water_layer=layers.get('water_type',[[0]*n]*n)
    fields={k:[] for k in ('temperature','moisture','biome','landform')}; candidates=[]
    for z in range(n):
        rows={k:[] for k in fields}
        for x in range(1 if z in (0,n-1) else n-1):
            p=direction(x,z,n); h=layers['height'][z][x]-sea
            temp=28-45*p[1]**2-.0065*max(0,h)+cfg.temperature_offset
            wet=max(0,min(1,.5+.22*math.cos(3*math.asin(p[1]))+.9*perlin3(*(v*2.3 for v in p),seed)+cfg.moisture_bias))
            if 'climate_moisture' in layers:wet=layers['climate_moisture'][z][x]
            slope=layers['slope'][z][x]; tpi=layers['tpi'][z][x]
            biome=classify(h,slope,temp,wet)
            water=water_layer[z][x]
            if water==1:biome=0
            elif water==2:biome=8
            if wetland and water==0 and h>0 and wetland[0][z][x]>=0 and marsh_suitable(wet,temp,slope,wetland[0][z][x],wetland[1][z][x]):biome=13
            if magical:biome=magic_biome(biome,layers['magic_density'][z][x],layers['magic_hazard'][z][x],layers['magic_growth'][z][x],wet,temp)
            form=0 if h<=0 else 2 if h>30 and tpi>12 else 3 if tpi< -10 else 1
            for k,v in zip(fields,(temp,wet,biome,form)): rows[k].append(v)
            if h>0 and water==0 and z not in (0,n-1):
                kind='haunted' if biome==14 else 'marsh' if biome==13 else 'crystal' if biome==11 else 'enchanted' if biome==12 else 'desolation' if biome==9 else 'fungal' if biome==10 else 'mountain' if form==2 else 'forest' if biome in (4,7) else 'desert' if biome==2 else 'snow' if biome==6 else None
                if kind:
                    score=tpi+h*.1 if kind=='mountain' else wet if kind=='forest' else 1-wet if kind=='desert' else -temp
                    candidates.append((score,kind,x,z,p))
        for key,row in rows.items(): fields[key].append(row*n if z in (0,n-1) else row+[row[0]])
    layers.update(fields)
    # Balanced per-kind selection, angular separation also wraps over the seam.
    selected=[]
    for kind in ('desolation','fungal','crystal','enchanted','haunted','marsh','mountain','forest','desert','snow'):
        count=0
        for score,k,x,z,p in sorted(candidates,reverse=True):
            if k!=kind: continue
            if any(sum(a*b for a,b in zip(p,f['direction']))>math.cos(.24) for f in selected): continue
            selected.append({'kind':kind,'x':x,'z':z,'direction':p,'height_m':layers['height'][z][x],
                             'label':{'marsh':'Wetland margin','haunted':'Haunted wetland','crystal':'Crystalline desert','enchanted':'Enchanted woodland','desolation':'Desolation region','fungal':'Fungal forest','mountain':'Prominent ridge','forest':'Forest region','desert':'Dry region','snow':'Snow region'}[kind]})
            count+=1
            if count==(2 if magical else 4): break
    result['terrain']={'version':4,'biomes':[{'id':i,'name':name,'color':color} for i,(name,color) in enumerate(BIOMES)],
                       'landforms':LANDFORMS,'features':selected,'climate_seed':seed,
                       'method':'Temperature: latitude and elevation proxy. Moisture: latitude and seeded spatial noise. No prevailing winds, rainfall or rain shadows simulated.',
                       'icons':'Sparse representative regions and prominent ridges; not unique geological objects.'}
    if result.get('climate'):
        result['terrain']['version']=4
        result['terrain']['method']='Temperature remains a latitude/elevation proxy. Biome moisture now follows wind-transport rainfall; lake extents still assume equilibrium filling.'
    if magical:
        result['terrain']['version']=4
        result['terrain']['method']+=' Leyline affinity and mutation create Desolation, Fungal forest, Crystalline desert, Enchanted forest and Haunted marsh on land; water remains water.'
    if wetland:result['terrain']['method']+=' Marsh is wet, unfrozen, gently sloping land within 180 m and 4 m above mapped water; no soil saturation simulation.'
    result['warnings'].append(result['terrain']['method'])
    elapsed=(perf_counter()-started)*1000; result['timing_ms']['classification']=elapsed; result['timing_ms']['total']+=elapsed
    return result
