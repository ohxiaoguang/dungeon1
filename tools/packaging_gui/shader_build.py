"""First-build Shader execution, using the existing readers, splitter and chain.

The registered tables remain authoritative. Sources must reproduce them byte
for byte; compilation writes its own stamp and generated runtime tables. The
Bundle and valid older caches are never modified.
"""
from dataclasses import replace
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from tools.packaging_gui import cache, engine, registry
from tools.nxrom.resourcefs import ResourceFS
from tools.nxrom.shader_package import digest


def source_mount(request, profile, version):
    expected = profile.build_ids(version)
    for update in (None, request.update or None):
        fs = ResourceFS(request.library, base=request.base, update=update, keys=request.keys,
                        title=profile.title_id)
        try:
            for module in profile.modules:
                fs.check_build(module, expected[module])
            return fs
        except OSError:
            fs.close()
    raise ValueError('Shader source version ' + version + ' is not present in the selected base/update. '
                     'Program version and Shader source versions are checked separately.')


def easf_prepare(request, profile, output):
    sys.path.insert(0, str(engine.REPO / 'dm/gfx/tools/easf'))
    import big4
    import keyfind
    import prepare
    versions = profile.shader_versions
    if len(versions) != 1:
        raise ValueError('EASF preparation requires one registered Shader source version')
    # Discovery reads the source version's module, never assumes an update's
    # code contains the same embedded key.
    from tools.packaging_gui.automatic import program
    with source_mount(request, profile, versions[0]) as fs:
        from tools.packaging_gui.automatic import mounted_version
        update = None
        with ResourceFS(request.library, base=request.base, keys=request.keys) as basefs:
            if mounted_version(basefs, profile) != versions[0]:
                update = request.update
        source_request = replace(request, update=update or '')
        source = program(source_request, cache.namespace(request.cache_root), profile, versions[0])
        ring = keyfind.Keyring(modules=[source / 'ExeFS/main'])
        import nximage
        archives = [(Path(name).name, nximage.member(fs, profile.archive_container, name))
                    for name in profile.archive_members]
        prepare.prepare(archives, output / 'pkg', output / 'profile' / profile.key, keys=ring)
    import hashlib
    return dict(provider='easf', versions=list(versions),
                archives={name: hashlib.sha256(data).hexdigest() for name, data in archives})


def nvn_prepare(request, profile, output, run):
    """Stage only registered Shader-bearing files, then call production split.

    Giant archives need a streaming adapter; refuse them before copying. Runtime
    capture sources likewise fail explicitly instead of emitting partial caches.
    """
    rows = [line.split('\t') for line in profile.table('shader_map.tsv').read_text().splitlines()
            if line and not line.startswith(('#', 'package\t'))]
    provenance = [row[4] for row in rows]
    romfs, mains, inputs = [], [], {}
    from tools.packaging_gui.automatic import program
    for i, version in enumerate(profile.shader_versions):
        version_dir = output / 'sources' / version
        with source_mount(request, profile, version) as fs:
            from tools.packaging_gui.automatic import mounted_version
            with ResourceFS(request.library, base=request.base, keys=request.keys) as basefs:
                base_version = mounted_version(basefs, profile)
            source = program(replace(request, update='' if version == base_version else request.update),
                             cache.namespace(request.cache_root), profile, version)
            folder = version_dir / 'RomFS'
            folder.mkdir(parents=True)
            for entry in fs.files():
                prefix = '/' + (version + '/' if i else '') + entry.path
                if not any(label == prefix or label.startswith(prefix + '#') or label.startswith(prefix + '/')
                           for label in provenance):
                    continue
                if entry.size > 512 * 1024**2:
                    raise ValueError('Shader source needs a streaming archive adapter: ' + entry.path)
                relative = Path(entry.path)
                if relative.is_absolute() or '..' in relative.parts:
                    raise ValueError('Unsafe Shader source path')
                dest = folder / relative
                dest.parent.mkdir(parents=True, exist_ok=True)
                with fs.open(entry.path) as src, dest.open('xb') as dst:
                    shutil.copyfileobj(src, dst, 1024 * 1024)
                inputs[version + '/' + entry.path] = digest(dest)
            romfs.append(str(folder)); mains.append(str(source / 'ExeFS/main'))
            inputs[version + '/main'] = digest(source / 'ExeFS/main')
    if not mains:
        raise ValueError('Profile registers no Shader source versions')
    selected = output / 'profile' / profile.key
    run([sys.executable, engine.REPO / 'dm/gfx/tools/shader_split.py', ','.join(romfs), ','.join(mains),
         output / 'pkg', selected / 'shader_map.tsv', selected / 'shader_facts.tsv', selected / 'shader_pairs.tsv'])
    return dict(provider='nvn', versions=list(profile.shader_versions), files=inputs)


def generate(request):
    profile = engine.profile_for(request)
    final = engine.path(request.cache)
    if final.exists() or final.is_symlink():
        # A previous platform in this batch may have completed both targets.
        engine.validate_cache(replace(request, shader_action='reuse'), profile)
        return
    output = Path(tempfile.mkdtemp(prefix='shader-build-', dir=Path(request.task_work)))
    (output / cache.OWNER).write_text(json.dumps({'owner': cache.NAMESPACE, 'schema': 1}))
    selected = output / 'profile' / profile.key
    shutil.copytree(profile.table('game.tsv').parent, selected,
                    ignore=shutil.ignore_patterns('c1_full.tsv', 'cb_extent.tsv', '__pycache__'))
    env = dict(os.environ, DM_GAME=profile.key, GAME=profile.key, DM_GAMES_FIRST='1',
               DM_GAMES_DIR=str(selected.parent), DM_ROOT=str(output),
               DMSH_CAS=str(output / 'cas'), IOSOUT=str(output / 'ios/dmsh_b'),
               J=str(request.jobs))
    def run(argv):
        subprocess.run([str(a) for a in argv], env=env, cwd=engine.REPO, check=True)
    from tools.packaging_gui import shader_sources
    evidence = shader_sources.for_profile(profile).prepare(request, profile, output, run)
    for name in registry.CACHE_TABLES:
        original = profile.table(name)
        if original.is_file() and (selected / name).read_bytes() != original.read_bytes():
            raise ValueError('Generated source tables differ from the registered Profile: ' + name)
    run([sys.executable, engine.REPO / 'dm/gfx/tools/dmsh_chain.py', '--check-tools'])
    run([sys.executable, engine.REPO / 'dm/gfx/tools/dmsh_build.py', output / 'pkg', output / 'shaders'])
    chain = engine.chain_tools().version()
    # dmsh_build writes one combined summary in the Mac output. A failed iOS
    # compile appears in that row's status; iOS has libraries/stamp/reflections,
    # not a second _b_build.json.
    results = json.loads((output / 'shaders' / ('b-' + chain) / '_b_build.json').read_text())
    from tools.nxrom.prepared_build import shader_keys
    expected = shader_keys(profile.game())
    if (not results or len(results) != len(expected)
            or {row.get('key') for row in results} != expected
            or any(row.get('st') != 'ok' for row in results)):
        raise ValueError('Shader compiler did not complete every registered key for both targets')
    for tool, name in [('c1_guard.py', 'c1_full.tsv'), ('cb_extent.py', 'cb_extent.tsv')]:
        run([sys.executable, engine.REPO / 'dm/gfx/tools' / tool,
             output / 'shaders' / ('b-' + chain), selected / name])
    manifest = dict(schema=2, chain=chain, source_generation=evidence,
                    packages={p.name: digest(p) for p in (output / 'pkg').glob('*.bin')},
                    libraries={p.name: digest(p) for p in (output / 'shaders' / ('b-' + chain)).glob('*.metallib')},
                    ios_libraries={p.name: digest(p) for p in (output / 'ios/dmsh_b' / ('b-' + chain)).glob('*.metallib')})
    (output / 'build-manifest.json').write_text(json.dumps(manifest, indent=2))
    for target in ('macos', 'ios'):
        engine.validate_cache(replace(request, cache=str(output), shader_action='reuse', target=target), profile)
    for name in ('sources', 'cas'):
        if (output / name).is_dir():
            shutil.rmtree(output / name)
    # Same cache volume as the task: atomic publication after both audits.
    output.rename(final)
    print('Shader cache compiled, validated and published for both targets', flush=True)
