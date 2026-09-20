"""Artistic layered habitats on the spherical grid; quantities are explicit proxies."""
import math
import random
from dataclasses import replace
from .terrain_world import options, NETWORKS, ZONES
from .terrain_tectonics import child_seed
from .terrain_globe import direction, perlin3
from .terrain_erosion import sphere_grid
from .terrain_climate import node_grid


def clamp(v):return max(0.,min(1.,v))
def dot(a,b):return sum(x*y for x,y in zip(a,b))
def angle(a,b):return math.acos(max(-1.,min(1.,dot(a,b))))
def random_point(rng):
    y=rng.uniform(-1,1);lon=rng.uniform(-math.pi,math.pi);c=math.sqrt(1-y*y)
    return (c*math.cos(lon),y,c*math.sin(lon))


def island_layout(cfg):
    o=options(cfg);rng=random.Random(child_seed(cfg.seed,'ocean-archipelagos-v1'));clusters=[]
    for k in range(o['archipelago_count']):
        center=random_point(rng);kind=rng.choices(('volcanic','atoll','continental','cold'),
            weights=[o[k] for k in ('volcanic_island_weight','atoll_weight','continental_island_weight','cold_island_weight')])[0]
        if kind=='cold':
            center=(center[0]*.4,math.copysign(.9,center[1]),center[2]*.4)
            norm=math.sqrt(dot(center,center));center=tuple(v/norm for v in center)
        if rng.random()>o['archipelago_occurrence']:continue
        islands=[]
        for j in range(o['islands_per_cluster']):
            q=random_point(rng);scale=o['island_radius']*o['island_spacing']*o['archipelago_extent']*math.sqrt(j)
            p=tuple(a+scale*b for a,b in zip(center,q));norm=math.sqrt(dot(p,p));p=tuple(v/norm for v in p)
            islands.append({'direction':p,'angular_radius':o['island_radius']*rng.uniform(.7,1.3)})
        clusters.append({'id':f'ocean-{k}','kind':kind,'direction':center,'islands':islands})
    return clusters


def shape_islands(layers,cfg):
    """Compact ocean uplifts before erosion and drainage; retain continental foundations."""
    clusters=island_layout(cfg);n=cfg.size
    layers['archipelago_relief']=[[0.]*n for _ in range(n)]
    for cluster in clusters:
        p=cluster['direction'];x=round((math.atan2(p[2],p[0])+math.pi)/(2*math.pi)*(n-1));z=round(math.acos(p[1])/math.pi*(n-1))
        cluster['eligible']=layers['continental'][z][x]<cfg.sea_level
    for z in range(n):
        for x in range(1 if z in (0,n-1) else n-1):
            p=direction(x,z,n);original=layers['structure'][z][x];value=original
            for cluster in clusters:
                if not cluster['eligible']:continue
                for island in cluster['islands']:
                    d=angle(p,island['direction'])/island['angular_radius']
                    if d>=2:continue
                    support=clamp((2-d)/.7)
                    if cluster['kind']=='atoll':target=cfg.sea_level+cfg.tectonic_relief*(.22*math.exp(-((d-.7)/.24)**2)-.07)
                    else:target=cfg.sea_level+cfg.tectonic_relief*((.9 if cluster['kind']=='volcanic' else .45)*math.exp(-d*d*2)-.1)
                    value=max(value,original+(target-original)*support)
            delta=value-original
            layers['archipelago_relief'][z][x]=delta
            for key in ('structure','height','base'):layers[key][z][x]+=delta
        for key in ('structure','height','base','archipelago_relief'):
            if z in (0,n-1):layers[key][z]=[layers[key][z][0]]*n
            else:layers[key][z][-1]=layers[key][z][0]
    return clusters


def monthly_temperatures(mean,latitude,wet,seasonality=1.):
    amplitude=20*math.sin(math.radians(latitude))*(1-.4*wet)*seasonality
    return [mean+amplitude*math.cos(2*math.pi*(month-6)/12) for month in range(12)]


def cold_habitat(temps,wet,accumulation):
    if max(temps)<1 and wet>=accumulation*.4:return 'ice_cap'
    if max(temps)<10:return 'tundra'
    if sum(t>5 for t in temps)<=6:return 'boreal' if wet>=.4 else 'tundra'
    return None


def add_environment(result,cfg):
    if cfg.phase<6 or not result.get('climate'):return
    from .terrain_humans import allocate_access
    o=options(cfg);l=result['layers'];n=cfg.size;r=result['effective_config']['globe_radius']
    points,areas,graph=sphere_grid(n,r);vectors=[direction(x,z,n) for x,z in points]
    def vals(k):return [l[k][z][x] for x,z in points]
    water=vals('water_type');temp=vals('temperature');wet=vals('moisture');slope=vals('slope');depth=vals('water_depth')
    river=vals('rain_river');height=vals('height')
    ocean=[(i,0) for i,w in enumerate(water) if w==1]
    distance,_,_=allocate_access(graph,ocean,lambda i,j,d:d)
    fields={k:[] for k in ('metal_richness','salinity','coastal_exposure','harbor_suitability','fishing_productivity',
                           'reef','lagoon','estuary','sheltered_bay','rocky_coast','kelp','fjord','open_ocean',
                           'maritime','boreal','tundra','ice_cap','coastal_support')}
    months=[{'temperature':[],'snow':[],'water_ice':[]} for _ in range(12)]
    for i,(x,z) in enumerate(points):
        p=vectors[i];near=[j for j,d in graph[i]];adj=sum(water[j]==1 for j in near)/max(1,len(near))
        coast=not water[i] and distance[i]<=max(result['spacing_m'],120)
        exposure=clamp(adj if coast else sum(water[j]>0 for j in near)/max(1,len(near)))
        shallow=clamp(1-depth[i]/80) if water[i] else 0.
        salt=1. if water[i]==1 else clamp((.6-wet[i])*2*o['salinity']) if water[i]==2 else 0.
        reef=shallow*clamp((temp[i]-15)/12)*(1-.5*exposure) if water[i]==1 else 0.
        lagoon=shallow*(1-exposure) if water[i]==1 else 0.
        estuary=float(water[i]==1 and any(river[j] and not water[j] for j in near))
        kelp=shallow*clamp(1-abs(temp[i]-10)/15) if water[i]==1 else 0.
        fjord=float(water[i]==1)*clamp(sum(slope[j]>12 and not water[j] for j in near)/3)*clamp((15-temp[i])/15)
        harbor=clamp((1-exposure)*.7+.3)*math.exp(-slope[i]/22) if coast and any(water[j]==1 and depth[j]>=o['sea_draft'] for j in near) else 0.
        fish=clamp(.12+.55*shallow+.3*estuary+.2*kelp+.15*reef) if water[i] else 0.
        temps=monthly_temperatures(temp[i],90-180*z/(n-1),wet[i],o['seasonality'])
        cold=cold_habitat(temps,wet[i],o['ice_accumulation']) if not water[i] else None
        if cold:l['biome'][z][x]={'boreal':15,'tundra':16,'ice_cap':17}[cold]
        metal=clamp((.45+.7*perlin3(*(v*5 for v in p),child_seed(cfg.seed,'metals-v1'))+.2*l['volcanic'][z][x])*o['metal_abundance'])
        values=(metal,salt,exposure,harbor,fish,reef,lagoon,estuary,harbor,float(coast)*exposure*clamp(slope[i]/25),kelp,fjord,
                float(water[i]==1)*(1-shallow),math.exp(-distance[i]/300) if not water[i] else 0.,
                float(cold=='boreal'),float(cold=='tundra'),float(cold=='ice_cap'),harbor*.5)
        for key,value in zip(fields,values):fields[key].append(value)
        for m,t in enumerate(temps):
            months[m]['temperature'].append(t)
            months[m]['snow'].append(clamp(-t/8)*clamp(wet[i]*2) if not water[i] else 0.)
            months[m]['water_ice'].append(clamp((-1.8*salt-t)/6) if water[i] else 0.)
    # Nearby coastal support is opportunity, never credited as harvested food.
    for i in range(len(points)):
        if not water[i]:fields['coastal_support'][i]=fields['harbor_suitability'][i]*.5+.5*max((fields['fishing_productivity'][j] for j,d in graph[i]),default=0.)
    for key,values in fields.items():l[key]=node_grid(values,points,n)
    unvisited={i for i,w in enumerate(water) if not w};islandness=[0.]*len(points)
    land_total=sum(a for a,w in zip(areas,water) if not w)
    while unvisited:
        start=min(unvisited);unvisited.remove(start);component=[start];stack=[start]
        while stack:
            i=stack.pop()
            for j,d in graph[i]:
                if j in unvisited:unvisited.remove(j);component.append(j);stack.append(j)
        component_area=sum(areas[i] for i in component)
        # A component is an island when it is small RELATIVE TO THIS WORLD'S LAND. The
        # dropped min(3e6,...) arm was 3 km2 in absolute metres, authored for the 11.15 km
        # reference world where every raster cell is under 0.25 km2. At the 200 km default
        # the smallest sphere-grid cell is 15.217 km2 at size 17, so at THE DEFAULT RASTER
        # no component of any seed can reach the floor and island_habitat is identically
        # zero -- a published layer that had become a constant.
        #
        # Scoped to size 17 deliberately: an earlier revision of this comment claimed the
        # layer was zero at EVERY raster and that is false. Cells shrink to 1.914 km2 at
        # size 33 and 0.240 km2 at size 65, so a one-cell polar component can clear the
        # 3 km2 floor. Measured at phase 12 on the 200 km default: under the old arm seed
        # 40 reads 1 island cell at size 33 and 6 at size 65 and seed 43 reads 1 at size
        # 65, against 29 / 167 / 166 under the fraction arm. Zero at the default raster,
        # all but zero above it -- not a mathematical constant there.
        #
        # The fraction arm is the one that bound on every world on disk (the 3e6
        # arm never bound at any raster there), so dropping the metre arm reproduces all
        # twelve archived worlds cell-for-cell while restoring the layer at 200 km.
        for i in component:islandness[i]=float(component_area<land_total*.15)
    l['island_habitat']=node_grid(islandness,points,n)
    # Return categorical edits to the duplicate seam and unique poles.
    for z in range(n):
        if z in (0,n-1):l['biome'][z]=[l['biome'][z][0]]*n
        else:l['biome'][z][-1]=l['biome'][z][0]
    l['natural_biome']=[row[:] for row in l['biome']]
    result['seasonal_environment']={'months':[{k:node_grid(v,points,n) for k,v in m.items()} for m in months],
                                    'method':'Monthly latitude/elevation temperature proxy; snow and water ice do not modify bedrock.'}
    def magic(name,i):
        x,z=points[i];return l.get('ley_'+name,[[0.]])[z][x] if 'ley_'+name in l else 0.
    eligibility={name:[] for name in ZONES}
    for i,(x,z) in enumerate(points):
        dry=1-float(bool(water[i]));arid=clamp((.5-wet[i])*3);mountain=clamp(max(0,height[i])/100)*clamp(slope[i]/20)
        v={'demonic':dry*magic('infernal',i),'draconic':dry*mountain*max(magic('primordial',i),magic('weave',i)),
           'pirate':fields['harbor_suitability'][i], 'steampunk':dry*fields['metal_richness'][i]*max(fields['maritime'][i],l['volcanic'][z][x],.2),
           'witch_huts':dry*magic('umbral',i)*(1-fields['coastal_support'][i]),'red_sands':dry*arid,
           'dead_sea':float(water[i]==2)*fields['salinity'][i],
           'starlight_lakes':float(water[i]==2)*max(magic('weave',i),magic('holy',i)),
           'haunted_sands':dry*arid*magic('umbral',i),'enchanted':dry*wet[i]*magic('weave',i),
           'fungal':dry*wet[i]*magic('primordial',i),'crystal':dry*arid*magic('primordial',i),
           'haunted_marsh':dry*wet[i]*math.exp(-slope[i]/6)*magic('umbral',i)}
        for name in ZONES:eligibility[name].append(v[name])
    regions=[];landmarks=[]
    for name,scores in eligibility.items():
        rng=random.Random(child_seed(cfg.seed,'region-'+name+'-v1'));candidates=[i for i,v in enumerate(scores) if v>.04]
        active=candidates and rng.random()<o[name+'_occurrence'];centers=[]
        if active:
            ranked=sorted(candidates,key=lambda i:-(scores[i]*(.6+.4*rng.random())))
            for i in ranked:
                if all(angle(vectors[i],vectors[j])>o[name+'_extent']*1.5 for j in centers):centers.append(i)
                if len(centers)>=3:break
        values=[o[name+'_intensity']*scores[i]*max((math.exp(-(angle(vectors[i],vectors[j])/o[name+'_extent'])**2) for j in centers),default=0.) for i in range(len(points))]
        l['zone_'+name]=node_grid(values,points,n)
        regions.append({'id':name,'centers':centers,'maximum':max(values,default=0.),'area_km2':sum(a for a,v in zip(areas,values) if v>.05)/1e6,
                        'reason':'manifested' if centers else 'insufficient suitable habitat' if not candidates else 'not selected by occurrence seed'})
        if name in ('witch_huts','haunted_sands'):
            for i in centers:
                x,z=points[i];landmarks.append({'id':f'{name}-{i}','kind':'witch_hut' if name=='witch_huts' else 'necropolis','x':x,'z':z,'layer':'surface','intensity':values[i]})
    result['regions']={'influences':regions,'landmarks':landmarks,'method':'Independent overlapping fields; low suitability can be valuable to specialist sites.'}
    result['habitats']={'version':1,'aquatic':['reef','lagoon','estuary','sheltered_bay','rocky_coast','kelp','fjord','open_ocean'],
                        'method':'Depth, coast exposure, salinity and climate proxies; no tides, currents or biological reef simulation.'}
