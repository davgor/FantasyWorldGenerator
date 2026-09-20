"""Versioned derivation of settings from seed, generated environment and population."""
import math
import random
from dataclasses import asdict,replace
from .terrain_profiles import get_profile,profile_options
from .terrain_tectonics import child_seed

# One shared calibration across seeds 0..31 at grid 65; never fitted per world.
RECIPE_WORLD_SCALE=0.1834617044641644


def seed_config(request):
    from .terrain_lab import Config
    rng=random.Random(child_seed(request.seed,'recipe-v1-geology'))
    count=rng.randint(9,15);relief=rng.uniform(650,850)
    weather=random.Random(child_seed(request.seed,'recipe-v1-climate'))
    magic=random.Random(child_seed(request.seed,'recipe-v1-magic'))
    p=get_profile(request.population_profile)
    radius=10000*{'small':1,'medium':2,'large':3}[request.world_size]
    return Config(shape='globe',tectonics=1,auto_parameters=1,seed=request.seed,size=request.size,phase=request.phase,
        population_profile=request.population_profile,world_size=request.world_size,globe_radius=radius,world_scale=RECIPE_WORLD_SCALE,plate_count=count,tectonic_relief=relief,
        belt_width=.28/math.sqrt(count),crust_bias=rng.uniform(-.08,.08),
        amplitude=relief*1.5,wavelength=radius*1.6/math.sqrt(count),mountain_detail=rng.uniform(.55,.8),
        wind_bearing=weather.uniform(0,360),temperature_offset=weather.uniform(-3,3),moisture_bias=weather.uniform(-.06,.06),
        rain_passes=min(128,max(24,math.ceil(request.size*.375))),
        ley_nodes=magic.randint(16,20),ley_width=radius*RECIPE_WORLD_SCALE*.1,
        magic_instability=magic.uniform(.5,.85),human_magic_limit=p['mutation_limit'],
        road_max_grade=p['road_grade_limit'],human_adaptation=p['irrigation'],
        urban_food_demand=p['food_demand'],stubbornness=p['difficult_fraction'])


def initialize_derivation(result,cfg):
    result['population']=get_profile(cfg.population_profile)
    result['population_profiles']=profile_options()
    if not cfg.auto_parameters:return
    fixed={'shape','tectonics','globe_radius','world_scale','sea_level','erosion_passes','erosion_strength','magic_enabled'}
    direct={'world_size','seed','size','phase','population_profile','auto_parameters'}
    prof={'human_magic_limit','road_max_grade','human_adaptation','urban_food_demand','stubbornness'}
    seeded={'plate_count','tectonic_relief','crust_bias','mountain_detail','wind_bearing','temperature_offset','moisture_bias','ley_nodes','magic_instability'}
    formulas={'globe_radius':'world_size preset: 1x, 2x or 3x small radius','belt_width':'plate count','amplitude':'tectonic relief','wavelength':'plate count and radius','ley_width':'physical radius','rain_passes':'grid resolution'}
    result['derivation']={'version':1,'mode':'derived','settings':{
        k:{'value':v,'source':'user choice' if k in direct else 'population profile' if k in prof else 'seed stream v1' if k in seeded else formulas[k] if k in formulas else 'world recipe constant' if k in fixed else 'solver/default constant'}
        for k,v in asdict(cfg).items()},
        'note':'Same seed recipe for every population. Shared scale targets roughly 20 km² land on average; no per-seed area fitting. Derived inputs supersede expert values.'}


def record(result,cfg,changes,sources):
    resolved=replace(cfg,**changes)
    result['config'].update(changes);result['effective_config'].update(changes)
    for k,v in changes.items():result['derivation']['settings'][k]={'value':v,'source':sources[k]}
    return resolved


def derive_water(result,cfg):
    if not cfg.auto_parameters:return cfg
    area=result.get('area',{}).get('land_km2',0)
    return record(result,cfg,{'river_threshold_km2':max(.01,min(1,area/110))},
                  {'river_threshold_km2':'generated above-sea land area / 110, bounded 0.01..1 km²'})


def derive_population(result,cfg):
    if not cfg.auto_parameters or 'water' not in result:return cfg
    p=get_profile(cfg.population_profile);area=result['water']['dry_km2']
    count=min(24,math.floor(area/p['land_per_city_km2'])) if area>0 else 0
    # The ceiling is the settlement_spacing config bound, not a world-size assumption.
    # At 1500 m a world wider than about 25 km had every city clamped into one region:
    # the formula wants 3.2 km at a 200 km circumference and 8.6 km at 1000 km.
    spacing=max(150,min(10000,math.sqrt(area*1e6/max(1,count))*.27))
    reach=max(100,min(10000,spacing*2.2*p['support_multiplier']))
    return record(result,cfg,{'settlement_count':count,'settlement_spacing':spacing,'support_reach':reach,'culture_link_cost':reach*1.8},
        {'settlement_count':'dry land area / population land-per-city trait; maximum 24',
         'settlement_spacing':'square root of dry land per requested city × 0.27',
         'support_reach':'city spacing × 2.2 × population support capability',
         'culture_link_cost':'derived support reach × 1.8'})


def derive_institutions(result,cfg):
    if not cfg.auto_parameters or 'roads' not in result:return cfg
    sites=result['settlements']['sites'];routes=result['roads']['routes']
    rural=max((s.get('rural_population_estimate',0) for s in sites),default=0)
    hamlets=min(8,math.ceil(rural/40))
    crossings={tuple(sorted(edge)) for road in routes for edge in road['river_crossings']}
    forts=min(24,math.floor(sum(road['length_m'] for road in routes)/cfg.support_reach)+len(crossings))
    count=0
    if sites and 'magic' in result:
        from .terrain_erosion import sphere_grid
        points,areas,_=sphere_grid(cfg.size,result['effective_config']['globe_radius'])
        layers=result['layers']
        opportunity=sum(areas[i]*layers['magic_density'][z][x] for i,(x,z) in enumerate(points)
            if layers['water_type'][z][x]==0 and layers['magic_density'][z][x]>=.35 and layers['magic_hazard'][z][x]<=cfg.human_magic_limit)
        residents=sum(s.get('urban_population_estimate',0) for s in sites)
        count=min(12,math.floor(opportunity/(math.pi*150**2)),residents//100)
    return record(result,cfg,{'hamlets_per_core':hamlets,'fortress_count':forts,'college_count':count},
        {'hamlets_per_core':'maximum city rural residents / 40, rounded up; each city uses its own residents; ceiling 8',
         'fortress_count':'road length / support reach plus unique river crossings; ceiling 24; strategic placement still required',
         'college_count':'safe dense magic footprint and urban residents / 100; ceiling 12; host eligibility and access still required'})
