"""Two deterministic habitat passes: animals, then monsters.

Both are thinned point processes over the ground rather than a fixed anchor budget.
For a species `s` in cell `c` the intensity is

    lambda = density(tier) * occurrence * area_km2 * suitability * biome_weight

so the expected count is an integral over habitable land and doubling the land doubles
the creatures, with no cap anywhere. A cell places `floor(lambda) + [u < frac(lambda)]`
groups and picks the species in proportion to its share, which is the marked-process
construction built from the only primitives both implementations have: one uniform draw
and a cumulative weighted pick.

Tier is danger to a player, one to five, and it does the ecological work: density falls
geometrically with it, so prey are many and apex creatures are few, and territory and
settlement clearance grow with it.

The two passes never read each other. Animals hold hunting grounds; monsters hold
territory over the same ground, and a monster is excluded only by an equal or greater
monster, so a dragon's range may contain a goblin camp. These remain static habitat
proposals: no populations, migrations, or runtime spawning.
"""
import json
import math
import random
from pathlib import Path
from functools import lru_cache
from .terrain_tectonics import child_seed
from .terrain_world import options
from .terrain_erosion import sphere_grid
from .terrain_globe import direction

MEDIA=('land','shore','marine','freshwater')


def clamp(v):
    return max(0., min(1., v))


@lru_cache(maxsize=1)
def _document():
    return json.loads(Path(__file__).with_name('terrain_nest_profiles.json').read_text(encoding='utf-8'))


@lru_cache(maxsize=1)
def profiles():
    rows=_document()['profiles']
    if len({p['id'] for p in rows}) != len(rows):
        raise ValueError('Duplicate creature profile IDs')
    for p in rows:
        if p['medium'] not in MEDIA or not p['weights'] or any(v<=0 for v in p['weights'].values()):
            raise ValueError('Invalid nest profile: '+p['name'])
        if p['class'] not in ('animal','monster') or not 1<=p['tier']<=5:
            raise ValueError('Creature needs class animal or monster and tier 1..5: '+p['name'])
        if p['class']=='animal' and p.get('role') not in roles():
            raise ValueError('Animal needs a known role: '+p['name'])
    return rows


@lru_cache(maxsize=1)
def roles():
    """Feeding roles and the biomes they favour, shared by every animal that has one."""
    return _document()['roles']


def biome_weight(p,biome_id):
    """Species table first, then its role's, then no preference.

    Keys are decimal strings of natural biome ids, matching how civilization biome
    preferences are authored. An absent biome is habitat the species does not use.
    """
    table=p.get('biome_weights')
    if table is None and p.get('role'):table=roles()[p['role']].get('biome_weights')
    if not table:return 1.
    return table.get(str(biome_id),0.)


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
    # Keep sum(): CPython 3.12 sums floats with Neumaier compensation, so an
    # explicit a[0]*b[0]+a[1]*b[1]+a[2]*b[2] is a different (less accurate) value
    # by about one ULP and silently changes generated worlds on some seeds.
    return radius*math.acos(max(-1.,min(1.,sum(x*y for x,y in zip(a,b)))))


def tier_density(base,falloff,tier):
    """Groups per square kilometre at full suitability; a pyramid, not a ladder.

    The pyramid is a property of the tier, not of the species in it: a tier is a niche
    with a share of the living space, and the species at that tier divide it. Authoring
    twenty more tier one animals makes each of them rarer rather than making the world
    thirty percent more crowded, so the shape of the ecosystem survives the catalogue
    growing.

    `occurrence` divides this share among the tier's members and nothing else. It is
    authored as a pure function of `size`, so spending it as an absolute multiplier
    taxed the big creatures a second time for being big: tier five monsters average
    .26 against tier one's .68, which on top of the pyramid left them at a hundredth
    rather than a fortieth and emptied small worlds of anything worth fearing.
    """
    return base*falloff**(1-tier)


def habitat_cells(result,cfg,points,areas):
    """Every cell's habitat description, in grid order: the ground both passes read."""
    l=result['layers'];n=cfg.size;cells=[]
    for i,(x,z) in enumerate(points):
        f={k:v[z][x] for k,v in l.items()}
        water=f.get('water_type',0);wet=f.get('moisture',0)
        f.update(medium='marine' if water==1 else 'freshwater' if water and f.get('salinity',0)<.2 else 'salt_lake' if water else 'land',
                 depth=f.get('water_depth',0),dryness=1-clamp(wet),coast=f.get('maritime',0),
                 mountain=clamp(f.get('slope',0)/25),plains=clamp(1-f.get('slope',0)/15)*(1-abs(wet-.45)),
                 wetland=max(float(bool(water)),f.get('river',0),wet*math.exp(-f.get('slope',0)/8)),
                 cold=clamp((10-f.get('temperature',10))/25))
        cells.append(dict(node=i,x=x,z=z,area_km2=areas[i]/1e6,biome=int(f.get('natural_biome',f.get('biome',0))),
                          direction=direction(x,z,n),fields=f))
    return cells


def settled_directions(result,cfg):
    """Everything already standing on the surface, for clearance tests."""
    n=cfg.size
    sites=result.get('settlements',{}).get('sites',[])
    sites=sites+result.get('fisheries',{}).get('ports',[])+result.get('humans',{}).get('hamlets',[])
    return [s.get('direction') or direction(s['x'],s['z'],n) for s in sites]


def _place(kind_of,catalogue,result,cfg,cells,settled,radius,domain,density,falloff,clearance,dominance):
    """One thinned point process over the cells, shared by both passes.

    `dominance` decides whether a candidate is refused by what is already there: an
    animal only competes with its own species, a monster with anything of equal or
    greater tier.
    """
    o=options(cfg)
    rng=random.Random(child_seed(cfg.seed,domain,o['nest_variation']))
    placed=[];counts={p['id']:0 for p in catalogue}
    per_species=o['nest_per_species']
    # Distance to the nearest settled thing, once per cell. Keeping clear of people is
    # a property of the ground rather than of luck, so it belongs in the rate: reject a
    # draw that already happened and the world quietly holds far fewer creatures than
    # the density asked for.
    nearest=[min((distance(cell['direction'],s,radius) for s in settled),default=float('inf'))
             for cell in cells]
    # Where each species can live and how much room it has there. `room` is what the
    # species would claim if nothing else existed: how common it is, how well the
    # ground suits it, and how much ground there is.
    #
    # Plain accumulation, not sum(): CPython compensates a builtin sum of floats and
    # the port would have to replicate that to stay bit-exact, which is not worth
    # buying here.
    rooms=[];tier_room={};ground={}
    for cell,clear_of in zip(cells,nearest):
        # Land and open water are two ecosystems sharing a planet, and a species
        # belongs to exactly one of them: the medium gate in `suitability` sees to
        # that. Budget them apart or the sea decides how empty the land is -- measured
        # on one world, land was a quarter of the surface and held five per cent of
        # the animals, half a group per square kilometre against a teeming ocean.
        wet=cell['fields'].get('medium')!='land'
        ground[wet]=ground.get(wet,0.)+cell['area_km2'];here=[]
        for p in catalogue:
            if clear_of<clearance(p):continue
            weight=biome_weight(p,cell['biome'])
            if weight<=0:continue
            score,_=suitability(p,cell['fields'])
            if score<o['nest_min_suitability']:continue
            room=p['occurrence']*score*weight*cell['area_km2']
            if room<=0:continue
            here.append((p,wet,room,score))
            tier_room[(p['tier'],wet)]=tier_room.get((p['tier'],wet),0.)+room
        rooms.append(here)
    # The pyramid is a claim about the world, so it is a budget for the world: tier t
    # gets `density * falloff^(1-t)` groups per square kilometre of its own medium,
    # and that budget is then spread over whatever ground the tier can actually use.
    #
    # Sharing per cell instead loses a tier its share wherever no member qualifies,
    # and the low monster tiers are the specialised ones -- grave mites want a barrow,
    # shipbreaker crabs want any sea at all. Measured, that inverted the pyramid
    # outright: 114 tier four lairs against 9 tier one. A budget cannot be forfeited
    # by being fussy about where it is spent.
    budget={key:tier_density(density,falloff,key[0])*ground[key[1]]/room
            for key,room in tier_room.items() if room>0}
    rates=[[(p,budget[(p['tier'],wet)]*room,score) for p,wet,room,score in here] for here in rooms]
    for cell,shares in zip(cells,rates):
        if not shares:continue
        total=sum(rate for _,rate,_ in shares)
        # floor plus one Bernoulli draw: an exact discretisation while the cell rate is
        # below one, which it is almost everywhere, and no new distribution is needed.
        groups=int(total)
        if rng.random()<total-groups:groups+=1
        for _ in range(groups):
            p,score=_pick(rng,shares,total)
            if per_species and counts[p['id']]>=per_species:continue
            reach=p['spacing_m']*o['nest_spacing']/2
            if dominance(p,reach,cell,placed,radius):continue
            counts[p['id']]+=1
            placed.append(dict(id=f"{kind_of}-{p['id']}-{cell['node']}",species_id=p['id'],name=p['name'],
                               node=cell['node'],x=cell['x'],z=cell['z'],layer='surface',
                               direction=cell['direction'],biome=cell['biome'],tier=p['tier'],
                               family=p['family'],kind=p['kind'],size=p['size'],role=p.get('role'),
                               suitability=score,range_m=reach,**{'class':p['class']},
                               # A den or lair is a place you can find and raid; a herd,
                               # roost or shoal is only a range where you meet them.
                               den=p['kind'] in ('den','lair'),real=p['class']=='animal'))
    limit=o['nest_limit']
    if limit and len(placed)>limit:
        # A safety valve, not the thing that decides how full a world is. When it has
        # to bite it keeps the notable creatures: highest tier first, then by id.
        placed=sorted(placed,key=lambda a:(-a['tier'],a['id']))[:limit]
        counts={key:0 for key in counts}
        for a in placed:counts[a['species_id']]+=1
    return sorted(placed,key=lambda a:a['id']),counts


def _pick(rng,shares,total):
    """The species that claims this group, in proportion to its share of the cell."""
    draw=rng.random()*total;cursor=0.
    for p,rate,score in shares:
        cursor+=rate
        if draw<=cursor:return p,score
    return shares[-1][0],shares[-1][2]


def add_animals(result,cfg):
    """Hunting grounds. Prey are many and small-ranged, predators few and wide."""
    if not cfg.world_recipe or cfg.phase<7:return result
    o=options(cfg);radius=result['effective_config']['globe_radius']
    points,areas,_=sphere_grid(cfg.size,radius)
    cells=habitat_cells(result,cfg,points,areas)
    settled=settled_directions(result,cfg)
    catalogue=[p for p in profiles() if p['class']=='animal']
    density=o['animal_density']*o['nest_density']
    def clearance(p):
        # Game keeps its distance from people in proportion to how dangerous it is.
        return o['nest_settlement_clearance']*p['tier']/3
    def dominance(p,reach,cell,placed,radius):
        # Territorial within a species only: a wolf range over a deer range is the
        # point of the map, not a collision.
        return any(a['species_id']==p['id'] and distance(a['direction'],cell['direction'],radius)<max(reach,a['range_m'])
                   for a in placed)
    sites,counts=_place('animal',catalogue,result,cfg,cells,settled,radius,'animals-v1',
                        density,o['animal_tier_falloff'],clearance,dominance)
    result['wildlife']=dict(version=1,sites=sites,
        diagnostics=[dict(species_id=p['id'],name=p['name'],tier=p['tier'],role=p.get('role'),placed=counts[p['id']])
                     for p in catalogue],
        profiles=catalogue,catalogue_count=len(catalogue),roles=roles(),
        method='Thinned point process over habitable ground: density falls geometrically with danger tier, so prey are common and apex animals rare. Hunting grounds are a centre and a radius; only a species competes with itself.',
        limits='Static habitat proposals. No prey carrying capacity, herd sizes, migrations or runtime spawning; a range is where an animal may be met, not a simulated population.')
    return result


def add_monsters(result,cfg):
    """Territory. A greater monster excludes an equal, and tolerates a lesser."""
    if not cfg.world_recipe or cfg.phase<7:return result
    o=options(cfg);radius=result['effective_config']['globe_radius']
    points,areas,_=sphere_grid(cfg.size,radius)
    cells=habitat_cells(result,cfg,points,areas)
    settled=settled_directions(result,cfg)
    catalogue=[p for p in profiles() if p['class']=='monster']
    density=o['monster_density']*o['nest_density']*o['nest_fantasy']
    def clearance(p):
        return o['nest_settlement_clearance']*p['tier']
    def dominance(p,reach,cell,placed,radius):
        # Rank, not spacing: only an equal or greater monster holds the ground against
        # this one, so lesser lairs nest inside a greater territory.
        return any(a['tier']>=p['tier'] and distance(a['direction'],cell['direction'],radius)<max(reach,a['range_m'])
                   for a in placed)
    sites,counts=_place('nest',catalogue,result,cfg,cells,settled,radius,'monsters-v1',
                        density,o['monster_tier_falloff'],clearance,dominance)
    result['beast_nests']=dict(version=2,sites=sites,
        diagnostics=[dict(species_id=p['id'],name=p['name'],tier=p['tier'],placed=counts[p['id']])
                     for p in catalogue],
        profiles=[p for p in profiles() if p['class']=='monster'],catalogue_count=len(catalogue),
        method='Thinned point process keyed to magic and terrain, independent of the animals. Density falls geometrically with danger tier and territory grows with it; a lair is refused only by an equal or greater lair, so lesser monsters live inside a greater territory and hunting grounds overlap.',
        limits='Static habitat proposals. No hostility, population, patrol or runtime spawning; territory is a claim on ground, not a simulated creature.')
    return result


def add_nests(result,cfg):
    """Both passes, animals first. They never read each other."""
    add_animals(result,cfg)
    add_monsters(result,cfg)
    return result
