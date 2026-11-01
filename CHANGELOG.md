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
