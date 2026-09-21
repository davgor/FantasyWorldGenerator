"""`villain` names two unrelated things, and every place a reader meets it must say so.

**`icarus_sim.terrain_villains`** — a super villain is a *field*: a continuous tier, a reach in
metres, a seat, held ley nodes, claims. At most one per cultural region. It lives in the
`villains` block and has its own schema.

**`hero_generator` and `story_web`** — `villain:prior_age` is a *feature token on an ordinary
person*. `features.py` sets it on a pretender whose civilization refounded a city after they
were born: a dispossessed claimant, with no tier, no reach and no seat. It travels into
`story_web` as a derivable fact and is listed in `weights.json` as a feature a runtime event can
*add* to somebody.

The two share no field, no id space and no derivation. Nothing collides at runtime, because the
packages never import each other -- that is the architecture working. It collides in a reader,
and the dangerous case is specific: the correct answer to "did a super villain stand here in a
prior age?" is currently *unavailable* (see VILLAIN-FALL-UNRECORDED), and this token is what
someone asking that question finds first.

So the tests below are of two kinds, and the distinction matters:

* the **controls** assert the collision is real and harmless in code -- a world can carry the
  token with an empty `villains` block, and a seated super villain who is in nobody's feature
  list. They pass today and must keep passing; they are what makes the rest mean anything.
* the **disambiguation** tests assert that the three documents a consumer would read, and the
  two source lines that define the token, each say the other `villain` exists and is unrelated.
  Those are the ones that were red.

VOCABULARY-VILLAIN-TWO-AXES records why this was answered with words rather than a rename, and
what the rename would cost if the owner reverses that.
"""
import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / 'tests'))

import hero_generator
from hero_generator import archetypes as hero_archetypes
from story_web import facts as web_facts

ROOT = pathlib.Path(__file__).resolve().parents[2]
TOKEN = 'villain:prior_age'

# Every document a consumer meeting one `villain` would read to understand the other.
DOCUMENTS = ('docs/hero-generator.md', 'docs/story-web.md', 'docs/super-villains.md')

# The two module-level declarations of the feature vocabulary. A grep for `villain` across
# `Sim/` lands on these before it lands on any prose.
DEFINITIONS = ('Sim/hero_generator/features.py', 'Sim/story_web/facts.py')


def _text(relative):
    return (ROOT / relative).read_text(encoding='utf-8')


class Controls(unittest.TestCase):
    """The collision is real, and it is only a collision of words. These pass today."""

    def test_the_token_is_a_declared_feature_of_both_reader_packages(self):
        self.assertIn(TOKEN, hero_archetypes.FEATURES)
        self.assertIn(TOKEN, web_facts.FACTS)

    def test_a_person_can_carry_the_token_with_no_villains_block_in_the_world(self):
        """A dispossessed pretender is not a super villain, and needs no villain to exist.

        The token fires on a pretender whose civilization founded a city after they were born,
        so the fixture's founding age is moved rather than a villain being added: this world has
        no `villains` key at all, and two people carry the token in it.
        """
        import test_hero_generator as cast_fixture
        world = cast_fixture.world()
        world['settlements']['sites'][0]['founded_age'] = 2
        self.assertNotIn('villains', world)
        block = hero_generator.generate(world, cast_fixture.certain())
        carriers = [p for p in block['people'] if TOKEN in p['selectable']]
        self.assertTrue(carriers, 'the fixture no longer precipitates a dispossessed pretender')
        for person in carriers:
            self.assertEqual(person['role'], 'pretender')
            for field in ('region', 'reach_m', 'growth', 'held_nodes', 'seat_uid'):
                self.assertNotIn(field, person,
                                 f'{field} belongs to a super villain; a feature token carries none of them')

    def test_the_two_vocabularies_share_one_field_name_and_it_means_two_things(self):
        """Read off the published contracts, not from memory.

        The one name in common is `tier`, and it is the trap in miniature: a hero's tier is one
        of three words (`notable`, `renowned`, `legendary`) while a super villain's is a
        continuous number that converts to a reach in metres. Everything else is disjoint.
        """
        villain = json.loads((ROOT / 'Contracts/schemas/villains.schema.json').read_text(encoding='utf-8')
                             )['properties']['people']['items']['properties']
        person = json.loads((ROOT / 'Contracts/schemas/hero-generator.schema.json').read_text(encoding='utf-8')
                            )['$defs']['person']['properties']
        shared = set(villain) & set(person)
        self.assertEqual(shared, {'born_age', 'log', 'school', 'status', 'tier', 'uid', 'well'},
                         'the overlap between the two vocabularies moved; re-read both contracts')
        self.assertEqual(villain['tier']['type'], 'number')
        self.assertEqual(person['tier']['enum'], ['notable', 'renowned', 'legendary'])


class Disambiguation(unittest.TestCase):
    """Each place a reader meets one `villain` names the other and says it is unrelated."""

    def test_every_document_names_the_other_villain(self):
        missing = []
        for relative in DOCUMENTS:
            text = _text(relative)
            if TOKEN not in text or 'unrelated' not in text:
                missing.append(relative)
        self.assertEqual(missing, [],
                         'these documents do not tell a reader that the other `villain` exists '
                         f'and is unrelated to the one they are reading about: {missing}')

    def test_both_definition_sites_disclaim_the_other_villain(self):
        missing = []
        for relative in DEFINITIONS:
            text = _text(relative)
            if 'terrain_villains' not in text:
                missing.append(relative)
        self.assertEqual(missing, [],
                         'a grep for `villain` across Sim/ lands here first, so here is where '
                         f'the disclaimer has to be: {missing}')

    def test_the_super_villain_document_points_back_at_the_feature_token(self):
        """The dangerous direction: someone looking for villain history finds the token first."""
        text = _text('docs/super-villains.md')
        self.assertIn(TOKEN, text)
        self.assertIn('hero_generator', text)


if __name__ == '__main__':
    unittest.main()
