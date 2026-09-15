"""Inspectable artistic climate proxies and terrain labels, not weather simulation."""
import math
import heapq
from time import perf_counter
from .terrain_globe import direction, perlin3
from .terrain_tectonics import child_seed

from .terrain_biome_catalogue import natural_catalogue

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
            form=0 if h<=0 else 2 if h>30 and tpi>12 else 3 if tpi< -10 else 1
            for k,v in zip(fields,(temp,wet,biome,form)): rows[k].append(v)
            if h>0 and water==0 and z not in (0,n-1):
                kind='marsh' if biome==13 else 'mountain' if form==2 else 'forest' if biome in (4,7) else 'desert' if biome==2 else 'snow' if biome==6 else None
                if kind:
                    score=tpi+h*.1 if kind=='mountain' else wet if kind=='forest' else 1-wet if kind=='desert' else -temp
                    candidates.append((score,kind,x,z,p))
        for key,row in rows.items(): fields[key].append(row*n if z in (0,n-1) else row+[row[0]])
    layers.update(fields)
    # Balanced per-kind selection, angular separation also wraps over the seam.
    selected=[]
    for kind in ('marsh','mountain','forest','desert','snow'):
        count=0
        for score,k,x,z,p in sorted(candidates,reverse=True):
            if k!=kind: continue
            if any(sum(a*b for a,b in zip(p,f['direction']))>math.cos(.24) for f in selected): continue
            selected.append({'kind':kind,'x':x,'z':z,'direction':p,'height_m':layers['height'][z][x],
                             'label':{'marsh':'Wetland margin','mountain':'Prominent ridge','forest':'Forest region','desert':'Dry region','snow':'Snow region'}[kind]})
            count+=1
            if count==4: break
    result['terrain']={'version':6,'biomes':natural_catalogue(),'natural_biomes':natural_catalogue(),
                       'landforms':LANDFORMS,'features':selected,'climate_seed':seed,
                       'method':'Temperature: latitude and elevation proxy. Moisture: latitude and seeded spatial noise. No prevailing winds, rainfall or rain shadows simulated.',
                       'icons':'Sparse representative regions and prominent ridges; not unique geological objects.'}
    if result.get('climate'):
        result['terrain']['version']=6
        result['terrain']['method']='Temperature remains a latitude/elevation proxy. Biome moisture now follows wind-transport rainfall; lake extents still assume equilibrium filling.'
    layers['natural_biome']=[row[:] for row in layers['biome']]
    if wetland:result['terrain']['method']+=' Marsh is wet, unfrozen, gently sloping land within 180 m and 4 m above mapped water; no soil saturation simulation.'
    result['warnings'].append(result['terrain']['method'])
    elapsed=(perf_counter()-started)*1000; result['timing_ms']['classification']=elapsed; result['timing_ms']['total']+=elapsed
    return result
