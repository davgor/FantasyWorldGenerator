"""Versioned, partial world recipes. No semantic prompt interpretation or engine I/O."""
import json
import math
from dataclasses import asdict
from functools import lru_cache
from .terrain_profiles import civilization_ids, profile_options

NETWORKS = ('weave', 'umbral', 'infernal', 'radiant', 'fire', 'water', 'earth', 'air')
ZONES = ('demonic', 'draconic', 'pirate', 'steampunk', 'witch_huts', 'red_sands',
         'dead_sea', 'starlight_lakes', 'haunted_sands', 'enchanted', 'fungal', 'crystal', 'haunted_marsh')


def spec(default, low, high, group, description, units='relative'):
    return dict(default=default, min=low, max=high, group=group,
                description=description, units=units, type='integer' if type(default) is int else 'number')


OPTIONS = {
    # Counts come from density over habitable ground, so the limit is a safety valve
    # rather than the thing that decides how full a world is: zero means systemic.
    'nest_limit': spec(0, 0, 20000, 'Beast nests', 'Hard cap on habitat anchors per pass; zero lets the ground decide', 'anchors'),
    'animal_density': spec(4.5, 0., 40., 'Beast nests', 'Tier one animal groups per square kilometre of land, and again per square kilometre of water; higher tiers follow the pyramid', 'groups/km2'),
    'monster_density': spec(.53, 0., 40., 'Beast nests', 'Tier one monster lairs per square kilometre of land, and again per square kilometre of water; higher tiers follow the pyramid', 'lairs/km2'),
    'animal_tier_falloff': spec(4., 1.5, 8., 'Beast nests', 'How much rarer each animal danger tier is than the one below it'),
    'monster_tier_falloff': spec(2., 1.5, 8., 'Beast nests', 'How much rarer each monster danger tier is; gentler than the animal pyramid so a greater lair is an event rather than a rumour, and the smallest world can still hold one', ),
    'nest_density': spec(1., 0., 3., 'Beast nests', 'Overall creature density multiplier; zero empties the world'),
    'nest_fantasy': spec(1., 0., 3., 'Beast nests', 'Monster density multiplier; zero leaves only animals'),
    'nest_per_species': spec(0, 0, 64, 'Beast nests', 'Cap on anchors for one species; zero lets density decide', 'anchors'),
    'nest_min_suitability': spec(.3, .05, .95, 'Beast nests', 'Minimum weighted habitat suitability'),
    'nest_spacing': spec(1., .25, 4., 'Beast nests', 'Same-species territory spacing multiplier'),
    'nest_settlement_clearance': spec(250., 0., 3000., 'Beast nests', 'Minimum distance from settled anchors on the same layer', 'm'),
    'nest_variation': spec(0, 0, 4294967295, 'Beast nests', 'Independent nest seed variation', 'seed'),
    'mountain_abundance': spec(1.3, .25, 2., 'Geography', 'Width of mountain collision belts relative to the legacy model'),
    'metal_abundance': spec(1., .1, 2., 'Geography', 'Overall geological metal richness multiplier'),
    'archipelago_count': spec(5, 0, 16, 'Ocean islands', 'Candidate oceanic island clusters', 'clusters'),
    'archipelago_occurrence': spec(.8, 0., 1., 'Ocean islands', 'Probability each candidate cluster manifests'),
    'islands_per_cluster': spec(5, 1, 12, 'Ocean islands', 'Islands in each manifested cluster', 'islands'),
    'island_radius': spec(.035, .008, .1, 'Ocean islands', 'Typical island radius / planet radius'),
    'island_spacing': spec(2.5, 1., 6., 'Ocean islands', 'Spacing relative to island radius'),
    'archipelago_extent': spec(1., .3, 3., 'Ocean islands', 'Cluster footprint multiplier'),
    'volcanic_island_weight': spec(1., 0., 5., 'Ocean islands', 'Relative chance of volcanic island chains'),
    'atoll_weight': spec(1., 0., 5., 'Ocean islands', 'Relative chance of reef islands and atolls'),
    'continental_island_weight': spec(1., 0., 5., 'Ocean islands', 'Relative chance of continental fragments'),
    'cold_island_weight': spec(1., 0., 5., 'Ocean islands', 'Relative chance of cold archipelagos'),
    'sky_clusters': spec(0, 0, 0, 'Sky', 'Candidate elevated archipelagos', 'clusters'),
    'sky_occurrence': spec(0., 0., 0., 'Sky', 'Probability a magically supported cluster manifests'),
    'sky_altitude': spec(450., 100., 2500., 'Sky', 'Island altitude above local ground or sea', 'm'),
    'sky_radius': spec(180., 40., 600., 'Sky', 'Typical independent island surface radius', 'm'),
    'sea_reach': spec(6000., 100., 50000., 'Transport', 'Maximum navigable sea route length', 'm'),
    'air_reach': spec(4500., 100., 50000., 'Transport', 'Maximum air route length', 'm'),
    'sea_draft': spec(1., .1, 10., 'Transport', 'Minimum navigable water depth', 'm'),
    'sea_capacity': spec(8., 0., 100., 'Transport', 'Monthly sea shipment ceiling', 'food units/month'),
    'air_capacity': spec(2., 0., 100., 'Transport', 'Monthly air shipment ceiling', 'food units/month'),
    'fish_productivity': spec(60., 0., 200., 'Coasts', 'Annual productive marine food yield', 'food units/km²/year'),
    'fishing_reach': spec(700., 50., 4000., 'Coasts', 'Ordinary coastal vessel harvesting reach', 'm'),
    'coastal_hamlets': spec(2, 0, 4, 'Coasts', 'Maximum additional coastal support hamlets per city', 'hamlets'),
    'salinity': spec(.65, 0., 1., 'Coasts', 'Arid lake salinization strength'),
    'seasonality': spec(1., 0., 2., 'Cold', 'Latitude-dependent temperature seasonality'),
    'ice_accumulation': spec(.5, 0., 1., 'Cold', 'Moisture required for persistent land ice'),
}
for name in NETWORKS:
    for suffix, definition in {
        'occurrence': spec(1., 0., 1., name.title(), 'Probability this magical network manifests'),
        'nodes': spec(8, 3, 24, name.title(), 'Independent ley node count', 'nodes'),
        'width': spec(110., 10., 2000., name.title(), 'Gaussian influence reach', 'm'),
        'strength': spec(.45 if name in ('umbral','infernal') else .7, 0., 2., name.title(), 'Magical influence amplitude'),
        'instability': spec(.65 if name == 'infernal' else .2, 0., 1., name.title(), 'Instability independent of density'),
        'variation': spec(0, 0, 4294967295, name.title(), 'Independent network seed variation', 'seed'),
    }.items():
        OPTIONS[name+'_'+suffix] = definition
for name in ZONES:
    OPTIONS[name+'_occurrence'] = spec(.55, 0., 1., 'Regions', name.replace('_',' ')+' manifestation probability')
    OPTIONS[name+'_extent'] = spec(.22, .04, .8, 'Regions', name.replace('_',' ')+' angular influence radius', 'radians')
    OPTIONS[name+'_intensity'] = spec(.8, 0., 1., 'Regions', name.replace('_',' ')+' intensity')


@lru_cache(maxsize=64)
def validate_options(raw, version=3):
    if type(version) is not int or version not in (0,3):raise ValueError('Retired world options version')
    definitions = OPTIONS
    try:
        values = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError('world_options must be a JSON object') from exc
    if not isinstance(values, dict) or set(values)-set(definitions):
        raise ValueError('Unknown world option')
    result = {key: item['default'] for key,item in definitions.items()}
    for key,value in values.items():
        s=definitions[key]
        if type(value) not in (int,float) or not math.isfinite(value) or not s['min']<=value<=s['max']:
            raise ValueError(f'{key} must be {s["min"]}..{s["max"]}')
        if s['type']=='integer' and type(value) is not int:
            raise ValueError(f'{key} must be an integer')
        result[key]=value
    if sum(result[k] for k in ('volcanic_island_weight','atoll_weight','continental_island_weight','cold_island_weight'))<=0:
        raise ValueError('At least one ocean island character weight must be positive')
    return result


def options(cfg):
    return validate_options(cfg.world_options, cfg.world_recipe)


def default_config(version=3):
    if type(version) is not int or version != 3:raise ValueError('Retired recipe; regenerate with recipe_version 3')
    from .terrain_lab import Config
    return Config(world_recipe=version, phase=16 if version==3 else 9, shape='globe', tectonics=1, auto_parameters=0,
                  population_profile='mixed', amplitude=1100., wavelength=4300.,
                  magic_instability=.45, belt_width=.08, settlement_count=24)


def registry(version=3):
    cfg=asdict(default_config(version))
    inactive={'world_recipe','world_options','auto_parameters','ley_nodes','ley_width','magic_instability',
              'extent','depth','width','meander','urban_food_demand','human_adaptation'}
    result={k:dict(default=v,group='World',description=k.replace('_',' '),
                   type='integer' if type(v) is int else 'number' if type(v) is float else 'string',units='')
            for k,v in cfg.items() if k not in inactive}
    for key,choices in {'world_size':['small','medium','large'], 'shape':['globe'],
                        'population_profile':['mixed',*civilization_ids()]}.items():
        result[key]['choices']=choices
    result['population_profile']['choice_labels']={p['id']:p['name'] for p in profile_options()}
    bounds={'seed':(0,4294967295),'size':(3,257),'phase':(1,16 if version==3 else 9),'tectonics':(1,1),'magic_enabled':(0,1),
            'plate_count':(3,48),'layout_variation':(0,4294967295),'detail_variation':(0,4294967295),
            'crust_bias':(-1,1),'belt_width':(.01,.3),'mountain_detail':(0,1),'temperature_offset':(-40,40),
            'moisture_bias':(-1,1),'wind_bearing':(0,360),'rain_passes':(1,128),'rain_strength':(0,3),
            'erosion_passes':(0,40),'erosion_strength':(0,1),'ley_nodes':(3,24),'ley_width':(10,2000),
            'magic_instability':(0,1),'human_magic_limit':(0,1),'college_count':(0,12),
            'hamlets_per_core':(0,8),'fortress_count':(0,1024),'settlement_count':(0,24),
            'support_reach':(100,10000),'culture_link_cost':(1,100000),'urban_food_demand':(0,10000),
            'human_adaptation':(0,1),'settlement_spacing':(10,10000),'stubbornness':(0,1),
            'road_max_grade':(.01,1),'bridge_cost':(0,10000),'river_threshold_km2':(.001,100),
            'world_scale':(.001,1000),'globe_radius':(.01,1e7),'extent':(.01,1e7),
            'amplitude':(0,1e7),'wavelength':(.01,1e7),'depth':(0,1e7),'width':(.01,1e7),
            'meander':(0,1e7),'radius':(.01,1e7),'tectonic_relief':(0,1e7),'sea_level':(-1e7,1e7),
            'ridge':(0,1),'octaves':(1,10),'orogeny':(0,20)}
    for key,(low,high) in bounds.items():
        if key in result:result[key].update(min=low,max=high)
    for group,keys in {'Terrain':'plate_count layout_variation detail_variation crust_bias belt_width tectonic_relief mountain_detail orogeny sea_level amplitude wavelength octaves ridge radius world_scale',
                       'Climate':'temperature_offset moisture_bias wind_bearing rain_passes rain_strength',
                       'Drainage':'erosion_passes erosion_strength river_threshold_km2',
                       'Communities':'population_profile human_magic_limit college_count hamlets_per_core fortress_count support_reach culture_link_cost settlement_count settlement_spacing stubbornness road_max_grade bridge_cost'}.items():
        for key in keys.split():result[key]['group']=group
    result['settlement_count']['description']='Maximum surface cities; actual counts require habitat and productive capacity'
    result['fortress_count']['description']='Maximum route-defence fortresses; road length, crossings and city count ask for fewer unless this is lowered'
    result.update(OPTIONS)
    return result


def generate_request(body):
    from .terrain_lab import Config, generate
    if not isinstance(body,dict) or set(body)-{'seed','recipe_version','overrides'}:
        raise ValueError('Expected seed, recipe_version and optional overrides')
    if type(body.get('recipe_version',3)) is not int or body.get('recipe_version',3) != 3:
        raise ValueError('Retired or unsupported recipe_version; regenerate with recipe_version 3')
    version=body.get('recipe_version',3)
    option_defs=OPTIONS
    seed=body.get('seed',42)
    if type(seed) is not int or not 0<=seed<2**32:raise ValueError('Invalid uint32 seed')
    overrides=body.get('overrides',{})
    if not isinstance(overrides,dict) or set(overrides)-set(registry(version)):raise ValueError('Unknown override')
    if 'seed' in overrides:raise ValueError('Supply seed at the top level, not inside overrides')
    raw=asdict(default_config(version)); extra={}; definitions=registry(version)
    for key,value in overrides.items():
        definition=definitions[key]
        kind=definition['type']
        if kind=='string':
            if not isinstance(value,str):raise ValueError(f'{key} must be text')
            if 'choices' in definition and value not in definition['choices']:raise ValueError(f'Invalid {key}')
        else:
            if type(value) not in (int,float) or not math.isfinite(value):raise ValueError(f'{key} must be finite numeric')
            if kind=='integer' and type(value) is not int:raise ValueError(f'{key} must be an integer')
            if not definition.get('min',-math.inf)<=value<=definition.get('max',math.inf):raise ValueError(f'{key} outside allowed range')
        if key in option_defs:extra[key]=value
        else:raw[key]=value
    raw['seed']=seed
    if 'globe_radius' not in overrides:raw['globe_radius']=10000*{'small':1,'medium':2,'large':3}.get(raw['world_size'],1)
    # Explicit requests for stronger regions bias prerequisites. Direct prerequisite
    # overrides always win, and the original requested overrides remain auditable.
    biases={}
    prerequisites={'draconic':('mountain_abundance',.6),'demonic':('infernal_strength',.8),
                   'haunted_sands':('umbral_strength',.8),'steampunk':('metal_abundance',.7),
                   'dead_sea':('salinity',.6),'starlight_lakes':('weave_strength',.6),
                   'pirate':('archipelago_occurrence',.4),'red_sands':('moisture_bias',-.5)}
    for zone,(target,gain) in prerequisites.items():
        delta=max([float(overrides[k])-OPTIONS[k]['default'] for k in (zone+'_occurrence',zone+'_intensity') if k in overrides]+[0.])
        if delta>0 and target not in overrides:
            s=definitions[target];value=max(s['min'],min(s['max'],s['default']+delta*gain))
            if target in option_defs:extra[target]=value
            else:raw[target]=value
            biases[target]={'value':value,'source':zone+' request biases suitable conditions; placement remains conditional'}
    if raw['shape']!='globe' or raw['tectonics']!=1:raise ValueError('World recipe requires a tectonic globe')
    if type(raw['size']) is not int or raw['size']>257:raise ValueError('Interactive grid maximum is 257')
    raw['world_options']=json.dumps(extra,sort_keys=True)
    cfg=Config(**raw)
    result=generate(cfg)
    result['recipe']={'version':version,'seed':seed,'overrides':overrides,
                      'resolved':{**asdict(cfg),**options(cfg)},'parameters':registry(version),
                      'provenance':{k:'override' if k in overrides else 'default' for k in registry(version)}}
    result['recipe']['biases']=biases
    for key,item in biases.items():result['recipe']['provenance'][key]=item['source']
    if 'globe_radius' not in overrides and raw['world_size']!='small':result['recipe']['provenance']['globe_radius']='world_size preset'
    result['recipe']['provenance']['seed']='request'
    return result
