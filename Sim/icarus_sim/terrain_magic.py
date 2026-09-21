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


# The eight limits a cell must clear to host a college, in the order they are tested.
# Declared once so the diagnostic names them out of the gate's own list rather than out
# of a second copy of it.
COLLEGE_LIMITS=('density','hazard','water','slope','temperature','freshwater','flood','suitability')
# What the college pass walks, in words. Cells a city cannot reach are never looked at,
# so a report that counted the whole grid would describe work that never happened.
SOURCE_KIND="cells within a city's support reach"


def college_refusal(density,hazard,limit,slope,temp,fresh,flood,suitability,water,profile=None):
    """Which of COLLEGE_LIMITS refuses this cell a college, or None if none does.

    This is the definition of college eligibility; `college_eligible` is this predicate
    read as a boolean. The diagnostic needs to say which limit refused, and a second copy
    of the gate written for the report is how a report starts disagreeing with the thing
    it reports on. The clause order is the original `and` chain's short-circuit order, so
    'the limit that refused' means the same thing it always did.
    """
    if profile is None:
        from .terrain_profiles import get_profile
        from .civilization_registry import default_profile_id
        profile=get_profile(default_profile_id())
    if not density>=.35:return 'density'
    if not hazard<=limit:return 'hazard'
    if not water==0:return 'water'
    if not slope<profile['college_slope_limit']:return 'slope'
    if not profile['college_temperature_min']<temp<profile['college_temperature_max']:return 'temperature'
    if not 0<=fresh<=profile['college_water_reach']:return 'freshwater'
    if not flood<profile['college_flood_limit']:return 'flood'
    if not suitability>=profile['college_suitability_min']:return 'suitability'
    return None


def college_eligible(density,hazard,limit,slope,temp,fresh,flood,suitability,water,profile=None):
    return college_refusal(density,hazard,limit,slope,temp,fresh,flood,suitability,water,profile) is None


def _row(placed,wanted,candidates,sources,reason):
    return {'institution':'wizard_college','placed':placed,'wanted':wanted,'candidates':candidates,
            'sources':sources,'source_kind':SOURCE_KIND,'reason':reason}


def pending_college_diagnostics(wanted):
    """The row a `magic` block carries before the college pass has run.

    generate_networks writes `colleges: []` and the pass fills it later, so between the
    two the empty list means "not yet", not "none placed". Those read alike in a finished
    document if only one of them says anything.
    """
    return [_row(0,int(wanted),0,0,'the college pass has not run at this phase, so nothing was evaluated')]


def college_diagnostics(placed,wanted,candidates,sources,refusals,clearance,spacing):
    """One row per institution: whether it placed, what was evaluated, and why none did.

    The shape `key_locations` publishes per archetype and `heroes` per role, in the block
    that owns the institutions. `candidates` counts every cell that cleared all eight
    limits, including cells the budget never reached, so `placed == candidates` means the
    world ran out of ground and `placed < candidates` means the budget or the spacing
    stopped it -- which are different facts and used to be the same zero.
    """
    if wanted<=0:
        reason='no colleges were requested'
    elif placed>=wanted:
        reason=f'{placed} of {candidates} candidates were seated, which is every college asked for'
    elif placed:
        reason=(f'{placed} of {wanted} colleges were seated from {candidates} candidates; '
                f'settlement clearance refused {clearance} and regional spacing refused {spacing}')
    elif candidates:
        reason=(f'no room: settlement clearance refused {clearance} of {candidates} candidates '
                f'and regional spacing refused {spacing}')
    elif sources:
        # Deterministic tie-break: the most refusals, then the earliest limit tested.
        worst=max((refusals.get(k,0),-i,k) for i,k in enumerate(COLLEGE_LIMITS))
        reason=(f'{sources} {SOURCE_KIND} were read and none produced a candidate; '
                f'{worst[2]} refused the most, at {worst[0]}')
    else:
        reason=f'no {SOURCE_KIND} in this world, so nothing rolled'
    return [_row(placed,wanted,candidates,sources,reason)]


def add_magic(result,cfg):
    # Dead writer. Imported by terrain_leyline_history and called from nowhere: no call
    # site, no string dispatch, no non-Python caller. generate_networks is the sole
    # writer of result['magic'] and emits version 4.
    #
    # Do not connect this. It does not merge, it REPLACES the whole block with a
    # version-1 body that has no school_order and no twelve-school contract, so
    # whichever of the two ran second would silently discard the other's block
    # entirely. Delete it or leave it; wiring it back in is the one move that breaks
    # worlds, and it is the move a tidiness pass makes because an imported-unused
    # symbol reads like an oversight. See docs/conformance/version-bindings.json and
    # board/backlog/MAGIC-ADD-MAGIC-DEAD-WRITER.md.
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


def college_spacing_m(radius):
    return max(1500.,radius*.15)


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
    colleges=[];college_points=[]
    spacing=college_spacing_m(r) if cfg.world_recipe==3 else 150
    # Counted for the diagnostic, never read by placement. The budget check moved below
    # the limits so a cell the budget never reached is still counted as a candidate:
    # placement is unchanged by that -- the checks above it have no side effects and a
    # `continue` past the placement body leaves colleges, occupied and college_points
    # exactly as the old `break` did.
    candidates=0;refusals={};refused_clearance=0;refused_spacing=0
    sources=sum(1 for o in owner if o>=0)
    for i in sorted(range(len(points)),key=lambda i:(-(density[i]*(1-hazard[i])+.25*suitability[i]),i)):
        if owner[i]<0:continue
        profile=city_profiles[owner[i]]
        refusal=college_refusal(density[i],hazard[i],profile['mutation_limit'] if cfg.world_recipe else cfg.human_magic_limit,slope[i],temp[i],fresh[i],flood[i],suitability[i],water[i],profile)
        if refusal is not None:refusals[refusal]=refusals.get(refusal,0)+1;continue
        candidates+=1
        if len(colleges)>=cfg.college_count:continue
        x,z=points[i];p=direction(x,z,n)
        if any(r*math.acos(max(-1,min(1,dot(p,q))))<150 for q in occupied):refused_clearance+=1;continue
        if any(r*math.acos(max(-1,min(1,dot(p,q))))<spacing for q in college_points):refused_spacing+=1;continue
        path=[i]
        own_parent=parent_by_city[owner[i]] if cfg.world_recipe else parent
        while own_parent[path[-1]]>=0:path.append(own_parent[path[-1]])
        colleges.append({'id':f'college-{len(colleges)+1}','kind':'wizard_college','node':i,'x':x,'z':z,
                         'core_id':owner[i],'population_profile':cities[owner[i]]['population_profile'],'culture_id':result['humans']['cores'][owner[i]]['culture_id'],
                         'density':density[i],'hazard':hazard[i],'suitability':suitability[i],
                         'access_nodes':path,'access_cost':distance[i],
                         'reason':'Strong magic within population mutation, slope, climate, freshwater, flood and suitability limits; reachable from a city.'})
        occupied.append(p);college_points.append(p)
    result['magic']['colleges']=colleges
    result['magic']['diagnostics']=college_diagnostics(len(colleges),cfg.college_count,candidates,sources,refusals,refused_clearance,refused_spacing)
    result['magic']['college_spacing_m']=spacing
    result['magic']['college_method']='Colleges share the selected population safety limit; no protective ward discount. Sites may be fewer than requested, and magic.diagnostics says per institution how many were asked for, how many cells were within a city\'s support reach, how many of those cleared every limit, and what refused the rest. Institutions have no separate population or supply demand yet.'
    elapsed=(perf_counter()-started)*1000;result['timing_ms']['colleges']=elapsed;result['timing_ms']['total']+=elapsed
    return result
