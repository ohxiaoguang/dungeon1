# Dungeon1 user guide

> This guide covers installation, resources and every setting. For the gestures themselves - what a tap, a swipe or a
> two-finger drag does in each input mode - see **[Controls](input-controls.md)**
> ([English](input-controls.en.md)).

## macOS

Open Dungeon1.app. In bundled mode the launcher identifies its included resources
and version; choose a writable storage folder, review settings and start. Keep the
App intact. Saves/logs/temp are under `Dungeon1-01008F1008DA6000` in that folder.
Errors stay in the launcher and the run log. The App is locally ad-hoc signed, not
notarized. No other project checkout is used at runtime.

Mouse HID and the Pointer Bridge default on and are one switch, **Experimental mouse
control**, in the everyday settings - not behind Advanced. A left click gives
touch/pointer ownership; physical mouse motion then drives hover/Tooltip. Controller input
keeps controller focus until the next click. Left click, dragging, wheel and gamepad
remain available. Turning the switch off clears both variables and restores the untouched
mouse and touch behaviour; a pair saved as two different values by an earlier build keeps
its own two switches under the merged one instead of being folded together.

**A two-finger trackpad swipe is the game's own touch drag.** The game reads no mouse, so
its torch and its lists only answer to a finger; the front end therefore opens one synthetic
contact at the mouse pointer and moves it with the swipe, which is exactly what a finger drag
does there - two fingers down pulls the torch down. The mouse itself does not move, no button
is pressed, and a left-button drag keeps the input to itself: the swipe stops while it is
held. The contact ends when the gesture ends, when nothing has arrived for 300 ms (a
phase-less device, or a stalled trackpad) or when the window loses focus; inertia is never
fed to the game, so lifting the fingers never keeps dragging. This applies to Dungeon1 only -
every other game's mouse and wheel behaviour is untouched.

**Settings are grouped.** Everyday: console mode, the mouse control above, then the
interface language. Everything else is inside one collapsed **Advanced** block - the
frame-rate counter, game rumble (with the strength underneath it, only while rumble is on),
the performance HUD and the experimental touch interaction policy - all off on a first
install. Click anywhere on the Advanced row (its title, the empty space or the chevron) to
open or close it.

The **game language** no longer has a row: the value the app was built with, or the one an
earlier version saved, is still kept and handed to the game. Change it with `DM_LANG` in
the app's `env.txt` if you need another language.

## iPhone and iPad

The IPA is unsigned. Use your own signing/install workflow, preserving required
capabilities and app identity; it cannot install directly. The application detects
its bundled data and retains the inherited resource import/error presentation,
controller preferences and storage controls. External mode asks for matching owned
containers and keys; keep those private. Data remains in this app's Documents.

**Input mode** is one choice in the launcher (Settings → Input mode), and the option that
belongs to the chosen mode sits directly under it:

- **Virtual gamepad** (the default, unchanged): the pad over the picture. Buttons, sticks,
  the layout button and the three layouts work exactly as before, and touches no control
  takes still reach the game. Its own option is **Disable touch input** (off by default):
  on, the game is sent no ordinary touch input while the pad, its layouts and a physical
  controller keep working.
- **Direct touch**: no pad; every touch is the game's own touch screen. Its own option is
  the **touch interaction policy** (off by default; see below), shown only here; changing the
  input mode turns it off so it cannot keep acting where it is not shown.
- **Virtual trackpad**: the whole screen is a trackpad, and its own option is the **pointer
  speed** (1.0× by default, 0.5×-2.0×): a gain on the pointer's travel only - it never moves
  where a tap clicks and never changes a gesture's classification.

  A finger that is only **down** publishes nothing at all, so pointing at an item and touching
  the glass again cannot pick it up by accident. **Swiping** moves the pointer and nothing else,
  and the pointer stays where the finger left it. A **quick tap** publishes one contact at the
  pointer - down and up in the same turn - which is the game's own Tap and therefore its click;
  two quick taps are its own double click. A finger held still for 0.5 s becomes the game's own
  hold: one contact is put down at the pointer (the arrow turns orange) and stays down, so after
  the game's own 0.5 s threshold its Press is reached - hold to buy, hold to toggle a skill.
  Moving cancels that contact instead of dragging with it, and a release before the threshold
  withdraws it instead of clicking. **Two fingers** are the game's own touch drag: as soon as
  they move, one contact opens at the pointer and follows them, which is what pulls the torch
  down and what scrolls a list - and it picks an item up if the pointer is on one. There is no
  pause to learn: both used to exist and produced the same contact, so there is now one path.

  The game's own UI draws no pointer for touch input, so the app draws one: a white arrow with
  a dark outline whose tip is exactly the coordinate the game clicks with (it follows the
  letterboxed 16:9 picture, rotation and a resized window). The arrow belongs to the
  launcher's overlay - it never takes part in hit testing and sends no input. Moving the
  pointer needs the same prepared 1.3.0 modules as the Mac bridge; the log says
  `DD pointer-only trackpad handoff: enabled` when it is in effect, and clicks keep working
  either way (a tap stores its own point, so the arrow and the click still agree).

  The small question mark beside **Input mode** opens the same instructions in the app, in the
  chosen language, with the other two modes a tap away.

**Changing the input mode resets the mode's own option.** Switching modes returns disable touch,
the touch policy and the pointer speed to their defaults, so an option the previous mode left
behind cannot keep acting in the new one. Opening the launcher, or re-selecting the mode already
set, changes nothing, and every value is still saved as usual.

A pair saved by an earlier version that is none of these three (no pad and no touch input)
is shown as **Kept from an earlier version** and left exactly as saved; choosing a mode
replaces it. The three modes are exclusive by construction - they are three values of the
same two variables - so no two of them ever run together. The right-stick detail is under
Advanced and is disabled while the gamepad is not the mode (its saved value is kept).

Everything else is inside the collapsed **Advanced** block, off on a first install: game
rumble (strength underneath, only while rumble is on), the frame-rate counter, the
performance HUD, touch feedback and the 3D right stick. **Game language** no longer has a
row - the built or saved value is still applied; `DM_LANG` in `env.txt` changes it.

With the touch policy on, short tap combat/camping skills to focus; hold to
request their native operation. Hold a town hero portrait about half a second and
lift for its details. Both Nomad and Comet shops use short tap for Tooltip and
price, hold at least 0.5 seconds then lift for **one** native purchase. In the guild,
a tap on a skill row only focuses it (name, price, description) and a 0.5 s hold buys it
once. The same policy now covers recognized blacksmith weapon/armour, camping trainer and building upgrade trees. The user has completed device acceptance of guild unlocks/upgrades and the added facilities. The game
still decides balance, stock and capacity. Moving beyond the slop, cancelling,
using multiple fingers or losing input ownership disarms the contact. Close the
shop and reopen it if its state changes while interacting.

The gamepad mode keeps every control the earlier build had; change layouts using the
inherited pad controls. External controllers retain their configuration and ownership
isolation, and they work in all three input modes (the trackpad only decides where the
pointer goes).

## Saves and migration

New identity `com.ohxiaoguang.dungeon1` is separate from the prior
`org.nxnative.01008f1008da6000` iOS app and `org.nxnative.dir.01008f1008da6000`
Mac app. They can coexist. No sandbox migration is automatic. A missing profile in
Dungeon1 does not mean the old save was deleted.

Quit both games. Export and back up the **whole** old `Documents/save` on iOS using
your existing file-sharing/backup workflow, then import into Dungeon1's
`Documents/save`. Keep the backup and old app until the new game loads it. On Mac,
copy the whole old `nxnative-01008F1008DA6000/save` into the new storage directory's
`Dungeon1-01008F1008DA6000/save`, preserving all profile and persist files. Never
merge partial binary persist files or hand-edit currency as part of migration.
Test saves and fixtures are private and excluded from source.

## DLC and MODs

Owned DLC must match this application; bundled builds validate the AOC manifest
and include the five locally prepared directories. In-game DLC entitlement/state
still determines availability. Do not copy DLC or modified saves into public Git.

On Mac choose the external MOD overlay folder in the launcher: `mods/romfs` or the
folder containing the individual MODs. On iOS retain the existing Documents MOD
resource workflow and full relative tree. The game selects/enables its local MODs;
restart after changing resources. Compatibility fixes for XML metadata and
`1099001958` trinket layout are code only; that MOD's resources and license are not
included. Test new MOD combinations on a backed-up save. No claim of universal
Workshop support or online service emulation is made.

## Troubleshooting

Check launcher errors and `log.txt`; preserve logs privately. Wrong resources,
Build IDs, stale rewritten modules and missing shaders require correct preparation.
Do not bypass validation. Confirm the experimental policy switch when a long press
uses the game's original behavior. See [compatibility](compatibility.md) for what
has actually been tested, including accepted standalone iPhone installation/start/coexistence and focused
remaining checks.

## About Dungeon1 / 关于 Dungeon1

Choose About Dungeon1 in launcher settings (关于 Dungeon1 in Chinese). Mac uses a
scrollable sheet; iPhone/iPad use a scrollable navigation sheet. The icon matches
the application source without another rounded mask. Version/build come from
installed metadata. Done / 完成 returns to the launcher without changing resource,
save or input settings. Choose English or 简体中文 in Interface language; the page
follows system appearance. GitHub, nxnative, license and DLC-detail links work.

The user confirmed standalone iPhone installation/start/coexistence for the prior
lantern build. The subsequently added About UI still needs physical phone/tablet
confirmation; compiling it is not that confirmation. No separate iPad report exists.
See [A–F evidence](compatibility.md). This is the Nintendo Switch 1.3.0 adaptation,
not a PC/Steam resource importer or official iOS release. Matching owned Switch
DLC must be prepared as described in [DLC support](dlc.md).
