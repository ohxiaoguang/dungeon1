"""FIFA 23 shader archives read out of a mounted image, nothing extracted.

The game keeps both EA shader archives as BIG4 members of one RomFS file, so the
build needs a way to read a member whose only home is the image. These tests use
a synthetic image (a real NSP layout, dummy keys) whose archives hold synthetic
NXSHADER programmes, and one gated test that runs the same code against the real
gamecard when the environment points at it.

No game data, keys or extracted archives are part of the repository.
"""
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / 'dm/gfx/tools/easf'))
from tools.nxrom.resourcefs import ResourceFS, build_library
import fixture
import big4
import nximage
import prepare

try:   # only the EASF member needs it, exactly as easf/prepare.py does
    from Crypto.Cipher import AES   # noqa: F401
    HAVE_CRYPTO = True
except ImportError:
    HAVE_CRYPTO = False

GAME = '01001C8016B4E000'
MEMBERS = ('data/fifarna/shader.big', 'data/fifarna/shaderboot.big')
DATAX = 'datax.big'
EASF_ID = 'test\x20\x20\x20\x20'
EASF_KEY = bytes(range(16, 32))


def cbc_encrypt(data, key):
    """EASF uses AES-128-CBC with the key as IV; encrypt with CommonCrypto ECB blocks."""
    out, previous = bytearray(), key
    for at in range(0, len(data), 16):
        previous = fixture.ecb(key, bytes(a ^ b for a, b in zip(data[at:at + 16], previous)))
        out += previous
    return bytes(out)


def easf(payload, key=EASF_KEY):
    padded = payload + bytes(-len(payload) % 16)
    return (b'EASF' + struct.pack('>I', len(payload)) + EASF_ID.encode()
            + hashlib.sha256(payload[:32]).digest() + cbc_encrypt(padded, key))


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


def fxo(programs, tail=0):
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
    body += bytes(tail)
    return bytes(b'NXSHADER' + bytes(8) + b'GLSL' + struct.pack('<I', len(body) + 8) + body)


def container(members):
    """The RomFS file: both archives as members under the game's own paths."""
    return big4_archive([(f'data/fifarna/{name}', body) for name, body in members.items()])


def image_files():
    """The two archive members, one EASF-encrypted and one plain."""
    shader = big4_archive([('combiner.fxo', fxo([('vs', 1, 3), ('ps', 5, 4)]))])
    boot = big4_archive([('boot.cs.fxo', fxo([('cs', 0, 9)], tail=2 * 1024 * 1024))])
    return {'shader.big': easf(shader), 'shaderboot.big': boot}


class Image(unittest.TestCase):
    """Member reads through a mount, including the per-call 1 MiB cap."""
    @classmethod
    def setUpClass(cls):
        if not (HERE / 'build').is_dir():
            (HERE / 'build').mkdir()
        cls.tmp = tempfile.TemporaryDirectory(prefix='fifa-image-', dir=HERE / 'build')
        cls.root = Path(cls.tmp.name)
        cls.members = image_files()
        cls.library = build_library(cls.root / 'reader.dylib')
        (cls.root / 'keys.txt').write_text('header_key = ' + fixture.HEADER_KEY.hex()
                                          + '\nkey_area_key_application_00 = ' + fixture.AREA_KEY.hex() + '\n')
        (cls.root / 'easf.json').write_text(json.dumps({EASF_ID: EASF_KEY.hex()}))
        (cls.root / 'base.nsp').write_bytes(fixture.pfs([
            ('program.nca', fixture.nca(fixture.romfs({'datax.big': container(cls.members)})))]))
        cls.fs = ResourceFS(cls.library, base=cls.root / 'base.nsp', keys=cls.root / 'keys.txt',
                            title=fixture.TITLE)

    @classmethod
    def tearDownClass(cls):
        cls.fs.close()
        cls.tmp.cleanup()

    def test_member_bytes_match_the_archive(self):
        for name, body in self.members.items():
            self.assertEqual(nximage.member(self.fs, DATAX, f'data/fifarna/{name}'), body)
        # The boot archive is larger than one mount read, so its bytes also prove
        # that read_range stitches the 1 MiB pieces back in order.
        self.assertGreater(len(self.members['shaderboot.big']), 1024 * 1024)

    def test_member_table_is_read_without_the_payload(self):
        parsed = nximage.table(self.fs, DATAX)
        self.assertEqual([(o, s, n) for o, s, n in parsed['entries']],
                         [(o, s, n) for o, s, n in big4.parse(
                             container(self.members))['entries']])

    def test_rejects_unknown_member_and_non_archive(self):
        with self.assertRaises(ValueError):
            nximage.member(self.fs, DATAX, 'data/fifarna/missing.big')
        (self.root / 'plain.nsp').write_bytes(fixture.pfs([
            ('program.nca', fixture.nca(fixture.romfs({'datax.big': bytes(64)})))]))
        with ResourceFS(self.library, base=self.root / 'plain.nsp', keys=self.root / 'keys.txt',
                        title=fixture.TITLE) as fs:
            with self.assertRaises(ValueError):
                nximage.table(fs, DATAX)


@unittest.skipUnless(HAVE_CRYPTO, 'pycryptodome decodes the EASF member')
class Prepare(unittest.TestCase):
    """The in-memory input must produce exactly what the file input produces."""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='fifa-prepare-', dir=HERE / 'build')
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def run_prepare(self, archives, key_file, where):
        pkg, profile = self.root / where / 'pkg', self.root / where / 'profile'
        prepare.prepare(archives, pkg, profile, key_file)
        return ({p.name: p.read_bytes() for p in sorted(pkg.iterdir())}
                | {p.name: p.read_bytes() for p in sorted(profile.iterdir())})

    def test_bytes_and_files_are_equivalent(self):
        members = image_files()
        key_file = self.root / 'easf.json'
        key_file.write_text(json.dumps({EASF_ID: EASF_KEY.hex()}))
        disk = []
        for name, body in members.items():
            (self.root / name).write_bytes(body)
            disk.append(self.root / name)
        from_bytes = self.run_prepare([(name, body) for name, body in members.items()],
                                      key_file, 'a')
        from_files = self.run_prepare(disk, key_file, 'b')
        self.assertEqual(from_bytes, from_files)

    def test_source_strings_keep_the_archive_name(self):
        members = image_files()
        key_file = self.root / 'easf.json'
        key_file.write_text(json.dumps({EASF_ID: EASF_KEY.hex()}))
        prepared = self.run_prepare([(name, body) for name, body in members.items()],
                                    key_file, 'c')
        rows = [line.split('\t') for line in prepared['shader_map.tsv'].decode().splitlines()
                if line and not line.startswith('#')]
        self.assertTrue(rows)
        for row in rows:
            self.assertTrue(row[4].startswith('shader#') or row[4].startswith('shaderboot#'), row[4])
        self.assertEqual({row[2] for row in rows}, {'vertex', 'pixel', 'compute'})


@unittest.skipUnless(os.environ.get('FIFA23_XCI') and os.environ.get('FIFA23_KEYS')
                     and os.environ.get('FIFA23_EASF_KEYS'),
                     'set FIFA23_XCI, FIFA23_KEYS and FIFA23_EASF_KEYS to check the real image')
class RealImage(unittest.TestCase):
    """The same code against the retail gamecard; the profile tables are the oracle."""
    @classmethod
    def setUpClass(cls):
        if not (HERE / 'build').is_dir():
            (HERE / 'build').mkdir()
        cls.tmp = tempfile.TemporaryDirectory(prefix='fifa-real-', dir=HERE / 'build')
        cls.root = Path(cls.tmp.name)
        cls.library = build_library(cls.root / 'reader.dylib')
        cls.out = cls.root / 'out'

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def image(self, update=None):
        return ResourceFS(self.library, base=os.environ['FIFA23_XCI'], update=update,
                          keys=os.environ['FIFA23_KEYS'], title=int(GAME, 16))

    def check(self, update=None):
        with self.image(update) as fs:
            archives = [(Path(name).name,
                         nximage.member(fs, DATAX, name)) for name in MEMBERS]
        # The build copies the profile inputs beside the output first; the pair
        # supplement is part of the package, so prepare must see it here too.
        profile = self.out / 'profile'
        profile.mkdir(parents=True, exist_ok=True)
        extra = REPO / 'dm/games' / GAME / 'shader_pairs_extra.tsv'
        if extra.exists():
            (profile / extra.name).write_bytes(extra.read_bytes())
        prepare.prepare(archives, self.out / 'pkg', profile, os.environ['FIFA23_EASF_KEYS'])
        rows = [line.split('\t') for line in
                (profile / 'shader_map.tsv').read_text().splitlines()
                if line and not line.startswith('#')]
        self.assertEqual(len(rows), 386)
        self.assertEqual({row[2] for row in rows}, {'vertex', 'pixel', 'compute'})
        for name in ('shader_map.tsv', 'shader_pairs.tsv', 'shader_facts.tsv'):
            self.assertEqual((profile / name).read_bytes(),
                             (REPO / 'dm/games' / GAME / name).read_bytes(), name)
        for name in ('vs_fifa.bin', 'ps_fifa.bin', 'cs_fifa.bin'):
            self.assertTrue((self.out / 'pkg' / name).is_file(), name)

    def test_gamecard_alone(self):
        self.check()

    def test_gamecard_with_the_update_laid_over_it(self):
        if not os.environ.get('FIFA23_UPDATE'):
            self.skipTest('set FIFA23_UPDATE to the matching update NSP')
        self.check(os.environ['FIFA23_UPDATE'])


if __name__ == '__main__':
    if not (HERE / 'build').is_dir():
        (HERE / 'build').mkdir()
    unittest.main()
