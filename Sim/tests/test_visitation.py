"""A summoned god is highly disruptive, deterministic, bounded, and leaves a footprint when it departs.

Until terrain_history wires astrology and religion into the pipeline, the fixture applies
them to a generated world by hand; the API itself is exercised end to end.
"""
import copy
import json
import unittest

from icarus_sim.terrain_world import generate_request
from icarus_sim.terrain_lab import Config
from icarus_sim.terrain_astrology import add_astrology
from icarus_sim.terrain_religion import add_religion
from icarus_sim.terrain_visitation import visitation_request, reach_m, MAX_VISITATIONS
from icarus_sim.terrain_leyline_history import SCHOOLS


class VisitationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.world = generate_request({'recipe_version': 3, 'seed': 42, 'overrides': {'size': 17, 'phase': 13}})
        cls.cfg = Config(**cls.world['config'])
        add_astrology(cls.world, cls.cfg)
        add_religion(cls.world, cls.cfg)
        cls.city = cls.world['settlements']['sites'][0]
        cls.god = next(g for g in cls.world['religion']['gods'] if g['family'] == 'school' and g['status'] == 'manifest')
        cls.school = cls.god['schools'][0]

    def summon(self, **extra):
        body = {'api_version': 1, 'world': self.world, 'god_id': self.god['id'], 'target': {'city_uid': self.city['uid']}, 'wrath': 1.}
        body.update(extra)
        return visitation_request(body)

    def test_same_request_same_world_and_input_untouched(self):
        before = copy.deepcopy(self.world)
        a = self.summon(); b = self.summon()
        self.assertEqual(self.world, before)
        for key in ('layers', 'magic', 'ruins', 'settlements', 'religion', 'beast_nests', 'threat_assessments'):
            self.assertEqual(a[key], b[key], key)
        json.dumps(a, allow_nan=False)

    def test_the_avatar_saturates_its_school_and_the_god_walks(self):
        after = self.summon()
        x, z, node = self.city['x'], self.city['z'], self.city['node']
        self.assertEqual(after['layers']['dominant_magic'][z][x], list(SCHOOLS).index(self.school))
        self.assertGreaterEqual(after['layers']['biome_variant'][z][x], 0)
        ids = {n['id'] for n in after['magic']['networks'][self.school]['nodes']}
        record = after['religion']['visitations'][0]
        self.assertTrue(set(record['cluster']) <= ids | {n['id'] for s in record['schools'] for n in after['magic']['networks'][s]['nodes']})
        self.assertEqual(len(record['cluster']), 5 * len(record['schools']))
        self.assertEqual((record['god_id'], record['node'], record['wrath'], record['departed_age']), (self.god['id'], node, 1., None))
        self.assertEqual(record['reach_m'], reach_m(self.world, self.cfg))
        self.assertEqual(record['day'], int(self.world['settlements']['founding']['end_year']) * 360)
        god = next(g for g in after['religion']['gods'] if g['id'] == self.god['id'])
        self.assertEqual(god['status'], 'walking')
        self.assertEqual(god['avatar']['node'], node)
        self.assertTrue(any(s['kind'] == 'theophany' and s['node'] == node for s in after['religion']['sites']))
        self.assertEqual(after['history']['operations'][-1]['kind'], 'visitation')
        self.assertEqual(after['build_stages'][-1]['kind'], 'visitation')
        self.assertIn('religion', after['build_stages'][-1]['state'])
        for ruin in after['ruins']:
            if ruin.get('visitation') == 0:
                self.assertIn(ruin['id'] + '-key', {n['id'] for n in after['magic']['networks'][ruin['legacy']['school']]['nodes']})
                self.assertEqual(ruin['destroyed_age'], len(self.world['history']['ages']))
        for nest in after['beast_nests']['sites']:
            self.assertNotIn(nest['id'], record['purged_nests'])
        # Opposed intensities within reach are weakened and recorded for restoration.
        for item in record['restore']:
            net = after['magic']['networks'][item['school']]
            pool = net['nodes'] if 'node_id' in item else net['edges']
            current = next(v for v in pool if v['id'] == item.get('node_id', item.get('line_id')))
            self.assertAlmostEqual(current['intensity'], item['intensity'] * .5)
        # Every city within reach that survived and did not already follow the god converted.
        for civilization in record['converted']:
            self.assertEqual(after['religion']['faiths'][civilization]['patron'], self.god['id'])

    def test_departure_leaves_a_footprint_and_restores_rivals(self):
        walking = self.summon()
        gone = visitation_request({'api_version': 1, 'world': walking, 'god_id': self.god['id'], 'depart': True})
        record = gone['religion']['visitations'][0]
        ids = {n['id'] for s in SCHOOLS for n in gone['magic']['networks'][s]['nodes']}
        self.assertFalse(set(record['cluster']) & ids)
        footprint = next(n for n in gone['magic']['networks'][self.school]['nodes'] if n['id'].startswith('footprint-'))
        self.assertEqual(footprint['intensity'], 3.5)
        self.assertEqual(record['departed_age'], len(self.world['history']['ages']))
        for item in record['restore']:
            net = gone['magic']['networks'][item['school']]
            pool = net['nodes'] if 'node_id' in item else net['edges']
            self.assertEqual(next(v for v in pool if v['id'] == item.get('node_id', item.get('line_id')))['intensity'], item['intensity'])
        god = next(g for g in gone['religion']['gods'] if g['id'] == self.god['id'])
        self.assertEqual(god['status'], 'manifest')
        self.assertNotIn('avatar', god)
        self.assertTrue(any(s['kind'] == 'pilgrimage' for s in gone['religion']['sites']))
        self.assertEqual(gone['build_stages'][-1]['kind'], 'departure')
        # Conversions outlast the god's presence.
        for civilization in record['converted']:
            self.assertEqual(gone['religion']['faiths'][civilization]['patron'], self.god['id'])
        with self.assertRaises(ValueError):
            visitation_request({'api_version': 1, 'world': gone, 'god_id': self.god['id'], 'depart': True})

    def test_wrathless_sovereign_visit_ruins_nothing(self):
        world = copy.deepcopy(self.world)
        god = next(g for g in world['religion']['gods'] if g['id'] == self.god['id'])
        god['aspect'] = 'sovereign'
        before = len(world['ruins'])
        after = visitation_request({'api_version': 1, 'world': world, 'god_id': self.god['id'],
                                    'target': {'city_uid': self.city['uid']}, 'wrath': 0.})
        divine = [r for r in after['ruins'][before:] if r['cause'].startswith('divine')]
        self.assertEqual(divine, [])

    def test_the_orchestrator_can_name_the_day(self):
        told = self.summon(day=777)
        record = told['religion']['visitations'][0]
        self.assertEqual(record['day'], 777)
        self.assertEqual(record['moon']['day'], 777)
        with self.assertRaises(ValueError):
            self.summon(day=-1)
        with self.assertRaises(ValueError):
            self.summon(day=1.5)

    def test_invalid_requests_are_rejected(self):
        absent = next(g['id'] for g in self.world['religion']['gods'] if g['status'] == 'absent')
        water_node = next(i for i, (x, z) in enumerate(self.world['water']['nodes']) if self.world['layers']['water_type'][z][x] != 0)
        walking = self.summon()
        bad = [
            {'api_version': 2, 'world': self.world, 'god_id': self.god['id'], 'target': {'node': self.city['node']}},
            {'api_version': 1, 'world': self.world, 'god_id': absent, 'target': {'node': self.city['node']}},
            {'api_version': 1, 'world': self.world, 'god_id': 'god_nobody', 'target': {'node': self.city['node']}},
            {'api_version': 1, 'world': self.world, 'god_id': self.god['id'], 'target': {'node': water_node}},
            {'api_version': 1, 'world': self.world, 'god_id': self.god['id'], 'target': {'node': self.city['node']}, 'wrath': 2},
            {'api_version': 1, 'world': self.world, 'god_id': self.god['id'], 'target': {'city_uid': 'nope'}},
            {'api_version': 1, 'world': self.world, 'god_id': self.god['id'], 'target': {'node': 1, 'city_uid': 'x'}},
            {'api_version': 1, 'world': self.world, 'god_id': self.god['id'], 'depart': True},
            {'api_version': 1, 'world': walking, 'god_id': self.god['id'], 'target': {'node': self.city['node']}},
            {'api_version': 1, 'world': self.world, 'god_id': self.god['id'], 'target': {'node': self.city['node']}, 'variation': -1},
        ]
        for body in bad:
            with self.subTest(body={k: v for k, v in body.items() if k != 'world'}):
                with self.assertRaises(ValueError):
                    visitation_request(body)
        stripped = copy.deepcopy(self.world)
        stripped['religion']['visitations'] = [{'departed_age': 0}] * MAX_VISITATIONS
        with self.assertRaises(ValueError):
            visitation_request({'api_version': 1, 'world': stripped, 'god_id': self.god['id'], 'target': {'node': self.city['node']}})
        stripped = copy.deepcopy(self.world)
        stripped['religion']['catalogue']['sha256'] = '0' * 64
        with self.assertRaises(ValueError):
            visitation_request({'api_version': 1, 'world': stripped, 'god_id': self.god['id'], 'target': {'node': self.city['node']}})


if __name__ == '__main__':
    unittest.main()
