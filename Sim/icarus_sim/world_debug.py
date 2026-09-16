"""Deterministic, JSON-safe final-world diagnostic summaries; no simulation decisions."""
import math
from collections import Counter


def build_debug(world):
    sites=world.get('settlements',{}).get('sites',[])
    ruins=world.get('ruins',[])
    plans={p['city_uid']:p for p in world.get('city_plans',{}).get('cities',[])}
    radius=world.get('effective_config',world.get('config',{})).get('globe_radius',10000)
    def key(s):return (s.get('node'),s.get('population_profile'))
    events={}
    states=[s.get('state',{}) for s in world.get('build_stages',[])]+[world]
    timeline=[]
    for state in states:
        settlement=state.get('settlements') or {}
        for e in settlement.get('founding',{}).get('events',[]):
            identity=tuple(e.get(k) for k in ('status','node','population_profile','parent_race_id','turn','founding_year'))
            events[identity]=e
    diaspora=[e for e in events.values() if e.get('status')=='diaspora_founded']
    live={key(s) for s in sites};dead={key(s) for s in ruins}
    races={};cultures={};cities=[]
    for s in sites:
        p=plans.get(s.get('uid',str(s.get('id'))),{})
        population=s.get('urban_population_estimate',s.get('population_estimate',0)) or 0
        for groups,label in ((races,s.get('parent_race_id','unknown')),(cultures,s.get('population_profile','unknown'))):
            row=groups.setdefault(label,{'id':label,'cities':0,'urban_population':0,'workers':0,'beds':0})
            row['cities']+=1;row['urban_population']+=population
            row['workers']+=p.get('stats',{}).get('workers',0);row['beds']+=p.get('stats',{}).get('worker_beds',0)
        distances=[]
        for other in sites:
            if other is s or 'direction' not in s or 'direction' not in other:continue
            distances.append(radius*math.acos(max(-1,min(1,sum(a*b for a,b in zip(s['direction'],other['direction']))))))
        cities.append({'uid':s.get('uid',str(s.get('id'))),'name':s['name'],'civilization':s.get('population_profile'),
                       'parent_race':s.get('parent_race_id'),'population':population,'nearest_city_m':min(distances) if distances else None,
                       'stats':p.get('stats',{}),'placement':p.get('debug',{}),'unplaced':p.get('unplaced',[]),
                       'junctions':Counter(c['status'] for c in p.get('road_connections',[]))})
    for snap in world.get('build_stages',[]):
        state=snap.get('state',{})
        if state.get('settlements') is not None:
            ss=state['settlements'].get('sites',[])
            timeline.append({'stage':snap['stage'],'title':snap.get('title',''),'cities':len(ss),
                             'urban_population':sum(s.get('urban_population_estimate',s.get('population_estimate',0)) or 0 for s in ss)})
    schools=[]
    for name,net in world.get('magic',{}).get('networks',{}).items():
        schools.append({'id':name,'nodes':len(net['nodes']),'lines':len(net['edges']),'distribution':net.get('distribution')})
    # Spherical area weights prevent polar rows and duplicate longitude seams inflating coverage.
    grid=world.get('layers',{}).get('natural_biome',world.get('layers',{}).get('biome',[]));coverage=Counter()
    if grid:
        n=len(grid)
        for z,row in enumerate(grid):
            lo=max(-math.pi/2,math.pi/2-math.pi*(z+.5)/(n-1))
            hi=min(math.pi/2,math.pi/2-math.pi*(z-.5)/(n-1))
            for value in row[:-1]:coverage[value]+=math.sin(hi)-math.sin(lo)
    total=sum(coverage.values()) or 1
    catalogue={b.get('id',i):b['name'] for i,b in enumerate(world.get('terrain',{}).get('biomes',[]))}
    return {'version':1,'scope':'Final completed state; population is urban estimate, beds cover placed workers only.',
            'parent_races':list(races.values()),'civilizations':list(cultures.values()),'cities':cities,
            'diaspora':{'founded':len(diaspora),'surviving':sum(key(e) in live for e in diaspora),
                        'destroyed':sum(key(e) in dead and key(e) not in live for e in diaspora)},
            'founding_outcomes':dict(Counter(e['status'] for e in events.values())),
            'founding_events':list(events.values()),'ruins':ruins,'timeline':timeline,'leylines':schools,
            'biome_coverage':[{'id':k,'name':catalogue.get(k,str(k)),'percent_world':100*v/total} for k,v in sorted(coverage.items())]}
