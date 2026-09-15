"""Editable population templates; no profile may bypass world generation rules."""
import json
import hashlib
import math
from pathlib import Path

FIELDS=set('name description temperature_ideal temperature_tolerance slope_comfort site_slope_limit work_slope_limit road_grade_limit water_reach moisture_ideal water_weight slope_weight climate_weight moisture_weight resource_weight flood_penalty magic_penalty mutation_limit difficult_fraction food_temperature_tolerance food_slope_comfort food_moisture_ideal irrigation food_demand land_per_city_km2 support_multiplier college_slope_limit college_temperature_min college_temperature_max college_water_reach college_flood_limit college_suitability_min biome_preferences food_biome_multipliers'.split())


def profiles():
    return json.loads(Path(__file__).with_name('terrain_profiles.json').read_text(encoding='utf-8'))


def get_profile(profile_id):
    registry=profiles()
    if not isinstance(profile_id,str) or profile_id not in registry:raise ValueError('Unknown population profile')
    raw=registry[profile_id];base=registry['human']
    if set(base)!=FIELDS:raise ValueError('Human profile has missing or unknown traits')
    if raw.get('extends','human')!='human':raise ValueError('Profiles may extend only human')
    if set(raw)-set(base)-{'extends'}:raise ValueError('Unknown population trait')
    result=dict(base);result.update({k:v for k,v in raw.items() if k!='extends'});result['id']=profile_id
    for k,v in result.items():
        if k in ('name','description','id'):
            if not isinstance(v,str) or not v:raise ValueError('Invalid profile text')
        elif k in ('biome_preferences','food_biome_multipliers'):
            if not isinstance(v,dict):raise ValueError('Invalid biome mapping')
            for biome,value in v.items():
                if not biome.isdigit() or not 0<=int(biome)<=17 or type(value) not in (int,float) or not math.isfinite(value):raise ValueError('Invalid biome trait')
                if not (-1<=value<=1 if k=='biome_preferences' else 0<=value<=2):raise ValueError('Invalid biome multiplier')
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
    result['schema_version']=1
    result['definition_hash']=hashlib.sha256(json.dumps(result,sort_keys=True).encode()).hexdigest()
    return result


def profile_options():return [{'id':key,'name':value['name']} for key,value in profiles().items()]
