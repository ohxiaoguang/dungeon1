"""Export FIFA 23 shaders to nxnative's shader package format.

Input : decrypted shader.big + shaderboot.big (BIG4 of NXSHADER .fxo)
Output: <pkg>/<stage>_fifa.bin       records 'BTCDBTCD' + 0x30 header
                                     (+0x28 control length, +0x2c code length)
                                     + code area + control section
        <map>                        same columns as shader_split.py's map
"""
import collections
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import big4  # noqa: E402
import fxo  # noqa: E402

STAGE_NAME = {"vs": "vertex", "hs": "hull", "ds": "domain",
              "gs": "geometry", "ps": "pixel", "cs": "compute"}


def collect(paths):
    """-> ordered dict key -> (where, stage, ctl, code)"""
    keys = {}
    for path in paths:
        d = Path(path).read_bytes()
        b = big4.parse(d)
        src = Path(path).stem
        for eo, es, name in b["entries"]:
            for st, key, ctl, code, off in fxo.programs(d[eo:eo + es]):
                keys.setdefault(key, (f"{src}#{name}@0x{off:x}", st, ctl, code))
    return keys


def write(keys, pkg, mapout):
    pkg.mkdir(parents=True, exist_ok=True)
    recs, rows = collections.defaultdict(list), []
    for key in sorted(keys, key=lambda k: (keys[k][1], keys[k][0], k)):
        where, st, ctl, code = keys[key]
        name = f"{st}_fifa.bin"
        rec = bytearray(b"BTCDBTCD" + bytes(0x30))
        struct.pack_into("<2I", rec, 0x28, len(ctl), len(code))
        rec += code + ctl
        rows.append((name, len(recs[name]), STAGE_NAME[st], key, where))
        recs[name].append(bytes(rec))
    for name, rr in recs.items():
        (pkg / name).write_bytes(b"".join(rr))
    with open(mapout, "w") as f:
        f.write("# path\tindex\tstage\tkey\tsource\n")
        for r in rows:
            f.write("%s\t%d\t%s\t%s\t%s\n" % r)
    return rows


if __name__ == "__main__":
    src = sys.argv[1:-2]
    keys = collect(src)
    rows = write(keys, Path(sys.argv[-2]), sys.argv[-1])
    st = collections.Counter(r[2] for r in rows)
    print(f"keys={len(rows)} {dict(st)}")
