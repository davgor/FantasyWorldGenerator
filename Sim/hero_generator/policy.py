"""Packaged policy documents: archetype cards, axis overlays, alignment weights, name tables.

Policies are data so the cast can grow or be rebalanced without touching code. Each file
carries its own ``revision``; the combined revisions travel with every generated cast so a
consumer can tell a policy edit from a world change.
"""
from importlib.resources import files
import json

POLICY_FILES = ('archetypes', 'axis_overlays', 'alignment', 'names', 'wells')
CARD_FIELDS = {'id', 'name', 'prior', 'requires', 'boosts', 'drift', 'intensity', 'faces', 'core', 'pole_notes', 'lines'}
FACE_SPECS = (None, ['public', 'true'], ['calm', 'unleashed'], ['first', 'second'])
CORE_FIELDS = {'belief', 'wants', 'fears', 'tells', 'mechanic', 'never'}
POLES = ('lawful', 'chaotic', 'good', 'evil')
INTENSITIES = (None, 'corner', 'good_axis')


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError(f'duplicate policy key {key!r}')
        result[key] = value
    return result


def _reject(token):
    raise ValueError(f'non-finite policy number {token}')


def load(name):
    if name not in POLICY_FILES:
        raise ValueError(f'unknown policy {name!r}')
    text = files('hero_generator.policies').joinpath(name + '.json').read_text(encoding='utf-8')
    document = json.loads(text, object_pairs_hook=_pairs, parse_constant=_reject)
    if type(document.get('revision')) is not int or document['revision'] < 1:
        raise ValueError(f'policy {name} needs a positive integer revision')
    return document


def load_all():
    policies = {name: load(name) for name in POLICY_FILES}
    lint_archetypes(policies['archetypes'])
    lint_overlays(policies['axis_overlays'])
    return policies


def revisions(policies):
    return {name: policies[name]['revision'] for name in POLICY_FILES}


def lint_archetypes(document):
    """Every card is complete, so a half-authored archetype fails here rather than in play."""
    seen = set()
    for card in document['cards']:
        if set(card) != CARD_FIELDS:
            raise ValueError(f'archetype {card.get("id")!r} fields must be exactly {sorted(CARD_FIELDS)}')
        if card['id'] in seen:
            raise ValueError(f'duplicate archetype {card["id"]!r}')
        seen.add(card['id'])
        if set(card['core']) != CORE_FIELDS or not all(card['core'][k] for k in CORE_FIELDS - {'never'}):
            raise ValueError(f'archetype {card["id"]!r} core is incomplete')
        if set(card['pole_notes']) != set(POLES) or not all(card['pole_notes'].values()):
            raise ValueError(f'archetype {card["id"]!r} needs all four pole notes')
        if not card['lines'] or not all(len(code) == 2 for code in card['lines']):
            raise ValueError(f'archetype {card["id"]!r} needs sample lines keyed by alignment code')
        if not card['requires'] or not all(isinstance(c, list) and c for c in card['requires']):
            raise ValueError(f'archetype {card["id"]!r} needs at least one non-empty precondition')
        if set(card['prior']) != {'law', 'good'} or card['intensity'] not in INTENSITIES:
            raise ValueError(f'archetype {card["id"]!r} has an invalid prior or intensity')
        if card['faces'] not in FACE_SPECS:
            raise ValueError(f'archetype {card["id"]!r} has an unknown faces spec')
    return document


def lint_overlays(document):
    for axis, poles in (('law', ('lawful', 'neutral', 'chaotic')), ('good', ('good', 'neutral', 'evil'))):
        for pole in poles:
            entry = document[axis][pole]
            if set(entry) != {'voice', 'lies', 'never', 'cornered', 'toward_player'} or not isinstance(entry['never'], list):
                raise ValueError(f'axis overlay {axis}/{pole} is incomplete')
    return document
