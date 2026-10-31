# Dungeon1

[中文说明](README.zh-CN.md)

Dungeon1 is an independently maintained, single-game Apple silicon macOS / iOS /
iPadOS runtime for **Darkest Dungeon 1.3.0** (Switch title `01008F1008DA6000`,
update v393216). It builds on [seedds/nxnative](https://github.com/seedds/nxnative):
the game's ARM64 code runs natively after host-kernel compatibility rewriting;
its desktop OpenGL calls are implemented on Metal. This is an unofficial community
project, unaffiliated with Red Hook Studios, Nintendo or Apple.

## Features

- A single-game Dungeon1 launcher, stable identity `com.ohxiaoguang.dungeon1`,
  resource/version checks, configurable storage and diagnostic errors.
- iPhone touch controls and virtual gamepad, separate controller ownership,
  combat/camping skill holds and town-roster long press.
- Both Nomad Wagon pages: short tap focuses and shows the tooltip; hold about
  0.5 seconds then lift to request one native purchase. Comet keeps its own shard
  purchase callback and the game's balance/capacity checks.
- Mac Mouse HID and Darkest Dungeon pointer bridge; mouse hover, click, drag,
  wheel and controller input. Both switches default on in Dungeon1.
- Save data, five local DLC inputs and external MOD overlays, including inherited
  compatibility fixes for MOD `1099001958`. No MOD assets are included.
- Bundled-directory and external-container runtime infrastructure. Private bundled
  builds include your prepared game data; public Git contains source only.

The experimental touch policy defaults **on** and remains switchable. Main and SDK
Build IDs and prepared gates are checked; 1.3.0 address hooks never apply to unknown
versions. Base-game identifiers remain only for preparing the union shader library;
the supported product baseline is 1.3.0.

## Build and play

Use an Apple silicon Mac, macOS 26+, Xcode with Metal tools, XcodeGen, Python 3.12+
with capstone/lz4/fonttools, .NET 10 and the shader tools described in
[building](docs/building.md). Supply your own lawful game dump and private keys.
Neither is downloaded or supplied by this project.

```sh
./scripts/build-mac.sh --nsp-dir /private/game --keys /private/prod.keys \
  --work /private/build-mac --out /private/Dungeon1.app
./scripts/build-ios.sh --nsp-dir /private/game --keys /private/prod.keys \
  --work /private/build-ios --out /private/Dungeon1.ipa
```

Previously prepared modules and both GL libraries can be reused with `--prepared`;
the wrapper verifies module Build IDs, source stamps and all required input gates.
See the [user guide](docs/user-guide.md) for storage, MODs and manual save import.
The IPA is **unsigned**: sign it with your own installation workflow. The Mac App
has local ad-hoc signing, without Developer ID signing or notarization.

## Validation and limits

[Compatibility](docs/compatibility.md) distinguishes inherited evidence, the new
independent build's tests and outstanding device acceptance. Previous iPhone user
acceptance covers the ordinary shop and earlier controls. Comet purchasing has
Mac-host iPhone-source evidence; **new Dungeon1 IPA iPhone acceptance is pending**.
Second-finger/close-while-held lifecycle cases have unit-test coverage and still
need device acceptance. No blanket claim of full-game completion is made.

## Source, licenses and distribution

[UPSTREAM](docs/UPSTREAM.md) records the exact import commit and independent-history
boundary. Preserve [LICENSE](LICENSE) (MIT, seedds) and all
[third-party notices](THIRD_PARTY_NOTICES.md). They do not license game assets.
Read the [public release audit](docs/public-release-audit.md) before publishing.
Never publish bundled App/IPA products, extracted code, RomFS/DLC, game shaders,
fonts, keys, saves or third-party MOD resources in Git, Releases or CI artifacts.
The project icon is original geometric artwork with its own retained source.

Local acceptance artifacts use a maintainer-supplied lantern image via `--icon`.
The two supplied PNGs remain private inputs; their redistribution license was not
provided. Public source keeps the original geometric fallback artwork/generator.
Passing `--icon /private/icon.png` applies the selected image to both Mac and iOS.
