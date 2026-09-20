"""The `pending_ley_edits` round trip: the half that is written, and the half that is not.

A cult of a hidden school cannot write its own leyline edit -- `advance_age_request`
refuses any school outside `KNOWN_SCHOOLS` -- so it queues the intent into a top-level
`pending_ley_edits` block for "the corruption pass" to drain. That contract was agreed
with a session that has since closed and has never been exercised, because the four
hidden schools are locked at zero occurrence until a player unlocks one, so no generated
world has ever put an entry in the queue.

`NOMAD-CORRUPTION-CONTRACT.md` names the way out and this module takes it: hand-construct
the world rather than wait for one. That turns the producer's contract from unexercised
into tested, and it turns "nobody has observed an applier" into a stated result.

The consequence of never running it: `tests/test_world_schema_conformance.py:247` loops
over `pending_ley_edits` asserting each entry is a hidden school with a bounded intensity.
On every world that has ever been generated the queue is absent, so that loop body has
never executed and the branch immediately below it -- `assertNotIn('pending_ley_edits',
...)` -- is the only one that has. The assertions in `QueuedIntentTests` are those
assertions, finally run against an entry that exists.

`ApplierContractTests` is expected to fail. It is the acceptance test for the card's
"Next action", and it will pass unchanged the day an applier lands.
"""
import unittest
from pathlib import Path

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
        'basis': {'ley_node_id': node_id},
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


class QueuedIntentTests(unittest.TestCase):
    """The producer's half of the contract, run for the first time against a real entry."""

    def setUp(self):
        self.school = HIDDEN[0]
        self.node = f'ley-{self.school}-1'
        self.world = world([band('nomad-1', self.school, self.node)])
        self.result, self.direct, self.queued = effects.apply_cultist_leylines(self.world, Config())

    def test_a_hidden_school_cult_queues_its_intent_instead_of_writing_it(self):
        self.assertEqual((self.direct, self.queued), (0, 1))
        self.assertEqual(len(self.result['pending_ley_edits']), 1)
        # And the network it wanted is untouched: queuing is not a partial write.
        node = self.result['magic']['networks'][self.school]['nodes'][0]
        self.assertEqual(node['intensity'], 2.)

    def test_a_queued_entry_carries_every_field_the_contract_names(self):
        entry = self.result['pending_ley_edits'][0]
        self.assertEqual(set(entry), {'school', 'kind', 'id', 'intensity', 'requested_by',
                                      'god_id', 'age'})
        self.assertEqual(entry['school'], self.school)
        self.assertEqual(entry['requested_by'], 'nomad-1')
        self.assertEqual(entry['god_id'], 'god-1')
        self.assertEqual(entry['age'], 0)

    def test_only_a_hidden_school_ever_reaches_the_queue(self):
        """The known schools are written directly, which is the reason the queue exists.

        This is `test_world_schema_conformance.py:248` with something in the list.
        """
        for entry in self.result['pending_ley_edits']:
            self.assertNotIn(entry['school'], KNOWN_SCHOOLS, entry)

    def test_a_queued_intensity_stays_inside_the_published_bounds(self):
        """`edit_network` refuses anything outside 0..4, so an out-of-range queue entry
        would be a write that can only fail at the moment it is finally applied."""
        for entry in self.result['pending_ley_edits']:
            self.assertGreaterEqual(entry['intensity'], 0., entry)
            self.assertLessEqual(entry['intensity'], effects.INTENSITY_CEILING, entry)

    def test_an_endpoint_is_a_node_id_and_never_an_index(self):
        """The contract calls this out because `depart_god` had the index bug.

        A node removed between write and apply renumbers every later entry, so an index
        stored now names something else by the time the applier reads it.
        """
        entry = self.result['pending_ley_edits'][0]
        self.assertIsInstance(entry['id'], str)
        self.assertEqual(entry['id'], self.node)

    def test_a_known_school_cult_writes_directly_and_queues_nothing(self):
        known = KNOWN[0]
        result, direct, queued = effects.apply_cultist_leylines(
            world([band('nomad-1', known, f'ley-{known}-1')]), Config())
        self.assertEqual((direct, queued), (1, 0))
        self.assertNotIn('pending_ley_edits', result)
        self.assertGreater(result['magic']['networks'][known]['nodes'][0]['intensity'], 2.)

    def test_the_queue_is_ordered_by_school_and_id_whatever_order_the_bands_arrive_in(self):
        """Two bands requesting in a different order must not make two different worlds.

        The producer's half of that guarantee. The applier's half is the contract's, and
        `ApplierContractTests` is where it would be checked if an applier existed.
        """
        first = band('nomad-9', HIDDEN[1], f'ley-{HIDDEN[1]}-1')
        second = band('nomad-1', HIDDEN[0], f'ley-{HIDDEN[0]}-1')
        forwards, _, _ = effects.apply_cultist_leylines(world([first, second]), Config())
        backwards, _, _ = effects.apply_cultist_leylines(world([second, first]), Config())
        self.assertEqual(forwards['pending_ley_edits'], backwards['pending_ley_edits'])
        keys = [(e['school'], str(e['id'])) for e in forwards['pending_ley_edits']]
        self.assertEqual(keys, sorted(keys))


class ApplierContractTests(unittest.TestCase):
    """Expected to fail: nothing in the simulation reads the queue.

    `NOMAD-CORRUPTION-CONTRACT.md` asks someone to "confirm against `terrain_corruption`
    whether it implements this contract". This is that confirmation, as a test rather
    than as a sentence, so the answer cannot go stale.

    Acceptance, for whoever writes the applier -- this test passes when all of it holds:

      1. a world carrying `pending_ley_edits` comes back from the drain with the queue
         emptied, not merely ignored;
      2. each applied entry has moved its node's intensity in `magic.networks[school]`;
      3. entries are resolved by node id, never by index;
      4. an entry naming a known school is rejected rather than applied;
      5. two worlds queuing the same entries in opposite order come back identical.

    Only (0) -- that a consumer exists at all -- is checked here, because the other five
    cannot be written against a function that does not exist. Replacing this with the real
    round trip is the point.
    """

    PRODUCER = 'icarus_sim/terrain_nomad_effects.py'
    CARRIER = 'icarus_sim/terrain_history.py'

    def mentions(self):
        root = Path(effects.__file__).resolve().parent.parent
        found = []
        for path in sorted(root.rglob('*.py')):
            # `path` is absolute, so its first part is the drive: ask the *relative* path
            # whether this is a test. Getting that wrong makes this module match itself and
            # report an applier that is not there.
            relative = path.relative_to(root)
            if '__pycache__' in relative.parts or relative.parts[0] == 'tests':
                continue
            if 'pending_ley_edits' in path.read_text(encoding='utf-8'):
                found.append(relative.as_posix())
        return found

    def test_the_carrier_only_carries(self):
        """Justifies excluding `terrain_history` below, and breaks if that stops being true.

        Its single mention is inside `STATE_KEYS`, which copies the block across an age
        boundary. Carrying a queue forward is not draining it -- it is the reason an
        undrained queue survives every age instead of being dropped.
        """
        source = (Path(effects.__file__).resolve().parent / 'terrain_history.py').read_text(encoding='utf-8')
        lines = [i for i, line in enumerate(source.splitlines(), 1) if 'pending_ley_edits' in line]
        self.assertEqual(len(lines), 1, f'terrain_history now mentions the queue on {lines}')
        self.assertIn('STATE_KEYS', source.splitlines()[lines[0] - 1])

    def test_something_in_the_simulation_drains_the_queue(self):
        found = self.mentions()
        self.assertIn(self.PRODUCER, found, 'the producer moved; this test needs updating')
        appliers = [path for path in found if path not in (self.PRODUCER, self.CARRIER)]
        self.assertTrue(appliers,
                        'no module under Sim/ outside the producer and STATE_KEYS so much as '
                        f'names `pending_ley_edits` (found: {found}). `terrain_corruption`, the '
                        'module the contract names as the applier, does not mention it at all, so '
                        'the queue is written and never read. Because it rides in STATE_KEYS it is '
                        'also carried across every age advance and appended to -- `apply_cultist_'
                        'leylines` reads the existing list and writes it back -- so the first world '
                        'to unlock a hidden school starts growing a queue that nothing will ever '
                        'drain and no age boundary will ever clear.')


if __name__ == '__main__':
    unittest.main()
