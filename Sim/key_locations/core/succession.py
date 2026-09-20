"""What happened to a place after it was built, and who is in it now.

The catalogue says what an archetype *is*. This module decides what the world did to it,
which is where "forgotten fortress" and "dungeon" come from — neither is an archetype, both
are outcomes. A fortress raised by a culture that no longer exists, left long enough, with a
beast lair nearby, is a ruined fortress full of monsters, and nothing had to author that.

Every modifier reads a fact the simulation already recorded: how far the nearest ruin and
settlement are, how unstable the local weave is, how close a beast nest sits, and how many
ages have passed. Weights come from the catalogue; this module only bends them.

Pure: no filesystem, no network, no engine, no generator imports.
"""

HOSTILE = ('monsters', 'undead', 'cult', 'beasts')
UNTENDED_STATES = ('natural', 'abandoned', 'ruined', 'sealed', 'buried', 'drowned',
                   'corrupted', 'reclaimed')
THREAT_BASE = {'none': 1, 'nature': 1, 'builders': 1, 'descendants': 1,
               'squatters': 2, 'beasts': 2, 'fae': 2, 'cult': 3, 'undead': 3, 'monsters': 4}
MIN_THREAT, MAX_THREAT = 1, 5


def choose(weights, draw):
    """Weighted pick over sorted keys, so the draw order never depends on dict insertion."""
    items = sorted(weights.items())
    total = sum(weight for _, weight in items)
    if total <= 0:
        return items[0][0]
    cut = draw.random() * total
    running = 0.
    for name, weight in items:
        running += weight
        if cut < running:
            return name
    return items[-1][0]


def _bend(weights, name, factor):
    if name in weights:
        weights[name] *= factor
    return weights


def derive_state(archetype, context, draw):
    """The catalogue's state weights, bent by what the world did to this ground."""
    weights = dict(archetype['states'])
    if archetype['domain'] in ('water', 'ocean', 'lake'):
        return 'drowned' if 'drowned' in weights else choose(weights, draw)
    if context['near_ruin']:
        for name, factor in (('ruined', 2.2), ('abandoned', 1.6), ('active', .35)):
            _bend(weights, name, factor)
    if context['remote']:
        _bend(weights, 'active', .5)
        _bend(weights, 'abandoned', 1.4)
    if context['unstable']:
        _bend(weights, 'corrupted', 2.5)
    if context['ages'] >= 2:
        _bend(weights, 'active', .7)
        _bend(weights, 'ruined', 1.3)
    return choose(weights, draw)


def derive_occupant(archetype, state, context, draw):
    """Who is in it, given what state it is in and what lives nearby."""
    weights = dict(archetype['occupants'])
    if state == 'active':
        for name, factor in (('builders', 2.0), ('descendants', 1.6)):
            _bend(weights, name, factor)
        for name in HOSTILE:
            _bend(weights, name, .4)
    if state in UNTENDED_STATES:
        for name, factor in (('builders', .2), ('descendants', .4)):
            _bend(weights, name, factor)
    if state == 'sealed':
        _bend(weights, 'none', 1.8)
        _bend(weights, 'squatters', .3)
    if state == 'corrupted':
        for name, factor in (('cult', 2.0), ('undead', 1.8), ('monsters', 1.5), ('none', .5)):
            _bend(weights, name, factor)
    if context['near_nest']:
        for name, factor in (('beasts', 2.0), ('monsters', 1.8), ('none', .6)):
            _bend(weights, name, factor)
    if context['remote']:
        _bend(weights, 'squatters', .5)
    else:
        _bend(weights, 'monsters', .6)
    return choose(weights, draw)


def succeed(site, table, context, draw):
    """Something else moved in after the builders left.

    Returns ``None`` when nothing succeeds. A succession is recorded on the site rather than
    silently overwriting the occupant, because "a goblin warren that used to be a silver
    mine" is a better location than either half, and a consumer should be able to say so.
    """
    if site['state'] not in UNTENDED_STATES or context['ages'] < 1:
        return None
    rule = table.get(site['family'])
    if not rule:
        return None
    if draw.random() >= float(rule.get('chance', 0.)):
        return None
    became = choose(rule['occupants'], draw)
    if became == site['occupant']:
        return None
    previous = site['occupant']
    site['occupant'] = became
    return {'from_occupant': previous, 'to_occupant': became, 'note': rule.get('note', '')}


def threat(site, context):
    """An integer 1-5 on the creature-tier rubric: 1 harmless, 5 a campaign threat.

    Deliberately the same scale the nest catalogue already uses, so a consumer ranking a
    dungeon against a beast lair is comparing like with like instead of inventing a bridge
    between two private scales.
    """
    value = THREAT_BASE.get(site['occupant'], 1)
    if site['state'] == 'corrupted':
        value += 1
    if site['tier'] >= 2 and site['occupant'] in HOSTILE:
        value += 1
    if site['state'] == 'active' and site['occupant'] in ('builders', 'descendants'):
        value -= 1
    nest_tier = context.get('nest_tier')
    if context['near_nest'] and nest_tier:
        value = max(value, min(MAX_THREAT, int(nest_tier)))
    if context['unstable']:
        value += 1
    if context.get('near_villain'):
        value += 1
    return max(MIN_THREAT, min(MAX_THREAT, value))
