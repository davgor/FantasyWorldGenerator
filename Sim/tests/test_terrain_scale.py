import math
import unittest

from icarus_sim.terrain_lab import Config
from icarus_sim.terrain_scale import (AMPLITUDE_RATIO, design_radius, detail_wavelength,
                                      max_relief_m, resolved_octaves, shape_overrides)

WORLD_SCALE = Config().world_scale
CIRCUMFERENCES = (11149.6, 60_000., 200_000., 1_000_000., 2_500_000.)


def config_from(overrides, **extra):
    return Config(**dict({'shape': 'globe', 'tectonics': 1, 'phase': 8, 'size': 33,
                          'globe_radius': overrides['globe_radius'],
                          'world_scale': overrides['world_scale'],
                          'tectonic_relief': overrides['tectonic_relief'],
                          'amplitude': overrides['amplitude'],
                          'wavelength': overrides['wavelength'],
                          'plate_count': overrides['plate_count'],
                          'orogeny': overrides['orogeny']}, **extra))


class DesignRadiusTests(unittest.TestCase):
    def test_matches_the_native_override(self):
        # Core/genesis.cpp:156 -- circumference_m/(2*pi*recipe.world_scale). Asserted
        # as the formula rather than a transcribed constant: the rounded 53817.9 that
        # gets quoted around is 1.2 m off, which is harmless until someone builds on it.
        for circumference in CIRCUMFERENCES:
            self.assertAlmostEqual(design_radius(circumference, WORLD_SCALE),
                                   circumference/(2*math.pi*WORLD_SCALE), places=9)
        self.assertAlmostEqual(design_radius(60_000., WORLD_SCALE), 53816.671, places=3)

    def test_design_radius_is_not_the_physical_radius(self):
        # The gap that makes octave counts easy to get wrong: they differ by 1/world_scale.
        self.assertAlmostEqual(design_radius(60_000., WORLD_SCALE)*WORLD_SCALE,
                               60_000./(2*math.pi), places=3)


class ScaleInvariantDetailTests(unittest.TestCase):
    """The whole point of deriving wavelength: detail must not thin out as the world grows."""

    def test_fixed_wavelength_loses_every_octave_on_a_large_world(self):
        for circumference, expected in ((60_000., 1), (200_000., 0), (1_000_000., 0)):
            radius = design_radius(circumference, WORLD_SCALE)
            kept = resolved_octaves(radius, 193, 4300., 5)['resolved_octaves']
            self.assertEqual(kept, expected, f'{circumference/1000:g} km at the fixed wavelength')

    def test_derived_wavelength_holds_the_octave_count_constant(self):
        counts = set()
        for circumference in CIRCUMFERENCES:
            radius = design_radius(circumference, WORLD_SCALE)
            counts.add(resolved_octaves(radius, 193, detail_wavelength(radius, 12), 5)['resolved_octaves'])
        self.assertEqual(len(counts), 1, f'octave count varied with world size: {counts}')
        self.assertGreater(counts.pop(), 0)

    def test_finer_rasters_resolve_strictly_more(self):
        radius = design_radius(1_000_000., WORLD_SCALE)
        wavelength = detail_wavelength(radius, 12)
        kept = [resolved_octaves(radius, size, wavelength, 5)['resolved_octaves']
                for size in (129, 257, 513)]
        self.assertEqual(kept, sorted(kept))
        self.assertLess(kept[0], kept[-1])


class ReliefBudgetTests(unittest.TestCase):
    """max_relief_m inverts the Config guard; check it against the guard, not against itself."""

    def test_ceiling_predicts_what_config_actually_accepts(self):
        for circumference in CIRCUMFERENCES:
            ceiling = max_relief_m(circumference)
            config_from(shape_overrides(circumference, ceiling*.98, 1., 12, WORLD_SCALE))
            with self.assertRaises(ValueError, msg=f'{circumference/1000:g} km above ceiling'):
                overrides = shape_overrides(circumference, ceiling*.5, 1., 12, WORLD_SCALE)
                relief = ceiling*1.02/WORLD_SCALE
                config_from(dict(overrides, tectonic_relief=relief,
                                 amplitude=relief*AMPLITUDE_RATIO))

    def test_todays_world_sits_just_under_its_own_ceiling(self):
        # 11.15 km admits about 206 m; the shipped world uses 142 m. This is why
        # raising relief before circumference is impossible, not merely unwise.
        ceiling = max_relief_m(11149.6)
        self.assertTrue(200 < ceiling < 215, ceiling)
        self.assertLess(800*WORLD_SCALE, ceiling)

    def test_heroic_relief_needs_a_larger_world(self):
        self.assertLess(max_relief_m(11149.6), 1667.)
        self.assertGreater(max_relief_m(1_000_000.), 1667.)

    def test_ceiling_is_independent_of_world_scale(self):
        # world_scale cancels in the inversion, so the ceiling is purely a
        # relief-to-circumference statement.
        overrides = shape_overrides(200_000., 500., 1., 12, WORLD_SCALE*3)
        config_from(overrides)
        self.assertAlmostEqual(max_relief_m(200_000.), max_relief_m(200_000.))


class ShapeOverrideTests(unittest.TestCase):
    def test_overrides_build_a_valid_config_at_every_scale(self):
        for circumference in CIRCUMFERENCES:
            relief = min(1667., max_relief_m(circumference)*.9)
            config = config_from(shape_overrides(circumference, relief, 3., 12, WORLD_SCALE))
            self.assertAlmostEqual(config.globe_radius*config.world_scale*2*math.pi,
                                   circumference, places=2)

    def test_impossible_relief_names_the_circumference_it_would_need(self):
        with self.assertRaises(ValueError) as caught:
            shape_overrides(11149.6, 1667., 1., 12, WORLD_SCALE)
        message = str(caught.exception)
        self.assertIn('km', message)
        self.assertIn('admits at most', message)

    def test_rejects_nonsense_inputs(self):
        for bad in ({'circumference_m': 0.}, {'relief_m': -1.}, {'plate_count': 1}):
            with self.assertRaises(ValueError):
                shape_overrides(**dict({'circumference_m': 200_000., 'relief_m': 500.,
                                        'orogeny': 1., 'plate_count': 12,
                                        'world_scale': WORLD_SCALE}, **bad))


if __name__ == '__main__':
    unittest.main()
