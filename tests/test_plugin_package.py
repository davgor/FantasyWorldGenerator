"""FantasyWorldGenerator plugin archive: reproducibility, contents, rejected files and honest manifest flags."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))

import package_plugin


class PluginPackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory=tempfile.TemporaryDirectory(prefix='fantasy-world-generator-plugin-')
        cls.addClassCleanup(cls.directory.cleanup)
        cls.root=Path(cls.directory.name).resolve()  # resolved so a symlinked temp root is not rejected
        for name in ('first','second'):
            built=subprocess.run([sys.executable,str(ROOT/'tools/package_plugin.py'),'--output-dir',str(cls.root/name)],
                                 capture_output=True,text=True,timeout=30)
            if built.returncode:raise AssertionError(built.stdout+built.stderr)
        cls.first=next((cls.root/'first').glob('*.zip'));cls.second=next((cls.root/'second').glob('*.zip'))

    def test_archive_is_byte_reproducible_and_content_addressed(self):
        self.assertEqual(self.first.name,self.second.name)
        self.assertEqual(self.first.read_bytes(),self.second.read_bytes())
        self.assertIn(hashlib.sha256(self.first.read_bytes()).hexdigest(),self.first.name)

    def test_archive_contains_plugin_sources_without_python_assets_or_absolute_paths(self):
        with zipfile.ZipFile(self.first) as archive:
            names=archive.namelist()
        for required in ('FantasyWorldGenerator/FantasyWorldGenerator.uplugin','FantasyWorldGenerator/LICENSE','manifest.json',
                         'FantasyWorldGenerator/Source/FantasyWorldGenerator/FantasyWorldGenerator.Build.cs',
                         'FantasyWorldGenerator/Source/FantasyWorldGenerator/Public/FantasyWorldGeneratorFrame.h',
                         'FantasyWorldGenerator/Source/FantasyWorldGenerator/Public/FantasyWorldGeneratorSubsystem.h',
                         'FantasyWorldGenerator/Source/FantasyWorldGenerator/Private/FantasyWorldGeneratorSubsystem.cpp'):
            self.assertIn(required,names)
        for name in names:
            path=Path(name)
            self.assertFalse(path.is_absolute(),name)
            self.assertNotIn('..',path.parts,name)
            self.assertFalse(name.startswith('/') or ':' in name,name)
            self.assertFalse(name.startswith('Sim/'),name)
            self.assertNotIn('Sim/fantasy_world_generator',name)
            self.assertNotIn(path.suffix,('.py','.pyc','.uasset','.umap','.dll','.lib','.pdb','.exe'),name)

    def test_manifest_flags_do_not_claim_generate_or_engine_qualification(self):
        consumer=self.root/'consumer'
        with zipfile.ZipFile(self.first) as archive:
            archive.extractall(consumer)
        manifest=json.loads((consumer/'manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['schema'],'fantasy-world-generator.unreal-plugin-package')
        self.assertEqual(manifest['genesis'],'native-core')
        self.assertEqual(manifest['native_generate'],'incomplete')
        self.assertEqual(manifest['engine']['version'],'5.8')
        self.assertEqual(manifest['engine']['platforms'],['Win64'])
        self.assertEqual(manifest['module_type'],'Runtime')
        self.assertEqual(manifest['qualification'],'unqualified-source-only')
        self.assertFalse(manifest['unreal_qualified'])
        self.assertFalse(manifest['unreal_cooked_runtime'])
        self.assertFalse(manifest['core_vendored'])
        self.assertFalse(manifest['python_runtime_required'])
        self.assertEqual(manifest['license'],'LICENSE')
        self.assertTrue(manifest['limitations'])
        for relative,digest in manifest['files'].items():
            self.assertEqual(hashlib.sha256((consumer/relative).read_bytes()).hexdigest(),digest,relative)

    def test_manifest_coordinates_match_the_shared_unreal_frame_fixture(self):
        with zipfile.ZipFile(self.first) as archive:
            manifest=json.loads(archive.read('manifest.json').decode('utf-8'))
        fixture=json.loads((ROOT/'Fixtures/unreal-frame-v1.json').read_text(encoding='utf-8'))
        for axis in ('unreal_x','unreal_y','unreal_z'):
            self.assertEqual(manifest['coordinates'][axis],fixture['mapping'][axis])
        self.assertEqual(manifest['coordinates']['scale_unit_axes'],fixture['mapping']['scale_unit_axes'])

    def test_uplugin_declares_a_win64_runtime_module_and_no_project_content(self):
        with zipfile.ZipFile(self.first) as archive:
            descriptor=json.loads(archive.read('FantasyWorldGenerator/FantasyWorldGenerator.uplugin').decode('utf-8'))
        self.assertEqual(descriptor['EngineVersion'],'5.8.0')
        self.assertFalse(descriptor['CanContainContent'])
        self.assertFalse(descriptor['EnabledByDefault'])
        self.assertEqual(len(descriptor['Modules']),1)
        module=descriptor['Modules'][0]
        self.assertEqual(module['Name'],'FantasyWorldGenerator')
        self.assertEqual(module['Type'],'Runtime')
        self.assertEqual(module['PlatformAllowList'],['Win64'])

    def test_packaging_rejects_assets_binaries_and_project_content_paths(self):
        staged=self.root/'staged'
        (staged/'Unreal').mkdir(parents=True,exist_ok=True)
        shutil.copytree(ROOT/'Unreal/FantasyWorldGenerator',staged/'Unreal/FantasyWorldGenerator',dirs_exist_ok=True)
        shutil.copyfile(ROOT/'LICENSE',staged/'LICENSE')
        self.assertTrue(package_plugin.bundle_bytes(staged))
        asset=staged/'Unreal/FantasyWorldGenerator/Content/Placeholder.uasset'
        asset.parent.mkdir(parents=True,exist_ok=True);asset.write_bytes(b'\x00binary')
        with self.assertRaises(ValueError):package_plugin.bundle_bytes(staged)
        asset.unlink()
        leak=staged/'Unreal/FantasyWorldGenerator/Source/FantasyWorldGenerator/Private/Leak.cpp'
        leak.write_text('const char* Path = "/Game/Maps/Hub";\n',encoding='utf-8')
        with self.assertRaises(ValueError):package_plugin.bundle_bytes(staged)
        leak.unlink()
        (staged/'Unreal/FantasyWorldGenerator/FantasyWorldGenerator.uplugin').unlink()
        with self.assertRaises(ValueError):package_plugin.bundle_bytes(staged)
