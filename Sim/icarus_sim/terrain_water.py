"""Connected ocean and equilibrium lake spill routing on the physical globe."""
import heapq
from time import perf_counter
from .terrain_erosion import sphere_grid


def route_water(h,areas,neighbors,sea):
    remaining={i for i,v in enumerate(h) if v<=sea}; components=[]
    while remaining:
        start=min(remaining); remaining.remove(start); group=[start]; stack=[start]
        while stack:
            i=stack.pop()
            for j,_ in neighbors[i]:
                if j in remaining: remaining.remove(j);group.append(j);stack.append(j)
        components.append(group)
    ocean_ids=max(components,key=lambda ids:sum(areas[i] for i in ids)) if components else []
    ocean=[False]*len(h)
    for i in ocean_ids:ocean[i]=True
    roots=ocean_ids or [min(range(len(h)),key=lambda i:(h[i],i))]
    root_set=set(roots)
    level=h[:]; parent=[-1]*len(h); visited=set(roots); queue=[];order=[]
    for i in roots:
        level[i]=sea if ocean[i] else h[i];heapq.heappush(queue,(level[i],i))
    while queue:
        elevation,i=heapq.heappop(queue);order.append(i)
        for j,_ in neighbors[i]:
            if j in visited:continue
            visited.add(j);parent[j]=i;level[j]=max(h[j],elevation)
            heapq.heappush(queue,(level[j],j))
    # Select steepest descent on the spill surface where possible. Flood parents
    # route flats without cycles; each receiver precedes its child in order.
    rank={i:k for k,i in enumerate(order)}
    for i in order:
        if i in root_set:continue
        lower=[((level[i]-level[j])/d,j) for j,d in neighbors[i] if d>0 and level[j]<level[i] and rank[j]<rank[i]]
        if lower:parent[i]=max(lower)[1]
    flow=areas[:]
    for i in reversed(order):
        if parent[i]>=0:flow[parent[i]]+=flow[i]
    return {'ocean':ocean,'level':level,'parent':parent,'flow':flow,'order':order}


def add_water(result,cfg):
    if cfg.shape!='globe' or not cfg.tectonics or cfg.phase<5:return result
    started=perf_counter();n=cfg.size;physical=result['effective_config']
    points,areas,neighbors=sphere_grid(n,physical['globe_radius'])
    h=[result['layers']['height'][z][x] for x,z in points]
    routed=route_water(h,areas,neighbors,physical['sea_level'])
    depth=[max(0,v-ground) for v,ground in zip(routed['level'],h)]
    kind=[1 if ocean else 2 if d>1e-7 else 0 for ocean,d in zip(routed['ocean'],depth)]
    # Uniform unit runoff proxy, not rainfall volume. River width is not modelled.
    river=[kind[i]==0 and routed['parent'][i]>=0 and routed['flow'][i]>=cfg.river_threshold_km2*1e6 for i in range(len(h))]
    def grid(values):
        out=[[0.]*n for _ in range(n)]
        for (x,z),v in zip(points,values):out[z][x]=v
        out[0]=[values[0]]*n;out[-1]=[values[-1]]*n
        for row in out:row[-1]=row[0]
        return out
    result['layers'].update({'water_type':grid(kind),'water_depth':grid(depth),
        'water_surface':grid(routed['level']),'routed_catchment':grid(routed['flow']),'river':grid([int(v) for v in river])})
    segments=[]
    for i,active in enumerate(river):
        if active:
            j=routed['parent'][i]
            segments.append([i,j])
    result['water']={'version':1,'nodes':points,'receivers':routed['parent'],'river_segments':segments,
        'ocean_km2':sum(a for a,k in zip(areas,kind) if k==1)/1e6,
        'lake_km2':sum(a for a,k in zip(areas,kind) if k==2)/1e6,
        'dry_km2':sum(a for a,k in zip(areas,kind) if k==0)/1e6,
        'lake_capacity_m3':sum(a*d for a,d,k in zip(areas,depth,kind) if k==2),
        'has_ocean':any(routed['ocean']),
        'method':'Largest connected below-sea component is the ocean. Inland depressions are filled to their spill levels assuming sufficient water. Water extents do not use a rainfall budget or time-dependent filling; lake evaporation and river width are not modelled.',
        'routing':'Receivers index unique spherical nodes; -1 is an ocean outlet or the global minimum in an oceanless world. Catchment assumes uniform unit runoff.'}
    result['warnings'].append(result['water']['method'])
    elapsed=(perf_counter()-started)*1000;result['timing_ms']['water']=elapsed;result['timing_ms']['total']+=elapsed
    return result
