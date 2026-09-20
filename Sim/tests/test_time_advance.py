import copy
import json
import pathlib
import unittest

from icarus_sim import terrain_time_schedule as schedule
from icarus_sim.terrain_time import advance_time_request, age_gate, cost_estimate, clock
from icarus_sim.terrain_liveness import liveness, is_present, present, census
from icarus_sim.terrain_villains import claim_influence, FALLEN_CLAIM_INFLUENCE, CLAIM_INFLUENCE_FLOOR


def _state(world):
    """Everything a tick is supposed to determine, without the record of how it got there.

    `timing_ms` is wall clock, and `time_advance` and `history.operations` are the log of
    what was asked -- two calls of fifteen years honestly record two operations. The claim
    under test is that the resulting *world* is the same either way.
    """
    out = {k: v for k, v in world.items() if k not in ('timing_ms', 'time_advance', 'time_api_version')}
    history = dict(out.get('history') or {})
    history.pop('operations', None)
    history.pop('replay', None)
    out['history'] = history
    return json.dumps(out, sort_keys=True, allow_nan=False)


class ScheduleTests(unittest.TestCase):
    """The pure half. No world, no RNG, no clock."""

    def test_elapsed_units(self):
        self.assertAlmostEqual(schedule.elapsed_days({'days': 5}), 5.)
        self.assertAlmostEqual(schedule.elapsed_days({'years': 1}), 360.)
        self.assertAlmostEqual(schedule.elapsed_days({'seconds': 86400}), 1.)
        self.assertAlmostEqual(schedule.elapsed_days({'seconds': 3}), 3. / 86400.)
        for bad in ({}, {'days': 1, 'years': 1}, {'weeks': 1}, {'days': -1}, {'days': float('inf')}, {'days': 'a'}):
            with self.assertRaises(ValueError):
                schedule.elapsed_days(bad)

    def test_bands(self):
        self.assertEqual(schedule.band(schedule.elapsed_days({'seconds': 3})), schedule.INSTANT)
        self.assertEqual(schedule.band(0.), schedule.INSTANT)
        self.assertEqual(schedule.band(1.), schedule.DAY)
        self.assertEqual(schedule.band(89.), schedule.DAY)
        self.assertEqual(schedule.band(90.), schedule.SEASON)
        self.assertEqual(schedule.band(720.), schedule.LONG)
        self.assertEqual(schedule.band(schedule.elapsed_days({'years': 30})), schedule.LONG)
        self.assertEqual(schedule.band(schedule.elapsed_days({'years': 5000})), schedule.AGE)
        self.assertEqual(schedule.ages_for(schedule.elapsed_days({'years': 5000})), 50)

    def test_a_span_runs_what_it_crosses_and_nothing_else(self):
        """Three seconds runs nothing because three seconds crosses nothing.

        The guarantee is a property of the window, not of a band table. It used to be
        enforced by filtering on `band(days)`, which skipped crossings *permanently* when a
        span was cut finer than its band -- see the next test.
        """
        self.assertEqual(schedule.steps(0., schedule.elapsed_days({'seconds': 3})), [])
        # ... but a sub-day span that does step over a day boundary runs that day.
        self.assertEqual([n for _, n, _ in schedule.steps(0.9, 0.2)], ['quests'])

    def test_a_span_cut_finer_than_its_band_still_runs_every_cadence(self):
        """The defect this replaces: a month-at-a-time game never aged its world.

        `steps()` chose the allowed cadence set from the band of *this* call, and the
        window is half-open at the start, so a yearly crossing skipped because one call was
        short was never revisited by any later call. Thirteen monthly ticks ran no ley
        drift, no nomad reclassification, no seasonal food and no villain outlook -- not
        deferred, gone -- and a game ticking by the second advanced nothing at all.
        """
        seen = set()
        now = 0.
        for _ in range(13):
            seen.update(name for _, name, _ in schedule.steps(now, 30.))
            now += 30.
        for name in ('ley_drift', 'nomads', 'seasonal_food', 'villain_outlook'):
            self.assertIn(name, seen, name + ' is never reached by monthly ticks')
        # Sub-day ticks still cross day boundaries rather than standing still forever.
        now, sub = 0., set()
        for _ in range(5):
            sub.update(name for _, name, _ in schedule.steps(now, .5))
            now += .5
        self.assertEqual(sub, {'quests'})

    def test_crossings_are_half_open(self):
        """A step lands in exactly one of two adjacent spans, never both and never neither."""
        first = list(schedule.crossings('encounters', 0., 30.))
        second = list(schedule.crossings('encounters', 30., 30.))
        self.assertEqual(first, [1])
        self.assertEqual(second, [2])
        self.assertEqual(set(first) & set(second), set())

    def test_chunking_does_not_change_the_step_sequence(self):
        """The contract, at the level the schedule can state it alone.

        Thirty years in one call and two calls of fifteen must enumerate the same steps,
        in the same order, with the same indices. Indices are absolute, so this holds for
        any cut of any span.
        """
        year = schedule.DAYS_PER_YEAR

        def accumulating(steps):
            return [step for step in steps if step[1] not in schedule.COALESCED]

        def last_index(steps):
            out = {}
            for _, name, index in steps:
                out[name] = index
            return out

        whole = schedule.steps(0., 30 * year)
        halves = schedule.steps(0., 15 * year) + schedule.steps(15 * year, 15 * year)
        thirds = (schedule.steps(0., 10 * year) + schedule.steps(10 * year, 10 * year)
                  + schedule.steps(20 * year, 10 * year))
        self.assertTrue(whole)
        # A cadence that compounds must execute every one of its steps, in the same order,
        # at the same absolute indices, however the span was cut.
        self.assertEqual(accumulating(whole), accumulating(halves))
        self.assertEqual(accumulating(whole), accumulating(thirds))
        # A cadence that is coalesced runs once per call rather than once per span, so the
        # sequences differ by construction -- what must match is where each one ends,
        # because every earlier run is overwritten by the last.
        self.assertEqual(last_index(whole), last_index(halves))
        self.assertEqual(last_index(whole), last_index(thirds))

    def test_a_wholesale_pass_runs_once_however_long_the_span(self):
        """Thirty years must not rebuild the encounter index three hundred and sixty times.

        Every earlier crossing of a wholesale-replacement pass is overwritten by the last
        one, so only the last is executed -- the same coalescing `advance_age_request`
        does at the end of a multi-age run.
        """
        counts = schedule.plan(0., schedule.elapsed_days({'years': 30}))['by_cadence']
        for name in schedule.COALESCED:
            self.assertEqual(counts.get(name), 1, name)
        # The accumulating cadences are not coalesced and must still run every step.
        self.assertEqual(counts['ley_drift'], 30)
        self.assertEqual(counts['quests'], 30 * 360)

    def test_producers_run_before_consumers(self):
        """`add_encounters` reads the blocks `add_nomads` and `add_beast_movements` write."""
        order = [name for _, name, _ in schedule.steps(0., 400.) if name != 'quests']
        self.assertLess(order.index('nomads'), order.index('nomad_routes'))
        self.assertLess(order.index('nomads'), order.index('encounters'))
        self.assertLess(order.index('beast_movements'), order.index('encounters'))
        self.assertNotIn('quests', schedule.COALESCED)
        self.assertNotIn('ley_drift', schedule.COALESCED)

    def test_steps_are_ordered_by_time_not_by_subsystem(self):
        days = [day for day, _, _ in schedule.steps(0., 400.)]
        self.assertEqual(days, sorted(days))
        names = {name for _, name, _ in schedule.steps(0., 400.)}
        self.assertIn('ley_drift', names)
        self.assertIn('quests', names)


class LivenessTests(unittest.TestCase):
    def test_every_vocabulary(self):
        self.assertEqual(liveness({'status': 'living'}, 'heroes'), 'present')
        self.assertEqual(liveness({'status': 'legend'}, 'heroes'), 'gone')
        self.assertEqual(liveness({'status': 'living'}, 'dreads'), 'present')
        self.assertEqual(liveness({'status': 'alive'}, 'npcs'), 'present')
        self.assertEqual(liveness({'status': 'dead'}, 'npcs'), 'gone')
        self.assertEqual(liveness({'status': 'living'}, 'villains'), 'present')
        self.assertEqual(liveness({'status': 'fallen'}, 'villains'), 'gone')

    def test_absent_status_reads_as_present(self):
        """A record written before its package recorded departure described someone who stood."""
        for block in ('heroes', 'npcs', 'villains', 'dreads'):
            self.assertEqual(liveness({}, block), 'present', block)

    def test_a_block_is_not_a_person(self):
        """The trap: `status` is 'ok'/'failed' on the block and 'living'/'legend' on a person."""
        for block_value in ({'status': 'ok', 'people': []}, {'status': 'failed', 'error': 'x', 'people': []}):
            with self.assertRaises(ValueError):
                liveness(block_value, 'heroes')

    def test_unknown_block_is_a_caller_error(self):
        with self.assertRaises(ValueError):
            liveness({'status': 'living'}, 'nomads')

    def test_agrees_with_is_standing(self):
        from icarus_sim.terrain_villains import is_standing
        for record in ({'status': 'living'}, {'status': 'fallen'}, {}, {'status': None}):
            self.assertEqual(is_present(record, 'villains'), is_standing(record), record)

    def test_present_filters_in_order(self):
        people = [{'uid': 'a', 'status': 'alive'}, {'uid': 'b', 'status': 'dead'}, {'uid': 'c'}]
        self.assertEqual([p['uid'] for p in present(people, 'npcs')], ['a', 'c'])

    def test_census_skips_a_failed_package(self):
        """Zero present people and no package at all are different facts."""
        self.assertEqual(census({'heroes': {'status': 'failed', 'error': 'x'}}), {})
        counts = census({'npcs': {'status': 'ok', 'people': [{'status': 'alive'}, {'status': 'dead'}]}})
        self.assertEqual(counts['npcs'], {'present': 1, 'gone': 1})


class ClaimDecayTests(unittest.TestCase):
    def test_decays_and_floors(self):
        self.assertEqual(claim_influence(0), FALLEN_CLAIM_INFLUENCE)
        self.assertLess(claim_influence(1), claim_influence(0))
        self.assertLess(claim_influence(3), claim_influence(2))
        self.assertEqual(claim_influence(50), 0.)
        for age in range(0, 20):
            value = claim_influence(age)
            self.assertTrue(value == 0. or value >= CLAIM_INFLUENCE_FLOOR)

    def test_the_decay_reaches_its_only_consumer(self):
        """The seed-visible half: `influence` must actually scale the cultist gate.

        `terrain_nomads._gate_cultists` is the sole reader of the field. Asserting the
        stamped number alone would prove the record changed and nothing about the world.
        """
        from icarus_sim import terrain_nomads as nomads
        direction = (1., 0., 0.)
        rule = {'min_ley_intensity': 99., 'ley_reach_spacings': 0.,
                'shrine_reach_spacings': 0., 'claim_reach_spacings': 10.}
        world = {'religion': {'gods': [{'id': 'god-test', 'schools': ['umbral']}]}}

        def weight(influence):
            claim = {'villain': {'school': 'umbral', 'tier': 2., 'uid': 'v-1'},
                     'claim': {'id': 'c-1', 'influence': influence}}
            g = {'ley': [], 'shrines': [], 'claims': [(direction, 'c-1', claim)],
                 'radius': 1000., 'spacing': 100.}
            got = nomads._gate_cultists({'direction': direction}, g, rule, world)
            return got[0] if got else None

        living = weight(1.)
        self.assertIsNotNone(living, 'the gate must fire on a claim at zero distance')
        just_fallen = weight(claim_influence(0))
        self.assertLess(just_fallen, living)
        older = weight(claim_influence(3))
        self.assertLess(older, just_fallen)
        # Past the floor the claim stops steering the gate at all.
        self.assertEqual(weight(claim_influence(50)), 0.)

    def test_a_living_holder_is_untouched(self):
        """Negative means "has not fallen"; a standing claim presses at full strength."""
        self.assertEqual(claim_influence(-1), 1.)


class AgeBandTests(unittest.TestCase):
    def test_the_gate_is_whatever_the_age_boundary_actually_refuses(self):
        """`age_gate` must ask the real gate, never restate it.

        It used to hard-code `size > 257` and attribute it to `validate_age_world` -- a
        ceiling that had already been raised to 1025, in a check that never contained the
        number. The whole 258..1025 band was refused a span it would have advanced, and a
        caller debugging it would have found nothing at the named location.
        """
        from icarus_sim.terrain_history import validate_age_world
        source = pathlib.Path(validate_age_world.__code__.co_filename).read_text(encoding='utf-8')
        self.assertNotIn('257', source, 'the age boundary no longer has a 257 ceiling')
        # Scan executable code only. 257 legitimately appears in a recorded cost basis and
        # in the comment explaining this very defect; what must never come back is a
        # comparison against it, which is how the stale ceiling was written.
        import io, tokenize
        path = pathlib.Path(__file__).resolve().parents[1] / 'icarus_sim' / 'terrain_time.py'
        code = ''.join(
            tok.string + ' ' for tok in
            tokenize.generate_tokens(io.StringIO(path.read_text(encoding='utf-8')).readline)
            if tok.type not in (tokenize.COMMENT, tokenize.STRING))
        self.assertNotIn('257', code, 'terrain_time must not restate a grid ceiling in code')

    def test_the_gate_reports_a_real_refusal_as_a_document(self):
        """A world the age boundary refuses is reported, with the envelope, not raised."""
        from icarus_sim.terrain_errors import SCHEMA
        gate = age_gate({'not': 'a world'})
        self.assertIsNotNone(gate)
        self.assertEqual(gate['schema'], SCHEMA)
        self.assertEqual(gate['gate'], 'terrain_history.validate_age_world')

    def test_estimate_says_whether_it_was_measured(self):
        unmeasured = cost_estimate({'config': {'size': 257}}, 50)
        self.assertFalse(unmeasured['measured'])
        self.assertEqual(unmeasured['ages'], 50)
        self.assertGreater(unmeasured['total_seconds'], unmeasured['per_age_seconds'])
        measured = cost_estimate({'config': {'size': 129}, 'timing_ms': {'age_advance_total': 4000.}}, 2)
        self.assertTrue(measured['measured'])
        self.assertAlmostEqual(measured['per_age_seconds'], 4.)


class WorldTimeTests(unittest.TestCase):
    """The half that needs a world. One size-17 world, generated once."""

    @classmethod
    def setUpClass(cls):
        from icarus_sim.terrain_world import generate_request
        cls.world = generate_request({'recipe_version': 3, 'seed': 42, 'overrides': {'size': 17}})

    def advance(self, world, elapsed, **extra):
        return advance_time_request({'api_version': 1, 'world': world, 'elapsed': elapsed, **extra})

    def test_clock_is_derived_from_the_founding_year(self):
        now = clock(self.world)
        self.assertEqual(now['version'], 1)
        self.assertGreaterEqual(now['day'], 0.)
        self.assertEqual(now['age'], len(self.world['history']['ages']))

    def test_three_seconds_changes_nothing_seeded(self):
        out = self.advance(self.world, {'seconds': 3})
        self.assertEqual(out['time_advance']['band'], 'instant')
        self.assertEqual(out['time_advance']['steps'], 0)
        for key in ('settlements', 'ruins', 'layers', 'beast_nests', 'encounters', 'heroes', 'npcs'):
            if key in self.world:
                self.assertEqual(out.get(key), self.world.get(key), key)
        self.assertGreater(out['world_clock']['day'], clock(self.world)['day'])

    def test_the_callers_world_is_never_touched(self):
        for elapsed in ({'seconds': 3}, {'days': 30}, {'years': 3}):
            before = json.dumps(self.world, sort_keys=True, allow_nan=False)
            self.advance(self.world, elapsed)
            self.assertEqual(json.dumps(self.world, sort_keys=True, allow_nan=False), before, elapsed)

    def test_an_instant_is_cheap(self):
        """The band's point is that a moment costs nothing, so it must not copy the world.

        A full deep copy grows with the square of the grid and a game asking what time it
        is cannot pay it. Asserted as a ratio against a day-band call rather than as a wall
        time, so a slow machine does not fail it.
        """
        import time
        start = time.perf_counter()
        self.advance(self.world, {'seconds': 3})
        instant = time.perf_counter() - start
        start = time.perf_counter()
        self.advance(self.world, {'days': 30})
        day = time.perf_counter() - start
        self.assertLess(instant, day / 4., f'instant {instant:.3f}s vs day {day:.3f}s')

    def test_same_span_cut_differently_is_the_same_world(self):
        """The contract in one assertion, over a real world.

        Thirty days once, versus fifteen and fifteen. The RNG domain is keyed by simulated
        time, so the cut cannot reach the result.
        """
        whole = self.advance(self.world, {'days': 30})
        first = self.advance(self.world, {'days': 15})
        second = self.advance(first, {'days': 15})
        self.assertEqual(_state(whole), _state(second))
        self.assertEqual(whole['world_clock'], second['world_clock'])

    def test_a_year_in_four_seasons_is_a_year(self):
        whole = self.advance(self.world, {'years': 1})
        stepped = self.world
        for _ in range(4):
            stepped = self.advance(stepped, {'days': 90})
        self.assertEqual(_state(whole), _state(stepped))

    def test_operations_record_each_call(self):
        once = self.advance(self.world, {'days': 30})
        twice = self.advance(self.advance(self.world, {'days': 15}), {'days': 15})
        self.assertEqual(len(once['history']['operations']) + 1, len(twice['history']['operations']))

    def test_a_persisted_world_without_timings_can_tick(self):
        """The document a real consumer has: the CLI strips `timing_ms` to keep it reproducible."""
        persisted = copy.deepcopy(self.world)
        persisted.pop('timing_ms', None)
        out = self.advance(persisted, {'days': 30})
        self.assertEqual(out['time_advance']['band'], 'day')

    def test_quests_open_and_expire(self):
        out = self.advance(self.world, {'days': 30})
        quests = out.get('quests')
        if not quests or not quests['quests']:
            self.skipTest('this world raised no quest hooks')
        self.assertTrue(all(q['state'] in ('offered', 'expired') for q in quests['quests']))
        self.assertTrue(all(q['expires_day'] > q['offered_day'] for q in quests['quests']))
        # Long enough that every offer outlives its window.
        later = self.advance(out, {'years': 10})
        self.assertTrue(all(q['state'] != 'offered' for q in later['quests']['quests']))

    def test_a_resolution_closes_a_quest_and_the_world_does_not_invent_one(self):
        out = self.advance(self.world, {'days': 30})
        quests = (out.get('quests') or {}).get('quests') or []
        open_quests = [q for q in quests if q['state'] == 'offered']
        if not open_quests:
            self.skipTest('this world raised no quest hooks')
        quest_id = open_quests[0]['quest_id']
        resolved = self.advance(out, {'days': 1},
                                resolutions=[{'quest_id': quest_id, 'outcome': 'completed'}])
        closed = {q['quest_id']: q for q in resolved['quests']['quests']}[quest_id]
        self.assertEqual(closed['state'], 'completed')
        self.assertEqual(closed['closed_reason'], 'resolved')
        with self.assertRaises(ValueError):
            self.advance(resolved, {'days': 1},
                         resolutions=[{'quest_id': quest_id, 'outcome': 'failed'}])
        with self.assertRaises(ValueError):
            self.advance(resolved, {'days': 1},
                         resolutions=[{'quest_id': 'no-such-quest', 'outcome': 'failed'}])

    def test_ley_base_field_only_moves_on_a_year_step(self):
        if not self.world['config'].get('magic_enabled', 1):
            self.skipTest('magic disabled')
        base = self.world['magic']['networks']
        month = self.advance(self.world, {'days': 30})['magic']['networks']
        for name, net in base.items():
            self.assertEqual([n['intensity'] for n in month[name]['nodes']],
                             [n['intensity'] for n in net['nodes']], name)
        year = self.advance(self.world, {'years': 2})['magic']['networks']
        moved = any([n['intensity'] for n in year[name]['nodes']] != [n['intensity'] for n in net['nodes']]
                    for name, net in base.items() if net['nodes'])
        self.assertTrue(moved, 'a two-year span must drift the base ley field')

    def test_the_surge_tracks_the_clock(self):
        if 'magic' not in self.world:
            self.skipTest('magic disabled')
        out = self.advance(self.world, {'days': 17})
        self.assertAlmostEqual(out['magic']['lunar_surge']['day'], out['world_clock']['day'])

    def test_five_thousand_years_is_an_age_advance_and_says_so(self):
        out = self.advance(self.world, {'years': 5000})
        report = out['time_advance']
        self.assertEqual(report['band'], 'age')
        self.assertEqual(report['ages'], 50)
        self.assertFalse(report['committed'])
        self.assertIn('cost_estimate', report)
        self.assertEqual(out['history']['ages'], self.world['history']['ages'])

    def test_an_age_span_commits_when_asked(self):
        out = self.advance(self.world, {'years': 100}, commit=True)
        self.assertEqual(out['time_advance']['band'], 'age')
        self.assertTrue(out['time_advance']['committed'])
        self.assertEqual(len(out['history']['ages']), len(self.world['history']['ages']) + 1)
        self.assertEqual(out['world_clock']['day'], clock(self.world)['day'] + schedule.AGE_DAYS)

    def test_new_blocks_are_registered_as_state(self):
        """A top-level block missing from STATE_KEYS is shown at every earlier stage.

        `materialize_stage` builds a stage from every key *not* in `STATE_KEYS`, and the lab
        does the same with its own list, so omitting one does not raise -- it silently
        reports the final state as if it had always been there. `docs/conformance/nomads.md`
        documents this exact failure for the same list.
        """
        from icarus_sim.terrain_history import STATE_KEYS, materialize_stage
        import pathlib
        for key in ('world_clock', 'quests'):
            self.assertIn(key, STATE_KEYS, key)
        ticked = self.advance(self.world, {'days': 30})
        if not ticked.get('build_stages'):
            self.skipTest('this world carries no build stages')
        early = materialize_stage(ticked, 5)
        for key in ('world_clock', 'quests'):
            self.assertNotIn(key, early, 'stage 5 must not carry ' + key)
        # The lab keeps its own copy of the list and is just as silent when it drifts.
        lab = (pathlib.Path(__file__).resolve().parents[2] / 'tools' / 'terrain_lab.html')
        if lab.exists():
            text = lab.read_text(encoding='utf-8')
            marker = text.split('historyStateKeys=[', 1)[1].split('];', 1)[0]
            for key in ('world_clock', 'quests'):
                self.assertIn("'" + key + "'", marker, 'lab stage list is missing ' + key)

    def test_a_year_of_monthly_ticks_matches_one_yearly_tick(self):
        """Cross-band chunk independence: the case the band filter used to break.

        Twelve monthly calls and one yearly call cross the same boundaries, so they must
        arrive at the same world. Before the fix the monthly path never ran ley drift,
        nomads, seasonal food or the villain outlook at all.
        """
        whole = self.advance(self.world, {'years': 1})
        stepped = self.world
        for _ in range(12):
            stepped = self.advance(stepped, {'days': 30})
        self.assertEqual(_state(whole), _state(stepped))

    def test_an_age_span_with_a_remainder_keeps_the_remainder(self):
        """`advance(150y)` must equal `advance(100y)` then `advance(50y)`.

        The age band floored the span to whole ages and dropped the rest, while still
        reporting the requested elapsed -- a counterexample to the invariant that needed no
        band table, and an operation log that described a move the clock never made.
        """
        start = clock(self.world)['day']
        whole = self.advance(self.world, {'years': 150}, commit=True)
        self.assertAlmostEqual(whole['world_clock']['day'], start + 150 * schedule.DAYS_PER_YEAR)
        self.assertAlmostEqual(whole['time_advance']['to_day'], start + 150 * schedule.DAYS_PER_YEAR)
        stepped = self.advance(self.advance(self.world, {'years': 100}, commit=True), {'years': 50})
        self.assertAlmostEqual(stepped['world_clock']['day'], whole['world_clock']['day'])

    def test_an_unbounded_span_is_refused_with_its_estimate(self):
        """A million years is ten thousand age rebuilds, not a request to attempt."""
        out = self.advance(self.world, {'years': 1000000}, commit=True)
        report = out['time_advance']
        self.assertFalse(report['committed'])
        self.assertIn('blocked', report)
        self.assertIn('cost_estimate', report['blocked'])
        self.assertEqual(out['history']['ages'], self.world['history']['ages'])

    def test_a_quest_whose_hook_disappears_is_closed(self):
        """The reaper walked hooks, so a quest whose hook vanished was immortal.

        An age transition regenerates `heroes` wholesale, so that was most of the board,
        every age, growing without bound.
        """
        out = self.advance(self.world, {'days': 30})
        quests = (out.get('quests') or {}).get('quests') or []
        if not quests:
            self.skipTest('this world raised no quest hooks')
        stripped = copy.deepcopy(out)
        stripped['heroes']['quest_hooks'] = []
        after = self.advance(stripped, {'days': 2})
        self.assertTrue(after['quests']['quests'], 'the records must survive')
        self.assertTrue(all(q['state'] != 'offered' for q in after['quests']['quests']))
        self.assertIn('hook_gone', [q['closed_reason'] for q in after['quests']['quests']])

    def test_the_nomad_write_backs_are_reapplied_when_the_bands_are(self):
        """`add_nomads` replaces the block wholesale, discarding `nomads.effects`."""
        out = self.advance(self.world, {'years': 1})
        if 'nomads' not in out:
            self.skipTest('this world raised no nomads')
        self.assertIn('effects', out['nomads'],
                      'a re-rolled nomad population must carry its own write-backs')

    def test_rejects_a_malformed_request(self):
        for body in ({'api_version': 2, 'world': self.world, 'elapsed': {'days': 1}},
                     {'api_version': 1, 'world': self.world},
                     {'api_version': 1, 'world': self.world, 'elapsed': {'days': 1}, 'nope': 1},
                     {'api_version': 1, 'world': self.world, 'elapsed': {'days': 1}, 'commit': 'yes'}):
            with self.assertRaises(ValueError):
                advance_time_request(body)

    def test_a_refusal_carries_the_envelope(self):
        """Every refusal at this boundary names the field, the value and what would work."""
        from icarus_sim.terrain_errors import RequestError
        cases = [
            ({'api_version': 2, 'world': self.world, 'elapsed': {'days': 1}}, 'api_version'),
            ({'api_version': 1, 'world': self.world, 'elapsed': {'days': 1}, 'nope': 1}, 'nope'),
            ({'api_version': 1, 'world': self.world, 'elapsed': {'days': 1}, 'commit': 'yes'}, 'commit'),
            ({'api_version': 1, 'world': self.world, 'elapsed': {'weeks': 1}}, 'elapsed'),
            ({'api_version': 1, 'world': self.world, 'elapsed': {'days': -1}}, 'elapsed.days'),
            ({'api_version': 1, 'world': self.world, 'elapsed': {'days': 1},
              'resolutions': [{'quest_id': 'nope', 'outcome': 'flourished'}]}, 'outcome'),
        ]
        for body, field in cases:
            with self.assertRaises(RequestError, msg=field) as caught:
                advance_time_request(body)
            document = caught.exception.document()
            self.assertEqual(document['field'], field, document)
            self.assertIn('suggestion', document)
            self.assertIn(document['code'],
                          ('INVALID_INPUT', 'UNSUPPORTED_VERSION', 'STATE_CAPACITY'))
        # An api_version this producer does not speak is not worth resending.
        with self.assertRaises(RequestError) as caught:
            advance_time_request({'api_version': 2, 'world': self.world, 'elapsed': {'days': 1}})
        self.assertFalse(caught.exception.document()['retry'])

    def test_resolving_a_closed_quest_is_refused_by_the_world_not_by_validation(self):
        from icarus_sim.terrain_errors import RequestError
        out = self.advance(self.world, {'days': 30})
        open_quests = [q for q in (out.get('quests') or {}).get('quests') or [] if q['state'] == 'offered']
        if not open_quests:
            self.skipTest('this world raised no quest hooks')
        quest_id = open_quests[0]['quest_id']
        resolved = self.advance(out, {'days': 1},
                                resolutions=[{'quest_id': quest_id, 'outcome': 'completed'}])
        with self.assertRaises(RequestError) as caught:
            self.advance(resolved, {'days': 1},
                         resolutions=[{'quest_id': quest_id, 'outcome': 'failed'}])
        document = caught.exception.document()
        self.assertEqual(document['field'], 'quest_id')
        self.assertEqual(document['expected'], {'refused_by': 'world state'})


if __name__ == '__main__':
    unittest.main()
