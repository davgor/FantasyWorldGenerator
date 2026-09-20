"""The packaged archetype catalogue, and the lint that stops a half-authored one shipping.

Archetypes are data so the world can gain a kind of place without a code change. The cost
of that is that a typo in the catalogue would otherwise surface as a silently missing
archetype in a generated world, months later; :func:`lint` turns it into a loud failure at
load. Every rule here exists because breaking it produces a world that looks fine.
"""
from importlib.resources import files
import json

CATALOGUE = 'catalogue.json'
TIERS = (0, 1, 2, 3)
DOMAINS = ('land', 'water', 'ocean', 'lake', 'any')
STATES = ('natural', 'active', 'occupied', 'abandoned', 'ruined', 'buried', 'drowned',
          'sealed', 'corrupted', 'reclaimed', 'restored')
OCCUPANTS = ('none', 'builders', 'descendants', 'squatters', 'monsters', 'cult', 'undead',
             'beasts', 'fae', 'nature')
INTERIOR_PLANS = ('linear', 'branching', 'radial', 'warren', 'vault')
REQUIRED = {'id', 'name', 'family', 'tier', 'domain', 'prefers', 'states', 'occupants', 'names', 'reason'}
TERM_KEYS = {'layer', 'min', 'max', 'equals', 'not_equals', 'in', 'above_percentile', 'below_percentile'}
PREFER_KEYS = {'layer', 'weight', 'invert'}
PLACEMENTS = ('node', 'path', 'cluster')
ALONG = ('road', 'frontier', 'approach')


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError(f'duplicate catalogue key {key!r}')
        result[key] = value
    return result


def _reject(token):
    raise ValueError(f'non-finite catalogue number {token}')


def load():
    text = files('key_locations').joinpath(CATALOGUE).read_text(encoding='utf-8')
    document = json.loads(text, object_pairs_hook=_pairs, parse_constant=_reject)
    return lint(document)


def _lint_weights(archetype, key, allowed):
    weights = archetype[key]
    if not weights:
        raise ValueError(f'archetype {archetype["id"]!r} needs at least one {key[:-1]}')
    for name, weight in weights.items():
        if name not in allowed:
            raise ValueError(f'archetype {archetype["id"]!r} names unknown {key[:-1]} {name!r}')
        if not isinstance(weight, (int, float)) or weight <= 0:
            raise ValueError(f'archetype {archetype["id"]!r} gives {name!r} a non-positive weight')


def lint(document):
    """Every archetype is complete and internally consistent, or nothing loads."""
    if document.get('schema') != 'fantasy-world-generator.key-locations-catalogue':
        raise ValueError('not a key-locations catalogue')
    if type(document.get('revision')) is not int or document['revision'] < 1:
        raise ValueError('catalogue needs a positive integer revision')
    families = document['families']
    seen = set()
    for archetype in document['archetypes']:
        missing = REQUIRED - set(archetype)
        if missing:
            raise ValueError(f'archetype {archetype.get("id")!r} is missing {sorted(missing)}')
        if archetype['id'] in seen:
            raise ValueError(f'duplicate archetype {archetype["id"]!r}')
        seen.add(archetype['id'])
        if archetype['family'] not in families:
            raise ValueError(f'archetype {archetype["id"]!r} names unknown family {archetype["family"]!r}')
        if archetype['tier'] not in TIERS:
            raise ValueError(f'archetype {archetype["id"]!r} has tier {archetype["tier"]!r}, expected one of {TIERS}')
        if archetype['domain'] not in DOMAINS:
            raise ValueError(f'archetype {archetype["id"]!r} has unknown domain {archetype["domain"]!r}')
        if archetype.get('placement', 'node') not in PLACEMENTS:
            raise ValueError(f'archetype {archetype["id"]!r} has unknown placement {archetype["placement"]!r}')
        if archetype.get('placement', 'node') == 'node':
            rate = archetype.get('per_1000_km2')
            if not isinstance(rate, (int, float)) or rate <= 0:
                # A rate of zero is the silent form of "never", and it does not look like
                # one. The five tier-3 wonders declared `per_1000_km2: 0.0` beside
                # `max_count: 1`, which reads as "at most one of these in a world" and
                # means "none, in any world, ever" - `budget` multiplies the rate by land
                # area, and zero times any area is zero at every raster and every seed.
                # They reported `wanted: 0` against 15 to 78 qualifying cells and nobody
                # saw it, because a missing archetype looks exactly like an unlucky one.
                # A composed archetype is exempt: a waystone's count comes from the length
                # of its road, so a rate would be the meaningless number here.
                raise ValueError(f'archetype {archetype["id"]!r} is placed by scatter and needs a positive '
                                 f'per_1000_km2 rate, not {rate!r}; a zero rate places it in no world ever')
        for term in archetype.get('requires', []):
            unknown = set(term) - TERM_KEYS
            if unknown or 'layer' not in term:
                raise ValueError(f'archetype {archetype["id"]!r} has a malformed requires term {term}')
            if len(set(term) - {'layer'}) == 0:
                raise ValueError(f'archetype {archetype["id"]!r} requires {term["layer"]!r} without a condition')
        for term in archetype['prefers']:
            unknown = set(term) - PREFER_KEYS
            if unknown or 'layer' not in term:
                raise ValueError(f'archetype {archetype["id"]!r} has a malformed prefers term {term}')
        _lint_weights(archetype, 'states', STATES)
        _lint_weights(archetype, 'occupants', OCCUPANTS)
        if not archetype['names'] or not archetype['reason']:
            raise ValueError(f'archetype {archetype["id"]!r} needs name templates and a reason')
        interior = archetype.get('interior')
        if interior is not None:
            if interior.get('plan') not in INTERIOR_PLANS:
                raise ValueError(f'archetype {archetype["id"]!r} has unknown interior plan {interior.get("plan")!r}')
            for key in ('levels', 'chambers'):
                span = interior.get(key)
                if not (isinstance(span, list) and len(span) == 2 and 0 < span[0] <= span[1]):
                    raise ValueError(f'archetype {archetype["id"]!r} has a malformed interior {key} {span}')
        if archetype['tier'] == 2 and interior is None:
            raise ValueError(f'archetype {archetype["id"]!r} is tier 2 and must declare an interior')
        if archetype['tier'] == 0 and interior is not None:
            raise ValueError(f'archetype {archetype["id"]!r} is a tier 0 marker and cannot have an interior')
    _lint_succession(document, families)
    _lint_composition(document, seen)
    return document


def _lint_composition(document, archetype_ids):
    """Chains and clusters name real archetypes, and those archetypes expect to be composed.

    The sharp one is the last check. An archetype left at the default ``placement: node`` is
    also placed by the scatter pass, so a waystone would be both strung along its road and
    dropped on whichever cell scored best - the same kind of place arriving by two routes that
    know nothing about each other.
    """
    for spec in document.get('chains', []):
        for key in ('id', 'name', 'archetype', 'along', 'interval_m', 'reason'):
            if key not in spec:
                raise ValueError(f'chain {spec.get("id")!r} is missing {key}')
        if spec['archetype'] not in archetype_ids:
            raise ValueError(f'chain {spec["id"]!r} names unknown archetype {spec["archetype"]!r}')
        if spec['along'] not in ALONG:
            raise ValueError(f'chain {spec["id"]!r} walks unknown thing {spec["along"]!r}; expected {ALONG}')
        if not isinstance(spec['interval_m'], (int, float)) or spec['interval_m'] <= 0:
            raise ValueError(f'chain {spec["id"]!r} needs a positive interval_m')
        if spec['along'] == 'approach' and not spec.get('anchor_family'):
            raise ValueError(f'chain {spec["id"]!r} walks an approach without saying to what')
    for spec in document.get('clusters', []):
        for key in ('id', 'name', 'archetype', 'count', 'offset_m', 'reason'):
            if key not in spec:
                raise ValueError(f'cluster {spec.get("id")!r} is missing {key}')
        if spec['archetype'] not in archetype_ids:
            raise ValueError(f'cluster {spec["id"]!r} names unknown archetype {spec["archetype"]!r}')
        if not (spec.get('anchor_kinds') or spec.get('anchor_families')):
            raise ValueError(f'cluster {spec["id"]!r} needs something to hang off')
        for key in ('count', 'offset_m'):
            span = spec[key]
            if not (isinstance(span, list) and len(span) == 2 and 0 < span[0] <= span[1]):
                raise ValueError(f'cluster {spec["id"]!r} has a malformed {key} {span}')
        for kind in spec.get('anchor_kinds', ()):
            if kind not in archetype_ids:
                raise ValueError(f'cluster {spec["id"]!r} anchors on unknown archetype {kind!r}')
    composed = {s['archetype'] for s in document.get('chains', []) + document.get('clusters', [])}
    for archetype in document['archetypes']:
        if archetype['id'] in composed and archetype.get('placement', 'node') == 'node'                 and not archetype.get('also_scatters'):
            raise ValueError(
                f'archetype {archetype["id"]!r} is composed but also scatters by default. Some kinds '
                f'genuinely do both - a barrow stands alone and also rings a necropolis - but a '
                f'waystone arriving both along its road and on whichever cell scored best is an '
                f'accident. Set placement to path or cluster, or declare also_scatters.')


def _lint_succession(document, families):
    """Succession rules name real families and real occupants, with a usable chance."""
    for family, rule in document.get('succession', {}).items():
        if family == 'note':
            continue
        if family not in families:
            raise ValueError(f'succession names unknown family {family!r}')
        chance = rule.get('chance')
        if not isinstance(chance, (int, float)) or not 0. <= chance <= 1.:
            raise ValueError(f'succession for {family!r} needs a chance in [0, 1]')
        occupants = rule.get('occupants') or {}
        if not occupants:
            raise ValueError(f'succession for {family!r} needs at least one occupant')
        for name, weight in occupants.items():
            if name not in OCCUPANTS:
                raise ValueError(f'succession for {family!r} names unknown occupant {name!r}')
            if not isinstance(weight, (int, float)) or weight <= 0:
                raise ValueError(f'succession for {family!r} gives {name!r} a non-positive weight')


def by_family(document):
    result = {}
    for archetype in document['archetypes']:
        result.setdefault(archetype['family'], []).append(archetype)
    return result
