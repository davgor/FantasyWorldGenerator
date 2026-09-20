"""Version 3 staged world history. Artistic deep-time and civilization proxies."""
import copy
import math
import json
import random
from time import perf_counter
from dataclasses import asdict, replace
from .terrain_tectonics import child_seed
from .terrain_leyline_history import SCHOOLS, KNOWN_SCHOOLS, generate_networks, evaluate_networks, edit_network, dominant_school
from .terrain_astrology import add_astrology, refresh_astrology, tide, day_state, DAYS_PER_YEAR
from .terrain_ruins import ruin_legacy

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


LEY_DESTRUCTION={'weave':'An arcane surge tore the city apart.', 'umbral':'Necrotic entropy extinguished the city.',
                 'infernal':'Infernal corruption and demonic incursions drove its people away.',
                 'radiant':'An overwhelming radiant surge forced the city to be abandoned.',
                 'fire':'A fire leyline engulfed the city in flames.', 'water':'A water leyline drowned or froze the city.',
                 'earth':'An earth leyline let roots and stone reclaim the city.',
                 'air':'An air leyline shattered the city with storms and force.'}
THREAT_ASSESSMENT_VERSION=3


def fantasy_nest_threats(city,nests,radius):
    """Standing monster pressure. Shared by age fate and regional threat assessment.

    Weight scales with the danger tier, so a greater lair at the gates is the reason a
    city falls and a tier one nuisance is not; tier five keeps the flat .55 the single
    fixed weight used to give every monster alike.
    """
    threats=[]
    for nest in sorted(nests,key=lambda n:n['id']):
        if nest.get('layer','surface')!='surface' or nest.get('real',True):continue
        dragon='dragon' in nest.get('name','').lower()
        dangerous=dragon or nest.get('family') in ('infernal','undead','aberrant')
        if not dangerous:continue
        distance=radius*math.acos(max(-1.,min(1.,sum(a*b for a,b in zip(city['direction'],nest['direction'])))))
        reach=min(radius*.5,max(350.,nest.get('range_m',nest.get('spacing_m',350.))*2))
        if distance>reach:continue
        threats.append({'kind':'dragon' if dragon else 'monster','weight':.11*nest.get('tier',5)*(1-distance/reach),
                        'reason':nest['name']+' drove the inhabitants away.',
                        'nest_id':nest['id'],'name':nest['name'],'family':nest.get('family'),
                        'distance_m':distance,'reach_m':reach})
    return threats


def city_potencies(city,layers,lunar=None):
    """The potencies a lottery reads: the base field, swayed by the moon when a surge is in force.

    `lunar` is (per-school tide factors, lunar_influence). The sway is momentary: it scales
    what the fate sees, never the exported field. Same association order as Core/ages.cpp.
    """
    potencies={name:layers['ley_'+name][city['z']][city['x']] if 'ley_'+name in layers else 0. for name in SCHOOLS}
    if lunar:
        factors,influence=lunar
        sway=layers['lunar_sensitivity'][city['z']][city['x']] if 'lunar_sensitivity' in layers else 0.
        # Only the known schools sway: the tide is charted against this world's moon,
        # and a school the world has never named was never in that chart.
        for name in KNOWN_SCHOOLS:
            factor=1+influence*sway*(factors[name]-1)
            potencies[name]=potencies[name]*factor
    return potencies


def lunar_context(result,cfg,day=None):
    """The moon on the day an age turns: the founding report's end year, or an explicit day."""
    if 'astrology' not in result:return None,None
    from .terrain_world import options
    if day is None:day=int((result.get('settlements',{}).get('founding') or {}).get('end_year',0))*DAYS_PER_YEAR
    moon=result['astrology']['moon'];state=day_state(moon,day)
    record={'day':day,'phase_fraction':state['phase_fraction'],'elongation_degrees':state['elongation_degrees'],
            'illumination':state['illumination'],'leaning':state['leaning'],'tide':state['tide']}
    return (tide(moon,day),options(cfg)['lunar_influence']),record


def ley_threat_pressure(city,layers,lunar=None):
    potencies=city_potencies(city,layers,lunar)
    winner=dominant_school(potencies)
    if not winner:return 0.,None
    return min(.6,potencies[winner]*.45),{'school':winner,'potency':potencies[winner]}


def assess_city_threat(city,layers,nests,radius,outlook=None):
    from .terrain_wars import veteran_wars
    nests=fantasy_nest_threats(city,nests,radius)
    nest_pressure=sum(t['weight'] for t in nests)
    ley_pressure,ley=ley_threat_pressure(city,layers)
    # A city that has already been to war expects the next one. This is why a veteran
    # builds heavier walls: the city planner reads regional_threat as defense_priority.
    fought=veteran_wars(city)
    war_pressure=min(.4,.15*fought)
    contributors=[{'kind':t['kind'],'weight':round(t['weight'],6),'nest_id':t['nest_id'],'name':t['name'],
                   'family':t['family'],'distance_m':round(t['distance_m'],4),'reach_m':round(t['reach_m'],4)}
                  for t in nests]
    if ley:contributors.append({'kind':'ley','weight':round(ley_pressure,6),**ley})
    if war_pressure:contributors.append({'kind':'war','weight':round(war_pressure,6),'wars_fought':fought})
    # Version 3 adds the forward-looking war outlook beside the backward-looking pressure. The
    # regional threat the city planner reads is unchanged: a forecast does not build walls yet.
    outlook=outlook or {'wars_recent':0,'enemy_living':False,'war_risk':0.,'war_risk_kind':None,'war_risk_opponent_uid':None,'war_hunger':0.,'war_hunger_target_uid':None}
    return {'city_uid':city['uid'],'city_name':city.get('name'),'site_id':city.get('id'),
            'regional_threat':round(min(1.,nest_pressure+ley_pressure+war_pressure),6),
            'nest_pressure':round(nest_pressure,6),'ley_pressure':round(ley_pressure,6),
            'war_pressure':round(war_pressure,6),'wars_fought':fought,
            'wars_recent':outlook['wars_recent'],'enemy_living':bool(outlook['enemy_living']),
            'war_risk':outlook['war_risk'],'war_risk_kind':outlook['war_risk_kind'],'war_risk_opponent_uid':outlook['war_risk_opponent_uid'],
            'war_hunger':outlook['war_hunger'],'war_hunger_target_uid':outlook['war_hunger_target_uid'],
            'contributors':contributors,'ley':ley}


def add_threat_assessments(result,evaluated_after,age=None,spacing=None):
    from .terrain_wars import war_outlook
    radius=result['effective_config']['globe_radius']
    nests=result.get('beast_nests',{}).get('sites',[])
    layers=result['layers']
    cities=sorted(result.get('settlements',{}).get('sites',[]),key=lambda s:str(s.get('uid',s['id'])))
    spacing=spacing if spacing is not None else (result.get('config') or {}).get('settlement_spacing')
    # `reach_m` is refreshed before the fall is decided, so a fallen villain still carries
    # a live-looking reach and would feed the war outlook without the standing filter.
    from .terrain_villains import standing as standing_villains
    villains=[v for v in standing_villains(result.get('villains',{}).get('people',[])) if v.get('reach_m')]
    outlook=war_outlook(cities,result.get('humans',{}).get('cores',[]),result.get('roads',{}).get('routes',[]),radius,spacing,age,villains) if spacing else {}
    reports=[assess_city_threat(city,layers,nests,radius,outlook.get(city['uid'])) for city in cities]
    result['threat_assessments']={
        'version':THREAT_ASSESSMENT_VERSION,'evaluated_after':evaluated_after,'age':age,
        'cities':reports,
        'method':'Per-city standing pressure from eligible fantasy nests (dragons and infernal/undead/aberrant families within reach) plus dominant local leyline potency, and the war outlook: wars fought this age, whether a former opponent still stands, and the strongest contention pressure a living neighbour exerts (the pair pressure the next age lottery draws against). Same nest eligibility and reach as age-fate weights; excludes magical self-destruction.',
        'limits':'Artistic regional threat for fortification and shape preference, not creature counts, hostility AI or guaranteed attacks. Real-animal nests do not contribute. The war outlook is a forecast, not a promise, and does not move regional_threat.'}


def city_fate(city,layers,nests,radius,seed,age,roll=None,magic_enabled=True,lunar=None,villains=()):
    potencies=city_potencies(city,layers,lunar)
    causes=[]
    ley_pressure,ley=ley_threat_pressure(city,layers,lunar)
    if ley:causes.append((ley['school'],ley_pressure,LEY_DESTRUCTION[ley['school']],ley))
    for threat in fantasy_nest_threats(city,nests,radius):
        causes.append((threat['kind'],threat['weight'],threat['reason'],
                       {'nest_id':threat['nest_id'],'family':threat['family'],'distance_m':threat['distance_m'],'reach_m':threat['reach_m']}))
    if magic_enabled:causes.append(('self_magic',.035+.06*potencies['weave'],
                                    'The city destroyed itself in a magical experiment, leaving a new Weave key point.',{}))
    # Appended last, like the divine cause: the selector walk below is order-sensitive,
    # so a villain may extend the list but must never insert into it.
    if villains:
        from .terrain_villains import causes as villain_causes
        causes.extend(villain_causes(villains,city,radius))
    chance=min(.9,sum(c[1] for c in causes))
    rng=random.Random(child_seed(seed,'city-fate-'+city['uid'],age))
    draw=rng.random() if roll is None else roll
    if draw>=chance or not causes:return None
    selector=(draw/chance)*sum(c[1] for c in causes)
    chosen=causes[-1]
    for cause in causes:
        selector-=cause[1]
        if selector<=0:chosen=cause;break
    # Every ruin seeds a key point: the destroyer's school, else the region's, else the culture's.
    legacy=ruin_legacy(city,chosen[0],potencies,nest_family=chosen[3].get('family'),villain_school=chosen[3].get('school'))
    evidence=dict(chosen[3])
    if lunar and chosen[0] in KNOWN_SCHOOLS:evidence['moon_tide']=lunar[0][chosen[0]]
    return dict(cause=chosen[0],reason=chosen[2],evidence=evidence,probability=chance,roll=draw,
                new_node_school=legacy['school'],legacy=legacy)


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
    if 'astrology' in result:refresh_astrology(result,cfg)


RUIN_KEYS=('uid','name','node','x','z','direction','height_m','population_profile','civilization_id',
           'city_class','source_culture','founded_age','war_history')


def rebuild_tail(result,cfg,survivors,label,age,*,evaluate=True,religion=True):
    """The tail an age transition and a visitation both run: fields, biomes, civilization,
    nests, threats, sky.

    One body, two callers, so the two cannot drift. `evaluate` skips the ley rebuild when
    magic is off; `religion` re-resolves the pantheon, which an age turning does and a
    visitation does not, because a visitation resolves religion itself once its own
    records are written. The threat pass takes the spacing explicitly from the config it
    was built with, rather than one caller passing it and the other letting the pass look
    it up.
    """
    from .terrain_nests import add_nests
    if evaluate:evaluate_networks(result,cfg)
    refresh_environment(result,cfg)
    add_biome_variants(result,cfg)
    result['_survivors']=survivors;result['_age']=age
    # All dependent institutions/roads/food are rebuilt from active cities, so no dead-city hamlets survive.
    civilization(result,cfg)
    result.pop('_survivors',None);result.pop('_age',None)
    add_nests(result,replace(cfg,phase=9))
    result['beast_nests']['evaluated_age']=age
    add_threat_assessments(result,label,age,spacing=cfg.settlement_spacing)
    if religion:
        if 'astrology' in result:
            from .terrain_religion import add_religion
            add_religion(result,cfg)
    else:
        refresh_astrology(result,cfg)


def age_transition(result,cfg,age,moon_day=None):
    from .terrain_nests import add_nests
    from .terrain_wars import participation, resolve_wars
    from .terrain_world import options
    add_nests(result,replace(cfg,phase=9))
    result['beast_nests']['evaluated_age']=age-1
    cities=copy.deepcopy(result['settlements']['sites'])
    ruins=result.setdefault('ruins',[]);events=[];survivors=[]
    radius=result['effective_config']['globe_radius']
    # The moon on the day the age turns. A momentary surge scales every potency the
    # lottery reads; the fields themselves are not rewritten.
    lunar,moon=lunar_context(result,cfg,moon_day)
    # The cast advances on the assessment this age inherited, so a villain is always one
    # rebuild behind the region it is eating, and can never be raised by its own damage.
    from .terrain_villains import advance as advance_villains, outlook as villain_outlook
    o=options(cfg)
    villains=advance_villains(result,cfg,age,float(o.get('villain_rise',0.)),
                              float(o.get('villain_hold',.7)),float(o.get('villain_density',3.)))
    # Wars are settled before any other fate. They are decided between cities out of the
    # ground and supply the finished age left them, and a city a neighbour has already
    # taken cannot also be eaten by a dragon; its ruin records the war that ended it.
    wars,war_fates=resolve_wars(cities,result.get('humans',{}).get('cores',[]),
                                result.get('roads',{}).get('routes',[]),result['layers'],
                                radius,cfg.settlement_spacing,cfg.seed,age,
                                magic_enabled=bool(cfg.magic_enabled),survival=float(options(cfg).get('war_survival',0.)),villains=villains)
    by_uid={city['uid']:city for city in cities}
    # Both sides carry the war, so a survivor's history says what it has already fought.
    for war in wars:
        for uid in war['participants']:
            by_uid[uid].setdefault('war_history',[]).append(participation(war,uid))
        if war.get('outcome')=='vassalage':
            # World option war_survival: the loser stands as a vassal, a living enemy in both histories.
            by_uid[war['defeated_uid']]['vassal_of']=war['victor_uid']
    for city in cities:
        fate=war_fates.get(city['uid'])
        if fate:
            # The victor's own magic scars the ground it took.
            legacy=ruin_legacy(city,fate['cause'],city_potencies(city,result['layers'],lunar),
                               victor_culture=fate['evidence'].get('opponent_civilization_id'))
            fate={**fate,'new_node_school':legacy['school'],'legacy':legacy}
        else:
            fate=city_fate(city,result['layers'],result.get('beast_nests',{}).get('sites',[]),radius,cfg.seed,age,
                           magic_enabled=bool(cfg.magic_enabled),lunar=lunar,villains=villains)
        if not fate:survivors.append(city);continue
        ruin={k:copy.deepcopy(city[k]) for k in RUIN_KEYS if k in city}
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
                    'direction':ruin['direction'],'intensity':ruin.get('legacy',{}).get('intensity',2.5)})
        # A god still walking the world goes home when the age turns; its footprint stays.
        if 'religion' in result:
            from .terrain_visitation import walking_gods, depart_god
            for god_id in walking_gods(result):depart_god(result,cfg,god_id,age,rebuild=False)
    rebuild_tail(result,cfg,survivors,'age',age,evaluate=bool(cfg.magic_enabled))
    if 'villains' in result:
        # Built after the rebuild, on settled ground: a well joins the holdings a
        # villain actually has this age, and a claim names the peoples actually near it.
        from .terrain_villains import build as build_villain_works
        from .terrain_villains import standing as standing_villains
        works=build_villain_works(result,cfg,age,standing_villains(result['villains']['people']))
        if works:
            evaluate_networks(result,cfg);add_biome_variants(result,cfg)
            result['villains']['works']=works
        result['villains']['outlook']=villain_outlook(result,cfg,float(o.get('villain_rise',0.)),
                                                      float(o.get('villain_density',3.)))
    old_ids={s['uid'] for s in survivors}
    new=[s['uid'] for s in result['settlements']['sites'] if s['uid'] not in old_ids]
    result['history']['ages'].append({'age':age,'events':events,'wars':copy.deepcopy(wars),'moon':moon,
                                    'surviving_city_ids':sorted(old_ids),
                                    'new_city_ids':new,'order':['nests before fates','wars','city fates','ruins and hamlet removal','leyline update','biomes','civilization','nests','threat assessment']})


STATE_KEYS=('world_scene','terrain_detail','wildlife','city_plans','hamlet_plans','castle_plans','civilizations','history','ocean_archipelagos','sediment_budget','terrain','water','climate','magic','settlements','roads','humans','sky','beast_nests','threat_assessments','ruins','villains','heroes','story_web','npcs','key_locations','key_location_plans','nomads','beast_movements','encounters','pending_ley_edits','settlement_candidates',
            'habitats','regions','seasonal_environment','population_budget','peoples','population',
            'population_profiles','seasonal_food','fisheries','transport','world_economy','geological_history','area',
            'astrology','lunar_almanac','religion')


def _attach_heroes(result):
    """The finished world's cast, from a separate package: one call, never a crash.

    `hero_generator` reads the world JSON and writes only this block; the core knows no
    roles, archetypes or schemas. A raising revision yields a `status: failed` block. The
    FANTASY_WORLD_HEROES=0 environment switch leaves the key absent entirely.
    """
    from hero_generator import attach
    result.pop('heroes',None)
    block=attach(result)
    if block is not None:result['heroes']=block


def _attach_story_web(result):
    """The cast's story web, from a second separate package that reads only `heroes` and the world.

    `story_web` writes only this block; the core knows no tropes or weights. A raising revision
    yields a `status: failed` block. FANTASY_WORLD_STORY_WEB=0 leaves the key absent.
    """
    from story_web import attach
    result.pop('story_web',None)
    block=attach(result)
    if block is not None:result['story_web']=block


def _attach_key_location_plans(result):
    """Exterior plans for the places, from the same package, after they are placed.

    A separate top-level block because `city_plans`, `hamlet_plans` and `castle_plans` are
    top-level: a consumer scanning for plan blocks would not find these nested inside a
    sited-feature one. It runs after `_attach_key_locations` because it reads that block, and
    yields nothing at all if the locations failed or were switched off.
    """
    from key_locations import attach_plans
    result.pop('key_location_plans',None)
    block=attach_plans(result)
    if block is not None:result['key_location_plans']=block


def _attach_key_locations(result):
    """The charged places between the settlements, from a fourth separate package.

    `key_locations` reads the finished terrain, hydrology, ley networks, roads, cultures,
    ruins, nests and religion and writes only this block: caves, mines, barrows, shrines,
    watchtowers, lairs, drowned ruins and wonders, each with a derived state, occupant and
    threat, and an interior chamber graph on the tier-2 complexes. It dedupes by node
    against every point another module already placed, so nothing here re-places a ruin, a
    nest, a shrine or a college. A raising revision yields a `status: failed` block.
    FANTASY_WORLD_KEY_LOCATIONS=0 leaves the key absent.
    """
    from key_locations import attach
    result.pop('key_locations',None)
    block=attach(result)
    if block is not None:result['key_locations']=block


def _attach_npcs(result):
    """The ordinary working population, from a third separate package that reads the planned sites.

    `npc_roster` expands the staffing rosters the city, hamlet and castle planners already
    placed into one record per post, folds in the cast by uid, and writes only this block; the
    core knows no posts or earmarks. A raising revision yields a `status: failed` block.
    FANTASY_WORLD_NPCS=0 leaves the key absent. It runs last because it reads `heroes`.
    """
    from npc_roster import attach
    result.pop('npcs',None)
    block=attach(result)
    if block is not None:result['npcs']=block


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
        # The snapshot above already holds an independent copy of everything that
        # changed, and an unchanged entry still equals the copy kept from the stage
        # that last wrote it. Re-deep-copying every layer and state key here copied
        # the whole world a second time on each of the sixteen stages.
        previous_layers={k:(layers[k] if k in layers else previous_layers.get(k)) for k in result['layers']}
        previous_state={k:(state[k] if k in state else previous_state.get(k)) for k in STATE_KEYS}
    for stage in range(1,cfg.phase+1):
        if stage<=5:
            result=generate_base(replace(cfg,phase=stage))
            # Climate/biome inspection belongs to stage 8 in this recipe.
            result.pop('terrain',None)
            for key in ('temperature','moisture','biome','natural_biome','landform'):result['layers'].pop(key,None)
            result['history']={'version':3,'ages':[]};result['ruins']=[]
        elif stage==6:old_water=tectonic_transition(result,cfg)
        elif stage==7:carve_relics(result,cfg,old_water)
        elif stage==8:
            c=replace(cfg,phase=6)
            add_climate(result,c);add_terrain_labels(result,c);add_environment(result,c)
            result['layers']['natural_biome']=copy.deepcopy(result['layers']['biome'])
            from .terrain_detail import attach_detail
            attach_detail(result)
        elif stage==9:
            generate_networks(result,cfg);refresh_environment(result,cfg);add_astrology(result,cfg)
        elif stage==10:
            add_biome_variants(result,cfg);civilization(result,cfg,7)
        elif stage==11:civilization(result,cfg,8)
        elif stage==12:civilization(result,cfg,9)
        elif stage==13:
            add_nests(result,replace(cfg,phase=9))
            add_threat_assessments(result,'beast_nests',spacing=cfg.settlement_spacing)
            from .terrain_religion import add_religion
            add_religion(result,cfg)
        elif stage in (14,15):age_transition(result,cfg,stage-13)
        elif stage==16:
            from .city_planner import fill_cities
            from .hamlet_planner import fill_hamlets
            from .castle_planner import fill_castles
            from .terrain_nomads import add_nomads
            from .terrain_nomad_routes import add_nomad_routes
            from .terrain_beast_movement import add_beast_movements
            from .terrain_encounters import add_encounters
            from .terrain_nomad_effects import apply_nomad_effects
            fill_cities(result)
            fill_hamlets(result)
            fill_castles(result)
            # Bands are part of the world, so they are placed before the packages that
            # only read it: heroes, the story web and the rosters see a world with them in.
            add_nomads(result, cfg)
            add_nomad_routes(result, cfg)
            add_beast_movements(result, cfg)
            add_encounters(result, cfg)
            apply_nomad_effects(result, cfg)
            _attach_heroes(result)
            _attach_story_web(result)
            _attach_npcs(result)
            _attach_key_locations(result)
            _attach_key_location_plans(result)
        capture(stage)
    result['generator_version']=16
    result['config']=asdict(cfg);result['effective_config']['world_recipe']=3;result['effective_config']['phase']=cfg.phase
    result['phases'].update(version=2,completed=cfg.phase,titles=STAGES)
    result['build_stages']=snapshots
    definitions=registry(3);resolved={**asdict(cfg),**options(cfg)}
    # Authored inputs the request builder consumes (circumference_km, relief_m) are not
    # config fields, so they never reach the resolved document; their effect appears in
    # the terms they derive.
    overrides={k:resolved[k] for k,v in definitions.items()
               if k!='seed' and k in resolved and resolved[k]!=v['default']}
    result['recipe']={'version':3,'seed':cfg.seed,'overrides':overrides,'parameters':definitions,'resolved':resolved,
                      'provenance':{k:'override' if k in overrides else 'default' for k in definitions}}
    result['warnings'].append('Recipe 3 history is an artistic simulation: plate motion, city mortality and leyline changes are not calibrated physical or demographic predictions.')
    result['timing_ms']['history_total']=(perf_counter()-started)*1000
    result['timing_ms']['total']=result['timing_ms']['history_total']
    from .world_debug import build_debug
    result['debug_stats']=build_debug(result)
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
        if world['terrain']['version']!=6 or world['generator_version']!=16 or world['recipe']['version']!=3:
            raise ValueError('Retired world contract; regenerate with recipe_version 3')
        if world['magic']['version']!=4 or world['history']['version']!=3:
            # History 3 is the twelve-school contract. A world built against the eight-school
            # taxonomy has no hidden networks to validate, so it cannot advance an age here.
            raise ValueError('Unsupported magic or history state version; regenerate for the twelve-school contract')
        astrology=world.get('astrology');almanac=world.get('lunar_almanac');religion=world.get('religion')
        if not isinstance(astrology,dict) or astrology.get('version')!=1 or not isinstance(almanac,dict) or almanac.get('version')!=1:
            raise ValueError('Retired world without the moon; regenerate')
        if not isinstance(religion,dict) or religion.get('version')!=1:
            raise ValueError('Retired world without a pantheon; regenerate')
        from .terrain_religion import catalogue_identity
        if religion.get('catalogue')!=catalogue_identity():
            raise ValueError('Pantheon catalogue changed; regenerate or explicitly migrate this world')
        from .terrain_astrology import PERIOD_RANGES, TILT_RANGE
        moon=astrology['moon']
        for key,(low,high) in PERIOD_RANGES.items():
            period=moon['periods'][key];offset=moon['offsets'][key]
            if type(period) is not int or not low<=period<=high or type(offset) is not int or not 0<=offset<period:
                raise ValueError('Invalid moon '+key+' cycle')
        if type(moon['tilt_max_degrees']) not in (int,float) or not TILT_RANGE[0]<=moon['tilt_max_degrees']<=TILT_RANGE[1]:
            raise ValueError('Invalid moon tilt')
        if moon['great_year_days']!=math.lcm(*moon['periods'].values()):raise ValueError('Invalid great year')
        if world['settlements']['version']!=15 or world['civilizations']['version']!=3:
            raise ValueError('Unsupported civilization or settlement version')
        # A rural report older than 7 pinned its fortresses to a static count. Advancing
        # it would rebuild the hinterland under the derived demand and hand back a world
        # whose two ages disagree about how much route defence it ever wanted.
        if world['humans']['version']!=8:
            raise ValueError('Retired rural report; regenerate for the derived fortress demand and war history')
        from .civilization_registry import registry_identity
        if world['civilizations']['registry']!=registry_identity():
            raise ValueError('Civilization registry changed; regenerate or explicitly migrate this world')
        from .terrain_detail import attach_detail
        expected_detail={}
        expected_detail['config']=world['config']
        attach_detail(expected_detail)
        if world.get('terrain_detail')!=expected_detail['terrain_detail']:raise ValueError('Terrain detail identity mismatch; regenerate')
        if 'city_plans' in world:
            from .city_planner import planner_identity
            if world['city_plans'].get('identity')!=planner_identity():
                raise ValueError('City planner data changed; regenerate this world')
        if 'hamlet_plans' in world:
            from .hamlet_planner import planner_identity as hamlet_planner_identity
            if world['hamlet_plans'].get('identity')!=hamlet_planner_identity():
                raise ValueError('Hamlet planner data changed; regenerate this world')
        if 'castle_plans' in world:
            from .castle_planner import planner_identity as castle_planner_identity
            if world['castle_plans'].get('identity')!=castle_planner_identity():
                raise ValueError('Castle planner data changed; regenerate this world')
        if set(world['magic']['networks'])!=set(SCHOOLS):raise ValueError(f'Expected exactly {len(SCHOOLS)} networks: the {len(KNOWN_SCHOOLS)} known schools and the {len(SCHOOLS)-len(KNOWN_SCHOOLS)} hidden')
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
    if not isinstance(body,dict) or set(body)-{'api_version','world','steps','leyline_edits','moon_day'}:
        raise ValueError('Expected api_version, world, optional steps, leyline_edits and moon_day')
    if type(body.get('api_version')) is not int or body['api_version']!=1:
        raise ValueError('Unsupported age API version')
    steps=body.get('steps',1)
    if type(steps) is not int or not 1<=steps<=10:raise ValueError('steps must be 1..10')
    # The orchestrator may say what day the age turns; otherwise the founding year decides.
    moon_day=body.get('moon_day')
    if moon_day is not None and (type(moon_day) is not int or moon_day<0):raise ValueError('moon_day must be an integer day >= 0')
    edits=body.get('leyline_edits',[])
    if not isinstance(edits,list) or len(edits)>128:raise ValueError('leyline_edits must be a list of at most 128 changes')
    world=body.get('world');cfg=validate_age_world(world)
    if edits and not cfg.magic_enabled:raise ValueError('Leyline edits require magic_enabled')
    # Snapshots are immutable; sharing their existing content avoids another full-history copy.
    result=copy.deepcopy({k:v for k,v in world.items() if k!='build_stages'})
    if 'build_stages' in world:result['build_stages']=list(world['build_stages'])
    for edit in edits:
        if not isinstance(edit,dict) or set(edit)-{'school','node_id','line_id','intensity','new_node'} or edit.get('school') not in KNOWN_SCHOOLS:
            raise ValueError('Invalid leyline edit')
        if 'new_node' in edit and 'intensity' in edit:raise ValueError('Put new-node intensity inside new_node')
        school=edit['school']
        result['magic']['networks'][school]=edit_network(result['magic']['networks'][school],**{k:v for k,v in edit.items() if k!='school'})
    # Without edits, result is a deepcopy of a world validate_age_world has just accepted
    # and the check is a pure function of content, so re-running it serialises the whole
    # world a second time to reach the answer already in cfg. Edits mutate magic.networks,
    # so an edited world still pays for the full re-check.
    if edits:validate_age_world(result)
    started=perf_counter()
    evaluate_networks(result,cfg);refresh_environment(result,cfg);add_biome_variants(result,cfg);refresh_astrology(result,cfg)
    start_age=len(result['history']['ages'])
    result['history'].setdefault('operations',[]).append({'api_version':1,'after_age':start_age,'steps':steps,'leyline_edits':copy.deepcopy(edits),'moon_day':moon_day})
    result['history']['replay']='Persist this returned world for subsequent calls. Config reproduces genesis; operation history records subsequent advances and player leyline edits.'
    for age in range(start_age+1,start_age+steps+1):
        baseline=world if age==start_age+1 else result
        # Only the build_stages snapshot below reads these, and a live world carries no
        # snapshots: the CLI drops them before any consumer sees the document. Copied
        # unconditionally, they were a full copy of every layer grid plus one per
        # STATE_KEY -- allocated, never read and freed, on every age of every advance a
        # game makes. Presence of build_stages cannot change inside this loop, so the
        # guard is the same condition the snapshot already tests.
        snapshotting='build_stages' in result
        previous_layers=copy.deepcopy(baseline['layers']) if snapshotting else {}
        previous_state={k:copy.deepcopy(baseline.get(k)) for k in STATE_KEYS} if snapshotting else {}
        result.pop('city_plans',None)
        result.pop('hamlet_plans',None)
        result.pop('castle_plans',None)
        result.pop('world_scene',None)
        age_transition(result,cfg,age,moon_day)
        if age==start_age+steps:
            from .city_planner import fill_cities
            from .hamlet_planner import fill_hamlets
            from .castle_planner import fill_castles
            from .terrain_nomads import add_nomads
            from .terrain_nomad_routes import add_nomad_routes
            from .terrain_beast_movement import add_beast_movements
            from .terrain_encounters import add_encounters
            from .terrain_nomad_effects import apply_nomad_effects
            fill_cities(result)
            fill_hamlets(result)
            fill_castles(result)
            # Regenerated, not carried: an age advance ruins cities, so bands classified
            # against the previous age would name ruins that have moved and refuges that
            # no longer stand. add_nomads replaces the block wholesale.
            add_nomads(result, cfg)
            add_nomad_routes(result, cfg)
            add_beast_movements(result, cfg)
            add_encounters(result, cfg)
            apply_nomad_effects(result, cfg)
            _attach_heroes(result)
            _attach_story_web(result)
            _attach_npcs(result)
            _attach_key_locations(result)
            _attach_key_location_plans(result)
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
    from .world_debug import build_debug
    result['debug_stats']=build_debug(result)
    return result
