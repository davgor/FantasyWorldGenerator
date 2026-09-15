"""Seeded magical geography: opportunity and human hazard are separate fields."""
import math
import random
from time import perf_counter
from .terrain_globe import direction
from .terrain_tectonics import child_seed
from .terrain_erosion import sphere_grid
from .terrain_climate import node_grid


def dot(a,b):return sum(x*y for x,y in zip(a,b))


def arc_frame(a,b):
    cosine=max(-1,min(1,dot(a,b)));angle=math.acos(cosine)
    tangent=tuple((y-cosine*x)/max(1e-12,math.sin(angle)) for x,y in zip(a,b))
    return a,b,tangent,angle


def distance_to_frame(p,frame):
    a,b,tangent,angle=frame;pa=dot(p,a);pt=dot(p,tangent)
    along=math.atan2(pt,pa);best=max(pa,dot(p,b))
    if 0<=along<=angle:best=max(best,math.hypot(pa,pt))
    return math.acos(max(-1,min(1,best)))


def arc_distance(p,a,b):return distance_to_frame(p,arc_frame(a,b))


def college_eligible(density,hazard,limit,slope,temp,fresh,flood,suitability,water,profile=None):
    if profile is None:
        from .terrain_profiles import get_profile
        profile=get_profile('human')
    return (density>=.35 and hazard<=limit and water==0 and slope<profile['college_slope_limit'] and profile['college_temperature_min']<temp<profile['college_temperature_max']
            and 0<=fresh<=profile['college_water_reach'] and flood<profile['college_flood_limit'] and suitability>=profile['college_suitability_min'])


def add_magic(result,cfg):
    if not cfg.magic_enabled or cfg.phase<6 or not result.get('climate'):return result
    started=perf_counter();rng=random.Random(child_seed(cfg.seed,'leylines'));nodes=[]
    # Separate from settlements and plate seeds. Minimum angular spacing avoids degenerate arcs.
    for attempt in range(10000):
        if len(nodes)>=cfg.ley_nodes:break
        y=rng.uniform(-1,1);lon=rng.uniform(-math.pi,math.pi);rad=math.sqrt(1-y*y)
        p=(rad*math.cos(lon),y,rad*math.sin(lon))
        if all(-.995<dot(p,q)<.97 for q in nodes):nodes.append(p)
    if len(nodes)<cfg.ley_nodes:raise ValueError('Could not separate ley nodes; try another seed')
    # A spanning tree plus each node's second-nearest link gives a sparse connected network.
    joined={0};pairs=set()
    while len(joined)<len(nodes):
        _,a,b=min((1-dot(nodes[a],nodes[b]),a,b) for a in joined for b in range(len(nodes)) if b not in joined)
        pairs.add(tuple(sorted((a,b))));joined.add(b)
    for a in range(len(nodes)):
        nearby=sorted((1-dot(nodes[a],p),b) for b,p in enumerate(nodes) if b!=a)
        pairs.add(tuple(sorted((a,nearby[1][1]))))
    edges=[];frames=[]
    for a,b in sorted(pairs):
        edge={'from':a,'to':b,'strength':rng.uniform(.65,1.25),'instability':rng.uniform(.15,1),
              'growth_affinity':rng.choice((.1,.9))}
        frame=arc_frame(nodes[a],nodes[b]);frames.append(frame)
        edge['path']=[tuple(x*math.cos(frame[3]*k/32)+t*math.sin(frame[3]*k/32) for x,t in zip(frame[0],frame[2])) for k in range(33)]
        edges.append(edge)
    n=cfg.size;r=result['effective_config']['globe_radius'];points,_,_=sphere_grid(n,r)
    density=[];hazard=[];growth=[]
    for x,z in points:
        p=direction(x,z,n);weights=[e['strength']*math.exp(-(r*distance_to_frame(p,f)/cfg.ley_width)**2) for e,f in zip(edges,frames)]
        total=sum(weights);power=-math.expm1(-total)
        affinity=sum(w*e['growth_affinity'] for w,e in zip(weights,edges))/total if total>1e-15 else 0.
        chaos=sum(w*e['instability'] for w,e in zip(weights,edges))/total if total>1e-15 else 0.
        density.append(power);hazard.append(power*chaos*cfg.magic_instability);growth.append(affinity)
    result['layers'].update({'magic_density':node_grid(density,points,n),'magic_hazard':node_grid(hazard,points,n),
                             'magic_growth':node_grid(growth,points,n)})
    result['magic']={'version':1,'nodes':nodes,'edges':edges,'colleges':[],
        'method':'Seeded minor great-circle arcs; density sums Gaussian distance influence. Growth versus destructive affinity and instability are independent line traits. Human mutation hazard is density times weighted instability. Geography and climate are unchanged; fantasy ecology and human choices respond to the fields.'}
    result['warnings'].append(result['magic']['method'])
    elapsed=(perf_counter()-started)*1000;result['timing_ms']['leylines']=elapsed;result['timing_ms']['total']+=elapsed
    return result


def add_colleges(result,cfg):
    if not result.get('magic') or not result.get('humans'):return result
    from .terrain_profiles import get_profile
    profile=get_profile(cfg.population_profile)
    from .terrain_humans import allocate_access
    from .terrain_settlements import road_cost_function
    started=perf_counter();n=cfg.size;r=result['effective_config']['globe_radius']
    points,_,graph=sphere_grid(n,r);layers=result['layers']
    def vals(k):return [layers[k][z][x] for x,z in points]
    density=vals('magic_density');hazard=vals('magic_hazard');slope=vals('slope');temp=vals('temperature')
    fresh=vals('freshwater_distance');flood=vals('flood_risk');suitability=vals('suitability');water=vals('water_type')
    cost=road_cost_function(points,water,vals('height'),flood,vals('rain_river'),cfg,hazard)
    cities=result['settlements']['sites'];distance,owner,parent=allocate_access(graph,[(s['node'],s['id']) for s in cities],cost,cfg.support_reach)
    city_profiles=[get_profile(s['population_profile']) for s in cities]
    parent_by_city={}
    if cfg.world_recipe:
        from dataclasses import replace
        from .terrain_settlements import shortest_paths
        distance=[math.inf]*len(points);owner=[-1]*len(points)
        for city,p in zip(cities,city_profiles):
            risk=vals('magic_risk_'+p['id']) if 'magic_risk_'+p['id'] in layers else hazard
            own_cost=road_cost_function(points,water,vals('height'),flood,vals('rain_river'),replace(cfg,human_magic_limit=p['mutation_limit'],road_max_grade=p['road_grade_limit']),risk)
            own_distance,own_parent=shortest_paths(graph,city['node'],own_cost)
            parent_by_city[city['id']]=own_parent
            for i,d in enumerate(own_distance):
                if d<distance[i] and d<=cfg.support_reach:distance[i]=d;owner[i]=city['id']
        hazard=[layers.get('magic_risk_'+city_profiles[o]['id'],layers['magic_hazard'])[z][x] if o>=0 else 1. for (x,z),o in zip(points,owner)]
    suitability=[layers.get('suitability_'+cities[o]['population_profile'],layers['suitability'])[points[i][1]][points[i][0]] if o>=0 else 0 for i,o in enumerate(owner)]
    occupied=[direction(s['x'],s['z'],n) for s in cities+result['humans']['hamlets']+result['humans']['fortresses']]
    colleges=[]
    for i in sorted(range(len(points)),key=lambda i:(-(density[i]*(1-hazard[i])+.25*suitability[i]),i)):
        if len(colleges)>=cfg.college_count:break
        if owner[i]<0:continue
        profile=city_profiles[owner[i]]
        if not college_eligible(density[i],hazard[i],profile['mutation_limit'] if cfg.world_recipe else cfg.human_magic_limit,slope[i],temp[i],fresh[i],flood[i],suitability[i],water[i],profile):continue
        x,z=points[i];p=direction(x,z,n)
        if any(r*math.acos(max(-1,min(1,dot(p,q))))<150 for q in occupied):continue
        path=[i]
        own_parent=parent_by_city[owner[i]] if cfg.world_recipe else parent
        while own_parent[path[-1]]>=0:path.append(own_parent[path[-1]])
        colleges.append({'id':f'college-{len(colleges)+1}','kind':'wizard_college','node':i,'x':x,'z':z,
                         'core_id':owner[i],'population_profile':cities[owner[i]]['population_profile'],'culture_id':result['humans']['cores'][owner[i]]['culture_id'],
                         'density':density[i],'hazard':hazard[i],'suitability':suitability[i],
                         'access_nodes':path,'access_cost':distance[i],
                         'reason':'Strong magic within population mutation, slope, climate, freshwater, flood and suitability limits; reachable from a city.'})
        occupied.append(p)
    result['magic']['colleges']=colleges
    result['magic']['college_method']='Colleges share the selected population safety limit; no protective ward discount. Sites may be fewer than requested. Institutions have no separate population or supply demand yet.'
    elapsed=(perf_counter()-started)*1000;result['timing_ms']['colleges']=elapsed;result['timing_ms']['total']+=elapsed
    return result
