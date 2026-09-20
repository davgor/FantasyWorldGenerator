"""Whether a villain's fall can happen in a world anyone can configure, and to a villain
the age loop still looks at.

`test_super_villains.FallTests` establishes what a fall *does* once it fires. It fires
those tests with `hold=99.`, and `villain_hold` is declared `0. .. 1.`. That gap is what
this module is about: everything downstream of the fall -- `status`, `fell_age`,
`villains.fallen`, `claims[].influence` and the seven consumers taught to filter on
standing -- is proven only under a parameter no world can be built with.

Every test here is expected to fail against the tree that introduced it. They are written
as the assertions that should hold, not as a description of what happens now, so they pass
unchanged once the defect is fixed and they say what "fixed" means.

Synthetic worlds throughout, for the reason FallTests gives: a generated world costs
minutes and nothing at the default `villain_rise` of zero produces a villain at all.
"""
import unittest

from icarus_sim import terrain_villains as villains
from icarus_sim.terrain_world import OPTIONS


class Config:
    settlement_spacing = 1000.


def one_region_world(threat):
    """One culture, one city, one ley node -- the shape FallTests uses."""
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


def two_region_world():
    """Two cultures, each with its own city and its own nearest ley node.

    Two regions rather than one so that when the first city dies the world still has a
    region to advance: the stranded villain is then a villain the loop skips, not a
    villain in an empty world.
    """
    cities = [
        {'id': 'site-1', 'uid': 'city-1', 'node': 7, 'direction': [0., 1., 0.],
         'population_profile': 'human_heartland'},
        {'id': 'site-2', 'uid': 'city-2', 'node': 9, 'direction': [1., 0., 0.],
         'population_profile': 'human_heartland'},
    ]
    return {
        'effective_config': {'globe_radius': 100000.},
        'settlements': {'sites': cities},
        'humans': {'cultures': [{'id': 'culture-1', 'city_ids': ['site-1']},
                                {'id': 'culture-2', 'city_ids': ['site-2']}]},
        'magic': {'networks': {'weave': {'nodes': [{'id': 'ley-1', 'direction': [0., 1., 0.]},
                                                   {'id': 'ley-2', 'direction': [1., 0., 0.]}],
                                         'edges': []}}},
        'threat_assessments': {'cities': [
            {'city_uid': 'city-1', 'regional_threat': 1., 'war_risk': 0., 'war_hunger': 0.,
             'war_pressure': 0., 'nest_pressure': 1., 'ley_pressure': 0.},
            {'city_uid': 'city-2', 'regional_threat': 0., 'war_risk': 0., 'war_hunger': 0.,
             'war_pressure': 0., 'nest_pressure': 0., 'ley_pressure': 0.},
        ]},
    }


def quieten(result, uid='city-1'):
    """The region stops being troubled. Every input `turmoil()` reads goes to zero."""
    for report in result['threat_assessments']['cities']:
        if report['city_uid'] == uid:
            report.update(regional_threat=0., war_risk=0., war_hunger=0.,
                          war_pressure=0., nest_pressure=0., ley_pressure=0.)


def remove_city(result, uid='city-1', site_id='site-1', culture='culture-1'):
    """What an age transition does to a city a fate took: it stops existing.

    `age_transition` rebuilds `settlements.sites` from the survivors and rebuilds
    `humans.cultures` from the roads that join them, so a culture whose only city died
    does not come back and its anchor is not produced again.
    """
    result['settlements']['sites'] = [c for c in result['settlements']['sites'] if c['uid'] != uid]
    result['humans']['cultures'] = [c for c in result['humans']['cultures'] if c['id'] != culture]
    result['threat_assessments']['cities'] = [r for r in result['threat_assessments']['cities']
                                              if r['city_uid'] != uid]


def seat_one(result, hold, rise=1.):
    """Seat a villain at age 0 and hand back its record.

    `rise=1.` against a fully troubled region seats at tier exactly `SUPER_TIER`: the
    weakest villain the model can produce. Using the weakest one makes the reachability
    claim as tight as it goes -- if even a villain that only just scraped over the band
    cannot be unseated by any legal `villain_hold`, no villain can.
    """
    cast = villains.advance(result, Config(), 0, rise=rise, hold=hold, density=3.)
    assert len(cast) == 1, f'expected exactly one seated villain, got {cast}'
    assert cast[0]['tier'] == villains.SUPER_TIER, cast[0]['tier']
    return cast[0]


def run_quiet_ages(result, uid, hold, rise, ages=25):
    """Advance a collapsed region and report the age the reign ended, or None."""
    for age in range(1, ages + 1):
        villains.advance(result, Config(), age, rise=rise, hold=hold, density=3.)
        record = next(p for p in result['villains']['people'] if p['uid'] == uid)
        if not villains.is_standing(record):
            return age
    return None


class HarnessControlTests(unittest.TestCase):
    """The positive control. This one passes, and the others only mean something if it does.

    Every failing test below reports the absence of a fall. Absence is exactly what a
    broken fixture also produces -- a villain that never seated, a record looked up by the
    wrong uid, a loop that never ran. So the harness is made to produce a fall first, out
    at the band `FallTests` uses, and only then used to show that no legal band gets there.
    """

    def test_the_harness_observes_a_fall_when_one_is_reachable(self):
        result = one_region_world(threat=1.)
        villain = seat_one(result, hold=99.)
        quieten(result)
        self.assertEqual(run_quiet_ages(result, villain['uid'], hold=99., rise=0., ages=5), 1,
                         'the fixture cannot observe a fall, so no absence it reports is evidence')


class ReachableFallTests(unittest.TestCase):
    """A reign must be able to end in a world someone can actually ask for.

    `villain_hold` is described in `OPTIONS` as "Tier a seated villain falls below to lose
    the world". Seating requires `tier >= SUPER_TIER`, and after seating the only writes to
    the ledger are `tiers[rid] = tiers.get(rid, 0.) + rise * pressed` with both factors
    non-negative. A seated villain's tier is therefore monotonically non-decreasing and
    never returns below 1.0, so `tier < hold` needs `hold > 1.0` -- outside the declared
    maximum. The option cannot do the one thing its description promises.
    """

    def test_some_legal_villain_hold_ends_a_reign_in_a_region_that_has_gone_quiet(self):
        """The headline. Sweep the whole declared range; at least one value must work.

        This deliberately does not say *which* value, nor how the fix should work -- decay
        the ledger, or measure current concentration rather than cumulative. It says only
        that the reachable set is not empty, which is the difference between a tuning
        parameter and a dead branch.
        """
        spec = OPTIONS['villain_hold']
        holds = [spec['min'], .35, spec['default'], .999, spec['max']]
        ended = {}
        for hold in holds:
            result = one_region_world(threat=1.)
            villain = seat_one(result, hold)
            quieten(result)
            ended[hold] = run_quiet_ages(result, villain['uid'], hold, rise=OPTIONS['villain_rise']['default'])
        self.assertTrue(any(age is not None for age in ended.values()),
                        'no legal villain_hold in '
                        f'[{spec["min"]}, {spec["max"]}] ends a reign over 25 quiet ages: {ended}. '
                        'The fall branch is unreachable in every configuration a world can be '
                        'built with, so everything it writes is dead code in production.')

    def test_the_band_that_would_end_a_reign_is_a_band_a_world_may_be_given(self):
        """Locate the boundary rather than asserting around it.

        Bisects for the smallest `hold` that ends a reign in a collapsed region, then
        checks that value against the declared range. The failure message is the finding:
        it prints the band the model actually requires beside the band the option permits.
        """
        spec = OPTIONS['villain_hold']

        def falls_at(hold):
            result = one_region_world(threat=1.)
            villain = seat_one(result, hold)
            quieten(result)
            return run_quiet_ages(result, villain['uid'], hold, rise=spec['default'], ages=3) is not None

        low, high = 0., 1024.
        self.assertTrue(falls_at(high), 'the probe itself is broken: no hold ends this reign')
        for _ in range(60):
            mid = (low + high) / 2.
            if falls_at(mid):
                high = mid
            else:
                low = mid
        self.assertLessEqual(high, spec['max'],
                             f'a reign ends only at villain_hold > {low!r}, but the option is '
                             f'declared {spec["min"]} .. {spec["max"]}. '
                             f'`test_super_villains.FallTests` forces the fall with hold=99., which is '
                             f'{99. / spec["max"]:.0f}x the declared maximum, so it establishes what a '
                             'fall does without establishing that one can happen.')

    def test_a_region_that_goes_quiet_does_not_hold_its_villain_at_peak_tier(self):
        """The mechanism under both of the above: tier is cumulative, and never falls.

        Hysteresis -- a band to stay below the band to rise -- only means anything if the
        measured value can come back down. `tier` is an accumulator over every age's
        turmoil, so it records the worst the region ever was, not how bad it is now. A
        region at zero turmoil for twenty-five ages keeps a villain at exactly the tier it
        seated with.
        """
        result = one_region_world(threat=1.)
        villain = seat_one(result, hold=OPTIONS['villain_hold']['default'])
        seated_tier = villain['tier']
        quieten(result)
        for age in range(1, 26):
            villains.advance(result, Config(), age, rise=OPTIONS['villain_rise']['default'],
                             hold=OPTIONS['villain_hold']['default'], density=3.)
        record = next(p for p in result['villains']['people'] if p['uid'] == villain['uid'])
        self.assertLess(record['tier'], seated_tier,
                        f'tier is still {record["tier"]!r} after 25 ages at zero turmoil. '
                        'Nothing in the model reduces a seated villain\'s tier, so the hold band '
                        'is never crossed from above and `villain_hold` can only ever be inert.')


class StrandedVillainTests(unittest.TestCase):
    """A villain whose region stops being produced is never looked at again.

    `advance()` iterates the regions `regions()` produces this age and reads each villain
    out of `living` by that region's anchor. A villain whose anchor is not produced is
    never the subject of the loop: its tier is not updated, the fall check does not run,
    and it is written straight back into `block['people']` as standing. Cities die every
    age transition and cultures are rebuilt from the roads that survive, so an anchor
    ceasing to be produced is ordinary, not exotic.

    `regions()` documents the anchor as the thing that persists. The ley node id does
    persist; the region built on it does not.
    """

    def test_the_fall_check_runs_for_a_villain_whose_region_is_no_longer_produced(self):
        """`hold=99.` is used here as an instrument, not as a configuration.

        `FallTests` establishes that a villain the loop *visits* falls immediately at this
        band. So a villain that does not fall at it was never visited, which isolates this
        defect from the unreachable-band defect above: this one would still be here after
        the band is fixed.
        """
        result = two_region_world()
        villain = seat_one(result, hold=.7)
        self.assertEqual(villain['region'], 'ley-1')
        remove_city(result)

        anchors = [r['anchor'] for r in villains.regions(
            result, 100000., {r['city_uid']: r for r in result['threat_assessments']['cities']})]
        self.assertNotIn('ley-1', anchors, 'the probe needs the anchor to actually be gone')

        ended = run_quiet_ages(result, villain['uid'], hold=99., rise=0., ages=5)
        record = next(p for p in result['villains']['people'] if p['uid'] == villain['uid'])
        self.assertIsNotNone(ended,
                             f'{villain["uid"]} still stands after five ages at hold=99., a band that '
                             f'unseats any villain the loop reaches. It holds tier {record["tier"]!r} and '
                             f'reach {record["reach_m"]!r} over a region the world no longer has, and '
                             '`advance()` returns it in the standing cast that feeds `resolve_wars`. '
                             'There is no path by which it can ever fall.')

    def test_the_outlook_does_not_contradict_itself_about_who_stands(self):
        """One returned document, two answers, no consumer able to tell which is right.

        `outlook()` counts `standing` from `block['people']` but builds `regions` from the
        anchors produced this age. A stranded villain is in the first and in none of the
        second, so the report says a villain stands and simultaneously shows nowhere it
        could be standing. This is the consumer-facing face of the defect above and it
        needs no knowledge of villain rules to call wrong.
        """
        result = two_region_world()
        seat_one(result, hold=.7)
        remove_city(result)
        villains.advance(result, Config(), 1, rise=0., hold=.7, density=3.)

        report = villains.outlook(result, Config(), rise=0., density=3.)
        seated_rows = [row for row in report['regions'] if row['seated']]
        self.assertEqual(report['standing'], len(seated_rows),
                         f'outlook reports standing={report["standing"]} but {len(seated_rows)} of '
                         f'{len(report["regions"])} regions are seated: {report["regions"]}')


if __name__ == '__main__':
    unittest.main()
