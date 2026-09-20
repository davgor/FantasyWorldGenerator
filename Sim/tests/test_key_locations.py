"""Key locations are chosen from a finished world's own record, and change nothing in it.

Hand-built worlds keep this fast and independent of terrain_history; the generated-world
conformance check lives with the world schema tests, which already build one world.

The pins matter as much as the behaviour. This package carries its own copies of
``child_seed`` and of the sphere-grid geometry, because it reads only world JSON and never
imports the generator. Copies that nothing compares silently fork the replay contract, so
they are compared here.
"""
import copy
import json
import math
import os
import pathlib
import unittest
from unittest.mock import patch

import key_locations
from key_locations import catalogue as catalogue_rules
from key_locations.core import fields, interiors, naming, placement, succession
from key_locations.core import grid, world as readers
from key_locations.seeds import child_seed, rng

SIZE = 17
RADIUS = 31830.99
SPACING = 2 * math.pi * RADIUS / (SIZE - 1)


def full(value):
    return [[value] * SIZE for _ in range(SIZE)]


def shaped(fn):
    grid_out = [[float(fn(x, z)) for x in range(SIZE)] for z in range(SIZE)]
    for row in grid_out:
        row[-1] = row[0]
    grid_out[0] = [grid_out[0][0]] * SIZE
    grid_out[-1] = [grid_out[-1][0]] * SIZE
    return grid_out


def direction(x, z):
    return list(grid.direction(x, z, SIZE))


def node(x, z):
    return grid.node_index(x, z, SIZE)


def site(kind, uid, name, x, z, **extra):
    record = {'id': uid, 'uid': uid, 'name': name, 'kind': kind, 'node': node(x, z), 'x': x, 'z': z,
              'direction': direction(x, z), 'civilization_id': 'human_heartland',
              'source_culture': 'human_heartland-seed', 'founded_age': 0}
    record.update(extra)
    return record


def layers():
    """Plausible fields: a warm wet continent on one side, cold dry highland on the other."""
    out = {
        'height': shaped(lambda x, z: 400 * math.sin(x / 3.) + 300 * math.cos(z / 2.5) + 500),
        'water_type': [[1. if (x < 3 and 4 < z < 12) else 0. for x in range(SIZE)] for z in range(SIZE)],
        'water_depth': shaped(lambda x, z: max(0., 40 - 6 * x)),
        'slope': shaped(lambda x, z: abs(math.sin(x / 2.)) * .6),
        'tpi': shaped(lambda x, z: math.sin(x / 2.) * math.cos(z / 3.)),
        'rainfall': shaped(lambda x, z: 40 + 30 * math.cos(z / 4.)),
        'moisture': shaped(lambda x, z: .3 + .4 * math.cos(z / 4.)),
        'temperature': shaped(lambda x, z: 22 - 2.2 * abs(z - SIZE / 2)),
        'catchment': shaped(lambda x, z: x * 3.),
        'erosion': shaped(lambda x, z: .2 + .1 * math.sin(x)),
        'deposition': shaped(lambda x, z: .3 * math.cos(x / 2.) + .3),
        'river': shaped(lambda x, z: 1. if z == 8 else .05),
        'shear': shaped(lambda x, z: .4 if x == 12 else .02),
        'volcanic': shaped(lambda x, z: .5 if (x == 14 and z in (6, 7, 8)) else 0.),
        'metal_richness': shaped(lambda x, z: .1 + .5 * (x > 9)),
        'salinity': shaped(lambda x, z: .5 if x < 5 else .05),
        'coastal_exposure': shaped(lambda x, z: .6 if x in (3, 4) else .02),
        'rocky_coast': shaped(lambda x, z: .5 if x == 3 else .01),
        'reef': shaped(lambda x, z: .4 if x == 2 else .01),
        'island_habitat': shaped(lambda x, z: .5 if (x == 5 and z == 3) else .01),
        'harbor_suitability': shaped(lambda x, z: .4 if x == 4 else .05),
        'fishing_productivity': shaped(lambda x, z: .5 if x < 6 else .05),
        'ice_cap': shaped(lambda x, z: .6 if z < 3 else 0.),
        'freshwater_distance': shaped(lambda x, z: abs(z - 8) * 900.),
        'wetland_distance': shaped(lambda x, z: abs(z - 10) * 800.),
        'magic_density': shaped(lambda x, z: .2 + .6 * math.cos((x - 8) / 4.)),
        'magic_hazard': shaped(lambda x, z: .1 + .5 * (x > 12)),
        'magic_growth': shaped(lambda x, z: .3),
        'magic_opposition': shaped(lambda x, z: .2),
        'dominant_magic': shaped(lambda x, z: x % 8),
        'culture_region': [[0. if x < 8 else 1. for x in range(SIZE)] for z in range(SIZE)],
        'relic_incision': shaped(lambda x, z: .4 if z in (5, 11) else .02),
        'relic_gorge': shaped(lambda x, z: .3 if z == 5 else .01),
        'dry_valley': shaped(lambda x, z: .3 if z == 12 else .01),
        'old_river': shaped(lambda x, z: .4 if z == 9 else .02),
        'natural_biome': [[float(4 if x > 8 else 3) for x in range(SIZE)] for z in range(SIZE)],
        'biome_variant': [[float(47 if x == 12 else -1) for x in range(SIZE)] for z in range(SIZE)],
    }
    return out


def world(seed=42, ages=2, **overrides):
    alder = site('city', 'surface-city-0-a', 'Alder City', 6, 6, city_class='capital', population_profile='human_heartland')
    bracken = site('city', 'surface-city-0-b', 'Bracken City', 11, 10, city_class='small', population_profile='human_heartland')
    fallen = site('ruins', 'ruin-surface-city-0-c', 'Fern City', 9, 13, destroyed_age=1, cause='war_civil')
    result = {
        'config': {'seed': seed, 'size': SIZE, 'globe_radius': 10000},
        'effective_config': {'globe_radius': RADIUS},
        'spacing_m': SPACING,
        'generator_version': 16,
        'layers': layers(),
        'settlements': {'version': 15, 'sites': [alder, bracken]},
        'humans': {'version': 8, 'hamlets': [site('hamlet', 'hamlet-1', 'hamlet', 7, 7, role='farming')],
                   'fortresses': [site('fortress', 'fortress-1', 'fortress', 5, 9)],
                   'cultures': [{'id': 'human_heartland-seed', 'civilization_id': 'human_heartland'}]},
        'roads': {'version': 2, 'routes': [{'from': 0, 'to': 1,
                                            'nodes': [node(x, 8) for x in range(6, 12)], 'length_m': 5 * SPACING}]},
        'ruins': [fallen],
        'beast_nests': {'version': 2, 'sites': [site('lair', 'nest-wyrm-1', 'Ashen wyrm', 14, 4, tier=5,
                                                     family='draconic', species_id='ashen-wyrm')]},
        'magic': {'version': 4, 'school_order': ['weave', 'umbral', 'infernal', 'radiant', 'fire', 'water', 'earth', 'air'],
                  'colleges': [site('wizard_college', 'college-1', 'college', 8, 5)]},
        'religion': {'version': 1, 'gods': [{'id': 'god_red_field', 'name': 'The Red Field'}], 'sites': []},
        'fisheries': {'ports': []},
        'regions': {'landmarks': []},
        'terrain': {'version': 6,
                    'natural_biomes': [{'name': n} for n in
                                       ('Ocean', 'Tundra', 'Desert', 'Grassland', 'Forest', 'Exposed rock',
                                        'Snow', 'Rainforest', 'Lake', 'Marsh', 'Boreal forest', 'Cold tundra',
                                        'Persistent land ice')],
                    'magical_biomes': [{'name': f'variant {i}', 'asset_id': f'terrain.mutation.v{i}'}
                                       for i in range(156)]},
        'history': {'version': 3, 'ages': [{'age': i + 1, 'wars': [], 'events': []} for i in range(ages)]},
    }
    result.update(overrides)
    return result


class Pins(unittest.TestCase):
    """The copied primitives still equal the generator's. An unpinned copy forks replay."""

    def test_seed_helper_matches_the_generator(self):
        from icarus_sim.terrain_tectonics import child_seed as reference
        for master in (0, 1, 42, 4294967295):
            for domain in ('keyloc-place-karst_cave', 'keyloc-site-barrow-91', 'plates'):
                for variation in (0, 3):
                    self.assertEqual(child_seed(master, domain, variation), reference(master, domain, variation))

    def test_grid_geometry_matches_the_generator(self):
        from icarus_sim.terrain_erosion import sphere_grid
        from icarus_sim.terrain_globe import direction as reference_direction
        for n in (9, 17, 33):
            points, areas, _ = sphere_grid(n, RADIUS)
            self.assertEqual(len(points), grid.node_count(n))
            for index, (x, z) in enumerate(points):
                self.assertEqual(grid.node_index(x, z, n), index, f'node index at {(x, z)} size {n}')
                self.assertEqual(grid.cell(index, n), (x, z), f'cell of node {index} size {n}')
                self.assertEqual(grid.direction(x, z, n), reference_direction(x, z, n))
                self.assertAlmostEqual(grid.cell_area_m2(z, n, RADIUS), areas[index], places=6)

    def test_great_circle_and_slerp_stay_on_the_sphere(self):
        a, b = grid.direction(2, 5, SIZE), grid.direction(9, 11, SIZE)
        self.assertAlmostEqual(grid.great_circle_m(a, a, RADIUS), 0., places=6)
        midpoint = grid.slerp(a, b, .5)
        self.assertAlmostEqual(math.sqrt(sum(c * c for c in midpoint)), 1., places=9)
        half = grid.great_circle_m(a, b, RADIUS) / 2
        self.assertAlmostEqual(grid.great_circle_m(a, midpoint, RADIUS), half, places=4)
        self.assertEqual(grid.slerp(a, a, .5), tuple(a))


class Catalogue(unittest.TestCase):
    def test_packaged_catalogue_lints_and_covers_every_family(self):
        document = catalogue_rules.load()
        self.assertGreaterEqual(len(document['archetypes']), 50)
        self.assertEqual(set(catalogue_rules.by_family(document)), set(document['families']))
        tiers = {a['tier'] for a in document['archetypes']}
        self.assertEqual(tiers, {0, 1, 2, 3}, 'every tier should be represented')

    def test_every_tier_two_declares_an_interior_and_no_marker_does(self):
        for archetype in catalogue_rules.load()['archetypes']:
            if archetype['tier'] == 2:
                self.assertIsNotNone(archetype.get('interior'), archetype['id'])
            if archetype['tier'] == 0:
                self.assertIsNone(archetype.get('interior'), archetype['id'])

    def test_broken_catalogues_fail_loudly(self):
        good = catalogue_rules.load()
        cases = {
            'unknown family': lambda d: d['archetypes'][0].update(family='nowhere'),
            'unknown state': lambda d: d['archetypes'][0].update(states={'melted': 1.}),
            'unknown occupant': lambda d: d['archetypes'][0].update(occupants={'aliens': 1.}),
            'bad tier': lambda d: d['archetypes'][0].update(tier=9),
            'bad domain': lambda d: d['archetypes'][0].update(domain='sky'),
            'negative weight': lambda d: d['archetypes'][0].update(states={'natural': -1.}),
            'condition-free requirement': lambda d: d['archetypes'][0].update(requires=[{'layer': 'height'}]),
            'tier two without interior': lambda d: d['archetypes'].append(
                dict(good['archetypes'][0], id='hollow', tier=2, interior=None)),
            'chain on an unknown archetype': lambda d: d['chains'].append(
                dict(d['chains'][0], id='nowhere', archetype='ghost')),
            'chain along an unknown thing': lambda d: d['chains'][0].update(along='sky'),
            'cluster with no anchor': lambda d: d['clusters'][0].pop('anchor_kinds', None) or d['clusters'][0].pop('anchor_families', None),
            'composed archetype that also scatters undeclared': lambda d: [
                a.pop('placement', None) for a in d['archetypes'] if a['id'] == 'waystone'],
            'succession names a stranger': lambda d: d.setdefault('succession', {}).update(nowhere={'chance': .5, 'occupants': {'none': 1.}}),
        }
        for label, break_it in cases.items():
            broken = copy.deepcopy(good)
            break_it(broken)
            with self.assertRaises(ValueError, msg=f'{label} should have been rejected'):
                catalogue_rules.lint(broken)

    def test_duplicate_keys_in_the_document_are_rejected(self):
        with self.assertRaises(ValueError):
            catalogue_rules._pairs([('a', 1), ('a', 2)])


class Placement(unittest.TestCase):
    def setUp(self):
        self.world = world()
        self.cells = readers.cells(self.world, 'land')
        self.layers = {**self.world['layers'], **fields.derive(self.world, readers)}

    def test_land_cells_skip_water_and_the_poles_and_the_seam(self):
        for cell in self.cells:
            self.assertEqual(self.world['layers']['water_type'][cell['z']][cell['x']], 0.)
            self.assertNotIn(cell['z'], (0, SIZE - 1))
            self.assertLess(cell['x'], SIZE - 1)
        water = readers.cells(self.world, 'water')
        self.assertTrue(water)
        self.assertFalse({c['node'] for c in water} & {c['node'] for c in self.cells})

    def test_a_requirement_on_an_absent_layer_places_nothing(self):
        archetype = {'id': 'x', 'requires': [{'layer': 'sulphur', 'min': .1}], 'prefers': []}
        self.assertIsNone(placement.resolve(archetype, self.layers, self.cells))
        self.assertEqual(placement.eligible(archetype, self.layers, self.cells), [])

    def test_percentile_requirements_resolve_against_this_world(self):
        archetype = {'id': 'x', 'requires': [{'layer': 'volcanic', 'above_percentile': .9, 'min': .05}], 'prefers': []}
        chosen = placement.eligible(archetype, self.layers, self.cells)
        self.assertTrue(chosen)
        for cell in chosen:
            self.assertGreaterEqual(self.layers['volcanic'][cell['z']][cell['x']], .05)

    def test_the_absolute_floor_beats_the_percentile_on_a_world_without_the_ground(self):
        """Top eight per cent of nothing is still nothing - this is the lava-tube gate."""
        quiet = copy.deepcopy(self.layers)
        quiet['volcanic'] = full(0.)
        archetype = {'id': 'x', 'requires': [{'layer': 'volcanic', 'above_percentile': .9, 'min': .05}], 'prefers': []}
        self.assertEqual(placement.eligible(archetype, quiet, self.cells), [])

    def test_budget_scales_with_land_and_respects_its_bounds(self):
        self.assertEqual(placement.budget({'per_1000_km2': 2.}, 1000., rng(1, 'b')), 2)
        self.assertEqual(placement.budget({'per_1000_km2': 2.}, 5000., rng(1, 'b')), 10)
        self.assertEqual(placement.budget({'per_1000_km2': 2., 'occurrence': 0.}, 5000., rng(1, 'b')), 0)
        self.assertEqual(placement.budget({'per_1000_km2': 0., 'min_count': 1}, 10., rng(1, 'b')), 1)
        self.assertEqual(placement.budget({'per_1000_km2': 99., 'max_count': 3}, 5000., rng(1, 'b')), 3)

    def test_a_fractional_expectation_is_a_chance_not_a_silent_zero(self):
        """Rounding sent the whole catalogue to zero at once on the 11 km reference world."""
        archetype = {'per_1000_km2': 1.}
        drawn = [placement.budget(archetype, 300., rng(seed, 'b')) for seed in range(400)]
        self.assertEqual(set(drawn), {0, 1}, 'an expectation of 0.3 yields zero or one')
        self.assertAlmostEqual(sum(drawn) / len(drawn), .3, delta=.06)
        big = [placement.budget(archetype, 3500., rng(seed, 'b')) for seed in range(200)]
        self.assertEqual(set(big), {3, 4}, 'an expectation of 3.5 yields three or four, never zero')

    def test_selection_respects_spacing_and_settlement_clearance(self):
        archetype = {'id': 'x', 'requires': [], 'prefers': [{'layer': 'height', 'weight': 1.}],
                     'spacing_m': SPACING * 2, 'settlement_clearance_m': SPACING * 1.5}
        norms = placement.normalisers(self.layers, {'height'}, self.cells)
        settled = readers.settled_directions(self.world)
        chosen = placement.select(archetype, self.layers, self.cells, norms, RADIUS,
                                  rng(1, 'test'), 12, settled=settled)
        self.assertTrue(chosen)
        points = [c['cell']['direction'] for c in chosen]
        for i, a in enumerate(points):
            for b in points[i + 1:]:
                self.assertGreaterEqual(grid.great_circle_m(a, b, RADIUS), SPACING * 2)
            for town in settled:
                self.assertGreaterEqual(grid.great_circle_m(a, town, RADIUS), SPACING * 1.5)

    def test_claimed_nodes_are_left_to_whoever_placed_them(self):
        claimed = {c['node'] for c in self.cells[:40]}
        archetype = {'id': 'x', 'requires': [], 'prefers': [], 'spacing_m': 0., 'settlement_clearance_m': 0.}
        norms = placement.normalisers(self.layers, set(), self.cells)
        chosen = placement.select(archetype, self.layers, self.cells, norms, RADIUS, rng(1, 't'), 50, claimed=claimed)
        self.assertTrue(chosen)
        self.assertFalse({c['cell']['node'] for c in chosen} & claimed)

    def test_a_flat_layer_scores_neutral_instead_of_dividing_by_zero(self):
        flat = {**self.layers, 'height': full(7.)}
        norms = placement.normalisers(flat, {'height'}, self.cells)
        self.assertIsNone(norms['height'])
        value, _ = placement.score({'prefers': [{'layer': 'height', 'weight': 1.}]}, flat, norms, 4, 4)
        self.assertEqual(value, placement.DEFAULT_SCORE)

    def test_derived_distance_fields_measure_from_the_right_things(self):
        derived = fields.derive(self.world, readers)
        road_z, road_x = 8, 9
        self.assertEqual(derived['road_distance'][road_z][road_x], 0.)
        self.assertGreater(derived['road_distance'][2][2], 0.)
        self.assertEqual(derived['ruin_distance'][13][9], 0.)
        self.assertEqual(derived['settlement_distance'][6][6], 0.)
        for row in derived['road_distance']:
            self.assertEqual(row[0], row[-1], 'the seam column must mirror column zero')

    def test_the_frontier_field_marks_borders_and_not_coastlines(self):
        derived = fields.derive(self.world, readers)
        self.assertEqual(derived['frontier'][6][7], 1.)
        self.assertEqual(derived['frontier'][6][3], 0.)

    def test_distance_from_no_sources_is_the_ceiling_everywhere(self):
        empty = fields.distance_field([], SIZE, SPACING)
        self.assertTrue(all(value == SPACING * SIZE for row in empty for value in row))


class Generation(unittest.TestCase):
    def setUp(self):
        self.world = world()
        self.block = key_locations.generate(self.world)
        self.layers = {**self.world['layers'], **fields.derive(self.world, readers)}

    def test_a_world_yields_locations_across_families_and_tiers(self):
        self.assertEqual(self.block['status'], 'ok')
        self.assertTrue(self.block['sites'])
        summary = self.block['summary']
        self.assertGreaterEqual(len(summary['by_family']), 6)
        self.assertIn('2', summary['by_tier'])

    def test_replay_is_byte_identical_and_the_world_is_untouched(self):
        before = copy.deepcopy(self.world)
        again = key_locations.generate(self.world)
        self.assertEqual(json.dumps(self.block, sort_keys=True), json.dumps(again, sort_keys=True))
        self.assertEqual(before, self.world, 'generation must not mutate the world it reads')

    def test_the_block_is_finite_json(self):
        json.dumps(self.block, allow_nan=False)

    def test_ids_are_a_function_of_position_not_list_position(self):
        """A consumer holding a foreign key must survive the block being re-derived.

        Every id is derived from where the place is, never from where it landed in a list:
        a node for scattered sites, a route key plus metres along it for chain members, and
        the anchor plus offset for cluster members. None of them renumber.
        """
        for record in self.block['sites']:
            if record['placement'] == 'node':
                self.assertEqual(record['id'], f"keyloc-{record['kind']}-{record['node']}")
            else:
                self.assertTrue(record['id'].startswith(f"keyloc-{record['kind']}-"), record['id'])
                self.assertNotIn(' ', record['id'])
        ids = [r['id'] for r in self.block['sites']]
        self.assertEqual(len(ids), len(set(ids)), 'ids must be unique across every placement')

    def test_node_placed_locations_never_share_ground_with_anything(self):
        """The one-per-node rule binds node-placed sites.

        Chain and cluster members stand between cells by design - a waystone every 2 km cannot
        be node-snapped on a 12 km raster - so they are exempt, and marked so a consumer knows.
        """
        scattered = [r for r in self.block['sites'] if r['placement'] == 'node']
        nodes = [r['node'] for r in scattered]
        self.assertEqual(len(nodes), len(set(nodes)))
        self.assertFalse(set(nodes) & readers.claimed_nodes(self.world),
                         'ruins, nests, shrines and colleges keep their own ground')
        self.assertTrue(any(r['placement'] != 'node' for r in self.block['sites']),
                        'this world should compose something, or the exemption is untested')
        for record in self.block['sites']:
            self.assertIn(record['placement'], ('node', 'path', 'cluster'))

    def test_tier_two_carries_an_interior_graph_and_markers_never_do(self):
        for record in self.block['sites']:
            if record['tier'] == 2:
                interior = record['interior']
                self.assertIsNotNone(interior, record['id'])
                ids = {c['id'] for c in interior['chambers']}
                self.assertTrue(interior['chambers'])
                self.assertEqual(interior['chambers'][0]['connects'], [])
                for chamber in interior['chambers']:
                    self.assertLess(chamber['depth'], interior['levels'])
                    for link in chamber['connects']:
                        self.assertIn(link, ids)
                        self.assertNotEqual(link, chamber['id'])
                for entrance in interior['entrances']:
                    self.assertIn(entrance['chamber'], ids)
            else:
                self.assertIsNone(record['interior'], record['id'])

    def test_state_and_occupant_stay_inside_the_published_vocabulary(self):
        for record in self.block['sites']:
            self.assertIn(record['state'], catalogue_rules.STATES)
            self.assertIn(record['occupant'], catalogue_rules.OCCUPANTS)
            self.assertIn(record['threat'], range(1, 6))
            self.assertTrue(record['name'])
            self.assertNotIn('{', record['name'], 'every placeholder must resolve')

    def test_dungeons_emerge_without_a_dungeon_archetype(self):
        kinds = {a['id'] for a in catalogue_rules.load()['archetypes']}
        self.assertNotIn('dungeon', kinds)
        self.assertGreater(self.block['summary']['dungeons'], 0,
                           'occupied tier-2 complexes are what "dungeon" means here')

    def test_a_world_without_volcanism_reports_the_gap_instead_of_approximating(self):
        quiet = world()
        quiet['layers']['volcanic'] = full(0.)
        block = key_locations.generate(quiet)
        placed = {r['kind'] for r in block['sites']}
        self.assertNotIn('lava_tube', placed)
        self.assertNotIn('geyser_basin', placed)
        note = next(d for d in block['diagnostics'] if d['archetype'] == 'lava_tube')
        self.assertEqual(note['placed'], 0)
        self.assertIn('no ground', note['reason'])

    def test_every_archetype_is_accounted_for_in_the_sites_or_the_diagnostics(self):
        reported = {d['archetype'] for d in self.block['diagnostics']} | {r['kind'] for r in self.block['sites']}
        self.assertEqual(reported, {a['id'] for a in catalogue_rules.load()['archetypes']})

    def test_water_archetypes_land_in_water_and_land_archetypes_do_not(self):
        water_nodes = {c['node'] for c in readers.cells(self.world, 'water')}
        for record in self.block['sites']:
            in_water = record['node'] in water_nodes
            self.assertEqual(in_water, record['domain'] in ('water', 'ocean', 'lake'), record['id'])

    def test_every_site_records_the_ground_it_will_be_dressed_against(self):
        """The same cave is a different art set in tundra and rainforest, and a mutated biome
        changes it again. A consumer building art should not have to re-sample rasters."""
        seen_variant = False
        for record in self.block['sites']:
            env = record['environment']
            self.assertIn(env['natural_biome'], range(13), record['id'])
            self.assertTrue(env['natural_biome_name'], record['id'])
            self.assertIsNotNone(env['temperature_c'])
            self.assertIsNotNone(env['moisture'])
            if env['biome_variant'] is not None:
                seen_variant = True
                self.assertTrue(env['variant_asset_id'].startswith('terrain.mutation.'))
                self.assertTrue(env['variant_name'])
            else:
                self.assertIsNone(env['variant_asset_id'], 'unmutated ground names no variant')
        self.assertTrue(seen_variant, 'this world has mutated ground, so some site should sit on it')

    def test_no_two_locations_share_a_name(self):
        """Three silver mines near one city all want the same name; a quest could not tell them apart."""
        names = [r['name'] for r in self.block['sites']]
        duplicated = {n for n in names if names.count(n) > 1}
        self.assertEqual(duplicated, set(), f'{len(duplicated)} names are carried by more than one location')

    def test_a_crowd_of_one_archetype_still_gets_distinct_names(self):
        archetype = {'names': ['the deeps under {near}'], 'family': 'extractive'}
        used = set()
        produced = [naming.unique_name(archetype, {'near': 'Fern'}, rng(i, 'n'), used) for i in range(120)]
        self.assertEqual(len(set(produced)), len(produced), 'one template must survive a crowd')
        self.assertEqual(len(used), len(produced), 'what is recorded must be what is returned')

    def test_chains_are_ordered_runs_at_their_declared_interval(self):
        from key_locations.core.grid import great_circle_m

        self.assertTrue(self.block['chains'], 'a world with roads and a border should chain something')
        by_id = {s['id']: s for s in self.block['sites']}
        for chain in self.block['chains']:
            members = [by_id[m] for m in chain['members']]
            self.assertGreaterEqual(len(members), 2, chain['id'])
            self.assertEqual([m['links']['chain_index'] for m in members], list(range(len(members))),
                             f"{chain['id']} must be ordered along its path")
            for member in members:
                self.assertEqual(member['links']['chain'], chain['id'])
                self.assertEqual(member['placement'], 'path')
            for a, b in zip(members, members[1:]):
                gap = great_circle_m(a['direction'], b['direction'], RADIUS)
                self.assertLess(gap, chain['interval_m'] * 2.6, f"{chain['id']} has a hole in it")

    def test_a_waystone_run_counts_itself_out(self):
        """Eleven stones all reading 'the grey stone' is a scatter wearing a chain's clothes."""
        by_id = {s['id']: s for s in self.block['sites']}
        runs = [c for c in self.block['chains'] if c['archetype'] == 'waystone']
        self.assertTrue(runs)
        names = [by_id[m]['name'] for m in runs[0]['members'][:4]]
        self.assertTrue(any('first' in n for n in names), names)
        self.assertTrue(any('second' in n for n in names), names)
        self.assertNotIn('{ordinal}', ' '.join(names))

    def test_a_beacon_line_can_see_itself(self):
        from key_locations.core.composition import line_of_sight

        by_id = {s['id']: s for s in self.block['sites']}
        checked = 0
        for chain in self.block['chains']:
            if chain['kind'] != 'beacon_line':
                continue
            members = [by_id[m] for m in chain['members']]
            for a, b in zip(members, members[1:]):
                checked += 1
                self.assertTrue(line_of_sight(a['direction'], b['direction'], self.layers, SIZE, RADIUS,
                                              a['height_m'], b['height_m']),
                                f"{a['id']} cannot see {b['id']}, which makes it a tower not a beacon")
        self.assertGreater(checked, 0, 'no beacon line was built, so the sightline rule is untested')

    def test_cluster_members_stand_at_their_declared_offset_from_the_anchor(self):
        from key_locations.core.grid import great_circle_m

        self.assertTrue(self.block['clusters'], 'barrow fields and mines should gather things')
        by_id = {s['id']: s for s in self.block['sites']}
        specs = {c['id']: c for c in catalogue_rules.load()['clusters']}
        for cluster in self.block['clusters']:
            anchor = by_id[cluster['anchor']]
            near, far = specs[cluster['kind']]['offset_m']
            for member in (by_id[m] for m in cluster['members']):
                self.assertEqual(member['placement'], 'cluster')
                self.assertEqual(member['links']['anchor'], anchor['id'])
                gap = great_circle_m(anchor['direction'], member['direction'], RADIUS)
                self.assertGreater(gap, near * .5, f"{member['id']} is on top of its anchor")
                self.assertLess(gap, far * 1.5, f"{member['id']} is too far to belong to {anchor['id']}")

    def test_composed_archetypes_do_not_also_arrive_by_scatter(self):
        document = catalogue_rules.load()
        composed = {c['archetype'] for c in document['chains'] + document['clusters']}
        declared = {a['id'] for a in document['archetypes'] if a.get('also_scatters')}
        for record in self.block['sites']:
            if record['kind'] in composed - declared:
                self.assertNotEqual(record['placement'], 'node',
                                    f"{record['kind']} arrived by two routes that know nothing of each other")

    def test_a_different_seed_moves_the_locations(self):
        other = key_locations.generate(world(seed=7))
        self.assertNotEqual([r['id'] for r in self.block['sites']], [r['id'] for r in other['sites']])


class Succession(unittest.TestCase):
    def context(self, **overrides):
        base = {'near_ruin': False, 'near_nest': False, 'remote': False, 'unstable': False,
                'ages': 2, 'nest_tier': None, 'near_villain': False}
        base.update(overrides)
        return base

    def test_choose_is_stable_and_ignores_dict_order(self):
        forward = {'a': 1., 'b': 1., 'c': 1.}
        backward = {'c': 1., 'b': 1., 'a': 1.}
        for seed in range(20):
            self.assertEqual(succession.choose(forward, rng(seed, 'x')), succession.choose(backward, rng(seed, 'x')))

    def test_a_nearby_ruin_ages_a_site_and_remoteness_empties_it(self):
        archetype = {'domain': 'land', 'states': {'active': 1., 'ruined': 1.},
                     'occupants': {'builders': 1., 'none': 1.}}
        ruined = sum(succession.derive_state(archetype, self.context(near_ruin=True), rng(s, 'a')) == 'ruined'
                     for s in range(200))
        plain = sum(succession.derive_state(archetype, self.context(), rng(s, 'a')) == 'ruined' for s in range(200))
        self.assertGreater(ruined, plain)

    def test_a_water_archetype_is_always_drowned(self):
        archetype = {'domain': 'water', 'states': {'drowned': 1., 'active': 1.}, 'occupants': {'none': 1.}}
        for seed in range(30):
            self.assertEqual(succession.derive_state(archetype, self.context(), rng(seed, 'a')), 'drowned')

    def test_an_active_site_keeps_its_builders_and_an_untended_one_loses_them(self):
        archetype = {'domain': 'land', 'states': {}, 'occupants': {'builders': 1., 'monsters': 1.}}
        active = sum(succession.derive_occupant(archetype, 'active', self.context(), rng(s, 'o')) == 'builders'
                     for s in range(200))
        ruined = sum(succession.derive_occupant(archetype, 'ruined', self.context(), rng(s, 'o')) == 'builders'
                     for s in range(200))
        self.assertGreater(active, ruined)

    def test_succession_needs_an_untended_state_and_a_passed_age(self):
        table = {'extractive': {'chance': 1., 'occupants': {'monsters': 1.}, 'note': 'n'}}
        base = {'state': 'ruined', 'family': 'extractive', 'occupant': 'none', 'tier': 2}
        self.assertIsNone(succession.succeed(dict(base), table, self.context(ages=0), rng(1, 's')))
        self.assertIsNone(succession.succeed(dict(base, state='active'), table, self.context(), rng(1, 's')))
        moved = dict(base)
        record = succession.succeed(moved, table, self.context(), rng(1, 's'))
        self.assertEqual(record['from_occupant'], 'none')
        self.assertEqual(moved['occupant'], 'monsters')

    def test_succession_reports_nothing_when_the_occupant_would_not_change(self):
        table = {'extractive': {'chance': 1., 'occupants': {'monsters': 1.}}}
        site = {'state': 'ruined', 'family': 'extractive', 'occupant': 'monsters', 'tier': 2}
        self.assertIsNone(succession.succeed(site, table, self.context(), rng(1, 's')))

    def test_threat_ranks_an_empty_barrow_below_an_occupied_complex(self):
        empty = {'occupant': 'none', 'state': 'sealed', 'tier': 1}
        infested = {'occupant': 'monsters', 'state': 'corrupted', 'tier': 2}
        self.assertLess(succession.threat(empty, self.context()), succession.threat(infested, self.context()))
        self.assertEqual(succession.threat(empty, self.context()), 1)
        self.assertEqual(succession.threat(infested, self.context()), 5)

    def test_threat_never_leaves_the_rubric(self):
        for occupant in catalogue_rules.OCCUPANTS:
            for state in catalogue_rules.STATES:
                for tier in (0, 1, 2, 3):
                    value = succession.threat({'occupant': occupant, 'state': state, 'tier': tier},
                                              self.context(near_nest=True, nest_tier=5, unstable=True))
                    self.assertIn(value, range(1, 6))

    def test_a_nearby_nest_lifts_threat_to_the_creature_rubric(self):
        site = {'occupant': 'none', 'state': 'natural', 'tier': 1}
        self.assertEqual(succession.threat(site, self.context(near_nest=True, nest_tier=5)), 5)

    def test_threat_tracks_the_whole_creature_range_not_a_truncated_one(self):
        """Creature tier runs 1-5. Capping at 3 would mis-scale exactly where a lair matters."""
        site = {'occupant': 'none', 'state': 'natural', 'tier': 1}
        for nest_tier in (1, 2, 3, 4, 5):
            self.assertEqual(succession.threat(site, self.context(near_nest=True, nest_tier=nest_tier)),
                             max(1, nest_tier))

    def test_a_villain_holding_nearby_raises_threat(self):
        site = {'occupant': 'squatters', 'state': 'abandoned', 'tier': 1}
        quiet = succession.threat(site, self.context())
        held = succession.threat(site, self.context(near_villain=True))
        self.assertEqual(held, quiet + 1)


class Interiors(unittest.TestCase):
    def test_every_plan_produces_a_connected_reachable_graph(self):
        for plan in interiors.PLAN_NOTES:
            archetype = {'family': 'extractive', 'interior': {'plan': plan, 'levels': [2, 4], 'chambers': [8, 14]}}
            interior = interiors.build(archetype, 'abandoned', rng(3, 'i'))
            ids = [c['id'] for c in interior['chambers']]
            reached = {ids[0]}
            for chamber in interior['chambers'][1:]:
                self.assertTrue(set(chamber['connects']) & reached or chamber['connects'],
                                f'{plan}: {chamber["id"]} hangs off nothing')
                reached.add(chamber['id'])
            self.assertEqual(len(ids), len(set(ids)))

    def test_a_drowned_state_floods_more_than_a_dry_one(self):
        archetype = {'family': 'drowned', 'interior': {'plan': 'vault', 'levels': [2, 2], 'chambers': [20, 20]}}
        wet = interiors.build(archetype, 'drowned', rng(5, 'i'))
        dry = interiors.build(archetype, 'sealed', rng(5, 'i'))
        self.assertGreater(sum(c['flooded'] for c in wet['chambers']), sum(c['flooded'] for c in dry['chambers']))

    def test_an_archetype_without_a_spec_gets_no_interior(self):
        self.assertIsNone(interiors.build({'family': 'wayside'}, 'active', rng(1, 'i')))

    def test_a_buried_site_hides_its_entrance(self):
        archetype = {'family': 'funerary', 'interior': {'plan': 'vault', 'levels': [1, 1], 'chambers': [3, 3]}}
        interior = interiors.build(archetype, 'buried', rng(2, 'i'))
        self.assertTrue(interior['entrances'][0]['hidden'])


class Naming(unittest.TestCase):
    def test_city_suffix_is_stripped_and_other_names_are_left_alone(self):
        self.assertEqual(naming.short_name('Fern City'), 'Fern')
        self.assertEqual(naming.short_name('Ashen wyrm'), 'Ashen wyrm')
        self.assertIsNone(naming.short_name(None))

    def test_every_placeholder_resolves_even_with_an_empty_context(self):
        filled = naming.fill('{near} {culture} {school} {god} {adj}', {}, rng(1, 'n'))
        self.assertNotIn('{', filled)

    def test_a_template_needing_a_neighbour_is_skipped_when_there_is_none(self):
        archetype = {'names': ['the caves under {near}', 'the {adj} deeps']}
        for seed in range(25):
            self.assertNotIn('the waste', naming.name_for(archetype, {}, rng(seed, 'n')))

    def test_nearest_breaks_ties_on_name_for_replay_stability(self):
        records = [{'name': 'Beta', 'direction': [1., 0., 0.]}, {'name': 'Alpha', 'direction': [1., 0., 0.]}]
        picked = naming.nearest(records, (1., 0., 0.), lambda a, b: 0.)
        self.assertEqual(picked['name'], 'Alpha')
        self.assertIsNone(naming.nearest([], (1., 0., 0.), lambda a, b: 0.))


class Exteriors(unittest.TestCase):
    """Every location gets a visible arrangement on the ground, in the city plot shape."""

    @classmethod
    def setUpClass(cls):
        cls.world = world()
        cls.world['key_locations'] = key_locations.generate(cls.world)
        cls.plans = key_locations.attach_plans(cls.world)
        cls.by_location = {p['location_id']: p for p in cls.plans['plans']}

    def test_every_placed_location_gets_a_plan_including_markers(self):
        self.assertEqual(self.plans['status'], 'ok')
        sites = {s['id'] for s in self.world['key_locations']['sites']}
        self.assertEqual(set(self.by_location), sites, 'a location without a plan renders as nothing')
        self.assertTrue(all(p['plots'] for p in self.plans['plans']), 'every plan must place something')

    def test_every_archetype_resolves_to_a_kit(self):
        from key_locations.exteriors import kit_for, load

        document = load()
        for archetype in catalogue_rules.load()['archetypes']:
            kit = kit_for(archetype['id'], archetype['family'], document)
            self.assertTrue(kit['parts'], archetype['id'])

    def test_plots_are_in_the_shape_the_city_importer_already_reads(self):
        required = ('id', 'building_id', 'name', 'kind', 'x_m', 'z_m', 'rotation_degrees',
                    'ground_elevation_m', 'foundation_bottom_m', 'plot_m', 'dimensions_m')
        for plan in self.plans['plans']:
            for plot in plan['plots']:
                for key in required:
                    self.assertIn(key, plot, plan['location_id'])
                self.assertGreaterEqual(plot['ground_elevation_m'], plot['foundation_bottom_m'])
                self.assertTrue(0 <= plot['rotation_degrees'] < 360)
                self.assertGreater(plot['plot_m']['width'], 0)
                self.assertGreater(plot['dimensions_m']['height'], 0)

    def test_a_ring_actually_reads_as_a_ring(self):
        """A stone circle whose stones are not on a circle is a scatter with a nicer name."""
        from key_locations.core.exterior import _positions

        draw = rng(1, 'ring')
        placed = _positions('ring', 8, 12., draw, 0.)
        radii = [math.hypot(x, z) for x, z, _ in placed]
        self.assertTrue(all(abs(r - 12.) < 12. * .25 for r in radii), radii)
        angles = sorted(math.atan2(z, x) for x, z, _ in placed)
        gaps = [b - a for a, b in zip(angles, angles[1:])]
        self.assertTrue(all(g > .3 for g in gaps), 'a ring should not clump')

    def test_a_single_arrangement_places_exactly_one_thing_at_the_centre(self):
        from key_locations.core.exterior import _positions

        placed = _positions('single', 1, 10., rng(1, 's'), 0.)
        self.assertEqual(len(placed), 1)
        self.assertEqual((placed[0][0], placed[0][1]), (0., 0.))

    def test_a_marker_is_a_one_plot_plan_rather_than_a_special_case(self):
        markers = [p for p in self.plans['plans'] if p['tier'] == 0]
        self.assertTrue(markers)
        self.assertTrue(all(p['plots'] for p in markers))
        self.assertTrue(any(len(p['plots']) == 1 for p in markers),
                        'a waystone should be one plot, not an arrangement')

    def test_a_ruined_site_gains_rubble_and_an_intact_one_does_not(self):
        def parts_of(state):
            site = dict(self.world['key_locations']['sites'][0], state=state)
            from key_locations.exteriors import generate as plan_all
            block = plan_all(self.world, {'sites': [site]})
            return {p['building_id'] for p in block['plans'][0]['plots']}

        self.assertIn('keyloc.part.rubble_pile', parts_of('ruined'))
        self.assertIn('keyloc.part.overgrown_mound', parts_of('reclaimed'))
        self.assertNotIn('keyloc.part.rubble_pile', parts_of('active'))

    def test_replay_is_byte_identical_and_the_world_is_untouched(self):
        before = copy.deepcopy(self.world)
        again = key_locations.attach_plans(self.world)
        self.assertEqual(json.dumps(self.plans, sort_keys=True), json.dumps(again, sort_keys=True))
        self.assertEqual(before, self.world)
        json.dumps(self.plans, allow_nan=False)

    def test_plans_join_back_to_their_location_by_id(self):
        sites = {s['id']: s for s in self.world['key_locations']['sites']}
        for plan in self.plans['plans']:
            site = sites[plan['location_id']]
            self.assertEqual(plan['kind'], site['kind'])
            self.assertEqual(plan['origin']['node'], site['node'])
            self.assertEqual(plan['origin']['direction'], site['direction'])

    def test_no_plans_without_locations(self):
        empty = world()
        self.assertIsNone(key_locations.attach_plans(empty), 'no locations block, no plans')
        empty['key_locations'] = {'status': 'failed', 'error': 'x'}
        self.assertIsNone(key_locations.attach_plans(empty), 'a failed block plans nothing')

    def test_broken_kits_fail_loudly(self):
        from key_locations import exteriors

        good = exteriors.load()
        cases = {
            'unknown part': lambda d: d['family_kits']['sacred']['parts'].append({'part': 'keyloc.part.ghost'}),
            'unknown arrangement': lambda d: d['family_kits']['sacred'].update(arrangement='spiral'),
            'kit places nothing': lambda d: d['family_kits']['sacred'].update(parts=[]),
            'part without a footprint': lambda d: d['parts'][0].update(plot_m={'width': 0, 'depth': 1}),
            'part with an unknown kind': lambda d: d['parts'][0].update(kind='vibes'),
            'malformed count': lambda d: d['family_kits']['sacred']['parts'][0].update(count=[3, 1]),
        }
        for label, break_it in cases.items():
            broken = copy.deepcopy(good)
            break_it(broken)
            with self.assertRaises(ValueError, msg=f'{label} should have been rejected'):
                exteriors.lint(broken)


class Shaping(unittest.TestCase):
    """A barrow is a mound in the ground, not a mound-shaped mesh on flat terrain."""

    @classmethod
    def setUpClass(cls):
        cls.world = world()
        cls.world['key_locations'] = key_locations.generate(cls.world)
        cls.plans = key_locations.attach_plans(cls.world)

    def _plan(self, kind):
        found = [p for p in self.plans['plans'] if p['kind'] == kind]
        if not found:
            self.skipTest(f'this world grew no {kind}')
        return found[0]

    def test_a_barrow_raises_the_ground_under_it(self):
        from key_locations.core import shaping

        plan = self._plan('barrow')
        entries = plan['terrain']['shaping']
        self.assertTrue(entries, 'a barrow that does not move the ground is a mesh on a field')
        self.assertEqual(entries[0]['shape'], 'mound')
        self.assertGreater(plan['terrain']['relief_m']['raised_m'], 1.5)
        centre = shaping.shaped_height(entries, 0., 0., 100., 100.)
        edge = shaping.shaped_height(entries, 40., 40., 100., 100.)
        self.assertGreater(centre, edge + 1.5, 'the middle of a mound is higher than beyond it')

    def test_a_cut_lowers_and_a_rim_does_both(self):
        from key_locations.core import shaping

        cut = {'shape': 'cut', 'radius_m': 8., 'depth_m': 6., 'x_m': 0., 'z_m': 0.}
        self.assertLess(shaping.delta(cut, 0., 0.), -5.)
        self.assertEqual(shaping.delta(cut, 40., 0.), 0., 'a cut does nothing outside its radius')

        rim = {'shape': 'rim', 'radius_m': 10., 'height_m': 3., 'depth_m': 5., 'x_m': 0., 'z_m': 0.}
        self.assertGreater(shaping.delta(rim, 10., 0.), 1.5, 'the ring itself rises')
        self.assertLess(shaping.delta(rim, 0., 0.), -2., 'the bowl inside falls')
        self.assertAlmostEqual(shaping.delta(rim, 60., 0.), 0., places=6)

    def test_levelling_flattens_toward_the_centre_rather_than_adding_to_it(self):
        from key_locations.core import shaping

        entries = [{'shape': 'level', 'radius_m': 8., 'height_m': 0., 'x_m': 0., 'z_m': 0.}]
        # Ground that slopes away from a centre at 100 m is pulled back toward 100 m.
        self.assertAlmostEqual(shaping.shaped_height(entries, 0., 0., 104., 100.), 100., places=3)
        self.assertGreater(shaping.shaped_height(entries, 30., 0., 104., 100.), 103.,
                           'beyond the radius the ground is untouched')

    def test_plots_are_seated_on_the_shaped_ground_not_the_raw_layer(self):
        """A marker standing on a barrow has to stand on the barrow."""
        plan = self._plan('barrow')
        mound = [p for p in plan['plots'] if p['building_id'] == 'keyloc.part.barrow_mound']
        others = [p for p in plan['plots'] if p['building_id'] != 'keyloc.part.barrow_mound']
        self.assertTrue(mound)
        if others:
            highest = max(p['ground_elevation_m'] for p in plan['plots'])
            flat = _flat_ground(self.world, plan)
            self.assertGreater(highest, flat + 1.,
                               'nothing on this plan sits above the flat ground, so shaping was not applied')

    def test_a_shaped_surface_matches_the_primitives_it_came_from(self):
        from key_locations.core import shaping

        plan = self._plan('barrow')
        surface, entries = plan['terrain']['surface'], plan['terrain']['shaping']
        half = plan['terrain']['bounds_m'][2]
        self.assertEqual(len(surface['heights_m']), surface['size'])
        centre = surface['heights_m'][surface['size'] // 2][surface['size'] // 2]
        corner = surface['heights_m'][0][0]
        self.assertGreater(centre, corner + 1., 'the sampled grid should show the mound too')
        self.assertAlmostEqual(surface['step_m'], 2 * half / (surface['size'] - 1), places=3)

    def test_most_locations_leave_the_ground_alone_and_say_so(self):
        untouched = [p for p in self.plans['plans'] if not p['terrain']['shaping']]
        self.assertTrue(untouched, 'a waystone should not deform anything')
        for plan in untouched:
            self.assertEqual(plan['terrain']['relief_m'], {'raised_m': 0., 'lowered_m': 0.})

    def test_an_unknown_shape_is_refused(self):
        from key_locations.core import shaping

        with self.assertRaises(ValueError):
            shaping.delta({'shape': 'swirl', 'x_m': 0., 'z_m': 0.}, 0., 0.)


def _flat_ground(world_dict, plan):
    """The unshaped terrain height at a plan's origin, for comparing against."""
    from key_locations.core.exterior import _sample_height
    from key_locations.core import world as readers
    return _sample_height(tuple(plan['origin']['direction']), 0., 0., world_dict['layers'],
                          readers.size(world_dict), readers.radius_m(world_dict))


class SchemaCoverage(unittest.TestCase):
    """Both directions: the schema declares what the block emits, and vice versa.

    Validation alone is one-way. An undeclared field passes every validator in this repo while
    being invisible to any consumer building against the published contract - which is exactly
    what happened when the `environment` block was added to the record and not to the schema.
    """

    SCHEMAS = pathlib.Path(__file__).resolve().parents[2] / 'Contracts' / 'schemas'

    @classmethod
    def setUpClass(cls):
        cls.world = world()
        cls.world['key_locations'] = key_locations.generate(cls.world)
        cls.plans = key_locations.attach_plans(cls.world)

    def schema(self, name):
        return json.loads((self.SCHEMAS / name).read_text(encoding='utf-8'))

    def assertDeclares(self, record, node, where):
        """Every key on a record is a declared property of the object schema describing it."""
        declared = set(node.get('properties') or {})
        self.assertTrue(declared, f'{where}: schema declares no properties')
        undeclared = set(record) - declared
        self.assertEqual(undeclared, set(),
                         f'{where} emits {sorted(undeclared)}, which no consumer can see in the contract')

    def test_the_locations_schema_declares_every_field_a_site_carries(self):
        site_schema = self.schema('key-locations.schema.json')['properties']['sites']['items']
        for site in self.block_sites():
            self.assertDeclares(site, site_schema, 'site')
            for key in ('origin', 'links', 'environment'):
                self.assertDeclares(site[key], site_schema['properties'][key], f'site.{key}')
            if site['interior']:
                self.assertDeclares(site['interior'], site_schema['properties']['interior'], 'site.interior')
            if site['succession']:
                self.assertDeclares(site['succession'], site_schema['properties']['succession'], 'site.succession')

    def test_the_plans_schema_declares_every_field_a_plan_carries(self):
        plan_schema = self.schema('key-location-plans.schema.json')['properties']['plans']['items']
        for plan in self.plans['plans']:
            self.assertDeclares(plan, plan_schema, 'plan')
            self.assertDeclares(plan['origin'], plan_schema['properties']['origin'], 'plan.origin')
            terrain_schema = plan_schema['properties']['terrain']
            self.assertDeclares(plan['terrain'], terrain_schema, 'plan.terrain')
            self.assertDeclares(plan['terrain']['surface'], terrain_schema['properties']['surface'],
                                'plan.terrain.surface')
            for entry in plan['terrain']['shaping']:
                self.assertDeclares(entry, terrain_schema['properties']['shaping']['items'],
                                    'plan.terrain.shaping[]')
            for plot in plan['plots']:
                self.assertDeclares(plot, plan_schema['properties']['plots']['items'], 'plan.plots[]')

    def test_required_fields_are_actually_always_present(self):
        """A required field that is sometimes absent is a contract nobody can rely on."""
        site_schema = self.schema('key-locations.schema.json')['properties']['sites']['items']
        for site in self.block_sites():
            for key in site_schema['required']:
                self.assertIn(key, site, f'site is missing required {key}')
        plan_schema = self.schema('key-location-plans.schema.json')['properties']['plans']['items']
        for plan in self.plans['plans']:
            for key in plan_schema['required']:
                self.assertIn(key, plan, f'plan is missing required {key}')

    def block_sites(self):
        return self.world['key_locations']['sites']


class Isolation(unittest.TestCase):
    def test_attach_reports_failure_instead_of_raising_and_honours_the_switch(self):
        with patch.dict(os.environ, {key_locations.ENV_SWITCH: '0'}):
            self.assertIsNone(key_locations.attach(world()))
        with patch.dict(os.environ, {key_locations.ENV_SWITCH: '1'}):
            self.assertEqual(key_locations.attach(world())['status'], 'ok')
            broken = key_locations.attach({'config': {'seed': 'not an int'}})
            self.assertEqual(broken['status'], 'failed')
            self.assertIn('ValueError', broken['error'])

    def test_a_world_without_the_resolved_radius_is_refused(self):
        stunted = world()
        stunted['effective_config'] = {}
        block = key_locations.attach(stunted)
        self.assertEqual(block['status'], 'failed')
        self.assertIn('globe_radius', block['error'])

    def test_package_reads_only_the_world_json(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(key_locations.__file__)))
        package = os.path.join(root, 'key_locations')
        checked = 0
        for folder, _, names in os.walk(package):
            for name in names:
                if not name.endswith('.py'):
                    continue
                checked += 1
                path = os.path.join(folder, name)
                with open(path, encoding='utf-8') as handle:
                    for line in handle:
                        self.assertFalse(line.lstrip().startswith(('import icarus_sim', 'from icarus_sim')),
                                         f'{path}: {line}')
        self.assertGreater(checked, 5)

    def test_summary_lines_read_for_a_log(self):
        lines = key_locations.summary_lines(key_locations.generate(world()))
        self.assertTrue(lines[0].startswith(tuple('0123456789')))
        self.assertIn('key locations', lines[0])
        self.assertEqual(key_locations.summary_lines({'status': 'failed', 'error': 'x'}),
                         ['key locations failed: x'])


class NaturalBiomeIdTests(unittest.TestCase):
    """`natural_biome` is a catalogue ID, not an array offset, and the id space is sparse.

    The world states the rule itself in ``terrain.biome_contract``: *"biome and
    natural_biome are natural catalogue IDs, never array offsets; biome_variant is a
    magical catalogue index or -1."* Keying the natural map by list position satisfied ids
    0..8 -- which are contiguous -- and silently lost every id above them.
    """

    def catalogue(self):
        from icarus_sim.terrain_biome_catalogue import natural_catalogue
        return natural_catalogue()

    def test_every_natural_id_resolves_to_a_name(self):
        catalogue = self.catalogue()
        names = key_locations._biome_names(
            {'terrain': {'natural_biomes': catalogue, 'magical_biomes': []}})
        unresolved = [entry['id'] for entry in catalogue
                      if names['natural'].get(entry['id']) is None]
        self.assertEqual(unresolved, [], 'every catalogue id must name its ground')

    def test_the_id_space_is_sparse_and_reaches_past_the_list_length(self):
        """The property that made the offset reading wrong, pinned so it cannot drift back."""
        ids = sorted(entry['id'] for entry in self.catalogue())
        self.assertEqual(ids, [0, 1, 2, 3, 4, 5, 6, 7, 8, 13, 15, 16, 17])
        self.assertGreater(max(ids), len(ids) - 1,
                           'ids run past the last list position, so position is not id')

    def test_the_cold_and_wet_biomes_are_the_ones_that_were_lost(self):
        """Named explicitly: these four resolved to None before the fix."""
        catalogue = self.catalogue()
        names = key_locations._biome_names(
            {'terrain': {'natural_biomes': catalogue, 'magical_biomes': []}})
        self.assertEqual(names['natural'][13], 'Marsh')
        self.assertEqual(names['natural'][15], 'Boreal forest')
        self.assertEqual(names['natural'][16], 'Cold tundra')
        self.assertEqual(names['natural'][17], 'Persistent land ice')

    def test_the_variant_map_stays_an_index(self):
        """The two maps are keyed differently on purpose; only the natural one was wrong."""
        variants = [{'asset_id': f'a{i}', 'name': f'n{i}'} for i in range(4)]
        names = key_locations._biome_names(
            {'terrain': {'natural_biomes': self.catalogue(), 'magical_biomes': variants}})
        self.assertEqual(names['variant_name'][0], 'n0')
        self.assertEqual(names['variant_name'][3], 'n3')

    def test_the_schema_bound_admits_the_whole_id_space(self):
        """A 0-12 maximum rejected valid output, which is how this surfaced."""
        root = pathlib.Path(__file__).resolve().parents[2]
        schema = json.loads((root / 'Contracts' / 'schemas'
                             / 'key-locations.schema.json').read_text(encoding='utf-8'))
        bound = (schema['properties']['sites']['items']['properties']
                 ['environment']['properties']['natural_biome'])
        self.assertGreaterEqual(bound['maximum'], max(e['id'] for e in self.catalogue()))


if __name__ == '__main__':
    unittest.main()
