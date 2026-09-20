"""Age-transition wars: which neighbours are in contention, and who is left standing.

Cities quarrel over the two things the simulation already gives them: ground and food.
Two cities closer than the spacing their founders were meant to keep are pressed against
each other's hinterland, and a city whose own land cannot feed it is living off whatever
its roads reach, which is some neighbour's ground whether either of them likes it. Both
are measured from the world as it stands at the end of an age, never invented here, and
both come from quantities the native core computes too, so a world's wars are the same
in either implementation.

A war is named for the relationship between its participants, not its cause: inside one
civilization it is civil, inside one parent race it is regional, and across parent races
it is international.

This is an artistic history generator. There is no campaign, no front line, no season of
manoeuvre and no casualty model: one exchange, decided by the people and forts each city
already has, and the loser becomes a ruin like any other lost city.
"""
import math
import random

from .terrain_leyline_history import SCHOOLS, dominant_school
from .terrain_tectonics import child_seed

WAR_CIVIL, WAR_REGIONAL, WAR_INTERNATIONAL = 'civil', 'regional', 'international'
# Two cities are pressed together once they stand nearer than this multiple of the
# spacing founding kept between them. At exactly the spacing there is no quarrel.
PROXIMITY_FACTOR = 1.5
# A villain covering both cities of a pair adds this much contention at its seat.
VILLAIN_CONTENTION = .35
# Frequent contention: a contested pair usually fights, and heavy pressure nearly assures it.
WAR_BASE_CHANCE, WAR_PRESSURE_GAIN, WAR_MAX_CHANCE = .5, .4, .92
# What a standing fortress is worth to a city's side of a war, in residents.
FORT_STRENGTH = 50

WAR_REASON = {
    WAR_CIVIL: 'Two cities of one civilization fell out over contested ground and supply, and only one survived the war.',
    WAR_REGIONAL: 'Kindred civilizations of one parent race fought a regional war over contested ground and supply.',
    WAR_INTERNATIONAL: 'Cities of different parent races fought an international war over contested ground and supply.'}


def war_kind(a, b):
    """Civil inside one civilization, regional inside one parent race, else international."""
    if a['population_profile'] == b['population_profile']:
        return WAR_CIVIL
    if a['parent_race_id'] == b['parent_race_id']:
        return WAR_REGIONAL
    return WAR_INTERNATIONAL


def separation(a, b, radius):
    """Surface metres between two cities on the globe."""
    return radius * math.acos(max(-1, min(1, sum(x * y for x, y in zip(a['direction'], b['direction'])))))


def shortfall(core):
    """The share of its own demand a city's hinterland cannot feed.

    Deliberately the pre-trade figure, from the two quantities every hinterland
    reports: what its own land delivers and what its people need. A city covered
    only because a neighbour exports is exactly the city under pressure here, so
    reading the post-trade deficit would hide the very thing being measured.
    """
    if not core:
        return 0.
    demand = core.get('food_demand', 0.)
    if demand <= 0:
        return 0.
    return max(0., min(1., (demand - core.get('food_supply', 0.)) / demand))


def _supply_pressure(a_id, b_id, cores, linked):
    """How hard two road-linked cities lean on the same food.

    Only cities a road already joins can share a harvest, so an unlinked pair has
    nothing to divide however hungry either one is. Between linked cities the
    hungrier one sets the pressure: it is the one that needs the other's ground.
    """
    if (a_id, b_id) not in linked and (b_id, a_id) not in linked:
        return 0.
    return max(shortfall(cores.get(a_id)), shortfall(cores.get(b_id)))


def _villain_pressure(a, b, villains, radius):
    """How hard a seated villain presses two cities together, in 0..1."""
    worst = 0.
    for villain in villains:
        reach = float(villain.get('reach_m') or 0.)
        if reach <= 0.:
            continue
        covered = []
        for city in (a, b):
            angle = math.acos(max(-1., min(1., sum(x * y for x, y in zip(city['direction'], villain['direction'])))))
            covered.append(radius * angle)
        if max(covered) > reach:
            continue
        worst = max(worst, VILLAIN_CONTENTION * (1. - max(covered) / reach))
    return worst


def contested_pairs(cities, cores, routes, radius, spacing, proximity_factor=PROXIMITY_FACTOR, villains=()):
    """Pairs under territorial or supply pressure, strongest contention first.

    `cores` are the hinterland records of the same cities, in any order, and `routes`
    the road network joining them; a city with no core simply contributes no supply
    pressure. Ordering is by pressure and then by uid, so the same world always
    presents the same quarrels in the same order.
    """
    by_site = {core['site_id']: core for core in cores}
    linked = {(road['from'], road['to']) for road in routes}
    limit = proximity_factor * spacing
    pairs = []
    for i, a in enumerate(cities):
        for j in range(i + 1, len(cities)):
            b = cities[j]
            distance = separation(a, b, radius)
            proximity = max(0., 1. - distance / limit) if limit > 0 else 0.
            supply = _supply_pressure(a['id'] if 'id' in a else i, b['id'] if 'id' in b else j,
                                      by_site, linked)
            if proximity <= 0 and supply <= 0:
                continue
            # A villain whose reach covers both presses them together: neighbours under
            # one shadow quarrel over what is left, which is how its presence reaches the
            # forecast and, through it, how thick the walls are built.
            villain = _villain_pressure(a, b, villains, radius)
            pairs.append({'a': i, 'b': j, 'a_uid': a['uid'], 'b_uid': b['uid'],
                          'distance_m': distance, 'proximity_pressure': proximity,
                          'supply_pressure': supply, 'villain_pressure': villain,
                          'pressure': min(1., proximity + supply + villain),
                          'kind': war_kind(a, b)})
    pairs.sort(key=lambda p: (-p['pressure'], p['a_uid'], p['b_uid']))
    return pairs


def war_chance(pressure, base=WAR_BASE_CHANCE, gain=WAR_PRESSURE_GAIN, cap=WAR_MAX_CHANCE):
    """Contested neighbours usually fight; pressure decides how close to certain it is."""
    return min(cap, base + gain * max(0., min(1., pressure)))


def war_strength(city, core):
    """What a city brings to one exchange: its people and the forts already on its roads."""
    return city.get('population_estimate', 0) + FORT_STRENGTH * len(core.get('fortress_ids', []) if core else [])


def _key_point_school(city, layers, magic_enabled):
    """The school a fallen city leaves behind, when its ground was already charged.

    `dominant_school` is the same test the leyline threat uses, so a war only seeds a
    key point where a clear school already held the ground.
    """
    if not magic_enabled:
        return None
    try:
        # A hidden school's field may be absent from a hand-built layer set; missing is
        # zero potency, not "this city has no school", which would drop the key point a
        # magically charged city is owed when it falls.
        potencies = {name: (layers['ley_' + name][city['z']][city['x']] if 'ley_' + name in layers else 0.)
                     for name in SCHOOLS}
    except (KeyError, IndexError):
        return None
    if not any(potencies.values()):
        return None
    return dominant_school(potencies)


def war_outlook(cities, cores, routes, radius, spacing, age=None, villains=()):
    """What each living city can expect of war, for the threat assessment and the story web.

    Per uid: `wars_recent` (wars fought in `age`), `enemy_living` (a former opponent still
    stands), `war_risk`, the strongest contention pressure a living neighbour puts on the
    city right now, with that neighbour and the kind of war it would be, and `war_hunger`,
    the pressure the city itself exerts on a neighbour because it cannot feed its people.
    A pair pressed by supply has a direction: the hungrier city is the one that needs the
    other's ground, so it carries the hunger and the other carries the risk. A pair pressed
    by proximity alone has none; both carry the risk. Either way it is the same pair
    pressure the next age's lottery will draw against, so it is a forecast the wars module
    itself stands behind, not a memory of wars already fought.
    """
    living = {city['uid'] for city in cities}
    by_site = {core['site_id']: core for core in cores}
    outlook = {city['uid']: {'wars_recent': sum(1 for e in city.get('war_history') or () if age is not None and e.get('age') == age),
                             'enemy_living': any(e.get('opponent_uid') in living for e in city.get('war_history') or ()),
                             'war_risk': 0., 'war_risk_kind': None, 'war_risk_opponent_uid': None,
                             'war_hunger': 0., 'war_hunger_target_uid': None}
               for city in cities}
    for pair in contested_pairs(cities, cores, routes, radius, spacing, villains=villains):
        a, b = cities[pair['a']], cities[pair['b']]
        hungry = None
        if pair['supply_pressure'] > pair['proximity_pressure']:
            need = {c['uid']: shortfall(by_site.get(c['id'] if 'id' in c else i)) for c, i in ((a, pair['a']), (b, pair['b']))}
            if need[a['uid']] != need[b['uid']]:
                hungry = a if need[a['uid']] > need[b['uid']] else b
        for city, other in ((a, b), (b, a)):
            row = outlook[city['uid']]
            if hungry is city:
                if pair['pressure'] > row['war_hunger']:
                    row.update(war_hunger=round(pair['pressure'], 6), war_hunger_target_uid=other['uid'])
            elif pair['pressure'] > row['war_risk']:
                row.update(war_risk=round(pair['pressure'], 6), war_risk_kind=pair['kind'], war_risk_opponent_uid=other['uid'])
    return outlook


def resolve_wars(cities, cores, routes, layers, radius, spacing, seed, age,
                 magic_enabled=True, rolls=None, survival=0., survival_rolls=None, villains=()):
    """Fight every contested pair that draws for it, and report what each war cost.

    Returns the war records and, separately, the fate of each defeated city keyed by
    uid, in the shape `city_fate` produces so the age transition can ruin them through
    the one path that already exists. A city can be dragged into several wars but can
    only be lost once, so a pair whose loser is already gone is not fought again.

    `survival` is the world option `war_survival`: the chance a defeated city survives
    as the victor's vassal instead of a ruin. At zero (the default) nothing changes and
    war records keep their old shape; above zero each war draws a second seeded roll,
    and a vassalage war carries `outcome`, `survival_chance` and `survival_roll` and
    leaves no fate. `rolls` and `survival_rolls` replace the seeded draws in tests,
    keyed by war id with `'*'` as a default.
    """
    by_site = {core['site_id']: core for core in cores}
    wars, fates, spared = [], {}, set()
    for pair in contested_pairs(cities, cores, routes, radius, spacing, villains=villains):
        a, b = cities[pair['a']], cities[pair['b']]
        if a['uid'] in fates or b['uid'] in fates or a['uid'] in spared or b['uid'] in spared:
            continue
        war_id = 'war-%d-%d' % (age, len(wars))
        chance = war_chance(pair['pressure'])
        if rolls is not None:
            draw = rolls.get(war_id, rolls.get('*', 1.))
        else:
            draw = random.Random(child_seed(seed, 'war-' + a['uid'] + '-' + b['uid'], age)).random()
        if draw >= chance:
            continue
        a_core = by_site.get(a['id'] if 'id' in a else pair['a'])
        b_core = by_site.get(b['id'] if 'id' in b else pair['b'])
        # Strength decides it. A genuine tie goes to the lower uid, which is stable and
        # which the native core can reproduce; a city's suitability is not carried there.
        ranked = sorted(((a, a_core), (b, b_core)),
                        key=lambda item: (-war_strength(*item), item[0]['uid']))
        victor, defeated = ranked[0][0], ranked[1][0]
        war = {'id': war_id, 'age': age, 'kind': pair['kind'],
               'participants': [a['uid'], b['uid']],
               'victor_uid': victor['uid'], 'defeated_uid': defeated['uid'],
               'victor_civilization_id': victor['population_profile'],
               'defeated_civilization_id': defeated['population_profile'],
               'victor_parent_race_id': victor['parent_race_id'],
               'defeated_parent_race_id': defeated['parent_race_id'],
               'distance_m': pair['distance_m'], 'proximity_pressure': pair['proximity_pressure'],
               'supply_pressure': pair['supply_pressure'], 'pressure': pair['pressure'],
               'victor_strength': war_strength(*ranked[0]), 'defeated_strength': war_strength(*ranked[1]),
               'chance': chance, 'roll': draw, 'reason': WAR_REASON[pair['kind']]}
        wars.append(war)
        if survival > 0.:
            if survival_rolls is not None:
                second = survival_rolls.get(war_id, survival_rolls.get('*', 1.))
            else:
                second = random.Random(child_seed(seed, 'war-survival-' + a['uid'] + '-' + b['uid'], age)).random()
            war.update(outcome='vassalage' if second < survival else 'ruin', survival_chance=survival, survival_roll=second)
            if second < survival:
                # The loser lives on as a vassal: a standing enemy for the victor's history,
                # a claim left open for its own. It cannot be fought again this age.
                spared.add(defeated['uid'])
                continue
        fates[defeated['uid']] = {
            'cause': 'war_' + pair['kind'], 'reason': WAR_REASON[pair['kind']],
            'evidence': {'war_id': war_id, 'kind': pair['kind'], 'opponent_uid': victor['uid'],
                         'opponent_civilization_id': victor['population_profile'],
                         'opponent_parent_race_id': victor['parent_race_id'],
                         'distance_m': pair['distance_m'], 'pressure': pair['pressure']},
            'probability': chance, 'roll': draw,
            'new_node_school': _key_point_school(defeated, layers, magic_enabled)}
    return wars, fates


def participation(war, uid):
    """One city's line in its own war history."""
    victor = war['victor_uid'] == uid
    return {'war_id': war['id'], 'age': war['age'], 'kind': war['kind'],
            'outcome': 'victor' if victor else 'defeated',
            'opponent_uid': war['defeated_uid'] if victor else war['victor_uid'],
            'opponent_civilization_id': (war['defeated_civilization_id'] if victor
                                         else war['victor_civilization_id']),
            'opponent_parent_race_id': (war['defeated_parent_race_id'] if victor
                                        else war['victor_parent_race_id'])}


def veteran_wars(city):
    """How many wars a city carries, whatever it did in them."""
    return len(city.get('war_history') or ())
