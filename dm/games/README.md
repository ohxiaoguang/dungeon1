# Dungeon1 profile

Only `01008F1008DA6000` is registered. `game.tsv` defines Darkest Dungeon's
modules, memory layout, GL path and registered builds. `patches.py` contains
Build-ID-specific adaptation; hashes/capture tables are metadata, not shader code.
The product baseline is 1.3.0; v0 metadata supports union shader preparation.
Use the root single-game build scripts. Other game profiles must not be added
automatically. Shared profile readers remain build infrastructure.
