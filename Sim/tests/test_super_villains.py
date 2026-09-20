"""Super villains: the band a region climbs into, and what it does once it is there."""
import unittest

from icarus_sim import terrain_villains as villains
from icarus_sim.terrain_world import generate_request


def world(rise=1., **overrides):
    body = {'size': 17, 'villain_rise': rise}
    body.update(overrides)
    return generate_request({'seed': 42, 'recipe_version': 3, 'overrides': body})


class DefaultTests(unittest.TestCase):
    def test_zero_rise_leaves_no_trace_at_all(self):
        """Not merely inert: a default world carries no villains block to ignore."""
        plain = generate_request({'seed': 42, 'recipe_version': 3, 'overrides': {'size': 17}})
        self.assertNotIn('villains', plain)

    def test_the_option_is_recorded_only_when_it_is_used(self):
        plain = generate_request({'seed': 42, 'recipe_version': 3, 'overrides': {'size': 17}})
        self.assertNotIn('villain_rise', plain['recipe']['overrides'])
        self.assertEqual(plain['recipe']['resolved']['villain_rise'], 0.)


class RiseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.world = world()

    def test_tier_accumulates_against_a_persistent_anchor(self):
        """A culture id is rebuilt every age, so tier may not be keyed to one.

        Keyed to a culture, accumulation silently resets each age and nothing can ever
        reach the band. The anchor is a ley node id, which only ever gets appended to.
        """
        tiers = self.world['villains']['tiers']
        self.assertTrue(tiers)
        nodes = {n['id'] for net in self.world['magic']['networks'].values() for n in net['nodes']}
        anchored = [k for k in tiers if k in nodes or k.startswith('seat-')]
        self.assertEqual(sorted(anchored), sorted(tiers), 'every tier key must be a persistent anchor')
        cultures = {str(c['id']) for c in self.world['humans']['cultures']}
        self.assertFalse(set(tiers) & cultures, 'tier must not be keyed to a culture id')

    def test_a_region_that_concentrates_enough_raises_one(self):
        people = self.world['villains']['people']
        self.assertTrue(people, 'a highly concentrated world should raise at least one')
        for person in people:
            self.assertGreaterEqual(person['tier'], villains.SUPER_TIER)
            self.assertGreater(person['reach_m'], 0.)
            self.assertIn(person['growth'], set(villains.GROWTH_BY_PRESSURE.values()) | {villains.DEFAULT_GROWTH})
            self.assertEqual(person['status'], 'living')

    def test_reach_is_the_tier(self):
        """Tier is not a flag, it is the reach: the two move together by construction."""
        for person in self.world['villains']['people']:
            expected = person['tier'] * villains.REACH_SPACINGS_PER_TIER * self.world['config']['settlement_spacing']
            self.assertAlmostEqual(person['reach_m'], expected, places=6)

    def test_a_villain_takes_cities_in_its_own_name(self):
        caused = [r for r in self.world['ruins'] if str(r.get('cause', '')).startswith('villain')]
        self.assertTrue(caused, 'a seated villain should cost the world at least one city')
        for ruin in caused:
            self.assertIn('villain_uid', ruin['evidence'])
            self.assertIn(ruin['evidence']['growth'], set(villains.GROWTH_BY_PRESSURE.values()) | {villains.DEFAULT_GROWTH})
            # The ground it scars carries what it held, not the region's own school.
            self.assertEqual(ruin['legacy']['basis'], 'source')
            self.assertEqual(ruin['legacy']['school'], ruin['evidence']['school'])

    def test_the_outlook_says_where_it_is_coming_from(self):
        outlook = self.world['villains']['outlook']
        self.assertGreaterEqual(outlook['ceiling'], 1)
        self.assertEqual(outlook['standing'], len(self.world['villains']['people']))
        for row in outlook['regions']:
            self.assertEqual(round(row['to_threshold'], 6),
                             round(max(0., villains.SUPER_TIER - row['tier']), 6))


class BandTests(unittest.TestCase):
    """The ceiling and the hysteresis band, unit-level so the rules are readable."""

    def test_the_ceiling_scales_with_the_world(self):
        self.assertEqual(villains.ceiling(0, 3.), 0)
        self.assertEqual(villains.ceiling(1, 3.), 1)
        self.assertEqual(villains.ceiling(9, 3.), 3)
        self.assertEqual(villains.ceiling(10, 3.), 4)
        # A dense world still gets one: scarcity is a ratio, never a prohibition.
        self.assertEqual(villains.ceiling(2, 12.), 1)

    def test_turmoil_reads_the_forecast_as_well_as_the_scars(self):
        scarred = villains.turmoil({'regional_threat': .5})
        coming = villains.turmoil({'regional_threat': .5, 'war_risk': 1., 'war_hunger': 1.})
        self.assertGreater(coming, scarred)
        self.assertLessEqual(coming, 1.)

    def test_a_pretender_stalls_just_beneath_the_band(self):
        self.assertLess(villains.STALLED_TIER, villains.SUPER_TIER)

    def test_the_band_to_stay_sits_below_the_band_to_rise(self):
        """Hysteresis is what makes a reign long once established."""
        from icarus_sim.terrain_world import OPTIONS
        self.assertLess(OPTIONS['villain_hold']['default'], villains.SUPER_TIER)


if __name__ == '__main__':
    unittest.main()
