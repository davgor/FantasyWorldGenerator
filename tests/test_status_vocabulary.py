"""`status` across the published contracts: one field name, seven namespaces.

Enumerated by walking every `*.schema.json` in `Contracts/` for a property literally named
`status`, rather than by reading them. Twelve declaration sites, five distinct enums, one
unconstrained, and one more emitted into the world with no schema at all:

    heroes / npcs / story_web / key_locations / key_location_plans
                                 block-level   ok | failed
    heroes.people[], heroes.dreads[]           living | legend
    npcs.people[]                              alive | dead
    key_location_plans.plans[]                 complete | empty
    city / hamlet / castle plan items          complete | partial | unbuildable
    asset_list.assets[]                        any string -- no enum at all
    villains.people[]                          living | fallen -- declared nowhere

Two things follow, and they are separate defects.

**No consumer can ask who is alive.** The live token is `living` for heroes, **`alive`** for
npcs and `living` for villains, so `status == 'living'` is right twice and silently wrong
once. The end token is `legend`, `dead`, `fallen` -- three words for one event, two of them
carrying a judgement the third does not. The only translation between two published
contracts anywhere in the repository is a hand-written expression inside a private record
builder at `Sim/npc_roster/__init__.py:190`:

    'status': 'alive' if person.get('status') == 'living' else 'dead'

That expression is the mapping. It is published nowhere, so every downstream consumer
rediscovers it or gets it wrong.

**And one token already means two things.** `complete` is in `key_location_plans.plans[]`,
where it says a plan has contents, and in the city/hamlet/castle plan items, where it says
an item was fully placed. A consumer matching `status == 'complete'` across plan blocks is
comparing two different questions and will never be told.

**Scope, stated so this is not read as more than it is.** `status` is a *required* property
of a person in both `hero-generator.schema.json` and `npc-roster.schema.json`, so no valid
world omits it, and the fact that `npc_roster` reads a missing value as `dead` while
`terrain_villains.is_standing` reads it as `living` is not asserted here as a defect -- each
default is defensible on its own ground, and the two never both fire. Nor is `route_status`
(`routed | stranded`, in `beast-movements` and `nomads`) counted above: it is a different
field name, and a collision analysis of the name `status` may not borrow it.

The person-versus-block guard passes and is meant to. It bounds the finding to the axis the
evidence actually supports: a consumer cannot read a failed block as a living person,
because those two sets are disjoint. Global disjointness is **not** claimed -- `complete`
disproves it -- and the test below says so by testing the real thing instead.
"""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
sys.path.insert(0, str(ROOT / 'Sim'))

SCHEMAS = ROOT / 'Contracts/schemas'

# The block's own outcome field sits at the document root and nowhere else.
BLOCK_PATH = '/properties/status'
# Where a person's liveness is declared, per schema.
PERSON_PATHS = ('/$defs/person/properties/status', '/$defs/dread/properties/status')


def status_sites(node, path=''):
    """Every property literally named `status`, with its path and its declared values.

    Keyed on the exact name: `route_status` and `plan_status` are different fields and a
    question about the name `status` may not quietly annex them.
    """
    if isinstance(node, dict):
        for key, value in node.items():
            if key == 'status' and isinstance(value, dict):
                yield path + '/status', value.get('enum'), value.get('type')
            yield from status_sites(value, f'{path}/{key}')
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from status_sites(value, f'{path}/{index}')


def published():
    """[(schema file, path within it, tokens or None if unconstrained)] for every site."""
    rows = []
    for path in sorted(SCHEMAS.glob('*.schema.json')):
        doc = json.loads(path.read_text(encoding='utf-8'))
        for where, enum, kind in status_sites(doc):
            rows.append((path.name, where, tuple(enum) if enum else None, kind))
    return rows


def vocabularies():
    """Every distinct declared `status` enum, as a set of token tuples."""
    return {tokens for _, _, tokens, _ in published() if tokens}


def villain_status_tokens():
    """The villain vocabulary, taken from the model rather than from a literal.

    There is no villains schema to read it out of, which is the point of the last test.
    `hold=99.` is an instrument, not a configuration -- the fall is unreachable at every
    legal `villain_hold`, which `Sim/tests/test_villain_fall_reachability.py` establishes --
    and it is used only to make the model emit its second token.
    """
    from icarus_sim import terrain_villains as villains

    class Config:
        settlement_spacing = 1000.

    city = {'id': 'site-1', 'uid': 'city-1', 'node': 7, 'direction': [0., 1., 0.],
            'population_profile': 'human_heartland'}
    world = {
        'effective_config': {'globe_radius': 100000.},
        'settlements': {'sites': [city]},
        'humans': {'cultures': [{'id': 'culture-1', 'city_ids': ['site-1']}]},
        'magic': {'networks': {'weave': {'nodes': [{'id': 'ley-1', 'direction': [0., 1., 0.]}],
                                         'edges': []}}},
        'threat_assessments': {'cities': [{'city_uid': 'city-1', 'regional_threat': 1.,
                                           'war_risk': 0., 'war_hunger': 0., 'war_pressure': 0.,
                                           'nest_pressure': 1., 'ley_pressure': 0.}]},
    }
    villains.advance(world, Config(), 0, rise=1., hold=.7, density=3.)
    seated = {p['status'] for p in world['villains']['people']}
    world['threat_assessments']['cities'][0].update(regional_threat=0., nest_pressure=0.)
    villains.advance(world, Config(), 1, rise=0., hold=99., density=3.)
    return seated | {p['status'] for p in world['villains']['people']}


LIVE = {'heroes': 'living', 'npcs': 'alive', 'villains': 'living'}
ENDED = {'heroes': 'legend', 'npcs': 'dead', 'villains': 'fallen'}
PEOPLE_SCHEMAS = {'heroes': 'hero-generator.schema.json', 'npcs': 'npc-roster.schema.json'}


def person_tokens(block):
    name = PEOPLE_SCHEMAS[block]
    for schema_name, where, tokens, _ in published():
        if schema_name == name and where in PERSON_PATHS:
            return tokens
    return None


class HarnessControlTests(unittest.TestCase):
    """Passes. Every test below compares vocabularies, and comparing nothing with nothing
    agrees, so the sets they compare must first be shown to exist."""

    def test_the_sites_this_module_reasons_about_are_all_present(self):
        rows = published()
        # Thirteen sites, twelve of them with an enum; the thirteenth is the free `string`
        # in asset-list. Both numbers are asserted because the gap between them is one of
        # the two findings, and a control that counted only the enums would hide it.
        self.assertEqual((len(rows), sum(1 for r in rows if r[2])), (13, 12),
                         f'the status surface moved: {[(r[0] + r[1], r[2]) for r in rows]}')
        for block in PEOPLE_SCHEMAS:
            self.assertTrue(person_tokens(block), f'{block}: person status enum moved')
        self.assertEqual(villain_status_tokens(), {'living', 'fallen'})
        self.assertGreaterEqual(len(vocabularies()), 5)

    def test_the_named_tokens_are_the_declared_ones(self):
        """Guards the two hand-written maps above against drifting out of the schemas."""
        for block in PEOPLE_SCHEMAS:
            declared = set(person_tokens(block))
            self.assertEqual(declared, {LIVE[block], ENDED[block]}, block)


class StatusVocabularyTests(unittest.TestCase):

    def test_a_block_outcome_cannot_be_read_as_a_person(self):
        """Passes, and is here so that stops being true audibly.

        `ok`/`failed` on a block and `living`/`legend` on a person share a field name at two
        depths of one document. They are safe to tell apart only because no token is in
        both, and nothing enforces that.
        """
        block = {t for _, where, tokens, _ in published()
                 if where == BLOCK_PATH and tokens for t in tokens}
        person = {t for _, where, tokens, _ in published()
                  if where in PERSON_PATHS and tokens for t in tokens}
        self.assertTrue(block and person, 'both sets must be non-empty for this to mean anything')
        self.assertEqual(block & person, set(),
                         f'{sorted(block & person)} is both a block outcome and a person state, so '
                         'a consumer matching the value alone can no longer tell which it holds')

    def test_no_token_means_two_different_things(self):
        """`complete` does. Two plan vocabularies, two questions, one word.

        `key_location_plans.plans[]` uses `complete` for "this plan has contents";
        the city, hamlet and castle plan items use it for "this item was fully placed". A
        consumer comparing plan blocks on `status == 'complete'` is asking two questions and
        will never be told which one it got.
        """
        shared = {}
        for tokens in vocabularies():
            for token in tokens:
                shared.setdefault(token, []).append(tokens)
        overloaded = {t: sorted(v) for t, v in shared.items() if len(v) > 1}
        self.assertEqual(overloaded, {},
                         f'these tokens appear in more than one `status` vocabulary: {overloaded}')

    def test_one_token_means_alive_across_every_block_that_has_people(self):
        for block in PEOPLE_SCHEMAS:
            self.assertIn(LIVE[block], person_tokens(block), block)
        self.assertIn(LIVE['villains'], villain_status_tokens())
        self.assertEqual(len(set(LIVE.values())), 1,
                         f'the live token differs by block: {LIVE}. A consumer joining a cast to a '
                         'roster cannot write one liveness predicate, and the only translation in '
                         'the repository is a hand-written expression at '
                         "Sim/npc_roster/__init__.py:190 -- \"'alive' if status == 'living' else "
                         '\'dead\'" -- published nowhere.')

    def test_one_token_means_no_longer_alive_across_every_block_that_has_people(self):
        for block in PEOPLE_SCHEMAS:
            self.assertIn(ENDED[block], person_tokens(block), block)
        self.assertIn(ENDED['villains'], villain_status_tokens())
        self.assertEqual(len(set(ENDED.values())), 1,
                         f'three blocks, three words for the same end: {ENDED}. `legend` and '
                         '`fallen` also carry a judgement `dead` does not, so a consumer cannot map '
                         'them without first deciding what a legend is.')

    def test_every_status_a_block_emits_is_constrained_by_its_contract(self):
        """Two ways to be undescribed: no enum, and no schema.

        `asset_list.assets[].status` is declared as a free `string`, so the contract permits
        any value and describes none. `villains.people[].status` has no schema at all, so a
        consumer cannot discover that `fallen` is a value it must handle -- nor that, as
        `test_villain_fall_reachability` shows, no world it will ever be given can contain
        one, which makes a handler for it dead code that looks defensive.
        """
        unconstrained = sorted({f'{name}{where}' for name, where, tokens, kind in published()
                                if not tokens})
        declared = {t for tokens in vocabularies() for t in tokens}
        undeclared = sorted(villain_status_tokens() - declared)
        self.assertEqual((unconstrained, undeclared), ([], []),
                         f'declared as a free string: {unconstrained}; emitted but in no schema: '
                         f'{undeclared}. `living` happens to be declared, but by '
                         '`hero-generator.schema.json` for a different block, so a consumer that '
                         'found it there learned the wrong complement -- a hero who is not `living` '
                         'is a `legend`, a villain who is not `living` is `fallen`.')


if __name__ == '__main__':
    unittest.main()
