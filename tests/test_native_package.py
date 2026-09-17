"""Source bundle reproducibility, tamper checks, and isolated headless consumer."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT=Path(__file__).resolve().parents[1]

class NativePackageTests(unittest.TestCase):
    def test_reproducible_source_bundle_and_isolated_consumer(self):
        with tempfile.TemporaryDirectory(prefix='fantasy-world-generator-package-') as directory:
            directory=Path(directory)
            for name in ('first','second'):
                built=subprocess.run([sys.executable,str(ROOT/'tools/package_native.py'),'--output-dir',str(directory/name)],capture_output=True,text=True,timeout=15)
                self.assertEqual(built.returncode,0,built.stdout+built.stderr)
            first=next((directory/'first').glob('*.zip'));second=next((directory/'second').glob('*.zip'))
            self.assertEqual(first.name,second.name)
            self.assertEqual(first.read_bytes(),second.read_bytes())
            self.assertIn(hashlib.sha256(first.read_bytes()).hexdigest(),first.name)
            consumer=directory/'consumer'
            with zipfile.ZipFile(first) as bundle:
                names=bundle.namelist()
                self.assertIn('LICENSE',names);self.assertIn('Core/json.cpp',names)
                self.assertNotIn('Sim/fantasy_world_generator/counter_kernel.py',names)
                self.assertTrue(all(not Path(n).is_absolute() and '..' not in Path(n).parts for n in names))
                bundle.extractall(consumer)
            manifest=json.loads((consumer/'manifest.json').read_text())
            self.assertEqual(manifest['qualification'],'unqualified-source-only')
            for relative,digest in manifest['files'].items():
                self.assertEqual(hashlib.sha256((consumer/relative).read_bytes()).hexdigest(),digest)
            if not (shutil.which('clang++') or shutil.which('g++')):
                self.skipTest('archive verified; isolated native qualification requires C++17 compiler')
            command=[sys.executable,str(consumer/'tools/qualify_native.py'),'--output-dir',str(directory/'evidence')]
            env=dict(os.environ);env.pop('PYTHONPATH',None)
            qualified=subprocess.run(command,cwd=consumer,env=env,capture_output=True,text=True,timeout=90)
            self.assertEqual(qualified.returncode,0,qualified.stdout+qualified.stderr)
            report=json.loads((directory/'evidence/qualification.json').read_text())
            self.assertEqual(report['status'],'passed')
            self.assertFalse(report['unreal_qualified'])
            self.assertEqual(report['manifest_sha256'],hashlib.sha256((consumer/'manifest.json').read_bytes()).hexdigest())
            manifest_bytes=(consumer/'manifest.json').read_bytes()
            for invalid in ([],dict(manifest,contracts=dict(manifest['contracts'],kernel_numeric=2)),dict(manifest,schema_version=True)):
                (consumer/'manifest.json').write_text(json.dumps(invalid))
                rejected=subprocess.run(command,cwd=consumer,env=env,capture_output=True,text=True,timeout=15)
                self.assertNotEqual(rejected.returncode,0)
                self.assertEqual(json.loads((directory/'evidence/qualification.json').read_text())['status'],'failed')
            (consumer/'manifest.json').write_bytes(manifest_bytes)
            (consumer/'Core/counter.cpp').write_text('// tampered\n')
            rejected=subprocess.run(command,cwd=consumer,env=env,capture_output=True,text=True,timeout=15)
            self.assertNotEqual(rejected.returncode,0)
            self.assertIn('source hash mismatch',rejected.stderr)
            self.assertEqual(json.loads((directory/'evidence/qualification.json').read_text())['status'],'failed')
