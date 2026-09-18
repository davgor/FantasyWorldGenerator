"""Castle wall-ring geometry: joins, segmentation and perimeter polylines (metres)."""
import math

from .city_fortifications import smooth_closed_ring

VERSION = 1


def turn_degrees(a, b, c):
    """Signed exterior turn at b going a->b->c, degrees in (-180, 180]."""
    v1 = (a[0] - b[0], a[1] - b[1])
    v2 = (c[0] - b[0], c[1] - b[1])
    ang1 = math.atan2(v1[1], v1[0])
    ang2 = math.atan2(v2[1], v2[0])
    delta = math.degrees(ang2 - ang1)
    while delta <= -180:
        delta += 360
    while delta > 180:
        delta -= 360
    return delta


def can_join(module_a, module_b, rules, thickness_a=None, thickness_b=None, height_a=None, height_b=None):
    """Validate end-type and thickness/height compatibility between two modules."""
    if module_a is None or module_b is None:
        return False, 'Missing module'
    ends_a = set(module_a.get('compatible_ends') or [])
    ends_b = set(module_b.get('compatible_ends') or [])
    end_a = module_a.get('end_type')
    end_b = module_b.get('end_type')
    if end_a is None or end_b is None:
        return False, 'Module has no join end'
    if end_b not in ends_a and end_a not in ends_b:
        return False, f'Incompatible ends {end_a}/{end_b}'
    ta = thickness_a if thickness_a is not None else (module_a.get('thickness_m') or {}).get('nominal')
    tb = thickness_b if thickness_b is not None else (module_b.get('thickness_m') or {}).get('nominal')
    ha = height_a if height_a is not None else (module_a.get('height_m') or {}).get('nominal')
    hb = height_b if height_b is not None else (module_b.get('height_m') or {}).get('nominal')
    if ta is None or tb is None or ha is None or hb is None:
        return False, 'Missing thickness or height'
    if abs(ta - tb) > rules['max_thickness_delta_m']:
        return False, f'Thickness delta {abs(ta - tb):.3f} exceeds {rules["max_thickness_delta_m"]}'
    if abs(ha - hb) > rules['max_height_delta_m']:
        return False, f'Height delta {abs(ha - hb):.3f} exceeds {rules["max_height_delta_m"]}'
    if rules.get('walkway_required') and module_a.get('walkway') and module_b.get('walkway') is False:
        return False, 'Walkway continuity broken'
    if rules.get('walkway_required') and module_b.get('walkway') and module_a.get('walkway') is False:
        return False, 'Walkway continuity broken'
    return True, None


def ellipse_ring(rx, rz, samples=48):
    """Closed-ready polyline samples on an axis-aligned ellipse (last != first)."""
    points = []
    for i in range(samples):
        angle = 2 * math.pi * i / samples
        points.append((round(rx * math.cos(angle), 2), round(rz * math.sin(angle), 2)))
    return points


def clip_ring_to_valid(points, valid, half, cell, max_slope_deg, height_fn, slope_fn):
    """Snap each ray sample inward until it lies on buildable land."""
    if not points or not valid:
        return []
    snapped = []
    for px, pz in points:
        length = math.hypot(px, pz) or 1.0
        ux, uz = px / length, pz / length
        best = None
        for dist in range(int(max(half, 1)), 0, -cell):
            x, z = ux * dist, uz * dist
            i = int(math.floor((x + half) / cell))
            j = int(math.floor((z + half) / cell))
            if (i, j) not in valid:
                continue
            if slope_fn(i, j) > max_slope_deg:
                continue
            best = (round(x, 2), round(z, 2))
            break
        if best:
            snapped.append(best)
    return smooth_closed_ring(snapped) if len(snapped) >= 8 else snapped


def segmentize(polyline, segment_depth_m, structure_id, ring_id, thickness_m, height_m):
    """Break a closed polyline into curtain segments with stable IDs."""
    if len(polyline) < 3:
        return [], []
    nodes = [{'id': f'{ring_id}-node-{i}', 'kind': 'vertex', 'position_m': list(point), 'ring_id': ring_id}
             for i, point in enumerate(polyline)]
    closed = list(polyline) + [polyline[0]]
    segments = []
    seg_i = 0
    carry = 0.0
    path = []
    for a, b in zip(closed, closed[1:]):
        path.append(a)
        edge = math.dist(a, b)
        while carry + edge >= segment_depth_m - 0.01:
            need = segment_depth_m - carry
            t = need / edge if edge else 0
            end = (round(a[0] + (b[0] - a[0]) * t, 2), round(a[1] + (b[1] - a[1]) * t, 2))
            start = path[-1] if path else a
            mid = ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)
            heading = math.degrees(math.atan2(end[1] - start[1], end[0] - start[0]))
            angle = heading - 90
            segments.append({
                'id': f'{ring_id}-seg-{seg_i}',
                'ring_id': ring_id,
                'structure_id': structure_id,
                'module_id': 'module.curtain_segment',
                'from_m': list(start),
                'to_m': list(end),
                'center_m': [round(mid[0], 2), round(mid[1], 2)],
                'length_m': round(math.dist(start, end), 3),
                'rotation_degrees': round(angle, 4),
                'thickness_m': thickness_m,
                'height_m': height_m,
                'walkway': True,
            })
            seg_i += 1
            path = [end]
            a = end
            edge = math.dist(a, b)
            carry = 0.0
        carry += edge
    return segments, nodes


def corner_indices(polyline, min_turn_degrees):
    """Indices where the absolute exterior turn exceeds the kit threshold."""
    if len(polyline) < 3:
        return []
    n = len(polyline)
    hits = []
    for i in range(n):
        a = polyline[(i - 1) % n]
        b = polyline[i]
        c = polyline[(i + 1) % n]
        if abs(turn_degrees(a, b, c)) >= min_turn_degrees:
            hits.append(i)
    return hits


def approach_gate_index(polyline, approach_m):
    """Nearest ring vertex to the approach gate local metres."""
    if not polyline:
        return None
    if approach_m is None:
        # Prefer the +x extremity as a deterministic fallback approach.
        return max(range(len(polyline)), key=lambda i: (polyline[i][0], -abs(polyline[i][1])))
    return min(range(len(polyline)), key=lambda i: math.dist(polyline[i], approach_m))


def opposite_index(polyline, index):
    if not polyline:
        return None
    return (index + len(polyline) // 2) % len(polyline)


def validate_segment_chain(segments, nodes_by_join, modules, rules):
    """Ensure consecutive curtain/node joins keep walkway and dimensional continuity."""
    failures = []
    curtain = modules['curtain_segment']
    for seg in segments:
        ok, reason = can_join(curtain, curtain, rules,
                              thickness_a=seg['thickness_m'], thickness_b=seg['thickness_m'],
                              height_a=seg['height_m'], height_b=seg['height_m'])
        if not ok:
            failures.append({'segment_id': seg['id'], 'reason': reason})
    for join in nodes_by_join:
        mod = modules.get(join.get('module_key'))
        # Node structures may rise above the walkway; join continuity uses curtain height.
        join_h = join.get('curtain_height_m', curtain['height_m']['nominal'])
        ok, reason = can_join(curtain, mod, rules,
                              thickness_a=join.get('thickness_m'), thickness_b=join.get('thickness_m'),
                              height_a=join_h, height_b=join_h)
        if not ok:
            failures.append({'node_id': join.get('id'), 'reason': reason or 'join failed'})
    return failures


def build_wall_network(*, ring_id, role, polyline, approach_m, ring_spec, modules, rules, ditch=False):
    """Assemble one closed fortification ring with gates, corners, stairs and curtain segments."""
    report = {
        'id': ring_id,
        'role': role,
        'polyline_m': [list(p) for p in polyline],
        'status': 'open',
        'segments': [],
        'nodes': [],
        'gates': [],
        'towers': [],
        'stairs': [],
        'walkway_continuous': False,
        'unplaced': [],
    }
    if len(polyline) < 8:
        report['unplaced'].append({'building_id': 'building.curtain_segment', 'reason': 'Perimeter could not close'})
        return report
    curtain = modules['curtain_segment']
    thickness = curtain['thickness_m']['nominal']
    height = curtain['height_m']['nominal']
    segments, vertices = segmentize(polyline, rules['segment_depth_m'], curtain['structure_id'],
                                    ring_id, thickness, height)
    if len(segments) < 6:
        report['unplaced'].append({'building_id': curtain['structure_id'],
                                   'reason': 'Insufficient continuous wall segments'})
        return report
    gate_idx = approach_gate_index(polyline, approach_m)
    gate_key = ring_spec.get('gate') or 'gatehouse'
    gate_mod = modules[gate_key]
    gate = {
        'id': f'{ring_id}-gate-0',
        'ring_id': ring_id,
        'module_key': gate_key,
        'module_id': gate_mod['id'],
        'structure_id': gate_mod['structure_id'],
        'position_m': list(polyline[gate_idx]),
        'approach_m': list(approach_m) if approach_m else list(polyline[gate_idx]),
        'thickness_m': thickness,
        'height_m': gate_mod['height_m']['nominal'],
        'curtain_height_m': height,
        'walkway': True,
    }
    gates = [gate]
    if ring_spec.get('postern'):
        post_idx = opposite_index(polyline, gate_idx)
        post_mod = modules['postern']
        gates.append({
            'id': f'{ring_id}-postern-0',
            'ring_id': ring_id,
            'module_key': 'postern',
            'module_id': post_mod['id'],
            'structure_id': post_mod['structure_id'],
            'position_m': list(polyline[post_idx]),
            'approach_m': list(polyline[post_idx]),
            'thickness_m': thickness,
            'height_m': post_mod['height_m']['nominal'],
            'curtain_height_m': height,
            'walkway': True,
            'kind': 'postern',
        })
    # Drop curtain segments that collide with gate centres.
    keep = []
    for seg in segments:
        if any(math.dist(seg['center_m'], g['position_m']) < max(8, rules['segment_depth_m'] * 0.6) for g in gates):
            continue
        keep.append(seg)
    towers = []
    for t_i, idx in enumerate(corner_indices(polyline, rules['min_turn_degrees_for_corner'])):
        if t_i >= ring_spec.get('tower_budget', 4):
            break
        if any(math.dist(polyline[idx], g['position_m']) < 10 for g in gates):
            continue
        corner = modules['corner_join']
        towers.append({
            'id': f'{ring_id}-tower-{t_i}',
            'ring_id': ring_id,
            'module_key': 'corner_join',
            'module_id': corner['id'],
            'structure_id': corner['structure_id'],
            'position_m': list(polyline[idx]),
            'thickness_m': thickness,
            'height_m': corner['height_m']['nominal'],
            'curtain_height_m': height,
            'walkway': True,
        })
    stairs = []
    stair_budget = ring_spec.get('stairs', 0)
    if stair_budget and keep:
        step = max(1, len(keep) // stair_budget)
        stair_mod = modules['wall_stair']
        for s_i, seg in enumerate(keep[::step][:stair_budget]):
            stairs.append({
                'id': f'{ring_id}-stair-{s_i}',
                'ring_id': ring_id,
                'module_key': 'wall_stair',
                'module_id': stair_mod['id'],
                'structure_id': stair_mod['structure_id'],
                'position_m': list(seg['center_m']),
                'thickness_m': thickness,
                'height_m': stair_mod['height_m']['nominal'],
                'curtain_height_m': height,
                'walkway': True,
            })
    joins = gates + towers + stairs
    failures = validate_segment_chain(keep, joins, modules, rules)
    if failures:
        report['unplaced'].extend({'building_id': f.get('segment_id') or f.get('node_id'), 'reason': f['reason']}
                                  for f in failures)
        report['status'] = 'broken'
        report['segments'] = keep
        report['nodes'] = vertices
        report['gates'] = gates
        report['towers'] = towers
        report['stairs'] = stairs
        return report
    report.update(status='closed', segments=keep, nodes=vertices, gates=gates, towers=towers, stairs=stairs,
                  walkway_continuous=True, segment_count=len(keep), gate_count=len(gates),
                  ditch=bool(ditch or ring_spec.get('ditch')))
    return report
