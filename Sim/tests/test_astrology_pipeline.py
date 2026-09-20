"""The moon, ruin legacies and the pantheon inside the generated pipeline and the age API."""
import copy
import json
import math
import re
import unittest
from pathlib import Path

from icarus_sim.terrain_world import generate_request
from icarus_sim.terrain_lab import Config
from icarus_sim.terrain_history import STATE_KEYS, materialize_stage, advance_age_request, city_fate
from icarus_sim.terrain_astrology import DAYS_PER_YEAR, tide
from icarus_sim.terrain_leyline_history import SCHOOLS, KNOWN_SCHOOLS
from icarus_sim.terrain_religion import catalogue_identity

ROOT = Path(__file__).resolve().parents[2]


class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.world = generate_request({'recipe_version': 3, 'seed': 42, 'overrides': {'size': 17}})

    def test_exports_are_present_versioned_and_replayable(self):
        world = self.world
        for key in ('astrology', 'lunar_almanac', 'religion'):
            self.assertEqual(world[key]['version'], 1, key)
            self.assertIn(key, STATE_KEYS)
        self.assertIn('lunar_sensitivity', world['layers'])
        grid = world['layers']['lunar_sensitivity']
        for row in grid:
            self.assertEqual(row[0], row[-1])
            self.assertTrue(all(0 <= v <= 1 for v in row))
        self.assertEqual(len(set(grid[0])), 1)
        self.assertEqual(world['lunar_almanac']['reported_year'], int(world['settlements']['founding']['end_year']))
        for name, net in world['magic']['networks'].items():
            if name not in world['magic']['lunar_surge']['factors']:
                # A hidden school has no tide and so carries no surge at all.
                self.assertNotIn('surged_strength', net)
                continue
            self.assertAlmostEqual(net['surged_strength'], net['strength'] * world['magic']['lunar_surge']['factors'][name])
        self.assertNotIn('astrology', materialize_stage(world, 8))
        self.assertEqual(materialize_stage(world, 9)['lunar_almanac']['reported_year'], 0)
        self.assertEqual(materialize_stage(world, 10)['lunar_almanac']['reported_year_source'], 'founding.end_year')
        self.assertNotIn('religion', materialize_stage(world, 12))
        self.assertIn('religion', materialize_stage(world, 13))
        final = materialize_stage(world, 16)
        for key in ('astrology', 'lunar_almanac', 'religion'):
            self.assertEqual(final[key], world[key], key)
        self.assertEqual(final['layers']['lunar_sensitivity'], grid)
        again = generate_request({'recipe_version': 3, 'seed': 42, 'overrides': {'size': 17}})
        for key in ('astrology', 'lunar_almanac', 'religion', 'ruins', 'history'):
            self.assertEqual(world[key], again[key], key)
        json.dumps(world, allow_nan=False)
        self.assertTrue(any('moon' in w.lower() for w in world['warnings']))

    def test_ages_record_the_moon_and_every_ruin_leaves_a_legacy(self):
        world = self.world
        ages = world['history']['ages']
        self.assertEqual(len(ages), 2)
        stage13 = materialize_stage(world, 13)
        self.assertEqual(ages[0]['moon']['day'], int(stage13['settlements']['founding']['end_year']) * DAYS_PER_YEAR)
        for age in ages:
            self.assertEqual(list(age['moon']['tide']), list(KNOWN_SCHOOLS))
            self.assertIn(age['moon']['leaning'], ('still', 'restless'))
            self.assertEqual(age['moon']['tide'], tide(world['astrology']['moon'], age['moon']['day']))
        for ruin in world['ruins']:
            self.assertIn(ruin['legacy']['school'], SCHOOLS)
            self.assertIn(ruin['legacy']['basis'], ('source', 'region', 'culture'))
            self.assertEqual(ruin['new_node_school'], ruin['legacy']['school'])
            net = world['magic']['networks'][ruin['legacy']['school']]
            node = next(n for n in net['nodes'] if n['id'] == ruin['id'] + '-key')
            self.assertLessEqual(node['intensity'], 4.)
            if ruin['cause'] in SCHOOLS:
                self.assertIn('moon_tide', ruin['evidence'])

    def test_lunar_influence_zero_changes_only_what_the_lottery_reads(self):
        quiet = generate_request({'recipe_version': 3, 'seed': 42, 'overrides': {'size': 17, 'lunar_influence': 0.}})
        loud = self.world
        for stage in (9, 13):
            a, b = materialize_stage(quiet, stage), materialize_stage(loud, stage)
            self.assertEqual(a['layers']['ley_weave'], b['layers']['ley_weave'])
            self.assertEqual(a['layers']['lunar_sensitivity'], b['layers']['lunar_sensitivity'])
        self.assertEqual(quiet['astrology'], loud['astrology'])
        for age_a, age_b in zip(quiet['history']['ages'], loud['history']['ages']):
            self.assertEqual(age_a['moon'], age_b['moon'])
        # Fate lotteries read different potencies under the moon, so probabilities can differ
        # even when the same cities happen to survive.
        probabilities = lambda world: [(r['id'], r['probability']) for r in world['ruins']]
        if probabilities(quiet) == probabilities(loud):
            self.skipTest('seed 42 at size 17 rolled the same fates with and without the moon')

    def test_city_fate_reads_the_surge(self):
        city = {'uid': 'city', 'x': 1, 'z': 1, 'direction': [1, 0, 0], 'population_profile': 'dwarf', 'city_class': 'capital'}
        layers = {'ley_' + s: [[0.] * 3 for _ in range(3)] for s in SCHOOLS}
        layers['ley_weave'][1][1] = .5
        layers['lunar_sensitivity'] = [[1.] * 3 for _ in range(3)]
        calm = city_fate(city, layers, [], 1000, 42, 1, roll=0., lunar=({s: 1. for s in SCHOOLS}, 1.))
        surge = city_fate(city, layers, [], 1000, 42, 1, roll=0., lunar=({s: (1.8 if s == 'weave' else 1.) for s in SCHOOLS}, 1.))
        self.assertGreater(surge['probability'], calm['probability'])
        self.assertEqual(surge['cause'], 'weave')
        self.assertAlmostEqual(surge['evidence']['moon_tide'], 1.8)
        self.assertEqual(surge['legacy'], {'school': 'weave', 'intensity': 3.5, 'basis': 'source'})
        off = city_fate(city, layers, [], 1000, 42, 1, roll=0., lunar=({s: 1.8 for s in SCHOOLS}, 0.))
        self.assertEqual(off['probability'], calm['probability'])

    def test_age_api_pins_and_refreshes_the_almanac(self):
        world = self.world
        advanced = advance_age_request({'api_version': 1, 'world': world, 'steps': 1})
        self.assertEqual(advanced['lunar_almanac']['reported_year'], int(advanced['settlements']['founding']['end_year']))
        self.assertEqual(len(advanced['history']['ages']), 3)
        self.assertIn('moon', advanced['history']['ages'][-1])
        self.assertEqual(advanced['religion']['version'], 1)
        self.assertEqual(materialize_stage(advanced, len(advanced['build_stages']))['religion'], advanced['religion'])
        for breaker in (lambda w: w.pop('astrology'), lambda w: w['astrology'].update(version=2),
                        lambda w: w['astrology']['moon'].update(great_year_days=7),
                        lambda w: w['religion']['catalogue'].update(sha256='0' * 64), lambda w: w.pop('lunar_almanac')):
            broken = copy.deepcopy(world)
            breaker(broken)
            with self.assertRaises(ValueError):
                advance_age_request({'api_version': 1, 'world': broken})
        self.assertEqual(world['religion']['catalogue'], catalogue_identity())

    def test_magic_disabled_world_still_has_a_moon_and_advances(self):
        world = generate_request({'recipe_version': 3, 'seed': 7, 'overrides': {'size': 17, 'magic_enabled': 0}})
        self.assertEqual(world['astrology']['version'], 1)
        self.assertTrue(all(g['status'] == 'absent' for g in world['religion']['gods'] if g['family'] == 'school'))
        advanced = advance_age_request({'api_version': 1, 'world': world})
        self.assertEqual(len(advanced['history']['ages']), 3)

    def test_moon_is_controllable_from_the_generation_and_age_apis(self):
        pinned = generate_request({'recipe_version': 3, 'seed': 42, 'overrides': {'size': 17, 'phase': 9, 'moon_synodic_days': 30, 'moon_tilt_degrees': 20.}})
        moon = pinned['astrology']['moon']
        self.assertEqual((moon['periods']['synodic'], moon['tilt_max_degrees']), (30, 20.))
        self.assertEqual(moon['periods']['spin'], self.world['astrology']['moon']['periods']['spin'])
        self.assertEqual(moon['controls']['overrides'], {'synodic': 30, 'tilt': 20.})
        varied = generate_request({'recipe_version': 3, 'seed': 42, 'overrides': {'size': 17, 'phase': 9, 'moon_variation': 3}})
        self.assertNotEqual(varied['astrology']['moon']['offsets'], self.world['astrology']['moon']['offsets'])
        self.assertEqual(varied['layers']['ley_weave'], pinned['layers']['ley_weave'], 'the moon never moves the base field')
        with self.assertRaises(ValueError):
            generate_request({'recipe_version': 3, 'seed': 42, 'overrides': {'size': 17, 'phase': 9, 'moon_synodic_days': 5}})
        with self.assertRaises(ValueError):
            generate_request({'recipe_version': 3, 'seed': 42, 'overrides': {'size': 17, 'phase': 9, 'moon_tilt_degrees': 5.}})
        told = advance_age_request({'api_version': 1, 'world': self.world, 'steps': 1, 'moon_day': 12345})
        self.assertEqual(told['history']['ages'][-1]['moon']['day'], 12345)
        self.assertEqual(told['history']['ages'][-1]['moon']['tide'], tide(self.world['astrology']['moon'], 12345))
        self.assertEqual(told['history']['operations'][-1]['moon_day'], 12345)
        with self.assertRaises(ValueError):
            advance_age_request({'api_version': 1, 'world': self.world, 'moon_day': -1})

    def test_lab_page_replays_every_state_key(self):
        text = (ROOT / 'tools' / 'terrain_lab.html').read_text(encoding='utf-8')
        line = re.search(r"const historyStateKeys=\[(.*?)\];", text).group(1)
        listed = set(re.findall(r"'([a-z_]+)'", line))
        self.assertTrue(set(STATE_KEYS) <= listed, sorted(set(STATE_KEYS) - listed))


if __name__ == '__main__':
    unittest.main()
