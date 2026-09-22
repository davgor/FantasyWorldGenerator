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

Cost, and the four things that decide it
----------------------------------------
This pass is the largest in a size-128 generation and the only superlinear one, so the
shape of the work is part of the design rather than an implementation detail. Four
structures carry it, and each exists to remove a term that grew with the world:

  priced edges   every passable step is priced once, by `_priced`, instead of once per
                 search that crosses it. The search below is run thousands of times over
                 one static graph, and the cost function is the expensive part of it
  bounded search `_searcher`'s search stops at the reach its caller will read and reports
                 the nodes it settled, out of arrays it keeps rather than rebuilds. The
                 old form searched the whole land component and then scanned every cell
                 in the world to find the two hundred it wanted
  one shape per  a route depends on the ground under the group, not on the group. Two
  ground         species standing on one cell walk the same circuit, so the circuit is
                 built once and worn by both -- see `shape`
  a latitude     `_follow` picks the nearest host out of everything that already walks,
  walk           and everything that already walks is most of this block. Comparing every
                 follower against every host is the quadratic that made the pass the
                 successor to `add_world_society`; the walk in `_follow` replaces it

None of the four moves a float. The block this module writes is byte-identical across the
change, floats by `repr`, at sizes 33, 65 and 128 -- which is the only claim worth making
about a performance change to a deterministic generator.
"""
import bisect
import heapq
import math
import random
from time import perf_counter
from .terrain_tectonics import child_seed
from .terrain_world import options
from .terrain_astrology import DAYS_PER_YEAR
from .terrain_erosion import sphere_grid
from .terrain_nests import habitat_cells, profiles, distance
from .terrain_society import trace
from .terrain_nomad_routes import travel_cost, _camp, _assign_days

# A sentinel the shape cache can tell apart from a builder that legitimately returned
# `None`, which is how a stranded group is reported and is very much a result worth
# remembering.
_MISSING = object()

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

# Slack on the latitude bound the host walk in `_follow` stops on, in radians. The bound
# -- that the angle between two directions is at least the difference of their latitudes
# -- is exact in real arithmetic; this absorbs the rounding in the `asin` that stands in
# for a latitude and the `acos` inside `distance`. It is the same number and the same
# argument as `terrain_nests.LATITUDE_SLACK`, kept here rather than imported because the
# two walks stop on different quantities and a shared constant would imply they move
# together. 1e-9 rad is 3e-5 m on the widest world this product ships, and the slack is
# ADDED to the threshold, so the walk goes one candidate too far rather than one too few.
WALK_SLACK = 1e-9

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


def _priced(graph, cost):
    """Every passable edge priced once, in place of once per search that crosses it.

    `travel_cost` is a closure over four per-cell lists with a diagonal-corner test in it,
    and it was being called on every relaxation of every search this pass runs -- several
    million evaluations of a function whose answer cannot change, because the graph and
    the ground are both fixed for the whole pass. Pricing the graph once is one call per
    directed edge, about eight per cell, and the searches then read floats.

    Impassable edges are dropped rather than priced as infinite, so the search never sees
    them. That is the same set the old form skipped on `edge is None`, in the same order,
    which is why the distances come out float for float the same.
    """
    priced = []
    for i, edges in enumerate(graph):
        row = []
        for j, span in edges:
            value = cost(i, j, span)
            if value is not None:
                row.append((j, value))
        priced.append(row)
    return priced


def _searcher(priced):
    """A search over `priced` that keeps its two arrays between calls.

    Four differences from `terrain_settlements.shortest_paths`, and each buys something
    this pass in particular needed.

    **It stops at the reach.** Every caller here discards everything past a reach of two
    and a half to four settlement spacings, and stopping inside the search is not an
    approximation: edge costs are strictly positive, so every prefix of a path costing
    `limit` or less also costs `limit` or less, and a node inside the bound keeps the
    distance and the parent it had when the search was unbounded.

    **It reports what it reached.** The callers used to recover that by scanning every
    cell in the world -- `_within` over 16 004 cells to find the 190 a search on a world
    four fifths ocean actually settles. A node enters the set the first time it is given a
    finite distance, which is the first time its parent stops being -1, and the list is
    sorted before it is returned so a caller reads it in ascending node order. That order
    is load-bearing: `_irruption` sums forage over it, and float addition is not
    associative.

    **It can stop on a target.** A leg only needs the path to one node. Every node on that
    path has a strictly smaller distance than the target -- strictly, because no edge here
    is free -- so all of them are settled with final parents by the time the target is
    popped, and the traced route is the one the unbounded search would have given.

    **It does not rebuild the arrays.** They are the width of the world and a search
    touches a few hundred cells of it, so allocating them per call was the one cost left
    in here that grew with the map rather than with the route -- 148 million list slots
    over a size-128 run, against 4.4 million cells actually settled. Each call clears
    what the last one dirtied instead.

    **`distances` and `parent` are therefore scratch.** They hold for exactly as long as
    it takes to call this again, which every caller in this module respects: two read only
    the reached list, `_drift` reads the distances before returning, and `route` traces
    the parents before returning. The reached list is a fresh one each time and is safe to
    keep. Nothing here is thread-safe, and nothing in this generator is.
    """
    distances = [math.inf] * len(priced)
    parent = [-1] * len(priced)
    dirty = []

    def search(start, limit=math.inf, target=None):
        pop, push = heapq.heappop, heapq.heappush
        for node in dirty:
            distances[node] = math.inf
            parent[node] = -1
        del dirty[:]
        distances[start] = 0
        dirty.append(start)
        queue = [(0, start)]
        while queue:
            value, i = pop(queue)
            if value != distances[i]:
                continue
            if i == target:
                break
            for j, edge in priced[i]:
                candidate = value + edge
                # Distance first, reach second, and not the other way round: the reach
                # test passes on almost every edge a bounded search looks at and is pure
                # overhead there, while most neighbours of a settled cell are already
                # settled better. Both have to hold, so the order is free to choose.
                if candidate < distances[j] and candidate <= limit:
                    if parent[j] < 0:
                        dirty.append(j)
                    distances[j] = candidate
                    parent[j] = i
                    push(queue, (candidate, j))
        return distances, parent, sorted(dirty)

    return search


def _host_index(hosts, dirs):
    """The hosts sorted by latitude, which is what `_follow` walks outwards from.

    Ties break on position in the caller's list so the order is a function of the world
    and not of the sort's stability.
    """
    lats = [math.asin(max(-1., min(1., dirs[host['node']][1]))) for host in hosts]
    order = sorted(range(len(hosts)), key=lambda i: (lats[i], i))
    return ([lats[i] for i in order], [hosts[i] for i in order],
            [dirs[hosts[i]['node']] for i in order])


def _seasonal(group, ctx):
    """The green wave: high and open for the warm months, sheltered and low for the cold.

    Both scores are taken in one pass over the reachable ground, and `clamp` is spelled
    out rather than called. That is not style: the two scorers are the innermost loop of
    this pass and were four million Python calls at size 128. It is the same arithmetic in
    the same order -- `clamp` *is* `max(0., min(1., v))` -- and the pick is the same
    `(score, -node)` maximum `_best` takes, so the two camps come out the same cells.
    """
    heights, forage = ctx['height'], ctx['forage']
    slope, temperature, tpi = ctx['slope'], ctx['temperature'], ctx['tpi']
    start = group['node']
    base = heights[start]
    # Loop-invariant: the denominator is the group's own ground, not the candidate's.
    span = max(1., abs(base) + 400.)
    _, _, reached = ctx['search'](start, SEASONAL_REACH * ctx['spacing'])
    s = w = None
    best_s = best_w = None
    for node in reached:
        # The start node is the calving camp and cannot also be a seasonal one.
        if node == start:
            continue
        food = forage[node]
        height = heights[node]
        lift = max(0., min(1., (height - base) / span))
        mark = (food * (1. + lift) * (.4 + max(0., min(1., 1. - slope[node] / 30.))), -node)
        if best_s is None or mark > best_s:
            best_s, s = mark, node
        drop = max(0., min(1., (base - height) / span))
        warmth = max(0., min(1., (temperature[node] + 20.) / 45.))
        mark = ((.3 + food) * (1. + drop) * (.4 + max(0., min(1., abs(tpi[node]) / 30.)))
                * (.5 + warmth), -node)
        if best_w is None or mark > best_w:
            best_w, w = mark, node
    if s is None or w is None or s == w:
        return None
    # Calving is the reason the round has a third stop: moving to it is what buys the young
    # their distance from the predators that follow the herd.
    return ([(start, 'calving'), (s, 'summer'), (w, 'winter')],
            [(0, 1, 'trunk'), (1, 2, 'trunk'), (2, 0, 'trunk')])


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
    forage = ctx['forage']
    start = group['node']
    _, _, within = ctx['search'](start, IRRUPTION_REACH * ctx['spacing'])
    if not within:
        return None
    # Plain accumulation rather than sum(): CPython compensates a builtin sum of floats and
    # a native port would have to replicate that to stay bit-exact. `within` is in
    # ascending node order, which is what makes this total reproducible.
    total = 0.
    for node in within:
        total += forage[node]
    local_mean = total / len(within)
    if forage[start] * ctx['year_forage'] >= IRRUPTION_MARGIN * local_mean:
        return SOLITARY
    # `_best` written out, for the reason `_seasonal` gives: the same `(score, -node)`
    # maximum, without a Python call per candidate.
    target = None
    best = None
    for node in within:
        if node == start:
            continue
        mark = (forage[node], -node)
        if best is None or mark > best:
            best, target = mark, node
    if target is None:
        return None
    return [(start, 'base'), (target, 'terminal')], [(0, 1, 'trunk')]


def _drift(group, ctx):
    """A circuit between the places that made them: ruins, and ground that remembers.

    These are the dead nobody buried, so the route has no seasonal logic at all. It is a
    wandering between sites of violence, which is the only thing that anchors them.
    """
    start = group['node']
    reach = DRIFT_REACH * ctx['spacing']
    distances, _, _ = ctx['search'](start, reach)
    cells = ctx['cells']
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
    camps = [(start, 'base')]
    for _, _, node in haunts[:3]:
        camps.append((node, 'terminal'))
    order = [(i, i + 1, 'trunk') for i in range(len(camps) - 1)]
    order.append((len(camps) - 1, 0, 'trunk'))
    return camps, order


def _follow(group, ctx):
    """Take the host's circuit, lagged. A follower does not search; it derives.

    This is the class that closes the loop the whole feature is for: predators and
    scavengers walking the routes that nomads and herds already walk.

    Finding the host is the part that had to change. A follower takes the nearest host in
    reach, biased by kind, and by the time followers are built nearly everything else in
    this block is a host -- so comparing each follower against every host is quadratic in
    the size of the block, and at size 128 that was half the pass. It is now the same
    outward walk `terrain_nests.nearest_settled` uses, over the same mathematics: the
    angle between two directions is at least the difference of their latitudes, so with
    the hosts sorted by latitude and taken nearest-latitude first, from whichever side has
    the smaller remaining gap, everything still unvisited is at least that far away.

    Two thresholds stop it, and the walk stops on whichever it meets first.

      the reach  a host whose latitude alone puts it past the reach cannot pass the cut,
                 and neither can anything behind it
      the mark   the winner is the smallest `span * bias`, and `bias` is never above one,
                 so a host at latitude gap `g` cannot mark below `radius * g * bias_min`.
                 Once that floor passes the best mark already found, nothing left can win

    The answer is the one the flat scan gave. The winner is the unique minimum of
    `(span * bias, uid)`, which does not depend on the order candidates arrive in, and
    `span` is the same `distance` call on the same two directions.
    """
    dirs, radius = ctx['dirs'], ctx['radius']
    start = group['node']
    reach = FOLLOW_REACH * ctx['spacing']
    bias = HOST_BIAS.get(group.get('role'), DEFAULT_BIAS)
    # `bias.get(kind, 1.)` falls back to one, so the floor has to admit one as well.
    floor = min(min(bias.values()), 1.)
    lats, ordered, host_dirs = ctx['host_index']
    total = len(lats)
    here = dirs[start]
    phi = math.asin(max(-1., min(1., here[1])))
    left = bisect.bisect_left(lats, phi)
    right = left
    slack = radius * WALK_SLACK
    best = None
    while True:
        gap_l = phi - lats[left - 1] if left else None
        gap_r = lats[right] - phi if right < total else None
        if gap_l is None and gap_r is None:
            break
        if gap_r is None or (gap_l is not None and gap_l <= gap_r):
            gap = gap_l
            left -= 1
            at = left
        else:
            gap = gap_r
            at = right
            right += 1
        floor_span = radius * gap
        if floor_span > reach + slack:
            break
        if best is not None and floor_span * floor > best[0][0] + slack:
            break
        # A bias below one shortens the effective distance, so a preferred host wins from
        # further away without ever letting an unreachable one through.
        span = distance(here, host_dirs[at], radius)
        if span > reach:
            continue
        host = ordered[at]
        kind = 'nomad' if host['uid'].startswith('nomad-') else 'beastmove'
        mark = (span * bias.get(kind, 1.), host['uid'])
        if best is None or mark < best[0]:
            best = (mark, host)
    if best is None:
        return None, None
    host = best[1]
    # The host's camps become the follower's, one step behind: it arrives where the host
    # has been rather than where it is going. The uid is claimed even when the circuit is
    # too short to derive from, because the follower did find a host -- it is the host's
    # route that failed it, and the block should say which host.
    camps = [(camp['node'], 'terminal' if camp['kind'] in ('station', 'terminal') else 'base')
             for camp in host['camps']]
    if len(camps) < 2:
        return host['uid'], None
    return host['uid'], (camps, [(i, (i + 1) % len(camps), 'trunk') for i in range(len(camps))])


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
    priced = _priced(graph, travel_cost(points, cells, cfg))
    spacing = float(cfg.settlement_spacing)
    # One searcher for the whole pass, builders and legs alike. Its arrays are scratch and
    # a builder is finished with them before `route` searches again -- see `_searcher`.
    search = _searcher(priced)

    # The fields the scorers read, lifted out of the cell dictionaries once. Every one of
    # them was being fetched with a `.get` inside a scoring function called for each
    # candidate node of each group -- and `height` was being rebuilt as a whole-world list
    # on every seasonal build. Same values, same defaults, same order of operations.
    dirs = [c['direction'] for c in cells]
    fields = [c['fields'] for c in cells]
    height = [f.get('height', 0.) for f in fields]
    forage = [max(f.get('food_potential', 0.), f.get('natural_food_potential', 0.)) for f in fields]
    slope = [f.get('slope', 0.) for f in fields]
    temperature = [f.get('temperature', 0.) for f in fields]
    tpi = [f.get('tpi', 0.) for f in fields]

    # Followers derive from whatever already walks: nomad bands first, then the herds built
    # in this same pass. So followers are built last, once there is something to follow.
    hosts = [b for b in (result.get('nomads', {}).get('groups', []) or []) if b.get('legs')]
    year = world_year(result)
    ctx = {'cells': cells, 'spacing': spacing, 'search': search, 'radius': radius,
           'ruins': result.get('ruins', []) or [],
           'year': year, 'year_forage': year_forage_factor(result, year),
           'dirs': dirs, 'height': height, 'forage': forage, 'slope': slope,
           'temperature': temperature, 'tpi': tpi, 'host_index': _host_index(hosts, dirs)}

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

    # A circuit is a property of the ground a group stands on, not of the group: nothing
    # any builder reads varies between two groups on one cell of one movement class -- a
    # follower additionally reads its role, because that is what biases its choice of
    # host. So the shape is built once per key and worn by everyone who shares it. What
    # cannot be shared is the naming: `_camp` stamps the group's own uid into every camp
    # id, and `_assign_days` runs on the group's own speed.
    shapes = {}

    def shape(group, movement):
        key = (movement, group['node'], group['role']) if movement == 'follower' \
            else (movement, group['node'])
        built = shapes.get(key, _MISSING)
        if built is _MISSING:
            built = shapes[key] = BUILDERS[movement](group, ctx)
        return built

    # One traced route per pair of camps, for the same reason. The nodes are copied out
    # per leg so two groups never share one list.
    routes = {}

    def route(source, destination):
        found = routes.get((source, destination))
        if found is None:
            _, parent, _ = search(source, target=destination)
            nodes = trace(parent, source, destination)
            length = 0.
            for i in range(len(nodes) - 1):
                length += distance(dirs[nodes[i]], dirs[nodes[i + 1]], radius)
            found = routes[(source, destination)] = (nodes, length)
        return found

    def build(group, movement):
        nonlocal stranded, solitary
        built = shape(group, movement)
        if movement == 'follower':
            group['host_uid'], built = built
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
        spec, order = built
        camps = [_camp(group, i, node, cells, kind) for i, (node, kind) in enumerate(spec)]
        legs = []
        for a, b, branch in order:
            src, dst = camps[a], camps[b]
            if src['node'] == dst['node']:
                continue
            nodes, length = route(src['node'], dst['node'])
            if not nodes:
                continue
            legs.append({'from': src['id'], 'to': dst['id'], 'nodes': list(nodes),
                         'length_m': length, 'depart_day': None, 'arrive_day': None,
                         'branch': branch})
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
    ctx['host_index'] = _host_index(hosts + [g for g, _ in groups if g['legs']], dirs)
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

