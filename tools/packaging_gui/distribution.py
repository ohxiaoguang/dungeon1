"""Build the minimal source/tool payload and a relocatable Python runtime.

Only the redistributor runs this module. End users never select an interpreter,
checkout, reader or extractor. No game input or game-derived cache is copied.
"""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys


def source_files(repo):
    tracked = subprocess.check_output(['git', 'ls-files', '-z'], cwd=repo).decode().split('\0')
    # dm is the compiler's source dependency graph (C/ObjC/Swift, profiles,
    # translator and vendored runtime sources). Tests and documentation are not
    # needed. Only four user-facing Python entry points are distributed.
    scripts = {'packaging_gui.py', 'packaging_supervisor.py', 'packaging_shaders.py',
               'packaging_resources.py', 'build_mac_app.py'}
    names = set(tracked) | {'scripts/packaging_shaders.py', 'scripts/packaging_resources.py'}
    names |= {p.relative_to(repo).as_posix() for p in (repo / 'tools/packaging_gui').glob('*.py')}
    for name in sorted(names):
        if not name:
            continue
        parts = Path(name).parts
        if any(p in ('tests', '__pycache__', 'bin', 'obj') for p in parts):
            continue
        if (parts[0] == 'dm' and not name.endswith('.md')
                or name.startswith('tools/packaging_gui/')
                or name.startswith('tools/nxrom/') and name.endswith('.py')
                or name in ('tools/__init__.py', 'LICENSE', 'gui/Sources/PackagingModel/Localization.swift')
                or parts[0] == 'scripts' and Path(name).name in scripts):
            yield name
    # Legal notices are kept even though other Markdown documents are omitted.
    for p in (repo / 'dm/third_party').rglob('*'):
        if p.is_file() and p.name.upper().startswith(('LICENSE', 'COPYING', 'NOTICE')):
            yield p.relative_to(repo).as_posix()


def python_runtime(python, destination, extra_sites=()):
    info = json.loads(subprocess.check_output([str(python), '-c',
        'import json,sys,sysconfig;print(json.dumps(dict(prefix=sys.base_prefix,version=sysconfig.get_python_version(),site=sysconfig.get_path("purelib"))))']))
    prefix = Path(info['prefix'])
    version = info['version']
    library = prefix / 'lib' / ('libpython' + version + '.dylib')
    if not library.is_file():
        raise ValueError('Supply a relocatable CPython standalone installation with lib/libpython*.dylib')
    (destination / 'bin').mkdir(parents=True)
    shutil.copy2(prefix / 'bin' / ('python' + version), destination / 'bin/python3')
    (destination / 'lib').mkdir()
    for p in (prefix / 'lib').glob('*.dylib'):
        shutil.copy2(p, destination / 'lib' / p.name)
    stdlib = destination / 'lib' / ('python' + version)
    shutil.copytree(prefix / 'lib' / ('python' + version), stdlib,
                    ignore=shutil.ignore_patterns('site-packages', '__pycache__', 'test', 'tests', 'idlelib',
                                                 'tkinter', 'ensurepip', 'turtledemo'))
    site = stdlib / 'site-packages'
    site.mkdir()
    # Copy only build dependencies and their distribution metadata/licenses.
    required = ('capstone', 'lz4', 'fontTools', 'Crypto', 'backports')
    sites = [Path(info['site']), *map(Path, extra_sites), prefix / 'lib' / ('python' + version) / 'site-packages']
    for name in required:
        source = next((p / name for p in sites if (p / name).is_dir()), None)
        if source is None:
            raise ValueError('Missing redistributable Python dependency: ' + name)
        shutil.copytree(source, site / name, ignore=shutil.ignore_patterns('__pycache__', 'test', 'tests'))
        distribution = {'fontTools': 'fonttools', 'Crypto': 'pycryptodome', 'backports': 'backports_zstd'}.get(name, name)
        for metadata in source.parent.glob(distribution + '-*.dist-info'):
            shutil.copytree(metadata, site / metadata.name)
    subprocess.run([str(destination / 'bin/python3'), '-I', '-B', '-c',
        'import capstone,lz4.block,fontTools,Crypto.Cipher.AES;from backports import zstd;print("Bundled Python dependencies verified")'],
        cwd=destination, check=True)


def bundle(repo, resources, python, build, extra_sites=()):
    payload = resources / 'Packaging'
    payload.mkdir(parents=True)
    for name in set(source_files(repo)):
        source = repo / name
        if source.is_symlink():
            raise ValueError('Source payload cannot contain a symlink: ' + name)
        target = payload / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    from tools.packaging_gui.registry import write_index
    write_index(payload / 'games.json')
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
    (payload / 'release.json').write_text(json.dumps(dict(schema=1, revision=revision,
        dirty=bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=repo)),
        external_tools=['Xcode and Metal toolchain', 'XcodeGen', '.NET 10', 'SPIRV-Cross', 'zstd'])))
    from tools.nxrom.resourcefs import build_library
    (payload / 'bin').mkdir()
    build_library(payload / 'bin/nxrom.dylib')
    env = dict(__import__('os').environ, DOTNET_CLI_HOME=str(build / 'dotnet-home'),
               NUGET_PACKAGES=str(Path.home() / '.nuget/packages'))
    subprocess.run(['dotnet', 'publish', str(repo / 'dm/tools/nx_extract/nx_extract.csproj'),
                    '-c', 'Release', '-o', str(payload / 'bin/nx_extract'),
                    '-p:BaseIntermediateOutputPath=' + str(build / 'extract-obj') + '/',
                    '-p:BaseOutputPath=' + str(build / 'extract-bin') + '/',
                    '-p:UseAppHost=false', '-p:UseSharedCompilation=false',
                    '-p:NuGetAudit=false', '-nodeReuse:false'], env=env, check=True)
    python_runtime(python, resources / 'Python', extra_sites)
    inventory = {p.relative_to(resources).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in resources.rglob('*') if p.is_file()}
    (resources / 'inventory.json').write_text(json.dumps(inventory, sort_keys=True))
    subprocess.run([str(resources / 'Python/bin/python3'), '-I', '-B', str(payload / 'scripts/packaging_gui.py'),
                    'games', '--games-index', str(payload / 'games.json')],
                   cwd=build, stdout=subprocess.DEVNULL, check=True)
    return payload
