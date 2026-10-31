# Third-party notices

Dungeon1 builds on [nxnative](https://github.com/seedds/nxnative) and retains
its original seedds MIT notice in [LICENSE](LICENSE). Kernel/service emulation,
NVN/Metal, translation and rewriting retain their original authorship. FIFA 23
adaptations, resource integration and packaging also include work developed by
the maintainer on that engine and now maintained in this independent project;
these additions are not all credited to the original official upstream.
[UPSTREAM.md](docs/UPSTREAM.md) records the accurate inheritance and evidence limits.
The root MIT grant does not replace other components' terms or grant rights to
game content, keys, firmware or third-party assets.

## Retained source

| Component | Original license and attribution | Notes |
| --- | --- | --- |
| nxnative | [MIT, seedds](LICENSE) and original source author notices | Engine and tools; snapshot lineage retained |
| libvpx | [BSD 3-Clause](dm/third_party/libvpx/LICENSE), [PATENTS](dm/third_party/libvpx/PATENTS), [AUTHORS](dm/third_party/libvpx/AUTHORS) | Recorded v1.17.0 VP9 subset |
| stb_vorbis | [MIT or public domain](dm/third_party/stb_vorbis/LICENSE) and source-end notice | Recorded 1.22 with inherited multichannel residue fix, described in its README |
| Ryujinx | [MIT, Ryujinx Team and Contributors](dm/third_party/ryujinx/LICENSE.txt) | Source label 1.3.2 plus inherited changes; exact source/provenance hashes recorded below |
| Spv.Generator | [Original grant](dm/third_party/ryujinx/src/Spv.Generator/LICENSE) and Khronos notice in spirv.cs | Referenced by the offline translator |
| MacNativeGames | [MIT](dm/third_party/macnativegames/LICENSE), original source comments | Adapted widening, clears and visibility-counter lowering |
| deko3d | [Original zlib license, fincs](dm/third_party/deko3d/LICENSE), [source record](dm/third_party/deko3d/README.md) | nvn_tex.c is an adapted C algorithm; exact historical import revision was not recorded |
| Vulkan-Headers | Headers permit Apache-2.0 OR MIT; this distribution selects [MIT](dm/third_party/vulkan-headers/LICENSES/MIT.txt) | Recorded v1.4.363; header copyrights and LICENSE.md retained |
| NVIDIA FLIP | [BSD 3-Clause](dm/third_party/flip/LICENSE) | Optional developer tooling; bundled stb_image, stb_image_write and tinyexr retain their in-file licenses |
| NVN declarations | Copyright 2020 h1k421, full MIT notice in nvn.h | Reconstructed interface declarations |
| ZBIC decompressor | [BSD-3-Clause](dm/tools/zbic/LICENSE.zstd), original amalgamation header | zstd 1.5.7 variant from the recorded Atmosphere commit; BSD option selected |
| Title-name data | [Retained titledb MIT notice](tools/packaging_gui/data/titledb-LICENSE.md) | Display-name metadata |

The inherited built-in MSL helpers remain source under the nxnative MIT grant;
no generated game shader pack is included. Retained source headers, modification
notes and original license files are authoritative.

## Locked translator binaries

[The runtime review](dm/third_party/translator-runtime/README.md) indexes eight
original license/notice files, package metadata, full per-file SHA-256 and the
producer/source evidence. All 61 binaries match the fixed Touchline 27 reference;
56 external DLLs were also independently matched to exact NuGet package members.
The four source-backed DLLs and native apphost match original rebuild commit
674c2e141cf87917271858c455657aa8637f22d0; 364 corresponding source/configuration/
license files match that producer snapshot. A bit-reproducible historical build
recipe is not claimed.

- Gommon 2.8.1.2: MIT, Evan Husted.
- Humanizer.Core / 51 locale assemblies 3.0.10: MIT, .NET Foundation and
  Contributors; Inflector (Scott Kirkland) and ByteSize (Omar Khudeira) attributions retained.
- Microsoft.IO.RecyclableMemoryStream 3.0.1: Microsoft MIT license.
- System.CodeDom 4.4.0: original package MIT license and full third-party notices.
- MsgPack.Cli 1.0.1: **Apache-2.0**, Copyright 2010-2016 FUJIWARA, Yusuke,
  all rights reserved. Full original license retained. It is not relicensed under MIT.
- .NET apphost 10.0.13: original package MIT license and full third-party notices;
  normalized SDK-template correspondence, not exact NuGet native-binary equality.

## External tools and private game artifacts

Xcode/Apple SDKs, Metal tools, XcodeGen, SPIRV-Cross, .NET, Python dependencies and
restored packages are external tools. nx_extract restores LibHac 0.19.0 separately;
the complete installed runtime/SDK and every restored package are not vendored here.
Their future binary distribution requires the applicable original notices too.

The source repository excludes game containers, keys, extracted executables,
RomFS, generated shaders/metallibs, saves, screenshots, logs and build products.
Profile tables contain compatibility identifiers and metadata, not shader programs.
App/IPA products may embed rewritten game code, derived shaders and fonts; source
publication clearance does not authorize publishing those artifacts. Release
products stay local and ignored.

Dungeon1 is an independent community project with no official affiliation or
endorsement from Red Hook Studios, Nintendo, Apple or their affiliates.
