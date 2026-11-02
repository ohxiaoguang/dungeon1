# Changelog

## Initial standalone version — 2026-10-31

- Import the Darkest Dungeon adaptation from maintainer commit
  `4ac9e7acc874428c808d468b51efab531933c72b`, retaining nxnative/seedds authorship.
- Keep one game profile and the inherited host, renderer, codecs, resource tools,
  DLC, saves and external MOD support.
- Preserve combat/camping holds, roster hold, ordinary/Comet shop native purchase
  policy, Mouse HID and pointer bridge with Build ID guards.
- Add Dungeon1 identity, original icon and independent Mac/iOS build wrappers.
- Separate public source/license material from private bundled App/IPA products;
  include bilingual documentation, provenance and release-audit tooling.
- At initialization, new-device acceptance was pending; the user confirmation
  below supersedes that historical status.

## Formal launcher and documentation update — 2026-10-31

- Record user-confirmed standalone iPhone installation, startup and coexistence;
  distinguish older interaction tests, Mac simulated input, GUI and automation.
- Clarify Nintendo Switch 1.3.0 inputs and all five DLC mappings/evidence limits.
- Publish the exact user-selected GPT lantern with project-use permission; default
  both platforms to it while retaining --icon.
- Add native shared English/Chinese About sheets, metadata version/build, working
  project/source/license links, scrolling and system appearance.
- Keep Bundle ID, version guards and all game input/DLC/MOD/save logic unchanged.
- The new About page's iPhone/iPad device UI remains a focused acceptance item.

## Independent build fixes — 2026-11-01

- Validate only the GL library each target packs (`shader/gl` for Mac, `shader/ios/gl`
  for iOS). A Mac-only preparation no longer fails on the absent iOS library, iOS-only
  no longer needs the Mac one, and a missing library for the target is still an error.
- Resolve DLC from `aoc/manifest.json` or the container bootstrap's `aoc-<digest>/`;
  Mac packaging previously reused the narrow `aoc` path and silently dropped all five
  owned packs. Ambiguous or manifest-less trees stop the build; base-only still builds.
- Add `scripts/tests/test_build_targets.py` (13 synthetic-preparation tests) covering
  per-target shader validation and DLC discovery/audit, including five indices and
  incomplete or unrelated trees.
- Record the verification this restores: Mac and iOS cold builds from the original
  containers each produced artifacts with five audited DLC indices; macOS was run to
  the title screen, iOS was built and statically checked without a device run.
- Ignore local build output (`out/`) so generated Apps, IPAs and caches stay untracked.

## One input choice, virtual trackpad, shorter launchers — 2026-11-02

- iPhone/iPad: the three touch switches stay three variables (`DM_TOUCH_INPUT`,
  `DM_TOUCH_CONTROLS`, `DM_RIGHT_STICK_VISIBLE`) and their readers are unchanged, but the
  launcher shows one **Input mode**: Virtual gamepad (default, the previous behaviour),
  Direct touch (the existing "no pad" combination) and Virtual trackpad. `DM_TOUCH_INPUT`
  gained the value `trackpad`; `0` and `1` keep the meaning the switch-only build gave them.
- Virtual trackpad: a full-screen relative cursor. Swiping moves only the pointer, a tap is
  the game's own Tap at the pointer (its click), lifting keeps the pointer, and holding the
  second press drags. A cancelled stroke cancels the contact instead of lifting it, so no
  click can arrive late. One finger, one published point - no button, no second contact.
- Why an extension: this build stores the pointer only on a Tap (`0x74c238`), which also
  clicks, so a swipe (Pan) could never hover. `dm_cursor_set` publishes a position-only
  cursor (no touch, no gesture, no Mouse HID), and the new iOS handoff
  (`dm/host/hle_dd_pointer_ios.c`, observation 22) writes the same two coordinates the Mac
  bridge writes, under the same build/gate and `mode == 0 && !controller` terms.
- macOS: Mouse HID and the Darkest Dungeon pointer bridge are one switch (both variables
  written together, each kept internally); a pair saved split keeps its own two switches.
  Performance HUD, the touch policy and the mouse experiment sit in one collapsed
  **Advanced** disclosure; rumble strength is the rumble switch's sub-setting; the FPS
  counter, console mode, game language and the storage/MOD folders keep their place.
- Chinese: every new string, plus the previously untranslated Mouse HID, pointer bridge and
  touch-policy names and notes, is in the shared catalog (one entry per string).
- A pair saved by an earlier version that no preset describes (the game's touch off with the
  pad on) is shown as kept and never rewritten; only choosing a mode replaces it.
- Tests: new `dm/ios/tests/test_trackpad_policy.py` (mode parsing, slop, delta totals),
  extended `scripts/tests/test_launcher_platform_settings.py` and
  `dm/apple/tests/LauncherSettingsChecks.swift` (mode mapping and round-trip, merged mouse
  switch, split pair). `compile_check.py` now type-checks the shared About page too.
- No game logic, shader, NSP, DLC, save, prepared module or Build ID guard changed; the
  launcher UI and the input paths above are the whole change. iOS IPA rebuilt.

### Input correctness audit of the trackpad (same day, before any release)

- The click point is the cursor, not the glass: the overlay builds its one published contact from the cursor
  (`publishTouch:`), and the finger's position only feeds the stroke delta; a source check keeps it that way.
  Driven through the real `hle_touch.c`, a tap after moving the cursor to A produces `Tap (A)` with the point list at
  A - also when the physical touch is far from A - and a tap after a stroke clicks at the new cursor.
- A stroke can no longer end in a click. The recognizer treats a contact as still until it has moved more than 8
  panel pixels **on either axis**, and a still contact's release is a Tap. The stroke's slop is now 9 panel pixels
  and is compared per axis (`DM_TRACKPAD_SLOP_PANEL`, `dm_trackpad_slop()`): at 8 the whole-pixel truncation of the
  published point could still publish exactly 8 (a click at the end of a tiny swipe), and a distance-based rule let a
  diagonal drift move the cursor while both axes stayed inside the slop. Both cases are covered by
  `dm/ios/tests/test_trackpad_policy.py`.
- No guest memory is written before the player's first input: the cursor is published on the first stroke (a first
  tap is the game's own Tap, which stores the point it clicked) instead of at launch.
- `dm/host/tests/t_trackpad.c` (25 checks, part of `make -C dm/host/tests run`) drives the publication sequence of
  the mode through the host's own touch layer: Tap at the cursor, no Tap during or after a stroke, the contact
  snapshot CANCELLED while moving (which is what disarms the title's hold policies), a 0.5 s still contact still
  PRESS, the shop's hold-tap release still the Tap it buys with, an explicit cancel never clicking, and the pointer
  handoff and the touch layer converting a position identically.
- Unchanged: `hle_touch.c`, `hle_dd_touch.c`, the Mac pointer bridge and every other input mode. Both artifacts were
  rebuilt from the audited sources; no device run yet (see the report's verification split).

### Visible pointer for the trackpad (after the iPad device test)

- The device report was "the trackpad works, but there is no pointer on screen": this build's UI draws no cursor for
  touch input, so the mode had nothing to follow the pointer with.
- The overlay now draws a classic arrow itself (`DmGamepad.m`: `arrowPath()` + `layoutArrow`, a `CAShapeLayer` on the
  view's own layer): white fill, dark outline, soft shadow, 12x19 points scaled by the pad's `u`. It appears only in
  the trackpad mode, follows a stroke live, keeps its place when the finger lifts, and is redrawn on every layout, so
  a letterboxed picture, a rotation, split view and a Stage Manager resize all follow. Being a layer, it takes no part
  in hit testing and produces no input event; it is not on `_controls`, so connecting a controller does not hide it.
- Its tip is the game's own pointer: `dm_trackpad_arrow_tip()` (TouchTrackpadPolicy.h) maps the panel coordinate the
  handoff publishes (`dm_panel_point` of the cursor, 1280x720) back into the picture rectangle, so the arrow cannot
  drift from the click - the normalized cursor would be up to one panel pixel off. `[self picture]` now floors the
  picture's origin exactly as `front_ios.m` lays the game out.
- Nothing else changed: the stroke, tap, hold and drag paths, `dm_cursor_set`, the bridge and every other input mode
  are the ones audited above. Tests: the arrow's panel-point round trip over three picture shapes and its corners,
  plus source checks that it exists only in trackpad mode, is a layer (never a subview), and follows strokes/layout.

## Launcher settings pass: one option per mode, shorter screens — 2026-11-02

- iOS/iPadOS: the input-mode row now shows the option that belongs to the chosen mode right under it and
  switches with it. Virtual gamepad → **Disable touch input** (off by default; the same `DM_TOUCH_INPUT`, so `0`
  keeps its old meaning and the pad, its layouts and a physical controller keep working). Direct touch → the
  **touch interaction policy** (`DM_DD_TOUCH_POLICY`, off by default, unchanged implementation: it is a shared
  switch that still governs the gamepad and trackpad modes, so its saved value keeps applying when the row is not
  shown). Virtual trackpad → **pointer speed** (`DM_TRACKPAD_SPEED`, new, 1.0×, 0.5×-2.0× in 0.1 steps, one key of
  its own): a gain on the cursor's travel only, applied as `gain * delta` with the stroke's slop divided by the
  same gain, so the first published movement still clears the recognizer's still radius at every speed (a slower
  pointer cannot turn a swipe into a click), and the tap path - which decides where a click lands - is untouched.
- iOS/iPadOS everyday area: console mode and the interface language; the game language no longer has a row (its
  saved or built value is still applied to the game; `env.txt` can change it). Everything else moved into one
  collapsed **Advanced** block: frame-rate counter, game rumble (strength underneath it, only while rumble is on),
  performance HUD, touch feedback and the 3D right stick - which is disabled while the gamepad is not the mode,
  with its value kept.
- macOS: **Mouse control** (the merged `DM_MOUSE_HID` + `DM_DD_MOUSE_POINTER`) moved into the everyday area, on by
  default; console mode and the interface language stay there; the split-pair compatibility rows still appear under
  it when the two variables disagree, and neither value is rewritten by opening the screen. Advanced now holds the
  frame-rate counter, game rumble (strength underneath), the performance HUD and the touch interaction policy.
- The **Advanced** header is one whole-row button now (`.buttonStyle(.plain)` over a `contentShape(Rectangle())`
  label, rows outside it), with its name, hint and expanded/collapsed value on the accessibility tree - no more
  aiming at the chevron, and no switch inside the row can be hit by that tap.
- First-install defaults (a saved value always wins, and `env.txt` still overrides everything): frame-rate counter,
  game rumble, touch feedback, performance HUD and the touch policy are off; pointer speed is 1.0×; the mouse
  control is on. The frame-rate default comes from the IPA build flag, which is off now too.
- Compatibility: `DM_TOUCH_INPUT` keeps `0` / `1` / `trackpad`; re-selecting a mode never clears its own option
  (`TouchInputMode.pair(keeping:)`); a saved pair of "gamepad with the touch screen off" is now the gamepad mode with
  that option on rather than a kept state, and only "no pad and no touch" still reports as **Kept from an earlier
  version**. No `launcher.<ENV>` key was removed and no stored value is rewritten by opening the launcher.
- Tests: `dm/apple/tests/LauncherSettingsChecks.swift` covers the new mapping, the mode-preserving pair, the
  common/advanced split (including the strength only under a switched-on rumble) and that nothing is drawn twice;
  `scripts/tests/test_launcher_platform_settings.py` covers the one-option-per-mode row, the whole-row Advanced
  header, the hidden game language and every new default; `dm/ios/tests/test_trackpad_policy.py` checks the pointer
  speed at five gains (the first published move still clears 8 panel px) and that the click path carries no gain.
- Unchanged: the input system, the trackpad's stroke/tap/hold/drag paths, the pointer bridge, `hle_touch.c` and
  `hle_dd_touch.c`. Both artifacts rebuilt from these sources.

## Trackpad: a touch no longer presses anything, two-finger drag, in-app instructions — 2026-11-02

- **The bug: touching the glass picked the item up.** The trackpad published one game contact the moment a finger
  went down, at the pointer, and moved it while the finger moved the pointer. The game turns a contact that starts on
  an item and then moves into a drag, so "hover a trinket, lift, touch again to keep moving" dragged the trinket. The
  same contact was also a live Press after 0.5 s, which is the title's hold (skill toggle, shop purchase, portrait
  details).
- **The fix is a gesture layer, not a tweak:** `dm/ios/Sources/TouchTrackpadPolicy.h` now owns what a touch means and
  the overlay only publishes what it is told to. A single finger that is merely down publishes **nothing** - no
  contact, no Press, no Tap, however long it rests. A quick still tap (inside the slop, released within 0.45 s)
  publishes one contact down-and-up in the same turn: the game's own Tap, one click at the pointer. Leaving the slop
  moves the pointer and publishes no contact; its release does nothing.
- **Two fingers** freeze the pointer and start a pause. Moving before 0.3 s is a scroll intent and stays inert;
  moving after it is a drag: the contact starts where the pointer is (not where the fingers are) and follows the
  pointer, the pointer turns orange while it carries, and lifting either finger ends the drag. A third finger cancels
  a drag instead of lifting it. A gesture can never change its mind, so a swipe cannot become a click and a drag
  cannot become a scroll.
- **Scrolling is not implemented, on purpose.** This game's `main` imports no mouse ABI at all (no `InitializeMouse`,
  `GetMouseState` or `GetMouseStates`; asserted by a test), so the Switch Mouse HID wheel is not a scroll channel for
  it, and its lists scroll through a raw touch drag - the very pickup this mode must not start by accident.
  `DM_TP_SCROLL` recognises the gesture and publishes nothing; the help sheet says so instead of promising it.
- **Native double tap is unchanged:** each tap is its own contact, and the recognizer's 0.35 s rule marks the second -
  verified against the real `hle_touch.c` (the second Tap carries the double-tap attribute).
- **Instructions in the launcher:** a small `questionmark.circle` button beside **Input mode** opens a sheet with the
  chosen mode's instructions (and the other two a tap away): pointer, tap, long press, two-finger drag, the current
  scroll limitation, plus the gamepad and direct-touch pages including what *Disable touch input* and the touch
  policy do. Bilingual, one catalog entry per sentence, switching with the interface language, and a sheet so the
  launcher does not grow.
- Tests: `dm/ios/tests/test_trackpad_policy.py` drives the state machine through C (tap, wobble, swipe, long press,
  two-finger scroll/drag separation, third finger, cancel, two taps, per-axis slop) and asserts the overlay publishes
  nothing on a down, a click only from the click path, and the mouse-import evidence above;
  `dm/host/tests/t_trackpad.c` (29 checks) drives the overlay's exact publication sequence through `hle_touch.c`:
  a tap is Touch then Tap at the pointer, a still finger produces no touch and no gesture at all, a drag is
  Touch/Pan/Complete with no Tap, a cancel is CANCEL, and a double tap still carries its attribute.
  `LauncherSettingsChecks` and `scripts/tests/test_launcher_platform_settings.py` cover the help sheet, its keys and
  the translations.
- Not changed: `hle_touch.c`, `hle_dd_touch.c`, the pointer bridge, `dm_cursor_set`, the gamepad and direct-touch
  paths, the pointer-speed gain's meaning, and every default or saved key from the previous round.
- **Known consequence:** with a long press deliberately inert, the shop's 0.5 s hold-to-buy cannot be reached from the
  trackpad mode. Use **Direct touch** for that until a deliberate two-finger hold is defined for it.

## Two-finger swipe on both platforms, bundled builds — 2026-11-02

- **iOS trackpad: the two-finger swipe now drags the game.** The state was recognised but published nothing, which is
  why the torch stopped working after single-finger touches were isolated. It now publishes exactly what a finger drag
  publishes - one contact at the pointer, moved by the two fingers' average delta - through the shared adapter
  (`dm/host/dm_swipe.h`), and lifts it on release. The pointer follows the contact, so the arrow, the game's pointer
  and the point a later tap clicks stay on one pixel. Swipe and pause-then-drag remain separate states that can never
  turn into each other, and a swipe can never click. Single-finger behaviour is untouched: a finger that is only down
  still publishes nothing.
- **macOS: a two-finger trackpad swipe becomes the same contact.** `front_mac.m`'s `scrollWheel:` still publishes the
  wheel to Mouse HID exactly as before, and additionally (Dungeon1 only, and only with the mouse switch on) turns the
  gesture into one synthetic contact at the mouse pointer that follows the swipe, from `DM_CONTACT_MAC_SWIPE`: a new
  source, so the title's left-button policies (roster hold) cannot fire from a scroll. The pointer does not move, no
  button is pressed, and a left-button drag ends the swipe instead of sharing it. Natural scrolling is honoured
  (`isDirectionInvertedFromDevice`), inertia (`momentumPhase`) is never fed to the game, and the contact ends on
  `NSEventPhaseEnded` - or, for a device that reports no phases, after `DM_SWIPE_IDLE_NS` (300 ms) of silence, which is
  under the title's 0.5 s Press promotion. Losing the window cancels the contact rather than lifting it.
- No second recogniser and no new gesture code in the game path: both ends feed `hle_touch.c`, which is unchanged.
- Tests: `dm/host/tests/t_swipe.c` (24 checks, in `make -C dm/host/tests run`) drives the Mac sequence through the real
  touch layer - Touch, Pan, Complete with no Tap, the swipe source not being the left button, a contact left open
  reaching PRESS while the adapter reports it idle, cancel, and a left click still working afterwards;
  `scripts/tests/test_mac_swipe_wiring.py` pins the front-end wiring (wheel still reaches Mouse HID, title gate,
  inertia, held button, focus loss, the timeout, and no pointer movement or button press);
  `dm/ios/tests/test_trackpad_policy.py` now covers the swipe's actions, its deltas and the two-way exclusion with the
  drag. The help sheet and the user guide say what the swipe does, in both languages.
- **Both artifacts are rebuilt in bundled/Directory resource mode**: the Mac App carries RomFS, Shaders, the patched
  modules and all DLC and needs no external container; the IPA carries the same and needs no Files import.

## Player-facing controls guide — 2026-11-02

`docs/input-controls.md` (and its English twin `docs/input-controls.en.md`) is now the place players look for the
gestures: it covers the three iPhone/iPad input modes, the Mac mouse and trackpad, every launcher setting with its
default, the known limitations and a FAQ. The READMEs link to it and `docs/user-guide.md` points at it for gestures
(the guide keeps installation and the full setting reference).

Summary of what this round changed, in the order a player meets it:

- **Trackpad input isolation:** a single finger that is only down sends the game nothing, so re-touching the glass to
  keep moving the pointer can no longer pick an item up; a tap is one click at the pointer and a long press is inert.
- **Two-finger swipe and drag:** a swipe publishes the game's own touch drag (torch, lists) and a pause first then a
  move is the deliberate drag of the item under the pointer. Both drag an item when the pointer is on one - that is the
  game's own behaviour - and the app never turns one gesture into the other.
- **Mac trackpad:** a two-finger scroll becomes the same native touch drag at the mouse pointer, without moving the
  pointer, pressing a button or disturbing the existing click / press-drag / hover paths.
- **Launcher help:** the question mark beside Input mode opens a bilingual, per-mode guide inside the app.
- **Automatic tests:** `t_trackpad.c` (29 checks) and `t_swipe.c` (24) drive the real touch layer in
  `make -C dm/host/tests run`; `test_mac_swipe_wiring.py`, `test_trackpad_policy.py`, the launcher setting checks and
  the launcher semantics tests cover the rest.
- **Bundled builds verified:** both delivery artifacts were rebuilt in Directory/bundled resource mode and checked -
  the Mac App carries RomFS, Shaders, the patched modules and all five DLC and boots into the game; the IPA carries
  the same behind `DMResourceBackend=directory` and needs no file import.
