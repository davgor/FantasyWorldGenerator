"""Validated population views of the master civilization registry."""
import json
import hashlib
import math
from .terrain_biome_catalogue import NATURAL_BIOMES, biome_catalogue

VARIANT_IDS = frozenset(b['id'] for b in biome_catalogue())

FIELDS=set('name description food_temperature_ideal minimum_founding_residents temperature_ideal temperature_tolerance slope_comfort site_slope_limit work_slope_limit road_grade_limit water_reach moisture_ideal water_weight slope_weight climate_weight moisture_weight resource_weight flood_penalty magic_penalty mutation_limit difficult_fraction food_temperature_tolerance food_slope_comfort food_moisture_ideal irrigation food_demand land_per_city_km2 support_multiplier college_slope_limit college_temperature_min college_temperature_max college_water_reach college_flood_limit college_suitability_min biome_preferences food_biome_multipliers magic_biome_preferences food_magic_biome_multipliers'.split())


def profiles():
    from .civilization_registry import population_profiles
    return population_profiles()


def validate_habitat(rule,depth=0):
    if not isinstance(rule,dict) or depth>8:raise ValueError('Invalid habitat rule')
    if not rule:return
    for operator in ('all','any'):
        if operator in rule:
            if set(rule)!={operator} or not isinstance(rule[operator],list) or not rule[operator]:raise ValueError('Invalid habitat combination')
            for child in rule[operator]:validate_habitat(child,depth+1)
            return
    if rule.get('field') not in ('biome','variant','temperature','moisture','maritime','landmass_area_m2','landmass_fraction','largest_landmass','resource','slope','height','tpi','coastal_support','abs_latitude'):
        raise ValueError('Unknown habitat field')
    if set(rule)-{'field','in','min','max','gt','equals'} or len(rule)<2:raise ValueError('Invalid habitat comparison')
    for key in ('min','max','gt'):
        if key in rule and (type(rule[key]) not in (int,float) or not math.isfinite(rule[key])):raise ValueError('Invalid habitat bound')
    if 'min' in rule and 'max' in rule and rule['min']>rule['max']:raise ValueError('Reversed habitat bounds')
    if 'in' in rule and (not isinstance(rule['in'],list) or not rule['in'] or any(not isinstance(v,str) and (type(v) not in (int,float,bool) or not math.isfinite(v)) for v in rule['in'])):
        raise ValueError('Invalid habitat membership')
    if 'equals' in rule and (type(rule['equals']) not in (int,float,bool) or not math.isfinite(rule['equals'])):raise ValueError('Invalid habitat equality')


def get_profile(profile_id):
    registry=profiles()
    if not isinstance(profile_id,str) or profile_id not in registry:raise ValueError('Unknown population profile')
    return validate_profile(registry[profile_id],profile_id)


def validate_profile(raw,profile_id):
    if set(raw)!=FIELDS|{'civilization'}:raise ValueError('Civilization requires a complete independent trait record')
    identity=raw['civilization']
    if not isinstance(identity,dict) or identity.get('kind') not in ('entity','aggregate'):
        raise ValueError('Invalid civilization identity')
    if set(identity)!={'kind','inspiration','environment','habitat','allocation_group','priority','structure_blocks'}:
        raise ValueError('Incomplete civilization identity')
    if type(identity['priority']) is not int or identity['priority']<0:raise ValueError('Invalid habitat priority')
    for key in ('inspiration','allocation_group','structure_blocks'):
        if identity[key] is not None and (not isinstance(identity[key],str) or not identity[key]):raise ValueError('Invalid civilization label')
    if not isinstance(identity['environment'],str) or not identity['environment']:raise ValueError('Missing civilization environment')
    validate_habitat(identity['habitat'])
    result={k:v for k,v in raw.items() if k!='civilization'};result['id']=profile_id
    for k,v in result.items():
        if k in ('name','description','id'):
            if not isinstance(v,str) or not v:raise ValueError('Invalid profile text')
        elif k in ('biome_preferences','food_biome_multipliers','magic_biome_preferences','food_magic_biome_multipliers'):
            if not isinstance(v,dict):raise ValueError('Invalid biome mapping')
            for biome,value in v.items():
                valid=isinstance(biome,str) and biome in VARIANT_IDS if 'magic_biome' in k else isinstance(biome,str) and biome.isdigit() and int(biome) in NATURAL_BIOMES
                if not valid or type(value) not in (int,float) or not math.isfinite(value):raise ValueError('Invalid biome trait')
                if not (-1<=value<=1 if k.endswith('preferences') else 0<=value<=2):raise ValueError('Invalid biome multiplier')
        elif type(v) not in (int,float) or not math.isfinite(v):raise ValueError('Invalid numeric profile trait')
    for k in ('temperature_tolerance','slope_comfort','site_slope_limit','work_slope_limit','water_reach',
              'food_temperature_tolerance','food_slope_comfort','land_per_city_km2','support_multiplier','college_water_reach'):
        if result[k]<=0:raise ValueError(f'{k} must be positive')
    for k in ('mutation_limit','difficult_fraction','irrigation','moisture_ideal','food_moisture_ideal','college_flood_limit','college_suitability_min'):
        if not 0<=result[k]<=1:raise ValueError(f'{k} must be 0..1')
    if result['food_moisture_ideal']==0 or not .01<=result['road_grade_limit']<=1:raise ValueError('Invalid profile reach or moisture')
    if result['college_temperature_min']>=result['college_temperature_max']:raise ValueError('Invalid college climate range')
    for k in ('water_weight','slope_weight','climate_weight','moisture_weight','resource_weight','flood_penalty','magic_penalty'):
        if not 0<=result[k]<=1:raise ValueError(f'{k} must be 0..1')
    for k in ('site_slope_limit','work_slope_limit','college_slope_limit','slope_comfort','food_slope_comfort'):
        if not 0<result[k]<90:raise ValueError(f'{k} must be between 0 and 90 degrees')
    if not 0<=result['food_demand']<=10000:raise ValueError('Food demand out of range')
    if not .01<=result['land_per_city_km2']<=1000 or not 0<result['support_multiplier']<=10:raise ValueError('Population footprint out of range')
    result['civilization']=identity
    if type(result['minimum_founding_residents']) is not int or not 1<=result['minimum_founding_residents']<=10000:raise ValueError('Invalid founding minimum')
    if not -100<=result['food_temperature_ideal']<=100:raise ValueError('Invalid food temperature ideal')
    result['schema_version']=4
    result['definition_hash']=hashlib.sha256(json.dumps(result,sort_keys=True).encode()).hexdigest()
    return result


def profile_options():return [{'id':key,'name':value['name']} for key,value in profiles().items()]


def civilization_ids():
    return tuple(key for key,value in profiles().items() if value['civilization']['kind']=='entity')


def biome_preference(profile, core_id, variant_id=None):
    """An exact magical state overrides its natural-core preference."""
    return profile['magic_biome_preferences'].get(variant_id, profile['biome_preferences'].get(str(core_id), 0))


def biome_food_multiplier(profile, core_id, variant_id=None):
    """Exact state food factor, before independent school-specific hazard losses."""
    return profile['food_magic_biome_multipliers'].get(variant_id, profile['food_biome_multipliers'].get(str(core_id), 1))
