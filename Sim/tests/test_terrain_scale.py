import math
import unittest

from icarus_sim.terrain_lab import Config
from icarus_sim.terrain_scale import (AMPLITUDE_RATIO, REFERENCE_CIRCUMFERENCE_M,
                                      design_radius, detail_wavelength, max_relief_m,
                                      reach_scale, resolved_octaves, runoff_scale,
                                      shape_overrides)

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

    def test_the_advice_in_the_message_actually_works(self):
        # The bug this guards: the message used ':.0f', which rounds the needed
        # circumference to NEAREST. For 1667 m the true minimum is 90.1934 km and the
        # message said "above 90 km" -- a caller who built exactly the width named was
        # refused again by the same guard. Both printed bounds must round OUTWARD, so
        # feeding either number straight back must be accepted.
        import re
        for circumference, relief in ((11149.6, 1667.), (200_000., 4000.),
                                      (123456., 2500.), (11149.6, 206.4)):
            with self.subTest(circumference=circumference, relief=relief):
                with self.assertRaises(ValueError) as caught:
                    shape_overrides(circumference, relief, 1., 12, WORLD_SCALE)
                message = str(caught.exception)
                needed_km = float(re.search(r'above ([0-9.]+) km', message).group(1))
                admitted_m = float(re.search(r'at most ([0-9.]+) m', message).group(1))
                exact_km = circumference*relief/max_relief_m(circumference)/1000
                self.assertGreaterEqual(needed_km, exact_km,
                                        f'advice rounds below the true bound: {message}')
                # Both numbers are advice; both must be honoured by the guard itself.
                shape_overrides(needed_km*1000, relief, 1., 12, WORLD_SCALE)
                shape_overrides(circumference, admitted_m, 1., 12, WORLD_SCALE)

    def test_rejects_nonsense_inputs(self):
        for bad in ({'circumference_m': 0.}, {'relief_m': -1.}, {'plate_count': 1}):
            with self.assertRaises(ValueError):
                shape_overrides(**dict({'circumference_m': 200_000., 'relief_m': 500.,
                                        'orogeny': 1., 'plate_count': 12,
                                        'world_scale': WORLD_SCALE}, **bad))


class RunoffScaleTests(unittest.TestCase):
    """The area analogue of reach_scale. Structural properties only.

    Deliberately NOT asserted: runoff_scale(200_000.) == 321.8037865406216. The value is
    arithmetically exact, but pinning it to 1e-9 would turn a calibrated factor into a
    repo contract and the next retune would land as a mysterious test failure rather than
    a decision. What matters is the SHAPE -- identity at the reference, the square
    relationship, and monotonicity -- plus the saturation guard in
    Sim/tests/test_layer_scale_regression.py, which measures the layer itself.
    """

    def test_reference_world_is_unscaled(self):
        self.assertEqual(runoff_scale(REFERENCE_CIRCUMFERENCE_M), 1.0)
        self.assertEqual(reach_scale(REFERENCE_CIRCUMFERENCE_M), 1.0)

    def test_is_exactly_the_square_of_the_reach_factor(self):
        # Reaches take the length factor, catchments take its square. A future reader
        # "simplifying" one into the other is the failure this guards.
        for circumference in CIRCUMFERENCES:
            self.assertEqual(runoff_scale(circumference), reach_scale(circumference)**2)

    def test_grows_strictly_and_faster_than_the_reach_factor(self):
        values = [runoff_scale(c) for c in CIRCUMFERENCES]
        self.assertEqual(values, sorted(values))
        for circumference in CIRCUMFERENCES:
            if circumference > REFERENCE_CIRCUMFERENCE_M:
                self.assertGreater(runoff_scale(circumference), reach_scale(circumference))

    def test_doubling_the_world_quadruples_the_catchment(self):
        for circumference in CIRCUMFERENCES:
            self.assertAlmostEqual(runoff_scale(2*circumference)/runoff_scale(circumference),
                                   4.0, places=9)


class RiverThresholdBoundTests(unittest.TestCase):
    """The widened 0.001..10000 bound, in both gates that enforce it."""

    def test_config_accepts_the_derived_preset_values(self):
        # 200/400/600 km resolve 48.27/193.08/434.44 km2. At the old ceiling of 100 the
        # medium and large presets raised instead of generating.
        for circumference in (200_000., 400_000., 600_000.):
            Config(river_threshold_km2=.15*runoff_scale(circumference))

    def test_config_rejects_past_the_bound(self):
        Config(river_threshold_km2=10000.)
        for bad in (10000.1, .0009, float('nan')):
            with self.assertRaises(ValueError):
                Config(river_threshold_km2=bad)

    def test_registry_bound_matches_the_config_bound(self):
        from icarus_sim.terrain_world import registry, RIVER_THRESHOLD_MAX_KM2
        entry = registry(3)['river_threshold_km2']
        self.assertEqual(entry['max'], RIVER_THRESHOLD_MAX_KM2)
        self.assertEqual(entry['min'], .001)

    def test_request_accepts_and_rejects_at_the_bound(self):
        from icarus_sim.terrain_world import generate_request
        with self.assertRaises(ValueError) as caught:
            generate_request({'recipe_version': 3, 'seed': 42,
                              'overrides': {'river_threshold_km2': 10000.1}})
        self.assertIn('river_threshold_km2', str(caught.exception))

    def test_too_wide_a_world_raises_rather_than_clamping(self):
        # The defect class being fixed is a constant that silently stops scaling. If the
        # derived threshold ever exceeds the bound the request must SAY so, naming the
        # width, not quietly clamp and re-saturate the rivers.
        #
        # The three reaches are pinned by override so this width reaches the river bound
        # at all: they bind at 619.39, 1114.90 and 2477.55 km, all below this one, and the
        # reach block runs first. Pinning them is what keeps this test about the river.
        from icarus_sim.terrain_world import (generate_request,
                                              RIVER_THRESHOLD_MAX_CIRCUMFERENCE_KM)
        too_wide = RIVER_THRESHOLD_MAX_CIRCUMFERENCE_KM*2
        with self.assertRaises(ValueError) as caught:
            generate_request({'recipe_version': 3, 'seed': 42,
                              'overrides': {'circumference_km': too_wide, 'size': 17,
                                            'phase': 1, 'settlement_spacing': 450.,
                                            'support_reach': 1000.,
                                            'culture_link_cost': 1800.}})
        message = str(caught.exception)
        self.assertIn('river_threshold_km2', message)
        self.assertIn(f'{too_wide:g} km', message)


class ReachCeilingTests(unittest.TestCase):
    """The three reach keys raise past their ceiling instead of clamping to it.

    `min(100000., raw*factor)` is the `min(<absolute>, <relative>)` arm swap
    SCALE-METRE-CONSTANTS-COLLAPSE is about, one preset away from firing:
    `culture_link_cost` resolves 96870.01 m at the 600 km large preset, 3.13% below the
    ceiling, so a world authored at 620 km would have stopped scaling cultural regions
    with no error and no log line.

    Widths are chosen per key so that key is the FIRST of the three to bind, which is what
    makes each assertion name its own key rather than whichever one the loop reaches first.
    """

    KEYS = (('settlement_spacing', 450., 2477.5470281766684),
            ('support_reach', 1000., 1114.8961626795008),
            ('culture_link_cost', 1800., 619.3867570441671))

    def request(self, circumference_km):
        from icarus_sim.terrain_world import generate_request
        return generate_request({'recipe_version': 3, 'seed': 42,
                                 'overrides': {'circumference_km': circumference_km,
                                               'size': 17, 'phase': 1}})

    def test_each_key_binds_at_the_width_the_base_and_ceiling_imply(self):
        from icarus_sim.terrain_world import REACH_MAX_M
        for key, base, binds_km in self.KEYS:
            self.assertAlmostEqual(REACH_MAX_M/base*REFERENCE_CIRCUMFERENCE_M/1000.,
                                   binds_km, places=6, msg=key)

    def test_a_world_past_a_reach_ceiling_is_refused_naming_that_reach(self):
        from icarus_sim.terrain_world import REACH_MAX_M
        # One width per key, each inside the band where that key binds first.
        for key, base, binds_km, width_km in (('culture_link_cost', 1800., 619.3867570441671, 700.),
                                              ('support_reach', 1000., 1114.8961626795008, 1500.),
                                              ('settlement_spacing', 450., 2477.5470281766684, 3000.)):
            with self.assertRaises(ValueError, msg=key) as caught:
                self.request(width_km)
            document = caught.exception.document()
            self.assertEqual(document['code'], 'STATE_CAPACITY', key)
            self.assertEqual(document['field'], key)
            self.assertAlmostEqual(document['received'],
                                   base*reach_scale(width_km*1000.), places=6)
            self.assertEqual(document['expected']['max'], REACH_MAX_M)
            self.assertAlmostEqual(document['expected']['max_circumference_km'],
                                   binds_km, places=6)
            message = str(caught.exception)
            self.assertIn(key, message)
            self.assertIn(f'{width_km:g} km', message)

    def test_a_world_just_under_the_first_ceiling_still_generates(self):
        """The bound must not move down onto a width that works today.

        619 km is under `culture_link_cost`'s binding width and over the 600 km large
        preset, so this is the nearest legal world to the refusal above.
        """
        world = self.request(619.)
        self.assertLess(world['config']['culture_link_cost'], 100000.)

    def test_the_presets_resolve_below_every_ceiling_and_are_unchanged(self):
        """The acceptance criterion: no world anyone has generated moves.

        Below the ceiling `min(ceiling, v)` returns `v` itself, so this is float identity
        rather than a tolerance: the three presets resolve exactly `base*reach_scale` both
        before and after the clamp became a raise.
        """
        from icarus_sim.terrain_world import REACH_MAX_M
        for circumference_km in (200., 400., 600.):
            world = self.request(circumference_km)
            factor = reach_scale(circumference_km*1000.)
            for key, base, _ in self.KEYS:
                resolved = world['config'][key]
                self.assertEqual(resolved, base*factor, (key, circumference_km))
                self.assertLess(resolved, REACH_MAX_M, (key, circumference_km))


if __name__ == '__main__':
    unittest.main()
