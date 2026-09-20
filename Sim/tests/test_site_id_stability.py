"""Whether a person's identity survives the age advance that renumbers the place they stand in.

`humans.fortresses` and `humans.hamlets` carry **ordinal** ids: `terrain_humans.record()`
builds `f'{kind}-{number}'` where the number is the position in the accepted list, and
fortresses are accepted in descending `defence_score` over a `strategic` map rebuilt from
the road graph every age. Cities die, roads move and war history reweights the score, so
both the membership and the order change at every age boundary. `fortress-36` names a
different piece of ground after an advance.

`npc_roster/sites.py` says this out loud and defends against it -- non-city sites are keyed
`fortress-node-1062`, positionally, "the way `terrain_villains` anchors villains to ley
nodes for exactly this reason", and it names the cast package as the one that does not:

    ``hamlet-0`` and ``fortress-0`` are ordinals that renumber every age [...] the cast
    package builds ``hero-castellan-fortress-36`` on the *ordinal* id, and two keys that
    read alike and mean different things is how a consumer joins the wrong rows without
    an error.

Three packages adopted node keying independently as a defence. Nothing enforces it, and
`hero_generator.wells.countryside` still spends the ordinal four times per person -- `uid`,
`presence.uid`, `deeds[].event_id` and `claim.target_uid`.

These tests are expected to fail. They assert the two halves of identity that a renumbering
breaks: the same place must keep its person's uid, and a uid must not come to mean a
different place. The second is the dangerous half, because it fails silently -- a consumer
holding `hero-castellan-fortress-0` across an advance gets a real person at a real
fortress, and the wrong one.

Built on the hand-built cast world, so no world is generated.
"""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / 'tests'))

import hero_generator

import test_hero_countryside as countryside_fixture
import test_hero_generator as cast_fixture

ALDER = 0


def before_advance():
    """The fixture world: one fortress, ordinal 0, standing on node 13."""
    return countryside_fixture.countryside_world()


def after_advance():
    """The same ground after an age advance that seated a better-defended fortress.

    Nothing about node 13 changed -- same ground, same city, same defence score. A new
    fortress on node 14 simply scored higher, and because the ordinal is the position in a
    list sorted by `defence_score`, it takes `fortress-0` and node 13 becomes `fortress-1`.
    This is the ordinary case, not a contrived one: `terrain_humans` re-runs that sort from
    scratch every age.
    """
    world = countryside_fixture.countryside_world()
    core = world['settlements']['sites'][ALDER]['id']
    world['humans']['fortresses'] = [
        {'id': 'fortress-0', 'kind': 'fortress', 'node': 14, 'x': 14, 'z': 0,
         'core_id': core, 'defence_score': 9.},
        {'id': 'fortress-1', 'kind': 'fortress', 'node': 13, 'x': 13, 'z': 0,
         'core_id': core, 'defence_score': 3.},
    ]
    return world


def cast(world):
    block = hero_generator.generate(world, cast_fixture.certain())
    assert block['status'] == 'ok', block.get('status')
    return block


def castellans(block, world):
    """Every castellan, indexed by the node of the fortress it actually garrisons.

    The person record carries the fortress id, not the node, so the join goes through the
    world -- which is the defect in miniature: the id alone does not say where anyone is.

    Both spellings are accepted deliberately. Today `presence.uid` is the ordinal id, so the
    ordinal map is what resolves. When the fix lands and it becomes `fortress-node-<n>`, the
    node map resolves instead and this harness keeps working -- so a green harness after the
    fix means the harness followed the product, not that it stopped looking. Node first,
    because the node key is the answer the fix is supposed to give.
    """
    by_id = {f['id']: f for f in world['humans']['fortresses']}
    by_node = {f"fortress-node-{f['node']}": f for f in world['humans']['fortresses']}
    found = {}
    for person in block['people']:
        if person.get('role') != 'castellan':
            continue
        anchor = person['presence']['uid']
        fortress = by_node.get(anchor) or by_id.get(anchor)
        if fortress is not None:
            found[fortress['node']] = person
    return found


def uid_nodes(block, world):
    """uid -> the node that uid names, for asking whether a uid changed its meaning."""
    return {person['uid']: node for node, person in castellans(block, world).items()}


class HarnessControlTests(unittest.TestCase):
    """Passes. The failures below only mean something once this does.

    Both failing tests report that two uids differ. Two uids also differ when a fixture
    precipitates nobody, or picks a different person, or when `certain()` stops making
    every candidate certain. So: the same world twice must give the same person the same
    uid, and node 13 must actually have a castellan to talk about.
    """

    def test_the_same_world_twice_names_the_same_castellan(self):
        world = before_advance()
        first, second = cast(world), cast(world)
        self.assertIn(13, castellans(first, world), 'no castellan on node 13 to reason about')
        self.assertEqual(uid_nodes(first, world), uid_nodes(second, world))

    def test_the_advance_fixture_moves_only_the_ordinal(self):
        """The renumbered world must differ from the first in numbering alone."""
        before, after = before_advance(), after_advance()
        kept = next(f for f in after['humans']['fortresses'] if f['node'] == 13)
        original = next(f for f in before['humans']['fortresses'] if f['node'] == 13)
        self.assertEqual({k: v for k, v in kept.items() if k != 'id'},
                         {k: v for k, v in original.items() if k != 'id'})
        self.assertNotEqual(kept['id'], original['id'])


class SiteIdStabilityTests(unittest.TestCase):

    def test_the_castellan_of_a_fortress_that_did_not_move_keeps_its_uid(self):
        """Same ground, same city, same garrison, same person -- and a new name for them.

        A story layer, a save file or a quest that referred to this person before the
        advance cannot find them after it, and nothing reports that anything happened.
        """
        before, after = before_advance(), after_advance()
        was = castellans(cast(before), before)[13]
        now = castellans(cast(after), after)[13]
        self.assertEqual(was['uid'], now['uid'],
                         f'the castellan on node 13 was {was["uid"]} and is now {now["uid"]}: '
                         'the uid follows the ordinal position of the fortress in a list that '
                         '`terrain_humans` re-sorts by defence score every age.')

    def test_a_uid_does_not_come_to_mean_a_different_place(self):
        """The dangerous half: the old uid still resolves, to somebody else.

        This is the failure `npc_roster/sites.py` describes -- "how a consumer joins the
        wrong rows without an error". There is no error. The uid is live, the person is
        real, the fortress is real, and it is not the one the consumer meant.
        """
        before, after = before_advance(), after_advance()
        was, now = uid_nodes(cast(before), before), uid_nodes(cast(after), after)
        moved = {uid: (was[uid], now[uid]) for uid in set(was) & set(now) if was[uid] != now[uid]}
        self.assertEqual(moved, {},
                         f'these uids name different ground after the advance: {moved} '
                         '(uid -> (node before, node after))')

    def test_a_castellan_is_anchored_to_its_fortress_by_something_that_persists(self):
        """The rule the other three packages adopted, stated once as a check.

        `npc_roster` keys `fortress-node-13`, `terrain_villains` anchors to a ley node id,
        and `npc_roster` refuses `culture_id` on the same grounds. The cast spends the
        ordinal in four places, so a fix that repairs `uid` alone still leaves three ways
        to join the wrong row.

        The ordinal is read out of the WORLD, and it used to be read off the person:

            ordinal = person['presence']['uid']

        `presence.uid` is one of the four fields checked below, so that line compared a
        field against itself and made it an offender for ANY value it could ever hold --
        including `fortress-node-13`, the value the fix is supposed to produce. The
        assertion could not hold however the product changed, so this test was pinned to
        fail forever rather than pinned to a defect. Taking the ordinal from
        `world['humans']['fortresses']` asks the question that was meant: does the person
        record carry the number that renumbers? It is still red today, because the answer
        is yes, four times.
        """
        world = after_advance()
        person = castellans(cast(world), world)[13]
        ordinal = next(f['id'] for f in world['humans']['fortresses'] if f['node'] == 13)
        carried = {'uid': person['uid'],
                   'presence.uid': person['presence']['uid'],
                   'claim.target_uid': person['claim']['target_uid'],
                   'deeds[0].event_id': person['deeds'][0]['event_id']}
        offenders = {field: value for field, value in carried.items() if ordinal in str(value)}
        self.assertEqual(offenders, {},
                         f'{ordinal} is an ordinal that renumbers every age, and it is carried '
                         f'in {sorted(offenders)}. Node 13 is the handle that survives; a key '
                         'spelling it out -- `fortress-node-13` -- also cannot be confused with '
                         'the ordinal space, which is why `npc_roster` writes it that way.')


if __name__ == '__main__':
    unittest.main()
