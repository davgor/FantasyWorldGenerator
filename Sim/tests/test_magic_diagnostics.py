"""`magic.diagnostics`: why the colleges that did not place did not place.

The `magic` block published `colleges: []` against `effective_config.college_count: 2` and
said nothing else, so a consumer could not tell "this world has no ground a college can
stand on" from "colleges are not implemented" from "colleges placed and something moved
them". `key_locations` already publishes that distinction per archetype and `heroes`
publishes it per role; this is the same row in the block that owns the institutions.

Every world here is synthetic. `add_colleges` reads layers, settlements, humans and a
sphere grid and nothing else, so a nine-cell globe with flat layers exercises the whole
pass in milliseconds and lets the two zeros be produced deliberately rather than hunted
for in a generated world.
"""
import math
import unittest
from dataclasses import replace

from icarus_sim.terrain_erosion import sphere_grid
from icarus_sim.terrain_lab import Config
from icarus_sim.terrain_magic import (COLLEGE_LIMITS, SOURCE_KIND, add_colleges,
                                      college_eligible, college_refusal,
                                      pending_college_diagnostics)

N = 9
ROW_KEYS = {'institution', 'placed', 'wanted', 'candidates', 'sources', 'source_kind', 'reason'}


def grid(value):
    return [[value for _ in range(N)] for _ in range(N)]


def world(radius=10000., cities=1, **layer_overrides):
    """A globe whose every cell is perfect college ground, unless a layer is overridden."""
    points, _, _ = sphere_grid(N, radius)
    layers = {'magic_density': grid(.9), 'magic_hazard': grid(.05), 'slope': grid(1.),
              'temperature': grid(20.), 'freshwater_distance': grid(50.), 'flood_risk': grid(.1),
              'suitability': grid(.9), 'water_type': grid(0), 'height': grid(100.),
              'rain_river': grid(0)}
    layers.update(layer_overrides)
    sites = [{'id': 0, 'node': points.index((3, 4)), 'x': 3, 'z': 4,
              'population_profile': 'human_heartland'}][:cities]
    return {'effective_config': {'globe_radius': radius}, 'layers': layers,
            'settlements': {'sites': sites},
            'humans': {'hamlets': [], 'fortresses': [], 'cores': [{'culture_id': 'culture-1'}]},
            'magic': {'colleges': []}, 'timing_ms': {'total': 0.}, 'warnings': []}


def seated(cfg, **kwargs):
    result = world(**kwargs)
    add_colleges(result, cfg)
    return result['magic']


class MagicDiagnosticsTests(unittest.TestCase):
    cfg = Config(size=N, support_reach=60000., college_count=2)

    def row(self, magic):
        self.assertIsInstance(magic['diagnostics'], list)
        self.assertEqual(len(magic['diagnostics']), 1, 'one row per institution')
        row = magic['diagnostics'][0]
        self.assertEqual(set(row), ROW_KEYS)
        self.assertEqual(row['institution'], 'wizard_college')
        self.assertEqual(row['source_kind'], SOURCE_KIND)
        return row

    def test_every_finished_magic_block_carries_a_row_per_institution(self):
        row = self.row(seated(self.cfg))
        self.assertEqual(row['wanted'], 2)

    def test_a_seated_college_is_reported_as_seated(self):
        magic = seated(self.cfg)
        row = self.row(magic)
        self.assertEqual(row['placed'], 2)
        self.assertEqual(row['placed'], len(magic['colleges']))
        self.assertGreaterEqual(row['candidates'], row['placed'])
        self.assertIn('2', row['reason'])

    def test_the_counts_agree_with_the_colleges_and_with_each_other(self):
        for kwargs in ({}, {'suitability': grid(.1)}, {'radius': 40.}, {'cities': 0}):
            with self.subTest(**{k: 'overridden' for k in kwargs}):
                magic = seated(self.cfg, **kwargs)
                row = self.row(magic)
                self.assertEqual(row['placed'], len(magic['colleges']))
                self.assertGreaterEqual(row['candidates'], row['placed'])
                self.assertGreaterEqual(row['sources'], row['candidates'])

    def test_no_ground_and_no_room_do_not_read_alike(self):
        """The two zeros this card exists for, produced deliberately and side by side."""
        # Nothing qualifies: every cell is within reach and every one fails a limit.
        barren = self.row(seated(self.cfg, suitability=grid(.1)))
        # Everything qualifies and nothing fits: on a 40 m globe the whole surface lies
        # inside the 150 m clearance every settlement keeps around itself.
        crowded = self.row(seated(self.cfg, radius=40.))
        self.assertEqual((barren['placed'], crowded['placed']), (0, 0))
        self.assertEqual(barren['candidates'], 0)
        self.assertGreater(crowded['candidates'], 0)
        self.assertNotEqual(barren['reason'], crowded['reason'])
        self.assertIn('suitability', barren['reason'])
        self.assertIn('clearance', crowded['reason'])

    def test_a_world_with_nothing_within_reach_says_that_and_not_that_it_lost(self):
        row = self.row(seated(self.cfg, cities=0))
        self.assertEqual((row['placed'], row['candidates'], row['sources']), (0, 0, 0))
        self.assertIn(SOURCE_KIND, row['reason'])

    def test_asking_for_no_colleges_is_not_a_shortfall(self):
        row = self.row(seated(replace(self.cfg, college_count=0)))
        self.assertEqual((row['placed'], row['wanted']), (0, 0))
        self.assertIn('requested', row['reason'])

    def test_candidates_are_counted_past_the_budget_so_placed_is_not_the_ceiling(self):
        """`candidates` counts every cell that qualified, not the few the budget consumed."""
        row = self.row(seated(replace(self.cfg, college_count=1)))
        self.assertEqual(row['placed'], 1)
        self.assertGreater(row['candidates'], 1)

    def test_a_block_whose_college_pass_has_not_run_says_so_rather_than_nothing(self):
        from icarus_sim.terrain_leyline_history import generate_networks
        result = world()
        result['climate'] = True
        generate_networks(result, self.cfg)
        row = self.row(result['magic'])
        self.assertEqual(result['magic']['colleges'], [])
        self.assertEqual((row['placed'], row['candidates'], row['sources']), (0, 0, 0))
        self.assertEqual(row['wanted'], 2)
        self.assertIn('not run', row['reason'])
        self.assertEqual(result['magic']['diagnostics'],
                         pending_college_diagnostics(self.cfg.college_count))

    def test_the_gate_and_the_diagnostic_have_one_definition(self):
        """`college_eligible` is `college_refusal` read as a boolean, so they cannot drift.

        A second copy of the predicate written for the report is the failure mode the
        hero half named: the report and the gate disagree and the report is believed.
        """
        good = dict(density=.8, hazard=.1, limit=.4, slope=4, temp=20, fresh=100, flood=.1,
                    suitability=.8, water=0)
        self.assertIsNone(college_refusal(**good))
        self.assertTrue(college_eligible(**good))
        refused = {'density': {'density': .1}, 'hazard': {'hazard': .5}, 'water': {'water': 2},
                   'slope': {'slope': 25}, 'temperature': {'temp': 60},
                   'freshwater': {'fresh': -1}, 'flood': {'flood': .9},
                   'suitability': {'suitability': .2}}
        self.assertEqual(set(refused), set(COLLEGE_LIMITS))
        for name, change in refused.items():
            with self.subTest(limit=name):
                args = dict(good, **change)
                self.assertEqual(college_refusal(**args), name)
                self.assertFalse(college_eligible(**args))

    def test_placement_is_unchanged_by_the_diagnostic(self):
        """The report reads the pass; it must not move a single college.

        Pinned against the gate itself rather than against a recorded list, so it fails if
        a seated college ever stands on ground its own limits refuse.
        """
        magic = seated(self.cfg)
        layers = world()['layers']
        self.assertEqual([c['id'] for c in magic['colleges']], ['college-1', 'college-2'])
        for college in magic['colleges']:
            x, z = college['x'], college['z']
            self.assertTrue(college_eligible(
                layers['magic_density'][z][x], layers['magic_hazard'][z][x], self.cfg.human_magic_limit,
                layers['slope'][z][x], layers['temperature'][z][x], layers['freshwater_distance'][z][x],
                layers['flood_risk'][z][x], layers['suitability'][z][x], layers['water_type'][z][x]))
        self.assertEqual(math.isclose(magic['college_spacing_m'], 150.), True)


if __name__ == '__main__':
    unittest.main()
