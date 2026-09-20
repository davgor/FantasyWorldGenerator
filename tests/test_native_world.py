"""Native in-process world genesis: oracle parity, detailed sampling, Unreal frame, asset registry.

The native core is the Unreal generate API. These tests run it headlessly, without
Unreal, and compare it against the Python reference world for the same seed. Integer
identities (plate, water, biome, landform, land) must match exactly; continuous fields
follow the numeric contract in Fixtures/native-world-v1.json, whose tolerance exists
only because the platform pow() differs from the interpreter's in the last ulp.
"""
import json
import math
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
sys.path.insert(0, str(ROOT / 'Sim'))

from native_cxx import compile_native, compiler_command

SOURCES = ('json.cpp', 'numeric.cpp', 'counter.cpp', 'genesis.cpp', 'pyrandom.cpp', 'globe.cpp', 'frame.cpp',
           'registry.cpp', 'hydrology.cpp', 'tectonics.cpp', 'history.cpp', 'climate.cpp', 'biomes.cpp',
           'magic.cpp', 'astrology.cpp', 'legacy.cpp', 'ecology.cpp', 'catalogue.cpp', 'profiles.cpp', 'settlements.cpp', 'founding.cpp',
           'roads.cpp', 'scene.cpp', 'cityplan.cpp', 'humans.cpp', 'society.cpp', 'nests.cpp', 'wars.cpp', 'ages.cpp', 'layers.cpp', 'world.cpp',
           # The settlement-geometry slice scene.cpp calls at the final stage: the three
           # planners, the geometry they share and the scene that dimensions their plots.
           'settlementpresets.cpp', 'sceneframe.cpp', 'citygeometry.cpp', 'cityshapes.cpp',
           'cityfortifications.cpp', 'castlegeometry.cpp', 'cityplanner.cpp', 'hamletplanner.cpp',
           'castleplanner.cpp', 'scenebuildings.cpp',
           'tests/world_driver.cpp')
CONTRACT = json.loads((ROOT / 'Fixtures' / 'native-world-v1.json').read_text(encoding='utf-8'))
IDENTITY_LAYERS = set(CONTRACT['identity_layers'])
REGISTRY = ROOT / 'Contracts' / 'catalogues' / 'unreal-asset-registry-v1.json'
CATALOGUES = ROOT / 'Contracts' / 'catalogues' / 'native-catalogues-v1.json'
# The reference world costs about a minute per seed, so one seed runs by default.
PARITY_SEED, PARITY_SIZE = 42, 33


def _blocks(text):
    """Parse the driver's output; a key emitted more than once collects one row each."""
    blocks, repeated, key = {}, set(), None
    for line in text.split('\n'):
        line = line.strip()
        if not line:
            continue
        if line.startswith('#'):
            key = line[1:]
            if key in blocks:
                if key not in repeated:
                    blocks[key] = [blocks[key]]
                    repeated.add(key)
                blocks[key].append([])
            else:
                blocks[key] = []
        elif key is None:
            # Rows the driver prints before any block, such as the tagged identity
            # lines of the finished world, are read by _tagged instead.
            continue
        elif key in repeated:
            blocks[key][-1].append(float(line))
        else:
            blocks[key].append(float(line))
    return blocks


def _tagged(text):
    """Parse the driver's tab-separated rows into one list per row tag."""
    rows = {}
    for line in text.split(chr(10)):
        line = line.rstrip()
        if not line or line.startswith('#') or not line[0].isalpha():
            continue
        parts = line.split(chr(9))
        rows.setdefault(parts[0], []).append(parts)
    return rows


def _plan_rows(text):
    """Parse the city-plan driver's tab-separated rows into one block per city."""
    plans = {}
    for line in text.split('\n'):
        if not line.strip():
            continue
        row = line.rstrip().split('\t')
        plan = plans.setdefault(int(row[1]), {'features': [], 'options': [], 'required': []})
        if row[0] == 'PLAN':
            plan['head'] = row
        elif row[0] == 'FEATURE':
            plan['features'].append(row)
        elif row[0] == 'OPTION':
            plan['options'].append(row)
        else:
            plan['required'].append(row)
    return [plans[key] for key in sorted(plans)]


def _anchors(fields):
    return [(int(field.split(':')[0]), float(field.split(':')[1])) for field in fields]


def _direction(latitude, longitude):
    lat, lon = math.radians(latitude), math.radians(longitude)
    return (math.cos(lat) * math.cos(lon), math.sin(lat), math.cos(lat) * math.sin(lon))


class NativeWorldTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if compiler_command() is None:
            raise unittest.SkipTest('native world genesis requires a C++17 compiler')
        cls.directory = tempfile.TemporaryDirectory(prefix='fantasy-world-generator-world-')
        cls.addClassCleanup(cls.directory.cleanup)
        cls.binary = Path(cls.directory.name) / ('world.exe' if os.name == 'nt' else 'world')
        compile_native([ROOT / 'Core' / name for name in SOURCES], ROOT / 'Core', cls.binary)
        cls._oracle = {}

    @classmethod
    def oracle(cls, seed, size):
        """The Python reference world, generated once per seed for the whole class."""
        if (seed, size) not in cls._oracle:
            from icarus_sim.terrain_world import generate_request
            # Pinned to a villainless world. `villain_rise` now defaults to .5 and a
            # generated world ends with super villains promoted into it, but Core has no
            # villain model at all -- `grep -rn -i villain Core/` finds only three unread
            # config fields -- so the oracle must ask for the configuration Core can
            # actually reproduce. Without this every layer a villain's well and claims
            # touch diverges, and the divergence looks like a numeric bug in the core.
            cls._oracle[(seed, size)] = generate_request(
                {'seed': seed, 'recipe_version': 3,
                 'overrides': {'size': size, 'villain_rise': 0.}})
        return cls._oracle[(seed, size)]

    # Operations that build a world from a seed and a size, and therefore need the same
    # world shape the oracle resolved. The rest read a catalogue or do frame arithmetic.
    WORLD_OPERATIONS = ('world', 'stage9', 'fields', 'cityplans', 'humans', 'nests', 'ages', 'samples', 'networks')

    # The shape parameters `Core/config.hpp` holds as raw authoring constants and recipe 3
    # resolves per world. `world_scale` is NOT among them: recipe 3 resolves it to Core's
    # own default, and passing it through `set:` aborts the driver (see the card).
    SHAPE_KEYS = ('globe_radius', 'tectonic_relief', 'amplitude', 'wavelength', 'orogeny',
                  'belt_width', 'plate_count', 'crust_bias', 'mountain_detail', 'sea_level',
                  'settlement_spacing', 'support_reach', 'culture_link_cost',
                  'temperature_offset', 'moisture_bias',
                  'erosion_passes', 'erosion_strength', 'river_threshold_km2')
    # Deliberately absent, having been checked rather than assumed: `ley_width` (180),
    # `ley_nodes` (10), `magic_instability` (.45), `rain_passes` (48) and `wind_bearing` (90)
    # are resolved by recipe 3 to exactly the values `Core/config.hpp` already holds, and
    # `override_bounds()` does not name them, so passing them would be noise at best.
    # `world_scale` is resolved to Core's own default too, and passing it aborts the driver.
    #
    # `river_threshold_km2` is newly present. Recipe 3 resolves it to 48.270568 km2 at the
    # 200 km default, because it is a catchment AREA authored for the 11.15 km reference
    # world and scales as the square of the width, while `Core/config.hpp` still holds the
    # reference world's .15. Left unpassed, the driver builds rivers on every land cell and
    # rain_river, river, freshwater_distance, flood_risk and every consumer of them diverge.
    # Core/world.cpp's override chain had to learn the key first -- it throws INVALID_INPUT
    # on any name it does not list -- and Core/genesis.cpp's override_bounds() now admits
    # .001..10000 to match the reference.
    #
    # `support_reach` is passed but is OUTSIDE Core's own `override_bounds()` entry of
    # [100, 10000]: recipe 3 resolves 17938.9 at this seed, because reaches are absolute
    # metres authored for the 11.15 km reference world and must grow with the world. The
    # driver's `set:` channel does not consult those bounds, so this works here -- but the
    # JSON request path at Core/genesis.cpp:104-107 would reject the same value.

    @classmethod
    def shape(cls, seed, size):
        """`set:` overrides carrying the oracle's resolved world shape to the driver.

        Without these the driver builds from `Core/config.hpp`'s authoring defaults -- a
        design radius of 10000 against the recipe's 179388.9 at this seed -- so the two
        sides generate different worlds and every metric layer disagrees while every
        dimensionless one matches exactly. That signature is what made a harness gap look
        like a numeric divergence in the core.
        """
        config = cls.oracle(seed, size).get('config', {})
        return [f'set:{key}={config[key]!r}' for key in cls.SHAPE_KEYS
                if isinstance(config.get(key), (int, float)) and not isinstance(config.get(key), bool)]

    def native(self, *arguments, stdin=''):
        arguments = list(arguments)
        if arguments and arguments[0] in self.WORLD_OPERATIONS:
            arguments += self.shape(PARITY_SEED, PARITY_SIZE)
        result = subprocess.run([str(self.binary), *[str(v) for v in arguments]], input=stdin,
                                capture_output=True, text=True, timeout=900)
        self.assertEqual(result.returncode, 0, result.stderr[-4000:])
        return result.stdout

    def test_native_world_reproduces_the_reference_world_for_one_seed(self):
        world = self.oracle(PARITY_SEED, PARITY_SIZE)
        blocks = _blocks(self.native('world', PARITY_SEED, PARITY_SIZE))
        self.assertTrue(IDENTITY_LAYERS <= set(blocks), sorted(IDENTITY_LAYERS - set(blocks)))
        for key, values in sorted(blocks.items()):
            if key == 'area':
                continue
            with self.subTest(layer=key):
                expected = [v for row in world['layers'][key] for v in row]
                self.assertEqual(len(values), len(expected))
                if key in IDENTITY_LAYERS:
                    self.assertCellsIdentical(values, [float(v) for v in expected], key, ' (identity)')
                    continue
                for native_value, reference in zip(values, expected):
                    if native_value == reference:
                        continue
                    difference = abs(native_value - reference)
                    self.assertLessEqual(difference, CONTRACT['absolute_tolerance']
                                         + CONTRACT['relative_tolerance'] * abs(reference))
        self.assertEqual(blocks['area'][0], world['area']['land_km2'])
        for index, key in enumerate(('ocean_km2', 'lake_km2', 'dry_km2'), start=1):
            self.assertEqual(blocks['area'][index], world['water'][key])

    def test_stage_nine_magic_and_environment_match_the_reference(self):
        """The ley networks and the fields that read them, before the age transitions.

        The reference rescales every ley intensity during ages one and two, so these are
        compared against the world materialized at stage nine: they are the inputs the
        civilization stages consume, not the world's final magic fields.
        """
        from icarus_sim.terrain_history import materialize_stage
        world = self.oracle(PARITY_SEED, PARITY_SIZE)
        staged = materialize_stage(world, 9)
        blocks = _blocks(self.native('stage9', PARITY_SEED, PARITY_SIZE))
        self.assertGreaterEqual(len(blocks), 40, 'stage nine exports the magic and environment fields')
        for key, values in sorted(blocks.items()):
            with self.subTest(layer=key):
                self.assertIn(key, staged['layers'])
                expected = [v for row in staged['layers'][key] for v in row]
                self.assertEqual(len(values), len(expected))
                if key.startswith(('zone_', 'boreal', 'tundra', 'ice_cap', 'island_habitat', 'estuary', 'dominant_magic')):
                    # Categorical or indicator fields: a tolerance here could hide a
                    # region that manifested in one implementation and not the other.
                    self.assertCellsIdentical(values, expected, key, ' (categorical)')
                    continue
                for native_value, reference in zip(values, expected):
                    if native_value == reference:
                        continue
                    self.assertLessEqual(abs(native_value - reference), CONTRACT['absolute_tolerance']
                                         + CONTRACT['relative_tolerance'] * abs(reference))

    def test_per_people_fields_budget_and_founded_cities_match_the_reference(self):
        """Where each people can live, how much that land feeds, and where cities land.

        These decide where cities land, so the habitat rules, the routed support reach
        and the marine fishing reach are all compared, not just the arithmetic.
        """
        from icarus_sim.terrain_history import materialize_stage
        world = self.oracle(PARITY_SEED, PARITY_SIZE)
        staged = materialize_stage(world, 10)
        blocks = _blocks(self.native('fields', PARITY_SEED, PARITY_SIZE, CATALOGUES))
        expected_names = {key for key in staged['layers']
                          if key.startswith(('suitability_', 'life_capacity_')) or key.endswith('_support_reach')}
        expected_names.discard('suitability')
        budget = staged['population_budget']
        self.assertEqual(set(blocks) - {'world_cap', 'cities', 'founding', 'roads', 'route', 'polyline', 'anchor'}
                         - {'budget_' + k for k in budget['allowances']}, expected_names)
        # The budget decides how many cities each people may found, so it is compared
        # exactly: a rounded allowance is a different world, not a near one.
        self.assertEqual(int(blocks['world_cap'][0]), budget['world_cap'])
        for species, allowance in budget['allowances'].items():
            with self.subTest(budget=species):
                values = blocks['budget_' + species]
                self.assertEqual(int(values[0]), allowance)
                self.assertEqual(int(values[1]), budget['requested_cities'][species])
                self.assertEqual(values[2], budget['weighted_habitat_km2'][species])
                self.assertEqual(values[3], budget['shares'][species])
        # Founded cities: same nodes, same peoples, same order, same founding years.
        # Nothing here is compared with a tolerance, because a city one node away is a
        # different world.
        import json
        identities = json.loads(CATALOGUES.read_text(encoding='utf-8'))['civilization_ids']
        founded = [blocks['cities'][i:i + 8] for i in range(0, len(blocks['cities']), 8)]
        sites = staged['settlements']['sites']
        self.assertEqual(len(founded), len(sites))
        self.assertEqual([int(v) for v in blocks['founding']],
                         [staged['settlements']['founding']['turns'],
                          staged['settlements']['founding']['target_cities'],
                          staged['settlements']['founding']['placed_cities']])
        for index, (row, site) in enumerate(zip(founded, sites)):
            with self.subTest(city=index):
                node, profile, turn, year, capital, diaspora, branch, distance = row
                self.assertEqual(int(node), site['node'])
                self.assertEqual(identities[int(profile)], site['population_profile'])
                self.assertEqual(int(turn), site['founding_turn'])
                self.assertEqual(year, site['founding_year'])
                self.assertEqual(bool(capital), bool(site['founding_capital']))
                self.assertEqual(bool(diaspora), bool(site.get('diaspora')))
                self.assertEqual(bool(branch), bool(site['cultural_branch']))
                self.assertEqual(distance, site['migration_distance_m'])
        # Regional roads: the same routes, node by node, with the same lengths, costs
        # and river crossings. A road that takes a different pass is a different world.
        oracle_roads = materialize_stage(world, 11)['roads']['routes']
        routes = blocks.get('route', [])
        if routes and not isinstance(routes[0], list):
            routes = [routes]
        self.assertEqual(int(blocks['roads'][0]), len(oracle_roads))
        self.assertEqual(len(routes), len(oracle_roads))
        for index, (row, route) in enumerate(zip(routes, oracle_roads)):
            with self.subTest(road=index):
                self.assertEqual([int(row[0]), int(row[1])], [route['from'], route['to']])
                self.assertEqual(row[2], route['length_m'])
                self.assertEqual(row[3], route['cost'])
                self.assertEqual([int(v) for v in row[6:]], route['nodes'])
                self.assertEqual(int(row[5]), len(route['river_crossings']))
        # The scene a consumer materializes: each route densified onto the sampled
        # surface at the reference's own four metre interval, and each city anchored at
        # its sampled height. A polyline that drifts off the ground is a floating road.
        import math
        from icarus_sim.terrain_detail import HeightField
        from icarus_sim.terrain_globe import direction as globe_direction
        from icarus_sim.world_scene import position as scene_position
        staged_roads = materialize_stage(world, 11)
        field = HeightField(staged_roads)
        nodes = staged_roads['water']['nodes']
        polylines = blocks.get('polyline', [])
        if polylines and not isinstance(polylines[0], list):
            polylines = [polylines]
        self.assertEqual(len(polylines), len(oracle_roads))
        for index, route in enumerate(oracle_roads):
            with self.subTest(polyline=index):
                vectors = [globe_direction(*nodes[node], PARITY_SIZE) for node in route['nodes']]
                dense = []
                for start, end in zip(vectors, vectors[1:]):
                    arc = field.radius * math.acos(max(-1, min(1, sum(a * b for a, b in zip(start, end)))))
                    steps = max(1, math.ceil(arc / 4))
                    for step in range(steps):
                        between = [a + (b - a) * step / steps for a, b in zip(start, end)]
                        length = math.sqrt(sum(v * v for v in between))
                        dense.append([v / length for v in between])
                dense.append(vectors[-1])
                expected = [value for point in dense for value in scene_position(field, point)]
                self.assertEqual(polylines[index], expected)
        anchors = blocks.get('anchor', [])
        if anchors and not isinstance(anchors[0], list):
            anchors = [anchors]
        self.assertEqual(len(anchors), len(sites))
        for anchor, site in zip(anchors, sites):
            with self.subTest(anchor=site['node']):
                self.assertEqual(int(anchor[0]), site['node'])
                self.assertEqual(anchor[4], field.height(globe_direction(site['x'], site['z'], PARITY_SIZE)))
        for key, values in sorted(blocks.items()):
            if key in ('world_cap', 'cities', 'founding', 'roads', 'route', 'polyline', 'anchor')                     or key.startswith('budget_'):
                continue
            with self.subTest(layer=key):
                expected = [v for row in staged['layers'][key] for v in row]
                self.assertEqual(len(values), len(expected))
                if key.endswith('_support_reach'):
                    # Reached or not reached: a tolerance would hide a hinterland that
                    # routes differently.
                    self.assertCellsIdentical(values, expected, key, ' (reached or not reached)')
                    continue
                for native_value, reference in zip(values, expected):
                    if native_value == reference:
                        continue
                    self.assertLessEqual(abs(native_value - reference), CONTRACT['absolute_tolerance']
                                         + CONTRACT['relative_tolerance'] * abs(reference))

    def test_city_layout_plans_match_the_reference(self):
        """Which pack a city builds from, and every district and building it plans.

        The pack is a seeded weighted draw, the districts and buildings claim from one
        walking-distance ring around the city, and every asset is drawn from the pack's
        own weighted choices. A plan that claims a different node is a different city,
        so nothing here is compared with a tolerance.
        """
        from icarus_sim.terrain_history import materialize_stage
        world = self.oracle(PARITY_SEED, PARITY_SIZE)
        sites = materialize_stage(world, 10)['settlements']['sites']
        plans = _plan_rows(self.native('cityplans', PARITY_SEED, PARITY_SIZE, CATALOGUES,
                                     'residents=1'))
        self.assertEqual(len(plans), len(sites))
        feature_order = ('leader_homes', 'barracks', 'noble_homes', 'worker_housing',
                         'apartments', 'market_district', 'religious_building')
        for index, site in enumerate(sites):
            layout = site['city_layout']
            plan = plans[index]
            head = plan['head']
            with self.subTest(city=index):
                # The pack seed decides the draw, so it is compared before the draw's result.
                self.assertEqual(int(head[2]), site['building_pack_seed'])
                self.assertEqual(head[3], site['building_pack_id'])
                self.assertEqual(head[4], layout['layout_profile_id'])
                river = layout['river']
                self.assertEqual(int(head[5]), river['adjacent_river_edges'])
                self.assertEqual(bool(int(head[6])), river['bridge_recommended'])
                self.assertEqual(int(head[7]), river['bridge_threshold'])
                if river['river_distance_m'] is None:
                    self.assertEqual(head[8], '-')
                else:
                    self.assertEqual(float(head[8]), river['river_distance_m'])
                self.assertEqual(int(head[9]), layout['required_asset_count'])
                self.assertEqual(int(head[10]), layout['required_node_slots'])
                self.assertEqual(bool(int(head[11])), layout['buildings']['missing_anchors'])
                self.assertEqual(head[12], layout.get('fallback', {}).get('reason', '-'))
                self.assertEqual([row[2] for row in plan['features']], list(feature_order))
                for row, name in zip(plan['features'], feature_order):
                    expected = layout['features'][name]
                    self.assertEqual(int(row[3]), expected['target_count'])
                    self.assertEqual(int(row[4]), expected['count'])
                    self.assertEqual(_anchors(row[5:]),
                                     [(a['node'], a['distance_to_city_m']) for a in expected['anchors']])
                options = layout['buildings']['options']
                self.assertEqual([row[2] for row in plan['options']], list(options))
                for row in plan['options']:
                    expected = options[row[2]]
                    self.assertEqual(row[3], expected['placement'])
                    self.assertEqual(int(row[4]), expected['target_count'])
                    self.assertEqual(int(row[5]), expected['placed_count'])
                    self.assertEqual(int(row[6]), expected['required_node_slots'])
                    self.assertEqual(bool(int(row[7])), expected['required'])
                    self.assertEqual(bool(int(row[8])), expected['bridge_required'])
                    self.assertEqual(None if row[9] == '-' else row[9], expected['skip_reason'])
                    self.assertEqual([] if row[10] == '-' else row[10].split(','), expected['tags'])
                    self.assertEqual([] if row[11] == '-' else row[11].split(','), expected['assets'])
                    self.assertEqual(_anchors(row[12:]),
                                     [(a['node'], a['distance_to_city_m']) for a in expected['anchors']])
                self.assertEqual([(row[2], int(row[3])) for row in plan['required']],
                                 [(row['asset_id'], row['count']) for row in layout['required_assets']])

    def test_hinterlands_ports_and_nests_match_the_reference(self):
        """Hamlets, fortresses, cultures, coastal landings and habitat anchors.

        These decide where the world's rural content stands, and the nests decide
        which cities later die, so every identity and node is compared exactly. The
        continuous food field is held to the numeric contract rather than to equality,
        because it is built from exp() and pow() like every other continuous layer.
        """
        from icarus_sim.terrain_history import materialize_stage
        world = self.oracle(PARITY_SEED, PARITY_SIZE)
        staged = materialize_stage(world, 13)
        rows = _tagged(self.native('humans', PARITY_SEED, PARITY_SIZE, CATALOGUES))
        nests = _tagged(self.native('nests', PARITY_SEED, PARITY_SIZE, CATALOGUES))
        hamlets = [site for site in staged['humans']['hamlets'] if site['id'].startswith('hamlet-')]
        self.assertEqual(len(rows['HAMLET']), len(hamlets))
        for row, expected in zip(rows['HAMLET'], hamlets):
            with self.subTest(hamlet=expected['id']):
                self.assertEqual(row[1], expected['id'])
                self.assertEqual(int(row[2]), expected['node'])
                self.assertEqual(row[3], expected['role'])
                self.assertEqual(row[5], expected['culture_id'])
                # The path first, then the cost. `access_cost` is a Dijkstra total, so the
                # additions run strictly along the settled path and an identical path gives
                # an identical double. Comparing the path separately is what tells a routing
                # divergence apart from arithmetic inside one edge -- six hamlets differ by
                # one to three ulp and neither side recorded which of the two it was.
                self.assertEqual([int(node) for node in row[11].split(',') if node],
                                 expected['access_nodes'], f"{expected['id']} access_nodes")
                for offset, key in enumerate(('access_cost', 'worked_area_km2', 'delivered_food',
                                              'delivered_materials', 'irrigation_benefit')):
                    self.assertEqual(float(row[6 + offset]), expected[key], f"{expected['id']} {key}")
        self.assertEqual(len(rows['FORTRESS']), len(staged['humans']['fortresses']))
        for row, expected in zip(rows['FORTRESS'], staged['humans']['fortresses']):
            with self.subTest(fortress=expected['id']):
                self.assertEqual(int(row[2]), expected['node'])
                self.assertEqual(float(row[4]), expected['defence_score'], expected['id'] + ' defence_score')
                self.assertEqual(int(row[5]), expected['protected_route_node'], expected['id'] + ' route node')
        self.assertEqual(len(rows['PORT']), len(staged['fisheries']['ports']))
        for row, expected in zip(rows['PORT'], staged['fisheries']['ports']):
            with self.subTest(port=expected['id']):
                self.assertEqual(row[1], expected['id'])
                self.assertEqual(int(row[2]), expected['node'])
                self.assertEqual(int(row[3]), expected['sea_node'])
                self.assertEqual(float(row[6]), expected['access_cost'])
        self.assertEqual([row[1] for row in rows['LANDMARK']],
                         [mark['id'] for mark in staged['regions']['landmarks']])
        # Two independent passes, each tagged by the driver: hunting grounds and
        # monster territory, compared anchor for anchor.
        for tag, key in (('animal', 'wildlife'), ('monster', 'beast_nests')):
            anchors = staged[key]['sites']
            rows_for = [row for row in nests['NEST'] if row[1] == tag]
            self.assertEqual(len(rows_for), len(anchors), key)
            for row, expected in zip(rows_for, anchors):
                with self.subTest(nest=expected['id']):
                    self.assertEqual(row[2], expected['id'])
                    self.assertEqual(int(row[4]), expected['node'])
                    self.assertEqual(int(row[5]), expected['tier'])
                    self.assertEqual(float(row[6]), expected['suitability'])
                    self.assertEqual(float(row[7]), expected['range_m'])
                    self.assertEqual(row[8] == '1', expected['den'])
            placed = {row[2]: int(row[4]) for row in nests['NESTDIAG'] if row[1] == tag}
            self.assertEqual(placed, {entry['species_id']: entry['placed']
                                      for entry in staged[key]['diagnostics']}, key)

    def test_the_finished_world_matches_the_reference(self):
        """The world after both age transitions: what a consumer actually receives.

        Stage nine is not the finished world. Ages one and two rescale every leyline,
        destroy cities into ruins whose ground is never resettled, and rebuild
        everything the dead cities supported. This compares the end of that history,
        which is the state the plugin hands to Unreal.
        """
        from icarus_sim.terrain_history import materialize_stage
        world = self.oracle(PARITY_SEED, PARITY_SIZE)
        staged = materialize_stage(world, 16)
        # One run, read two ways: generating the finished world twice would double a
        # slow test for nothing.
        reported = self.native('ages', PARITY_SEED, PARITY_SIZE, CATALOGUES)
        blocks = _blocks(reported)
        rows = _tagged(reported)
        sites = staged['settlements']['sites']
        self.assertEqual(len(rows['CITY']), len(sites))
        for row, expected in zip(rows['CITY'], sites):
            with self.subTest(city=expected['uid']):
                # The uid carries the age a city was founded in, so comparing it also
                # compares which ages founded and spared it.
                self.assertEqual(row[1], expected['uid'])
                self.assertEqual(int(row[2]), expected['node'])
                self.assertEqual(int(row[4]), expected['founded_age'])
                self.assertEqual(float(row[5]), expected['founding_year'])
        ruins = staged['ruins']
        self.assertEqual(len(rows['RUIN']), len(ruins))
        for row, expected in zip(rows['RUIN'], ruins):
            with self.subTest(ruin=expected['id']):
                self.assertEqual(row[1], expected['id'])
                self.assertEqual(int(row[2]), expected['node'])
                self.assertEqual(row[3], expected['cause'])
                self.assertEqual(int(row[4]), expected['destroyed_age'])
                self.assertEqual(float(row[5]), expected['probability'])
                self.assertEqual(float(row[6]), expected['roll'])
                # Every ruin seeds a key point; its school, intensity and basis are contract too.
                self.assertEqual(row[7], expected['legacy']['school'])
                self.assertEqual(float(row[8]), expected['legacy']['intensity'])
                self.assertEqual(row[9], expected['legacy']['basis'])
        # Wars decide which cities reach the finished world at all, so they are
        # compared themselves and not only through the ruins they leave.
        wars = [war for entry in staged['history']['ages'] for war in entry['wars']]
        self.assertEqual(len(rows.get('WAR', [])), len(wars))
        for row, expected in zip(rows.get('WAR', []), wars):
            with self.subTest(war=expected['id']):
                self.assertEqual(row[1], expected['id'])
                self.assertEqual(row[2], expected['kind'])
                self.assertEqual(row[3], expected['victor_uid'])
                self.assertEqual(row[4], expected['defeated_uid'])
                self.assertEqual(int(row[5]), expected['age'])
                self.assertEqual(float(row[6]), expected['pressure'], 'pressure')
                self.assertEqual(float(row[7]), expected['chance'], 'chance')
                self.assertEqual(float(row[8]), expected['roll'], 'roll')
        veterans = [(city['uid'], entry['war_id'], entry['outcome'], entry['opponent_uid'])
                    for city in sites for entry in city.get('war_history', [])]
        self.assertEqual([tuple(row[1:5]) for row in rows.get('VETERAN', [])], veterans)
        counts = rows['COUNTS'][0]
        self.assertEqual([int(value) for value in counts[1:]],
                         [len(sites), len(ruins), len(staged['roads']['routes']),
                          len([h for h in staged['humans']['hamlets'] if h['id'].startswith('hamlet-')]),
                          len(staged['fisheries']['ports']), len(staged['beast_nests']['sites'])])
        # Identity layers are exact; the continuous magic fields keep the contract.
        # Compared cell by cell rather than with a bare assertEqual: these are 1089-element
        # lists, and the difflib diff unittest renders for one of those raises RecursionError
        # before it reaches the message, which turns a real divergence into an ERROR whose
        # traceback names difflib instead of the layer. See `assertCellsIdentical`.
        for name in ('biome', 'dominant_magic'):
            self.assertCellsIdentical(blocks[name], [value for row in staged['layers'][name] for value in row],
                                      name, ' (finished world, identity layer)')
        for name in ('ley_weave', 'magic_hazard'):
            expected = [value for row in staged['layers'][name] for value in row]
            for native_value, reference in zip(blocks[name], expected):
                if native_value == reference:
                    continue
                self.assertLessEqual(abs(native_value - reference), CONTRACT['absolute_tolerance']
                                     + CONTRACT['relative_tolerance'] * abs(reference))

    def test_detailed_samples_are_the_shared_surface_function(self):
        from icarus_sim.terrain_detail import HeightField, export_height_tile
        world = self.oracle(PARITY_SEED, PARITY_SIZE)
        field = HeightField(world)
        cases = [(lat, lon) for lat in (-71.5, -12.25, 0.0, 33.75, 68.5) for lon in (-179.5, -90.0, -0.25, 47.5, 179.5)]
        native = [float(v) for v in self.native('samples', PARITY_SEED, PARITY_SIZE,
                                                stdin='\n'.join(f'{a!r} {b!r}' for a, b in cases)).split()]
        for (latitude, longitude), value in zip(cases, native):
            with self.subTest(latitude=latitude, longitude=longitude):
                reference = field.height(_direction(latitude, longitude))
                self.assertLessEqual(abs(value - reference), CONTRACT['absolute_tolerance']
                                     + CONTRACT['relative_tolerance'] * abs(reference))
        # Shared tile indices must resolve to the same height as a direct sample: the
        # Landscape, foundations, roads and nests all read this one function.
        tile = export_height_tile(world, 4, 3, 5, cells=4)
        rows = 2 ** 4
        indices = [(3 + i, 5 + j) for j in range(5) for i in range(5)]
        stdin = '\n'.join(f'{90 - 180 * z / rows!r} {-180 + 180 * (x % (2 * rows)) / rows!r}' for x, z in indices)
        samples = [float(v) for v in self.native('samples', PARITY_SEED, PARITY_SIZE, stdin=stdin).split()]
        expected = [tile['heights_m'][j][i] for j in range(5) for i in range(5)]
        for value, reference in zip(samples, expected):
            self.assertLessEqual(abs(value - reference), CONTRACT['absolute_tolerance']
                                 + CONTRACT['relative_tolerance'] * abs(reference))

    def test_unreal_world_frame_fixtures_hold_for_cardinals_elevation_seam_and_poles(self):
        fixtures = json.loads((ROOT / 'Fixtures' / 'unreal-world-frame-v1.json').read_text(encoding='utf-8'))
        from fantasy_world_generator.coordinates import resolve_coordinate
        origin = fixtures['origin']
        frame = resolve_coordinate({'coordinate_version': 1, 'operation': 'tangent_frame', 'values': {
            'latitude_degrees': origin['latitude_degrees'], 'longitude_degrees': origin['longitude_degrees']}})
        centre = resolve_coordinate({'coordinate_version': 1, 'operation': 'globe_position', 'values': {
            'latitude_degrees': origin['latitude_degrees'], 'longitude_degrees': origin['longitude_degrees'],
            'radius_m': origin['radius_m'], 'height_m': origin['origin_height_m']}})
        for case in fixtures['sign_cases']:
            with self.subTest(name=case['name']):
                position = [centre[i] + case['offset_east_m'] * frame['east'][i]
                            + case['offset_up_m'] * frame['up'][i] + case['offset_north_m'] * frame['north'][i]
                            for i in range(3)]
                values = [float(v) for v in self.native('frame', stdin=' '.join(repr(v) for v in (
                    origin['latitude_degrees'], origin['longitude_degrees'], origin['radius_m'],
                    origin['origin_height_m'], *position))).split()]
                unreal = dict(zip(('x_cm', 'y_cm', 'z_cm'), values[15:18]))
                for axis, expectation in case['expect'].items():
                    if expectation == 'positive':
                        self.assertGreater(unreal[axis], 0)
                    elif expectation == 'negative':
                        self.assertLess(unreal[axis], 0)
                    else:
                        self.assertLessEqual(abs(unreal[axis]), 1e-6)
                self.assertAlmostEqual(unreal['x_cm'], case['offset_east_m'] * 100, places=6)
                self.assertAlmostEqual(unreal['y_cm'], case['offset_north_m'] * 100, places=6)
                self.assertAlmostEqual(unreal['z_cm'], case['offset_up_m'] * 100, places=6)
        for case in fixtures['axis_cases']:
            with self.subTest(name=case['name']):
                east, up, north = case['axis_east_up_north']
                self.assertEqual([east, north, up], case['expected_axis'], 'unit axes permute and never scale')
        for case in fixtures['identity_cases']:
            with self.subTest(name=case['name']):
                values = [float(v) for v in self.native('frame', stdin=' '.join(repr(v) for v in (
                    case['latitude_degrees'], case['longitude_degrees'], origin['radius_m'], 0.0, 0.0, 0.0, 0.0))).split()]
                up = values[0:3]
                if case['kind'] == 'pole':
                    self.assertEqual(up, case['expected_up'])
                else:
                    mirrored = [float(v) for v in self.native('frame', stdin=' '.join(repr(v) for v in (
                        case['latitude_degrees'], case['mirror_longitude_degrees'], origin['radius_m'],
                        0.0, 0.0, 0.0, 0.0))).split()]
                    self.assertEqual(up, mirrored[0:3], 'the seam must not tear')

    def test_frame_operations_match_the_coordinate_oracle(self):
        import random
        from fantasy_world_generator.coordinates import resolve_coordinate
        rng = random.Random(4)
        cases = [(rng.uniform(-90, 90), rng.uniform(-180, 180), rng.uniform(100, 20000), rng.uniform(-50, 50),
                  rng.uniform(-20000, 20000), rng.uniform(-20000, 20000), rng.uniform(-20000, 20000))
                 for _ in range(64)]
        cases += [(90, 0, 10000, 0, 0, 10000, 0), (-90, 180, 1774, 5, 1, 2, 3), (0, 180, 1774, 0, 1774, 0, 0)]
        native = [float(v) for v in self.native(
            'frame', stdin='\n'.join(' '.join(repr(v) for v in case) for case in cases)).split()]
        for index, (latitude, longitude, radius, height, *position) in enumerate(cases):
            with self.subTest(case=index):
                block = native[index * 21:(index + 1) * 21]
                frame = resolve_coordinate({'coordinate_version': 1, 'operation': 'tangent_frame', 'values': {
                    'latitude_degrees': latitude, 'longitude_degrees': longitude}})
                self.assertEqual(block[0:9], frame['up'] + frame['east'] + frame['north'])
                self.assertEqual(block[9:12], resolve_coordinate(
                    {'coordinate_version': 1, 'operation': 'globe_position', 'values': {
                        'latitude_degrees': latitude, 'longitude_degrees': longitude,
                        'radius_m': radius, 'height_m': height}}))
                local = resolve_coordinate({'coordinate_version': 1, 'operation': 'local_position', 'values': {
                    'latitude_degrees': latitude, 'longitude_degrees': longitude, 'radius_m': radius,
                    'origin_height_m': height, 'position_m': list(position)}})
                self.assertEqual(block[12:15], local)
                self.assertEqual(block[15:18], [local[0] * 100, local[2] * 100, local[1] * 100])

    def test_native_catalogue_reads_the_same_traits_habitats_and_preferences(self):
        """Authoring stays in Python; the native rules read the resolved result.

        A trait, a biome preference or a habitat rule that reads differently in the two
        implementations would place cities somewhere else, so every one of them is
        compared rather than the file being trusted because it parsed.
        """
        from icarus_sim.terrain_civilizations import eligible_civilizations
        from icarus_sim.terrain_profiles import (biome_food_multiplier, biome_preference,
                                                 civilization_ids, get_profile)
        queries, checks = [], []
        traits = ('water_reach', 'slope_comfort', 'climate_weight', 'flood_penalty', 'magic_penalty',
                  'land_per_city_km2', 'minimum_founding_residents', 'mutation_limit', 'food_demand',
                  'site_slope_limit', 'support_multiplier')
        for identity in civilization_ids():
            for trait in traits:
                queries.append(f'trait {identity} {trait}')
                checks.append(('trait', identity, trait))
        for identity in ('human_heartland', 'elf', 'dwarf'):
            for core, variant in ((3, '-'), (4, '-'), (17, '-'), (4, 'forest.weave'), (3, 'grassland.umbral')):
                queries.append(f'preference {identity} {core} {variant}')
                checks.append(('preference', identity, core, variant))
        environments = [(3, 18.0, 0.5, 0.4, 5e6, 0.8, 20.0, 1), (0, 5.0, 0.2, 0.9, 1e5, 0.02, 70.0, 0),
                        (4, 25.0, 0.9, 0.1, 2e7, 1.0, 5.0, 1), (17, -20.0, 0.6, 0.0, 3e6, 0.3, 85.0, 0),
                        (5, 10.0, 0.3, 0.05, 8e6, 0.5, 45.0, 0), (8, 12.0, 0.7, 0.6, 2e6, 0.1, 30.0, 1)]
        for values in environments:
            queries.append('habitat ' + ' '.join(repr(v) for v in values))
            checks.append(('habitat', values))
        output = self.native('catalogues', CATALOGUES, stdin='\n'.join(queries)).strip().split('\n')
        header = [line for line in output if line.startswith(('default ', 'registry ', 'profile '))]
        answers = [line for line in output if line not in header]
        self.assertEqual(len(header) - 2, len(civilization_ids()))
        self.assertEqual(len(answers), len(checks))
        for check, line in zip(checks, answers):
            with self.subTest(check=check[:3]):
                if check[0] == 'trait':
                    self.assertEqual(float(line), float(get_profile(check[1])[check[2]]))
                elif check[0] == 'preference':
                    variant = None if check[3] == '-' else check[3]
                    profile = get_profile(check[1])
                    self.assertEqual([float(v) for v in line.split()],
                                     [biome_preference(profile, check[2], variant),
                                      biome_food_multiplier(profile, check[2], variant)])
                else:
                    biome, temp, moisture, maritime, area, fraction, latitude, largest = check[1]
                    expected = eligible_civilizations(dict(
                        biome=biome, temperature=temp, moisture=moisture, maritime=maritime,
                        landmass_area_m2=area, landmass_fraction=fraction, abs_latitude=latitude,
                        largest_landmass=bool(largest)))
                    self.assertEqual([] if line == '-' else line.split(','), expected)

    def test_every_plannable_building_asset_has_a_registry_row(self):
        """The plan names a catalogue asset; the plugin resolves `building.<id>`.

        That prefix is the whole mapping between a planned building and something a
        consumer can spawn, so a renamed pack asset has to fail here rather than as a
        silently unplaced building in a cooked run.
        """
        catalogue = json.loads(CATALOGUES.read_text(encoding='utf-8'))
        rows = {row['id'] for row in json.loads(REGISTRY.read_text(encoding='utf-8'))['rows']}
        planned = {choice['asset_id']
                   for pack in catalogue['city_building_packs']['packs']
                   for option in pack['building_options']
                   for choice in option['asset_choices']}
        self.assertTrue(planned, 'the packs must offer buildings to plan')
        self.assertEqual(sorted(identity for identity in planned
                                if 'building.' + identity not in rows), [])

    def test_asset_registry_binds_every_catalogue_identity(self):
        from fantasy_world_generator.asset_list import compile_asset_list
        catalogue = compile_asset_list()
        table = json.loads(REGISTRY.read_text(encoding='utf-8'))
        identities = [asset['id'] for asset in catalogue['assets']]
        rows = {row['id']: row for row in table['rows']}
        self.assertEqual(len(rows), len(table['rows']), 'registry identities must be unique')
        self.assertEqual(sorted(rows), sorted(identities), 'every catalogue identity needs a binding slot')
        self.assertEqual(table['asset_list_sha256'], catalogue['content_sha256'])
        for identity, row in rows.items():
            with self.subTest(identity=identity):
                if row['status'] in ('bound', 'placeholder'):
                    self.assertTrue(row['path'].startswith('/'), 'bindings are engine object paths')
                    self.assertIn('.', row['path'])
                else:
                    self.assertEqual(row['status'], 'unbound')
                    self.assertTrue(row['reason'], 'an unbound identity states why, so it can be diagnosed')
        bound = [row for row in table['rows'] if row['status'] == 'bound']
        self.assertGreaterEqual(len(bound), 2, 'at least one mesh and one material swap prove the registry path')
        # A path outside a mount point cannot cook, and a bound identity that resolves
        # to the same object as its kind placeholder would prove nothing.
        placeholders = {row['kind']: row['path'] for row in table['rows'] if row['status'] == 'placeholder'}
        for row in table['rows']:
            if row['status'] == 'unbound':
                continue
            self.assertTrue(row['path'].startswith('/Engine/') or row['path'].startswith('/Game/'), row['path'])
            self.assertEqual(row['path'].count('.'), 1, 'object paths are Package.Object')
            package, _, obj = row['path'].partition('.')
            self.assertEqual(package.rsplit('/', 1)[-1], obj, 'the object must be the package default object')
            if row['status'] == 'bound' and row['kind'] in placeholders:
                self.assertNotEqual(row['path'], placeholders[row['kind']],
                                    'a swap must resolve to a different object than the placeholder')

    def test_native_registry_loader_resolves_and_diagnoses(self):
        from fantasy_world_generator.asset_list import compile_asset_list
        catalogue = compile_asset_list()
        identities = [asset['id'] for asset in catalogue['assets']]
        output = self.native('registry', REGISTRY, stdin='\n'.join(identities[:200] + ['no.such.identity']))
        lines = output.strip().split('\n')
        self.assertEqual(lines[0], f'rows {len(identities)}')
        self.assertTrue(lines[2].startswith('asset_list ' + catalogue['content_sha256']))
        resolved = dict(line.split(' ', 1) for line in lines[3:])
        for identity in identities[:200]:
            self.assertIn(identity, resolved)
            self.assertNotEqual(resolved[identity], 'missing_identity')
        self.assertEqual(resolved['no.such.identity'], 'missing_identity')

    def test_native_registry_rejects_unsupported_and_ambiguous_tables(self):
        table = json.loads(REGISTRY.read_text(encoding='utf-8'))
        broken = {
            'version': {**table, 'version': 2},
            'schema': {**table, 'schema': 'something.else'},
            'duplicate': {**table, 'rows': table['rows'][:2] + [table['rows'][0]]},
            'relative path': {**table, 'rows': [{**table['rows'][0], 'path': '../Escape.Escape'}]},
            'status': {**table, 'rows': [{**table['rows'][0], 'status': 'maybe'}]},
            'silent missing': {**table, 'rows': [{'id': 'a.b', 'kind': 'mesh', 'status': 'unbound', 'reason': ''}]},
        }
        for name, body in broken.items():
            with self.subTest(case=name):
                path = Path(self.directory.name) / 'broken.json'
                path.write_text(json.dumps(body), encoding='utf-8')
                result = subprocess.run([str(self.binary), 'registry', str(path)], input='',
                                        capture_output=True, text=True, timeout=60)
                self.assertNotEqual(result.returncode, 0, result.stdout[:400])

    # How many differing cells a failed layer comparison names before it stops.
    FIRST_DIFFERENCES = 6

    def assertCellsIdentical(self, values, expected, key, note=''):
        """Exact whole-layer comparison that names the differing cells instead of diffing them.

        Defined at the end of the class on purpose. Four board cards cite line numbers
        inside this file -- `tests/test_native_world.py:186`, `:456` and `:461` among
        them -- so anything inserted above them silently invalidates those citations and
        `tools/docs_check.py` reports CITE warnings against cards this lane does not own.

        The layers that call this are categorical: a biome id, a zone flag, a
        reached-or-not-reached hinterland. They are compared with no tolerance at all,
        and that is deliberate -- a tolerance here would hide a region that manifested in
        one implementation and not the other. What is NOT deliberate is what
        `assertEqual` does on the way to reporting a difference. A 1089-element list
        comparison hands both lists to `difflib`, `difflib._fancy_replace` recurses once
        per element, and unittest raises `RecursionError` while it is rendering the
        failure message. Measured on this interpreter, not inferred: two 1089-element
        float lists take about seven minutes to reach a 1000-frame `RecursionError`
        through `difflib._fancy_helper`. The assertion found a real divergence, spent
        minutes on it, and then crashed explaining it -- the layer name is lost, the
        mismatch count is lost, and the runner prints a difflib stack trace under the
        heading ERROR rather than FAIL.

        That cost a review cycle. The previous full run's six ERRORs -- `dominant_magic`
        and five `zone_*` layers -- were read as a separate root-cause family needing
        their own investigation; every one of them was this, wrapped around the same
        ley-width divergence the FAILs beside them were already reporting. `self.maxDiff`
        does not help: the recursion is inside difflib's comparison, not inside the
        truncation that follows it.

        So compare the lists here, with exactly the predicate `assertEqual` would use --
        `==` with CPython's per-element identity shortcut, which is what makes a list
        containing NaN equal to itself -- and report the count and the first few
        offenders. This cannot mask a difference: it examines every element before it
        decides, and it fails whenever `assertEqual` would have.
        """
        self.assertEqual(len(values), len(expected),
                         f'{key}{note}: {len(values)} cells against the reference\'s {len(expected)}')
        differing = [index for index, (native_value, reference) in enumerate(zip(values, expected))
                     if not (native_value is reference or native_value == reference)]
        if not differing:
            return
        shown = '; '.join(f'cell {index}: native {values[index]!r} vs reference {expected[index]!r}'
                          for index in differing[:self.FIRST_DIFFERENCES])
        if len(differing) > self.FIRST_DIFFERENCES:
            shown += f'; and {len(differing) - self.FIRST_DIFFERENCES} more'
        self.fail(f'{key}{note}: {len(differing)} of {len(expected)} cells differ -- {shown}')

    def test_resolved_ley_networks_match_the_reference(self):
        """The ley network parameters themselves, before any raster reads them.

        This exists because the divergence it pins had no visible edge. `Core/magic.cpp`
        assigned the authored width straight through -- a flat 110 m -- while the
        reference scales it by the world's own circumference at
        `terrain_leyline_history.py:101`, resolving 1973.28 m at the 200 km default. A
        110 m Gaussian on a kilometres-wide cell falls between raster cells, so every ley
        field, every instability field and every categorical layer downstream collapsed,
        and what the suite reported was fifty-five mismatched grids and six RecursionErrors.
        Nothing anywhere asserted the width itself, on either side.

        So assert it here, where a revert is one wrong number rather than a wall of them,
        and assert it with no tolerance: it is a resolved parameter, not a sampled field.
        The driver's `networks` operation builds no world, so this costs milliseconds on
        top of the oracle the rest of the class already shares.
        """
        world = self.oracle(PARITY_SEED, PARITY_SIZE)
        reference = world['magic']['networks']
        rows = _tagged(self.native('networks', PARITY_SEED, PARITY_SIZE))['NETWORK']
        # Only the three resolved PARAMETERS are compared, not the node count. The oracle
        # is a finished world, and the age transitions append a key point to a network for
        # every ruin whose legacy names that school, so the reference's `weave` carries 26
        # nodes at this seed against the eight it was generated with. Width, strength and
        # instability are untouched by an age, so they are comparable against a fresh
        # `generate_networks` and the node count is not. (Measured, not assumed:
        # `network_geometry(seed, 8)` returns exactly 8 positions, so the extra 18 are the
        # age transitions' and not a generation difference.)
        #
        # Core carries the eight known schools; the reference declares twelve, the extra
        # four being the hidden schools generation never raises. Core's order is contract
        # -- dominance ties break on it -- so check the names as well as the numbers.
        self.assertEqual(len(rows), 8, 'the native core carries the eight known schools')
        for row in rows:
            name = row[1]
            with self.subTest(school=name):
                self.assertIn(name, reference, 'native school names come from the reference')
                network = reference[name]
                self.assertEqual(float(row[2]), network['width_m'],
                                 'ley width is reach-scaled by the world, not an absolute 110 m')
                self.assertEqual(float(row[3]), network['strength'], name + ' strength')
                self.assertEqual(float(row[4]), network['instability'], name + ' instability')


if __name__ == '__main__':
    unittest.main()
