"""What the travelling groups do to the world they walk through.

Four write-backs, in the order they are safe to apply:

  cultist leylines   a pilgrimage circuit is worship, and worship on charged ground leaves
                     a mark. Cults of a known school edit the network directly; cults of a
                     hidden god cannot, so they queue their intent instead
  raid pressure      a lair within strike of a town is a thing the town knows about, and it
                     belongs beside the nest, ley and war pressures already recorded
  caravan trade      a road a caravan actually rides carries more than a road nobody walks
  survivor camps     a band that reached safety and stayed is where a hamlet comes from

The ley split is not a stylistic choice. `advance_age_request` rejects any leyline edit
whose school is outside `KNOWN_SCHOOLS`, so a blood cult writing its own node would be
refused at the next age boundary. Hidden-school intent therefore goes into a generic
`pending_ley_edits` block that the corruption pass drains, and it is deliberately NOT
nested inside `nomads` so that the applier never has to understand what a nomad is.

**That applier contract was agreed with the super-villains session, which has since
closed.** It will never be confirmed by its author. What a future reader would need to
re-derive if `terrain_corruption` disagrees: entries are keyed by node id and never by
index, because a node removed between write and apply renumbers every later edge; only
hidden schools appear, because known ones are written directly here; intensity is bounded
zero to four; and the applier sorts by `(school, id)` before applying so that two bands
requesting in a different order cannot produce two different worlds.
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
    """Let cults deepen the ground they walk, or queue the intent when they cannot."""
    bands = [b for b in (result.get('nomads', {}).get('groups', []) or [])
             if b['classification'] == 'cultists' and b.get('school')]
    if not bands or not cfg.magic_enabled:
        return result, 0, 0
    networks = result.get('magic', {}).get('networks', {}) or {}
    pending = result.get('pending_ley_edits', []) or []
    direct = queued = 0
    # Sorted so two bands touching the same node cannot produce two different worlds
    # depending on which happened to be placed first.
    for band in sorted(bands, key=lambda b: b['uid']):
        school = band['school']
        node_ids = [c['id'] for c in band.get('camps', []) if c['kind'] == 'shrine']
        basis_node = band['basis'].get('ley_node_id')
        if school not in KNOWN_SCHOOLS:
            # Only the corruption pass may touch a hidden network, so record the intent.
            pending.append({
                'school': school, 'kind': 'intensity', 'id': basis_node,
                'intensity': round(DEVOTION_GAIN * max(1, len(node_ids)), 6),
                'requested_by': band['uid'], 'god_id': band.get('god_id'),
                'age': band['origin']['age'],
            })
            queued += 1
            continue
        net = networks.get(school)
        if not net or not basis_node:
            continue
        current = next((n for n in net['nodes'] if n['id'] == basis_node), None)
        if current is None:
            continue
        lifted = _clamp_intensity(current['intensity'] * (1. + DEVOTION_GAIN))
        if lifted == current['intensity']:
            continue
        networks[school] = edit_network(net, node_id=basis_node, intensity=lifted)
        direct += 1
    if pending:
        # Emitted only when non-empty, so its presence means something is genuinely queued
        # rather than "here is a buffer, interpret it".
        result['pending_ley_edits'] = sorted(pending, key=lambda e: (e['school'], str(e['id'])))
    return result, direct, queued


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


def apply_nomad_effects(result, cfg):
    """Every write-back, in a fixed order, reported rather than silent."""
    if not cfg.world_recipe or cfg.phase < 16 or not result.get('nomads'):
        return result
    started = perf_counter()
    result, direct, queued = apply_cultist_leylines(result, cfg)
    result, towns = apply_raid_pressure(result, cfg)
    result, roads = apply_caravan_trade(result, cfg)
    result, seeds = seed_survivor_camps(result, cfg)
    result['nomads']['effects'] = {
        'version': VERSION, 'leyline_edits': direct, 'leyline_edits_queued': queued,
        'towns_under_raid_pressure': towns, 'roads_ridden': roads,
        'settlement_candidates': seeds,
        'method': 'Cults of a known school deepen their circuit node directly through edit_network; cults of a '
                  'hidden god queue the same intent into pending_ley_edits for the corruption pass, because '
                  'advance_age_request refuses a leyline edit outside KNOWN_SCHOOLS. Raiders add a '
                  'distance-weighted nomad_pressure beside the nest, ley and war pressures a town already '
                  'tracks. Roads a caravan actually rides record their riders and a throughput share. Refugee '
                  'bands that reached safety are recorded as settlement candidates.',
        'limits': 'The pending_ley_edits applier contract was agreed with a session that has since closed and '
                  'will never be confirmed by its author; the module docstring records what a future reader '
                  'would need to re-derive if terrain_corruption disagrees. Survivor camps are candidates, not '
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
