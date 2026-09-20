import copy
import unittest
from dataclasses import replace

from icarus_sim.terrain_world import default_config
from icarus_sim.terrain_lab import generate
from icarus_sim.terrain_metrics import (elevation_metrics, weighted_percentile, window_angle,
                                        bluff_sites, resolved_octaves)


def world(**kwargs):
    return generate(replace(default_config(3), seed=42, size=33, phase=8, **kwargs))


class MetricPurityTests(unittest.TestCase):
    def test_metrics_do_not_mutate_the_world(self):
        built = world()
        before = copy.deepcopy(built)
        elevation_metrics(built)
        self.assertEqual(built.keys(), before.keys())
        self.assertEqual(built['layers'].keys(), before['layers'].keys())
        self.assertEqual(built['layers']['height'], before['layers']['height'])
        self.assertEqual(built['effective_config'], before['effective_config'])

    def test_weighted_percentile_follows_area_not_count(self):
        # One enormous low cell outweighs many tiny high ones.
        pairs = [(0., 100.)]+[(90., 1.)]*20
        self.assertEqual(weighted_percentile(pairs, .5), 0.)
        self.assertEqual(weighted_percentile(pairs, .99), 90.)
        self.assertIsNone(weighted_percentile([], .5))


class WindowHonestyTests(unittest.TestCase):
    """A window finer than the grid must be refused, never silently widened."""

    def test_window_angle_reports_what_it_did(self):
        radius, size = 1774.41, 129
        cell = radius*3.14159265358979/(size-1)
        _, effective, status = window_angle(radius, size, cell/10)
        self.assertEqual(status, 'below_grid')
        self.assertAlmostEqual(effective, cell, places=2)
        _, _, status = window_angle(radius, size, cell*2)
        self.assertEqual(status, 'resolved')
        _, _, status = window_angle(radius, size, radius*10)
        self.assertEqual(status, 'above_cap')

    def test_sub_grid_bluff_run_refuses_to_answer(self):
        built = world()
        radius = built['effective_config']['globe_radius']
        result = bluff_sites(built['layers']['height'], radius, 0., 20., 40.)
        # Widening 40 m to a whole cell and counting anyway is how a 42 m planet
        # comes to report hundreds of cliffs.
        self.assertEqual(result['run_status'], 'below_grid')
        self.assertIsNone(result['bluff_sites'])
        self.assertIn('below the', result['reason'])

    def test_resolvable_bluff_run_returns_a_count(self):
        built = world()
        radius = built['effective_config']['globe_radius']
        spacing = 2*3.14159265358979*radius/(len(built['layers']['height'])-1)
        result = bluff_sites(built['layers']['height'], radius, 0., 20., 2*spacing)
        self.assertIsNotNone(result['bluff_sites'])
        self.assertGreaterEqual(result['bluff_sites'], 0)


class KnobResponsivenessTests(unittest.TestCase):
    """Every metric must move under the knob that should move it.

    A metric that ignores its own knob is a broken measurement, not a stable one,
    and is worse than no metric because it reads as evidence. Delete any metric
    that cannot earn a test here.
    """

    def metrics(self, **kwargs):
        return elevation_metrics(world(**kwargs))

    def test_orogeny_raises_the_relief_hierarchy(self):
        low = self.metrics(orogeny=1.)['land']
        high = self.metrics(orogeny=6.)['land']
        self.assertGreater(high['land_p90_over_p50'], low['land_p90_over_p50'])
        self.assertGreater(high['land_max_m'], low['land_max_m'])

    def test_orogeny_lowers_the_craton_fraction(self):
        low = self.metrics(orogeny=1.)['tectonics']
        high = self.metrics(orogeny=6.)['tectonics']
        self.assertLess(high['craton_land_fraction'], low['craton_land_fraction'])

    def test_more_plates_means_more_orogenic_land(self):
        few = self.metrics(plate_count=12)['tectonics']
        many = self.metrics(plate_count=24)['tectonics']
        self.assertGreater(many['orogenic_land_fraction'], few['orogenic_land_fraction'])

    def test_erosion_flattens_local_relief(self):
        none = self.metrics(erosion_passes=0)['local_relief'][0]
        heavy = self.metrics(erosion_passes=20)['local_relief'][0]
        self.assertLess(heavy['p90_m'], none['p90_m'])

    def test_wavelength_raises_resolved_octaves(self):
        short = self.metrics(wavelength=4300.)['noise']
        long = self.metrics(wavelength=25000.)['noise']
        self.assertGreater(long['resolved_octaves'], short['resolved_octaves'])


class OctaveMirrorTests(unittest.TestCase):
    """resolved_octaves mirrors generate_tectonics; prove it against real output."""

    def test_the_mirror_tracks_the_generator_up_the_octave_ladder(self):
        """Both directions, at three sizes, because one direction at one size proves nothing.

        This test used to build seed 42 at size 17 -- the artifacts configuration, exactly --
        and assert the noise layer was identically zero. It passed, and what it established
        was not the docstring's claim. A predictor stuck at 0 and a generator that never
        accumulated would agree just as well, because the only case it looked at was the one
        where both sides are zero. It was also the repository's own written proof that the
        world `tools/validate_repo.py` guards for determinism is flat, sitting green.

        The ladder fixes that. 0/1/2 octaves at 17/33/65 is a property of the generator, not
        of seed 42: admission is 1.6*(size-1)/(2*pi*sqrt(plate_count)), so the globe radius
        cancels out. Each rung asserts the predictor's count, the count the generator
        published for itself -- which is what makes this a mirror test rather than a
        restatement of the predictor -- and that noise is zero exactly when zero octaves
        resolve, so a generator that stopped accumulating now fails at 33 and 65.
        """
        for size, expected in ((17, 0), (33, 1), (65, 2)):
            with self.subTest(size=size):
                cfg = replace(default_config(3), seed=42, size=size, phase=3)
                predicted = resolved_octaves(cfg.globe_radius, cfg.size, cfg.wavelength, cfg.octaves)
                self.assertEqual(predicted['resolved_octaves'], expected)
                built = generate(cfg)
                self.assertEqual(built['resolved_octaves'], expected,
                                 'the generator disagrees with the predictor it mirrors')
                flat = all(value == 0. for row in built['layers']['noise'] for value in row)
                self.assertEqual(flat, expected == 0,
                                 f'{expected} octaves resolved and the noise layer is '
                                 f'{"identically zero" if flat else "not flat"}')

    def test_design_radius_not_physical_radius(self):
        # The filter runs before apply_world_scale, so it sees the design radius.
        # Reading the physical radius here overstates surviving octaves badly.
        design = resolved_octaves(53817.9, 193, 4300., 5)['resolved_octaves']
        physical = resolved_octaves(9549.3, 193, 4300., 5)['resolved_octaves']
        self.assertEqual(design, 1)
        self.assertEqual(physical, 3)


if __name__ == '__main__':
    unittest.main()
