# Dungeon1

[简体中文](README.zh-CN.md)

Dungeon1 is an independently maintained **unofficial port adaptation based on
[seedds/nxnative](https://github.com/seedds/nxnative)** for running the **Nintendo
Switch version of Darkest Dungeon** on Apple silicon Mac, iPhone and iPad.
It supports this one game; PC/Steam files are not inputs to this pipeline.
This community project is not an official Red Hook Studios, Nintendo or Apple product.

| Item | Supported baseline |
| --- | --- |
| Game / source platform | Darkest Dungeon / Nintendo Switch |
| Adapted version / update | **1.3.0 / v393216** |
| Title ID | `01008F1008DA6000` |
| Targets | Apple silicon macOS / iOS / iPadOS, deployment targets 26.0 |
| App identity | `com.ohxiaoguang.dungeon1`, separate from the older app |

## Features

The inherited host rewrites kernel-incompatible ARM64 operations and implements
this game's OpenGL on Metal. Dungeon1 provides a single-game launcher, saves,
external MODs, Mac Mouse HID / Pointer Bridge Hover, and three iPhone/iPad input
modes: **virtual gamepad**, **direct touch** and a **virtual trackpad** with its own
pointer. A two-finger swipe - on the iPad glass or on a MacBook trackpad - becomes
the game's own touch drag, which is what the lists and the torch answer to. The
experimental touch policy is off by default (iPhone/iPad launcher → Direct touch): combat/camping
holds, town-roster long press, and tap-to-inspect / hold-and-release purchases
in both wagon pages, guild skills (initial unlock and upgrades), blacksmith weapon/armour,
camping trainer and building upgrade trees. These upgrade interactions and the revised
trackpad gestures/mode-switch resets have user device acceptance. Balance, level requirements
and other purchase conditions remain the game's decisions. The proposed dungeon hero-status
overlay is not implemented; see the [feasibility assessment](docs/darkest-dungeon-hero-status-audit.md).

**Playing it:** see **[Controls](docs/input-controls.en.md)** ([简体中文](docs/input-controls.md))
for every gesture, what each launcher setting does, and the known limitations.

The official **lantern icon** is included and is the default on both platforms.
Settings include **About Dungeon1**, with that icon, metadata version/build,
bilingual support information, system appearance and real source/license links.
[Icon source and authorization](assets/app-icon/USAGE.md) are separate from code MIT.

## DLC support

| DLC | Internal identifier | Resource / mount |
| --- | --- | --- |
| The Crimson Court | `crimson_court` | `aoc/1` / `dlc0:` |
| The Shieldbreaker | `shieldbreaker` | `aoc/2` / `dlc1:` |
| The Musketeer | `musketeer` | `aoc/3` / `dlc2:` |
| The Color of Madness | `color_of_madness` | `aoc/4` / `dlc3:` |
| The Fire's Edge | `fires_edge` | `aoc/5` / `dlc4:` |

All five local packs were recognized/mounted on Mac. The Color of Madness shop has
real Shards debit/inventory/refusal evidence with simulated iPhone input on Mac.
**Mounting is not full DLC campaign/gameplay acceptance.** See
[DLC mapping and evidence](docs/dlc.md) for activation, versions and limits.

## Resources, build and installation

Supply your own Switch base game, matching **1.3.0 update**, optional owned DLC and
local `prod.keys`. The repository downloads/provides none of them. Base v0 helps
prepare union shader coverage; it is not another fully accepted product runtime.
Preparation checks registered program Build IDs. PC/Steam assets cannot substitute.

Use Apple silicon, macOS 26+, Xcode with Metal tools, XcodeGen, Python 3.12+ with
capstone/lz4/fonttools, .NET 10 and the shader tools in [building](docs/building.md):

```sh
./scripts/build-mac.sh --nsp-dir /private/game --keys /private/prod.keys \
  --work /private/work-mac --out /private/Dungeon1.app
./scripts/build-ios.sh --nsp-dir /private/game --keys /private/prod.keys \
  --work /private/work-ios --out /private/Dungeon1.ipa
```

Use `--prepared` to reuse validated modules/platform shaders. Bundled mode includes
your prepared resources in a **private local** App/IPA. External mode keeps
containers/keys on selected storage; see the guide for its DLC/preparation limits.
Each wrapper builds its own platform alone from the same containers: Mac packages
`shader/gl` and iOS packages `shader/ios/gl`, so neither needs the other platform's
library to have been built. Owned DLC in the preparation is audited and packaged on
both platforms; a base-only preparation builds without it.
Neither the former repository nor Touchline folders are build dependencies.
The IPA is unsigned: sign/install it yourself. Local Mac builds are ad-hoc signed,
without Developer ID signing/notarization. The [user guide](docs/user-guide.md)
explains controls, About, storage and manual save import.

## Verified status

The user confirms the **standalone Dungeon1 IPA installs and starts on iPhone**,
and coexists with the old app without replacing it. Earlier iPhone skill/shop/
roster acceptance belongs to the older adaptation. Independent Mac GUI/mouse,
Mac simulated-iPhone transaction and automated results are separate evidence.
Not every feature has been reaccepted on the new IPA. The **new About page's
physical iPhone/iPad UI** still needs confirmation. Complete DLC campaigns, all
MOD combinations, long sessions and every lifecycle/multitouch edge are not claimed.
See the [A–F acceptance matrix](docs/compatibility.md).

## Source and licenses

[UPSTREAM](docs/UPSTREAM.md) records exact lineage and independent-history limits.
Keep [LICENSE](LICENSE) (MIT, seedds) and [third-party notices](THIRD_PARTY_NOTICES.md);
components retain their own terms. [AI icon permission](assets/app-icon/USAGE.md)
is separate. No rights to game/update/DLC/firmware/keys are granted. Do not publish
bundled products, extracted code, RomFS, game-derived shaders/fonts, keys, saves,
game screenshots or original MOD resources. See [public audit](docs/public-release-audit.md).
