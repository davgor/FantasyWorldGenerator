"""Super villains: antagonists that operate on a different order than the kings around them.

Every figure the generator otherwise produces is a point in the world, named after events
that already happened. A super villain is a field: a reach in metres with falloff, like a
ley network or a visitation, that causes wars and city fates in its own name.

Tier is reach and it is continuous, so "super villain" is a band on a curve rather than a
flag that flips. That is the whole pacing model: one that has just crossed the line is a
threat that is growing, not one that has arrived, so the peace after a player kills one
comes from the successor being weak rather than from a cooldown holding anything back.

`villain_rise` defaults to .5 and a generated world ends with super villains standing in
it: accumulation alone cannot seat anybody inside two age transitions, so the rate is the
campaign ramp and `promote()` is the arrival. Setting it to zero is still a real off
switch -- no `villains` block is written at all.
"""
import copy
import math

from .terrain_tectonics import child_seed

VERSION = 1
SUPER_TIER = 1.             # the band a villain is "super" above
REACH_SPACINGS_PER_TIER = 4.  # how far one tier of reach carries, in settlement spacings
RISK_WEIGHT, HUNGER_WEIGHT = .3, .3
FALLOFF = 1.5               # reach multiples at which a villain's pressure is spent
VILLAIN_WEIGHT = .5         # its share of a city's fate lottery at the seat, at tier one
STALLED_TIER = .999         # where a pretender sits when the ceiling is full
FRAGMENT_SHARE = .35        # the tier a region keeps when its villain falls
# How hard a fallen villain's claims still press on the world. Ground it took stays
# taken -- that is a decision, not a default -- but how *strongly* taken is a separate
# question from whether the record persists, and it is deliberately a number rather
# than a boolean so it can decay without reopening the consumers.
#
# The decay is now argued and set, by the same case FRAGMENT_SHARE makes for tier: a
# region's grip fades when its holder goes. A world that never decays this places by who
# *ever* held power rather than who holds it, and that failure only appears over spans no
# single age advance could reach -- which is why the value waited for the clock.
#
# The claim drops at the fall and fades by the same factor each age after it, to a floor
# below which it stops steering entirely and is reported as zero. The record is never
# pruned: what fades is how hard the claim presses, not whether it happened.
#
#   ages since fall  0     1     2     3     4     5
#   influence        .60   .36   .216  .130  .078  0 (below the floor)
#
# Seed-visible: a world containing a fallen villain places differently than it did when
# this was 1.0. See docs/decisions/024-fallen-claim-decay.md.
FALLEN_CLAIM_INFLUENCE = .6   # what a claim keeps at the moment its holder falls
CLAIM_DECAY_PER_AGE = .6      # what it keeps of that for each further age
CLAIM_INFLUENCE_FLOOR = .05   # below this a claim no longer steers anything


def claim_influence(ages_since_fall):
    """How hard a fallen villain's claim still presses, `ages_since_fall` ages later.

    Zero below the floor rather than a vanishing fraction, so a consumer scaling by this
    stops being nudged by claims too old to matter instead of being nudged imperceptibly
    forever.
    """
    if ages_since_fall < 0:
        return 1.
    value = FALLEN_CLAIM_INFLUENCE * (CLAIM_DECAY_PER_AGE ** ages_since_fall)
    return 0. if value < CLAIM_INFLUENCE_FLOOR else round(value, 9)

# Which pressure raised them decides how their reach grows, and therefore how they are
# fought. The sim owns this field; the hero generator reads it and picks the matching
# escalation of the archetype card a person already carries, so the two agree without
# either package importing the other.
GROWTH_BY_PRESSURE = {'war': 'devouring', 'nest': 'spreading', 'ley': 'hoarding'}
DEFAULT_GROWTH = 'usurping'


def is_standing(villain):
    """True while a villain still holds its region.

    `people` holds the fallen as well as the living, the way `heroes.people` holds
    legends and `npcs.people` holds the dead: one list, a status field, and the reader
    filters. Every consumer that means "who stands right now" must say so, because the
    list stopped answering that question by construction when the fallen began staying
    in it.

    Absent status reads as living: a record written before the fall was recorded at all
    described someone who stood.
    """
    return (villain.get('status') or 'living') == 'living'


def standing(people):
    """Only the villains that still hold their region."""
    return [v for v in (people or []) if is_standing(v)]


def turmoil(report):
    """What a city contributes to its region concentrating, in 0..1.

    Standing threat plus the forward-looking outlook, because a region about to fight is
    concentrating as surely as one that already has.
    """
    standing_threat = float(report.get('regional_threat') or 0.)
    risk = float(report.get('war_risk') or 0.)
    hunger = float(report.get('war_hunger') or 0.)
    return max(0., min(1., standing_threat + RISK_WEIGHT * risk + HUNGER_WEIGHT * hunger))


def dominant_pressure(reports):
    """Which kind of pressure dominates a region, for the growth function."""
    totals = {}
    for report in reports:
        for key, field in (('war', 'war_pressure'), ('nest', 'nest_pressure'), ('ley', 'ley_pressure')):
            totals[key] = totals.get(key, 0.) + float(report.get(field) or 0.)
    if not totals or not any(totals.values()):
        return None
    return max(sorted(totals), key=lambda k: totals[k])


def regions(result, radius=None, reports_by_uid=None):
    """Cultural regions, each with the cities in it and a stable anchor.

    `humans.cultures` groups road-linked cities, so a region is something the world
    decided rather than something this module invented. But a culture's id is rebuilt
    every age from whatever the roads join that age, so it cannot carry anything across
    one: accumulating tier against it silently resets the region every time.

    The anchor is therefore the nearest ley node, which persists — ids are stable, new
    ones are only ever appended. Where there is no magic at all it falls back to the seat
    city's uid, which survivors also carry forward.
    """
    cultures = result.get('humans', {}).get('cultures', [])
    by_uid = {c['uid']: c for c in result.get('settlements', {}).get('sites', []) if 'uid' in c}
    by_site = {c['id']: c for c in result.get('settlements', {}).get('sites', []) if 'id' in c}
    groups = []
    for culture in sorted(cultures, key=lambda c: str(c.get('id'))):
        cities = [by_site[i] for i in culture.get('city_ids', []) if i in by_site]
        if cities:
            groups.append({'id': str(culture.get('id')), 'cities': cities})
    if not groups and by_uid:
        groups = [{'id': 'world', 'cities': sorted(by_uid.values(), key=lambda c: c['uid'])}]
    if radius is None:
        return groups
    out = []
    for group in groups:
        seat = _seat(group, reports_by_uid or {})
        if seat is None:
            continue
        school, node_id = _held_node(result, seat, radius)
        group.update(seat=seat, school=school, node_id=node_id, anchor=node_id or 'seat-' + seat['uid'])
        out.append(group)
    # Two regions can share a nearest node; the troubled one keeps it, so an anchor names
    # one region and a tier cannot be double-counted into it.
    best = {}
    for group in out:
        current = best.get(group['anchor'])
        if current is None or concentration(group, reports_by_uid or {}) > concentration(current, reports_by_uid or {}):
            best[group['anchor']] = group
    return [best[k] for k in sorted(best)]


def concentration(region, reports_by_uid):
    """How hard turmoil is pressed into one region, in 0..1.

    The mean is what separates "one bad city" from "a region coming apart", and a region
    the assessment has nothing to say about concentrates nothing.
    """
    values = [turmoil(reports_by_uid[c['uid']]) for c in region['cities'] if c.get('uid') in reports_by_uid]
    return sum(values) / len(values) if values else 0.


def ceiling(count, density):
    """How many villains may stand at or above the super band at once."""
    if not count:
        return 0
    return max(1, int(math.ceil(count / max(density, 1.))))


def _seat(region, reports_by_uid):
    """The city a villain rises in: the most troubled in its region, ties by uid."""
    ranked = sorted(region['cities'], key=lambda c: (-turmoil(reports_by_uid.get(c['uid'], {})), c['uid']))
    return ranked[0] if ranked else None


# A villain's own well is a ley node it created at its own seat, so it is always the
# nearest node to that seat. Left in the running it re-anchors the region onto the
# holder's own work: `regions()` then reports a different anchor, `advance` looks the
# villain up by the old one and misses, and the reign is stranded on the very age it
# began -- deterministically, for every villain bound to a school god. That is why the
# anchor must be ground the world laid down, not ground the villain did.
WELL_NODE_PREFIX = 'well-'


def _held_node(result, seat, radius):
    """The nearest existing ley node, which is what the villain actually holds.

    Keyed to the node and not to the city on purpose: anything hung on a city dict that
    is not in the survivor key tuple is dropped silently at the next age transition.

    Wells are skipped, because a region anchored to its own villain's well is anchored to
    something that did not exist before that villain and will not outlast it.
    """
    best = None
    for school, net in sorted(result.get('magic', {}).get('networks', {}).items()):
        for node in net['nodes']:
            if node['id'].startswith(WELL_NODE_PREFIX):
                continue
            angle = math.acos(max(-1., min(1., sum(a * b for a, b in zip(seat['direction'], node['direction'])))))
            distance = radius * angle
            if best is None or distance < best[0]:
                best = (distance, school, node['id'])
    return (best[1], best[2]) if best else (None, None)


# What a fallen villain carries out of its reign, chosen the way RUIN_KEYS chooses what a
# ruined city carries: identity, where it stood, and what it was -- not its live state.
# `tier` and `reach_m` are deliberately absent; both describe a grip it no longer has.
MARK_KEYS = ('uid', 'region', 'born_age', 'seat_uid', 'node', 'direction', 'school',
             'growth', 'held_nodes', 'claims', 'well', 'god', 'log')


def marks_left(result, villain):
    """What a villain actually did to the world, as the world itself recorded it.

    Read back out of `ruins` rather than accumulated on the villain, for the same reason
    the region is anchored to a ley node: anything hung on a live record is lost the moment
    that record is rebuilt, and ruins are already durable and already carry the attribution.
    """
    uid = villain['uid']
    ruined = [r['id'] for r in (result.get('ruins') or [])
              if (r.get('evidence') or {}).get('villain_uid') == uid]
    claims = [c['id'] for c in (villain.get('claims') or [])]
    well = (villain.get('well') or {}).get('node')
    return {'ruins': sorted(ruined), 'claims': sorted(claims),
            'well': well, 'held_nodes': sorted(villain.get('held_nodes') or [])}


def fallen_mark(result, villain, age):
    """The durable record of a reign, or None when there is nothing to record.

    "If they indeed left a mark" is a real condition, not a formality. A villain that
    reached the band, held nothing, took no city and sank no well did not mark the world,
    and inventing a monument for it would make the record of the dead less useful rather
    than more. What that villain leaves is what it always left: the decayed tier the region
    keeps, which is the successor squabble.
    """
    left = marks_left(result, villain)
    if not (left['ruins'] or left['claims'] or left['well']):
        return None
    mark = {k: copy.deepcopy(villain[k]) for k in MARK_KEYS if k in villain}
    # `or age` would be wrong here: age 0 is falsy, and the first age is exactly when a
    # villain is most likely to have risen. A villain seated at age 0 and fallen at age 3
    # reigned 3 ages, not 0.
    born = villain.get('born_age')
    born = age if born is None else int(born)
    mark.update(id='fallen-' + villain['uid'], kind='fallen_villains',
                fell_age=age, born_age=born, reigned_ages=max(0, age - born),
                tier_at_fall=round(float(villain.get('tier') or 0.), 9),
                left=left)
    # No asset_id, unlike a ruin. A ruin is a thing standing on the ground and needs a
    # marker in the exhaustive asset list; a fallen villain is a record about ground that
    # other records already hold -- its wells are ley nodes and its claims are claims, both
    # already placed. Giving it an asset would add an identity the catalogue must carry for
    # nothing to stand at.
    return mark

def advance(result, cfg, age, rise, hold, density):
    """Accumulate each region's tier, then seat, hold or unseat its villain.

    Returns the standing cast. A region's tier is the thing that persists; a villain is the
    name the world puts on a region that has concentrated past the band.

    `block['people']` holds the fallen as well, with `status: 'fallen'` and a `fell_age`.
    They are kept and never pruned: a world that forgets what stood in it cannot be asked
    about its own history. Read them through `standing()` whenever the question is who
    holds ground now.
    """
    if rise <= 0. and 'villains' not in result:
        # Zero raises none, and a world that has never had one carries no block at all:
        # the option is invisible in the output, not merely inert in it. A world that was
        # built with villains keeps its record even if the rate is later turned down.
        return []
    block = result.setdefault('villains', {'version': VERSION, 'people': [], 'tiers': {}, 'outlook': [],
                                           'fallen': []})
    # A world built before the durable list existed still advances into one.
    block.setdefault('fallen', [])
    tiers = dict(block.get('tiers') or {})
    # Only the standing are candidates to hold, fall or be counted against the ceiling.
    # Without this filter a fallen villain is reloaded as living and rises from the dead.
    living = {v['region']: dict(v) for v in standing(block.get('people', []))}
    fallen = [dict(v) for v in block.get('people', []) if not is_standing(v)]
    # The dead fade. Every age a fallen villain's claims press less on the ground it took,
    # restamped here rather than computed by each consumer, because the claim is what the
    # leaf packages read and they cannot import this module to ask.
    for old in fallen:
        fell_age = old.get('fell_age')
        if fell_age is None:
            continue
        for claim in old.get('claims', []):
            claim['influence'] = claim_influence(age - int(fell_age))
    marks = []
    reports_by_uid = {r['city_uid']: r for r in result.get('threat_assessments', {}).get('cities', [])}
    radius = result['effective_config']['globe_radius']
    spacing = cfg.settlement_spacing
    region_list = regions(result, radius, reports_by_uid)
    limit = ceiling(len(region_list), density)
    seated_count = sum(1 for v in living.values() if v['tier'] >= SUPER_TIER)

    for region in region_list:
        rid = region['anchor']
        pressed = concentration(region, reports_by_uid)
        tier = tiers.get(rid, 0.) + rise * pressed
        villain = living.get(rid)
        if tier >= SUPER_TIER and villain is None and seated_count >= limit:
            # Pretenders stall at the line: the ceiling stops a rise, not an existence.
            tier = min(tier, STALLED_TIER)
        tiers[rid] = tier
        if villain is None:
            if tier >= SUPER_TIER:
                seat, school, node_id = region['seat'], region['school'], region['node_id']
                pressure = dominant_pressure([reports_by_uid[c['uid']] for c in region['cities']
                                              if c.get('uid') in reports_by_uid])
                living[rid] = {
                    'uid': f'villain-{age}-{seat["node"]}',
                    'region': rid, 'born_age': age,
                    'seat_uid': seat['uid'], 'node': seat['node'], 'direction': list(seat['direction']),
                    'school': school, 'held_nodes': [node_id] if node_id else [],
                    'tier': tier, 'reach_m': tier * REACH_SPACINGS_PER_TIER * spacing,
                    'growth': GROWTH_BY_PRESSURE.get(pressure, DEFAULT_GROWTH),
                    'status': 'living', 'log': [{'age': age, 'event': 'rose', 'concentration': round(pressed, 6)}],
                }
                seated_count += 1
        else:
            villain['tier'] = tier
            villain['reach_m'] = tier * REACH_SPACINGS_PER_TIER * spacing
            if tier < hold:
                # Hysteresis: the band to stay is below the band to rise, so a reign is
                # long once established and nothing flickers across the line.
                villain['status'] = 'fallen'
                villain['fell_age'] = age
                villain['log'].append({'age': age, 'event': 'fell', 'concentration': round(pressed, 6)})
                tiers[rid] = tier * FRAGMENT_SHARE
                # Out of the standing set, into the record. This line used to be
                # `living.pop(rid)` alone, which threw away the status and the log entry
                # written immediately above it.
                # The claims are stamped with the holder's state as it changes, so a
                # consumer reads how hard a claim presses off the claim itself and needs
                # neither this module nor a join against the holder. That matters because
                # `key_locations` is a leaf package and cannot import any of this.
                for claim in villain.get('claims', []):
                    claim['holder_status'] = 'fallen'
                    claim['holder_fell_age'] = age
                    claim['influence'] = claim_influence(0)
                # The mark is taken before the roster entry leaves the standing set, so it
                # reads the villain as it was at the end of its reign rather than after.
                mark = fallen_mark(result, villain, age)
                if mark is not None:
                    marks.append(mark)
                fallen.append(living.pop(rid))
                seated_count -= 1
            else:
                living[rid] = villain

    block['version'] = VERSION
    block['tiers'] = {k: round(v, 9) for k, v in sorted(tiers.items())}
    # Appended and never pruned, exactly as `ruins` is. The world has a finite
    # population, so its dead are a knowable set rather than an unbounded stream --
    # which is the argument for keeping them properly, not the argument against.
    block['fallen'] = list(block.get('fallen') or []) + sorted(marks, key=lambda m: m['id'])
    # The living keep their existing order, by region anchor, so a world in which nobody
    # has fallen serialises exactly as it did before the fallen were kept at all. The
    # fallen are appended in the order they fell, ties by uid: a region can hold both a
    # fallen villain and the successor that replaced it, so region is no longer unique.
    block['people'] = ([living[k] for k in sorted(living)]
                       + sorted(fallen, key=lambda v: (v.get('fell_age', -1), v['uid'])))
    # The standing cast, not the block. This return flows into resolve_wars, whose
    # `_villain_pressure` reads `reach_m` with no status test of its own, and a fallen
    # villain still carries the reach it had when it fell. Returning the block here
    # would press cities together on behalf of someone who no longer stands.
    return standing(block['people'])


def causes(villains, city, radius):
    """A villain's share of a city's fate lottery, in the shape city_fate already takes.

    Appended, never inserted: the selector walk in city_fate is order-sensitive.
    """
    out = []
    for villain in standing(villains):
        # The tier test below also excludes the fallen, because a villain falls under
        # `hold` and `hold` is under SUPER_TIER -- but that is a coupling between two
        # constants, not a rule. A fallen villain reaching this lottery would move every
        # world, so the rule is stated rather than relied upon.
        if villain['tier'] < SUPER_TIER or not villain.get('reach_m'):
            continue
        angle = math.acos(max(-1., min(1., sum(a * b for a, b in zip(city['direction'], villain['direction'])))))
        distance = radius * angle
        spent = FALLOFF * villain['reach_m']
        if distance >= spent or city['uid'] == villain['seat_uid']:
            continue
        weight = VILLAIN_WEIGHT * villain['tier'] * (1. - distance / spent)
        if weight <= 0.:
            continue
        out.append(('villain_' + villain['growth'], weight,
                    f"A power seated at {villain['seat_uid']} reached this far and the city did not stand.",
                    {'villain_uid': villain['uid'], 'growth': villain['growth'], 'tier': round(villain['tier'], 6),
                     'distance_m': round(distance, 3), 'reach_m': round(villain['reach_m'], 3),
                     'school': villain.get('school')}))
    return out


def outlook(result, cfg, rise, density):
    """Where turmoil is concentrating, so a story layer need not guess.

    The counterpart of war_outlook: that one tells "they are coming" from "we once
    fought", this one tells a region that is about to produce something from one that is
    merely violent, and names who is stalled at the line.
    """
    reports_by_uid = {r['city_uid']: r for r in result.get('threat_assessments', {}).get('cities', [])}
    block = result.get('villains', {})
    tiers = block.get('tiers') or {}
    seated = {v['region'] for v in standing(block.get('people', []))}
    region_list = regions(result, result['effective_config']['globe_radius'], reports_by_uid)
    limit = ceiling(len(region_list), density)
    rows = []
    for region in region_list:
        rid = region['anchor']
        tier = tiers.get(rid, 0.)
        rows.append({
            'region': rid,
            'culture': region['id'],
            'concentration': round(concentration(region, reports_by_uid), 6),
            'tier': round(tier, 6),
            'to_threshold': round(max(0., SUPER_TIER - tier), 6),
            'seated': rid in seated,
            'stalled': rid not in seated and tier >= STALLED_TIER,
            'cities': len(region['cities']),
        })
    return {'rise': rise, 'ceiling': limit, 'standing': len(seated), 'regions': rows}


def promote(result, cfg, age, density):
    """Seat the world's most concentrated regions as the simulation ends.

    `advance` accumulates tier from turmoil, and a world only ever runs two age
    transitions inside a generation, so organic seating needs a `villain_rise` above
    0.834536 at seed 42 size 17 -- above most of the legal range, and unreachable at the
    default. Turning the rate up far enough to seat somebody would also make every
    intervening age lurch. So the rate stays the campaign ramp and this is the arrival:
    at the end of the run the regions that concentrated the most take the seats the
    ceiling allows, and a generated world always ends with antagonists in it.

    Deliberately NOT an accumulation. A promoted villain enters at exactly `SUPER_TIER`,
    the bottom of the band, because a villain that has just crossed the line is a threat
    that is growing rather than one that has arrived -- which is the whole pacing model.
    The tier it is given is the tier it would have to hold.

    Idempotent: a region that already holds a standing villain is skipped, and the ceiling
    counts who is already seated, so running this twice changes nothing. That matters
    because the hook fires on the final age of a generation AND on the final age of an
    `advance_age_request`, and a caller may advance a world that was already promoted.
    """
    block = result.get('villains')
    if block is None:
        # `villain_rise: 0` stays a real off switch: a world that never raised anybody
        # carries no block, and the end of the simulation must not invent one.
        return []
    reports_by_uid = {r['city_uid']: r for r in result.get('threat_assessments', {}).get('cities', [])}
    radius = result['effective_config']['globe_radius']
    spacing = cfg.settlement_spacing
    tiers = dict(block.get('tiers') or {})
    living = {v['region']: v for v in standing(block.get('people', []))}
    region_list = regions(result, radius, reports_by_uid)
    limit = ceiling(len(region_list), density)
    room = limit - sum(1 for v in living.values() if v['tier'] >= SUPER_TIER)
    if room <= 0:
        return []
    # Most concentrated first, ties by anchor so the order is a property of the world and
    # not of dictionary iteration.
    ranked = sorted((r for r in region_list if r['anchor'] not in living),
                    key=lambda r: (-concentration(r, reports_by_uid), r['anchor']))
    promoted = []
    for region in ranked[:room]:
        rid = region['anchor']
        seat, school, node_id = region['seat'], region['school'], region['node_id']
        pressed = concentration(region, reports_by_uid)
        pressure = dominant_pressure([reports_by_uid[c['uid']] for c in region['cities']
                                      if c.get('uid') in reports_by_uid])
        villain = {
            'uid': f'villain-{age}-{seat["node"]}',
            'region': rid, 'born_age': age,
            'seat_uid': seat['uid'], 'node': seat['node'], 'direction': list(seat['direction']),
            'school': school, 'held_nodes': [node_id] if node_id else [],
            'tier': SUPER_TIER, 'reach_m': SUPER_TIER * REACH_SPACINGS_PER_TIER * spacing,
            'growth': GROWTH_BY_PRESSURE.get(pressure, DEFAULT_GROWTH),
            'status': 'living',
            'log': [{'age': age, 'event': 'promoted', 'concentration': round(pressed, 6)}],
        }
        living[rid] = villain
        tiers[rid] = SUPER_TIER
        promoted.append(villain)
    if not promoted:
        return []
    block['version'] = VERSION
    block['tiers'] = {k: round(v, 9) for k, v in sorted(tiers.items())}
    fallen = [dict(v) for v in block.get('people', []) if not is_standing(v)]
    block['people'] = ([living[k] for k in sorted(living)]
                       + sorted(fallen, key=lambda v: (v.get('fell_age', -1), v['uid'])))
    return promoted


# --- what a seated villain builds -----------------------------------------------------

WELL_INTENSITY = 3.75     # a well is a source in its own right, not a marker
WELL_EDGE_INTENSITY = 2.
FOUND_SPACINGS = .8       # how far from its seat a villain plants its own ground
MIXED_FACTIONS = 3        # peoples a villain's own settlement draws from


def school_god(school):
    """The god of a known school, so a villain may be bound to an old one as well as new."""
    from .terrain_religion import catalogue
    for god in catalogue()['gods']:
        if god.get('family') == 'school' and school in god.get('school_affinity', []):
            return god['id']
    return None


def sink_well(result, cfg, villain, age):
    """A god-bound villain sinks a leyline well, which re-routes the tracks themselves.

    A key point is a source; a well is a source that is *joined*. The edges are the point:
    they change what the network carries between the villain's holdings, which a lone node
    cannot do. Edges index their endpoints by position, so they are appended with the
    node and never inserted.
    """
    from .terrain_magic import arc_frame
    school = villain.get('school')
    networks = result.get('magic', {}).get('networks', {})
    if not school or school not in networks or not villain.get('god'):
        return None
    net = copy.deepcopy(networks[school])
    well_id = f"well-{villain['uid']}"
    if any(n['id'] == well_id for n in net['nodes']):
        return None
    direction = list(villain['direction'])
    net['nodes'].append({'id': well_id, 'direction': direction, 'intensity': WELL_INTENSITY})
    index = len(net['nodes']) - 1
    held = {n for n in villain.get('held_nodes', [])}
    joined = []
    for position, node in enumerate(net['nodes'][:-1]):
        if node['id'] not in held:
            continue
        frame = arc_frame(direction, node['direction'])
        path = [[x * math.cos(frame[3] * k / 32) + t * math.sin(frame[3] * k / 32)
                 for x, t in zip(frame[0], frame[2])] for k in range(33)]
        edge_id = f"{well_id}-line-{len(joined)}"
        net['edges'].append({'from': index, 'to': position, 'path': path,
                             'id': edge_id, 'intensity': WELL_EDGE_INTENSITY})
        joined.append(edge_id)
    networks[school] = net
    villain['held_nodes'] = sorted(set(villain.get('held_nodes', [])) | {well_id})
    villain['well'] = {'node': well_id, 'school': school, 'god': villain['god'],
                       'lines': joined, 'age': age}
    villain.setdefault('log', []).append({'age': age, 'event': 'sank a well', 'school': school,
                                          'lines': len(joined)})
    return villain['well']


def claim_settlements(result, cfg, villain, age):
    """Ground a villain has taken for its own, mixed rather than of one people.

    Recorded as the villain's claim, not injected into `settlements.sites`: add_settlements
    places by suitability and only inherits identity from a survivor already at that node,
    so a site pushed into the survivor list would simply not be placed. Founding real
    cities means changing placement, which is a settlement-model change and not a tail on
    this one. The claim is what an orchestrator reads until then.
    """
    radius = result['effective_config']['globe_radius']
    cities = result.get('settlements', {}).get('sites', [])
    near = sorted(((radius * math.acos(max(-1., min(1., sum(a * b for a, b in zip(villain['direction'], c['direction']))))), c['uid'], c)
                   for c in cities), key=lambda r: (r[0], r[1]))
    mix = [c['population_profile'] for _, _, c in near[:MIXED_FACTIONS]]
    if not mix:
        return None
    claim = {'id': f"claim-{villain['uid']}", 'villain_uid': villain['uid'], 'age': age,
             'direction': list(villain['direction']), 'node': villain['node'],
             'kind': 'seat' if villain['tier'] >= SUPER_TIER * 1.5 else 'village',
             # Mixed by construction: a villain takes whoever is close, not whoever
             # shares its blood, which is what makes its holdings look wrong to everyone.
             'factions': sorted(set(mix)), 'drawn_from': [uid for _, uid, _ in near[:MIXED_FACTIONS]],
             'well': (villain.get('well') or {}).get('node'),
             # Stated on both sides so a reader never has to treat absence as a state.
             'holder_status': 'living', 'influence': 1.}
    villain.setdefault('claims', [])
    if not any(c['id'] == claim['id'] for c in villain['claims']):
        villain['claims'].append(claim)
    return claim


def build(result, cfg, age, villains):
    """Everything a seated villain puts on the ground this age."""
    built = []
    for villain in standing(villains):
        if villain['tier'] < SUPER_TIER:
            continue
        if not villain.get('god') and villain.get('school'):
            # Bound to an old god by the ground it holds, if no new one has taken it.
            villain['god'] = school_god(villain['school'])
        well = sink_well(result, cfg, villain, age)
        claim = claim_settlements(result, cfg, villain, age)
        if well or claim:
            built.append({'villain_uid': villain['uid'], 'well': bool(well), 'claim': bool(claim)})
    return built
