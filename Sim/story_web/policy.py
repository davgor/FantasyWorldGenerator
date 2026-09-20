"""Packaged policy documents: the trope catalogue, archetype constraints and the weight equation.

Policies are data so the web can widen or be rebalanced without touching code. Each file
carries its own ``revision``; the combined revisions travel with every compiled block so a
consumer can tell a policy edit from a world change.
"""
from importlib.resources import files
import json
import math

from .facts import known_fact

POLICY_FILES = ('tropes', 'constraints', 'weights')
TROPE_FIELDS = {'id', 'name', 'pull', 'requires', 'boosts', 'fits', 'claims', 'cast', 'acts', 'examples'}
CASTS = ('person', 'dread')
ACT_FIELDS = {'id', 'title', 'prompt', 'completion', 'abandonment', 'options'}
OPTION_FIELDS = {'id', 'text', 'delta', 'effect'}
WEIGHT_FIELDS = {'schema', 'revision', 'notes', 'fit_gain', 'fit_floor', 'pull_floor', 'fits_factor', 'claim_factor',
                 'threshold', 'node_intense_threshold', 'famine_coverage', 'gainable_features', 'max_threads_per_act', 'initiative_days'}
CONSTRAINT_FIELDS = {'claim_locked', 'drift_locked', 'allowed_verbs'}
CLAIM_VERBS = ('hold', 'retake', 'avenge', 'exploit', 'convert', 'protect', 'unify', 'kill', 'expose', 'overthrow', 'none')
MAX_DELTA = 0.5
ACTS_PER_TROPE = 3


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
    text = files('story_web.policies').joinpath(name + '.json').read_text(encoding='utf-8')
    document = json.loads(text, object_pairs_hook=_pairs, parse_constant=_reject)
    if type(document.get('revision')) is not int or document['revision'] < 1:
        raise ValueError(f'policy {name} needs a positive integer revision')
    return document


def load_all():
    policies = {name: load(name) for name in POLICY_FILES}
    lint_tropes(policies['tropes'])
    lint_constraints(policies['constraints'])
    lint_weights(policies['weights'])
    return policies


def revisions(policies):
    return {name: policies[name]['revision'] for name in POLICY_FILES}


def _finite(value, what):
    if type(value) not in (int, float) or isinstance(value, bool) or not math.isfinite(value):
        raise ValueError(f'{what} must be a finite number')
    return value


def lint_tropes(document):
    """Every spoke is complete, so a half-authored trope fails here rather than in the lab."""
    seen = set()
    for trope in document['tropes']:
        tid = trope.get('id')
        if set(trope) != TROPE_FIELDS:
            raise ValueError(f'trope {tid!r} fields must be exactly {sorted(TROPE_FIELDS)}')
        if tid in seen:
            raise ValueError(f'duplicate trope {tid!r}')
        seen.add(tid)
        if set(trope['pull']) != {'law', 'good'} or any(abs(_finite(trope['pull'][k], f'{tid} pull')) > 1 for k in ('law', 'good')):
            raise ValueError(f'trope {tid!r} pull must be two axes within -1..1')
        if not trope['requires'] or not all(isinstance(c, list) and c for c in trope['requires']):
            raise ValueError(f'trope {tid!r} needs at least one non-empty precondition')
        for conjunction in trope['requires']:
            for token in conjunction:
                if not known_fact(token.lstrip('!')):
                    raise ValueError(f'trope {tid!r} names an unknown fact {token!r}')
        for fact, factor in trope['boosts'].items():
            if not known_fact(fact) or _finite(factor, f'{tid} boost {fact}') <= 0:
                raise ValueError(f'trope {tid!r} boost {fact!r} is unknown or non-positive')
        if not isinstance(trope['fits'], list) or not all(isinstance(a, str) and a for a in trope['fits']):
            raise ValueError(f'trope {tid!r} fits must be archetype ids')
        if any(v not in CLAIM_VERBS for v in trope['claims']):
            raise ValueError(f'trope {tid!r} names an unknown claim verb')
        if not trope['cast'] or any(c not in CASTS for c in trope['cast']):
            raise ValueError(f'trope {tid!r} cast must be a non-empty subset of {CASTS}')
        if len(trope['acts']) != ACTS_PER_TROPE:
            raise ValueError(f'trope {tid!r} needs exactly {ACTS_PER_TROPE} acts')
        act_ids = set()
        for act in trope['acts']:
            if set(act) != ACT_FIELDS:
                raise ValueError(f'trope {tid!r} act {act.get("id")!r} fields must be exactly {sorted(ACT_FIELDS)}')
            if act['id'] in act_ids:
                raise ValueError(f'trope {tid!r} repeats act id {act["id"]!r}')
            act_ids.add(act['id'])
            if not isinstance(act['prompt'], str) or not act['title']:
                raise ValueError(f'trope {tid!r} act {act["id"]!r} needs a title and a string prompt')
            if act['completion'].get('kind') != 'target' or not act['completion'].get('target') or not act['completion'].get('state'):
                raise ValueError(f'trope {tid!r} act {act["id"]!r} completion must be a typed target state')
            if act['abandonment'].get('kind') != 'deadline' or type(act['abandonment'].get('days')) is not int or act['abandonment']['days'] < 1:
                raise ValueError(f'trope {tid!r} act {act["id"]!r} abandonment must be a deadline in whole days')
            if not 2 <= len(act['options']) <= 4:
                raise ValueError(f'trope {tid!r} act {act["id"]!r} needs two to four options')
            option_ids = set()
            for option in act['options']:
                if set(option) != OPTION_FIELDS or option['id'] in option_ids or not option['text'] or not option['effect']:
                    raise ValueError(f'trope {tid!r} act {act["id"]!r} has an incomplete or duplicate option')
                option_ids.add(option['id'])
                if set(option['delta']) != {'law', 'good'} or any(abs(_finite(option['delta'][k], 'delta')) > MAX_DELTA for k in ('law', 'good')):
                    raise ValueError(f'trope {tid!r} option {option["id"]!r} delta must stay within ±{MAX_DELTA}')
        if not trope['examples'] or not all(isinstance(e, str) and e for e in trope['examples']):
            raise ValueError(f'trope {tid!r} needs at least one prose example')
    return document


def lint_constraints(document):
    if set(document['default']) != CONSTRAINT_FIELDS:
        raise ValueError('constraints default must carry exactly the constraint fields')
    for archetype, entry in document['archetypes'].items():
        if set(entry) != CONSTRAINT_FIELDS:
            raise ValueError(f'constraint for {archetype!r} must carry exactly the constraint fields')
        if entry['allowed_verbs'] is not None and any(v not in CLAIM_VERBS for v in entry['allowed_verbs']):
            raise ValueError(f'constraint for {archetype!r} names an unknown claim verb')
    return document


def lint_weights(document):
    if set(document) != WEIGHT_FIELDS:
        raise ValueError(f'weights fields must be exactly {sorted(WEIGHT_FIELDS)}')
    for key in ('fit_gain', 'fit_floor', 'pull_floor', 'fits_factor', 'claim_factor', 'threshold', 'node_intense_threshold', 'famine_coverage'):
        if _finite(document[key], key) <= 0:
            raise ValueError(f'weights {key} must be positive')
    for fact in document['gainable_features']:
        if not known_fact(fact):
            raise ValueError(f'weights names an unknown gainable fact {fact!r}')
    if type(document['max_threads_per_act']) is not int or document['max_threads_per_act'] < 1:
        raise ValueError('weights max_threads_per_act must be a positive integer')
    if type(document['initiative_days']) is not int or document['initiative_days'] < 1:
        raise ValueError('weights initiative_days must be a positive integer')
    return document
