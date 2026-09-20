"""Key locations: the charged places a finished world's terrain and history imply.

Called once when the world generator finishes, with the world as plain JSON. It reads
terrain, hydrology, ley networks, roads, settlements, cultures, ruins, nests and religion,
and writes nothing back. Its output is the ``key_locations`` block: caves, mines, barrows,
mausoleums, shrines, watchtowers, ley nexuses, dragon lairs, drowned villages and wonders,
each with a tier, a state, an occupant, a threat rating and — for tier 2 — an interior
chamber graph.

The design move is that a location is not a noun from a list. It is
``(archetype, tier, state, occupant, origin)``. "Forgotten fortress" is a fortress that is
ruined and empty; "dungeon" is any tier-2 complex whose occupant is hostile. State and
occupant are *derived* from what the simulation already recorded — whether the founding
culture survives, whether a ruin or a nest sits nearby, how unstable the local weave is,
how many ages have passed — so the world does the authoring and nothing is hand-written as
"forgotten".

Determinism: every draw comes from ``child_seed(world seed, 'keyloc-...')``, so the same
world gives the same locations byte for byte. Isolation: the generator core imports only
:func:`attach`; a raising revision yields a failed block, not a crashed world, and
``FANTASY_WORLD_KEY_LOCATIONS=0`` leaves the key absent entirely.
"""
import os

from .catalogue import load as load_catalogue
from .core import composition, fields, interiors, naming, placement, succession, world as readers
from .core.grid import cell_of_direction, great_circle_m, node_index, offset as grid_offset
from .seeds import rng

VERSION = 1
_EMPTY_NAMES = {'natural': {}, 'variant_asset': {}, 'variant_name': {}}
ENV_SWITCH = 'FANTASY_WORLD_KEY_LOCATIONS'
NEAR_RUIN_CELLS = 3.
NEAR_NEST_CELLS = 2.
NEAR_VILLAIN_CELLS = 3.
REMOTE_CELLS = 4.
UNSTABLE_PERCENTILE = .8
# Spacing is authored in cells, but of a FIXED reference raster, never the raster in hand.
# Tied to the actual raster, "two cells apart" would mean 25 km at size 17 and 6 km at size
# 129 - the same world would space its caves differently depending only on how finely it was
# sampled. Against a reference raster it is a physical distance that scales with the world
# and is invariant to resolution. Where the real raster is coarser than the spacing, the node
# grid binds first, which is honest: you cannot place two distinct points inside one cell.
REFERENCE_RASTER = 65
METHOD = ('Archetypes are catalogue data, not code. Each declares the layers it requires, the layers that make one '
          'cell better than another, how many of itself belong in a thousand square kilometres of land, and how far '
          'apart two may stand. Requirements are percentile-relative to each world own distribution with an absolute '
          'floor, so a world with no volcanism gets no lava tubes rather than its least-quiet hillside. Candidates are '
          'thinned greedily over jittered suitability with per-archetype and per-family spacing and a clearance from '
          'anywhere people already live. Ground already carrying a ruin, nest, shrine, college or landmark is left to '
          'the module that placed it. State and occupant are then derived from the surrounding record - a nearby ruin '
          'ages a site, remoteness empties it, an unstable weave corrupts it, a nest nearby fills it - and a '
          'succession pass lets something else move into what the builders left. Tier 2 sites gain an interior '
          'chamber graph.')
LIMITS = ('Static proposals about ground, not a populated world. Nothing here acts, spawns, patrols, guards or holds '
          'treasure. Interiors are graphs - depth, role, rough size, connections - with no metre positions, no '
          'contents and no encounters; a real interior layout is a later phase. Tier is physical scale and how much '
          'the place still needs building out, never danger: read threat for that. T0 chain furniture (waystones, '
          'boundary stones, beacon lines) is not placed yet and arrives with the composition pass.')


def enabled():
    return os.environ.get(ENV_SWITCH, '1') != '0'


def attach_plans(world):
    """The exterior plans for a world whose `key_locations` block is already attached.

    A second call rather than part of the first, because the plans are a separate top-level
    block: `city_plans`, `hamlet_plans` and `castle_plans` all sit at the top level, and a
    consumer scanning for plan blocks would not find these nested inside a sited-feature one.
    """
    if not enabled():
        return None
    block = world.get('key_locations')
    if not block or block.get('status') != 'ok':
        return None
    try:
        from .exteriors import generate as generate_plans
        return generate_plans(world, block)
    except Exception as exc:  # noqa: BLE001 - report, never crash the world
        return {'version': 1, 'status': 'failed', 'error': f'{type(exc).__name__}: {exc}'}


def attach(world):
    """The one call the generator makes. Never raises; a failure is a reported block."""
    if not enabled():
        return None
    try:
        return generate(world)
    except Exception as exc:  # noqa: BLE001 - the whole point is to report, not to crash the world
        return {'version': VERSION, 'status': 'failed', 'error': f'{type(exc).__name__}: {exc}'}


def _validate(world):
    if not isinstance(world, dict) or type(world.get('config', {}).get('seed')) is not int:
        raise ValueError('key locations need a finished world with an integer config.seed')
    if not world.get('layers', {}).get('height'):
        raise ValueError('key locations need the height layer; generate a world past the terrain stages')
    if not world.get('effective_config', {}).get('globe_radius'):
        raise ValueError('key locations need effective_config.globe_radius, the resolved physical radius')


def _referenced_layers(document):
    names = set()
    for archetype in document['archetypes']:
        for term in archetype.get('requires', []):
            names.add(term['layer'])
        for term in archetype['prefers']:
            names.add(term['layer'])
    return names


def _context(world, cell, layers, spacing, hazard_cut, ages, nests_by_node):
    ruin_gap = layers['ruin_distance'][cell['z']][cell['x']]
    nest_gap = layers['nest_distance'][cell['z']][cell['x']]
    town_gap = layers['settlement_distance'][cell['z']][cell['x']]
    hazard = layers.get('magic_hazard')
    return {
        'near_ruin': ruin_gap <= NEAR_RUIN_CELLS * spacing,
        'near_nest': nest_gap <= NEAR_NEST_CELLS * spacing,
        'remote': town_gap >= REMOTE_CELLS * spacing,
        'unstable': hazard is not None and hazard_cut is not None and hazard[cell['z']][cell['x']] >= hazard_cut,
        'ages': ages,
        'nest_tier': nests_by_node.get(cell['node'], {}).get('tier'),
        'near_villain': layers['villain_distance'][cell['z']][cell['x']] <= NEAR_VILLAIN_CELLS * spacing,
    }


def _biome_names(world):
    """Index maps for the two biome catalogues, read from the world's own `terrain` block.

    The world publishes all 13 natural biomes and all 156 magical variants with their names
    and asset ids, so a consumer never has to import the generator's catalogue to say what
    ground a location stands on. That is why this reads the world rather than `icarus_sim`.
    """
    terrain = world.get('terrain') or {}
    natural = {i: b.get('name') for i, b in enumerate(terrain.get('natural_biomes') or [])}
    variants = terrain.get('magical_biomes') or []
    return {
        'natural': natural,
        'variant_asset': {i: v.get('asset_id') for i, v in enumerate(variants)},
        'variant_name': {i: v.get('name') for i, v in enumerate(variants)},
    }


def _environment(cell, layers, names):
    """The ground a location stands on, for whoever has to dress it.

    All of it is already in the layers; the point is that anything building art should not
    have to re-sample a raster it otherwise never touches, nor know that `biome_variant` is
    an index into a 156-entry core-by-school catalogue. The same karst cave is a different
    art set in tundra and in rainforest, and a magically mutated biome changes it again.
    """
    def at(name):
        grid = layers.get(name)
        return None if grid is None else grid[cell['z']][cell['x']]

    natural, variant, coastal = at('natural_biome'), at('biome_variant'), at('coastal_exposure')
    natural_index = None if natural is None else int(natural)
    variant_index = None if variant is None or variant < 0 else int(variant)
    return {
        'natural_biome': natural_index,
        'natural_biome_name': names['natural'].get(natural_index),
        'biome_variant': variant_index,
        'variant_asset_id': names['variant_asset'].get(variant_index),
        'variant_name': names['variant_name'].get(variant_index),
        'temperature_c': None if at('temperature') is None else round(float(at('temperature')), 2),
        'moisture': None if at('moisture') is None else round(float(at('moisture')), 4),
        'slope': None if at('slope') is None else round(float(at('slope')), 4),
        'coastal': bool(coastal is not None and coastal > .05),
    }


def _origin(world, cell, layers, nearest_ruin, nearest_city, ages):
    """Who built it and when, read off the nearest recorded people rather than invented."""
    source = nearest_ruin if nearest_ruin is not None else nearest_city
    dominant = layers.get('dominant_magic')
    school = None
    if dominant is not None:
        index = int(dominant[cell['z']][cell['x']])
        order = world.get('magic', {}).get('school_order') or []
        if 0 <= index < len(order):
            school = order[index]
    return {
        'age': int(source.get('founded_age', 0)) if source else 0,
        'culture_id': (source or {}).get('source_culture'),
        'civilization_id': (source or {}).get('civilization_id'),
        'ruin_id': nearest_ruin.get('id') if nearest_ruin else None,
        'school': school,
        'ages_since': max(0, ages - int((source or {}).get('founded_age', 0))),
    }


def generate(world, document=None):
    """The key locations for a finished world. ``document`` overrides the packaged catalogue."""
    _validate(world)
    seed = readers.world_seed(world)
    document = document or load_catalogue()
    n = readers.size(world)
    radius = readers.radius_m(world)
    spacing = readers.spacing_m(world) or (2 * 3.141592653589793 * radius / max(1, n - 1))
    reference_cell = 2 * 3.141592653589793 * radius / (REFERENCE_RASTER - 1)
    ages = readers.final_age(world)

    derived = fields.derive(world, readers)
    layers = {**world.get('layers', {}), **derived}
    cells_by_domain = {domain: readers.cells(world, domain) for domain in ('land', 'water', 'ocean', 'lake', 'any')}
    land_km2 = sum(c['area_m2'] for c in cells_by_domain['land']) / 1e6
    norms = placement.normalisers(layers, _referenced_layers(document), cells_by_domain['land'])

    hazard = layers.get('magic_hazard')
    hazard_cut = None
    if hazard is not None and cells_by_domain['land']:
        hazard_cut = placement.percentile([hazard[c['z']][c['x']] for c in cells_by_domain['land']],
                                          UNSTABLE_PERCENTILE)

    ruin_records, city_records = readers.ruins(world), readers.cities(world)
    nests_by_node = {int(nest['node']): nest for nest in readers.nests(world) if nest.get('node') is not None}
    gods = {god['id']: god for god in world.get('religion', {}).get('gods', [])}
    biome_names = _biome_names(world)
    claimed = set(readers.claimed_nodes(world))
    settled = readers.settled_directions(world)
    succession_table = document.get('succession', {})

    sites, diagnostics = [], []
    family_taken = {}
    used_names = set()
    by_id = {a['id']: a for a in document['archetypes']}
    # Chain and cluster archetypes are placed by the composition pass, not scattered: road
    # furniture belongs on the road at metre intervals and a siege camp belongs beside the
    # fort it besieged, and neither survives being dropped on the best-scoring cell.
    scattered = [a for a in document['archetypes'] if a.get('placement', 'node') == 'node']
    for archetype in sorted(scattered, key=lambda a: (-a['tier'], a['id'])):
        cells = cells_by_domain[archetype['domain']]
        family = document['families'][archetype['family']]
        resolved = dict(archetype)
        resolved['spacing_m'] = archetype.get('spacing_m', archetype.get('spacing_cells', 0.) * reference_cell)
        resolved['settlement_clearance_m'] = archetype.get(
            'settlement_clearance_m', archetype.get('settlement_clearance_cells', 0.) * reference_cell)
        resolved['family_spacing_m'] = family.get('family_spacing_cells', 0.) * reference_cell
        draw = rng(seed, 'keyloc-place-' + archetype['id'])
        wanted = placement.budget(resolved, land_km2, draw)
        candidates = placement.eligible(resolved, layers, cells)
        if not candidates or wanted <= 0:
            diagnostics.append({'archetype': archetype['id'], 'placed': 0, 'wanted': wanted,
                                'candidates': len(candidates),
                                'reason': 'no ground in this world satisfies the requirements' if not candidates
                                          else 'the world is too small to support one'})
            continue
        taken = family_taken.setdefault(archetype['family'], [])
        chosen = placement.select(resolved, layers, candidates, norms, radius, draw, wanted,
                                  settled=settled, claimed=claimed, family_taken=taken)
        for entry in chosen:
            cell = entry['cell']
            claimed.add(cell['node'])
            taken.append(cell['direction'])
            sites.append(_record(world, archetype, resolved, entry, layers, spacing, radius, seed, ages,
                                 hazard_cut, nests_by_node, ruin_records, city_records, gods,
                                 succession_table, used_names, biome_names))
        diagnostics.append({'archetype': archetype['id'], 'placed': len(chosen), 'wanted': wanted,
                            'candidates': len(candidates),
                            'reason': 'placed' if len(chosen) == wanted else 'spacing and clearance left room for fewer'})
    context = {'radius': radius, 'layers': layers, 'n': n, 'world': world, 'reader': readers,
               'land_cells': cells_by_domain['land']}

    def compose(archetype_id, point, height, cell_x, cell_z, node, placement_kind, site_id, draw, extra_name=None):
        archetype = by_id[archetype_id]
        context_cell = {'x': cell_x, 'z': cell_z, 'node': node, 'direction': point, 'height_m': height}
        return _build(world, archetype, {'cell': context_cell, 'suitability': 0.0, 'suitability_factors': {}},
                      layers, spacing, radius, seed, ages, hazard_cut, nests_by_node, ruin_records,
                      city_records, gods, succession_table, used_names, placement_kind, site_id, draw,
                      extra_name, biome_names)

    def make_chain_site(spec, point, height, chain_key, distance, index, draw, anchor):
        x, z = cell_of_direction(point, n)
        site_id = f"keyloc-{spec['archetype']}-{chain_key}-{distance}"
        return compose(spec['archetype'], point, height, x, z, node_index(x, z, n), 'path', site_id, draw,
                       {'ordinal': composition.ordinal(index),
                        'near': naming.short_name((anchor or {}).get('name'))})

    def place_near(spec, anchor, gap, draw, index):
        """A cluster member at a real offset from its anchor, between cells if it must be.

        Snapping to a node would put a camp meant to be 1.5 km from the wall wherever the
        raster happens to allow, which on a coarse one is ten times too far or nowhere. Walk
        the offset instead and take the ground that is actually there.
        """
        archetype = by_id[spec['archetype']]
        origin = tuple(anchor['direction'])
        water = layers.get('water_type')
        wants_land = archetype['domain'] == 'land'
        for attempt in range(8):
            bearing = (index * 2.399963 + attempt * .7854 + draw.random() * .5) % (2 * 3.141592653589793)
            point = grid_offset(origin, bearing, gap, radius)
            x, z = cell_of_direction(point, n)
            if wants_land and water is not None and water[z][x] != 0:
                continue
            node = node_index(x, z, n)
            site_id = f"keyloc-{spec['archetype']}-{anchor['node']}-{int(round(gap))}-{index}"
            return compose(spec['archetype'], point, float(layers['height'][z][x]), x, z, node,
                           'cluster', site_id, draw)
        return None

    chains, chain_members = composition.build_chains(document.get('chains', []), sites, context,
                                                     make_chain_site, lambda domain: rng(seed, domain))
    clusters, cluster_members = composition.build_clusters(document.get('clusters', []), sites, context,
                                                           place_near, lambda domain: rng(seed, domain))
    sites += chain_members + cluster_members
    sites.sort(key=lambda s: (s['family'], s['kind'], s['links']['chain'] or '',
                              s['links']['chain_index'] if s['links']['chain_index'] is not None else -1,
                              s['id']))
    for spec in document.get('chains', []) + document.get('clusters', []):
        produced = sum(1 for s in sites if s['kind'] == spec['archetype']
                       and (s['links']['chain'] or s['links']['cluster']))
        diagnostics.append({'archetype': spec['archetype'], 'placed': produced, 'wanted': produced,
                            'candidates': produced,
                            'reason': f"composed by {spec['id']}" if produced
                                      else f"nothing in this world to run {spec['id']} along"})
    return {'version': VERSION, 'status': 'ok', 'catalogue_revision': document['revision'],
            'catalogue_count': len(document['archetypes']),
            'summary': _summary(sites), 'sites': sites, 'chains': chains, 'clusters': clusters,
            'families': document['families'], 'diagnostics': diagnostics,
            'method': METHOD, 'limits': LIMITS}


def _record(world, archetype, resolved, entry, layers, spacing, radius, seed, ages, hazard_cut,
            nests_by_node, ruin_records, city_records, gods, succession_table, used_names, names=None):
    cell = entry['cell']
    draw = rng(seed, f'keyloc-site-{archetype["id"]}-{cell["node"]}')
    return _build(world, archetype, entry, layers, spacing, radius, seed, ages, hazard_cut, nests_by_node,
                  ruin_records, city_records, gods, succession_table, used_names, 'node',
                  f'keyloc-{archetype["id"]}-{cell["node"]}', draw, names=names)


def _build(world, archetype, entry, layers, spacing, radius, seed, ages, hazard_cut, nests_by_node,
           ruin_records, city_records, gods, succession_table, used_names, placement_kind, site_id,
           draw, extra_name=None, names=None):
    """One site record, however it was positioned.

    Scatter, chain and cluster members differ only in where they stand and what id they carry;
    everything downstream - state, occupant, succession, threat, name, interior - is decided the
    same way, so a consumer never has to ask which pass produced a location.
    """
    cell = entry['cell']
    point = cell['direction']
    context = _context(world, cell, layers, spacing, hazard_cut, ages, nests_by_node)
    nearest_ruin = naming.nearest(ruin_records, point, lambda a, b: great_circle_m(a, b, radius))
    nearest_city = naming.nearest(city_records, point, lambda a, b: great_circle_m(a, b, radius))
    origin = _origin(world, cell, layers, nearest_ruin if context['near_ruin'] else None, nearest_city, ages)
    state = succession.derive_state(archetype, context, draw)
    occupant = succession.derive_occupant(archetype, state, context, draw)
    near_record = nearest_ruin if context['near_ruin'] and nearest_ruin else nearest_city
    god = sorted(gods)[draw.randrange(len(gods))] if gods else None
    name_context = {'near': naming.short_name((near_record or {}).get('name')),
                    'culture': (near_record or {}).get('civilization_id'),
                    'school': origin['school'],
                    'god': gods.get(god, {}).get('name') if god else None}
    if extra_name:
        name_context.update({k: v for k, v in extra_name.items() if v})
    site = {
        'id': site_id, 'placement': placement_kind,
        'kind': archetype['id'], 'name': naming.unique_name(archetype, name_context, draw, used_names),
        'family': archetype['family'], 'tier': archetype['tier'],
        'state': state, 'occupant': occupant,
        'node': cell['node'], 'x': cell['x'], 'z': cell['z'],
        'direction': list(point), 'height_m': round(cell['height_m'], 2),
        'layer': 'surface', 'domain': archetype['domain'],
        'suitability': entry['suitability'], 'suitability_factors': entry['suitability_factors'],
        'origin': origin, 'environment': _environment(cell, layers, names or _EMPTY_NAMES),
        'links': {'chain': None, 'chain_index': None, 'cluster': None, 'anchor': None},
        'asset_id': f'marker.key_location.{archetype["id"]}',
        'reason': archetype['reason'],
    }
    succeeded = succession.succeed(site, succession_table, context, draw)
    site['succession'] = succeeded
    site['threat'] = succession.threat(site, context)
    site['interior'] = interiors.build(archetype, site['state'], draw) if archetype['tier'] == 2 else None
    return site


def _summary(sites):
    by_tier, by_family, by_state, by_occupant = {}, {}, {}, {}
    for site in sites:
        by_tier[str(site['tier'])] = by_tier.get(str(site['tier']), 0) + 1
        by_family[site['family']] = by_family.get(site['family'], 0) + 1
        by_state[site['state']] = by_state.get(site['state'], 0) + 1
        by_occupant[site['occupant']] = by_occupant.get(site['occupant'], 0) + 1
    return {'sites': len(sites), 'by_tier': by_tier, 'by_family': by_family,
            'by_state': by_state, 'by_occupant': by_occupant,
            'dungeons': sum(1 for s in sites if s['tier'] >= 2 and s['occupant'] in succession.HOSTILE)}


def summary_lines(block):
    """Short human lines for logs and the lab status."""
    if block.get('status') != 'ok':
        return [f"key locations failed: {block.get('error')}"]
    s = block['summary']
    tiers = ' · '.join(f"T{k} {v}" for k, v in sorted(s['by_tier'].items()))
    return [f"{s['sites']} key locations ({tiers}) · {s['dungeons']} occupied complexes",
            ' · '.join(f'{k} {v}' for k, v in sorted(s['by_family'].items()))]
