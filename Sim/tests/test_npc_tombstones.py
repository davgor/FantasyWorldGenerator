"""The roster forgets its dead, and nothing in the document says anyone was ever there.

**These tests are expected to fail.** They are a defect pin for
`board/backlog/NPC-TOMBSTONES.md`, which could not be implemented in the sweep that wrote them:
every surface the fix needs -- `Sim/npc_roster/__init__.py`, `Sim/tests/test_npc_roster.py`,
`docs/npc-roster.md` and the pop-before-attach seam in `Sim/icarus_sim/terrain_history.py` -- is
fenced to another live session. The card carries the exact patch each one needs.

Do not "fix" these by weakening them. Exactly two failures is correct; zero means somebody
deleted the evidence, and a green here without a `carried` counter in `npcs.summary` means the
assertions stopped asking the question.

## What they pin

`npcs` is a pure function of the world in front of it: `collect(world)` walks `city_plans`,
`hamlet_plans` and `castle_plans`, and a site those blocks no longer carry takes its people with
it. An age advance ruins cities, so a consumer holding a uid across one cannot tell

* this person died,
* this person never existed,
* the producer renamed the key,

and the only correct reading of an absent uid is the useless one: gone, cause unknown. The
nomads work already leans on this -- a band's `refuge_uid` is resolved against `sites | ruins`
precisely because its `basis` outlives the roster records it points at -- and a quest anchored on
"recover what he was carrying" needs the corpse addressable.

## What is NOT the defect, and why the first test is narrow

`npcs.people` already carries `status: 'dead'` records: `npc_roster/__init__.py:190` writes
`'alive' if person.get('status') == 'living' else 'dead'` when it folds the cast in, so a hero the
cast has passed into legend is already a tombstone. The block is therefore **already not** a pure
function of who is currently alive, for one subset of people. This card widens an existing
exception rather than crossing a line for the first time, and the test below asserts exactly
that, as a control that passes.

The ruin here is applied to the plan blocks rather than generated, because the loss is a property
of the derivation and not of any particular seed: `collect` cannot see a plan that is not there.
No world is generated.
"""
import copy
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Sim'))
sys.path.insert(0, str(ROOT / 'Sim' / 'tests'))

import npc_roster

import test_npc_roster as roster_fixture

RUINED_CITY = 'surface-city-0-40-human_heartland'


def before_advance():
    return roster_fixture.world()


def after_advance():
    """The same world after an age in which Bracken City was ruined.

    Its city plan is gone, and so are the hamlet and castle plans that hung off it -- which is
    what an age advance does: the planners rebuild from the settlements that survived, and a
    ruined city's plans are simply not among them. The survivor, Umber, is untouched.
    """
    world = copy.deepcopy(roster_fixture.world())
    world['city_plans']['cities'] = [c for c in world['city_plans']['cities']
                                     if c['city_uid'] != RUINED_CITY]
    world['hamlet_plans']['hamlets'] = [h for h in world['hamlet_plans']['hamlets']
                                        if h.get('core_city_uid') != RUINED_CITY]
    world['castle_plans']['castles'] = []
    world['ruins'] = [{'id': 'ruin-' + RUINED_CITY, 'uid': RUINED_CITY, 'name': 'Bracken City (Age 1)',
                       'node': 40, 'x': 6, 'z': 2, 'city_class': 'medium',
                       'civilization_id': 'human_heartland', 'destroyed_age': 2, 'cause': 'war_civil'}]
    world['heroes'] = copy.deepcopy(world['heroes'])
    for person in world['heroes']['people']:
        if (person.get('home') or {}).get('uid') == RUINED_CITY:
            person['status'] = 'legend'
    return world


def uids(block):
    return {person['uid'] for person in block['people']}


class Controls(unittest.TestCase):
    """These pass. The failures below only mean something once these do."""

    def test_the_block_already_carries_dead_records_for_one_subset(self):
        """A cast legend is already a tombstone, so this card widens rather than crosses."""
        block = npc_roster.generate(before_advance())
        dead = [p for p in block['people'] if p['status'] == 'dead']
        self.assertTrue(dead, 'the fixture no longer folds in a hero the cast passed into legend')
        for person in dead:
            self.assertIn('hero_uid', person,
                          'only cast records can be dead today; a staffed post is always alive')
        self.assertEqual(block['summary']['dead'], len(dead))

    def test_the_advance_fixture_removes_one_city_and_nothing_else(self):
        """The renumbered world must differ from the first in that one ruin alone."""
        before, after = before_advance(), after_advance()
        self.assertEqual([c['city_uid'] for c in after['city_plans']['cities']],
                         [c['city_uid'] for c in before['city_plans']['cities'] if c['city_uid'] != RUINED_CITY])
        survivor = 'surface-city-0-77-dwarf'
        self.assertEqual(next(c for c in after['city_plans']['cities'] if c['city_uid'] == survivor),
                         next(c for c in before['city_plans']['cities'] if c['city_uid'] == survivor))

    def test_a_surviving_site_keeps_its_people_across_the_advance(self):
        """Without this, the failures below could be the whole roster collapsing."""
        before = npc_roster.generate(before_advance())
        after = npc_roster.generate(after_advance())
        survivor = 'surface-city-0-77-dwarf'
        self.assertEqual({p['uid'] for p in before['people'] if p['site_uid'] == survivor},
                         {p['uid'] for p in after['people'] if p['site_uid'] == survivor})


class Tombstones(unittest.TestCase):

    def test_a_person_whose_site_was_ruined_is_carried_as_dead_rather_than_dropped(self):
        """The corpse must stay addressable: a uid held from the first age still resolves."""
        before = npc_roster.generate(before_advance())
        prior = dict(before)
        after = npc_roster.generate(dict(after_advance(), npcs=prior))
        lost = sorted(uids(before) - uids(after))
        self.assertEqual(lost, [],
                         f'{len(lost)} uids vanished with no record that they ever existed, so a '
                         'consumer holding one cannot tell death from a renamed key. First few: '
                         f'{lost[:3]}')

    def test_a_carried_record_says_when_and_why_it_died(self):
        """`status: dead` alone is not a tombstone. A cause and an age are what make it one."""
        before = npc_roster.generate(before_advance())
        after = npc_roster.generate(dict(after_advance(), npcs=dict(before)))
        carried = [p for p in after['people'] if p.get('carried')]
        self.assertTrue(carried, 'no record is marked as carried forward from the prior block')
        for person in carried:
            self.assertEqual(person['status'], 'dead')
            self.assertEqual(person['died_age'], 2)
            self.assertIn(person['cause'], ('site_ruined', 'post_removed'))
        self.assertEqual(after['summary']['carried'], len(carried))
        self.assertIn('vanished', after['summary'])
        self.assertEqual(after['prior_age'], 1,
                         'a consumer must be able to tell a first derivation from a continued one')


if __name__ == '__main__':
    unittest.main()
