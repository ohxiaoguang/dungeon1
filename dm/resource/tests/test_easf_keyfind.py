"""The EASF key found in a game's own program module, and every way it can fail.

The fixtures are synthetic: a small NSO0 whose read-only segment holds the key
registry record, and an EASF container made with the matching key. Nothing here
reads the retail game, and no key from it appears in the repository.

Cases: a module that holds the record, two module builds with the record at
different offsets, a private key file alone, a private key file that does not
verify, no identifier, a corrupted container, a file that is not an NSO0, and
the end-to-end check that discovery and the key file prepare byte-identical
packages.
"""
import hashlib
import io
import json
from contextlib import redirect_stdout
import struct
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / 'dm/gfx/tools/easf'))
import fixture
import keyfind
import prepare

try:   # the container itself needs it, exactly as easf/prepare.py does
    from Crypto.Cipher import AES   # noqa: F401
    HAVE_CRYPTO = True
except ImportError:
    HAVE_CRYPTO = False
try:   # an NSO0 module is LZ4-compressed in the retail game; the fixtures are not
    import lz4.block   # noqa: F401
    HAVE_LZ4 = True
except ImportError:
    HAVE_LZ4 = False

KEY_ID = 'test    '            # the eight-character ID an EASF header names
KEY = bytes(range(16, 32))
OTHER_KEY = bytes(range(32, 48))
BUILD_ID = bytes(range(0x40, 0x60))


def cbc_encrypt(data, key):
    """EASF is AES-128-CBC with the key as IV; encrypt block by block."""
    out, previous = bytearray(), key
    for at in range(0, len(data), 16):
        previous = fixture.ecb(key, bytes(a ^ b for a, b in zip(data[at:at + 16], previous)))
        out += previous
    return bytes(out)


def easf(payload, key=KEY, key_id=KEY_ID, size=None, digest=None):
    """An EASF container; `size` / `digest` bend it into a rejected variant."""
    padded = payload + bytes(-len(payload) % 16)
    return (b'EASF' + struct.pack('>I', len(payload) if size is None else size)
            + key_id.encode()
            + (hashlib.sha256(payload[:32]).digest() if digest is None else digest)
            + cbc_encrypt(padded, key))


def nso(rodata, data=b'', build_id=BUILD_ID, pad=b'', compress=False):
    """A three-segment NSO0; `pad` shifts the record, `compress` LZ4-blocks it."""
    text = bytes(4)
    blobs = [text, pad + rodata, data]
    memory, at = [0], 0
    for blob in blobs:
        at += len(blob)
        memory.append(at)
    header = bytearray(0x70)
    header[:4] = b'NSO0'
    header[0x40:0x60] = build_id
    if compress:
        header[0xC] = 0b111
    body = bytearray()
    for i, blob in enumerate(blobs):
        packed = lz4.block.compress(blob, store_size=False) if compress else blob
        struct.pack_into('<III', header, 0x10 + i * 0x10, 0x100 + len(body), memory[i], len(blob))
        struct.pack_into('<I', header, 0x60 + i * 4, len(packed))
        body += packed
    return bytes(header) + bytes(0x100 - len(header)) + bytes(body)


def records(*entries):
    """The registry as it is compiled in: each record is id[8] then key[16]."""
    return b''.join(f'{name:<8}'.encode() + key for name, key in entries)


def big4_archive(members):
    """BIG4 with absolute member offsets, as big4.parse reads them."""
    table, names = bytearray(), bytearray()
    for name, body in members:
        table += struct.pack('>II', 0, len(body)) + name.encode() + b'\0'
    table_end = 0x10 + len(table)
    out = bytearray(b'BIG4' + struct.pack('<I', table_end + sum(len(b) for _, b in members))
                    + struct.pack('>II', len(members), table_end) + table)
    offset, at = table_end, 0x10
    for name, body in members:
        struct.pack_into('>I', out, at, offset)
        at += 8 + len(name) + 1
        offset += len(body)
    return bytes(out + b''.join(body for _, body in members))


def fxo(programs):
    """A NXSHADER container holding one GLSLC output per (stage, sphere, seed)."""
    body = bytearray()
    for stage, sphere, seed in programs:
        control = bytearray(0x880)
        control[:4] = bytes.fromhex('34127698')
        struct.pack_into('<I', control, 0x20, len(control))
        code = bytearray(0x80)
        code[:4] = bytes.fromhex('78563412' if stage != 'cs' else '79563412')
        struct.pack_into('<I', code, 0x30, 0x61 | sphere << 10)
        code[0x40] = seed
        struct.pack_into('<I', control, 0x704, len(code))
        struct.pack_into('<I', control, 0x6f0, len(control) + 0x180)
        if stage == 'cs':
            struct.pack_into('<3I', control, 0x748, 32, 1, 1)
            struct.pack_into('<I', control, 0x754, 8)
        body += control + bytes(0x180) + code
    return bytes(b'NXSHADER' + bytes(8) + b'GLSL' + struct.pack('<I', len(body) + 8) + body)


def archives():
    """The two archive files the game keeps in RomFS, one of them encrypted."""
    shader = big4_archive([('combiner.fxo', fxo([('vs', 1, 3), ('ps', 5, 4)]))])
    boot = big4_archive([('boot.cs.fxo', fxo([('cs', 0, 9)]))])
    return {'shader.big': easf(shader), 'shaderboot.big': boot}


@unittest.skipUnless(HAVE_CRYPTO, 'pycryptodome opens the EASF container')
class Discovery(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='easf-keyfind-', dir=HERE / 'build'
                                               if (HERE / 'build').is_dir() else None)
        self.root = Path(self.tmp.name)
        self.data = easf(big4_archive([('a.fxo', fxo([('vs', 0, 1)]))]))

    def tearDown(self):
        self.tmp.cleanup()

    def module(self, name='main', **kwargs):
        path = self.root / name
        path.write_bytes(nso(records((KEY_ID, KEY)), **kwargs))
        return path

    def test_finds_the_record_and_confirms_it(self):
        module = self.module()
        ring = keyfind.Keyring(modules=[module])
        key, source = ring.resolve(self.data)
        self.assertEqual(key, KEY)
        self.assertEqual(source, f'main@{keyfind.records(keyfind.module_image(module), KEY_ID.encode())[0][0]:#x}')
        self.assertEqual(ring.fingerprints[KEY_ID], hashlib.sha256(KEY).hexdigest()[:16])
        self.assertIn('1 candidate(s) checked', ' '.join(ring.notes))

    def test_two_builds_with_the_record_at_different_offsets(self):
        first = self.module('main', pad=b'')
        second_root = self.root / 'v103'
        second_root.mkdir()
        second = second_root / 'main'
        second.write_bytes(nso(records(('other   ', OTHER_KEY), (KEY_ID, KEY)),
                               build_id=bytes(range(1, 33)), pad=bytes(0x120)))
        places = set()
        for module in (first, second):
            ring = keyfind.Keyring(modules=[module])
            key, source = ring.resolve(self.data)
            self.assertEqual(key, KEY)
            places.add(source.rsplit('@', 1)[1])
        # The two modules hold the same record at different addresses: nothing
        # in the discovery depends on a fixed offset.
        self.assertEqual(len(places), 2, places)

    def test_a_decoy_record_before_the_real_one(self):
        module = self.root / 'main'
        module.write_bytes(nso(records((KEY_ID, OTHER_KEY), (KEY_ID, KEY))))
        ring = keyfind.Keyring(modules=[module])
        self.assertEqual(ring.resolve(self.data)[0], KEY)
        self.assertIn('2 candidate(s) checked', ' '.join(ring.notes))

    def test_the_private_file_alone_answers(self):
        key_file = self.root / 'easf.json'
        key_file.write_text(json.dumps({KEY_ID: KEY.hex()}))
        ring = keyfind.Keyring(key_file=key_file)
        key, source = ring.resolve(self.data)
        self.assertEqual((key, source), (KEY, 'easf key file'))

    def test_a_wrong_private_key_falls_through_to_discovery(self):
        key_file = self.root / 'easf.json'
        key_file.write_text(json.dumps({KEY_ID: OTHER_KEY.hex()}))
        ring = keyfind.Keyring(key_file=key_file, modules=[self.module()])
        key, source = ring.resolve(self.data)
        self.assertEqual(key, KEY)
        self.assertTrue(source.startswith('main@'))
        self.assertIn('does not verify', ring.notes[0])

    def test_a_private_file_without_the_entry_falls_through(self):
        key_file = self.root / 'easf.json'
        key_file.write_text(json.dumps({'none    ': KEY.hex()}))
        ring = keyfind.Keyring(key_file=key_file, modules=[self.module()])
        self.assertEqual(ring.resolve(self.data)[0], KEY)

    def test_no_source_answers_nothing(self):
        ring = keyfind.Keyring()
        self.assertEqual(ring.resolve(self.data), (None, None))
        with self.assertRaises(ValueError) as caught:
            prepare.decode_archive('shader.big', self.data, keys=ring)
        message = str(caught.exception)
        self.assertIn('test', message)          # the key ID, so the user knows which one
        self.assertNotIn(KEY.hex(), message)    # never the key itself

    def test_a_missing_identifier_needs_the_bounded_scan(self):
        # The record is there, under a name the container does not use: only the
        # bounded scan of the read-only segment can still confirm the key.
        module = self.root / 'main'
        module.write_bytes(nso(records(('datax   ', KEY))))
        self.assertEqual(keyfind.Keyring(modules=[module]).resolve(self.data), (None, None))
        ring = keyfind.Keyring(modules=[module], bounded=True)
        key, source = ring.resolve(self.data)
        self.assertEqual(key, KEY)
        self.assertIn('bounded scan', source)

    def test_a_compressed_module_like_the_retail_one(self):
        # The retail main is an LZ4-blocked NSO0, so this is the path a real
        # build takes: segments are placed at their memory offsets before the
        # record is looked for.
        if not HAVE_LZ4:
            self.skipTest('lz4 decompresses an NSO0 segment')
        module = self.module('main', compress=True)
        self.assertNotEqual(keyfind.module_image(module)[:4], b'NSO0')
        ring = keyfind.Keyring(modules=[module])
        self.assertEqual(ring.resolve(self.data)[0], KEY)
        self.assertIn('found in main', ' '.join(ring.notes))

    def test_a_module_whose_segment_does_not_decompress_is_rejected(self):
        if not HAVE_LZ4:
            self.skipTest('lz4 decompresses an NSO0 segment')
        module = self.module('main', compress=True)
        broken = bytearray(module.read_bytes())
        struct.pack_into('<I', broken, 0x60, len(broken))    # a compressed size past the file
        module.write_bytes(bytes(broken))
        with self.assertRaises(ValueError):
            keyfind.Keyring(modules=[module]).resolve(self.data)

    def test_a_corrupted_container_is_rejected(self):
        module = self.module()
        broken = bytearray(easf(big4_archive([('a.fxo', fxo([('vs', 0, 1)]))])))
        broken[48] ^= 1                          # the first ciphertext block no longer matches the digest
        self.assertEqual(keyfind.Keyring(modules=[module]).resolve(bytes(broken)), (None, None))

    def test_a_container_whose_digest_is_wrong_is_rejected(self):
        lying = easf(big4_archive([('a.fxo', fxo([('vs', 0, 1)]))]), digest=bytes(32))
        module = self.module()
        self.assertEqual(keyfind.Keyring(modules=[module]).resolve(lying), (None, None))

    def test_a_file_that_is_not_a_module_is_rejected(self):
        other = self.root / 'main'
        other.write_bytes(big4_archive([('a.fxo', b'')]))
        with self.assertRaises(ValueError) as caught:
            keyfind.Keyring(modules=[other]).resolve(self.data)
        self.assertIn('not an NSO0 module', str(caught.exception))

    def test_a_truncated_module_is_rejected(self):
        module = self.module()
        module.write_bytes(module.read_bytes()[:0x50])
        with self.assertRaises(ValueError):
            keyfind.Keyring(modules=[module]).resolve(self.data)

    def test_the_header_is_checked_before_anything_else(self):
        with self.assertRaises(ValueError):
            keyfind.parse_header(b'NOPE' + bytes(60))
        with self.assertRaises(ValueError):
            keyfind.parse_header(b'EASF' + bytes(20))       # too short
        with self.assertRaises(ValueError):
            keyfind.parse_header(b'EASF' + struct.pack('>I', 8) + bytes(8) + bytes(32) + bytes(17))


@unittest.skipUnless(HAVE_CRYPTO and HAVE_LZ4, 'the EASF container and an NSO0 module are both needed')
class Prepare(unittest.TestCase):
    """Discovery and the private key file must prepare the same package."""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='easf-prepare-', dir=HERE / 'build'
                                               if (HERE / 'build').is_dir() else None)
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def run_prepare(self, where, **kwargs):
        members = archives()
        for name, body in members.items():
            (self.root / name).write_bytes(body)
        pkg, profile = self.root / where / 'pkg', self.root / where / 'profile'
        out = io.StringIO()
        with redirect_stdout(out):
            prepare.prepare([(name, body) for name, body in members.items()], pkg, profile, **kwargs)
        files = {p.name: p.read_bytes() for p in sorted(pkg.iterdir())}
        files |= {p.name: p.read_bytes() for p in sorted(profile.iterdir())}
        return files, out.getvalue()

    def test_discovery_and_the_key_file_agree(self):
        key_file = self.root / 'easf.json'
        key_file.write_text(json.dumps({KEY_ID: KEY.hex()}))
        module = self.root / 'main'
        module.write_bytes(nso(records((KEY_ID, KEY))))
        from_file, said_file = self.run_prepare('file', key_file=key_file)
        from_module, said_module = self.run_prepare('module', modules=[module])
        self.assertEqual(from_file, from_module)
        self.assertNotIn(KEY.hex(), said_file + said_module)
        self.assertIn(hashlib.sha256(KEY).hexdigest()[:16], said_module)
        self.assertIn('private key file', said_file)
        self.assertIn('found in main', said_module)

    def test_the_command_line_discovers_too(self):
        """easf/prepare.py --module, the preparer's own entry point."""
        module = self.root / 'main'
        module.write_bytes(nso(records((KEY_ID, KEY)), compress=HAVE_LZ4))
        paths = []
        for name, body in archives().items():
            (self.root / name).write_bytes(body)
            paths.append(self.root / name)
        pkg, profile = self.root / 'cli' / 'pkg', self.root / 'cli' / 'profile'
        done = subprocess.run([sys.executable, str(REPO / 'dm/gfx/tools/easf/prepare.py'),
                               *[str(a) for a in paths], '--pkg', str(pkg),
                               '--profile', str(profile), '--module', str(module)],
                              capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn('found in main', done.stdout)
        self.assertNotIn(KEY.hex(), done.stdout + done.stderr)
        rows = [line for line in (profile / 'shader_map.tsv').read_text().splitlines()
                if line and not line.startswith('#')]
        self.assertEqual(len(rows), 3)


if __name__ == '__main__':
    if not (HERE / 'build').is_dir():
        (HERE / 'build').mkdir()
    unittest.main()
