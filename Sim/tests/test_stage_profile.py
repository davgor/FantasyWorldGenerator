"""The stage profiler measures a generation without changing it.

A profiler earns its place by being invisible in the output and honest in the input. The
two failure modes worth a test are opposite:

- it perturbs the world, so the numbers describe a run nobody else will ever have;
- it stops measuring something -- a pass gets renamed, the wrapper no longer attaches --
  and the missing cost reads as an improvement rather than as a gap.

`test_a_profiled_world_equals_an_unprofiled_one` pins the first. `test_every_named_target_exists`
pins the second, and it is the one that fails when somebody renames a pass: that is the
point, because a renamed target is exactly the case where the report would otherwise go
quietly wrong.

Size 5 rather than the usual 17: this asserts the shape of the measurement, not the cost
of a world, and 25 cells is a whole sixteen-stage generation in about a second.
"""

import unittest

from icarus_sim import terrain_profile
from icarus_sim.terrain_history import STAGES

SIZE = 5
PHASE = 16


def build():
    from icarus_sim.terrain_world import generate_request
    return generate_request({'seed': 42, 'overrides': {'size': SIZE, 'phase': PHASE}})


def without_timings(value):
    from fantasy_world_generator.cli import _without_timings
    return _without_timings(value)


class StageProfile(unittest.TestCase):

    def test_a_profiled_world_equals_an_unprofiled_one(self):
        """Every wrapper is a pass-through, so the world is the same world.

        Timings are excluded because they are wall clock and differ between any two runs
        of one seed -- the same equality `cli._without_timings` exists to give.
        """
        plain = build()
        with terrain_profile.profile_run():
            profiled = build()
        self.assertEqual(without_timings(plain), without_timings(profiled),
                         'profiling changed the generated world')

    def test_every_stage_is_recorded_once_in_order(self):
        with terrain_profile.profile_run() as run:
            build()
        report = run.report()
        self.assertEqual([s['stage'] for s in report['stages']], list(range(1, PHASE + 1)))
        self.assertEqual([s['title'] for s in report['stages']], list(STAGES[:PHASE]))
        for stage in report['stages']:
            self.assertGreaterEqual(stage['wall_ms'], 0.)
            # The split is exhaustive: a stage is its body plus its snapshot capture and
            # nothing else, so a reader can price the bookkeeping separately.
            self.assertAlmostEqual(stage['body_ms'] + stage['capture_ms'], stage['wall_ms'],
                                   places=3)

    def test_every_named_target_exists(self):
        """A target that cannot be found is a hole in the report, not a free pass."""
        with terrain_profile.profile_run() as run:
            build()
        self.assertEqual(run.report()['missing_targets'], [],
                         'a step named in STEP_TARGETS no longer exists; the report would '
                         'hide its cost inside a caller rather than naming it')

    def test_self_time_never_exceeds_total_time(self):
        """Nested steps are subtracted once, so self <= total and neither goes negative."""
        with terrain_profile.profile_run() as run:
            build()
        recorded = run.report()['steps']
        self.assertTrue(recorded, 'no steps were recorded at all')
        for record in recorded:
            self.assertGreaterEqual(record['self_ms'], -1e-6, record['label'])
            self.assertLessEqual(record['self_ms'], record['total_ms'] + 1e-6, record['label'])
            self.assertGreaterEqual(record['calls'], 1, record['label'])

    def test_wrappers_are_removed_when_the_block_closes(self):
        from icarus_sim import city_planner
        before = city_planner.fill_cities
        with terrain_profile.profile_run():
            self.assertIsNot(city_planner.fill_cities, before, 'the wrapper never attached')
        self.assertIs(city_planner.fill_cities, before, 'a wrapper outlived its profile')
        self.assertIsNone(terrain_profile.active())

    def test_a_failed_run_still_restores_the_wrappers(self):
        from icarus_sim import city_planner
        before = city_planner.fill_cities
        with self.assertRaises(ValueError):
            with terrain_profile.profile_run():
                raise ValueError('the generation blew up')
        self.assertIs(city_planner.fill_cities, before)
        self.assertIsNone(terrain_profile.active())

    def test_profiles_refuse_to_nest(self):
        """Two open runs would share one stage pointer and interleave two step stacks."""
        with terrain_profile.profile_run():
            with self.assertRaises(RuntimeError):
                with terrain_profile.profile_run():
                    pass
        self.assertIsNone(terrain_profile.active())

    def test_the_report_names_the_code_it_measured(self):
        """A cost figure against an unnamed tree cannot be told from one against another.

        The shared working tree is where this bites: a module rewritten after a run leaves
        the report reading as though it described the new one.
        """
        with terrain_profile.profile_run() as run:
            build()
        subject = run.report()['subject']
        self.assertIn('Sim/icarus_sim/terrain_nests.py', subject['modules'])
        self.assertIn('Sim/icarus_sim/city_planner.py', subject['modules'])
        self.assertEqual(len(subject['combined']), 16)
        # Every measured module is named, so a reader can tell which ones moved.
        self.assertEqual(len(subject['modules']),
                         len({m for m, _ in terrain_profile.STEP_TARGETS}))

    def test_the_profile_is_not_written_into_the_world(self):
        """The report is returned to the caller; the interchange document is untouched."""
        with terrain_profile.profile_run():
            world = build()
        self.assertNotIn('stage_profile', world)
        self.assertNotIn('stages', world.get('timing_ms', {}))


if __name__ == '__main__':
    unittest.main()
