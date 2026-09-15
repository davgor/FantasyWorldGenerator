"""Deterministic steady-wind moisture experiment; not a weather forecast."""
import math
from time import perf_counter
from .terrain_erosion import sphere_grid
from .terrain_globe import direction


def node_grid(values,points,n):
    out=[[0.]*n for _ in range(n)]
    for (x,z),v in zip(points,values):out[z][x]=v
    out[0]=[values[0]]*n;out[-1]=[values[-1]]*n
    for row in out:row[-1]=row[0]
    return out


def transport_moisture(height,water,upstream,passes,strength):
    humidity=[0.]*len(height);rain=[0.]*len(height)
    rise=[max(0,height[i]-sum(height[j]*w for j,w in stencil)) for i,stencil in enumerate(upstream)]
    loss=[min(.85,.06+strength*v/150) for v in rise]
    residual=0.
    for _ in range(passes):
        following=[];rain=[]
        for i,stencil in enumerate(upstream):
            incoming=sum(humidity[j]*w for j,w in stencil)
            available=incoming+.45*(1-incoming) if water[i] else incoming
            rain.append(available*loss[i])
            following.append(available-rain[-1])
        residual=max(abs(a-b) for a,b in zip(following,humidity))
        humidity=following
    return {'humidity':humidity,'rain':rain,'uplift':rise,'residual':residual}


def add_climate(result,cfg):
    if not result.get('water') or cfg.phase<6:return result
    started=perf_counter();n=cfg.size;radius=result['effective_config']['globe_radius']
    points,areas,_=sphere_grid(n,radius);lookup={p:i for i,p in enumerate(points)}
    def index(x,z):return lookup[(0,z) if z in (0,n-1) else (x%(n-1),z)]
    bearing=math.radians(cfg.wind_bearing);angle=2*math.pi/(n-1)
    stencils=[];winds=[]
    for x,z in points:
        p=direction(x,z,n);lon=2*math.pi*x/(n-1)-math.pi;lat=math.pi/2-math.pi*z/(n-1)
        east=(-math.sin(lon),0,math.cos(lon));north=(-math.sin(lat)*math.cos(lon),math.cos(lat),-math.sin(lat)*math.sin(lon))
        wind=tuple(math.sin(bearing)*a+math.cos(bearing)*b for a,b in zip(east,north))
        q=tuple(v*math.cos(angle)-w*math.sin(angle) for v,w in zip(p,wind))
        xx=(math.atan2(q[2],q[0])+math.pi)/(2*math.pi)*(n-1)
        zz=max(0,min(n-1,(math.pi/2-math.asin(max(-1,min(1,q[1]))))/math.pi*(n-1)))
        ix=int(xx);iz=int(zz);fx=xx-ix;fz=zz-iz;jz=min(n-1,iz+1)
        stencils.append([(index(ix,iz),(1-fx)*(1-fz)),(index(ix+1,iz),fx*(1-fz)),
                         (index(ix,jz),(1-fx)*fz),(index(ix+1,jz),fx*fz)])
        winds.append(wind)
    height=[result['layers']['water_surface'][z][x] for x,z in points]
    water=[result['layers']['water_type'][z][x]>0 for x,z in points]
    air=transport_moisture(height,water,stencils,cfg.rain_passes,cfg.rain_strength)
    moisture=[max(0,min(1,r/(r+.025)+cfg.moisture_bias)) for r in air['rain']]
    runoff=[a*r/.04 for a,r in zip(areas,air['rain'])]
    parents=result['water']['receivers']
    # Leaf-to-root accumulation works for any acyclic receiver ordering.
    children=[0]*len(points)
    for p in parents:
        if p>=0:children[p]+=1
    queue=[i for i,k in enumerate(children) if k==0]
    for i in queue:
        p=parents[i]
        if p>=0:
            runoff[p]+=runoff[i];children[p]-=1
            if children[p]==0:queue.append(p)
    rivers=[i for i in range(len(points)) if not water[i] and parents[i]>=0 and runoff[i]>=cfg.river_threshold_km2*1e6]
    river_set=set(rivers)
    result['layers'].update({k:node_grid(v,points,n) for k,v in (
        ('air_moisture',air['humidity']),('rainfall',air['rain']),('wind_uplift',air['uplift']),
        ('climate_moisture',moisture),('rain_runoff',runoff),('rain_river',[int(i in river_set) for i in range(len(points))]))})
    arrows=[{'x':x,'z':z,'direction':direction(x,z,n),'wind':winds[i]} for i,(x,z) in enumerate(points)
            if x%max(1,(n-1)//8)==0 and z%max(1,(n-1)//6)==0 and z not in (0,n-1)]
    result['climate']={'version':1,'wind_arrows':arrows,'river_segments':[[i,parents[i]] for i in rivers],
        'residual':air['residual'],'passes':cfg.rain_passes,'transport_step_m':radius*angle,
        'runoff_input_m2_equivalent':sum(a*r/.04 for a,r in zip(areas,air['rain'])),
        'runoff_outlets_m2_equivalent':sum(v for v,p in zip(runoff,parents) if p<0),
        'method':'Fixed compass-bearing wind transports humidity from equilibrium ocean/lake surfaces. Rising air loses extra moisture as rainfall, drying the lee. Relative rainfall and runoff proxies, not mm/year or discharge. Lake volumes are not solved from this rain budget.',
        'convergence':'Fixed iteration count; residual is max humidity change on final pass. No convergence guarantee.'}
    elapsed=(perf_counter()-started)*1000;result['timing_ms']['climate']=elapsed;result['timing_ms']['total']+=elapsed
    result['warnings'].append(result['climate']['method'])
    return result
