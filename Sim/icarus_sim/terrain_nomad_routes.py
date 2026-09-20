"""Migration routes: the circuits the bands walk, and when in the year they walk them.

`terrain_nomads` decides who a band is from the ground it stands on. This decides where
that answer makes it go. The two are separate passes because they fail differently: a
classification is wrong when it ignores the land, a route is wrong when it ignores the
calendar.

The shapes are not interchangeable and none of them is a loop for its own sake:

  wanderers   two long moves a year between high summer pasture and sheltered winter
              ground, returning to the same camps -- transhumance, not drift
  merchants   a chain between markets, subdivided so no leg exceeds a day's march, because
              the whole point of a caravan stop is not sleeping in the gap
  cultists    a closed circuit over the sacred ground of one god
  bandits     a lair with out-and-back spurs onto wealth; a raider orbits, it does not migrate
  deserters   one flight away from the war that broke them, ending in cover
  survivors   one displacement toward the nearest place still standing, and it terminates

Branches are typed rather than decorative. `trunk` is the annual round; `base_limb` is the
transhumance split where part of the group holds a base while the herd moves; `spur` is a
short out-and-back. `fission` is reserved for the lineage split that is not built yet.

Days are integers in [0, DAYS_PER_YEAR) and the seasonal phase **inverts across the
equator**, so a southern clan winters on the opposite half of the year. Getting that wrong
is invisible on a world whose land happens to sit in one hemisphere, which is why it is
pinned by a test rather than by inspection.

Every reach is a multiple of settlement spacing. Travel time is length over
`speed_m_per_day`, which is the one absolute the bands carry.
"""
import math
import random
from time import perf_counter
from .terrain_tectonics import child_seed
from .terrain_world import options
from .terrain_erosion import sphere_grid
from .terrain_globe import direction
from .terrain_astrology import DAYS_PER_YEAR
from .terrain_nests import habitat_cells, distance, clamp
from .terrain_settlements import shortest_paths
from .terrain_society import trace
from .terrain_nomads import policy, population_of, ruggedness, VERSION as NOMAD_VERSION

# Midsummer in the northern hemisphere, as a fraction of the year. The south is half a
# year away. Anchoring on a fraction rather than a day keeps this correct if the calendar
# length ever changes.
MIDSUMMER_NORTH = .5
# A laden pack animal makes 30-40 km in a day, which is why caravan stations sat that far
# apart. Clamped against settlement spacing so stations never land closer than towns.
DAY_MARCH_M = 35000.
# Herds and refugees cross ground roads refuse: steeper, and they ford rather than bridge.
GRADE_RELIEF = 2.2

# How long a band lingers, by what the camp is for. A winter camp is where the year is
# survived and a lair is where a raider lives; a market stall and a village just robbed are
# both places you leave. Splitting the year evenly across camps put a bandit at the hamlet
# it had raided for four months, which is not a raid.
CAMP_REST = {'winter': 5., 'summer': 4., 'base': 3., 'lair': 5., 'shrine': 2.,
             'station': 1., 'terminal': .35, 'calving': 3.}

# Some stops are events, not seasons, however much of the year is left to divide. A raid
# and a market day are measured in days; a share of the leftover year is the wrong unit for
# them and produced a band sitting three weeks in a hamlet it had just robbed.
CAMP_REST_CEILING = {'terminal': 3, 'station': 6, 'shrine': 21}


def midsummer_day(z, n):
    """The day the sun is highest at this row, inverting across the equator."""
    latitude = 90. - 180. * z / (n - 1)
    phase = MIDSUMMER_NORTH if latitude >= 0 else MIDSUMMER_NORTH + .5
    return int(round((phase % 1.) * DAYS_PER_YEAR)) % DAYS_PER_YEAR


def midwinter_day(z, n):
    return (midsummer_day(z, n) + DAYS_PER_YEAR // 2) % DAYS_PER_YEAR


def travel_cost(points, cells, cfg):
    """Cost of walking between two adjacent nodes, for people with herds and carts.

    Not `road_cost_function`: that refuses a river without a bridge and caps grade at the
    road limit, both of which describe an engineered route rather than a walked one. A band
    fords, and takes ground a road would not. Water is still impassable -- these are not
    boats -- and the forage term makes a herd prefer the green way round.
    """
    n = cfg.size
    lookup = {p: i for i, p in enumerate(points)}
    ceiling = cfg.road_max_grade * GRADE_RELIEF
    water = [1 if c['fields'].get('medium') != 'land' else 0 for c in cells]
    height = [c['fields'].get('height', 0.) for c in cells]
    forage = [clamp(max(c['fields'].get('food_potential', 0.),
                        c['fields'].get('natural_food_potential', 0.))) for c in cells]

    def cost(i, j, d):
        if water[i] or water[j] or d <= 0:
            return None
        xi, zi = points[i]
        xj, zj = points[j]
        # A diagonal cannot slip between two water-filled corner cells.
        if xi != xj and zi != zj and zi not in (0, n - 1) and zj not in (0, n - 1):
            if water[lookup[(xi, zj)]] or water[lookup[(xj, zi)]]:
                return None
        grade = abs(height[j] - height[i]) / d
        if grade > ceiling:
            return None
        # Plain accumulation rather than a sum(): one term, and the native port would
        # otherwise have to carry a compensated accumulator for nothing.
        green = 1. - .25 * (forage[i] + forage[j]) / 2.
        return d * (1. + 8. * grade ** 2) * green
    return cost


def _reach(band, pol, key, spacing, fallback):
    gate = pol['classifications'][band['classification']]['gate']
    return gate.get(key, fallback) * spacing


def _camp(band, index, node, cells, kind):
    cell = cells[node]
    return {'id': '%s-camp-%d' % (band['uid'], index), 'node': node,
            'direction': list(cell['direction']), 'kind': kind,
            'arrive_day': None, 'depart_day': None}


def _best(candidates, score):
    """Highest scoring candidate; ties break on node index so a replay cannot diverge."""
    best = None
    for node in candidates:
        mark = (score(node), -node)
        if best is None or mark > best[0]:
            best = (mark, node)
    return best[1] if best else None


def _within(distances, limit):
    return [i for i, d in enumerate(distances) if d <= limit and math.isfinite(d)]


def _seasonal_camps(band, ctx):
    """Summer pasture and winter shelter, the two grounds a herding round needs.

    Summer wants height and openness -- ground that cannot be used in the cold months, so
    it is not competing with anyone. Winter wants the opposite and one thing more: snow
    settles on the flat, so the camps that work are tucked against relief where sun and
    wind strip the pasture clear.
    """
    cells, cfg, pol, spacing = ctx['cells'], ctx['cfg'], ctx['pol'], ctx['spacing']
    start = band['node']
    reach_s = _reach(band, pol, 'summer_reach_spacings', spacing, 3.5)
    reach_w = _reach(band, pol, 'winter_reach_spacings', spacing, 3.5)
    distances, parent = ctx['paths'](start)
    heights = [c['fields'].get('height', 0.) for c in cells]
    base = heights[start]

    def summer(node):
        f = cells[node]['fields']
        openness = clamp(1. - f.get('slope', 0.) / 30.)
        lift = clamp((heights[node] - base) / max(1., abs(base) + 400.))
        forage = max(f.get('food_potential', 0.), f.get('natural_food_potential', 0.))
        return forage * (1. + lift) * (.4 + openness)

    def winter(node):
        f = cells[node]['fields']
        shelter = clamp(abs(f.get('tpi', 0.)) / 30.)
        drop = clamp((base - heights[node]) / max(1., abs(base) + 400.))
        warmth = clamp((f.get('temperature', 0.) + 20.) / 45.)
        forage = max(f.get('food_potential', 0.), f.get('natural_food_potential', 0.))
        return (.3 + forage) * (1. + drop) * (.4 + shelter) * (.5 + warmth)

    # The start node is the base and cannot also be a seasonal camp: if it were, the
    # base_limb leg would collapse to zero length, be dropped, and leave the base camp with
    # no leg referencing it and so no day window at all.
    s = _best([i for i in _within(distances, reach_s) if i != start], summer)
    w = _best([i for i in _within(distances, reach_w) if i != start], winter)
    if s is None or w is None or s == w:
        return None
    camps = [_camp(band, 0, start, cells, 'base'),
             _camp(band, 1, s, cells, 'summer'),
             _camp(band, 2, w, cells, 'winter')]
    order = [(0, 1, 'base_limb'), (1, 2, 'trunk'), (2, 1, 'trunk')]
    return camps, order, parent, distances


def _market_stations(band, ctx):
    """Markets worth walking between, then subdivided so no leg exceeds a day's march."""
    cells, pol, spacing = ctx['cells'], ctx['pol'], ctx['spacing']
    start = band['node']
    reach = _reach(band, pol, 'market_reach_spacings', spacing, 3.)
    floor = pol['classifications']['merchants']['gate'].get('min_market_population', 0)
    distances, parent = ctx['paths'](start)
    found = []
    for site in ctx['sites']:
        node = site.get('node')
        if node is None or not 0 <= node < len(cells):
            continue
        if population_of(site) < floor or not math.isfinite(distances[node]) or distances[node] > reach:
            continue
        found.append((distances[node], site['uid'], node))
    if len(found) < 2:
        return None
    found.sort()
    camps = [_camp(band, 0, start, cells, 'station')]
    for i, (_, _, node) in enumerate(found[:4]):
        camps.append(_camp(band, i + 1, node, cells, 'station'))
    order = [(i, i + 1, 'trunk') for i in range(len(camps) - 1)]
    order.append((len(camps) - 1, 0, 'trunk'))
    return camps, order, parent, distances


def _sacred_circuit(band, ctx):
    """A closed loop over the sacred ground of one god, nearest first."""
    cells, pol, spacing = ctx['cells'], ctx['pol'], ctx['spacing']
    start = band['node']
    reach = _reach(band, pol, 'claim_reach_spacings', spacing, 1.2) * 2.5
    distances, parent = ctx['paths'](start)
    school = band.get('school')
    nodes = []
    for where, node_id, record in ctx['ley']:
        if record['school'] != school:
            continue
        node = ctx['nearest_node'](where)
        if node is None or not math.isfinite(distances[node]) or distances[node] > reach:
            continue
        nodes.append((distances[node], node_id, node))
    nodes.sort()
    seen, picked = {start}, []
    for _, _, node in nodes:
        if node in seen:
            continue
        seen.add(node)
        picked.append(node)
        if len(picked) == 3:
            break
    if not picked:
        return None
    camps = [_camp(band, 0, start, cells, 'shrine')]
    for i, node in enumerate(picked):
        camps.append(_camp(band, i + 1, node, cells, 'shrine'))
    order = [(i, i + 1, 'trunk') for i in range(len(camps) - 1)]
    order.append((len(camps) - 1, 0, 'trunk'))
    return camps, order, parent, distances


def _raid_orbit(band, ctx):
    """A lair, and out-and-back spurs onto what is worth taking.

    A raiding band does not migrate. The spur returning to the lair is the whole shape:
    strike, vanish, and be somewhere defensible before anyone organises.
    """
    cells, pol, spacing = ctx['cells'], ctx['pol'], ctx['spacing']
    start = band['node']
    reach = _reach(band, pol, 'strike_reach_spacings', spacing, 1.3)
    distances, parent = ctx['paths'](start)
    prizes = []
    for site in ctx['sites'] + ctx['hamlets']:
        node = site.get('node')
        if node is None or not 0 <= node < len(cells) or node == start:
            continue
        if not math.isfinite(distances[node]) or distances[node] > reach:
            continue
        prizes.append((-population_of(site), distances[node], node))
    if not prizes:
        return None
    prizes.sort()
    camps = [_camp(band, 0, start, cells, 'lair')]
    order = []
    for i, (_, _, node) in enumerate(prizes[:2]):
        camps.append(_camp(band, i + 1, node, cells, 'terminal'))
        order.append((0, i + 1, 'spur'))
        order.append((i + 1, 0, 'spur'))
    return camps, order, parent, distances


def _flight(band, ctx, kind):
    """One move away from what happened, ending where it cannot easily follow.

    Deserters run from a decided war into cover. Survivors run from a ruin toward the
    nearest place still standing. Both terminate: neither is a circuit.
    """
    cells, pol, spacing = ctx['cells'], ctx['pol'], ctx['spacing']
    start = band['node']
    distances, parent = ctx['paths'](start)
    if kind == 'survivors':
        reach = _reach(band, pol, 'refuge_reach_spacings', spacing, 2.5)
        target = None
        for site in ctx['sites']:
            node = site.get('node')
            if node is None or site['uid'] != band['basis'].get('refuge_uid'):
                continue
            target = node
        if target is None or not math.isfinite(distances[target]) or distances[target] > reach:
            return None
        camps = [_camp(band, 0, start, cells, 'base'), _camp(band, 1, target, cells, 'terminal')]
    else:
        reach = _reach(band, pol, 'war_reach_spacings', spacing, .8) * 3.
        away = ctx['war_direction'](band)
        candidates = _within(distances, reach)

        def cover(node):
            if node == start:
                return -1.
            lead = 0.
            if away:
                lead = clamp((1. + sum(a * b for a, b in zip(away, cells[node]['direction']))) / 2.)
            return ruggedness(cells[node]['fields']) * (.4 + lead)
        target = _best(candidates, cover)
        if target is None or target == start:
            return None
        camps = [_camp(band, 0, start, cells, 'base'), _camp(band, 1, target, cells, 'lair')]
    return camps, [(0, 1, 'trunk')], parent, distances


BUILDERS = {
    'wanderers': lambda band, ctx: _seasonal_camps(band, ctx),
    'merchants': lambda band, ctx: _market_stations(band, ctx),
    'cultists': lambda band, ctx: _sacred_circuit(band, ctx),
    'bandits': lambda band, ctx: _raid_orbit(band, ctx),
    'deserters': lambda band, ctx: _flight(band, ctx, 'deserters'),
    'survivors': lambda band, ctx: _flight(band, ctx, 'survivors'),
}


def _subdivide(band, camps, legs, cells, radius, day_march):
    """Cut any leg longer than a day's march, putting a station at the break.

    This is the whole logic of a caravan route rather than a decoration on it: stations sat
    a day apart precisely so a laden train never had to spend a night in the unmonitored
    gap between nodes. A leg that survives uncut is one a caravan can walk between dawn and
    dusk, so it needs no station.
    """
    out_camps = list(camps)
    out_legs = []
    for leg in legs:
        if leg['length_m'] <= day_march or len(leg['nodes']) < 3:
            out_legs.append(leg)
            continue
        cut_from = leg['from']
        run = 0.
        nodes = leg['nodes']
        segment = [nodes[0]]
        for a, b in zip(nodes, nodes[1:]):
            step = distance(cells[a]['direction'], cells[b]['direction'], radius)
            run += step
            segment.append(b)
            remaining = leg['length_m'] - run
            if run >= day_march and remaining > day_march * .5:
                station = _camp(band, len(out_camps), b, cells, 'station')
                out_camps.append(station)
                out_legs.append({'from': cut_from, 'to': station['id'], 'nodes': segment,
                                 'length_m': run, 'depart_day': None, 'arrive_day': None,
                                 'branch': leg['branch']})
                cut_from = station['id']
                segment = [b]
                run = 0.
        if len(segment) > 1:
            out_legs.append({'from': cut_from, 'to': leg['to'], 'nodes': segment,
                             'length_m': run, 'depart_day': None, 'arrive_day': None,
                             'branch': leg['branch']})
        elif out_legs:
            out_legs[-1]['to'] = leg['to']
    return out_camps, out_legs


def _assign_days(band, camps, legs, ctx):
    """Walk the circuit assigning arrival and departure, anchored on the calendar.

    A herding round is anchored so the winter camp is occupied at midwinter -- that is the
    camp survival depends on, so it is the one the year is built around. Everything else
    starts at its own midsummer and runs on travel time, which is length over speed.
    """
    n = ctx['cfg'].size
    speed = max(1., band['speed_m_per_day'])
    total_travel = 0
    for leg in legs:
        total_travel += max(1, int(round(leg['length_m'] / speed)))
    shares = [CAMP_REST.get(c['kind'], 1.) for c in camps]
    weight = 0.
    for share in shares:
        weight += share
    spare = max(len(camps), DAYS_PER_YEAR - total_travel)
    rest_of = {}
    for camp, share in zip(camps, shares):
        held = max(1, int(spare * share / weight))
        rest_of[camp['id']] = min(held, CAMP_REST_CEILING.get(camp['kind'], held))
    anchor = 0
    winter = next((c for c in camps if c['kind'] == 'winter'), None)
    if winter is not None:
        anchor = midwinter_day(ctx['cells'][winter['node']]['z'], n)
    else:
        anchor = midsummer_day(ctx['cells'][band['node']]['z'], n)
    day = anchor
    by_id = {c['id']: c for c in camps}
    if winter is not None:
        # Start the clock at the winter camp so it holds midwinter, then walk forward.
        order = [l for l in legs]
        start_index = next((k for k, l in enumerate(order) if l['from'] == winter['id']), 0)
        order = order[start_index:] + order[:start_index]
    else:
        order = legs
    first = by_id.get(order[0]['from']) if order else None
    if first is not None:
        first['arrive_day'] = day % DAYS_PER_YEAR
        first['depart_day'] = (day + rest_of[first['id']]) % DAYS_PER_YEAR
    for leg in order:
        travel = max(1, int(round(leg['length_m'] / speed)))
        held = rest_of.get(leg['from'], 1)
        leg['depart_day'] = (day + held) % DAYS_PER_YEAR
        day += held + travel
        leg['arrive_day'] = day % DAYS_PER_YEAR
        camp = by_id.get(leg['to'])
        if camp is not None and camp['arrive_day'] is None:
            camp['arrive_day'] = day % DAYS_PER_YEAR
            camp['depart_day'] = (day + rest_of.get(camp['id'], 1)) % DAYS_PER_YEAR
    # A camp that is only ever a leg's source -- the base a transhumant group holds while
    # the herd moves -- is never reached by the loop above, so it would carry no window at
    # all. It is occupied from when the moving limb leaves it until the limb returns.
    for leg in order:
        camp = by_id.get(leg['from'])
        if camp is not None and camp['arrive_day'] is None and leg['depart_day'] is not None:
            held = rest_of.get(camp['id'], 1)
            camp['depart_day'] = leg['depart_day']
            camp['arrive_day'] = (leg['depart_day'] - held) % DAYS_PER_YEAR


def add_nomad_routes(result, cfg):
    """Give every placed band the circuit its classification implies."""
    block = result.get('nomads')
    if not block or not block.get('groups'):
        return result
    started = perf_counter()
    o = options(cfg)
    pol = policy()
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

    node_of = {}
    for i, cell in enumerate(cells):
        node_of[cell['direction']] = i

    def nearest_node(where):
        if where in node_of:
            return node_of[where]
        best = None
        for i, cell in enumerate(cells):
            mark = (distance(where, cell['direction'], radius), i)
            if best is None or mark < best[0]:
                best = (mark, i)
        return best[1] if best else None

    ley = []
    for name, net in (result.get('magic', {}).get('networks', {}) or {}).items():
        for node in net.get('nodes', []):
            ley.append((tuple(node['direction']), node['id'], {'school': name}))

    def war_direction(band):
        """Unit vector pointing away from the war site the band fled."""
        uid = band['basis'].get('war_site_uid')
        for record in (result.get('ruins', []) or []) + result['settlements']['sites']:
            if record.get('uid') != uid:
                continue
            here = band['direction']
            there = record.get('direction')
            if not there:
                return None
            away = [h - t for h, t in zip(here, there)]
            norm = math.sqrt(sum(v * v for v in away))
            return [v / norm for v in away] if norm > 1e-9 else None
        return None

    ctx = {'cells': cells, 'cfg': cfg, 'pol': pol, 'spacing': spacing, 'paths': paths,
           'sites': result.get('settlements', {}).get('sites', []),
           'hamlets': result.get('humans', {}).get('hamlets', []),
           'ley': ley, 'nearest_node': nearest_node, 'war_direction': war_direction}

    routed = stranded = 0
    for band in block['groups']:
        built = BUILDERS[band['classification']](band, ctx)
        if not built:
            # A band whose circuit cannot be built keeps its start camp and says so. The
            # honest outcome: a herder with nowhere to winter is a real thing the gates
            # cannot see, because reachability needs this pass to exist.
            band['route_status'] = 'stranded'
            stranded += 1
            continue
        camps, order, parent, distances = built
        legs = []
        for a, b, branch in order:
            src, dst = camps[a], camps[b]
            if src['node'] == dst['node']:
                continue
            nodes = trace(parent, band['node'], dst['node']) if src['node'] == band['node'] else []
            if not nodes:
                sub_d, sub_p = paths(src['node'])
                nodes = trace(sub_p, src['node'], dst['node'])
            if not nodes:
                continue
            length = 0.
            for i in range(len(nodes) - 1):
                length += distance(cells[nodes[i]]['direction'], cells[nodes[i + 1]]['direction'], radius)
            legs.append({'from': src['id'], 'to': dst['id'], 'nodes': nodes,
                         'length_m': length, 'depart_day': None, 'arrive_day': None,
                         'branch': branch})
        if not legs:
            band['route_status'] = 'stranded'
            stranded += 1
            continue
        if band['classification'] == 'merchants':
            camps, legs = _subdivide(band, camps, legs, cells, radius, DAY_MARCH_M)
        _assign_days(band, camps, legs, ctx)
        band['camps'] = camps
        band['legs'] = legs
        band['route_status'] = 'routed'
        band['round_length_m'] = round(sum(l['length_m'] for l in legs), 6)
        routed += 1

    block['routes'] = {
        'version': 1, 'routed': routed, 'stranded': stranded,
        'day_march_m': DAY_MARCH_M,
        'method': 'Each classification builds the circuit its behaviour implies -- a two-move seasonal round '
                  'for herders, a market chain subdivided by day marches for caravans, a closed circuit over one '
                  "god's sacred ground for cults, a lair with out-and-back spurs for raiders, and a single "
                  'terminating move for the bands running from something. Legs are traced with Dijkstra over a '
                  'walking cost that permits fords and steeper ground than a road, and prefers forage. Day windows '
                  'come from leg length over speed, anchored so a winter camp holds midwinter; the seasonal phase '
                  'inverts across the equator.',
        'limits': 'Lineage fission is not built, so no band has a child and `fission` never appears as a branch. '
                  'Circuits are static: a band walks the same round every year and nothing re-routes it when the '
                  'world changes underneath. Rest is split evenly across camps rather than earned from forage, so '
                  'a rich camp holds no longer than a poor one. A band whose circuit could not be built carries '
                  'route_status "stranded" and keeps its start camp -- a herder with nowhere to winter is the '
                  'case the classification gate cannot see on its own.',
    }
    elapsed = (perf_counter() - started) * 1000
    result['timing_ms']['nomad_routes'] = elapsed
    result['timing_ms']['total'] += elapsed
    return result
