"""Conservative, downhill sediment experiment on a spherical nodal grid.

Closed depressions retain sediment; this does not simulate lake overflow or rain.
"""
import math
from functools import lru_cache
from .terrain_globe import direction


# Pure in (n, radius) and rebuilt from scratch by sixteen call sites, roughly forty
# times per world: at grid 129 that is forty passes over sixteen thousand nodes
# computing an arc length per neighbour. No caller mutates the returned lists, so
# the grid is shared. Two entries bound the memory a 257 grid can retain.
@lru_cache(maxsize=2)
def sphere_grid(n, radius):
    points=[(0,0)]+[(x,z) for z in range(1,n-1) for x in range(n-1)]+[(0,n-1)]
    lookup={p:i for i,p in enumerate(points)}
    def index(x,z):
        return lookup[(0,z) if z in (0,n-1) else (x%(n-1),z)]
    vectors=[direction(x,z,n) for x,z in points]
    areas=[]; neighbors=[]; step=math.pi/(n-1)
    for i,(x,z) in enumerate(points):
        lat=math.pi/2-z*step
        area=radius**2*2*step*(math.sin(min(math.pi/2,lat+step/2))-math.sin(max(-math.pi/2,lat-step/2)))
        areas.append(area*(n-1 if z in (0,n-1) else 1))
        if z in (0,n-1):
            ids={index(xx,1 if z==0 else n-2) for xx in range(n-1)}
        else:
            ids={index(x+dx,z+dz) for dx in (-1,0,1) for dz in (-1,0,1)}-{i}
        neighbors.append([(j,radius*math.acos(max(-1,min(1,sum(a*b for a,b in zip(vectors[i],vectors[j])))))) for j in sorted(ids)])
    return points,areas,neighbors


_INDEX={}


def sphere_index(points):
    """`{(x,z):i}` and the grid width for a `sphere_grid` point list, built once.

    Every routing cost function needs to name the two corner cells a diagonal step would
    otherwise slip between, and each was rebuilding this sixteen-thousand-entry map --
    and rescanning the same points for the width -- on every call. One
    `add_world_society` at size 128 built it 3 886 times for twelve seconds.

    Keyed on the identity of the point list rather than on `(n, radius)`, because
    `water_cost` is handed the points and never learns the radius. The entry holds the
    list itself, so the id cannot be recycled by a later grid while the entry lives.
    """
    entry=_INDEX.get(id(points))
    if entry is None or entry[0] is not points:
        if len(_INDEX)>4:_INDEX.clear()
        entry=_INDEX[id(points)]=(points,{p:i for i,p in enumerate(points)},max(z for x,z in points)+1)
    return entry[1],entry[2]


def erode(height,radius,sea_level,passes,strength):
    n=len(height); points,areas,neighbors=sphere_grid(n,radius)
    h=[height[z][x] for x,z in points]; original=h[:]; ceiling=max(h)
    sediment=[0.]*len(h); cut=[0.]*len(h); fill=[0.]*len(h)
    flow=areas[:]; total_cut=total_fill=0.
    def routes():
        receivers=[]
        for i in range(len(h)):
            candidates=[((h[i]-h[j])/distance,j,distance) for j,distance in neighbors[i] if h[j]<h[i] and distance>0]
            receivers.append(max(candidates) if candidates and h[i]>sea_level else (0.,-1,1.))
        order=sorted(range(len(h)),key=lambda i:(-h[i],i))
        discharge=areas[:]
        for i in order:
            j=receivers[i][1]
            if j>=0: discharge[j]+=discharge[i]
        return receivers,order,discharge
    for _ in range(passes):
        receivers,order,flow=routes()
        delta=[0.]*len(h); retained=[0.]*len(h)
        for i in order:
            slope,j,distance=receivers[i]
            # Stream-power proxy, limited to a fraction of the downstream drop.
            depth=min(.15*(h[i]-h[j]),strength*.04*math.sqrt(flow[i])*slope) if j>=0 else 0.
            capacity=2*depth*areas[i]
            incoming=sediment[i]
            removed=min(depth*areas[i],max(0.,capacity-incoming))
            load=incoming+removed
            deposited=min(max(0.,load-capacity),max(0.,ceiling-h[i])*.25*areas[i])
            delta[i]+=(deposited-removed)/areas[i]
            cut[i]+=removed/areas[i]; fill[i]+=deposited/areas[i]
            total_cut+=removed; total_fill+=deposited
            if j>=0: sediment[j]+=load-deposited
            else: retained[i]=load-deposited
        h=[v+d for v,d in zip(h,delta)]; sediment=retained
    # Diagnostics describe the final surface, not the preceding iteration.
    receivers,order,flow=routes()
    def grid(values):
        out=[[0.]*n for _ in range(n)]
        for (x,z),v in zip(points,values): out[z][x]=v
        out[0]=[values[0]]*n; out[-1]=[values[-1]]*n
        for row in out: row[-1]=row[0]
        return out
    layers={'height':grid(h),'erosion':grid(cut),'deposition':grid(fill),
            'erosion_delta':grid([a-b for a,b in zip(h,original)]),'catchment':grid(flow)}
    budget={'eroded_m3':total_cut,'deposited_m3':total_fill,'stored_sediment_m3':sum(sediment),
            'balance_error_m3':total_cut-total_fill-sum(sediment),
            'method':'downhill stream-power proxy; closed depressions and submerged cells retain sediment; no lake overflow',
            'passes':passes}
    return layers,budget
