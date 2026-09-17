"""Headless native genesis slice: Unreal centimetre frame and generate-request validation."""
import json
import os
import sys
import tempfile
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
sys.path.insert(0, str(ROOT / 'Sim'))

from native_cxx import compile_native, compiler_command
from fantasy_world_generator.kernel_numeric import canonical_bytes
from fantasy_world_generator.kernel_contract import KernelError


class NativeGenesisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if compiler_command() is None:
            raise unittest.SkipTest('native genesis requires a C++17 compiler')
        for relative in ('Core/genesis.hpp', 'Core/genesis.cpp', 'Core/tests/genesis_driver.cpp'):
            if not (ROOT / relative).is_file():
                raise AssertionError('missing ' + relative + '; native world generate API is not implemented')
        cls.directory = tempfile.TemporaryDirectory(prefix='fantasy-world-generator-genesis-')
        cls.addClassCleanup(cls.directory.cleanup)
        cls.binary = Path(cls.directory.name) / ('genesis.exe' if os.name == 'nt' else 'genesis')
        sources = [ROOT / 'Core' / name for name in
                   ('json.cpp', 'numeric.cpp', 'counter.cpp', 'wire.cpp', 'genesis.cpp', 'tests/genesis_driver.cpp')]
        compile_native(sources, ROOT / 'Core', cls.binary)

    def run_native(self, operation, value):
        result = subprocess.run([str(self.binary), operation], input=canonical_bytes(value),
                                capture_output=True, timeout=10)
        if result.returncode:
            self.assertEqual(result.returncode, 2, result.stderr)
            failure = json.loads(result.stdout)
            self.assertEqual(failure['schema'], 'fantasy-world-generator.failure')
            raise KernelError(failure['code'])
        return json.loads(result.stdout)

    def test_source_tangent_becomes_unreal_z_up_centimetres(self):
        fixtures = json.loads((ROOT / 'Fixtures/unreal-frame-v1.json').read_text())
        for case in fixtures['valid']:
            with self.subTest(name=case['name']):
                result = self.run_native('unreal_cm', {
                    'east_m': case['east_m'], 'up_m': case['up_m'], 'north_m': case['north_m']})
                self.assertEqual(result, case['expected_cm'])

    def test_generate_request_rejects_retired_recipe_and_invalid_seed_size(self):
        fixtures = json.loads((ROOT / 'Fixtures/unreal-frame-v1.json').read_text())
        for body in fixtures['invalid_generate']:
            with self.subTest(body=body), self.assertRaises(KernelError):
                self.run_native('validate_generate', body)

    def test_valid_generate_request_is_accepted_without_python(self):
        result = self.run_native('validate_generate', {'recipe_version': 3, 'seed': 42, 'overrides': {'size': 65}})
        self.assertEqual(result['ok'], True)
        self.assertEqual(result['recipe_version'], 3)
        self.assertEqual(result['seed'], 42)
