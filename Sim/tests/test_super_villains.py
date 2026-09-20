"""Super villains: the band a region climbs into, and what it does once it is there."""
import unittest

from icarus_sim import terrain_villains as villains
from icarus_sim.terrain_world import generate_request


def world(rise=1., **overrides):
    body = {'size': 17, 'villain_rise': rise}
    body.update(overrides)
    return generate_request({'seed': 42, 'recipe_version': 3, 'overrides': body})


class DefaultTests(unittest.TestCase):
    """The default changed: a generated world now ends with antagonists standing in it.

    These tests used to assert the opposite, and they were right to until the ruling of
    2026-09-20. They are kept and inverted rather than deleted, because the property that
    matters is unchanged in shape -- the option still decides, and zero is still a real off
    switch that writes no block at all.
    """

    @classmethod
    def setUpClass(cls):
        cls.plain = generate_request({'seed': 42, 'recipe_version': 3, 'overrides': {'size': 17}})

    def test_a_default_world_ends_with_super_villains_standing(self):
        self.assertIn('villains', self.plain)
        standing = villains.standing(self.plain['villains']['people'])
        self.assertTrue(standing, 'a default world raised nobody')
        for villain in standing:
            self.assertGreaterEqual(villain['tier'], villains.SUPER_TIER)

    def test_the_promoted_are_seated_at_the_bottom_of_the_band(self):
        """A villain that has just crossed the line is growing, not arrived."""
        promoted = [v for v in villains.standing(self.plain['villains']['people'])
                    if any(e['event'] == 'promoted' for e in v.get('log', []))]
        self.assertTrue(promoted)
        for villain in promoted:
            self.assertEqual(villain['tier'], villains.SUPER_TIER)

    def test_no_more_stand_than_the_ceiling_allows(self):
        """Asserted against the ceiling, never against a count.

        The number of regions is phase- and age-dependent -- 9 after two ages at phase 16,
        11 at phase 14 -- so any test naming a literal number of villains is pinning a
        coincidence rather than a rule.
        """
        block = self.plain['villains']
        outlook = block['outlook']
        standing = villains.standing(block['people'])
        self.assertLessEqual(len(standing), outlook['ceiling'])
        self.assertEqual(outlook['ceiling'],
                         villains.ceiling(len(outlook['regions']), 3.))

    def test_the_outlook_agrees_with_the_roster(self):
        """The regression this guards: a villain's own well used to re-anchor its region.

        `sink_well` appends a ley node at the villain's seat and `_held_node` took the
        nearest node, so the anchor moved onto the well and the roster and the outlook
        stopped describing the same world -- standing 1 against zero regions seated, on the
        very age the villain rose.
        """
        block = self.plain['villains']
        seated = sum(1 for row in block['outlook']['regions'] if row['seated'])
        self.assertEqual(block['outlook']['standing'], seated)
        self.assertEqual(len(villains.standing(block['people'])), seated)

    def test_no_region_is_anchored_to_a_villains_own_well(self):
        wells = {v['well']['node'] for v in villains.standing(self.plain['villains']['people'])
                 if v.get('well')}
        self.assertTrue(wells, 'no well was sunk, so this guards nothing')
        for row in self.plain['villains']['outlook']['regions']:
            self.assertNotIn(row['region'], wells)

    def test_zero_rise_is_still_a_real_off_switch(self):
        """Not merely inert: a world built with zero carries no villains block to ignore."""
        off = generate_request({'seed': 42, 'recipe_version': 3,
                                'overrides': {'size': 17, 'villain_rise': 0.}})
        self.assertNotIn('villains', off)

    def test_the_option_is_recorded_only_when_it_is_used(self):
        self.assertNotIn('villain_rise', self.plain['recipe']['overrides'])
        self.assertEqual(self.plain['recipe']['resolved']['villain_rise'], .5)


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
        # `people` holds the fallen too, so the assertions below -- which describe what a
        # villain that HOLDS ground looks like -- are scoped to the standing. Before the
        # fallen were kept, this loop read `people` directly and passed for the wrong
        # reason: everyone was living because nobody was ever recorded as anything else.
        people = villains.standing(self.world['villains']['people'])
        self.assertTrue(people, 'a highly concentrated world should raise at least one')
        for person in people:
            self.assertGreaterEqual(person['tier'], villains.SUPER_TIER)
            self.assertGreater(person['reach_m'], 0.)
            self.assertIn(person['growth'], set(villains.GROWTH_BY_PRESSURE.values()) | {villains.DEFAULT_GROWTH})
            self.assertEqual(person['status'], 'living')

    def test_reach_is_the_tier(self):
        """Tier is not a flag, it is the reach: the two move together by construction.

        True of the fallen as well: a villain keeps the reach it had when it fell, which is
        why every consumer that means "who presses on this city now" has to test status
        rather than reach.
        """
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


class FallTests(unittest.TestCase):
    """A villain that falls is kept, is not counted as standing, and does not come back.

    Built from a synthetic world rather than a generated one. Nothing at the default
    `villain_rise` of zero ever produces a fall, and a generated world that does costs
    minutes — which is exactly why `advance()` discarded the fallen record for as long as
    it did, with `test_a_region_that_concentrates_enough_raises_one` asserting everyone is
    `living` and passing because nobody ever stopped being.
    """

    class Config:
        settlement_spacing = 1000.

    def world(self, threat):
        """One culture, one city, one ley node to anchor the region to."""
        city = {'id': 'site-1', 'uid': 'city-1', 'node': 7, 'direction': [0., 1., 0.],
                'population_profile': 'human_heartland'}
        return {
            'effective_config': {'globe_radius': 100000.},
            'settlements': {'sites': [city]},
            'humans': {'cultures': [{'id': 'culture-1', 'city_ids': ['site-1']}]},
            'magic': {'networks': {'weave': {'nodes': [{'id': 'ley-1', 'direction': [0., 1., 0.]}],
                                             'edges': []}}},
            'threat_assessments': {'cities': [{'city_uid': 'city-1', 'regional_threat': threat,
                                               'war_risk': 0., 'war_hunger': 0.,
                                               'war_pressure': 0., 'nest_pressure': threat,
                                               'ley_pressure': 0.}]},
        }

    def seat(self):
        """A world with one seated villain, and the world it is seated in."""
        world = self.world(threat=1.)
        cast = villains.advance(world, self.Config(), 0, rise=2., hold=.7, density=3.)
        self.assertEqual(len(cast), 1, 'a fully troubled region should seat one')
        return world, cast[0]

    def test_a_fall_is_recorded_rather_than_discarded(self):
        """The regression: status and the log entry used to be written and then dropped."""
        world, villain = self.seat()
        uid = villain['uid']
        # Turmoil collapses, so the tier decays below `hold` and the reign ends.
        world['threat_assessments']['cities'][0].update(regional_threat=0., nest_pressure=0.)
        standing_now = villains.advance(world, self.Config(), 1, rise=0., hold=99., density=3.)

        self.assertEqual(standing_now, [], 'nobody holds ground after the fall')
        people = world['villains']['people']
        record = next((p for p in people if p['uid'] == uid), None)
        self.assertIsNotNone(record, 'the fallen villain must still be in people')
        self.assertEqual(record['status'], 'fallen')
        self.assertEqual(record['fell_age'], 1)
        self.assertIn('fell', [entry.get('event') for entry in record['log']])

    def test_the_fallen_do_not_rise_again(self):
        """`advance` rebuilds its working set from `people`; unfiltered, the dead come back."""
        world, villain = self.seat()
        world['threat_assessments']['cities'][0].update(regional_threat=0., nest_pressure=0.)
        villains.advance(world, self.Config(), 1, rise=0., hold=99., density=3.)

        for age in (2, 3):
            standing_now = villains.advance(world, self.Config(), age, rise=0., hold=99., density=3.)
            self.assertEqual(standing_now, [], f'age {age} resurrected a fallen villain')
        uids = [p['uid'] for p in world['villains']['people']]
        self.assertEqual(len(uids), len(set(uids)), 'a fallen villain must not be duplicated')

    def test_the_fallen_are_excluded_from_every_standing_question(self):
        world, villain = self.seat()
        world['threat_assessments']['cities'][0].update(regional_threat=0., nest_pressure=0.)
        villains.advance(world, self.Config(), 1, rise=0., hold=99., density=3.)
        people = world['villains']['people']

        self.assertEqual(villains.standing(people), [])
        # The fate lottery is the one that would move worlds, and the tier test alone is
        # not the reason it is safe.
        city = world['settlements']['sites'][0]
        self.assertEqual(villains.causes(people, city, 100000.), [])
        # And the outlook must not report a fallen region as seated.
        report = villains.outlook(world, self.Config(), rise=0., density=3.)
        self.assertTrue(all(not row['seated'] for row in report['regions']))

    def test_a_world_where_nobody_falls_is_unchanged(self):
        """The ordering guarantee: living-first, by region anchor, exactly as before."""
        world = self.world(threat=1.)
        villains.advance(world, self.Config(), 0, rise=2., hold=.7, density=3.)
        villains.advance(world, self.Config(), 1, rise=2., hold=.7, density=3.)
        people = world['villains']['people']
        self.assertTrue(all(p['status'] == 'living' for p in people))
        self.assertEqual([p['region'] for p in people], sorted(p['region'] for p in people))

    def test_a_claim_records_how_hard_it_still_presses(self):
        """Ground a villain took stays taken, and says whose and how hard.

        The user's decision was that a fallen villain's claims keep steering the world.
        That settles whether the record persists; it does not settle at what strength, and
        those are different questions. `influence` is a number rather than a boolean so the
        second can be answered later -- by decaying it the way `FRAGMENT_SHARE` already
        decays tier -- without reopening the consumers that read it.
        """
        world, villain = self.seat()
        record = next(p for p in world['villains']['people'] if p['uid'] == villain['uid'])
        claim = villains.claim_settlements(world, self.Config(), record, 0)
        self.assertIsNotNone(claim, 'a seated villain near a city should claim ground')
        self.assertEqual(claim['holder_status'], 'living')
        self.assertEqual(claim['influence'], 1.)

        world['threat_assessments']['cities'][0].update(regional_threat=0., nest_pressure=0.)
        villains.advance(world, self.Config(), 1, rise=0., hold=99., density=3.)

        fallen = next(p for p in world['villains']['people'] if p['uid'] == villain['uid'])
        self.assertEqual(fallen['status'], 'fallen')
        held = fallen['claims'][0]
        self.assertEqual(held['holder_status'], 'fallen')
        self.assertEqual(held['holder_fell_age'], 1)
        self.assertEqual(held['influence'], villains.FALLEN_CLAIM_INFLUENCE)
        # This constant moves worlds, which is the point of asserting it here. It moved
        # once, deliberately, from 1.0 to a decaying curve: see
        # docs/decisions/024-fallen-claim-decay.md. Retention is unchanged -- the claim is
        # never pruned -- but how hard it presses now fades, because a world advanced
        # across many ages was otherwise placed entirely by villains who no longer exist.
        self.assertEqual(villains.FALLEN_CLAIM_INFLUENCE, .6)
        self.assertEqual(villains.CLAIM_DECAY_PER_AGE, .6)
        self.assertEqual(villains.CLAIM_INFLUENCE_FLOOR, .05)

        # The claim fades with each further age and is restamped on the record itself, so
        # a leaf package reads the current strength off the claim without a join.
        world['villains']['tiers'] = {k: 0. for k in world['villains']['tiers']}
        villains.advance(world, self.Config(), 4, rise=0., hold=99., density=3.)
        faded = next(p for p in world['villains']['people'] if p['uid'] == villain['uid'])
        self.assertEqual(faded['claims'][0]['influence'], villains.claim_influence(3))
        self.assertLess(faded['claims'][0]['influence'], villains.FALLEN_CLAIM_INFLUENCE)
        # The record itself is untouched by the fading.
        self.assertEqual(faded['claims'][0]['holder_fell_age'], 1)
        self.assertEqual(faded['status'], 'fallen')

    def test_a_villain_that_marked_the_world_leaves_a_record_of_it(self):
        """The ruin pattern: who they were, when they ended, and what they left.

        Kept beside the live roster rather than in it, the way `ruins` sits beside
        `settlements.sites`: the roster answers who holds ground, this answers who held it.
        """
        world, villain = self.seat()
        record = next(p for p in world['villains']['people'] if p['uid'] == villain['uid'])
        villains.claim_settlements(world, self.Config(), record, 0)
        world['threat_assessments']['cities'][0].update(regional_threat=0., nest_pressure=0.)
        villains.advance(world, self.Config(), 3, rise=0., hold=99., density=3.)

        marks = world['villains']['fallen']
        self.assertEqual(len(marks), 1)
        mark = marks[0]
        self.assertEqual(mark['id'], 'fallen-' + villain['uid'])
        self.assertEqual(mark['kind'], 'fallen_villains')
        self.assertEqual(mark['fell_age'], 3)
        self.assertEqual(mark['born_age'], 0)
        self.assertEqual(mark['reigned_ages'], 3)
        self.assertEqual(mark['left']['claims'], ['claim-' + villain['uid']])
        # A grip it no longer holds is not part of what it left behind.
        self.assertNotIn('tier', mark)
        self.assertNotIn('reach_m', mark)
        # And no asset: its wells are ley nodes and its claims are claims, both already
        # placed. An asset_id here would be an identity the catalogue carries for nothing.
        self.assertNotIn('asset_id', mark)

    def test_a_villain_that_marked_nothing_leaves_no_monument(self):
        """"If they indeed left a mark" is a condition, not a formality.

        One that reached the band, took no city, staked no claim and sank no well did not
        mark the world. What it leaves is what it always left: the decayed tier on the land.
        """
        world, villain = self.seat()
        world['threat_assessments']['cities'][0].update(regional_threat=0., nest_pressure=0.)
        villains.advance(world, self.Config(), 1, rise=0., hold=99., density=3.)

        self.assertEqual(world['villains']['fallen'], [], 'nothing caused, nothing recorded')
        # It is still off the roster and still recorded as having existed.
        record = next(p for p in world['villains']['people'] if p['uid'] == villain['uid'])
        self.assertEqual(record['status'], 'fallen')
        # And the land keeps its scar, which is the successor squabble.
        self.assertTrue(any(v > 0. for v in world['villains']['tiers'].values()))

    def test_the_record_of_the_dead_is_never_pruned(self):
        """`ruins` is initialised once and never pruned; this follows it."""
        world, villain = self.seat()
        record = next(p for p in world['villains']['people'] if p['uid'] == villain['uid'])
        villains.claim_settlements(world, self.Config(), record, 0)
        world['threat_assessments']['cities'][0].update(regional_threat=0., nest_pressure=0.)
        villains.advance(world, self.Config(), 1, rise=0., hold=99., density=3.)
        first = [m['id'] for m in world['villains']['fallen']]
        self.assertTrue(first)

        for age in (2, 3, 4):
            villains.advance(world, self.Config(), age, rise=0., hold=99., density=3.)
        self.assertEqual([m['id'] for m in world['villains']['fallen']], first,
                         'the dead are neither dropped nor duplicated by later ages')


if __name__ == '__main__':
    unittest.main()
