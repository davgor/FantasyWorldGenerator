"""Two deterministic habitat passes: animals, then monsters.

Both are thinned point processes over the ground rather than a fixed anchor budget.
For a species `s` in cell `c` the intensity is

    lambda = density(tier) * occurrence * area_km2 * suitability * biome_weight * danger_ramp

so the expected count is an integral over habitable land and doubling the land doubles
the creatures, with no cap anywhere. A cell places `floor(lambda) + [u < frac(lambda)]`
groups and picks the species in proportion to its share, which is the marked-process
construction built from the only primitives both implementations have: one uniform draw
and a cumulative weighted pick.

Tier is danger to a player, one to five, and it does the ecological work: density falls
geometrically with it, so prey are many and apex creatures are few, and territory and
settlement clearance grow with it, and `danger_ramp` slides it outward from people.

The two passes never read each other. Animals hold hunting grounds; monsters hold
territory over the same ground, and a monster is excluded only by an equal, so a dragon's
range may contain a goblin camp whichever of the two was drawn first. These remain static
habitat proposals: no populations, migrations, or runtime spawning.

Placement resolves at the raster cell, and that is the ceiling on all of it: every site in
a cell carries the cell's own direction, so a tier holds at most one lair per cell and a
species at most one den per cell whatever else the spacing rule does. `saturation`
publishes the gap that leaves -- cells reached, groups drawn, placed, refused -- because
the pyramid is exact in the rate and clipped in what is placed, and a flat placed
histogram is unreadable without both.

The rule does more than that, though this module used to say it did not. It claimed no
territory was as wide as the raster pitch, so the test only ever compared a cell against
itself; the grid is lat/lon, the rings beside the poles are packed a hundred times tighter
than the equator, and a cross-cell refusal is ordinary ground there. See `_blocked`, which
carries the bound that is actually true, and board/NEST-SAME-CELL-CLAIM-IS-FALSE.md.

The same ceiling swallows the danger gradient, so `saturation` states that in the same
shape. `rate_distance_m` is where the rate puts a tier and `placed_distance_m` is where
the sites ended up; the first rises with tier because `danger_ramp` makes it, the second
barely moves because a saturated tier is pinned to the cells it reaches and every tier
reaches nearly the same ground.

`diagnostics` says why a species is not in the world, and `reachability` counts how many
of the catalogue this world could hold against how many it does. Both are statements about
THIS world: eligibility moves with the seed, so a per-world count is a sample. The one
world-independent verdict is `never satisfiable`, and it is decided from the profile alone.
"""
import bisect
import json
import math
import random
from pathlib import Path
from functools import lru_cache
from .terrain_tectonics import child_seed
from .terrain_world import options, HIDDEN_NETWORKS
from .terrain_erosion import sphere_grid
from .terrain_globe import direction
from .terrain_scale import reach_scale

MEDIA=('land','shore','marine','freshwater')

# 2: `wildlife` gained `saturation`. The placed set alone cannot say whether a flat tier
# histogram is the rate or the raster clipping it, and it was the raster.
# 3: `saturation` gained the two distance columns, `diagnostics` gained `cells` and
# `reason`, and the block gained `reachability`. All additive; no site moved.
WILDLIFE_VERSION=3
# 3: `beast_nests` gained `saturation`, and a lair is now refused by an equal lair only
# rather than by an equal or greater one. Every tier's placed count moves, and a consumer
# that inferred danger from the shape of the histogram was reading a different shape.
# 4: the same additive reporting as `wildlife` 3.
BEAST_NESTS_VERSION=4

# How far out the danger ramp turns over, in reference-world metres. Authored against
# the 11.15 km reference like every other reach in this repo and scaled by
# circumference, because an absolute metre constant is sub-cell on a 200 km world and
# ramps nothing. See `danger_ramp`.
NEST_DANGER_SPAN_M=300.
# The share of the rate that survives at the wrong end of the ramp. Nothing may become
# impossible: a floor of zero would make a tier five species unplaceable on the doorstep
# of a town and a tier one species unplaceable in the wilderness, and neither is true.
NEST_DANGER_FLOOR=.2

# Why a species is not in a world. Five values, because "absent" bundles one catalogue
# defect and one placement rule with two ordinary facts about a particular world, and a
# count that does not separate them is the thing `key_locations` grew `diagnostics` to
# stop doing.
PLACED='placed'
LOST_THE_DRAW='lost the draw to incumbents'
ABSENT_FROM_THIS_WORLD='conditions absent from this world'
NEVER_SATISFIABLE='never satisfiable'
# The fifth is not a world reason and must not be reported as one. A species whose habitat
# is the ground people stand on -- `graves` exists where people bury people -- can have all
# its eligible cells inside the settlement clearance, and the clearance refuses exactly
# them. Measured at size 33: 57 profiles on seed 42, 32 on seed 7, 1 on seed 73, all of them
# graveyard and barrow creatures. It swings that hard because it depends on how much grave
# ground a world puts outside a settlement's own cell, which is why it is reported per world
# like everything else here. Calling it "conditions absent from this world" sends a reader
# to look at the terrain, where there is nothing to find.
CLEARED_OUT='its only ground is inside a settlement clearance'
REACH_REASONS=(PLACED,LOST_THE_DRAW,ABSENT_FROM_THIS_WORLD,NEVER_SATISFIABLE,CLEARED_OUT)

# Ley schools generation can never raise. A weight on one contributes nothing anywhere;
# a `requires` on one can be met nowhere. See docs/hidden-schools.md.
DORMANT_FIELDS=frozenset('ley_'+name for name in HIDDEN_NETWORKS)


def clamp(v):
    return max(0., min(1., v))


def never_satisfiable(p):
    """Whether no world generation can produce admits this profile -- from the profile alone.

    This is the whole of what is decidable without generating worlds, and it is much less
    than the set of profiles a given world happens not to hold. Measured across five seeds
    at size 33: 579 of 680 profiles are eligible on all five, 53 on some but not all, and
    48 on none -- and only 25 of that 48 are provable here. Calling the other 23
    unreachable would be asserting a search nobody ran; `polar-bear` and `sea-otter` want
    ground those five worlds did not roll, not ground no world can carry.

    A `requires` on a dormant school is the provable case because the threshold is a hard
    gate against a layer that is identically zero in every world the generator can build.
    A profile that merely *scores* on one is not proved unreachable, only handicapped, and
    `test_creature_movement` asserts that separately.
    """
    return any(k in DORMANT_FIELDS and v>0 for k,v in p['requires'].items())


def reach_reason(p,cells_reached,placed_count,cleared_out=False):
    """One of `REACH_REASONS` for a species, given what this world did with it."""
    if placed_count:return PLACED
    if never_satisfiable(p):return NEVER_SATISFIABLE
    if cells_reached:return LOST_THE_DRAW
    return CLEARED_OUT if cleared_out else ABSENT_FROM_THIS_WORLD


def reachability(catalogue,species_cells,counts):
    """Authored, eligible here, placed here -- and a scope line saying which is which.

    The three integers `PRODUCT-REACHABILITY-REPORT` asked for, with the middle one named
    honestly. "Ever reachable" is a search over seed, raster and every world option, not a
    check, and it was measured to be genuinely world-dependent rather than merely
    expensive: 53 of 680 profiles change eligibility across five seeds at one raster. So
    the middle integer is this world's, `never_satisfiable` is the part that is proved, and
    the gap between them is the part nobody has searched.
    """
    return dict(authored=len(catalogue),
                eligible=sum(1 for p in catalogue if species_cells[p['id']]),
                placed=sum(1 for p in catalogue if counts[p['id']]),
                never_satisfiable=sum(1 for p in catalogue if never_satisfiable(p)),
                scope='`eligible` and `placed` count this world only and move with the seed; '
                      'they are a sample, not a capability. `never_satisfiable` is decided '
                      'from the profile alone and holds for every world.')


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
        # Monsters have no feeding role, so a monster without its own table falls
        # through `biome_weight` to 1. and is equally at home on a glacier and in a
        # rainforest. That fallback was the whole of the monster half's opinion about
        # biome until the 2026-09-20 ruling; refuse it rather than let it come back.
        if p['class']=='monster' and not p.get('biome_weights'):
            raise ValueError('Monster needs its own biome_weights: '+p['name'])
    return rows


@lru_cache(maxsize=1)
def roles():
    """Feeding roles and the biomes they favour, shared by every animal that has one."""
    return _document()['roles']


def biome_weight(p,biome_id):
    """Species table first, then its role's, then no preference.

    Keys are decimal strings of natural biome ids, matching how civilization biome
    preferences are authored. An absent biome is habitat the species does not use.

    An animal resolves its table through its feeding role; a monster carries its own,
    authored from a family template with per-species deltas, and `profiles()` refuses a
    monster that has none. So the bare `return 1.` is unreachable for the shipped
    catalogue: it survives only for a caller passing a hand-built profile. Every monster
    table names every live biome for the same reason -- an absent key is exclusion, not
    neutrality, so a five-key table silently forbids a quarter of the catalogue the
    ground it was measured on.
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


def danger_ramp(tier,clear_of,span):
    """Rate multiplier that slides danger outward from settled ground.

    The clearance below is a hard floor and stays one: nothing lairs in the town
    square. But a cutoff is the wrong shape for a difficulty gradient and cannot make
    one at any resolution -- scaling `clearance * tier` up digs a wider hole around
    every settlement rather than ramping anything, and measured on a 200 km world it
    left a tier five apex monster and a tier one prey animal at the same median 6.45 km
    from the nearest town against a source comment declaring a 3:1 intent.

    So the ramp is continuous and lives in the rate. `near` is 1 on a settlement's
    doorstep and falls to a half one span out; a tier one species is drawn towards it
    and a tier five species away from it, in proportion to danger. `span` grows with
    circumference, and a floor keeps every tier possible on every ground.

    A ratio of squares rather than an exponential: no `pow`, no `exp`, nothing whose
    last bit depends on the libm the native build links against. Squared because the
    plain ratio is too gentle to be worth having -- the usable band on a settled world
    is about one span wide, and across it `span/(span+d)` swings by a factor of two
    however low the floor goes, which is not a gradient a player would notice.

    The tier's total is untouched. `budget` renormalises by `tier_room`, which sums the
    same factor, so this redistributes a tier over the ground and never changes how many
    of it a world holds.
    """
    reach=span*span;out=clear_of*clear_of
    near=reach/(reach+out)
    danger=(tier-1)/4.
    return NEST_DANGER_FLOOR+(1-NEST_DANGER_FLOOR)*(danger*(1-near)+(1-danger)*near)


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


# Slack on the latitude bound in `nearest_settled`, in radians. The bound is exact in real
# arithmetic; this absorbs the rounding in the two `asin` calls that stand in for the
# latitudes. 1e-9 rad is 3e-5 m on the widest world this product ships, ten orders of
# magnitude above the error it covers, and being generous costs at most one extra
# candidate per cell.
LATITUDE_SLACK=1e-9


def nearest_settled(cells,settled,radius):
    """Distance from every cell to the nearest settled thing, in grid order.

    Float for float the same list as a `min` of `distance` over every settled site, and
    for a reason rather than by measurement: `distance` is `radius*acos(clamp(dot))`,
    `acos` is decreasing and `clamp` is not, so the smallest distance is the one at the
    LARGEST dot product, and the value returned here is that same expression applied to
    that same dot. Written as a `min` the scan cannot stop early; written as an argmax it
    can, and this is the only reason to write it the second way.

    The stopping rule is the one new piece of mathematics. The angle between two unit
    vectors is at least the difference of their latitudes, whatever their longitudes do.
    So with the sites sorted by latitude and walked outwards from the cell's own latitude,
    nearest latitude first, the walk can stop the moment that difference reaches the best
    angle already found: everything still unvisited is at least that far away on both
    sides, because the side with the smaller remaining gap is the one being taken.

    Cost is what changes. The old form was one `acos` per cell per settled site -- 108
    million of them on a size 513 world holding 410 settled things.
    """
    if not settled:return [float('inf')]*len(cells)
    order=sorted(range(len(settled)),
                 key=lambda i:(math.asin(max(-1.,min(1.,settled[i][1]))),i))
    lats=[math.asin(max(-1.,min(1.,settled[i][1]))) for i in order]
    dirs=[settled[i] for i in order]
    total=len(lats);out=[]
    for cell in cells:
        c=cell['direction'];phi=math.asin(max(-1.,min(1.,c[1])))
        left=bisect.bisect_left(lats,phi);right=left
        best=-2.;angle=math.pi
        while True:
            gap_l=phi-lats[left-1] if left else None
            gap_r=lats[right]-phi if right<total else None
            if gap_l is None and gap_r is None:break
            if gap_r is None or (gap_l is not None and gap_l<=gap_r):
                gap=gap_l;left-=1;at=left
            else:
                gap=gap_r;at=right;right+=1
            # The candidate taken is the nearest in latitude on either side, so if it is
            # already further out than the best angle, so is everything behind it.
            #
            # The slack is ADDED, so the walk goes one candidate too far rather than one
            # too few. A cell whose nearest settled thing is due north or south of it has
            # a latitude gap exactly equal to its angle, and subtracting the slack stops
            # the walk on the tie: measured at size 33, that lost the argmax at 2 of 994
            # cells and moved `rate_distance_m` in the last three digits.
            if gap>=angle+LATITUDE_SLACK:break
            # Keep sum(): the compensated builtin is what `distance` uses, and an
            # explicit three-term dot product differs from it by about one ULP.
            dot=sum(x*y for x,y in zip(c,dirs[at]))
            if dot>best:best=dot;angle=math.acos(max(-1.,min(1.,best)))
        out.append(radius*math.acos(max(-1.,min(1.,best))))
    return out


def _place(kind_of,catalogue,result,cfg,cells,settled,radius,domain,density,falloff,clearance,bucket):
    """One thinned point process over the cells, shared by both passes.

    `bucket` names the company a candidate has to keep its distance from: an animal
    competes only with its own species, a monster only with its own tier. Everything in
    the same bucket holds ground against everything else in it, and nothing holds ground
    against another bucket -- which is why a wolf range crosses a deer range and a lesser
    lair nests inside a greater territory.

    Scoping the scan to the bucket is also what keeps it affordable. Comparing a
    candidate against every site already placed is quadratic in the pass, and this pass
    is the dominant cost of a generation; comparing it only against its own bucket is the
    same predicate over a fifth (monsters, five tiers) or a three-hundredth (animals, one
    species) of the list. Order inside a bucket is placement order either way, and the
    test short-circuits, so the answer is identical.
    """
    o=options(cfg)
    rng=random.Random(child_seed(cfg.seed,domain,o['nest_variation']))
    placed=[];counts={p['id']:0 for p in catalogue}
    per_species=o['nest_per_species']
    # Distance to the nearest settled thing, once per cell. Keeping clear of people is
    # a property of the ground rather than of luck, so it belongs in the rate: reject a
    # draw that already happened and the world quietly holds far fewer creatures than
    # the density asked for.
    nearest=nearest_settled(cells,settled,radius)
    # ...and how far out a cell is decides how dangerous the ground is, continuously.
    # The clearance below still refuses the doorstep outright; this is the ramp between
    # the doorstep and the wilderness. Authored against the reference world, so it means
    # the same thing at every width.
    span=NEST_DANGER_SPAN_M*reach_scale(2*math.pi*radius)
    # Where each species can live and how much room it has there. `room` is what the
    # species would claim if nothing else existed: how common it is, how well the
    # ground suits it, and how much ground there is.
    #
    # Plain accumulation, not sum(): CPython compensates a builtin sum of floats and
    # the port would have to replicate that to stay bit-exact, which is not worth
    # buying here.
    rooms=[];tier_room={};ground={};tier_cells={}
    # How many cells each species could live in at all, which is the per-species form of
    # the same ceiling `tier_cells` names. A species with none of these is absent for a
    # reason about the world; a species with some and no sites lost the draw. Those are
    # different problems and `diagnostics` used to report one number for both.
    species_cells={p['id']:0 for p in catalogue}
    # Two of the four gates below read nothing about a cell but its medium and its biome,
    # and a world has about a dozen distinct pairs of those against tens of thousands of
    # cells -- twelve at size 65, twelve at size 129. So the pair decides the candidate
    # list once and every cell holding it reuses that list, with the biome weight already
    # resolved. Measured on the size 65 world: of the cell-by-species pairs this loop used
    # to walk, the biome gate refuses 44% of the animal ones and the medium gate a further
    # 26%, and the medium gate alone refuses 67% of the monster ones -- every monster
    # biome table names every live biome, so the monster half has no opinion about biome
    # at all and all of its pruning here is medium.
    #
    # Order inside a list is catalogue order, unchanged. It has to be: `total` below is a
    # float sum over the list and `_pick` walks it cumulatively, so a reordering is a
    # different world even when it is the same set.
    #
    # Nothing is hoisted out of `suitability`, which still re-tests the medium it was
    # selected on. Keeping that call whole is worth more than the duplicated comparison:
    # it stays the single published answer to "can this species live here".
    by_ground={}
    def ground_candidates(medium,biome):
        row=by_ground.get((medium,biome))
        if row is None:
            row=[]
            for p in catalogue:
                if medium!=('land' if p['medium']=='shore' else p['medium']):continue
                weight=biome_weight(p,biome)
                if weight>0:row.append((p,weight,clearance(p)))
            by_ground[(medium,biome)]=row
        return row
    for cell,clear_of in zip(cells,nearest):
        # Land and open water are two ecosystems sharing a planet, and a species
        # belongs to exactly one of them: the medium gate in `suitability` sees to
        # that. Budget them apart or the sea decides how empty the land is -- measured
        # on one world, land was a quarter of the surface and held five per cent of
        # the animals, half a group per square kilometre against a teeming ocean.
        medium=cell['fields'].get('medium');wet=medium!='land'
        ground[wet]=ground.get(wet,0.)+cell['area_km2'];here=[]
        for p,weight,clear_needed in ground_candidates(medium,cell['biome']):
            if clear_of<clear_needed:continue
            score,_=suitability(p,cell['fields'])
            if score<o['nest_min_suitability']:continue
            room=p['occurrence']*score*weight*danger_ramp(p['tier'],clear_of,span)*cell['area_km2']
            if room<=0:continue
            here.append((p,wet,room,score))
            species_cells[p['id']]+=1
            tier_room[(p['tier'],wet)]=tier_room.get((p['tier'],wet),0.)+room
            # How much of the raster a tier can reach at all. This is the ceiling on what
            # it can place, not a curiosity: see `saturation` below.
            tier_cells.setdefault(p['tier'],set()).add(cell['node'])
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
    # Where the rate puts each tier, weighted by the rate itself: the mean distance from
    # settled ground of the groups the intensity asks for. This is `danger_ramp` integrated
    # over the world and it is the only place the danger gradient is exact. What is placed
    # cannot show it -- a saturated tier fills the cells it reaches whatever the rate said
    # about which of them it preferred, and every tier reaches nearly the same ground,
    # because the only tier-keyed gate on a cell is a clearance of a few hundred metres
    # against a pitch of kilometres. Measured on the reference world: ablating the ramp
    # entirely moves the spread of placed tier medians by 0.02 km.
    #
    # Plain accumulation and a guard on `settled`: with nothing settled anywhere `clear_of`
    # is infinite, and an infinite times a zero rate is a NaN in the world document.
    rate_reach={};rate_weight={}
    if settled:
        for clear_of,shares in zip(nearest,rates):
            for p,rate,_ in shares:
                rate_reach[p['tier']]=rate_reach.get(p['tier'],0.)+rate*clear_of
                rate_weight[p['tier']]=rate_weight.get(p['tier'],0.)+rate
    clear_by_node={cell['node']:clear_of for cell,clear_of in zip(cells,nearest)}
    # Every group the intensity asked for, by tier, whether or not it found room. The
    # placed set is this minus everything the territory rule refused, and the two differ
    # by an order of magnitude, so publishing only the placed set hides which of the two
    # a flat histogram is describing. See `saturation`.
    drawn={}
    # The company a bucket keeps, indexed twice rather than held as one list. `at_node`
    # is the sites in a given cell, `on_row` the sites in a given grid row, and `widest`
    # the largest territory the bucket has placed so far. `_blocked` says what each is
    # for; the same sites are in both, and appended to both in placement order.
    at_node={};on_row={};widest={}
    # Metres between two grid rows. `direction` puts row z at latitude pi/2 - pi*z/(n-1),
    # so this is the meridional pitch and it does not vary with latitude, which is the
    # whole reason `_blocked` bounds by row rather than by cell.
    pitch=radius*math.pi/(cfg.size-1)
    for cell,shares in zip(cells,rates):
        if not shares:continue
        total=sum(rate for _,rate,_ in shares)
        # floor plus one Bernoulli draw: an exact discretisation while the cell rate is
        # below one, which it is almost everywhere, and no new distribution is needed.
        groups=int(total)
        if rng.random()<total-groups:groups+=1
        # A species this cell has already REFUSED needs no second answer: the company
        # only ever grows and the test is a disjunction over it, so the answer cannot
        # come back the other way. A cell draws about ninety groups from a few dozen
        # species, so it is asked the same question many times -- 62% of animal draws
        # and 47% of monster draws at size 65 repeat a (cell, species) pair.
        #
        # A species this cell has already PLACED is deliberately NOT memoised, though it
        # will be refused too. Memoising it would mean asserting that a second site in
        # the same cell is always refused, which needs `reach` to be positive: true of
        # the shipped catalogue and of the option bounds, but an assumption, and
        # `_blocked` answers it from `at_node` in one dict hit regardless. Both forms
        # were timed at size 65 and neither is faster.
        settled_here=set()
        for _ in range(groups):
            p,score=_pick(rng,shares,total)
            drawn[p['tier']]=drawn.get(p['tier'],0)+1
            if per_species and counts[p['id']]>=per_species:continue
            if p['id'] in settled_here:continue
            reach=p['spacing_m']*o['nest_spacing']/2
            b=bucket(p)
            if _blocked(at_node.get(b),on_row.get(b),widest.get(b,0.),cell,reach,radius,pitch):
                settled_here.add(p['id']);continue
            counts[p['id']]+=1
            site=dict(id=f"{kind_of}-{p['id']}-{cell['node']}",species_id=p['id'],name=p['name'],
                      node=cell['node'],x=cell['x'],z=cell['z'],layer='surface',
                      direction=cell['direction'],biome=cell['biome'],tier=p['tier'],
                      family=p['family'],kind=p['kind'],size=p['size'],role=p.get('role'),
                      suitability=score,range_m=reach,**{'class':p['class']},
                      # A den or lair is a place you can find and raid; a herd,
                      # roost or shoal is only a range where you meet them.
                      den=p['kind'] in ('den','lair'),real=p['class']=='animal')
            at_node.setdefault(b,{}).setdefault(cell['node'],[]).append(site)
            on_row.setdefault(b,{}).setdefault(cell['z'],[]).append(site)
            if reach>widest.get(b,0.):widest[b]=reach
            placed.append(site)
    limit=o['nest_limit']
    if limit and len(placed)>limit:
        # A safety valve, not the thing that decides how full a world is. When it has
        # to bite it keeps the notable creatures: highest tier first, then by id.
        placed=sorted(placed,key=lambda a:(-a['tier'],a['id']))[:limit]
        counts={key:0 for key in counts}
        for a in placed:counts[a['species_id']]+=1
    # Which of the species that found nothing were refused by the clearance rather than by
    # the world. Scanned only over the cells close enough to be refused by anything in the
    # catalogue, and only for species with no cells at all, so it is a few hundred species
    # against a few hundred cells rather than a second pass over the raster.
    ceiling=max((clearance(p) for p in catalogue),default=0.)
    close=[(cell,clear_of) for cell,clear_of in zip(cells,nearest) if clear_of<ceiling]
    floor=o['nest_min_suitability']
    cleared_out={p['id']:(not species_cells[p['id']]) and any(
                     clear_of<clearance(p) and biome_weight(p,cell['biome'])>0
                     and suitability(p,cell['fields'])[0]>=floor
                     for cell,clear_of in close)
                 for p in catalogue}
    # What the rate asked for, what the raster could hold, and what survived. A tier can
    # hold at most one site per bucket per cell, because every site in a cell carries the
    # cell's own direction and no species' reach is as wide as the raster pitch at any
    # width this product ships -- so a tier whose budget exceeds `cells` is pinned there
    # and stays pinned however much ground the world gains. Read a flat placed histogram
    # against `drawn` and `cells` before reading it as the ecology.
    kept={};kept_reach={}
    for a in placed:
        kept[a['tier']]=kept.get(a['tier'],0)+1
        kept_reach[a['tier']]=kept_reach.get(a['tier'],0.)+clear_by_node[a['node']]
    saturation=[dict(tier=t,cells=len(tier_cells.get(t,())),drawn=drawn.get(t,0),
                     placed=kept.get(t,0),refused=drawn.get(t,0)-kept.get(t,0),
                     rate_distance_m=(rate_reach[t]/rate_weight[t]
                                      if settled and rate_weight.get(t) else None),
                     placed_distance_m=(kept_reach[t]/kept[t]
                                        if settled and kept.get(t) else None))
                for t in sorted(set(tier_cells)|set(drawn)|set(kept))]
    return sorted(placed,key=lambda a:a['id']),counts,species_cells,cleared_out,saturation


def _blocked(at_node,on_row,widest,cell,reach,radius,pitch):
    """Whether this bucket already holds ground against a candidate in this cell.

    Exactly `any(distance(a,cell) < max(reach, a.range_m))` over everything the bucket has
    placed, and every comparison below IS that predicate on a real pair. What changes is
    which pairs are worth forming.

    **Same cell first.** A site sits at its cell's centre, so a second site in the same
    cell is at distance zero and refused by any positive reach -- and same-cell is where
    the refusals are. Measured at size 65: 71% of every comparison the flat scan made was
    a walk towards a blocker that turned out to be in the candidate's own cell, usually
    the one appended last, because a cell that has just placed something keeps drawing.
    The test is still the real predicate rather than an assertion that reach is positive.

    **Then the rows that `reach` can cross.** `direction` puts grid row z at latitude
    pi/2 - pi*z/(n-1), and the angle between two unit vectors is at least the difference
    of their latitudes, so two sites r rows apart are at least r*pitch apart on the sphere
    whatever their longitudes are. A blocker has to be nearer than `max(reach, range_m)`,
    so it has to be inside that many rows. One row is added to the bound, because it is
    exact in real arithmetic and a raster row is cheaper than an argument about the last
    bit of a divide.

    This is NOT the claim that only the same cell can ever block, which this module and
    `docs/conformance/creature-placement.md` both used to make and which is false. The
    grid is lat/lon, so the rings beside the poles are packed far tighter than the
    equator -- 2.4 m against a 391 m equatorial pitch at size 513 on a 200 km world, and
    611 m at size 33 -- and a cross-cell refusal is ordinary ground there rather than an
    edge case. Measured at size 65: 426 of 9777 monster refusals and 50 of 47311 animal
    refusals have their blocker in another cell. The row band finds all of them; a
    same-cell test would place 476 sites the flat scan refuses. See board/
    NEST-SAME-CELL-CLAIM-IS-FALSE.md.
    """
    here=at_node.get(cell['node']) if at_node else None
    facing=cell['direction']
    if here:
        for a in here:
            if distance(a['direction'],facing,radius)<max(reach,a['range_m']):return True
    if not on_row:return False
    band=int(max(reach,widest)/pitch)+1
    z=cell['z']
    for row in range(z-band,z+band+1):
        for a in on_row.get(row,()):
            if distance(a['direction'],facing,radius)<max(reach,a['range_m']):return True
    return False


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
    def bucket(p):
        # Territorial within a species only: a wolf range over a deer range is the
        # point of the map, not a collision.
        return p['id']
    sites,counts,species_cells,cleared_out,saturation=_place('animal',catalogue,result,cfg,cells,settled,radius,'animals-v1',
                                         density,o['animal_tier_falloff'],clearance,bucket)
    result['wildlife']=dict(version=WILDLIFE_VERSION,sites=sites,
        diagnostics=[dict(species_id=p['id'],name=p['name'],tier=p['tier'],role=p.get('role'),
                          placed=counts[p['id']],cells=species_cells[p['id']],
                          reason=reach_reason(p,species_cells[p['id']],counts[p['id']],cleared_out[p['id']]))
                     for p in catalogue],
        saturation=saturation,reachability=reachability(catalogue,species_cells,counts),
        profiles=catalogue,catalogue_count=len(catalogue),roles=roles(),
        method='Thinned point process over habitable ground: density falls geometrically with danger tier, so prey are common and apex animals rare. Hunting grounds are a centre and a radius; only a species competes with itself. `saturation` reports, per tier, the raster cells the tier can reach, the groups the rate drew, what was placed, what territory refused, and the mean distance from settled ground of the rate and of the placed set. `diagnostics` reports, per species, the cells it could live in and why it is not here; `reachability` counts the catalogue against what this world holds.',
        limits='Static habitat proposals. No prey carrying capacity, herd sizes, migrations or runtime spawning; a range is where an animal may be met, not a simulated population. Placement resolves at the raster cell: every site in a cell carries the cell centre, so the spacing rule can keep only one site per species per cell and a species whose rate exceeds the cells it reaches is pinned there rather than growing with the ground. The pyramid is exact in `saturation.drawn` and clipped in `sites`, and the danger gradient is exact in `saturation.rate_distance_m` and clipped the same way. `reachability.eligible` and `.placed` are this world only and move with the seed; only `never_satisfiable` holds for every world.')
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
    def bucket(p):
        # Rank, not spacing, and an equal only. A greater monster excludes an equal and
        # tolerates a lesser, which is what "a dragon's range may contain a goblin camp"
        # has always meant. The rule used to read `a['tier']>=p['tier']`, which says the
        # opposite in one direction: a goblin drawn after the dragon was refused by it,
        # so a lesser lair nested inside a greater territory only when the draw happened
        # to reach it first. Refusing by rank also refused the pyramid -- a tier one
        # candidate was held off by every lair on the world while a tier five was held
        # off only by other tier fives.
        return p['tier']
    sites,counts,species_cells,cleared_out,saturation=_place('nest',catalogue,result,cfg,cells,settled,radius,'monsters-v1',
                                         density,o['monster_tier_falloff'],clearance,bucket)
    result['beast_nests']=dict(version=BEAST_NESTS_VERSION,sites=sites,
        diagnostics=[dict(species_id=p['id'],name=p['name'],tier=p['tier'],
                          placed=counts[p['id']],cells=species_cells[p['id']],
                          reason=reach_reason(p,species_cells[p['id']],counts[p['id']],cleared_out[p['id']]))
                     for p in catalogue],
        saturation=saturation,reachability=reachability(catalogue,species_cells,counts),
        profiles=[p for p in profiles() if p['class']=='monster'],catalogue_count=len(catalogue),
        method='Thinned point process keyed to magic and terrain, independent of the animals. Density falls geometrically with danger tier and territory grows with it; a lair is refused only by an equal lair, so a greater monster tolerates a lesser inside its territory and hunting grounds overlap. `saturation` reports, per tier, the raster cells the tier can reach, the lairs the rate drew, what was placed, what territory refused, and the mean distance from settled ground of the rate and of the placed set. `diagnostics` reports, per species, the cells it could live in and why it is not here; `reachability` counts the catalogue against what this world holds.',
        limits='Static habitat proposals. No hostility, population, patrol or runtime spawning; territory is a claim on ground, not a simulated creature. Placement resolves at the raster cell: every lair in a cell carries the cell centre and no species\' territory is as wide as the raster pitch, so a tier holds at most one lair per cell and a tier whose rate exceeds the cells it reaches is pinned at that ceiling however much ground the world gains. The pyramid is exact in `saturation.drawn` and clipped in `sites`, and the danger gradient is exact in `saturation.rate_distance_m` and clipped the same way: danger ramps outward from people in the rate and the placed medians barely move. `reachability.eligible` and `.placed` are this world only and move with the seed; only `never_satisfiable` holds for every world. `saturation` reports what this pass produced: a divine visitation purges lairs from `sites` afterwards, so the two stop agreeing once one has run.')
    return result


def add_nests(result,cfg):
    """Both passes, animals first. They never read each other."""
    add_animals(result,cfg)
    add_monsters(result,cfg)
    return result
