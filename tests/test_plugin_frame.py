"""FantasyWorldGenerator frame mirror: shared Unreal-frame fixture checked headlessly, without the editor.

A pass here proves the engine-independent rules in the plugin header only. It is not an
Unreal Build Tool compile, editor load or cooked-runtime result.
"""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(Path(__file__).resolve().parent))

from native_cxx import compile_native, compiler_command

PLUGIN=ROOT/'Unreal/FantasyWorldGenerator'
RELATIVE_TOLERANCE=1e-12
ABSOLUTE_TOLERANCE=1e-9


class PluginFrameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if compiler_command() is None:
            raise unittest.SkipTest('plugin frame mirror requires a C++17 compiler')
        cls.directory=tempfile.TemporaryDirectory(prefix='fantasy-world-generator-plugin-frame-')
        cls.addClassCleanup(cls.directory.cleanup)
        cls.binary=Path(cls.directory.name)/('frame_driver.exe' if sys.platform=='win32' else 'frame_driver')
        compile_native([PLUGIN/'Tests/frame_driver.cpp'],PLUGIN/'Source/FantasyWorldGenerator/Public',cls.binary)
        cls.fixture=json.loads((ROOT/'Fixtures/unreal-frame-v1.json').read_text(encoding='utf-8'))

    def run_driver(self, *arguments):
        result=subprocess.run([str(self.binary),*[str(value) for value in arguments]],
                              capture_output=True,text=True,timeout=10)
        self.assertIn(result.returncode,(0,2),result.stdout+result.stderr)
        return result.returncode,result.stdout.strip()

    def assert_close(self, actual, expected):
        self.assertAlmostEqual(actual,expected,
                               delta=max(ABSOLUTE_TOLERANCE,RELATIVE_TOLERANCE*abs(expected)))

    def test_source_tangent_metres_become_unreal_z_up_centimetres(self):
        for case in self.fixture['valid']:
            with self.subTest(name=case['name']):
                code,output=self.run_driver('unreal_cm',case['east_m'],case['up_m'],case['north_m'])
                self.assertEqual(code,0)
                for actual,expected in zip([float(value) for value in output.split()],case['expected_cm']):
                    self.assert_close(actual,expected)

    def test_unit_axes_permute_without_the_centimetre_scale(self):
        code,output=self.run_driver('unit_axis',1,0,0)
        self.assertEqual(code,0)
        self.assertEqual([float(value) for value in output.split()],[1.0,0.0,0.0])
        code,output=self.run_driver('unit_axis',0,1,0)
        self.assertEqual(code,0)
        self.assertEqual([float(value) for value in output.split()],[0.0,0.0,1.0])
        code,output=self.run_driver('unit_axis',0,0,1)
        self.assertEqual(code,0)
        self.assertEqual([float(value) for value in output.split()],[0.0,1.0,0.0])

    def expected_failure_code(self, body):
        """Core's precedence in Core/genesis.cpp: recipe, then seed, then size, then shape."""
        overrides=body.get('overrides',{})
        if body['recipe_version']!=3:return 'UNSUPPORTED_VERSION'
        if not 0<=body['seed']<=4294967295:return 'INVALID_INPUT'
        if not 3<=overrides.get('size',129)<=257:return 'STATE_CAPACITY'
        return 'INVALID_INPUT'

    def test_generate_request_rejects_retired_recipe_shape_and_out_of_range_seed_or_size(self):
        for body in self.fixture['invalid_generate']:
            overrides=body.get('overrides',{})
            with self.subTest(body=body):
                code,output=self.run_driver('validate_generate',body['recipe_version'],body['seed'],
                                            overrides.get('size',129),
                                            0 if overrides.get('shape','globe')!='globe' else 1)
                self.assertEqual(code,2,output)
                status,failure=output.split()
                self.assertNotEqual(status,'valid')
                self.assertEqual(failure,self.expected_failure_code(body))

    def test_valid_generate_request_is_accepted_without_python(self):
        code,output=self.run_driver('validate_generate',3,42,65,1)
        self.assertEqual(code,0,output)
        self.assertEqual(output,'valid -')
