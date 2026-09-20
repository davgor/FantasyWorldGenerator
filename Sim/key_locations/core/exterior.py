"""Exterior plans: the visible arrangement on the ground at a key location.

A marker tells an engine *where* a place is. It says nothing about what standing there looks
like, and every location rendering as one prop is what makes a generated world read as a map
rather than a place. So each location gets a plan in the same shape the city, hamlet and
castle planners already emit — `plots` in a local metre frame with rotation, plot footprint,
dimensions, ground elevation and foundation bottom — so the importer that already reads
`city_plans` speaks this without a second code path.

Arrangement is the interesting part. A barrow field is mounds scattered on a rise; a stone
circle is stones on a radius; a mine head is a headframe with its spoil downslope; a
monastery is a courtyard. Seven rules cover all of it, and which one an archetype uses is
catalogue data rather than code.

Every tier gets a plan, including tier-0 markers, where the plan is a single plot. That is
deliberate: one contract and one importer path is worth more than the handful of bytes a
special case would save.

**Ground elevation is sampled bilinearly from the `height` layer.** The generator's own
planners use `terrain_detail.HeightField`, which adds micro-relief this package cannot import.
At plot scale on a multi-kilometre raster the difference is below the cell, so
`ground_elevation_m` and `foundation_bottom_m` come out near-equal and a consumer should
conform plots to its own landscape rather than trusting them to describe local relief. That is
declared in `limits` rather than hidden.

Pure: no filesystem, no network, no engine, no generator imports.
"""
import math

from . import shaping
from . import shaping
from .grid import cell_of_direction

ARRANGEMENTS = ('single', 'ring', 'scatter', 'row', 'courtyard', 'terrace', 'mouth')
GOLDEN_ANGLE = 2.39996322972865332
SURFACE_POSTS = 17


def _sample_height(point, offset_x_m, offset_z_m, layers, n, radius):
    """Height at a local metre offset from a site, bilinear over the raster.

    Local metres convert to a fraction of a cell through the raster's own spacing, so this
    stays correct at every world size and raster without carrying a metres-per-cell constant.
    """
    grid = layers.get('height')
    if not grid:
        return 0.
    cell_m = 2 * math.pi * radius / max(1, n - 1)
    base_x, base_z = cell_of_direction(point, n)
    fx = base_x + offset_x_m / cell_m
    fz = base_z + offset_z_m / cell_m
    x0, z0 = int(math.floor(fx)), int(math.floor(fz))
    tx, tz = fx - x0, fz - z0
    def at(x, z):
        return grid[max(0, min(n - 1, z))][x % (n - 1)]
    top = at(x0, z0) * (1 - tx) + at(x0 + 1, z0) * tx
    bottom = at(x0, z0 + 1) * (1 - tx) + at(x0 + 1, z0 + 1) * tx
    return float(top * (1 - tz) + bottom * tz)


def _corners(x, z, width, depth, degrees):
    rad = math.radians(degrees)
    c, s = math.cos(rad), math.sin(rad)
    for u, v in ((-width / 2, -depth / 2), (width / 2, -depth / 2),
                 (width / 2, depth / 2), (-width / 2, depth / 2)):
        yield x + u * c - v * s, z + u * s + v * c


def _positions(arrangement, count, spread_m, draw, slope_bearing):
    """Local metre offsets and rotations for `count` parts under one arrangement rule."""
    if count <= 0:
        return []
    if arrangement == 'single':
        return [(0., 0., draw.random() * 360.)]
    if arrangement == 'ring':
        # Evenly spaced with a small jitter, so a circle reads as raised by hand not stamped.
        step = 360. / count
        out = []
        for i in range(count):
            angle = math.radians(i * step + (draw.random() - .5) * step * .3)
            r = spread_m * (.9 + draw.random() * .2)
            out.append((r * math.cos(angle), r * math.sin(angle), math.degrees(angle) + 90.))
        return out
    if arrangement == 'scatter':
        # Golden-angle spiral, so parts never clump the way uniform random does at low counts.
        out = []
        for i in range(count):
            angle = i * GOLDEN_ANGLE + draw.random() * .4
            r = spread_m * math.sqrt((i + .5) / count)
            out.append((r * math.cos(angle), r * math.sin(angle), draw.random() * 360.))
        return out
    if arrangement == 'row':
        out, step = [], (spread_m * 2) / max(1, count - 1) if count > 1 else 0.
        bearing = math.radians(slope_bearing)
        for i in range(count):
            d = -spread_m + step * i
            out.append((d * math.cos(bearing), d * math.sin(bearing), slope_bearing))
        return out
    if arrangement == 'courtyard':
        # A perimeter facing inward, with the first part held back as the gate side.
        out = []
        for i in range(count):
            angle = math.radians(360. * i / count)
            out.append((spread_m * math.cos(angle), spread_m * math.sin(angle),
                        math.degrees(angle) + 180.))
        return out
    if arrangement == 'terrace':
        # Stepped along the fall of the ground: working sites follow the slope, not a grid.
        out, bearing = [], math.radians(slope_bearing)
        for i in range(count):
            d = spread_m * (i / max(1, count - 1) - .5) * 2
            lateral = (draw.random() - .5) * spread_m * .5
            out.append((d * math.cos(bearing) - lateral * math.sin(bearing),
                        d * math.sin(bearing) + lateral * math.cos(bearing), slope_bearing))
        return out
    if arrangement == 'mouth':
        # One part on the entrance and the rest fanned across the approach in front of it.
        out = [(0., 0., slope_bearing)]
        for i in range(1, count):
            angle = math.radians(slope_bearing + (i - count / 2) * 28.)
            r = spread_m * (.5 + draw.random() * .5)
            out.append((r * math.cos(angle), r * math.sin(angle), math.degrees(angle) + 180.))
        return out
    raise ValueError(f'unknown arrangement {arrangement!r}; expected one of {ARRANGEMENTS}')


def _slope_bearing(point, layers, n, radius):
    """Downhill direction in the local frame, so working sites can follow the fall."""
    step = 2 * math.pi * radius / max(1, n - 1) * .5
    east = _sample_height(point, step, 0., layers, n, radius) - _sample_height(point, -step, 0., layers, n, radius)
    north = _sample_height(point, 0., step, layers, n, radius) - _sample_height(point, 0., -step, layers, n, radius)
    if abs(east) < 1e-9 and abs(north) < 1e-9:
        return 0.
    return math.degrees(math.atan2(-north, -east)) % 360.


def plan(site, kit, parts, layers, n, radius, draw):
    """One exterior plan for one location, in the shape the city importer already reads."""
    point = tuple(site['direction'])
    bearing = _slope_bearing(point, layers, n, radius)
    # First pass: choose positions and collect the ground each part moves. Elevations are not
    # resolved yet, because a grave marker standing on a barrow has to sit on the barrow, and
    # the barrow does not exist until every shaping entry is known.
    placements, shapes, extent = [], [], 0.
    for entry in kit['parts']:
        part = parts[entry['part']]
        low, high = entry.get('count', [1, 1])
        count = draw.randint(int(low), int(high))
        spread = float(entry.get('spread_m', kit.get('spread_m', 12.)))
        for x, z, degrees in _positions(entry.get('arrangement', kit['arrangement']),
                                        count, spread, draw, bearing):
            placements.append((entry, part, x, z, degrees % 360.))
            extent = max(extent, abs(x) + part['plot_m']['width'], abs(z) + part['plot_m']['depth'])
            if part.get('shaping'):
                shapes.append(dict(part['shaping'], x_m=round(x, 2), z_m=round(z, 2),
                                   rotation_degrees=round(degrees % 360., 4), part=part['id']))

    def base(local_x, local_z):
        return _sample_height(point, local_x, local_z, layers, n, radius)

    centre_base = base(0., 0.)

    plots = []
    for entry, part, x, z, degrees in placements:
        footprint = part['plot_m']
        ground = [shaping.shaped_height(shapes, cx, cz, base(cx, cz), centre_base)
                  for cx, cz in _corners(x, z, footprint['width'], footprint['depth'], degrees)]
        plots.append({
            'id': f'plot-{len(plots)}',
            'building_id': part['id'], 'name': part['name'],
            'kind': entry.get('kind', 'structure'), 'phase': entry.get('phase', 0),
            'x_m': round(x, 2), 'z_m': round(z, 2),
            'rotation_degrees': round(degrees, 4),
            'ground_elevation_m': round(max(ground), 4),
            'foundation_bottom_m': round(min(ground), 4),
            'plot_m': footprint, 'dimensions_m': part['dimensions_m'],
            'road_access': [round(x, 2), round(z, 2)],
            'workers': 0, 'beds': 0,
        })
    half = max(extent, 6.)
    terrain = {
        'cell_m': round(2 * half / (SURFACE_POSTS - 1), 4),
        'size': SURFACE_POSTS - 1,
        'bounds_m': [-round(half, 2), -round(half, 2), round(half, 2), round(half, 2)],
        'shaping': shapes,
        'relief_m': shaping.relief(shapes, half, base, centre_base),
        'surface': shaping.surface(shapes, half, SURFACE_POSTS, base, centre_base),
    }
    return {
        'location_id': site['id'], 'kind': site['kind'], 'family': site['family'],
        'tier': site['tier'], 'kit_id': kit['id'], 'version': 1,
        'status': 'complete' if plots else 'empty',
        'arrangement': kit['arrangement'],
        'origin': {'direction': list(point), 'height_m': site['height_m'], 'node': site['node']},
        'bounds_m': {'width': round(extent * 2, 2), 'depth': round(extent * 2, 2)},
        'slope_bearing_degrees': round(bearing, 2),
        'terrain': terrain,
        'plots': plots,
        'stats': {'plots': len(plots), 'parts': len({p['building_id'] for p in plots}),
                  'shaping': len(shapes)},
    }
