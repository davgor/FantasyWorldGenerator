"""Seeded parent-race founding rounds; geographic distances are physical metres."""
import random
from .terrain_tectonics import child_seed


def found_cities(seed, parents, owners, quotas, candidates, scores, distance, spacing, world_reach, survivors=(), forbidden=(), years_per_round=250, origin_min_separation_degrees=90, start_year=0, diaspora_interval_years=1000, diaspora_bonus_per_parent=1, food_allowances=None, city_limit=24, diaspora_bonus_used=(), used_civilizations=(), magic_enabled=True):
    sites=[dict(s) for s in survivors];blocked=set(forbidden);events=[]
    quotas=dict(quotas);bonus_used=set(diaspora_bonus_used);ever_used=set(used_civilizations)|{s['population_profile'] for s in sites}
    origin_gap=world_reach*origin_min_separation_degrees/180
    year_offset=max(start_year,max((s.get('founding_year',0) or 0 for s in sites),default=0)+(years_per_round if sites else 0))
    blocked_parents=set()
    target=sum(quotas.values());base=max(spacing*2,world_reach/32,1)
    def available(race):
        counts={key:sum(s['population_profile']==key for s in sites) for key in owners}
        return [(key,node) for key in owners if owners[key]==race and counts[key]<quotas[key]
                for node in candidates[key] if node not in blocked and all(node!=s['node'] and distance(node,s['node'])>=spacing for s in sites)]
    def diaspora_candidates():
        if food_allowances is None or len(sites)>=city_limit:return {}
        options={}
        for key,race in owners.items():
            if key in ever_used or food_allowances.get(key,0)<40:continue
            bonus=quotas[key]==0
            if bonus and (not diaspora_bonus_per_parent or race in bonus_used or target>=city_limit):continue
            if len(sites)>=target and not bonus:continue
            members=[s for s in sites if s['parent_race_id']==race]
            pool=[node for node in candidates[key] if node not in blocked and all(node!=s['node'] and distance(node,s['node'])>=spacing for s in sites)]
            if not members:pool=[node for node in pool if all(distance(node,s['node'])+1e-8>=origin_gap for s in sites if s.get('founding_capital',False))]
            if pool:options[key]=pool
        return options
    stop='round_limit_reached'
    for turn in range(1,129):
        radius=min(world_reach,base*1.6**min(turn-1,32));possible=False
        # Rotate initiative so one parent does not always claim contested sites first.
        races=list(parents);offset=(turn-1)%len(races) if races else 0;races=races[offset:]+races[:offset]
        for race in races:
            if len(sites)>=target:break
            if race in blocked_parents:continue
            members=[s for s in sites if s['parent_race_id']==race]
            pool=available(race)
            pct=parents[race]['founding_participation_percent']
            if not pool or ((turn>1 or members) and pct==0):continue
            if not members:
                origins=[s for s in sites if s.get('founding_capital',False)]
                pool=[pair for pair in pool if all(distance(pair[1],s['node'])+1e-8>=origin_gap for s in origins)]
                if not pool:
                    blocked_parents.add(race)
                    events.append(dict(turn=turn,parent_race_id=race,status='no_separated_origin',radius_m=world_reach,required_separation_degrees=origin_min_separation_degrees))
                    continue
            possible=True
            draw=random.Random(child_seed(seed,f'founding-{turn}-{race}')).random()*100
            if (turn>1 or members) and draw>=pct:
                events.append(dict(turn=turn,parent_race_id=race,status='did_not_participate',draw_percent=draw,radius_m=radius));continue
            unused=[pair for pair in pool if not any(s['population_profile']==pair[0] for s in sites)]
            if unused:pool=unused
            if members:pool=[pair for pair in pool if min(distance(pair[1],s['node']) for s in members)<=radius]
            if not pool:
                events.append(dict(turn=turn,parent_race_id=race,status='search_radius_too_small',radius_m=radius));continue
            key,node=min(pool,key=lambda pair:(-scores[pair[0]][pair[1]],pair[0],pair[1]))
            record=dict(node=node,population_profile=key,parent_race_id=race,founding_turn=turn,founding_capital=not members)
            source=min(members,key=lambda s:(distance(node,s['node']),s['node'])) if members else None
            record.update(founding_year=year_offset+(turn-1)*years_per_round,
                          migration_source_node=source['node'] if source else None,
                          source_civilization_id=source['population_profile'] if source else None,
                          migration_distance_m=distance(node,source['node']) if source else 0,
                          cultural_branch=bool(source and source['population_profile']!=key))
            sites.append(record);ever_used.add(key)
            events.append(dict(record,status='founded',turn=turn,radius_m=world_reach if not members else radius,suitability=scores[key][node]))
        year=year_offset+(turn-1)*years_per_round
        options=diaspora_candidates()
        if options and year>0 and year%diaspora_interval_years==0:
            rng=random.Random(child_seed(seed,f'diaspora-{year}'))
            key=rng.choice(sorted(options));race=owners[key]
            node=min(options[key],key=lambda n:(-scores[key][n],n))
            members=[s for s in sites if s['parent_race_id']==race]
            source=min(members,key=lambda s:(distance(node,s['node']),s['node'])) if members else None
            bonus=quotas[key]==0
            if bonus:quotas[key]=1;target+=1;bonus_used.add(race)
            reasons=['exile','religious_schism','expedition']+(['magical_displacement'] if magic_enabled else [])
            record=dict(node=node,population_profile=key,parent_race_id=race,founding_turn=turn,founding_capital=not members,
                        founding_year=year,migration_source_node=source['node'] if source else None,
                        source_civilization_id=source['population_profile'] if source else None,
                        migration_distance_m=distance(node,source['node']) if source else 0,cultural_branch=bool(source),
                        diaspora=True,diaspora_reason=rng.choice(reasons),diaspora_bonus=bonus)
            sites.append(record);ever_used.add(key)
            events.append(dict(record,status='diaspora_founded',turn=turn,radius_m=world_reach,suitability=scores[key][node]))
            options=diaspora_candidates()
        if options:possible=True
        if len(sites)>=target and not options:stop='capacity_target_reached';break
        if not possible:stop='no_eligible_expansion';break
    return sites,dict(version=3,effective_quotas=quotas,diaspora_interval_years=diaspora_interval_years,diaspora_bonus_used=sorted(bonus_used),used_civilizations=sorted(ever_used),start_year=year_offset,end_year=year_offset+(turn-1)*years_per_round,years_per_round=years_per_round,elapsed_years=(turn-1)*years_per_round,origin_min_separation_degrees=origin_min_separation_degrees,turns=turn,target_cities=target,placed_cities=len(sites),stop_reason=stop,events=events,
                      definition='Sufficient population means capacity-derived city quotas, plus at most one food-supported diaspora bonus per parent, subject to safe habitat, spacing and a 24-city lab ceiling; 128-round safety limit.')
