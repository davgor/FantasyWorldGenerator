"""The bounded read surface: five questions about a world that already exists.

Two halves, for the same reason `test_time_advance.py` has two. The pure half needs no
world at all -- block accounting, the grid arithmetic, and every refusal -- and runs in
milliseconds. The world half generates one size-17 seed-42 world, ticks it once so a
`quests` block exists, and then sweeps rather than samples: every id every read returns is
resolved back in the same world, because a join that is right for the first row and wrong
for the hundredth looks exactly like a join that works.

`FANTASY_WORLD_READ_BASE` points at a pre-generated world file so a developer iterating on
a read does not pay ninety seconds for it again. The default path generates, because a
test whose evidence depends on a file being present proves nothing on a machine that has
not got one.
"""

import copy
import json
import os
import pathlib
import sys
import time
import unittest

from icarus_sim import terrain_read_select as select
from icarus_sim.terrain_read import (MAX_NEAR_ROWS, MAX_PLACE_POSTS, MAX_QUEST_ROWS,
                                     NEAR_RADIUS_FRACTION, READ_API_VERSION, READS,
                                     blocks_request, near_request, person_request,
                                     place_request, quests_request)
from icarus_sim.terrain_errors import RequestError
from icarus_sim.terrain_erosion import sphere_grid
from icarus_sim.terrain_history import STATE_KEYS
from icarus_sim.terrain_liveness import liveness


def _bytes(value):
    return len(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'),
                          allow_nan=False).encode('utf-8'))


def _tiny_world():
    """The smallest thing shaped like a world. No generation, no layers, no joins."""
    return {'config': {'seed': 42, 'size': 17, 'phase': 16, 'world_recipe': 3},
            'effective_config': {'globe_radius': 31830.988618379066},
            'generator_version': 16,
            'terrain': {'version': 6},
            'settlements': {'version': 15, 'sites': []},
            'not_a_state_key': {'version': 3, 'a': 1}}


class BlockAccountingTests(unittest.TestCase):
    """`blocks` has no join, so this is the half that cannot be subtly wrong."""

    def test_every_top_level_key_appears_exactly_once(self):
        world = _tiny_world()
        document = blocks_request({'api_version': READ_API_VERSION, 'world': world})
        names = [row['name'] for row in document['blocks']]
        self.assertEqual(sorted(names), sorted(world))
        self.assertEqual(len(names), len(set(names)))

    def test_rows_are_sorted_by_name(self):
        document = blocks_request({'api_version': READ_API_VERSION, 'world': _tiny_world()})
        names = [row['name'] for row in document['blocks']]
        self.assertEqual(names, sorted(names))

    def test_registration_is_read_from_state_keys_not_restated(self):
        document = blocks_request({'api_version': READ_API_VERSION, 'world': _tiny_world()})
        by_name = {row['name']: row for row in document['blocks']}
        self.assertTrue(by_name['settlements']['registered'])
        self.assertTrue(by_name['terrain']['registered'])
        self.assertFalse(by_name['config']['registered'])
        self.assertFalse(by_name['not_a_state_key']['registered'])
        self.assertIn('not_a_state_key', document['unregistered'])
        self.assertNotIn('settlements', document['unregistered'])
        # Absent is the other direction: registered blocks this world does not carry.
        self.assertIn('quests', document['absent'])
        self.assertNotIn('terrain', document['absent'])
        self.assertEqual(set(document['absent']), set(STATE_KEYS) - set(_tiny_world()))

    def test_an_unregistered_block_is_reported_rather_than_dropped(self):
        """The `materialize_stage` failure mode, arriving at a new surface.

        A report built by walking `STATE_KEYS` would silently omit a block the world
        carries and nothing registered. Walking the world and marking membership is what
        makes the omission visible instead.
        """
        world = _tiny_world()
        world['invented_later'] = {'version': 1}
        document = blocks_request({'api_version': READ_API_VERSION, 'world': world})
        self.assertIn('invented_later', [row['name'] for row in document['blocks']])
        self.assertIn('invented_later', document['unregistered'])

    def test_bytes_are_the_canonical_encoding(self):
        world = _tiny_world()
        document = blocks_request({'api_version': READ_API_VERSION, 'world': world})
        for row in document['blocks']:
            self.assertEqual(row['bytes'], _bytes(world[row['name']]), row['name'])
        self.assertEqual(document['total_bytes'], sum(row['bytes'] for row in document['blocks']))

    def test_a_version_is_read_and_never_guessed(self):
        world = _tiny_world()
        world['no_version'] = {'a': 1}
        world['string_version'] = {'version': 'two'}
        world['listed'] = [1, 2, 3]
        document = blocks_request({'api_version': READ_API_VERSION, 'world': world})
        by_name = {row['name']: row for row in document['blocks']}
        self.assertEqual(by_name['settlements']['version'], 15)
        self.assertIsNone(by_name['no_version']['version'])
        self.assertIsNone(by_name['string_version']['version'])
        self.assertIsNone(by_name['listed']['version'])
        self.assertEqual(by_name['listed']['type'], 'array')
        self.assertEqual(by_name['listed']['count'], 3)

    def test_a_block_that_cannot_cross_is_named_rather_than_raising(self):
        """NaN is not JSON. A world carrying one still deserves an answer about which block."""
        world = _tiny_world()
        world['broken'] = {'value': float('nan')}
        document = blocks_request({'api_version': READ_API_VERSION, 'world': world})
        by_name = {row['name']: row for row in document['blocks']}
        self.assertFalse(by_name['broken']['encodable'])
        self.assertIsNone(by_name['broken']['bytes'])
        self.assertEqual(document['unencodable'], ['broken'])
        self.assertTrue(by_name['settlements']['encodable'])


class GeometryTests(unittest.TestCase):
    """The grid arithmetic, checked against the generator's own grid rather than restated."""

    def test_arc_distance_reproduces_the_generators_neighbour_distances(self):
        size, radius = 17, 31830.988618379066
        world = _tiny_world()
        points, _areas, neighbors = sphere_grid(size, radius)
        self.assertEqual(select.node_count(world), len(points))
        for node in (0, 1, 50, len(points) - 1):
            here = select.node_cell(world, node)
            for other, expected in neighbors[node]:
                there = select.node_cell(world, other)
                self.assertAlmostEqual(
                    select.arc_distance_m(radius, here['direction'], there['direction']),
                    expected, places=6, msg='node %d -> %d' % (node, other))

    def test_a_node_cell_is_the_generators_own_point(self):
        world = _tiny_world()
        points, _a, _n = sphere_grid(17, 31830.988618379066)
        for node in (0, 7, 100, len(points) - 1):
            cell = select.node_cell(world, node)
            self.assertEqual((cell['x'], cell['z']), points[node])


class RefusalTests(unittest.TestCase):
    """Every refusal carries the shared envelope. No read invents an error shape."""

    def _refused(self, call, body):
        with self.assertRaises(RequestError) as caught:
            call(body)
        document = caught.exception.document()
        self.assertEqual(document['schema'], 'fantasy-world-generator.failure')
        self.assertEqual(document['schema_version'], 2)
        return document

    def test_every_read_refuses_an_unknown_field_by_name(self):
        for name, call in READS.items():
            document = self._refused(call, {'api_version': READ_API_VERSION,
                                            'world': _tiny_world(), 'nod': 1})
            self.assertEqual(document['field'], 'nod', name)
            self.assertEqual(document['code'], 'INVALID_INPUT', name)

    def test_every_read_refuses_an_api_version_it_does_not_speak(self):
        for name, call in READS.items():
            document = self._refused(call, {'api_version': 99, 'world': _tiny_world()})
            self.assertEqual(document['code'], 'UNSUPPORTED_VERSION', name)
            self.assertFalse(document['retry'], name)

    def test_every_read_refuses_a_body_that_is_not_an_object(self):
        for name, call in READS.items():
            self._refused(call, ['world'])

    def test_a_near_read_refuses_a_node_off_the_grid(self):
        count = select.node_count(_tiny_world())
        document = self._refused(near_request, {'api_version': READ_API_VERSION,
                                                'world': _tiny_world(), 'node': count})
        self.assertEqual(document['field'], 'node')
        self.assertEqual(document['received'], count)
        self.assertEqual(document['expected'], {'refused_by': 'world state'})

    def test_a_near_read_refuses_a_radius_above_this_worlds_ceiling(self):
        world = _tiny_world()
        ceiling = world['effective_config']['globe_radius'] * NEAR_RADIUS_FRACTION
        document = self._refused(near_request, {'api_version': READ_API_VERSION, 'world': world,
                                                'node': 0, 'radius_m': ceiling * 2})
        self.assertEqual(document['field'], 'radius_m')
        self.assertEqual(document['expected'], {'refused_by': 'world state'})
        # And the ceiling itself is accepted, so the bound is a bound and not an off-by-one.
        near_request({'api_version': READ_API_VERSION, 'world': world, 'node': 0,
                      'radius_m': ceiling})

    def test_a_near_read_refuses_a_negative_radius(self):
        document = self._refused(near_request, {'api_version': READ_API_VERSION,
                                                'world': _tiny_world(), 'node': 0,
                                                'radius_m': -1.})
        self.assertEqual(document['field'], 'radius_m')
        self.assertEqual(document['code'], 'INVALID_INPUT')

    def test_a_near_read_refuses_a_node_or_radius_that_is_not_a_number(self):
        """NaN and Infinity are not JSON numbers a distance can be compared against, and a
        float node is not a node. Both are refused before any grid is touched."""
        for bad in ('5', 5.0, True, None):
            document = self._refused(near_request, {'api_version': READ_API_VERSION,
                                                    'world': _tiny_world(), 'node': bad})
            self.assertEqual(document['field'], 'node', repr(bad))
        for bad in (float('nan'), float('inf'), float('-inf'), '10', True):
            document = self._refused(near_request, {'api_version': READ_API_VERSION,
                                                    'world': _tiny_world(), 'node': 0,
                                                    'radius_m': bad})
            self.assertEqual(document['field'], 'radius_m', repr(bad))
        # A node is required, and its absence is named rather than defaulted to zero.
        document = self._refused(near_request, {'api_version': READ_API_VERSION,
                                                'world': _tiny_world()})
        self.assertEqual(document['field'], 'node')

    def test_a_world_missing_the_block_asked_for_is_missing_block_not_empty(self):
        """The distinction the card turns on: no quests block and an empty quest board."""
        world = _tiny_world()
        document = self._refused(quests_request, {'api_version': READ_API_VERSION, 'world': world})
        self.assertEqual(document['field'], 'world.quests')
        self.assertEqual(document['expected'], {'requires_block': 'quests'})
        self.assertFalse(document['retry'])
        # An empty board is an answer, not a refusal.
        world['quests'] = {'version': 1, 'quests': [], 'log': []}
        answered = quests_request({'api_version': READ_API_VERSION, 'world': world})
        self.assertEqual(answered['quests'], [])

    def test_place_and_person_refuse_a_world_carrying_nothing_to_look_in(self):
        bare = {'config': {'size': 17}, 'effective_config': {'globe_radius': 1000.}}
        document = self._refused(place_request, {'api_version': READ_API_VERSION,
                                                 'world': bare, 'place_id': 'x'})
        self.assertEqual(document['expected'], {'requires_block': 'settlements'})
        document = self._refused(person_request, {'api_version': READ_API_VERSION,
                                                  'world': bare, 'uid': 'x'})
        self.assertIn('requires_block', document['expected'])

    def test_an_unknown_id_names_what_exists(self):
        world = _tiny_world()
        world['settlements'] = {'version': 15, 'sites': [
            {'id': 0, 'uid': 'surface-city-0-100-human_heartland', 'node': 100, 'x': 4, 'z': 6,
             'kind': 'city', 'name': 'Froskor', 'population_profile': 'human_heartland'}]}
        document = self._refused(place_request, {'api_version': READ_API_VERSION,
                                                 'world': world, 'place_id': 'surface-city-0-100'})
        self.assertEqual(document['code'], 'INVALID_INPUT')
        self.assertEqual(document['field'], 'surface-city-0-100')
        self.assertIn('surface-city-0-100-human_heartland', document['suggestion'].get('candidates', []))

    def test_the_row_ceiling_refuses_rather_than_truncating_when_it_is_reached(self):
        """Driven here rather than on a generated world, because no generated world reaches it.

        Seed 42 at sizes 17 and 33 tops out at 314 rows inside the full radius ceiling, so
        a test that only asked a real world for a wide neighbourhood would pass while the
        branch it claims to cover never executed.
        """
        world = _tiny_world()
        world['beast_nests'] = {'version': 2, 'sites': [
            {'id': 'nest-%d' % i, 'species_id': 's', 'name': 'n', 'node': 5, 'x': 4, 'z': 1,
             'tier': 1, 'family': 'f', 'range_m': 1.}
            for i in range(MAX_NEAR_ROWS + 1)]}
        document = self._refused(near_request, {'api_version': READ_API_VERSION,
                                                'world': world, 'node': 5})
        self.assertEqual(document['code'], 'STATE_CAPACITY')
        self.assertEqual(document['field'], 'near.rows')
        self.assertEqual(document['received'], MAX_NEAR_ROWS + 1)
        self.assertEqual(document['expected']['max'], MAX_NEAR_ROWS)
        # One fewer is answered in full, so the bound is the bound and not an off-by-one.
        world['beast_nests']['sites'].pop()
        answered = near_request({'api_version': READ_API_VERSION, 'world': world, 'node': 5})
        self.assertEqual(answered['rows'], MAX_NEAR_ROWS)

    def test_quests_refuses_a_state_outside_the_vocabulary(self):
        world = _tiny_world()
        world['quests'] = {'version': 1, 'quests': [], 'log': []}
        document = self._refused(quests_request, {'api_version': READ_API_VERSION,
                                                  'world': world, 'states': ['opened']})
        self.assertEqual(document['field'], 'states')
        self.assertEqual(sorted(document['expected']['choices']), sorted(select.QUEST_STATES))


def _base_world():
    """One size-17 seed-42 world, generated once per process and then ticked once.

    Ticked because `quests` is written by the time capability and by nothing else, so a
    freshly generated world carries no quest board at all and the fifth read would have
    nothing to read.
    """
    if _base_world.cache is not None:
        return _base_world.cache
    cached = os.environ.get('FANTASY_WORLD_READ_BASE')
    if cached and pathlib.Path(cached).is_file():
        _base_world.cache = json.loads(pathlib.Path(cached).read_text(encoding='utf-8'))
        return _base_world.cache
    from icarus_sim.terrain_world import generate_request
    from icarus_sim.terrain_time import advance_time_request
    started = time.perf_counter()
    world = generate_request({'recipe_version': 3, 'seed': 42, 'overrides': {'size': 17}})
    world = advance_time_request({'api_version': 1, 'world': world, 'elapsed': {'days': 1}})
    world['_generation_seconds'] = round(time.perf_counter() - started, 1)
    _base_world.cache = world
    return world


_base_world.cache = None


class WorldReadTests(unittest.TestCase):
    """The half that needs a world. Sweeps, never samples."""

    @classmethod
    def setUpClass(cls):
        cls.world = _base_world()
        cls.body = {'api_version': READ_API_VERSION, 'world': cls.world}

    # --- the invariant every read shares -------------------------------------------

    def test_no_read_mutates_the_callers_world(self):
        before = json.dumps(self.world, sort_keys=True, allow_nan=False)
        node = self.world['settlements']['sites'][0]['node']
        uid = self.world['settlements']['sites'][0]['uid']
        person = (self.world['npcs']['people'][0])['uid']
        blocks_request(dict(self.body))
        near_request(dict(self.body, node=node, radius_m=5000.))
        place_request(dict(self.body, place_id=uid))
        person_request(dict(self.body, uid=person))
        quests_request(dict(self.body))
        self.assertEqual(before, json.dumps(self.world, sort_keys=True, allow_nan=False))

    def test_no_read_regenerates_the_world(self):
        """`patch_request` rebuilds the whole submitted world before it cuts a patch, which
        is why a patch costs what a generate costs. Nothing here may inherit that.

        Asserted by making generation itself fail. A cost measurement would only show that
        a read is fast today; this shows the code path is not reachable at all.
        """
        from icarus_sim import terrain_lab

        def refuse(*args, **kwargs):
            raise AssertionError('a read regenerated the world')

        original = terrain_lab.generate
        terrain_lab.generate = refuse
        try:
            blocks_request(dict(self.body))
            near_request(dict(self.body, node=self.world['settlements']['sites'][0]['node']))
            place_request(dict(self.body, place_id=self.world['settlements']['sites'][0]['uid']))
            person_request(dict(self.body, uid=self.world['npcs']['people'][0]['uid']))
            quests_request(dict(self.body))
        finally:
            terrain_lab.generate = original

    def _every_read(self, world):
        body = {'api_version': READ_API_VERSION, 'world': world}
        site = world['settlements']['sites'][0]
        return {
            'blocks': blocks_request(dict(body)),
            'near': near_request(dict(body, node=site['node'], radius_m=4000.)),
            'place': place_request(dict(body, place_id=site['uid'])),
            'person': person_request(dict(body, uid=world['npcs']['people'][0]['uid'])),
            'quests': quests_request(dict(body)),
        }

    def test_two_identical_reads_are_byte_identical(self):
        """Same world, same arguments, same bytes. A read that sorted by a dict's iteration
        order would pass on one process and differ on another."""
        first, second = self._every_read(self.world), self._every_read(self.world)
        for name in first:
            self.assertEqual(_bytes(first[name]), _bytes(second[name]), name)
            self.assertEqual(json.dumps(first[name], sort_keys=True, allow_nan=False),
                             json.dumps(second[name], sort_keys=True, allow_nan=False), name)

    def test_a_world_that_has_been_persisted_reads_the_same(self):
        """The document a real consumer holds: through JSON and back off disk.

        Every other test here reads an in-memory world. A game reads one it loaded, and the
        round trip turns tuples into lists and integer-like floats into floats.
        """
        persisted = json.loads(json.dumps(self.world, allow_nan=False))
        live, saved = self._every_read(self.world), self._every_read(persisted)
        for name in live:
            self.assertEqual(json.dumps(live[name], sort_keys=True, allow_nan=False),
                             json.dumps(saved[name], sort_keys=True, allow_nan=False), name)

    def test_no_read_mints_a_version_or_records_an_operation(self):
        operations = len(self.world['history'].get('operations') or [])
        for name, call in READS.items():
            body = dict(self.body)
            if name == 'near':
                body['node'] = 0
            if name == 'place':
                body['place_id'] = self.world['settlements']['sites'][0]['uid']
            if name == 'person':
                body['uid'] = self.world['npcs']['people'][0]['uid']
            document = call(body)
            self.assertNotIn('handle', document, name)
            self.assertNotIn('world', document, name)
            self.assertEqual(document['read'], name)
            self.assertEqual(document['schema'], 'fantasy-world-generator.read.' + name)
        self.assertEqual(len(self.world['history'].get('operations') or []), operations)

    # --- blocks ---------------------------------------------------------------------

    def test_blocks_names_every_top_level_key_a_real_world_carries(self):
        document = blocks_request(dict(self.body))
        self.assertEqual(sorted(row['name'] for row in document['blocks']),
                         sorted(self.world))
        for row in document['blocks']:
            self.assertEqual(row['registered'], row['name'] in STATE_KEYS, row['name'])

    def test_blocks_agrees_with_the_worlds_own_declared_versions(self):
        document = blocks_request(dict(self.body))
        for row in document['blocks']:
            value = self.world[row['name']]
            declared = value.get('version') if isinstance(value, dict) else None
            self.assertEqual(row['version'],
                             declared if isinstance(declared, int) and not isinstance(declared, bool)
                             else None, row['name'])

    # --- near ------------------------------------------------------------------------

    def test_near_at_a_city_node_finds_that_city(self):
        for site in self.world['settlements']['sites']:
            document = near_request(dict(self.body, node=site['node']))
            found = [row['uid'] for row in document['near']['settlements']]
            self.assertIn(site['uid'], found, 'node %s' % site['node'])
            for row in document['near']['settlements']:
                if row['uid'] == site['uid']:
                    self.assertEqual(row['distance_m'], 0.)
                    self.assertEqual(row['node'], site['node'])

    def test_near_encounters_resolve_through_the_index_the_writer_built(self):
        """`by_node` -> occupancy -> entry, exactly as `terrain_encounters` wrote it."""
        encounters = self.world['encounters']
        node = int(max(encounters['by_node'], key=lambda k: len(encounters['by_node'][k])))
        document = near_request(dict(self.body, node=node))
        rows = document['near']['encounters']
        self.assertEqual(len(rows), len(encounters['by_node'][str(node)]))
        for row, index in zip(rows, encounters['by_node'][str(node)]):
            occupancy = encounters['occupancy'][index]
            self.assertEqual(row['node'], occupancy['node'])
            self.assertEqual(row['camp_id'], occupancy['camp_id'])
            self.assertEqual(row['group_uid'], encounters['entries'][occupancy['entry']]['group_uid'])

    def test_every_id_near_returns_resolves_in_the_same_world(self):
        """Swept over every city node, not sampled at one.

        A join that is right for the first neighbourhood and wrong for the twelfth looks
        exactly like a join that works.
        """
        radius = self.world['effective_config']['globe_radius'] * NEAR_RADIUS_FRACTION / 4
        known = {
            'settlements': {s['uid'] for s in self.world['settlements']['sites']},
            'hamlets': {h['id'] for h in self.world['humans']['hamlets']},
            'fortresses': {f['id'] for f in self.world['humans']['fortresses']},
            'key_locations': {s['id'] for s in self.world['key_locations']['sites']},
            'beast_nests': {s['id'] for s in self.world['beast_nests']['sites']},
            'ley_nodes': {n['id'] for net in self.world['magic']['networks'].values()
                          for n in net['nodes']},
        }
        occupancy = self.world['encounters']['occupancy']
        total = 0
        for site in self.world['settlements']['sites']:
            document = near_request(dict(self.body, node=site['node'], radius_m=radius))
            near = document['near']
            self.assertEqual(set(near), set(select.NEAR_CATEGORIES))
            for category, ids in known.items():
                for row in near[category]:
                    total += 1
                    self.assertIn(row.get('uid') or row.get('id'), ids, category)
                    self.assertLessEqual(row['distance_m'], radius + 1e-6)
            for row in near['encounters']:
                total += 1
                self.assertEqual(occupancy[row['occupancy']]['camp_id'], row['camp_id'])
        self.assertGreater(total, 0, 'a quarter-ceiling radius around a city found nothing')

    def test_near_is_ordered_by_distance_then_by_the_writers_order(self):
        node = self.world['settlements']['sites'][0]['node']
        radius = self.world['effective_config']['globe_radius'] * NEAR_RADIUS_FRACTION / 2
        document = near_request(dict(self.body, node=node, radius_m=radius))
        for category, rows in document['near'].items():
            distances = [row['distance_m'] for row in rows]
            self.assertEqual(distances, sorted(distances), category)

    def test_a_radius_that_would_exceed_the_row_ceiling_is_refused_not_truncated(self):
        node = self.world['settlements']['sites'][0]['node']
        radius = self.world['effective_config']['globe_radius'] * NEAR_RADIUS_FRACTION
        try:
            document = near_request(dict(self.body, node=node, radius_m=radius))
        except RequestError as exc:
            envelope = exc.document()
            self.assertEqual(envelope['code'], 'STATE_CAPACITY')
            self.assertEqual(envelope['expected']['max'], MAX_NEAR_ROWS)
        else:
            self.assertLessEqual(sum(len(v) for v in document['near'].values()), MAX_NEAR_ROWS)

    # --- place -------------------------------------------------------------------------

    def test_every_place_id_in_the_world_resolves(self):
        for place_id, kind in select.place_ids(self.world):
            document = place_request(dict(self.body, place_id=place_id))
            self.assertEqual(document['anchor']['id'], place_id)
            self.assertEqual(document['anchor']['kind'], kind)
            self.assertIsInstance(document['anchor']['node'], int)

    def test_a_city_resolves_its_core_its_food_model_and_its_plan(self):
        for site in self.world['settlements']['sites']:
            document = place_request(dict(self.body, place_id=site['uid']))
            resolved = document['resolved']
            self.assertEqual(resolved['core']['site_id'], site['id'])
            self.assertEqual(resolved['seasonal_food_model']['site_id'], site['id'])
            self.assertEqual(resolved['plan']['id'], site['uid'])
            self.assertEqual(resolved['plan']['block'], 'city_plans')
            self.assertEqual(resolved['npc_site']['uid'], site['uid'])

    def test_city_posts_are_exactly_the_roster_rows_filed_under_that_site(self):
        for site in self.world['settlements']['sites']:
            document = place_request(dict(self.body, place_id=site['uid']))
            expected = [p for p in self.world['npcs']['people'] if p['site_uid'] == site['uid']]
            self.assertEqual(document['resolved']['post_count'], len(expected))
            returned = document['resolved']['npc_posts']
            self.assertEqual(len(returned), min(len(expected), MAX_PLACE_POSTS))
            self.assertEqual([r['uid'] for r in returned],
                             [p['uid'] for p in expected[:MAX_PLACE_POSTS]])

    def test_a_hamlet_joins_its_plan_by_the_field_the_planner_wrote(self):
        """`hamlet_plans.hamlets[].hamlet_id`, not the node and not the ordinal position.

        Both would agree on this world -- the plan list is a permutation of the hamlet
        list and both are one to one -- which is exactly why matching on the writer's own
        field is the only thing that stays right.
        """
        plans = {p['hamlet_id']: p for p in self.world['hamlet_plans']['hamlets']}
        for hamlet in self.world['humans']['hamlets']:
            document = place_request(dict(self.body, place_id=hamlet['id']))
            self.assertEqual(document['anchor']['kind'], 'hamlet')
            self.assertEqual(document['anchor']['node'], hamlet['node'])
            self.assertEqual(document['resolved']['plan']['id'], hamlet['id'])
            self.assertEqual(document['resolved']['plan']['status'], plans[hamlet['id']]['status'])
            self.assertEqual(document['resolved']['core_city']['uid'],
                             self.world['settlements']['sites'][hamlet['core_id']]['uid'])

    def test_a_site_plan_and_a_location_plan_never_share_a_key(self):
        """The two plan vocabularies are kept apart at this boundary, over every place.

        Swept, because the whole point is that exactly one of the two is ever filled: a
        place that answered under both keys would be a place a consumer could compare
        `complete` across.
        """
        site_tokens, location_tokens = set(), set()
        for place_id, kind in select.place_ids(self.world):
            resolved = place_request(dict(self.body, place_id=place_id))['resolved']
            filled = [k for k in ('plan', 'location_plan') if resolved[k] is not None]
            self.assertLessEqual(len(filled), 1, '%s filled %s' % (place_id, filled))
            if resolved['plan']:
                self.assertIn(resolved['plan']['block'],
                              ('city_plans', 'hamlet_plans', 'castle_plans'))
                self.assertNotEqual(kind, 'key_location')
                site_tokens.add(resolved['plan']['status'])
            if resolved['location_plan']:
                self.assertEqual(resolved['location_plan']['block'], 'key_location_plans')
                self.assertEqual(kind, 'key_location')
                location_tokens.add(resolved['location_plan']['status'])
        self.assertTrue(site_tokens and location_tokens, 'both kinds must appear to mean anything')
        self.assertLessEqual(site_tokens, {'complete', 'partial', 'unbuildable'})
        self.assertLessEqual(location_tokens, {'complete', 'empty'})

    def test_a_post_status_is_the_rosters_own_vocabulary(self):
        """`alive`/`dead`, carried verbatim and never translated into the hero words."""
        tokens = set()
        for site in self.world['settlements']['sites']:
            for post in place_request(dict(self.body, place_id=site['uid']))['resolved']['npc_posts']:
                tokens.add(post['status'])
        self.assertTrue(tokens)
        self.assertLessEqual(tokens, {'alive', 'dead'})

    def test_a_fortress_joins_its_castle_plan_by_fortress_id(self):
        plans = {p['fortress_id']: p for p in self.world['castle_plans']['castles']}
        for fort in self.world['humans']['fortresses']:
            document = place_request(dict(self.body, place_id=fort['id']))
            self.assertEqual(document['anchor']['kind'], 'fortress')
            self.assertEqual(document['resolved']['plan']['id'], fort['id'])
            self.assertEqual(document['resolved']['plan']['status'], plans[fort['id']]['status'])

    def test_a_key_location_joins_its_plan_by_location_id(self):
        """And answers under `location_plan`, never under `plan`.

        A key location plan's `status` is `complete | empty` -- has this plan contents -- and
        a site plan's is `complete | partial | unbuildable` -- was it fully placed. `complete`
        is in both and means two different things, which is the overload
        `board/backlog/SDET-STATUS-VOCABULARY.md` records. One key would republish it here.
        """
        plans = {p['location_id']: p for p in self.world['key_location_plans']['plans']}
        for location in self.world['key_locations']['sites']:
            document = place_request(dict(self.body, place_id=location['id']))
            self.assertEqual(document['anchor']['kind'], 'key_location')
            self.assertEqual(document['anchor']['node'], location['node'])
            self.assertIsNone(document['resolved']['plan'])
            self.assertEqual(document['resolved']['location_plan']['id'], location['id'])
            self.assertEqual(document['resolved']['location_plan']['block'], 'key_location_plans')
            self.assertEqual(document['resolved']['location_plan']['status'],
                             plans[location['id']]['status'])

    def test_an_ordinal_id_says_it_is_an_ordinal(self):
        """Hamlet, fortress and plot ids renumber at an age boundary. The read says so."""
        city = place_request(dict(self.body, place_id=self.world['settlements']['sites'][0]['uid']))
        self.assertTrue(city['anchor']['id_survives_an_age'])
        hamlet = place_request(dict(self.body, place_id=self.world['humans']['hamlets'][0]['id']))
        self.assertFalse(hamlet['anchor']['id_survives_an_age'])
        self.assertIn('node', hamlet['anchor'])
        fortress = place_request(dict(self.body, place_id=self.world['humans']['fortresses'][0]['id']))
        self.assertFalse(fortress['anchor']['id_survives_an_age'])

    def test_place_names_the_writing_site_of_every_join_it_resolves(self):
        document = place_request(dict(self.body,
                                      place_id=self.world['settlements']['sites'][0]['uid']))
        self.assertTrue(document['joins'])
        for join in document['joins']:
            self.assertTrue(join['writer'], join)
            self.assertIn('.py:', join['writer'], join)

    # --- person ---------------------------------------------------------------------

    def test_the_person_index_agrees_with_the_quest_givers_index(self):
        """Giver resolution must not be a second implementation of the writer's own."""
        from icarus_sim.terrain_time import _giver_index
        theirs = _giver_index(self.world)
        mine = select.person_index(self.world)
        for uid, (record, block) in theirs.items():
            self.assertIn(uid, mine)
            self.assertIs(mine[uid][0], record, uid)
            self.assertEqual(mine[uid][1], block, uid)

    def test_every_person_uid_resolves_and_reports_the_one_liveness(self):
        index = select.person_index(self.world)
        self.assertGreater(len(index), 100)
        for uid, (record, block) in index.items():
            document = person_request(dict(self.body, uid=uid))
            self.assertEqual(document['person']['uid'], uid)
            self.assertEqual(document['block'], block)
            self.assertEqual(document['liveness'], liveness(record, block))

    def test_a_person_carries_a_node_anchor_wherever_the_world_knows_one(self):
        for uid in [p['uid'] for p in self.world['npcs']['people'][:40]]:
            document = person_request(dict(self.body, uid=uid))
            self.assertIn('anchor', document)
            if document['anchor']['node'] is not None:
                self.assertIsInstance(document['anchor']['node'], int)

    def test_a_cast_presence_at_a_ruined_city_still_resolves_to_its_node(self):
        """An age advance moves a city record to `ruins`, keeping its uid and its node.

        The cast keeps naming the city it named before, so resolving a presence against
        `settlements.sites` alone leaves everyone standing in a dead city unplaced.
        `Sim/npc_roster/sites.py:194` handles the same case from the other side.
        """
        ruins = {ruin['uid']: ruin['node'] for ruin in self.world['ruins']
                 if ruin.get('uid') and ruin.get('node') is not None}
        self.assertTrue(ruins, 'this world has no ruins, so the branch is untested')
        seen = 0
        for uid, (record, block) in select.person_index(self.world).items():
            anchor = select.person_anchor(self.world, record, block)
            if anchor['source'] != 'ruins[].uid':
                continue
            seen += 1
            self.assertEqual(anchor['node'], ruins[anchor['uid']], uid)
        self.assertGreater(seen, 0, 'nobody in this world stands at a ruin')
        # A standing city wins over a ruin carrying the same uid, so a rebuilt name never
        # resolves to the grave of the town it replaced.
        forged = copy.deepcopy(self.world)
        site = forged['settlements']['sites'][0]
        forged['ruins'].append({'uid': site['uid'], 'node': site['node'] + 1, 'id': 'ruin-x'})
        self.assertEqual(select._settlement_nodes(forged)[site['uid']], site['node'])

    def test_a_villain_is_a_person_too(self):
        for villain in self.world['villains']['people']:
            document = person_request(dict(self.body, uid=villain['uid']))
            self.assertEqual(document['block'], 'villains')
            self.assertEqual(document['liveness'], liveness(villain, 'villains'))
            self.assertEqual(document['anchor']['node'], villain['node'])

    def test_a_block_is_never_answered_as_a_person(self):
        with self.assertRaises(RequestError):
            person_request(dict(self.body, uid='npcs'))

    # --- quests ----------------------------------------------------------------------

    def test_quests_returns_the_board_the_time_capability_wrote(self):
        document = quests_request(dict(self.body))
        board = self.world['quests']['quests']
        self.assertEqual([q['quest_id'] for q in document['quests']],
                         [q['quest_id'] for q in board])
        self.assertEqual(document['counts']['total'], len(board))

    def test_every_quest_giver_and_anchor_resolves(self):
        document = quests_request(dict(self.body))
        self.assertGreater(len(document['quests']), 0)
        index = select.person_index(self.world)
        for quest in document['quests']:
            self.assertIn(quest['giver_uid'], index)
            self.assertEqual(quest['giver']['uid'], quest['giver_uid'])
            self.assertEqual(quest['giver']['block'], index[quest['giver_uid']][1])
            self.assertIn('anchor', quest)

    def test_a_state_filter_selects_and_never_invents(self):
        everything = quests_request(dict(self.body))
        offered = quests_request(dict(self.body, states=['offered']))
        self.assertEqual([q['quest_id'] for q in offered['quests']],
                         [q['quest_id'] for q in everything['quests'] if q['state'] == 'offered'])
        none = quests_request(dict(self.body, states=[]))
        self.assertEqual(none['quests'], [])

    # --- the published contract --------------------------------------------------------

    def test_every_read_document_validates_against_its_published_schema(self):
        """The card's open question, answered: the read documents are schema'd, not the blocks.

        Seven of the 49 blocks in `STATE_KEYS` have a schema file of their own and the
        rest reach `world-output.schema.json` as a declared property; waiting for
        `PRODUCT-BLOCK-REGISTRY` would block five reads on forty-two. So each read declares
        its own document at its own boundary, and the block rows it carries through are
        typed as objects rather than described a second time.

        `tests/schema_subset.py` is the repository's own standard-library validator for the
        subset `Contracts/schemas/*.json` uses. It raises on an unsupported keyword rather
        than passing silently, so a schema it has never inspected cannot slip through.
        """
        root = pathlib.Path(__file__).resolve().parents[2]
        if str(root / 'tests') not in sys.path:
            sys.path.insert(0, str(root / 'tests'))
        import schema_subset

        node = self.world['settlements']['sites'][0]['node']
        documents = {
            'blocks': blocks_request(dict(self.body)),
            'near': near_request(dict(self.body, node=node, radius_m=4000.)),
            'place': place_request(dict(self.body,
                                        place_id=self.world['settlements']['sites'][0]['uid'])),
            'person': person_request(dict(self.body, uid=self.world['npcs']['people'][0]['uid'])),
            'quests': quests_request(dict(self.body)),
        }
        for name, document in documents.items():
            path = root / 'Contracts' / 'schemas' / ('read-%s.schema.json' % name)
            self.assertTrue(path.is_file(), path)
            schema = json.loads(path.read_text(encoding='utf-8'))
            self.assertEqual(list(schema_subset.errors(document, schema)), [], name)
        # And the other three place kinds, which take different branches of `resolved`.
        place_schema = json.loads((root / 'Contracts' / 'schemas'
                                   / 'read-place.schema.json').read_text(encoding='utf-8'))
        for place_id in (self.world['humans']['hamlets'][0]['id'],
                         self.world['humans']['fortresses'][0]['id'],
                         self.world['key_locations']['sites'][0]['id']):
            document = place_request(dict(self.body, place_id=place_id))
            self.assertEqual(list(schema_subset.errors(document, place_schema)), [], place_id)

    # --- the ceiling and the cost -----------------------------------------------------

    def test_every_read_answers_within_its_stated_byte_ceiling(self):
        ceilings = {}
        node = self.world['settlements']['sites'][0]['node']
        radius = self.world['effective_config']['globe_radius'] * NEAR_RADIUS_FRACTION / 4
        ceilings['blocks'] = _bytes(blocks_request(dict(self.body)))
        ceilings['near'] = _bytes(near_request(dict(self.body, node=node, radius_m=radius)))
        ceilings['place'] = max(
            _bytes(place_request(dict(self.body, place_id=s['uid'])))
            for s in self.world['settlements']['sites'])
        ceilings['person'] = max(
            _bytes(person_request(dict(self.body, uid=uid)))
            for uid in list(select.person_index(self.world))[:200])
        ceilings['quests'] = _bytes(quests_request(dict(self.body)))
        for name, size in ceilings.items():
            self.assertLess(size, 512 * 1024, '%s answered %d bytes' % (name, size))
        print('\nread byte sizes (seed 42, size 17): '
              + ', '.join('%s=%d' % kv for kv in sorted(ceilings.items())))

    def test_the_quest_row_ceiling_is_a_number_and_not_a_word(self):
        self.assertIsInstance(MAX_QUEST_ROWS, int)
        self.assertIsInstance(MAX_NEAR_ROWS, int)
        self.assertIsInstance(MAX_PLACE_POSTS, int)
        document = quests_request(dict(self.body))
        self.assertLessEqual(len(document['quests']), MAX_QUEST_ROWS)


if __name__ == '__main__':
    unittest.main()
