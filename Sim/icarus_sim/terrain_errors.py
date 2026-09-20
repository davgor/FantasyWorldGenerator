"""Machine-readable refusals for the request boundary.

The caller is a local model packaged inside the game. When a request is refused it has to
decide what to send next with no one to ask, so a refusal carries the field, the value it
sent, the bound or choice list it violated, and where available a value that would work.

Same envelope the native core already emits (`Core/wire.cpp` `failure_json`), extended to
schema version 2. Version 1 keeps its exact shape: `Sim/fantasy_world_generator/
kernel_contract.KernelError` and the counter proof still emit it and are untouched.

`RequestError` subclasses `ValueError` for the same reason `KernelError` does: every
existing handler at the CLI, the lab server and the leaf packages already catches
`ValueError`, so adopting this changes nothing for them while adding a document for the
callers that want one.

**The detail tier is switchable on purpose.** `document(detail=False)` emits only the core
five fields. Whether `suggestion` actually reduces a small model's retry count is an
empirical question, and the evaluation harness has to be able to turn it off to measure it.
A field that cannot be switched off cannot be measured.

Codes come from the enum already declared in `Contracts/schemas/counter-kernel.schema.json`
and are not widened. Every refusal at this boundary is one of three: a malformed or
out-of-range input, a retired version, or a request past a hard capacity bound.
"""

import difflib
import math

SCHEMA = 'fantasy-world-generator.failure'
SCHEMA_VERSION = 2

INVALID_INPUT = 'INVALID_INPUT'
UNSUPPORTED_VERSION = 'UNSUPPORTED_VERSION'
STATE_CAPACITY = 'STATE_CAPACITY'

# `kind` values a caller may branch on without reading prose.
CLAMP = 'clamp'
CHOOSE = 'choose'
DID_YOU_MEAN = 'did_you_mean'
NONE = 'none'


class RequestError(ValueError):
    """A refused request, with everything needed to build a better one."""

    def __init__(self, code, message, *, field=None, received=None, expected=None,
                 suggestion=None, retry=True):
        self.code = code
        self.field = field
        self.received = received
        self.expected = expected
        self.suggestion = suggestion
        self.retry = retry
        super().__init__(message)

    def document(self, detail=True):
        """The envelope. `detail=False` drops everything a v1 consumer cannot read."""
        body = {'schema': SCHEMA, 'schema_version': SCHEMA_VERSION,
                'code': self.code, 'message': str(self), 'field': self.field}
        if not detail:
            return body
        body['received'] = self.received
        body['expected'] = self.expected
        body['suggestion'] = self.suggestion or {'kind': NONE}
        body['retry'] = self.retry
        return body


def nearest(name, candidates):
    """Names a caller plausibly meant, best first.

    `difflib` alone is good on a typo and poor on a bare prefix -- `rain` scores closer to
    `radius` than to `rain_passes`, because it is shorter. So prefix and substring matches
    are folded in ahead of it rather than after, which is the case an LLM actually produces
    when it guesses a control name from a group it half-remembers.
    """
    if not isinstance(name, str):
        return []
    pool = sorted(candidates)
    lowered = name.casefold()
    prefixed = [k for k in pool if k.casefold().startswith(lowered)]
    contained = [k for k in pool if lowered in k.casefold() and k not in prefixed]
    close = [k for k in difflib.get_close_matches(name, pool, n=5, cutoff=0.6)
             if k not in prefixed and k not in contained]
    return (prefixed + contained + close)[:5]


def unknown_field(name, candidates, *, noun='control'):
    """A name that is not in the vocabulary, with what the caller probably meant."""
    guesses = nearest(name, candidates)
    message = 'No %s named %r.' % (noun, name)
    if guesses:
        message += ' Did you mean %s?' % ', '.join(repr(g) for g in guesses)
    elif noun == 'control':
        message += ' Call describe_controls to list what exists.'
    else:
        # Only controls have a discovery call. Pointing a caller at describe_controls for a
        # request field or a god id sends it somewhere that cannot answer.
        known = sorted(candidates)
        message += (' Known %ss: %s.' % (noun, ', '.join(repr(k) for k in known[:8]))
                    if known else ' Nothing of that kind exists in this world.')
    return RequestError(INVALID_INPUT, message, field=name, received=None,
                        expected={'kind': 'one_of_catalogue', 'candidates': guesses},
                        suggestion={'kind': DID_YOU_MEAN, 'candidates': guesses} if guesses
                        else {'kind': NONE})


def out_of_range(name, value, definition):
    """A value outside a declared bound, with the nearest value that is inside it."""
    low, high = definition.get('min'), definition.get('max')
    kind = definition.get('type')
    clamped = value
    if isinstance(value, (int, float)) and math.isfinite(value):
        if low is not None:
            clamped = max(clamped, low)
        if high is not None:
            clamped = min(clamped, high)
        if kind == 'integer':
            clamped = int(round(clamped))
    units = definition.get('units') or ''
    # 'seed must be 0..4294967295 seed' reads as a stutter. A unit that merely repeats the
    # field name carries nothing, so drop it from the sentence and keep it in `expected`.
    spoken = '' if units and units in name.split('_') else units
    message = '%s must be %s..%s%s; received %r.' % (
        name, low, high, ' ' + spoken if spoken else '', value)
    if low is not None and low == high:
        message = ('%s is pinned at %s and rejects every other value; received %r.'
                   % (name, low, value))
        return RequestError(INVALID_INPUT, message, field=name, received=value,
                            expected={'type': kind, 'min': low, 'max': high, 'pinned': True},
                            suggestion={'kind': NONE})
    return RequestError(INVALID_INPUT, message, field=name, received=value,
                        expected={'type': kind, 'min': low, 'max': high, 'units': units or None},
                        suggestion={'kind': CLAMP, 'value': clamped})


def wrong_type(name, value, definition):
    """A value of the wrong kind, saying which kind is wanted."""
    kind = definition.get('type')
    article = 'an integer' if kind == 'integer' else 'text' if kind == 'string' else 'a finite number'
    return RequestError(INVALID_INPUT,
                        '%s must be %s; received %r.' % (name, article, value),
                        field=name, received=value, expected={'type': kind},
                        suggestion={'kind': NONE})


def invalid_choice(name, value, definition):
    """A value outside a closed vocabulary, listing the vocabulary."""
    choices = list(definition.get('choices') or ())
    guesses = nearest(value, choices) if isinstance(value, str) else []
    message = '%s must be one of %s; received %r.' % (
        name, ', '.join(repr(c) for c in choices), value)
    return RequestError(INVALID_INPUT, message, field=name, received=value,
                        expected={'type': 'string', 'choices': choices},
                        suggestion={'kind': CHOOSE, 'value': guesses[0], 'candidates': guesses}
                        if guesses else {'kind': NONE})


def retired_version(field, value, supported):
    """A version this producer no longer accepts. Not retryable with a different value."""
    return RequestError(UNSUPPORTED_VERSION,
                        '%s %r is retired; this producer accepts %s. Regenerate rather than '
                        'migrating.' % (field, value, ', '.join(str(s) for s in supported)),
                        field=field, received=value,
                        expected={'choices': list(supported)},
                        suggestion={'kind': CHOOSE, 'value': supported[0],
                                    'candidates': list(supported)},
                        retry=False)


def over_capacity(field, value, limit, noun):
    """A request past a hard bound that is a cost ceiling rather than a validation range."""
    return RequestError(STATE_CAPACITY,
                        '%s %r is above the %s maximum of %s.' % (field, value, noun, limit),
                        field=field, received=value, expected={'max': limit},
                        suggestion={'kind': CLAMP, 'value': limit})


def unsupported_api(name, value, supported):
    """An api_version this producer does not implement. Not retryable with a value.

    Distinct from `retired_version`, which means the caller is holding a world this
    producer will not read. Here the world is fine and the caller is speaking the wrong
    protocol, so the remedy is a different client rather than a regenerated world.
    """
    return RequestError(UNSUPPORTED_VERSION,
                        '%s %r is not implemented; this producer speaks %s.'
                        % (name, value, ', '.join(str(s) for s in supported)),
                        field=name, received=value,
                        expected={'choices': list(supported)},
                        suggestion={'kind': CHOOSE, 'value': supported[0],
                                    'candidates': list(supported)},
                        retry=False)


def missing_block(block, message):
    """The world handed in does not carry something this call needs.

    Names the block rather than the request field, because the fix is to generate or
    advance the world far enough to have it, not to change an argument.
    """
    return RequestError(INVALID_INPUT, message, field='world.' + block, received=None,
                        expected={'requires_block': block},
                        suggestion={'kind': NONE}, retry=False)


def refused_by_world(field, value, reason, *, alternatives=None):
    """A well-formed request the world will not satisfy where it was asked.

    This is its own shape on purpose. Every other refusal here says the request was
    malformed, and the remedy is a better value. This one says the request was fine and the
    ground was wrong -- a band on water, a god sent to a sea tile, a node past the edge of
    the grid. A caller that cannot tell the two apart will keep correcting a value that was
    never the problem.
    """
    suggestion = {'kind': NONE}
    if alternatives:
        suggestion = {'kind': CHOOSE, 'value': alternatives[0],
                      'candidates': list(alternatives)[:5]}
    return RequestError(INVALID_INPUT, reason, field=field, received=value,
                        expected={'refused_by': 'world state'}, suggestion=suggestion)


def cross_field(message, fields, *, code=INVALID_INPUT):
    """A refusal no single field owns; names every field that took part."""
    return RequestError(code, message, field=None, received=None,
                        expected={'fields': list(fields)}, suggestion={'kind': NONE})
