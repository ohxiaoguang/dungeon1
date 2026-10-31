"""The generic nxnative build engine: one entry for every registered game.

A request names the game by its base Title ID (`game`), the engine loads that
profile from `dm/games/<title ID>`, derives the program version from the ExeFS
module headers and emits the same stage sequence for every profile:

    rewrite the code modules -> build the host -> font -> launcher settings ->
    package the App / IPA

FIFA 23 is not a second path: the only thing its profile adds is an archive
format (`archive_format easf`), whose preparation lives in
`tools/packaging_gui/shader_sources.py` and `scripts/build_fifa23.py` and is
called by the same plan as any other Shader source.

Nothing here decides anything by game name.
"""
from dataclasses import dataclass
import importlib.util
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys

REPO = Path(__file__).resolve().parents[2]
# The modules the executable chain imports: capstone and lz4.block from
# dm/tools/patch_nso.py, fontTools from dm/tools/make_ext_font.py. Crypto is not
# one of them: only dm/gfx/tools/easf/{prepare,keyfind}.py import it lazily, and
# only the preview-only generation path reaches them.
PYTHON_DEPENDENCIES = ('capstone', 'lz4.block', 'fontTools')

if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
from tools.packaging_gui import capabilities, registry


def chain_tools():
    spec = importlib.util.spec_from_file_location('gui_dmsh_chain', REPO / 'dm/gfx/tools/dmsh_chain.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@dataclass
class Request:
    """One build selection. `game` is the base game Title ID the engine plans for."""
    target: str = 'macos'
    mode: str = 'nsp'
    game: str = ''
    base: str = ''
    update: str = ''
    keys: str = ''
    easf_key_file: str = ''
    output: str = ''
    exefs: str = ''
    romfs: str = ''
    aoc: str = ''
    cache: str = ''
    library: str = ''
    shader_action: str = 'reuse'
    jobs: int = 4
    automatic: str = ''
    cache_root: str = ''
    task_work: str = ''
    resource_bytes: int = 0
    resource_folder: str = ''
    dlcs: tuple = ()
    dlc_warnings: tuple = ()

    def validate_options(self):
        if self.target not in capabilities.TARGETS or self.mode not in capabilities.MODES:
            raise ValueError('Unsupported target or resource mode')
        if self.shader_action not in ('reuse', 'generate') or not 1 <= self.jobs <= 32:
            raise ValueError('Invalid Shader action or worker count')
        if self.aoc and self.mode != 'directory':
            raise ValueError('Extracted AOC is bundled only in Directory mode; external DLC is imported after installation')

    def artifact_name(self, profile=None):
        """The one file this target publishes: a bundle or a single IPA."""
        profile = profile or profile_for(self)
        return profile.app_name + ('.ipa' if self.target == 'ios' else '.app')


def path(value):
    if not value or '\0' in value or not Path(value).expanduser().is_absolute():
        raise ValueError('Choose an absolute path')
    return Path(value).expanduser().resolve()


def profile_for(request, required=True):
    """-> the registered profile this request builds, by the Title ID it carries."""
    try:
        found = registry.by_title(request.game) if request.game else None
    except (TypeError, ValueError):
        raise ValueError('Invalid game Title ID: ' + str(request.game))
    if found is None:
        if not required:
            return None
        raise ValueError('No registered game profile for Title ID '
                         + (format(int(request.game, 16), '016X') if request.game else '<empty>')
                         + '; identify the game before planning a build')
    return found


def detect_program(profile, exefs):
    """-> (version, {module: build id}) read from the ExeFS module headers.

    The version is never guessed from whether an update was selected: the NSO
    headers carry each module's build ID, and the profile registers the versions
    it was brought up on. A file whose IDs match no row is refused instead of
    being packaged as some other version.
    """
    folder = path(str(exefs))
    if not folder.is_dir():
        raise ValueError('Select the extracted ExeFS folder')
    found = {}
    for module in profile.modules:
        candidate = folder / module
        if not candidate.is_file():
            raise ValueError('ExeFS holds no ' + module + ' module')
        with candidate.open('rb') as stream:
            head = stream.read(0x60)
        if head[:4] != b'NSO0':
            raise ValueError('Not an NSO module: ' + module)
        found[module] = head[0x40:0x50].hex()
    for version, _, ids in profile.versions:
        if all(found.get(module) == ids.get(module) for module in profile.modules):
            return version, found
    raise ValueError(profile.name + ' registers no program version with these module build IDs ('
                     + ', '.join(module + '=' + found[module] for module in profile.modules)
                     + '); select the ExeFS of a registered version: '
                     + ', '.join(version + ' ' + display for version, display, _ in profile.versions))


def profile_at(cache, profile):
    """The profile copy a completed Shader build wrote beside its libraries."""
    return path(str(cache)) / 'profile' / profile.key


def cached_game(r, profile=None):
    """-> the profile copy inside the selected cache, for the tools that take one.

    It is authoritative for the build: it holds the generated tables
    (c1_full.tsv, cb_extent.tsv) the host and the audits read, and validate_cache
    has already compared it with the repository profile.
    """
    profile = profile or profile_for(r)
    return registry.game_profiles.Game(profile_at(r.cache, profile))


def unique_artifact(folder, name):
    """The first free ``name`` in a folder. Never overwrites.

    ``name`` is a whole file name, so an App and an IPA built from the same game
    keep their own numeric suffix sequence.
    """
    base = path(str(folder))
    stem, suffix = Path(name).stem, Path(name).suffix
    candidate = base / name
    for index in range(2, 100):
        if not candidate.exists() and not candidate.is_symlink():
            return candidate
        candidate = base / ('%s (%d)%s' % (stem, index, suffix))
    raise ValueError('Too many existing artifacts in the output folder; choose another output folder')


def make_alias(task):
    """A whitespace-free spelling; all bytes still live on the cache disk."""
    return Path('/private/tmp') / ('nxpack-work-' + hashlib.sha256(str(task).encode()).hexdigest()[:24])


def plan(r, task, profile=None):
    """Describe commands for a future executor; never create task directories."""
    from tools.packaging_gui import shader_sources
    r.validate_options()
    profile = profile or profile_for(r)
    gap = capabilities.gap(profile, r.target)
    if gap:
        raise ValueError(capabilities.TARGET_NAMES[r.target] + ' cannot be built for ' + profile.name + ': ' + gap)
    version, _ = detect_program(profile, r.exefs)
    display = profile.display_of(version)
    task = path(str(task))
    if task.exists() or task.is_symlink() or task.name in ('', '.', '..'):
        raise ValueError('Task must be a new directory that does not exist')
    if not task.parent.is_dir():
        raise ValueError('Task parent folder must already exist')
    py = sys.executable
    source = shader_sources.for_profile(profile)
    shader = (path(r.cache) if r.automatic or r.shader_action == 'reuse' else task / 'shader-source')
    prof = shader / 'profile' / profile.key
    env = dict(DM_GAME=profile.key, GAME=profile.key, DM_GAMES_FIRST='1',
               DM_GAMES_DIR=str(prof.parent), DM_ROOT=str(task),
               WORK=str(task / 'tmp'), TMPDIR=str(task / 'tmp'),
               PYTHONPYCACHEPREFIX=str(task / 'tmp/pycache'),
               DMSH_CAS=str(task / 'shader-cas'), J=str(r.jobs),
               DM_RESOURCE_BACKEND=r.mode)
    commands = []

    def command(stage, argv, extra=None):
        commands.append(dict(stage=stage, argv=[str(a) for a in argv],
                             environment=dict(env, **(extra or {}))))

    exefs = path(r.exefs)
    # The chain version only names an NVN library's folder; a layer provider
    # (gl / vk) has none. One value serves both branches below.
    chain = chain_tools().version() if source.needs_chain else None
    if r.shader_action == 'generate':
        prepared = (dict(argv=[py, REPO / 'scripts/packaging_shaders.py',
                              '--request', task / 'shader-request.json'], environment={})
                    if r.automatic else source.generation_command(r, profile, shader, exefs, py, REPO))
        command('generate-shaders', prepared['argv'], prepared.get('environment'))
    if r.automatic and r.mode == 'directory':
        command('prepare-resources', [py, REPO / 'scripts/packaging_resources.py',
                '--library', r.library, '--base', r.base, '--keys', r.keys,
                '--update', r.update, '--title', profile.key, '--output', path(r.romfs)])
        if r.dlcs:
            command('prepare-dlc', [py, REPO / 'scripts/packaging_resources.py',
                    '--dlc-request', task / 'dlc-request.json'])
    patched = task / 'patched'
    for module in profile.modules:
        command('rewrite-' + module,
                [py, REPO / 'dm/tools/patch_nso.py', exefs / module, patched, module])
    if r.target == 'macos':
        make_root = make_alias(task) if any(c.isspace() for c in str(task)) else task
        command('host', ['make', '-C', REPO / 'dm/host', 'GAME=' + profile.key,
                         'GEN=' + str(make_root / 'gen'), 'HOST=' + str(make_root / 'dmhost'), '-j' + str(r.jobs)])
        # A future executor creates font/, copies the system font bytes and
        # runs these tools. Filesystem preparation is explicit plan metadata.
        command('font', [py, REPO / 'dm/tools/make_ext_font.py', task / 'font/nintendo_ext.ttf'])
        command('settings', [py, REPO / 'dm/games/settings.py', profile.key, patched,
                             exefs.parent / 'control.nacp', task / 'launcher.json'])
        artifact = task / r.artifact_name(profile)
        args = [py, REPO / 'scripts/build_mac_app.py', '--resource-backend', r.mode,
                '--host', task / 'dmhost', '--patched', patched,
                '--shaders', source.library_dir(shader, r.target, chain),
                '--profile', prof, '--font', task / 'font',
                '--settings', task / 'launcher.json', '--title-id', profile.key,
                '--name', profile.app_name, '--version', display,
                '--output', artifact]
        if r.mode == 'directory':
            args += ['--romfs', path(r.romfs)]
            if r.aoc:
                args += ['--aoc', path(r.aoc)]
        command('package-app', args)
    else:
        artifact = task / r.artifact_name(profile)
        # In external mode ROMFS is a nonexistent sibling of control.nacp:
        # the shell uses the parent metadata, and never bundles this path.
        romfs = path(r.romfs) if r.mode == 'directory' else exefs.parent / 'RomFS'
        # The shell reads the app name/version from the control data beside the
        # RomFS, and the icon from there too; the ExeFS folder of the selected
        # program version is the authoritative pair, so point both at it.
        icon = exefs.parent / 'icon.jpg'
        # MSL_IOS is the folder build_ipa.sh looks under for this backend's
        # sub-folder: <ios>/dmsh_b/b-<chain> for NVN, <ios>/gl for GLSL, <ios>/vk
        # for Vulkan. Ask the provider instead of assuming the NVN layout, or a
        # layer cache would be looked for in a folder no layer build writes.
        extra = dict(W=str(task / 'ios-work'), PATCHED=str(patched), ROMFS=str(romfs),
                     MSL_IOS=str(Path(source.library_dir(shader, 'ios', chain)).parent),
                     GFXAPI=profile.graphics_api,
                     # Add-on content is a set of numeric index folders and only the
                     # directory backend packs it (build_ipa.sh).
                     AOC=str(path(r.aoc)) if r.mode == 'directory' and r.aoc else '',
                     DM_IOS_BUILD_DIR=str(task / 'ios-project'),
                     DM_XCODE_DERIVED_DATA=str(task / 'DerivedData'), FONT_PY=py,
                     DM_DISPLAY_NAME=profile.app_name, DM_APP_VERSION=display)
        if icon.is_file():
            extra['DM_ICON'] = str(icon)
        command('package-ipa', ['bash', REPO / 'dm/ios/tools/build_ipa.sh', artifact], extra)
    return dict(schema=1, title_id=profile.key, game=profile.key, name=profile.name,
                program_version=version, program_display=display,
                shader_source_versions=list(profile.shader_versions),
                shader_source=source.key,
                target=r.target, mode=r.mode, shader_action=r.shader_action,
                task=str(task), artifact=str(artifact), artifact_name=r.artifact_name(profile),
                commands=commands, execution_enabled=False,
                environment_policy={'inherit_only': ['PATH', 'USER', 'LANG', 'LC_ALL', 'DOTNET_ROOT', 'DOTNET_ROOT_ARM64'],
                                    'apply_explicit_stage_environment': True},
                pending=['Preview only: eligible recipes require a fresh review and explicit confirmation',
                         'Retail input and runtime validation have not been performed'],
                preparation={'new_directories': [str(task), str(task / 'tmp'), str(task / 'font')],
                             'font_copy': {'source': '/System/Library/Fonts/Supplemental/Arial Unicode.ttf',
                                           'destination': str(task / 'font/standard.ttf')}})


def validate_cache(r, profile=None):
    """Use the existing chain and profile-input functions; reject stale assets."""
    from tools.packaging_gui import shader_sources
    profile = profile or profile_for(r)
    source = shader_sources.for_profile(profile)
    if not source.needs_chain:
        # A layer library (GLSL the game compiles itself) carries one metallib and
        # the table naming its Metal functions; it has no chain version, stamp,
        # reflections or constant-segment tables, so those checks do not apply and
        # the provider proves what its own format must carry.
        return source.validate_cache(profile, path(r.cache), r.target, cached_game(r, profile))
    chain = chain_tools()
    version = chain.version()
    header = (REPO / 'dm/gfx/nvn/dmsh_chain.h').read_text()
    if '#define DMSH_CHAIN "' + version + '"' not in header:
        raise ValueError('Repository chain header is stale; do not change it from the GUI')
    cached = cached_game(r, profile)
    for name in registry.CACHE_TABLES:
        original = profile.table(name)
        if name == 'game.tsv' and original.exists():
            # GUI labels and source-provider routing do not affect compiled
            # Shader inputs or runtime constants. Older caches keep their exact
            # bytes; compare every other profile row, including build IDs.
            def relevant(game):
                return [(k, v) for k, v in game.rows if k not in registry.EXTRA_KEYS]
            matches = relevant(cached) == relevant(profile.game())
        else:
            matches = not original.exists() or cached.table(name).read_bytes() == original.read_bytes()
        if not matches:
            raise ValueError('Cached Profile differs from repository: ' + name)
    root = path(r.cache)
    # A completed cache may carry the source build's manifest. When it does, its
    # chain and library bytes are part of the evidence; a cache without one is
    # still judged by its tables, stamp, reflections and libraries below.
    manifest_path = root / 'build-manifest.json'
    manifest = json.loads(manifest_path.read_text()) if manifest_path.is_file() else {}
    if 'chain' in manifest and manifest.get('chain') != version:
        raise ValueError('Shader cache was built with another chain version; rebuild it separately')
    # The archive format decides what else a complete source build must carry.
    shader_sources.for_profile(profile).check_cache(profile, root, manifest, chain, profile_at(r.cache, profile))
    cache = root / ('shaders' if r.target == 'macos' else 'ios/dmsh_b') / ('b-' + version)
    stamp = chain.read_stamp(str(cache))
    if stamp != {'game': profile.key, 'inputs': chain.inputs(cached)}:
        raise ValueError('Shader inputs.tsv does not match the selected Profile; regenerate separately')
    for name in ('c1_full.tsv', 'cb_extent.tsv'):
        first = cached.table(name).read_text().splitlines()[0]
        if not (first == chain.table_head(str(cache)) or first.startswith(chain.table_head(str(cache)) + ' ')):
            raise ValueError('Stale generated Profile table: ' + name)
    from tools.nxrom.prepared_build import shader_keys
    keys = shader_keys(cached)
    if not keys:
        raise ValueError('Empty Shader map')
    sdk = 'macosx' if r.target == 'macos' else 'iphoneos'
    reflections = list(cache.glob('*_b.json'))
    if {p.name[:-7] for p in reflections} != keys:
        raise ValueError('Shader reflection coverage differs from the Profile')
    for key in keys:
        reflected = json.loads((cache / (key + '_b.json')).read_text())
        if (reflected.get('chain') != version or reflected.get('key') != key + '_b'
                or sdk not in reflected.get('chain_metal', '')):
            raise ValueError('Shader platform, key or chain mismatch')
        if not (cache / (key + '_b.metallib')).is_file():
            raise ValueError('Missing base Shader library')
    for lib in cache.glob('*.metallib'):
        if lib.is_symlink() or lib.stem.split('_', 1)[0] not in keys:
            raise ValueError('Unexpected Shader library')
        with lib.open('rb') as stream:
            if stream.read(4) != b'MTLB' or lib.stat().st_size < 32:
                raise ValueError('Invalid Shader library')
    if r.target == 'macos' and manifest.get('libraries'):
        from tools.nxrom.shader_package import digest
        inventory = {lib.name: digest(lib) for lib in cache.glob('*.metallib')}
        if manifest.get('libraries') != inventory:
            raise ValueError('Mac Shader library bytes differ from the source-build manifest')
    if r.target == 'ios' and manifest.get('ios_libraries'):
        from tools.nxrom.shader_package import digest
        if manifest['ios_libraries'] != {lib.name: digest(lib) for lib in cache.glob('*.metallib')}:
            raise ValueError('iOS Shader library bytes differ from the source-build manifest')
    return dict(chain=version, inputs=stamp['inputs'], target=r.target, shader_count=len(keys))


def inspect(r):
    """Read-only preflight. No extraction, compilation, subprocess or writes."""
    from tools.packaging_gui import games   # identify is the reader's own report
    issues, checks = [], []
    profile = None
    try:
        profile = profile_for(r)
    except ValueError as exc:
        issues.append('game-profile')
        checks.append(dict(name='game-profile', ok=False, detail=str(exc)))

    def check(name, function):
        try:
            detail = function()
            checks.append(dict(name=name, ok=True, detail=detail))
        except (OSError, ValueError, KeyError, IndexError, TypeError) as exc:
            issues.append(name)
            checks.append(dict(name=name, ok=False, detail=str(exc)))

    def file(value, suffixes=None):
        p = path(value)
        if not p.is_file() or not os.access(p, os.R_OK) or p.stat().st_size == 0:
            raise ValueError('Select a readable nonempty file')
        if suffixes and p.suffix.lower() not in suffixes:
            raise ValueError('Unsupported format: use ' + ', '.join(suffixes))
        return p

    def options_check():
        r.validate_options()
        detail = dict(target=r.target, resource_mode=r.mode, shader=r.shader_action)
        if profile is not None:
            detail['game'] = profile.key
        return detail

    check('options', options_check)
    check('base', lambda: file(r.base, ('.xci', '.nsp')).name)
    check('console-keys', lambda: str(file(r.keys)))
    if profile is not None:
        def support_check():
            gap = capabilities.gap(profile, r.target)
            if gap:
                raise ValueError(gap)
            return dict(graphics_api=profile.graphics_api, archive_format=profile.archive_format,
                        targets=[entry['id'] for entry in capabilities.of(profile)['targets'] if entry['supported']])
        check('graphics-api', support_check)
    if r.update:
        def update_file():
            # A compressed update is not a container the native reader can mount,
            # so it is named here instead of failing later inside the mount.
            selected = path(r.update)
            if selected.suffix.lower() in ('.nsz', '.xcz'):
                raise ValueError('更新包是压缩格式（' + selected.suffix.lower()
                                 + '）：请先用 nsz -D 转成 .nsp 再选择')
            return file(r.update, ('.nsp',)).name
        check('update', update_file)
    if r.easf_key_file:
        def easf_file():
            selected = file(r.easf_key_file, ('.json',))
            if selected.is_relative_to(REPO):
                raise ValueError('Keep the private EASF key file outside the repository')
            return str(selected)
        check('easf-key-file', easf_file)

    def output_check():
        p = path(r.output)
        if not p.is_dir() or not os.access(p, os.W_OK | os.X_OK):
            raise ValueError('Select an existing writable output folder')
        if p.is_relative_to(REPO) or (not r.automatic and p.is_relative_to(Path.home())):
            raise ValueError('Choose the game drive outside the repository and home folder')
        if r.automatic:
            from tools.packaging_gui.cache import NAMESPACE
            if p.is_relative_to(path(r.cache_root) / NAMESPACE):
                raise ValueError('Output must be outside the managed cache namespace')
        if not r.automatic and any(c.isspace() for c in str(p)):
            raise ValueError('The existing host Makefile requires a task path without whitespace')
        for value in (r.cache, r.exefs, r.romfs, r.aoc):
            if value and p.is_relative_to(path(value)):
                raise ValueError('Output must be outside the selected input/cache tree')
        required = 15 * 2**30 if r.shader_action == 'generate' else 8 * 2**30
        if r.mode == 'directory':
            root = path(r.romfs)
            # Work and publication coexist until the copied artifact is audited.
            required += (3 * r.resource_bytes if r.automatic else
                         2 * sum(f.stat().st_size for f in root.rglob('*') if f.is_file()))
        if r.aoc:
            required += 2 * sum(f.stat().st_size for f in path(r.aoc).rglob('*') if f.is_file())
        free = shutil.disk_usage(p).free
        if free < required:
            raise ValueError('Insufficient space for conservative task estimate')
        if r.automatic and shutil.disk_usage(path(r.cache_root)).free < required:
            raise ValueError('Insufficient space on the selected cache disk for temporary work')
        return dict(free_bytes=free, estimated_bytes=required, estimate_only=True)

    check('output-space', output_check)
    selected = {}

    def program_check():
        if profile is None:
            raise ValueError('Select the game profile first')
        version, modules = detect_program(profile, r.exefs)
        selected['version'] = version
        file(str(path(r.exefs).parent / 'control.nacp'))
        return dict(version=version, display=profile.display_of(version), modules=profile.modules)

    check('program-identity', program_check)
    if r.dlcs or r.dlc_warnings:
        check('dlc-discovery', lambda: dict(count=len(r.dlcs),
              indexes=[d['index'] for d in r.dlcs], warnings=list(r.dlc_warnings),
              shader_policy='ordinary AOC resources use the existing program Shader cache; executable modules require rewriting'))
    if profile is not None and r.mode == 'directory' and not r.automatic:
        check('romfs', lambda: str(file(str(path(r.romfs) / profile.romfs_marker))))
    if r.aoc and not (r.automatic and r.dlcs):
        def aoc_check():
            from tools.packaging_gui.dlc import audit_tree
            audit_tree(path(r.aoc), profile.title_id)
            # One numeric folder per add-on index, as dm/host/hle_fs.c mounts them
            # (DM_AOC_DIR/<index>/); an empty folder would be packed silently.
            root = path(r.aoc)
            if not root.is_dir():
                raise ValueError('Select the extracted add-on content folder')
            indexes = sorted((p.name for p in root.iterdir() if p.is_dir() and p.name.isdigit()),
                             key=int)
            if not indexes:
                raise ValueError('Add-on content needs one numeric folder per DLC: <folder>/<index>/')
            empty = [name for name in indexes
                     if not any(f.is_file() for f in (root / name).rglob('*'))]
            if empty:
                raise ValueError('Empty add-on content index folder: ' + ', '.join(empty))
            return dict(indexes=','.join(indexes))
        check('aoc', aoc_check)
    if r.target == 'ios':
        def control_check():
            # build_ipa.sh takes the app name from $W/data/v0/control.nacp, else
            # from the folder next to the RomFS; it never takes it from ExeFS.
            # An external build points ROMFS at that folder, so the metadata must
            # be there before Xcode is started.
            if r.mode == 'directory' and not r.automatic:
                control = path(r.romfs).parent / 'control.nacp'
            else:
                # External mode points ROMFS at ExeFS's parent (see plan()), so
                # the metadata the shell resolves is the one next to ExeFS.
                control = path(r.exefs).parent / 'control.nacp'
            if not control.is_file() or control.stat().st_size == 0:
                raise ValueError('iOS builds read control.nacp from ' + str(control.parent)
                                 + '; select an ExeFS/RomFS whose folder holds it')
            return dict(control=str(control.name))
        check('control-nacp', control_check)

    def container_check():
        from tools.nxrom.resourcefs import ResourceFS
        if profile is None:
            raise ValueError('Select the game profile first')
        version = selected.get('version')
        if version is None:
            raise ValueError('The ExeFS program version could not be established')
        # Only load an explicitly selected existing native reader. This stage
        # does not compile a library just to perform input inspection.
        library = file(r.library, ('.dylib',))
        # title=0 makes the reader report the container's own Program NCA title
        # instead of trusting a constant here: the resource decides which game
        # this is, and a mismatch stops the build before any command is planned.
        with ResourceFS(library, base=file(r.base, ('.xci', '.nsp')),
                        update=file(r.update, ('.nsp',)) if r.update else None,
                        keys=file(r.keys), title=0) as fs:
            found = games.describe(fs.title)
            if not found['ok']:
                raise ValueError(found['message'])
            if found['game'] != profile.key:
                raise ValueError('所选游戏（' + found['title_hex'] + '）不是计划中的 '
                                 + profile.name + '（' + profile.key + '）')
            for module in profile.modules:
                fs.check_build(module, profile.build_ids(version)[module])
        return dict(title_id=found['title_hex'], game=found['game'], name=found['name'],
                    program_version=version)

    check('container-identity', container_check)
    # No EASF line is invented here: reusing a verified Shader cache never opens
    # an EASF archive, so reporting "EASF checked" would be a status nothing
    # performed. The generate path keeps its own automatic key discovery and
    # digest verification in dm/gfx/tools/easf/{keyfind,prepare}.py.
    if r.easf_key_file:
        def easf_file():
            selected = file(r.easf_key_file, ('.json',))
            if selected.is_relative_to(REPO):
                raise ValueError('Keep the private EASF key file outside the repository')
            return '已指定手动 EASF 密钥文件（仅 Shader 生成路径使用）'
        check('easf-key-file', easf_file)
    if r.shader_action == 'reuse':
        check('shader-cache', lambda: validate_cache(r, profile))
    else:
        from tools.packaging_gui import shader_sources
        available = profile is not None and (bool(r.automatic) or shader_sources.for_profile(profile).can_generate)
        checks.append(dict(name='shader-generation', ok=True,
                           detail='No compatible cache; source verification and full compilation will run after confirmation'
                           if available else 'This profile has no Shader generator in the GUI; '
                           'prepare the cache through the existing tools'))
    tools = ['make', 'xcrun'] + (['xcodebuild', 'xcodegen'] if r.target == 'ios' else [])
    if r.shader_action == 'generate':
        tools += ['dotnet', 'spirv-cross']
    for tool in tools:
        def installed(t=tool):
            found = shutil.which(t)
            if not found:
                raise ValueError('Missing tool: ' + t)
            return found
        check('tool-' + tool, installed)
    for module in PYTHON_DEPENDENCIES:
        def dependency(m=module):
            __import__(m)
            return 'available'
        try:
            dependency()
            checks.append(dict(name='python-' + module, ok=True, detail='available'))
        except ImportError:
            issues.append('python-' + module)
            checks.append(dict(name='python-' + module, ok=False, detail='Missing Python dependency: ' + module))
    return dict(schema=1, title_id=profile.key if profile else None, game=profile.key if profile else None,
                input_checks_passed=not issues,
                execution_enabled=False, checks=checks, issues=issues,
                game_run_verified=False, device_run_verified=False)


def redact(value, r):
    """Hide private paths and plausible raw key strings before returning UI data."""
    text = json.dumps(value, ensure_ascii=False)
    values = [(v, label) for v, label in ((r.keys, '<console-key-file>'),
              (r.easf_key_file, '<easf-key-file>'), (r.base, '<base>'),
              (r.update, '<update>'), (r.aoc, '<aoc>'),
              (str(Path.home()), '<home>')) if v]
    for private, label in sorted(values, key=lambda pair: len(pair[0]), reverse=True):
        text = text.replace(json.dumps(private)[1:-1], label)
    text = re.sub(r'(?<![0-9a-fA-F])[0-9a-fA-F]{32,64}(?![0-9a-fA-F])', '<redacted-digest-or-key>', text)
    result = json.loads(text)
    # One dedicated field is exempt: the review fingerprint is public metadata a
    # human must compare against the confirmation sheet it approves. No other
    # digest, Shader hash or key-like string is restored anywhere.
    if isinstance(result, dict) and isinstance(value, dict):
        candidate = value.get('fingerprint')
        if isinstance(candidate, str) and re.fullmatch(r'[0-9a-f]{64}', candidate):
            result['fingerprint'] = candidate
    return result
