"""Creatures that do not hold ground, and the one of them that answers to the calendar.

The pass itself is exercised by `tests/test_world_schema_conformance.py`, which validates
the whole block against `Contracts/schemas/beast-movements.schema.json`. What that cannot
see is behaviour *across time*, because it reads one world at one moment. This module runs
the pass repeatedly against the same world at different years, which is the only way to
tell a swarm that erupts from a swarm that is simply always there.
"""
import unittest

from icarus_sim.terrain_astrology import DAYS_PER_YEAR

PHASE = 16
# A century of years to search for the best and worst forage year. Long enough that the
# extremes of the draw are actually sampled; short enough that finding them is free,
# because `year_forage_factor` touches no world.
WINDOW = 100


def build(seed=42, size=17, **overrides):
    from icarus_sim.terrain_world import generate_request
    return generate_request({'seed': seed, 'overrides': {'size': size, 'phase': PHASE, **overrides}})


class IrruptionTriggerTests(unittest.TestCase):
    """A swarm is normally sparse and occasionally overwhelming.

    Before this, every irruptive group marched in every year, because nothing in the
    generator distinguished one year from another. `world_clock` now does.
    """

    @classmethod
    def setUpClass(cls):
        from icarus_sim.terrain_lab import Config
        from icarus_sim.terrain_beast_movement import year_forage_factor
        cls.world = build()
        cls.cfg = Config(**cls.world['config'])
        factors = {year: year_forage_factor(cls.world, year) for year in range(WINDOW)}
        cls.lean = min(factors, key=lambda year: factors[year])
        cls.fat = max(factors, key=lambda year: factors[year])

    def movements_in(self, year):
        """Re-run the pass with the clock standing at `year`, and return the block."""
        from icarus_sim.terrain_beast_movement import add_beast_movements
        self.world['world_clock'] = {
            'version': 1, 'day': float(year) * DAYS_PER_YEAR,
            'age': len(self.world['history']['ages']), 'epoch_day': 0.,
            'derived_from': 'test'}
        add_beast_movements(self.world, self.cfg)
        return self.world['beast_movements']

    @staticmethod
    def marching(block):
        return {group['uid'] for group in block['groups']
                if group['movement'] == 'irruptive' and group['route_status'] == 'routed'}

    def test_a_swarm_marches_in_a_lean_year_and_stays_put_in_a_fat_one(self):
        """The whole card. A fixture on both sides of the threshold: the leanest and the
        fattest year of a century, so a trigger that fired always and one that fired never
        both go red here rather than passing on whichever year the world happened to be
        standing in."""
        lean = self.movements_in(self.lean)
        lean_marching = self.marching(lean)
        fat = self.movements_in(self.fat)
        fat_marching = self.marching(fat)
        self.assertTrue(lean_marching, 'no swarm marched in the leanest year of a century')
        self.assertGreater(len(lean_marching), len(fat_marching),
                           'the same swarms march in a lean year and a fat one, so the year '
                           'is not deciding anything')
        # The solitary phase is the normal state, so a group that marches in the lean year
        # and not in the fat one must exist rather than merely being implied by the counts.
        self.assertTrue(lean_marching - fat_marching)
        self.assertGreater(fat['solitary'], 0, 'every swarm erupted in the fattest year')

    def test_a_group_that_is_not_swarming_is_solitary_rather_than_stranded(self):
        """Two different facts that shared one word. `stranded` means no ground to march
        to; `solitary` means nothing worth marching for this year."""
        block = self.movements_in(self.fat)
        self.assertEqual(block['routed'] + block['stranded'] + block['solitary'],
                         len(block['groups']))
        for group in block['groups']:
            if group['route_status'] != 'solitary':
                continue
            self.assertEqual(group['movement'], 'irruptive', group['uid'])
            self.assertFalse(group['legs'], group['uid'])
            # It keeps a camp, so the encounter index can still place it: a player can meet
            # the solitary phase, just not a swarm on the march.
            self.assertEqual(len(group['camps']), 1, group['uid'])

    def test_the_year_survives_the_tick_that_asks_about_it(self):
        """The trap this pass sits in. `terrain_time` runs it on a MONTHLY cadence and
        hands it `replace(cfg, seed=child_seed(cfg.seed, 'time-beast_movements', index))`,
        so a year factor drawn from `cfg.seed` would be a different number in every month
        of one year -- twelve different weathers inside a year, and a swarm that formed and
        dissolved with the call rather than with the world."""
        from dataclasses import replace
        from icarus_sim.terrain_tectonics import child_seed
        expected = self.movements_in(self.lean)['year_forage_factor']
        for index in (1, 7, 12):
            stepped = replace(self.cfg, seed=child_seed(self.cfg.seed, 'time-beast_movements', index))
            from icarus_sim.terrain_beast_movement import add_beast_movements
            add_beast_movements(self.world, stepped)
            self.assertEqual(self.world['beast_movements']['year_forage_factor'], expected,
                             'month %d of the same year drew a different year' % index)

    def test_the_clock_decides_the_year_and_a_world_without_one_still_has_a_year(self):
        """A generated world carries no `world_clock` -- it is minted by the first time
        advance -- so the pass reads its founding year instead, which is the same day the
        age lottery already samples."""
        from icarus_sim.terrain_beast_movement import world_year
        from icarus_sim.terrain_astrology import reported_year
        naked = {k: v for k, v in self.world.items() if k != 'world_clock'}
        self.assertEqual(world_year(naked), int(reported_year(naked)[0]))
        self.world['world_clock'] = {'version': 1, 'day': 41.0 * DAYS_PER_YEAR, 'age': 0,
                                     'epoch_day': 0., 'derived_from': 'test'}
        self.assertEqual(world_year(self.world), 41)


if __name__ == '__main__':
    unittest.main()
