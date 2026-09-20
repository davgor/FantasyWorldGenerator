"""One moon, two hemispheres, eight schools: seeded cycles, tide, almanac. No engine I/O.

The moon is not tidally locked. Its Still hemisphere carries the ordered schools and
its Restless hemisphere the chaotic ones, one school per quarter. Three integer-day
cycles with a coprime preference (phase, spin, nod) make a beat far longer than any
one of them: fully replayable, and long enough to read as chaos. Every quantity here
is a ratio of a cycle or a unit vector, never a metre, so world scale cannot move it.

Numeric contract: only sin, cos, products, sums, min and max, and integer modulo on
integer days. No pow, so the C++ mirror in Core/astrology.cpp can reproduce it.
"""
import math
from .terrain_errors import (cross_field, missing_block, out_of_range, unknown_field,
                             unsupported_api, wrong_type)
import random
from time import perf_counter
from .terrain_tectonics import child_seed
from .terrain_leyline_history import KNOWN_SCHOOLS

HOURS_PER_DAY = 24
DAYS_PER_MONTH = 30
MONTHS_PER_YEAR = 12
DAYS_PER_YEAR = DAYS_PER_MONTH * MONTHS_PER_YEAR
HEMISPHERES = {'still': ['radiant', 'water', 'earth', 'umbral'], 'restless': ['weave', 'fire', 'air', 'infernal']}
HEMISPHERE_LATITUDE = {'still': 45., 'restless': -45.}
PERIOD_RANGES = {'synodic': (26, 34), 'spin': (15, 63), 'nod': (17, 37)}
TILT_RANGE = (10., 35.)
REDRAWS = 8
DEG = math.pi / 180
TIDE_FLOOR, TIDE_GAIN, TIDE_MIN, TIDE_MAX = .7, 1.1, .5, 1.8
SURGE, HOLLOW = 1.6, .75
WORLDWARD = (1., 0., 0.)


def region_direction(hemisphere, quarter):
    """Unit vector of a quarter's centre in the moon frame: y is the polar axis."""
    latitude = HEMISPHERE_LATITUDE[hemisphere] * DEG
    longitude = quarter * 90 * DEG
    return (math.cos(latitude) * math.cos(longitude), math.sin(latitude), math.cos(latitude) * math.sin(longitude))


def _regions():
    where = {school: (hemisphere, quarter) for hemisphere, schools in HEMISPHERES.items()
             for quarter, school in enumerate(schools)}
    return {school: region_direction(*where[school]) for school in KNOWN_SCHOOLS}


REGIONS = _regions()


def seed_moon(seed, variation=0, overrides=None):
    """Seeded integer-day periods, offsets and nod tilt; draw order is part of the contract.

    `overrides` may pin any period or the tilt (zero or absent keeps the seeded value);
    the draws still happen in the same order so an override never changes another cycle.
    """
    rng = random.Random(child_seed(seed, 'astrology-v1', variation))
    synodic = rng.randint(*PERIOD_RANGES['synodic'])
    spin = rng.randint(*PERIOD_RANGES['spin'])
    for _ in range(REDRAWS):
        if math.gcd(spin, synodic) == 1:
            break
        spin = rng.randint(*PERIOD_RANGES['spin'])
    nod = rng.randint(*PERIOD_RANGES['nod'])
    for _ in range(REDRAWS):
        if math.gcd(nod, synodic) == 1 and math.gcd(nod, spin) == 1:
            break
        nod = rng.randint(*PERIOD_RANGES['nod'])
    periods = {'synodic': synodic, 'spin': spin, 'nod': nod}
    offsets = {key: rng.randint(0, periods[key] - 1) for key in ('synodic', 'spin', 'nod')}
    tilt = rng.uniform(*TILT_RANGE)
    controls = {'variation': variation, 'overrides': {}}
    for key, value in (overrides or {}).items():
        if not value:
            continue
        if key == 'tilt':
            if not TILT_RANGE[0] <= value <= TILT_RANGE[1]:
                raise ValueError(f'moon_tilt_degrees must be 0 or {TILT_RANGE[0]:g}..{TILT_RANGE[1]:g}')
            tilt = float(value)
        elif key in PERIOD_RANGES:
            low, high = PERIOD_RANGES[key]
            if type(value) is not int or not low <= value <= high:
                raise ValueError(f'moon_{key}_days must be 0 or {low}..{high}')
            periods[key] = value
            offsets[key] = offsets[key] % value
        else:
            raise ValueError('Unknown moon override ' + str(key))
        controls['overrides'][key] = value
    return {'periods': periods, 'offsets': offsets, 'tilt_max_degrees': tilt,
            'great_year_days': math.lcm(periods['synodic'], periods['spin'], periods['nod']), 'controls': controls}


def cycle_fraction(moon, key, t):
    """Fraction of a cycle at time t in days; integer days stay in integer arithmetic."""
    return ((t + moon['offsets'][key]) % moon['periods'][key]) / moon['periods'][key]


def moon_state(moon, t):
    phase = 2 * math.pi * cycle_fraction(moon, 'synodic', t)
    spin = 2 * math.pi * cycle_fraction(moon, 'spin', t)
    nod = moon['tilt_max_degrees'] * math.sin(2 * math.pi * cycle_fraction(moon, 'nod', t))
    return {'phase_angle': phase, 'spin_angle': spin, 'nod_degrees': nod}


def _facing(vector, spin, nod_degrees):
    """Rotate a moon-frame vector by the spin about y, then lean by the nod about z."""
    x, y, z = vector
    cs, ss = math.cos(spin), math.sin(spin)
    x, z = x * cs + z * ss, -x * ss + z * cs
    cn, sn = math.cos(nod_degrees * DEG), math.sin(nod_degrees * DEG)
    # A positive nod turns the Still (y > 0) hemisphere toward the world (+x).
    x, y = x * cn + y * sn, -x * sn + y * cn
    return x, y, z


def tide(moon, t):
    """Per-school strength multiplier: visible fraction times lit fraction of its quarter."""
    state = moon_state(moon, t)
    sun = (math.cos(state['phase_angle']), 0., math.sin(state['phase_angle']))
    factors = {}
    for school, vector in REGIONS.items():
        x, y, z = _facing(vector, state['spin_angle'], state['nod_degrees'])
        visible = max(0., x)
        lit = max(0., x * sun[0] + z * sun[2])
        factors[school] = min(TIDE_MAX, max(TIDE_MIN, TIDE_FLOOR + TIDE_GAIN * visible * lit))
    return factors


def day_state(moon, t):
    """What a clock needs: phase, rise hour after sunrise, illumination, lean and tide."""
    state = moon_state(moon, t)
    fraction = cycle_fraction(moon, 'synodic', t)
    return {'phase_fraction': fraction, 'elongation_degrees': 360 * fraction,
            'illumination': (1 + math.cos(state['phase_angle'])) / 2, 'moonrise_hour': HOURS_PER_DAY * fraction,
            'spin_fraction': cycle_fraction(moon, 'spin', t), 'nod_degrees': state['nod_degrees'],
            'leaning': 'still' if state['nod_degrees'] >= 0 else 'restless', 'tide': tide(moon, t)}


def almanac(moon, year):
    """One reported year: month heads, events and the next day all three cycles restart."""
    start = year * DAYS_PER_YEAR
    months = []
    for m in range(MONTHS_PER_YEAR):
        first = start + m * DAYS_PER_MONTH
        totals = {school: 0. for school in KNOWN_SCHOOLS}
        for d in range(DAYS_PER_MONTH):
            for school, value in tide(moon, first + d).items():
                totals[school] += value
        months.append({'first_day': first, **day_state(moon, first),
                       'mean_tide': {school: totals[school] / DAYS_PER_MONTH for school in KNOWN_SCHOOLS}})
    periods, offsets = moon['periods'], moon['offsets']
    events = []
    for d in range(DAYS_PER_YEAR):
        day = start + d
        synodic = (day + offsets['synodic']) % periods['synodic']
        if synodic == 0:
            events.append({'day': d, 'kind': 'full_moon'})
        elif synodic == periods['synodic'] // 2:
            events.append({'day': d, 'kind': 'new_moon'})
        nod = (day + offsets['nod']) % periods['nod']
        if nod == periods['nod'] // 4:
            events.append({'day': d, 'kind': 'still_ascendant'})
        elif nod == (3 * periods['nod']) // 4:
            events.append({'day': d, 'kind': 'restless_ascendant'})
        factors = tide(moon, day)
        for school in KNOWN_SCHOOLS:
            if factors[school] >= SURGE:
                events.append({'day': d, 'kind': 'surge', 'school': school, 'tide': factors[school]})
        if all(v <= HOLLOW for v in factors.values()):
            events.append({'day': d, 'kind': 'hollow_night'})
    events.sort(key=lambda e: (e['day'], e['kind'], e.get('school', '')))
    alignment = None
    for day in range(start, start + moon['great_year_days']):
        if all((day + offsets[key]) % periods[key] == 0 for key in ('synodic', 'spin', 'nod')):
            alignment = day
            break
    return {'reported_year': year, 'now': {'day': start, **day_state(moon, start)}, 'months': months,
            'events': events, 'next_grand_alignment_day': alignment}


FORMULAS = {
    'time': 't is real days since founding year 0; hour 0 is sunrise; integer days use integer modulo',
    'fraction': 'f_k(t) = ((t + offsets[k]) mod periods[k]) / periods[k] for k in synodic, spin, nod',
    'phase_angle': 'alpha = 2*pi*f_synodic; 0 is full, pi is new',
    'spin_angle': 'beta = 2*pi*f_spin, rotation of the moon frame about its polar axis y',
    'nod_degrees': 'gamma = tilt_max_degrees * sin(2*pi*f_nod); positive leans the still hemisphere toward the world',
    'region': 'x,z = x*cos(beta)+z*sin(beta), -x*sin(beta)+z*cos(beta); then x,y = x*cos(gamma)+y*sin(gamma), -x*sin(gamma)+y*cos(gamma)',
    'tide': 'tide_s = clamp(.7 + 1.1 * max(0,x) * max(0, x*cos(alpha)+z*sin(alpha)), .5, 1.8) using that school region',
    'illumination': '(1 + cos(alpha)) / 2',
    'moonrise_hour': '24 * f_synodic hours after sunrise (full moon rises at sunset)',
    'elongation_degrees': '360 * f_synodic',
    'leyline_at_time': 'ley_s(t) = ley_s * (1 + lunar_sensitivity * (tide_s(t) - 1))',
}
LIMITS = ('The moon is artistic astronomy: one body reduced to phase, rise hour, spin and lean. No altitude, '
          'no latitude dependence, no solar eclipses, no water tides. Surges are momentary multipliers; the '
          'exported leyline grids are the base field.')


MOON_FIELDS = ('api_version', 'world', 'day', 'year', 'month', 'day_of_month', 'hour')
MOON_API_VERSION = 1


def lunar_request(body):
    """Stateless moon query: the sky and the surge at any day or hour of a generated world.

    Time is `day` (real days since founding year 0) or year, month, day_of_month and
    hour; both give the same closed-form answer the exported formulas describe, so an
    orchestrator can drive a clock from this and stay bit-consistent with the almanac.
    """
    if not isinstance(body, dict):
        raise wrong_type('request', body, {'type': 'object'})
    if set(body) - set(MOON_FIELDS):
        raise unknown_field(sorted(set(body) - set(MOON_FIELDS))[0], MOON_FIELDS,
                            noun='request field')
    if type(body.get('api_version')) is not int or body['api_version'] != MOON_API_VERSION:
        raise unsupported_api('api_version', body.get('api_version'), (MOON_API_VERSION,))
    world = body.get('world')
    if not isinstance(world, dict):
        raise wrong_type('world', world, {'type': 'object'})
    if not isinstance(world.get('astrology'), dict) or world['astrology'].get('version') != 1:
        raise missing_block('astrology', 'This world lacks the astrology contract at version '
                            '1. The moon is seeded during generation, so a world exported '
                            'before that contract has to be regenerated rather than '
                            'migrated.')
    moon = world['astrology']['moon']
    almanac_now = world.get('lunar_almanac', {})
    if 'day' in body:
        if any(k in body for k in ('year', 'month', 'day_of_month', 'hour')):
            raise cross_field('Give an absolute day or a calendar time, not both. They are '
                              'two spellings of one instant and this call cannot tell which '
                              'you meant.',
                              ('day', 'year', 'month', 'day_of_month', 'hour'))
        t = body['day']
        if type(t) not in (int, float) or not math.isfinite(t):
            raise wrong_type('day', t, {'type': 'number'})
        if t < 0:
            raise out_of_range('day', t, {'type': 'number', 'min': 0, 'units': 'days since '
                                          'founding year 0'})
        year, remainder = divmod(int(t), DAYS_PER_YEAR)
        month, day_of_month = divmod(remainder, DAYS_PER_MONTH)
        hour = (t - int(t)) * HOURS_PER_DAY
        month += 1
        day_of_month += 1
    else:
        year = body.get('year', almanac_now.get('reported_year', 0))
        month = body.get('month', 1)
        day_of_month = body.get('day_of_month', 1)
        hour = body.get('hour', 0)
        if type(year) is not int:
            raise wrong_type('year', year, {'type': 'integer'})
        if year < 0:
            raise out_of_range('year', year, {'type': 'integer', 'min': 0, 'units': 'years'})
        if type(month) is not int:
            raise wrong_type('month', month, {'type': 'integer'})
        if not 1 <= month <= MONTHS_PER_YEAR:
            raise out_of_range('month', month, {'type': 'integer', 'min': 1,
                                                'max': MONTHS_PER_YEAR, 'units': 'months'})
        if type(day_of_month) is not int:
            raise wrong_type('day_of_month', day_of_month, {'type': 'integer'})
        if not 1 <= day_of_month <= DAYS_PER_MONTH:
            raise out_of_range('day_of_month', day_of_month,
                               {'type': 'integer', 'min': 1, 'max': DAYS_PER_MONTH,
                                'units': 'days'})
        if type(hour) not in (int, float) or not math.isfinite(hour):
            raise wrong_type('hour', hour, {'type': 'number'})
        if not 0 <= hour <= HOURS_PER_DAY:
            raise out_of_range('hour', hour, {'type': 'number', 'min': 0,
                                              'max': HOURS_PER_DAY, 'units': 'hours'})
        t = year * DAYS_PER_YEAR + (month - 1) * DAYS_PER_MONTH + (day_of_month - 1)
        if hour:
            t = t + hour / HOURS_PER_DAY
    state = day_state(moon, t)
    # Only the known schools have a tide. A hidden school is absent from this report
    # rather than reported as unmoved, because the moon never charted it.
    strengths = {name: net['strength'] * state['tide'][name]
                 for name, net in world.get('magic', {}).get('networks', {}).items()
                 if name in state['tide']}
    report = almanac(moon, year)
    return {'api_version': MOON_API_VERSION,
            'time': {'day': t, 'year': year, 'month': month, 'day_of_month': day_of_month, 'hour': hour},
            **state, 'surged_strength': strengths, 'year_events': report['events'],
            'next_grand_alignment_day': report['next_grand_alignment_day'], 'great_year_days': moon['great_year_days']}


def lunar_sensitivity(result, cfg):
    """How far a cell's magic sways with the moon, from fields that are already ratios."""
    layers = result['layers']
    n = cfg.size
    empty = [[0.] * n for _ in range(n)]
    instability = [layers.get('instability_' + school, empty) for school in KNOWN_SCHOOLS]
    water = layers.get('water_type', empty)
    exposure = layers.get('coastal_exposure', empty)
    grid = []
    for z in range(n):
        row = []
        for x in range(n):
            total = 0.
            for field in instability:
                total += field[z][x]
            shore = 1. if water[z][x] == 2 else exposure[z][x]
            row.append(min(1., max(0., .2 + .5 * total + .3 * shore)))
        grid.append(row)
    return grid


def reported_year(result):
    founding = result.get('settlements', {}).get('founding') or {}
    if 'end_year' in founding:
        return int(founding['end_year']), 'founding.end_year'
    return 0, 'epoch'


def refresh_astrology(result, cfg):
    """Recompute everything that depends on the year or on the ley fields; never reseed."""
    started = perf_counter()
    moon = result['astrology']['moon']
    year, source = reported_year(result)
    report = almanac(moon, year)
    result['lunar_almanac'] = {'version': 1, 'reported_year_source': source, **report}
    result['layers']['lunar_sensitivity'] = lunar_sensitivity(result, cfg)
    factors = report['now']['tide']
    magic = result.get('magic')
    if magic is not None:
        for name, net in magic.get('networks', {}).items():
            # A hidden school takes no surge and carries no surged_strength key: alien
            # magic does not answer to this world's sky.
            if name in factors:
                net['surged_strength'] = net['strength'] * factors[name]
        magic['lunar_surge'] = {'day': report['now']['day'], 'factors': dict(factors),
                                'formula': 'surged_strength = strength * tide_school(day)'}
    timing = result.setdefault('timing_ms', {})
    timing['astrology'] = timing.get('astrology', 0.) + (perf_counter() - started) * 1000
    return result


def add_astrology(result, cfg):
    """Stage 9: seed the moon once per world, then publish the first almanac."""
    from .terrain_world import options
    o = options(cfg) if cfg.world_recipe else {}
    moon = seed_moon(cfg.seed, o.get('moon_variation', 0),
                     {'synodic': o.get('moon_synodic_days', 0), 'spin': o.get('moon_spin_days', 0),
                      'nod': o.get('moon_nod_days', 0), 'tilt': o.get('moon_tilt_degrees', 0.)})
    result['astrology'] = {
        'version': 1,
        'calendar': {'hours_per_day': HOURS_PER_DAY, 'days_per_month': DAYS_PER_MONTH,
                     'months_per_year': MONTHS_PER_YEAR, 'days_per_year': DAYS_PER_YEAR,
                     'epoch': 'day 0 is founding year 0; hour 0 is sunrise'},
        'moon': {**moon, 'hemispheres': HEMISPHERES, 'regions': {school: list(v) for school, v in REGIONS.items()},
                 'period_ranges': PERIOD_RANGES, 'tilt_range_degrees': list(TILT_RANGE)},
        'formulas': FORMULAS,
        'method': 'One moon, not tidally locked. Its still hemisphere carries radiant, water, earth and umbral; '
                  'its restless hemisphere weave, fire, air and infernal, one school per quarter. Seeded '
                  'integer-day phase, spin and nod cycles prefer coprime periods, so the great year is their '
                  'least common multiple. A school surges when its quarter both faces the world and is lit.',
        'limits': LIMITS}
    result.setdefault('warnings', []).append(LIMITS)
    return refresh_astrology(result, cfg)
