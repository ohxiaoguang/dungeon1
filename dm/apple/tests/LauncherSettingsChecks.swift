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
        #if os(macOS)
        // The virtual gamepad's haptic click is an iPhone/iPad setting; a Mac launcher must not list it, while the
        // game's own rumble stays (a controller on a Mac rumbles).
        let haptics = Setting(env: "DM_TOUCH_HAPTICS", kind: "toggle", label: "Touch feedback", note: "", def: "1", options: nil, min: nil, max: nil, step: nil)
        let rumble = Setting(env: "DM_RUMBLE", kind: "toggle", label: "Game rumble", note: "", def: "1", options: nil, min: nil, max: nil, step: nil)
        let mac = LauncherModel([haptics, rumble], defaults: d2)
        assert(!mac.settings.contains { $0.env == "DM_TOUCH_HAPTICS" })
        assert(mac.settings.contains { $0.env == "DM_RUMBLE" })
        let mouse = mac.settings.first { $0.env == "DM_MOUSE_HID" }!
        assert(mac.values[mouse.env] == "0")
        mac.set(mouse, "1")
        let restoredMouse = LauncherModel([], defaults: d2)
        assert(restoredMouse.values[mouse.env] == "1")
        assert(restoredMouse.settings.filter { $0.env == "DM_MOUSE_HID" }.count == 1)
        // The Mac process passes only model values to dmhost. The DD bridge
        // must be a real persisted setting, independent of the iOS touch policy.
        let dd = LauncherModel([], defaults: d2, gameTitleID: "01008f1008da6000")
        let bridge = dd.settings.first { $0.env == "DM_DD_MOUSE_POINTER" }!
        assert(dd.values[bridge.env] == "0")
        dd.set(bridge, "1")
        let ddRestored = LauncherModel([], defaults: d2, gameTitleID: "01008F1008DA6000")
        assert(ddRestored.values[bridge.env] == "1")
        assert(ddRestored.settings.filter { $0.env == bridge.env }.count == 1)
        assert(!LauncherModel([], defaults: d2, gameTitleID: "010015100B514000").settings.contains { $0.env == bridge.env })
        assert(!LauncherModel([], defaults: d2, gameTitleID: nil).settings.contains { $0.env == bridge.env })
        let previousBridge = getenv("DM_DD_MOUSE_POINTER").map { String(cString: $0) }
        ddRestored.apply()
        assert(ProcessInfo.processInfo.environment[bridge.env] == "1")
        if let previousBridge { setenv(bridge.env, previousBridge, 1) } else { unsetenv(bridge.env) }
        #endif
        print("Launcher defaults, persistence, editability independent of layout, separate touch input switch and platform filter checks passed")
    }
}
