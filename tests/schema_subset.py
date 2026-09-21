"""Standard-library validator for the JSON Schema subset the Contracts/ schemas use.

The repository baseline is Python 3.9 plus the standard library, so published
interchange documents cannot be checked with a third-party validator. This
covers exactly the keywords Contracts/schemas/*.json rely on; an unsupported
keyword raises instead of passing silently, so the checker cannot drift into
accepting a contract it never inspected.
"""

from __future__ import annotations

import re

SUPPORTED = frozenset((
    '$schema', '$id', '$defs', '$ref', 'title', 'description',
    'type', 'properties', 'required', 'additionalProperties', 'items',
    'const', 'enum', 'pattern', 'minimum', 'maximum', 'exclusiveMinimum',
    'minItems', 'maxItems', 'minLength', 'maxLength', 'not',
    # Annotations. They constrain nothing and this validator ignores them, but they must
    # be listed or the unknown-keyword guard above rejects the schema that carries one.
    # `liveness` maps each token of a person-level `status` enum to `present` or `gone`;
    # it is the cross-block translation that lived only in Python until 2026-09-21, and
    # tests/test_status_vocabulary.py checks it against Sim/icarus_sim/terrain_liveness.py.
    'liveness',
))

TYPES = {
    'object': dict, 'array': list, 'string': str, 'boolean': bool,
    'number': (int, float), 'integer': int, 'null': type(None),
}


def _kind(value, name):
    if name == 'boolean':
        return type(value) is bool
    if name in ('number', 'integer') and type(value) is bool:
        return False  # JSON booleans are not numbers even though Python bools are ints.
    return isinstance(value, TYPES[name])


def _resolve(schema, root):
    seen = set()
    while '$ref' in schema:
        ref = schema['$ref']
        if ref in seen:
            raise ValueError('circular $ref: ' + ref)
        seen.add(ref)
        if not ref.startswith('#/'):
            raise ValueError('only local $ref is supported: ' + ref)
        target = root
        for part in ref[2:].split('/'):
            target = target[part.replace('~1', '/').replace('~0', '~')]
        schema = target
    return schema


def errors(value, schema, root=None, path=''):
    """Yield '<json path>: <reason>' for every violation, deepest constraint first."""
    root = schema if root is None else root
    schema = _resolve(schema, root)
    unknown = set(schema) - SUPPORTED
    if unknown:
        raise ValueError(f'unsupported schema keywords at {path or "<root>"}: {sorted(unknown)}')

    if 'type' in schema:
        names = schema['type'] if isinstance(schema['type'], list) else [schema['type']]
        if not any(_kind(value, name) for name in names):
            yield f'{path or "<root>"}: expected type {"/".join(names)}, found {type(value).__name__}'
            return
    if 'const' in schema and value != schema['const']:
        yield f'{path or "<root>"}: expected {schema["const"]!r}, found {value!r}'
    if 'enum' in schema and value not in schema['enum']:
        yield f'{path or "<root>"}: {value!r} is not one of {schema["enum"]!r}'
    if 'not' in schema and not any(errors(value, schema['not'], root, path)):
        yield f'{path or "<root>"}: {value!r} must not satisfy the excluded schema'
    if isinstance(value, str):
        if 'pattern' in schema and not re.search(schema['pattern'], value):
            yield f'{path}: {value!r} does not match /{schema["pattern"]}/'
        if 'minLength' in schema and len(value) < schema['minLength']:
            yield f'{path}: {len(value)} characters is below minLength {schema["minLength"]}'
        if 'maxLength' in schema and len(value) > schema['maxLength']:
            yield f'{path}: {len(value)} characters is above maxLength {schema["maxLength"]}'
    if isinstance(value, (int, float)) and type(value) is not bool:
        if 'minimum' in schema and value < schema['minimum']:
            yield f'{path}: {value} is below minimum {schema["minimum"]}'
        if 'maximum' in schema and value > schema['maximum']:
            yield f'{path}: {value} is above maximum {schema["maximum"]}'
        if 'exclusiveMinimum' in schema and value <= schema['exclusiveMinimum']:
            yield f'{path}: {value} is not above {schema["exclusiveMinimum"]}'
    if isinstance(value, dict):
        for name in schema.get('required', ()):
            if name not in value:
                yield f'{path or "<root>"}: missing required property {name!r}'
        properties = schema.get('properties', {})
        if schema.get('additionalProperties') is False:
            for name in sorted(set(value) - set(properties)):
                yield f'{path or "<root>"}: unexpected property {name!r}'
        for name, item in properties.items():
            if name in value:
                yield from errors(value[name], item, root, f'{path}/{name}')
    if isinstance(value, list):
        if 'minItems' in schema and len(value) < schema['minItems']:
            yield f'{path}: {len(value)} items is below minItems {schema["minItems"]}'
        if 'maxItems' in schema and len(value) > schema['maxItems']:
            yield f'{path}: {len(value)} items is above maxItems {schema["maxItems"]}'
        if 'items' in schema:
            for index, item in enumerate(value):
                yield from errors(item, schema['items'], root, f'{path}/{index}')


def validate(value, schema, limit=25):
    found = []
    for message in errors(value, schema):
        found.append(message)
        if len(found) >= limit:
            found.append('... additional errors suppressed')
            break
    if found:
        raise ValueError('document does not satisfy the schema:\n  ' + '\n  '.join(found))
