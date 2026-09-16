"""Independent geometry vectors and agreement with existing producer exports."""
from contextlib import redirect_stderr
import io
import json
import math
from pathlib import Path
import unittest
import tempfile
from unittest.mock import patch

from fantasy_world_generator.coordinates import resolve_coordinate
from fantasy_world_generator.capabilities import capabilities_document, require_capabilities


ROOT = Path(__file__).resolve().parents[1]


def resolve(operation, **values):
    return resolve_coordinate(dict(coordinate_version=1, operation=operation, values=values))


class CoordinateContractTests(unittest.TestCase):
    def assertVector(self, actual, expected):
        self.assertEqual(len(actual), len(expected))
        for a, b in zip(actual, expected):
            self.assertTrue(math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-9), (a, b))

    def test_independent_coordinate_fixtures(self):
        fixtures = json.loads((ROOT / 'Fixtures/coordinates-v1.json').read_text())
        for case in fixtures['valid']:
            with self.subTest(name=case['name']):
                result = resolve_coordinate(case['request'])
                expected = case['expected']
                if isinstance(expected, dict):
                    self.assertEqual(set(result), set(expected))
                    for key in expected:
                        self.assertVector(result[key], expected[key])
                elif isinstance(expected, list):
                    self.assertVector(result, expected)
                else:
                    self.assertAlmostEqual(result, expected, places=9)
                json.dumps(result, allow_nan=False)
        for request in fixtures['invalid']:
            with self.subTest(request=request), self.assertRaises(ValueError):
                resolve_coordinate(request)

    def test_seams_poles_and_nested_tile_samples(self):
        for latitude in (-90, -45, 0, 45, 90):
            a = resolve('globe_position', latitude_degrees=latitude, longitude_degrees=-180, radius_m=1000, height_m=20)
            b = resolve('globe_position', latitude_degrees=latitude, longitude_degrees=180, radius_m=1000, height_m=20)
            self.assertEqual(a, b)
        for longitude in (-180, -60, 0, 90, 180):
            self.assertEqual(resolve('globe_position', latitude_degrees=90, longitude_degrees=longitude, radius_m=1000, height_m=-20), [0, 980, 0])
        for x, z in ((0, 0), (3, 2), (8, 4), (16, 8)):
            self.assertEqual(resolve('tile_direction', level=3, x=x, z=z), resolve('tile_direction', level=4, x=2*x, z=2*z))

    def test_frames_are_right_handed_even_at_poles(self):
        for lat, lon in ((0, 0), (45, 70), (90, -30), (-90, 180)):
            f = resolve('tangent_frame', latitude_degrees=lat, longitude_degrees=lon)
            e, u, n = f['east'], f['up'], f['north']
            self.assertVector([e[1]*u[2]-e[2]*u[1], e[2]*u[0]-e[0]*u[2], e[0]*u[1]-e[1]*u[0]], n)
            for a in (e, u, n):
                self.assertAlmostEqual(sum(v*v for v in a), 1)
            for a, b in ((e, u), (e, n), (u, n)):
                self.assertAlmostEqual(sum(x*y for x, y in zip(a, b)), 0)

    def test_strict_types_shapes_versions_and_finite_arithmetic(self):
        base = dict(coordinate_version=1, operation='globe_position', values=dict(latitude_degrees=0, longitude_degrees=0, radius_m=1000, height_m=10))
        invalid = [None, [], {}, dict(base, extra=1), dict(base, operation='unreal_import'), dict(base, values=[])]
        invalid += [dict(base, coordinate_version=v) for v in (True, 1.0, '1', 0, 2)]
        for key in base['values']:
            invalid.append(dict(base, values={k: v for k, v in base['values'].items() if k != key}))
            for value in (True, None, '0', [], {}, float('nan'), float('inf'), -float('inf'), 10**1000):
                invalid.append(dict(base, values=dict(base['values'], **{key: value})))
        invalid.append(dict(base, values=dict(base['values'], extra=0)))
        for request in invalid:
            with self.subTest(request=str(request)[:200]), self.assertRaises(ValueError):
                resolve_coordinate(request)
        for operation, values in (
            ('globe_position', dict(latitude_degrees=0, longitude_degrees=0, radius_m=1e308, height_m=1e308)),
            ('metres_to_centimetres', dict(value_m=1e308)),
            ('height_above_sea', dict(height_m=1e308, sea_level_m=-1e308)),
            ('city_direction', dict(latitude_degrees=0, longitude_degrees=0, radius_m=1e-308, x_m=1e308, z_m=0)),
            ('local_position', dict(latitude_degrees=0, longitude_degrees=0, radius_m=1000, origin_height_m=0, position_m=[0, 1])),
        ):
            with self.subTest(operation=operation), self.assertRaises(ValueError):
                resolve(operation, **values)

    def test_existing_city_patch_and_tile_geometry_agrees(self):
        from icarus_sim.world_scene import frame, local_direction, position
        from icarus_sim.terrain_detail import attach_detail, HeightField, export_height_tile
        from icarus_sim.terrain_patch import generate_patch, PatchConfig
        world = {'config': {'seed': 42, 'size': 9}, 'effective_config': {'globe_radius': 1000, 'sea_level': -30},
                 'layers': {'height': [[-20.]*9 for _ in range(9)], 'water_type': [[1]*9 for _ in range(9)]}}
        attach_detail(world)
        field = HeightField(world)
        f = frame(world, {'x': 4, 'z': 4})
        for x, z in ((0, 0), (3, 4), (-50, 30)):
            p = resolve('city_direction', latitude_degrees=0, longitude_degrees=0, radius_m=1000, x_m=x, z_m=z)
            self.assertVector(p, local_direction(f, x, z))
            self.assertVector(position(field, p), [980*v for v in p])
        mesh = generate_patch(world, PatchConfig(span=4, spacing=2))
        for row in range(3):
            for col in range(3):
                p = resolve('patch_direction', latitude_degrees=0, longitude_degrees=0, radius_m=1000, x_m=col*2-2, z_m=row*2-2)
                local = resolve('local_position', latitude_degrees=0, longitude_degrees=0, radius_m=1000, origin_height_m=-20, position_m=[980*v for v in p])
                self.assertVector(local, [mesh[k][row][col] for k in ('local_x', 'local_y', 'local_z')])
        for x, z in ((0, 0), (7, 1), (3, 3)):
            seen = []
            def height(_field, p):
                seen.append(list(p))
                return 0.
            with patch.object(HeightField, 'height', height):
                export_height_tile(world, 2, x, z, 1)
            expected = [resolve('tile_direction', level=2, x=x+i, z=z+j) for j in range(2) for i in range(2)]
            for a, b in zip(seen, expected):
                self.assertVector(a, b)


class CapabilityContractTests(unittest.TestCase):
    def test_cli_exports_descriptor_and_rejects_unknown_version_without_overwrite(self):
        from fantasy_world_generator.cli import main
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'capabilities.json'
            self.assertEqual(main(['capabilities', '--output', str(output)]), 0)
            self.assertEqual(json.loads(output.read_text()), capabilities_document())
            original = output.read_bytes()
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                main(['capabilities', '--version', '2', '--output', str(output)])
            self.assertEqual(error.exception.code, 2)
            self.assertEqual(output.read_bytes(), original)

    def test_negotiation_accepts_reference_and_rejects_unavailable_runtime(self):
        cases = json.loads((ROOT / 'Fixtures/capabilities-v1.json').read_text())
        for request in cases['valid']:
            self.assertEqual(require_capabilities(request), capabilities_document())
        for request in cases['invalid']:
            with self.subTest(request=request), self.assertRaises(ValueError):
                require_capabilities(request)
        for value in (True, 1.0, '1', 0, 2, None):
            with self.subTest(version=value), self.assertRaises(ValueError):
                capabilities_document(value)
        for value in (True, 2.0, '2', [2], None, {}):
            with self.subTest(version=value), self.assertRaises(ValueError):
                require_capabilities({'capability_version': 1, 'requires': {'world_json': value}})
        for request in (None, [], {}, {'capability_version': 1, 'requires': []}, {'capability_version': 1, 'requires': {}, 'extra': 0}):
            with self.subTest(request=request), self.assertRaises(ValueError):
                require_capabilities(request)

    def test_registry_is_caller_owned_and_agrees_with_export_contracts(self):
        from icarus_sim.city_planner import VERSION
        from fantasy_world_generator.cli import world_document
        doc = capabilities_document()
        self.assertEqual(doc['implementation'], 'python-reference')
        self.assertEqual(doc['supported']['city_plans_json'], [VERSION])
        for name, filename, field in (('world_json', 'world-output.schema.json', 'schema_version'), ('asset_list_json', 'asset-list.schema.json', 'schema_version'), ('height_tile_json', 'height-tile.schema.json', 'version')):
            schema = json.loads((ROOT / 'Contracts/schemas' / filename).read_text())
            self.assertEqual(doc['supported'][name], [schema['properties'][field]['const']])
        world = world_document({'recipe_version': 3, 'seed': 42, 'overrides': {'size': 9, 'phase': 1}})
        self.assertEqual(doc['supported']['generation_algorithm'], [world['generator_version']])
        self.assertEqual(doc['supported']['recipe'], [world['recipe']['version']])
        schema = json.loads((ROOT / 'Contracts/schemas/world-output.schema.json').read_text())
        self.assertEqual(doc['supported']['world_scene_json'], [schema['properties']['world_scene']['properties']['version']['const']])
        self.assertTrue(set(doc['unsupported']).isdisjoint(doc['supported']))
        self.assertEqual(doc['coordinates']['tangent']['axes'], ['east', 'up', 'north'])
        doc['supported']['world_json'].clear()
        doc['coordinates']['tangent']['axes'].clear()
        self.assertEqual(capabilities_document()['supported']['world_json'], [2])
        self.assertEqual(capabilities_document()['coordinates']['tangent']['axes'], ['east', 'up', 'north'])
