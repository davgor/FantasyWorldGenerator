"""`status` across the published contracts: one field name, seven namespaces.

Enumerated by walking every `*.schema.json` in `Contracts/` for a property literally named
`status`, rather than by reading them. Fourteen declaration sites, seven distinct enums:

    heroes / npcs / story_web / key_locations / key_location_plans
                                 block-level   ok | failed
    heroes.people[], heroes.dreads[]           living | legend
    npcs.people[]                              alive | dead
    villains.people[]                          living | fallen
    key_location_plans.plans[]                 complete | empty
    city / hamlet / castle plan items          complete | partial | unbuildable
    asset_list.assets[]                        supported | unreachable | schematic | not_started

Two of the three defects this module was written against have since been closed, and the
count above is where it shows: `asset_list.assets[].status` was a free `string` with no enum
at all, and `villains.people[].status` was emitted into the world with no schema anywhere.
`Contracts/schemas/villains.schema.json` and the asset-list enum closed both, which is why
`test_every_status_a_block_emits_is_constrained_by_its_contract` now passes. It also added
`living` to a second vocabulary, so the overload finding below grew rather than shrank.

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

**And two tokens already mean two things each.** `complete` is in
`key_location_plans.plans[]`, where it says a plan has contents, and in the city/hamlet/castle
plan items, where it says an item was fully placed. A consumer matching
`status == 'complete'` across plan blocks is comparing two different questions and will never
be told. `living` joined it when the villains schema was published: it is a hero who has not
become a legend and a villain who has not fallen, and the complement differs, so a consumer
that learned `living` from `hero-generator.schema.json` learned the wrong other half.

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


def status_objects(node, path=''):
    """The same walk as `status_sites`, yielding the declaration object rather than a summary.

    Kept separate rather than widening `status_sites` to a four-tuple: three tests below
    unpack that one, and a shape change to a walker they share would be a change to what
    they assert made silently, on the way past.
    """
    if isinstance(node, dict):
        for key, value in node.items():
            if key == 'status' and isinstance(value, dict):
                yield path + '/status', value
            yield from status_objects(value, f'{path}/{key}')
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from status_objects(value, f'{path}/{index}')


def declarations():
    """{(schema file, path within it): the declaration object} for every `status` site."""
    out = {}
    for path in sorted(SCHEMAS.glob('*.schema.json')):
        doc = json.loads(path.read_text(encoding='utf-8'))
        for where, decl in status_objects(doc):
            out[(path.name, where)] = decl
    return out


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


def textual_status_sites():
    """A second count of the `status` declarations, taken from raw text rather than a walk.

    `status_sites` descends the parsed document. This counts the literal `"status": {` in
    the bytes. Two routes to the same number, so a walker that starts annexing
    `route_status` -- the near-miss a `path.endswith('status')` test would have made, and
    `"route_status": {` does not contain `"status": {` -- or one that stops descending into
    a container disagrees with this immediately.

    This is what the control below asserts instead of a literal total. A total is a fact
    about how many schemas `Contracts/` happens to hold today, and it is wrong the moment
    someone legitimately adds one.
    """
    return sum(path.read_text(encoding='utf-8').count('"status": {')
               for path in sorted(SCHEMAS.glob('*.schema.json')))


# The sites the module docstring reasons about, named rather than counted. A site appearing
# here and not in the walk is a harness failure; a site in the walk and not here is a schema
# somebody added, which is not this control's business.
REASONED_ABOUT = (
    'asset-list.schema.json/properties/assets/items/properties/status',
    'hero-generator.schema.json/properties/status',
    'hero-generator.schema.json/$defs/person/properties/status',
    'hero-generator.schema.json/$defs/dread/properties/status',
    'key-location-plans.schema.json/properties/status',
    'key-location-plans.schema.json/properties/plans/items/properties/status',
    'key-locations.schema.json/properties/status',
    'npc-roster.schema.json/properties/status',
    'npc-roster.schema.json/$defs/person/properties/status',
    'story-web.schema.json/properties/status',
    'world-output.schema.json/properties/city_plans/properties/cities/items/properties/status',
    'world-output.schema.json/properties/hamlet_plans/properties/hamlets/items/properties/status',
    'world-output.schema.json/properties/castle_plans/properties/castles/items/properties/status',
)

LIVE = {'heroes': 'living', 'npcs': 'alive', 'villains': 'living'}
ENDED = {'heroes': 'legend', 'npcs': 'dead', 'villains': 'fallen'}
PEOPLE_SCHEMAS = {'heroes': 'hero-generator.schema.json', 'npcs': 'npc-roster.schema.json'}

# Every `status` a *person record of an emitted block* declares, and the liveness block it
# belongs to. `read-place.schema.json`'s `post` is a read-API projection of `npcs` rather
# than a block contract and is deliberately not here; `person-state-request.schema.json`
# already speaks `present`/`gone` and needs no translation.
PERSON_STATUS_SITES = {
    ('hero-generator.schema.json', '/$defs/person/properties/status'): 'heroes',
    ('hero-generator.schema.json', '/$defs/dread/properties/status'): 'dreads',
    ('npc-roster.schema.json', '/$defs/person/properties/status'): 'npcs',
    ('villains.schema.json', '/properties/people/items/properties/status'): 'villains',
}
# The two states `Sim/icarus_sim/terrain_liveness.py` answers in, and the only values a
# published `liveness` mapping may take.
STATES = ('present', 'gone')


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
        # This asserted `(len(rows), sum(...with an enum...)) == (13, 12)` and it fired for
        # the wrong reason the first time it was touched: publishing
        # `Contracts/schemas/villains.schema.json`, which board/backlog/VILLAINS-NO-SCHEMA.md
        # asks for, made the surface (14, 14) and turned a control that guards the HARNESS
        # into a control that guards the size of `Contracts/`. That is the defect
        # board/backlog/SDET-CEILING-SENTINELS.md describes: a literal that is correct on
        # the day it is written and wrong, silently or noisily, the day the thing it counts
        # legitimately moves. So the total is derived from the schema files by a second
        # route, and the sites are named instead of tallied. Adding a fifteenth `status`
        # anywhere in `Contracts/` is expected to leave this green.
        self.assertEqual(len(rows), textual_status_sites(),
                         'the structural walk and a raw-text count of `"status": {` disagree, so '
                         'one of them is answering a different question than the other: '
                         f'{[(r[0] + r[1], r[2]) for r in rows]}')
        missing = [site for site in REASONED_ABOUT if site not in {r[0] + r[1] for r in rows}]
        self.assertEqual(missing, [],
                         f'the walk no longer finds sites this module argues about: {missing}')
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
        """Two ways to be undescribed: no enum, and no schema. NOW PASSES -- both are closed.

        It was written failing. `asset_list.assets[].status` was a free `string`, so the
        contract permitted any value and described none, and `villains.people[].status` had
        no schema at all, so a consumer could not discover that `fallen` is a value it must
        handle. An asset-list enum and `Contracts/schemas/villains.schema.json` closed both.

        It stays because the two ways of being undescribed are permanent shapes, not
        one-off mistakes: the next block published without an enum, or emitted without a
        schema, fails here without anyone having to notice it. The assertion is over the
        whole surface, not over those two sites, so it does not need editing to cover a
        fifteenth.
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


class PublishedLivenessMappingTests(unittest.TestCase):
    """The three failures above are not fixed here, and that is deliberate.

    They pin a token divergence that only a rename of three shipped enums can close, and
    `docs/decisions/030-magnitude-and-identity-conventions.md` C1 part 3 rules that no
    shipped schema is renamed. `board/backlog/SDET-STATUS-VOCABULARY.md` names the other
    option the Contracts owner had -- *a `liveness` sibling keyword on each person-level
    `status`* -- and that is what these tests hold.

    What the annotation buys is the thing the card actually asks for: **the mapping is
    published**. It existed only as Python (`Sim/icarus_sim/terrain_liveness.py`) and,
    before that, only as one hand-written expression inside a private record builder. A
    consumer reading exported JSON and the schemas beside it -- the roadmap phase 2
    reader -- could not see it at all. Now each person-level `status` carries a `liveness`
    object mapping each of its own tokens to `present` or `gone`, so the translation is
    readable from the contract without running the generator.

    What it does not buy is one token. `status == 'living'` is still right twice and wrong
    once, and the three tests above still say so.
    """

    def test_the_sites_this_class_maps_are_the_blocks_the_predicate_knows(self):
        """Control. Every test below iterates `PERSON_STATUS_SITES`, and iterating an empty
        or stale mapping agrees with anything."""
        from icarus_sim.terrain_liveness import GONE_STATUS, PRESENT_STATUS

        self.assertEqual(set(PERSON_STATUS_SITES.values()), set(PRESENT_STATUS),
                         'terrain_liveness answers for a set of blocks this module does not map, '
                         'or the other way round, so the agreement test below is comparing a '
                         'subset and calling it the surface')
        self.assertEqual(set(PRESENT_STATUS), set(GONE_STATUS))
        found = declarations()
        missing = sorted(site for site in PERSON_STATUS_SITES if site not in found)
        self.assertEqual(missing, [],
                         f'a person `status` this class maps is no longer at that path: {missing}')

    def test_every_person_status_declaration_publishes_its_liveness_mapping(self):
        """A consumer that cannot run Python still has to be able to ask who is here."""
        found = declarations()
        without = sorted(f'{name}{where}' for name, where in PERSON_STATUS_SITES
                         if not (found.get((name, where)) or {}).get('liveness'))
        self.assertEqual(without, [],
                         f'these person `status` declarations publish an enum but no mapping from '
                         f'its tokens to liveness: {without}. The live token is `living` for heroes, '
                         '`alive` for npcs and `living` for villains, so a consumer reading only the '
                         'schema has to guess which word this block uses, and guessing `living` is '
                         'right twice and silently wrong once.')

    def test_the_published_mapping_is_total_over_the_enum_and_two_valued(self):
        """A partial mapping is worse than none: it answers for some records and not others."""
        found = declarations()
        for (name, where), block in sorted(PERSON_STATUS_SITES.items()):
            with self.subTest(block=block):
                decl = found[(name, where)]
                tokens = set(decl.get('enum') or ())
                mapping = decl.get('liveness') or {}
                self.assertEqual(set(mapping), tokens,
                                 f'{name}{where}: the mapping covers {sorted(mapping)} and the enum '
                                 f'declares {sorted(tokens)}; a token with no entry is a record no '
                                 'consumer can resolve, and an entry with no token is a value the '
                                 'contract says cannot occur')
                self.assertEqual(set(mapping.values()) - set(STATES), set(),
                                 f'{name}{where}: a liveness state outside {STATES}')
                self.assertEqual(sorted(mapping.values()).count('present'), 1,
                                 f'{name}{where}: exactly one token means still here')

    def test_the_published_mapping_agrees_with_the_predicate_that_implements_it(self):
        """Two statements of one rule is the defect `terrain_liveness` exists to prevent.

        The schema is the published half and the module is the running half, so they are
        compared rather than one being derived from the other -- a derivation would make
        this test compare a value with itself.
        """
        from icarus_sim.terrain_liveness import GONE_STATUS, PRESENT_STATUS

        found = declarations()
        for (name, where), block in sorted(PERSON_STATUS_SITES.items()):
            with self.subTest(block=block):
                mapping = found[(name, where)].get('liveness') or {}
                self.assertEqual(mapping.get(PRESENT_STATUS[block]), 'present',
                                 f'{name}{where}: terrain_liveness writes '
                                 f'{PRESENT_STATUS[block]!r} for a person who is still here and the '
                                 'contract does not say so')
                self.assertEqual(mapping.get(GONE_STATUS[block]), 'gone',
                                 f'{name}{where}: terrain_liveness writes {GONE_STATUS[block]!r} for '
                                 'a person who is gone and the contract does not say so')

    def test_the_published_mapping_resolves_a_real_record_the_same_way_the_predicate_does(self):
        """End to end, on a record of each block's own shape rather than on the tables.

        The three tests above compare two descriptions of the rule. This one applies both
        to a record, including the absent-status case, which is the clause every consumer
        gets wrong: a record written before its package recorded departure described
        someone who stood, so a missing `status` is `present` and not `gone`.
        """
        from icarus_sim.terrain_liveness import liveness

        found = declarations()
        for (name, where), block in sorted(PERSON_STATUS_SITES.items()):
            mapping = found[(name, where)].get('liveness') or {}
            # Without this the token loop below is empty when the annotation is missing and
            # the absent-status clause carries the whole test, which is a green that means
            # nothing. It was exactly that on the first run.
            self.assertTrue(mapping, f'{name}{where}: no mapping to apply')
            for token, state in sorted(mapping.items()):
                with self.subTest(block=block, token=token):
                    self.assertEqual(liveness({'status': token}, block), state)
            with self.subTest(block=block, token='<absent>'):
                self.assertEqual(liveness({}, block), 'present',
                                 'an absent status must read as present, or every world '
                                 'generated before its package recorded departure becomes a '
                                 'world of ghosts')


if __name__ == '__main__':
    unittest.main()
