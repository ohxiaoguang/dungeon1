# Source origin and independent history

Dungeon1 imports the maintainer development snapshot
`4ac9e7acc874428c808d468b51efab531933c72b` from
[ohxiaoguang/nxnative-zzg](https://github.com/ohxiaoguang/nxnative-zzg).
That source builds on [seedds/nxnative](https://github.com/seedds/nxnative).
The snapshot is a maintainer commit, not an asserted official upstream import SHA.
Root LICENSE retains the original MIT grant and seedds copyright.

Native execution, kernel/service emulation, host rewriting, graphics, multimedia
and tool foundations are inherited. Darkest Dungeon GL work, MOD compatibility,
pointer/Mouse HID and touch-policy adaptations were developed in the maintainer
line. The Comet commit adds the distinct verified purchase callable. Independent
Git history does not make these components original Dungeon1 work.

Dungeon1 adds single-game registration/build entry points, a dedicated app identity,
the initial geometric fallback, default settings, docs and public-file audit. Other profiles,
product docs and game-memory frame-limit writes were omitted. Shared HLE, codecs,
GL/NVN/Vulkan infrastructure, containers, rewriting, fonts generator and shader
translation tools remain where needed by the build graph. SDK registry now contains
only the two SDK builds of this game; neither requires SDK cuts.

Touchline 23 and Touchline 27 were architecture/license references. Their code is
not required on disk to build. License/provenance material was copied from the
Touchline 23 audited snapshot and checked against this file set: 61 binary and
364 source/configuration entries match exactly; see
[comparison](translator-comparison.json) and the
[translator record](../dm/third_party/translator-runtime/README.md).
Original license files are retained. Historical producer objects need not be in
this new Git history; a bit-reproducible historical build is not claimed.

Darkest Dungeon offsets and expected instruction words are compatibility metadata;
no original executables, game UI art/fonts, textures, screenshots, save files or
MOD resources are part of the source snapshot. Private bundled products have a
separate distribution boundary and must never be uploaded with this source.

The 364 source/config/license manifest entries were additionally read directly
from producer commit `674c2e141cf87917271858c455657aa8637f22d0` in the maintainer
repository and independently hashed: zero mismatches. See
[producer verification](producer-verification.json). No producer Git objects were
imported into Dungeon1 history.

The formal default lantern is a user-selected GPT-generated image, explicitly
authorized for public Dungeon1 use. [Icon usage](../assets/app-icon/USAGE.md) records
its exact hash, scope and terms review. The shared bilingual About is presentation
code inspired by the reference's sheet pattern, without FIFA branding/content.
