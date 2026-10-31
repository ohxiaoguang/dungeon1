# About and official-icon validation — 2026-10-31

Scope: launcher presentation, documentation and icon packaging. Game profiles,
1.3.0 Build ID checks, FILTER/OBS gates, input logic, DLC/MOD loaders, Bundle ID
and save handling are unchanged. No shader translation or game rewriting ran.

## Builds and resource inspection

Both independent wrappers completed with matching private prepared inputs and
existing platform shader caches. New local outputs use a fresh private delivery
directory, not a previous accepted package. Neither product is published in Git.

| Check | Result |
| --- | --- |
| macOS Swift launcher + host/package | Passed; `Dungeon1.app`, arm64, ID `com.ohxiaoguang.dungeon1`, version 1.3.0 / build 1 |
| iOS/iPadOS Swift/Objective-C + IPA | Passed; same ID, version 1.3.0 / build 1.3.0, deployment 26.0, device families 1 and 2 |
| Shared About source integration | Mac shared-source glob and explicit iOS XcodeGen source; compiled on both targets |
| Mac icon | Generated `Dungeon1.icns`, valid `icns` header, 1,635,652 bytes, metadata selects Dungeon1 |
| iOS icons | Compiled Assets.car and iPhone/iPad AppIcon files; metadata selects AppIcon |
| About/launcher image | Both packaged project-icon.png files are byte-identical to the official source |
| IPA isolation | No Mac dylib, keys file, provisioning profile or code-signature folder |
| Signing | Mac ad-hoc; no Developer ID/notarization. IPA unsigned; user signing required |
| Packaging/platform regression | 28 tests passed, no failures |

Official source is an unchanged opaque 1024 × 1024 PNG, SHA-256
`f0e63900db55018238ff2fef2493c3b825364f7f3a4d7cb670b2b9cdb8725ca7`.
The default and custom --icon paths both feed the platform icon generation and
About resource; no private absolute source path or additional UI rounded mask.
Code review confirms the override remains accepted; no second custom-art build
was needed for this default-icon change.

## Actual Mac GUI checks

Computer Use opened the newly built application, not an older installed copy.
The Chinese settings entry opened the About sheet with the selected lantern,
metadata version/build, Nintendo Switch introduction, support limits, attribution
and working link controls. Full-size visual inspection showed normal wrapping;
long content scrolls to the complete disclaimer with Done remaining available.

Clicking Dungeon1 · GitHub opened Chrome at
https://github.com/ohxiaoguang/dungeon1 (browser address and window verified).
Done returned to the launcher with Play, embedded resource indication, storage
and input switches still present. Touch policy, Mouse HID and Pointer Bridge
retained their on values; game language/storage were not changed.

Changing the existing interface-language selector to English changed the entry,
About text and Done. The English sheet was visually inspected at full size and
scrolled; Done closed it successfully. Interface language was restored to its
original System language selection. Both introduction and license/DLC links have
real URL destinations; license/notices/DLC paths exist in the source tree.

Current visual inspection used system light appearance. Native SwiftUI semantic
colors and removal of a forced dark launcher scheme allow system appearance;
a separate dark-mode visual pass and every Dynamic Type size are not claimed.

## Device boundaries

The user has already confirmed standalone Dungeon1 installation, startup, use and
coexistence with the old app on iPhone. This is retained as level A in
[compatibility](compatibility.md), not relabelled as wholly untested.

The subsequent About-enabled IPA has compile, integration, resource and static
navigation/layout checks only. Its About page still needs physical iPhone and
separate iPad checks: small/large screen, large text, light/dark, language,
scrolling, links, Done and return to Play. Earlier game-interaction evidence is
preserved by source; this round did not repeat a full game playthrough.

## Public-source checks

Maintained documentation local links, Git whitespace differences, selected index
and every reachable local ref are checked before the normal main push. The image
allowlist is restricted to exact paths/hashes for the earlier geometric fallback
and this authorized lantern. All other binary restrictions remain in force.
Original seedds MIT and retained dependency notices are preserved. See
[release audit](public-release-audit.md) and [icon usage](../assets/app-icon/USAGE.md).

Recorded precommit result: 1,067 indexed files, 1,090 distinct path/blob pairs,
1,237 existing reachable objects, main and origin/main only, zero findings.
A focused allowlist check accepted the exact official PNG, rejected changed bytes
at its approved path and rejected identical bytes at an unapproved PNG path.
Maintained Markdown: 16 files, 67 local file links, zero missing destinations.
Whitespace diff and Mac deep/strict ad-hoc signature verification passed.
