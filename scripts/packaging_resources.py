#!/usr/bin/env python3
"""Stream Directory-mode resources into the current task only."""
import argparse
from pathlib import Path
import shutil
import sys
import json
import subprocess

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.nxrom.resourcefs import ResourceFS


def extract(fs, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    for entry in fs.files():
        relative = Path(entry.path)
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('Unsafe resource entry path')
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        with fs.open(entry.path) as source, target.open('xb') as dest:
            shutil.copyfileobj(source, dest, 1024 * 1024)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dlc-request', type=Path)
    for name in ('library', 'base', 'keys', 'update', 'title', 'output'):
        p.add_argument('--' + name)
    a = p.parse_args()
    if a.dlc_request:
        from tools.packaging_gui import dlc, automatic
        request = json.loads(a.dlc_request.read_text())
        dlc.prepare_inputs(request['library'], request['dlcs'], request['keys'],
                                      int(request['game'], 16), request['application_version'])
        dlc.extract(request['dlcs'], request['aoc'], automatic.extractor_command() + [request['keys']],
                    lambda argv: subprocess.run(argv, check=True))
        dlc.audit_tree(request['aoc'], int(request['game'], 16))
        return
    if not all(getattr(a, name) is not None for name in ('library', 'base', 'keys', 'update', 'title', 'output')):
        p.error('all resource arguments are required')
    with ResourceFS(a.library, base=a.base, keys=a.keys, update=a.update or None,
                    title=int(a.title, 16)) as fs:
        extract(fs, a.output)


if __name__ == '__main__':
    main()
