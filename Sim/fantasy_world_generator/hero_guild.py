"""Opt-in guild demand planning; never mutates generated cities or population."""
import copy
from importlib.resources import files
import json

from icarus_sim.civilization_registry import city_plan, section

MAX_COUNT = 1_000_000_000
REQUEST_FIELDS = {'civilization_id','city_block','population','visiting_heroes_requested',
                  'available_jobs','already_housed_resident_heroes','available_visitor_beds'}
POLICY_FIELDS = {'resident_rate_numerator','resident_rate_denominator','max_resident_heroes',
                 'max_visiting_heroes','party_size','max_active_parties','heroes_per_service_worker',
                 'max_additional_staff'}


def _exact(value, fields):
    if type(value) is not dict or set(value) != fields:
        raise ValueError('unexpected or missing guild planning fields')


def _count(value):
    if type(value) is not int or not 0 <= value <= MAX_COUNT:
        raise ValueError('guild counts must be bounded nonnegative integers')


def _policy(value):
    _exact(value,POLICY_FIELDS)
    for count in value.values(): _count(count)
    if (value['resident_rate_denominator'] == 0 or
        value['resident_rate_numerator'] > value['resident_rate_denominator'] or
        not 1 <= value['party_size'] <= 64 or value['heroes_per_service_worker'] == 0):
        raise ValueError('invalid guild rate or capacity')
    return copy.deepcopy(value)


def _pairs(items):
    result={}
    for key,value in items:
        if key in result: raise ValueError('duplicate guild policy key')
        result[key]=value
    return result


def policy_document():
    document=json.loads(files(__package__).joinpath('hero_guild_policies.json').read_text(encoding='utf-8'),object_pairs_hook=_pairs)
    _exact(document,{'schema','schema_version','revision','policies'})
    if (document['schema'] != 'fantasy-world-generator.hero-guild-policies' or
        type(document['schema_version']) is not int or document['schema_version'] != 1):
        raise ValueError('unsupported guild policy version')
    _count(document['revision'])
    if document['revision'] == 0: raise ValueError('policy revision must be positive')
    policies=document['policies']
    if type(policies) is not dict or set(policies) != set(section('entities')):
        raise ValueError('guild policies must cover exactly the current civilizations')
    for policy in policies.values(): _policy(policy)
    return document


def calculate(request, policy=None):
    _exact(request,REQUEST_FIELDS)
    if type(request['civilization_id']) is not str or type(request['city_block']) is not str:
        raise ValueError('civilization and city block must be strings')
    for key in REQUEST_FIELDS-{'civilization_id','city_block'}: _count(request[key])
    # Resolve the selected roster so its two workers are never added a second time.
    plan=city_plan(request['civilization_id'],request['city_block'])
    halls=[row for row in plan['buildings'] if row['structure_id']=='building.guildhall']
    if len(halls) != 1 or halls[0]['count'] != 1 or halls[0]['placement_conditions']:
        raise ValueError('expected one unconditional core guild hall')
    staff=halls[0]['staffing']
    roles={row['role']:row for row in staff['roles']}
    if (staff['housing_location'] != 'city' or set(roles) != {'cook','bartender'} or
        any(row[level] != 1 for row in roles.values() for level in ('minimum','target','maximum'))):
        raise ValueError('guild model requires the fixed cook and bartender roster')
    if policy is None:
        document=policy_document()
        selected=_policy(document['policies'][request['civilization_id']])
        source='packaged'; revision=document['revision']
    else:
        selected=_policy(policy); source='caller'; revision=None
    resident=min(selected['max_resident_heroes'],request['population']*selected['resident_rate_numerator']//selected['resident_rate_denominator'])
    if request['already_housed_resident_heroes'] > resident:
        raise ValueError('housed resident heroes exceed calculated membership')
    visiting=min(request['visiting_heroes_requested'],selected['max_visiting_heroes'])
    present=resident+visiting
    parties=min(present//selected['party_size'],selected['max_active_parties'],request['available_jobs'])
    per_worker=selected['heroes_per_service_worker']
    needed=(present+per_worker-1)//per_worker
    additional=min(selected['max_additional_staff'],max(0,needed-2))
    resident_beds=resident-request['already_housed_resident_heroes']
    return dict(schema='fantasy-world-generator.hero-guild-plan',schema_version=1,
                policy_source=source,policy_revision=revision,policy=selected,request=copy.deepcopy(request),
                heroes=dict(resident=resident,visiting=visiting,present=present,
                            unserved_visitors=request['visiting_heroes_requested']-visiting),
                activity=dict(active_parties=parties,active_heroes=parties*selected['party_size'],
                              inactive_heroes=present-parties*selected['party_size']),
                service=dict(existing_workers_already_counted=2,additional_workers=additional,
                             total_workers=2+additional,unserved_heroes=max(0,present-(2+additional)*per_worker)),
                accommodation=dict(resident_hero_beds_needed=resident_beds,new_staff_beds=additional,
                                   additional_permanent_beds=resident_beds+additional,
                                   temporary_beds_required=visiting,
                                   temporary_bed_shortfall=max(0,visiting-request['available_visitor_beds'])))
