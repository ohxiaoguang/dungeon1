"""Folder inputs for the existing packager; native reader owns all identities."""
import ctypes as C
import os
from pathlib import Path


def candidates(root):
    seen = set()
    root = Path(root)
    scanned = 0
    for directory, dirs, files in os.walk(root, followlinks=False):
        here = Path(directory)
        if len(here.relative_to(root).parts) > 64:
            raise ValueError('Resource folder nesting exceeds 64 levels')
        dirs[:] = sorted(d for d in dirs if not (here / d).is_symlink()
                         and not d.endswith(('.app', '_build', '-work')) and d not in ('.git', 'NXPackagingCache'))
        for name in sorted(files):
            scanned += 1
            if scanned > 200000:
                raise ValueError('Resource folder exceeds 200000 files; choose a narrower folder')
            p = here / name
            if p.is_symlink() or p.suffix.lower() not in ('.nsp', '.xci', '.nsz', '.xcz', '.ncz'):
                continue
            st = p.stat()
            identity = (st.st_dev, st.st_ino)
            if identity not in seen:
                seen.add(identity)
                yield p


def probe(library, path, keys):
    lib = C.CDLL(str(library), use_errno=True)
    lib.nxrom_probe_container.argtypes = [C.c_char_p, C.c_char_p, C.POINTER(C.c_int), C.POINTER(C.c_int),
                                         C.POINTER(C.c_int), C.POINTER(C.c_uint64), C.c_char_p, C.c_size_t]
    fmt, programs, patched, title = C.c_int(), C.c_int(), C.c_int(), C.c_uint64()
    error = C.create_string_buffer(512)
    if lib.nxrom_probe_container(os.fsencode(path), os.fsencode(keys), C.byref(fmt), C.byref(programs),
                                 C.byref(patched), C.byref(title), error, len(error)):
        raise OSError(C.get_errno(), error.value.decode(), str(path))
    return dict(title=title.value, patched=bool(patched.value))


def resolve(request):
    """A folder in the base field needs one unambiguous registered base/update.

    Existing explicit-file selections retain their program-version rules. No
    Profile is synthesized. Unknown files are diagnosed by DLC preflight.
    """
    from dataclasses import replace
    from tools.packaging_gui import registry
    root = Path(request.base)
    if not root.is_dir():
        return request
    bases, updates = [], []
    for p in candidates(root):
        try:
            facts = probe(request.library, p, request.keys)
        except OSError:
            continue
        if facts['patched']:
            updates.append((p, facts))
        else:
            bases.append((p, facts))
    if len(bases) != 1:
        raise ValueError('Resource folder needs exactly one base game; found ' + str(len(bases)) +
                         '. Narrow the folder or use the existing explicit base selection.')
    base, facts = bases[0]
    if registry.by_title(facts['title']) is None:
        raise ValueError('Resource folder base has no registered Profile: ' + format(facts['title'], '016X'))
    matching = [p for p, f in updates if f['title'] in (facts['title'], facts['title'] + 0x800)]
    if request.update:
        update = request.update
    elif len(matching) > 1:
        raise ValueError('Resource folder contains conflicting updates; choose the required update explicitly')
    else:
        update = str(matching[0]) if matching else ''
    return replace(request, base=str(base), update=update, resource_folder=str(root),
                   output=request.output or str(root))
