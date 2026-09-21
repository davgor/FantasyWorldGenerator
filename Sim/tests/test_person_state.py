"""The person channel: one liveness vocabulary in, four block-local ones out.

Four blocks answer "is this person still here" in three sets of words -- `living`/`legend`
for a hero or a dread, `alive`/`dead` for an npc, `living`/`fallen` for a villain -- and a
fifth `status`, `ok`/`failed`, sits one level up on the block itself under the same key
name. `terrain_liveness` already reads all of that with one predicate. Nothing could write
it, so a game that lost a character wrote a block-local word into the persisted document by
hand and had to know which of the three it was.

The tests that matter here are the ones about the seam rather than the effect:

* **A write goes through `liveness`, not around it.** The predicate dispatches on the block
  a record came from and refuses a block handed to it in place of a person, because
  `hero_generator` and `npc_roster` write `ok`/`failed` and `living`/`legend` under one key
  at two depths. A writer that matched on the string would mark a failed package as a
  departed person.
* **No sixth vocabulary is published.** The request speaks `present`/`gone`, which is the
  predicate's own published pair, and every word written into a world is one of the eight
  that block already used.
* **The translation is the promoted one.** `Sim/npc_roster/__init__.py` carries the only
  hand-written translation between two published contracts in this repository. The leaf
  packages must not import the generator, so the expression stays where it is and this
  file binds it to `terrain_liveness`, the same way `test_npc_roster` binds that package's
  `posts.json` snapshot to the registry it was copied from.
"""
import json
import pathlib
import unittest

from icarus_sim.terrain_errors import RequestError
from icarus_sim.terrain_liveness import GONE, GONE_STATUS, PRESENT, PRESENT_STATUS, census, liveness, token
from icarus_sim.terrain_person_api import PERSON_API_VERSION, person_state_request
from icarus_sim.terrain_person_state import MAX_CHANGES, STATUSES, plan, validate_changes
from icarus_sim.terrain_time import advance_time_request, clock

# The same world the quest channel's tests use, generated once for both. Borrowing a
# sibling test module's fixture is the idiom here -- `test_story_web` and
# `test_site_id_stability` both do it -- and generating a second world would cost the suite
# a minute and a half to arrive at the same bytes.
import test_quest_actions as quest_fixture

ticked_world = quest_fixture.ticked_world


def digest(world):
    return json.dumps(world, sort_keys=True, allow_nan=False)


class VocabularyTests(unittest.TestCase):
    """Pure. No world, no clock, no draw."""

    def test_the_request_speaks_the_predicates_own_pair_and_no_new_word(self):
        self.assertEqual(STATUSES, (PRESENT, GONE))
        self.assertEqual(sorted(set(PRESENT_STATUS) ^ set(GONE_STATUS)), [])
        published = set(PRESENT_STATUS.values()) | set(GONE_STATUS.values())
        self.assertEqual(published, {'living', 'legend', 'alive', 'dead', 'fallen'},
                         'a word that is not already in a block vocabulary has been invented')

    def test_every_block_translates_in_both_directions(self):
        for block in PRESENT_STATUS:
            self.assertEqual(token(block, PRESENT), PRESENT_STATUS[block], block)
            self.assertEqual(token(block, GONE), GONE_STATUS[block], block)
            for state in STATUSES:
                # The round trip is the claim: what the writer writes is what the reader
                # reads back, in that block's own words.
                self.assertEqual(liveness({'status': token(block, state)}, block), state, block)

    def test_the_route_looks_in_exactly_the_blocks_the_predicate_knows(self):
        from icarus_sim.terrain_person_api import SOURCES
        self.assertEqual(sorted(block for _, _, block in SOURCES), sorted(PRESENT_STATUS),
                         'the writer and the predicate disagree about which blocks hold people')

    def test_an_unknown_block_or_state_is_a_caller_error(self):
        for bad in ('people', 'settlements', None):
            with self.assertRaises(ValueError):
                token(bad, PRESENT)
        with self.assertRaises(ValueError):
            token('heroes', 'missing')

    def test_a_plan_goes_through_the_predicate_and_refuses_a_block(self):
        record = {'uid': 'hero-1', 'status': 'living'}
        changed, before, after = plan(record, 'heroes', GONE)
        self.assertEqual((before, after), (PRESENT, GONE))
        self.assertEqual(changed['status'], 'legend')
        self.assertEqual(record['status'], 'living', 'plan mutated the record it was given')
        # The depth collision the predicate exists to catch: a block carrying `people` and a
        # block-level `status` must not be writable as though it were a person.
        for block_shaped in ({'status': 'ok', 'people': []},
                             {'status': 'failed', 'quest_hooks': []},
                             {'status': 'ok', 'policy_revision': 3}):
            with self.assertRaises(ValueError):
                plan(block_shaped, 'npcs', GONE)

    def test_absent_status_reads_as_present_and_a_no_op_writes_nothing(self):
        record = {'uid': 'hero-1'}
        changed, before, after = plan(record, 'heroes', PRESENT)
        self.assertEqual((before, after), (PRESENT, PRESENT))
        self.assertIsNone(changed, 'a no-op added a status key to a record that had none')

    def test_the_dread_vocabulary_is_reachable_even_when_a_world_has_none(self):
        changed, before, after = plan({'uid': 'dread-1', 'status': 'living'}, 'dreads', GONE)
        self.assertEqual((before, after, changed['status']), (PRESENT, GONE, 'legend'))

    def test_shape_validation(self):
        good = validate_changes([{'uid': 'u', 'status': GONE, 'reason': 'slain', 'day': 10}])
        self.assertEqual(good, [{'uid': 'u', 'status': GONE, 'reason': 'slain', 'day': 10.}])
        for bad in (None, 'gone', 7, {}):
            with self.assertRaises(RequestError):
                validate_changes(bad)
        base = {'uid': 'u', 'status': GONE, 'reason': 'slain', 'day': 10}
        for field in ('uid', 'status', 'reason', 'day'):
            missing = {k: v for k, v in base.items() if k != field}
            with self.assertRaises(RequestError):
                validate_changes([missing])
        for bad in ({**base, 'status': 'dead'}, {**base, 'status': 'ok'},
                    {**base, 'reason': ''}, {**base, 'reason': 5}, {**base, 'day': -1},
                    {**base, 'day': float('nan')}, {**base, 'uid': 4}, {**base, 'block': 'npcs'}):
            with self.assertRaises(RequestError):
                validate_changes([bad])

    def test_the_capacity_bound(self):
        self.assertEqual(MAX_CHANGES, 1024)
        with self.assertRaises(RequestError) as caught:
            validate_changes([{'uid': 'u', 'status': GONE, 'reason': 'r', 'day': 1}]
                             * (MAX_CHANGES + 1))
        self.assertEqual(caught.exception.document()['code'], 'STATE_CAPACITY')


class PromotedTranslationTests(unittest.TestCase):
    """The expression at `Sim/npc_roster/__init__.py`, bound to the published mapping.

    The leaf packages are forbidden from importing `icarus_sim` -- `npc_roster/policy.py`
    says so in as many words -- so the roster cannot call the promoted function and the
    snapshot-plus-guard shape used for `posts.json` is the one available. This is the guard.
    """

    def test_the_roster_expression_is_the_published_mapping(self):
        import npc_roster
        source = ' '.join(pathlib.Path(npc_roster.__file__).read_text(encoding='utf-8').split())
        # Rebuilt from the published tables rather than restated, so this fails in both
        # directions: if the roster's expression is edited, and if the mapping it was
        # copied from moves underneath it.
        expected = ("'status': %r if person.get('status') == %r else %r,"
                    % (token('npcs', PRESENT), PRESENT_STATUS['heroes'], token('npcs', GONE)))
        self.assertIn(expected, source,
                      'npc_roster no longer translates a hero into a roster record the way '
                      'terrain_liveness says it should. Expected to find: ' + expected)

    def test_the_leaf_package_still_does_not_import_the_generator(self):
        """The reason the expression was promoted rather than replaced by a call.

        `npc_roster/policy.py` states the rule; this asserts it, because the promotion is
        only worth anything as a guard while the import route stays closed.
        """
        for name in ('npc_roster', 'hero_generator', 'story_web', 'heritage'):
            package = pathlib.Path(__file__).resolve().parents[1] / name
            for module in sorted(package.rglob('*.py')):
                body = module.read_text(encoding='utf-8')
                for line in body.splitlines():
                    stripped = line.strip()
                    if stripped.startswith(('import ', 'from ')) and 'icarus_sim' in stripped:
                        self.fail('%s imports the generator: %s' % (module.name, stripped))


class PersonRequestTests(unittest.TestCase):
    """The half that needs a world. One size-17 world, generated once."""

    @classmethod
    def setUpClass(cls):
        cls.world = ticked_world()

    def call(self, world, changes):
        return person_state_request({'api_version': PERSON_API_VERSION, 'world': world,
                                     'changes': changes})

    def someone(self, block, key, listing, state=PRESENT):
        container = self.world.get(key) or {}
        for record in container.get(listing) or []:
            if liveness(record, block) == state:
                return record
        raise unittest.SkipTest('no %s is %s in this world' % (block, state))

    def test_a_change_lands_in_each_blocks_own_words(self):
        for block, key, listing in (('heroes', 'heroes', 'people'),
                                    ('npcs', 'npcs', 'people'),
                                    ('villains', 'villains', 'people')):
            record = self.someone(block, key, listing)
            out = self.call(self.world, [{'uid': record['uid'], 'status': GONE,
                                          'reason': 'slain in play', 'day': 5.}])
            after = {r['uid']: r for r in out[key][listing]}[record['uid']]
            self.assertEqual(after['status'], GONE_STATUS[block], block)
            self.assertEqual(liveness(after, block), GONE, block)
            row = out['person_state']['changes'][0]
            self.assertEqual((row['block'], row['from_status'], row['to_status'], row['token']),
                             (block, PRESENT, GONE, GONE_STATUS[block]))

    def test_the_census_moves_by_exactly_one(self):
        record = self.someone('npcs', 'npcs', 'people')
        before = census(self.world)['npcs']
        out = self.call(self.world, [{'uid': record['uid'], 'status': GONE,
                                      'reason': 'slain in play', 'day': 5.}])
        after = census(out)['npcs']
        self.assertEqual((after[PRESENT], after[GONE]),
                         (before[PRESENT] - 1, before[GONE] + 1))

    def test_the_callers_world_is_never_touched_on_any_path(self):
        record = self.someone('heroes', 'heroes', 'people')
        before = digest(self.world)
        self.call(self.world, [{'uid': record['uid'], 'status': GONE, 'reason': 'x', 'day': 1.}])
        self.assertEqual(digest(self.world), before, 'a successful call mutated the caller')
        refusals = (
            [{'uid': 'no-such-person', 'status': GONE, 'reason': 'x', 'day': 1.}],
            [{'uid': record['uid'], 'status': 'dead', 'reason': 'x', 'day': 1.}],
            [{'uid': record['uid'], 'status': GONE, 'reason': 'x', 'day': -1.}],
            [{'uid': record['uid'], 'status': GONE, 'reason': 'x', 'day': 1.},
             {'uid': 'no-such-person', 'status': GONE, 'reason': 'x', 'day': 1.}],
        )
        for changes in refusals:
            with self.assertRaises(RequestError):
                self.call(self.world, changes)
            self.assertEqual(digest(self.world), before, changes)

    def test_an_unknown_uid_names_the_field_and_suggests(self):
        record = self.someone('npcs', 'npcs', 'people')
        typo = record['uid'][:-1]
        with self.assertRaises(RequestError) as caught:
            self.call(self.world, [{'uid': typo, 'status': GONE, 'reason': 'x', 'day': 1.}])
        document = caught.exception.document()
        self.assertEqual(document['schema'], 'fantasy-world-generator.failure')
        self.assertEqual(document['field'], typo)
        self.assertIn(record['uid'], document['suggestion'].get('candidates', []))

    def test_an_unsupported_api_version_is_not_retryable(self):
        with self.assertRaises(RequestError) as caught:
            person_state_request({'api_version': 99, 'world': self.world, 'changes': []})
        self.assertIs(caught.exception.document()['retry'], False)

    def test_one_operation_per_call_that_changes_the_world_and_none_otherwise(self):
        record = self.someone('npcs', 'npcs', 'people')
        before = len((self.world.get('history') or {}).get('operations') or [])
        out = self.call(self.world, [{'uid': record['uid'], 'status': GONE,
                                      'reason': 'slain in play', 'day': 5.}])
        self.assertEqual(len(out['history']['operations']), before + 1)
        row = out['history']['operations'][-1]
        self.assertEqual((row['kind'], row['api_version']), ('person', PERSON_API_VERSION))
        self.assertEqual(row['changes'], [{'uid': record['uid'], 'status': GONE,
                                           'reason': 'slain in play', 'day': 5.}])
        self.assertEqual(len((self.call(self.world, []).get('history') or {})
                             .get('operations') or []), before)
        # A change that asks for the state a record is already in changes nothing, so it
        # records nothing either.
        idle = self.call(self.world, [{'uid': record['uid'], 'status': PRESENT,
                                       'reason': 'still here', 'day': 5.}])
        self.assertEqual(idle['person_state']['applied'], 0)
        self.assertEqual(len((idle.get('history') or {}).get('operations') or []), before)
        self.assertIs(idle['person_state']['changes'][0]['changed'], False)

    def test_the_same_changes_against_the_same_world_are_byte_identical(self):
        record = self.someone('heroes', 'heroes', 'people')
        changes = [{'uid': record['uid'], 'status': GONE, 'reason': 'x', 'day': 2.}]
        self.assertEqual(digest(self.call(self.world, changes)),
                         digest(self.call(self.world, changes)))

    def test_the_route_moves_nothing_but_the_block_it_was_asked_about(self):
        record = self.someone('npcs', 'npcs', 'people')
        out = self.call(self.world, [{'uid': record['uid'], 'status': GONE,
                                      'reason': 'x', 'day': 2.}])
        self.assertEqual(out.get('world_clock'), self.world.get('world_clock'))
        for key in ('heroes', 'villains', 'magic', 'layers', 'settlements', 'quests'):
            if key in self.world:
                self.assertEqual(digest(out.get(key)), digest(self.world.get(key)), key)

    def test_this_resolver_agrees_with_the_quest_lifecycles_own(self):
        """Two resolvers, one fact, bound rather than left to drift.

        `terrain_time._giver_index` answers a narrower question -- who can hold a quest
        open -- so it spans `heroes.people`, `heroes.dreads` and `npcs.people` only, keeps
        the first writer of a uid, and returns `(record, block)`. A writer needs the list
        and the position to put a record back, and needs villains, and must refuse a uid
        two blocks claim instead of silently preferring one. So this route indexes
        separately, and the two must not disagree about which block a uid came from.
        """
        from icarus_sim.terrain_time import _giver_index
        from icarus_sim.terrain_person_api import index as person_index
        givers, mine = _giver_index(self.world), person_index(self.world)
        self.assertEqual([uid for uid in givers if uid not in mine], [],
                         'the lifecycle can resolve a giver this route cannot find')
        disagreed = [(uid, givers[uid][1], mine[uid][0][2]) for uid in givers
                     if givers[uid][1] != mine[uid][0][2]]
        self.assertEqual(disagreed, [], 'the two resolvers disagree about a uid\'s block')
        self.assertEqual(sorted(set(mine) - set(givers)),
                         sorted(r['uid'] for r in (self.world.get('villains') or {}).get('people') or []),
                         'the only uids this route knows and the lifecycle does not are villains')

    def test_a_cli_persisted_world_is_acted_on_and_gains_no_timing(self):
        """`cli.py` strips every `timing_ms`; this route writes none, so the seam is moot."""
        from fantasy_world_generator.cli import _without_timings
        persisted = _without_timings({k: v for k, v in self.world.items()
                                      if k != 'build_stages'})
        self.assertNotIn('timing_ms', persisted,
                         'without this the rest of the test proves nothing')
        record = next(r for r in persisted['npcs']['people'] if liveness(r, 'npcs') == PRESENT)
        out = self.call(persisted, [{'uid': record['uid'], 'status': GONE,
                                     'reason': 'slain in play', 'day': 5.}])
        self.assertNotIn('timing_ms', out)
        self.assertEqual({r['uid']: r for r in out['npcs']['people']}[record['uid']]['status'],
                         GONE_STATUS['npcs'])

    def test_a_giver_who_is_gone_closes_the_quest_on_the_next_tick(self):
        """The one consequence this route has, and it is the lifecycle's, not this route's.

        Nothing cascades at the moment of the write. `terrain_time._quest_step` reads
        liveness on its next sweep and closes the offer as `giver_gone`, which is exactly
        what it already did for a giver the world itself removed.
        """
        open_quests = [q for q in self.world['quests']['quests'] if q['state'] == 'offered']
        givers = {r['uid'] for r in (self.world['heroes'].get('people') or [])}
        quest = next((q for q in open_quests if q['giver_uid'] in givers), None)
        if quest is None:
            self.skipTest('no open quest in this world is held by a living hero')
        out = self.call(self.world, [{'uid': quest['giver_uid'], 'status': GONE,
                                      'reason': 'slain in play',
                                      'day': clock(self.world)['day']}])
        ticked = advance_time_request({'api_version': 1, 'world': out, 'elapsed': {'days': 2}})
        closed = {q['quest_id']: q for q in ticked['quests']['quests']}[quest['quest_id']]
        self.assertEqual((closed['state'], closed['closed_reason']), ('expired', 'giver_gone'))

    def test_the_npc_mirror_of_a_hero_is_not_updated_and_the_report_says_so(self):
        """A known limitation, asserted so it cannot change without someone noticing.

        `npc_roster` copies the cast into `npcs.people` under a prefixed uid at generation
        time. That copy is a snapshot; this route writes the record the uid names and
        nothing else, because deciding what else must move when someone stops existing is
        the question `NPC-TOMBSTONES` and `VILLAIN-FALL-UNRECORDED` share and it may not be
        answered here alone.
        """
        hero = self.someone('heroes', 'heroes', 'people')
        mirror = next((r for r in self.world['npcs']['people']
                       if r.get('hero_uid') == str(hero['uid'])), None)
        if mirror is None:
            self.skipTest('this world has no roster mirror for that hero')
        out = self.call(self.world, [{'uid': hero['uid'], 'status': GONE,
                                      'reason': 'slain in play', 'day': 5.}])
        after = {r['uid']: r for r in out['npcs']['people']}[mirror['uid']]
        self.assertEqual(after['status'], mirror['status'],
                         'the mirror moved; this test, and the record, now describe '
                         'something the route no longer does')
        self.assertTrue(any('mirror' in note for note in out['person_state']['notes']))


if __name__ == '__main__':
    unittest.main()
