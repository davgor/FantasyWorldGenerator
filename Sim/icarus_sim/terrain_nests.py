"""Deterministic habitat anchors, not creature populations or runtime spawns."""
import json
import math
import random
from pathlib import Path
from functools import lru_cache
from .terrain_tectonics import child_seed
from .terrain_world import options
from .terrain_erosion import sphere_grid
from .terrain_globe import direction


def clamp(v):
    return max(0., min(1., v))


@lru_cache(maxsize=1)
def profiles():
    rows=json.loads(Path(__file__).with_name('terrain_nest_profiles.json').read_text(encoding='utf-8'))['profiles']
    if len({p['id'] for p in rows}) != len(rows):
        raise ValueError('Duplicate creature profile IDs')
    for p in rows:
        if p['medium'] not in ('land','shore','marine','freshwater') or not p['weights'] or any(v<=0 for v in p['weights'].values()):
            raise ValueError('Invalid nest profile: '+p['name'])
    return rows


def suitability(p, f):
    """Hard eligibility before preferences; absent required fields fail closed."""
    medium=f.get('medium')
    if medium!=('land' if p['medium']=='shore' else p['medium']):return 0., {'excluded':'water/land habitat mismatch'}
    if p['medium']=='shore' and f.get('coast',0)<.1:return 0., {'excluded':'no coastal refuge'}
    if not p['temperature'][0]<=f.get('temperature',100)<=p['temperature'][1]:return 0., {'excluded':'temperature outside profile range'}
    if any(f.get(k,0)<v for k,v in p['requires'].items()):return 0., {'excluded':'missing required habitat or magical influence'}
    total=sum(p['weights'].values()); factors={k:clamp(f.get(k,0))*w/total for k,w in p['weights'].items()}
    return sum(factors.values()), factors


def distance(a,b,radius):
    return radius*math.acos(max(-1.,min(1.,sum(x*y for x,y in zip(a,b)))))


def add_nests(result,cfg):
    if not cfg.world_recipe or cfg.phase<7:return result
    o=options(cfg);n=cfg.size;l=result['layers'];radius=result['effective_config']['globe_radius']
    points,areas,_=sphere_grid(n,radius)
    # Bounded, area-weighted search avoids dense polar sampling. Shared geography
    # sample is independent of nest controls and each species' lottery.
    rng=random.Random(child_seed(cfg.seed,'nest-habitat-sample-v1'))
    sampled=sorted(set(rng.choices(range(len(points)),weights=areas,k=min(2048,len(points)*2))))
    features=[];sites=result.get('settlements',{}).get('sites',[])
    sites=sites+result.get('fisheries',{}).get('ports',[])+result.get('sky',{}).get('settlements',[])
    occupied={}
    for s in sites:
        occupied.setdefault(s.get('layer','surface'),[]).append(s.get('direction') or direction(s['x'],s['z'],n))
    for i in sampled:
        x,z=points[i];f={k:v[z][x] for k,v in l.items()}
        water=f.get('water_type',0);wet=f.get('moisture',0)
        f.update(medium='marine' if water==1 else 'freshwater' if water and f.get('salinity',0)<.2 else 'salt_lake' if water else 'land',
                 depth=f.get('water_depth',0),dryness=1-clamp(wet),coast=f.get('maritime',0),
                 mountain=clamp(f.get('slope',0)/25),plains=clamp(1-f.get('slope',0)/15)*(1-abs(wet-.45)),
                 wetland=max(float(bool(water)),f.get('river',0),wet*math.exp(-f.get('slope',0)/8)),
                 cold=clamp((10-f.get('temperature',10))/25))
        features.append(dict(id=str(i),node=i,x=x,z=z,layer='surface',direction=direction(x,z,n),fields=f))
    for island in result.get('sky',{}).get('islands',[]):
        f=dict(medium='land',temperature=island['temperature_c'],moisture=island['moisture'],mountain=.8,plains=.3,cold=clamp((10-island['temperature_c'])/25))
        for network in ('weave','umbral','infernal','holy','primordial'):f['ley_'+network]=l['ley_'+network][island['z']][island['x']]
        features.append(dict(id=island['id'],node=None,x=island['x'],z=island['z'],layer=island['id'],direction=island['direction'],altitude_m=island['altitude_m'],fields=f))
    proposals=[];diagnostics=[]
    for p in profiles():
        prng=random.Random(child_seed(cfg.seed,'nests-'+p['id']+'-v1',o['nest_variation']))
        accepted=[];eligible=0
        enabled=o['nest_limit']>0 and o['nest_density']>0 and (p['real'] or o['nest_fantasy']>0)
        chosen=enabled and prng.random()<min(1.,p['occurrence']*o['nest_density']*(1 if p['real'] else o['nest_fantasy']))
        if chosen:
            ranked=[]
            for c in features:
                if c['layer']!='surface' and not p['sky']:continue
                score,why=suitability(p,c['fields'])
                if score<o['nest_min_suitability']:continue
                if any(distance(c['direction'],s,radius)<o['nest_settlement_clearance'] for s in occupied.get(c['layer'],[])):continue
                eligible+=1;ranked.append((score*(.65+.35*prng.random()),c,score,why))
            for _,c,score,why in sorted(ranked,key=lambda r:-r[0]):
                spacing=p['spacing_m']*o['nest_spacing']
                if any(a['layer']==c['layer'] and distance(a['direction'],c['direction'],radius)<spacing for a in accepted):continue
                nest={k:v for k,v in c.items() if k!='fields'}
                nest.update(id='nest-'+p['id']+'-'+c['layer']+'-'+c['id'],species_id=p['id'],name=p['name'],real=p['real'],family=p['family'],kind=p['kind'],size=p['size'],suitability=score,factors=why,spacing_m=spacing,priority=prng.random(),reason='; '.join(k.replace('_',' ')+f' {v:.2f}' for k,v in sorted(why.items(),key=lambda kv:-kv[1])[:3]))
                accepted.append(nest)
                if len(accepted)>=o['nest_per_species']:break
        proposals.extend(accepted)
        diagnostics.append(dict(species_id=p['id'],name=p['name'],eligible_samples=eligible,proposed=len(accepted),reason='candidate anchors found' if accepted else 'no sampled habitat meets suitability and settlement clearance' if chosen else 'disabled' if not enabled else 'not selected by occurrence seed'))
    selected=[];used=set()
    for nest in sorted(proposals,key=lambda a:(-a['priority'],a['id'])):
        cell=(nest['layer'],nest['node'])
        if len(selected)>=o['nest_limit']:break
        if cell in used:continue
        used.add(cell);nest.pop('priority');selected.append(nest)
    counts={}
    for nest in selected:counts[nest['species_id']]=counts.get(nest['species_id'],0)+1
    for d in diagnostics:
        d['placed']=counts.get(d['species_id'],0)
        if d['proposed']:d['reason']='placed' if d['placed']==d['proposed'] else 'limited by shared anchor budget or occupied sample'
    result['beast_nests']=dict(version=1,sites=sorted(selected,key=lambda a:a['id']),diagnostics=diagnostics,profiles=profiles(),sample_count=len(sampled),catalogue_count=len(profiles()),method='Area-weighted bounded habitat search; independent species seeds; one anchor per sampled cell; spherical same-species spacing. Static habitat proposals, no hostility or population assumption.',limits='No prey carrying capacity, food deductions, migrations, underground cavities or runtime spawning. Small habitats may be missed at coarse resolution; aquatic territories are not literal nests.')
    return result
