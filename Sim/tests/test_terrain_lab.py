import math
import unittest

from icarus_sim.terrain_lab import Config, carve, generate, measure, perlin


class TerrainLabTests(unittest.TestCase):
    def test_plane_slope_in_physical_units(self):
        for spacing in (2.0, 10.0):
            h = [[2*x*spacing + 3*z*spacing for x in range(7)] for z in range(7)]
            slope, _ = measure(h, spacing, 2)
            expected = math.degrees(math.atan(math.sqrt(13)))
            for row in slope:
                for value in row:
                    self.assertAlmostEqual(value, expected)

    def test_tpi_matches_brute_force_including_edges(self):
        h = [[float((x*7+z*11)%17) for x in range(7)] for z in range(7)]
        _, tpi = measure(h, 5, 2)
        for z in range(7):
            for x in range(7):
                values = [h[j][i] for j in range(max(0,z-2), min(7,z+3))
                          for i in range(max(0,x-2), min(7,x+3))]
                self.assertAlmostEqual(tpi[z][x], h[z][x]-sum(values)/len(values))

    def test_carve_has_exact_depth_and_local_support(self):
        cfg = Config(size=17, extent=1600, depth=300, width=200, meander=0)
        base = [[1000.0]*17 for _ in range(17)]
        h = carve(base, cfg)
        self.assertAlmostEqual(h[8][8], 700)
        self.assertAlmostEqual(h[8][0], 1000)
        self.assertEqual(base[8][8], 1000)
        self.assertTrue(all(700 <= v <= 1000 for row in h for v in row))

    def test_seed_repeatability_and_stage_isolation(self):
        a = generate(Config(size=17))
        b = generate(Config(size=17))
        c = generate(Config(size=17, seed=52))
        d = generate(Config(size=17, depth=0))
        self.assertEqual(a['layers'], b['layers'])
        self.assertNotEqual(a['layers']['base'], c['layers']['base'])
        self.assertEqual(a['layers']['base'], d['layers']['base'])
        self.assertEqual(d['layers']['base'], d['layers']['height'])
        self.assertTrue(all(math.isfinite(v) for layer in a['layers'].values() for row in layer for v in row))

    def test_noise_is_continuous_and_nonconstant(self):
        self.assertAlmostEqual(perlin(1-1e-7, .37, 9), perlin(1+1e-7, .37, 9), places=5)
        self.assertNotEqual(perlin(.3, .7, 9), perlin(.4, .7, 9))

    def test_invalid_configuration(self):
        for args in ({'size':1}, {'size':2049}, {'extent':0}, {'width':0},
                     {'depth':-1}, {'extent':math.nan}, {'ridge':1.1}, {'octaves':0},
                     {'extent':1e308}, {'width':1e-300}):
            with self.subTest(args=args), self.assertRaises(ValueError):
                Config(**args)

    def test_underresolved_features_are_reported(self):
        result = generate(Config(size=17, width=10, wavelength=100))
        self.assertEqual(result['resolved_octaves'], 0)
        self.assertTrue(any('half-width' in w for w in result['warnings']))

    def test_export_is_reproducible_without_timing(self):
        import json
        from tools.terrain_lab import report
        result = generate(Config(size=17))
        self.assertEqual(json.loads(json.dumps(result))['layers'], result['layers'])
        html = report(result)
        self.assertNotIn('__DATA__', html)
        self.assertIn('const live=false', html)

    def test_globe_seam_poles_and_reproducibility(self):
        cfg = Config(size=17, shape='globe')
        a, b = generate(cfg), generate(cfg)
        self.assertEqual(a['layers'], b['layers'])
        for layer in a['layers'].values():
            for row in layer:
                self.assertAlmostEqual(row[0], row[-1])
                self.assertTrue(all(math.isfinite(v) for v in row))
            for row in (layer[0], layer[-1]):
                self.assertLess(max(row)-min(row), 1e-8)

    def test_constant_globe_has_no_slope_or_tpi(self):
        a = generate(Config(size=17, shape='globe', amplitude=0, depth=0))
        for key in ('height', 'slope', 'tpi'):
            self.assertTrue(all(abs(v)<1e-8 for row in a['layers'][key] for v in row))

    def test_globe_rejects_inverted_surface(self):
        with self.assertRaises(ValueError):
            Config(shape='globe', globe_radius=100)

    def test_spherical_gradient_against_analytic_field(self):
        from icarus_sim.terrain_globe import direction, measure_globe
        n, r, a = 65, 10000, 500
        h = [[a*direction(x,z,n)[1] for x in range(n)] for z in range(n)]
        slope, _ = measure_globe(h, r, 500)
        self.assertAlmostEqual(slope[n//2][n//2], math.degrees(math.atan(a/r)), delta=.02)
        self.assertAlmostEqual(slope[0][0], 0, delta=.02)

    def test_seed_api_inputs_and_prompt_normalization(self):
        from icarus_sim.terrain_seed import manual_seed, prompt_seed
        self.assertEqual(manual_seed(42)['seed'], 42)
        self.assertEqual(prompt_seed('  café\r\nmountains  '), prompt_seed('cafe\u0301\nmountains'))
        self.assertNotEqual(prompt_seed('desert')['seed'], prompt_seed('mountains')['seed'])
        self.assertEqual(prompt_seed('A world of mountains and deep gorges')['seed'], 1014459558)
        for value in (True, -1, 2**32, 4.5, '42'):
            with self.assertRaises(ValueError):
                manual_seed(value)
        for value in ('  ', 'x'*4097, 42):
            with self.assertRaises(ValueError):
                prompt_seed(value)


if __name__ == '__main__':
    unittest.main()
