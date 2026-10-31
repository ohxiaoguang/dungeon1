# Dungeon1 user guide

## macOS

Open Dungeon1.app. In bundled mode the launcher identifies its included resources
and version; choose a writable storage folder, review settings and start. Keep the
App intact. Saves/logs/temp are under `Dungeon1-01008F1008DA6000` in that folder.
Errors stay in the launcher and the run log. The App is locally ad-hoc signed, not
notarized. No other project checkout is used at runtime.

Mouse HID and Pointer Bridge default on. A left click gives touch/pointer ownership;
physical mouse motion then drives hover/Tooltip. Controller input keeps controller
focus until the next click. Left click, dragging, wheel and gamepad remain available.
The experimental town-roster hold is enabled with the touch policy.

## iPhone and iPad

The IPA is unsigned. Use your own signing/install workflow, preserving required
capabilities and app identity; it cannot install directly. The application detects
its bundled data and retains the inherited resource import/error presentation,
controller preferences and storage controls. External mode asks for matching owned
containers and keys; keep those private. Data remains in this app's Documents.

The touch policy defaults on. Short tap combat/camping skills to focus; hold to
request their native operation. Hold a town hero portrait about half a second and
lift for its details. Both Nomad and Comet shops use short tap for Tooltip and
price, hold at least 0.5 seconds then lift for **one** native purchase. The game
still decides balance, stock and capacity. Moving beyond the slop, cancelling,
using multiple fingers or losing input ownership disarms the contact. Close the
shop and reopen it if its state changes while interacting.

The virtual controller remains available; its touchscreen-input switch and overlay
visibility switch are separate. Change layouts using the inherited pad controls.
External controllers retain their configuration and ownership isolation.

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
has actually been tested, including the pending new-IPA device checklist.
