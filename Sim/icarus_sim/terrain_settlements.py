"""Explainable candidate settlement sites and terrain-constrained road proposals."""
import heapq
import math
import random
from time import perf_counter
from .terrain_erosion import sphere_grid
from .terrain_globe import direction,perlin3
from .terrain_tectonics import child_seed
from .terrain_climate import node_grid
from .terrain_biome_catalogue import NATURAL_BIOMES, biome_catalogue, cell_variant
from .terrain_profiles import biome_preference, biome_food_multiplier
from .civilization_registry import building_pack_data,layout_profile_data,entity_rules,section


def _coerce_finite_number(value, field):
    if not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f'{field} must be finite number')
    return float(value)


def _coerce_optional_number(value, default, field):
    if value is None:
        return default
    return _coerce_finite_number(value, field)


def _coerce_int(value, field):
    if not isinstance(value, int):
        raise ValueError(f'{field} must be integer')
    return value


def _coerce_non_negative_number(value, field):
    value = _coerce_finite_number(value, field)
    if value < 0:
        raise ValueError(f'{field} must be non-negative')
    return value


def _coerce_feature_count(value, field):
    if isinstance(value, (int, float)):
        base = _coerce_finite_number(value, field)
        return {'base': base, 'per_100_residents': 0., 'min': None, 'max': None, 'profiles': None}
    if not isinstance(value, dict):
        raise ValueError(f'{field} must be number or object')
    base = _coerce_finite_number(value.get('base', 0), f'{field}.base')
    per_100 = _coerce_non_negative_number(value.get('per_100_residents', 0), f'{field}.per_100_residents')
    min_count = value.get('min')
    max_count = value.get('max')
    if min_count is not None and not isinstance(min_count, int):
        raise ValueError(f'{field}.min must be integer')
    if max_count is not None and not isinstance(max_count, int):
        raise ValueError(f'{field}.max must be integer')
    if min_count is not None and max_count is not None and min_count > max_count:
        raise ValueError(f'{field}.min cannot exceed {field}.max')
    profiles = value.get('profiles')
    if profiles is not None and (not isinstance(profiles, list) or any(not isinstance(p, str) for p in profiles)):
        raise ValueError(f'{field}.profiles must be list of profile ids')
    return {'base': base, 'per_100_residents': per_100, 'min': min_count, 'max': max_count, 'profiles': set(profiles) if profiles is not None else None}


def _coerce_optional_bool(value, default, field):
    if value is None:
        return default
    if not isinstance(value, bool):
        raise ValueError(f'{field} must be boolean')
    return value


def _coerce_string_list(values, field):
    if values is None:
        return []
    if not isinstance(values, list) or any((not isinstance(v, str) or not v) for v in values):
        raise ValueError(f'{field} must be a list of strings')
    return [str(v) for v in values]


def _coerce_building_placement(value, pack_id, option_id):
    value = 'anchored' if value is None else str(value)
    allowed = {'anchored', 'structural', 'river_gate', 'wall'}
    if value not in allowed:
        raise ValueError(f'Pack {pack_id} building option {option_id}.placement must be one of {sorted(allowed)}')
    return value


def _coerce_building_choices(raw_choices, pack_id, option_id):
    if not isinstance(raw_choices, list) or not raw_choices:
        raise ValueError(f'Pack {pack_id} building option {option_id} requires a non-empty asset_choices list')
    choices = []
    for index, raw_choice in enumerate(raw_choices):
        if not isinstance(raw_choice, dict):
            raise ValueError(f'Pack {pack_id} building option {option_id} asset choice {index} must be object')
        asset_id = raw_choice.get('asset_id')
        if not isinstance(asset_id, str) or not asset_id:
            raise ValueError(f'Pack {pack_id} building option {option_id} asset choice {index} requires asset_id')
        weight = _coerce_finite_number(raw_choice.get('weight', 1.), f'Pack {pack_id} building option {option_id} asset choice {index}.weight')
        if weight <= 0:
            raise ValueError(f'Pack {pack_id} building option {option_id} asset choice {index}.weight must be positive')
        choices.append({'asset_id': asset_id, 'weight': weight})
    return choices


def _coerce_building_options(raw_value, pack_id):
    if raw_value is None:
        return []
    if not isinstance(raw_value, list) or not raw_value:
        raise ValueError(f'Pack {pack_id} building_options must be a non-empty list when provided')
    normalized = []
    option_ids = set()
    for raw in raw_value:
        if not isinstance(raw, dict):
            raise ValueError(f'Pack {pack_id} building option must be object')
        if 'id' not in raw or not isinstance(raw['id'], str) or not raw['id']:
            raise ValueError(f'Pack {pack_id} building option id required')
        if raw['id'] in option_ids:
            raise ValueError(f'Pack {pack_id} duplicate building option id {raw["id"]}')
        option_ids.add(raw['id'])
        count_value = raw.get('count', {'base': 0})
        count = _coerce_feature_count(count_value, f'Pack {pack_id} building option {raw["id"]}')
        raw_profiles = raw.get('profiles')
        if raw_profiles is None:
            profiles = count.get('profiles')
        else:
            if not isinstance(raw_profiles, list) or any(not isinstance(p, str) for p in raw_profiles):
                raise ValueError(f'Pack {pack_id} building option {raw["id"]} profiles must be list of strings')
            profiles = set(raw_profiles) if raw_profiles else None
        required = _coerce_optional_bool(raw.get('required', False), False, f'Pack {pack_id} building option {raw["id"]}.required')
        if required and count['min'] is None:
            count['min'] = 1
        elif required and count['min'] is not None:
            count['min'] = max(count['min'], 1)
        placement = _coerce_building_placement(raw.get('placement', 'anchored'), pack_id, raw['id'])
        requires_bridge = _coerce_optional_bool(raw.get('requires_bridge', False), False, f'Pack {pack_id} building option {raw["id"]}.requires_bridge')
        normalized.append({
            'id': raw['id'],
            'name': str(raw.get('name', raw['id'])),
            'count': count,
            'profiles': set(profiles) if profiles else None,
            'asset_choices': _coerce_building_choices(raw.get('asset_choices'), pack_id, raw['id']),
            'placement': placement,
            'required': required,
            'requires_bridge': requires_bridge,
            'tags': set(_coerce_string_list(raw.get('tags'), f'Pack {pack_id} building option {raw["id"]}.tags'))
        })
    return normalized


def _normalize_layout_profile(raw):
    if not isinstance(raw, dict):
        raise ValueError('City layout profile must be object')
    if not isinstance(raw.get('id'), str) or not raw['id']:
        raise ValueError('City layout profile id required')
    features = raw.get('features')
    if not isinstance(features, dict) or not features:
        raise ValueError(f'Layout profile {raw["id"]} missing features')
    defaults = {
        'leader_homes': {'base': 1},
        'barracks': {'base': 1},
        'noble_homes': {'base': 1, 'per_100_residents': 0.04},
        'worker_housing': {'base': 2, 'per_100_residents': 0.25},
        'apartments': {'base': 0, 'per_100_residents': 0.15, 'max': 5},
        'market_district': {'base': 1, 'max': 3},
        'religious_building': {'base': 1, 'profiles': ['human', 'elf', 'gnome', 'dwarf', 'tidekin'], 'max': 2}
    }
    normalized = {}
    for feature, definition in defaults.items():
        normalized[feature] = _coerce_feature_count(features.get(feature, definition), f'features.{feature}')
    placement = raw.get('placement')
    if placement is None:
        placement = {}
    if not isinstance(placement, dict):
        raise ValueError(f'Layout profile {raw["id"]} placement must be object')
    return {
        'id': raw['id'],
        'name': str(raw.get('name', raw['id'])),
        'features': normalized,
        'placement': {
            'river_buffer_m': _coerce_non_negative_number(placement.get('river_buffer_m', 30), 'placement.river_buffer_m'),
            'river_fork_bridge_threshold': _coerce_int(placement.get('river_fork_bridge_threshold', 2), 'placement.river_fork_bridge_threshold'),
            'bridge_if_river_fork': bool(placement.get('bridge_if_river_fork', True)),
            'max_anchor_slope_degrees': _coerce_finite_number(placement.get('max_anchor_slope_degrees', 12), 'placement.max_anchor_slope_degrees')
        }
    }


def _resolve_feature_count(feature, residents):
    base = feature['base']
    if residents is not None:
        base += feature['per_100_residents'] * (max(0, residents) / 100)
    count = int(math.floor(base))
    if feature['min'] is not None:
        count = max(count, feature['min'])
    if feature['max'] is not None:
        count = min(count, feature['max'])
    return max(0, count)


def _profile_fits_feature(feature, population_profile):
    return feature['profiles'] is None or population_profile in feature['profiles']


def _weighted_pick(rng, choices):
    total = sum(choice['weight'] for choice in choices)
    if total <= 0:
        return choices[0]['asset_id']
    draw = rng.random() * total
    cursor = 0.
    for choice in choices:
        cursor += choice['weight']
        if draw <= cursor:
            return choice['asset_id']
    return choices[-1]['asset_id']


def _build_city_building_plan(rng, city_seed, population_profile, city_population, bridge_recommended, ordered_nodes, anchor_distance, river_neighbors, river, used_nodes, points, building_pack, graph=None):
    graph_neighbors = graph if graph is not None else []
    ordered_node_set = set(ordered_nodes)
    river_frontier_nodes = []
    if graph_neighbors:
        river_frontier_nodes = [node_id for node_id in ordered_nodes if any(
            river[neighbor] for neighbor, _ in graph_neighbors[node_id] if 0 <= neighbor < len(river))]
    boundary_nodes = []
    if ordered_node_set and graph_neighbors:
        boundary_nodes = [node_id for node_id in ordered_nodes
                          if any((neighbor not in ordered_node_set) for neighbor, _ in graph_neighbors[node_id])]

    option_plans = {}
    required_assets = {}
    required_node_slots = 0
    missing_anchors = False
    anchor_cursor = rng.randrange(len(ordered_nodes)) if ordered_nodes else 0
    wall_cursor = 0

    def _collect_anchors(candidates, target_count, cursor):
        if target_count <= 0:
            return [], cursor, False
        if not candidates:
            return [], cursor, True
        n = len(candidates)
        anchors = []
        attempts = 0
        max_attempts = target_count * max(1, n)
        cursor %= n
        while len(anchors) < target_count and attempts < max_attempts:
            node_id = candidates[cursor]
            cursor = (cursor + 1) % n
            attempts += 1
            if node_id in used_nodes:
                continue
            used_nodes.add(node_id)
            x, z = points[node_id]
            anchors.append({
                'node': node_id,
                'x': x,
                'z': z,
                'distance_to_city_m': anchor_distance.get(node_id, 0.),
                'sequence': len(anchors)
            })
        return anchors, cursor, len(anchors) < target_count

    for option in building_pack.get('building_options', []):
        if option['profiles'] is not None and population_profile not in option['profiles']:
            continue
        target_count = _resolve_feature_count(option['count'], city_population)
        if target_count == 0:
            option_plans[option['id']] = {
                'option_id': option['id'],
                'name': option['name'],
                'target_count': 0,
                'placed_count': 0,
                'required': option['required'],
                'placement': option['placement'],
                'tags': sorted(option['tags']),
                'anchors': [],
                'assets': [],
                'asset_requirements': {},
                'bridge_required': option['requires_bridge'],
                'skip_reason': None,
                'required_node_slots': 0
            }
            continue

        planned_count = target_count
        if option['placement'] == 'anchored':
            anchors, anchor_cursor, has_missing = _collect_anchors(ordered_nodes, target_count, anchor_cursor)
            planned_count = len(anchors)
            if has_missing:
                missing_anchors = True
        elif option['placement'] == 'river_gate':
            if option['requires_bridge'] and not bridge_recommended:
                anchors = []
                has_missing = option['required']
                planned_count = 0
            else:
                if not river_frontier_nodes:
                    gate_candidates = []
                else:
                    gate_candidates = list(reversed(river_frontier_nodes))
                anchors, anchor_cursor, has_missing = _collect_anchors(gate_candidates, target_count, anchor_cursor)
                planned_count = len(anchors)
            if has_missing:
                missing_anchors = True
        elif option['placement'] == 'wall':
            if boundary_nodes:
                wall_candidates = sorted(boundary_nodes, key=lambda node_id: anchor_distance.get(node_id, 0.), reverse=True)
            else:
                wall_candidates = list(reversed(ordered_nodes))
            anchors, wall_cursor, has_missing = _collect_anchors(wall_candidates, target_count, wall_cursor)
            planned_count = len(anchors)
            if has_missing:
                missing_anchors = True
        elif option['placement'] == 'structural':
            anchors = []
            has_missing = False
        else:
            raise ValueError(f'Unknown placement {option["placement"]} for building option {option["id"]}')

        selected_assets = [_weighted_pick(rng, option['asset_choices']) for _ in range(planned_count)] if option['asset_choices'] else []
        for asset_id in selected_assets:
            required_assets[asset_id] = required_assets.get(asset_id, 0) + 1
        asset_requirements = {}
        for asset_id in selected_assets:
            asset_requirements[asset_id] = asset_requirements.get(asset_id, 0) + 1

        required_node_slots += len(anchors)
        skip_reason = None
        if option['placement'] == 'river_gate' and option['requires_bridge'] and not bridge_recommended:
            skip_reason = 'requires_bridge'
        option_plans[option['id']] = {
            'option_id': option['id'],
            'name': option['name'],
            'target_count': target_count,
            'placed_count': len(anchors),
            'required': option['required'],
            'placement': option['placement'],
            'tags': sorted(option['tags']),
            'anchors': anchors,
            'assets': selected_assets,
            'asset_requirements': asset_requirements,
            'bridge_required': option['requires_bridge'],
            'skip_reason': skip_reason,
            'required_node_slots': len(anchors)
        }

    required_rows = [{'asset_id': asset_id, 'count': required_assets[asset_id]} for asset_id in sorted(required_assets)]
    return {
        'version': 1,
        'city_seed': city_seed,
        'options': option_plans,
        'required_assets': required_rows,
        'required_asset_count': sum(required_assets.values()),
        'required_node_slots': required_node_slots,
        'missing_anchors': missing_anchors
    }


def _load_city_layout_profiles():
    raw = layout_profile_data()
    if not isinstance(raw, dict):
        raise ValueError('City layout profiles must be object')
    if not isinstance(raw.get('schema_version'), int):
        raise ValueError('City layout schema_version must be integer')
    if not isinstance(raw.get('fallback_profile_id'), str) or not raw['fallback_profile_id']:
        raise ValueError('City layout profiles must define fallback_profile_id')
    profiles = raw.get('profiles')
    if not isinstance(profiles, list) or not profiles:
        raise ValueError('City layout profiles must include profiles list')
    normalized = {}
    for raw_profile in profiles:
        profile = _normalize_layout_profile(raw_profile)
        if profile['id'] in normalized:
            raise ValueError('Duplicate city layout profile id')
        normalized[profile['id']] = profile
    if raw['fallback_profile_id'] not in normalized:
        raise ValueError('fallback_profile_id must reference a profile id')
    catalogue = {'schema_version': int(raw['schema_version']),
                            'fallback_profile_id': raw['fallback_profile_id'],
                            'profiles': normalized}
    return catalogue


def _pick_city_layout_profile(pack_entry, layout_profiles, river_distance_m):
    riverfront = layout_profiles['profiles'].get('riverfront_city_layout')
    if pack_entry is not None:
        forced = pack_entry.get('layout_profile_id')
        if forced and forced in layout_profiles['profiles']:
            return layout_profiles['profiles'][forced]
    if riverfront is None:
        return layout_profiles['profiles'][layout_profiles['fallback_profile_id']]
    if math.isfinite(river_distance_m) and river_distance_m <= riverfront['placement']['river_buffer_m'] * 1.8:
        return riverfront
    return layout_profiles['profiles'][layout_profiles['fallback_profile_id']]


def _validate_building_packs(value):
    if not isinstance(value, dict):
        raise ValueError('City building packs must be a dictionary')
    if value.get('schema_version') != 3:
        raise ValueError('City building packs require schema 3')
    if not isinstance(value.get('fallback_pack_id'), str) or not value['fallback_pack_id']:
        raise ValueError('City building packs must define fallback_pack_id')
    packs = value.get('packs')
    if not isinstance(packs, list) or not packs:
        raise ValueError('City building packs must include packs list')
    normalized = []
    pack_ids = set()
    for raw in packs:
        if not isinstance(raw, dict):
            raise ValueError('City building pack entry must be object')
        if 'id' not in raw or not isinstance(raw['id'], str) or not raw['id']:
            raise ValueError('City building pack id required')
        if raw['id'] in pack_ids:
            raise ValueError('Duplicate city building pack id')
        pack_ids.add(raw['id'])
        criteria = raw.get('criteria')
        if not isinstance(criteria, dict):
            raise ValueError(f'Pack {raw["id"]} is missing criteria')
        biome_ids=criteria.get('biomes')
        variant_ids=criteria.get('biome_variants', [])
        valid_variants={b['id'] for b in biome_catalogue()}
        if 'biomes' in criteria and (not isinstance(biome_ids,list) or any(type(b) is not int or b not in NATURAL_BIOMES for b in biome_ids)):
            raise ValueError('Unknown natural biome in building pack')
        if not isinstance(variant_ids,list) or any(not isinstance(v,str) or v not in valid_variants for v in variant_ids):
            raise ValueError('Unknown magical biome in building pack')
        def as_population_profiles(v):
            if v is None:
                return None
            if not isinstance(v, list) or any(not isinstance(p, str) for p in v):
                raise ValueError(f'Pack {raw["id"]} profiles must be list of strings')
            return set(v)
        entry = {
            'id': raw['id'],
            'name': str(raw.get('name', raw['id'])),
            'profiles': as_population_profiles(criteria.get('population_profiles')),
            'layout_profile_id': str(raw['layout_profile_id']) if raw.get('layout_profile_id') is not None else None,
            'biomes': set(biome_ids or []) if 'biomes' in criteria or 'biome_variants' in criteria else None,
            'biome_variants': set(variant_ids),
            'height_min': _coerce_optional_number(criteria.get('height_min_m'), -1e6, 'height_min_m'),
            'height_max': _coerce_optional_number(criteria.get('height_max_m'), 1e6, 'height_max_m'),
            'resource_min': _coerce_optional_number(criteria.get('resource_min'), 0., 'resource_min'),
            'resource_max': _coerce_optional_number(criteria.get('resource_max'), 1., 'resource_max'),
            'slope_max': _coerce_optional_number(criteria.get('slope_max_degrees'), 1000., 'slope_max_degrees'),
            'water_distance_min': _coerce_optional_number(criteria.get('freshwater_distance_m_min'), 0., 'freshwater_distance_m_min'),
            'water_distance_max': _coerce_optional_number(criteria.get('freshwater_distance_m_max'), 1e9, 'freshwater_distance_m_max'),
            'weight': _coerce_finite_number(raw.get('weight', 1.), 'weight'),
            'building_options': _coerce_building_options(raw.get('building_options'), raw['id'])
        }
        if entry['weight'] <= 0:
            raise ValueError(f'Pack {raw["id"]} weight must be positive')
        normalized.append(entry)
    if value['fallback_pack_id'] not in pack_ids:
        raise ValueError('fallback_pack_id must reference a pack id')
    return {'schema_version': int(value['schema_version']),
            'fallback_pack_id': value['fallback_pack_id'],
            'packs': normalized,
            'pack_index': {pack['id']: pack for pack in normalized}}


def _dijkstra_distances(graph, sources):
    distances = [math.inf] * len(graph)
    queue = []
    for source in sources:
        if 0 <= source < len(graph) and distances[source] > 0:
            distances[source] = 0
            heapq.heappush(queue, (0, source))
    while queue:
        distance, node = heapq.heappop(queue)
        if distance != distances[node]:
            continue
        for neighbor, edge in graph[node]:
            candidate = distance + edge
            if candidate < distances[neighbor]:
                distances[neighbor] = candidate
                heapq.heappush(queue, (candidate, neighbor))
    return distances


def _collect_land_anchor_candidates(points, graph, start, river_distances, water, slope, max_slope, min_river_distance):
    max_walk = 800 if not math.isfinite(min_river_distance) else max(180, 4 * min_river_distance + 180)
    distances = [math.inf] * len(graph)
    queue = [(0, start)]
    distances[start] = 0
    candidates = []
    while queue:
        distance, node = heapq.heappop(queue)
        if distance != distances[node]:
            continue
        if distance > max_walk:
            continue
        if water[node] == 0 and slope[node] <= max_slope:
            if math.isinf(min_river_distance) or river_distances[node] >= min_river_distance:
                candidates.append((distance, node))
        for neighbor, edge in graph[node]:
            candidate = distance + edge
            if candidate < distances[neighbor]:
                distances[neighbor] = candidate
                heapq.heappush(queue, (candidate, neighbor))
    candidates.sort(key=lambda item: (item[0], item[1]))
    return candidates


def _build_city_layout_plan(city_seed, node, points, layout_profile, population_profile, city_population, river_distance_m, river_neighbors, river, anchor_candidates, graph=None, building_pack=None):
    rng = random.Random(city_seed)
    placement = layout_profile['placement']
    city_plan = {'version': 1, 'layout_profile_id': layout_profile['id'],
                 'layout_profile_name': layout_profile['name'],
                 'population_profile': population_profile,
                 'residents': city_population}
    fork_degree = sum(1 for neighbor_id, _ in river_neighbors if river[neighbor_id])
    city_plan['river'] = {'adjacent_river_edges': fork_degree,
                          'river_distance_m': river_distance_m if math.isfinite(river_distance_m) else None,
                          'bridge_recommended': bool(fork_degree >= placement['river_fork_bridge_threshold'] and placement['bridge_if_river_fork']),
                          'bridge_threshold': placement['river_fork_bridge_threshold']}
    ordered_nodes = []
    seen_nodes = set()
    for _, node_id in anchor_candidates:
        if node_id not in seen_nodes:
            seen_nodes.add(node_id)
            ordered_nodes.append(node_id)
    anchor_distance = {node_id: distance for distance, node_id in anchor_candidates}
    features = {}
    cursor = rng.randrange(len(ordered_nodes)) if ordered_nodes else 0
    used_nodes = set()
    missing_anchors = False
    feature_order = ('leader_homes', 'barracks', 'noble_homes', 'worker_housing', 'apartments', 'market_district', 'religious_building')
    if ordered_nodes:
        ordered_nodes = ordered_nodes[cursor:] + ordered_nodes[:cursor]
    cursor = 0
    for feature_name in feature_order:
        spec = layout_profile['features'][feature_name]
        count = _resolve_feature_count(spec, city_population)
        if not _profile_fits_feature(spec, population_profile):
            count = 0
        anchors = []
        for candidate in ordered_nodes[cursor:cursor + count]:
            x, z = points[candidate]
            anchors.append({
                'node': candidate,
                'x': x,
                'z': z,
                'distance_to_city_m': anchor_distance.get(candidate, 0.)
            })
            used_nodes.add(candidate)
        cursor += len(anchors)
        if len(anchors) < count:
            missing_anchors = True
        features[feature_name] = {'target_count': count, 'count': len(anchors), 'anchors': anchors}
    if missing_anchors:
        city_plan['fallback'] = {'reason': 'Not enough valid non-water land anchors for requested feature counts within local search band.'}
    if building_pack is None:
        building_pack = {'id': None, 'building_options': []}
    if not isinstance(building_pack, dict):
        raise ValueError('building_pack must be a city building pack object')
    building_plan = _build_city_building_plan(
        rng,
        city_seed,
        population_profile,
        city_population,
        city_plan['river']['bridge_recommended'],
        ordered_nodes,
        anchor_distance,
        river_neighbors,
        river,
        used_nodes,
        points,
        building_pack,
        graph
    )
    city_plan['building_pack_id'] = building_pack['id']
    city_plan['buildings'] = building_plan
    city_plan['required_assets'] = building_plan['required_assets']
    city_plan['required_asset_count'] = building_plan['required_asset_count']
    city_plan['required_node_slots'] = building_plan['required_node_slots']
    if building_plan['missing_anchors']:
        city_plan['fallback'] = {'reason': 'Not enough valid non-water land anchors for requested feature and building placement counts within local search band.'}
    city_plan['features'] = features
    city_plan['constraints'] = {'max_anchor_slope_degrees': placement['max_anchor_slope_degrees'],
                                'river_buffer_m': placement['river_buffer_m'],
                                'min_river_distance_m': placement['river_buffer_m']}
    return city_plan


def _city_building_packs():
    return _validate_building_packs(building_pack_data())


def _pick_city_building_pack(city_seed, profile_id, biome, height_m, slope_deg, resource, freshwater_m, pack_catalog, variant_id=None):
    candidates = []
    for pack in pack_catalog['packs']:
        if pack['profiles'] is not None and profile_id not in pack['profiles']:
            continue
        if (pack['biomes'] is not None or pack['biome_variants']) and biome not in (pack['biomes'] or set()) and variant_id not in pack['biome_variants']:
            continue
        if not (pack['height_min'] <= height_m <= pack['height_max']):
            continue
        if resource < pack['resource_min'] or resource > pack['resource_max']:
            continue
        if slope_deg > pack['slope_max']:
            continue
        if not (pack['water_distance_min'] <= freshwater_m <= pack['water_distance_max']):
            continue
        candidates.append((pack['id'], pack['weight']))
    if not candidates:
        return pack_catalog['fallback_pack_id']
    total = sum(weight for _, weight in candidates)
    draw = random.Random(city_seed).random() * total
    current = 0.
    for pack_id, weight in candidates:
        current += weight
        if draw <= current:
            return pack_id
    return candidates[-1][0]


def shortest_paths(graph,start,cost,targets=None):
    distances=[math.inf]*len(graph);parent=[-1]*len(graph);distances[start]=0
    queue=[(0,start)];remaining=set(targets) if targets is not None else None
    while queue:
        value,i=heapq.heappop(queue)
        if value!=distances[i]:continue
        if remaining is not None:
            remaining.discard(i)
            if not remaining:break
        for j,d in graph[i]:
            edge=cost(i,j,d)
            if edge is None:continue
            candidate=value+edge
            if candidate<distances[j]:
                distances[j]=candidate;parent[j]=i;heapq.heappush(queue,(candidate,j))
    return distances,parent



def road_cost_function(points,water,height,flood,river,cfg,hazard=None):
    n=cfg.size
    lookup={p:i for i,p in enumerate(points)}
    def cost(i,j,d):
        if water[i] or water[j] or d<=0:return None
        if hazard is not None and max(hazard[i],hazard[j])>cfg.human_magic_limit:return None
        xi,zi=points[i];xj,zj=points[j]
        # A diagonal cannot slip between two water-filled corner cells.
        if xi!=xj and zi!=zj and zi not in (0,n-1) and zj not in (0,n-1):
            if water[lookup[(xi,zj)]] or water[lookup[(xj,zi)]]:return None
            if hazard is not None and max(hazard[lookup[(xi,zj)]],hazard[lookup[(xj,zi)]])>cfg.human_magic_limit:return None
        grade=abs(height[j]-height[i])/d
        if grade>cfg.road_max_grade:return None
        return d*(1+12*grade**2+.5*(flood[i]+flood[j]))+(cfg.bridge_cost if river[i] or river[j] else 0)
    return cost


def reachable_support(graph,starts,cost,reach):
    """Support must follow passable terrain, not a circle across water or cliffs."""
    from .terrain_humans import allocate_access
    distances,owners,_=allocate_access(graph,[(node,k) for k,node in enumerate(starts)],cost,reach)
    return [owner>=0 and distances[i]<=reach for i,owner in enumerate(owners)]


def habitat_capacity(areas,scores,eligible,land_per_city):
    """Whole communities supported by quality-weighted habitat footprint; no minimum."""
    return math.floor(sum(areas[i]*scores[i] for i in eligible)/1e6/land_per_city)


def city_capacity(weighted_habitat_km2, allowance, profile):
    return min(math.floor(weighted_habitat_km2/profile['land_per_city_km2']),allowance//profile['minimum_founding_residents'])


def life_capacity(areas,potentials):
    """100 residents per fully productive km2: explicit provisional food calibration.

    Overlapping species claims divide each cell's best supported capacity; they
    never multiply that cell's capacity. Fractional residents remain unallocated.
    """
    totals={p:0. for p in potentials};total=0.
    for i,area in enumerate(areas):
        values={p:field[i] for p,field in potentials.items()};weight=sum(values.values())
        if weight<=0:continue
        capacity=area/1e6*100*max(values.values());total+=capacity
        for p,value in values.items():totals[p]+=capacity*value/weight
    return math.floor(total),{p:math.floor(value) for p,value in totals.items()}



def _settlement_names(seed,selected,points,peoples):
    """A name per settled node, in each people's own language.

    This replaces a 24-word English list indexed by founding order. That index was the
    problem: `names[k%24]` renamed every later city when one was founded earlier, and it
    could not survive an age advance without the explicit copy-back downstream. Keying on
    the node and its coordinates instead gives a name that is a property of the place and
    the people, not of the order they happened to be founded in.

    Naming runs in node order rather than founding order so that collision resolution is
    canonical: whichever city is processed second re-draws, and which one that is must not
    depend on how the founding loop happened to be sequenced. The redraw is bounded and
    uses child_seed's third parameter, so a duplicate yields another authentic name rather
    than a numeric suffix.

    Returns {node: (name, gloss)}. The gloss is the English reading of the roots the name
    was built from, so a consumer can say that Bargdorn is the wood-hold.
    """
    import heritage
    lexicon=heritage.lexicon();profile_by_node={node:peoples[k] for k,node in enumerate(selected)}
    resolved={};named={};taken=set()
    for node in sorted(profile_by_node):
        profile=profile_by_node[node]
        if profile not in resolved:
            resolved[profile]=heritage.resolve(profile,entity_rules(profile)['parent_race_id'])
        x,z=points[node];domain=f'city-name-{node}-{x}-{z}-{profile}'
        for variation in range(8):
            draw=random.Random(child_seed(seed,domain,variation))
            name,gloss=heritage.settlement_name(resolved[profile],lexicon,draw)
            if name.lower() not in taken:break
        taken.add(name.lower());named[node]=(name,gloss)
    return named


def add_settlements(result,cfg):
    if not result.get('climate') or cfg.phase<7:return result
    from .terrain_profiles import get_profile
    profile=get_profile(cfg.population_profile)
    building_packs=_city_building_packs()
    started=perf_counter();n=cfg.size;r=result['effective_config']['globe_radius']
    points,areas,graph=sphere_grid(n,r);layers=result['layers']
    def values(key):return [layers[key][z][x] for x,z in points]
    height=values('height');water=values('water_type');slope=values('slope')
    hazard=values('magic_hazard') if 'magic_hazard' in layers else [0.]*len(points)
    temp=values('temperature');wet=values('moisture');river=values('rain_river')
    freshwater=[i for i in range(len(points)) if (water[i]==2 or river[i]) and (not cfg.world_recipe or layers['salinity'][points[i][1]][points[i][0]]<.2)]
    distances=[math.inf]*len(points);source=[-1]*len(points);queue=[]
    for i in freshwater:distances[i]=0;source[i]=i;heapq.heappush(queue,(0,i))
    while queue:
        distance,i=heapq.heappop(queue)
        if distance!=distances[i]:continue
        for j,d in graph[i]:
            if water[j]==1:continue
            if distance+d<distances[j]:
                distances[j]=distance+d;source[j]=source[i];heapq.heappush(queue,(distance+d,j))
    river_cells=[i for i in range(len(points)) if river[i]]
    river_distances=_dijkstra_distances(graph,river_cells)
    seed=child_seed(cfg.seed,'settlements');rng=random.Random(seed)
    layout_profiles=_load_city_layout_profiles()
    vectors=[direction(x,z,n) for x,z in points];resource=[];flood=[];scores=[]
    for i,p in enumerate(vectors):
        resource.append(layers['metal_richness'][points[i][1]][points[i][0]] if cfg.world_recipe else max(0,min(1,.5+.8*perlin3(*(v*4 for v in p),seed))))
        level=layers['water_surface'][points[source[i]][1]][points[source[i]][0]] if source[i]>=0 else 0
        flood.append(math.exp(-distances[i]/80)*max(0,1-max(0,height[i]-level)/10))
        score=(profile['water_weight']*math.exp(-distances[i]/profile['water_reach'])
               +profile['slope_weight']*math.exp(-(slope[i]/profile['slope_comfort'])**2)
               +profile['climate_weight']*math.exp(-((temp[i]-profile['temperature_ideal'])/profile['temperature_tolerance'])**2)
               +profile['moisture_weight']*max(0,1-abs(wet[i]-profile['moisture_ideal']))
               +profile['resource_weight']*resource[i]-profile['flood_penalty']*flood[i]
               +biome_preference(profile,layers['biome'][points[i][1]][points[i][0]],cell_variant(result,*points[i])))
        scores.append(max(0,min(1,score-profile['magic_penalty']*hazard[i])) if water[i]==0 else 0)
    eligible=[i for i in range(len(points)) if water[i]==0 and slope[i]<profile['site_slope_limit'] and hazard[i]<=cfg.human_magic_limit]
    from .terrain_profiles import civilization_ids, profiles as profile_registry
    from .terrain_civilizations import landmass_context, environment_at, eligible_civilizations, classify_cities, civilization_report,matches
    species_ids=civilization_ids() if cfg.population_profile=='mixed' else (cfg.population_profile,)
    contexts=landmass_context(points,areas,graph,water)
    registry=profile_registry()
    rules={key:entity_rules(key) for key in species_ids};defaults=section('defaults')
    entity_habitats=[set(eligible_civilizations(environment_at(result,x,z,contexts[i]),registry)) for i,(x,z) in enumerate(points)]
    score_sets={};habitats={};potentials={};profiles={p:get_profile(p) for p in species_ids}
    from .terrain_humans import farming_potential
    for species,p in profiles.items():
        settlement=rules[species]['settlement'];economy=rules[species]['economy']
        species_hazard=values('magic_risk_'+species) if cfg.world_recipe and 'magic_risk_'+species in layers else hazard
        field=[];candidates=[];potential=[]
        for i,(x,z) in enumerate(points):
            biome=layers['biome'][z][x]
            score=(p['water_weight']*math.exp(-distances[i]/p['water_reach'])
                +p['slope_weight']*math.exp(-(slope[i]/p['slope_comfort'])**2)
                +p['climate_weight']*math.exp(-((temp[i]-p['temperature_ideal'])/p['temperature_tolerance'])**2)
                +p['moisture_weight']*max(0,1-abs(wet[i]-p['moisture_ideal']))
                +p['resource_weight']*resource[i]-p['flood_penalty']*flood[i]
                +biome_preference(p,biome,cell_variant(result,x,z))-p['magic_penalty']*species_hazard[i])
            if cfg.world_recipe:
                score+=layers['coastal_support'][z][x]*settlement['coastal_score_weight']
                if settlement['resource_score_weight']:score+=settlement['resource_score_weight']*resource[i]
            field.append(max(0,min(1,score)) if not water[i] else 0)
            habitat=species in entity_habitats[i]
            environment=dict(environment_at(result,x,z,contexts[i]),resource=resource[i],slope=slope[i],height=height[i],
                             tpi=layers['tpi'][z][x],variant=cell_variant(result,x,z),coastal_support=layers['coastal_support'][z][x] if cfg.world_recipe else 0.)
            habitat=habitat and matches(settlement['world_habitat' if cfg.world_recipe else 'surface_habitat'],environment)
            if cfg.world_recipe:
                if biome==17:habitat=False
            safe=not water[i] and species_hazard[i]<=(p['mutation_limit'] if cfg.world_recipe else min(cfg.human_magic_limit,p['mutation_limit']))
            suitable=habitat and safe and slope[i]<p['site_slope_limit']
            if settlement['freshwater_reach_multiplier'] is not None:suitable=suitable and distances[i]<=p['water_reach']*settlement['freshwater_reach_multiplier']
            if suitable:candidates.append(i)
            fresh=distances[i] if math.isfinite(distances[i]) else -1
            _,food=farming_potential(slope[i],temp[i],wet[i],flood[i],fresh,p['irrigation'],p)
            food*=biome_food_multiplier(p,biome,cell_variant(result,x,z))*(1-species_hazard[i])
            if cfg.world_recipe and biome==17:food=0.
            potential.append(food if safe and slope[i]<p['work_slope_limit'] and (suitable or settlement['support_outside_habitat']) else 0.)
        if settlement['support_outside_habitat']:
            support=reachable_support(graph,candidates,road_cost_function(points,water,height,flood,river,cfg,hazard),cfg.support_reach)
            potential=[value if support[i] else 0. for i,value in enumerate(potential)]
            layers[species+'_support_reach']=node_grid([int(v) for v in support],points,n)
        if cfg.world_recipe:
            from .terrain_world import options
            from .terrain_society import water_cost
            from .terrain_humans import allocate_access
            o=options(cfg);depth=values('water_depth')
            starts={j for i in candidates for j,d in graph[i] if water[j]==1 and depth[j]>=.1 and species_hazard[j]<=p['mutation_limit']}
            fishing_cost=water_cost(points,water,depth,species_hazard,p['mutation_limit'],.1)
            marine_distance,_,_=allocate_access(graph,[(i,0) for i in starts],fishing_cost,o['fishing_reach']*economy['fishing_reach_multiplier'])
            for i,(x,z) in enumerate(points):
                if math.isfinite(marine_distance[i]):potential[i]=layers['fishing_productivity'][z][x]*o['fish_productivity']/100
        score_sets[species]=field;habitats[species]=candidates;potentials[species]=potential
    inferred=cfg.world_recipe or cfg.auto_parameters or cfg.population_profile=='mixed'
    cap,allowances=life_capacity(areas,potentials)
    quotas={};footprints={}
    for species,p in profiles.items():
        footprints[species]=sum(areas[i]*score_sets[species][i] for i in habitats[species])/1e6
        capacity=city_capacity(footprints[species],allowances[species],p)
        quotas[species]=capacity if inferred else min(capacity,cfg.settlement_count)
    if not cfg.auto_parameters and cfg.settlement_count==0:quotas={p:0 for p in profiles}
    # The shared ceiling is the ground itself: cities must stand a settlement spacing
    # apart, so habitable land divided by the densest packing of that separation is
    # how many can exist at all. It is applied after every entity is assessed, so an
    # early registry entry cannot exhaust the budget before a later one is considered.
    habitable=set()
    for candidates in habitats.values():habitable.update(candidates)
    habitable_km2=sum(areas[i] for i in habitable)/1e6
    # Cities cannot be packed closer than the raster can separate them. Spacing alone
    # bounded this while the world was 11 km across and a cell was 87 m, but a coarse
    # grid on a large world inverts that: at 200 km circumference a size-17 grid has
    # 12.5 km cells against an 8 km spacing, so the area ceiling admitted about 63
    # cities onto 289 nodes -- a city every four or five nodes, each then planning a
    # full crop. The binding spacing is whichever is coarser.
    cell_spacing_m=2*math.pi*r/(n-1)
    resolvable_spacing_m=max(cfg.settlement_spacing,cell_spacing_m)
    per_city_km2=math.sqrt(3)/2*(resolvable_spacing_m/1000)**2
    packing=int(math.floor(habitable_km2/per_city_km2)) if per_city_km2>0 else 0
    # A world that infers its own quotas is ceilinged by its ground, not by a count
    # the caller never set: the quota line above already reads `inferred`, and the two
    # have to agree or a recipe world silently keeps the settlement_count default.
    #
    # Asking for no cities is not the same as asking for no ceiling, and it outranks
    # the ground: a caller who wants an empty world gets one, inferred or not.
    # A caller who lowers the ceiling is asking for fewer cities and gets them, inferred
    # or not: `settlement_count` is published as "Maximum surface cities", so a request
    # for two that silently returns ten is a broken parameter rather than a ground rule.
    # Leaving it at the recipe default still means "no ceiling but the ground", which is
    # what the inferred path is for.
    from .terrain_world import default_config
    asked_for_fewer=cfg.settlement_count<default_config(cfg.world_recipe or 3).settlement_count
    if not cfg.auto_parameters and cfg.settlement_count==0:limit=0
    elif inferred and not asked_for_fewer:limit=packing
    else:limit=min(packing,cfg.settlement_count)
    while sum(quotas.values())>limit:
        key=max(quotas,key=lambda p:(quotas[p],p));quotas[key]-=1
    if cfg.world_recipe:scores=score_sets[species_ids[0]]
    from .founding import found_cities
    parents=section('parent_races')
    owners={key:rules[key]['parent_race_id'] for key in profiles}
    parents={key:value for key,value in parents.items() if key in owners.values()}
    survivors=[dict(s,parent_race_id=owners[s['population_profile']]) for s in result.get('_survivors',[])]
    def founding_distance(i,j):
        return r*math.acos(max(-1,min(1,sum(a*b for a,b in zip(vectors[i],vectors[j])))))
    founded,founding=found_cities(seed,parents,owners,quotas,habitats,score_sets,founding_distance,
                                cfg.settlement_spacing,math.pi*r,survivors,[ruin['node'] for ruin in result.get('ruins',[])],food_allowances=allowances,minimum_residents={k:p['minimum_founding_residents'] for k,p in profiles.items()},city_limit=limit,magic_enabled=bool(cfg.magic_enabled),diaspora_bonus_used=result.get('settlements',{}).get('founding',{}).get('diaspora_bonus_used',[]) if '_survivors' in result else [],used_civilizations=result.get('settlements',{}).get('founding',{}).get('used_civilizations',[]) if '_survivors' in result else [],start_year=(result.get('settlements',{}).get('founding',{}).get('end_year',0)+section('founding_rules')['years_per_round']) if '_survivors' in result else 0,**section('founding_rules'))
    quotas=founding['effective_quotas']
    selected=[s['node'] for s in founded];peoples=[s['population_profile'] for s in founded];outposts=[]
    if inferred:
        result['population_budget']={'version':4,'world_cap':cap,'allowances':allowances,
            'shares':{p:allowances[p]/cap if cap else 0 for p in profiles},
            'weighted_habitat_km2':footprints,'requested_cities':quotas,
            'calibration':{'residents_per_productive_km2':100,'minimum_city_region_residents':{k:p['minimum_founding_residents'] for k,p in profiles.items()},'spacing_city_ceiling':packing,'habitable_km2':habitable_km2},
            'method':'Capacity integrates area-weighted farming potential, climate, freshwater/irrigation, slope, biome and mutation penalties. Dwarven productive hinterland may extend beyond mineral uplands only over safe terrain routes within support reach. Overlapping peoples split each cell capacity. Provisional 100 residents per fully productive km2, not validated agricultural yields; access and trade can reduce realized support. Cities require habitat footprint and their civilization-specific minimum regional residents; no species count or majority guarantee. Diaspora can waive a city-count footprint quota for an unused civilization with its required supported residents, once per parent; habitat and spacing still apply. Unsettled capacity remains unused.'}
        for species,field in potentials.items():layers['life_capacity_'+species]=node_grid(field,points,n)
        if cfg.auto_parameters:
            result['config']['settlement_count']=sum(quotas.values())
            result['effective_config']['settlement_count']=sum(quotas.values())
            result['derivation']['settings']['settlement_count']={'value':sum(quotas.values()),'source':'quality-weighted eligible habitat and productive capacity per people; no minimum; ceiling is the densest packing of the settlement spacing over habitable land'}
    for species,field in score_sets.items():layers['suitability_'+species]=node_grid(field,points,n)
    named=_settlement_names(seed,selected,points,peoples)
    sites=[]
    for k,i in enumerate(selected):
        x,z=points[i];outpost=i in outposts
        city_seed=child_seed(seed,f'building-pack-{i}-{k}-{x}-{z}-{peoples[k]}')
        building_pack_id=_pick_city_building_pack(city_seed,peoples[k],layers['biome'][z][x],height[i],slope[i],resource[i],
                                                 distances[i] if math.isfinite(distances[i]) else -1,building_packs,cell_variant(result,x,z))
        pack_entry=building_packs['pack_index'].get(building_pack_id)
        if pack_entry is None:
            pack_entry = building_packs['pack_index'][building_packs['fallback_pack_id']]
        city_river_distance = river_distances[i] if math.isfinite(river_distances[i]) else math.inf
        city_layout_profile=_pick_city_layout_profile(pack_entry,layout_profiles,city_river_distance)
        anchor_candidates=_collect_land_anchor_candidates(points,graph,i,river_distances,water,slope,
                                                         city_layout_profile['placement']['max_anchor_slope_degrees'],
                                                         city_layout_profile['placement']['river_buffer_m'])
        city_layout=_build_city_layout_plan(city_seed,i,points,city_layout_profile,peoples[k],None,city_river_distance,graph[i],river,anchor_candidates,graph,pack_entry)
        sites.append({'id':k,'name':named[i][0],'name_gloss':named[i][1],'population_profile':peoples[k],
            **{key:founded[k].get(key) for key in ('founding_year','migration_source_node','source_civilization_id','migration_distance_m','cultural_branch','diaspora','diaspora_reason','diaspora_bonus')},
            'parent_race_id':founded[k]['parent_race_id'],'founding_turn':founded[k].get('founding_turn',1),'founding_capital':founded[k].get('founding_capital',False),
            'node':i,'x':x,'z':z,'direction':vectors[i],'height_m':height[i],'outpost':outpost,'kind':'city',
            'suitability':score_sets[peoples[k]][i],'freshwater_distance_m':distances[i] if math.isfinite(distances[i]) else None,
            'slope_degrees':slope[i],'temperature_c':temp[i],'moisture':wet[i],'flood_risk':flood[i],
            'resource_potential':resource[i],'city_layout':city_layout,
            'building_pack_id':building_pack_id,'building_pack_seed':city_seed,'building_pack_version':building_packs['schema_version'],
            'reason':rules[peoples[k]]['settlement']['reason'] or (defaults['outpost_site_reason'] if outpost else defaults['normal_site_reason'])})
        if cfg.world_recipe:
            p=profiles[peoples[k]];risk=layers.get('magic_risk_'+peoples[k],layers.get('magic_hazard',[[0.]*n]*n))[z][x]
            sites[-1]['suitability_factors']={
                'freshwater':p['water_weight']*math.exp(-distances[i]/p['water_reach']),
                'slope':p['slope_weight']*math.exp(-(slope[i]/p['slope_comfort'])**2),
                'temperature':p['climate_weight']*math.exp(-((temp[i]-p['temperature_ideal'])/p['temperature_tolerance'])**2),
                'moisture':p['moisture_weight']*max(0,1-abs(wet[i]-p['moisture_ideal'])),
                'resources':p['resource_weight']*resource[i], 'flood':-p['flood_penalty']*flood[i],
                'biome':biome_preference(p,layers['biome'][z][x],cell_variant(result,x,z)), 'magic':-p['magic_penalty']*risk,
                'coastal_support':layers['coastal_support'][z][x]*rules[peoples[k]]['settlement']['coastal_score_weight'],
                defaults['resource_score_factor_label']:rules[peoples[k]]['settlement']['resource_score_weight']*resource[i]}
    if cfg.world_recipe==3:
        previous={s['node']:s for s in result.get('_survivors',result.get('settlements',{}).get('sites',[]))}
        for site in sites:
            old=previous.get(site['node'])
            if old and old['population_profile']==site['population_profile']:
                # war_history travels with the city: a survivor that rebuilds its
                # hinterland is still the city that fought, and its forts answer to that.
                for key in ('uid','source_culture','founded_age','name','war_history'):
                    if key in old:site[key]=old[key]
    if 'population_budget' in result:
        budget=result['population_budget']
        if cfg.world_recipe:
            budget['method']+=' New recipe includes bounded potentially reachable marine habitat, shared across peoples once per cell. Actual fishing delivery requires allocated hamlets and is assessed separately.'
        for species,allowance in budget['allowances'].items():
            members=[s for s in sites if s['population_profile']==species]
            for index,site in enumerate(members):
                residents=allowance//len(members)+(index<allowance%len(members))
                urban=round(residents*.55)
                site.update(population_estimate=residents,urban_population_estimate=urban,rural_population_estimate=residents-urban)
                layout_profile=layout_profiles['profiles'][site['city_layout']['layout_profile_id']]
                site_river_distance=river_distances[site['node']]
                site_pack_entry = building_packs['pack_index'].get(site['building_pack_id'], building_packs['pack_index'][building_packs['fallback_pack_id']])
                anchors=_collect_land_anchor_candidates(points,graph,site['node'],river_distances,water,slope,
                                                       layout_profile['placement']['max_anchor_slope_degrees'],
                                                       layout_profile['placement']['river_buffer_m'])
                site['city_layout']=_build_city_layout_plan(site['building_pack_seed'],site['node'],points,layout_profile,site['population_profile'],residents,
                                                           site_river_distance if math.isfinite(site_river_distance) else math.inf,graph[site['node']],river,anchors,graph,site_pack_entry)
        budget['placed_cities']={p:sum(s['population_profile']==p for s in sites) for p in budget['shares']}
        result['peoples']={p:get_profile(p) for p in budget['shares']}
        budget['allocated']=sum(s['population_estimate'] for s in sites)
        budget['unallocated']=budget['world_cap']-budget['allocated']
    layers.update({'suitability' :node_grid(scores,points,n),'flood_risk':node_grid(flood,points,n),
                   'resource_potential':node_grid(resource,points,n),
                   'freshwater_distance':node_grid([v if math.isfinite(v) else -1 for v in distances],points,n)})
    classify_cities(sites)
    result['civilizations']=civilization_report(sites)
    result['settlements']={'version':15,'founding':founding,'population_profile':cfg.population_profile,'sites':sites,'seed':seed,'requested':sum(result['population_budget']['requested_cities'].values()) if 'population_budget' in result else cfg.settlement_count,
        'method':'Candidate sites, not built cities or population simulation. Resources are seeded potential, flood risk a proximity/height proxy. Outposts can accept poor conditions; water cells and slopes beyond the selected population limit remain excluded. City assets are selected from deterministic data-driven building packs.'}
    site_end=perf_counter();result['timing_ms']['settlements']=(site_end-started)*1000
    if cfg.phase>=8:
        cost=road_cost_function(points,water,height,flood,river,cfg,hazard)
        candidates=[];targets={s['node'] for s in sites}
        for a,site in enumerate(sites):
            if cfg.world_recipe:
                from dataclasses import replace
                p=profiles[site['population_profile']]
                risk=values('magic_risk_'+site['population_profile']) if 'magic_risk_'+site['population_profile'] in layers else hazard
                cost=road_cost_function(points,water,height,flood,river,replace(cfg,human_magic_limit=p['mutation_limit'],road_max_grade=p['road_grade_limit']),risk)
            distance,parent=shortest_paths(graph,site['node'],cost,targets)
            for b in range(a+1,len(sites)):
                goal=sites[b]['node']
                if not math.isfinite(distance[goal]):continue
                path=[];i=goal
                while i!=site['node']:path.append(i);i=parent[i]
                path.append(i);path.reverse();candidates.append((distance[goal],a,b,path))
                if cfg.world_recipe:
                    other=profiles[sites[b]['population_profile']]
                    other_risk=values('magic_risk_'+sites[b]['population_profile']) if 'magic_risk_'+sites[b]['population_profile'] in layers else hazard
                    other_cost=road_cost_function(points,water,height,flood,river,replace(cfg,human_magic_limit=other['mutation_limit'],road_max_grade=other['road_grade_limit']),other_risk)
                    if any(other_cost(i,j,next(d for k,d in graph[i] if k==j)) is None for i,j in zip(path,path[1:])):candidates.pop()
        groups=list(range(len(sites)));roads=[]
        def root(i):
            while groups[i]!=i:i=groups[i]
            return i
        for value,a,b,path in sorted(candidates):
            ra,rb=root(a),root(b)
            if ra==rb:continue
            groups[ra]=rb
            length=sum(next(d for j,d in graph[i] if j==k) for i,k in zip(path,path[1:]))
            crossings=[[i,j] for i,j in zip(path,path[1:]) if river[i] or river[j]]
            roads.append({'from':a,'to':b,'nodes':path,'length_m':length,'cost':value,'river_crossings':crossings})
        result['roads']={'version':1,'routes':roads,'components':len({root(i) for i in range(len(sites))}),
            'method':'Minimum spanning forest of shortest terrain-cost routes. Lakes/ocean and edges above max grade are forbidden. River crossings incur a penalty and are bridge candidates, not engineered bridges. Disconnected islands remain disconnected.'}
        result['timing_ms']['roads']=(perf_counter()-site_end)*1000
    if 'magic' in result:
        result['settlements']['method']+=' All city sites must pass the mutation hazard limit, including difficult-site cities.'
        if 'roads' in result:
            result['roads']['version']=2
            result['roads']['method']+=' Mutation above the human safety limit also forbids road nodes and diagonal corners.'
    result['timing_ms']['total']+=(perf_counter()-started)*1000
    return result
