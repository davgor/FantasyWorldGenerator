"""Faces: what the world sees first, and what is true.

Most people have one face. A card may declare two: `public`/`true` (the Deceiver, the
False Hero), `calm`/`unleashed` (the Beast), `first`/`second` (the Fractured Heart). Each
face carries its own alignment, apparent role, claim and persona, so a public face speaks
with a Good overlay while the true face underneath speaks with an Evil one.
"""
from .alignment import record
from .persona import compose
from .seeds import rng


def build(card, person, alignment, overlays, names_policy, seed):
    base = {'label': 'public', 'name': person['name'], 'apparent_role': person['role'], 'alignment': alignment,
            'claim': person['claim'], 'persona': compose(card, overlays, alignment)}
    spec = card['faces']
    if not spec:
        return [base]
    if spec == ['public', 'true']:
        draw = rng(seed, 'hero-face-' + person['uid'])
        shown = record(alignment['law'], max(.5, abs(alignment['good'])))  # the mask is always visibly good
        covers = names_policy['cover_roles']
        cover = draw.choice(covers.get(person['role'], covers['default']))
        public = {'label': 'public', 'name': person['name'], 'apparent_role': cover, 'alignment': shown,
                  'claim': {'verb': 'protect', 'target_uid': person['claim']['target_uid'], 'target_name': person['claim']['target_name']},
                  'persona': compose(card, overlays, shown)}
        true = dict(base, label='true')
        return [public, true]
    if spec == ['calm', 'unleashed']:
        loosed = record(-1., min(alignment['good'], -.5))
        return [dict(base, label='calm'), dict(base, label='unleashed', alignment=loosed, persona=compose(card, overlays, loosed))]
    if spec == ['first', 'second']:
        draw = rng(seed, 'hero-face-' + person['uid'])
        other = record(-alignment['law'] + draw.uniform(-.3, .3), -alignment['good'] + draw.uniform(-.3, .3))
        return [dict(base, label='first'), dict(base, label='second', alignment=other, persona=compose(card, overlays, other))]
    raise ValueError(f'unknown faces spec {spec!r} on {card["id"]}')
