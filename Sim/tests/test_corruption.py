"""Corruption: the only path by which a hidden school ever gets a node."""
import copy
import unittest

from icarus_sim import terrain_corruption as corruption
from icarus_sim.terrain_religion import hidden_catalogue
from icarus_sim.terrain_world import generate_request


def villain_world():
    return generate_request({'seed': 42, 'recipe_version': 3,
                             'overrides': {'size': 17, 'villain_rise': 1.0}})


def without_timings(world):
    out = {k: v for k, v in world.items() if k != 'timing_ms'}
    return out


class GateTests(unittest.TestCase):
    def test_below_the_noticing_point_the_chance_is_exactly_zero(self):
        """Zero, not merely small: an early playthrough is guaranteed clean."""
        for god in hidden_catalogue()['gods']:
            for encounters in range(0, god['noticing']):
                self.assertEqual(corruption.chance(god, encounters), 0.,
                                 f"{god['id']} must not act at {encounters} encounters")

    def test_the_chance_climbs_to_certain(self):
        for god in hidden_catalogue()['gods']:
            self.assertEqual(corruption.chance(god, god['climb']), 1.)
            self.assertGreater(corruption.chance(god, god['climb']), corruption.chance(god, god['noticing'] + 1))

    def test_the_four_are_staggered_so_they_arrive_across_playthroughs(self):
        points = sorted(g['noticing'] for g in hidden_catalogue()['gods'])
        self.assertEqual(len(set(points)), 4, 'each god needs its own noticing point')
        self.assertGreater(points[-1], points[0] * 2, 'the last should be far behind the first')


class QuietTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.world = villain_world()

    def test_nobody_is_watching_at_zero(self):
        out = corruption.corruption_request({'api_version': 1, 'world': self.world, 'encounters': 0})
        self.assertFalse(out['corruption']['acted'])
        self.assertEqual(out['corruption']['watching'], [])
        self.assertEqual(out['religion'].get('corruptions', []), [])

    def test_the_caller_world_is_never_touched(self):
        before = copy.deepcopy(self.world)
        corruption.corruption_request({'api_version': 1, 'world': self.world, 'encounters': 40})
        self.assertEqual(self.world, before)

    def test_a_world_without_a_villain_is_refused(self):
        # The fixture must ASK for a villainless world now. A default world ends with
        # super villains promoted into it, so `{'size': 17}` stopped being one.
        plain = generate_request({'seed': 42, 'recipe_version': 3,
                                  'overrides': {'size': 17, 'villain_rise': 0.}})
        with self.assertRaises(ValueError):
            corruption.corruption_request({'api_version': 1, 'world': plain, 'encounters': 999})

    def test_malformed_requests_are_refused(self):
        for body in ({'api_version': 2, 'world': self.world},
                     {'api_version': 1, 'world': self.world, 'encounters': -1},
                     {'api_version': 1, 'world': self.world, 'encounters': True},
                     {'api_version': 1, 'world': self.world, 'nonsense': 1},
                     {'api_version': 1, 'world': self.world, 'villain_uid': 'nobody'}):
            with self.assertRaises(ValueError):
                corruption.corruption_request(body)


class CorruptedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.world = villain_world()
        cls.out = corruption.corruption_request({'api_version': 1, 'world': cls.world, 'encounters': 40})
        cls.record = cls.out['religion']['corruptions'][-1]

    def test_a_god_took_a_villain(self):
        self.assertTrue(self.out['corruption']['acted'])
        host = next(p for p in self.out['villains']['people'] if p['uid'] == self.record['villain_uid'])
        self.assertEqual(host['god'], self.record['god_id'])
        self.assertTrue(host['corrupted'])
        self.assertEqual(host['school'], self.record['school'])

    def test_the_nodes_are_what_persists(self):
        school = self.record['school']
        ids = {n['id'] for n in self.out['magic']['networks'][school]['nodes']}
        self.assertTrue(set(self.record['nodes']) <= ids)
        host = next(p for p in self.out['villains']['people'] if p['uid'] == self.record['villain_uid'])
        self.assertTrue(set(self.record['nodes']) <= set(host['held_nodes']))

    def test_the_hidden_field_is_live_and_the_ground_mutates(self):
        """Generation can never do this; only this API can."""
        field = self.out['layers']['ley_' + self.record['school']]
        self.assertGreater(max(v for row in field for v in row), 0.)
        catalogue = self.out['terrain']['magical_biomes']
        corrupted = {catalogue[v]['magic_school'] for row in self.out['layers']['biome_variant']
                     for v in row if v >= 104}
        self.assertIn(self.record['school'], corrupted,
                      'corrupted ground must actually wear the hidden school')

    def test_the_known_gods_stop_not_speaking_of_it(self):
        revealed = next(g for g in self.out['religion']['gods'] if g['id'] == self.record['god_id'])
        self.assertEqual(revealed['status'], 'walking')
        self.assertEqual(revealed['aspect'], 'wild')
        roused = [g for g in self.out['religion']['gods'] if g.get('roused_by')]
        self.assertTrue(roused, 'its rivals in the known pantheon should be roused')
        from icarus_sim.terrain_religion import gods_by_id
        for god in roused:
            self.assertIn(self.record['god_id'], god['roused_by'])
            # A god with no Wild face keeps the one it has; a civic god has only the one.
            if gods_by_id()[god['id']].get('aspects', {}).get('wild'):
                self.assertEqual(god['aspect'], 'wild')

    def test_a_villain_sworn_to_an_old_god_is_still_taken(self):
        """Being bound to a school god must not make a villain ineligible.

        Sinking a leyline well binds a villain to its school's god, so excluding anyone
        with a `god` made every seated villain un-corruptible the moment wells shipped.
        A hidden god reaching for someone already sworn elsewhere is the whole shape of
        the story this is modelling.
        """
        host = next(p for p in self.world['villains']['people']
                    if p['uid'] == self.record['villain_uid'])
        self.assertTrue(host.get('god'), 'the seated villain was already sworn to a god')
        self.assertFalse(host.get('corrupted'), 'and had not been taken before this')
        taken = next(p for p in self.out['villains']['people'] if p['uid'] == host['uid'])
        self.assertTrue(taken['corrupted'])
        self.assertNotEqual(taken['god'], host['god'], 'the hidden god replaced the old one')

    def test_the_reach_is_the_villains_own(self):
        host = next(p for p in self.world['villains']['people'] if p['uid'] == self.record['villain_uid'])
        self.assertGreaterEqual(self.record['reach_m'], host['reach_m'] - 1e-6)

    def test_same_request_same_world(self):
        again = corruption.corruption_request({'api_version': 1, 'world': self.world, 'encounters': 40})
        self.assertEqual(without_timings(again), without_timings(self.out))

    def test_the_ledger_is_recorded_in_both_places(self):
        """Or history.replay is a lie and the world cannot be replayed from its own record."""
        self.assertEqual(self.record['encounters'], 40)
        operation = self.out['history']['operations'][-1]
        self.assertEqual(operation['kind'], 'corruption')
        self.assertEqual(operation['encounters'], 40)
        self.assertEqual(operation['variation'], self.record['variation'])


class FailureModeTests(unittest.TestCase):
    """The four do different things to a city, which is why they play differently."""

    @classmethod
    def setUpClass(cls):
        cls.world = villain_world()

    def mode(self, school):
        world = copy.deepcopy(self.world)
        host = world['villains']['people'][0]
        god = {'id': 'test', 'name': 'Test', 'school': school, 'smite': 'x'}
        return corruption._failure_mode(world, god, host, host['reach_m'], 3)

    def test_blood_farms_a_city_that_still_stands(self):
        survivors, touched, ruined = self.mode('blood')
        self.assertFalse(ruined, 'blood does not end a city')
        self.assertTrue(touched)
        self.assertTrue(all(t['effect'] == 'farmed' and t['people_lost'] > 0 for t in touched))

    def test_eldritch_takes_a_city_and_changes_nothing_visible(self):
        survivors, touched, ruined = self.mode('eldritch')
        self.assertFalse(ruined)
        self.assertTrue(all(t['effect'] == 'taken' for t in touched))
        taken = [c for c in survivors if c.get(corruption.TAKEN_KEY)]
        self.assertTrue(taken)
        for city in taken:
            self.assertGreater(city['population_estimate'], 0., 'a taken city is intact')

    def test_rot_and_void_end_the_city(self):
        for school, cause in (('rot', 'rot_plague'), ('void', 'void_unmade')):
            survivors, touched, ruined = self.mode(school)
            self.assertTrue(ruined, f'{school} should cost cities')
            self.assertTrue(all(c == cause for _, c, _ in ruined))


class CleanseTests(unittest.TestCase):
    """Killing the holder is not cleansing the land. The nodes are what persist."""

    @classmethod
    def setUpClass(cls):
        world = villain_world()
        cls.corrupted = corruption.corruption_request(
            {'api_version': 1, 'world': world, 'encounters': 40})
        cls.record = cls.corrupted['religion']['corruptions'][0]

    def drive(self, power, limit=12):
        """Cleanse repeatedly until it completes, returning the world and the tick count."""
        world, ticks = self.corrupted, 0
        while ticks < limit:
            world = corruption.cleanse_request(
                {'api_version': 1, 'world': world, 'target': {'corruption': 0}, 'power': power})
            ticks += 1
            if world['cleanse']['cleansed']:
                break
        return world, ticks

    def test_it_takes_time(self):
        """A structure that finished in one tick would not be a structure."""
        _, ticks = self.drive(.3)
        self.assertGreater(ticks, 1, 'a partial-power cleanse must take more than one tick')

    def test_it_drains_rather_than_out_competes(self):
        """Out-competing is arithmetically impossible: potency saturates at strength."""
        school = self.record['school']
        before = {n['id']: n['intensity'] for n in self.corrupted['magic']['networks'][school]['nodes']
                  if n['id'] in self.record['nodes']}
        once = corruption.cleanse_request(
            {'api_version': 1, 'world': self.corrupted, 'target': {'corruption': 0}, 'power': .2})
        after = {n['id']: n['intensity'] for n in once['magic']['networks'][school]['nodes']
                 if n['id'] in self.record['nodes']}
        self.assertTrue(after, 'a light touch should not finish it')
        for node, intensity in after.items():
            self.assertLess(intensity, before[node], 'every corrupted node must lose ground')

    def test_completing_it_returns_the_land_and_unseats_the_holder(self):
        done, _ = self.drive(1.)
        self.assertTrue(done['cleanse']['cleansed'])
        self.assertIsNotNone(done['religion']['corruptions'][0]['cleansed_age'])
        corrupted_cells = sum(1 for row in done['layers']['biome_variant'] for v in row if v >= 104)
        self.assertEqual(corrupted_cells, 0, 'the ground comes back')
        host = next(p for p in done['villains']['people'] if p['uid'] == self.record['villain_uid'])
        self.assertIsNone(host.get('god'))
        self.assertFalse(host['corrupted'])
        god = next(g for g in done['religion']['gods'] if g['id'] == self.record['god_id'])
        self.assertEqual(god['status'], 'sleeping')

    def test_an_unmanifested_field_keeps_its_negative_zero(self):
        """Cleansing must not leave the world different from one that was never corrupted."""
        import math
        done, _ = self.drive(1.)
        field = done['layers']['ley_' + self.record['school']]
        self.assertTrue(all(math.copysign(1., v) < 0 or v == 0. for row in field for v in row))
        self.assertEqual(max(v for row in field for v in row), 0.)

    def test_the_caller_world_is_never_touched(self):
        before = copy.deepcopy(self.corrupted)
        corruption.cleanse_request(
            {'api_version': 1, 'world': self.corrupted, 'target': {'corruption': 0}, 'power': 1.})
        self.assertEqual(self.corrupted, before)

    def test_malformed_cleanses_are_refused(self):
        for body in ({'api_version': 1, 'world': self.corrupted, 'target': {'corruption': 99}},
                     {'api_version': 1, 'world': self.corrupted, 'target': {'god_id': 'nobody'}},
                     {'api_version': 1, 'world': self.corrupted, 'target': {'corruption': 0}, 'power': 0},
                     {'api_version': 1, 'world': self.corrupted, 'target': {'corruption': 0}, 'power': 2},
                     {'api_version': 1, 'world': self.corrupted, 'target': {}}):
            with self.assertRaises(ValueError):
                corruption.cleanse_request(body)

    def test_a_god_that_does_not_walk_cannot_be_opposed(self):
        with self.assertRaises(ValueError):
            corruption.cleanse_request({'api_version': 1, 'world': self.corrupted,
                                        'target': {'god_id': 'god_radiant'}})

    def test_opposing_a_revealed_god_by_god_id_refuses_and_never_raises_stopiteration(self):
        """The only god corruption ever makes walk is the one this route cannot handle.

        `_reveal` sets `status` to 'walking' without writing a visitation record, because a
        corrupted god's footprint is its ley cluster. `depart_god` needs that record. Before
        this guard the call raised a bare `StopIteration` out of a validated request API,
        on the exact path `docs/corruption.md` advertises for opposing a walking god.
        """
        god_id = self.record['god_id']
        walking = next(g for g in self.corrupted['religion']['gods'] if g['id'] == god_id)
        self.assertEqual(walking['status'], 'walking')
        self.assertFalse([v for v in self.corrupted['religion'].get('visitations', [])
                          if v.get('god_id') == god_id])
        try:
            corruption.cleanse_request({'api_version': 1, 'world': self.corrupted,
                                        'target': {'god_id': god_id}, 'power': 1.})
        except ValueError as error:
            self.assertIn('corruption', str(error))
        except StopIteration:
            self.fail('a validated request API must not raise a bare StopIteration')
        else:
            self.fail('opposing a corruption-revealed god by god_id must be refused')

    def test_departing_a_revealed_god_is_refused_at_the_visitation_door_too(self):
        """The same status-only guard, reached through `visitation_request(depart=True)`."""
        from icarus_sim.terrain_visitation import visitation_request
        god_id = self.record['god_id']
        try:
            visitation_request({'api_version': 1, 'world': self.corrupted,
                                'god_id': god_id, 'depart': True})
        except ValueError:
            pass
        except StopIteration:
            self.fail('a validated request API must not raise a bare StopIteration')
        else:
            self.fail('a god that walks by corruption cannot depart a visitation it never made')

    def test_the_corruption_route_is_the_one_that_works(self):
        """The refusal names `{"corruption": <index>}`, so that route must actually work."""
        done, _ = self.drive(1.)
        self.assertTrue(done['cleanse']['cleansed'])
        god = next(g for g in done['religion']['gods'] if g['id'] == self.record['god_id'])
        self.assertEqual(god['status'], 'sleeping')


class CorruptionLegacyTests(unittest.TestCase):
    """A city unmade by a walking god names the god as the source of its scar.

    This costs no world: it is why the four lines that build it were lifted out of
    `corrupt`, where proving anything about them needed a villain world and a hidden god
    that happened to hold rot or void.
    """

    CITY = {'uid': 'city', 'population_profile': 'human_heartland', 'city_class': 'medium'}

    def potencies(self, **values):
        from icarus_sim.terrain_leyline_history import SCHOOLS
        return {school: values.get(school, 0.) for school in SCHOOLS}

    def test_the_god_is_the_source_even_though_no_branch_names_the_cause(self):
        """The region held umbral; the ruin must not say umbral chose this."""
        for school, cause in (('rot', 'rot_plague'), ('void', 'void_unmade')):
            with self.subTest(school=school):
                legacy = corruption.corruption_legacy(
                    self.CITY, cause, self.potencies(umbral=.9), school)
                self.assertEqual(legacy['school'], school)
                self.assertEqual(legacy['basis'], 'source',
                                 'a walking god is the source, not the region')

    def test_the_scar_still_follows_the_city_class(self):
        """Only school and basis are stated here; intensity stays ruin_legacy's."""
        for city_class, expected in (('small', 1.5), ('medium', 2.5), ('capital', 3.5)):
            with self.subTest(city_class=city_class):
                city = {**self.CITY, 'city_class': city_class}
                legacy = corruption.corruption_legacy(city, 'void_unmade', self.potencies(), 'void')
                self.assertEqual(legacy['intensity'], expected)

    def test_a_hidden_school_never_arrives_by_any_other_route(self):
        """The guard that makes the basis matter: nothing else can attribute one.

        `ruin_legacy` resolves a hidden school only if it is handed one, and the two
        corruption causes match no branch, so without this helper's explicit statement
        the ruin would carry a region or culture basis over a school neither holds.
        """
        from icarus_sim.terrain_ruins import ruin_legacy
        unattributed = ruin_legacy(self.CITY, 'void_unmade', self.potencies(umbral=.9),
                                   villain_school='void')
        self.assertNotEqual(unattributed['school'], 'void',
                            'villain_school is inert for a cause that is not a villain')
        self.assertEqual(unattributed['basis'], 'region')


if __name__ == '__main__':
    unittest.main()
