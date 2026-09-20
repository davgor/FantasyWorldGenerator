"""Pure reads of a finished world's JSON.

Nothing here is written back and only documented export fields are consulted, so a saved
``world.json`` serves as well as a live generation result. Every function tolerates a
missing block: a world generated to an earlier stage simply offers fewer archetypes ground
to stand on, which is the behaviour we want rather than a crash.
"""
from .grid import cell_area_m2, direction, node_index

WATER_DRY = 0


def world_seed(world):
    return int(world['config']['seed'])


def size(world):
    """Raster edge length. ``config.size`` is authoritative; the height grid confirms it."""
    height = world.get('layers', {}).get('height')
    if height:
        return len(height)
    return int(world['config']['size'])


def radius_m(world):
    """Physical globe radius in metres.

    Always the resolved value: ``config.globe_radius`` is design space and is off by the
    world-scale factor, which is the trap that makes every metre threshold meaningless.
    """
    effective = world.get('effective_config') or world.get('config', {})
    return float(effective['globe_radius'])


def spacing_m(world):
    return float(world.get('spacing_m') or 0.)


def layer(world, name):
    return world.get('layers', {}).get(name)


def has_layers(world, names):
    layers = world.get('layers', {})
    return all(name in layers for name in names)


def ages(world):
    return world.get('history', {}).get('ages', [])


def final_age(world):
    return len(ages(world))


def ruins(world):
    return world.get('ruins', [])


def cities(world):
    return world.get('settlements', {}).get('sites', [])


def hamlets(world):
    return world.get('humans', {}).get('hamlets', [])


def fortresses(world):
    return world.get('humans', {}).get('fortresses', [])


def cultures(world):
    return world.get('humans', {}).get('cultures', [])


def colleges(world):
    return world.get('magic', {}).get('colleges', [])


def ports(world):
    return world.get('fisheries', {}).get('ports', [])


def nests(world):
    return world.get('beast_nests', {}).get('sites', [])


def religion_sites(world):
    return world.get('religion', {}).get('sites', [])


def villain_holdings(world):
    """Where seated villains stand, plus the settlements they have claimed.

    ``villains.works`` records only that a well or claim happened; the positions live on the
    villains themselves and on their claims, so both are read here.
    """
    result = []
    for villain in world.get('villains', {}).get('people', []):
        if villain.get('direction'):
            result.append(villain)
        for claim in villain.get('claims', []):
            if claim.get('direction'):
                result.append(claim)
    return result


def routes(world):
    return world.get('roads', {}).get('routes', [])


def wars(world):
    return [war for age in ages(world) for war in age.get('wars', [])]


def surviving_culture_ids(world):
    return {culture['id'] for culture in cultures(world) if culture.get('id')}


WATER_OCEAN = 1
WATER_LAKE = 2
DOMAINS = ('land', 'water', 'ocean', 'lake', 'any')


def _in_domain(value, domain):
    if domain == 'any' or value is None:
        return True
    if domain == 'land':
        return value == WATER_DRY
    if domain == 'water':
        return value != WATER_DRY
    if domain == 'ocean':
        return value == WATER_OCEAN
    if domain == 'lake':
        return value == WATER_LAKE
    raise ValueError(f'unknown domain {domain!r}; expected one of {DOMAINS}')


def cells(world, domain='land'):
    """Every placeable cell in a domain, with its node id, direction and area.

    Poles are excluded: they are single degenerate nodes covering a whole latitude band, and
    a mausoleum on the north pole is a bug that looks like content. The seam column is
    excluded by construction because ``x`` stops at ``n - 2``.
    """
    n = size(world)
    radius = radius_m(world)
    water = layer(world, 'water_type')
    height = layer(world, 'height')
    if not height:
        return []
    result = []
    for z in range(1, n - 1):
        area = cell_area_m2(z, n, radius)
        for x in range(n - 1):
            if not _in_domain(None if water is None else water[z][x], domain):
                continue
            result.append({'x': x, 'z': z, 'node': node_index(x, z, n),
                           'direction': direction(x, z, n), 'area_m2': area,
                           'height_m': float(height[z][x])})
    return result


def land_cells(world):
    return cells(world, 'land')


def land_area_km2(world):
    return sum(c['area_m2'] for c in land_cells(world)) / 1e6


def settled_directions(world):
    """Where people already are, for clearance. Cities, hamlets, fortresses, ports, colleges."""
    result = []
    for group in (cities(world), hamlets(world), fortresses(world), ports(world), colleges(world)):
        for record in group:
            if record.get('direction'):
                result.append(tuple(record['direction']))
    return result


def claimed_nodes(world):
    """Nodes already carrying a point feature, so key locations never double-book ground.

    Ruins, nests, religion sites, colleges and landmarks all publish their own records; this
    generator reads and respects them rather than re-placing the same ideas under new names.
    """
    result = set()
    for group in (ruins(world), nests(world), religion_sites(world), colleges(world),
                  world.get('regions', {}).get('landmarks', [])):
        for record in group:
            node = record.get('node')
            if node is not None:
                result.add(int(node))
    return result
