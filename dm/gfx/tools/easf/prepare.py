#!/usr/bin/env python3
"""Prepare standard nxnative packages and tables from local EA shader archives.

BIG4, chunkzip, or EASF inputs are accepted. An EASF key is taken from the
private JSON key file when one is given, and otherwise discovered in the game's
own program module (easf/keyfind.py): either source is confirmed against the
container's header digest before it is used. No key is bundled or logged.
Encrypted inputs require pycryptodome.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct

import big4
import chunkzip
import export
import fxo
import keyfind


def decode_archive(name, data, key_file=None, keys=None):
    """Decode one archive held in memory; `name` only labels its source records.

    Accepts the same three forms as read_archive (EASF, chunkzip, BIG4) so an
    archive that never touches the disk decodes exactly like a file does. The
    name must have the file's own basename semantics: archive_name below turns
    it into the source string, which orders shader_map.tsv.

    `keys` is a keyfind.Keyring: the private key file first, then keys found in
    the game's modules. Without one, a key file alone is wrapped in a Keyring.
    """
    data = bytes(data)
    if data.startswith(b'EASF'):
        from Crypto.Cipher import AES
        if len(data) < 48 or (len(data) - 48) % 16:
            raise ValueError('invalid EASF length')
        if keys is None:
            if not key_file:
                raise ValueError('EASF input requires --key-file or --module to discover the key from')
            keys = keyfind.Keyring(key_file=key_file)
        key, _ = keys.resolve(data)
        if not key:
            raise ValueError('no verified EASF key for ' + data[8:16].decode('ascii', 'replace').strip()
                             + ': pass --key-file (private, outside the repository) or a module to discover it from')
        size = struct.unpack_from('>I', data, 4)[0]
        plain = AES.new(key, AES.MODE_CBC, iv=key).decrypt(data[48:])
        if size > len(plain) or hashlib.sha256(plain[:32]).digest() != data[16:48]:
            raise ValueError('EASF plaintext verification failed')
        data = plain[:size]
    if data.startswith(b'chunkzip'):
        _, data, _ = chunkzip.decode(data)
    if not data.startswith(b'BIG4'):
        raise ValueError(f'expected a BIG4 shader archive after decoding: {name}')
    return data


def read_archive(path, key_file=None, keys=None):
    return decode_archive(Path(path).name, Path(path).read_bytes(), key_file, keys)


def archive_inputs(archives):
    """-> (name, bytes) for each input: a path reads the file, a pair is used as is.

    A pair lets a caller supply an archive that exists only inside a mounted
    image (nxrom / ResourceFS), where there is no file to open. The name keeps
    the file's basename, because it becomes the source string in shader_map.tsv.
    """
    for item in archives:
        if isinstance(item, (str, bytes, Path)):
            path = Path(item)
            yield path.name, path.read_bytes()
        else:
            name, data = item
            yield str(name), bytes(data)


def prepare(archives, pkg, profile, key_file=None, modules=(), bounded=False, keys=None):
    ring = keys if keys is not None else keyfind.Keyring(key_file=key_file, modules=modules, bounded=bounded)
    keys, pairs, facts = {}, set(), {}
    for archive_name, raw in archive_inputs(archives):
        data = decode_archive(archive_name, raw, keys=ring)
        for offset, size, name in big4.parse(data)['entries']:
            if offset + size > len(data):
                raise ValueError('BIG4 entry exceeds archive')
            programs = fxo.programs(data[offset:offset + size])
            for st, key, ctl, code, off in programs:
                stem = Path(archive_name.removesuffix('.easf')).stem
                value = (f'{stem}#{name}@0x{off:x}', st, ctl, code)
                if key in keys and keys[key][1:] != value[1:]:
                    raise ValueError('shader hash collision')
                keys.setdefault(key, value)
                if st == 'cs':
                    local = list(struct.unpack_from('<3I', ctl, 0x748))
                    shared = struct.unpack_from('<I', ctl, 0x754)[0]
                    facts[key] = {'local': local, 'shared': (shared + 15) & ~15}
            pairs.update((v[1], p[1]) for v in programs if v[0] == 'vs'
                         for p in programs if p[0] == 'ps')
    # FXO programs are one stage each and the engine combines vertex and pixel per draw, across archive files
    # (observed live: combiner.fxo's vertex with glares.fxo's and hair_strand.fxo's pixel, vbeams.fxo's vertex with
    # hair_strand.fxo's -- each unseen pairing failed to link and its draws were dropped), like the single-stage
    # sources of shader_split.py (separable_pairs): every vertex is paired with a pixel cover, the fewest pixel
    # shaders whose read locations together cover all pixel inputs (SPH words 6-13, 8 bits per attribute), so
    # dmsh_build's vs_pad closes every vertex's outputs and any pairing links. The in-file pairs stay as evidence.
    ins = {k: {i for i in range(32) if struct.unpack_from('<I', v[3], 0x30 + 4 * (6 + (i >> 2)))[0] >> ((i & 3) * 8) & 0xff}
           for k, v in keys.items() if v[1] == 'ps'}
    left, cover = set().union(*ins.values()) if ins else set(), []
    while left:
        k = min(ins, key=lambda k: (-len(ins[k] & left), k)); cover.append(k); left -= ins[k]
    pairs.update((v, p) for v, vrec in keys.items() if vrec[1] == 'vs' for p in cover)
    # Runtime-observed pairs the archives cannot list (the engine recombines vertex / pixel programs at run time,
    # across archive files): rows of <profile>/shader_pairs_extra.tsv, vertex key TAB pixel key, '#' comments. They end
    # up in shader_pairs.tsv (part of the chain version) so dmsh_build's vs_pad gives the vertex the outputs these
    # pixel shaders read; without a row Metal refuses the pipeline and the host drops every such draw.
    extra = profile / 'shader_pairs_extra.tsv'
    if extra.exists():
        for ln in extra.read_text().splitlines():
            ln = ln.strip()
            if ln and not ln.startswith('#'):
                v, p = ln.split()
                pairs.add((v, p))
    if not keys:
        raise ValueError('no NXSHADER programs found')
    pkg.mkdir(parents=True, exist_ok=True)
    profile.mkdir(parents=True, exist_ok=True)
    export.write(keys, pkg, profile / 'shader_map.tsv')
    (profile / 'shader_map.tsv.conflicts.tsv').write_text('# No conflicting shader records.\n')
    (profile / 'shader_pairs.tsv').write_text('# kind: evidence  NXSHADER vertex / pixel pairs\n' +
        ''.join(f'{v}\t{p}\n' for v, p in sorted(pairs)))
    (profile / 'shader_facts.tsv').write_text('# Compute query answers from NXSHADER control sections\n' +
        ''.join(k + '\t' + json.dumps(v, sort_keys=True, separators=(',', ':')) + '\n'
                for k, v in sorted(facts.items())))
    print(f'Prepared {len(keys)} programs, {len(pairs)} pairs ({len(cover)} pixel cover), {len(facts)} compute facts')
    for note in dict.fromkeys(ring.notes):   # key-free: where a key came from, or why a source did not answer
        print(f'[note] {note}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archives', nargs='+', type=Path)
    parser.add_argument('--pkg', required=True, type=Path)
    parser.add_argument('--profile', required=True, type=Path)
    parser.add_argument('--key-file', type=Path, help='private JSON key file (used first)')
    parser.add_argument('--module', action='append', default=[], type=Path,
                        help='NSO0 module to discover the key from; repeatable')
    parser.add_argument('--bounded-scan', action='store_true',
                        help='also scan the module read-only segment when the key ID is not found verbatim')
    args = parser.parse_args()
    prepare(args.archives, args.pkg, args.profile, args.key_file, args.module, args.bounded_scan)
