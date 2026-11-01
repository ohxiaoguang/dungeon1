# Building Dungeon1

Use the scripts in this checkout; neither the former nxnative checkout nor either
Touchline project is a build dependency. They were source references only.

## Environment

Apple silicon, macOS 26+, Xcode/command-line tools and Metal toolchain, XcodeGen,
.NET 10, SPIRV-Cross and glslang are required. Python 3.12+ is recommended for the
inherited modern Python syntax. Install capstone, lz4 and fonttools into an isolated
Python environment; unicorn enables actual ARM64 execution tests. Some legacy
resource tools also use backports.zstd. External tools are not downloaded by the
prepared-assets wrapper. NuGet restore can occur during container bootstrap.

```sh
python3 -m venv /private/tools/venv
/private/tools/venv/bin/python -m pip install capstone lz4 fonttools unicorn backports.zstd
export PYTHON=/private/tools/venv/bin/python
```

Keep TMPDIR, build work and compiler caches on a volume with adequate space. The
wrapper directs its caches into `--work`. `--font-python` may select another
interpreter containing fonttools. Do not put private keys or game inputs in Git.

## From privately supplied containers

Supply the base, update 1.3.0 and optional owned DLC in one folder. Pass the private
keys file with `--keys`. The independent entry points fix the game, package, name,
Bundle ID and original project icon; no other title is surveyed or registered.

```sh
./scripts/build-mac.sh --nsp-dir /private/game --keys /private/prod.keys \
  --work /private/work-mac --out /private/Dungeon1.app
./scripts/build-ios.sh --nsp-dir /private/game --keys /private/prod.keys \
  --work /private/work-ios --out /private/Dungeon1.ipa
```

The underlying inherited container pipeline prepares under `<work>/prepared`,
checks/extracts game inputs, rewrites programs, translates GL shaders for each
platform, then builds the host and packages directory mode. The package default
is v393216. Do not use the low-level generic tools to imply support for other games.

## Reusing prepared inputs

A preparation root contains `extract/v0/`, `extract/v393216/`,
`patched_v393216/`, `shader/gl/`, `shader/ios/gl/` and optional DLC at
`aoc/manifest.json` or, as the container bootstrap writes it, `aoc-<digest>/manifest.json`.
All rewriter inputs in `build_src.sha256` must match retained sources; modules
must have registered 1.3.0 Build IDs and required FILTER/OBS gates. Each wrapper
checks only the library it packs against `gl_capture.tsv`: Mac packages
`shader/gl`, iOS packages `shader/ios/gl` (a Mac-only preparation stays valid for
Mac, an iOS-only one for iOS), while a preparation carrying both is accepted by
both. A missing library for the target is still a hard error. Foreign game stamp
entries are ignored only when their profiles were removed; no retained source
mismatch is ignored.

```sh
./scripts/build-mac.sh --prepared /private/prepared \
  --work /private/work-mac --out /private/Dungeon1.app
./scripts/build-ios.sh --prepared /private/prepared \
  --work /private/work-ios --out /private/Dungeon1.ipa
```

A source-stamp mismatch requires rewriting from the original ExeFS, not editing the
stamp. Keep a separate private prepared root for Dungeon1. The standalone split
reprepared all three modules; Mac and iOS GL caches were reused after coverage
validation. The NVN translator and shared graphics infrastructure remain available
as build dependencies, but this game actually renders through GL, not NVN.

Each wrapper builds one platform on its own from the same containers: `--target mac`
and `--target ios` share no platform-specific shader product, and neither needs the
other to have run. A preparation without DLC still builds the base game; when DLC is
present, the tree is resolved (either layout), audited file by file against its
manifest and then packaged. An ambiguous pair of trees, a tree without `manifest.json`
or an incomplete tree stops the build instead of producing a DLC-less artifact. The
Mac App's `Contents/Resources/aoc` and the IPA's `Payload/DmIOS.app/aoc` hold the same
audited indices. The IPA is built and statically checked here; no iPhone/iPad device
run is performed by the build.

Prepared mode also accepts `--resource-backend nsp` for external runtime resources.
That mode still embeds rewritten modules/derived shaders and is not a public binary
distribution clearance. Bootstrap defaults to bundled directory mode. The Mac App
asks for external input files in NSP mode; directory mode needs only writable storage.

The output path must not already exist. Use a fresh work path for each iOS project
(the inherited builder refuses to replace an existing generated project). Local Mac
artifacts are ad-hoc signed; the IPA is unsigned, never signed or installed here.
No game containers or keys are placed in bundled artifacts.

## Tests and common failures

```sh
make -C dm/host/tests GAME=01008F1008DA6000 run
$PYTHON -m unittest discover -s dm/tools/tests -v
$PYTHON -m unittest discover -s scripts/tests -v
$PYTHON scripts/check_public.py
```

`scripts/tests/test_build_targets.py` covers the two build-wrapper regressions with
synthetic preparations: per-target shader validation (Mac-only, iOS-only, both, and a
missing library) and DLC discovery (`aoc/`, `aoc-<digest>/`, five indices, base-only,
ambiguous, manifest-less and incomplete trees). It needs no game container, rewritten
module or shader compilation.

Audio/HID tests need access to macOS services; restricted execution can abort at
AudioUnit setup. Missing capstone/lz4/fonttools is an environment error. A missing
DLC manifest is resolved by preparing/validating owned DLC, not disabling the audit.
Wrong Build IDs and missing gates are hard errors. Rebuild shaders only when their
sources/targets or translation inputs have changed. Do not substitute a Mac metallib
for the iPhone library. Restore tools from their recorded sources with original
licenses; never replace the locked translator merely to tidy the repository.

## Official icon and shared About

Both wrappers default to committed `assets/app-icon/dungeon1-lantern.png`, an opaque
1024 × 1024 PNG. No private icon path is needed after cloning. --icon remains a
local override. Mac ICNS and iOS AppIcon use the same selected source; an unchanged
project-icon.png is bundled for launcher/About (Mac Resources root; iOS dm/). No
extra rounded mask is applied. See [image usage](../assets/app-icon/USAGE.md).

`dm/apple/AboutDungeon1.swift` is compiled by the Mac shared-source glob and iOS
XcodeGen list. It reads metadata version/build and only changes sheet state. This
UI/docs update requires no shader translation or game-module rewriting. Deployment
targets stay macOS/iOS 26.0; current local Xcode does not prove all older toolchains.

Inputs must be Switch base plus matching 1.3.0 update. v0 is read for union shader
coverage, not another accepted runtime. Exact Build IDs remain unchanged. See
[compatibility](compatibility.md) and [DLC CNMT mapping](dlc.md).
