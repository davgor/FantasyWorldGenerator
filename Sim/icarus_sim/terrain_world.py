"""Versioned, partial world recipes. No semantic prompt interpretation or engine I/O."""
import json
import math
from dataclasses import asdict
from functools import lru_cache

NETWORKS = ('weave', 'umbral', 'infernal', 'holy', 'primordial')
ZONES = ('demonic', 'draconic', 'pirate', 'steampunk', 'witch_huts', 'red_sands',
         'dead_sea', 'starlight_lakes', 'haunted_sands', 'enchanted', 'fungal', 'crystal', 'haunted_marsh')


def spec(default, low, high, group, description, units='relative'):
    return dict(default=default, min=low, max=high, group=group,
                description=description, units=units, type='integer' if type(default) is int else 'number')


OPTIONS = {
    'nest_limit': spec(120, 0, 500, 'Beast nests', 'Maximum habitat anchors across species', 'anchors'),
    'nest_density': spec(1., 0., 3., 'Beast nests', 'Species occurrence multiplier; zero disables nests'),
    'nest_fantasy': spec(1., 0., 3., 'Beast nests', 'Fantasy species occurrence multiplier; zero leaves real animals'),
    'nest_per_species': spec(2, 1, 8, 'Beast nests', 'Maximum anchors per species', 'anchors'),
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
    'sky_clusters': spec(3, 0, 12, 'Sky', 'Candidate elevated archipelagos', 'clusters'),
    'sky_occurrence': spec(.7, 0., 1., 'Sky', 'Probability a magically supported cluster manifests'),
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
        'strength': spec(.7 if name == 'weave' else .45, 0., 2., name.title(), 'Magical influence amplitude'),
        'instability': spec(.65 if name == 'infernal' else .2, 0., 1., name.title(), 'Instability independent of density'),
        'variation': spec(0, 0, 4294967295, name.title(), 'Independent network seed variation', 'seed'),
    }.items():
        OPTIONS[name+'_'+suffix] = definition
for name in ZONES:
    OPTIONS[name+'_occurrence'] = spec(.55, 0., 1., 'Regions', name.replace('_',' ')+' manifestation probability')
    OPTIONS[name+'_extent'] = spec(.22, .04, .8, 'Regions', name.replace('_',' ')+' angular influence radius', 'radians')
    OPTIONS[name+'_intensity'] = spec(.8, 0., 1., 'Regions', name.replace('_',' ')+' intensity')


@lru_cache(maxsize=64)
def validate_options(raw):
    try:
        values = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError('world_options must be a JSON object') from exc
    if not isinstance(values, dict) or set(values)-set(OPTIONS):
        raise ValueError('Unknown world option')
    result = {key: item['default'] for key,item in OPTIONS.items()}
    for key,value in values.items():
        s=OPTIONS[key]
        if type(value) not in (int,float) or not math.isfinite(value) or not s['min']<=value<=s['max']:
            raise ValueError(f'{key} must be {s["min"]}..{s["max"]}')
        if s['type']=='integer' and type(value) is not int:
            raise ValueError(f'{key} must be an integer')
        result[key]=value
    if sum(result[k] for k in ('volcanic_island_weight','atoll_weight','continental_island_weight','cold_island_weight'))<=0:
        raise ValueError('At least one ocean island character weight must be positive')
    return result


def options(cfg):
    return validate_options(cfg.world_options)


def default_config():
    from .terrain_lab import Config
    return Config(world_recipe=1, shape='globe', tectonics=1, auto_parameters=0,
                  population_profile='mixed', amplitude=1100., wavelength=4300.,
                  magic_instability=.45, belt_width=.08, settlement_count=24)


def registry():
    cfg=asdict(default_config())
    inactive={'world_recipe','world_options','auto_parameters','ley_nodes','ley_width','magic_instability',
              'extent','depth','width','meander','urban_food_demand','human_adaptation'}
    result={k:dict(default=v,group='World',description=k.replace('_',' '),
                   type='integer' if type(v) is int else 'number' if type(v) is float else 'string',units='')
            for k,v in cfg.items() if k not in inactive}
    for key,choices in {'world_size':['small','medium','large'], 'shape':['globe'],
                        'population_profile':['mixed','human','dwarf','elf','gnome','tidekin']}.items():
        result[key]['choices']=choices
    bounds={'seed':(0,4294967295),'size':(3,257),'phase':(1,9),'tectonics':(1,1),'magic_enabled':(0,1),
            'plate_count':(3,48),'layout_variation':(0,4294967295),'detail_variation':(0,4294967295),
            'crust_bias':(-1,1),'belt_width':(.01,.3),'mountain_detail':(0,1),'temperature_offset':(-40,40),
            'moisture_bias':(-1,1),'wind_bearing':(0,360),'rain_passes':(1,128),'rain_strength':(0,3),
            'erosion_passes':(0,40),'erosion_strength':(0,1),'ley_nodes':(3,24),'ley_width':(10,2000),
            'magic_instability':(0,1),'human_magic_limit':(0,1),'college_count':(0,12),
            'hamlets_per_core':(0,8),'fortress_count':(0,24),'settlement_count':(0,24),
            'support_reach':(100,10000),'culture_link_cost':(1,100000),'urban_food_demand':(0,10000),
            'human_adaptation':(0,1),'settlement_spacing':(10,10000),'stubbornness':(0,1),
            'road_max_grade':(.01,1),'bridge_cost':(0,10000),'river_threshold_km2':(.001,100),
            'world_scale':(.001,1000),'globe_radius':(.01,1e7),'extent':(.01,1e7),
            'amplitude':(0,1e7),'wavelength':(.01,1e7),'depth':(0,1e7),'width':(.01,1e7),
            'meander':(0,1e7),'radius':(.01,1e7),'tectonic_relief':(0,1e7),'sea_level':(-1e7,1e7),
            'ridge':(0,1),'octaves':(1,10)}
    for key,(low,high) in bounds.items():
        if key in result:result[key].update(min=low,max=high)
    for group,keys in {'Terrain':'plate_count layout_variation detail_variation crust_bias belt_width tectonic_relief mountain_detail sea_level amplitude wavelength octaves ridge radius world_scale',
                       'Climate':'temperature_offset moisture_bias wind_bearing rain_passes rain_strength',
                       'Drainage':'erosion_passes erosion_strength river_threshold_km2',
                       'Communities':'population_profile human_magic_limit college_count hamlets_per_core fortress_count support_reach culture_link_cost settlement_count settlement_spacing stubbornness road_max_grade bridge_cost'}.items():
        for key in keys.split():result[key]['group']=group
    result['settlement_count']['description']='Maximum surface cities; actual counts require habitat and productive capacity'
    result.update(OPTIONS)
    return result


def generate_request(body):
    from .terrain_lab import Config, generate
    if not isinstance(body,dict) or set(body)-{'seed','recipe_version','overrides'}:
        raise ValueError('Expected seed, recipe_version and optional overrides')
    if type(body.get('recipe_version',1)) is not int or body.get('recipe_version',1)!=1:
        raise ValueError('Unsupported recipe_version')
    seed=body.get('seed',42)
    if type(seed) is not int or not 0<=seed<2**32:raise ValueError('Invalid uint32 seed')
    overrides=body.get('overrides',{})
    if not isinstance(overrides,dict) or set(overrides)-set(registry()):raise ValueError('Unknown override')
    if 'seed' in overrides:raise ValueError('Supply seed at the top level, not inside overrides')
    raw=asdict(default_config()); extra={}; definitions=registry()
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
        if key in OPTIONS:extra[key]=value
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
            if target in OPTIONS:extra[target]=value
            else:raw[target]=value
            biases[target]={'value':value,'source':zone+' request biases suitable conditions; placement remains conditional'}
    if raw['shape']!='globe' or raw['tectonics']!=1:raise ValueError('World recipe requires a tectonic globe')
    if type(raw['size']) is not int or raw['size']>257:raise ValueError('Interactive grid maximum is 257')
    raw['world_options']=json.dumps(extra,sort_keys=True)
    cfg=Config(**raw)
    result=generate(cfg)
    result['recipe']={'version':1,'seed':seed,'overrides':overrides,
                      'resolved':{**asdict(cfg),**options(cfg)},'parameters':registry(),
                      'provenance':{k:'override' if k in overrides else 'default' for k in registry()}}
    result['recipe']['biases']=biases
    for key,item in biases.items():result['recipe']['provenance'][key]=item['source']
    if 'globe_radius' not in overrides and raw['world_size']!='small':result['recipe']['provenance']['globe_radius']='world_size preset'
    result['recipe']['provenance']['seed']='request'
    return result
