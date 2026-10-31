"""Owned cache namespace, cooperative leases and symlink-safe manual removal."""
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import shutil

NAMESPACE = 'NXPackagingGUI-v1'
OWNER = '.nxpackaging-owner.json'
KINDS = ('programs', 'shaders', 'tasks')


def namespace(folder):
    selected = Path(folder).expanduser()
    if not selected.is_absolute():
        raise ValueError('Cache folder must be absolute')
    selected.mkdir(parents=True, exist_ok=True)
    root = selected.resolve() / NAMESPACE
    if root.is_symlink():
        raise ValueError('Managed cache namespace cannot be a symbolic link')
    root.mkdir(exist_ok=True)
    marker = root / OWNER
    if not marker.exists():
        if any(root.iterdir()):
            raise ValueError('Existing cache namespace has no ownership marker; nothing was changed')
        with marker.open('x') as stream:
            json.dump({'owner': NAMESPACE, 'schema': 1}, stream)
    if marker.is_symlink() or json.loads(marker.read_text()) != {'owner': NAMESPACE, 'schema': 1}:
        raise ValueError('Invalid cache ownership marker')
    return root


@contextmanager
def lease(folder, *, exclusive=False):
    root = namespace(folder)
    fd = os.open(root / '.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(fd, (fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH) | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('Cache is in use by another task; try again after it finishes') from None
        yield root
    finally:
        os.close(fd)


def area(root, kind):
    if kind not in KINDS:
        raise ValueError('Unknown managed cache area')
    target = root / kind
    if target.is_symlink():
        raise ValueError('Cache area cannot be a symbolic link')
    target.mkdir(exist_ok=True)
    return target


def usage(root):
    total = 0
    for target in owned_entries(root):
        for parent, dirs, files in os.walk(target, followlinks=False):
            dirs[:] = [name for name in dirs if not (Path(parent) / name).is_symlink()]
            total += sum((Path(parent) / name).lstat().st_size for name in files
                         if not (Path(parent) / name).is_symlink())
    return total


def owned_entries(root):
    """Recognize entries we created; unrelated siblings are never cache data."""
    for kind in KINDS:
        parent = root / kind
        if parent.is_symlink() or not parent.is_dir():
            continue
        for entry in parent.iterdir():
            if entry.is_symlink() or not entry.is_dir():
                continue
            marker = entry / OWNER
            try:
                if not marker.is_symlink() and json.loads(marker.read_text()) == {'owner': NAMESPACE, 'schema': 1}:
                    yield entry
                    continue
            except (OSError, ValueError):
                pass
            if kind == 'tasks' and entry.name.startswith('gui-task-'):
                record = entry / 'result.json'
                try:
                    state = json.loads(record.read_text()) if not record.is_symlink() else {}
                    if state.get('taskDirectory') == str(entry) and state.get('state') not in ('starting', 'running', 'cancelling'):
                        yield entry
                except (OSError, ValueError):
                    pass


def status(folder):
    with lease(folder) as root:
        return {'bytes': usage(root), 'path': str(root)}


def clear(folder, expected_bytes):
    """The UI confirms the measured bytes. Never remove the chosen folder itself.

    rmtree's fd-based implementation does not follow links within a tree. A
    top-level link is refused, and arbitrary siblings of our namespace survive.
    """
    with lease(folder, exclusive=True) as root:
        if usage(root) != expected_bytes:
            raise ValueError('Cache size changed; measure and confirm again')
        for kind in KINDS:
            target = root / kind
            if target.is_symlink():
                raise ValueError('Cache area is a symbolic link; nothing was removed')
        for target in list(owned_entries(root)):
            shutil.rmtree(target)
        return {'bytes': 0, 'removed_bytes': expected_bytes, 'path': str(root)}
