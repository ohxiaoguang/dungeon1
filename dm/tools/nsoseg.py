#!/usr/bin/env python3
"""NSO0 segments: header parsing, decompression and integrity, shared by every tool here.

A Switch module is an NSO0 header (0x100 bytes) followed by three segments: .text, .rodata
and .data. Each is stored raw, LZ4-compressed (flags bits 0-2) or - since the 22.0.0 SDK -
ZBIC-compressed (flags bit 7, "UseZbicCompression"). ZBIC is zstd with Nintendo's binary
interpolative coding of the entropy tables and the frame magic 0x4349425A, so stock zstd and
lz4 both refuse it; dm/tools/zbic/ carries a BSD-licensed decompressor for it, built on first
use (see _zbic_library).

Bits 3-5 say the header holds the SHA-256 of the decompressed segment; when they are set this
module checks them, so a decoder bug or a corrupt container fails loudly instead of feeding
garbage to a rewriter. Unknown flag bits, truncated segments, sizes that disagree with the
header and unsupported compression all raise NsoError.

    header = nsoseg.parse(open(path,'rb').read())
    img, build_id, sizes, bss = nsoseg.load(path)      # the image the loaders and rewriters use
"""
import ctypes
import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
import struct
import subprocess
import tempfile
import threading

MAGIC = b'NSO0'
HEADER_SIZE = 0x100
FLAG_COMPRESSED = 0b00000111          # bits 0-2: .text, .rodata, .data are compressed
FLAG_HASH = 0b00111000                # bits 3-5: the header holds that segment's SHA-256
FLAG_EXECUTE_ONLY = 0x40              # bit 6, 20.0.0+: code pages are not readable
FLAG_ZBIC = 0x80                      # bit 7, 22.0.0+: compressed segments use ZBIC, not LZ4
KNOWN_FLAGS = 0xFF
SEGMENT_LIMIT = 2 << 30               # one segment, the same cap the C decoder applies
IMAGE_LIMIT = 4 << 30                 # .text + .rodata + .data (bss is not held in the image)
CHUNK = 1 << 20


class NsoError(ValueError):
    """An NSO this reader refuses: bad header, truncated data, failed decode or hash mismatch."""


@dataclass(frozen=True)
class Segment:
    index: int
    file_offset: int
    memory_offset: int
    size: int                  # decompressed size, as the header declares it
    file_size: int             # bytes stored in the container
    compressed: bool
    zbic: bool
    sha256: bytes              # the header's hash, or None when it is not declared valid

    @property
    def compression(self):
        return ('zbic' if self.zbic else 'lz4') if self.compressed else 'raw'

    @property
    def name(self):
        return ('text', 'rodata', 'data')[self.index]


@dataclass(frozen=True)
class Header:
    flags: int
    segments: tuple
    bss: int
    build_id: bytes            # 0x40..0x60: the 32-byte module ID, of which the first 16 are the Build ID
    module_name: str
    image_size: int

    @property
    def execute_only(self):
        return bool(self.flags & FLAG_EXECUTE_ONLY)

    @property
    def compression(self):
        """'raw', 'lz4' or 'zbic' for the module as a whole (the strongest one used)."""
        kinds = {s.compression for s in self.segments}
        return 'zbic' if 'zbic' in kinds else 'lz4' if 'lz4' in kinds else 'raw'


def parse(data, verify_layout=True):
    """The NSO0 header of `data`. Raises NsoError for anything this reader cannot trust."""
    if len(data) < HEADER_SIZE:
        raise NsoError(f'not an NSO: {len(data)} bytes is shorter than the 0x100-byte header')
    if data[:4] != MAGIC:
        raise NsoError(f'not an NSO: magic is {data[:4]!r}, not {MAGIC!r}')
    flags = struct.unpack_from('<I', data, 0x0C)[0]
    if flags & ~KNOWN_FLAGS:
        raise NsoError(f'unknown NSO flag bits in {flags:#010x}: this reader knows {KNOWN_FLAGS:#04x}')
    zbic = bool(flags & FLAG_ZBIC)
    raw = [struct.unpack_from('<III', data, 0x10 + i * 16) for i in range(3)]   # (file, memory, size)
    stored = struct.unpack_from('<III', data, 0x60)
    bss = struct.unpack_from('<I', data, 0x3C)[0]
    segments = []
    for i, (file_offset, memory_offset, size) in enumerate(raw):
        compressed = bool(flags >> i & 1)
        file_size = stored[i] if compressed else size
        if size == 0:
            raise NsoError(f'segment {i} ({("text", "rodata", "data")[i]}) has no size')
        if size > SEGMENT_LIMIT:
            raise NsoError(f'segment {i} declares {size:#x} bytes, over the {SEGMENT_LIMIT:#x} limit')
        if compressed and file_size == 0:
            raise NsoError(f'segment {i} is marked compressed but stores no bytes')
        if file_offset + file_size > len(data):
            raise NsoError(f'segment {i} runs past the file: {file_size:#x} bytes at {file_offset:#x} '
                           f'of {len(data):#x} (truncated container)')
        hashed = bool(flags >> (3 + i) & 1)
        segments.append(Segment(i, file_offset, memory_offset, size, file_size, compressed, zbic and compressed,
                                bytes(data[0xA0 + i * 0x20:0xA0 + (i + 1) * 0x20]) if hashed else None))
    image_size = max(s.memory_offset + s.size for s in segments)
    if image_size > IMAGE_LIMIT:
        raise NsoError(f'the image would span {image_size:#x} bytes, over the {IMAGE_LIMIT:#x} limit')
    if verify_layout:
        for s in segments:
            if s.memory_offset + s.size > image_size:
                raise NsoError(f'segment {s.index} lies outside the image')
        ordered = sorted(segments, key=lambda s: s.memory_offset)
        for a, b in zip(ordered, ordered[1:]):
            if a.memory_offset + a.size > b.memory_offset:
                raise NsoError(f'segments {a.index} and {b.index} overlap in memory')
    # The module name sits at 0x100 and is empty in most titles ("Darkest", "nnSdk", "opengl"
    # in 22.0.0 ones); its size is at 0x2C. A malformed size is ignored rather than fatal: no
    # caller depends on the name, and the segments above are already validated.
    name_size = struct.unpack_from('<I', data, 0x2C)[0]
    name = b''
    if 0 < name_size <= 0x200 and HEADER_SIZE + name_size <= len(data):
        name = data[HEADER_SIZE:HEADER_SIZE + name_size].split(b'\0')[0]
    return Header(flags, tuple(segments), bss, bytes(data[0x40:0x60]), name.decode('utf-8', 'replace'), image_size)


def decode(data, header, index):
    """One segment's decompressed bytes, checked against the declared size and, when the header
    declares one, its SHA-256."""
    segment = header.segments[index]
    stored = data[segment.file_offset:segment.file_offset + segment.file_size]
    if not segment.compressed:
        out = bytes(stored)
    elif segment.zbic:
        out = _zbic(stored, segment.size, index)
    else:
        try:
            import lz4.block
            out = lz4.block.decompress(bytes(stored), uncompressed_size=segment.size)
        except Exception as exc:   # lz4.block raises LZ4BlockError; never let it look like success
            raise NsoError(f'segment {index} ({segment.name}): LZ4 decode failed: {exc}') from exc
    if len(out) != segment.size:
        raise NsoError(f'segment {index} ({segment.name}): decoded {len(out)} bytes, header declares {segment.size}')
    if segment.sha256 is not None:
        digest = hashlib.sha256(out).digest()
        if digest != segment.sha256:
            raise NsoError(f'segment {index} ({segment.name}): SHA-256 {digest.hex()} does not match the header\'s '
                           f'{segment.sha256.hex()} (corrupt container or a decoder that cannot be trusted)')
    return out


def image(data, header=None, bss=False):
    """(the loaded image, header). The image covers .text/.rodata/.data; with bss=True it is
    extended with the zero pages the module's .bss occupies, as nso.py and nso_syms.py expect."""
    header = header or parse(data)
    total = header.image_size + (header.bss if bss else 0)
    if total > IMAGE_LIMIT:
        raise NsoError(f'the image with bss would span {total:#x} bytes, over the {IMAGE_LIMIT:#x} limit')
    out = bytearray(total)
    for segment in header.segments:
        out[segment.memory_offset:segment.memory_offset + segment.size] = decode(data, header, segment.index)
    return bytes(out), header


def load(path, bss=True):
    """(image, build id hex, [segment sizes], bss) for a module file - the tuple every tool here
    used to assemble by hand."""
    data = Path(path).read_bytes()
    img, header = image(data, bss=bss)
    return img, header.build_id[:16].hex(), [s.size for s in header.segments], header.bss


def _zbic(stored, size, index):
    """ZBIC: one frame per segment, decoded by the vendored zstd variant bound below."""
    lib = _zbic_library()
    out = ctypes.create_string_buffer(size)          # exact capacity: a longer stream fails inside zstd
    error = ctypes.create_string_buffer(256)
    produced = ctypes.c_size_t(0)
    status = lib.zbic_decompress(out, ctypes.c_size_t(size), stored, ctypes.c_size_t(len(stored)),
                                 ctypes.byref(produced), error, ctypes.c_size_t(len(error)))
    if status:
        raise NsoError(f'segment {index} ({("text", "rodata", "data")[index]}): ZBIC decode failed: '
                       f'{error.value.decode("utf-8", "replace")}')
    return out.raw[:produced.value]


_LIB = None
_LIB_LOCK = threading.Lock()
_HERE = Path(__file__).resolve().parent
_SOURCES = (_HERE / 'zbic' / 'zbic.c', _HERE / 'zbic' / 'zbicdeclib.inc')


def _fingerprint():
    digest = hashlib.sha256()
    for source in _SOURCES:
        digest.update(source.read_bytes())
    return digest.hexdigest()[:16]


def _cache_dir():
    """Where the decoder is built and kept: NXNSO_CACHE, else a directory under the system's
    temporary directory (never HOME, never the repository)."""
    override = os.environ.get('NXNSO_CACHE')
    path = Path(override).expanduser() if override else Path(tempfile.gettempdir()) / 'nxnative-nso'
    path.mkdir(parents=True, exist_ok=True)
    return path


def _zbic_library():
    """The ZBIC decoder, built with the platform toolchain on first use and cached by content
    fingerprint. Only modules that really carry a ZBIC segment pay for this."""
    global _LIB
    if _LIB is not None:
        return _LIB
    with _LIB_LOCK:
        if _LIB is not None:
            return _LIB
        for source in _SOURCES:
            if not source.is_file():
                raise NsoError(f'ZBIC decoder source is missing: {source}')
        try:
            cached = _cache_dir() / f'libzbic-{_fingerprint()}.dylib'
        except OSError as exc:
            raise NsoError(f'ZBIC decoder: no writable cache directory ({exc}); set NXNSO_CACHE') from exc
        if not cached.is_file():
            target = cached.with_name(cached.name + f'.{os.getpid()}.tmp')
            command = ['xcrun', 'clang', '-dynamiclib', '-O2', '-w', '-I', str(_SOURCES[0].parent),
                       str(_SOURCES[0]), '-Wl,-install_name,@rpath/libzbic.dylib', '-o', str(target)]
            result = subprocess.run(command, capture_output=True, text=True)
            if result.returncode:
                target.unlink(missing_ok=True)
                raise NsoError('ZBIC decoder could not be built (a ZBIC NSO needs the Metal/Xcode command line '
                               'tools for its decompressor): ' + (result.stderr.strip() or 'xcrun clang failed'))
            os.replace(target, cached)
        lib = ctypes.CDLL(str(cached))
        lib.zbic_decompress.restype = ctypes.c_int
        lib.zbic_decompress.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_char_p, ctypes.c_size_t,
                                        ctypes.POINTER(ctypes.c_size_t), ctypes.c_char_p, ctypes.c_size_t]
        _LIB = lib
        return _LIB


def describe(header, build_id=None):
    """One line for logs and reports: what the header says and how each segment is stored."""
    parts = []
    for s in header.segments:
        parts.append(f'{s.name} {s.size} B {s.compression}'
                     + (f' ({s.file_size} B stored)' if s.compressed else ''))
    return (f'flags {header.flags:#04x} ({"zbic" if header.flags & FLAG_ZBIC else "lz4/raw"}'
            f'{", execute-only" if header.execute_only else ""}), '
            + ', '.join(parts) + f', bss {header.bss:#x}'
            + (f', build id {build_id}' if build_id else ''))
