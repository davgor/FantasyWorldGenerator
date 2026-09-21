"""One sphere-grid implementation, shared, and pinned to the generator in one place.

Four reader packages — ``hero_generator``, ``story_web``, ``npc_roster`` and
``key_locations`` — used to carry their own copy of ``child_seed``, and ``key_locations``
carried a copy of the node layout as well, because a reader reads only a finished world's
JSON and never imports the generator. That isolation is real and is asserted below. What it
did not require was four copies: it required that no reader import ``icarus_sim``, which a
shared pure-arithmetic package satisfies too.

So the primitives live in :mod:`world_geometry` once, every reader imports them, and this
module is the single pin that holds them to the generator's own behaviour at several raster
sizes. The identity assertions are the point of the file: equality would pass again on the
day someone re-forks a copy, and identity would not.

``icarus_sim`` deliberately stays the oracle and imports nothing from here — see
SHARED-GEOMETRY for the rejected alternative.
"""
import ast
import math
import pathlib
import unittest

import world_geometry
from world_geometry import grid, seeds

RADIUS = 31830.99
SIZE = 17


class SharedImplementation(unittest.TestCase):
    """Identity, not equality. Four things that are equal today can fork tomorrow."""

    def test_every_reader_package_shares_one_seed_helper(self):
        import hero_generator.seeds as hero
        import key_locations.seeds as keyloc
        import npc_roster.seeds as roster
        import story_web.seeds as web
        for module in (hero, keyloc, roster, web):
            self.assertIs(module.child_seed, seeds.child_seed, module.__name__)
            self.assertIs(module.rng, seeds.rng, module.__name__)

    def test_the_grid_primitives_have_one_implementation(self):
        from key_locations.core import grid as keyloc_grid
        for name in ('node_count', 'node_index', 'cell', 'direction', 'cell_area_m2',
                     'cell_of_direction', 'great_circle_m', 'offset', 'normalise', 'slerp'):
            self.assertIs(getattr(keyloc_grid, name), getattr(grid, name), name)


class Pins(unittest.TestCase):
    """The one place the shared primitives are held to the generator's own arithmetic."""

    def test_seed_helper_matches_the_generator(self):
        from icarus_sim.terrain_tectonics import child_seed as reference
        for master in (0, 1, 42, 4294967295):
            for domain in ('', 'plates', 'keyloc-site-barrow-91', 'npc-name-a',
                           'hero-alignment-a', 'web-initiative-a'):
                for variation in (0, 1, 3):
                    self.assertEqual(seeds.child_seed(master, domain, variation),
                                     reference(master, domain, variation),
                                     f'{master}/{domain}/{variation}')

    def test_grid_geometry_matches_the_generator(self):
        from icarus_sim.terrain_erosion import sphere_grid
        from icarus_sim.terrain_globe import direction as reference_direction
        for n in (5, 9, 17, 33, 65):
            points, areas, _ = sphere_grid(n, RADIUS)
            self.assertEqual(len(points), grid.node_count(n))
            for index, (x, z) in enumerate(points):
                self.assertEqual(grid.node_index(x, z, n), index, f'node index at {(x, z)} size {n}')
                self.assertEqual(grid.cell(index, n), (x, z), f'cell of node {index} size {n}')
                self.assertEqual(grid.direction(x, z, n), reference_direction(x, z, n),
                                 f'direction at {(x, z)} size {n}')
                self.assertAlmostEqual(grid.cell_area_m2(z, n, RADIUS), areas[index], places=6)

    def test_great_circle_and_slerp_stay_on_the_sphere(self):
        a, b = grid.direction(2, 5, SIZE), grid.direction(9, 11, SIZE)
        self.assertAlmostEqual(grid.great_circle_m(a, a, RADIUS), 0., places=6)
        midpoint = grid.slerp(a, b, .5)
        self.assertAlmostEqual(math.sqrt(sum(c * c for c in midpoint)), 1., places=9)
        half = grid.great_circle_m(a, b, RADIUS) / 2
        self.assertAlmostEqual(grid.great_circle_m(a, midpoint, RADIUS), half, places=4)
        self.assertEqual(grid.slerp(a, a, .5), tuple(a))

    def test_offset_walks_the_distance_it_was_given(self):
        origin = grid.direction(4, 7, SIZE)
        for bearing in (0., 1.1, math.pi, 4.7):
            walked = grid.offset(origin, bearing, 1500., RADIUS)
            self.assertAlmostEqual(math.sqrt(sum(c * c for c in walked)), 1., places=9)
            self.assertAlmostEqual(grid.great_circle_m(origin, walked, RADIUS), 1500., places=3)


class Isolation(unittest.TestCase):
    def test_the_package_is_arithmetic_and_nothing_else(self):
        """No generator, no reader package, no filesystem, no network, no engine.

        The imports are read out of the parse tree rather than matched as substrings, so a
        word in a docstring is not mistaken for a dependency and an aliased import is not
        missed.
        """
        allowed = {'math', 'hashlib', 'random', 'world_geometry'}
        root = pathlib.Path(world_geometry.__file__).parent
        checked, imported = 0, set()
        for path in sorted(root.rglob('*.py')):
            source = path.read_text(encoding='utf-8')
            checked += 1
            self.assertNotIn('open(', source, f'{path.name} touches the filesystem')
            for node in ast.walk(ast.parse(source)):
                if isinstance(node, ast.Import):
                    imported.update(alias.name.split('.')[0] for alias in node.names)
                elif isinstance(node, ast.ImportFrom):
                    # A relative import is this package importing itself.
                    imported.add('world_geometry' if node.level
                                 else (node.module or '').split('.')[0])
        self.assertEqual(imported - allowed, set(), 'the shared geometry grew a dependency')
        self.assertGreaterEqual(checked, 3)

    def test_the_readers_still_never_reach_into_the_generator(self):
        import hero_generator
        import key_locations
        import npc_roster
        import story_web
        for package in (hero_generator, key_locations, npc_roster, story_web):
            root = pathlib.Path(package.__file__).parent
            for path in sorted(root.rglob('*.py')):
                for line in path.read_text(encoding='utf-8').splitlines():
                    self.assertFalse(line.lstrip().startswith(('import icarus_sim', 'from icarus_sim')),
                                     f'{path}: {line}')


if __name__ == '__main__':
    unittest.main()
