"""The embedded-mode resource answer, run against real directories.

The host accepts Documents/romfs first and then the App's own copy, exporting the one it chose as DM_ROMFS.
These cases pin the rule to the host's and exercise boot's marker export: passing an NSString object to setenv
corrupted DM_ROMFS_MARKER, so the Swift check failed even though the host found the bundled game files.
"""
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / 'Sources/BundledResources.swift'
MARKER = 'audio/secondary_banks/voiceover.bank'
MISSING_FILES = 'This App does not contain the game files (romfs). Install the IPA again.'
MISSING_SHADERS = 'This App does not contain its Shader library (msl). Install the IPA again.'

MAIN = '''import Foundation
let a = CommandLine.arguments
var env: [String: String] = [:]
if a[3] != "-" { env["DM_ROMFS"] = a[3] }
if a[4] != "-" { env["DM_MSL_DIR"] = a[4] }
if a[5] != "-" { env["DM_ROMFS_MARKER"] = a[5] }
print(BundledResources.problem(environment: env, documents: a[1], bundle: a[2]) ?? "<nil>")
'''


class BundledResources(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        root = Path(cls.temp.name)
        main = root / 'main.swift'
        main.write_text(MAIN)
        cls.binary = root / 'check'
        subprocess.run(['xcrun', 'swiftc', '-swift-version', '5', str(SOURCE), str(main),
                        '-o', str(cls.binary)], check=True, capture_output=True)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(dir=self.temp.name))
        self.documents = self.root / 'Documents'
        self.bundle = self.root / 'DmIOS.app'
        self.documents.mkdir()
        self.bundle.mkdir()

    def put(self, folder, relative, data=b'x'):
        path = Path(folder) / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def library(self):
        self.put(self.bundle, 'msl/gl/gl_shaders.metallib', b'MTLB' + bytes(28))

    def ask(self, dm_romfs='-', dm_msl='-', marker=MARKER):
        result = subprocess.run([str(self.binary), str(self.documents), str(self.bundle),
                                 dm_romfs, dm_msl, marker], capture_output=True, text=True, check=True)
        return result.stdout.strip()

    def test_apps_own_romfs_is_enough(self):
        self.put(self.bundle, 'romfs/' + MARKER)
        self.library()
        self.assertEqual(self.ask(), '<nil>')

    def test_boot_exports_the_marker_as_a_c_string(self):
        # Compile the actual boot statement: Swift-only fixtures cannot catch an NSString* passed to setenv.
        boot = SOURCE.with_name('main.m').read_text()
        statement = re.search(r'setenv\("DM_ROMFS_MARKER",[^;]+;', boot).group()
        source = self.root / 'boot.m'
        source.write_text('#import <Foundation/Foundation.h>\n#include <stdlib.h>\n#include <stdio.h>\n'
                          f'#define DM_GAME_ROMFS_MARKER "{MARKER}"\n'
                          'int main(void) { @autoreleasepool {\n' + statement + '\n'
                          'puts(getenv("DM_ROMFS_MARKER"));\n} return 0; }\n')
        binary = self.root / 'boot'
        compiled = subprocess.run(['xcrun', 'clang', '-fobjc-arc', '-Werror=incompatible-pointer-types',
                                   '-framework', 'Foundation', str(source), '-o', str(binary)],
                                  capture_output=True, text=True)
        self.assertEqual(compiled.returncode, 0, compiled.stderr)
        marker = subprocess.run([str(binary)], check=True, capture_output=True, text=True).stdout.strip()
        self.assertEqual(marker, MARKER)
        self.put(self.bundle, 'romfs/' + MARKER)
        self.library()
        self.assertEqual(self.ask(marker=marker), '<nil>')
        (self.bundle / 'romfs' / MARKER).unlink()
        self.assertEqual(self.ask(marker=marker), MISSING_FILES)

    def test_game_files_in_documents_are_enough(self):
        # Preserve the host's Documents override as well as the bundled path.
        self.put(self.documents, 'romfs/' + MARKER)
        self.library()
        self.assertEqual(self.ask(), '<nil>')

    def test_already_resolved_root_is_taken_first(self):
        elsewhere = self.root / 'elsewhere'
        self.put(elsewhere, MARKER)
        self.library()
        self.assertEqual(self.ask(dm_romfs=str(elsewhere)), '<nil>')

    def test_nothing_anywhere_is_still_reported(self):
        self.library()
        self.assertEqual(self.ask(), MISSING_FILES)

    def test_a_root_without_the_marker_does_not_count(self):
        (self.bundle / 'romfs').mkdir()
        self.put(self.bundle, 'romfs/other/file.bin')
        self.library()
        self.assertEqual(self.ask(), MISSING_FILES)

    def test_missing_shader_library_is_named(self):
        self.put(self.bundle, 'romfs/' + MARKER)
        self.put(self.bundle, 'msl/gl/gl_shaders.tsv')   # a table without its metallib is not a usable library
        self.assertEqual(self.ask(), MISSING_SHADERS)

    def test_shader_folder_comes_from_the_environment_when_set(self):
        self.put(self.bundle, 'romfs/' + MARKER)
        elsewhere = self.root / 'shaders'
        self.put(elsewhere, 'gl/gl_shaders.metallib', b'MTLB' + bytes(28))
        self.assertEqual(self.ask(dm_msl=str(elsewhere)), '<nil>')

    def test_without_a_marker_the_directory_itself_decides(self):
        (self.bundle / 'romfs').mkdir()
        self.library()
        self.assertEqual(self.ask(marker='-'), '<nil>')


if __name__ == '__main__':
    unittest.main()
