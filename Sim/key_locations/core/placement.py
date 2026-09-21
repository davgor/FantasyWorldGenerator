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


def _percentile_rule(term, values):
    """The absolute rule a percentile term resolves to on this domain, and the cut it used.

    One statement of the arithmetic, read by both :func:`resolve` and :func:`gap`. The two
    used to describe the same resolution in their own words and that is how a diagnostic
    starts naming a different question from the one the gate asked.

    ``(rule, cut)``, where ``rule`` is the term with its percentile keys replaced by an
    absolute ``min`` or ``max`` that keeps whichever of the two is the stricter. Takes the
    domain's values rather than the grid so the caller reads each cell once.
    """
    rule = dict(term)
    cut = None
    if 'above_percentile' in term:
        cut = percentile(values, term['above_percentile'])
        rule['min'] = max(cut, term['min']) if 'min' in term else cut
    if 'below_percentile' in term:
        cut = percentile(values, term['below_percentile'])
        rule['max'] = min(cut, term['max']) if 'max' in term else cut
    rule.pop('above_percentile', None)
    rule.pop('below_percentile', None)
    return rule, cut


def _admits_everything(rule, layers, cells):
    """Whether every cell in the domain clears this resolved rule.

    Calls :func:`satisfies` rather than restating it. A near-miss reimplementation here would
    answer a slightly different question from the one ``eligible`` goes on to ask, and the
    gate would refuse a term that does discriminate or keep one that does not.
    """
    return all(satisfies(rule, layers, c['x'], c['z']) for c in cells)


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

    **A percentile over a field with no variation inside the domain resolves to nothing.**
    That rule is the asymmetry this function used to get wrong, and it is worth stating in
    full because the two halves fail in opposite directions. An absolute floor on an empty
    field admits no cell, so the archetype disappears and ``diagnostics`` says so — it fails
    *closed*, loudly. A percentile on an empty field computes a cut equal to the one value
    present, every cell clears it, and the gate silently admits the entire domain — it fails
    *open*, and reports ``"placed"``. Measured: ``holy_well`` asks for the nearest 35 per
    cent of ``freshwater_distance``, that layer reads a flat 0.0 on all 47 land cells of the
    size-17 reference world, and the archetype was eligible on all 47 — its defining
    requirement voided while the diagnostic claimed success. A closed failure costs a kind of
    place; an open one puts the place somewhere the archetype's own reason does not hold.

    ``normalisers`` above already draws this line for scoring — *"a constant field carries no
    information about where to put anything"* — so the test here is the same one, applied to
    the harder question of whether a cell may stand at all.

    **And zero variance is only the degenerate case of the real rule, which is about the
    outcome.** A field that varies can still resolve to a cut every cell clears, and then the
    gate admits the whole domain and reports ``placed`` exactly as a flat one did. Two ways
    in, both measured on generated worlds: *saturation*, where ``river`` read a flat 1.0 on
    land and every cell was a river; and *sparsity*, where it now reads zero on 246 of 268
    land cells at size 33 and a nearest-rank ``above_percentile 0.55`` cut over a field that
    is zero on 92 per cent of the domain lands **on** zero, so every cell clears it again.
    Zero variance, saturation and sparsity are three routes to one place.

    So the test is not *"does the field vary"* but *"does the resolved term separate the
    domain"*. A term that admits every cell selects nothing, and the archetype is refused.
    Measured on seed 42 at phase 16 on 2026-09-21: 14 archetypes at size 17, 18 at size 33 and
    **5 at size 65**. Most of the coarse-raster ones are ``settlement_distance`` collapsing on
    a world that is mostly settlement, which resolves by itself at 65; what does not resolve is
    ``river``, and ``bridge`` was placing five sites at 33 and six at 65 through a ``river``
    term that had stopped filtering — the wrong-content case rather than the absent-content
    one. This is what a percentile now means
    here: *the top N per cent, and it has to be a genuine top.* An absolute floor beside it is
    untouched and still rescues the term — the admission is tested against the resolved rule,
    floor included, which is precisely the job ``floor_rule`` gives a floor.

    An archetype declaring no ``requires`` at all is not touched by any of this. Chain and
    cluster furniture stands anywhere by declaration; this is a rule about a percentile that
    stopped discriminating, not about a wide gate.
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
            if min(values) == max(values):
                return None
            rule, _cut = _percentile_rule(term, values)
            if _admits_everything(rule, layers, cells):
                return None
        resolved.append(rule)
    return resolved


def gap(archetype, layers, cells):
    """Why this world cannot serve the archetype at all, or ``None`` when it can.

    Four different things make an archetype impossible and they point at four different
    people. A missing layer is a world generated to too early a phase. A field that is
    identically constant inside the archetype's own domain is a **catalogue** mistake — the
    archetype is asking a question its declared ground cannot answer, and no raster, seed or
    threshold will change that. Everything else is an ordinary world that happens not to have
    the ground this time. Collapsing them into *"no ground in this world satisfies the
    requirements"* sends someone looking at the world when the fault is in the catalogue.

    Measured on seed 42 at every size from 17 to 257: ``salinity`` is 0.0 on every land cell
    and 1.0 on every water cell, and ``fishing_productivity`` is 0.0 on every land cell. They
    are ocean quantities. Three ``domain: land`` archetypes gated on them, which is the shape
    this reason exists to name.

    A fourth was separated out afterwards and points somewhere else again: a field that
    *does* carry data, over which the percentile still resolves to a cut the whole domain
    clears. That is neither a missing layer nor a dead one; it is a distribution too piled up
    at one end for a nearest-rank cut to divide, and the person it points at is whoever tuned
    the field or the threshold. Saying *"carries no data"* for that case would send them to
    the wrong place, so it says how much of the domain the cut let through instead.
    """
    domain = archetype.get('domain')
    for term in archetype.get('requires', []):
        grid = layers.get(term['layer'])
        if grid is None:
            return f"the world never generated the {term['layer']} layer"
        values = [grid[c['z']][c['x']] for c in cells]
        if not values:
            return f"this world has no {domain} cells for it to stand on"
        if 'above_percentile' not in term and 'below_percentile' not in term:
            continue
        if min(values) == max(values):
            return (f"{term['layer']} is identically {min(values):g} across the {domain} domain, "
                    f"so a percentile over it selects nothing - the archetype names a field "
                    f"that carries no data where it is allowed to stand")
        rule, cut = _percentile_rule(term, values)
        if _admits_everything(rule, layers, cells):
            share = term.get('above_percentile', term.get('below_percentile'))
            return (f"{term['layer']} resolves to a cut of {cut:g} at the {share:g} percentile, "
                    f"which admits all {len(values)} {domain} cells - the gate separates "
                    f"nothing, so the archetype would stand on ground its own requirement "
                    f"never tested")
    return None


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
