"""What the travelling groups do to the world they walk through.

Four write-backs, in the order they are safe to apply:

  cultist leylines   a pilgrimage circuit is worship, and worship on charged ground leaves
                     a mark. Every cult edits its network directly, known school or hidden
  raid pressure      a lair within strike of a town is a thing the town knows about, and it
                     belongs beside the nest, ley and war pressures already recorded
  caravan trade      a road a caravan actually rides carries more than a road nobody walks
  survivor camps     a band that reached safety and stayed is where a hamlet comes from

There used to be a ley split here, and it rested on a premise that was tested and is false.
It held that `advance_age_request` rejects any leyline edit whose school is outside
`KNOWN_SCHOOLS`, so a blood cult writing its own node would be refused at the next age
boundary; hidden-school intent therefore went into a `pending_ley_edits` block that a
corruption-side applier was supposed to drain. No applier was ever written.

The gate at `terrain_history.py:741` validates only the caller-supplied
`body['leyline_edits']` of an age-advance request. It never looks at the world's own
networks. `validate_age_world` was run against a world carrying a hidden-school node, both
newly created and intensified, and accepted both - it asserts the twelve networks exist and
never asks which network a node sits in. This pass writes through `edit_network` directly
and never passes through that validator at all, exactly as the known-school half already
did. The queue was working around a gate that did not apply to it, so it is gone.

The invariant that does hold, and that the code enforces rather than merely states: a cult
may only **deepen** a hidden node that already exists, never create one. Only the corruption
API creates a node in a hidden network. That is `current = next((n for n in net['nodes'] if
n['id'] == basis_node), None)` followed by `if current is None: continue`, plus the
`if not net or not basis_node: continue` above it, which now covers hidden schools too.

One number is worth recording, because it is the strongest argument against ever rebuilding
the queue: the direct write is `current['intensity'] * 1.18` - absolute, shrine count
ignored - while the queued value was `DEVOTION_GAIN * shrines`. On a node at 3.0 with three
shrines those are 3.54 and 0.54, and `edit_network` SETS intensity rather than adding to it,
so an applier reading the queue the obvious way would have cut the node by 82% in the act of
deepening it.
"""
from time import perf_counter
from .terrain_leyline_history import KNOWN_SCHOOLS, edit_network

VERSION = 1

# What a circuit leaves behind. A pilgrimage does not rip the land open; it deepens a
# groove that was already there, so the gain is a fraction of the node's existing charge.
DEVOTION_GAIN = .18
INTENSITY_CEILING = 4.
# A band's contribution to a town's sense of threat, per band, before distance falls off.
RAID_WEIGHT = {'bandits': .22, 'deserters': .14}
STRIKE_SPACINGS = 2.


def _clamp_intensity(value):
    # `x - 0.0` rather than max(0., x): max(0., -0.0) returns 0.0 and flips a sign bit that
    # a byte comparison catches, for no gain.
    return min(INTENSITY_CEILING, value - 0.0)


def apply_cultist_leylines(result, cfg):
    """Let cults deepen the ground they walk. Deepen only: corruption is what creates."""
    bands = [b for b in (result.get('nomads', {}).get('groups', []) or [])
             if b['classification'] == 'cultists' and b.get('school')]
    if not bands or not cfg.magic_enabled:
        return result, 0, 0
    networks = result.get('magic', {}).get('networks', {}) or {}
    direct = hidden = 0
    # Sorted so two bands touching the same node cannot produce two different worlds
    # depending on which happened to be placed first.
    for band in sorted(bands, key=lambda b: b['uid']):
        school = band['school']
        basis_node = band['basis'].get('ley_node_id')
        net = networks.get(school)
        # A claim-derived or shrine-derived band carries no `ley_node_id`, so there is
        # nothing to deepen. This guard used to cover only known schools, which is why the
        # hidden branch could queue an entry naming no node at all.
        if not net or not basis_node:
            continue
        # Deepen, never create. Only the corruption API seats a node in a hidden network.
        current = next((n for n in net['nodes'] if n['id'] == basis_node), None)
        if current is None:
            continue
        lifted = _clamp_intensity(current['intensity'] * (1. + DEVOTION_GAIN))
        if lifted == current['intensity']:
            continue
        networks[school] = edit_network(net, node_id=basis_node, intensity=lifted)
        if school in KNOWN_SCHOOLS:
            direct += 1
        else:
            hidden += 1
    return result, direct, hidden


def apply_raid_pressure(result, cfg):
    """Record raiders beside the nest, ley and war pressures a town already tracks."""
    from .terrain_nests import distance
    assessments = result.get('threat_assessments')
    sites = result.get('settlements', {}).get('sites', [])
    if not assessments or not sites:
        return result, 0
    radius = result['effective_config']['globe_radius']
    reach = STRIKE_SPACINGS * float(cfg.settlement_spacing)
    by_uid = {s['uid']: s for s in sites}
    raiders = [b for b in (result.get('nomads', {}).get('groups', []) or [])
               if b['classification'] in RAID_WEIGHT]
    touched = 0
    for city in assessments.get('cities', []):
        site = by_uid.get(city.get('city_uid'))
        if not site or not site.get('direction'):
            continue
        pressure = 0.
        named = []
        for band in raiders:
            span = distance(tuple(site['direction']), tuple(band['direction']), radius)
            if span > reach:
                continue
            # Falls off with distance: a lair on the doorstep is not the same as one at the
            # edge of the reach, and a flat term made every town in a region read alike.
            pressure += RAID_WEIGHT[band['classification']] * (1. - span / reach)
            named.append(band['uid'])
        city['nomad_pressure'] = round(pressure - 0.0, 6)
        if named:
            city['nomad_contributors'] = sorted(named)
            city['regional_threat'] = round(min(1., city.get('regional_threat', 0.) + pressure), 6)
            touched += 1
    return result, touched


def apply_caravan_trade(result, cfg):
    """A road a caravan rides is busier than one nobody walks."""
    routes = (result.get('roads', {}) or {}).get('routes', [])
    if not routes:
        return result, 0
    ridden = {}
    for band in (result.get('nomads', {}).get('groups', []) or []):
        if band['classification'] != 'merchants':
            continue
        walked = set()
        for leg in band.get('legs', []):
            walked.update(leg['nodes'])
        for index, route in enumerate(routes):
            shared = walked.intersection(route.get('nodes', []))
            if len(shared) < 2:
                continue
            ridden.setdefault(index, []).append((band['uid'], len(shared)))
    for index, riders in ridden.items():
        route = routes[index]
        # Plain accumulation, not sum(): a native port would otherwise need a compensated
        # accumulator here for a handful of terms.
        carried = 0.
        for _, shared in riders:
            carried += shared
        route['caravan_riders'] = sorted(uid for uid, _ in riders)
        route['caravan_throughput'] = round(carried / max(1, len(route.get('nodes', []) or [1])), 6)
    return result, len(ridden)


def seed_survivor_camps(result, cfg):
    """Mark where a refugee band settled, without pretending it is a town yet.

    A survivor band that reached its refuge and stopped is exactly how a hamlet starts. It
    is recorded as a candidate rather than founded outright, because founding one here
    would mean re-running settlement generation after every downstream block has already
    read the settlements it produced -- which invalidates the world to add one hamlet.
    The existing founding fields are used so a later pass can adopt these directly.
    """
    candidates = []
    for band in (result.get('nomads', {}).get('groups', []) or []):
        if band['classification'] != 'survivors' or band.get('route_status') != 'routed':
            continue
        terminal = next((c for c in band['camps'] if c['kind'] == 'terminal'), None)
        if terminal is None:
            continue
        candidates.append({
            'id': 'settlement-candidate-' + band['uid'], 'from_band': band['uid'],
            'node': terminal['node'], 'direction': list(terminal['direction']),
            'migration_source_node': band['node'],
            'migration_distance_m': round(band.get('round_length_m', 0.), 6),
            'population_estimate': band['size'],
            'reason': 'Refugees from ' + str(band['basis'].get('ruin_uid')) + ' who reached '
                      + str(band['basis'].get('refuge_uid')) + ' and stayed.',
        })
    if candidates:
        result['settlement_candidates'] = sorted(candidates, key=lambda c: c['id'])
    return result, len(candidates)


def absorb_survivor_camps(result, survivors, age):
    """Grow the refuge a survivor band walked to, instead of founding a town on top of it.

    **Owner ruling, 2026-09-21.** A candidate does not name free ground. It names the
    refuge city's own node, 4 of 4 across two worlds and true by construction:
    `terrain_nomad_routes._flight` routes the band to the node of the site whose uid is
    `basis['refuge_uid']`, and `seed_survivor_camps` records the candidate at
    `terminal['node']`. "Adopt the candidate as a settlement" would therefore found a
    second settlement on a standing city. The band did not reach empty ground and start a
    hamlet; it reached a town and stopped, so the town gets bigger. The rejected
    alternative was recording the camp one cell short of the refuge, which buys free
    ground at the price of a resolution-dependent placement constant -- 8 km at size 17,
    under 1 km at size 129 -- which is the exact failure this subsystem exists to avoid.

    Called at the age boundary with the cities that survived it, so the filter the card
    asked for is the argument rather than a lookup: a refuge that fell this age absorbs
    nobody and the band's arrival is simply not recorded.

    **The absorbed count has to ride `CARRIED_SURVIVOR_KEYS`, not `population_estimate`.**
    The founding seam worked out on the card does not transfer here, and this is the part
    that had to be re-verified rather than assumed: `add_settlements` re-derives
    `population_estimate` from the population budget on every rebuild
    (`residents = allowance//len(members) + ...`), so a number added to a survivor row
    before `rebuild_tail` is overwritten by the very rebuild it was meant to ride. What
    survives is `absorbed_refugees`, which the budget adds back after the capacity split.

    Idempotent across advances by band uid, which is `nomad-<age>-<node>` and so is never
    reused by a later age. It has to be: `seed_survivor_camps` only assigns the block when
    it has candidates, so a world can carry a previous advance's list unchanged, and
    absorbing it again would breed people every age out of one migration.
    """
    candidates = result.get('settlement_candidates') or []
    if not candidates:
        return 0, 0
    bands = {band['uid']: band for band in ((result.get('nomads') or {}).get('groups') or [])}
    standing = {site['uid']: site for site in survivors if 'uid' in site}
    absorbed = 0
    people = 0
    for candidate in sorted(candidates, key=lambda c: c['id']):
        band = bands.get(candidate.get('from_band'))
        if band is None:
            continue
        refuge_uid = (band.get('basis') or {}).get('refuge_uid')
        site = standing.get(refuge_uid)
        if site is None:
            continue
        taken = list(site.get('absorbed_bands') or [])
        if band['uid'] in taken:
            continue
        count = int(candidate.get('population_estimate') or 0)
        if count <= 0:
            continue
        site['absorbed_bands'] = sorted(taken + [band['uid']])
        site['absorbed_refugees'] = int(site.get('absorbed_refugees') or 0) + count
        candidate['absorbed_age'] = age
        candidate['absorbed_into'] = refuge_uid
        absorbed += 1
        people += count
    return absorbed, people


def apply_nomad_effects(result, cfg):
    """Every write-back, in a fixed order, reported rather than silent."""
    if not cfg.world_recipe or cfg.phase < 16 or not result.get('nomads'):
        return result
    started = perf_counter()
    result, direct, hidden = apply_cultist_leylines(result, cfg)
    result, towns = apply_raid_pressure(result, cfg)
    result, roads = apply_caravan_trade(result, cfg)
    result, seeds = seed_survivor_camps(result, cfg)
    result['nomads']['effects'] = {
        'version': VERSION, 'leyline_edits': direct, 'leyline_edits_hidden': hidden,
        'towns_under_raid_pressure': towns, 'roads_ridden': roads,
        'settlement_candidates': seeds,
        'method': 'Every cult deepens its circuit node directly through edit_network, hidden school or known, by '
                  'the same multiplicative lift. A cult can only deepen a node that already exists; only the '
                  'corruption API creates one in a hidden network, so a hidden lift counts separately. Raiders add a '
                  'distance-weighted nomad_pressure beside the nest, ley and war pressures a town already '
                  'tracks. Roads a caravan actually rides record their riders and a throughput share. Refugee '
                  'bands that reached safety are recorded as settlement candidates.',
        'limits': 'A cult deepens ground, it does not open it: a band naming a node that does not exist in its '
                  'network writes nothing, and a band with no ley node in its basis writes nothing at all. This '
                  'pass runs on every nomad_request as well as every age advance, so a node a cult holds ratchets '
                  'toward the 4.0 ceiling across calls rather than settling. Survivor camps are candidates, not '
                  'settlements: founding one here would mean re-running settlement generation after every '
                  'downstream block has read the settlements it produced. Caravan throughput is a share of '
                  'nodes ridden, not a modelled cargo volume, and nothing consumes it yet. Raid pressure is '
                  'added after the threat assessment was evaluated, so it widens regional_threat without '
                  'having influenced anything that already read it.',
    }
    elapsed = (perf_counter() - started) * 1000
    result['timing_ms']['nomad_effects'] = elapsed
    result['timing_ms']['total'] += elapsed
    return result
