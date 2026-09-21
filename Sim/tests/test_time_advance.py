import copy
import json
import pathlib
import unittest

from icarus_sim import terrain_time_schedule as schedule
from icarus_sim.terrain_time import (AGE_TURNED, CLOSED_REASONS, LEY_AGE_HIGH, LEY_AGE_LOW,
                                     LEY_YEAR_HIGH, LEY_YEAR_LOW, advance_time_request,
                                     age_gate, cost_estimate, clock)
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


def _unclocked(world):
    """`_state` without `world_clock`, for the refusals that report the clock they read.

    A reported refusal returns the caller's world with the clock it was measured against
    and the report attached, and changes nothing else. A world that has never been ticked
    carries no clock at all, so comparing that key would compare a key against its own
    absence rather than comparing two worlds.
    """
    return _state({k: v for k, v in world.items() if k != 'world_clock'})


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
        self.assertEqual(schedule.ages_for(schedule.elapsed_days({'years': 5000})), 1)
        self.assertEqual(schedule.ages_for(schedule.elapsed_days({'years': 250000})), 50)

    def test_a_century_is_a_long_tick_and_not_an_age_advance(self):
        """An age is five thousand years, so a century is one fiftieth of one.

        `band` returned `AGE` at a hundred years while `AGE_YEARS` was `100.`, so a span
        that size rebuilt every derived layer, regenerated the cast and cleared the board.
        Under `docs/decisions/028-an-age-is-five-thousand-years.md` it moves the living
        layer and nothing else.
        """
        century = schedule.elapsed_days({'years': 100})
        self.assertEqual(schedule.band(century), schedule.LONG)
        self.assertEqual(schedule.ages_for(century), 0)
        self.assertEqual(schedule.plan(0., century)['ages'], 0)
        # And the age band still begins at exactly one age, not at one age plus a day.
        self.assertEqual(schedule.band(schedule.AGE_DAYS), schedule.AGE)
        self.assertEqual(schedule.band(schedule.AGE_DAYS - 1.), schedule.LONG)

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


class WorkCeilingTests(unittest.TestCase):
    """The cost guard keyed on work rather than on band membership. Pure: no world.

    Decision 028 moved the age boundary from a century to five thousand years, which moved
    a fifty-fold cost increase onto the unguarded side of the one guard this module had:
    `cost_estimate`, `age_gate` and the ages-per-request cap are all reached only when the
    band is `AGE`. Below that boundary a span was executed however long it was, and the
    longest such span is now 4,999 years -- 1.8 million cadence steps.
    """

    # A span named in years, deliberately NOT derived from `MAX_TICK_STEPS` by arithmetic.
    # `SDET-CEILING-SENTINELS` records three rejection tests whose sentinel was "one above
    # the current limit": when the limit moved, each sentinel became legal work and a
    # 0.1 s rejection turned into a 48 s generation, with no signal but a slower suite.
    # The precondition is asserted instead, so raising the ceiling past this span fails
    # loudly here rather than quietly ticking a millennium inside a rejection test.
    SENTINEL_YEARS = 1000

    def sentinel_days(self):
        return self.SENTINEL_YEARS * schedule.DAYS_PER_YEAR

    def test_the_sentinel_is_still_outside_the_ceiling(self):
        """The guard on this class's own sentinel, which is the trap that keeps being sprung."""
        from icarus_sim.terrain_time import MAX_TICK_STEPS
        work = schedule.work(0., self.sentinel_days())
        self.assertLess(MAX_TICK_STEPS, work,
                        'MAX_TICK_STEPS has been raised above this class\'s sentinel of %d '
                        'years (%d steps). The rejection tests below now *execute* that '
                        'span instead of refusing it. Choose a new sentinel deliberately; '
                        'do not derive one from the constant.'
                        % (self.SENTINEL_YEARS, work))

    def test_the_counter_and_the_enumerator_agree(self):
        """`work` answers exactly the question `steps` answers, for every span.

        It exists so the guard can answer before the step list is built -- a span just
        under an age is 1.8 million tuples and `plan` used to build a second copy -- and a
        counter that answers a slightly different question than the enumerator is the
        near-miss this repository keeps finding. So it is checked against the enumerator
        rather than against a formula.
        """
        for now in (0., 0.5, 17., 359.9, 1234.5):
            for days in (0., .25, 1., 89., 90., 400., 720., 7200.):
                with self.subTest(now=now, days=days):
                    self.assertEqual(schedule.work(now, days),
                                     len(schedule.steps(now, days)))

    def test_the_plan_still_reports_what_it_always_reported(self):
        """`plan` counts crossings instead of materialising them; the document is identical."""
        for now, days in ((0., 400.), (13.5, 7200.), (1234.5, 90.)):
            with self.subTest(now=now, days=days):
                counts = {}
                for _, name, _ in schedule.steps(now, days):
                    counts[name] = counts.get(name, 0) + 1
                plan = schedule.plan(now, days)
                self.assertEqual(plan['by_cadence'], dict(sorted(counts.items())))
                self.assertEqual(plan['steps'], sum(counts.values()))

    def test_the_ceiling_is_an_absolute_count_and_not_a_share_of_an_age(self):
        """It must not move when the length of an age moves.

        A ceiling written as a fraction of `AGE_DAYS` would re-couple the guard to the band
        boundary, which is the defect this card is about: how much work a box can afford
        does not change when the calendar is redefined. The number is a measurement, so it
        moves only when something is measured again.
        """
        import io
        import pathlib
        import tokenize
        path = pathlib.Path(__file__).resolve().parents[1] / 'icarus_sim' / 'terrain_time.py'
        source = io.StringIO(path.read_text(encoding='utf-8')).readline
        code = [tok for tok in tokenize.generate_tokens(source)
                if tok.type not in (tokenize.COMMENT, tokenize.STRING, tokenize.NL,
                                    tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT)]
        line = next((tok.start[0] for tok in code if tok.string == 'MAX_TICK_STEPS'), None)
        self.assertIsNotNone(line, 'MAX_TICK_STEPS must be a module constant')
        assignment = [tok.string for tok in code if tok.start[0] == line]
        for forbidden in ('AGE_DAYS', 'AGE_YEARS', 'schedule'):
            self.assertNotIn(forbidden, assignment,
                             'the work ceiling must not be derived from the age length')


class LeyDriftCompositionTests(unittest.TestCase):
    """A year-step composed over one whole age must land in the age transition's own band.

    This is the half of `docs/decisions/028-an-age-is-five-thousand-years.md` that is
    silent when it breaks, and it is the reason the age length and the ley bounds are one
    change rather than two. Every individual step stays inside its stated per-year bounds
    while the composition over an age leaves the band entirely: the pair that composes
    correctly over a century is `0.65 ** 0.01`, and over the five thousand years an age now
    lasts that composes to `0.65 ** 50` -- about 2e-10. The magic layer drains to zero
    through ordinary ticking, with nothing out of range anywhere to notice.

    So the exponent is derived from `AGE_YEARS` in `terrain_time` rather than written as a
    literal, and these two tests fail the moment anybody writes it as one. They are pure:
    no world, no clock, no generation.
    """

    def test_the_year_bounds_are_the_age_bounds_taken_to_one_over_an_age(self):
        """The arithmetic, stated directly. Fails at `1/100` with a five-thousand-year age."""
        self.assertAlmostEqual(LEY_YEAR_LOW ** schedule.AGE_YEARS, LEY_AGE_LOW, places=9)
        self.assertAlmostEqual(LEY_YEAR_HIGH ** schedule.AGE_YEARS, LEY_AGE_HIGH, places=9)
        # A year is a smaller move than an age in both directions, never the same one.
        self.assertLess(LEY_AGE_LOW, LEY_YEAR_LOW)
        self.assertLess(LEY_YEAR_LOW, 1.)
        self.assertLess(1., LEY_YEAR_HIGH)
        self.assertLess(LEY_YEAR_HIGH, LEY_AGE_HIGH)

    def test_an_age_of_year_steps_stays_inside_the_age_band(self):
        """The real drift pass, run for one whole age of year steps.

        The arithmetic above could be satisfied by a constant nothing reads. This drives
        `_ley_drift` itself -- the same random walk a ticking world runs, keyed on the same
        absolute year indices -- and asserts both halves of the failure at once: every
        single step is inside its stated per-year bounds, and the product of all of them is
        inside the age's.
        """
        from icarus_sim.terrain_time import _ley_drift

        class Cfg:
            magic_enabled = 1
            seed = 42

        cfg = Cfg()
        start = 1.
        world = {'magic': {'networks': {'weave': {'nodes': [{'id': 'ley-1', 'intensity': start}],
                                                  'edges': []}}}}
        node = world['magic']['networks']['weave']['nodes'][0]
        previous = node['intensity']
        for index in range(1, int(schedule.AGE_YEARS) + 1):
            self.assertTrue(_ley_drift(world, cfg, index), 'the pass must report that it moved')
            ratio = node['intensity'] / previous
            self.assertGreaterEqual(ratio, LEY_YEAR_LOW - 1e-12, 'year %d' % index)
            self.assertLessEqual(ratio, LEY_YEAR_HIGH + 1e-12, 'year %d' % index)
            previous = node['intensity']
        composed = node['intensity'] / start
        self.assertGreaterEqual(composed, LEY_AGE_LOW,
                                'an age of year-steps drained the field below the age band: '
                                '%r, against a floor of %r' % (composed, LEY_AGE_LOW))
        self.assertLessEqual(composed, LEY_AGE_HIGH,
                             'an age of year-steps drove the field above the age band: %r' % composed)


class QuestReasonVocabularyTests(unittest.TestCase):
    """`closed_reason` is a published vocabulary and has exactly one home."""

    def test_the_published_enum_is_the_vocabulary_the_writers_use(self):
        """A token written and not published cannot be branched on by any consumer."""
        root = pathlib.Path(__file__).resolve().parents[2]
        schema = json.loads((root / 'Contracts' / 'schemas' / 'read-quests.schema.json')
                            .read_text(encoding='utf-8'))
        published = schema['$defs']['quest']['properties']['closed_reason']['enum']
        self.assertEqual(sorted(token for token in published if token is not None),
                         sorted(CLOSED_REASONS))
        self.assertIn(None, published, 'a quest that has not closed carries no reason')

    def test_an_age_turning_is_not_a_hook_vanishing(self):
        """Two different facts about why a quest ended, and a player is owed both.

        `hook_gone` is this hook leaving `heroes.quest_hooks` while the world around it
        stands. `age_turned` is five thousand years passing and taking everyone who could
        have offered or populated the quest. A consumer handed one token for both cannot
        tell a player whether their quest went away or their age did.
        """
        self.assertNotEqual(AGE_TURNED, 'hook_gone')
        for token in (AGE_TURNED, 'hook_gone'):
            self.assertIn(token, CLOSED_REASONS, token)

    def test_an_age_turn_does_not_start_a_quest_lifecycle_that_never_began(self):
        """The lifecycle begins when a world is first ticked, not when an age turns.

        `POST /world/quests` refuses a world that has never been advanced, because no
        quests and no quest lifecycle are different facts. An age turn continues a
        lifecycle; it does not start one, and a world that has never carried a board does
        not acquire one by being advanced five thousand years.
        """
        from icarus_sim.terrain_time import _turn_age_board

        class Cfg:
            magic_enabled = 1
            seed = 42

        world = {'heroes': {'status': 'ok', 'people': [],
                            'quest_hooks': [{'hook_id': 'hook-1', 'giver_uid': 'hero-1'}]}}
        _turn_age_board(world, Cfg(), 1800000.)
        self.assertNotIn('quests', world)


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
        """One age exactly, and nothing is advanced until a caller says `commit`."""
        out = self.advance(self.world, {'years': 5000})
        report = out['time_advance']
        self.assertEqual(report['band'], 'age')
        self.assertEqual(report['ages'], 1)
        self.assertFalse(report['committed'])
        self.assertIn('cost_estimate', report)
        self.assertEqual(out['history']['ages'], self.world['history']['ages'])
        # The cap is fifty ages and it is now a quarter of a million years.
        capped = self.advance(self.world, {'years': 250000})
        self.assertEqual(capped['time_advance']['ages'], 50)
        self.assertNotIn('blocked', capped['time_advance'])

    def test_a_century_moves_the_living_layer_and_not_the_ground(self):
        """Decision 028, point 3, against a real world rather than the schedule alone.

        A hundred years used to be an age advance: every derived layer rebuilt, the cast
        regenerated, the board cleared. It is one fiftieth of an age and it is a tick.
        """
        out = self.advance(self.world, {'years': 100})
        self.assertEqual(out['time_advance']['band'], 'long')
        self.assertTrue(out['time_advance']['committed'])
        self.assertEqual(out['history']['ages'], self.world['history']['ages'])
        # Ground and cast are read-only to a tick, however long the tick is.
        for key in ('settlements', 'city_plans', 'humans', 'heroes', 'npcs', 'key_locations'):
            if key in self.world:
                self.assertEqual(out.get(key), self.world.get(key), key)

    def test_an_age_span_commits_when_asked(self):
        out = self.advance(self.world, {'years': 5000}, commit=True)
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
        """One age and thirty days must equal one age, then thirty days.

        The age band floored the span to whole ages and dropped the rest, while still
        reporting the requested elapsed -- a counterexample to the invariant that needed no
        band table, and an operation log that described a move the clock never made.

        The cut is expressed in days rather than years because the band boundary moved with
        `AGE_YEARS`: a hundred and fifty years used to be an age plus fifty and is now a
        `LONG` tick that crosses no age at all. The claim is about a cut that straddles the
        age boundary, so it has to be written against that boundary and not against a
        number that once sat on it.
        """
        start = clock(self.world)['day']
        span = schedule.AGE_DAYS + 30.
        whole = self.advance(self.world, {'days': span}, commit=True)
        self.assertEqual(whole['time_advance']['ages'], 1)
        self.assertAlmostEqual(whole['world_clock']['day'], start + span)
        self.assertAlmostEqual(whole['time_advance']['to_day'], start + span)
        stepped = self.advance(self.advance(self.world, {'years': 5000}, commit=True), {'days': 30})
        self.assertAlmostEqual(stepped['world_clock']['day'], whole['world_clock']['day'])
        # And it is the same world, not merely the same clock: the age turn and the tick
        # after it are both keyed on simulated time, so the call boundary cannot reach them.
        self.assertEqual(_state(whole), _state(stepped))

    def test_an_unbounded_span_is_refused_with_its_estimate(self):
        """A million years is two hundred age rebuilds, not a request to attempt."""
        out = self.advance(self.world, {'years': 1000000}, commit=True)
        report = out['time_advance']
        self.assertFalse(report['committed'])
        self.assertIn('blocked', report)
        self.assertIn('cost_estimate', report['blocked'])
        self.assertEqual(out['history']['ages'], self.world['history']['ages'])

    def test_a_tick_past_the_work_ceiling_is_reported_rather_than_executed(self):
        """The guard the age band always had, on the band a game actually drives.

        Reported and not raised, matching the age gate: a caller that asked for a
        millennium deserves the estimate and the reason together, and an exception throws
        away the more useful half.
        """
        from icarus_sim.terrain_errors import SCHEMA
        from icarus_sim.terrain_time import MAX_TICK_STEPS
        years = WorkCeilingTests.SENTINEL_YEARS
        out = self.advance(self.world, {'years': years})
        report = out['time_advance']
        self.assertFalse(report['committed'])
        self.assertIn('blocked', report)
        self.assertEqual(report['blocked']['schema'], SCHEMA)
        self.assertEqual(report['blocked']['field'], 'elapsed')
        self.assertIn('cost_estimate', report['blocked'])
        # The suggestion must be a span this API accepts, not the ceiling restated as a
        # value for a field that never carried steps -- and sending it straight back must
        # be permitted, which is the only form of "a value that would work" worth the name.
        # So it is sent back, rather than the guard's own condition being restated here.
        from icarus_sim.terrain_errors import CLAMP
        suggestion = report['blocked']['suggestion']
        self.assertEqual(suggestion['kind'], CLAMP)
        suggested = schedule.work(clock(self.world)['day'], suggestion['value']['days'])
        self.assertLessEqual(suggested, MAX_TICK_STEPS)
        # Sending it back *runs* it, so this assertion has a cost, and that cost follows
        # the ceiling. Bounded against a literal as well so raising the ceiling cannot
        # quietly turn a four-second test into an hour-long one -- the SDET-CEILING-SENTINELS
        # shape arriving from the other side, where work grows instead of a rejection
        # becoming work.
        self.assertLessEqual(suggested, 250000,
                             'MAX_TICK_STEPS has been raised far enough that this test now '
                             'ticks a span nobody sized for a test suite; bound it deliberately')
        accepted = self.advance(self.world, {'days': suggestion['value']['days']})
        self.assertTrue(accepted['time_advance']['committed'],
                        'the suggested span must not itself be refused')
        # Both units, because a step is what costs and a year is what a caller asks in.
        self.assertEqual(report['steps'], schedule.work(clock(self.world)['day'],
                                                        years * schedule.DAYS_PER_YEAR))
        self.assertGreater(report['steps'], MAX_TICK_STEPS)
        self.assertEqual(report['elapsed_days'], years * schedule.DAYS_PER_YEAR)
        # Nothing ran. `world_clock` is excluded because the report carries the clock the
        # refusal was measured against, exactly as the age gate's refusal does, and a
        # world that has never been ticked carries no clock at all to compare it with.
        self.assertEqual(_unclocked(out), _unclocked(self.world))
        self.assertEqual(len((out.get('history') or {}).get('operations') or []),
                         len((self.world.get('history') or {}).get('operations') or []))

    def test_the_longest_span_the_long_band_can_hold_is_refused(self):
        """4,999 years: the span decision 028 moved onto the unguarded side of the guard."""
        out = self.advance(self.world, {'years': 4999})
        report = out['time_advance']
        self.assertEqual(report['band'], schedule.LONG)
        self.assertFalse(report['committed'])
        self.assertIn('blocked', report)
        self.assertEqual(_unclocked(out), _unclocked(self.world))

    def test_commit_ticks_a_span_past_the_ceiling_anyway(self):
        """`commit` proceeds, exactly as it does for the age band. The ceiling advises."""
        years = WorkCeilingTests.SENTINEL_YEARS
        out = self.advance(self.world, {'years': years}, commit=True)
        report = out['time_advance']
        self.assertTrue(report['committed'])
        self.assertNotIn('blocked', report)
        self.assertAlmostEqual(out['world_clock']['day'],
                               clock(self.world)['day'] + years * schedule.DAYS_PER_YEAR)
        self.assertEqual(out['history']['operations'][-1]['band'], schedule.LONG)

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
        # And `hook_gone` is what a hook vanishing under a standing world is called. An age
        # turn is a different fact and carries a different reason.
        self.assertNotIn(AGE_TURNED, [q['closed_reason'] for q in after['quests']['quests']])

    def test_an_age_turn_closes_every_open_quest_because_the_age_turned(self):
        """A quest does not cross an age, and not by luck.

        Reaping used to happen by accident: `_quest_step` walks hook ids and an age
        transition regenerates `heroes` wholesale, so most ids vanished and their quests
        closed as `hook_gone`. Most is not all. The regenerated cast re-mints positional
        uids -- `hero-reeve-hamlet-0`, `hero-sovereign-<city uid>` -- as the same string, so
        a quest whose id was minted twice survived pointing at a hook nobody wrote it for:
        the old age's `anchor`, `verb` and `stated_purpose`, the new age's target check, and
        a `giver_uid` naming someone who no longer exists. Measured 2026-09-21: 39 closed,
        10 survived.

        So the assertion is over *every* open quest and is keyed on the age turning, never
        on whether an id happened to disappear.
        """
        ticked = self.advance(self.world, {'days': 30})
        before = [quest for quest in (ticked.get('quests') or {}).get('quests') or []
                  if quest['state'] in ('offered', 'taken')]
        if not before:
            self.skipTest('this world raised no quest hooks')
        out = self.advance(ticked, {'years': 5000}, commit=True)
        board = out['quests']['quests']
        reaped = {entry['quest_id'] for entry in out['quests']['log']
                  if entry.get('event') == AGE_TURNED}
        self.assertEqual(reaped, {quest['quest_id'] for quest in before},
                         'every quest open when the age turned must close because it turned')
        # No survivor, by id or by state. This is the assertion the ten chimeras failed.
        carried = [quest['quest_id'] for quest in board
                   if quest['quest_id'] in {q['quest_id'] for q in before}
                   and quest.get('offered_day') != out['world_clock']['day']]
        self.assertEqual(carried, [], 'a quest outlived the age that raised it')
        # The board is the new age's, rebuilt from the cast this age raised.
        hooks = [hook['hook_id'] for hook in (out['heroes'].get('quest_hooks') or [])]
        self.assertEqual(sorted(quest['quest_id'] for quest in board), sorted(hooks))
        self.assertTrue(board, 'the new age must raise a board of its own')
        for quest in board:
            self.assertEqual(quest['offered_day'], out['world_clock']['day'], quest['quest_id'])
            self.assertNotEqual(quest.get('closed_reason'), AGE_TURNED,
                                'a quest opened by the turn cannot also have been reaped by it')
        # A giver on the new board is somebody this age holds, which is the whole point.
        givers = {person.get('uid') for person in (out['heroes'].get('people') or [])}
        givers |= {person.get('uid') for person in (out['heroes'].get('dreads') or [])}
        givers |= {person.get('uid') for person in ((out.get('npcs') or {}).get('people') or [])}
        unknown = [quest['quest_id'] for quest in board if quest['giver_uid'] not in givers]
        self.assertEqual(unknown, [], 'a rebuilt board names a giver the new age does not hold')


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
