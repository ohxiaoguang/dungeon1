// SPDX-License-Identifier: MIT
// Shared iOS/macOS settings schema, persistence and controls.
import SwiftUI
import Foundation
import Darwin

struct Setting: Decodable, Identifiable {
    let env, kind, label, note, def: String
    let options: [[String]]?   // choice: [value, label]
    let min, max, step: Double?   // range
    var id: String { env }
    enum CodingKeys: String, CodingKey { case env, kind, label, note, def = "default", options, min, max, step }
}
struct SettingsFile: Decodable { let settings: [Setting] }


// MARK: - What the screen shows first

/// Where a setting is drawn. The values and defaults stay exactly as the packed JSON has them - this only decides
/// whether a switch is one of the everyday ones, one that matters while experimenting or diagnosing, or one with no
/// row of its own (the input mode and the merged mouse switch draw their variables, the rumble strength sits under
/// its switch, and a variable kept only for compatibility - the game language - has no row at all).
enum SettingPlacement { case common, advanced, composed }

func settingPlacement(_ env: String) -> SettingPlacement {
    switch env {
    case "DM_SHOW_FPS",              // diagnostics
         "DM_METAL_HUD",             // Apple's HUD over the picture: diagnostics
         "DM_RUMBLE",                // off unless a controller or a phone is meant to vibrate
         "DM_TOUCH_HAPTICS",         // a detail of the overlay, not of the game
         "DM_RIGHT_STICK_VISIBLE":   // an overlay detail (disabled while the gamepad is not the mode)
        return .advanced
    case "DM_TOUCH_INPUT", "DM_TOUCH_CONTROLS",   // the input-mode row is their only control
         "DM_RUMBLE_GAIN",                        // the strength belongs under the rumble switch
         "DM_TRACKPAD_SPEED",                     // drawn under the trackpad mode
         "DM_MOUSE_HID", "DM_DD_MOUSE_POINTER",   // one switch is drawn over this pair (unless it was saved split)
         "DM_LANG":                               // kept and applied from its saved value; no row (see below)
        return .composed
    case "DM_DD_TOUCH_POLICY":
        #if os(iOS)
        return .composed   // drawn under Direct touch, the mode it is about (it still applies in every mode)
        #else
        return .advanced   // on a Mac it belongs with the other experimental switches
        #endif
    default:
        return .common
    }
}

/// The one input choice, over the two variables the overlay already read. Always compiled - only the rows that show
/// it are iPhone/iPad-only (TouchInputModeRow) - so the mapping is checked without a phone (dm/apple/tests).
let dmTouchInputTrackpad = "trackpad"   // DM_TOUCH_INPUT_TRACKPAD_VALUE in dm/host/dm_input.h: one spelling per language

enum TouchInputMode: String, CaseIterable {
    case gamepad, touch, trackpad, custom
    /// The row's name and the line under it, as English keys: GUIText renders both.
    var title: String {
        switch self {
        case .gamepad: return "Virtual gamepad"
        case .touch: return "Direct touch"
        case .trackpad: return "Virtual trackpad"
        case .custom: return "Kept from an earlier version"
        }
    }
    var note: String {
        switch self {
        case .gamepad:
            return "The gamepad over the picture: buttons, sticks and the layout button work as before, and touches no control takes still reach the game."
        case .touch:
            return "No gamepad: every touch is the game's own touch screen. Tap, drag and hold work as the game defines them."
        case .trackpad:
            return "The whole screen is a trackpad: swiping moves the pointer, a tap clicks where it points, a long press does nothing. Two fingers swipe the game's own touch (torch, lists); two fingers after a pause carry the item."
        case .custom:
            return "Saved by an earlier version and kept as it is: no gamepad and no touch input. Pick a mode above to replace it."
        }
    }
    /// The mode a saved pair describes. The gamepad may have its touch screen switched off (its own sub-option), so
    /// `0` plus a drawn gamepad is the gamepad, not a kept state; only a pair with neither the gamepad nor the touch
    /// screen describes nothing a player can pick today.
    static func saved(input: String?, controls: String?) -> TouchInputMode {
        switch input ?? "1" {
        case dmTouchInputTrackpad: return .trackpad
        case "0": return controls == "0" ? .custom : .gamepad
        default: return controls == "0" ? .touch : .gamepad
        }
    }
    /// The pair this mode writes. `.gamepad` keeps a saved "touch off", because that sub-option belongs to the mode:
    /// re-selecting the mode must not switch the touch screen back on. `.custom` writes what it is given and is never
    /// selected by a control, so only a pair the player already had reports it.
    func pair(keeping input: String? = nil) -> (input: String, controls: String) {
        switch self {
        case .gamepad: return (input == "0" ? "0" : "1", "1")
        case .touch: return ("1", "0")
        case .trackpad: return (dmTouchInputTrackpad, "0")
        case .custom: return (input ?? "0", "1")
        }
    }
}


final class LauncherModel: ObservableObject {
    private let defaults: UserDefaults
    let settings: [Setting]
    let fromFile: Set<String>   // set by an env file: shown, not changed
    @Published var values: [String: String] = [:]

    init(_ settings: [Setting], defaults: UserDefaults = .standard,
         gameTitleID: String? = Bundle.main.object(forInfoDictionaryKey: "NXTitleID") as? String) {
        self.defaults = defaults
        #if os(iOS)
        // The iPhone/iPad touch switches. They stay separate variables on purpose - whether the game receives the
        // touch screen, whether the overlay is drawn, and whether pressing it vibrates are different questions with
        // different readers (DmGamepad.m, hle_hid.c) - but the launcher shows one input mode over the first two, with
        // that mode's own option under it, and the rest behind Advanced. DM_TOUCH_INPUT also carries the virtual
        // trackpad, which replaces the overlay rather than adding to it, and the pointer speed is a gain the overlay
        // applies to the cursor only (it never moves a click).
        let settings = settings + [
            // Not drawn as a row of its own: the gamepad mode's option below inverts it ("disable touch" is 0), and
            // the mode picker writes the same variable. It stays in the list because apply() hands it to the game.
            Setting(env: "DM_TOUCH_INPUT", kind: "toggle", label: "Enable touchscreen input", note: "The game receives taps, drags and gestures. The virtual controller and this screen keep working when it is off.", def: "1", options: nil, min: nil, max: nil, step: nil),
            Setting(env: "DM_TOUCH_CONTROLS", kind: "toggle", label: "Show virtual controller", note: "External controllers and game touch input remain available.", def: "1", options: nil, min: nil, max: nil, step: nil),
            Setting(env: "DM_RIGHT_STICK_VISIBLE", kind: "toggle", label: "Show right stick in 3D mode", note: "Changes appearance only. The right stick is drawn in the 3D layout.", def: "0", options: nil, min: nil, max: nil, step: nil),
            Setting(env: "DM_TRACKPAD_SPEED", kind: "range", label: "Pointer speed", note: "How far the pointer travels for a swipe: 1.0× follows the finger one to one. It never moves where a tap clicks.", def: "1.0", options: nil, min: 0.5, max: 2, step: 0.1)]
        #endif
        #if os(macOS)
        // Touch feedback is the virtual gamepad's haptic click (dm/ios/Sources/DmGamepad.m is its only reader), so a
        // Mac launcher must not offer it even when a profile's settings name it. The switches above are added under
        // #if os(iOS) and never reach this list. Game rumble (DM_RUMBLE) stays: a controller on a Mac rumbles.
        // Mouse HID and the Darkest Dungeon pointer bridge keep their own variables and their dependency (the bridge
        // is inert without Mouse HID); the screen puts one switch in front of the pair, in the everyday area.
        var settings = settings.filter { $0.env != "DM_TOUCH_HAPTICS" && $0.env != "DM_MOUSE_HID" && $0.env != "DM_DD_MOUSE_POINTER" } + [
            Setting(env: "DM_MOUSE_HID", kind: "toggle", label: "Enable native Mouse HID (experimental)", note: "Keeps left-button touch emulation. The game must read Switch Mouse HID; this does not add a game-specific pointer bridge.", def: "1", options: nil, min: nil, max: nil, step: nil)]
        if gameTitleID?.uppercased() == "01008F1008DA6000" {
            settings.append(Setting(env: "DM_DD_MOUSE_POINTER", kind: "toggle",
                label: "Darkest Dungeon pointer bridge (experimental)",
                note: "Enable native Mouse HID as well. After a left click selects touch input, mouse movement can drive hover. Controller input retains focus until the next click.",
                def: "1", options: nil, min: nil, max: nil, step: nil))
        }
        #endif
        self.settings = settings
        fromFile = Set((ProcessInfo.processInfo.environment["DM_ENV_FILE_KEYS"] ?? "").split(separator: " ").map(String.init))
        for s in settings {
            if fromFile.contains(s.env), let v = ProcessInfo.processInfo.environment[s.env] { values[s.env] = v; continue }
            let saved = defaults.string(forKey: "launcher." + s.env)
            values[s.env] = saved.flatMap { v in s.options == nil || s.options!.contains { $0[0] == v } ? v : nil } ?? s.def   // a saved choice the game no longer offers: its default
        }
    }

    func set(_ s: Setting, _ value: String) { setValue(s.env, value) }
    func binding(_ s: Setting) -> Binding<String> { Binding(get: { self.values[s.env] ?? s.def }, set: { self.set(s, $0) }) }
    /// One place that writes a variable and remembers it, so a switch drawn by a control above it (the input mode
    /// over two variables, the merged mouse switch) persists exactly like a row of its own. A value an env file set
    /// is never written over.
    func setValue(_ env: String, _ value: String) {
        guard !fromFile.contains(env) else { return }
        values[env] = value
        defaults.set(value, forKey: "launcher." + env)
    }
    func locked(_ env: String) -> Bool { fromFile.contains(env) }
    func setting(_ env: String) -> Setting? { settings.first { $0.env == env } }

    /// The everyday switches and everything behind Advanced, in the order the packed JSON lists them.
    var commonSettings: [Setting] { settings.filter { settingPlacement($0.env) == .common } }
    var advancedSettings: [Setting] { settings.filter { settingPlacement($0.env) == .advanced } }
    /// The advanced rows in order, with the rumble strength right under its switch - and only while rumble is on.
    var advancedRows: [Setting] {
        var rows: [Setting] = []
        for s in advancedSettings {
            rows.append(s)
            if s.env == "DM_RUMBLE", let strength = rumbleStrength { rows.append(strength) }
        }
        return rows
    }
    /// The rumble strength is a sub-setting: drawn under the rumble switch, and only while rumble itself is on.
    var rumbleStrength: Setting? { values["DM_RUMBLE"] == "0" ? nil : setting("DM_RUMBLE_GAIN") }

    // Editable while the virtual controller is on, in every layout: the saved layout only decides whether the stick is
    // drawn (3D yes, 2D and Tap no), so a setting changed in 2D or Tap must not be locked out until the player switches.
    var rightStickSettingEnabled: Bool {
        values["DM_TOUCH_CONTROLS"] != "0"
    }

    #if os(iOS)
    /// The input mode over DM_TOUCH_INPUT and DM_TOUCH_CONTROLS. A pair saved by an earlier version that is none of
    /// the three presets (no gamepad and no touch input) is reported as `.custom` and left untouched: opening this
    /// screen never rewrites a choice the player made in a build that could not express it.
    var touchMode: TouchInputMode {
        TouchInputMode.saved(input: values["DM_TOUCH_INPUT"], controls: values["DM_TOUCH_CONTROLS"])
    }
    /// The presets, plus the current state only when that is a kept legacy pair: nothing else can select it.
    var touchModes: [TouchInputMode] { TouchInputMode.allCases.filter { $0 != .custom || touchMode == .custom } }
    var touchModeLocked: Bool { locked("DM_TOUCH_INPUT") || locked("DM_TOUCH_CONTROLS") }
    /// Both variables in one step, so the modes can never be half applied; `.custom` writes nothing and stays as saved.
    func setTouchMode(_ mode: TouchInputMode) {
        guard mode != .custom else { return }
        let pair = mode.pair(keeping: values["DM_TOUCH_INPUT"])
        setValue("DM_TOUCH_INPUT", pair.input)
        setValue("DM_TOUCH_CONTROLS", pair.controls)
    }
    /// The gamepad's own option, right under the mode: the touch screen switched off while the pad keeps working. It is
    /// the same variable the mode rides on (DM_TOUCH_INPUT) - no second switch, no second reader - so `0` means "no
    /// ordinary touch input" exactly as it always did.
    var gamepadTouchDisabled: Bool { values["DM_TOUCH_INPUT"] == "0" }
    var gamepadTouchLocked: Bool { locked("DM_TOUCH_INPUT") }
    func setGamepadTouchDisabled(_ off: Bool) { setValue("DM_TOUCH_INPUT", off ? "0" : "1") }
    /// The direct-touch option and the trackpad's speed, from the same table as every other row.
    var touchPolicy: Setting? { setting("DM_DD_TOUCH_POLICY") }
    var pointerSpeed: Setting? { setting("DM_TRACKPAD_SPEED") }
    #endif

    #if os(macOS)
    /// The experimental mouse is one switch over two variables. Mouse HID is what publishes the pointer and what the
    /// game can see at all; the Darkest Dungeon bridge requires it and adds the hover handoff. Only both together
    /// change anything the player can observe, so the switch shows that pair and sets both - while a pair saved as
    /// two different values keeps its own two switches (below), never silently rewritten.
    var mouseExperiment: Bool { mouseOn("DM_MOUSE_HID") && mouseOn("DM_DD_MOUSE_POINTER") }
    var mouseExperimentSplit: Bool { mouseOn("DM_MOUSE_HID") != mouseOn("DM_DD_MOUSE_POINTER") }
    var mouseRawSettings: [Setting] { settings.filter { $0.env == "DM_MOUSE_HID" || $0.env == "DM_DD_MOUSE_POINTER" } }
    func setMouseExperiment(_ enabled: Bool) {
        setValue("DM_MOUSE_HID", enabled ? "1" : "0")
        if values["DM_DD_MOUSE_POINTER"] != nil { setValue("DM_DD_MOUSE_POINTER", enabled ? "1" : "0") }
    }
    private func mouseOn(_ env: String) -> Bool { (values[env] ?? "1") != "0" }
    #endif

    // Before the game starts: every setting not set by an env file goes into the environment (DM_LANG replaces the packed language main.m set as a default)
    func apply() {
        for s in settings {
            let v = values[s.env] ?? s.def
            if fromFile.contains(s.env) { fputs("launcher: \(s.env) kept at \(v) (env file)\n", stderr); continue }
            defaults.set(v, forKey: "launcher." + s.env)
            setenv(s.env, v, 1); fputs("launcher: \(s.env)=\(v)\n", stderr)
        }
    }
}


// MARK: - Rows

/// One setting: its control and, under it, the line that explains it. Sections group these, so an everyday switch and
/// an experimental one look the same and a note always stays with its own switch.
struct SettingLine: View {
    let s: Setting
    @ObservedObject var m: LauncherModel
    @EnvironmentObject private var language: LanguagePreferences
    private func l(_ s: String) -> String { GUIText(key: s).render(language.language) }
    private var locked: Bool { m.locked(s.env) }
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            switch s.kind {
            case "choice":
                Picker(l(s.label), selection: m.binding(s)) { ForEach(s.options ?? [], id: \.[0]) { Text(l($0[1])).tag($0[0]) } }
            case "range":
                let lo = s.min ?? 0, hi = s.max ?? 1
                let v = Binding<Double>(get: { Double(m.values[s.env] ?? s.def) ?? hi }, set: { m.set(s, String(format: "%.2f", $0)) })
                HStack {
                    Text(l(s.label))
                    Slider(value: v, in: lo...hi, step: s.step ?? 0.05)
                    Text("\(Int((v.wrappedValue * 100).rounded())) %").monospacedDigit().foregroundStyle(.secondary).frame(width: 56, alignment: .trailing)
                }
            default:
                Toggle(l(s.label), isOn: Binding(get: { (m.values[s.env] ?? s.def) == "1" }, set: { m.set(s, $0 ? "1" : "0") }))
            }
            let note = noteText
            if !note.isEmpty { Text(note).font(.caption).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true) }
        }
        .padding(.vertical, 2)
        .disabled(locked || childOfAnotherSwitch)
    }
    private var noteText: String {
        if locked { return (s.note.isEmpty ? "" : l(s.note) + " · ") + l("Set by an env file") }
        if childOfAnotherSwitch { return (s.note.isEmpty ? "" : l(s.note) + " · ") + l("Only the virtual gamepad draws it.") }
        return l(s.note)
    }
    /// Two of these are details of another switch: the right stick belongs to the overlay, the strength to rumble.
    private var childOfAnotherSwitch: Bool {
        switch s.env {
        case "DM_RIGHT_STICK_VISIBLE": return !m.rightStickSettingEnabled
        case "DM_RUMBLE_GAIN": return m.values["DM_RUMBLE"] == "0"
        default: return false
        }
    }
}

/// The pointer speed, drawn as a multiplier rather than the percentage the generic range row shows.
struct PointerSpeedRow: View {
    let s: Setting
    @ObservedObject var m: LauncherModel
    @EnvironmentObject private var language: LanguagePreferences
    private func l(_ s: String) -> String { GUIText(key: s).render(language.language) }
    var body: some View {
        let lo = s.min ?? 0.5, hi = s.max ?? 2, step = s.step ?? 0.1
        let v = Binding<Double>(get: { Double(m.values[s.env] ?? s.def) ?? 1 }, set: { m.set(s, String(format: "%.1f", $0)) })
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(l(s.label))
                Slider(value: v, in: lo...hi, step: step)
                Text(String(format: "%.1f×", v.wrappedValue)).monospacedDigit().foregroundStyle(.secondary)
                    .frame(width: 48, alignment: .trailing)
            }
            let note = m.locked(s.env) ? (s.note.isEmpty ? "" : l(s.note) + " · ") + l("Set by an env file") : l(s.note)
            if !note.isEmpty { Text(note).font(.caption).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true) }
        }
        .padding(.vertical, 2)
        .disabled(m.locked(s.env))
    }
}

/// The advanced block's header. The whole row toggles it - not just the chevron - through a plain Button whose label
/// fills the row, which is the SwiftUI way to get one hit area: the rows themselves stay outside the button, so no
/// switch inside it can be hit by this tap and no second tap is needed. A Button keeps the row in the accessibility
/// tree with the button trait, its name, its hint, and expanded/collapsed as its value.
struct AdvancedToggleRow: View {
    @Binding var expanded: Bool
    @EnvironmentObject private var language: LanguagePreferences
    private func l(_ s: String) -> String { GUIText(key: s).render(language.language) }
    var body: some View {
        Button {
            withAnimation(.easeInOut(duration: 0.18)) { expanded.toggle() }
        } label: {
            HStack(spacing: 8) {
                Label(l("Advanced"), systemImage: "slider.horizontal.3")
                Spacer(minLength: 8)
                Image(systemName: expanded ? "chevron.up" : "chevron.down")
                    .font(.footnote.weight(.semibold)).foregroundStyle(.secondary)
            }
            .contentShape(Rectangle())   // the gap between the title and the chevron is part of the row's hit area
        }
        .buttonStyle(.plain)
        .accessibilityIdentifier("launcher.advanced")
        .accessibilityLabel(l("Advanced"))
        .accessibilityHint(l("Shows or hides the advanced settings."))
        .accessibilityValue(expanded ? l("Expanded") : l("Collapsed"))
        .accessibilityAddTraits(.isButton)
    }
}

/// The settings both launchers show: the input choice with its own option (iPhone/iPad), the everyday switches, the
/// interface language, and one collapsed block with everything experimental or diagnostic. Shared, so the two
/// platforms cannot drift apart.
struct LauncherSettingsSections: View {
    @ObservedObject var m: LauncherModel
    @EnvironmentObject private var language: LanguagePreferences
    @State private var advanced = false
    private func l(_ s: String) -> String { GUIText(key: s).render(language.language) }
    var body: some View {
        Section {
            #if os(iOS)
            TouchInputModeRow(m: m)
            #endif
            ForEach(m.commonSettings) { SettingLine(s: $0, m: m) }
            #if os(macOS)
            MouseExperimentRow(m: m)   // the everyday area: on by default, and it is a normal entry here
            #endif
        } header: {
            Text(l("Settings"))
        }
        LauncherLanguageRow()
        Section {
            AdvancedToggleRow(expanded: $advanced)
            if advanced {
                ForEach(m.advancedRows) { SettingLine(s: $0, m: m) }
            }
        }
    }
}

#if os(iOS)
/// The one input choice, with the option that belongs to the chosen mode directly under it and a question mark that
/// opens the instructions for it. One option at a time: the three modes never share a sub-option, and each one is the
/// same variable the game already reads.
struct TouchInputModeRow: View {
    @ObservedObject var m: LauncherModel
    @EnvironmentObject private var language: LanguagePreferences
    @State private var help = false
    private func l(_ s: String) -> String { GUIText(key: s).render(language.language) }
    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(spacing: 6) {
                Text(l("Input mode"))
                // A small button beside the title, not another switch: it opens the sheet and adds no row and no
                // height to the screen.
                Button { help = true } label: {
                    Image(systemName: "questionmark.circle").imageScale(.medium).foregroundStyle(.tint)
                }
                .buttonStyle(.borderless)
                .accessibilityIdentifier("launcher.input.help")
                .accessibilityLabel(l("Input help"))
                .accessibilityHint(l("How each input mode is used."))
                Spacer(minLength: 4)
                // The picker keeps its place at the end of the same row: the mode's name and its value read as one
                // iOS settings line, and the question mark sits right after the title.
                Picker("", selection: Binding(get: { m.touchMode }, set: { m.setTouchMode($0) })) {
                    ForEach(m.touchModes, id: \.self) { mode in Text(l(mode.title)).tag(mode) }
                }
                .pickerStyle(.menu)
                .labelsHidden()
                .disabled(m.touchModeLocked)
            }
            let note = m.touchModeLocked ? l(m.touchMode.note) + " · " + l("Set by an env file") : l(m.touchMode.note)
            Text(note).font(.caption).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
            subOption
        }
        .padding(.vertical, 2)
        .sheet(isPresented: $help) { InputHelpSheet(start: m.touchMode).environmentObject(language) }
    }
    @ViewBuilder private var subOption: some View {
        switch m.touchMode {
        case .gamepad:
            Toggle(l("Disable touch input"), isOn: Binding(get: { m.gamepadTouchDisabled }, set: { m.setGamepadTouchDisabled($0) }))
                .disabled(m.gamepadTouchLocked)
            Text(m.gamepadTouchLocked ? l(gamepadNote) + " · " + l("Set by an env file") : l(gamepadNote))
                .font(.caption).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
        case .touch:
            if let policy = m.touchPolicy { SettingLine(s: policy, m: m) }
        case .trackpad:
            if let speed = m.pointerSpeed { PointerSpeedRow(s: speed, m: m) }
        case .custom:
            EmptyView()   // a kept pair has no option of its own; the note above says how to leave it
        }
    }
    private var gamepadNote: String {
        "On: the game is sent no ordinary touch input. The gamepad, its layouts and a physical controller keep working."
    }
}

/// The instructions, opened from the question mark beside the input mode. It starts on the mode the launcher is set
/// to and can show the other two, so a player can look ahead without changing anything. A sheet, so the launcher's
/// own height does not change; it scrolls, so it fits a small iPhone and an iPad in portrait (Stage Manager) alike.
struct InputHelpSheet: View {
    @Environment(\.dismiss) private var dismiss
    @EnvironmentObject private var language: LanguagePreferences
    @State private var mode: TouchInputMode
    init(start: TouchInputMode) { _mode = State(initialValue: start == .custom ? .trackpad : start) }
    private func l(_ s: String) -> String { GUIText(key: s).render(language.language) }
    private static let modes: [TouchInputMode] = [.gamepad, .touch, .trackpad]
    var body: some View {
        NavigationStack {
            Form {
                Section {
                    Picker(l("Input mode"), selection: $mode) {
                        ForEach(Self.modes, id: \.self) { Text(l($0.title)).tag($0) }
                    }
                    .pickerStyle(.segmented)
                }
                Section(l(mode.title)) {
                    ForEach(TouchHelp.lines(mode), id: \.title) { line in
                        VStack(alignment: .leading, spacing: 3) {
                            Text(l(line.title)).font(.subheadline.weight(.semibold))
                            Text(l(line.text)).font(.caption).foregroundStyle(.secondary)
                                .fixedSize(horizontal: false, vertical: true)
                        }
                        .padding(.vertical, 2)
                    }
                }
            }
            .navigationTitle(l("How to play"))
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .confirmationAction) { Button(l("Done")) { dismiss() } } }
        }
    }
}
#endif

/// One line of the instructions: a bold title and the sentence under it, both as English keys GUIText renders. Kept
/// outside the iOS-only view so the LauncherSettingsChecks (which build on a Mac) can assert that every mode has its
/// own text and that no key is missing from the catalog.
struct TouchHelpLine { let title: String; let text: String }

enum TouchHelp {
    static func lines(_ mode: TouchInputMode) -> [TouchHelpLine] {
        switch mode {
        case .gamepad: return [
            TouchHelpLine(title: "Buttons and sticks",
                          text: "The pad sits over the picture: ZL/L and ZR/R in the top corners, − and + at the top centre, the left stick in the bottom-left, A/B/X/Y in the bottom-right. The button at the top centre switches the layout."),
            TouchHelpLine(title: "Three layouts",
                          text: "2D keeps the essential pad, 3D adds the D-pad, L3/R3 and the optional right stick, and Tap draws only the layout button and sends every other touch to the game."),
            TouchHelpLine(title: "Touches outside the controls",
                          text: "A touch that lands on no control still reaches the game's own touch screen, so the map, the tablets and the lists keep working."),
            TouchHelpLine(title: "Disable touch input",
                          text: "On: the game is sent no ordinary touch input. The gamepad, its layouts and a physical controller keep working."),
        ]
        case .touch: return [
            TouchHelpLine(title: "The glass is the game",
                          text: "Every finger is the game's own touch screen: tap, drag and hold mean exactly what the game defines, as on the Switch."),
            TouchHelpLine(title: "Touch interaction policy",
                          text: "On (experimental), this build adds its own hold behaviour: a held combat or camping skill toggles, the Nomad and Comet shops focus on a tap and run one purchase on a 0.5 s hold, and a held town portrait opens its details on release. Off is the game's original behaviour."),
        ]
        case .trackpad: return [
            TouchHelpLine(title: "One finger moves the pointer",
                          text: "Swipe anywhere: only the pointer moves, and it stays where you left it. Hover and tooltips follow it."),
            TouchHelpLine(title: "One tap clicks",
                          text: "A quick tap clicks where the pointer is, never where the finger is. Two quick taps are the game's own double click."),
            TouchHelpLine(title: "A long press does nothing",
                          text: "Resting a finger never presses, drags, buys or toggles anything, however long it stays. Only a tap or a two-finger drag acts."),
            TouchHelpLine(title: "Two fingers, pause, then move",
                          text: "Hold two fingers still for about a third of a second and then move them: the item under the pointer is dragged and the pointer turns orange while it is carried. Lifting either finger ends the drag."),
            TouchHelpLine(title: "Two fingers, straight away",
                          text: "A two-finger swipe is the game's own touch drag, starting where the pointer is: it pulls the torch down and scrolls a list, and it never clicks. It cannot turn into a drag or the other way round. On a draggable item it picks that item up, exactly as a finger drag there would."),
            TouchHelpLine(title: "The pointer is the target",
                          text: "Everything above applies where the pointer is, never where your fingers are, so the pointer is what has to be over the item, skill or portrait you mean."),
        ]
        case .custom: return [
            TouchHelpLine(title: "Kept from an earlier version",
                          text: "An earlier version saved a combination none of the three modes describes. It is left exactly as it was; choose a mode above to replace it."),
        ]
        }
    }
}

#if os(macOS)
/// One switch in front of the two mouse experiments. A pair saved as two different values shows its own two switches
/// underneath instead, so nothing is written over just by opening the screen.
struct MouseExperimentRow: View {
    @ObservedObject var m: LauncherModel
    @EnvironmentObject private var language: LanguagePreferences
    private func l(_ s: String) -> String { GUIText(key: s).render(language.language) }
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Toggle(l("Experimental mouse control"), isOn: Binding(get: { m.mouseExperiment }, set: { m.setMouseExperiment($0) }))
            Text(l("Publishes the pointer as Switch Mouse HID and, in Darkest Dungeon, lets mouse movement steer the game's own pointer once a click has selected touch input. Off is the untouched mouse and touch behaviour."))
                .font(.caption).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
            if m.mouseExperimentSplit {
                Text(l("Saved as two different switches; these are kept until you set them here."))
                    .font(.caption).foregroundStyle(.orange).fixedSize(horizontal: false, vertical: true)
                ForEach(m.mouseRawSettings) { SettingLine(s: $0, m: m) }
            }
        }
        .padding(.vertical, 2)
    }
}
#endif


struct LauncherLanguageRow: View {
    @EnvironmentObject private var language: LanguagePreferences
    var body: some View {
        Picker(GUIText(key: "Interface language").render(language.language), selection: $language.language) {
            ForEach(InterfaceLanguage.allCases, id: \.self) { item in Text(item == .system ? GUIText(key: "System language").render(language.language) : item.displayName).tag(item) }
        }
    }
}

struct ResourceStatusView: View {
    let external, busy, verified: Bool
    let count: Int?
    let message: String
    let notes: [String]
    @EnvironmentObject private var language: LanguagePreferences
    private func l(_ text: GUIText) -> String { text.render(language.language) }
    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(l(busy ? "Checking the selected files…" : verified ? (external ? "Resources verified for this App." : "The game files are inside this App; they are read only.") : "Resources need attention. Open the diagnostics below."))
                .font(.footnote).foregroundStyle(verified ? Color.green : Color.secondary)
            Text(l(DLCDiscoveryText.summary(external: external, busy: busy, verified: verified, count: count)))
                .font(.footnote)
            Text(l("This count is discovery only, not a runtime loaded count.")).font(.caption2).foregroundStyle(.secondary)
            if !notes.isEmpty && !busy {
                Text(l("Resource notices: \(notes.count). Open diagnostics.")).font(.caption).foregroundStyle(.orange)
            }
            DisclosureGroup(l("Resource diagnostics")) {
                ScrollView {
                    VStack(alignment: .leading, spacing: 4) {
                        Text(GUIText(key: message).render(language.language)).font(.caption)
                        ForEach(Array(notes.prefix(20).enumerated()), id: \.offset) { _, note in
                            Text(GUIText(key: note).render(language.language)).font(.caption)
                        }
                        if notes.count > 20 { Text(l("Showing the first 20 of \(notes.count) diagnostics.")).font(.caption2) }
                    }.frame(maxWidth: .infinity, alignment: .leading)
                }.frame(maxHeight: 160)
            }
        }
    }
}
