"""Generated documents must satisfy the published Contracts/ schemas.

Before this existed the schemas were hand-edited per section and drifted: the
city-plan contract reached version 6 and gained a fortification pass while
world-output.schema.json still declared version 4 and the old phase order.
Nothing failed, because no test ever compared real output against the schema
that Unreal consumers are told to build against.
"""

import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
sys.path.insert(0, str(ROOT / 'Sim'))

from schema_subset import errors, validate


def schema(name):
    return json.loads((ROOT / 'Contracts/schemas' / name).read_text(encoding='utf-8'))


class WorldSchemaConformanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from fantasy_world_generator.cli import world_document
        # Small enough to stay quick, large enough to populate every planner section.
        cls.world = world_document({'recipe_version': 3, 'seed': 42, 'overrides': {'size': 17}})

    def test_generated_world_satisfies_the_published_world_schema(self):
        validate(self.world, schema('world-output.schema.json'))

    def test_generated_world_exercises_every_versioned_section(self):
        """A conformance pass is only meaningful if the sections are actually present."""
        for section in ('terrain', 'settlements', 'civilizations', 'city_plans',
                        'hamlet_plans', 'castle_plans', 'world_scene'):
            with self.subTest(section=section):
                self.assertIn(section, self.world)
        self.assertTrue(self.world['city_plans']['cities'], 'seed 42 size 17 must plan at least one city')

    def test_asset_list_satisfies_its_published_schema(self):
        from fantasy_world_generator.asset_list import compile_asset_list
        validate(compile_asset_list(), schema('asset-list.schema.json'))

    def test_capabilities_document_satisfies_its_published_schema(self):
        from fantasy_world_generator.capabilities import capabilities_document
        path = ROOT / 'Contracts/schemas/capabilities.schema.json'
        if not path.is_file():
            self.skipTest('no published capabilities schema')
        validate(capabilities_document(), json.loads(path.read_text(encoding='utf-8')))

    def test_validator_reports_a_drifted_version_constant(self):
        """Guard the guard: a stale const must fail rather than pass silently."""
        drifted = schema('world-output.schema.json')
        drifted['properties']['city_plans']['properties']['version']['const'] = 4
        found = list(errors(self.world, drifted))
        self.assertTrue(any('/city_plans/version' in message for message in found), found)


if __name__ == '__main__':
    unittest.main()
