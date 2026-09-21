"""The countryside wells: every hamlet may have a reeve, every fortress a castellan.

A hamlet is the place that actually starves in a famine and actually loses its herds to
a nest; its reeve speaks for it. A fortress guards a road; its castellan holds it. Both
are named handles on a site the world already placed, and both roll like everything else.
Hamlets and fortresses have no globe direction, so nest reach is measured on the grid in
metres (`spacing_m` per node), the same for every hero, never on the render.
"""
import math

from ..history import cities, final_age, nests, parent_race, short_name
from . import chance, roll
from .guilds import _dangerous

ROLE_WORD = {'farming': 'farmstead', 'resource': 'quarry camp', 'coastal': 'fishing village'}


def anchor(site, kind):
    """The handle a countryside person is keyed on: the terrain node, spelled out.

    ``humans.hamlets[].id`` and ``humans.fortresses[].id`` are **ordinals**.
    ``terrain_humans.record()`` builds ``f'{kind}-{number}'`` where the number is the position
    in the accepted list, and fortresses are accepted in descending ``defence_score`` over a
    ``strategic`` map rebuilt from the road graph every age. Cities die, roads move and war
    history reweights the score, so both the membership and the ordering change at every age
    boundary: ``fortress-36`` names different ground after an advance, and the person built on
    it is renamed although nothing about their ground changed. Worse, the old uid still
    resolves -- to a real person at a real fortress, and the wrong one, with no error.

    The terrain node does not renumber. ``-node-`` is written into the key rather than left
    implicit because ``fortress-13`` and ``fortress-node-13`` would otherwise read alike and
    mean different things, which is how a consumer joins the wrong rows without an error. This
    is the spelling ``npc_roster/sites.py`` already uses for the same sites, so the two key
    spaces join for the first time; ``terrain_villains`` anchors a villain to a ley node id for
    the same reason.

    The kind is part of the key because a hamlet and a fortress can share a node. On the seed-42
    size-33 sample world no fortress currently shares one with a hamlet (0 of 56), but 18 nodes
    are shared across the two kinds on the size-65 sample, so the prefix is load-bearing at
    other sizes even where it looks redundant at this one.

    A site with no ``node`` keeps its ordinal id: there is nothing stabler to key it on, and a
    world whose small-site records have lost their node is broken upstream of this package.
    """
    node = site.get('node')
    return f'{kind}-node-{node}' if node is not None else str(site.get('id'))


def _city_ref(city):
    return {'kind': 'city', 'uid': city['uid'], 'name': city['name']}


def _cores(world):
    return {c.get('site_id'): c for c in (world.get('humans') or {}).get('cores') or []}


def _grid_metres(a, b, spacing):
    return math.hypot(a['x'] - b['x'], a['z'] - b['z']) * spacing


def _nearest_threat(site, dangerous, spacing):
    best = None
    for nest in dangerous:
        if 'x' not in nest or 'z' not in nest:
            continue
        key = (_grid_metres(site, nest, spacing), nest['id'])
        if best is None or key < best[0]:
            best = (key, nest)
    return (best[1], best[0][0]) if best else (None, None)


def hamlet_name(hamlet, city):
    word = ROLE_WORD.get(hamlet.get('role', '').split(' ')[0], 'hamlet')
    return f"the {word} below {short_name(city['name'])}"


def fortress_name(fortress, city):
    return f"the fortress above {short_name(city['name'])}"


def candidates(world, realm_of_city, seed, policy):
    """Reeves and castellans, in site order for exact replay."""
    final = final_age(world)
    by_id = {c['id']: c for c in cities(world) if 'id' in c}
    cores = _cores(world)
    threat = {c.get('city_uid'): c for c in ((world.get('threat_assessments') or {}).get('cities') or [])}
    spacing = float(world.get('spacing_m') or 1000.)
    dangerous = [n for n in nests(world) if _dangerous(n)]
    rules = policy['precipitation']
    people, rolls = [], []
    humans = world.get('humans') or {}
    for hamlet in humans.get('hamlets') or []:
        city = by_id.get(hamlet.get('core_id'))
        if city is None or hamlet.get('kind') != 'hamlet' or 'harbor' in hamlet.get('role', '') or str(hamlet.get('id', '')).startswith('coastal'):
            continue  # harbours belong to the ports well
        core = cores.get(hamlet['core_id']) or {}
        nest, distance = _nearest_threat(hamlet, dangerous, spacing)
        threatened = nest is not None and distance <= rules['reeve']['reach_factor'] * float(nest.get('range_m') or 1000.)
        person = _reeve(world, hamlet, city, core, realm_of_city, final, nest if threatened else None)
        value = rules['reeve']['base'] + (rules['reeve']['starving_bonus'] if float(core.get('food_deficit') or 0.) > 0. else 0.) \
            + (rules['reeve']['threatened_bonus'] if threatened else 0.)
        if roll(person, 'reeve', chance(policy, value), seed, rolls):
            people.append(person)
    for fortress in humans.get('fortresses') or []:
        city = by_id.get(fortress.get('core_id'))
        if city is None:
            continue
        pressed = float((threat.get(city['uid']) or {}).get('war_pressure') or 0.) > 0.
        person = _castellan(world, fortress, city, realm_of_city, final, pressed)
        value = rules['castellan']['base'] + (rules['castellan']['pressed_bonus'] if pressed else 0.) \
            + rules['castellan']['per_defence'] * float(fortress.get('defence_score') or 0.)
        if roll(person, 'castellan', chance(policy, value), seed, rolls):
            people.append(person)
    return people, rolls


def _reeve(world, hamlet, city, core, realm_of_city, final, nest):
    name = hamlet_name(hamlet, city)
    features = {'role:reeve', 'hamlet:' + (hamlet.get('role', 'farming').split(' ')[0] or 'farming')}
    if float(core.get('food_deficit') or 0.) > 0.:
        features.add('hamlet:starving')
    if nest is not None:
        features.add('hamlet:threatened')
    # All four uses of the anchor, together. Repairing one leaves three ways to join the wrong
    # row, and three of them are the ones a story layer, a quest and a save file reach for.
    key = anchor(hamlet, 'hamlet')
    return {'uid': 'hero-reeve-' + key, 'role': 'reeve', 'well': 'hamlets',
            'civilization_id': city['civilization_id'], 'race_id': parent_race(world, city), 'born_age': max(1, final),
            'status': 'living', 'home': _city_ref(city), 'site_name': name,
            'presence': {'site_kind': 'hamlet', 'uid': key, 'situation': 'reeve'},
            'realm_uid': (realm_of_city.get(city['uid']) or {}).get('uid'),
            'nest_id': nest['id'] if nest else None, 'nest_name': nest.get('name') if nest else None,
            'deeds': [{'event_kind': 'hamlet', 'event_id': key, 'age': max(1, final), 'role': 'keeper'}],
            'claim': {'verb': 'protect', 'target_uid': key, 'target_name': name},
            'features': features}


def _castellan(world, fortress, city, realm_of_city, final, pressed):
    name = fortress_name(fortress, city)
    features = {'role:castellan', 'order:member', 'warden:post'}
    if pressed:
        features.add('fortress:pressed')
    key = anchor(fortress, 'fortress')
    return {'uid': 'hero-castellan-' + key, 'role': 'castellan', 'well': 'fortresses',
            'civilization_id': city['civilization_id'], 'race_id': parent_race(world, city), 'born_age': max(1, final),
            'status': 'living', 'home': _city_ref(city), 'site_name': name,
            'presence': {'site_kind': 'fortress', 'uid': key, 'situation': 'garrison'},
            'realm_uid': (realm_of_city.get(city['uid']) or {}).get('uid'),
            'deeds': [{'event_kind': 'fortress', 'event_id': key, 'age': max(1, final), 'role': 'keeper'}],
            'claim': {'verb': 'hold', 'target_uid': key, 'target_name': name},
            'features': features}
