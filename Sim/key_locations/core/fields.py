"""Derived per-cell fields the generator does not publish but archetypes need.

The world exports distance fields for the things *it* cared about — ``freshwater_distance``,
``wetland_distance`` — but not distance to a road, a settlement or a ruin, because nothing
upstream had to ask. A watchtower that wants to sit above a road, a hermitage that wants to
be far from anyone, and a barrow field that wants to ring a fallen city all need exactly
those, so they are computed here and merged into the layer dictionary under their own names.

Distances come from a multi-source breadth-first sweep in cell steps rather than exact
great-circle metres to every source. At 6 km per cell the difference is far below the
thresholds an archetype expresses, and the sweep is linear where the exact form is
quadratic. Grids wrap at the seam because column ``n - 1`` duplicates column ``0``.

Pure: no filesystem, no network, no engine, no generator imports.
"""
from collections import deque
import math

from .grid import cell as grid_cell

DIAGONAL = math.sqrt(2.)
STEPS = ((-1, -1, DIAGONAL), (0, -1, 1.), (1, -1, DIAGONAL),
         (-1, 0, 1.), (1, 0, 1.),
         (-1, 1, DIAGONAL), (0, 1, 1.), (1, 1, DIAGONAL))
UNREACHED = float('inf')


def _blank(n, value):
    return [[value] * n for _ in range(n)]


def _seal_seam(grid, n):
    """Column ``n - 1`` mirrors column ``0``; poles are one node, so their rows are flat."""
    for row in grid:
        row[-1] = row[0]
    grid[0] = [grid[0][0]] * n
    grid[-1] = [grid[-1][0]] * n
    return grid


def distance_field(sources, n, spacing_m, ceiling_m=None):
    """Metres from every cell to the nearest source cell, by weighted cell-step sweep.

    ``sources`` is an iterable of ``(x, z)``. With no sources every cell reads as the
    ceiling, which makes ``prefers`` terms neutral rather than undefined — a world with no
    roads should not make every cell equally *good* for a tollhouse, it should make the
    archetype's road term carry no information.
    """
    limit = ceiling_m if ceiling_m is not None else spacing_m * n
    grid = _blank(n, UNREACHED)
    queue = deque()
    for x, z in sources:
        if not 0 <= z < n:
            continue
        column = x % (n - 1)
        if grid[z][column] != 0.:
            grid[z][column] = 0.
            queue.append((column, z))
    while queue:
        x, z = queue.popleft()
        base = grid[z][x]
        for dx, dz, weight in STEPS:
            nz = z + dz
            if not 0 <= nz < n:
                continue
            nx = (x + dx) % (n - 1)
            stepped = base + weight
            if stepped < grid[nz][nx]:
                grid[nz][nx] = stepped
                queue.append((nx, nz))
    for z in range(n):
        for x in range(n):
            steps = grid[z][x]
            grid[z][x] = limit if steps == UNREACHED else min(limit, steps * spacing_m)
    return _seal_seam(grid, n)


def _cells_of(records, n):
    for record in records:
        if record.get('x') is not None and record.get('z') is not None:
            yield int(record['x']), int(record['z'])
        elif record.get('node') is not None:
            yield grid_cell(int(record['node']), n)


def _route_cells(routes, n):
    for route in routes:
        for node in route.get('nodes', []):
            yield grid_cell(int(node), n)


def frontier_field(region_grid, n):
    """How close a cell is to a border: 1 where owners differ across a step, 0 deep inside.

    Territory in this world is a raster frontier rather than a polygon, so a boundary stone
    has to be told where the frontier *is*. Unowned ground (``-1``) does not count as a
    different owner, or every coastline would read as a political border.
    """
    grid = _blank(n, 0.)
    if not region_grid:
        return grid
    for z in range(1, n - 1):
        for x in range(n - 1):
            mine = region_grid[z][x]
            if mine < 0:
                continue
            for dx, dz, _ in STEPS:
                nz, nx = z + dz, (x + dx) % (n - 1)
                if not 0 <= nz < n:
                    continue
                other = region_grid[nz][nx]
                if other >= 0 and other != mine:
                    grid[z][x] = 1.
                    break
    return _seal_seam(grid, n)


def coastal_water_field(layers, water_type, name, n):
    """The best value of a water layer among a land cell's neighbours; 0 inland and at sea.

    A shore building is a land feature whose reason for existing is out at sea. A whaling
    station stands on land and lives off ``fishing_productivity``, which is an ocean
    quantity: measured on seed 42 at sizes 17, 33, 65, 129 and 257, it is **identically 0.0
    on every land cell** and runs 0.12 to 1.0 on water. So a ``domain: land`` archetype
    gating on it is unplaceable by construction, at every raster, forever — the question it
    asks cannot be answered where it is allowed to stand.

    Answering it with the neighbouring water instead is a different query, not a lowered
    threshold, which is why this is a derived layer rather than a tuned constant. A coastal
    land cell takes the best of the water it touches; a cell touching no water reads 0, and
    so does a water cell, so the field is only ever meaningful inside the ``land`` domain.

    ``max`` rather than a mean on purpose: a station is sited for the richest water in reach
    of a boat, and averaging over eight neighbours would penalise exactly the ragged inlet a
    whaler wants. Grids wrap at the seam because column ``n - 1`` duplicates column ``0``.
    """
    source = layers.get(name)
    grid = _blank(n, 0.)
    if not source or not water_type:
        return grid
    for z in range(1, n - 1):
        for x in range(n - 1):
            if water_type[z][x] != 0.:
                continue
            best = 0.
            for dx, dz, _ in STEPS:
                nz, nx = z + dz, (x + dx) % (n - 1)
                if not 0 <= nz < n:
                    continue
                if water_type[nz][nx] != 0.:
                    best = max(best, source[nz][nx])
            grid[z][x] = best
    return _seal_seam(grid, n)


def derive(world, readers):
    """The derived layer dictionary for a finished world, keyed by the names archetypes use."""
    n = readers.size(world)
    spacing = readers.spacing_m(world) or (2 * math.pi * readers.radius_m(world) / max(1, n - 1))
    settled = list(_cells_of(readers.cities(world), n)) + list(_cells_of(readers.hamlets(world), n)) \
        + list(_cells_of(readers.fortresses(world), n)) + list(_cells_of(readers.ports(world), n))
    return {
        'road_distance': distance_field(_route_cells(readers.routes(world), n), n, spacing),
        'settlement_distance': distance_field(settled, n, spacing),
        'ruin_distance': distance_field(_cells_of(readers.ruins(world), n), n, spacing),
        'nest_distance': distance_field(_cells_of(readers.nests(world), n), n, spacing),
        'villain_distance': distance_field(_cells_of(readers.villain_holdings(world), n), n, spacing),
        'frontier': frontier_field(readers.layer(world, 'culture_region'), n),
        # What the sea next door is worth, carried onto the shore so a land archetype can
        # ask about it. See `coastal_water_field`: the underlying layer is zero on every
        # land cell at every raster measured, so this is the only form of the question a
        # `domain: land` archetype can actually ask.
        'coastal_fishing_productivity': coastal_water_field(
            world.get('layers', {}), readers.layer(world, 'water_type'), 'fishing_productivity', n),
    }
