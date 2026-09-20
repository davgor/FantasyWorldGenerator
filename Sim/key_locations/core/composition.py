"""Chains and clusters: the locations that are wrong when placed independently.

A lone waystone is noise. Eleven of them counting down to a shrine is a story. Most of what
makes a map read as *authored* rather than scattered is not the individual places but the
relationships between them, and those cannot come out of a per-cell suitability field
however good it is — a field has no way to say "and then another one, two kilometres on".

Two shapes:

**Chains** are ordered runs along something the world already has — a road, a political
frontier, the approach to a shrine. Their members are **not node-snapped**. A waystone every
two kilometres on a world whose cells are six kilometres apart has to stand between cells, so
chain members carry a real interpolated direction and use their nearest node only for reading
layers. This is the one place the one-location-per-node rule does not apply, and members are
marked ``placement: "path"`` so a consumer can tell.

Intervals and offsets are **absolute metres**, deliberately unscaled. How far apart people
set waystones, and how far from a wall an army digs in, are facts about people rather than
about the size of the world; a larger world gets more of them, not longer gaps between them.

**Clusters** hang off an anchor that has already been placed: a siege camp outside a ruined
fort, cottages and a slag heap beside a mine, barrows ringing a necropolis. They are ordinary
node-snapped sites with a link back to what explains them.

Pure: no filesystem, no network, no engine, no generator imports.
"""
import math

from .grid import cell_of_direction, great_circle_m, slerp

LOS_SAMPLES = 12
SEARCH_CELLS = 1.2
ORDINALS = ('first', 'second', 'third', 'fourth', 'fifth', 'sixth', 'seventh', 'eighth',
            'ninth', 'tenth', 'eleventh', 'twelfth')


def ordinal(index):
    return ORDINALS[index] if index < len(ORDINALS) else f'{index + 1}th'


def _height_at(point, layers, n):
    x, z = cell_of_direction(point, n)
    return float(layers['height'][z][x])


def _walk(directions, radius):
    """Cumulative arc length along a polyline of unit directions."""
    spans, total = [], 0.
    for i in range(len(directions) - 1):
        step = great_circle_m(directions[i], directions[i + 1], radius)
        spans.append((total, total + step, directions[i], directions[i + 1]))
        total += step
    return spans, total


def _at_distance(spans, distance):
    """The direction and the fraction of its span at ``distance`` along a walked polyline."""
    for start, end, a, b in spans:
        if distance <= end or (start, end, a, b) is spans[-1]:
            fraction = 0. if end <= start else (distance - start) / (end - start)
            return slerp(a, b, max(0., min(1., fraction))), a, b, fraction
    return spans[-1][2], spans[-1][2], spans[-1][3], 0.


def line_of_sight(a, b, layers, n, radius, height_a, height_b):
    """Whether nothing between two points stands above the line joining them.

    A beacon chain that cannot see itself is decoration. Sampled on the heightfield with the
    curve of the world ignored, which over a few kilometres of a world this size is far below
    the relief the sampling already rounds away.
    """
    for step in range(1, LOS_SAMPLES):
        fraction = step / LOS_SAMPLES
        between = slerp(a, b, fraction)
        sightline = height_a + (height_b - height_a) * fraction
        if _height_at(between, layers, n) > sightline:
            return False
    return True


def _route_paths(world_reader, world, radius):
    """Every road as a polyline of directions, keyed stably by its endpoints."""
    from .grid import cell, direction as cell_direction
    n = world_reader.size(world)
    paths = []
    for route in world_reader.routes(world):
        nodes = route.get('nodes') or []
        if len(nodes) < 2:
            continue
        points = [cell_direction(*cell(int(node), n), n) for node in nodes]
        key = f"r{route.get('from', '?')}-{route.get('to', '?')}"
        paths.append((key, points))
    paths.sort(key=lambda row: row[0])
    return paths


def _frontier_paths(layers, cells, radius, interval_m):
    """Border cells strung into a run by walking nearest-neighbour from one end.

    Territory here is a raster frontier rather than a polygon, so there is no border to walk;
    it has to be recovered. Starting from the westernmost border cell and always stepping to
    the nearest unvisited one reconstructs a run that reads as a line on the map, which is
    what a boundary stone needs.
    """
    border = [c for c in cells if layers.get('frontier') and layers['frontier'][c['z']][c['x']] >= .5]
    if len(border) < 3:
        return []
    remaining = sorted(border, key=lambda c: (c['x'], c['z']))
    ordered = [remaining.pop(0)]
    while remaining:
        last = ordered[-1]['direction']
        nearest = min(remaining, key=lambda c: (great_circle_m(last, c['direction'], radius), c['node']))
        if great_circle_m(last, nearest['direction'], radius) > interval_m * 3:
            break
        ordered.append(nearest)
        remaining.remove(nearest)
    if len(ordered) < 3:
        return []
    return [('frontier', [c['direction'] for c in ordered])]


def _approach_paths(sites, world_reader, world, radius, spec):
    """The road in from the nearest city to each anchor worth walking to."""
    anchors = [s for s in sites
               if s['family'] == spec.get('anchor_family') and s['tier'] >= spec.get('anchor_tier', 2)]
    # Only the places actually worth walking to. Every shrine having its own pilgrim road makes
    # none of them a pilgrimage.
    anchors.sort(key=lambda s: (-s['tier'], -s['suitability'], s['id']))
    anchors = anchors[:int(spec.get('max_chains', len(anchors)))]
    cities = [c for c in world_reader.cities(world) if c.get('direction')]
    paths = []
    for anchor in sorted(anchors, key=lambda s: s['id']):
        if not cities:
            break
        start = min(cities, key=lambda c: (great_circle_m(tuple(c['direction']), tuple(anchor['direction']), radius),
                                           str(c.get('uid') or '')))
        paths.append((f"to-{anchor['id']}", [tuple(start['direction']), tuple(anchor['direction'])], anchor))
    return paths


def build_chains(specs, sites, context, make_site, rng_for):
    """Every chain the world can carry, plus the member sites they are made of."""
    radius, layers, n = context['radius'], context['layers'], context['n']
    world, reader = context['world'], context['reader']
    chains, members = [], []
    for spec in sorted(specs, key=lambda s: s['id']):
        interval = float(spec['interval_m'])
        if spec['along'] == 'road':
            paths = [(key, points, None) for key, points in _route_paths(reader, world, radius)]
        elif spec['along'] == 'frontier':
            paths = [(key, points, None) for key, points in
                     _frontier_paths(layers, context['land_cells'], radius, interval)]
        elif spec['along'] == 'approach':
            paths = _approach_paths(sites, reader, world, radius, spec)
        else:
            raise ValueError(f"chain {spec['id']!r} walks unknown thing {spec['along']!r}")
        for key, points, anchor in paths:
            spans, total = _walk(points, radius)
            if total < interval * 2:
                continue
            draw = rng_for(f"keyloc-chain-{spec['id']}-{key}")
            placed, previous = [], None
            distance, index = interval, 0
            while distance < total - interval * .5:
                point, _, _, _ = _at_distance(spans, distance)
                height = _height_at(point, layers, n)
                if spec.get('line_of_sight') and previous is not None:
                    if not line_of_sight(previous[0], point, layers, n, radius, previous[1], height):
                        distance += interval * .25
                        continue
                member = make_site(spec, point, height, f"{spec['id']}-{key}", int(round(distance)), index,
                                   draw, anchor)
                placed.append(member)
                previous = (point, height)
                distance += interval
                index += 1
            if len(placed) < 2:
                continue
            chain_id = f"chain-{spec['id']}-{key}"
            for position, member in enumerate(placed):
                member['links']['chain'] = chain_id
                member['links']['chain_index'] = position
                if anchor is not None:
                    member['links']['anchor'] = anchor['id']
            members += placed
            chains.append({'id': chain_id, 'kind': spec['id'], 'name': spec['name'],
                           'archetype': spec['archetype'], 'along': spec['along'],
                           'interval_m': round(interval, 1), 'length_m': round(total, 1),
                           'anchor': anchor['id'] if anchor is not None else None,
                           'members': [m['id'] for m in placed],
                           'reason': spec['reason']})
    return chains, members


def build_clusters(specs, sites, context, place_near, rng_for):
    """Sites that hang off an already-placed anchor, and the anchors they explain."""
    radius = context['radius']
    by_id = {s['id']: s for s in sites}
    clusters, members = [], []
    for spec in sorted(specs, key=lambda s: s['id']):
        kinds, families = set(spec.get('anchor_kinds', ())), set(spec.get('anchor_families', ()))
        states = set(spec.get('anchor_states', ()))
        anchors = [s for s in sites
                   if (s['kind'] in kinds or s['family'] in families)
                   and (not states or s['state'] in states)]
        for anchor in sorted(anchors, key=lambda s: s['id']):
            draw = rng_for(f"keyloc-cluster-{spec['id']}-{anchor['id']}")
            if draw.random() >= float(spec.get('chance', 1.)):
                continue
            low, high = spec['count']
            wanted = draw.randint(int(low), int(high))
            near, far = (float(v) for v in spec['offset_m'])
            produced = []
            for index in range(wanted):
                gap = near + (far - near) * draw.random()
                member = place_near(spec, anchor, gap, draw, index)
                if member is None:
                    continue
                member['links']['cluster'] = f"cluster-{spec['id']}-{anchor['id']}"
                member['links']['anchor'] = anchor['id']
                produced.append(member)
            if not produced:
                continue
            members += produced
            clusters.append({'id': f"cluster-{spec['id']}-{anchor['id']}", 'kind': spec['id'],
                             'name': spec['name'], 'anchor': anchor['id'],
                             'anchor_kind': anchor['kind'], 'anchor_name': anchor['name'],
                             'members': [m['id'] for m in produced], 'reason': spec['reason']})
            by_id.setdefault(anchor['id'], anchor)
    return clusters, members
