"""Independent civilization habitats and deterministic city classifications."""
from .terrain_profiles import profiles, get_profile, civilization_ids
from .civilization_registry import section,entity_rules,registry_identity


def matches(rule, environment):
    if not rule:return True
    if 'all' in rule:return all(matches(r,environment) for r in rule['all'])
    if 'any' in rule:return any(matches(r,environment) for r in rule['any'])
    value=environment[rule['field']]
    return (('in' not in rule or value in rule['in'])
            and ('min' not in rule or value>=rule['min'])
            and ('max' not in rule or value<=rule['max'])
            and ('gt' not in rule or value>rule['gt'])
            and ('equals' not in rule or value==rule['equals']))


def eligible_civilizations(environment, registry=None):
    """Exclusive habitat groups partition capacity, without profile inheritance."""
    registry=registry if registry is not None else profiles()
    eligible=[];claimed=set()
    for key in sorted(registry,key=lambda k:(registry[k]['civilization']['priority'],k)):
        entity=registry[key]['civilization'];group=entity['allocation_group']
        if entity['kind']!='entity' or (group and group in claimed):continue
        if matches(entity['habitat'],environment):
            eligible.append(key)
            if group:claimed.add(group)
    return eligible


def landmass_context(points,areas,graph,water):
    """Topology uses unique spherical nodes, including seam and pole links."""
    remaining={i for i,w in enumerate(water) if w==0};components=[]
    while remaining:
        start=min(remaining);remaining.remove(start);members=[start];stack=[start]
        while stack:
            for j,_ in graph[stack.pop()]:
                if j in remaining:remaining.remove(j);members.append(j);stack.append(j)
        components.append((members,sum(areas[i] for i in members)))
    total=sum(area for _,area in components);largest=max((area for _,area in components),default=0)
    contexts=[dict(landmass_area_m2=0.,landmass_fraction=0.,largest_landmass=False) for _ in points]
    for members,area in components:
        for i in members:contexts[i]=dict(landmass_area_m2=area,landmass_fraction=area/total if total else 0.,largest_landmass=area==largest)
    return contexts


def environment_at(result,x,z,context):
    layers=result['layers']
    return dict(context,biome=layers['biome'][z][x],temperature=layers['temperature'][z][x],
                moisture=layers['moisture'][z][x],maritime=layers.get('maritime',[[0.]])[z][x] if 'maritime' in layers else 0.)


def classify_cities(sites):
    """One best-suitability capital per nonempty entity; no forced cities."""
    threshold=section('city_classification')['medium_suitability_min']
    groups={}
    for site in sites:groups.setdefault(site['population_profile'],[]).append(site)
    for key,members in groups.items():
        capital=min(members,key=lambda s:(not s.get('founding_capital',False),-s['suitability'],s['node']))
        for site in members:
            site['civilization_id']=key
            site['city_class']='capital' if site is capital else 'medium' if site['suitability']>=threshold else 'small'
            site['classification_reason']='Founding capital retained; otherwise highest suitability, node breaks ties' if site is capital else f'Suitability >= {threshold:g}' if site['city_class']=='medium' else f'Suitability < {threshold:g}'


def civilization_report(sites):
    classes=section('city_classification')
    return {'version':2,'registry':registry_identity(),'medium_suitability_min':classes['medium_suitability_min'],'capital_scope':classes['capital_scope'],
            'parent_races':section('parent_races'),
            'presentation_defaults':{k:v for k,v in section('defaults').items() if k.endswith('_color_rgb')},
            'entities':[dict(id=key,region_index=index,name=get_profile(key)['name'],**get_profile(key)['civilization'],
                             presentation=entity_rules(key)['presentation'],parent_race_id=entity_rules(key)['parent_race_id'],
                             city_count=sum(s['population_profile']==key for s in sites),
                             capital_node=next((s['node'] for s in sites if s['population_profile']==key and s['city_class']=='capital'),None))
                        for index,key in enumerate(civilization_ids())]}
