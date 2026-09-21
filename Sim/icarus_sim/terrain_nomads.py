"""Nomad bands: who walks the land once the simulation has settled, and why.

The land decides who walks it. A candidate start point is read for what surrounds it --
a fresh ruin, a battlefield, sacred ground, a road between markets, rough country above
wealth, or pasture with a seasonal swing -- and that reading decides the band's
classification before any weight is drawn. A classification whose preconditions fail is
ineligible outright, so cultists cannot rise where nothing is sacred and caravans cannot
form off the roads. A candidate that satisfies nothing produces no band at all: empty
ground is a result, not a failure.

Placement is a thinned point process over the same ground the nest passes read, so the
expected band count is an integral over habitable land and a wider world holds
proportionally more, with no cap anywhere.

Every gate returns a score in zero to one, so the weight in `nomads.json` is the only
balance lever. Unnormalised scores made that table a lie: ley intensity runs to four while
a bandit's score sat near a half, so cultists won almost every contested draw no matter
what the weights said.

Every reach is a multiple of settlement spacing, never a metre constant or a raster cell,
so world scale and raster size cannot turn a local band into a regional one. Travel speed
is the one deliberate absolute: a walking pace belongs to the traveller, not to the world.

Wealth is read as population rather than `city_class`, which is a label ('capital',
'medium') and has no ordering to compare against.

This pass places and classifies. Routes, seasonal camps and day windows are a separate
pass; a band here carries the camp it starts from and the speed it would walk at.
"""
import json
import math
import random
from pathlib import Path
from functools import lru_cache
from time import perf_counter
from .terrain_tectonics import child_seed
from .terrain_world import options
from .terrain_erosion import sphere_grid
from .terrain_globe import direction
from .terrain_nests import habitat_cells, settled_directions, distance, clamp

VERSION = 1

# Evaluation order, most specific first. It is stable and exported, so a new
# classification is APPENDED, never inserted: anything that has stored an index into
# this order would otherwise be renumbered in every world ever generated.
CLASSIFICATIONS = ('survivors', 'deserters', 'cultists', 'merchants', 'bandits', 'wanderers')

# The camp a band starts from, before the route pass gives it a seasonal set.
ORIGIN_CAMP_KIND = {'survivors': 'base', 'deserters': 'lair', 'cultists': 'shrine',
                    'merchants': 'station', 'bandits': 'lair', 'wanderers': 'base'}


@lru_cache(maxsize=1)
def policy():
    """The balance table, validated on load so a malformed row fails at import."""
    doc = json.loads(Path(__file__).with_name('nomads.json').read_text(encoding='utf-8'))
    if doc.get('version') != 2:
        raise ValueError('Unsupported nomad policy version')
    classes = doc.get('classifications')
    if not isinstance(classes, dict) or set(classes) != set(CLASSIFICATIONS):
        raise ValueError('Nomad policy must define exactly the known classifications')
    for name, entry in classes.items():
        if not entry.get('weight', 0) > 0:
            raise ValueError('Nomad weight must be positive: ' + name)
        low, high = entry['size']
        if not 0 < low <= high:
            raise ValueError('Nomad size band must be positive and ordered: ' + name)
        if not entry.get('speed_m_per_day', 0) > 0:
            raise ValueError('Nomad speed must be positive: ' + name)
        if not isinstance(entry.get('gate'), dict):
            raise ValueError('Nomad classification needs a gate: ' + name)
    split = doc.get('fission')
    if not isinstance(split, dict):
        raise ValueError('Nomad policy must define a fission section')
    if not set(split.get('classifications') or ()) <= set(CLASSIFICATIONS):
        raise ValueError('Fission names a classification that does not exist')
    share_low, share_high = split['child_share']
    if not 0 < share_low <= share_high < 1:
        raise ValueError('Fission child share must be an ordered fraction below one')
    for name in split['classifications']:
        # The capacity curve runs from the gate's own forage floor to this number, so a
        # rich_forage at or below the floor would divide by zero-width and make every
        # band of that class either always or never over capacity.
        if not split.get('rich_forage', 0) > classes[name]['gate'].get('min_forage', 0.):
            raise ValueError('Fission rich_forage must exceed the gate forage floor: ' + name)
    return doc


def ruggedness(fields):
    """How much cover the ground gives: the refuge term bandits and deserters need.

    Slope carries it and the topographic position index sharpens it -- a ridge or a
    ravine hides a band that open ground of the same steepness does not.
    """
    return clamp(fields.get('slope', 0.) / 22.) * (1. + .35 * clamp(abs(fields.get('tpi', 0.)) / 40.))


def seasonal_swing(result, x, z):
    """Summer-to-winter spread in monthly temperature at one cell, zero to one.

    Wanderers exist because of this number: a round is only worth walking where the good
    ground moves with the year. A flat year feeds a settled farm, not a herd. The twelve
    monthly grids already carry the latitude and elevation proxy, including the reversal
    across the equator, so a southern cell swings on the opposite half of the year.
    """
    months = result.get('seasonal_environment', {}).get('months') or []
    if len(months) < 2:
        return 0.
    warm = []
    for month in months:
        grid = month.get('temperature')
        if not grid:
            return 0.
        warm.append(grid[z][x])
    return clamp((max(warm) - min(warm)) / 30.)


def population_of(site):
    """A settlement's weight as a target or a market, in people.

    Hamlets carry `population_estimate: None` -- they are sized by the food they deliver,
    not by a head count -- so the chain ends at that yield. Without the fallback a hamlet
    scores zero and bandits ignore the rural settlements that are their easiest prey.
    """
    for key in ('population_estimate', 'urban_population_estimate', 'rural_population_estimate'):
        value = site.get(key)
        if isinstance(value, (int, float)) and value > 0:
            return float(value)
    yielded = site.get('delivered_food')
    return float(yielded) if isinstance(yielded, (int, float)) and yielded > 0 else 0.


def _where(item, points, n):
    """A record's unit direction, resolved from whatever it carries.

    Sites carry `direction`; hamlets and shrines carry only a node or a grid position, so
    those are resolved the same way `settled_directions` resolves them.
    """
    if item.get('direction'):
        return tuple(item['direction'])
    if 'x' in item and 'z' in item:
        return direction(item['x'], item['z'], n)
    node = item.get('node')
    if isinstance(node, int) and 0 <= node < len(points):
        return direction(points[node][0], points[node][1], n)
    return None


def _nearest(point, candidates, radius):
    """Closest candidate to a direction, as (metres, item). Ties break on the sort key.

    Candidates are (direction, key, item) triples; the key keeps the choice reproducible
    when two things sit exactly the same distance away.
    """
    best = None
    for where, key, item in candidates:
        if not where:
            continue
        mark = (distance(point, where, radius), key)
        if best is None or mark < best[0]:
            best = (mark, item)
    return (best[0][0], best[1]) if best else (math.inf, None)


def _god_for_school(result, school):
    """A god bound to a school, read from the world's own religion block.

    Deliberately not `terrain_religion.gods_by_id`: that reads `pantheon.json` alone, so
    the four hidden gods are absent from it and a blood cult -- the exact case a villain
    of the blood god creates -- would raise instead of finding its patron. Hidden gods
    are the entries whose family is 'outside'.
    """
    if not school:
        return None
    for god in result.get('religion', {}).get('gods', []):
        schools = god.get('schools')
        if not schools:
            single = (god.get('exists') or {}).get('school')
            schools = [single] if single else []
        if school in schools:
            return god.get('id')
    return None


def ground(result, cfg, radius, points):
    """Everything the gates read, resolved once rather than per candidate."""
    n = cfg.size
    sites = result.get('settlements', {}).get('sites', [])
    hamlets = result.get('humans', {}).get('hamlets', [])
    ruins = result.get('ruins', []) or []
    ages = result.get('history', {}).get('ages', []) or []
    latest = max((age.get('age', 0) for age in ages), default=0)
    ley = []
    for name, net in (result.get('magic', {}).get('networks', {}) or {}).items():
        for node in net.get('nodes', []):
            ley.append((tuple(node['direction']), node['id'],
                        {'school': name, 'id': node['id'], 'intensity': node.get('intensity', 0.)}))
    shrines = []
    for site in (result.get('religion', {}).get('sites', []) or []):
        where = _where(site, points, n)
        if where:
            shrines.append((where, site.get('id', ''), site))
    claims = []
    # Deliberately not filtered to standing villains: held ground outlives its holder, so
    # a cult raised on a claim does not disband because the villain that staked it fell.
    # The holder record reached through `claim['villain']` may therefore be fallen.
    for villain in (result.get('villains', {}).get('people', []) or []):
        for claim in villain.get('claims', []) or []:
            where = _where(claim, points, n)
            if where:
                claims.append((where, claim['id'], {'claim': claim, 'villain': villain}))
    roads = []
    seen = set()
    for route in (result.get('roads', {}).get('routes', []) or []):
        for node in route.get('nodes', []):
            if node in seen or not 0 <= node < len(points):
                continue
            seen.add(node)
            roads.append((direction(points[node][0], points[node][1], n), str(node), node))
    # A war site is where a war was decided, which is the ground a deserter runs from.
    # Ruins carry the loser's history; surviving cities carry their own.
    wars = [(_where(r, points, n), r['uid'], r) for r in ruins if r.get('war_history')]
    wars += [(_where(s, points, n), s['uid'], s) for s in sites if s.get('war_history')]
    wealth = [(_where(s, points, n), s['uid'], s) for s in sites]
    wealth += [(_where(h, points, n), h.get('id', ''), h) for h in hamlets]
    return {
        'spacing': float(cfg.settlement_spacing), 'radius': radius, 'latest_age': latest,
        'sites': sites, 'wealth': [w for w in wealth if w[0]],
        'markets': [(_where(s, points, n), s['uid'], s) for s in sites if _where(s, points, n)],
        'fresh_ruins': [(_where(r, points, n), r['uid'], r) for r in ruins
                        if r.get('destroyed_age') == latest and _where(r, points, n)],
        'wars': [w for w in wars if w[0]], 'ley': ley, 'shrines': shrines, 'claims': claims,
        'roads': roads,
        'settled': [(d, str(i), d) for i, d in enumerate(settled_directions(result, cfg)) if d],
    }


def _gate_survivors(cell, g, rule, result):
    """Refugees: a town died this age, and somewhere near is still standing.

    Displaced people overwhelmingly stay close to home, so the band only exists where
    there is both a fresh ruin to flee and a surviving neighbour to flee toward.
    """
    span, ruin = _nearest(cell['direction'], g['fresh_ruins'], g['radius'])
    if ruin is None or span > rule['ruin_reach_spacings'] * g['spacing']:
        return None
    safe, site = _nearest(cell['direction'], g['markets'], g['radius'])
    if site is None or safe > rule['refuge_reach_spacings'] * g['spacing']:
        return None
    scar = clamp((ruin.get('legacy', {}) or {}).get('intensity', 1.) / 4.)
    return clamp(scar / (1. + safe / g['spacing'])), {'ruin_uid': ruin['uid'], 'ruin_distance_m': span,
                    'refuge_uid': site['uid'], 'refuge_distance_m': safe}


def _gate_deserters(cell, g, rule, result):
    """Broken soldiery: a war was decided near here and there is cover to vanish into."""
    span, war = _nearest(cell['direction'], g['wars'], g['radius'])
    if war is None or span > rule['war_reach_spacings'] * g['spacing']:
        return None
    rough = ruggedness(cell['fields'])
    if rough < rule['min_ruggedness']:
        return None
    history = war.get('war_history') or []
    return clamp(rough) * clamp(.6 + .2 * len(history)), {'war_site_uid': war['uid'], 'war_distance_m': span,
                                              'ruggedness': rough, 'engagements': len(history)}


def _gate_cultists(cell, g, rule, result):
    """Pilgrims: sacred ground, and a god who answers to it.

    The hard part of this gate is the point of the whole feature. Without a ley node, a
    shrine or a villain's claim within reach -- and a god actually bound to that school --
    there is no cult here, however well the weights would have scored.
    """
    span, node = _nearest(cell['direction'], g['ley'], g['radius'])
    shrine_span, shrine = _nearest(cell['direction'], g['shrines'], g['radius'])
    claim_span, claim = _nearest(cell['direction'], g['claims'], g['radius'])
    school, strength, evidence = None, 0., {}
    if node is not None and node['intensity'] >= rule['min_ley_intensity'] \
            and span <= rule['ley_reach_spacings'] * g['spacing']:
        school, strength = node['school'], node['intensity']
        evidence = {'ley_node_id': node['id'], 'ley_distance_m': span, 'ley_intensity': strength}
    elif shrine is not None and shrine_span <= rule['shrine_reach_spacings'] * g['spacing']:
        god = shrine.get('god_id')
        evidence = {'shrine_id': shrine.get('id'), 'shrine_distance_m': shrine_span, 'god_id': god}
        for record in result.get('religion', {}).get('gods', []):
            if record.get('id') == god and record.get('schools'):
                school = record['schools'][0]
                break
        strength = 1.
    elif claim is not None and claim_span <= rule['claim_reach_spacings'] * g['spacing']:
        school = claim['villain'].get('school')
        # Scaled by the claim's own influence, which is 1.0 for a living holder and the
        # fallen-claim value once its holder goes. Reading it off the claim keeps the
        # decay question in one place instead of in every consumer.
        strength = (max(1., float(claim['villain'].get('tier', 1.)))
                    * float(claim['claim'].get('influence', 1.)))
        evidence = {'claim_id': claim['claim']['id'], 'villain_uid': claim['villain']['uid'],
                    'claim_distance_m': claim_span}
    if not school:
        return None
    god = _god_for_school(result, school)
    if not god:
        return None
    evidence.update(school=school, god_id=god)
    return clamp(strength / 4.), evidence


def _gate_merchants(cell, g, rule, result):
    """Caravans: a road underfoot and at least two markets worth walking between."""
    road_span, node = _nearest(cell['direction'], g['roads'], g['radius'])
    if node is None or road_span > rule['road_reach_spacings'] * g['spacing']:
        return None
    reach = rule['market_reach_spacings'] * g['spacing']
    found = []
    for where, key, site in g['markets']:
        people = population_of(site)
        if people < rule['min_market_population']:
            continue
        span = distance(cell['direction'], where, g['radius'])
        if span <= reach:
            found.append((span, key, site, people))
    if len(found) < rule['min_markets']:
        return None
    found.sort()
    weight = 0.
    # Plain accumulation, not sum(): CPython compensates a builtin sum of floats and a
    # native port would have to replicate that to stay bit-exact. Not worth buying here.
    for span, _, site, people in found[:4]:
        weight += clamp(math.log10(1. + people) / 5.) / (1. + span / g['spacing'])
    return clamp(weight / min(4, len(found))), {'markets': [site['uid'] for _, _, site, _ in found[:4]],
                    'market_count': len(found), 'nearest_market_m': found[0][0],
                    'road_distance_m': road_span, 'road_node': node}


def _gate_bandits(cell, g, rule, result):
    """Brigands: rough ground, wealth in reach of it, and nobody close enough to police it.

    The productive pattern is refuge terrain beside prosperity -- the hills supply safety
    and the lowlands supply targets -- so both must hold, and authority must not.
    """
    rough = ruggedness(cell['fields'])
    if rough < rule['min_ruggedness']:
        return None
    span, prize = _nearest(cell['direction'], g['wealth'], g['radius'])
    if prize is None or span > rule['strike_reach_spacings'] * g['spacing']:
        return None
    control, seat = _nearest(cell['direction'], g['markets'], g['radius'])
    if control < rule['control_clear_spacings'] * g['spacing']:
        return None
    worth = clamp(math.log10(1. + population_of(prize)) / 5.)
    if worth <= 0:
        return None
    return clamp(rough) * worth * clamp(control / g['spacing'] / 3.), \
        {'prize_uid': prize.get('uid') or prize.get('id'), 'prize_distance_m': span,
         'ruggedness': rough, 'nearest_seat_m': control}


def _gate_wanderers(cell, g, rule, result):
    """Herders: forage worth following, and a year that moves it.

    Transhumance needs two grounds, not one -- high open pasture for the warm months and
    sheltered low ground for the cold. A cell with forage but no seasonal spread feeds a
    farm instead.
    """
    fields = cell['fields']
    forage = max(fields.get('food_potential', 0.), fields.get('natural_food_potential', 0.))
    if forage < rule['min_forage']:
        return None
    swing = cell.get('swing', 0.)
    if swing < rule['min_seasonal_swing']:
        return None
    openness = clamp(1. - fields.get('slope', 0.) / 30.)
    return clamp(forage / .25) * clamp(.5 + .5 * swing) * clamp(.4 + .6 * openness), \
        {'forage': forage, 'seasonal_swing': swing, 'openness': openness}


GATES = {'survivors': _gate_survivors, 'deserters': _gate_deserters, 'cultists': _gate_cultists,
         'merchants': _gate_merchants, 'bandits': _gate_bandits, 'wanderers': _gate_wanderers}


def _pick(rng, shares, total):
    """Cumulative walk over eligible classifications; one uniform draw decides.

    Mirrors the marked-process pick the nest passes use, so both features choose from a
    weighted set with the same primitives a native port has.
    """
    draw = rng.random() * total
    cursor = 0.
    for name, share in shares:
        cursor += share
        if draw <= cursor:
            return name, draw
    return shares[-1][0], draw


def add_nomads(result, cfg):
    """Place and classify the bands walking the finished world."""
    if not cfg.world_recipe or cfg.phase < 16:
        return result
    started = perf_counter()
    o = options(cfg)
    pol = policy()
    occurrence = float(o.get('nomad_occurrence', 1.))
    density = float(o.get('nomad_density', pol['candidate']['density_per_1000km2']))
    radius = result['effective_config']['globe_radius']
    points, areas, _ = sphere_grid(cfg.size, radius)
    cells = habitat_cells(result, cfg, points, areas)
    g = ground(result, cfg, radius, points)
    rng = random.Random(child_seed(cfg.seed, 'nomads-v1', int(o.get('nomad_variation', 0))))
    clearance = pol['candidate']['settlement_clearance_spacings'] * g['spacing']
    groups, rolls = [], []
    counts = {name: 0 for name in CLASSIFICATIONS}
    for cell in cells:
        fields = cell['fields']
        if fields.get('medium') != 'land':
            continue
        # Clearance belongs in the rate rather than in a rejection after the draw: reject
        # an already-drawn candidate and the world quietly holds fewer bands than asked.
        room = clamp(1. - fields.get('slope', 0.) / 45.)
        if room <= 0:
            continue
        if g['settled']:
            near, _ = _nearest(cell['direction'], g['settled'], radius)
            # Clearance scales the rate; it does not skip the cell. A skip discards whole
            # cells, and a cell is 52 km2 at raster 17 against 13 km2 at raster 33, so the
            # same world quietly holds a different number of bands at a different
            # resolution -- the failure does not raise, it just changes the world. Scaling
            # the rate removes area instead of cells and is resolution-independent.
            room *= clamp(near / clearance)
        rate = occurrence * density * cell['area_km2'] / 1000. * room
        if rate <= 0:
            continue
        drawn = int(rate)
        if rng.random() < rate - drawn:
            drawn += 1
        if not drawn:
            continue
        cell['swing'] = seasonal_swing(result, cell['x'], cell['z'])
        for index in range(drawn):
            shares, evidence, total = [], {}, 0.
            for name in CLASSIFICATIONS:
                verdict = GATES[name](cell, g, pol['classifications'][name]['gate'], result)
                if verdict is None:
                    continue
                score, why = verdict
                share = score * pol['classifications'][name]['weight']
                if share <= 0:
                    continue
                shares.append((name, share))
                evidence[name] = why
                total += share
            record = {'node': cell['node'], 'x': cell['x'], 'z': cell['z'],
                      'eligible': [name for name, _ in shares],
                      'evidence': evidence, 'precipitated': bool(shares)}
            if not shares:
                # No gate held. Empty ground is the honest answer, and the ledger says why.
                rolls.append(record)
                continue
            name, draw = _pick(rng, shares, total)
            rule = pol['classifications'][name]
            low, high = rule['size']
            size = rng.randint(low, high)
            # Keyed to the terrain node, never to an ordinal or a culture id: those are
            # renumbered by an age transition and a band has to survive one. The draw
            # index disambiguates a cell that raises more than one band.
            uid = 'nomad-{}-{}'.format(g['latest_age'], cell['node'])
            if index:
                uid = '{}-{}'.format(uid, index)
            groups.append({
                'uid': uid, 'classification': name, 'parent_uid': None,
                'origin': {'kind': 'world', 'id': None, 'age': g['latest_age']},
                'god_id': evidence[name].get('god_id'), 'school': evidence[name].get('school'),
                'node': cell['node'], 'x': cell['x'], 'z': cell['z'],
                'direction': list(cell['direction']), 'biome': cell['biome'],
                'size': size, 'speed_m_per_day': float(rule['speed_m_per_day']),
                'column_length_m': round(size * rule['column_length_per_head_m'], 6),
                'disposition': rule['disposition'], 'seeks': list(rule['seeks']),
                'carries': list(rule['carries']),
                'camps': [{'id': uid + '-camp-0', 'node': cell['node'],
                           'direction': list(cell['direction']),
                           'kind': ORIGIN_CAMP_KIND[name], 'arrive_day': None, 'depart_day': None}],
                'legs': [], 'basis': evidence[name],
            })
            counts[name] += 1
            record.update(roll=draw, chose=name, uid=uid)
            rolls.append(record)
    groups.sort(key=lambda band: band['uid'])
    result['nomads'] = {
        'version': VERSION, 'groups': groups, 'counts': counts, 'rolls': rolls,
        'method': 'A thinned point process over habitable land proposes start points, and the ground around each one '
                  'decides the band. Six classifications are gated on hard geographic preconditions -- a ruin destroyed '
                  'this age with a survivor settlement to flee to, a decided war with cover nearby, sacred ground with '
                  'a god bound to its school, a road between two markets, rough country within strike of wealth and '
                  'clear of authority, or forage with a seasonal swing -- and only eligible classifications enter a '
                  'single weighted draw. A candidate that satisfies no gate produces no band. Every reach is a multiple '
                  'of settlement spacing; speed is absolute metres per day because a walking pace belongs to the '
                  'traveller rather than the world.',
        'limits': 'Placement and classification only. Routes, seasonal camps, day windows and branch topology are a '
                  'separate pass, so a band here carries the camp it starts from and nothing it walks to. Sizes are '
                  'drawn from authored bands rather than from local carrying capacity, and no band consumes forage, '
                  'raids, trades or dies. Nothing here writes back into the world yet.',
    }
    elapsed = (perf_counter() - started) * 1000
    result['timing_ms']['nomads'] = elapsed
    result['timing_ms']['total'] += elapsed
    return result
