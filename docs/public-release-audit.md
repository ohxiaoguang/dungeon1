# Public source release audit

Date: 2026-10-31 (Asia/Shanghai). Scope: Dungeon1 source and new independent Git
history, not permission to redistribute any bundled game product. This is a
file/provenance review, not a general legal warranty.

## Import and history boundary

The source snapshot is maintainer commit `4ac9e7acc874428c808d468b51efab531933c72b`.
The destination was empty and the remote had no advertised refs. Files were read
from that committed tree, selected by path, and copied without `.git`, build
outputs or untracked research. New Git initialization uses main and a single new
root commit. No original history is imported or rewritten. The old project keeps
its own remote; the new origin is only ohxiaoguang/dungeon1.

## Source selection

Only `dm/games/01008F1008DA6000` remains. Other 59 game profiles, their cuts,
launcher entries, old multi-game product docs/screenshots, FIFA-specific scripts
and game-memory frame-limit tables are omitted. SDK cuts belonging only to other
titles are removed; two explicit SDK registry records for this game have no cuts.
Generic service/graphics/container/codec/rewriter facilities remain dependencies,
not registrations or support claims for other titles. Synthetic fixtures may name
fake IDs to test generic parsing and do not contain proprietary game programs.

The public tree contains compatibility offsets/expected instruction words,
source-authored logic and hash/capture metadata. No game program, RomFS, DLC,
derived shader library/source, game artwork, font, save, screenshot, key or original
MOD resource is intentionally selected. The initial icon was AppKit-generated geometry; the current default is the
explicitly authorized GPT lantern PNG (reviewed below). Historical touch/DLC markdown is labelled as inherited
evidence, not new-package acceptance. Private machine paths in those records are
historical context, not build dependencies.

## Licenses and tool provenance

Root MIT and seedds attribution are unchanged. Original libvpx LICENSE/PATENTS/
AUTHORS, stb, Ryujinx, Spv.Generator/Khronos, MacNativeGames, deko3d, Vulkan-Headers,
FLIP, NVN declaration notices and zstd BSD material remain. Third-party software
is not collectively relicensed MIT; MsgPack.Cli retains Apache-2.0.

The 61 locked translator binaries and 364 corresponding source/config/license
files were hashed against Touchline 23's audited manifests, all equal. Original
package licenses/notices/nuspecs and historical producer/source evidence are
retained in `dm/third_party/translator-runtime`. No binary was replaced.
Historical compiler invocation and bit-reproducible historical output are not
claimed. See [source origin](UPSTREAM.md), [comparison](translator-comparison.json)
and [third-party notices](../THIRD_PARTY_NOTICES.md).

## Scanning and release boundary

`scripts/check_public.py` inspects the index plus every blob reachable from all
local refs. It checks paths, container/program signatures, common key/token
patterns, size, non-regular files, the one-profile rule, required notices and
binary allowlisting against exact hashes. Artwork is allowed only at the exact path/hash pairs for the geometric
fallback and the separately authorized lantern. The scanner is an additional control, not a
proof that no conceivable secret or rights issue exists. Manual selection and
license inspection remain part of the review.

Private bundled Mac/IPA products embed user-supplied rewritten game programs,
RomFS/DLC, derived shaders and font stand-ins. They stay outside this repository;
no Release or public CI artifact is created. Keys are build-time private inputs
and are not embedded. Source publication does not authorize binary distribution.

## Execution record

Final index/history scan, test results, object/ref counts and commit/push evidence
are recorded below after the commands complete. No unresolved critical binary
origin or missing-license blocker has been identified in the selected source set.
Actual device validation and full-game/MOD coverage remain limited as described
in [compatibility](compatibility.md).


## Recorded review results

The source selection and all reachable-ref audit initially checked 1,060 indexed
files with zero findings and no refs/commits. Subsequent documentation, fixture
and license additions were restaged and scanned again before the root commit.
The 364 translator source entries were also independently checked directly
against fixed producer Git objects with zero mismatches. Required original
Vulkan MIT text was added after link review found that the inherited overview
linked to a missing full-license file. No locked translator was rebuilt.

The initial review withheld the lantern until explicit public-use authorization.
That temporary restriction is superseded by the review below.
All private game products/test saves/logs/screenshots remain outside the checkout.

Final precommit index audit: **1,062 files**, zero findings, no existing refs or
reachable history. `git diff --cached --check` passes; vendored upstream whitespace
is deliberately exempted rather than modifying source/provenance hashes. New
maintained documentation local links were checked; historical code expressions
inside markdown tables are not treated as file links. No public CI or binary
release is configured. Final history is rechecked after the root commit and
before the normal main push.

The independent root commit is `7545d55c5230c8759b34a6e2c44084caea5e0c5e`.
Its postcommit scan checked 1,062 indexed files and 1,232 reachable Git objects,
with only refs/heads/main and zero findings. No old repository history is present.
The initial main push completed normally after retrying an HTTP 400 transport
failure with HTTP/1.1 and a per-command post buffer (no force push). A subsequent
documentation-only commit records the final MOD management test; it does not
change the application binaries or import additional source/content.

## Formal lantern / About review — 2026-10-31

The user expressly authorized public GitHub inclusion/use of the exact selected
1024 × 1024 GPT-generated lantern, now assets/app-icon/dungeon1-lantern.png.
SHA-256: f0e63900db55018238ff2fef2493c3b825364f7f3a4d7cb670b2b9cdb8725ca7.
No redraw/recrop was made. GPT was confirmed; exact model/account/plan were not
supplied. [OpenAI terms](https://openai.com/policies/terms-of-use/) were reviewed;
[USAGE](../assets/app-icon/USAGE.md) records provenance, user permission and limits.
No blanket image MIT license, hand-drawing or trademark/exclusive-output claim
is made. The root seedds MIT and third-party licenses stay unchanged.

.gitignore allows only the two named project PNGs, and the scanner requires exact
path/hash matches; unknown/modified PNGs still fail. About/launcher and Mac/iOS
icons derive from the same source, with --icon overrides supported. No private
absolute icon path is required. About is presentation-only; resource scanning,
Bundle ID, version gates, persisted settings and game controls remain separate.
The user's prior standalone installation/start/coexistence report does not accept
the new About UI on a device. Compilation/UI/links and final index/all-refs audit
results are in [About validation](about-validation.md). No game resource, private
key/save, runtime screenshot/cache or bundled application is added to public Git.

Formal-update precommit scan: 1,067 selected index files, 1,090 unique path/blob
pairs and 1,237 existing reachable objects; only main/origin-main refs and zero
findings. The two rejected-image negative checks confirm the whitelist was not
broadened to arbitrary artwork. All newly added binary content is the exact
reviewed lantern PNG. Git whitespace and maintained local Markdown links passed.
The incorrect inherited FIFA 23 attribution sentence was corrected to describe
Darkest Dungeon work and distinguish Touchline engineering references; no genuine
upstream author/license notice was removed. No unresolved critical publication
blocker was identified within this source-review scope.
