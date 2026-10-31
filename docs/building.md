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
`patched_v393216/`, `shader/gl/`, `shader/ios/gl/` and optional `aoc/manifest.json`.
All rewriter inputs in `build_src.sha256` must match retained sources; modules
must have registered 1.3.0 Build IDs and required FILTER/OBS gates. Both GL libraries
are checked against `gl_capture.tsv`. Foreign game stamp entries are ignored only
when their profiles were removed; no retained source mismatch is ignored.

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
$PYTHON scripts/check_public.py
```

Audio/HID tests need access to macOS services; restricted execution can abort at
AudioUnit setup. Missing capstone/lz4/fonttools is an environment error. A missing
DLC manifest is resolved by preparing/validating owned DLC, not disabling the audit.
Wrong Build IDs and missing gates are hard errors. Rebuild shaders only when their
sources/targets or translation inputs have changed. Do not substitute a Mac metallib
for the iPhone library. Restore tools from their recorded sources with original
licenses; never replace the locked translator merely to tidy the repository.

Local acceptance artifacts use a maintainer-supplied lantern image via `--icon`.
The two supplied PNGs remain private inputs; their redistribution license was not
provided. Public source keeps the original geometric fallback artwork/generator.
Passing `--icon /private/icon.png` applies the selected image to both Mac and iOS.
