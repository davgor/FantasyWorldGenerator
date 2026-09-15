"""Human city hinterlands: relative surplus, route defence and interaction groups."""
import heapq
import math
from time import perf_counter
from .terrain_erosion import sphere_grid
from .terrain_globe import direction
from .terrain_climate import node_grid
from .terrain_settlements import road_cost_function, shortest_paths
from .terrain_tectonics import child_seed


def culture_groups(count, links, threshold):
    """Single-link groups; canonical ID is the lowest member city index."""
    groups=list(range(count))
    def root(i):
        while groups[i]!=i:i=groups[i]
        return i
    for link in links:
        if link['cost']<=threshold:
            a,b=root(link['from']),root(link['to'])
            groups[max(a,b)]=min(a,b)
    return [root(i) for i in range(count)]


def allocate_access(graph, seeds, cost, limit=math.inf):
    """One terrain-cost owner per node; deterministic ties, no water shortcuts."""
    distance=[math.inf]*len(graph);owner=[-1]*len(graph);parent=[-1]*len(graph);queue=[]
    for node,label in seeds:
        distance[node]=0.;owner[node]=label;heapq.heappush(queue,(0.,label,node))
    while queue:
        value,label,i=heapq.heappop(queue)
        if value!=distance[i] or label!=owner[i]:continue
        for j,d in graph[i]:
            edge=cost(i,j,d)
            if edge is None:continue
            candidate=value+edge
            if candidate<=limit and (candidate<distance[j] or (candidate==distance[j] and label<owner[j])):
                distance[j]=candidate;owner[j]=label;parent[j]=i
                heapq.heappush(queue,(candidate,label,j))
    return distance,owner,parent


def farming_potential(slope,temp,wet,flood,freshwater_distance,adaptation,profile=None):
    if profile is None:
        from .terrain_profiles import get_profile
        profile=get_profile('human')
    terrain=math.exp(-(slope/profile['food_slope_comfort'])**2)*max(0,1-abs(temp-profile['temperature_ideal'])/profile['food_temperature_tolerance'])*(1-.7*flood)
    natural=terrain*max(0,1-abs(wet-profile['food_moisture_ideal'])/profile['food_moisture_ideal'])
    access=math.exp(-freshwater_distance/profile['water_reach']) if freshwater_distance>=0 else 0
    irrigation=adaptation*access*max(0,(profile['food_moisture_ideal']-wet)/profile['food_moisture_ideal'])
    # Maintenance reduces the added exportable surplus; no source means no irrigation.
    return natural,natural+.75*terrain*irrigation


def exchange_food(cores,roads):
    """Finite local surplus traded over existing roads, with loss and material cost."""
    graph=[[] for _ in cores]
    for road in roads:
        a,b=road['from'],road['to'];graph[a].append((b,road['cost']));graph[b].append((a,road['cost']))
    for c in cores:c.update({'food_imports':0.,'food_exports':0.,'trade_material_cost':0.})
    shipments=[]
    for buyer in sorted(cores,key=lambda c:(c['food_supply']-c['food_demand'],c['site_id'])):
        needed=max(0,buyer['food_demand']-buyer['food_supply']);b=buyer['site_id']
        distances,parents=shortest_paths(graph,b,lambda i,j,d:d)
        for a in sorted(range(len(cores)),key=lambda a:(distances[a],a)):
            if needed<=1e-9:break
            if a==b or not math.isfinite(distances[a]):continue
            seller=cores[a];surplus=max(0,seller['food_supply']-seller['food_demand']-seller['food_exports'])
            efficiency=math.exp(-distances[a]/4000)
            price=.2+distances[a]/5000
            budget=max(0,buyer['material_supply']-buyer['trade_material_cost'])
            received=min(needed,surplus*efficiency,budget/price)
            if received<=1e-9:continue
            sent=received/efficiency;seller['food_exports']+=sent;buyer['food_imports']+=received
            buyer['trade_material_cost']+=received*price;needed-=received
            path=[a]
            while path[-1]!=b:path.append(parents[path[-1]])
            shipments.append({'from':a,'to':b,'sent':sent,'delivered':received,'lost':sent-received,
                              'material_cost':received*price,'city_path':path})
    for c in cores:c['food_deficit']=max(0,c['food_demand']-c['food_supply']-c['food_imports']+c['food_exports'])
    return shipments


def add_humans(result,cfg):
    if cfg.phase<9 or not result.get('roads'):return result
    from .terrain_profiles import get_profile
    profile=get_profile(cfg.population_profile)
    started=perf_counter();n=cfg.size;r=result['effective_config']['globe_radius']
    points,areas,graph=sphere_grid(n,r);layers=result['layers'];sites=result['settlements']['sites']
    def values(key):return [layers[key][z][x] for x,z in points]
    height=values('height');water=values('water_type');slope=values('slope');flood=values('flood_risk')
    wet=values('moisture');temp=values('temperature');resource=values('resource_potential')
    tpi=values('tpi');river=values('rain_river')
    hazard=values('magic_hazard') if 'magic_hazard' in layers else [0.]*len(points)
    cost=road_cost_function(points,water,height,flood,river,cfg,hazard)
    distance,owner,parent=allocate_access(graph,[(s['node'],s['id']) for s in sites],cost)
    individual_costs={}
    if cfg.world_recipe:
        from dataclasses import replace
        distance=[math.inf]*len(points);owner=[-1]*len(points);parent=[-1]*len(points)
        for site in sites:
            p=get_profile(site['population_profile'])
            risk=values('magic_risk_'+site['population_profile']) if 'magic_risk_'+site['population_profile'] in layers else hazard
            individual_costs[site['id']]=road_cost_function(points,water,height,flood,river,replace(cfg,human_magic_limit=p['mutation_limit'],road_max_grade=p['road_grade_limit']),risk)
        # A frontier retains its owner's traversal rules; parent paths cannot jump ownership.
        queue=[]
        for site in sites:
            i=site['node'];owner[i]=site['id'];distance[i]=0.;heapq.heappush(queue,(0.,site['id'],i))
        while queue:
            d,o,i=heapq.heappop(queue)
            if d!=distance[i] or o!=owner[i]:continue
            for j,length in graph[i]:
                edge=individual_costs[o](i,j,length)
                if edge is None:continue
                candidate=d+edge
                if candidate<distance[j] and candidate<=cfg.support_reach:
                    distance[j]=candidate;owner[j]=o;parent[j]=i;heapq.heappush(queue,(candidate,o,j))
    site_profiles=[get_profile(s['population_profile']) for s in sites]
    node_profiles=[site_profiles[o] if o>=0 else profile for o in owner]
    if cfg.world_recipe:
        hazard=[layers.get('magic_risk_'+p['id'],layers.get('magic_hazard',[[0.]*n]*n))[z][x] for p,(x,z) in zip(node_profiles,points)]
    links=[r for r in result['roads']['routes'] if sites[r['from']]['population_profile']==sites[r['to']]['population_profile']]
    groups=culture_groups(len(sites),links,cfg.culture_link_cost)
    culture_ids={g:f"{sites[g]['population_profile']}-{child_seed(cfg.seed,'culture-'+str(g)):08x}" for g in sorted(set(groups))}
    cultures=[{'index':g,'id':culture_ids[g],'city_ids':[i for i,v in enumerate(groups) if v==g],
               'population_profile':sites[g]['population_profile'],'architecture_style_id':None} for g in sorted(set(groups))]
    region=[groups[o] if o>=0 and distance[i]<=cfg.support_reach else -1 for i,o in enumerate(owner)]
    # Relative exportable potential after rural subsistence, not people or tonnes/year.
    fresh=values('freshwater_distance')
    yields=[(0.,0.) if water[i] else farming_potential(slope[i],temp[i],wet[i],flood[i],fresh[i],node_profiles[i]['irrigation'] if cfg.population_profile=='mixed' else cfg.human_adaptation,node_profiles[i])
            for i in range(len(points))]
    biomes=values('biome')
    yields=[(a*node_profiles[i]['food_biome_multipliers'].get(str(biomes[i]),1)*(1-hazard[i]),
             b*node_profiles[i]['food_biome_multipliers'].get(str(biomes[i]),1)*(1-hazard[i])) for i,(a,b) in enumerate(yields)]
    natural=[a for a,b in yields];food=[b for a,b in yields]
    vectors=[direction(x,z,n) for x,z in points];occupied=[s['node'] for s in sites]
    def separated(i,minimum):
        return all(r*math.acos(max(-1,min(1,sum(a*b for a,b in zip(vectors[i],vectors[j])))))>=minimum for j in occupied)
    def record(i,kind,number,reason):
        core=owner[i];x,z=points[i];path=[i]
        while parent[path[-1]]>=0:path.append(parent[path[-1]])
        return {'id':f'{kind}-{number}','kind':kind,'node':i,'x':x,'z':z,'core_id':core,
                'population_profile':sites[core]['population_profile'],'culture_id':culture_ids[groups[core]],'height_m':height[i],
                'access_cost':distance[i],'access_nodes':path,'reason':reason}
    hamlets=[]
    for site in sites:
        profile=site_profiles[site['id']]
        eligible=[i for i,o in enumerate(owner) if o==site['id'] and 100<=distance[i]<=cfg.support_reach
                  and not water[i] and slope[i]<profile['work_slope_limit']]
        hamlet_limit=min(cfg.hamlets_per_core,math.ceil(site.get('rural_population_estimate',0)/40)) if cfg.auto_parameters else cfg.hamlets_per_core
        for k in range(hamlet_limit):
            role='resource' if k%3==2 else 'farming'
            def score(i):return (food[i] if role=='farming' else resource[i]*(1-flood[i]))*math.exp(-distance[i]/cfg.support_reach)
            for i in sorted(eligible,key=lambda i:(-score(i),i)):
                if score(i)<.025:break
                if separated(i,120):
                    h=record(i,'hamlet',len(hamlets),'Reachable '+role+' potential with low transport cost')
                    h.update({'role':role,'irrigation_benefit':food[i]-natural[i],
                              'worked_area_km2':0.,'delivered_food':0.,'delivered_materials':0.})
                    hamlets.append(h);occupied.append(i);break
    # Each productive cell belongs to at most one hamlet and cannot cross city catchments.
    def farm_cost(i,j,d):
        if owner[i]!=owner[j] or distance[j]>cfg.support_reach:return None
        return individual_costs[owner[i]](i,j,d) if cfg.world_recipe and owner[i]>=0 else cost(i,j,d)
    _,farm_owner,_=allocate_access(graph,[(h['node'],k) for k,h in enumerate(hamlets)],farm_cost,250.)
    city_nodes={s['node'] for s in sites}
    for i,k in enumerate(farm_owner):
        if k<0 or i in city_nodes or slope[i]>=node_profiles[i]['work_slope_limit']:continue
        h=hamlets[k];area=areas[i]/1e6;delivery=math.exp(-h['access_cost']/cfg.support_reach)
        h['worked_area_km2']+=area
        h['delivered_food']+=100*area*food[i]*delivery*(1 if h['role']=='farming' else .25)
        h['delivered_materials']+=100*area*resource[i]*delivery*(1 if h['role']=='resource' else .25)
    # Route junctions/crossings and elevated surroundings suggest defensive sites.
    route_neighbors={};crossings=set()
    for road in result['roads']['routes']:
        for i,j in zip(road['nodes'],road['nodes'][1:]):
            route_neighbors.setdefault(i,set()).add(j);route_neighbors.setdefault(j,set()).add(i)
        for edge in road['river_crossings']:crossings.update(edge)
    strategic={}
    for node,links in route_neighbors.items():
        base=1+min(2,max(0,len(links)-2))+(1 if node in crossings else 0)
        for i,d in [(node,0.)]+graph[node]:
            if water[i] or slope[i]>=node_profiles[i]['work_slope_limit'] or owner[i]<0 or distance[i]>cfg.support_reach:continue
            if i!=node and cost(node,i,d) is None:continue
            value=base+max(-.5,min(1,tpi[i]/30))-.5*flood[i]-slope[i]/40-d/500
            if value>strategic.get(i,(-math.inf,None))[0]:strategic[i]=(value,node)
    forts=[]
    for i,(score,route_node) in sorted(strategic.items(),key=lambda item:(-item[1][0],item[0])):
        if len(forts)>=cfg.fortress_count:break
        if separated(i,200):
            fort=record(i,'fortress',len(forts),'Nearby city road; junction/crossing importance and elevated surroundings')
            fort.update({'defence_score':score,'protected_route_node':route_node})
            forts.append(fort);occupied.append(i)
    cores=[]
    for site in sites:
        members=[h for h in hamlets if h['core_id']==site['id']]
        supply=sum(h['delivered_food'] for h in members)
        cores.append({'site_id':site['id'],'population_profile':site['population_profile'],'culture_id':culture_ids[groups[site['id']]],
                      'hamlet_ids':[h['id'] for h in members],
                      'fortress_ids':[f['id'] for f in forts if f['core_id']==site['id']],
                      'food_demand':site_profiles[site['id']]['food_demand']*site['urban_population_estimate']/100 if 'urban_population_estimate' in site else cfg.urban_food_demand,'food_supply':supply,
                      'food_deficit':max(0,cfg.urban_food_demand-supply),
                      'material_supply':sum(h['delivered_materials'] for h in members)})
    shipments=exchange_food(cores,result['roads']['routes'])
    layers.update({'food_potential':node_grid(food,points,n),'natural_food_potential':node_grid(natural,points,n),
                   'irrigation_benefit':node_grid([b-a for a,b in yields],points,n),'culture_region':node_grid(region,points,n),
                   'hamlet_catchment':node_grid(farm_owner,points,n)})
    result['humans']={'version':4,'population_profile':cfg.population_profile,'cores':cores,'hamlets':hamlets,'fortresses':forts,'cultures':cultures,'shipments':shipments,
        'method':'All primary pins are cities. Rural sites share exclusive reachable catchments. Food/material values are relative exportable potential units, not historical yields or population capacity. Irrigation requires nearby mapped freshwater; water extraction capacity and groundwater are not simulated. Cities can buy finite surplus over roads using material potential, with transport loss; remaining shortages stay visible.',
        'culture_method':'Existing road links below a cost threshold form single-link interaction groups. Culture IDs are seed-local, not inferred ethnicities or political borders; styles remain unassigned. Territory stops at the support reach; wilderness remains unassigned.',
        'defence_method':'Fortresses are spaced route-defence proposals, not a siege or visibility simulation. Garrison demand is not yet budgeted.'}
    if 'magic' in result:
        result['humans']['version']=4
        result['humans']['method']+=' Mutation and the selected population biome food multipliers reduce crop surplus. Rural access cannot cross unsafe magic.'
    result['warnings'].extend([result['humans']['method'],result['humans']['culture_method'],result['humans']['defence_method']])
    elapsed=(perf_counter()-started)*1000;result['timing_ms']['human_hinterlands']=elapsed;result['timing_ms']['total']+=elapsed
    return result
