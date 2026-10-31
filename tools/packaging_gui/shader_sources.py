"""Shader source formats: what prepares a game's Shaders, and what a cache must prove.

Shader source providers describe real format differences, and both are resource formats, not games:

``nvn``   The game's own NVN shaders, split into the profile's tables and built by
          ``dm/gfx/tools/dmsh_build.py``. The automatic provider stages registered
          source files and invokes the production splitter and compiler.
``easf``  EA's shader archives (FIFA 23): the archives sit inside one RomFS file
          as BIG4 members and are encrypted with an EASF key. The provider
          prepares them with automatic key discovery from the game's own program
          module and then runs the same ``dmsh_build.py`` chain. Only the input
          preparation differs, which is why it is a provider here and not a
          separate packaging flow.

``glsl``  The game compiles GLSL itself and the host answers its GL calls
          (``dm/gfx/gl/hle_gl.m``): Darkest Dungeon. There is no chain version and
          no constant segment table; the library is one metallib plus the table
          that names its Metal functions, and the host finds a program by the hash
          of the source the game handed ``glShaderSource``.

A profile names its format with the optional ``archive_format`` key; the archive
location comes from ``archive_container`` / ``archive_member``, so no game-specific dispatch
appears in this module. ``graphics_api`` says how the host renders, which is a
separate fact: a Vulkan game still builds NVN-chain libraries today.
"""
from pathlib import Path


class NvnSource:
    """The game's NVN shaders, prepared from verified registered sources."""

    key = 'nvn'
    can_generate = True
    # Libraries are named after the chain version and the audits read its stamp.
    needs_chain = True
    layer = None

    def library_dir(self, root, target, chain):
        base = Path(root) / 'shaders' if target == 'macos' else Path(root) / 'ios' / 'dmsh_b'
        return base / ('b-' + chain)

    def library_name(self, profile=None, chain=None):
        return 'b-' + chain

    def prepare(self, request, profile, output, run):
        from tools.packaging_gui.shader_build import nvn_prepare
        return nvn_prepare(request, profile, output, run)

    def generation_command(self, request, profile, shader, exefs, python, repo):
        raise ValueError('Full Shader generation for this profile has no command in the GUI; '
                         'build the cache with dm/gfx/tools/dmsh_build.py and select it')

    def check_cache(self, profile, root, manifest, chain, cached_profile):
        """Nothing archive-specific: validate_cache checks tables, stamp and bytes."""
        return None


class EasfSource:
    """EA shader archives: BIG4 members of one RomFS file, EASF-encrypted."""

    key = 'easf'
    can_generate = True
    needs_chain = True
    layer = None

    def library_dir(self, root, target, chain):
        return NvnSource().library_dir(root, target, chain)

    def library_name(self, profile=None, chain=None):
        return 'b-' + chain

    def prepare(self, request, profile, output, run):
        from tools.packaging_gui.shader_build import easf_prepare
        return easf_prepare(request, profile, output)

    def generation_command(self, request, profile, shader, exefs, python, repo):
        if not profile.archive_container or not profile.archive_members:
            raise ValueError(profile.name + ' declares archive_format easf but no archive_container / '
                             'archive_member rows; the Shader archives cannot be located')
        args = [python, repo / 'scripts/build_fifa23.py',
                '--base', Path(request.base), '--keys', Path(request.keys),
                '--out', shader, '--exefs', exefs.resolve(), '-j', request.jobs,
                '--datax', profile.archive_container]
        for member in profile.archive_members:
            args += ['--member', member]
        if request.update:
            args += ['--update', Path(request.update)]
        if request.easf_key_file:
            args += ['--key-file', Path(request.easf_key_file)]
        extra = {'IOSOUT': str(shader / 'ios/dmsh_b')} if request.target == 'ios' else {}
        return dict(argv=args, environment=extra)

    def check_cache(self, profile, root, manifest, chain, cached_profile):
        """A reused EASF cache must be the output of a completed source build.

        The prepared archive package and the manifest's source markers are the
        evidence that the Shaders came from this game's archives through the
        verified key, not from a partial or hand-assembled directory.
        """
        if manifest.get('chain') != chain.version():
            raise ValueError('Select a completed ' + profile.name + ' source build with a matching chain manifest')
        generated = manifest.get('source_generation', {})
        if generated.get('provider') == 'easf':
            if (generated.get('versions') != list(profile.shader_versions)
                    or not generated.get('archives') or not manifest.get('packages')):
                raise ValueError('Missing EASF source-generation evidence')
            from tools.nxrom.shader_package import digest
            if manifest['packages'] != {p.name: digest(p) for p in (root / 'pkg').glob('*.bin')}:
                raise ValueError('EASF source package bytes changed')
            return
        if manifest.get('host_from_source') is not True:
            raise ValueError('Select a completed ' + profile.name + ' source build with a matching chain manifest')
        if not (root / 'pkg').is_dir() or not list((root / 'pkg').glob('*.bin')):
            raise ValueError('Missing ' + profile.name + ' Shader Package; select a complete source build')


class GlslSource:
    """GLSL the game compiles itself, translated for the host's GL layer.

    ``dm/gfx/tools/gl_shaders.py`` reads the game's own sources (the RomFS .glsl
    files and the GLSL strings embedded in ``main``), translates every stage and
    writes ``<root>/gl/gl_shaders.metallib`` beside the table that names its
    Metal functions (``gl_<key>_v`` / ``gl_<key>_f``). There is no chain version,
    no constant-segment table and no ``inputs.tsv`` stamp: the host finds a
    program by the hash of the source the game handed ``glShaderSource``, which is
    the table's first column, and ``gl_capture.tsv`` records the keys a real run
    asked for.

    Generation needs the game's extracted RomFS and program, which this engine
    does not stage for a layer game yet; ``scripts/build_ipa_from_nsp.py`` runs
    the same translator, and the cache it writes is what a build selects.
    """

    key = 'glsl'
    can_generate = False
    needs_chain = False
    layer = 'gl'

    def library_dir(self, root, target, chain=None):
        """macOS: <cache>/gl; iPhone: <cache>/ios/gl (what build_ipa.sh reads from MSL_IOS)."""
        return Path(root) / 'gl' if target == 'macos' else Path(root) / 'ios' / 'gl'

    def library_name(self, profile=None, chain=None):
        return self.layer

    def prepare(self, request, profile, output, run):
        raise ValueError('The GUI does not prepare ' + profile.name + ' Shaders: its GLSL comes from the '
                         'game files themselves; run scripts/build_ipa_from_nsp.py once and select the cache')

    def generation_command(self, request, profile, shader, exefs, python, repo):
        raise ValueError('The GUI does not generate a GL Shader library: dm/gfx/tools/gl_shaders.py reads the '
                         'game\'s RomFS and main, so run scripts/build_ipa_from_nsp.py (or gl_shaders.py itself) '
                         'once and select the cache it writes')

    def check_cache(self, profile, root, manifest, chain, cached_profile):
        """A GL library is one metallib and the table naming its functions."""
        return self.validate_cache(profile, root, 'macos', cached_profile)

    def validate_cache(self, profile, root, target, cached_profile):
        """-> the summary every audit reads, for a layer library instead of a chain build.

        What a layer cache must prove: the table and its metallib are present and
        non-empty, the table names every program ``gl_capture.tsv`` recorded a real
        run compiling (a key the library misses is a draw the host would skip), and
        the profile copy inside the cache is the repository profile, so the bytes
        audited later are the bytes this profile describes.
        """
        from tools.nxrom.shader_package import digest
        root = Path(root)
        folder = self.library_dir(root, target)
        table = folder / 'gl_shaders.tsv'
        library = folder / 'gl_shaders.metallib'
        if not table.is_file() or not library.is_file():
            raise ValueError('Select a completed GL Shader build: ' + str(folder)
                             + ' holds no gl_shaders.tsv / gl_shaders.metallib')
        from tools.nxrom.gl_library import validate
        summary = validate(folder, profile.table('gl_capture.tsv'))
        # The cache's own profile copy is what the App will carry; a cache built
        # from another revision of the profile is not the profile being audited.
        from tools.packaging_gui import registry
        for name in registry.CACHE_TABLES + ('gl_capture.tsv',):
            original = profile.table(name)              # the repository profile
            cached = Path(cached_profile.dir) / name    # the copy inside the cache
            if not original.is_file():
                continue
            if not cached.is_file():
                raise ValueError('Cache carries no profile copy: ' + name + '; select a completed build')
            if name == 'game.tsv':
                # cached_profile IS the cache's own game.tsv reader; the repository
                # profile is profile.game(). GUI labels do not affect compiled inputs.
                def relevant(game):
                    return [(k, v) for k, v in game.rows if k not in registry.EXTRA_KEYS]
                if relevant(cached_profile) != relevant(profile.game()):
                    raise ValueError('Cached Profile differs from repository: game.tsv')
            elif digest(cached) != digest(original):
                raise ValueError('Cached Profile differs from repository: ' + name)
        return dict(chain=None, inputs={}, target=target, shader_count=summary['shader_count'],
                    layer=self.layer, provider=self.key,
                    library=library.name, table=table.name)


PROVIDERS = {provider.key: provider for provider in (NvnSource(), EasfSource(), GlslSource())}


def for_profile(profile):
    """-> the provider the profile's archive_format names."""
    provider = PROVIDERS.get(profile.archive_format)
    if provider is None:
        raise ValueError('Unknown archive_format ' + profile.archive_format + ' in profile ' + profile.key)
    return provider
