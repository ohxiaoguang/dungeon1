"""Explicitly approved build orchestration and post-package auditing.

One executor owns every game: the plan, the approval fingerprint, the stage
events, the audit and the publication are the same code for FIFA 23 and for any
other registered profile. What differs per game is the profile and, where the
resource format really differs, the Shader source provider.
"""
from dataclasses import asdict
import hashlib
import importlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import uuid

from tools.packaging_gui.engine import (PYTHON_DEPENDENCIES, REPO, Request, cached_game, chain_tools,
                                        inspect, path, plan, profile_at, profile_for,
                                        unique_artifact, validate_cache, redact)
from tools.packaging_gui import capabilities
from tools.nxrom.shader_package import digest

# Distribution names differ from the imported module names; the distribution
# metadata is the fallback when a module does not publish its own version.
DEPENDENCY_DISTRIBUTIONS = {'capstone': 'capstone', 'lz4.block': 'lz4', 'fontTools': 'fonttools'}

# One place decides the stage sequence. The executor prepends the local
# revalidation step and Python appends audit and publication, so the count the
# window shows is always this list, never a number written into the UI.
STAGE_LABELS = {
    'prepare-program': 'Prepare game program',
    'prepare-resources': 'Prepare bundled resources',
    'prepare-dlc': 'Prepare verified add-on content',
    'revalidate': '复核输入与审核指纹',
    'generate-shaders': '生成 Shader',
    'rewrite-main': '重写主程序',
    'rewrite-sdk': '重写 SDK',
    'host': '构建运行环境',
    'font': '生成字体',
    'settings': '生成启动设置',
    'package-app': '打包 App',
    'package-ipa': '打包 IPA',
    'audit': '审计产物',
    'publish': '投放产物到输出目录',
}
PUBLISH_STAGE = 'publish'


def stage_plan(recipe):
    """Ordered stages this recipe will really emit, with natural Chinese names."""
    stages = [dict(key='revalidate', label=STAGE_LABELS['revalidate'])]
    for command in recipe['commands']:
        stages.append(dict(key=command['stage'],
                           label=STAGE_LABELS.get(command['stage'], command['stage'])))
    for key in ('audit', PUBLISH_STAGE):
        stages.append(dict(key=key, label=STAGE_LABELS[key]))
    return stages


def disabled_reason(r, profile=None):
    # A structural gap comes first: a target the engine cannot audit must never
    # look selectable. Target and resource mode are otherwise decided by the
    # input gates in inspect(); what stays disabled for every profile is full
    # Shader generation, whose toolchain this delivery did not verify.
    profile = profile or profile_for(r, required=False)
    if profile is not None:
        gap = capabilities.gap(profile, r.target)
        if gap:
            return capabilities.TARGET_NAMES[r.target] + ' cannot be built for ' + profile.name + ': ' + gap
    if r.shader_action != 'reuse' and not r.automatic:
        return 'Use automatic preparation for first-time Shader generation'
    return None


def tool_environment(task):
    allowed = ('USER', 'LANG', 'LC_ALL', 'DOTNET_ROOT', 'DOTNET_ROOT_ARM64')
    env = {k: v for k, v in os.environ.items() if k in allowed}
    import pwd
    env.setdefault('USER', pwd.getpwuid(os.getuid()).pw_name)
    env.update(PATH=os.pathsep.join([str(Path(sys.executable).parent), '/opt/homebrew/bin', '/usr/local/bin',
                                    '/usr/bin', '/bin', '/usr/sbin', '/sbin']),
               PYTHONDONTWRITEBYTECODE='1', PYTHONUNBUFFERED='1',
               DOTNET_SKIP_FIRST_TIME_EXPERIENCE='1', DOTNET_CLI_TELEMETRY_OPTOUT='1',
               DOTNET_CLI_HOME=str(task / 'tmp/dotnet'),
               CLANG_MODULE_CACHE_PATH=str(task / 'tmp/clang'),
               SWIFTPM_MODULECACHE_OVERRIDE=str(task / 'tmp/swift'))
    return env


def verify_tools():
    if sys.platform != 'darwin' or platform.machine() != 'arm64' or int(platform.mac_ver()[0].split('.')[0]) < 26:
        raise ValueError('The current macOS game launcher requires Apple silicon and macOS 26 or later')
    font = Path('/System/Library/Fonts/Supplemental/Arial Unicode.ttf')
    if not font.is_file():
        raise ValueError('The existing packager requires the installed Arial Unicode system font')
    from tools.nxrom.shader_compile import runtime_root
    runtime = runtime_root(dict(os.environ))
    os.environ['DOTNET_ROOT'] = os.environ['DOTNET_ROOT_ARM64'] = runtime
    bad = chain_tools().check_tools()
    if bad:
        raise ValueError('Installed Shader tools differ from the repository lock; no lock update is permitted')


def git_sha():
    release = REPO / 'release.json'
    if release.is_file():
        return json.loads(release.read_text())['revision']
    return subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=REPO, check=True,
                          capture_output=True, text=True).stdout.strip()


def dependency_state(module, distribution):
    """Import one build dependency and report its real version, or that it is absent."""
    try:
        loaded = importlib.import_module(module)
    except ImportError as exc:
        return dict(available=False, version=None, distribution=None, error=str(exc))
    reported = getattr(loaded, '__version__', None)
    try:
        installed = importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        installed = None
    return dict(available=True, version=str(reported or installed), distribution=installed)


def interpreter_identity():
    """Identify the interpreter every build stage would inherit from this process.

    The GUI starts the bridge with the selected interpreter and that process runs
    plan() and execute(), so this description and the commands share one
    interpreter. It is part of the review fingerprint: a different path, Python
    version or dependency version can never reuse an earlier confirmation.
    """
    dependencies = {name: dependency_state(name, DEPENDENCY_DISTRIBUTIONS.get(name, name))
                    for name in PYTHON_DEPENDENCIES}
    return dict(executable=sys.executable, realpath=os.path.realpath(sys.executable),
                version=platform.python_version(), implementation=platform.python_implementation(),
                cache_tag=getattr(sys.implementation, 'cache_tag', None), prefix=sys.prefix,
                dependencies=dependencies,
                missing=[name for name, state in dependencies.items() if not state['available']])


def shader_inventory(r, chain, profile=None):
    """The bytes this target's Shader library is made of, keyed by file name.

    The stamp (inputs.tsv) and the compiler's build summary are not part of the
    library inventory; they travel beside the libraries and are checked apart.
    A layer library (an OpenGL game) is one metallib plus its table, so its
    inventory is exactly the files in that folder.
    """
    from tools.packaging_gui import shader_sources
    source = shader_sources.for_profile(profile or profile_for(r))
    folder = source.library_dir(path(r.cache), r.target, chain)
    if not source.needs_chain:
        return folder, {p.name: digest(p) for p in folder.iterdir() if p.is_file()}
    return folder, {p.name: digest(p) for p in folder.iterdir()
                    if p.suffix in ('.json', '.metallib') and p.name != '_b_build.json'}


def review(r, task):
    """Return only safe, typed metadata. Do not create the future build folder."""
    r.validate_options()
    profile = profile_for(r)
    root = path(str(task))
    output = path(r.output)
    # The run directory lives outside the player-visible output folder: only the
    # finished artifact is published there. It must be new, never a symlink, and
    # must not already hold build products.
    if root.is_symlink() or root.name in ('', '.', '..') or root.parent == output:
        raise ValueError('Build task must be a new directory outside the output folder')
    if root.exists():
        if not (root / 'result.json').is_file():
            raise ValueError('Existing directory is not an executor task; nothing was touched')
        if (root / 'work').exists() or (root / 'work').is_symlink():
            raise ValueError('Task already contains build products; choose a new task')
    checks = inspect(r)
    reason = disabled_reason(r, profile)
    identity = interpreter_identity()
    # The Title ID the resource itself reported; the confirmation sheet repeats
    # it so a human approves the game that will actually be packaged.
    found = next((c['detail'] for c in checks['checks']
                  if c['name'] == 'container-identity' and c['ok']), None)
    identified = (dict(title_id=found['title_id'], game=found['game'], name=found['name'])
                  if isinstance(found, dict) else None)
    program = next((c['detail'] for c in checks['checks']
                    if c['name'] == 'program-identity' and c['ok']), None)
    version = program['version'] if isinstance(program, dict) else (profile.package or '')
    dependency_error = ('Selected Python is missing required dependencies: '
                        + ', '.join(identity['missing'])) if identity['missing'] else None
    tool_error = None
    if not reason and checks['input_checks_passed']:
        try:
            verify_tools()
        except (OSError, ValueError, subprocess.CalledProcessError) as exc:
            tool_error = str(exc)
    eligible = (not reason and dependency_error is None and tool_error is None
                and checks['input_checks_passed'])
    metadata, private_stamps = {}, {}
    for name in ('base', 'update', 'keys', 'exefs', 'romfs', 'aoc', 'cache', 'library'):
        if name == 'cache' and r.shader_action == 'generate':
            continue
        value = getattr(r, name)
        if value:
            p = path(value)
            if p.exists():
                st = p.stat()
                private_stamps[name] = [str(p), st.st_size, st.st_mtime_ns, st.st_dev, st.st_ino]
                if name != 'keys':
                    metadata[name] = f'{p.name}; bytes={st.st_size}; mtime_ns={st.st_mtime_ns}'
    shader = next((c['detail'] for c in checks['checks'] if c['name'] == 'shader-cache' and c['ok']), {})
    revision = git_sha()
    inventory = {}
    if shader and r.shader_action == 'reuse':
        # Both targets are bound to their own cache bytes: an iOS confirmation
        # must not be reusable after the iOS libraries change.
        inventory = shader_inventory(r, shader['chain'])[1]
    # Include actual recipe sources, not only HEAD, so uncommitted changes also
    # invalidate an earlier confirmation. No key contents enter this digest.
    sources = {name: digest(REPO / name) for name in (
        'tools/packaging_gui/engine.py', 'tools/packaging_gui/workflow.py',
        'tools/packaging_gui/registry.py', 'tools/packaging_gui/capabilities.py',
        'tools/packaging_gui/shader_sources.py', 'tools/packaging_gui/games.py',
        'tools/packaging_gui/dlc.py', 'tools/packaging_gui/folder.py',
        'dm/resource/nxrom.c', 'dm/resource/nxrom.h', 'dm/tools/nx_extract/Program.cs',
        'tools/nxrom/resourcefs.py', 'tools/nxrom/gl_library.py', 'tools/nxrom/mac_build.py', 'dm/host/hle_fs.c', 'dm/host/hle_misc.c',
        'dm/apple/ResourceDiscovery.swift', 'dm/macos/Launcher.swift', 'dm/ios/Sources/Launcher.swift',
        'scripts/packaging_gui.py', 'scripts/build_mac_app.py',
        'dm/ios/tools/build_ipa.sh', 'dm/ios/tools/pack_ipa.py',
        'dm/ios/tools/gen_build.py', 'tools/nxrom/prepared_build.py')}
    if r.automatic:
        for name in ('tools/packaging_gui/automatic.py', 'tools/packaging_gui/cache.py',
                     'tools/packaging_gui/shader_build.py', 'scripts/packaging_shaders.py',
                     'scripts/packaging_resources.py', 'bin/nx_extract/nx_extract.dll', 'bin/nxrom.dylib'):
            sources[name] = digest(REPO / name)
        for source in profile.table('game.tsv').parent.iterdir():
            if source.suffix in ('.tsv', '.py', '.h') and source.is_file():
                sources['profile/' + source.name] = digest(source)
    fingerprint = hashlib.sha256(json.dumps(dict(request=asdict(r), task=str(root),
        input_stamps=private_stamps, shader=shader, inventory=inventory, sources=sources, git=revision,
        identified=identified, interpreter=identity), sort_keys=True).encode()).hexdigest()
    space = next((c['detail'] for c in checks['checks'] if c['name'] == 'output-space' and c['ok']), {})
    return dict(schema=1, execution_allowed=bool(eligible),
                disabled_reason=reason or dependency_error or tool_error
                or ('Input inspection failed' if checks['issues'] else ''),
                fingerprint=fingerprint, task_directory=str(root), target=r.target, mode=r.mode,
                game=profile.key, game_name=profile.name,
                artifact_path=str(unique_artifact(r.output, r.artifact_name(profile))),
                git_sha=revision, interpreter=identity, identified=identified, inputs=metadata,
                shader={k: str(v) for k, v in shader.items()},
                program_version=version, shader_source_versions=list(profile.shader_versions),
                prepared_shader=dict(cache=r.cache, action=r.shader_action),
                estimated_bytes=space.get('estimated_bytes', 0), free_bytes=space.get('free_bytes', 0),
                cleanup='Only the temporary work folder of this run is removed. The published artifact '
                        'and the run log stay. Existing files are never deleted.',
                issues=checks['issues'], game_run_verified=False,
                dlcs=[dict(title=format(d['title'], '016X'), index=d['index'], version=d['version']) for d in r.dlcs],
                dlc_warnings=r.dlc_warnings)


def inventory(root):
    """Deterministic directory hash: sorted paths, file sizes and content hashes."""
    entries = []
    for p in sorted(root.rglob('*')):
        if p.is_file():
            entries.append(dict(path=p.relative_to(root).as_posix(), bytes=p.stat().st_size, sha256=digest(p)))
    encoded = json.dumps(entries, sort_keys=True, separators=(',', ':')).encode()
    return entries, hashlib.sha256(encoded).hexdigest()


def audit(r, task, artifact, inventory_path=None):
    """Reuse the existing full external macOS byte/layout audit, or the IPA one."""
    profile = profile_for(r)
    if disabled_reason(r, profile):
        raise ValueError(disabled_reason(r, profile))
    checked = validate_cache(r, profile)
    root, target = path(str(task)), path(str(artifact))
    layer = checked.get('layer')
    cache, shader_files = shader_inventory(r, checked['chain'], profile)
    if layer:
        # A layer library has no stamp: what proves it is the table naming every
        # program, checked by validate_cache against the profile's capture.
        shader = dict(graphics_api=profile.graphics_api, layer=layer,
                      table=str(checked.get('table', '')), files_sha256=shader_files)
    else:
        shader = dict(chain=checked['chain'], files_sha256=shader_files,
                      inputs_sha256=digest(cache / 'inputs.tsv'))
    # The cached profile is what the artifact was packaged with; its tables and
    # marker are the same ones validate_cache compared with the repository.
    cached = cached_game(r, profile)
    if r.target == 'macos':
        from tools.nxrom.mac_build import audit_app
        app = target
        if not app.is_relative_to(root) or app.suffix != '.app' or not app.is_dir():
            raise ValueError('Missing App in this task')
        marker = (cached.get('romfs_marker') if r.mode == 'directory' else None)
        details = audit_app(app, cached, root / 'patched', root / 'dmhost', shader,
                            backend=r.mode, romfs_marker=marker, layer=layer)
        if r.aoc:
            from tools.packaging_gui.dlc import audit_tree
            source = audit_tree(path(r.aoc), profile.title_id)
            bundled = audit_tree(app / 'Contents/Resources/aoc', profile.title_id)
            if source != bundled:
                raise ValueError('Packaged AOC differs from prepared source')
        if not layer:
            stamp = app / 'Contents/Resources/msl' / cache.name / 'inputs.tsv'
            if stamp.read_bytes() != (cache / 'inputs.tsv').read_bytes():
                raise ValueError('Packaged Shader stamp differs from validated cache')
        from scripts.build_mac_app import audit as layout_audit
        layout_audit(app, r.mode, marker, None if layer else cache.name, layer)
        entries, summary = inventory(app)
        if not entries or details['bytes'] <= 0:
            raise ValueError('Empty App')
        audit_flags = dict(layout=True, shader_bytes=True, program_bytes=True,
                           file_inventory=True)
        audit_flags['shader_table' if layer else 'input_stamp'] = True
    else:
        from tools.nxrom.prepared_build import audit_ipa
        ipa = target
        if not ipa.is_relative_to(root) or ipa.suffix != '.ipa' or not ipa.is_file():
            raise ValueError('Missing IPA in this task')
        marker = (cached.get('romfs_marker') if r.mode == 'directory' else None)
        if r.aoc:
            from tools.packaging_gui.dlc import audit_tree
            audit_tree(path(r.aoc), profile.title_id)
        aoc = sorted((p.name for p in path(r.aoc).iterdir() if p.is_dir() and p.name.isdigit()),
                     key=int) if r.aoc else []
        resources = {}
        if r.mode == 'directory':
            for label, folder in [('romfs', r.romfs)] + ([('aoc', r.aoc)] if r.aoc else []):
                source = path(folder)
                for entry in sorted(source.rglob('*')):
                    if entry.is_file():
                        resources[label + '/' + entry.relative_to(source).as_posix()] = dict(
                            bytes=entry.stat().st_size, sha256=digest(entry))
        details = audit_ipa(ipa, expected_libraries=len(list(cache.glob('*.metallib'))),
                            shader=shader, backend=r.mode, romfs_marker=marker, aoc_indexes=aoc,
                            expected_bundle_id='org.nxnative.' + profile.key.lower(), resources=resources)
        entries = [dict(path=ipa.name, bytes=ipa.stat().st_size, sha256=digest(ipa))]
        summary = digest(ipa)
        audit_flags = dict(layout=True, shader_bytes=True, ipa_crc=True, input_stamp=True,
                           bundle_identity=True, resource_bytes=True, file_inventory=True)
        if aoc:
            audit_flags['addon_content'] = True
    # BuildExecutor treats this mapping as passed checks, so record only checks
    # applicable to this recipe. Facts such as "no DLC selected" are not failures.
    audit_flags['bundled_game_data' if r.mode == 'directory' else 'no_bundled_game_data'] = True
    target_path = path(str(inventory_path)) if inventory_path else root / 'artifact-files.json'
    with target_path.open('x') as stream:
        json.dump(entries, stream, sort_keys=True, separators=(',', ':'))
        stream.write('\n')
    return dict(path=str(target), bytes=details['bytes'] if r.target == 'macos' else target.stat().st_size,
                sha256=summary, audit=audit_flags, game_run_verified=False)


def discard_work(work):
    """Remove one run's temporary work folder and nothing else.

    The path must be exactly ``<executor task>/work``: a real directory, not a
    symlink, whose parent still holds the executor's ``result.json``. No glob,
    no wildcard and no recursion into any other folder is ever used.
    """
    tree = Path(work)
    if tree.name != 'work' or tree.is_symlink() or not tree.is_dir():
        return False
    if not (tree.parent / 'result.json').is_file():
        return False
    shutil.rmtree(tree)
    return True


def publish(report, source, folder, name=None):
    """Copy the audited artifact next to the game file and verify the copy.

    An App is a directory and is compared file by file; an IPA is one file and is
    compared by its SHA-256. ``unique_artifact`` picks a free name, so an existing
    App or IPA is never merged into or overwritten. The copy is written under a
    hidden partial name and only renamed to the published name after its bytes
    match, so an interrupted publication can never leave something that looks
    like a finished artifact. A mismatch removes only the partial copy.
    """
    source = Path(source)
    base = path(str(folder))
    final = unique_artifact(base, name or source.name)
    partial = base / ('.' + final.name + '.partial-' + uuid.uuid4().hex[:8])
    try:
        if source.is_dir():
            shutil.copytree(source, partial)
            entries, summary = inventory(partial)
            matches = bool(entries) and summary == report['sha256']
        else:
            shutil.copyfile(source, partial)
            summary = digest(partial)
            matches = summary == report['sha256']
        if not matches:
            raise ValueError('Published artifact bytes differ from the audited build; the copy was removed')
        if final.exists() or final.is_symlink():
            raise ValueError('A file appeared at the output name; nothing was replaced')
        if sys.platform == 'darwin':
            # RENAME_EXCL is atomic: a competing publisher cannot create a file
            # between our existence check and the final rename and be replaced.
            import ctypes
            lib = ctypes.CDLL(None, use_errno=True)
            rename = lib.renamex_np
            rename.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
            rename.restype = ctypes.c_int
            if rename(os.fsencode(partial), os.fsencode(final), 0x4):
                code = ctypes.get_errno()
                raise OSError(code, os.strerror(code), str(final))
        elif source.is_file():
            os.link(partial, final)
            partial.unlink()
        else:
            raise ValueError('Atomic exclusive directory publication requires macOS')
    except BaseException:
        if partial.is_dir() and not partial.is_symlink():
            shutil.rmtree(partial, ignore_errors=True)
        elif partial.exists():
            partial.unlink()
        raise
    return final


def failure_report(r, root, stage, exc, work, keep_work):
    """Write the one small record a failed run must keep, then clean its work."""
    payload = dict(schema=1, stage=stage, exit_code=getattr(exc, 'returncode', None),
                   message=redact(dict(error=str(exc)), r).get('error', str(exc)),
                   game_run_verified=False)
    try:
        payload['work_removed'] = False if keep_work else discard_work(work)
    except OSError as cleanup_error:
        payload['work_removed'] = False
        payload['cleanup_error'] = str(cleanup_error)
    payload['work_retained'] = not payload['work_removed'] and work.exists()
    try:
        (Path(root) / 'failure.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n')
    except OSError:
        pass
    return payload


def execute(r, task, approval, keep_work=False):
    """Only called after a human has confirmed the matching review fingerprint."""
    root = path(str(task))
    # BuildExecutor owns this root. No existing build directory is reused.
    if not root.is_dir() or not (root / 'result.json').is_file():
        raise ValueError('Expected an executor-owned task directory')
    work = root / 'work'
    if work.exists() or work.is_symlink():
        raise ValueError('Expected a task with no build products; existing files were retained')
    owner = json.loads((root / 'result.json').read_text())
    if (owner.get('context', {}).get('kind') != 'build'
            or owner.get('taskDirectory') != str(root)
            or owner.get('state') not in ('starting', 'running')):
        raise ValueError('Task is not an active build owned by the executor')
    current = review(r, root)
    if not current['execution_allowed'] or not approval or approval != current['fingerprint']:
        raise ValueError('Build requires a matching explicit confirmation and fresh passing checks')
    recipe = plan(r, work, profile_for(r))
    if r.automatic:
        from tools.packaging_gui import cache
        marker = root / cache.OWNER
        if not marker.exists():
            with marker.open('x') as stream:
                json.dump({'owner': cache.NAMESPACE, 'schema': 1}, stream)
    work.mkdir()
    alias = None
    alias_created = False
    stage = 'revalidate'
    try:
        if any(c.isspace() for c in str(work)):
            from tools.packaging_gui.engine import make_alias
            alias = make_alias(work)
            alias.symlink_to(work, target_is_directory=True)
            alias_created = True
        summary = json.dumps(redact(recipe, r), indent=2)
        for value in (r.cache, r.exefs, r.romfs, r.library):
            if value:
                summary = summary.replace(json.dumps(value)[1:-1], '<input-path>')
        with (work / 'recipe-summary.json').open('x') as stream:
            stream.write(summary + '\n')
        (work / 'tmp').mkdir(); (work / 'font').mkdir()
        if r.automatic and r.mode == 'directory':
            metadata = path(r.romfs).parent
            metadata.mkdir(parents=True)
            for name in ('control.nacp', 'icon.jpg'):
                source = path(r.exefs).parent / name
                if source.is_file():
                    shutil.copyfile(source, metadata / name)
            if r.dlcs:
                (work / 'dlc-request.json').write_text(json.dumps(dict(
                    library=r.library, keys=r.keys, game=r.game, aoc=r.aoc,
                    application_version=int(current['program_version'].removeprefix('v')), dlcs=r.dlcs)))
        if r.automatic and r.shader_action == 'generate':
            (work / 'shader-request.json').write_text(json.dumps(asdict(r)))
        shutil.copyfile(recipe['preparation']['font_copy']['source'], work / 'font/standard.ttf')
        env = tool_environment(work)
        for command in recipe['commands']:
            stage = command['stage']
            print('@@NX_STAGE@@' + stage, flush=True)
            subprocess.run(command['argv'], cwd=REPO, env=dict(env, **command['environment']), check=True)
        if r.automatic and r.shader_action == 'generate':
            from dataclasses import replace
            r = replace(r, shader_action='reuse')
        stage = 'audit'
        print('@@NX_STAGE@@audit', flush=True)
        # The full audit runs on the work copy, before anything moves or is cleaned.
        report = audit(r, work, Path(recipe['artifact']), inventory_path=root / 'artifact-files.json')
        stage = PUBLISH_STAGE
        print('@@NX_STAGE@@' + PUBLISH_STAGE, flush=True)
        final = publish(report, Path(recipe['artifact']), path(r.output), recipe['artifact_name'])
        report['path'] = str(final)
        with (root / 'audit.json').open('x') as stream:
            json.dump(report, stream, indent=2)
        removed = discard_work(work)
        (root / 'summary.json').write_text(json.dumps(
            dict(schema=1, artifact=report, work_removed=removed, output=str(path(r.output)),
                 stages=[s['key'] for s in stage_plan(recipe)]), ensure_ascii=False, indent=2) + '\n')
        print('Packaging, byte audits and publication passed; game runtime remains unverified.', flush=True)
        return report
    except BaseException as exc:
        failure_report(r, root, stage, exc, work, keep_work)
        raise
    finally:
        if alias_created and alias.is_symlink() and os.readlink(alias) == str(work):
            alias.unlink()
