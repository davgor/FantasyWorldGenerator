"""Seeded terrain routes and conservative rotated-plot rasterization (metres)."""
import heapq
import math
import random


def grow_roads(valid, height, size, seed, spacing_cells, required=()):
    if not valid:return set(),[]
    rng=random.Random(seed)
    root=min(valid,key=lambda c:((c[0]-size/2)**2+(c[1]-size/2)**2,c))
    # A smooth travel-cost field produces persistent bends, rather than white-noise zigzags.
    phases=[rng.uniform(-math.pi,math.pi) for _ in range(3)]
    heights={c:height(c) for c in sorted(valid)}
    costs={c:1+.45*(1+math.sin(c[0]/9+phases[0])*math.cos(c[1]/11+phases[1]))
           +.3*(1+math.sin((c[0]+c[1])/17+phases[2])) for c in sorted(valid)}
    distances={root:0};previous={};queue=[(0,root)]
    while queue:
        cost,c=heapq.heappop(queue)
        if cost!=distances[c]:continue
        x,z=c
        for dx,dz in ((-1,0),(0,-1),(0,1),(1,0),(-1,-1),(-1,1),(1,-1),(1,1)):
            q=(x+dx,z+dz)
            if q not in valid:continue
            if dx and dz and ((x+dx,z) not in valid or (x,z+dz) not in valid):continue
            if dx and dz and any(abs(heights[r]-heights[end])>1.4
                                  for r in ((x+dx,z),(x,z+dz)) for end in (c,q)):continue
            length=math.hypot(dx,dz)*4
            grade=abs(heights[q]-heights[c])/length
            if grade>.35:continue
            new=cost+length*((costs[c]+costs[q])/2+18*grade*grade)
            if new<distances.get(q,float('inf')):
                distances[q]=new;previous[q]=c;heapq.heappush(queue,(new,q))
    reachable=sorted(distances)
    # Destinations represent gates and growing districts, never an imposed street grid.
    targets=sorted(set(required)&set(distances))
    count=max(12,min(36,round(len(valid)/max(12,spacing_cells)**2*1.5)))
    candidates=rng.sample(reachable,min(len(reachable),max(256,count*20)))
    for _ in range(count):
        if not candidates:break
        target=max(candidates,key=lambda c:(min((c[0]-q[0])**2+(c[1]-q[1])**2 for q in [root]+targets),c))
        targets.append(target);candidates.remove(target)
    network={root};paths=[]
    for target in targets:
        path=[target]
        while path[-1] not in network:path.append(previous[path[-1]])
        if len(path)>1:paths.append(list(reversed(path)));network.update(path)
    roads=set(network)
    for x,z in sorted(network):
        for dx,dz in ((1,0),(-1,0),(0,1),(0,-1)):
            q=(x+dx,z+dz)
            if q in distances and abs(heights[q]-heights[(x,z)])<=1.4:roads.add(q)
    # Diagonal centerline steps have orthogonal safe support cells (no corner cutting).
    return roads,paths


def corners(x,z,w,d,angle):
    c=math.cos(angle);s=math.sin(angle)
    return [(x+u*c-v*s,z+u*s+v*c) for u,v in ((-w/2,-d/2),(w/2,-d/2),(w/2,d/2),(-w/2,d/2))]


def footprint_cells(x,z,w,d,angle,half,cell=4):
    points=corners(x,z,w,d,angle);c=math.cos(angle);s=math.sin(angle)
    lo=[math.floor((min(p[k] for p in points)+half)/cell) for k in (0,1)]
    hi=[math.floor((max(p[k] for p in points)+half)/cell) for k in (0,1)]
    cells=set();r=cell/2*(abs(c)+abs(s))
    for j in range(lo[1],hi[1]+1):
        for i in range(lo[0],hi[0]+1):
            dx=-half+(i+.5)*cell-x;dz=-half+(j+.5)*cell-z
            if abs(dx*c+dz*s)<w/2+r-1e-8 and abs(-dx*s+dz*c)<d/2+r-1e-8:
                cells.add((i,j))
    return cells
