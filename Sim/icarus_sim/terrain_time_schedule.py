"""Which steps fall inside a span of simulated time. Pure: no world, no RNG, no clock.

This module is the whole of the determinism argument for time advance, which is why it
holds no state and touches no world document. `terrain_time` executes what this returns.

**The binding invariant: the RNG domain is keyed by simulated time, never by tick ordinal
or call count.** Every cadence below fires on an absolute step index `floor(day / period)`
measured from the epoch, so a call for elapsed E executes exactly the indices falling in
`(now, now + E]` and nothing else. No draw is made per call, and no index depends on how
the span was cut. That is what makes `advance(30y)` and `advance(15y)` twice identical,
and the byte-equality test over that pair is the contract in one assertion.

The failure mode this shape exists to prevent is a seed derived from tick ordinal. It is
invisible until someone chunks differently, and by then a saved world has been advanced
across it. Float addition is not associative and city identity is compared at zero
tolerance downstream, so a quantity summed in two chunks that differs in the last ulp
propagates into a different city set.

Steps are returned in absolute-time order, ties broken by the pinned cadence order below.
Ordering by time rather than by subsystem is the second half of chunk-independence: a
subsystem-major order would run a year of one pass before a month of another, and the two
orders diverge the moment a call boundary lands between them.
"""
import math

# The calendar is the moon's, and it already exists: `docs/astrology.md` fixes 24-hour
# days, 30-day months and 12-month years, with day 0 at founding year 0. Time here is a
# real number of days on that same scale so a tick and `POST /world/moon` cannot disagree.
HOURS_PER_DAY = 24.
DAYS_PER_MONTH = 30.
MONTHS_PER_YEAR = 12.
DAYS_PER_YEAR = DAYS_PER_MONTH * MONTHS_PER_YEAR      # 360
SEASON_DAYS = DAYS_PER_YEAR / 4.                       # 90

# An age had no duration before this module. Ages were ordinal -- `history.ages` is a list
# and the age lottery samples `int(founding.end_year) * 360` for its moon day -- so
# nothing in the generator said how long one lasts. A tick cannot route a long span into
# an age advance without an answer, so this is that answer, and it is new contract rather
# than a discovered constant: **an age is five thousand years**
# (`docs/decisions/028-an-age-is-five-thousand-years.md`).
#
# It is load-bearing in two places outside this line, and both move with it or break
# silently. `terrain_time` takes the age transition's own ley band to the power of
# `1 / AGE_YEARS`, so a year-step composes over one whole age to the band the age boundary
# itself applies -- hard-code that exponent and a longer age drains the magic layer to zero
# through ordinary ticking with every individual step inside its stated bounds. And `band`
# returns `AGE` at `AGE_DAYS`, so what counts as a tick rather than an age advance moves
# with it: a century is a `LONG` tick, one fiftieth of an age, and moves the living layer
# only.
AGE_YEARS = 5000.
AGE_DAYS = AGE_YEARS * DAYS_PER_YEAR                   # 1800000

INSTANT = 'instant'
DAY = 'day'
SEASON = 'season'
LONG = 'long'
AGE = 'age'

# Ordered, and the order is load-bearing twice over: it breaks ties between cadences that
# fire on the same day, and it is **dependency order**, producers before consumers.
# `add_nomad_routes` reads and writes the block `add_nomads` replaced; `add_encounters`
# reads both `nomads` and `beast_movements`. Ordering them any other way would build an
# index of bands that no longer exist. Period is in days; `rank` is the position here.
#
# Every one of these passes has the same `(result, cfg)` signature, so the executor needs
# no per-pass glue -- see `terrain_time.CADENCE_PASSES`.
CADENCES = (
    ('quests', 1.),               # offers expire and are reaped daily; O(hooks), no world rebuild
    ('ley_drift', DAYS_PER_YEAR),
    ('seasonal_food', SEASON_DAYS),
    ('nomads', DAYS_PER_YEAR),
    ('nomad_routes', DAYS_PER_MONTH),
    ('beast_movements', DAYS_PER_MONTH),
    ('encounters', DAYS_PER_MONTH),
    # The nomad chain's write-backs. `add_nomads` replaces the block wholesale, which
    # discards `nomads.effects` and orphans the cultist ley deepening, raid pressure, ridden
    # roads and survivor camps the *previous* population left behind. The age path runs this
    # for the same reason, last, after routes exist to ride.
    ('nomad_effects', DAYS_PER_YEAR),
    ('villain_outlook', DAYS_PER_YEAR),
)

# Cadences whose pass **replaces its block wholesale** rather than accumulating into it.
# Only the last crossing inside a span can survive, because every earlier one is
# overwritten by it, so only the last is executed. A thirty-year span runs one
# `add_encounters` instead of three hundred and sixty identical-fated ones.
#
# This is exactly the coalescing `advance_age_request` already does, where the planners,
# heroes and key locations run at `age == start_age + steps` rather than once per age.
#
# It is safe only because of the dependency ordering above, and only for passes that never
# read the block they write. Both were checked at the source: `add_encounters` writes
# `result['encounters']` and reads `nomads` and `beast_movements`; `add_nomads` writes
# `result['nomads']` and reads settlements and ruins. A pass that accumulated -- `quests`,
# which carries expiry forward, and `ley_drift`, which is a compounding random walk -- must
# never be listed here, and neither is.
#
# Chunk independence survives it. A shorter period divides a longer one, so a consumer's
# last crossing is never earlier than its producer's, and a coalesced run in one call is
# wholly overwritten by the coalesced run in the next.
COALESCED = frozenset({'seasonal_food', 'nomads', 'nomad_routes', 'beast_movements',
                       'encounters', 'nomad_effects', 'villain_outlook'})
CADENCE_RANK = {name: rank for rank, (name, _) in enumerate(CADENCES)}
CADENCE_PERIOD = dict(CADENCES)

# A band names how big a span is. It does **not** decide which cadences may run.
#
# It used to. `steps()` filtered by `BAND_CADENCES[band(days)]`, which was a silent,
# permanent data-loss bug rather than a conservative one: the window is half-open at the
# start, so a crossing skipped because *this* call was too short is never revisited by any
# later call. A game ticking a month at a time would never once run ley drift, nomad
# reclassification, seasonal food or the villain outlook -- not deferred, skipped -- and a
# game ticking by the second would advance nothing but its clock, forever. It also made the
# central invariant false: the same span cut across a band boundary produced a different
# world, which is the one thing this module exists to prevent.
#
# What actually enforces the guarantee is `crossings()`. A span runs exactly the cadence
# boundaries inside it and nothing else, so three seconds normally runs nothing because
# three seconds normally crosses nothing -- and on the rare tick that does step over a day
# boundary, running that day's quest sweep is correct rather than a violation. Cities are
# only ever killed at an age transition, which is a different band and a different call.
#
# Kept as a label for the report, for routing the age band, and for documenting what a span
# of each size typically touches.
BAND_CADENCES = {
    INSTANT: (),
    DAY: ('quests', 'encounters', 'beast_movements', 'nomad_routes'),
    SEASON: ('quests', 'encounters', 'beast_movements', 'nomad_routes', 'seasonal_food',
             'ley_drift', 'nomads', 'nomad_effects', 'villain_outlook'),
}
BAND_CADENCES[LONG] = BAND_CADENCES[SEASON]


def elapsed_days(spec):
    """Days from `{'seconds'|'days'|'years': n}`. Exactly one unit, finite, not negative.

    This is the one function here that reads a caller's input rather than the clock, so it
    is the one that raises the structured refusal the rest of the request boundary uses.
    `terrain_errors` is pure, so importing it costs this module nothing it claims not to
    have.
    """
    from .terrain_errors import cross_field, invalid_choice, wrong_type
    UNITS = ('seconds', 'days', 'years')
    if not isinstance(spec, dict):
        raise wrong_type('elapsed', spec,
                         {'type': 'object', 'description': 'one of ' + ', '.join(UNITS)})
    if len(spec) != 1:
        raise cross_field('elapsed names exactly one unit; received ' + (str(sorted(spec)) or 'none') + '.',
                          tuple(sorted(spec)) or UNITS)
    (unit, value), = spec.items()
    if unit not in UNITS:
        raise invalid_choice('elapsed', unit, {'choices': list(UNITS)})
    if type(value) not in (int, float) or isinstance(value, bool) or not math.isfinite(value) or value < 0:
        raise wrong_type('elapsed.' + unit, value,
                         {'type': 'number', 'min': 0,
                          'description': 'a finite count of ' + unit + ' to advance'})
    if unit == 'seconds':
        return value / (HOURS_PER_DAY * 3600.)
    if unit == 'years':
        return value * DAYS_PER_YEAR
    return float(value)


def band(days):
    """Which band a span of `days` falls in."""
    if days < 1.:
        return INSTANT
    if days < SEASON_DAYS:
        return DAY
    if days < 2. * DAYS_PER_YEAR:
        return SEASON
    if days < AGE_DAYS:
        return LONG
    return AGE


def ages_for(days):
    """How many age advances a span of `days` is worth, for the age band."""
    return int(days // AGE_DAYS)


def crossings(name, now, days):
    """The absolute step indices of cadence `name` falling in `(now, now + days]`.

    Half-open at the start so a step is never executed twice by two adjacent calls, and
    closed at the end so a step landing exactly on the boundary is executed once.
    """
    period = CADENCE_PERIOD[name]
    first = int(math.floor(now / period)) + 1
    last = int(math.floor((now + days) / period))
    return range(first, last + 1)


def steps(now, days, allowed=None):
    """Ordered `(day, name, index)` for every cadence step inside `(now, now + days]`.

    `allowed` defaults to every cadence. Ordering is by absolute day, then by the pinned
    cadence order, then by index -- never by subsystem, because a subsystem-major order is
    not chunk-independent.

    This function is the whole invariant: a step belongs to exactly one window, decided by
    its own absolute index, so no cut of a span can create or destroy one.
    """
    if days < 0:
        raise ValueError('days must be >= 0')
    # Every cadence, always. Which ones actually produce a step is decided by whether the
    # window contains one of their crossings, never by how long the window is.
    names = CADENCE_PERIOD if allowed is None else allowed
    out = []
    for name in names:
        period = CADENCE_PERIOD[name]
        indices = crossings(name, now, days)
        if name in COALESCED:
            # Only the survivor runs. `indices` is a range, so this is the last element
            # without materialising three hundred and sixty of them.
            indices = indices[-1:] if len(indices) else indices
        for index in indices:
            out.append((index * period, name, index))
    out.sort(key=lambda step: (step[0], CADENCE_RANK[step[1]], step[2]))
    return out


def by_cadence(now, days):
    """How many steps each cadence would run in `(now, now + days]`, counted not built.

    `crossings` returns a `range`, and `len` on a range is O(1), so the whole span is
    priced without allocating a tuple per step. That matters at the top of the band: a
    span just under an age is 1.8 million steps, and the guard in `terrain_time` has to
    answer *before* that list exists rather than after it.

    Cadences that contribute nothing are absent, exactly as they are when the counts are
    tallied from `steps`.
    """
    if days < 0:
        raise ValueError('days must be >= 0')
    counts = {}
    for name in CADENCE_PERIOD:
        count = len(crossings(name, now, days))
        if name in COALESCED:
            count = min(count, 1)
        if count:
            counts[name] = count
    return dict(sorted(counts.items()))


def work(now, days):
    """How much work a span would execute: the number of steps, without building them.

    The honest unit for a cost ceiling, because a step is what costs. It must answer
    exactly the question `steps` answers, and `WorkCeilingTests` asserts that against the
    enumerator itself rather than against a formula, because a counter that answers a
    slightly different question than the thing it stands in for is the near-miss that
    keeps being mistaken here for an answer.

    Steps are a proxy for cost and not cost: a coalesced pass runs once per call however
    many crossings it had, while a daily quest sweep runs every day, so two spans with
    equal counts can differ by orders of magnitude. The ceiling that reads this says so.
    """
    return sum(by_cadence(now, days).values())


def longest_span(now, limit):
    """The longest span in days, from `now`, whose work is at most `limit` steps.

    A cost ceiling counts steps, but a caller asks in days or years, so a refusal that
    only named the step limit would be telling them to clamp a field they never sent.
    `work` is non-decreasing in `days` -- a longer window contains every crossing a
    shorter one did -- so the answer is a bisection over whole days, and the whole search
    allocates nothing.

    Whole days, and rounded down: the answer is a span that is certainly permitted rather
    than the exact boundary, so a caller that sends it back is not refused again by a
    fraction of a day.
    """
    if limit < 0:
        raise ValueError('limit must be >= 0')
    low, high = 0, int(AGE_DAYS)
    if work(now, float(high)) <= limit:
        return float(high)
    while low < high:
        middle = (low + high + 1) // 2
        if work(now, float(middle)) <= limit:
            low = middle
        else:
            high = middle - 1
    return float(low)


def plan(now, days):
    """A description of what a span would do, without doing any of it.

    Returned to the caller in the `time_advance` report and used by the age band to
    answer what a request would cost before it commits to paying it.
    """
    which = band(days)
    counts = by_cadence(now, days)
    return {'band': which, 'elapsed_days': days, 'from_day': now, 'to_day': now + days,
            'ages': ages_for(days) if which == AGE else 0,
            'steps': sum(counts.values()), 'by_cadence': counts}
