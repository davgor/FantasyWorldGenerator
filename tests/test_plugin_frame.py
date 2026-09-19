"""The plugin carries no second copy of the generator rules.

The Unreal module wraps Core/; it must not restate the frame conversion, the request
bounds or the recipe version. A pass here is a source-level check: it is not an Unreal
Build Tool compile, an editor load or a cooked-runtime result. The rules themselves are
tested against the Python oracle in test_native_world.py.
"""
import json
from pathlib import Path
import sys
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))

import package_plugin

PLUGIN = ROOT / 'Unreal/FantasyWorldGenerator'
MODULE = PLUGIN / 'Source/FantasyWorldGenerator'
CORE = ROOT / 'Core'


class PluginCoreLinkTests(unittest.TestCase):
    def test_the_temporary_frame_mirror_is_gone(self):
        self.assertFalse((MODULE / 'Public/FantasyWorldGeneratorFrame.h').exists(),
                         'the mirrored frame header must not come back; Core owns the mapping')
        self.assertFalse((MODULE / 'Private/FantasyWorldGeneratorCoreContract.cpp').exists(),
                         'the mirror drift guard is unnecessary once Core is compiled in')

    def test_no_plugin_source_restates_a_core_constant(self):
        # Core owns these numbers. A literal here would be a second source of truth that
        # can drift without any test noticing.
        forbidden = ('4294967295', 'genesis_recipe = 3', 'MaximumRasterSize', 'MinimumRasterSize',
                     'UnrealCentimetresPerMetre')
        for path in sorted(MODULE.rglob('*')):
            if path.is_dir() or path.suffix not in ('.h', '.cpp', '.inl'):
                continue
            if path.parts[-2:] == ('FantasyWorldGeneratorCore',):
                continue
            text = path.read_text(encoding='utf-8')
            for literal in forbidden:
                self.assertNotIn(literal, text, f'{path.name} restates a Core rule: {literal}')

    def test_build_rules_compile_core_when_vendored_and_say_so(self):
        text = (MODULE / 'FantasyWorldGenerator.Build.cs').read_text(encoding='utf-8')
        self.assertIn('FantasyWorldGeneratorCore', text, 'the module must find the vendored Core tree')
        self.assertIn('FANTASY_WORLD_GENERATOR_CORE_LINKED', text,
                      'a host has to be able to tell a linked build from a headers-only one')
        self.assertIn('bEnableExceptions = true', text, 'Core reports failures as exceptions')
        self.assertIn('RuntimeDependencies', text, 'the registry table must be staged into a cooked build')

    def test_packaged_plugin_vendors_core_byte_for_byte(self):
        payload = package_plugin.plugin_files()
        vendored = {name[len(package_plugin.VENDORED_CORE):]: data
                    for name, data in payload.items() if name.startswith(package_plugin.VENDORED_CORE)}
        expected = {}
        for path in sorted(CORE.rglob('*')):
            if path.is_dir() or 'tests' in path.relative_to(CORE).parts:
                continue
            if path.suffix == '.md' or path.name in package_plugin.CORE_SOURCES_NOT_VENDORED:
                continue
            expected[path.relative_to(CORE).as_posix()] = path.read_bytes()
        self.assertEqual(sorted(vendored), sorted(expected), 'vendored Core must mirror the repository tree')
        for name, data in expected.items():
            self.assertEqual(vendored[name], data, f'vendored {name} differs from Core/{name}')
        for required in ('world.cpp', 'tectonics.cpp', 'history.cpp', 'climate.cpp', 'biomes.cpp',
                         'hydrology.cpp', 'globe.cpp', 'pyrandom.cpp', 'registry.cpp', 'frame.cpp'):
            self.assertIn(required, vendored, 'the generate path must be compiled into the module')

    def test_registry_table_travels_with_the_plugin(self):
        payload = package_plugin.plugin_files()
        self.assertIn(package_plugin.REGISTRY_TARGET, payload)
        table = json.loads(payload[package_plugin.REGISTRY_TARGET])
        self.assertEqual(table['schema'], 'fantasy-world-generator.unreal-asset-registry')
        self.assertGreater(len(table['rows']), 1000)


if __name__ == '__main__':
    unittest.main()
