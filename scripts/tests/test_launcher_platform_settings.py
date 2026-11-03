"""Platform split of the launcher's virtual-gamepad settings, and the one input mode over them.

The three touch switches are declared inside `#if os(iOS)` blocks of the shared schema, so a macOS build of the same
file cannot exercise them and only a macOS binary can exercise the filter. This checks the source wiring that
neither run covers: that the three are declared for iOS only, that they are three different variables, that the Mac
launcher drops the gamepad-only one instead of showing it, and that the single input choice writes exactly those two
variables (never a fourth one of its own).
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / 'gui/Sources/PackagingModel/Localization.swift'
SCHEMA = ROOT / 'dm/apple/LauncherSettings.swift'
LAUNCHER = ROOT / 'dm/ios/Sources/Launcher.swift'
GAMEPAD = ROOT / 'dm/ios/Sources/DmGamepad.m'
BUNDLED = ROOT / 'dm/ios/Sources/BundledResources.swift'
INPUT_H = ROOT / 'dm/host/dm_input.h'

TOUCH_SETTINGS = ('DM_TOUCH_INPUT', 'DM_TOUCH_CONTROLS', 'DM_RIGHT_STICK_VISIBLE')


def blocks(source, condition):
    """-> the text of every `#if <condition>` … `#endif` block of a Swift file."""
    out, i = [], 0
    while True:
        start = source.find('#if ' + condition, i)
        if start < 0:
            return out
        end = source.index('#endif', start)
        out.append(source[start:end])
        i = end + 1


def ios_blocks(source):
    return blocks(source, 'os(iOS)') + blocks(source, 'os(iOS) &&')


class PlatformSettings(unittest.TestCase):
    def test_the_three_touch_switches_are_declared_for_ios_only(self):
        source = SCHEMA.read_text()
        ios = '\n'.join(ios_blocks(source))
        for env in TOUCH_SETTINGS:
            self.assertIn('env: "%s"' % env, ios, env)
        # Three separate variables: the game's touch input is not the overlay's visibility nor its haptics.
        self.assertEqual(len({m for m in re.findall(r'env: "(DM_[A-Z_]+)"', ios)} & set(TOUCH_SETTINGS)),
                         len(TOUCH_SETTINGS))
        # Outside those blocks (a Mac build) none of them may be declared.
        outside = source
        for b in ios_blocks(source):
            outside = outside.replace(b, '')
        for env in TOUCH_SETTINGS:
            self.assertNotIn('env: "%s"' % env, outside, env)

    def test_touchscreen_input_is_on_by_default(self):
        ios = '\n'.join(ios_blocks(SCHEMA.read_text()))
        row = next(line for line in ios.splitlines() if 'env: "DM_TOUCH_INPUT"' in line)
        self.assertIn('def: "1"', row)

    def test_the_mac_launcher_drops_the_gamepad_only_setting(self):
        source = SCHEMA.read_text()
        mac = '\n'.join(blocks(source, 'os(macOS)'))
        self.assertIn('DM_TOUCH_HAPTICS', mac)
        self.assertIn('filter', mac)
        # Game rumble is not a touch setting: it must survive on a Mac with a controller.
        self.assertNotIn('DM_RUMBLE"', mac)

    def test_one_input_mode_writes_the_two_variables_and_nothing_else(self):
        source = SCHEMA.read_text()
        # The three presets are the only writers of the pair, and each writes both halves in one step. The gamepad
        # keeps a saved "touch off" (that is its own sub-option, not something the picker may clear).
        self.assertIn('case .gamepad: return (input == "0" ? "0" : "1", "1")', source)
        self.assertIn('case .touch: return ("1", "0")', source)
        self.assertIn('case .trackpad: return (dmTouchInputTrackpad, "0")', source)
        self.assertIn('let pair = mode.pair()', source)   # the mode's own default, never the last mode's sub-option
        self.assertIn('setValue("DM_TOUCH_INPUT", pair.input)', source)
        self.assertIn('setValue("DM_TOUCH_CONTROLS", pair.controls)', source)
        # A pair with neither the gamepad nor the touch screen is reported as it is and never rewritten.
        self.assertIn('case "0": return controls == "0" ? .custom : .gamepad', source)
        self.assertIn('guard mode != .custom, mode != touchMode else { return }', source)
        # The rows of the raw switches are not drawn: the mode is their only row (settingPlacement).
        self.assertIn('"DM_TOUCH_INPUT", "DM_TOUCH_CONTROLS",', source)
        self.assertIn('return .composed', source)

    def test_each_mode_draws_its_own_option_under_the_row(self):
        source = SCHEMA.read_text()
        row = source[source.index('struct TouchInputModeRow: View'):]
        row = row[:row.index('#endif')]
        # One option at a time, chosen by the mode - and each one is an existing variable, not a new switch.
        self.assertIn('switch m.touchMode {', row)
        self.assertIn('case .gamepad:', row)
        self.assertIn('Toggle(l("Disable touch input"), isOn: Binding(get: { m.gamepadTouchDisabled }', row)
        self.assertIn('case .touch:', row)
        self.assertIn('if let policy = m.touchPolicy { SettingLine(s: policy, m: m) }', row)
        self.assertIn('case .trackpad:', row)
        self.assertIn('if let speed = m.pointerSpeed { PointerSpeedRow(s: speed, m: m) }', row)
        # The gamepad's option is the same variable the mode rides on (no second switch, no new reader).
        self.assertIn('func setGamepadTouchDisabled(_ off: Bool) { setValue("DM_TOUCH_INPUT", off ? "0" : "1") }', source)
        # The trackpad's speed is one new variable, a gain the overlay applies to the cursor only.
        self.assertIn('Setting(env: "DM_TRACKPAD_SPEED", kind: "range"', source)
        self.assertIn('min: 0.5, max: 2, step: 0.1', source)

    def test_the_input_help_is_a_question_mark_and_a_sheet(self):
        """A small button beside the title, not another row or switch, and a sheet that shows every mode."""
        source = SCHEMA.read_text()
        row = source[source.index('struct TouchInputModeRow: View'):]
        row = row[:row.index('\n}\n')]
        self.assertIn('Image(systemName: "questionmark.circle")', row)
        self.assertIn('.buttonStyle(.borderless)', row)      # it must not swallow the row or the picker
        self.assertIn('.accessibilityLabel(l("Input help"))', row)
        self.assertIn('.accessibilityHint(l("How each input mode is used."))', row)
        self.assertIn('.sheet(isPresented: $help) { InputHelpSheet(start: m.touchMode)', row)
        # The sheet: a segmented choice so the other modes can be read without leaving it, a Done button, and it
        # scrolls inside a Form rather than growing the launcher.
        sheet = source[source.index('struct InputHelpSheet: View'):]
        sheet = sheet[:sheet.index('\n}\n')]
        self.assertIn('NavigationStack', sheet)
        self.assertIn('.pickerStyle(.segmented)', sheet)
        self.assertIn('ForEach(TouchHelp.lines(mode)', sheet)
        self.assertIn('Button(l("Done")) { dismiss() }', sheet)
        self.assertIn('.navigationTitle(l("How to play"))', sheet)

    def test_the_help_text_covers_every_mode_in_both_languages(self):
        source = SCHEMA.read_text()
        catalog = CATALOG.read_text()
        help_block = source[source.index('enum TouchHelp {'):]
        help_block = help_block[:help_block.index('\n}\n')]
        # Every mode the picker offers has lines of its own, and the kept state explains itself too.
        for case in ('case .gamepad:', 'case .touch:', 'case .trackpad:', 'case .custom:'):
            self.assertIn(case, help_block)
        titles = re.findall(r'TouchHelpLine\(title: "((?:[^"\\]|\\.)*)"', help_block)
        texts = re.findall(r'text: "((?:[^"\\]|\\.)*)"', help_block)
        self.assertGreaterEqual(len(titles), 12)
        self.assertEqual(len(titles), len(texts))
        # The instructions the spec asks for, by name.
        for title in ('One finger moves the pointer', 'One tap clicks', 'One finger, hold',
                      'Two fingers swipe', 'The pointer is the target',
                      'The glass is the game', 'Touch interaction policy', 'Buttons and sticks', 'Three layouts',
                      'Disable touch input'):
            self.assertIn(title, titles)
        # One entry per sentence, and no English left untranslated in a Chinese interface.
        for text in titles + texts:
            self.assertIn('"%s":' % text, catalog, text)
        # The two-finger swipe is documented as the game's own touch drag (the torch and the lists), not as a click,
        # and with no pause to learn any more.
        straight = [t for t in texts if "game's own touch drag" in t]
        self.assertTrue(straight, texts)
        self.assertIn('pulls the torch down', straight[0])
        self.assertIn('nothing to wait for', straight[0])
        # The single-finger hold is documented as the game's own long press.
        hold = [t for t in texts if 'the game is pressed where the pointer is' in t]
        self.assertTrue(hold, texts)

    def test_changing_the_mode_resets_the_options_of_the_mode_entered(self):
        """An option the last mode left behind must not keep acting in a mode that does not show it."""
        source = SCHEMA.read_text()
        body = source[source.index('func setTouchMode'):]
        body = body[:body.index('\n    }\n')]
        # Only a real change writes anything: opening the launcher, or picking the mode already set, keeps the choice.
        self.assertIn('guard mode != .custom, mode != touchMode else { return }', body)
        self.assertIn('setValue("DM_DD_TOUCH_POLICY", "0")', body)      # the touch policy belongs to direct touch
        self.assertIn('setValue("DM_TRACKPAD_SPEED", "1.0")', body)     # and the speed to the trackpad
        # The gamepad's "disable touch" is part of the pair, and the pair no longer keeps the previous value.
        self.assertNotIn('keeping:', body)
        # setValue is what refuses to overwrite an env-file value, so a pinned setting survives a mode change.
        self.assertIn('guard !fromFile.contains(env) else { return }', source)

    def test_the_advanced_header_is_one_whole_row(self):
        source = SCHEMA.read_text()
        view = source[source.index('struct AdvancedToggleRow: View'):]
        view = view[:view.index('\n}\n')]
        # A plain Button with a full-width hit shape: the whole row toggles, and nothing inside it is a control.
        self.assertIn('Button {', view)
        self.assertIn('.buttonStyle(.plain)', view)
        self.assertIn('.contentShape(Rectangle())', view)
        # Accessibility keeps its name, hint and state.
        self.assertIn('.accessibilityLabel(l("Advanced"))', view)
        self.assertIn('.accessibilityHint(', view)
        self.assertIn('.accessibilityValue(expanded ?', view)
        # The rows are outside the button, so the tap cannot reach a switch and opens no other setting.
        sections = source[source.index('struct LauncherSettingsSections: View'):]
        sections = sections[:sections.index('\n}\n')]
        self.assertIn('AdvancedToggleRow(expanded: $advanced)', sections)
        self.assertIn('if advanced {', sections)
        self.assertNotIn('Toggle(', sections.split('AdvancedToggleRow', 1)[0])

    def test_the_game_language_has_no_row_but_keeps_its_value(self):
        source = SCHEMA.read_text()
        # Composed: applied from its saved value and its packed default, drawn by nobody. It is in the .composed case
        # list of settingPlacement - not in .common and not in .advanced.
        placement = source[source.index('func settingPlacement'):]
        placement = placement[:placement.index('\n}\n')]
        composed_case = placement[:placement.index('return .composed')]
        composed_case = composed_case[composed_case.rindex('case '):]
        self.assertIn('"DM_LANG"', composed_case)
        common_case = placement[placement.index('default:'):]
        self.assertNotIn('"DM_LANG"', common_case)
        # It is still declared by the profile (settings.tsv) and applied by apply(), which walks `settings`.
        self.assertIn('DM_LANG', (ROOT / 'dm/games/settings.tsv').read_text())
        self.assertIn('for s in settings {', source[source.index('func apply()'):])

    def test_the_first_run_defaults_are_the_new_ones(self):
        rows = {}
        for line in (ROOT / 'dm/games/settings.tsv').read_text().splitlines():
            if not line.strip() or line.startswith('#'):
                continue
            c = line.split('\t')
            rows[c[0]] = c
        # The everyday screen keeps the console mode; everything diagnostic or optional starts off.
        self.assertEqual(rows['DM_METAL_HUD'][3], '0')
        self.assertEqual(rows['DM_TOUCH_HAPTICS'][3], '0')
        self.assertEqual(rows['DM_RUMBLE'][3], '0')
        self.assertEqual(rows['DM_DD_TOUCH_POLICY'][3], '0')
        self.assertEqual(rows['DM_RUMBLE_GAIN'][3], '1.0')      # the strength itself keeps its 1.0
        # The frame-rate counter's default comes from the IPA build, and that build default is now off (a Mac build
        # leaves the variable unset, which resolves to the same 0).
        self.assertEqual(rows['DM_SHOW_FPS'][3], 'build:DM_SHOW_FPS')
        self.assertRegex((ROOT / 'scripts/build_ipa_from_nsp.py').read_text(), r'(?m)^SHOW_FPS = False')
        # The touch switches' own first-run state: gamepad on, touch on, right stick and pointer speed untouched.
        schema = SCHEMA.read_text()
        self.assertIn('Setting(env: "DM_RIGHT_STICK_VISIBLE", kind: "toggle"', schema)
        self.assertIn('def: "1", options: nil, min: nil, max: nil, step: nil),\n            Setting(env: "DM_TOUCH_CONTROLS"', schema)
        self.assertIn('def: "1.0", options: nil, min: 0.5, max: 2, step: 0.1', schema)

    def test_the_trackpad_value_has_one_spelling_in_both_languages(self):
        swift = re.search(r'let dmTouchInputTrackpad = "([a-z]+)"', SCHEMA.read_text())[1]
        host = re.search(r'#define DM_TOUCH_INPUT_TRACKPAD_VALUE "([a-z]+)"', INPUT_H.read_text())[1]
        self.assertEqual(swift, host)
        # And the overlay reads it through the host's own parser, not with a second comparison of its own.
        self.assertIn('dm_touch_input_mode(', GAMEPAD.read_text())

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
