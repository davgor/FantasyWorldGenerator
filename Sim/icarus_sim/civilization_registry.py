"""Validated access to linked civilization and building authoring registries."""
import copy
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
import re

REGISTRY_PATH=Path(__file__).with_name('civilizations.json')
BUILDING_SECTIONS=('building_packs','layout_profiles','structure_blocks','housing_profiles')
CITY_BLOCKS=('small_city','medium_city','capital_city')
HAMLET_BLOCK='hamlet'
PLACEMENT_CONDITIONS={'usable_groundwater','water_collection_or_delivery','navigable_shore',
    'flowing_water','reliable_wind','ore_and_fuel_supply','food_surplus','working_animals',
    'clay_and_fuel_supply','medicinal_supply','clear_sky_view','isolation_access',
    'route_crossing','grade_change','retention_needed','defended_perimeter',
    'farming_support','resource_support'}
STAFF_LEVELS=('minimum','target','maximum')


def _validate_staffing(staff):
    if set(staff)!={'basis','housing_location','roles','notes'} or staff['basis']!='distinct_people_all_shifts':
        raise ValueError('Invalid staffing basis')
    if staff['housing_location'] not in ('city','hinterland'):raise ValueError('Invalid worker housing location')
    if not isinstance(staff['notes'],str) or not staff['notes']:raise ValueError('Missing staffing notes')
    if not isinstance(staff['roles'],list):raise ValueError('Invalid staffing roles')
    seen=set()
    for role in staff['roles']:
        if set(role)!={'role',*STAFF_LEVELS} or not isinstance(role['role'],str) or not role['role'] or role['role'] in seen:
            raise ValueError('Invalid or duplicate staffing role')
        seen.add(role['role'])
        values=[role[k] for k in STAFF_LEVELS]
        if any(type(v) is not int or not 0<=v<=10000 for v in values) or values!=sorted(values) or values[-1]==0:
            raise ValueError('Invalid staffing range')


def staffing_totals(staff, count):
    """Count unique roster posts, assuming each post has its own resident worker."""
    _validate_staffing(staff)
    if type(count) is not int or not 0<=count<=10000:raise ValueError('Invalid staffing instance count')
    workers={level:count*sum(role[level] for role in staff['roles']) for level in STAFF_LEVELS}
    return {'workers':workers,
            'city_worker_beds':{k:v if staff['housing_location']=='city' else 0 for k,v in workers.items()},
            'hinterland_worker_beds':{k:v if staff['housing_location']=='hinterland' else 0 for k,v in workers.items()}}


def _validate_settlement_blocks(entity, libraries, tiers, label):
    structures={s['id']:s for key in entity['buildings']['structure_block_ids']
                for block in libraries[key]['blocks'] for s in block['structures']}
    for tier in tiers:
        plan=entity[tier]
        if plan['status']!='preconfigured_design' or plan['housing_status']!='deferred':
            raise ValueError('Unsupported '+label+' plan status')
        for group in ('buildings','infrastructure'):
            entries=plan[group]
            if not isinstance(entries,list) or not entries:raise ValueError('Empty '+label+' plan group')
            seen=set()
            for entry in entries:
                sid=entry['structure_id']
                if sid not in structures or sid in seen:raise ValueError('Unknown or duplicate '+label+' structure')
                seen.add(sid);structure=structures[sid]
                if 'staffing' in entry:_validate_staffing(entry['staffing'])
                if group=='infrastructure' and entry.get('staffing',structure['staffing'])['roles']:
                    raise ValueError('Linear infrastructure uses shared service crews')
                if structure['module_family']=='housing':raise ValueError('Housing is deferred')
                if not isinstance(entry['placement_conditions'],list) or not set(entry['placement_conditions'])<=PLACEMENT_CONDITIONS:
                    raise ValueError('Invalid '+label+' placement condition')
                if group=='buildings':
                    if structure['geometry_type']=='linear_segment':raise ValueError('Linear structure needs route sizing')
                    if type(entry['count']) is not int or not 1<=entry['count']<=10000:raise ValueError('Invalid '+label+' building count')
                    if not isinstance(entry['name'],str) or not entry['name'].strip():raise ValueError('Missing '+label+' building name')
                elif structure['geometry_type']!='linear_segment' or entry['quantity_mode']!='fit_route_or_perimeter':
                    raise ValueError('Invalid '+label+' infrastructure sizing')
                size=structure['dimensions_m'];clear=structure['clearance_m'];plot=structure['plot_m']
                for value in (size['width'],size['depth'],plot['width'],plot['depth']):_number(value,.01,100000,'structure dimension')
                _number(size['height'],0,100000,'structure height')
                for side in ('left','right','front','rear'):_number(clear[side],0,100000,'structure clearance')
                if plot['width']!=size['width']+clear['left']+clear['right'] or plot['depth']!=size['depth']+clear['front']+clear['rear']:
                    raise ValueError(label.capitalize()+' structure plot does not include its clearances')


def _validate_city_blocks(entity, libraries):
    _validate_settlement_blocks(entity, libraries, CITY_BLOCKS, 'city')


def _validate_hamlet_block(entity, libraries):
    _validate_settlement_blocks(entity, libraries, (HAMLET_BLOCK,), 'hamlet')


def _finite(value):
    if isinstance(value,dict):
        for child in value.values():_finite(child)
    elif isinstance(value,list):
        for child in value:_finite(child)
    elif isinstance(value,float) and not math.isfinite(value):raise ValueError('Registry numbers must be finite')


def _number(value,low,high,label,nullable=False):
    if nullable and value is None:return
    if type(value) not in (int,float) or not math.isfinite(value) or not low<=value<=high:
        raise ValueError('Invalid registry '+label)


def validate_registry(data):
    from .terrain_profiles import validate_profile,validate_habitat
    if not isinstance(data,dict) or data.get('schema')!='fantasy-world-generator.civilization-registry' or type(data.get('schema_version')) is not int or data.get('schema_version')!=6:
        raise ValueError('Unsupported civilization registry schema')
    if type(data.get('revision')) is not int or data['revision']<1:raise ValueError('Invalid registry revision')
    _finite(data)
    try:
        entities=data['entities'];configs=data['configurations']
        _number(data['founding_rules']['years_per_round'],1,10000,'years per founding round')
        _number(data['founding_rules']['diaspora_interval_years'],1,100000,'diaspora interval')
        if data['founding_rules']['diaspora_interval_years']%data['founding_rules']['years_per_round']:raise ValueError('Diaspora interval must align with founding rounds')
        if type(data['founding_rules']['diaspora_bonus_per_parent']) is not int or data['founding_rules']['diaspora_bonus_per_parent'] not in (0,1):raise ValueError('Diaspora bonus must be zero or one')
        _number(data['founding_rules']['origin_min_separation_degrees'],0,180,'origin angular separation')
        parents=data['parent_races']
        if not isinstance(parents,dict) or not parents:raise ValueError('Missing parent race blocks')
        for key,parent in parents.items():
            _number(parent['founding_participation_percent'],0,100,'founding participation percent')
            if not re.fullmatch('[a-z][a-z0-9_]*',key) or not isinstance(parent.get('name'),str) or not parent['name']:raise ValueError('Invalid parent race')
        for housing_key in ('worker_house','worker_apartment','hamlet_house'):
            house=data['housing_profiles'][housing_key]
            if house['id']!='building.'+housing_key or type(house['worker_beds']) is not int or not 1<=house['worker_beds']<=32:
                raise ValueError('Invalid housing capacity')
            for key in ('width','depth'):
                _number(house['dimensions_m'][key],1,100,'housing footprint')
                _number(house['plot_m'][key],house['dimensions_m'][key],200,'housing plot')
            _number(house['dimensions_m']['height'],1,100,'housing height')
        houses=data['housing_profiles']
        if houses['worker_apartment']['plot_m']!=houses['worker_house']['plot_m'] or houses['worker_apartment']['worker_beds']<=houses['worker_house']['worker_beds']:
            raise ValueError('Apartment densification requires the same plot and higher capacity')
        for library in data['structure_blocks'].values():
            for block in library['blocks']:
                for structure in block['structures']:
                    _validate_staffing(structure['staffing'])
                    if structure['geometry_type']=='linear_segment' and structure['staffing']['roles']:
                        raise ValueError('Linear infrastructure uses shared service crews')
        if not isinstance(entities,dict) or not entities or len(entities)>128:raise ValueError('Expected 1..128 civilization entities')
        if set(entities)&set(configs):raise ValueError('Entity/configuration IDs collide')
        for key in [*entities,*configs]:
            if not re.fullmatch('[a-z][a-z0-9_]*',key):raise ValueError('Invalid civilization ID')
        if data['defaults']['profile_id'] not in entities or data['defaults']['aggregate_profile_id'] not in configs:
            raise ValueError('Invalid registry default')
        classes=data['city_classification']
        _number(classes['medium_suitability_min'],0,1,'medium threshold')
        if classes['capital_policy']!='retain_founding_capital_else_highest_suitability_then_lowest_node':raise ValueError('Unsupported capital policy')
        packs=data['building_packs']['packs'];layouts=data['layout_profiles']['profiles']
        pack_index={p['id']:{o['id'] for o in p['building_options']} for p in packs}
        layout_index={p['id']:set(p['features']) for p in layouts}
        if len(pack_index)!=len(packs) or len(layout_index)!=len(layouts):raise ValueError('Duplicate library ID')
        if data['building_packs']['fallback_pack_id'] not in pack_index or data['layout_profiles']['fallback_profile_id'] not in layout_index:
            raise ValueError('Invalid library fallback')
        for pack in packs:
            if len({o['id'] for o in pack['building_options']})!=len(pack['building_options']):raise ValueError('Duplicate building option')
            if pack.get('layout_profile_id') is not None and pack['layout_profile_id'] not in layout_index:raise ValueError('Unknown pack layout')
        for key,entity in entities.items():
            if set(entity)!={'parent_race_id','population','settlement','economy','sky','presentation','buildings',*CITY_BLOCKS,HAMLET_BLOCK}:raise ValueError('Incomplete civilization entity')
            if entity['parent_race_id'] not in parents:raise ValueError('Unknown parent race')
            population=validate_profile(entity['population'],key)
            if population['civilization']['kind']!='entity':raise ValueError('Entity must declare entity kind')
            rules=entity['settlement'];economy=entity['economy']
            validate_habitat(rules['surface_habitat']);validate_habitat(rules['world_habitat'])
            _number(rules['freshwater_reach_multiplier'],0,100,'freshwater multiplier',True)
            if type(rules['support_outside_habitat']) is not bool:raise ValueError('Invalid support policy')
            for field in ('coastal_score_weight','resource_score_weight'):_number(rules[field],0,2,field)
            if rules['reason'] is not None and not isinstance(rules['reason'],str):raise ValueError('Invalid site reason')
            _number(economy['winter_fishing_fraction'],0,1,'winter fishing fraction')
            _number(economy['fishing_reach_multiplier'],.01,10,'fishing reach')
            for field in ('industrial_resource_min','air_terminal_resource_min'):_number(economy[field],0,1,field,True)
            _number(entity['sky']['score_bias'],-100,100,'sky bias')
            _number(entity['sky']['moisture_score_weight'],-100,100,'sky moisture')
            for field in ('map_color_rgb','wall_color_rgb','roof_color_rgb'):
                color=entity['presentation'][field]
                if not isinstance(color,list) or len(color)!=3 or any(type(v) is not int or not 0<=v<=255 for v in color):raise ValueError('Invalid display color')
            if type(entity['presentation']['outpost_colors']) is not bool:raise ValueError('Invalid outpost display flag')
            buildings=entity['buildings']
            for pack,options in buildings['packs'].items():
                if pack not in pack_index or not isinstance(options,list) or len(options)!=len(set(options)) or not set(options)<=pack_index[pack]:raise ValueError('Unknown or duplicate building reference')
            if data['building_packs']['fallback_pack_id'] not in buildings['packs']:raise ValueError('Entity needs an explicit fallback pack binding')
            for layout,features in buildings['layout_features'].items():
                if layout not in layout_index or not set(features)<=layout_index[layout]:raise ValueError('Unknown layout feature reference')
            if not set(buildings['structure_block_ids'])<=set(data['structure_blocks']):raise ValueError('Unknown structure block library')
            if 'rural' not in buildings['structure_block_ids']:raise ValueError('Entity needs the rural hamlet structure library')
            block=population['civilization']['structure_blocks']
            if block is not None and block not in buildings['structure_block_ids']:raise ValueError('Structure block identity disagrees with bindings')
            _validate_city_blocks(entity,data['structure_blocks'])
            _validate_hamlet_block(entity,data['structure_blocks'])
        for key,profile in configs.items():
            if validate_profile(profile,key)['civilization']['kind']!='aggregate':raise ValueError('Invalid aggregate configuration')
    except (KeyError,TypeError,AttributeError) as exc:
        raise ValueError('Malformed civilization registry: '+str(exc)) from exc
    return data


def _unique_object(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise ValueError('Duplicate registry key: '+key)
        result[key]=value
    return result


@lru_cache(maxsize=8)
def _read(path,mtime_ns,size):
    return json.loads(Path(path).read_text(encoding='utf-8'),object_pairs_hook=_unique_object)


@lru_cache(maxsize=8)
def _resolve(path,mtime_ns,size,building_path,building_mtime_ns,building_size):
    raw=_read(path,mtime_ns,size)
    if any(key in raw for key in (*BUILDING_SECTIONS,'building_catalogue_metadata')):
        raise ValueError('Building definitions must live in the linked buildings.json')
    buildings=_read(building_path,building_mtime_ns,building_size)
    if not isinstance(buildings,dict) or buildings.get('schema')!='fantasy-world-generator.building-registry' or type(buildings.get('schema_version')) is not int or buildings['schema_version']!=2:
        raise ValueError('Unsupported building registry schema')
    if type(buildings.get('revision')) is not int or buildings['revision']<1:
        raise ValueError('Invalid building registry revision')
    if not all(key in buildings for key in BUILDING_SECTIONS):raise ValueError('Incomplete building registry')
    ids=[s['id'] for library in buildings['structure_blocks'].values() for block in library['blocks'] for s in block['structures']]
    if len(ids)!=len(set(ids)) or any(not re.fullmatch(r'building\.[a-z][a-z0-9_]*',sid) for sid in ids):
        raise ValueError('Invalid or duplicate neutral building ID')
    if raw.get('schema_version')!=6 or 'entities' in raw:
        raise ValueError('Expected schema 5 with civilizations nested in parent race blocks')
    data=copy.deepcopy(raw)
    entities={};parents={}
    try:
        for race,block in data['parent_races'].items():
            parents[race]={'name':block['name'],'founding_participation_percent':block['founding_participation_percent']}
            for key,entity in block['civilizations'].items():
                if key in entities or 'parent_race_id' in entity:raise ValueError('Duplicate civilization or redundant parent race')
                entities[key]={**entity,'parent_race_id':race}
        order=data['civilization_order']
        if not isinstance(order,list) or len(order)!=len(set(order)) or set(order)!=set(entities):raise ValueError('Civilization order must name every nested entity exactly once')
        data['entities']={key:entities[key] for key in order}
        data['parent_races']=parents
    except (KeyError,TypeError,AttributeError) as exc:
        raise ValueError('Malformed parent race blocks') from exc
    data.update({key:copy.deepcopy(buildings[key]) for key in BUILDING_SECTIONS})
    data['building_catalogue_metadata']={key:copy.deepcopy(value) for key,value in buildings.items() if key not in BUILDING_SECTIONS}
    return validate_registry(data)


def _document():
    try:
        stat=REGISTRY_PATH.stat();path=str(REGISTRY_PATH.resolve())
        raw=_read(path,stat.st_mtime_ns,stat.st_size)
        if raw.get('building_catalogue')!={'path':'buildings.json','schema_version':2}:
            raise ValueError('Expected a sibling buildings.json registry link with schema version 2')
        building_path=REGISTRY_PATH.with_name('buildings.json');building_stat=building_path.stat()
        return _resolve(path,stat.st_mtime_ns,stat.st_size,str(building_path.resolve()),building_stat.st_mtime_ns,building_stat.st_size)
    except (OSError,KeyError,TypeError,AttributeError) as exc:
        raise ValueError('Cannot load linked civilization/building registries: '+str(exc)) from exc


def load_registry():return copy.deepcopy(_document())


def section(name):return copy.deepcopy(_document()[name])


def entity_rules(entity_id):return copy.deepcopy(_document()['entities'][entity_id])


def _expand_settlement_plan(entity_id, block_name, block_key):
    doc=_document()
    if entity_id not in doc['entities']:raise ValueError('Unknown civilization')
    entity=doc['entities'][entity_id]
    structures={s['id']:s for key in entity['buildings']['structure_block_ids']
                for block in doc['structure_blocks'][key]['blocks'] for s in block['structures']}
    plan=copy.deepcopy(entity[block_name])
    for group in ('buildings','infrastructure'):
        plan[group]=[{**copy.deepcopy(structures[row['structure_id']]),**row} for row in plan[group]]
    summary={group:{metric:{level:0 for level in STAFF_LEVELS}
                    for metric in ('workers','city_worker_beds','hinterland_worker_beds')}
             for group in ('unconditional','conditional','all_configured')}
    for row in plan['buildings']:
        row['staffing_totals']=staffing_totals(row['staffing'],row['count'])
        group='conditional' if row['placement_conditions'] else 'unconditional'
        for metric,levels in row['staffing_totals'].items():
            for level,value in levels.items():
                summary[group][metric][level]+=value
                summary['all_configured'][metric][level]+=value
    summary.update(total_residents=None,houses_required=None,
                   basis='One distinct resident worker per filled roster post; household members and housing occupancy not yet modeled.')
    plan['staffing_summary']=summary
    plan.update(civilization_id=entity_id,unit='metres',runtime_placement_enabled=False)
    plan[block_key]=block_name
    return plan


def city_plan(entity_id, city_block):
    """Resolve an independent size preset into measured, unplaced requirements."""
    if city_block not in CITY_BLOCKS:raise ValueError('Unknown city size block')
    return _expand_settlement_plan(entity_id, city_block, 'city_block')


def hamlet_plan(entity_id):
    """Resolve the rural hamlet preset into measured, unplaced requirements."""
    return _expand_settlement_plan(entity_id, HAMLET_BLOCK, 'settlement_block')


def default_profile_id():return _document()['defaults']['profile_id']


def registry_identity():
    doc=_document()
    canonical=json.dumps(doc,ensure_ascii=False,separators=(',',':')).encode('utf-8')
    return {'schema_version':doc['schema_version'],'revision':doc['revision'],'sha256':hashlib.sha256(canonical).hexdigest()}


def population_profiles():
    doc=_document()
    return copy.deepcopy({**{key:entity['population'] for key,entity in doc['entities'].items()},**doc['configurations']})


def building_pack_data():
    doc=_document();data=copy.deepcopy(doc['building_packs'])
    for pack in data['packs']:
        pack['criteria']['population_profiles']=[key for key,e in doc['entities'].items() if pack['id'] in e['buildings']['packs']]
        for option in pack['building_options']:
            allowed=[key for key,e in doc['entities'].items() if option['id'] in e['buildings']['packs'].get(pack['id'],[])]
            # Empty profiles mean unrestricted in the legacy layout engine. Remove
            # truly unreachable options instead of accidentally enabling them.
            option['profiles']=allowed
        pack['building_options']=[o for o in pack['building_options'] if o['profiles']]
    return data


def layout_profile_data():
    doc=_document();data=copy.deepcopy(doc['layout_profiles'])
    for layout in data['profiles']:
        for name,feature in layout['features'].items():
            if not isinstance(feature,dict):
                feature={'base':feature}
                layout['features'][name]=feature
            feature['profiles']=[key for key,e in doc['entities'].items() if name in e['buildings']['layout_features'].get(layout['id'],[])]
    return data
