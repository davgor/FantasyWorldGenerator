"""How much of a world `world-output.schema.json` actually describes.

`test_world_schema_conformance.py` validates a generated world against this schema and
passes, which reads as "the published contract matches the product". It does not establish
that, because passing is close to unconditional: the schema has `additionalProperties:
true`, declares 17 properties, and requires 6 -- `schema`, `schema_version`,
`generator_version`, `config`, `layers` and `recipe`. Three of those six are constants and
the other three need only be objects.

So a document carrying six keys and no world at all satisfies the contract that the
`docs/unreal-integration.md` audience is told to build against. Deleting `settlements`,
`heroes`, `npcs`, `nomads`, `key_locations` and every other content block from a real world
does not make it invalid, because none of them is required and the ones that are not
declared are waved through by the open root.

That is not an argument about style. A consumer generates its import code from a contract;
this one tells it that a world may legitimately arrive with nothing in it, so either the
consumer hand-writes the real shape -- in which case the schema is not the contract -- or
it trusts this and breaks on the first world that omits a block for a reason the schema
never mentions.

`STATE_KEYS` is used below as the list of blocks a consumer actually sees, because it is
the simulation's own answer to "what is a block": the tuple `terrain_history` carries
across an age boundary. It is maintained by the people adding blocks, so this test tracks
the product rather than a list copied here that would go stale.

Expected to fail, except the control.
"""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
sys.path.insert(0, str(ROOT / 'Sim'))

from schema_subset import errors as _errors


def errors(value, schema):
    """`schema_subset.errors` is a generator, so a bare truth test on it is always true.

    Every assertion in this module turns on whether the validator complained. A generator
    object is truthy whether it would yield anything or not, so calling the library
    function directly makes each of these tests pass unconditionally -- which is what
    happened when they were first written, including the control that was supposed to
    catch precisely this. A control only guards against failure modes it does not share.
    """
    return list(_errors(value, schema))

SCHEMA = json.loads((ROOT / 'Contracts/schemas/world-output.schema.json').read_text(encoding='utf-8'))

# Every key the schema demands, filled with the least it will accept. `recipe` is the only
# required property with required contents of its own, and those four are a version const,
# a seed integer and two objects that may be empty. `config` and `layers` declare no
# required keys at all, so `{}` satisfies both -- a world with no terrain grid in it.
EMPTY_WORLD = {'schema': 'fantasy-world-generator.world', 'schema_version': 2,
               'generator_version': 16, 'config': {}, 'layers': {},
               'recipe': {'version': 3, 'seed': 0, 'resolved': {}, 'provenance': {}}}

# The sections `test_world_schema_conformance.test_generated_world_exercises_every_versioned_section`
# asserts a real world carries. A contract that does not ask for what the product's own
# conformance test insists on is describing a different artifact.
VERSIONED_SECTIONS = ('terrain', 'settlements', 'civilizations', 'city_plans', 'hamlet_plans',
                      'castle_plans', 'world_scene', 'astrology', 'lunar_almanac', 'religion')


def state_keys():
    from icarus_sim.terrain_history import STATE_KEYS
    return STATE_KEYS


class HarnessControlTests(unittest.TestCase):
    """Passes. Everything below reports that the validator found nothing wrong, and a
    validator that never finds anything wrong reports exactly the same."""

    def test_the_validator_rejects_a_document_it_should_reject(self):
        wrong = dict(EMPTY_WORLD, schema_version=1)
        self.assertTrue(errors(wrong, SCHEMA), 'the validator accepts a retired schema_version')
        self.assertTrue(errors({k: v for k, v in EMPTY_WORLD.items() if k != 'config'}, SCHEMA),
                        'the validator accepts a document with a required key missing')


class WorldSchemaSurfaceTests(unittest.TestCase):

    def test_a_world_with_no_world_in_it_is_not_a_valid_world(self):
        """Six top-level keys, an empty `layers` and a stub `recipe`."""
        found = errors(EMPTY_WORLD, SCHEMA)
        self.assertTrue(found,
                        f'a document with only {sorted(EMPTY_WORLD)} satisfies '
                        'world-output.schema.json. No terrain grid, no settlements, no people, no '
                        'plans -- `config` and `layers` are empty objects and every content block '
                        'is absent -- and it is a conforming world.')

    def test_the_schema_requires_the_sections_the_conformance_suite_requires(self):
        required = set(SCHEMA.get('required') or ())
        missing = [s for s in VERSIONED_SECTIONS if s not in required]
        self.assertEqual(missing, [],
                         'the suite asserts a generated world carries these and the published '
                         f'contract does not ask for them: {missing}. A consumer reading the '
                         'schema cannot tell that any of them is always present, so it must '
                         'either duplicate this list by hand or treat all of them as optional.')

    def test_every_block_the_simulation_carries_is_at_least_described(self):
        """Declared, not required -- a block a consumer meets should have a stated shape.

        The weaker of the two asks: this does not argue any block must be present, only
        that the contract should say what one looks like when it is.
        """
        declared = set(SCHEMA.get('properties') or ())
        undescribed = sorted(k for k in state_keys() if k not in declared)
        self.assertEqual(undescribed, [],
                         f'{len(undescribed)} of {len(state_keys())} blocks the simulation carries '
                         f'across an age boundary have no shape in the published contract, and the '
                         f'root is `additionalProperties: true`, so each arrives unannounced and '
                         f'unvalidated: {undescribed}')


if __name__ == '__main__':
    unittest.main()
