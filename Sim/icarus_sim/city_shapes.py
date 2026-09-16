"""Research-backed shape selection for a future city-footprint planner.

This module selects a pattern and parameters; it does not generate coordinates.
"""
import copy
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path

CATALOGUE_PATH = Path(__file__).with_name('city_shapes.json')


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def _check_rule(rule, features):
    if not isinstance(rule, dict) or rule.get('field') not in features:
        raise ValueError('Unknown shape-rule field')
    if set(rule) - {'field', 'min', 'max', 'equals'} or len(rule) < 2:
        raise ValueError('Invalid shape rule')
    boolean = features[rule['field']]['type'] == 'boolean'
    if boolean:
        if set(rule) != {'field', 'equals'} or type(rule['equals']) is not bool:
            raise ValueError('Boolean rule requires explicit boolean equality')
    else:
        for key in set(rule) - {'field'}:
            if not _number(rule[key]): raise ValueError('Nonfinite shape-rule value')
        if rule.get('min', -math.inf) > rule.get('max', math.inf):
            raise ValueError('Reversed shape-rule range')


def validate_catalogue(data):
    try:
        if data['schema'] != 'fantasy-world-generator.city-shapes' or type(data['schema_version']) is not int or data['schema_version'] != 1:
            raise ValueError('Unsupported city-shape schema')
        if type(data['revision']) is not int or data['revision'] < 1:
            raise ValueError('Invalid city-shape revision')
        features = data['site_features']
        for definition in features.values():
            if definition['type'] not in ('boolean', 'number'): raise ValueError('Invalid feature type')
            if definition['type'] == 'number':
                if not all(_number(definition[k]) for k in ('min', 'max')) or definition['min'] > definition['max']:
                    raise ValueError('Invalid feature range')
        selection = data['selection']
        if selection['algorithm'] != 'sha256_weighted_v1': raise ValueError('Unsupported selection algorithm')
        if not selection['required_site_fields'] or not set(selection['required_site_fields']) <= set(features):
            raise ValueError('Unknown required feature')
        if not _number(selection['repetition_penalty']) or selection['repetition_penalty'] < 0:
            raise ValueError('Invalid repetition penalty')
        for source in data['sources'].values():
            if not source['url'].startswith('https://') or not source['supports']:
                raise ValueError('Missing research attribution')
        seen = set()
        if not data['shapes']: raise ValueError('Empty shape catalogue')
        for shape in data['shapes']:
            if not isinstance(shape['id'], str) or not shape['id'] or shape['id'] in seen:
                raise ValueError('Duplicate or invalid shape ID')
            seen.add(shape['id'])
            if type(shape['enabled_by_default']) is not bool: raise ValueError('Invalid default flag')
            if not shape['city_classes'] or not set(shape['city_classes']) <= {'small', 'medium', 'capital'}:
                raise ValueError('Invalid city class')
            if not _number(shape['base_weight']) or not 0 < shape['base_weight'] <= 1000:
                raise ValueError('Invalid shape weight')
            if not shape['history']['source_ids'] or not set(shape['history']['source_ids']) <= set(data['sources']):
                raise ValueError('Unknown historical source')
            if set(shape['eligibility']) != {'all'}: raise ValueError('Invalid eligibility expression')
            for rule in shape['eligibility']['all']: _check_rule(rule, features)
            for preference in shape['preferences']:
                _check_rule(preference['when'], features)
                if not _number(preference['bonus']) or not 0 <= preference['bonus'] <= 1000:
                    raise ValueError('Invalid preference weight')
            for parameter in shape['variation'].values():
                if not all(_number(parameter[k]) for k in ('min', 'max')) or parameter['min'] > parameter['max']:
                    raise ValueError('Invalid variation range')
                if type(parameter.get('integer', False)) is not bool: raise ValueError('Invalid integer flag')
                if parameter.get('integer') and any(type(parameter[k]) is not int for k in ('min', 'max')):
                    raise ValueError('Integer variation needs integer endpoints')
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError('Malformed city-shape catalogue: ' + str(exc)) from exc
    return data


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result: raise ValueError('Duplicate city-shape JSON key')
        result[key] = value
    return result


@lru_cache(maxsize=4)
def _read(path, mtime, size):
    return validate_catalogue(json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=_unique))


def load_catalogue():
    stat = CATALOGUE_PATH.stat()
    return copy.deepcopy(_read(str(CATALOGUE_PATH.resolve()), stat.st_mtime_ns, stat.st_size))


def _matches(rule, site):
    if rule['field'] not in site: return False
    value = site[rule['field']]
    return (('equals' not in rule or value == rule['equals'])
            and ('min' not in rule or value >= rule['min'])
            and ('max' not in rule or value <= rule['max']))


def _rank(data, site, city_class, nearby_counts, include_later):
    if not isinstance(site, dict) or not set(data['selection']['required_site_fields']) <= set(site):
        raise ValueError('Missing required footprint location data')
    if city_class not in ('small', 'medium', 'capital') or type(include_later) is not bool:
        raise ValueError('Invalid city class or period option')
    for key, value in site.items():
        if key not in data['site_features']: raise ValueError('Unknown site feature: ' + str(key))
        definition = data['site_features'][key]
        if definition['type'] == 'boolean':
            if type(value) is not bool: raise ValueError('Expected boolean site feature')
        elif not _number(value) or not definition['min'] <= value <= definition['max']:
            raise ValueError('Out-of-range site feature')
    ids = {s['id'] for s in data['shapes']}
    counts = {} if nearby_counts is None else nearby_counts
    if not isinstance(counts, dict) or any(k not in ids or type(v) is not int or not 0 <= v <= 10000 for k, v in counts.items()):
        raise ValueError('Invalid nearby shape counts')
    ranked = []
    for shape in sorted(data['shapes'], key=lambda s: s['id']):
        if not shape['enabled_by_default'] and not include_later: continue
        if city_class not in shape['city_classes']: continue
        if not all(_matches(rule, site) for rule in shape['eligibility']['all']): continue
        matched = [p for p in shape['preferences'] if _matches(p['when'], site)]
        weight = (shape['base_weight'] + sum(p['bonus'] for p in matched)) / (1 + counts.get(shape['id'], 0) * data['selection']['repetition_penalty'])
        ranked.append({'id': shape['id'], 'family': shape['family'], 'weight': weight,
                       'matched_preferences': [p['when']['field'] for p in matched]})
    return ranked


def rank_shapes(site, city_class='medium', nearby_counts=None, include_later=False):
    """Return eligible weighted alternatives in stable ID order, not a forced winner."""
    return _rank(load_catalogue(), site, city_class, nearby_counts, include_later)


def select_shape(site, seed, city_id, city_class='medium', nearby_counts=None, include_later=False):
    if type(seed) is not int or not isinstance(city_id, str) or not 1 <= len(city_id) <= 256:
        raise ValueError('Expected an integer seed and stable nonempty city ID')
    data = load_catalogue()
    identity = hashlib.sha256(json.dumps(data, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    candidates = _rank(data, site, city_class, nearby_counts, include_later)
    result = {'version': 1, 'catalogue_revision': data['revision'], 'catalogue_sha256': identity,
              'shape_id': None, 'parameters': {}, 'candidates': candidates, 'runtime_geometry_generated': False}
    if not candidates:
        result['reason'] = 'No compatible shape; change site or provide missing location facts.'
        return result
    def unit(label):
        payload = json.dumps([seed, city_id, identity, label], separators=(',', ':')).encode()
        return int.from_bytes(hashlib.sha256(payload).digest()[:8], 'big') / 2**64
    target = unit('shape') * sum(row['weight'] for row in candidates)
    chosen = candidates[-1]
    for row in candidates:
        target -= row['weight']
        if target < 0:
            chosen = row
            break
    shape = next(s for s in data['shapes'] if s['id'] == chosen['id'])
    parameters = {}
    for key, interval in sorted(shape['variation'].items()):
        low, high = interval['min'], interval['max']
        u = unit(shape['id'] + ':' + key)
        parameters[key] = min(high, low + int(u * (high-low+1))) if interval.get('integer') else round(low + u * (high-low), 6)
    result.update(shape_id=shape['id'], parameters=parameters, layout=shape['layout'],
                  source_ids=shape['history']['source_ids'], reason='Seeded weighted choice among compatible shapes.')
    return result
