"""The quest channel: the writer for a state the reader has honoured all along.

`terrain_time` opens, expires and resolves quests, and it *honours* `taken` -- a taken
quest does not expire on its offer window -- but nothing could set that state. A game that
accepted a quest for its player had to write `taken` into the persisted document by hand,
outside every boundary the request APIs exist to enforce.

Three things are asserted here and each has already been got wrong somewhere in this
repository:

* **The caller's world is byte-identical afterwards, including on every refusal.** A route
  that copies lazily and validates late leaves a half-written world behind on the third
  action of a batch.
* **A call that changes nothing records nothing.** The age band's estimate path already
  works this way, and an operation log that grows on every no-op is an unbounded record of
  nothing happening.
* **A taken quest does not cross an age boundary, and not by luck.** `heroes` is
  regenerated wholesale at an age transition, so most hook ids used to be re-minted as
  different strings and the reaper closed their quests as `hook_gone` -- but the cast
  re-mints positional uids as the same string, so ten of forty-nine survived pointing at a
  hook nobody wrote them for. An age turn now closes every open quest under its own reason
  and rebuilds the board, so the assertion here is over the whole board rather than over
  whichever ids happened to vanish.
"""
import json
import unittest

from icarus_sim.terrain_errors import RequestError
from icarus_sim.terrain_quest_actions import (ABANDON, ACTIONS, MAX_ACTIONS, TAKE, OPEN_STATES,
                                              transition, validate_actions)
from icarus_sim.terrain_quest_api import QUEST_API_VERSION, quest_request
from icarus_sim.terrain_time import advance_time_request, clock

_CACHE = {}


def ticked_world():
    """A size-17 seed-42 world advanced one month, so it carries an open quest board.

    Generated once for the whole module: two classes need it and generation is the most
    expensive thing in this file by two orders of magnitude.
    """
    if 'world' not in _CACHE:
        from icarus_sim.terrain_world import generate_request
        raw = generate_request({'recipe_version': 3, 'seed': 42, 'overrides': {'size': 17}})
        _CACHE['world'] = advance_time_request(
            {'api_version': 1, 'world': raw, 'elapsed': {'days': 30}})
    return _CACHE['world']


def digest(world):
    return json.dumps(world, sort_keys=True, allow_nan=False)


def a_quest(world, state='offered'):
    for quest in world['quests']['quests']:
        if quest['state'] == state:
            return quest
    raise unittest.SkipTest('this world carries no quest in state ' + state)


class QuestShapeTests(unittest.TestCase):
    """The pure half. No world, no clock, no RNG."""

    def test_the_vocabulary_is_two_words(self):
        self.assertEqual(ACTIONS, (TAKE, ABANDON))
        self.assertEqual(OPEN_STATES, ('offered', 'taken'))

    def test_shape_validation_refuses_what_the_resolution_array_refuses(self):
        for bad in (None, 'take', 7, {}):
            with self.assertRaises(RequestError):
                validate_actions(bad)
        with self.assertRaises(RequestError):
            validate_actions([{'quest_id': 'q', 'action': 'complete'}])
        with self.assertRaises(RequestError):
            validate_actions([{'quest_id': 'q', 'action': TAKE, 'outcome': 'completed'}])
        with self.assertRaises(RequestError):
            validate_actions([{'action': TAKE}])
        for bad_day in (-1., float('inf'), 'today', True):
            with self.assertRaises(RequestError):
                validate_actions([{'quest_id': 'q', 'action': TAKE, 'day': bad_day}])

    def test_the_capacity_bound_is_the_resolution_arrays(self):
        self.assertEqual(MAX_ACTIONS, 1024)
        too_many = [{'quest_id': 'q', 'action': TAKE}] * (MAX_ACTIONS + 1)
        with self.assertRaises(RequestError) as caught:
            validate_actions(too_many)
        self.assertEqual(caught.exception.document()['code'], 'STATE_CAPACITY')

    def test_a_transition_does_not_mutate_the_quest_it_is_given(self):
        quest = {'quest_id': 'q', 'state': 'offered', 'offered_day': 10., 'expires_day': 90.,
                 'closed_day': None, 'closed_reason': None}
        before = dict(quest)
        taken, entry = transition(quest, TAKE, 20.)
        self.assertEqual(quest, before)
        self.assertEqual(taken['state'], 'taken')
        self.assertEqual(entry, {'day': 20., 'quest_id': 'q', 'event': 'taken'})
        # A taken quest keeps its window: the window is what it is now exempt from, and
        # erasing it would lose the fact that an offer was ever made.
        self.assertEqual(taken['expires_day'], 90.)
        self.assertIsNone(taken['closed_day'])

    def test_abandon_closes_with_its_reason_and_its_day(self):
        quest = {'quest_id': 'q', 'state': 'taken', 'offered_day': 10., 'expires_day': 90.,
                 'closed_day': None, 'closed_reason': None}
        closed, entry = transition(quest, ABANDON, 33.)
        self.assertEqual((closed['state'], closed['closed_day'], closed['closed_reason']),
                         ('abandoned', 33., 'abandoned'))
        self.assertEqual(entry['event'], 'abandoned')

    def test_a_closed_quest_refuses_both_actions_as_the_world_not_as_validation(self):
        for state in ('completed', 'failed', 'abandoned', 'expired'):
            quest = {'quest_id': 'q', 'state': state, 'offered_day': 10., 'expires_day': 90.,
                     'closed_day': 50., 'closed_reason': 'resolved'}
            for action in ACTIONS:
                with self.assertRaises(RequestError) as caught:
                    transition(quest, action, 60.)
                document = caught.exception.document()
                self.assertEqual(document['expected'], {'refused_by': 'world state'})
                self.assertIs(document['retry'], True)

    def test_taking_a_taken_quest_is_refused(self):
        quest = {'quest_id': 'q', 'state': 'taken', 'offered_day': 10., 'expires_day': 90.,
                 'closed_day': None, 'closed_reason': None}
        with self.assertRaises(RequestError):
            transition(quest, TAKE, 20.)

    def test_a_lapsed_offer_cannot_be_taken(self):
        """The one refusal this route adds that the resolution array has no analogue for.

        `_quest_step` only tests the window while a quest is `offered`, so a take applied
        after the window closed but before the next sweep would make the offer immortal:
        the state is no longer `offered`, so the expiry branch is never reached again.
        """
        quest = {'quest_id': 'q', 'state': 'offered', 'offered_day': 10., 'expires_day': 90.,
                 'closed_day': None, 'closed_reason': None}
        with self.assertRaises(RequestError) as caught:
            transition(quest, TAKE, 91.)
        self.assertEqual(caught.exception.document()['expected'], {'refused_by': 'world state'})
        # Abandoning a lapsed offer is still legal: declining something is never too late.
        closed, _ = transition(quest, ABANDON, 91.)
        self.assertEqual(closed['state'], 'abandoned')


class QuestRequestTests(unittest.TestCase):
    """The half that needs a world."""

    @classmethod
    def setUpClass(cls):
        cls.world = ticked_world()

    def call(self, world, actions):
        return quest_request({'api_version': QUEST_API_VERSION, 'world': world,
                              'actions': actions})

    def test_take_is_honoured_by_the_lifecycle_that_already_reads_it(self):
        quest = a_quest(self.world)
        out = self.call(self.world, [{'quest_id': quest['quest_id'], 'action': TAKE}])
        taken = {q['quest_id']: q for q in out['quests']['quests']}[quest['quest_id']]
        self.assertEqual(taken['state'], 'taken')
        # Long enough that every offer outlives its window. The taken one must not close.
        later = advance_time_request({'api_version': 1, 'world': out, 'elapsed': {'years': 10}})
        still = {q['quest_id']: q for q in later['quests']['quests']}[quest['quest_id']]
        self.assertEqual(still['state'], 'taken', 'a taken quest expired on its offer window')
        self.assertIsNone(still['closed_reason'])

    def test_abandon_closes_the_quest_with_its_reason_and_its_day(self):
        quest = a_quest(self.world)
        day = clock(self.world)['day']
        out = self.call(self.world, [{'quest_id': quest['quest_id'], 'action': ABANDON}])
        closed = {q['quest_id']: q for q in out['quests']['quests']}[quest['quest_id']]
        self.assertEqual((closed['state'], closed['closed_reason']), ('abandoned', 'abandoned'))
        self.assertEqual(closed['closed_day'], day)
        self.assertIn({'day': day, 'quest_id': quest['quest_id'], 'event': 'abandoned'},
                      out['quests']['log'])

    def test_the_callers_world_is_never_touched_on_any_path(self):
        quest = a_quest(self.world)
        before = digest(self.world)
        self.call(self.world, [{'quest_id': quest['quest_id'], 'action': TAKE}])
        self.assertEqual(digest(self.world), before, 'a successful call mutated the caller')
        refusals = (
            [{'quest_id': 'no-such-quest', 'action': TAKE}],
            [{'quest_id': quest['quest_id'], 'action': 'complete'}],
            [{'quest_id': quest['quest_id'], 'action': TAKE, 'day': -1.}],
            # A batch whose first action is legal and whose second is not: the half-written
            # world this asserts against is the one a late-validating route leaves behind.
            [{'quest_id': quest['quest_id'], 'action': TAKE},
             {'quest_id': 'no-such-quest', 'action': ABANDON}],
            [{'quest_id': quest['quest_id'], 'action': TAKE},
             {'quest_id': quest['quest_id'], 'action': TAKE}],
        )
        for actions in refusals:
            with self.assertRaises(RequestError):
                self.call(self.world, actions)
            self.assertEqual(digest(self.world), before, actions)

    def test_a_refusal_carries_the_failure_envelope(self):
        quest = a_quest(self.world)
        with self.assertRaises(RequestError) as caught:
            self.call(self.world, [{'quest_id': 'no-such-quest', 'action': TAKE}])
        document = caught.exception.document()
        self.assertEqual(document['schema'], 'fantasy-world-generator.failure')
        self.assertEqual(document['code'], 'INVALID_INPUT')
        self.assertEqual(document['field'], 'no-such-quest')
        with self.assertRaises(RequestError) as caught:
            quest_request({'api_version': 99, 'world': self.world, 'actions': []})
        self.assertIs(caught.exception.document()['retry'], False,
                      'an unsupported api_version is not worth resending')
        with self.assertRaises(RequestError) as caught:
            quest_request({'api_version': QUEST_API_VERSION, 'world': self.world,
                           'actions': [], 'elapsed': {'days': 1}})
        self.assertEqual(caught.exception.document()['code'], 'INVALID_INPUT')
        # The world is the constraint, not the value: the id was real and the caller is late.
        taken = self.call(self.world, [{'quest_id': quest['quest_id'], 'action': ABANDON}])
        with self.assertRaises(RequestError) as caught:
            self.call(taken, [{'quest_id': quest['quest_id'], 'action': TAKE}])
        self.assertEqual(caught.exception.document()['expected'], {'refused_by': 'world state'})

    def test_a_world_with_no_quest_board_says_which_block_is_missing(self):
        bare = dict(self.world)
        bare.pop('quests')
        with self.assertRaises(RequestError) as caught:
            quest_request({'api_version': QUEST_API_VERSION, 'world': bare,
                           'actions': [{'quest_id': 'q', 'action': TAKE}]})
        self.assertEqual(caught.exception.document()['field'], 'world.quests')

    def test_one_operation_per_call_that_changes_the_world_and_none_otherwise(self):
        quest = a_quest(self.world)
        before = len((self.world.get('history') or {}).get('operations') or [])
        out = self.call(self.world, [{'quest_id': quest['quest_id'], 'action': TAKE}])
        self.assertEqual(len(out['history']['operations']), before + 1)
        row = out['history']['operations'][-1]
        self.assertEqual((row['kind'], row['api_version']), ('quest', QUEST_API_VERSION))
        self.assertEqual(row['actions'],
                         [{'quest_id': quest['quest_id'], 'action': TAKE,
                           'day': clock(self.world)['day']}])
        empty = self.call(self.world, [])
        self.assertEqual(len((empty.get('history') or {}).get('operations') or []), before,
                         'a call that changed nothing recorded an operation')
        self.assertEqual(empty['quest_actions']['applied'], 0)

    def test_the_same_actions_against_the_same_world_are_byte_identical(self):
        quest = a_quest(self.world)
        actions = [{'quest_id': quest['quest_id'], 'action': TAKE}]
        self.assertEqual(digest(self.call(self.world, actions)),
                         digest(self.call(self.world, actions)))

    def test_the_route_does_not_move_the_clock_or_the_ley_field(self):
        quest = a_quest(self.world)
        out = self.call(self.world, [{'quest_id': quest['quest_id'], 'action': TAKE}])
        self.assertEqual(out.get('world_clock'), self.world.get('world_clock'))
        for key in ('magic', 'layers', 'heroes', 'npcs', 'settlements', 'encounters'):
            if key in self.world:
                self.assertEqual(digest(out.get(key)), digest(self.world.get(key)), key)

    def test_a_cli_persisted_world_is_acted_on_and_gains_no_timing(self):
        """The document a real consumer holds, not the one a test happens to have.

        `cli.py` strips every `timing_ms` to keep an exported world byte-reproducible, and
        every in-memory test world still carries the key. This route writes no timing at
        all, so the seam `adopt_world` guards for the older mutators does not arise here --
        and a world it returns is still the reproducible document it was handed.
        """
        from fantasy_world_generator.cli import _without_timings
        persisted = _without_timings({k: v for k, v in self.world.items()
                                      if k != 'build_stages'})
        self.assertNotIn('timing_ms', persisted,
                         'without this the rest of the test proves nothing')
        quest = a_quest(persisted)
        out = self.call(persisted, [{'quest_id': quest['quest_id'], 'action': TAKE}])
        self.assertNotIn('timing_ms', out)
        self.assertEqual({q['quest_id']: q for q in out['quests']['quests']}
                         [quest['quest_id']]['state'], 'taken')

    def test_a_batch_applies_in_request_order(self):
        quest = a_quest(self.world)
        out = self.call(self.world, [{'quest_id': quest['quest_id'], 'action': TAKE},
                                     {'quest_id': quest['quest_id'], 'action': ABANDON}])
        final = {q['quest_id']: q for q in out['quests']['quests']}[quest['quest_id']]
        self.assertEqual(final['state'], 'abandoned')
        self.assertEqual([row['action'] for row in out['quest_actions']['actions']],
                         [TAKE, ABANDON])


class QuestAgeBoundaryTests(unittest.TestCase):
    """A taken quest ends when the age does, under `age_turned`.

    The ruling is `docs/decisions/028-an-age-is-five-thousand-years.md`: an age is five
    thousand years, so a quest does not cross one, because the people who offered and
    populate it are gone. The reaping used to be an accident of `heroes` being regenerated
    wholesale -- most hook ids vanished, their quests closed as `hook_gone`, and the ten of
    forty-nine whose positional uid the new cast re-minted as the same string survived
    carrying the old age's prose against the new age's target check. This class asserts the
    whole board, keyed on the age turning rather than on which ids disappeared.
    """

    @classmethod
    def setUpClass(cls):
        world = ticked_world()
        cls.taken = [q['quest_id'] for q in world['quests']['quests'] if q['state'] == 'offered']
        if not cls.taken:
            raise unittest.SkipTest('this world raised no quest hooks')
        cls.held = quest_request({'api_version': QUEST_API_VERSION, 'world': world,
                                  'actions': [{'quest_id': qid, 'action': TAKE}
                                              for qid in cls.taken]})
        # Exactly one age and no remainder, so what is asserted below is the age turn's own
        # doing and not a tick's. The reaping used to need the remainder: the age band ran
        # no quest sweep at all, so a span of whole ages left the whole board standing.
        cls.after = advance_time_request({'api_version': 1, 'world': cls.held,
                                          'elapsed': {'years': 5000}, 'commit': True})

    def test_every_taken_quest_closes_because_the_age_turned(self):
        held = {q['quest_id']: q for q in self.held['quests']['quests']}
        for qid in self.taken:
            self.assertEqual(held[qid]['state'], 'taken',
                             'the fixture must actually hold these quests taken')
        reaped = {entry['quest_id'] for entry in self.after['quests']['log']
                  if entry.get('event') == 'age_turned'}
        self.assertEqual(reaped, set(self.taken),
                         'a taken quest crossed the age boundary without being reaped')

    def test_no_taken_quest_survives_a_re_minted_hook_id(self):
        """The ten survivors, asserted gone.

        A survivor was never the old quest and never the new one: `anchor`, `verb` and
        `stated_purpose` are written once at open time and never refreshed, while
        `_target_present` ran against whatever hook now held the id and `giver_uid` named
        someone who no longer existed.
        """
        board = {q['quest_id']: q for q in self.after['quests']['quests']}
        turn_day = self.after['world_clock']['day']
        for qid in self.taken:
            self.assertNotEqual(board.get(qid, {}).get('state'), 'taken', qid)
            if qid in board:
                self.assertEqual(board[qid]['offered_day'], turn_day,
                                 'this row is the old age\'s quest wearing a re-minted id')

    def test_the_board_after_a_turn_is_the_new_age_s_hooks(self):
        board = self.after['quests']['quests']
        hooks = sorted(h['hook_id'] for h in (self.after['heroes'].get('quest_hooks') or []))
        self.assertTrue(hooks, 'the new age raised no hooks, so this proves nothing')
        self.assertEqual(sorted(q['quest_id'] for q in board), hooks)


if __name__ == '__main__':
    unittest.main()
