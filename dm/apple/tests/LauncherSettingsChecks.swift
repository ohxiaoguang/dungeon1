import Foundation
@main struct SettingsChecks {
    @MainActor static func main() {
        let suite = "org.nxnative.launcher-test." + UUID().uuidString
        let defaults = UserDefaults(suiteName: suite)!
        defer { defaults.removePersistentDomain(forName: suite) }
        let pad = Setting(env: "DM_TOUCH_CONTROLS", kind: "toggle", label: "Show virtual controller", note: "", def: "1", options: nil, min: nil, max: nil, step: nil)
        let right = Setting(env: "DM_RIGHT_STICK_VISIBLE", kind: "toggle", label: "Show right stick in 3D mode", note: "", def: "0", options: nil, min: nil, max: nil, step: nil)
        let model = LauncherModel([pad, right], defaults: defaults)
        assert(model.values[pad.env] == "1" && model.values[right.env] == "0")
        model.binding(pad).wrappedValue = "0"
        model.binding(right).wrappedValue = "1"
        let restored = LauncherModel([pad, right], defaults: defaults)
        assert(restored.values[pad.env] == "0" && restored.values[right.env] == "1")
        // The saved layout decides whether the stick is drawn, never whether the setting can be edited: Tap (2), 2D (0)
        // and 3D (1) all leave it editable while the virtual controller is on.
        restored.set(pad, "1")
        for layout in [0, 1, 2] {
            defaults.set(layout, forKey: "DmPadLayout")
            assert(restored.rightStickSettingEnabled)
        }
        restored.set(pad, "0")
        assert(!restored.rightStickSettingEnabled)   // virtual controller off: its stick settings go with it
        restored.set(pad, "1")
        setenv("DM_ENV_FILE_KEYS", "DM_TOUCH_CONTROLS", 1)
        setenv("DM_TOUCH_CONTROLS", "0", 1)
        let locked = LauncherModel([pad, right], defaults: defaults)
        locked.set(pad, "1")
        assert(locked.values[pad.env] == "0")
        assert(!locked.rightStickSettingEnabled)
        // Enable touchscreen input is a switch of its own: on by default, persisted like the others, and it never
        // depends on the overlay's switch (that one may be off while the game still gets touches, and the reverse).
        let input = Setting(env: "DM_TOUCH_INPUT", kind: "toggle", label: "Enable touchscreen input", note: "", def: "1", options: nil, min: nil, max: nil, step: nil)
        let suite2 = "org.nxnative.launcher-input." + UUID().uuidString
        let d2 = UserDefaults(suiteName: suite2)!
        defer { d2.removePersistentDomain(forName: suite2) }
        unsetenv("DM_TOUCH_INPUT"); unsetenv("DM_ENV_FILE_KEYS")
        let fresh = LauncherModel([input, pad], defaults: d2)
        assert(fresh.values[input.env] == "1")                       // default on
        fresh.set(input, "0")
        assert(fresh.values[pad.env] == "1")                         // the overlay switch is untouched by it
        let kept = LauncherModel([input, pad], defaults: d2)
        assert(kept.values[input.env] == "0")                        // persisted for the next launch
        assert(kept.values[pad.env] == "1")
        // A pair saved by the switch-only build is read, kept and handed to the game exactly as it was: opening the
        // launcher never rewrites it. The gamepad now has its own "disable touch" option, so 0 with a drawn gamepad is
        // that option - the same behaviour the player chose back then - and not a kept state.
        let legacy = LauncherModel([input, pad], defaults: d2)       // d2 already holds DM_TOUCH_INPUT=0
        assert(legacy.values["DM_TOUCH_INPUT"] == "0" && legacy.values["DM_TOUCH_CONTROLS"] == "1")
        assert(TouchInputMode.saved(input: legacy.values["DM_TOUCH_INPUT"],
                                    controls: legacy.values["DM_TOUCH_CONTROLS"]) == .gamepad)
        legacy.apply()
        assert(ProcessInfo.processInfo.environment["DM_TOUCH_INPUT"] == "0")
        assert(ProcessInfo.processInfo.environment["DM_TOUCH_CONTROLS"] == "1")
        unsetenv("DM_TOUCH_INPUT"); unsetenv("DM_TOUCH_CONTROLS")
        // The input mode is one choice over those two variables (iOS). The mapping is written once, so it is checked
        // here on the Mac: every preset must round-trip, the gamepad carries its own "touch off" sub-option, and a pair
        // an older build could save with neither the gamepad nor the touch screen is reported as kept.
        for mode in [TouchInputMode.gamepad, .touch, .trackpad] {
            let pair = mode.pair()
            assert(TouchInputMode.saved(input: pair.input, controls: pair.controls) == mode, "round trip \(mode)")
        }
        assert(TouchInputMode.saved(input: nil, controls: nil) == .gamepad)          // nothing saved: the defaults
        assert(TouchInputMode.saved(input: "1", controls: nil) == .gamepad)          // a saved input, no saved overlay
        assert(TouchInputMode.saved(input: "0", controls: "1") == .gamepad)          // the gamepad, its touch screen off
        assert(TouchInputMode.saved(input: "0", controls: "0") == .custom)           // neither of them: a kept pair
        assert(TouchInputMode.saved(input: dmTouchInputTrackpad, controls: "1") == .trackpad)   // the mode wins over the overlay flag
        assert(TouchInputMode.saved(input: "unexpected", controls: "1") == .gamepad) // never a fourth state by accident
        assert(TouchInputMode.allCases.count == 4)
        // Choosing a mode again must not clear that mode's own option: the gamepad keeps a saved "touch off", the
        // other two write the input they need (III.6).
        assert(TouchInputMode.gamepad.pair(keeping: "0").input == "0")
        assert(TouchInputMode.gamepad.pair(keeping: "0").controls == "1")
        assert(TouchInputMode.gamepad.pair(keeping: "1").input == "1")
        assert(TouchInputMode.touch.pair(keeping: "0").input == "1")            // direct touch needs the touch screen
        assert(TouchInputMode.trackpad.pair(keeping: "0").input == dmTouchInputTrackpad)
        // Changing the mode resets the options the previous mode left behind, and only a real change does it: opening
        // the launcher, or re-selecting the mode that is already set, keeps the player's own choice.
        let suiteSwitch = "org.nxnative.launcher-mode-switch." + UUID().uuidString
        let dSwitch = UserDefaults(suiteName: suiteSwitch)!
        defer { dSwitch.removePersistentDomain(forName: suiteSwitch) }
        let policy = Setting(env: "DM_DD_TOUCH_POLICY", kind: "toggle", label: "Touch interaction policy (experimental)", note: "", def: "0", options: nil, min: nil, max: nil, step: nil)
        let speed = Setting(env: "DM_TRACKPAD_SPEED", kind: "range", label: "Pointer speed", note: "", def: "1.0", options: nil, min: 0.5, max: 2, step: 0.1)
        unsetenv("DM_ENV_FILE_KEYS"); unsetenv("DM_DD_TOUCH_POLICY")
        let sw = LauncherModel([input, pad, policy, speed], defaults: dSwitch)
        assert(sw.touchMode == .gamepad)
        sw.setTouchMode(.touch)                                  // direct touch: its option is the policy
        assert(sw.touchMode == .touch && sw.values["DM_TOUCH_INPUT"] == "1" && sw.values["DM_TOUCH_CONTROLS"] == "0")
        sw.setValue("DM_DD_TOUCH_POLICY", "1")                   // the player turns it on there
        sw.setValue("DM_TRACKPAD_SPEED", "1.6")                  // and a speed is left behind from an earlier visit
        sw.setTouchMode(.trackpad)
        assert(sw.touchMode == .trackpad)
        assert(sw.values["DM_TOUCH_INPUT"] == dmTouchInputTrackpad && sw.values["DM_TOUCH_CONTROLS"] == "0")
        assert(sw.values["DM_DD_TOUCH_POLICY"] == "0")           // the policy does not follow into the trackpad
        assert(sw.values["DM_TRACKPAD_SPEED"] == "1.0")          // and the speed starts again at 1.0x
        // Re-selecting the mode that is already set changes nothing, so a choice made in that mode survives a visit to
        // the launcher.
        sw.setValue("DM_TRACKPAD_SPEED", "1.9")
        sw.setTouchMode(.trackpad)
        assert(sw.values["DM_TRACKPAD_SPEED"] == "1.9")
        // Leaving a mode also clears its option: back to direct touch, the speed is default again, and the gamepad no
        // longer inherits a "disable touch" from anywhere.
        sw.setTouchMode(.touch)
        assert(sw.values["DM_TRACKPAD_SPEED"] == "1.0")
        sw.setTouchMode(.gamepad)
        assert(sw.touchMode == .gamepad)
        assert(sw.values["DM_TOUCH_INPUT"] == "1" && sw.values["DM_TOUCH_CONTROLS"] == "1")
        assert(sw.values["DM_DD_TOUCH_POLICY"] == "0")
        // The switch is persisted like any other write: a new model reads the same values back.
        let swAgain = LauncherModel([input, pad, policy, speed], defaults: dSwitch)
        assert(swAgain.touchMode == .gamepad && swAgain.values["DM_TRACKPAD_SPEED"] == "1.0")
        // A value an env file pins is never rewritten, not even by a mode change.
        setenv("DM_ENV_FILE_KEYS", "DM_DD_TOUCH_POLICY", 1)
        setenv("DM_DD_TOUCH_POLICY", "1", 1)
        let pinned = LauncherModel([input, pad, policy, speed], defaults: dSwitch)
        pinned.setTouchMode(.touch)
        assert(pinned.values["DM_DD_TOUCH_POLICY"] == "1")       // the file owns it
        unsetenv("DM_ENV_FILE_KEYS"); unsetenv("DM_DD_TOUCH_POLICY")

        // What the screen shows first, and what it keeps behind the disclosure (the placements are platform data too).
        let suite3 = "org.nxnative.launcher-layout." + UUID().uuidString
        let d3 = UserDefaults(suiteName: suite3)!
        defer { d3.removePersistentDomain(forName: suite3) }
        let opmode = Setting(env: "DM_OPMODE", kind: "choice", label: "Console mode", note: "", def: "1", options: [["1", "Docked"], ["0", "Handheld"]], min: nil, max: nil, step: nil)
        let lang = Setting(env: "DM_LANG", kind: "choice", label: "Game language", note: "", def: "en-US", options: [["en-US", "American English"]], min: nil, max: nil, step: nil)
        let fps = Setting(env: "DM_SHOW_FPS", kind: "toggle", label: "Frame-rate counter", note: "", def: "0", options: nil, min: nil, max: nil, step: nil)
        let rumbleSwitch = Setting(env: "DM_RUMBLE", kind: "toggle", label: "Game rumble", note: "", def: "0", options: nil, min: nil, max: nil, step: nil)
        let strength = Setting(env: "DM_RUMBLE_GAIN", kind: "range", label: "Rumble strength", note: "", def: "1.0", options: nil, min: 0, max: 3, step: 0.1)
        let hud = Setting(env: "DM_METAL_HUD", kind: "toggle", label: "Performance HUD", note: "", def: "0", options: nil, min: nil, max: nil, step: nil)
        let layout = LauncherModel([opmode, lang, fps, rumbleSwitch, strength, hud], defaults: d3)
        assert(layout.commonSettings.map { $0.env } == ["DM_OPMODE"])                       // the game language has no row at all
        assert(layout.advancedSettings.map { $0.env } == ["DM_SHOW_FPS", "DM_RUMBLE", "DM_METAL_HUD"])
        assert(layout.advancedRows.map { $0.env } == ["DM_SHOW_FPS", "DM_RUMBLE", "DM_METAL_HUD"])   // rumble off: no strength
        assert(layout.rumbleStrength == nil)
        layout.set(rumbleSwitch, "1")
        assert(layout.advancedRows.map { $0.env } == ["DM_SHOW_FPS", "DM_RUMBLE", "DM_RUMBLE_GAIN", "DM_METAL_HUD"])
        // Nothing is drawn twice, and a composed variable is drawn by nobody (it is applied from its saved value).
        assert(Set(layout.advancedRows.map { $0.env }).count == layout.advancedRows.count)
        assert(!layout.commonSettings.contains { $0.env == "DM_LANG" } && !layout.advancedSettings.contains { $0.env == "DM_LANG" })
        assert(!layout.advancedSettings.contains { $0.env == "DM_RUMBLE_GAIN" })   // only through advancedRows
        #if os(macOS)
        assert(settingPlacement("DM_DD_TOUCH_POLICY") == .advanced)   // on a Mac the policy keeps its own row
        #endif
        assert(settingPlacement("DM_LANG") == .composed)
        #if os(macOS)
        // The virtual gamepad's haptic click is an iPhone/iPad setting; a Mac launcher must not list it, while the
        // game's own rumble stays (a controller on a Mac rumbles).
        let haptics = Setting(env: "DM_TOUCH_HAPTICS", kind: "toggle", label: "Touch feedback", note: "", def: "1", options: nil, min: nil, max: nil, step: nil)
        let rumble = Setting(env: "DM_RUMBLE", kind: "toggle", label: "Game rumble", note: "", def: "1", options: nil, min: nil, max: nil, step: nil)
        let mac = LauncherModel([haptics, rumble], defaults: d2)
        assert(!mac.settings.contains { $0.env == "DM_TOUCH_HAPTICS" })
        assert(mac.settings.contains { $0.env == "DM_RUMBLE" })
        // The Mac process passes only model values to dmhost, so the mouse experiment must be real persisted settings.
        let mouse = mac.settings.first { $0.env == "DM_MOUSE_HID" }!
        assert(mac.values[mouse.env] == mouse.def)                   // nothing saved yet: the build's default
        mac.set(mouse, "0")
        let restoredMouse = LauncherModel([], defaults: d2)
        assert(restoredMouse.values[mouse.env] == "0")               // and the next launch reads what was chosen
        assert(restoredMouse.settings.filter { $0.env == "DM_MOUSE_HID" }.count == 1)
        restoredMouse.set(restoredMouse.settings.first { $0.env == "DM_MOUSE_HID" }!, "1")
        // One switch over both variables: on sets both, off clears both, never half.
        let merged = LauncherModel([], defaults: d2, gameTitleID: "01008F1008DA6000")
        assert(merged.mouseExperiment && !merged.mouseExperimentSplit)
        merged.setMouseExperiment(false)
        assert(!merged.mouseExperiment)
        assert(merged.values["DM_MOUSE_HID"] == "0" && merged.values["DM_DD_MOUSE_POINTER"] == "0")
        merged.setMouseExperiment(true)
        assert(merged.mouseExperiment && !merged.mouseExperimentSplit)
        // The Darkest Dungeon bridge is a setting of this title only, independent of the iOS touch policy.
        let dd = LauncherModel([], defaults: d2, gameTitleID: "01008f1008da6000")
        let bridge = dd.settings.first { $0.env == "DM_DD_MOUSE_POINTER" }!
        assert(dd.values[bridge.env] == bridge.def)
        dd.set(bridge, "0")
        let ddRestored = LauncherModel([], defaults: d2, gameTitleID: "01008F1008DA6000")
        assert(ddRestored.values[bridge.env] == "0")
        assert(ddRestored.settings.filter { $0.env == bridge.env }.count == 1)
        assert(!LauncherModel([], defaults: d2, gameTitleID: "010015100B514000").settings.contains { $0.env == bridge.env })
        assert(!LauncherModel([], defaults: d2, gameTitleID: nil).settings.contains { $0.env == bridge.env })
        // A pair saved as two different values keeps its own two switches: the merged one must not fold it together
        // just by being read (Mouse HID on, the bridge off, as set above).
        assert(ddRestored.mouseExperimentSplit && !ddRestored.mouseExperiment)
        assert(ddRestored.mouseRawSettings.count == 2)
        // A title without the pointer bridge has one raw switch, and the merged one must not invent a second variable.
        let other = LauncherModel([], defaults: d2, gameTitleID: "010015100B514000")
        assert(other.mouseRawSettings.count == 1 && !other.mouseExperimentSplit)
        other.setMouseExperiment(false)
        assert(other.values["DM_DD_MOUSE_POINTER"] == nil)   // no setting, no write
        let previousBridge = getenv("DM_DD_MOUSE_POINTER").map { String(cString: $0) }
        let previousMouse = getenv("DM_MOUSE_HID").map { String(cString: $0) }
        ddRestored.apply()
        assert(ProcessInfo.processInfo.environment[bridge.env] == "0")
        assert(ProcessInfo.processInfo.environment["DM_MOUSE_HID"] == "1")
        if let previousBridge { setenv(bridge.env, previousBridge, 1) } else { unsetenv(bridge.env) }
        if let previousMouse { setenv("DM_MOUSE_HID", previousMouse, 1) } else { unsetenv("DM_MOUSE_HID") }
        #endif

        // The instructions beside the input mode: every mode the picker offers has its own text, every line is in the
        // shared catalog (so the sheet cannot show an English sentence in a Chinese interface), and the wording
        // matches what the input paths do - a long press is inert, and a two-finger swipe is not a scroll here.
        for mode in [TouchInputMode.gamepad, .touch, .trackpad] {
            let lines = TouchHelp.lines(mode)
            assert(lines.count >= 2, "no instructions for \(mode)")
            for line in lines {
                assert(!line.title.isEmpty && !line.text.isEmpty)
                assert(GUIText.catalog[line.title] != nil, "missing translation: \(line.title)")
                assert(GUIText.catalog[line.text] != nil, "missing translation: \(line.text)")
            }
        }
        let pad_help = TouchHelp.lines(.gamepad).map(\.title)
        assert(pad_help.contains("Buttons and sticks") && pad_help.contains("Three layouts"))
        assert(pad_help.contains("Disable touch input"))
        let touch_help = TouchHelp.lines(.touch).map(\.title)
        assert(touch_help.contains("The glass is the game") && touch_help.contains("Touch interaction policy"))
        let pad_instructions = TouchHelp.lines(.trackpad).map(\.title)
        assert(pad_instructions.contains("One finger moves the pointer"))
        assert(pad_instructions.contains("One tap clicks"))
        assert(pad_instructions.contains("One finger, hold"))            // the hold is back, at the pointer
        assert(pad_instructions.contains("Two fingers swipe"))           // one two-finger path, no pause to learn
        assert(!pad_instructions.contains("pause, then move"))           // the old drag branch is gone
        assert(pad_instructions.contains("The pointer is the target"))
        // The mode's own line under the picker keeps up with it: no double-tap drag, no "a long press does nothing".
        assert(!TouchInputMode.trackpad.note.contains("double tap"))
        assert(!TouchInputMode.trackpad.note.contains("long press does nothing"))
        assert(TouchInputMode.trackpad.note.contains("resting finger"))
        print("Launcher defaults, persistence, editability independent of layout, separate touch input switch, input-mode mapping, instructions and platform filter checks passed")
    }
}
