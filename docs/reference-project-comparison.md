# Reference projects reviewed

Touchline 23 supplies a single-title wrapper around the same host/rewriter and
separates extracted, rewritten, shader and package stages. Its packaging GUI is
specific to that product and is not copied as a new Dungeon1 product UI. Dungeon1
uses the inherited native single-game launcher and dedicated CLI wrappers.

Touchline 27 documents exact translator binary/source lineage and distinguishes
source release review from private bundled products. Touchline 23's later
translator-runtime notices retain original package licenses and 61/364 hash
manifests. Dungeon1 rechecked those bytes, rather than inheriting a blanket claim.

Both use private game inputs, per-project cache/output locations, a single profile
and an independent initial Git history. Dungeon1 additionally supports the bundled
directory artifacts required here, with DLC and the title's GL layer. No dependency
on either reference directory is embedded in the build or runtime paths.
