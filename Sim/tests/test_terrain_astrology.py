"""Behavioral coverage for the single moon: seeding, tide, almanac and exports.

The generated-world half (stage wiring, age lottery under surge, age API pins) is
added once terrain_history.py is free; these tests need only the pure functions.
"""
import json
import math
import random
import unittest

from icarus_sim.terrain_astrology import (REGIONS, HEMISPHERES, DAYS_PER_MONTH, MONTHS_PER_YEAR, HOURS_PER_DAY, DAYS_PER_YEAR,
                                          seed_moon, moon_state, tide, almanac, region_direction, day_state)
from icarus_sim.terrain_leyline_history import KNOWN_SCHOOLS


def fixed_moon(**overrides):
    """A moon with round numbers so expectations can be computed by hand."""
    moon = {'periods': {'synodic': 30, 'spin': 40, 'nod': 20}, 'offsets': {'synodic': 0, 'spin': 0, 'nod': 0},
            'tilt_max_degrees': 30., 'great_year_days': 120}
    moon.update(overrides)
    return moon


class MoonGeometryTests(unittest.TestCase):
    def test_regions_cover_every_school_once_in_school_order(self):
        self.assertEqual(list(REGIONS), list(KNOWN_SCHOOLS))
        self.assertEqual(HEMISPHERES['still'], ['radiant', 'water', 'earth', 'umbral'])
        self.assertEqual(HEMISPHERES['restless'], ['weave', 'fire', 'air', 'infernal'])
        for school, vector in REGIONS.items():
            self.assertAlmostEqual(sum(v*v for v in vector), 1., places=12)
            self.assertAlmostEqual(abs(vector[1]), math.sin(math.radians(45)), places=12)
        self.assertGreater(REGIONS['radiant'][1], 0)
        self.assertLess(REGIONS['weave'][1], 0)

    def test_seeding_is_deterministic_bounded_and_prefers_coprime_periods(self):
        a = seed_moon(42); b = seed_moon(42); c = seed_moon(43)
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)
        for seed in (0, 1, 7, 42, 2**32-1):
            moon = seed_moon(seed)
            p = moon['periods']
            self.assertTrue(26 <= p['synodic'] <= 34 and 15 <= p['spin'] <= 63 and 17 <= p['nod'] <= 37, p)
            for key in ('synodic', 'spin', 'nod'):
                self.assertTrue(0 <= moon['offsets'][key] < p[key])
            self.assertTrue(10 <= moon['tilt_max_degrees'] <= 35)
            self.assertEqual(moon['great_year_days'], math.lcm(p['synodic'], p['spin'], p['nod']))
        coprime = sum(math.gcd(seed_moon(s)['periods']['synodic'], seed_moon(s)['periods']['spin']) == 1 for s in range(40))
        self.assertGreater(coprime, 30, 'redraws should make coprime synodic/spin periods the norm')

    def test_state_and_tide_are_finite_bounded_and_agree_on_integer_days(self):
        moon = seed_moon(42)
        for day in range(0, 400, 7):
            state = moon_state(moon, day)
            self.assertTrue(all(math.isfinite(v) for v in state.values()))
            factors = tide(moon, day)
            self.assertEqual(list(factors), list(KNOWN_SCHOOLS))
            for value in factors.values():
                self.assertTrue(.5 <= value <= 1.8 and math.isfinite(value), value)
            self.assertEqual(tide(moon, float(day)), factors)
        self.assertNotEqual(tide(moon, 0), tide(moon, 1))

    def test_full_moon_lights_the_facing_region_and_new_moon_dims_all(self):
        moon = fixed_moon()
        # Day 0: phase 0 (full), spin 0 (longitude 0 faces the world), nod 0 (no lean).
        # Longitude 0 carries radiant (still) and weave (restless), both at 45 degrees.
        factors = tide(moon, 0)
        for school in ('radiant', 'weave'):
            self.assertGreater(factors[school], 1.2)
        self.assertEqual(factors['radiant'], factors['weave'])
        # Longitude 180 regions are on the far side: unseen, so they ebb to .7.
        for school in ('earth', 'air'):
            self.assertAlmostEqual(factors[school], .7)
        # Day 15: new moon. Nothing is lit, whatever faces the world.
        self.assertTrue(all(abs(v-.7) < 1e-12 for v in tide(moon, 15).values()))
        # Day 5 of the nod (quarter cycle): the still hemisphere leans in by tilt_max,
        # so radiant outranks weave; day 15 of the nod is the reverse lean.
        lean_in = tide(fixed_moon(periods={'synodic': 30, 'spin': 40, 'nod': 20}, offsets={'synodic': 0, 'spin': 0, 'nod': 5}), 0)
        self.assertGreater(lean_in['radiant'], lean_in['weave'])
        lean_out = tide(fixed_moon(offsets={'synodic': 0, 'spin': 0, 'nod': 15}), 0)
        self.assertGreater(lean_out['weave'], lean_out['radiant'])
        # A facing region under a full moon with a favourable lean is a surge.
        self.assertGreater(lean_in['radiant'], 1.6)

    def test_day_state_exposes_the_clock_hooks(self):
        moon = fixed_moon()
        state = day_state(moon, 0)
        self.assertEqual(state['phase_fraction'], 0.)
        self.assertEqual(state['moonrise_hour'], 0.)
        self.assertAlmostEqual(state['illumination'], 1.)
        self.assertEqual(state['elongation_degrees'], 0.)
        state = day_state(moon, 15)
        self.assertAlmostEqual(state['phase_fraction'], .5)
        self.assertAlmostEqual(state['moonrise_hour'], HOURS_PER_DAY/2)
        self.assertAlmostEqual(state['illumination'], 0.)
        self.assertEqual(state['elongation_degrees'], 180.)
        self.assertIn(state['leaning'], ('still', 'restless'))
        self.assertEqual(day_state(moon, 7.5)['phase_fraction'], .25)


class ControlTests(unittest.TestCase):
    def test_overrides_pin_one_cycle_without_moving_the_others(self):
        seeded = seed_moon(42)
        pinned = seed_moon(42, 0, {'synodic': 30, 'spin': 0, 'nod': 0, 'tilt': 20.})
        self.assertEqual(pinned['periods']['synodic'], 30)
        for key in ('spin', 'nod'):
            self.assertEqual(pinned['periods'][key], seeded['periods'][key])
            self.assertEqual(pinned['offsets'][key], seeded['offsets'][key])
        self.assertLess(pinned['offsets']['synodic'], 30)
        self.assertEqual(pinned['tilt_max_degrees'], 20.)
        self.assertEqual(pinned['great_year_days'], math.lcm(30, seeded['periods']['spin'], seeded['periods']['nod']))
        self.assertEqual(pinned['controls'], {'variation': 0, 'overrides': {'synodic': 30, 'tilt': 20.}})
        self.assertNotEqual(seed_moon(42, 1)['periods'], seeded['periods'] if seed_moon(42, 1)['offsets'] == seeded['offsets'] else None)
        for bad in ({'synodic': 5}, {'spin': 64}, {'nod': 16}, {'tilt': 36.}, {'comet': 3}):
            with self.assertRaises(ValueError):
                seed_moon(42, 0, bad)

    def test_moon_query_answers_by_day_or_calendar_time(self):
        from icarus_sim.terrain_astrology import lunar_request
        moon = seed_moon(42)
        world = {'astrology': {'version': 1, 'moon': moon}, 'lunar_almanac': {'reported_year': 3},
                 'magic': {'networks': {s: {'strength': .7} for s in KNOWN_SCHOOLS}}}
        by_calendar = lunar_request({'api_version': 1, 'world': world, 'year': 3, 'month': 2, 'day_of_month': 5, 'hour': 6})
        self.assertEqual(by_calendar['time']['day'], 3 * DAYS_PER_YEAR + DAYS_PER_MONTH + 4 + .25)
        by_day = lunar_request({'api_version': 1, 'world': world, 'day': by_calendar['time']['day']})
        self.assertEqual(by_day['tide'], by_calendar['tide'])
        self.assertEqual((by_day['time']['year'], by_day['time']['month'], by_day['time']['day_of_month'], by_day['time']['hour']), (3, 2, 5, 6.))
        self.assertEqual(by_day['surged_strength'], {s: .7 * by_day['tide'][s] for s in KNOWN_SCHOOLS})
        self.assertEqual(by_day['year_events'], almanac(moon, 3)['events'])
        default = lunar_request({'api_version': 1, 'world': world})
        self.assertEqual(default['time'], {'day': 3 * DAYS_PER_YEAR, 'year': 3, 'month': 1, 'day_of_month': 1, 'hour': 0})
        json.dumps(by_day, allow_nan=False)
        for bad in ({'api_version': 2, 'world': world}, {'api_version': 1, 'world': world, 'day': -1},
                    {'api_version': 1, 'world': world, 'month': 13}, {'api_version': 1, 'world': world, 'day': 3, 'year': 1},
                    {'api_version': 1, 'world': {}}, {'api_version': 1, 'world': world, 'hour': 25}):
            with self.assertRaises(ValueError):
                lunar_request(bad)


class AlmanacTests(unittest.TestCase):
    def test_monthly_means_events_and_alignment(self):
        moon = seed_moon(42)
        report = almanac(moon, 3)
        self.assertEqual(report['reported_year'], 3)
        self.assertEqual(report['now']['day'], 3*DAYS_PER_MONTH*MONTHS_PER_YEAR)
        self.assertEqual(len(report['months']), MONTHS_PER_YEAR)
        start = report['now']['day']
        for m, month in enumerate(report['months']):
            self.assertEqual(month['first_day'], start + m*DAYS_PER_MONTH)
            self.assertEqual(list(month['mean_tide']), list(KNOWN_SCHOOLS))
            for school in KNOWN_SCHOOLS:
                expected = sum(tide(moon, month['first_day']+d)[school] for d in range(DAYS_PER_MONTH))/DAYS_PER_MONTH
                self.assertAlmostEqual(month['mean_tide'][school], expected, places=12)
        days = [e['day'] for e in report['events']]
        self.assertTrue(all(0 <= d < DAYS_PER_MONTH*MONTHS_PER_YEAR for d in days))
        self.assertEqual(report['events'], sorted(report['events'], key=lambda e: (e['day'], e['kind'], e.get('school', ''))))
        kinds = {e['kind'] for e in report['events']}
        self.assertTrue({'full_moon', 'new_moon'} <= kinds, kinds)
        for event in report['events']:
            if event['kind'] == 'surge':
                self.assertGreaterEqual(event['tide'], 1.6)
                self.assertGreaterEqual(tide(moon, start+event['day'])[event['school']], 1.6)
            if event['kind'] == 'hollow_night':
                self.assertTrue(all(v <= .75 for v in tide(moon, start+event['day']).values()))
        alignment = report['next_grand_alignment_day']
        if alignment is not None:
            self.assertGreaterEqual(alignment, start)
            self.assertLess(alignment, start + moon['great_year_days'])
            for key in ('synodic', 'spin', 'nod'):
                self.assertEqual((alignment + moon['offsets'][key]) % moon['periods'][key], 0)
        json.dumps(report, allow_nan=False)

    def test_fixed_moon_alignment_and_hollow_nights(self):
        moon = fixed_moon()
        report = almanac(moon, 0)
        self.assertEqual(report['next_grand_alignment_day'], 0)
        hollow = [e['day'] for e in report['events'] if e['kind'] == 'hollow_night']
        self.assertIn(15, hollow)
        self.assertEqual([e['day'] for e in report['events'] if e['kind'] == 'full_moon'], list(range(0, 360, 30)))


if __name__ == '__main__':
    unittest.main()
