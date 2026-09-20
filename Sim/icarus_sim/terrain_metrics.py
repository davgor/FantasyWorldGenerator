"""Pure elevation and relief statistics for a generated world.

No filesystem, no network, no engine, and nothing here mutates its inputs. Every
function takes plain grids and scalars so it can be exercised without running a
generation, and `elevation_metrics` reads a world document without writing to it.

These are descriptive measurements of the emitted heightfield, not claims about
geology. Areas are latitude-weighted reference-sphere footprints on the same
convention as `terrain_area.land_area`: the duplicate longitude column is excluded
and each pole contributes once.
"""
import math
from .terrain_globe import direction, sample
from .terrain_erosion import sphere_grid
# One definition of the Nyquist mirror, next to the rest of the scale arithmetic.
from .terrain_scale import resolved_octaves


def weighted_nodes(grid, radius):
    """(value, area_m2) for every unique node. Poles once; duplicate seam excluded."""
    points, areas, _ = sphere_grid(len(grid), radius)
    return [(grid[z][x], areas[i]) for i, (x, z) in enumerate(points)]


def weighted_percentile(pairs, fraction):
    """Area-weighted percentile of (value, weight) pairs. fraction is 0..1."""
    if not pairs:
        return None
    ordered = sorted(pairs)
    total = sum(w for _, w in ordered)
    if total <= 0:
        return ordered[len(ordered)//2][0]
    target = fraction*total
    seen = 0.
    for value, weight in ordered:
        seen += weight
        if seen >= target:
            return value
    return ordered[-1][0]


def land_statistics(height, radius, sea_level):
    """Area-weighted elevation distribution above and below sea level, in metres."""
    nodes = weighted_nodes(height, radius)
    land = [(v, w) for v, w in nodes if v > sea_level]
    total = sum(w for _, w in nodes)
    land_area = sum(w for _, w in land)
    values = [v for v, _ in nodes]
    stats = {'land_fraction': land_area/total if total else 0.,
             'land_km2': land_area/1e6, 'total_km2': total/1e6,
             'min_m': min(values) if values else 0., 'max_m': max(values) if values else 0.,
             'total_relief_m': (max(values)-min(values)) if values else 0.,
             'land_nodes': len(land)}
    if land:
        stats.update({'land_mean_m': sum(v*w for v, w in land)/land_area,
                      'land_p50_m': weighted_percentile(land, .5),
                      'land_p90_m': weighted_percentile(land, .9),
                      'land_p99_m': weighted_percentile(land, .99),
                      'land_max_m': max(v for v, _ in land)})
        # The hierarchy ratio: 1.0 is a featureless platform, higher means the top
        # decile of land stands meaningfully above the median. This is the number
        # that stays flat when relief is raised without raising orogeny.
        stats['land_p90_over_p50'] = stats['land_p90_m']/stats['land_p50_m'] if stats['land_p50_m'] else 0.
    return stats


def hypsometry(height, radius, bins=20):
    """Area-weighted elevation histogram: (low_m, high_m, area_km2) per bin."""
    nodes = weighted_nodes(height, radius)
    values = [v for v, _ in nodes]
    low, high = min(values), max(values)
    if high <= low:
        return [(low, high, sum(w for _, w in nodes)/1e6)]
    width = (high-low)/bins
    buckets = [0.]*bins
    for value, weight in nodes:
        buckets[min(bins-1, int((value-low)/width))] += weight
    return [(low+i*width, low+(i+1)*width, area/1e6) for i, area in enumerate(buckets)]


def window_angle(radius, size, window_m):
    """Resolve a requested window to a ring angle, and say what actually happened.

    A window below one cell cannot be measured on this grid: the ring would sample
    inside a single bilinear cell and report that cell's gradient as if it were a
    local drop. Callers must not paper over that -- a silently widened window
    answers a different question from the one asked.

    Returns (angle_rad, effective_m, status) where status is 'resolved',
    'below_grid' (widened to one cell) or 'above_cap' (narrowed to 1/16 of a
    great circle, past which 'local' relief is just global relief).
    """
    step = math.pi/(size-1)
    cap = math.pi/8
    wanted = window_m/radius
    if wanted < step:
        return step, step*radius, 'below_grid'
    if wanted > cap:
        return cap, cap*radius, 'above_cap'
    return wanted, window_m, 'resolved'


def relief_grid(height, radius, window_m):
    """Per-node local relief: max-minus-min over two sampled rings plus the centre.

    A ring sample, like the TPI in `terrain_globe.measure_globe`, not a disc scan.
    It is O(1) per node and can miss a peak that falls between rings, so read it as
    a lower bound on true neighbourhood relief.
    """
    n = len(height)
    outer, _, _ = window_angle(radius, n, window_m)
    grid = []
    for z in range(n):
        row = []
        for x in range(1 if z in (0, n-1) else n-1):
            p = direction(x, z, n)
            norm = math.hypot(p[0], p[2])
            e = (-p[2]/norm, 0, p[0]/norm) if norm > 1e-10 else (1, 0, 0)
            v = (p[1]*e[2]-p[2]*e[1], p[2]*e[0]-p[0]*e[2], p[0]*e[1]-p[1]*e[0])
            seen = [height[z][x]]
            for theta in (outer/2, outer):
                c, s = math.cos(theta), math.sin(theta)
                for j in range(8):
                    ca, sa = math.cos(j*math.pi/4), math.sin(j*math.pi/4)
                    seen.append(sample(height, tuple(p[k]*c+(e[k]*ca+v[k]*sa)*s for k in range(3))))
            row.append(max(seen)-min(seen))
        row = row*n if z in (0, n-1) else row+[row[0]]
        grid.append(row)
    return grid


def local_relief(height, radius, sea_level, window_m):
    """Area-weighted local-relief distribution over land, in metres."""
    _, effective, status = window_angle(radius, len(height), window_m)
    head = {'window_m': window_m, 'effective_window_m': effective, 'window_status': status}
    grid = relief_grid(height, radius, window_m)
    points, areas, _ = sphere_grid(len(height), radius)
    land = [(grid[z][x], areas[i]) for i, (x, z) in enumerate(points) if height[z][x] > sea_level]
    if not land:
        return {**head, 'p50_m': 0., 'p90_m': 0., 'p99_m': 0., 'max_m': 0.}
    return {**head,
            'p50_m': weighted_percentile(land, .5), 'p90_m': weighted_percentile(land, .9),
            'p99_m': weighted_percentile(land, .99), 'max_m': max(v for v, _ in land)}


def slope_statistics(slope, height, radius, sea_level, steep_degrees=38.):
    """Area-weighted land slope distribution. steep_degrees matches the exposed-rock gate."""
    points, areas, _ = sphere_grid(len(height), radius)
    land = [(slope[z][x], areas[i]) for i, (x, z) in enumerate(points) if height[z][x] > sea_level]
    if not land:
        return {'p50_deg': 0., 'p90_deg': 0., 'p99_deg': 0., 'steep_land_fraction': 0.}
    total = sum(w for _, w in land)
    return {'p50_deg': weighted_percentile(land, .5), 'p90_deg': weighted_percentile(land, .9),
            'p99_deg': weighted_percentile(land, .99),
            'max_deg': max(v for v, _ in land),
            'steep_land_fraction': sum(w for v, w in land if v >= steep_degrees)/total}


def orogenic_fraction(interaction, height, radius, sea_level, relief_m, share=.10):
    """Fraction of land carrying tectonic uplift above `share` of one relief unit.

    `interaction` is the blended boundary term from `terrain_tectonics.relief_at`,
    already in metres. Land above the threshold is orogenic belt; the remainder is
    craton. This is the metric the epoch count is chosen against, so it must move
    when `tectonic_epochs` moves or the epoch accumulation is not doing anything.
    """
    points, areas, _ = sphere_grid(len(height), radius)
    land = [(abs(interaction[z][x]), areas[i]) for i, (x, z) in enumerate(points)
            if height[z][x] > sea_level]
    total = sum(w for _, w in land)
    if not total:
        return {'orogenic_land_fraction': 0., 'craton_land_fraction': 0., 'threshold_m': 0.}
    threshold = share*relief_m
    belt = sum(w for v, w in land if v > threshold)
    return {'orogenic_land_fraction': belt/total, 'craton_land_fraction': 1-belt/total,
            'threshold_m': threshold}


def range_systems(height, radius, sea_level, relief_grid_m, minimum_relief_m, minimum_nodes=4):
    """Count connected groups of high-relief land, as a proxy for distinct ranges.

    Eight-connected over the sphere grid's own neighbour lists, so the seam and the
    poles behave. Groups smaller than `minimum_nodes` are noise and are dropped.
    """
    n = len(height)
    points, _, neighbors = sphere_grid(n, radius)
    member = [height[z][x] > sea_level and relief_grid_m[z][x] >= minimum_relief_m
              for x, z in points]
    seen = [False]*len(points)
    groups = []
    for start in range(len(points)):
        if not member[start] or seen[start]:
            continue
        seen[start] = True
        stack, size = [start], 0
        while stack:
            i = stack.pop()
            size += 1
            for j, _ in neighbors[i]:
                if member[j] and not seen[j]:
                    seen[j] = True
                    stack.append(j)
        if size >= minimum_nodes:
            groups.append(size)
    return {'range_systems': len(groups), 'largest_range_nodes': max(groups) if groups else 0,
            'minimum_relief_m': minimum_relief_m}


def bluff_sites(height, radius, sea_level, drop_m, run_m):
    """Count land nodes with at least `drop_m` of fall inside `run_m`.

    The buildable-drama census: a cliffside hamlet needs a real fall close by.

    Refuses to answer when `run_m` is finer than the grid. A 40 m run on an 87 m
    raster is not a small measurement, it is an unavailable one -- widening it to
    one cell and reporting the count anyway produces confident nonsense, which is
    how a 42 m planet comes to report hundreds of cliffs.
    """
    _, effective, status = window_angle(radius, len(height), run_m)
    head = {'drop_m': drop_m, 'run_m': run_m, 'effective_run_m': effective, 'run_status': status}
    if status == 'below_grid':
        return {**head, 'bluff_sites': None, 'bluff_area_km2': None,
                'reason': f'run of {run_m:g} m is below the {effective:.1f} m grid resolution; '
                          'raise the raster size or measure a longer run'}
    grid = relief_grid(height, radius, run_m)
    points, areas, _ = sphere_grid(len(height), radius)
    hits = [areas[i] for i, (x, z) in enumerate(points)
            if height[z][x] > sea_level and grid[z][x] >= drop_m]
    return {**head, 'bluff_sites': len(hits), 'bluff_area_km2': sum(hits)/1e6}


def elevation_metrics(world, relief_windows=None):
    """Every elevation measurement for a generated world. Reads; never mutates."""
    layers = world['layers']
    effective = world.get('effective_config', {})
    config = world.get('config', {})
    height = layers['height']
    radius = effective.get('globe_radius') or config.get('globe_radius')
    sea_level = effective.get('sea_level', 0.)
    relief_m = effective.get('tectonic_relief', 0.)
    spacing = 2*math.pi*radius/(len(height)-1)
    windows = relief_windows or (spacing, 4*spacing, 16*spacing)
    metrics = {'version': 1, 'radius_m': radius, 'sea_level_m': sea_level,
               'cell_spacing_m': spacing, 'size': len(height),
               'land': land_statistics(height, radius, sea_level),
               'local_relief': [local_relief(height, radius, sea_level, w) for w in windows]}
    if 'slope' in layers:
        metrics['slope'] = slope_statistics(layers['slope'], height, radius, sea_level)
    if 'interaction' in layers and relief_m:
        metrics['tectonics'] = orogenic_fraction(layers['interaction'], height, radius, sea_level, relief_m)
    coarse = relief_grid(height, radius, 4*spacing)
    metrics['ranges'] = range_systems(height, radius, sea_level, coarse,
                                      max(1., .15*metrics['land'].get('land_max_m', 0.)))
    # Two runs on purpose. The 40 m run is the one a cliffside settlement actually
    # cares about and will report unavailable on any raster we run -- that gap is a
    # finding, not a failure, and says the cliff work must be validated at the
    # detail/patch sampler rather than here. The grid run gives a number that moves.
    metrics['bluffs'] = [bluff_sites(height, radius, sea_level, 20., 40.),
                         bluff_sites(height, radius, sea_level, 20., 4*spacing)]
    if config:
        metrics['noise'] = resolved_octaves(config['globe_radius'], config['size'],
                                            config['wavelength'], config['octaves'])
    metrics['meaning'] = ('Descriptive statistics of the emitted heightfield. Areas are '
                          'latitude-weighted reference-sphere footprints, not slope surface '
                          'area. Local relief is a two-ring sample and reads as a lower bound.')
    return metrics
