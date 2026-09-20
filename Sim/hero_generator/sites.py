"""Camps and relics from ruins, and where the dispossessed end up.

A ruin may be squatted: a Camp (bandits, a cult, a remnant), rolled per ruin. A ruin
always leaves a relic resting in it. Placement then gives the people no city shelters a
place to be: an heir leads the camp in their own ruin, a master of a dead college is held
captive or hides at a camp, or shelters as a refugee in the nearest surviving city.
None of this is a script; it is where the person is standing when the story starts.
"""
from .history import cause_kind, cities, final_age, nearest_city, radius, ruins, short_name
from .seeds import rng
from .wells import chance, roll

RELIC_BY_CAUSE = {'self_magic': ('focus', 'the {school} focus of {name}'), 'ley': ('focus', 'the {school} focus of {name}'),
                  'war': ('banner', 'the banner of {name}'), 'beast': ('reliquary', 'the reliquary of {name}')}


def camps(world, seed, policy):
    rule = policy['precipitation']['camp']
    found, rolls = [], []
    for ruin in ruins(world):
        record = {'uid': 'camp-' + ruin['uid'], 'ruin_uid': ruin['uid'], 'name': f"the camp in the ruins of {short_name(ruin['name'])}",
                  'node': ruin['node'], 'x': ruin['x'], 'z': ruin['z'], 'direction': list(ruin['direction']),
                  'origin': 'ruin_squat', 'civilization_id': ruin['civilization_id'], 'since_age': ruin['destroyed_age'],
                  'deeds': [{'event_kind': 'ruin', 'event_id': ruin['id'], 'age': ruin['destroyed_age']}]}
        value = chance(policy, rule['base'] + rule['per_city_class'].get(ruin.get('city_class', 'small'), 0.))
        if roll(record, 'camp', value, seed, rolls):
            record.pop('deeds')
            found.append(record)
    return found, rolls


def relics(world):
    out = []
    for ruin in ruins(world):
        kind, template = RELIC_BY_CAUSE.get(cause_kind(ruin), RELIC_BY_CAUSE['war'])
        if ruin.get('city_class') == 'capital' and kind == 'banner':
            kind, template = 'crown', 'the crown of {name}'
        school = ruin.get('new_node_school') if kind == 'focus' else None
        out.append({'uid': 'relic-' + ruin['uid'], 'kind': kind, 'name': template.format(name=short_name(ruin['name']), school=school or 'weave'),
                    'origin_event': ruin['id'], 'resting_at': ruin['uid'], 'holder_uid': None, 'school': school})
    return out


def place(world, people, camp_list, seed, policy):
    """Give the dispossessed somewhere to stand; a person with nowhere at all stays a legend."""
    final = final_age(world)
    globe = radius(world)
    living = cities(world)
    by_ruin = {c['ruin_uid']: c for c in camp_list}
    for person in people:
        if final - person['born_age'] > 1 or person.get('home'):
            continue
        lost = person.get('lost')
        camp = by_ruin.get(lost['uid']) if lost else None
        if person['role'] == 'pretender' and camp and policy['placement']['heir_leads_own_camp'] and person['status'] == 'legend':
            person.update(status='living', presence={'site_kind': 'camp', 'uid': camp['uid'], 'situation': 'leader'})
            person['features'] |= {'role:camp_leader', 'stake:none'}
            camp['leader_uid'] = person['uid']
        elif person.get('dispossessed'):
            if camp:
                situation = rng(seed, 'hero-place-' + person['uid']).choice(policy['placement']['magister_at_camp'])
                person.update(status='living', presence={'site_kind': 'camp', 'uid': camp['uid'], 'situation': situation})
            else:
                city = nearest_city(ruins_by_uid(world)[lost['uid']], living, globe) if living else None
                if city is None:
                    person['status'] = 'legend'
                    continue
                person.update(status='living', home={'kind': 'city', 'uid': city['uid'], 'name': city['name']},
                              presence={'site_kind': 'city', 'uid': city['uid'], 'situation': 'refugee'})
    return people


def ruins_by_uid(world):
    return {r['uid']: r for r in ruins(world)}
