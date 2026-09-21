"""Every role the hero policy declares appears in the cast or in a diagnostic saying why not.

`heroes.summary.dreads` was `0` with no reason attached, and a consumer reading the document
could not tell "this world has no antagonist because it has no beast-ruined city" from "the
Dread role is not implemented" from "the Dread role failed to precipitate". That distinction is
what `PRODUCT-REACHABILITY-REPORT` asks every catalogue to publish and what `key_locations`
already does: every archetype appears in `sites` or in `diagnostics` with a reason.

The measurement that started it, re-taken on the current tree: `Fixtures/sample-world-v1.json`
(seed 42, size 33, generator 16) carries 201 living people across ten roles and **zero Dreads**,
and `dread` does not appear in `rolls` at all. It is not that the role rolled and lost — **no
candidate was ever built**, because all 39 ruins there were destroyed by war, water or air and
none by a beast. Nothing in the block said so.

Built on the hand-built cast world, so no world is generated.
"""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / 'tests'))

import hero_generator
from hero_generator.policy import load_all

import test_hero_generator as cast_fixture
import test_hero_countryside as countryside_fixture


def rows(block):
    return {row['role']: row for row in block['diagnostics']}


class Coverage(unittest.TestCase):

    def test_every_policy_role_appears_in_a_diagnostic(self):
        """Both directions. A role that stops firing must be visible, and an invented one caught."""
        block = hero_generator.generate(countryside_fixture.countryside_world(), cast_fixture.certain())
        declared = set(load_all()['wells']['precipitation'])
        self.assertEqual(set(rows(block)), declared,
                         'the diagnostics and the policy disagree about which roles exist')

    def test_a_role_that_precipitated_nobody_carries_a_reason(self):
        block = hero_generator.generate(countryside_fixture.countryside_world(), cast_fixture.certain())
        for role, row in sorted(rows(block).items()):
            if row['placed'] == 0:
                self.assertTrue(row['reason'].strip(), f'{role} placed nobody and says nothing')

    def test_the_counts_agree_with_the_cast_and_the_ledger(self):
        """A diagnostic that does not reconcile with `people` is a second, wrong answer.

        `camp` is a role in `wells.json`'s `precipitation` that precipitates a **place**, not a
        person: it lands in `camps[]`, and a consumer looking for its four in `people` finds
        none. That is the one row in this table whose output is not a member of the cast, and it
        is asserted here rather than filtered out, because silently dropping it from the
        reconciliation is how the mismatch would stop being visible.
        """
        block = hero_generator.generate(countryside_fixture.countryside_world(), cast_fixture.certain())
        table = rows(block)
        self.assertEqual(table['camp']['placed'], len(block['camps']))
        self.assertEqual(sum(row['placed'] for row in table.values()),
                         len(block['people']) + len(block['dreads']) + len(block['camps']))
        self.assertEqual(sum(row['candidates'] for row in table.values()), len(block['rolls']))
        self.assertEqual(sum(row['candidates'] for row in table.values()),
                         block['summary']['candidates'])
        self.assertEqual(sum(row['placed'] for row in table.values()),
                         block['summary']['precipitated'])


class TheEmptyAntagonist(unittest.TestCase):
    """The card's headline: `dreads` is empty and the block must say why."""

    def test_a_world_with_no_beast_ruin_says_that_is_why_it_has_no_dread(self):
        block = hero_generator.generate(cast_fixture.world(dragon=False), cast_fixture.certain())
        self.assertEqual(block['dreads'], [])
        row = rows(block)['dread']
        self.assertEqual((row['placed'], row['candidates'], row['sources']), (0, 0, 0))
        self.assertIn('beast', row['reason'])
        self.assertIn('no', row['reason'])

    def test_a_world_with_a_beast_ruin_reports_the_input_it_had(self):
        block = hero_generator.generate(cast_fixture.world(), cast_fixture.certain())
        row = rows(block)['dread']
        self.assertEqual(row['sources'], 1, 'the fixture has exactly one dragon-eaten city')
        self.assertEqual(row['candidates'], 1)
        self.assertEqual(row['placed'], len(block['dreads']))

    def test_zero_candidates_and_zero_precipitated_do_not_read_alike(self):
        """The distinction the card is about: nothing to roll is not the same as rolling and losing."""
        never = rows(hero_generator.generate(cast_fixture.world(dragon=False), cast_fixture.certain()))['dread']
        policies = cast_fixture.certain()
        policies['wells']['precipitation']['dread']['base'] = 0.
        policies['wells']['precipitation']['dread']['per_nest_tier'] = 0.
        lost = rows(hero_generator.generate(cast_fixture.world(), policies))['dread']
        self.assertEqual((never['candidates'], lost['candidates']), (0, 1))
        self.assertEqual((never['placed'], lost['placed']), (0, 0))
        self.assertNotEqual(never['reason'], lost['reason'])


class Determinism(unittest.TestCase):

    def test_the_table_is_ordered_and_replays(self):
        world = countryside_fixture.countryside_world()
        first = hero_generator.generate(world, cast_fixture.certain())['diagnostics']
        second = hero_generator.generate(countryside_fixture.countryside_world(),
                                         cast_fixture.certain())['diagnostics']
        self.assertEqual(first, second)
        self.assertEqual([row['role'] for row in first], sorted(row['role'] for row in first))


if __name__ == '__main__':
    unittest.main()
