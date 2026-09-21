"""What happens to a refugee band that reached a town that is still standing.

The ruling this pins (owner, 2026-09-21): the band is **absorbed into the refuge**, not
founded as a settlement. A `settlement_candidates` entry does not name free ground -- it
names the refuge city's own node, 4 of 4 across two measured worlds and true by
construction, because `terrain_nomad_routes._flight` routes a survivor band to the node of
the site whose uid is `basis['refuge_uid']` and `seed_survivor_camps` records the candidate
at that terminal camp. Founding there would put a second settlement on a standing city.

Two things are asserted separately because they fail separately:

  the boundary pass   `absorb_survivor_camps` credits the right city, only while it is
                      still standing, and only once per band however often it is called
  the carry          the credited count survives `rebuild_tail`. It has to ride
                      `CARRIED_SURVIVOR_KEYS`, because `add_settlements` re-derives
                      `population_estimate` from the population budget on every rebuild --
                      a number written into that field before the rebuild is erased by it

The second is the half the founding analysis on the card did NOT cover, so it is measured on
a generated world put through the real `rebuild_tail` rather than reasoned about. See
`AbsorptionSurvivesTheRebuildTests` for why it is driven there and not through
`advance_age_request`.
"""
import copy
import unittest

from icarus_sim.terrain_nomad_effects import absorb_survivor_camps
from icarus_sim.terrain_settlements import CARRIED_SURVIVOR_KEYS, carry_survivor

REFUGE = 'surface-city-0-147-elf'


def band(uid='nomad-2-723', refuge_uid=REFUGE):
    return {'uid': uid, 'classification': 'survivors', 'route_status': 'routed',
            'basis': {'ruin_uid': 'ruin-surface-city-0-99-human', 'refuge_uid': refuge_uid}}


def candidate(uid='nomad-2-723', node=147, size=40):
    return {'id': 'settlement-candidate-' + uid, 'from_band': uid, 'node': node,
            'direction': [0., 1., 0.], 'migration_source_node': 99,
            'migration_distance_m': 12345.6, 'population_estimate': size,
            'reason': 'Refugees who reached ' + REFUGE + ' and stayed.'}


def city(uid=REFUGE, node=147, profile='elf'):
    return {'uid': uid, 'node': node, 'population_profile': profile, 'kind': 'city',
            'population_estimate': 5000, 'name': 'Korsal'}


def world(bands, candidates):
    return {'nomads': {'groups': list(bands)}, 'settlement_candidates': list(candidates)}


class AbsorptionTests(unittest.TestCase):
    def test_the_refuge_takes_the_band_in_and_nothing_is_founded(self):
        refuge = city()
        survivors = [refuge]
        absorbed, people = absorb_survivor_camps(world([band()], [candidate()]), survivors, 3)
        self.assertEqual((absorbed, people), (1, 40))
        self.assertEqual(refuge['absorbed_refugees'], 40)
        self.assertEqual(refuge['absorbed_bands'], ['nomad-2-723'])
        # Absorption is not founding: the survivor list it was handed is the same length.
        self.assertEqual(len(survivors), 1)

    def test_the_candidate_records_where_its_people_went(self):
        state = world([band()], [candidate()])
        absorb_survivor_camps(state, [city()], 3)
        entry = state['settlement_candidates'][0]
        self.assertEqual(entry['absorbed_age'], 3)
        self.assertEqual(entry['absorbed_into'], REFUGE)

    def test_a_refuge_that_fell_this_age_absorbs_nobody(self):
        """The filter the card asked for: the survivors list IS the standing cities."""
        state = world([band()], [candidate()])
        self.assertEqual(absorb_survivor_camps(state, [], 3), (0, 0))
        self.assertNotIn('absorbed_age', state['settlement_candidates'][0])

    def test_absorbing_the_same_band_twice_does_not_breed_people(self):
        """`seed_survivor_camps` only assigns the block when it has candidates, so a world
        can carry a previous advance's list unchanged into the next one."""
        state = world([band()], [candidate()])
        refuge = city()
        first = absorb_survivor_camps(state, [refuge], 3)
        second = absorb_survivor_camps(state, [refuge], 4)
        self.assertEqual(first, (1, 40))
        self.assertEqual(second, (0, 0))
        self.assertEqual(refuge['absorbed_refugees'], 40)
        self.assertEqual(refuge['absorbed_bands'], ['nomad-2-723'])

    def test_two_bands_on_one_refuge_both_land_in_a_fixed_order(self):
        bands = [band('nomad-2-723'), band('nomad-2-104')]
        candidates = [candidate('nomad-2-723', size=40), candidate('nomad-2-104', size=15)]
        refuge = city()
        forward = absorb_survivor_camps(world(bands, candidates), [refuge], 3)
        self.assertEqual(forward, (2, 55))
        self.assertEqual(refuge['absorbed_refugees'], 55)
        self.assertEqual(refuge['absorbed_bands'], ['nomad-2-104', 'nomad-2-723'])
        # Order of the stored list must not decide the answer.
        other = city()
        absorb_survivor_camps(world(bands[::-1], candidates[::-1]), [other], 3)
        self.assertEqual(other['absorbed_refugees'], refuge['absorbed_refugees'])
        self.assertEqual(other['absorbed_bands'], refuge['absorbed_bands'])

    def test_a_candidate_whose_band_is_gone_is_not_guessed_at(self):
        """The join is `from_band` -> band -> `basis['refuge_uid']`, an exact identity.

        Matching the candidate's node against a site instead would answer a different
        question -- which city stands there now -- and city ids renumber across ages.
        """
        state = world([], [candidate()])
        self.assertEqual(absorb_survivor_camps(state, [city()], 3), (0, 0))

    def test_a_band_that_fled_to_a_different_city_credits_that_city(self):
        other = city('surface-city-2-206-frosthold_dwarf', node=206, profile='frosthold_dwarf')
        refuge = city()
        state = world([band(refuge_uid=other['uid'])], [candidate()])
        self.assertEqual(absorb_survivor_camps(state, [refuge, other], 3), (1, 40))
        self.assertEqual(other['absorbed_refugees'], 40)
        self.assertNotIn('absorbed_refugees', refuge)


class CarryTests(unittest.TestCase):
    """The rebuild is what erases things. These two keys have to survive it."""

    def test_the_absorbed_count_is_inherited_by_the_rebuilt_site(self):
        for key in ('absorbed_refugees', 'absorbed_bands'):
            self.assertIn(key, CARRIED_SURVIVOR_KEYS, key)
        old = dict(city(), absorbed_refugees=40, absorbed_bands=['nomad-2-723'])
        fresh = {'uid': None, 'node': 147, 'population_profile': 'elf'}
        carry_survivor(fresh, old)
        self.assertEqual(fresh['absorbed_refugees'], 40)
        self.assertEqual(fresh['absorbed_bands'], ['nomad-2-723'])

    def test_a_site_that_absorbed_nobody_gains_no_keys(self):
        fresh = {'uid': None, 'node': 147, 'population_profile': 'elf'}
        carry_survivor(fresh, city())
        self.assertNotIn('absorbed_refugees', fresh)
        self.assertNotIn('absorbed_bands', fresh)


class AbsorptionSurvivesTheRebuildTests(unittest.TestCase):
    """A real world, rebuilt twice: once with the band absorbed and once without.

    **Driven through `rebuild_tail` rather than through `advance_age_request`, and that is
    a decision worth stating.** An age boundary decides fates before it absorbs anybody, and
    it is lethal: measured on seed 42 size 17, age 3 leaves **3 of 12 cities standing**, and
    all three refuges named by the three candidates are among the nine that fall. A live
    advance therefore absorbs nobody on this world — `absorb_survivor_camps` returns (0, 0),
    correctly — and a test that drove one would assert nothing while passing green.

    The fate lottery is not what is under test. What is under test is whether the credit
    outlives the rebuild that re-derives `population_estimate` from the population budget,
    so every city is handed to the rebuild as a survivor and the two runs differ in exactly
    one thing. `AbsorptionTests.test_a_refuge_that_fell_this_age_absorbs_nobody` covers the
    other half — the case that actually occurs on this world.
    """

    @classmethod
    def setUpClass(cls):
        from icarus_sim.terrain_world import generate_request
        from icarus_sim.terrain_lab import Config
        from icarus_sim.terrain_history import rebuild_tail
        world = generate_request({'seed': 42, 'overrides': {'size': 17, 'phase': 16}})
        cls.candidates = copy.deepcopy(world.get('settlement_candidates') or [])
        cfg = Config(**world['config'])
        age = len(world['history']['ages']) + 1

        # The control first, so only its population survives into the second run: two
        # finished worlds of this size held at once is gigabytes on a shared box.
        control = copy.deepcopy(world)
        untouched = copy.deepcopy(control['settlements']['sites'])
        rebuild_tail(control, cfg, untouched, 'age', age, evaluate=bool(cfg.magic_enabled))
        cls.control_population = {s['uid']: s['population_estimate']
                                  for s in control['settlements']['sites']}
        del control, untouched

        survivors = copy.deepcopy(world['settlements']['sites'])
        cls.absorbed, cls.people = absorb_survivor_camps(world, survivors, age)
        cls.credited = {s['uid']: int(s['absorbed_refugees']) for s in survivors
                        if s.get('absorbed_refugees')}
        rebuild_tail(world, cfg, survivors, 'age', age, evaluate=bool(cfg.magic_enabled))
        cls.after = world

    def sites(self, world):
        return {s['uid']: s for s in world['settlements']['sites']}

    def test_the_world_under_test_carries_candidates_to_absorb(self):
        """Without this the rest is vacuously true, which is how a green lies."""
        self.assertTrue(self.candidates, 'seed 42 size 17 must raise survivor camps')
        self.assertEqual(self.absorbed, len(self.candidates))
        self.assertEqual(self.people, sum(c['population_estimate'] for c in self.candidates))
        self.assertTrue(self.credited)

    def test_the_credit_is_still_on_the_city_after_the_rebuild(self):
        sites = self.sites(self.after)
        for uid, count in self.credited.items():
            self.assertEqual(sites[uid].get('absorbed_refugees'), count, uid)
            self.assertTrue(sites[uid].get('absorbed_bands'), uid)

    def test_the_rebuilt_population_is_higher_by_exactly_the_refugees(self):
        """The control is the same rebuild on the same survivors without the credit."""
        control = self.control_population
        moved = {}
        for uid, site in self.sites(self.after).items():
            if uid in control:
                delta = site['population_estimate'] - control[uid]
                if delta:
                    moved[uid] = delta
        self.assertEqual(moved, self.credited)

    def test_the_species_totals_still_add_up(self):
        """Independent of the split's own arithmetic: it reads only the totals."""
        sites = self.after['settlements']['sites']
        for species, allowance in self.after['population_budget']['allowances'].items():
            members = [s for s in sites if s['population_profile'] == species]
            if not members:
                continue
            self.assertEqual(sum(s['population_estimate'] for s in members),
                             allowance + sum(int(s.get('absorbed_refugees') or 0)
                                             for s in members), species)


if __name__ == '__main__':
    unittest.main()
