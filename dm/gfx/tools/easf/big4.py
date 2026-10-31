"""Minimal BIG4 reader (EA); mirrors the layout already verified via romfspeek."""
import struct


def parse(d):
    if d[:4] != b"BIG4":
        raise ValueError("not BIG4: %r" % d[:4])
    size = struct.unpack("<I", d[4:8])[0]
    count = struct.unpack(">I", d[8:12])[0]
    table_end = struct.unpack(">I", d[12:16])[0]
    off, entries = 0x10, []
    for _ in range(count):
        eo, es = struct.unpack(">II", d[off:off + 8])
        off += 8
        z = d.index(b"\0", off)
        name = d[off:z].decode("latin1")
        off = z + 1
        entries.append((eo, es, name))
    return dict(size=size, count=count, table_end=table_end,
                entries=entries, parsed_end=off)
