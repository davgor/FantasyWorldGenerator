"""Creatures that do not hold ground: the herds, swarms, followers and unhoused dead.

The nest passes place everything as if it lived somewhere. Most creatures do. The ones that
do not are here, and each moves for a different reason, which is why they are separate
classes rather than one "wanders" flag:

  migratory  follows the green wave -- high open pasture in the warm months, sheltered low
             ground in the cold, the same two moves every year. Routes are inherited, so a
             herd walking the same ground each year is the correct behaviour, not a
             limitation
  irruptive  normally sparse; when marginal ground stops supporting them they go, in a
             body, and keep going until something feeds them. Not a season -- a trigger,
             and since `world_clock` exists the trigger is a particular year being bad.
             A group whose year is ordinary stays in the solitary phase and carries
             `route_status: "solitary"`, which is a normal state and not a failed route
  follower   derives its route from something else's. A wolf pack does not hold a range
             when the herd it eats does not either
  drifter    the dead with no grave to return to. An undead with one nests at it; these
             have nowhere to be, so they move between the places that made them

Groups share the shape of `nomads.groups` deliberately, so an encounter index or a time
mover reads both with one code path. A beast group additionally carries `species_id` and,
for followers, `host_uid`.
"""
import math
import random
from time import perf_counter
from .terrain_tectonics import child_seed
from .terrain_world import options
from .terrain_astrology import DAYS_PER_YEAR
from .terrain_erosion import sphere_grid
from .terrain_nests import habitat_cells, profiles, distance, clamp
from .terrain_settlements import shortest_paths
from .terrain_society import trace
from .terrain_nomad_routes import (travel_cost, _camp, _best, _within, _assign_days,
                                   midwinter_day)

# 2: irruptions gained a condition in time. Under version 1 every irruptive group marched
# in every year, so a consumer could read the block as a fixed roster of swarms; now a
# group may carry `route_status: "solitary"` and the roster changes from year to year.
VERSION = 2
MOVING = ('migratory', 'irruptive', 'follower', 'drifter')

# The solitary phase: normally sparse, and not going anywhere this year. Returned by the
# irruption builder instead of `None`, because `None` means "no route could be built" and
# is reported as `stranded`. A swarm that is not swarming is not a failure to route.
SOLITARY = 'solitary'

# Metres a day, by how big the thing is. A herd moves at the pace of its slowest member and
# a swarm at the pace of the wind behind it. Absolute, like the nomad speeds, because a
# gait belongs to the animal rather than to the world.
SPEED_BY_SIZE = {'tiny': 26000., 'small': 21000., 'medium': 17000.,
                 'large': 14000., 'huge': 10000., 'colossal': 7000.}
# Head count by tier: the pyramid again -- many small things, few great ones.
HERD_BY_TIER = {1: 900, 2: 400, 3: 160, 4: 60, 5: 12}
SPREAD_PER_HEAD_M = {'tiny': .05, 'small': .4, 'medium': 1.2, 'large': 3., 'huge': 8.,
                     'colossal': 20.}
# Which host a follower prefers when several are in reach. Scavengers and camp followers
# attach to people -- that is the whole of what they do -- while hunters attach to herds. A
# plain nearest-host rule got this wrong in one direction: herds outnumber bands roughly
# forty to one, so nothing ever followed a caravan.
HOST_BIAS = {'scavenger': {'nomad': .45, 'beastmove': 1.},
             'bird_of_prey': {'nomad': .8, 'beastmove': 1.},
             'pack_predator': {'nomad': .7, 'beastmove': 1.}}
DEFAULT_BIAS = {'nomad': .85, 'beastmove': 1.}

# Reaches, in settlement spacings, as everywhere else in this feature.
SEASONAL_REACH = 3.
IRRUPTION_REACH = 4.
DRIFT_REACH = 2.5
FOLLOW_REACH = 3.

# How much a year's forage departs from an ordinary one. One draw for the whole world, not
# one per group: a bad year is bad for everybody at once, which is what makes the swarms of
# one year a regional event rather than a flat probability wearing a calendar.
IRRUPTION_YEAR_LOW, IRRUPTION_YEAR_HIGH = .55, 1.25
# How far below its own neighbourhood this year's forage has to fall before the gregarious
# phase takes over. Marginal ground AND a bad year; either on its own is ordinary life.
# Measured against the neighbourhood rather than an absolute floor because a swarm forms
# where conditions turn, not where they were always poor -- and because an absolute floor
# is a forage constant, which would mean something different in every biome.
#
# The number is calibrated, and the shape of the distribution it sits in is the reason it
# is well below one. An irruptive species is already placed on marginal ground by the nest
# pass, so `forage(start) / mean(forage within a march)` runs 0.08 at the tenth percentile
# to 1.14 at the maximum with a median of 0.30 -- measured over the 90 irruptive groups of
# seed 42 at size 17. At 0.18, 59% of them march in the leanest year of a century, 28% in
# an ordinary one and 20% in the fattest, so the solitary phase stays the normal state and
# a bad year roughly doubles the swarms. At 0.85 nearly every group marched in every year,
# which is the behaviour this card exists to remove.
IRRUPTION_MARGIN = .18


def world_year(result):
    """The absolute year this world stands in.

    `world_clock` is minted by the first time advance, so a freshly generated world has
    none and is read at its founding year -- the same day the age lottery already samples,
    which is how `terrain_time.clock` adopts a clock for a world that predates one.
    Derived from `terrain_astrology` directly rather than by importing `terrain_time`,
    which imports this module.

    **Known imprecision, stated because it is visible in the output.** On a tick this reads
    the clock as it stands when the pass runs, and `advance_time_request` writes the
    advanced `world_clock` only after its cadence loop finishes. So a span crossing several
    years builds this block for the year the span *started* in -- measured at 5250 against a
    clock that ended at 5252 on a two-year advance. Generation, the age path and any span
    that does not cross a year boundary are exact. Closing it means the executor handing
    each cadence step its own day, which is a change to `terrain_time` and belongs to
    whoever owns that module.
    """
    clock = result.get('world_clock')
    if isinstance(clock, dict) and isinstance(clock.get('day'), (int, float)):
        return int(clock['day'] // (DAYS_PER_YEAR or 1))
    from .terrain_astrology import reported_year
    year, _ = reported_year(result)
    return int(year)


def year_forage_factor(result, year):
    """This year's forage against an ordinary year's, one draw for the whole world.

    **Keyed on the world's genesis seed, deliberately not on `cfg.seed`.** The time advance
    hands each cadence a stepped config -- `replace(cfg, seed=child_seed(cfg.seed,
    'time-beast_movements', index))` -- and this pass runs on a *monthly* cadence, so a
    factor drawn from `cfg.seed` would be a different number in every month of the same
    year. That is the failure `terrain_time_schedule` exists to prevent, arriving from the
    other direction: the year's weather is a property of the world and the year, and of
    nothing about when somebody happened to tick.
    """
    seed = int((result.get('config') or {}).get('seed', 0))
    return random.Random(child_seed(seed, 'beast-year', int(year))).uniform(
        IRRUPTION_YEAR_LOW, IRRUPTION_YEAR_HIGH)


def movement_of(profile):
    return profile.get('movement', 'nester')


def group_size(profile):
    return max(2, int(HERD_BY_TIER.get(profile['tier'], 40)))


def _site_groups(result):
    """Every placed site whose species moves, with its profile."""
    catalogue = {p['id']: p for p in profiles()}
    out = []
    for key in ('wildlife', 'beast_nests'):
        for site in (result.get(key) or {}).get('sites', []):
            profile = catalogue.get(site.get('species_id'))
            if profile is None or movement_of(profile) == 'nester':
                continue
            out.append((site, profile, key))
    out.sort(key=lambda pair: (pair[0]['species_id'], pair[0]['node']))
    return out


def _seasonal(group, ctx):
    """The green wave: high and open for the warm months, sheltered and low for the cold."""
    cells, spacing = ctx['cells'], ctx['spacing']
    start = group['node']
    distances, parent = ctx['paths'](start)
    heights = [c['fields'].get('height', 0.) for c in cells]
    base = heights[start]
    reach = SEASONAL_REACH * spacing

    def summer(node):
        f = cells[node]['fields']
        lift = clamp((heights[node] - base) / max(1., abs(base) + 400.))
        forage = max(f.get('food_potential', 0.), f.get('natural_food_potential', 0.))
        return forage * (1. + lift) * (.4 + clamp(1. - f.get('slope', 0.) / 30.))

    def winter(node):
        f = cells[node]['fields']
        drop = clamp((base - heights[node]) / max(1., abs(base) + 400.))
        warmth = clamp((f.get('temperature', 0.) + 20.) / 45.)
        forage = max(f.get('food_potential', 0.), f.get('natural_food_potential', 0.))
        return (.3 + forage) * (1. + drop) * (.4 + clamp(abs(f.get('tpi', 0.)) / 30.)) * (.5 + warmth)

    reachable = [i for i in _within(distances, reach) if i != start]
    s = _best(reachable, summer)
    w = _best(reachable, winter)
    if s is None or w is None or s == w:
        return None
    camps = [_camp(group, 0, start, cells, 'calving'),
             _camp(group, 1, s, cells, 'summer'),
             _camp(group, 2, w, cells, 'winter')]
    # Calving is the reason the round has a third stop: moving to it is what buys the young
    # their distance from the predators that follow the herd.
    return camps, [(0, 1, 'trunk'), (1, 2, 'trunk'), (2, 0, 'trunk')], parent


def _irruption(group, ctx):
    """One march out of ground that stopped supporting them, until something does.

    A swarm does not form where conditions are good; it forms where they are marginal and
    then leaves. So the destination is the best forage in reach and the route is one way.

    **And it forms in a particular year, not in every year.** That is the whole of the
    locust pattern and it is the half this builder did not have: the solitary phase is the
    normal state, and gregarious swarming is a response to violent environmental
    fluctuation. Two conditions, and neither on its own is enough:

      the year   `year_forage_factor` scales this year's forage against an ordinary one.
                 One draw for the world, so a bad year is a bad year for everybody.
      the ground the group's own cell against the mean of what a march can reach. Marginal
                 ground is ground that falls short of its *neighbourhood* -- a swarm forms
                 where conditions turn, not where they were always poor, and an absolute
                 floor would have made the same handful of desert cells swarm forever.

    A group that fails to clear the bar is `SOLITARY`, which is a normal state. `None` is
    kept for its old meaning -- no reachable ground to march to -- and is still `stranded`.
    """
    cells, spacing = ctx['cells'], ctx['spacing']
    start = group['node']
    distances, parent = ctx['paths'](start)

    def fed(node):
        f = cells[node]['fields']
        return max(f.get('food_potential', 0.), f.get('natural_food_potential', 0.))

    within = _within(distances, IRRUPTION_REACH * spacing)
    if not within:
        return None
    # Plain accumulation rather than sum(): CPython compensates a builtin sum of floats and
    # a native port would have to replicate that to stay bit-exact.
    total = 0.
    for node in within:
        total += fed(node)
    local_mean = total / len(within)
    if fed(start) * ctx['year_forage'] >= IRRUPTION_MARGIN * local_mean:
        return SOLITARY
    target = _best([i for i in within if i != start], fed)
    if target is None:
        return None
    return ([_camp(group, 0, start, cells, 'base'), _camp(group, 1, target, cells, 'terminal')],
            [(0, 1, 'trunk')], parent)


def _drift(group, ctx):
    """A circuit between the places that made them: ruins, and ground that remembers.

    These are the dead nobody buried, so the route has no seasonal logic at all. It is a
    wandering between sites of violence, which is the only thing that anchors them.
    """
    cells, spacing = ctx['cells'], ctx['spacing']
    start = group['node']
    distances, parent = ctx['paths'](start)
    reach = DRIFT_REACH * spacing
    haunts = []
    for ruin in ctx['ruins']:
        node = ruin.get('node')
        if node is None or node == start or not 0 <= node < len(cells):
            continue
        if math.isfinite(distances[node]) and distances[node] <= reach:
            haunts.append((distances[node], ruin.get('uid', ''), node))
    haunts.sort()
    if not haunts:
        return None
    camps = [_camp(group, 0, start, cells, 'base')]
    for i, (_, _, node) in enumerate(haunts[:3]):
        camps.append(_camp(group, i + 1, node, cells, 'terminal'))
    order = [(i, i + 1, 'trunk') for i in range(len(camps) - 1)]
    order.append((len(camps) - 1, 0, 'trunk'))
    return camps, order, parent


def _follow(group, ctx):
    """Take the host's circuit, lagged. A follower does not search; it derives.

    This is the class that closes the loop the whole feature is for: predators and
    scavengers walking the routes that nomads and herds already walk.
    """
    cells, spacing = ctx['cells'], ctx['spacing']
    start = group['node']
    reach = FOLLOW_REACH * spacing
    bias = HOST_BIAS.get(group.get('role'), DEFAULT_BIAS)
    best = None
    for host in ctx['hosts']:
        if not host.get('legs'):
            continue
        span = distance(cells[start]['direction'], cells[host['node']]['direction'], ctx['radius'])
        if span > reach:
            continue
        # A bias below one shortens the effective distance, so a preferred host wins from
        # further away without ever letting an unreachable one through.
        kind = 'nomad' if host['uid'].startswith('nomad-') else 'beastmove'
        mark = (span * bias.get(kind, 1.), host['uid'])
        if best is None or mark < best[0]:
            best = (mark, host)
    if best is None:
        return None
    host = best[1]
    group['host_uid'] = host['uid']
    # The host's camps become the follower's, one step behind: it arrives where the host
    # has been rather than where it is going.
    camps = []
    for i, camp in enumerate(host['camps']):
        camps.append(_camp(group, i, camp['node'], cells,
                           'terminal' if camp['kind'] in ('station', 'terminal') else 'base'))
    if len(camps) < 2:
        return None
    order = [(i, (i + 1) % len(camps), 'trunk') for i in range(len(camps))]
    _, parent = ctx['paths'](start)
    return camps, order, parent


BUILDERS = {'migratory': _seasonal, 'irruptive': _irruption,
            'drifter': _drift, 'follower': _follow}


def add_beast_movements(result, cfg):
    """Give the creatures that do not hold ground the circuits they actually walk."""
    if not cfg.world_recipe or cfg.phase < 16:
        return result
    started = perf_counter()
    o = options(cfg)
    share = float(o.get('beast_movement_share', 1.))
    radius = result['effective_config']['globe_radius']
    points, areas, graph = sphere_grid(cfg.size, radius)
    cells = habitat_cells(result, cfg, points, areas)
    cost = travel_cost(points, cells, cfg)
    spacing = float(cfg.settlement_spacing)
    cache = {}

    def paths(start):
        if start not in cache:
            cache[start] = shortest_paths(graph, start, cost)
        return cache[start]

    # Followers derive from whatever already walks: nomad bands first, then the herds built
    # in this same pass. So followers are built last, once there is something to follow.
    hosts = [b for b in (result.get('nomads', {}).get('groups', []) or []) if b.get('legs')]
    year = world_year(result)
    ctx = {'cells': cells, 'spacing': spacing, 'paths': paths, 'radius': radius,
           'ruins': result.get('ruins', []) or [], 'hosts': hosts,
           'year': year, 'year_forage': year_forage_factor(result, year)}

    rng = random.Random(child_seed(cfg.seed, 'beast-movement-v1', int(o.get('nomad_variation', 0))))
    groups, deferred, stranded, solitary = [], [], 0, 0
    considered = skipped = 0
    for site, profile, source in _site_groups(result):
        movement = movement_of(profile)
        considered += 1
        # Wildlife is dense -- thousands of sites -- so every eligible one becoming a
        # routed group makes the block enormous for little added meaning. The share is a
        # deterministic thinning over an ordered list, not a cap, so it stays proportional
        # to the ground rather than to whatever happened to be placed first.
        if share < 1. and rng.random() >= share:
            skipped += 1
            continue
        uid = 'beastmove-%s-%d' % (site['species_id'], site['node'])
        size = group_size(profile)
        group = {
            'uid': uid, 'species_id': site['species_id'], 'name': site.get('name'),
            'movement': movement, 'family': profile['family'], 'tier': profile['tier'],
            'kind': profile['class'], 'source': source, 'host_uid': None,
            'node': site['node'], 'x': site['x'], 'z': site['z'],
            'direction': list(site['direction']), 'size': size,
            'speed_m_per_day': SPEED_BY_SIZE.get(profile['size'], 15000.),
            'column_length_m': round(size * SPREAD_PER_HEAD_M.get(profile['size'], 1.), 6),
            'disposition': 'hostile' if profile['class'] == 'monster' else 'wary',
            'role': profile.get('role'),
            'camps': [], 'legs': [], 'route_status': 'stranded',
        }
        (deferred if movement == 'follower' else groups).append((group, movement))

    def build(group, movement):
        nonlocal stranded, solitary
        built = BUILDERS[movement](group, ctx)
        if built is SOLITARY:
            # Sparse and staying put, which is the normal state for this class and not a
            # route that failed. It keeps a base camp, so the encounter index still places
            # it: a player can meet the solitary phase, just not a swarm on the march.
            group['route_status'] = SOLITARY
            group['camps'] = [_camp(group, 0, group['node'], cells, 'base')]
            solitary += 1
            return
        if not built:
            group['route_status'] = 'stranded'
            group['camps'] = [_camp(group, 0, group['node'], cells, 'base')]
            stranded += 1
            return
        camps, order, parent = built
        legs = []
        for a, b, branch in order:
            src, dst = camps[a], camps[b]
            if src['node'] == dst['node']:
                continue
            sub_d, sub_p = paths(src['node'])
            nodes = trace(sub_p, src['node'], dst['node'])
            if not nodes:
                continue
            length = 0.
            for i in range(len(nodes) - 1):
                length += distance(cells[nodes[i]]['direction'], cells[nodes[i + 1]]['direction'], radius)
            legs.append({'from': src['id'], 'to': dst['id'], 'nodes': nodes, 'length_m': length,
                         'depart_day': None, 'arrive_day': None, 'branch': branch})
        if not legs:
            group['route_status'] = 'stranded'
            group['camps'] = [_camp(group, 0, group['node'], cells, 'base')]
            stranded += 1
            return
        _assign_days(group, camps, legs, {'cfg': cfg, 'cells': cells})
        group['camps'] = camps
        group['legs'] = legs
        group['route_status'] = 'routed'
        group['round_length_m'] = round(sum(l['length_m'] for l in legs), 6)

    for group, movement in groups:
        build(group, movement)
    # Herds now exist, so a follower may attach to one as readily as to a nomad band.
    ctx['hosts'] = hosts + [g for g, _ in groups if g['legs']]
    for group, movement in deferred:
        build(group, movement)

    everything = [g for g, _ in groups + deferred]
    everything.sort(key=lambda g: g['uid'])
    counts = {}
    for group in everything:
        counts[group['movement']] = counts.get(group['movement'], 0) + 1
    result['beast_movements'] = {
        'version': VERSION, 'groups': everything, 'counts': counts,
        'considered': considered, 'skipped': skipped, 'share': share,
        'routed': sum(1 for g in everything if g['route_status'] == 'routed'), 'stranded': stranded,
        'solitary': solitary, 'year': year, 'year_forage_factor': round(ctx['year_forage'], 6),
        'method': 'Every placed site whose species declares a movement class other than nester becomes a '
                  'travelling group. Herds walk a seasonal round between high summer pasture and sheltered '
                  'winter ground through a calving camp; the unhoused dead circuit between ruins; and '
                  'followers derive their circuit from a host\'s, taking nomad bands and herds alike. A swarm '
                  'marches only in a year that is actually bad for it: this year\'s forage factor -- one draw '
                  'for the whole world, keyed on the genesis seed and the absolute year so a monthly tick '
                  'cannot re-roll it -- is applied to the group\'s own cell and compared against the mean of '
                  'what a march can reach, so marginal ground in a lean year erupts and the same ground in an '
                  'ordinary year stays solitary. Groups share the shape of nomads.groups so one consumer '
                  'reads both.',
        'limits': 'A group is one site rather than a modelled population: nothing breeds, starves, is eaten or '
                  'merges with another group, and a herd does not shrink when a follower attaches to it. '
                  'Followers pick the nearest host and never change host. The irruption year is a draw rather '
                  'than a simulated drought: seasonal_environment carries twelve climatological months that '
                  'are the same in every year, so there is no modelled weather for a year to depart from, and '
                  'the factor stands in for one. On a tick the year is read from world_clock as it '
                  'stands when this pass runs, and a time advance writes the advanced clock after its '
                  'cadence loop, so a span crossing several years builds this block for the year that '
                  'span started in. A swarm that is not swarming carries route_status '
                  '"solitary", which is its normal state; a group whose route could not be built is still '
                  'reported as stranded. This block is therefore not stable from year to year, which is the '
                  'point of it. Circuits are otherwise static.',
    }
    elapsed = (perf_counter() - started) * 1000
    result['timing_ms']['beast_movements'] = elapsed
    result['timing_ms']['total'] += elapsed
    return result
