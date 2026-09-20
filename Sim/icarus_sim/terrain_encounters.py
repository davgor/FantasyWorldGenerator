"""What travelling thing is near here, at this time of year, and what is it.

This exists because travelling groups are the one kind of world content a consumer cannot
find by looking at a place. A city is at a node; a caravan is at a different node every
week. Answering "what might a party run into around here" means either scanning every
group's every leg, or having this.

It is an index, not a generator. There are no quests here, no objectives, no rewards and
no difficulty -- those belong to whatever eventually consumes it, and inventing them now
would be guessing at a contract that does not exist yet. What it guarantees is that the
question is answerable in one lookup rather than a scan.

Occupancy is recorded at **camps**, where a group dwells, not along legs. A group in
transit is derivable from its leg node path and its speed, and recording every node of
every leg would multiply the block by the length of the walking. Where a group is camped
is the thing you cannot derive.
"""
from time import perf_counter

VERSION = 1

# How dangerous a thing is to walk into, on the creature-tier rubric so it reads the same
# as `beast_nests`. Nomad bands have no tier of their own, so their classification supplies
# one: what a band will do to you is a property of what kind of band it is.
NOMAD_THREAT = {'merchants': 1, 'survivors': 1, 'wanderers': 2,
                'cultists': 3, 'deserters': 3, 'bandits': 4}
MONTHS = 12


def _month_of(day, days_per_year):
    return min(MONTHS - 1, int(day * MONTHS / days_per_year))


def _window_months(start, end, days_per_year):
    """Months a camp is occupied, wrapping across the turn of the year."""
    if start is None or end is None:
        return []
    first = _month_of(start % days_per_year, days_per_year)
    last = _month_of(end % days_per_year, days_per_year)
    if first <= last:
        return list(range(first, last + 1))
    return list(range(first, MONTHS)) + list(range(0, last + 1))


def _nomad_entry(band):
    return {
        'group_uid': band['uid'], 'source': 'nomads', 'kind': band['classification'],
        'disposition': band['disposition'],
        'threat_tier': NOMAD_THREAT.get(band['classification'], 2),
        'size': band['size'], 'carries': list(band.get('carries') or []),
        'seeks': list(band.get('seeks') or []), 'host_uid': None,
        'god_id': band.get('god_id'), 'speed_m_per_day': band['speed_m_per_day'],
        'column_length_m': band['column_length_m'],
    }


def _beast_entry(group):
    return {
        'group_uid': group['uid'], 'source': 'beast_movements',
        'kind': group['species_id'], 'disposition': group['disposition'],
        'threat_tier': group['tier'], 'size': group['size'],
        # A herd is worth something to whoever can take it; a swarm is worth avoiding.
        'carries': ['hides', 'meat'] if group['kind'] == 'animal' else [],
        'seeks': {'migratory': ['pasture'], 'irruptive': ['anything'],
                  'follower': ['the group ahead'], 'drifter': ['rest']}.get(group['movement'], []),
        'host_uid': group.get('host_uid'), 'god_id': None,
        'speed_m_per_day': group['speed_m_per_day'],
        'column_length_m': group['column_length_m'],
    }


def add_encounters(result, cfg):
    """Index every travelling group by where and when it can be met."""
    if not cfg.world_recipe or cfg.phase < 16:
        return result
    started = perf_counter()
    from .terrain_astrology import DAYS_PER_YEAR
    entries, occupancy = [], []
    sources = [(result.get('nomads', {}).get('groups', []) or [], _nomad_entry),
               (result.get('beast_movements', {}).get('groups', []) or [], _beast_entry)]
    for groups, make in sources:
        for group in groups:
            if not group.get('camps'):
                continue
            index = len(entries)
            entries.append(make(group))
            for camp in group['camps']:
                arrive, depart = camp.get('arrive_day'), camp.get('depart_day')
                occupancy.append({
                    'entry': index, 'node': camp['node'], 'camp_id': camp['id'],
                    'camp_kind': camp['kind'], 'from_day': arrive, 'to_day': depart,
                    'months': _window_months(arrive, depart, DAYS_PER_YEAR),
                })

    by_month = {str(m): [] for m in range(MONTHS)}
    by_node = {}
    for i, record in enumerate(occupancy):
        for month in record['months']:
            by_month[str(month)].append(i)
        by_node.setdefault(str(record['node']), []).append(i)

    result['encounters'] = {
        'version': VERSION, 'entries': entries, 'occupancy': occupancy,
        'by_month': by_month, 'by_node': {k: by_node[k] for k in sorted(by_node, key=int)},
        'method': 'One entry per travelling group and one occupancy record per camp it holds, indexed by month '
                  'and by terrain node so a consumer answers "what is near here, and when" in a lookup rather '
                  'than a scan over every leg of every group. Both nomad bands and travelling creatures are '
                  'indexed through the same shape. Threat is on the creature-tier rubric, one to five; a band '
                  'takes its tier from its classification, because what a band will do to you is a property of '
                  'what kind of band it is.',
        'limits': 'An index, not a quest generator: no objectives, stakes, rewards or difficulty, because the '
                  'consumer that would define them does not exist yet. Occupancy covers camps only -- a group '
                  'in transit is derivable from its leg node path and its speed, and indexing every node of '
                  'every leg would multiply the block by the length of the walking. Stranded groups appear with '
                  'their start camp and no schedule, so a null day window means "here, always" rather than '
                  '"here, never". Nothing here accounts for two groups meeting each other.',
    }
    elapsed = (perf_counter() - started) * 1000
    result['timing_ms']['encounters'] = elapsed
    result['timing_ms']['total'] += elapsed
    return result
