"""Exercise the Mac launcher's actual MOD path and child-environment policy."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class ModFolder(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        root = Path(cls.temp.name)
        main = root / 'main.swift'
        main.write_text('''import Foundation
let a = CommandLine.arguments
let env = ["DM_RESOURCE_BACKEND": a[2], "DM_RESOURCE_NSP": "/fixture/base.nsp", "DM_ROMFS_OVERLAY": "/stale"]
do {
    let selected = a[1] == "-" ? nil : URL(fileURLWithPath: a[1])
    let result = try ModOverlay.applying(folder: selected, to: env)
    print(String(data: try JSONSerialization.data(withJSONObject: result), encoding: .utf8)!)
} catch { print("unreadable"); exit(1) }
''')
        cls.binary = root / 'check'
        subprocess.run(['xcrun', 'swiftc', '-module-cache-path', str(root / 'cache'),
                        str(ROOT / 'dm/macos/ModOverlay.swift'), str(main), '-o', str(cls.binary)],
                       capture_output=True, check=True)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def check(self, folder=None, backend='directory'):
        result = subprocess.run([str(self.binary), str(folder) if folder else '-', backend],
                                capture_output=True, text=True)
        return result

    def test_unselected_removes_inherited_overlay_in_both_modes(self):
        for backend in ['directory', 'nsp']:
            env = json.loads(self.check(backend=backend).stdout)
            self.assertNotIn('DM_ROMFS_OVERLAY', env)
            self.assertEqual(env['DM_RESOURCE_BACKEND'], backend)
            self.assertEqual(env['DM_RESOURCE_NSP'], '/fixture/base.nsp')

    def test_three_conventional_folder_choices_resolve_to_the_same_overlay(self):
        outer = Path(self.temp.name) / 'My MODs'
        overlay = outer / 'romfs'
        mods = overlay / 'mods'
        project = mods / 'example/project.xml'
        project.parent.mkdir(parents=True)
        project.write_text('<project><Title>Example</Title></project>')
        for backend in ['directory', 'nsp']:
            for folder in [outer, overlay, mods]:
                with self.subTest(folder=folder, backend=backend):
                    env = json.loads(self.check(folder, backend).stdout)
                    self.assertEqual(Path(env['DM_ROMFS_OVERLAY']).resolve(), overlay.resolve())
                    self.assertEqual(env['DM_RESOURCE_BACKEND'], backend)

    def test_generic_overlay_with_spaces_and_unicode(self):
        overlay = Path(self.temp.name) / 'Overlay \u6d4b\u8bd5'
        overlay.mkdir()
        self.assertEqual(Path(json.loads(self.check(overlay).stdout)['DM_ROMFS_OVERLAY']).resolve(), overlay.resolve())

    def test_disconnected_or_invalid_folder_is_reported(self):
        self.assertNotEqual(self.check(Path(self.temp.name) / 'gone').returncode, 0)
        file = Path(self.temp.name) / 'file'
        file.touch()
        self.assertNotEqual(self.check(file).returncode, 0)

    def test_colon_cannot_inject_a_second_overlay(self):
        folder = Path(self.temp.name) / 'a:b'
        folder.mkdir()
        self.assertNotEqual(self.check(folder).returncode, 0)


if __name__ == '__main__':
    unittest.main()
