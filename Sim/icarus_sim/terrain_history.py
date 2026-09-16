"""Version 3 staged world history. Artistic deep-time and civilization proxies."""
import copy
import math
import json
import random
from time import perf_counter
from dataclasses import asdict, replace
from .terrain_tectonics import child_seed
from .terrain_leyline_history import SCHOOLS, generate_networks, evaluate_networks, edit_network, dominant_school

STAGES = ['Plate layout', 'Tectonic relief', 'Surface detail', 'Erosion and sediment',
          'Connected water', 'Second tectonic relief', 'Valleys and gorges', 'Wind and rain',
          'Leylines', 'Founding', 'Roads', 'Populated regions', 'Beasties and animals',
          'Age transition 1', 'Age transition 2', 'Simulation complete']
from .terrain_biome_catalogue import NATURAL_BIOMES, biome_catalogue, natural_catalogue


def add_biome_variants(result, cfg):
    l=result['layers']; catalogue=biome_catalogue(); index={e['id']:i for i,e in enumerate(catalogue)}
    l['biome_variant']=[[index[NATURAL_BIOMES[l['natural_biome'][z][x]]+'.'+school]
                         if (school:=dominant_school({s:l['ley_'+s][z][x] for s in SCHOOLS})) else -1
                         for x in range(cfg.size)] for z in range(cfg.size)]
    result['terrain']['version']=6
    result['terrain']['natural_biomes']=natural_catalogue()
    result['terrain']['biomes']=natural_catalogue()
    result['terrain']['magical_biomes']=catalogue
    result['terrain']['biome_contract']='biome and natural_biome are natural catalogue IDs, never array offsets; biome_variant is a magical catalogue index or -1. Food and habitat rules use the natural core and explicit variant ID with independent school risk.'
    l['biome']=copy.deepcopy(l['natural_biome'])



def refresh_environment(result,cfg):
    from .terrain_biomes import add_terrain_labels
    from .terrain_ecology import add_environment
    density=result['layers'].pop('magic_density',None)
    add_terrain_labels(result,replace(cfg,phase=6))
    if density is not None:result['layers']['magic_density']=density
    add_environment(result,replace(cfg,phase=6))
    result['layers']['natural_biome']=copy.deepcopy(result['layers']['biome'])

def abandoned_waterways(old, new):
    gorges=[[int(bool(r) and not new['river'][z][x] and new['water_type'][z][x]==0)
             for x,r in enumerate(row)] for z,row in enumerate(old['river'])]
    valleys=[[int(bool(w) and new['water_type'][z][x]==0)
              for x,w in enumerate(row)] for z,row in enumerate(old['water_type'])]
    return gorges,valleys


def measure_surface(result,cfg):
    from .terrain_globe import measure_globe
    from .terrain_area import land_area
    l=result['layers'];physical=result['effective_config']
    l['slope'],l['tpi']=measure_globe(l['height'],physical['globe_radius'],physical['radius'])
    l['land']=[[int(h>physical['sea_level']) for h in row] for row in l['height']]
    result['area']=land_area(l['height'],physical['globe_radius'],physical['sea_level'])


def tectonic_transition(result,cfg):
    from .terrain_tectonics import layout_point, unit, cross, dot
    from .terrain_globe import direction, sample
    from .terrain_water import add_water
    # Rotate each existing plate and backtrace its crust along its own angular velocity.
    plates=copy.deepcopy(result['phases']['plates']); original=copy.deepcopy(plates)
    duration=.65
    def rotate(p,omega,t):
        speed=math.sqrt(dot(omega,omega));axis=unit(omega);angle=speed*t
        c=math.cos(angle);s=math.sin(angle);crossed=cross(axis,p);along=dot(axis,p)
        return tuple(p[i]*c+crossed[i]*s+axis[i]*along*(1-c) for i in range(3))
    for plate in plates:plate['center']=rotate(plate['center'],plate['omega'],duration)
    l=result['layers'];old=copy.deepcopy({k:l[k] for k in ('height','river','water_type','water_depth')})
    fields={k:[] for k in ('height','second_uplift','moved_plates','second_convergence','second_divergence')}
    crust_seed=result['phases']['seeds']['crust'];scale=cfg.world_scale
    for z in range(cfg.size):
        rows={k:[] for k in fields}
        for x in range(1 if z in (0,cfg.size-1) else cfg.size-1):
            p=direction(x,z,cfg.size);record=layout_point(p,plates,crust_seed,cfg)
            owner=record[0];back=rotate(p,plates[owner]['omega'],-duration)
            transported=sample(old['height'],back)
            uplift=scale*cfg.tectonic_relief*(.9*record[3]-.7*record[4]+.18*record[5])
            height=.25*old['height'][z][x]+.75*transported+uplift
            for key,value in zip(fields,(height,height-old['height'][z][x],owner,record[3],record[4])):rows[key].append(value)
        for key,row in rows.items():fields[key].append(row*cfg.size if z in (0,cfg.size-1) else row+[row[0]])
    l.update(fields);l['pre_tectonic_height']=old['height'];l['old_river']=old['river'];l['old_water_type']=old['water_type']
    result['geological_history']={'version':1,'elapsed_million_years':50,'angular_duration':duration,
        'plates_before':original,'plates_after':plates,
        'method':'50-million-year artistic epoch: rotate original plate centers, backtrace crust, blend transported relief and new boundary uplift. Angular speeds are dimensionless, not calibrated geodynamics.'}
    measure_surface(result,cfg);add_water(result,replace(cfg,phase=5))
    return old


def carve_relics(result,cfg,old):
    from .terrain_water import add_water
    from .terrain_erosion import sphere_grid
    from .terrain_climate import node_grid
    l=result['layers'];gorges,valleys=abandoned_waterways(old,l)
    points,_,graph=sphere_grid(cfg.size,result['effective_config']['globe_radius'])
    cuts=[min(45.,max(4.,cfg.tectonic_relief*cfg.world_scale*.12)) if gorges[z][x] else
          min(100.,max(12.,old['water_depth'][z][x]*.6)) if valleys[z][x] else 0. for x,z in points]
    # Small shoulders make former river beds visible as terrain, not just marker pixels.
    cuts=[max(cuts[i],max((cuts[j]*.25 for j,_ in graph[i]),default=0.)) for i in range(len(points))]
    l['relic_incision']=node_grid(cuts,points,cfg.size)
    l['height']=[[h-l['relic_incision'][z][x] for x,h in enumerate(row)] for z,row in enumerate(l['height'])]
    measure_surface(result,cfg);add_water(result,replace(cfg,phase=5))
    # Refilled cuts are historical features; only still-dry abandoned beds are current gorges/valleys.
    l['gorge'],l['dry_valley']=abandoned_waterways(old,l)
    l['relic_gorge']=gorges;l['relic_valley']=valleys
    result['geological_history']['relic_method']='Compare old and rerouted river occupancy and dry former water footprints. Incise beds/shoulders, then reroute again; refilled features retain relic provenance.'


def city_fate(city,layers,nests,radius,seed,age,roll=None,magic_enabled=True):
    p={name:layers['ley_'+name][city['z']][city['x']] for name in SCHOOLS}
    causes=[]
    descriptions={'weave':'An arcane surge tore the city apart.', 'umbral':'Necrotic entropy extinguished the city.',
                  'infernal':'Infernal corruption and demonic incursions drove its people away.',
                  'radiant':'An overwhelming radiant surge forced the city to be abandoned.',
                  'fire':'A fire leyline engulfed the city in flames.', 'water':'A water leyline drowned or froze the city.',
                  'earth':'An earth leyline let roots and stone reclaim the city.',
                  'air':'An air leyline shattered the city with storms and force.'}
    winner=dominant_school(p)
    if winner:causes.append((winner,min(.6,p[winner]*.45),descriptions[winner],{'school':winner,'potency':p[winner]}))
    for nest in sorted(nests,key=lambda n:n['id']):
        if nest.get('layer','surface')!='surface' or nest.get('real',True):continue
        dragon='dragon' in nest.get('name','').lower()
        dangerous=dragon or nest.get('family') in ('infernal','undead','aberrant')
        if not dangerous:continue
        distance=radius*math.acos(max(-1.,min(1.,sum(a*b for a,b in zip(city['direction'],nest['direction'])))))
        reach=min(radius*.5,max(350.,nest.get('spacing_m',350.)*2))
        if distance>reach:continue
        causes.append(('dragon' if dragon else 'monster',.55*(1-distance/reach),
                       nest['name']+' drove the inhabitants away.',{'nest_id':nest['id'],'distance_m':distance,'reach_m':reach}))
    if magic_enabled:causes.append(('self_magic',.035+.06*p['weave'],'The city destroyed itself in a magical experiment, leaving a new Weave key point.',{}))
    chance=min(.9,sum(c[1] for c in causes))
    rng=random.Random(child_seed(seed,'city-fate-'+city['uid'],age))
    draw=rng.random() if roll is None else roll
    if draw>=chance or not causes:return None
    selector=(draw/chance)*sum(c[1] for c in causes)
    chosen=causes[-1]
    for cause in causes:
        selector-=cause[1]
        if selector<=0:chosen=cause;break
    return dict(cause=chosen[0],reason=chosen[2],evidence=chosen[3],probability=chance,roll=draw,
                new_node_school='weave' if chosen[0]=='self_magic' else None)


def remember_cities(result,age):
    cores={c['site_id']:c for c in result.get('humans',{}).get('cores',[])}
    for city in result.get('settlements',{}).get('sites',[]):
        if 'uid' not in city and age>0:city['name']+=f' (Age {age})'
        city.setdefault('uid',f"surface-city-{age}-{city['node']}-{city['population_profile']}")
        city.setdefault('founded_age',age)
        if city['founded_age']==age and city['id'] in cores:
            city['source_culture']=cores[city['id']]['culture_id']
        city.setdefault('source_culture',city['population_profile']+'-founders-'+str(city['node']))


def civilization(result,cfg,phase=9):
    from .terrain_settlements import add_settlements
    from .terrain_humans import add_humans
    from .terrain_magic import add_colleges
    from .terrain_seasons import add_seasonal_food
    from .terrain_society import add_world_society
    c=replace(cfg,phase=phase)
    add_settlements(result,c)
    if phase>=9:
        add_humans(result,c);add_colleges(result,c);add_seasonal_food(result,c);add_world_society(result,c)
    remember_cities(result,result.get('_age',0))


def age_transition(result,cfg,age):
    from .terrain_nests import add_nests
    add_nests(result,replace(cfg,phase=9))
    result['beast_nests']['evaluated_age']=age-1
    cities=copy.deepcopy(result['settlements']['sites'])
    ruins=result.setdefault('ruins',[]);events=[];survivors=[]
    radius=result['effective_config']['globe_radius']
    for city in cities:
        fate=city_fate(city,result['layers'],result.get('beast_nests',{}).get('sites',[]),radius,cfg.seed,age,
                       magic_enabled=bool(cfg.magic_enabled))
        if not fate:survivors.append(city);continue
        ruin={k:copy.deepcopy(city[k]) for k in ('uid','name','node','x','z','direction','height_m','population_profile','civilization_id','city_class','source_culture','founded_age')}
        ruin.update(id='ruin-'+city['uid'],kind='ruins',destroyed_age=age,asset_id='marker.city_ruins',**fate)
        ruins.append(ruin);events.append(copy.deepcopy(ruin))
    # Death decisions all use the pre-transition fields. Only then evolve the ley inputs.
    if cfg.magic_enabled:
        for name,net in result['magic']['networks'].items():
            rng=random.Random(child_seed(cfg.seed,'age-ley-'+name,age))
            for item in net['nodes']+net['edges']:item['intensity']=min(4.,item['intensity']*rng.uniform(.65,1.35))
        for ruin in events:
            if ruin['new_node_school']:
                name=ruin['new_node_school'];net=result['magic']['networks'][name]
                result['magic']['networks'][name]=edit_network(net,new_node={'id':ruin['id']+'-key',
                    'direction':ruin['direction'],'intensity':2.5})
        evaluate_networks(result,cfg)
    refresh_environment(result,cfg)
    add_biome_variants(result,cfg)
    result['_survivors']=survivors;result['_age']=age
    # All dependent institutions/roads/food are rebuilt from active cities, so no dead-city hamlets survive.
    civilization(result,cfg)
    result.pop('_survivors',None);result.pop('_age',None)
    add_nests(result,replace(cfg,phase=9))
    result['beast_nests']['evaluated_age']=age
    old_ids={s['uid'] for s in survivors}
    new=[s['uid'] for s in result['settlements']['sites'] if s['uid'] not in old_ids]
    result['history']['ages'].append({'age':age,'events':events,'surviving_city_ids':sorted(old_ids),
                                    'new_city_ids':new,'order':['nests before fates','city fates','ruins and hamlet removal','leyline update','biomes','civilization','nests']})


STATE_KEYS=('city_plans','civilizations','history','ocean_archipelagos','sediment_budget','terrain','water','climate','magic','settlements','roads','humans','sky','beast_nests','ruins',
            'habitats','regions','seasonal_environment','population_budget','peoples','population',
            'population_profiles','seasonal_food','fisheries','transport','world_economy','geological_history','area')


def materialize_stage(world,stage):
    if not 1<=stage<=len(world['build_stages']):raise ValueError('Stage was not generated')
    out={k:v for k,v in world.items() if k not in STATE_KEYS and k not in ('layers','build_stages')}
    out['layers']={}
    for entry in world['build_stages'][:stage]:
        out['layers'].update(entry['layers'])
        for key in entry['removed_layers']:out['layers'].pop(key,None)
        for key,value in entry['state'].items():
            if value is None:out.pop(key,None)
            else:out[key]=value
    return out


def generate_history(cfg):
    from .terrain_lab import generate_base
    from .terrain_world import registry,options
    from .terrain_water import add_water
    from .terrain_climate import add_climate
    from .terrain_biomes import add_terrain_labels
    from .terrain_ecology import add_environment
    from .terrain_nests import add_nests
    started=perf_counter()
    snapshots=[];previous_layers={};previous_state={}
    result=None;old_water=None
    def capture(stage):
        nonlocal previous_layers,previous_state
        # Content deltas survive in-place changes in downstream generators and keep exports bounded.
        layers={k:copy.deepcopy(v) for k,v in result['layers'].items() if previous_layers.get(k)!=v}
        state={k:copy.deepcopy(result.get(k)) for k in STATE_KEYS if previous_state.get(k)!=result.get(k)}
        snapshots.append({'stage':stage,'title':STAGES[stage-1],'layers':layers,
                          'removed_layers':sorted(set(previous_layers)-set(result['layers'])),'state':state})
        previous_layers=copy.deepcopy(result['layers']);previous_state={k:copy.deepcopy(result.get(k)) for k in STATE_KEYS}
    for stage in range(1,cfg.phase+1):
        if stage<=5:
            result=generate_base(replace(cfg,phase=stage))
            # Climate/biome inspection belongs to stage 8 in this recipe.
            result.pop('terrain',None)
            for key in ('temperature','moisture','biome','natural_biome','landform'):result['layers'].pop(key,None)
            result['history']={'version':1,'ages':[]};result['ruins']=[]
        elif stage==6:old_water=tectonic_transition(result,cfg)
        elif stage==7:carve_relics(result,cfg,old_water)
        elif stage==8:
            c=replace(cfg,phase=6)
            add_climate(result,c);add_terrain_labels(result,c);add_environment(result,c)
            result['layers']['natural_biome']=copy.deepcopy(result['layers']['biome'])
        elif stage==9:
            generate_networks(result,cfg);refresh_environment(result,cfg)
        elif stage==10:
            add_biome_variants(result,cfg);civilization(result,cfg,7)
        elif stage==11:civilization(result,cfg,8)
        elif stage==12:civilization(result,cfg,9)
        elif stage==13:add_nests(result,replace(cfg,phase=9))
        elif stage in (14,15):age_transition(result,cfg,stage-13)
        elif stage==16:
            from .city_planner import fill_cities
            fill_cities(result)
        capture(stage)
    result['generator_version']=12
    result['config']=asdict(cfg);result['effective_config']['world_recipe']=3;result['effective_config']['phase']=cfg.phase
    result['phases'].update(version=2,completed=cfg.phase,titles=STAGES)
    result['build_stages']=snapshots
    definitions=registry(3);resolved={**asdict(cfg),**options(cfg)}
    overrides={k:resolved[k] for k,v in definitions.items() if k!='seed' and resolved[k]!=v['default']}
    result['recipe']={'version':3,'seed':cfg.seed,'overrides':overrides,'parameters':definitions,'resolved':resolved,
                      'provenance':{k:'override' if k in overrides else 'default' for k in definitions}}
    result['warnings'].append('Recipe 3 history is an artistic simulation: plate motion, city mortality and leyline changes are not calibrated physical or demographic predictions.')
    result['timing_ms']['history_total']=(perf_counter()-started)*1000
    result['timing_ms']['total']=result['timing_ms']['history_total']
    return result


def validate_age_world(world):
    """Check the versioned state boundary before an externally requested age advance."""
    from .terrain_lab import Config
    if not isinstance(world,dict):raise ValueError('world must be a generated recipe 3 object')
    try:
        json.dumps(world,allow_nan=False)
        cfg=Config(**world['config'])
        if cfg.world_recipe!=3 or cfg.phase<13 or cfg.size>257:
            raise ValueError('Age advancement requires recipe 3 through creatures (phase 13), grid <=257')
        if world['terrain']['version']!=6 or world['generator_version']!=12 or world['recipe']['version']!=3:
            raise ValueError('Retired world contract; regenerate with recipe_version 3')
        if world['magic']['version']!=3 or world['history']['version']!=1:
            raise ValueError('Unsupported magic or history state version')
        if world['settlements']['version']!=13 or world['civilizations']['version']!=2:
            raise ValueError('Unsupported civilization or settlement version')
        from .civilization_registry import registry_identity
        if world['civilizations']['registry']!=registry_identity():
            raise ValueError('Civilization registry changed; regenerate or explicitly migrate this world')
        if 'city_plans' in world:
            from .city_planner import planner_identity
            if world['city_plans'].get('identity')!=planner_identity():
                raise ValueError('City planner data changed; regenerate this world')
        if set(world['magic']['networks'])!=set(SCHOOLS):raise ValueError('Expected exactly eight networks')
        ages=world['history']['ages']
        if not isinstance(ages,list) or [a['age'] for a in ages]!=list(range(1,len(ages)+1)):
            raise ValueError('Age history must be contiguous')
        n=cfg.size
        for key in ('height','slope','tpi','water_type','water_surface','water_depth','river','rain_river',
                    'temperature','moisture','climate_moisture','volcanic','natural_biome'):
            if key not in world['layers']:raise ValueError('Missing world layer: '+key)
        for key,grid in world['layers'].items():
            if not isinstance(grid,list) or len(grid)!=n or any(not isinstance(row,list) or len(row)!=n for row in grid):
                raise ValueError('Invalid grid dimensions: '+key)
            if any(type(v) not in (int,float,bool) or not math.isfinite(v) for row in grid for v in row):
                raise ValueError('Nonfinite or nonnumeric grid: '+key)
            if any(row[0]!=row[-1] for row in grid) or any(len(set(row))!=1 for row in (grid[0],grid[-1])):
                raise ValueError('Invalid sphere seam or pole: '+key)
        if any(type(v) is not int or v not in NATURAL_BIOMES for row in world['layers']['natural_biome'] for v in row):
            raise ValueError('Unknown natural biome')
        catalogue=biome_catalogue()
        if world['terrain']['natural_biomes']!=natural_catalogue() or world['terrain']['biomes']!=natural_catalogue() or world['terrain']['magical_biomes']!=catalogue:
            raise ValueError('Unknown biome catalogue')
        if world['layers']['biome']!=world['layers']['natural_biome']:
            raise ValueError('biome must carry natural IDs; legacy phenotypes are retired')
        for z,row in enumerate(world['layers']['biome_variant']):
            for x,value in enumerate(row):
                if type(value) is not int or not -1<=value<len(catalogue):raise ValueError('Invalid biome variant')
                if value>=0 and catalogue[value]['core_biome_id']!=world['layers']['natural_biome'][z][x]:
                    raise ValueError('Magical biome core disagrees with natural biome')
        physical=world['effective_config']
        for key in ('globe_radius','sea_level','radius'):
            if not math.isclose(physical[key],getattr(cfg,key)*cfg.world_scale,rel_tol=1e-10,abs_tol=1e-10):
                raise ValueError('Physical scale disagrees with config')
        from .terrain_erosion import sphere_grid
        from .terrain_globe import direction
        points,_,_=sphere_grid(n,physical['globe_radius'])
        uids=set();occupied=set()
        for city in world['settlements']['sites']:
            from .terrain_profiles import get_profile
            if get_profile(city['population_profile'])['civilization']['kind']!='entity' or city['civilization_id']!=city['population_profile']:
                raise ValueError('Invalid city civilization')
            if city['city_class'] not in ('small','medium','capital'):
                raise ValueError('Invalid city classification')
            node=city['node']
            if type(node) is not int or not 0<=node<len(points) or node in occupied:
                raise ValueError('Invalid or repeated active city node')
            occupied.add(node)
            if tuple(points[node])!=(city['x'],city['z']):raise ValueError('City grid location disagrees with node')
            if any(abs(a-b)>1e-8 for a,b in zip(direction(city['x'],city['z'],n),city['direction'])):
                raise ValueError('City direction disagrees with node')
            if city['uid'] in uids or not isinstance(city['source_culture'],str):raise ValueError('Invalid city identity')
            uids.add(city['uid'])
        from .terrain_civilizations import classify_cities
        classified=copy.deepcopy(world['settlements']['sites']);classify_cities(classified)
        if any(a['city_class']!=b['city_class'] for a,b in zip(classified,world['settlements']['sites'])):
            raise ValueError('City classifications disagree with suitability')
        if any(r['node'] in occupied for r in world['ruins']):raise ValueError('An active city occupies a ruin')
        for net in world['magic']['networks'].values():
            for key,low,high in [('strength',0,2),('width_m',10,2000),('instability',0,1)]:
                if type(net[key]) not in (int,float) or not low<=net[key]<=high:raise ValueError('Invalid network '+key)
            if len(net['nodes'])>1024 or len(net['edges'])>4096:raise ValueError('Leyline edit budget exceeded')
            node_ids=set();line_ids=set()
            for node in net['nodes']:
                # Reuse the public edit boundary's finite vector/intensity/id checks.
                edit_network({'nodes':[],'edges':[]},new_node={k:node[k] for k in ('id','direction','intensity')})
                if node['id'] in node_ids:raise ValueError('Duplicate ley node id')
                node_ids.add(node['id'])
            for edge in net['edges']:
                if edge['id'] in line_ids:raise ValueError('Duplicate leyline id')
                line_ids.add(edge['id'])
                if any(type(edge[k]) is not int or not 0<=edge[k]<len(net['nodes']) for k in ('from','to')) or edge['from']==edge['to']:
                    raise ValueError('Invalid leyline endpoints')
                if type(edge['intensity']) not in (int,float) or not 0<=edge['intensity']<=4:raise ValueError('Invalid line intensity')
        return cfg
    except (KeyError,TypeError,IndexError,OverflowError) as exc:
        raise ValueError('Malformed age world: '+str(exc)) from exc


def advance_age_request(body):
    """Stateless JSON API v1: advance a supplied world, optionally after player ley edits.

    Same input => same output. Persist the returned world to advance again; Config alone
    reproduces genesis, not player-modified runtime state. The caller's object is unchanged.
    """
    if not isinstance(body,dict) or set(body)-{'api_version','world','steps','leyline_edits'}:
        raise ValueError('Expected api_version, world, optional steps and leyline_edits')
    if type(body.get('api_version')) is not int or body['api_version']!=1:
        raise ValueError('Unsupported age API version')
    steps=body.get('steps',1)
    if type(steps) is not int or not 1<=steps<=10:raise ValueError('steps must be 1..10')
    edits=body.get('leyline_edits',[])
    if not isinstance(edits,list) or len(edits)>128:raise ValueError('leyline_edits must be a list of at most 128 changes')
    world=body.get('world');cfg=validate_age_world(world)
    if edits and not cfg.magic_enabled:raise ValueError('Leyline edits require magic_enabled')
    # Snapshots are immutable; sharing their existing content avoids another full-history copy.
    result=copy.deepcopy({k:v for k,v in world.items() if k!='build_stages'})
    if 'build_stages' in world:result['build_stages']=list(world['build_stages'])
    for edit in edits:
        if not isinstance(edit,dict) or set(edit)-{'school','node_id','line_id','intensity','new_node'} or edit.get('school') not in SCHOOLS:
            raise ValueError('Invalid leyline edit')
        if 'new_node' in edit and 'intensity' in edit:raise ValueError('Put new-node intensity inside new_node')
        school=edit['school']
        result['magic']['networks'][school]=edit_network(result['magic']['networks'][school],**{k:v for k,v in edit.items() if k!='school'})
    validate_age_world(result)
    started=perf_counter()
    evaluate_networks(result,cfg);refresh_environment(result,cfg);add_biome_variants(result,cfg)
    start_age=len(result['history']['ages'])
    result['history'].setdefault('operations',[]).append({'api_version':1,'after_age':start_age,'steps':steps,'leyline_edits':copy.deepcopy(edits)})
    result['history']['replay']='Persist this returned world for subsequent calls. Config reproduces genesis; operation history records subsequent advances and player leyline edits.'
    for age in range(start_age+1,start_age+steps+1):
        baseline=world if age==start_age+1 else result
        previous_layers=copy.deepcopy(baseline['layers'])
        previous_state={k:copy.deepcopy(baseline.get(k)) for k in STATE_KEYS}
        result.pop('city_plans',None)
        age_transition(result,cfg,age)
        if age==start_age+steps:
            from .city_planner import fill_cities
            fill_cities(result)
        if 'build_stages' in result:
            stage=len(result['build_stages'])+1
            result['build_stages'].append({'stage':stage,'title':f'Age transition {age}','kind':'age',
                'layers':{k:copy.deepcopy(v) for k,v in result['layers'].items() if previous_layers.get(k)!=v},
                'removed_layers':sorted(set(previous_layers)-set(result['layers'])),
                'state':{k:copy.deepcopy(result.get(k)) for k in STATE_KEYS if previous_state.get(k)!=result.get(k)}})
            result['phases']['titles']=[s['title'] for s in result['build_stages']]
            result['phases']['completed']=stage
    result['age_api_version']=1
    result['timing_ms']['age_advance_total']=(perf_counter()-started)*1000
    return result
