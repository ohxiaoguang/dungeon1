from pathlib import Path

def write_program(exefs, profile, version):
    """Synthetic NSO headers carrying that version's build IDs, plus control.nacp."""
    exefs = Path(exefs)
    exefs.mkdir(parents=True, exist_ok=True)
    ids = profile.build_ids(version)
    for module in profile.modules:
        data = bytearray(0x60)
        data[:4] = b'NSO0'
        data[0x40:0x50] = bytes.fromhex(ids[module])
        (exefs / module).write_bytes(data)
    (exefs.parent / 'control.nacp').write_bytes(b'synthetic metadata')
    return exefs
