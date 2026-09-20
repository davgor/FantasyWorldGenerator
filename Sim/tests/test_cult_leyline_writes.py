"""What a cult does to the ground it walks, now that the `pending_ley_edits` queue is gone.

History, because it is the reason these assertions are worth pinning. A cult of a hidden
school used to queue its intent into a top-level `pending_ley_edits` block instead of
writing, on the stated grounds that `advance_age_request` refuses any school outside
`KNOWN_SCHOOLS` and a blood cult writing its own node would be refused at the next age
boundary. No applier was ever written for that queue, and the premise turned out to be
false: the gate at `terrain_history.py:741` validates only the caller-supplied
`body['leyline_edits']` of an age-advance request, never the world's own networks, and
`validate_age_world` accepts a world already carrying hidden-school nodes. This pass writes
through `edit_network` directly and never reaches that validator, exactly as the
known-school half always did. So the queue was removed rather than drained.

Three defects died with it, and (b), (c) and the unit test in (a) are the regressions that
keep them dead:

  (a) the queued `intensity` had a different unit from the direct write. On a node at 3.0
      with three shrines, the known path wrote 3.54 (`current * 1.18`, absolute, shrine
      count ignored) and the hidden path queued 0.54 (`DEVOTION_GAIN * shrines`, a gain).
      `edit_network` SETS intensity, so an applier reading the queue the obvious way would
      have cut the node by 82% in the act of deepening it.
  (b) the queue could hold an entry naming no node at all. A claim- or shrine-derived band
      carries no `ley_node_id`; the known path skipped those, the hidden path queued
      `{"id": null}`.
  (c) nothing separated deepening a node from creating one.

The fixtures below are the ones that proved the unit divergence and are kept verbatim.
"""
import unittest

from icarus_sim import terrain_nomad_effects as effects
from icarus_sim.terrain_leyline_history import HIDDEN_SCHOOLS, KNOWN_SCHOOLS

HIDDEN = sorted(HIDDEN_SCHOOLS)
KNOWN = sorted(KNOWN_SCHOOLS)


class Config:
    magic_enabled = True


def band(uid, school, node_id, *, god_id='god-1', age=0, shrines=1):
    """A cultist band as the nomad pass emits one, reduced to what the write-back reads."""
    return {
        'uid': uid, 'classification': 'cultists', 'school': school,
        'god_id': god_id, 'origin': {'age': age},
        'basis': {'ley_node_id': node_id} if node_id is not None else {'claim_id': 'claim-7'},
        'camps': [{'id': f'{uid}-shrine-{i}', 'kind': 'shrine'} for i in range(shrines)],
    }


def world(bands, *, node_intensity=2.):
    """A world with one node per school, so a direct write has somewhere to land."""
    networks = {}
    for school in KNOWN + HIDDEN:
        networks[school] = {'nodes': [{'id': f'ley-{school}-1', 'direction': [0., 1., 0.],
                                       'intensity': node_intensity}],
                            'edges': []}
    return {'magic': {'networks': networks}, 'nomads': {'groups': list(bands)}}


class DirectWriteTests(unittest.TestCase):
    """Hidden and known schools take the same path and the same arithmetic."""

    def test_a_hidden_school_cult_lands_the_same_intensity_as_a_known_one(self):
        """THE unit-divergence regression. Same band, same node, same shrines.

        Before the removal this was 3.54 for `fire` and a queued 0.54 for `blood` - two
        numbers in two units for one operation, and the smaller one would have been
        written absolutely by any applier.
        """
        landed = {}
        for school in (KNOWN[0], HIDDEN[0]):
            result, direct, hidden = effects.apply_cultist_leylines(
                world([band('nomad-1', school, f'ley-{school}-1', shrines=3)],
                      node_intensity=3.),
                Config())
            landed[school] = result['magic']['networks'][school]['nodes'][0]['intensity']
            self.assertEqual((direct, hidden),
                             (1, 0) if school in KNOWN_SCHOOLS else (0, 1))
        self.assertEqual(landed[KNOWN[0]], 3.54)
        self.assertEqual(landed[HIDDEN[0]], 3.54)
        self.assertEqual(landed[KNOWN[0]], landed[HIDDEN[0]])

    def test_the_two_counters_split_by_school_family_and_nothing_is_queued(self):
        result, direct, hidden = effects.apply_cultist_leylines(
            world([band('nomad-1', KNOWN[0], f'ley-{KNOWN[0]}-1'),
                   band('nomad-2', HIDDEN[0], f'ley-{HIDDEN[0]}-1'),
                   band('nomad-3', HIDDEN[1], f'ley-{HIDDEN[1]}-1')]),
            Config())
        self.assertEqual((direct, hidden), (1, 2))
        self.assertNotIn('pending_ley_edits', result)

    def test_no_world_carries_a_pending_ley_edits_block(self):
        """The queue is retired. Its absence is now unconditional, not a branch."""
        for school in (KNOWN[0], HIDDEN[0]):
            for node_id in (f'ley-{school}-1', None, 'ley-nowhere-1'):
                with self.subTest(school=school, node=node_id):
                    result, _, _ = effects.apply_cultist_leylines(
                        world([band('nomad-1', school, node_id)]), Config())
                    self.assertNotIn('pending_ley_edits', result)

    def test_the_ceiling_holds_for_a_hidden_school_too(self):
        """`_clamp_intensity` is what stops a ratcheting node running past the contract.

        It matters more now than it did: this pass runs on every `nomad_request` as well
        as every age advance, so a held node is re-lifted x1.18 per call.
        """
        result, _, hidden = effects.apply_cultist_leylines(
            world([band('nomad-1', HIDDEN[0], f'ley-{HIDDEN[0]}-1')], node_intensity=3.9),
            Config())
        self.assertEqual(hidden, 1)
        self.assertEqual(result['magic']['networks'][HIDDEN[0]]['nodes'][0]['intensity'],
                         effects.INTENSITY_CEILING)


class DeepenNeverCreateTests(unittest.TestCase):
    """Only the corruption API puts a node in a hidden network. A cult deepens one."""

    def test_a_band_whose_basis_names_no_node_writes_nothing(self):
        """The `{"id": null}` regression.

        A claim-derived or shrine-derived band (`terrain_nomads.py:278-286`) has no
        `ley_node_id`. The known path always skipped those; the hidden path queued an
        entry naming nothing, and the `str(e['id'])` in the old sort key was the tell that
        this was known about.
        """
        for school in (KNOWN[0], HIDDEN[0]):
            with self.subTest(school=school):
                before = world([band('nomad-1', school, None)])
                intensities = {s: n['nodes'][0]['intensity']
                               for s, n in before['magic']['networks'].items()}
                result, direct, hidden = effects.apply_cultist_leylines(before, Config())
                self.assertEqual((direct, hidden), (0, 0))
                self.assertEqual({s: n['nodes'][0]['intensity']
                                  for s, n in result['magic']['networks'].items()},
                                 intensities)

    def test_a_band_naming_a_node_that_does_not_exist_creates_nothing(self):
        """The create-vs-deepen invariant, which is what keeps the removal legal.

        `docs/hidden-schools.md` rests on this sentence: corruption is the only thing that
        CREATES a node in a hidden network. If a cult could create one, removing the queue
        really would have broken an invariant.
        """
        for school in (KNOWN[0], HIDDEN[0]):
            with self.subTest(school=school):
                result, direct, hidden = effects.apply_cultist_leylines(
                    world([band('nomad-1', school, 'ley-nowhere-1')]), Config())
                self.assertEqual((direct, hidden), (0, 0))
                self.assertEqual(len(result['magic']['networks'][school]['nodes']), 1)
                self.assertEqual(
                    [n['id'] for n in result['magic']['networks'][school]['nodes']],
                    [f'ley-{school}-1'])


class DeterminismTests(unittest.TestCase):

    def test_two_bands_in_opposite_order_produce_identical_worlds(self):
        """The guarantee the queue's `(school, id)` sort used to carry for the hidden half.

        It survives the removal because the producer already iterates
        `sorted(bands, key=lambda b: b['uid'])`, which covers both halves at once.
        """
        first = band('nomad-9', HIDDEN[1], f'ley-{HIDDEN[1]}-1')
        second = band('nomad-1', HIDDEN[0], f'ley-{HIDDEN[0]}-1')
        forwards, *forward_counts = effects.apply_cultist_leylines(world([first, second]), Config())
        backwards, *backward_counts = effects.apply_cultist_leylines(world([second, first]), Config())
        self.assertEqual(forward_counts, backward_counts)
        self.assertEqual(forwards['magic']['networks'], backwards['magic']['networks'])

    def test_two_bands_on_one_node_compound_in_a_fixed_order(self):
        """Two lifts on the same node is a different number from one, and must be stable."""
        pair = [band('nomad-2', HIDDEN[0], f'ley-{HIDDEN[0]}-1'),
                band('nomad-1', HIDDEN[0], f'ley-{HIDDEN[0]}-1')]
        forwards, _, hidden = effects.apply_cultist_leylines(world(pair), Config())
        backwards, _, _ = effects.apply_cultist_leylines(world(list(reversed(pair))), Config())
        self.assertEqual(hidden, 2)
        self.assertEqual(forwards['magic']['networks'], backwards['magic']['networks'])


if __name__ == '__main__':
    unittest.main()
