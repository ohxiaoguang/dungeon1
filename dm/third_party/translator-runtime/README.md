# Locked shader translator: provenance and licenses

Review date: 2026-10-31. All six publication blockers are resolved for this source
file set; see [the final audit](../../../docs/public-release-audit.md). This is not a
claim of a bit-reproducible historical build or permission to distribute game data.

## Identity and original materials

All **60 DLLs and one arm64 native apphost** match Touchline 27's fixed manifest
and working files byte-for-byte. Both runtime JSON files also match. There are no
changed or unmatched runtime binaries. [binaries.tsv](binaries.tsv) records every
full SHA-256, reference SHA-256, package/member or producer Git blob and disposition.
[binary-provenance.json](binary-provenance.json) preserves the exact package URLs,
package hashes and the fixed reference commit, with current verification results.

The 56 external DLLs were independently rechecked against the exact cached NuGet
packages: both full package SHA-256 and member bytes match the reference evidence.
The following original materials were copied without alteration from Touchline 27,
then checked against the original package members or fixed upstream source:

| Dependency | Distributed files | Original terms and materials |
| --- | --- | --- |
| Gommon 2.8.1.2 | Gommon.dll | [MIT](licenses/Gommon-MIT.txt), Evan Husted; package content/LICENSE, source revision 222084874ac473e02f27faeb10e540f926702976 |
| Humanizer.Core and locale packages 3.0.10 | Humanizer.dll + 51 satellites | [MIT and Inflector/ByteSize attributions](licenses/Humanizer-MIT.txt); .NET Foundation and Contributors, Scott Kirkland and Omar Khudeira; source revision 90f0cb1d7427635f38b46350bb1dc5fca2164f2d |
| Microsoft.IO.RecyclableMemoryStream 3.0.1 | Microsoft.IO.RecyclableMemoryStream.dll | [MIT](licenses/RecyclableMemoryStream-MIT.txt), Microsoft; source revision e29a28387da9018fa9605a1dcb3f7a0435aa9974 |
| MsgPack.Cli 1.0.1 | MsgPack.dll | [Apache-2.0 original full text](licenses/MsgPack-Apache-2.0.txt); Copyright 2010-2016 FUJIWARA, Yusuke, all rights reserved. No separate NOTICE was located by the reference audit at tag 1.0.1; the distributed DLL is unchanged. It is not relicensed by the root MIT license. |
| System.CodeDom 4.4.0 | System.CodeDom.dll | [Package MIT license](licenses/System.CodeDom-LICENSE.txt) and [complete package third-party notices](licenses/System.CodeDom-THIRD-PARTY-NOTICES.txt) |
| Microsoft.NETCore.App.Host.osx-arm64 10.0.13 | dmsh_xlate native apphost | [Original package license](licenses/Dotnet-AppHost-LICENSE.txt) and [complete third-party notices](licenses/Dotnet-AppHost-THIRD-PARTY-NOTICES.txt) |

`metadata/` retains original nuspec files. The manifest hashes every original
license. [Original-source verification](metadata/original-license-verification.json)
records direct fixed-source/license and .NET package checks. Gommon/CodeDom texts
were additionally compared with the cached package members. Earlier top-level
notice copies remain byte-identical compatibility copies.

## Producer and source lineage: resolved

The four source-backed DLLs and apphost are byte-identical to original development
commit `674c2e141cf87917271858c455657aa8637f22d0`,
which records rebuilding the translator from in-repository source and remeasuring
the lock. Its parent is ffb3122026aa9aea4ffe35a1af54146cc7f19d04.
The producer Git objects are from the maintainer's non-public development record;
they were read locally without changing that repository. The exact producer SHA,
parent, source tree and blob identities are retained here. This is a maintainer-verified
comparison, not a claim that those original objects are anonymously accessible. The public reference's R3 supplement is
[linked here](https://github.com/ohxiaoguang/touchline27/blob/7ff172ea582dedea1f09cd4f3c98f681ca1c1cd0/docs/upstream-provenance.md#original-repository-investigation-r3-supplement).

All **364 non-README source, project, configuration and license files** in the
translator/Ryujinx paths were independently compared with producer Git objects.
They are identical. [source-provenance.tsv](source-provenance.tsv) records their
SHA-256 and Git blob IDs. The Ryujinx src tree is
`eb03ac436a486e3bf4e003af125be706eea7e403`, also the source tree identified by
Touchline 27's final R3 decision and the historical official source baseline.

The retained graph is translator -> Ryujinx.Graphics.Shader -> Ryujinx.Common /
Spv.Generator, with a direct translator -> Common reference. Projects target
net10.0; resolved dependency versions are in the unchanged deps.json. Original
nxnative MIT, Ryujinx MIT and Spv.Generator/Khronos notices remain in place.
The current wrapper's embedded source check and lock verification pass.

This establishes producer, source snapshot, project relationships and licensing.
The exact historical compiler command, SDK patch and environment were not
recorded. The three Ryujinx/Spv assemblies' informational-version marker is not
asserted as an independently verified source revision. No bit-reproducible build
or equality with current upstream binaries is claimed, and none is needed merely
to resolve the former unidentified-origin concern.

## Native apphost: resolved

The apphost SHA-256 is
`f534c3370b84833fd1a4c75ea37b7ffb8d8e68dbc91adae6e1c4b8894d5db381`.
It identifies .NET 10.0.13, dotnet/dotnet source commit
`4099f83977f4d29604a9aeb971fb0a7bc1d5f699`. The normalized SDK-template comparison
was independently repeated: the installed template SHA-256 is
`c5200056995c1efd7465cefe2d4ce3df6d42674baf68fec482f1e63ef492cff2`.
Bytes before the signature payload at 0x1d990 match after normalizing only the
1024-byte application-name buffer at 0x10228, __LINKEDIT size fields at 0x520 /
0x530 and LC_CODE_SIGNATURE size at 0x6e4. The signature payload itself differs.
This is a generated SDK-template match, **not an exact NuGet apphost byte match**.
The NuGet package's hash and original license/notices were separately verified.

## Preserved tooling and disclosed metadata

No binary, translator source, runtime configuration, shader chain lock/header or
shader library was replaced or rebuilt. The standalone PDB stays ignored.
`dmsh_xlate.dll` retains a historical absolute build/PDB path in its debug metadata,
as does the byte-identical reference binary. This is build metadata, not a key or
credential; it is disclosed rather than patched away. Keep all applicable notices
with redistributions of the translator. Game-derived artifacts have a separate
rights boundary; see [THIRD_PARTY_NOTICES](../../../THIRD_PARTY_NOTICES.md).
