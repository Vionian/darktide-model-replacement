import argparse
import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import darktide as dt
from package_mod import package_candidate
from scaffold_mod import scaffold, lua


class ToolkitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def manifest(self, folder=None):
        folder = folder or self.root
        folder.mkdir(parents=True, exist_ok=True)
        raw = b'synthetic fixture, not a game asset'
        (folder / 'model.unit').write_bytes(raw)
        data = {'roots': [{'type': 'unit', 'name': 'content/mods/test/weapon'}], 'resources': [{
            'key': {'type': 'unit', 'name': 'content/mods/test/weapon'},
            'file': {'path': 'model.unit', 'size': len(raw), 'crc32': f'{zlib.crc32(raw):08x}'},
            'dependencies': []}], 'external_resources': []}
        dt.save_json(folder / 'build.json', data)
        return folder / 'build.json', data

    def test_manifest_success_and_explicit_external_dependency(self):
        path, data = self.manifest()
        dep = {'type': 'material', 'name': 'native/parent'}
        data['resources'][0]['dependencies'].append(dep)
        data['external_resources'].append({'key': dep})
        dt.save_json(path, data)
        self.assertEqual(dt.validate_manifest(path)['resources'], 1)

    def test_manifest_rejects_size_crc_missing_dependency_duplicate_and_root(self):
        path, original = self.manifest()
        variants = []
        data = copy.deepcopy(original); data['resources'][0]['file']['size'] += 1; variants.append(data)
        data = copy.deepcopy(original); data['resources'][0]['file']['crc32'] = '00000000'; variants.append(data)
        data = copy.deepcopy(original); data['resources'][0]['dependencies'] = [{'type': 'material', 'name': 'absent'}]; variants.append(data)
        data = copy.deepcopy(original); data['resources'] *= 2; variants.append(data)
        data = copy.deepcopy(original); data['roots'][0]['name'] = 'absent'; variants.append(data)
        for data in variants:
            with self.subTest(data=data):
                dt.save_json(path, data)
                with self.assertRaises(ValueError): dt.validate_manifest(path)

    def test_manifest_rejects_traversal_and_missing_artifact(self):
        path, data = self.manifest()
        data['resources'][0]['file']['path'] = '../outside.unit'
        dt.save_json(path, data)
        with self.assertRaises(ValueError): dt.validate_manifest(path)
        path, data = self.manifest()
        data['artifacts'] = [{'path': 'missing.texture', 'size': 10}]
        dt.save_json(path, data)
        with self.assertRaises(ValueError): dt.validate_manifest(path)

    def test_portable_relative_path_restrictions(self):
        for name in ('../escape', '..\\escape', '/absolute', 'C:/absolute', 'C:relative', ''):
            with self.subTest(name=name), self.assertRaises(ValueError): dt.inside(self.root, name)
        self.assertEqual(dt.inside(self.root, 'data/test.stream'), self.root / 'data/test.stream')

    def test_archive_traversal_and_symlink_rejected(self):
        for name in ('../escape.txt', '..\\escape.txt', 'C:/escape.txt'):
            archive = self.root / 'bad.zip'
            with zipfile.ZipFile(archive, 'w') as out: out.writestr(name, b'fixture')
            with self.assertRaises(ValueError): dt.unpack(archive, self.root / 'extract')
        with zipfile.ZipFile(archive, 'w') as out:
            member = zipfile.ZipInfo('link'); member.external_attr = 0o120777 << 16
            out.writestr(member, 'outside')
        with self.assertRaises(ValueError): dt.unpack(archive, self.root / 'extract')

    def test_download_digest_rejected_and_partial_removed(self):
        target = self.root / 'download.zip'
        with patch('urllib.request.urlopen', return_value=io.BytesIO(b'bad bytes')):
            with self.assertRaises(ValueError):
                dt.download({'url': 'https://example.invalid/fixture', 'sha256': '0' * 64}, target)
        self.assertFalse(target.exists())
        self.assertFalse(target.with_suffix('.zip.partial').exists())

    def test_download_cached_digest_avoids_network(self):
        target = self.root / 'download.zip'; target.write_bytes(b'cached')
        with patch('urllib.request.urlopen') as request:
            dt.download({'url': 'https://example.invalid/fixture', 'sha256': dt.sha256(target)}, target)
            request.assert_not_called()

    def test_install_skill_location_and_backup(self):
        args = argparse.Namespace(destination=str(self.root / 'skills'), replace=False)
        with contextlib.redirect_stdout(io.StringIO()): dt.install_skill(args)
        target = self.root / 'skills/darktide-model-replacement'
        self.assertEqual((target / 'repository-location.txt').read_text().strip(), str(dt.ROOT))
        (target / 'personal-marker').write_text('preserve')
        with self.assertRaises(ValueError): dt.install_skill(args)
        args.replace = True
        with contextlib.redirect_stdout(io.StringIO()): dt.install_skill(args)
        backups = list((self.root / 'skill-backups').glob('darktide-model-replacement.*'))
        self.assertEqual(len(backups), 1)
        self.assertEqual((backups[0] / 'personal-marker').read_text(), 'preserve')
        self.assertFalse((target / 'personal-marker').exists())

    def test_materialize_paths_without_touching_archive(self):
        repo = self.root / 'repository'
        for kind in ('character', 'weapon'):
            folder = repo / 'toolbox' / kind; folder.mkdir(parents=True)
            (folder / 'fixture.py').write_text('path="<CHARACTER_WORKSPACE>"; tool="<BLENDER_EXE>"')
        destination = self.root / 'working'
        with patch.object(dt, 'ROOT', repo), patch.object(dt, 'load_config', return_value={'blender': '/fixture/blender'}):
            with contextlib.redirect_stdout(io.StringIO()):
                dt.materialize(argparse.Namespace(output=str(destination)))
        content = (destination / 'AnimeModelReplacement/tools/model-work/fixture.py').read_text()
        self.assertNotIn('<CHARACTER_WORKSPACE>', content)
        self.assertIn('/fixture/blender', content)
        self.assertIn('<CHARACTER_WORKSPACE>', (repo / 'toolbox/character/fixture.py').read_text())

    def candidate(self, kind='weapon'):
        candidate = self.root / 'candidate'
        path, _ = self.manifest(candidate / 'compiled/test_asset')
        profile = {'id': 'test_asset', 'kind': kind, 'local_source': str(self.root / 'private.blend')}
        if kind == 'weapon': profile.update(target_templates=['forcesword_p1_m1'], attachment_prefix='content/weapons/sword/attachments/')
        dt.save_json(candidate / 'build-report.json', {'profile': profile, 'assets': ['test_asset'],
            'source_sha256': 'a' * 64, 'native_audits_passed': True, 'in_game_visual_verified': False})
        dt.save_json(candidate / 'native-audit.json', [{'asset': 'test_asset', 'units': [
            {'zero_material_ids': 0, 'all_bound_materials_in_manifest': True}]}])
        (candidate / 'private.blend').write_bytes(b'not for publication')
        return candidate

    def test_package_only_manifest_resources_and_reviewed_runtime(self):
        candidate = self.candidate()
        runtime = scaffold(candidate, self.root / 'runtime', 'FixtureWeapon')
        (candidate / 'compiled/test_asset/private.blend').write_bytes(b'not listed')
        archive = Path(package_candidate(candidate, runtime, self.root / 'dist', ROOT))
        with zipfile.ZipFile(archive) as package:
            names = package.namelist()
            self.assertTrue(all(x.startswith('FixtureWeapon/') for x in names))
            self.assertFalse(any('.blend' in x or 'job.local' in x for x in names))
            evidence = json.loads(package.read('FixtureWeapon/build-evidence.json'))
            self.assertFalse(evidence['in_game_visual_verified'])
            self.assertNotIn('local_source', evidence['profile'])
            hashes = json.loads(package.read('FixtureWeapon/SHA256SUMS.json'))
            for relative, digest in hashes.items():
                self.assertEqual(hashlib.sha256(package.read('FixtureWeapon/' + relative)).hexdigest(), digest)
            self.assertIn('Custom/test_asset/model.unit', hashes)

    def test_package_rejects_unlisted_assets_and_unsafe_runtime(self):
        candidate = self.candidate()
        runtime = scaffold(candidate, self.root / 'runtime', 'FixtureWeapon')
        (runtime / 'source.blend').write_bytes(b'private')
        with self.assertRaises(ValueError): package_candidate(candidate, runtime, self.root / 'dist', ROOT)
        (runtime / 'source.blend').unlink()
        report = json.loads((candidate / 'build-report.json').read_text())
        report['assets'] = ['missing']
        dt.save_json(candidate / 'build-report.json', report)
        with self.assertRaises(ValueError): package_candidate(candidate, runtime, self.root / 'dist', ROOT)
        self.assertFalse((self.root / 'dist').exists())

    def test_scaffold_rejects_profile_injection_and_control_strings(self):
        candidate = self.candidate()
        path = candidate / 'build-report.json'
        data = json.loads(path.read_text()); data['profile']['attachment_prefix'] = "content/';error('bad')--/"
        dt.save_json(path, data)
        with self.assertRaises(ValueError): scaffold(candidate, self.root / 'runtime', 'FixtureWeapon')
        self.assertFalse((self.root / 'runtime').exists())
        with self.assertRaises(ValueError): lua('line\ncontrol')

    def test_doctor_detects_embedded_api_without_claiming_load_order(self):
        api = self.root / 'mods/Example/scripts/mods/CustomAssets/CustomAssets.lua'
        api.parent.mkdir(parents=True); api.write_text('-- fixture')
        report = dt.doctor_report({'game': str(self.root)})
        self.assertTrue(report['game_mod_prerequisites']['custom_assets'])
        self.assertFalse(report['custom_assets_load_order_verified'])


if __name__ == '__main__':
    unittest.main()
