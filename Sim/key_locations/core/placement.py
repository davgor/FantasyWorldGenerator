"""Choosing ground: which cells an archetype may stand on, and which ones it takes.

An archetype declares the layers it needs (``requires``), the layers that make one cell
better than another (``prefers``), how many of itself belong in a thousand square
kilometres of land, and how far apart two of them must be. Everything else — state,
occupant, name, interior — is decided later from what the world already recorded.

Two properties this module exists to guarantee:

* **A world without the ground gets none of the archetype.** A ``requires`` term naming a
  layer the world never generated, or one no cell satisfies, yields an empty list and a
  diagnostic — not a fallback placement somewhere approximate.
* **Replay is exact.** Candidates are sorted on ``(-jittered score, node)``, never on a set
  or dict iteration order, and every draw comes from the caller's seeded generator.

Pure: no filesystem, no network, no engine, no generator imports.
"""
from .grid import great_circle_m

DEFAULT_SCORE = .5
JITTER = .35


def _value(layers, name, x, z):
    grid = layers.get(name)
    return None if grid is None else grid[z][x]


def normalisers(layers, names, cells):
    """Per-layer ``(low, high)`` over land, so metres and unit fractions score comparably.

    A layer that is flat across the whole world gets an empty range and is scored as neutral
    rather than dividing by zero — a constant field carries no information about where to
    put anything.
    """
    result = {}
    for name in sorted(names):
        grid = layers.get(name)
        if grid is None:
            continue
        values = [grid[c['z']][c['x']] for c in cells]
        if not values:
            continue
        low, high = min(values), max(values)
        result[name] = (low, high) if high > low else None
    return result


def _normalised(layers, norms, name, x, z, invert=False):
    span = norms.get(name)
    if span is None:
        return DEFAULT_SCORE
    raw = _value(layers, name, x, z)
    if raw is None:
        return DEFAULT_SCORE
    low, high = span
    unit = (raw - low) / (high - low)
    unit = max(0., min(1., unit))
    return 1. - unit if invert else unit


def satisfies(term, layers, x, z):
    """One ``requires`` term against one cell. An absent layer never satisfies anything."""
    raw = _value(layers, term['layer'], x, z)
    if raw is None:
        return False
    if 'min' in term and raw < term['min']:
        return False
    if 'max' in term and raw > term['max']:
        return False
    if 'equals' in term and raw != term['equals']:
        return False
    if 'not_equals' in term and raw == term['not_equals']:
        return False
    if 'in' in term and raw not in term['in']:
        return False
    return True


def percentile(values, q):
    """The value at quantile ``q`` of ``values``; nearest-rank, so it is always a real sample."""
    ordered = sorted(values)
    index = int(round(q * (len(ordered) - 1)))
    return ordered[max(0, min(len(ordered) - 1, index))]


def resolve(archetype, layers, cells):
    """Turn percentile requirements into absolute ones against this world's own distribution.

    An archetype cannot name absolute thresholds and stay honest: ``volcanic >= 0.35`` means
    something different on every world, and on a quiet one it silently means *never*. Asking
    instead for the top eight per cent of volcanism travels between worlds. The absolute
    ``min`` alongside is the floor that stops "the most volcanic ground on a world with no
    volcanism" from qualifying — percentile picks the best available, the floor decides
    whether the best available is good enough at all.

    Returns ``None`` when the world cannot serve the archetype, which callers report as a
    diagnostic rather than approximating around.
    """
    resolved = []
    for term in archetype.get('requires', []):
        grid = layers.get(term['layer'])
        if grid is None:
            return None
        rule = dict(term)
        if 'above_percentile' in term or 'below_percentile' in term:
            values = [grid[c['z']][c['x']] for c in cells]
            if not values:
                return None
            if 'above_percentile' in term:
                cut = percentile(values, term['above_percentile'])
                rule['min'] = max(cut, term['min']) if 'min' in term else cut
            if 'below_percentile' in term:
                cut = percentile(values, term['below_percentile'])
                rule['max'] = min(cut, term['max']) if 'max' in term else cut
            rule.pop('above_percentile', None)
            rule.pop('below_percentile', None)
        resolved.append(rule)
    return resolved


def eligible(archetype, layers, cells):
    resolved = resolve(archetype, layers, cells)
    if resolved is None:
        return []
    return [c for c in cells if all(satisfies(term, layers, c['x'], c['z']) for term in resolved)]


def score(archetype, layers, norms, x, z):
    """Weighted mean of the archetype's preference terms; ``(score, factors)``."""
    prefers = archetype.get('prefers', [])
    if not prefers:
        return DEFAULT_SCORE, {}
    factors, total, weighted = {}, 0., 0.
    for term in prefers:
        unit = _normalised(layers, norms, term['layer'], x, z, term.get('invert', False))
        weight = float(term.get('weight', 1.))
        key = term['layer'] + ('_low' if term.get('invert') else '')
        factors[key] = round(unit, 4)
        weighted += unit * weight
        total += weight
    return (weighted / total if total else DEFAULT_SCORE), factors


def budget(archetype, land_km2, draw, density=1.):
    """How many of this archetype the world's land supports, as a thinned draw.

    The expected count is ``per_1000_km2`` scaled by land area. Rounding that to the nearest
    integer looks harmless and is not: on a small world every archetype's expectation falls
    below a half and the whole catalogue rounds to zero at once, so the world reports
    "too small to support one" ninety times and grows nothing. The legacy 11 km reference
    world the lab builds by default has about six square kilometres of land and does exactly
    that.

    So take the floor and draw for the remainder, which is the same thinned point process
    ``terrain_nests`` uses for creature anchors: a fractional expectation becomes a
    proportional chance rather than a silent zero. A tiny island then grows one or two
    notable places instead of none, and a continent is unaffected.
    """
    per = float(archetype.get('per_1000_km2', 0.))
    expected = per * land_km2 / 1000. * float(archetype.get('occurrence', 1.)) * density
    whole = int(expected)
    count = whole + (1 if draw.random() < expected - whole else 0)
    floor, ceiling = archetype.get('min_count'), archetype.get('max_count')
    if floor is not None:
        count = max(count, int(floor))
    if ceiling is not None:
        count = min(count, int(ceiling))
    return max(0, count)


def _clear(point, taken, radius, minimum):
    return all(great_circle_m(point, other, radius) >= minimum for other in taken)


def select(archetype, layers, cells, norms, radius, draw, wanted, settled=(), claimed=frozenset(), family_taken=()):
    """Thin the eligible cells down to ``wanted`` placements that respect every spacing rule.

    Greedy over jittered score. The jitter matters: pure greed clusters every site on the
    single best ridge and the map reads as a gradient rather than a world, while pure random
    ignores the suitability field the archetype just declared.
    """
    if wanted <= 0:
        return []
    spacing = float(archetype.get('spacing_m', 0.))
    clearance = float(archetype.get('settlement_clearance_m', 0.))
    family_spacing = float(archetype.get('family_spacing_m', 0.))
    ranked = []
    for candidate in cells:
        if candidate['node'] in claimed:
            continue
        value, factors = score(archetype, layers, norms, candidate['x'], candidate['z'])
        jittered = value * (1. - JITTER + 2. * JITTER * draw.random())
        ranked.append((-jittered, candidate['node'], candidate, value, factors))
    ranked.sort(key=lambda row: (row[0], row[1]))
    taken, placed = list(family_taken), []
    own = []
    for _, _, candidate, value, factors in ranked:
        if len(placed) >= wanted:
            break
        point = candidate['direction']
        if clearance and not _clear(point, settled, radius, clearance):
            continue
        if spacing and not _clear(point, own, radius, spacing):
            continue
        if family_spacing and not _clear(point, taken, radius, family_spacing):
            continue
        own.append(point)
        taken.append(point)
        placed.append({'cell': candidate, 'suitability': round(value, 4), 'suitability_factors': factors})
    return placed
