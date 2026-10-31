"""NSO segment handling: raw, LZ4 and ZBIC containers, and the checks that must fail.

Every fixture here is built in the test from a few bytes: no game module, NSP or key is
involved. The ZBIC frames are hand-assembled single-block frames whose block is stored raw,
which is valid ZBIC (the entropy tables that Nintendo's binary-interpolative coding covers
only exist in compressed blocks); a real SDK 22.0.0 module exercises that path end to end.
"""
import importlib.util
import struct
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / 'dm/tools'))
import nsoseg


def zbic_frame(payload, magic=0x4349425A):
    """One-block ZBIC frame whose block is stored raw: magic, frame header, block header, data."""
    assert len(payload) < 256
    frame = struct.pack('<I', magic) + bytes([0x20, len(payload)])          # single segment, 1-byte size
    frame += struct.pack('<I', 1 | (len(payload) << 3))[:3]                  # last block, type raw, size
    return frame + bytes(payload)


def lz4_block(payload):
    import lz4.block
    return lz4.block.compress(bytes(payload), store_size=False)


def nso(*segments, flags=None, bss=0, build_id=b'\x11' * 16, hashes=True, module_name=b''):
    """An NSO0 container holding `segments`, each (memory offset, plain bytes, stored bytes, compressed).

    A module always has three segments, so a test that names fewer gets 4-byte fillers after the
    last one (the reader refuses a zero-size segment).
    flags: override the whole flag word; otherwise bits 0-2 follow `compressed`, bits 3-5 are
    set when `hashes` is true and bit 7 is set when the whole flag word says so."""
    segments = list(segments)
    end = max(mo + len(plain) for mo, plain, _, _ in segments)
    while len(segments) < 3:
        segments.append((end, b'\0\0\0\0', b'\0\0\0\0', False)); end += 4
    if flags is None:
        flags = 0
        for i, (_, _, _, compressed) in enumerate(segments):
            if compressed: flags |= 1 << i
        if hashes: flags |= nsoseg.FLAG_HASH
    head = bytearray(0x100)
    head[0:4] = b'NSO0'
    struct.pack_into('<I', head, 0x0C, flags)
    body = bytearray()
    offset = 0x100 + len(module_name)
    for i, (memory_offset, plain, stored, compressed) in enumerate(segments):
        struct.pack_into('<III', head, 0x10 + i * 16, offset, memory_offset, len(plain))
        struct.pack_into('<I', head, 0x60 + i * 4, len(stored) if compressed else len(plain))
        if hashes:
            import hashlib
            head[0xA0 + i * 0x20:0xA0 + (i + 1) * 0x20] = hashlib.sha256(plain).digest()
        body += stored
        offset += len(stored)
    struct.pack_into('<I', head, 0x3C, bss)
    struct.pack_into('<I', head, 0x2C, len(module_name))
    head[0x40:0x50] = build_id
    head[0x50:0x60] = b'\x22' * 16
    return bytes(head) + module_name + bytes(body)


class Container(unittest.TestCase):
    def test_raw_segments(self):
        text, ro, data = b'CODE' * 8, b'RO' * 4, b'DAT' * 2
        image, header = nsoseg.image(nso((0x0, text, text, False), (0x100, ro, ro, False), (0x200, data, data, False)))
        self.assertEqual(header.compression, 'raw')
        self.assertEqual(header.flags & nsoseg.FLAG_HASH, nsoseg.FLAG_HASH)
        self.assertEqual(image[0x0:0x20], text)
        self.assertEqual(image[0x100:0x108], ro)
        self.assertEqual(image[0x200:0x206], data)
        self.assertEqual(len(image), 0x206)

    def test_lz4_segments(self):
        text, ro, data = b'\x01\x02\x03\x04' * 64, b'RODATA' * 8, b'DATA' * 4
        image, header = nsoseg.image(nso((0x0, text, lz4_block(text), True),
                                         (0x100, ro, lz4_block(ro), True),
                                         (0x200, data, data, False)))
        self.assertEqual(header.compression, 'lz4')
        self.assertEqual(header.segments[0].compression, 'lz4')
        self.assertEqual(image[0x0:len(text)], text)
        self.assertEqual(image[0x200:0x210], data)

    def test_zbic_segments(self):
        text, ro, data = b'ZBIC text' * 6, b'rodata-here', b'data!'
        image, header = nsoseg.image(nso((0x0, text, zbic_frame(text), True),
                                         (0x100, ro, zbic_frame(ro), True),
                                         (0x200, data, data, False),
                                         flags=(1 << 0) | (1 << 1) | nsoseg.FLAG_HASH | nsoseg.FLAG_ZBIC))
        self.assertEqual(header.compression, 'zbic')
        self.assertTrue(header.flags & nsoseg.FLAG_ZBIC)
        self.assertEqual([s.compression for s in header.segments], ['zbic', 'zbic', 'raw'])
        self.assertEqual(image[0x0:len(text)], text)
        self.assertEqual(image[0x100:0x100 + len(ro)], ro)

    def test_mixed_container_and_bss(self):
        text = b'A' * 32
        image, header = nsoseg.image(nso((0x0, text, lz4_block(text), True),
                                         (0x20, b'RO', b'RO', False), (0x24, b'DA', b'DA', False), bss=0x40), bss=True)
        self.assertEqual(len(image), 0x26 + 0x40)
        self.assertEqual(image[0x26:], bytes(0x40))
        self.assertEqual(header.bss, 0x40)

    def test_load_reads_build_id_and_sizes(self):
        tmp = Path(tempfile.mkdtemp()); self.addCleanup(shutil.rmtree, tmp)
        path = tmp / 'main'
        text, ro, data = b'T' * 40, b'R' * 8, b'D' * 4
        path.write_bytes(nso((0x0, text, zbic_frame(text), True), (0x100, ro, ro, False),
                             (0x200, data, data, False), flags=0b10000001))
        image, build_id, sizes, bss = nsoseg.load(path, bss=False)
        self.assertEqual(build_id, '11' * 16)
        self.assertEqual(sizes, [40, 8, 4])
        self.assertEqual(bss, 0)
        self.assertEqual(len(image), 0x204)


class Refusals(unittest.TestCase):
    def test_not_an_nso(self):
        with self.assertRaisesRegex(nsoseg.NsoError, 'magic'):
            nsoseg.parse(b'NRO0' + bytes(0x100))
        with self.assertRaisesRegex(nsoseg.NsoError, 'shorter than'):
            nsoseg.parse(b'NSO0')

    def test_unknown_flag_bits(self):
        data = bytearray(nso((0x0, b'x' * 4, b'x' * 4, False)))
        struct.pack_into('<I', data, 0x0C, 0x100)          # bit 8: not a known NSO flag
        with self.assertRaisesRegex(nsoseg.NsoError, 'unknown NSO flag'):
            nsoseg.parse(bytes(data))

    def test_truncated_segment(self):
        data = nso((0x0, b'T' * 64, lz4_block(b'T' * 64), True))
        with self.assertRaisesRegex(nsoseg.NsoError, 'runs past the file'):
            nsoseg.parse(data[:-8])

    def test_segment_without_size(self):
        data = bytearray(nso((0x0, b'x' * 4, b'x' * 4, False)))
        struct.pack_into('<I', data, 0x18, 0)
        with self.assertRaisesRegex(nsoseg.NsoError, 'has no size'):
            nsoseg.parse(bytes(data))

    def test_hash_mismatch(self):
        data = bytearray(nso((0x0, b'T' * 16, b'T' * 16, False)))
        data[0xA0] ^= 0xFF                                  # a header hash that cannot be right
        header = nsoseg.parse(bytes(data))
        with self.assertRaisesRegex(nsoseg.NsoError, 'SHA-256'):
            nsoseg.decode(bytes(data), header, 0)

    def test_zbic_flag_on_an_lz4_segment(self):
        text = b'L' * 32
        data = nso((0x0, text, lz4_block(text), True), flags=0b10001000 | 0b1)   # bit 7 set, LZ4 payload
        header = nsoseg.parse(data)
        with self.assertRaisesRegex(nsoseg.NsoError, 'ZBIC decode failed'):
            nsoseg.decode(data, header, 0)

    def test_zbic_truncated_frame(self):
        text = b'Z' * 24
        data = nso((0x0, text, zbic_frame(text)[:-4], True), flags=0b10001000 | 0b1)
        header = nsoseg.parse(data)
        with self.assertRaisesRegex(nsoseg.NsoError, 'ZBIC decode failed'):
            nsoseg.decode(data, header, 0)

    def test_zbic_size_disagrees_with_header(self):
        text = b'Z' * 24
        data = nso((0x0, text, zbic_frame(text), True), (0x100, b'RO', b'RO', False),
                   (0x104, b'DA', b'DA', False), flags=nsoseg.FLAG_HASH | nsoseg.FLAG_ZBIC | 1)
        wrong = bytearray(data)
        struct.pack_into('<I', wrong, 0x18, len(text) + 8)   # text size larger than the frame holds
        header = nsoseg.parse(bytes(wrong))
        with self.assertRaises(nsoseg.NsoError):
            nsoseg.decode(bytes(wrong), header, 0)

    def test_lz4_corruption(self):
        text = b'0123456789abcdef' * 8
        stored = bytearray(lz4_block(text)); stored[len(stored) // 2] ^= 0xFF
        data = nso((0x0, text, bytes(stored), True), flags=nsoseg.FLAG_HASH | 1)
        header = nsoseg.parse(data)
        with self.assertRaisesRegex(nsoseg.NsoError, 'LZ4 decode failed|SHA-256'):
            nsoseg.decode(data, header, 0)


if __name__ == '__main__':
    unittest.main()
