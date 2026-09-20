"""Alignment: two axes in -1..1, derived from provenance before any archetype is chosen.

The civilization gives a centre, the deeds push it, a seeded jitter spreads it without
ever flipping a sign the deeds decided, and the label is read off the nine-cell grid.
Archetype intensity (Incarnate, Broken Soul, the moral poles) is applied afterwards.
"""
from .seeds import rng

THRESHOLD = .34
LAW_NAMES = ('Chaotic', 'Neutral', 'Lawful')
GOOD_NAMES = ('Evil', 'Neutral', 'Good')


def clamp(value):
    return max(-1., min(1., value))


def pole(value):
    return 1 if value > THRESHOLD else -1 if value < -THRESHOLD else 0


def law_pole(value):
    return ('chaotic', 'neutral', 'lawful')[pole(value) + 1]


def good_pole(value):
    return ('evil', 'neutral', 'good')[pole(value) + 1]


def label(law, good):
    names = (LAW_NAMES[pole(law) + 1], GOOD_NAMES[pole(good) + 1])
    return 'True Neutral' if names == ('Neutral', 'Neutral') else ' '.join(names)


def code(law, good):
    return 'CNL'[pole(law) + 1] + 'ENG'[pole(good) + 1]


def _shift(policy, key):
    return policy['deed_shifts'].get(key, {'law': 0., 'good': 0.})


def _bounded(value, decided):
    """Jitter may move a value but never across zero once a deed put it on one side."""
    if decided > 0:
        return max(.01, value)
    if decided < 0:
        return min(-.01, value)
    return value


def derive_person(person, policy, seed):
    bias = policy['civilization_bias'].get(person['civilization_id'], {'law': 0., 'good': 0.})
    law, good = bias['law'], bias['good']
    decided_law = decided_good = 0.
    for deed in person['deeds']:
        if deed['event_kind'] == 'ruin' and deed['role'] == 'heir':
            key = 'ruin_heir_capital' if person['lost']['city_class'] == 'capital' else 'ruin_heir'
        elif deed['event_kind'] == 'war':
            key = f"war_{deed.get('kind', 'civil')}_{'victor' if deed['role'] == 'credited' else 'defeated'}"
        else:
            continue
        shift = _shift(policy, key)
        law += shift['law']
        good += shift['good']
        decided_law += shift['law']
        decided_good += shift['good']
    draw = rng(seed, 'hero-alignment-' + person['uid'])
    spread = policy['jitter']
    law = _bounded(clamp(law + draw.uniform(-spread, spread)), decided_law)
    good = _bounded(clamp(good + draw.uniform(-spread, spread)), decided_good)
    return record(law, good)


def derive_dread(dread, policy, seed):
    base = policy['dread_base']
    family = policy['dread_family'].get(dread.get('family') or '', {'law': 0., 'good': 0.})
    draw = rng(seed, 'hero-alignment-' + dread['uid'])
    spread = policy['jitter']
    law = clamp(base['law'] + family['law'] + draw.uniform(-spread, spread))
    good = clamp(base['good'] + family['good'] + draw.uniform(-spread, spread))
    return record(law, good)


def record(law, good, drift=None):
    law, good = round(clamp(law), 3), round(clamp(good), 3)
    return {'law': law, 'good': good, 'label': label(law, good), 'code': code(law, good), 'drift': drift}


def intensify(alignment, intensity, draw):
    """Push to the corner (Incarnate) or to a moral pole (Broken Soul, Malevolent/Benevolent)."""
    if not intensity:
        return alignment
    sign = lambda v: 1. if v > 0 else -1. if v < 0 else (1. if draw.random() < .5 else -1.)
    good = sign(alignment['good'])
    law = sign(alignment['law']) if intensity == 'corner' else alignment['law']
    return record(law, good, alignment.get('drift'))
