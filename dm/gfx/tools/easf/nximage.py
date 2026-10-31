"""Read an EA shader archive that lives inside a mounted resource image.

The archives are BIG4 members of a RomFS file (FIFA 23 keeps both under
`datax.big`), so nothing has to be extracted: this module reads the container's
member table and then the requested member's byte range, both through
`tools/nxrom/resourcefs.py`'s read-only mount.

The mount caps a single read at 1 MiB, so ranges larger than that are read in
pieces -- that cap is a property of the mount, not of these archives.
"""
import struct

import big4

CHUNK = 1024 * 1024


def read_range(fs, path, offset, size):
    """Read exactly `size` bytes at `offset`; the mount refuses more per call."""
    out = bytearray()
    with fs.open(path, buffering=0) as f:
        f.seek(offset)
        while len(out) < size:
            piece = f.read(min(CHUNK, size - len(out)))
            if not piece:
                raise ValueError(f'{path}: short read at offset {offset + len(out)}')
            out += piece
    return bytes(out)


def table(fs, path):
    """-> big4.parse() of the container's member table, reading only the table."""
    total = fs.stat(path).size
    head = read_range(fs, path, 0, 16)
    if head[:4] != b'BIG4':
        raise ValueError(f'{path}: not a BIG4 archive: {head[:4]!r}')
    end = struct.unpack_from('>I', head, 12)[0]
    if not 16 <= end <= total:
        raise ValueError(f'{path}: BIG4 member table ends outside the file ({end} > {total})')
    return big4.parse(read_range(fs, path, 0, end))


def member(fs, path, name):
    """-> the bytes of BIG4 member `name` inside the mounted file `path`."""
    found = [(offset, size) for offset, size, entry in table(fs, path)['entries'] if entry == name]
    if len(found) != 1:
        raise ValueError(f'{path}: expected one member named {name!r}, found {len(found)}')
    offset, size = found[0]
    total = fs.stat(path).size
    if offset + size > total:
        raise ValueError(f'{path}: member {name!r} exceeds the archive ({offset + size} > {total})')
    return read_range(fs, path, offset, size)
