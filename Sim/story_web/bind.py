"""Binding: prompt and option templates filled with the names the hero's own record supplies.

Slots are `{hero}`, `{target}`, `{rival}`, `{home}`, `{lost}`, `{relic}`, `{realm}`,
`{realm_other}` and `{species}`. A slot the record cannot fill is left readable
("their rival") rather than invented. Every lookup is guarded: a record missing a name
falls back the same way rather than failing the whole block.
"""

FALLBACK = {'hero': 'the hero', 'target': 'what they claim', 'rival': 'their rival', 'home': 'their home',
            'lost': 'what was lost', 'relic': 'the relic', 'realm': 'their realm', 'realm_other': 'the neighbouring realm',
            'species': 'the beast', 'lost_other': 'the city they took'}


class _Slots(dict):
    def __missing__(self, key):
        return FALLBACK.get(key, '{' + key + '}')


def slots_for(hero, heroes):
    names = {p.get('uid'): p.get('display_name') or p.get('uid') for p in (heroes.get('people') or []) + (heroes.get('dreads') or [])}
    realms = {r.get('uid'): r.get('name') for r in heroes.get('realms') or [] if r.get('uid') and r.get('name')}
    relics = {r.get('resting_at'): r.get('name') for r in heroes.get('relics') or []
              if r.get('holder_uid') is None and r.get('resting_at') and r.get('name')}
    slots = _Slots(hero=hero.get('display_name') or hero['uid'])
    claim = hero.get('claim') or {}
    if claim.get('target_name'):
        slots['target'] = claim['target_name']
    rivals = hero.get('rivals') or []
    if rivals:
        slots['rival'] = names.get(rivals[0]) or rivals[0]
    elif claim.get('verb') in ('kill', 'avenge', 'expose', 'overthrow') and claim.get('target_name'):
        slots['rival'] = claim['target_name']
    if (hero.get('home') or {}).get('name'):
        slots['home'] = hero['home']['name']
    lost = hero.get('lost') or {}
    if lost.get('name'):
        slots['lost'] = lost['name']
        if relics.get(lost.get('uid')):
            slots['relic'] = relics[lost['uid']]
    realm_uid = hero.get('realm_uid')
    if realm_uid in realms:
        slots['realm'] = realms[realm_uid]
        others = sorted(name for uid, name in realms.items() if uid != realm_uid)
        if others:
            slots['realm_other'] = others[0]
    elif realms:
        slots['realm_other'] = sorted(realms.values())[0]
    if hero.get('species'):
        slots['species'] = hero['species']
    taken = hero.get('defeated') or []
    if taken and isinstance(taken[0], dict) and taken[0].get('name'):
        slots['lost_other'] = taken[0]['name']
    return slots


def fill(template, slots):
    text = template.format_map(slots)
    return text[:1].upper() + text[1:]
