"""Coastal hamlets, bounded fisheries, elevated surfaces and multimodal supply tests."""
import copy
import math
import random
from dataclasses import replace
from .terrain_world import options
from .terrain_ecology import angle, clamp, monthly_temperatures, cold_habitat
from .terrain_tectonics import child_seed
from .terrain_erosion import sphere_grid
from .terrain_globe import direction
from .terrain_climate import node_grid
from .terrain_profiles import get_profile
from .civilization_registry import entity_rules
from .terrain_settlements import road_cost_function, shortest_paths
from .terrain_humans import allocate_access
from .terrain_seasons import simulate_food, seasonal_harvest


def trace(parent,start,end):
    path=[end]
    while path[-1]!=start:
        j=parent[path[-1]]
        if j<0:return []
        path.append(j)
    return list(reversed(path))


def water_cost(points,water,depth,hazard,limit,draft):
    lookup={p:i for i,p in enumerate(points)};n=max(z for x,z in points)+1
    def passable(i):return water[i]==1 and depth[i]>=draft and hazard[i]<=limit
    def cost(i,j,d):
        if not passable(i) or not passable(j):return None
        x,z=points[i];xx,zz=points[j]
        if x!=xx and z!=zz and z not in (0,n-1) and zz not in (0,n-1):
            if not passable(lookup[(x,zz)]) or not passable(lookup[(xx,z)]):return None
        return d
    return cost


def make_sky(result,cfg):
    o=options(cfg);l=result['layers'];n=cfg.size;r=result['effective_config']['globe_radius']
    points,_,_=sphere_grid(n,r);rng=random.Random(child_seed(cfg.seed,'sky-archipelagos-v1'))
    islands=[];sites=[];models=[]
    if not cfg.magic_enabled:return islands,sites,models
    candidates=[(x,z) for x,z in points if max(l['ley_weave'][z][x],l['ley_primordial'][z][x])>.06]
    rng.shuffle(candidates);centers=[]
    for k in range(o['sky_clusters']):
        if not candidates:break
        center=next(((x,z) for x,z in candidates if all(angle(direction(x,z,n),p)>.25 for p in centers)),None)
        if center is None:break
        centers.append(direction(*center,n))
        if rng.random()>o['sky_occurrence']:continue
        cx,cz=center
        for j in range(3):
            x=(cx+(j-1)*2)%(n-1);z=max(1,min(n-2,cz+rng.randint(-2,2)))
            radius=o['sky_radius']*rng.uniform(.7,1.3)
            altitude=max(l['height'][z][x],l['water_surface'][z][x])+o['sky_altitude']*rng.uniform(.8,1.2)
            temp=l['temperature'][z][x]-.0065*(altitude-l['height'][z][x]);wet=l['moisture'][z][x]
            temps=monthly_temperatures(temp,90-180*z/(n-1),wet,o['seasonality'])
            cold=cold_habitat(temps,wet,o['ice_accumulation']);area=math.pi*radius**2/1e6
            freshwater=area*wet*160 # provisional rain capture residents-equivalent budget
            food=area*80*clamp(1-abs(temp-16)/35)*wet*(0 if cold=='ice_cap' else 1.)
            from .terrain_civilizations import eligible_civilizations
            potential=math.floor(min(freshwater,food*1.5))
            sky_environment=dict(biome=7 if wet>=.7 and temp>20 else 3,temperature=temp,moisture=wet,
                                 maritime=0.,landmass_area_m2=area*1e6,landmass_fraction=1.,largest_landmass=True)
            eligible=eligible_civilizations(sky_environment)
            people=eligible if cfg.population_profile=='mixed' else [p for p in eligible if p==cfg.population_profile]
            people_rng=random.Random(child_seed(cfg.seed,f'sky-population-{k}-{j}-v1'))
            sky_rules={p:entity_rules(p)['sky'] for p in people}
            profile_id=max(people,key=lambda p: -abs(get_profile(p)['temperature_ideal']-temp)+people_rng.uniform(0,8)+(sky_rules[p]['score_bias']+sky_rules[p]['moisture_score_weight']*wet)) if people else None
            profile=get_profile(profile_id) if profile_id else None
            hazard=l.get('magic_risk_'+profile_id,l['magic_hazard'])[z][x] if profile_id else 0
            population=potential if profile and hazard<=profile['mutation_limit'] else 0
            island_id=f'sky-{k}-{j}';vertices=[];triangles=[]
            # A small independent disk mesh, never a displacement of the ground below.
            vertices.append([0.,altitude,0.])
            for ring in range(1,5):
                for a in range(24):
                    theta=2*math.pi*a/24;rr=radius*ring/4
                    relief=radius*.08*math.sin(theta*3+j)*math.sin(math.pi*ring/4)
                    vertices.append([rr*math.cos(theta),altitude+relief,rr*math.sin(theta)])
            for a in range(24):triangles.append([0,1+a,1+(a+1)%24])
            for ring in range(3):
                for a in range(24):
                    a0=1+ring*24+a;a1=1+ring*24+(a+1)%24;b0=a0+24;b1=a1+24
                    triangles.extend(([a0,b0,b1],[a0,b1,a1]))
            island={'id':island_id,'cluster_id':f'sky-{k}','layer':island_id,'x':x,'z':z,'direction':direction(x,z,n),
                    'radius_m':radius,'altitude_m':altitude,'area_km2':area,'temperature_c':temp,'moisture':wet,
                    'cold_habitat':cold,'food_potential':food,'freshwater_capacity':freshwater,
                    'magic_support':max(l['ley_weave'][z][x],l['ley_primordial'][z][x]),
                    'mesh':{'vertices':vertices,'triangles':triangles,'coordinates':'local east, radial altitude, north; metres'},
                    'months':[{'temperature':t,'snow':clamp(-t/8)*clamp(wet*2)} for t in temps]}
            islands.append(island)
            if population<4:continue
            site={'id':island_id+'-settlement','layer':island_id,'kind':'sky_settlement','population_profile':profile_id,'civilization_id':profile_id,
                  'x':x,'z':z,'direction':direction(x,z,n),'altitude_m':altitude,'population_estimate':population,
                  'name':f'{profile["name"]} Skyhaven {k+1}.{j+1}','freshwater_capacity':freshwater,
                  'reason':'Independent rain capture, growing climate and magical tolerance support this island community.'}
            sites.append(site)
            demand=population*profile['food_demand']/100/12
            models.append({'site_id':site['id'],'harvest':seasonal_harvest(food,wet,90-180*z/(n-1),temp,profile['food_temperature_tolerance'],profile['temperature_ideal'],o['seasonality']),
                           'demand':demand,'storage':demand*4,'spoilage':.02,'transport_budget':area*40/12})
    return islands,sites,models


def summarize_run(run,models,sites):
    result=[]
    for i,site in enumerate(sites):
        records=[month['cities'][i] for month in run['months'][-12:]]
        demand=sum(v['demand'] for v in records);shortage=sum(v['shortage'] for v in records)
        result.append({'site_id':site['id'],'layer':site.get('layer','surface'),'name':site['name'],
                       'annual_demand':demand,'annual_harvest':sum(v['harvest'] for v in records),
                       'annual_shortage':shortage,'food_coverage':1-shortage/demand if demand else 1.,
                       'lean_months':[i+1 for i,v in enumerate(records) if v['shortage']>1e-8],
                       'ending_reserve':records[-1]['closing']})
    return result


def add_world_society(result,cfg):
    if cfg.phase<6 or 'habitats' not in result:return
    islands,sky_sites,sky_models=make_sky(result,cfg)
    result['sky']={'version':1,'islands':islands,'settlements':sky_sites if cfg.phase>=7 else [],
                   'area_km2':sum(i['area_km2'] for i in islands),
                   'method':'Separate disk surfaces with rain capture, altitude climate and bounded food; static magical support.'}
    if cfg.phase<9 or 'seasonal_food' not in result:return
    o=options(cfg);l=result['layers'];n=cfg.size;r=result['effective_config']['globe_radius']
    points,areas,graph=sphere_grid(n,r)
    def vals(k):return [l[k][z][x] for x,z in points]
    water=vals('water_type');depth=vals('water_depth');height=vals('height');flood=vals('flood_risk');river=vals('rain_river')
    hazard=vals('magic_hazard') if 'magic_hazard' in l else [0.]*len(points);harbor=vals('harbor_suitability');fish=vals('fishing_productivity')
    sites=result['settlements']['sites'];models=copy.deepcopy(result['seasonal_food']['models'])
    # Huts follow their own preference for isolation and poor conventional suitability.
    wanted=sum(s['kind']=='witch_hut' for s in result['regions']['landmarks'])
    result['regions']['landmarks']=[s for s in result['regions']['landmarks'] if s['kind']!='witch_hut']
    hut_nodes=[]
    for i in sorted(range(len(points)),key=lambda i:-l['zone_witch_huts'][points[i][1]][points[i][0]]):
        if len(hut_nodes)>=wanted:break
        x,z=points[i]
        if water[i] or l['suitability'][z][x]>=.55 or l['zone_witch_huts'][z][x]<.02:continue
        p=direction(x,z,n)
        if any(r*angle(p,s['direction'])<cfg.settlement_spacing for s in sites):continue
        if any(r*angle(p,direction(*points[j],n))<200 for j in hut_nodes):continue
        hut_nodes.append(i)
        result['regions']['landmarks'].append({'id':f'witch-hut-{i}','kind':'witch_hut','x':x,'z':z,'layer':'surface',
            'intensity':l['zone_witch_huts'][z][x],'conventional_suitability':l['suitability'][z][x],
            'reason':'Umbral influence, isolation and low conventional settlement suitability.'})
    ports=[];occupied={s['node'] for s in sites+result['humans']['hamlets']};ground_candidates=[i for i,v in enumerate(harbor) if v>.1]
    for site in sites:
        site['layer']='surface';site['mobility']='settled';profile=get_profile(site['population_profile'])
        risk=vals('magic_risk_'+site['population_profile']) if 'magic_risk_'+site['population_profile'] in l else hazard
        cost=road_cost_function(points,water,height,flood,river,replace(cfg,human_magic_limit=profile['mutation_limit'],road_max_grade=profile['road_grade_limit']),risk)
        distances,parents=shortest_paths(graph,site['node'],cost,ground_candidates)
        eligible=[i for i in ground_candidates if distances[i]<=cfg.support_reach and i not in occupied]
        for node in sorted(eligible,key=lambda i:-(harbor[i]+.5*l['coastal_support'][points[i][1]][points[i][0]])*math.exp(-distances[i]/cfg.support_reach))[:o['coastal_hamlets']]:
            access=[(j,d) for j,d in graph[node] if water[j]==1 and depth[j]>=o['sea_draft'] and risk[j]<=profile['mutation_limit']]
            if not access:continue
            sea_node,landing_distance=min(access,key=lambda pair:pair[1]);occupied.add(node);x,z=points[node]
            port={'id':f'coastal-{site["id"]}-{len(ports)}','kind':'hamlet','role':'harbor + fishing',
                  'layer':'surface','node':node,'sea_node':sea_node,'landing_distance_m':landing_distance,
                  'x':x,'z':z,'core_id':site['id'],'population_profile':site['population_profile'],
                  'culture_id':result['humans']['cores'][site['id']]['culture_id'],'height_m':height[node],
                  'harbor_quality':harbor[node],'trade_terminal':harbor[node]>=.4,'access_nodes':trace(parents,site['node'],node),
                  'access_cost':distances[node],'reason':'Safe ground connection to city; navigable landing; fishing allocated from exclusive grounds.',
                  'worked_area_km2':0.,'delivered_food':0.,'delivered_materials':0.,'irrigation_benefit':0.,
                  'monthly_fish':[0.]*12,'fishing_nodes':[]}
            ports.append(port)
        city_ports=[p for p in ports if p['core_id']==site['id']]
        industrial_min=entity_rules(site['population_profile'])['economy']['industrial_resource_min']
        site['community_traits']=(['islander'] if city_ports and l['island_habitat'][site['z']][site['x']] else ['maritime'] if city_ports else [])+(['industrial'] if industrial_min is not None and site['resource_potential']>industrial_min else [])
    # Each port searches only accessible water. Globally award each cell once.
    claims={};fishing_ice=[]
    for k,port in enumerate(ports):
        profile=get_profile(port['population_profile']);reach=o['fishing_reach']*entity_rules(port['population_profile'])['economy']['fishing_reach_multiplier']
        risk=vals('magic_risk_'+port['population_profile']) if 'magic_risk_'+port['population_profile'] in l else hazard
        cost=water_cost(points,water,depth,risk,profile['mutation_limit'],.1)
        distances,_,parents=allocate_access(graph,[(port['sea_node'],0)],cost,reach)
        path_ice={}
        for i in sorted((i for i,d in enumerate(distances) if d<=reach),key=lambda i:distances[i]):
            x,z=points[i];upstream=path_ice.get(parents[i],[0.]*12)
            path_ice[i]=[max(upstream[m],result['seasonal_environment']['months'][m]['water_ice'][z][x]) for m in range(12)]
        fishing_ice.append(path_ice)
        for i,d in enumerate(distances):
            if d>reach:continue
            candidate=(d,k)
            if candidate<claims.get(i,(math.inf,0)):claims[i]=candidate
    owner=[-1]*len(points);production=0.
    for i,(distance,k) in claims.items():
        port=ports[k];owner[i]=k;port['fishing_nodes'].append(i)
        area=areas[i]/1e6;annual=area*fish[i]*o['fish_productivity'];production+=annual
        delivery=math.exp(-(distance+port['access_cost'])/max(1,cfg.support_reach))
        x,z=points[i];port['worked_area_km2']+=area
        for m in range(12):
            ice=fishing_ice[k][i][m]
            port['monthly_fish'][m]+=annual/12*delivery*(1-ice)
    for port in ports:
        port['delivered_food']=sum(port['monthly_fish'])
        port['role']='harbor + fishing' if port['trade_terminal'] and port['delivered_food']>0 else 'harbor' if port['trade_terminal'] else 'fishing' if port['delivered_food']>0 else 'landing'
        model=models[port['core_id']];model['harvest']=[a+b for a,b in zip(model['harvest'],port['monthly_fish'])]
        result['humans']['cores'][port['core_id']]['hamlet_ids'].append(port['id'])
    result['humans']['hamlets'].extend(ports)
    l['fishing_ground_owner']=node_grid(owner,points,n)
    result['fisheries']={'ports':ports,'potential_annual_food':production,
                         'delivered_annual_food':sum(p['delivered_food'] for p in ports),
                         'method':'One owner per reachable ocean cell; distance losses and monthly ice reduce delivery. Potential capacity is never credited before allocation.'}
    routes=[]
    for road,model in zip(result['roads']['routes'],result['seasonal_food']['routes']):
        routes.append({**model,'mode':'ground','nodes':road['nodes'],'length_m':road['length_m']})
    sea_pairs={}
    for a,port in enumerate(ports):
        for other in ports[a+1:]:
            if not port['trade_terminal'] or not other['trade_terminal']:continue
            if port['core_id']==other['core_id']:continue
            limit=min(get_profile(port['population_profile'])['mutation_limit'],get_profile(other['population_profile'])['mutation_limit'])
            cost=water_cost(points,water,depth,hazard,limit,o['sea_draft'])
            distances,parent=shortest_paths(graph,port['sea_node'],cost,{other['sea_node']})
            length=distances[other['sea_node']]+port['landing_distance_m']+other['landing_distance_m']
            if length>o['sea_reach']:continue
            path=trace(parent,port['sea_node'],other['sea_node']);a_id,b_id=sorted((port['core_id'],other['core_id']))
            value=length+port['access_cost']+other['access_cost']
            if (a_id,b_id) in sea_pairs and sea_pairs[a_id,b_id]['cost']<=value:continue
            capacity=[]
            for m in range(12):
                ice=max((result['seasonal_environment']['months'][m]['water_ice'][points[i][1]][points[i][0]] for i in path),default=0.)
                capacity.append(o['sea_capacity']*min(port['harbor_quality'],other['harbor_quality'])*(1-ice))
            sea_pairs[a_id,b_id]={'from':a_id,'to':b_id,'mode':'sea','nodes':path,'length_m':length,'cost':value,
                                 'ports':[port['id'],other['id']],'capacity':capacity,'efficiency':math.exp(-value/12000),'price':.2+value/10000}
    routes.extend(sea_pairs.values())
    all_sites=[*sites,*sky_sites];models.extend(sky_models)
    # Air terminals require industry or stable Weave access; sky settlements have a landing surface.
    terminals=[]
    for i,site in enumerate(all_sites):
        x,z=site['x'],site['z'];is_sky=i>=len(sites)
        air_min=entity_rules(site['population_profile'])['economy']['air_terminal_resource_min']
        enabled=is_sky or (air_min is not None and site['resource_potential']>air_min) or l.get('ley_weave',[[0.]*n]*n)[z][x]>.12
        if enabled:terminals.append(i)
    for index,a in enumerate(terminals):
        for b in terminals[index+1:]:
            aa,bb=all_sites[a],all_sites[b];va,vb=aa['direction'],bb['direction']
            altitude_a=aa.get('altitude_m',aa.get('height_m',0));altitude_b=bb.get('altitude_m',bb.get('height_m',0))
            length=math.hypot(r*angle(va,vb),altitude_b-altitude_a)
            if length>o['air_reach']:continue
            limit=min(get_profile(aa['population_profile'])['mutation_limit'],get_profile(bb['population_profile'])['mutation_limit'])
            safe=True;path=[]
            steps=max(2,math.ceil(length/max(result['spacing_m'],1)))
            for j in range(steps+1):
                t=j/steps;p=tuple(u*(1-t)+v*t for u,v in zip(va,vb));norm=math.sqrt(sum(v*v for v in p))
                if norm<1e-8:safe=False;break
                p=tuple(v/norm for v in p);x=round((math.atan2(p[2],p[0])+math.pi)/(2*math.pi)*(n-1));z=round(math.acos(max(-1,min(1,p[1])))/math.pi*(n-1))
                if max(l.get('magic_risk_'+s['population_profile'],l.get('magic_hazard',[[0.]*n]*n))[z][x] for s in (aa,bb))>limit:safe=False;break
                path.append([x,z])
            cruise=max([altitude_a,altitude_b]+[l['height'][z][x]+80 for x,z in path])
            length=r*angle(va,vb)+max(0,cruise-altitude_a)+max(0,cruise-altitude_b)
            if safe and length<=o['air_reach']:routes.append({'from':a,'to':b,'mode':'air','path':path,'length_m':length,'cruise_altitude_m':cruise,
                                   'capacity':[o['air_capacity']]*12,'efficiency':math.exp(-length/8000),'price':.5+length/5000})
    for site in sites:
        if l['zone_pirate'][site['z']][site['x']]>.02 and any(route['mode']=='sea' and site['id'] in (route['from'],route['to']) for route in routes):
            site['community_traits'].append('pirate')
    run=simulate_food(models,routes)
    result['transport']={'routes':routes,'terminals':terminals,'sites':[{'id':s['id'],'layer':s['layer']} for s in all_sites]}
    result['world_economy']={'version':1,'sites':summarize_run(run,models,all_sites),'models':models,'months':run['months'],
                             'method':'Authoritative new-recipe four-year monthly stress test: existing farm surplus plus allocated fisheries and independent sky production; shared finite ground/sea/air throughput, material budgets, spoilage and loss. No same-month re-export.',
                             'limits':'Artistic food units; static communities and routes. Surface farm production is rural export surplus; this is not demographic equilibrium or a vessel simulator.'}
