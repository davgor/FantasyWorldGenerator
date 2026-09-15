"""Deterministic seasonal stress test of proposed cities, not live population state."""
import math
from time import perf_counter


def seasonal_harvest(annual_food,wet,latitude,mean_temp,tolerance,ideal=18,seasonality=1.):
    """One-month harvest lag; thermal seasonality reverses across the equator.

    Annual food is the existing mean-climate estimate, not a guaranteed yield.
    Seasonal growing suitability can change the year's actual production.
    """
    amplitude=20*math.sin(math.radians(latitude))*(1-.4*wet)*seasonality
    baseline=max(.05,math.exp(-((mean_temp-ideal)/tolerance)**2))
    growth=[]
    for month in range(12):
        temp=mean_temp+amplitude*math.cos(2*math.pi*(month-6)/12)
        thermal=math.exp(-((temp-ideal)/tolerance)**2)*max(0,min(1,temp/8))
        growth.append(min(1.5,thermal/baseline))
    return [annual_food*growth[(month-1)%12]/12 for month in range(12)]


def simulate_food(cities,roads,years=4):
    """Monthly conservation with shared edge throughput and no same-month re-export.

    Stores start empty; consumption precedes storage overflow. Trade is directly
    between road neighbours and costs the buyer renewable monthly material units.
    """
    stocks=[0.]*len(cities);history=[]
    for step in range(years*12):
        month=step%12;opening=list(stocks)
        spoiled=[stocks[i]*c['spoilage'] for i,c in enumerate(cities)]
        harvest=[c['harvest'][month] for c in cities]
        stocks=[stocks[i]-spoiled[i]+harvest[i] for i in range(len(cities))]
        exportable=[max(0,stocks[i]-c['demand']-min(c['demand'],c['storage'])) for i,c in enumerate(cities)]
        budgets=[c.get('transport_budget',math.inf) for c in cities]
        imports=[0.]*len(cities);exports=[0.]*len(cities);spent=[0.]*len(cities)
        shipments=[];loss=0.
        for route_index,edge in enumerate(roads):
            a,b=edge['from'],edge['to'];remaining=edge['capacity'][month]
            for seller,buyer in ((a,b),(b,a)):
                efficiency=edge['efficiency'];price=edge.get('price',1.)
                if efficiency<=0:continue
                need=max(0,cities[buyer]['demand']-stocks[buyer])
                sent=min(exportable[seller],remaining,need/efficiency,budgets[buyer]/price/efficiency)
                if sent<=1e-12:continue
                received=sent*efficiency;charge=received*price
                stocks[seller]-=sent;stocks[buyer]+=received;exportable[seller]-=sent;remaining-=sent
                budgets[buyer]-=charge;spent[buyer]+=charge;exports[seller]+=sent;imports[buyer]+=received
                loss+=sent-received
                shipments.append({'from':seller,'to':buyer,'route_index':route_index,'sent':sent,'delivered':received,'lost':sent-received,'material_cost':charge})
        records=[]
        for i,c in enumerate(cities):
            consumed=min(c['demand'],stocks[i]);stocks[i]-=consumed
            overflow=max(0,stocks[i]-c['storage']);stocks[i]-=overflow
            records.append({'opening':opening[i],'harvest':harvest[i],'spoiled':spoiled[i],
                'imports':imports[i],'exports':exports[i],'material_spent':spent[i],
                'demand':c['demand'],'consumed':consumed,'shortage':max(0,c['demand']-consumed),
                'overflow':overflow,'closing':stocks[i]})
        history.append({'year':step//12+1,'month':month+1,'cities':records,'shipments':shipments,
            'opening':sum(opening),'harvest':sum(harvest),'closing':sum(stocks),'transit_loss':loss,
            **{key:sum(c[key] for c in records) for key in ('consumed','spoiled','overflow')}})
    return {'months':history}


def add_seasonal_food(result,cfg):
    if not result.get('humans'):return result
    from .terrain_profiles import get_profile
    from .terrain_world import options
    started=perf_counter();sites=result['settlements']['sites'];society=result['humans'];layers=result['layers']
    models=[]
    for core,site in zip(society['cores'],sites):
        p=get_profile(site['population_profile']);harvest=[0.]*12
        for hamlet in society['hamlets']:
            if hamlet['core_id']!=site['id']:continue
            x,z=hamlet['x'],hamlet['z'];latitude=90-180*z/(cfg.size-1)
            annual=seasonal_harvest(hamlet['delivered_food'],layers['moisture'][z][x],latitude,
                layers['temperature'][z][x],p['food_temperature_tolerance'],p['temperature_ideal'],options(cfg)['seasonality'] if cfg.world_recipe else 1.)
            harvest=[a+b for a,b in zip(harvest,annual)]
        demand=core['food_demand']/12
        # Materials imply storage construction/maintenance; humidity/heat drive spoilage.
        storage_months=min(6,core['material_supply']/max(core['food_demand'],.01)*3)
        spoilage=min(.08,.005+.035*site['moisture']*max(0,min(1,(site['temperature_c']+5)/35)))
        models.append({'site_id':site['id'],'harvest':harvest,'demand':demand,
            'storage':demand*storage_months,'spoilage':spoilage,'transport_budget':core['material_supply']/12})
    routes=[]
    for road in result['roads']['routes']:
        a,b=road['from'],road['to'];mean=(sites[a]['temperature_c']+sites[b]['temperature_c'])/2
        latitude=90-90*(sites[a]['z']+sites[b]['z'])/(cfg.size-1)
        base=(models[a]['demand']+models[b]['demand'])/(1+road['cost']/cfg.support_reach)
        capacities=[]
        for month in range(12):
            temp=mean+15*math.sin(math.radians(latitude))*math.cos(2*math.pi*(month-6)/12)
            winter=max(0,min(1,(temp+15)/20))
            capacities.append(base*winter/(1+.1*len(road['river_crossings'])))
        routes.append({'from':a,'to':b,'capacity':capacities,'efficiency':math.exp(-road['cost']/4000),
                       'price':.2+road['cost']/5000})
    run=simulate_food(models,routes);final=run['months'][-12:];summaries=[]
    for i,(core,site) in enumerate(zip(society['cores'],sites)):
        months=[m['cities'][i] for m in final];shortage=sum(m['shortage'] for m in months)
        demand=sum(m['demand'] for m in months);coverage=1-shortage/demand if demand else 1.
        delta=months[-1]['closing']-months[0]['opening']
        summary={'site_id':i,'annual_demand':demand,'annual_harvest':sum(m['harvest'] for m in months),
            'annual_shortage':shortage,'food_coverage':coverage,
            'lean_months':[m+1 for m,v in enumerate(months) if v['shortage']>1e-8],
            'reserve_change':delta,'ending_reserve':months[-1]['closing'],
            'passes_final_year':shortage<1e-8 and delta>=-1e-8,
            'urban_food_equivalent':math.floor(site.get('urban_population_estimate',0)*coverage)}
        summaries.append(summary)
    result['seasonal_food']={'version':1,'years':4,'reported_year':4,'cities':summaries,'models':models,
        'routes':routes,'months':run['months'],
        'method':'Four repeated climatic years from empty stores; year 4 is a stress-test observation, not proof of equilibrium. Monthly mean thermal growth and a one-month harvest lag use existing rural exportable surplus after rural subsistence. Storage and monthly transport budgets derive from material potential; humidity/heat cause spoilage. Direct road neighbours trade finite surplus, protecting one month of donor reserve; shared edge throughput, winter penalties, transport loss and material cost apply. No same-month re-export. Legacy annual trade is a separate diagnostic, not extra food. Proposed population is not mutated.',
        'limits':'Relative food units retain provisional calibration. Rural subsistence is assumed upstream, not seasonally validated here; coverage and food-equivalent residents concern urban demand only. No crop calendar diversity, stochastic droughts, soil depletion, groundwater extraction, shipping, migration or mortality. Route winter conditions use endpoint climate rather than every pass. Greedy direct-neighbour trade is not an optimal multi-hop logistics solver.'}
    result['warnings'].append(result['seasonal_food']['limits'])
    elapsed=(perf_counter()-started)*1000;result['timing_ms']['seasonal_food']=elapsed;result['timing_ms']['total']+=elapsed
    return result
