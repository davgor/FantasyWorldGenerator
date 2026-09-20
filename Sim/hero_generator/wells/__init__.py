"""Wells: each generator output that precipitates people, and the one roll they all share.

A candidate rolls exactly once, seeded from its uid, and the ledger keeps the outcome
either way, so the block records what history could have produced and did not.
"""
from ..seeds import rng


def chance(policy, value):
    return round(max(0., min(policy['cap'], value)), 3)


def roll(record, kind, value, seed, rolls, event_id=None, age=None):
    draw = rng(seed, 'hero-roll-' + record['uid']).random()
    precipitated = draw < value
    first = record['deeds'][0] if record.get('deeds') else {}
    rolls.append({'candidate_uid': record['uid'], 'kind': kind, 'event_id': event_id or first.get('event_id'),
                  'age': age if age is not None else first.get('age'), 'chance': value, 'roll': round(draw, 6),
                  'precipitated': precipitated})
    return precipitated
