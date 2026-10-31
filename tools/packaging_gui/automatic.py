"""Resolve user selections into the existing engine's verified build inputs."""
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import uuid

from tools.packaging_gui import cache, engine, games, registry
from tools.nxrom.resourcefs import ResourceFS
from tools.nxrom.shader_package import digest


def file_identity(value):
    p = engine.path(value)
    st = p.stat()
    return [str(p), st.st_size, st.st_mtime_ns, st.st_dev, st.st_ino]


def mounted_version(fs, profile):
    for version, _, ids in profile.versions:
        try:
            for module in profile.modules:
                fs.check_build(module, ids[module])
            return version
        except OSError:
            continue
    raise ValueError(profile.name + ' has no registered program version matching the selected '
                     'base/update modules. Registered versions: ' + ', '.join(
                         v + ' / ' + display for v, display, _ in profile.versions))


def extractor_command():
    dll = engine.REPO / 'bin/nx_extract/nx_extract.dll'
    if not dll.is_file():
        raise ValueError('Bundled program extractor is missing; rebuild NXPackagingGUI.app')
    dotnet = shutil.which('dotnet')
    if not dotnet:
        raise ValueError('Program extraction requires an installed .NET 10 runtime (dotnet)')
    return [dotnet, str(dll)]


def control_version(folder, profile, version):
    data = (folder / 'control.nacp').read_bytes()
    if len(data) < 0x3070:
        raise ValueError('Invalid or truncated control.nacp')
    display = data[0x3060:0x3070].split(b'\0', 1)[0].decode('utf-8').strip()
    expected = profile.display_of(version)
    if display != expected:
        raise ValueError('Selected package display version ' + display + ' differs from registered '
                         + expected + ' (' + version + '), although its code Build IDs match. '
                         'This package version is not registered; no version was substituted.')
    return display


def program(request, root, profile, version):
    source = dict(base=file_identity(request.base), update=file_identity(request.update) if request.update else None,
                  keys=file_identity(request.keys), profile=digest(profile.table('game.tsv')),
                  extractor=digest(engine.REPO / 'bin/nx_extract/nx_extract.dll'))
    ident = hashlib.sha256(json.dumps(source, sort_keys=True).encode()).hexdigest()[:24]
    parent = cache.area(root, 'programs')
    folder = parent / (profile.key + '-' + ident)
    if folder.is_symlink():
        raise ValueError('Program cache cannot be a symbolic link')
    for candidate in sorted(parent.glob(folder.name + '*')):
        if candidate.is_symlink():
            continue
        ready = candidate / 'ready.json'
        try:
            if ready.is_symlink():
                continue
            saved = json.loads(ready.read_text())
            from tools.nxrom.prepared_build import checked_files
            files = dict(saved['files'], **{'ready.json': digest(ready)})
            checked_files(candidate, files)
            if saved['source'] == source and engine.detect_program(profile, candidate / 'ExeFS')[0] == version:
                control_version(candidate, profile, version)
                print('Verified program cache reused: ' + profile.key, flush=True)
                return candidate
        except (OSError, ValueError, KeyError):
            continue
    # Never overwrite an existing entry, including a damaged earlier cache.
    fresh = parent / (profile.key + '-' + ident + '-' + uuid.uuid4().hex[:10])
    fresh.mkdir()
    (fresh / cache.OWNER).write_text(json.dumps({'owner': cache.NAMESPACE, 'schema': 1}))
    try:
        print('@@NX_STAGE@@prepare-program', flush=True)
        cmd = extractor_command() + [request.keys, request.base, request.update or '-', str(fresh), '--program-only']
        subprocess.run(cmd, check=True)
        if (fresh / 'RomFS').exists():
            raise ValueError('Program-only extraction unexpectedly wrote RomFS')
        if engine.detect_program(profile, fresh / 'ExeFS')[0] != version:
            raise ValueError('Extracted program version differs from the selected container')
        if not (fresh / 'control.nacp').is_file():
            raise ValueError('Selected game has no control metadata')
        control_version(fresh, profile, version)
        files = {p.relative_to(fresh).as_posix(): digest(p) for p in fresh.rglob('*') if p.is_file()}
        (fresh / 'ready.json').write_text(json.dumps(dict(source=source, files=files), sort_keys=True))
        if not folder.exists():
            fresh.rename(folder)
            return folder
        return fresh
    except BaseException:
        shutil.rmtree(fresh)
        raise


def shader_slot(request, root, profile):
    from tools.packaging_gui import shader_sources
    source = shader_sources.for_profile(profile)
    if source.needs_chain:
        chain = engine.chain_tools()
        identity = dict(game=profile.key, source_versions=profile.shader_versions,
                        chain=chain.version(), inputs=chain.inputs(profile.game()))
    else:
        identity = dict(game=profile.key, source_versions=profile.shader_versions,
                        provider=source.key, capture=digest(profile.table('gl_capture.tsv')))
    key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:24]
    parent = cache.area(root, 'shaders')
    legacy = Path(request.cache_root)
    candidates = ([legacy] if (legacy / 'profile' / profile.key).is_dir() else [])
    candidates += sorted(parent.glob(profile.key + '-' + key + '*'))
    for folder in candidates:
        if folder.is_symlink():
            continue
        candidate = replace(request, cache=str(folder), shader_action='reuse')
        try:
            engine.validate_cache(candidate, profile)
            print('Verified Shader cache reused for ' + request.target + ': ' + profile.key, flush=True)
            return candidate
        except (OSError, ValueError, KeyError, IndexError) as exc:
            print('Shader cache incompatible; retained unchanged: ' + str(exc), flush=True)
    fresh = parent / (profile.key + '-' + key)
    if fresh.exists() or fresh.is_symlink():
        fresh = parent / (fresh.name + '-' + uuid.uuid4().hex[:10])
    return replace(request, cache=str(fresh), shader_action='generate')


def resolve(request, shader_selection=None):
    """Called under a cache lease by check and execute, never writes the Bundle."""
    root = cache.namespace(request.cache_root)
    cache.area(root, 'tasks')
    library = request.library or str(engine.REPO / 'bin/nxrom.dylib')
    request = replace(request, library=library)
    from tools.packaging_gui import folder, dlc
    request = folder.resolve(request)
    with ResourceFS(library, base=request.base, update=request.update or None, keys=request.keys) as fs:
        found = games.describe(fs.title)
        if not found['ok']:
            raise ValueError(found['message'])
        profile = registry.by_key(found['game'])
        gap = engine.capabilities.gap(profile, request.target)
        if gap:
            raise ValueError(gap)
        version = mounted_version(fs, profile)
        if request.mode == 'directory':
            request.resource_bytes = sum(entry.size for entry in fs.files())
    extracted = program(request, root, profile, version)
    # Discover beside an explicit base as well as inside a selected folder. The
    # exact list and source hashes travel in the existing approval fingerprint.
    report = dlc.discover(library, request.resource_folder or Path(request.base).parent,
                          request.keys, profile.title_id, int(version.removeprefix('v')))
    if report['errors']:
        raise ValueError('; '.join(report['errors']))
    if report['dlcs']:
        selected = dlc.metadata(library, request.update or request.base, request.keys)
        if (selected['type'] not in (0x80, 0x81) or selected['application'] != profile.title_id
                or selected['version'] != int(version.removeprefix('v'))):
            raise ValueError('Selected application CNMT does not match the registered program version for DLC')
    if request.mode == 'directory':
        dlc.prepare_inputs(library, report['dlcs'], request.keys,
                                       profile.title_id, int(version.removeprefix('v')))
        request = replace(request, dlcs=tuple(report['dlcs']), dlc_warnings=tuple(report['warnings']),
                          aoc=str(Path(request.task_work) / 'resources/aoc') if report['dlcs'] else '')
    elif report['dlcs']:
        request = replace(request, dlc_warnings=tuple(report['warnings']) +
                          ('External mode: import DLC NSPs into the game resource folder after installation.',))
    request = replace(request, game=profile.key, exefs=str(extracted / 'ExeFS'),
                      output=request.output or str(Path(request.base).resolve().parent))
    if request.mode == 'directory':
        # RomFS extraction is a build stage, after the user confirms its size.
        request.romfs = str(Path(request.task_work) / 'resources/RomFS')
    if shader_selection:
        return replace(request, cache=shader_selection[0], shader_action=shader_selection[1])
    return shader_slot(request, root, profile)


def tool_status():
    """Presence hints only. This report is never consulted to enable a button."""
    result = {name: bool(shutil.which(name)) for name in
              ('xcodebuild', 'xcrun', 'make', 'xcodegen', 'dotnet', 'spirv-cross', 'zstd')}
    for name, argv in [('Xcode', ['xcode-select', '-p']),
                       ('Metal', ['xcrun', '--find', 'metal'])]:
        try:
            result[name] = subprocess.run(argv, capture_output=True).returncode == 0
        except OSError:
            result[name] = False
    return result
