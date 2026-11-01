"""Platform-scoped validation and AOC discovery of the standalone builder.

A Mac-only preparation carries no iOS shader library, and the container bootstrap
writes its verified DLC tree beside `aoc` as `aoc-<digest>/`. Both regressions are
covered here with synthetic preparations: no game container, shader translation or
multi-gigabyte build is involved.
"""
import hashlib
import json
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO), str(REPO / 'dm/games')]
import game
from scripts import dungeon1_build
from tools.nxrom import gl_library
from tools.packaging_gui import dlc

TITLE = '01008F1008DA6000'
APPLICATION = int(TITLE, 16)


def captured_pairs():
    rows = (REPO / 'dm/games' / TITLE / 'gl_capture.tsv').read_text().splitlines()
    return [line.strip().rsplit('.', 1) for line in rows if line.strip() and not line.startswith('#')]


def write_shader_library(folder, pairs):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'gl_shaders.tsv').write_text(
        ''.join(key + '\t' + stage + '\tfields\tfixture\n' for key, stage in pairs))
    (folder / 'gl_shaders.metallib').write_bytes(b'MTLB' + bytes(28))


def write_preparation(root, platforms):
    """Everything `validate` inspects, except a real container: registered 1.3.0 Build
    IDs, current rewriter stamps, the profile's gates, the RomFS marker and shaders."""
    profile = game.load(TITLE)
    patched = root / 'patched_v393216'
    patched.mkdir(parents=True)
    for module in profile.words('modules'):
        (patched / (module + '.fixups.tsv')).write_text(
            '# BUILD_ID\t' + profile.builds()['v393216'][module] + '\n')
        (patched / (module + '.patched.bin')).write_bytes(b'NSO0' + bytes(12))
    sources = ['patch_nso.py', 'nso_code.py', 'nso_asm.py', 'sdk_patches.py',
               '../games/' + TITLE + '/patches.py']
    (patched / 'build_src.sha256').write_text(''.join(
        hashlib.sha256((REPO / 'dm/tools' / name).read_bytes()).hexdigest() + '  ' + name + '\n'
        for name in sources))
    patches = runpy.run_path(str(REPO / 'dm/games' / TITLE / 'patches.py'))
    gates = []
    for kind, table in (('obs', 'OBS'), ('filter', 'FILTERS')):
        for site, number, *_ in patches[table][profile.builds()['v393216']['main']]:
            gates.append('-0x%x\t%s\t%d\t0x%x\n' % (site, kind, number, site))
    (patched / 'main.gates.tsv').write_text(''.join(gates))
    marker = root / 'extract/v393216/RomFS' / profile.get('romfs_marker')
    marker.parent.mkdir(parents=True)
    marker.write_bytes(b'')
    pairs = captured_pairs()
    for platform in platforms:
        write_shader_library(root / 'shader' / platform, pairs)
    return root


class ShaderTargetTests(unittest.TestCase):
    """Each target validates exactly the library it packs (mac: gl, ios: ios/gl)."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        symbols = ''.join('0000 T gl_' + key + ('_v' if stage == 'vert' else '_f') + '\n'
                          for key, stage in captured_pairs())
        self.reader = patch.object(gl_library.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, symbols, ''))
        self.reader.start()
        self.addCleanup(self.reader.stop)

    def prepare(self, name, platforms):
        return write_preparation(self.root / name, platforms)

    def test_mac_only_preparation_validates_for_mac(self):
        prepared = self.prepare('mac-only', ('gl',))
        self.assertFalse((prepared / 'shader/ios').exists())
        self.assertEqual(dungeon1_build.validate(prepared, 'mac'), prepared / 'patched_v393216')

    def test_ios_only_preparation_validates_for_ios(self):
        prepared = self.prepare('ios-only', ('ios/gl',))
        self.assertFalse((prepared / 'shader/gl').exists())
        self.assertEqual(dungeon1_build.validate(prepared, 'ios'), prepared / 'patched_v393216')

    def test_preparation_with_both_libraries_validates_each_target(self):
        prepared = self.prepare('both', ('gl', 'ios/gl'))
        for target in ('mac', 'ios'):
            self.assertEqual(dungeon1_build.validate(prepared, target), prepared / 'patched_v393216')

    def test_target_rejects_a_missing_library(self):
        with self.assertRaisesRegex(ValueError, 'shader/ios'):
            dungeon1_build.validate(self.prepare('no-ios', ('gl',)), 'ios')
        with self.assertRaisesRegex(ValueError, 'shader/gl'):
            dungeon1_build.validate(self.prepare('no-mac', ('ios/gl',)), 'mac')

    def test_unknown_target_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Unknown build target'):
            dungeon1_build.validate(self.prepare('tree', ('gl',)), 'nsp')


def write_aoc(root, indexes, application=APPLICATION):
    root.mkdir(parents=True)
    for index in indexes:
        folder = root / str(index)
        folder.mkdir()
        (folder / 'romfs.bin').write_bytes(b'DLC %d payload' % index)
    (root / 'manifest.json').write_text(json.dumps(dict(
        schema=1,
        dlcs=[dict(title=application + 0x1000 + index, application=application, version=65536,
                   required_version=0, index=index, sha256='0' * 64) for index in indexes],
        files=dlc.tree_inventory(root)), sort_keys=True))
    return root


class AocDiscoveryTests(unittest.TestCase):
    """`aoc/` and the bootstrap's `aoc-<digest>/` are both found; nothing else is."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.prepared = Path(self.temp.name) / 'prepared'
        self.prepared.mkdir()

    def test_named_aoc_tree_is_used(self):
        tree = write_aoc(self.prepared / 'aoc', (1, 2, 3, 4, 5))
        self.assertEqual(dungeon1_build.aoc_tree(self.prepared), tree)

    def test_digest_tree_is_discovered(self):
        tree = write_aoc(self.prepared / 'aoc-0123456789abcdef', (1,))
        self.assertEqual(dungeon1_build.aoc_tree(self.prepared), tree)

    def test_all_five_dlc_reach_the_packaging_manifest(self):
        tree = write_aoc(self.prepared / 'aoc-9f1c2d3e4a5b6c7d', (1, 2, 3, 4, 5))
        found = dungeon1_build.aoc_tree(self.prepared)
        saved = dlc.audit_tree(found, APPLICATION)
        self.assertEqual(found, tree)
        self.assertEqual(sorted(d['index'] for d in saved['dlcs']), [1, 2, 3, 4, 5])
        self.assertEqual({p.name for p in found.iterdir() if p.is_dir()}, {'1', '2', '3', '4', '5'})

    def test_base_only_preparation_has_no_aoc(self):
        (self.prepared / 'extract').mkdir()
        (self.prepared / 'shader').mkdir()
        for unrelated in ('dlcs', 'aoc-notes', 'romfs'):
            (self.prepared / unrelated).mkdir()
        self.assertIsNone(dungeon1_build.aoc_tree(self.prepared))

    def test_tree_without_manifest_is_an_error(self):
        (self.prepared / 'aoc' / '1').mkdir(parents=True)
        with self.assertRaisesRegex(ValueError, 'verified AOC manifest'):
            dungeon1_build.aoc_tree(self.prepared)

    def test_two_candidate_trees_are_ambiguous(self):
        write_aoc(self.prepared / 'aoc-0123456789abcdef', (1,))
        write_aoc(self.prepared / 'aoc-9f1c2d3e4a5b6c7d', (2,))
        with self.assertRaisesRegex(ValueError, 'Ambiguous AOC trees'):
            dungeon1_build.aoc_tree(self.prepared)

    def test_incomplete_candidate_tree_never_audits(self):
        tree = write_aoc(self.prepared / 'aoc-0123456789abcdef', (1, 2, 3, 4, 5))
        (tree / '3/romfs.bin').unlink()
        with self.assertRaisesRegex(ValueError, 'inventory differs'):
            dlc.audit_tree(dungeon1_build.aoc_tree(self.prepared), APPLICATION)

    def test_unrelated_manifest_directory_is_rejected_by_audit(self):
        folder = self.prepared / 'aoc-cache'
        folder.mkdir()
        (folder / 'manifest.json').write_text(json.dumps(dict(schema=1, dlcs=[], files={})))
        (folder / 'stray.bin').write_bytes(b'not DLC')
        with self.assertRaises(ValueError):
            dlc.audit_tree(dungeon1_build.aoc_tree(self.prepared), APPLICATION)


if __name__ == '__main__':
    unittest.main()
