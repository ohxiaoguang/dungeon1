"""Platform split of the launcher's virtual-gamepad settings.

The three touch switches are declared inside `#if os(iOS)` in the shared schema, so a macOS build of the same
file cannot exercise them and only a macOS binary can exercise the filter. This checks the source wiring that
neither run covers: that the three are declared for iOS only, that they are three different variables, and that
the Mac launcher drops the gamepad-only one instead of showing it.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / 'dm/apple/LauncherSettings.swift'
LAUNCHER = ROOT / 'dm/ios/Sources/Launcher.swift'
GAMEPAD = ROOT / 'dm/ios/Sources/DmGamepad.m'
BUNDLED = ROOT / 'dm/ios/Sources/BundledResources.swift'

TOUCH_SETTINGS = ('DM_TOUCH_INPUT', 'DM_TOUCH_CONTROLS', 'DM_RIGHT_STICK_VISIBLE')


def block(source, condition):
    """-> the text inside the first `#if <condition>` … `#endif` of a Swift file."""
    start = source.index('#if ' + condition)
    end = source.index('#endif', start)
    return source[start:end]


class PlatformSettings(unittest.TestCase):
    def test_the_three_touch_switches_are_declared_for_ios_only(self):
        source = SCHEMA.read_text()
        ios = block(source, 'os(iOS)')
        for env in TOUCH_SETTINGS:
            self.assertIn('env: "%s"' % env, ios, env)
        # Three separate variables: the game's touch input is not the overlay's visibility nor its haptics.
        self.assertEqual(len({m for m in re.findall(r'env: "(DM_[A-Z_]+)"', ios)} & set(TOUCH_SETTINGS)),
                         len(TOUCH_SETTINGS))
        # Outside that block (a Mac build) none of them may be declared.
        outside = source.replace(ios, '')
        for env in TOUCH_SETTINGS:
            self.assertNotIn('env: "%s"' % env, outside, env)

    def test_touchscreen_input_is_on_by_default(self):
        ios = block(SCHEMA.read_text(), 'os(iOS)')
        row = next(line for line in ios.splitlines() if 'env: "DM_TOUCH_INPUT"' in line)
        self.assertIn('def: "1"', row)

    def test_the_mac_launcher_drops_the_gamepad_only_setting(self):
        source = SCHEMA.read_text()
        mac = block(source, 'os(macOS)')
        self.assertIn('DM_TOUCH_HAPTICS', mac)
        self.assertIn('filter', mac)
        # Game rumble is not a touch setting: it must survive on a Mac with a controller.
        self.assertNotIn('DM_RUMBLE"', mac)

    def test_the_gamepad_reads_the_switch_at_the_host_boundary(self):
        source = GAMEPAD.read_text()
        self.assertIn('DM_TOUCH_INPUT', source)
        self.assertIn('launcher.DM_TOUCH_INPUT', source)          # falls back to the saved choice
        # The single boundary both layouts and every game pass through.
        push = source[source.index('- (void)pushGame {'):]
        push = push[:push.index('\n}\n')]
        self.assertIn('_gameTouch', push)
        self.assertIn('dm_touch_set(NULL, 0)', push)

    def test_the_ios_launcher_hides_resource_diagnostics_when_embedded(self):
        source = LAUNCHER.read_text()
        # The status view is rendered for the external backend only; the embedded case shows a real error instead of
        # a healthy-looking screen. One occurrence, guarded — not a second unconditional one further down.
        self.assertEqual(source.count('ResourceStatusView('), 1)
        guard = re.search(r'if resources\.external \{[\s\S]{0,400}?ResourceStatusView\(', source)
        self.assertIsNotNone(guard, 'the resource status view is not behind the external backend check')
        self.assertIn('bundledProblem', source)
        self.assertIn('BundledResources.problem', source)
        # In embedded mode the launcher must not claim a scan or a selection happened.
        self.assertNotIn('Looking for this game\'s files', source.split('bundledProblem', 1)[1])
        # The check itself must ask for the host's roots, not a bundle path of its own.
        check = BUNDLED.read_text()
        self.assertIn('DM_ROMFS', check)
        self.assertIn('DM_ROMFS_MARKER', check)
        self.assertIn('documents', check)


if __name__ == '__main__':
    unittest.main()
