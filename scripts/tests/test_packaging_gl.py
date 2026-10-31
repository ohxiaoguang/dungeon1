"""GL stage coverage, compiled symbol integrity, IPA audit layout and generic engine routing."""
from dataclasses import replace
from pathlib import Path
import hashlib
import plistlib
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from tools.nxrom import gl_library
from tools.packaging_gui import engine, registry, workflow
from scripts.tests.fixtures import write_program

TITLE = '01008F1008DA6000'
KEY = '0123456789abcdef'


class GlLibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.folder = self.root / 'gl'; self.folder.mkdir()
        (self.folder / 'gl_shaders.tsv').write_text(KEY + '\tvert\ta:position=0:vec3\tfixture\n')
        (self.folder / 'gl_shaders.metallib').write_bytes(b'MTLB' + bytes(28))
        self.capture = self.root / 'gl_capture.tsv'; self.capture.write_text(KEY + '.vert\n')
        self.nm = patch.object(gl_library.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '0000 T gl_' + KEY + '_v\n', ''))
        self.reader = self.nm.start(); self.addCleanup(self.nm.stop)

    def test_valid_stage_and_compiled_function_agree(self):
        self.assertEqual(gl_library.validate(self.folder, self.capture)['functions'], 1)
        self.assertEqual(self.reader.call_args.args[0][:2], ['xcrun', 'metal-nm'])

    def test_same_key_in_wrong_stage_does_not_cover_capture(self):
        self.capture.write_text(KEY + '.frag\n')
        with self.assertRaisesRegex(ValueError, 'captured stages'):
            gl_library.validate(self.folder, self.capture)

    def test_duplicate_key_stage_is_rejected(self):
        p = self.folder / 'gl_shaders.tsv'; p.write_text(p.read_text() * 2)
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            gl_library.validate(self.folder)

    def test_malformed_table_is_rejected(self):
        (self.folder / 'gl_shaders.tsv').write_text('bad\tcompute\tfields\n')
        with self.assertRaisesRegex(ValueError, 'Invalid GL Shader table'):
            gl_library.validate(self.folder)

    def test_header_alone_cannot_prove_function_coverage(self):
        self.reader.return_value.stdout = ''
        with self.assertRaisesRegex(ValueError, 'function inventory'):
            gl_library.validate(self.folder)

    def test_unlisted_compiled_stage_is_rejected(self):
        self.reader.return_value.stdout += '0001 T gl_' + KEY + '_f\n'
        with self.assertRaisesRegex(ValueError, 'function inventory'):
            gl_library.validate(self.folder)

    def test_unreadable_compiled_library_is_rejected(self):
        self.reader.return_value.returncode = 1
        self.reader.return_value.stderr = 'bad library'
        with self.assertRaisesRegex(ValueError, 'Cannot inspect'):
            gl_library.validate(self.folder)

    def test_missing_capture_and_linked_input_are_rejected(self):
        self.capture.unlink()
        with self.assertRaisesRegex(ValueError, 'Missing GL capture'):
            gl_library.validate(self.folder, self.capture)
        p = self.folder / 'gl_shaders.metallib'; p.rename(self.root / 'library')
        p.symlink_to(self.root / 'library')
        with self.assertRaisesRegex(ValueError, 'regular files'):
            gl_library.validate(self.folder)


class GlEngineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve(); self.profile = registry.by_title(TITLE)
        self.exefs = write_program(self.root / 'program/ExeFS', self.profile, 'v0')
        self.cache = self.root / 'cache'; self.cached = self.cache / 'profile' / TITLE
        shutil.copytree(self.profile.table('game.tsv').parent, self.cached)
        folder = self.cache / 'gl'; folder.mkdir()
        rows = [(line.rsplit('.', 1)) for line in self.profile.table('gl_capture.tsv').read_text().splitlines() if line and not line.startswith('#')]
        self.rows = rows   # the count the engine must report is the profile's own capture table, not a number kept here
        (folder / 'gl_shaders.tsv').write_text(''.join(key + '\t' + stage + '\tfields\tfixture\n' for key, stage in rows))
        (folder / 'gl_shaders.metallib').write_bytes(b'MTLB' + bytes(28))
        symbols = ''.join('0000 T gl_' + key + ('_v' if stage == 'vert' else '_f') + '\n' for key, stage in rows)
        self.nm = patch.object(gl_library.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, symbols, '')); self.nm.start(); self.addCleanup(self.nm.stop)
        self.request = engine.Request(game=TITLE, exefs=str(self.exefs), cache=str(self.cache), output=str(self.root))

    def test_gl_cache_needs_no_nvn_chain_tables_or_stamp(self):
        with patch.object(engine, 'chain_tools', side_effect=AssertionError('NVN chain called')):
            state = engine.validate_cache(self.request)
        self.assertIsNone(state['chain']); self.assertEqual(state['shader_count'], len(self.rows))

    def test_cached_capture_cannot_replace_repository_coverage(self):
        (self.cached / 'gl_capture.tsv').write_text(KEY + '.vert\n')
        with self.assertRaisesRegex(ValueError, 'Cached Profile differs'):
            engine.validate_cache(self.request)

    def test_plan_routes_to_gl_folder_and_retains_identity(self):
        with patch.object(engine, 'chain_tools', side_effect=AssertionError('NVN chain called')):
            plan = engine.plan(self.request, self.root / 'task')
        package = plan['commands'][-1]['argv']
        self.assertEqual(package[package.index('--shaders') + 1], str(self.cache / 'gl'))
        self.assertEqual(len([c for c in plan['commands'] if c['stage'].startswith('rewrite-')]), 3)
        self.assertEqual(engine.detect_program(self.profile, self.exefs)[0], 'v0')

    def test_ios_plan_points_msl_ios_at_the_layer_folder(self):
        # build_ipa.sh looks for $MSL_IOS/gl/gl_shaders.metallib, so MSL_IOS is the
        # layer library's parent, not the NVN ios/dmsh_b folder.
        with patch.object(engine, 'chain_tools', side_effect=AssertionError('NVN chain called')):
            plan = engine.plan(replace(self.request, target='ios'), self.root / 'ios-task')
        package = plan['commands'][-1]
        self.assertEqual(package['environment']['MSL_IOS'], str(self.cache / 'ios'))
        self.assertEqual(package['environment']['GFXAPI'], 'gl')

    def test_automatic_gl_reuse_does_not_query_nvn_chain(self):
        from tools.packaging_gui import automatic
        slots = self.root / 'slots'; slots.mkdir()
        with patch.object(engine, 'chain_tools', side_effect=AssertionError('NVN chain called')), \
             patch.object(automatic.cache, 'area', return_value=slots):
            found = automatic.shader_slot(replace(self.request, cache_root=str(self.cache)), self.root, self.profile)
        self.assertEqual(found.cache, str(self.cache))
        self.assertEqual(found.shader_action, 'reuse')

    def test_workflow_inventory_binds_library_and_table_bytes(self):
        folder, before = workflow.shader_inventory(self.request, None, self.profile)
        self.assertEqual(set(before), {'gl_shaders.tsv', 'gl_shaders.metallib'})
        (folder / 'gl_shaders.metallib').write_bytes(b'MTLB changed')
        self.assertNotEqual(before, workflow.shader_inventory(self.request, None, self.profile)[1])


class GlIpaAuditTests(unittest.TestCase):
    """The IPA audit must read msl/gl, not the NVN chain folder, for a GL profile."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.ipa = self.root / 'DarkestDungeon.ipa'
        self.table = KEY + '\tvert\ta:position=0:vec3\tfixture\n'
        self.library = b'MTLB' + bytes(28)
        self.inventory = {'gl_shaders.tsv': hashlib.sha256(self.table.encode()).hexdigest(),
                          'gl_shaders.metallib': hashlib.sha256(self.library).hexdigest()}
        self.shader = dict(graphics_api='gl', layer='gl', table='gl_shaders.tsv',
                           files_sha256=self.inventory)

    def write(self, table=None, library=None, with_table=True):
        """A minimal unsigned IPA: Info.plist, executable and the two layer files."""
        from tools.nxrom.prepared_build import audit_ipa
        prefix = 'Payload/DmIOS.app/'
        with zipfile.ZipFile(self.ipa, 'w') as archive:
            archive.writestr(prefix + 'Info.plist', plistlib.dumps(
                {'CFBundleExecutable': 'DmIOS', 'DMResourceBackend': 'nsp',
                 'CFBundleIdentifier': 'org.nxnative.01008f1008da6000'}))
            archive.writestr(prefix + 'DmIOS', b'\xcf\xfa\xed\xfe')
            if with_table:
                archive.writestr(prefix + 'msl/gl/gl_shaders.tsv',
                                 table if table is not None else self.table)
            archive.writestr(prefix + 'msl/gl/gl_shaders.metallib',
                             library if library is not None else self.library)
        return audit_ipa

    def test_layer_library_is_audited_under_its_own_folder(self):
        audit_ipa = self.write()
        details = audit_ipa(self.ipa, expected_libraries=1, shader=self.shader,
                            expected_bundle_id='org.nxnative.01008f1008da6000')
        self.assertTrue(details['shader_bytes_match_cache'])

    def test_missing_layer_table_is_rejected(self):
        audit_ipa = self.write(with_table=False)
        with self.assertRaisesRegex(ValueError, 'no gl_shaders.tsv'):
            audit_ipa(self.ipa, expected_libraries=1, shader=self.shader)

    def test_changed_layer_bytes_are_rejected(self):
        audit_ipa = self.write(library=b'MTLB' + bytes(24) + b'changed')
        with self.assertRaisesRegex(ValueError, 'bytes differ from validated cache'):
            audit_ipa(self.ipa, expected_libraries=1, shader=self.shader)


if __name__ == '__main__':
    unittest.main()
