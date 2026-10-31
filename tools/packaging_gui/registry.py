"""The game profile registry: one description of every registered game.

The supported-games list and the build engine read this model, so a profile that
is listed is exactly a profile the engine can plan for. Nothing here decides
that a game is supported because of its name: `dm/games/<title ID>/game.tsv`
supplies the constants, `tools/packaging_gui/capabilities.py` decides what the
engine can do with them, and `data/evidence.tsv` records what was actually
built and run.

The registry is the data boundary for a future standalone App: `catalog()` is
the payload the GUI consumes, `write_index()` generates it into a file, and
`load_index()` reads such a file, so a build without the source checkout still
has the game list.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[2]
GAMES = REPO / 'dm/games'
EVIDENCE = Path(__file__).resolve().parent / 'data' / 'evidence.tsv'

if str(GAMES) not in sys.path:
    sys.path.insert(0, str(GAMES))
import game as game_profiles   # dm/games/game.py, the one reader of game.tsv

# Profile keys the engine reads that do not exist upstream. Each is optional and
# has a documented default, so an upstream profile stays valid as it is. None of
# them start with `shader_` / `nvn_`: those are chain inputs, and adding one would
# invalidate every built Shader cache.
EXTRA_KEYS = ('app_name', 'graphics_api', 'archive_format', 'archive_container', 'archive_member')
GRAPHICS_APIS = ('nvn', 'vulkan', 'gl')
# What a profile's Shaders are, and therefore what prepares them: NVN's own
# shaders, EA's EASF archives, or GLSL the game itself compiles (graphics_api gl
# answers its GL calls in the host, so its library is one table plus one
# metallib and has no chain version).
ARCHIVE_FORMATS = ('nvn', 'easf', 'glsl')
# The tables a cache carries a copy of. A cached copy that differs from the
# repository is not the profile the libraries were built from.
CACHE_TABLES = ('game.tsv', 'bf_want.tsv', 'pso_manifest.tsv', 'shader_pairs_extra.tsv',
                'shader_map.tsv', 'shader_facts.tsv', 'shader_pairs.tsv')


def title_hex(value):
    """-> the 16-digit uppercase form used in the UI, the profile folder and DM_GAME."""
    return format(parse_title(value), '016X')


def parse_title(value):
    """-> the numeric Title ID of an int or of its 16 hex digits."""
    return value if isinstance(value, int) else int(str(value).strip(), 16)


@dataclass(frozen=True)
class Profile:
    """One registered game, read from `dm/games/<title ID>/game.tsv`."""
    key: str                      # folder name: the base game Title ID, uppercase hex
    title_id: int
    name: str                     # human label for lists, errors and the Mac window title
    app_name: str                 # bundle display name and artifact base name
    ipa: str
    category: str
    modules: tuple                # code modules rewritten and loaded, in load order
    versions: tuple               # ((version, display version, {module: build id}), ...) in file order
    package: str
    shader_versions: tuple
    romfs_marker: str
    graphics_api: str             # nvn / vulkan / gl
    archive_format: str           # nvn / easf / glsl
    archive_container: str
    archive_members: tuple
    mem_reserve: int
    source: object = None         # dm/games/game.Game for the tools that take one
    error: str = ''               # non-empty: the profile is present but unreadable/incomplete

    @property
    def title_hex(self):
        return format(self.title_id, '016X')

    @property
    def readable(self):
        return not self.error

    def display_of(self, version):
        for name, display, _ in self.versions:
            if name == version:
                return display
        raise KeyError(version)

    def build_ids(self, version):
        for name, _, ids in self.versions:
            if name == version:
                return ids
        raise KeyError(version)

    def table(self, name):
        """-> the path of one profile file; the tools read it from there."""
        return Path(self.source.dir) / name if self.source else Path(self.key) / name

    def game(self):
        if self.source is None:
            raise ValueError('profile ' + self.key + ' is not readable: ' + (self.error or 'unknown error'))
        return self.source


def _profile(folder):
    """One profile folder -> Profile. A damaged profile is reported, never raised."""
    key = folder.name
    try:
        source = game_profiles.Game(folder)
    except (OSError, ValueError, UnicodeDecodeError) as error:
        try:
            title = int(key, 16)
        except ValueError:
            title = 0
        return Profile(key=key, title_id=title, name=key, app_name=key, ipa='', category='',
                       modules=(), versions=(), package='', shader_versions=(), romfs_marker='',
                       graphics_api='nvn', archive_format='nvn', archive_container='', archive_members=(),
                       mem_reserve=0, error='unreadable game.tsv: ' + str(error).strip())
    problems = []
    try:
        title = source.title_id
    except (KeyError, ValueError):
        problems.append('no readable title_id')
        title = int(key, 16) if _is_hex(key) else 0
    if _is_hex(key) and title != int(key, 16):
        problems.append('title_id ' + format(title, '016X') + ' differs from the folder name')
    name = source.get('name', '') or key
    graphics = (source.get('graphics_api', 'nvn') or 'nvn').lower()
    if graphics not in GRAPHICS_APIS:
        problems.append('graphics_api must be one of ' + ', '.join(GRAPHICS_APIS) + ': ' + graphics)
        graphics = 'nvn'
    archive = (source.get('archive_format', 'nvn') or 'nvn').lower()
    if archive not in ARCHIVE_FORMATS:
        problems.append('archive_format must be one of ' + ', '.join(ARCHIVE_FORMATS) + ': ' + archive)
        archive = 'nvn'
    try:
        modules = tuple(source.words('modules'))
        versions = tuple((version, display, dict(ids))
                         for version, display, ids in _build_rows(source))
        package = source.get('package', '')
        shader_versions = tuple(source.words('shader_versions', ''))
        romfs_marker = source.get('romfs_marker', '')
        mem_reserve = source.int('mem_reserve') if source.get('mem_reserve', '') else 0
        ipa = source.get('ipa', '')
        category = source.get('app_category', '')
    except (KeyError, ValueError) as error:
        problems.append(str(error))
        modules, versions, package, shader_versions = (), (), '', ()
        romfs_marker, mem_reserve, ipa, category = '', 0, '', ''
    if not modules:
        problems.append('no modules row')
    if not versions:
        problems.append('no build rows')
    return Profile(key=key, title_id=title, name=name,
                   app_name=source.get('app_name', '') or name, ipa=ipa, category=category,
                   modules=modules, versions=versions, package=package,
                   shader_versions=shader_versions, romfs_marker=romfs_marker,
                   graphics_api=graphics, archive_format=archive,
                   archive_container=source.get('archive_container', ''),
                   archive_members=tuple(row[0] for row in source.values('archive_member')),
                   mem_reserve=mem_reserve, source=source, error='; '.join(problems))


def _is_hex(value):
    try:
        int(value, 16)
        return len(value) == 16
    except (TypeError, ValueError):
        return False


def _build_rows(source):
    """`build <version> <display> <module>=<build id>...` -> (version, display, ids)."""
    for row in source.values('build'):
        ids = dict(item.split('=', 1) for item in row[2:] if '=' in item)
        yield row[0], row[1] if len(row) > 1 else row[0], ids


_PROFILE_CACHE = {}


def _signature(root):
    """A cheap fingerprint of the profile folders: names and game.tsv timestamps."""
    if not root.is_dir():
        return ()
    return tuple((folder.name, (folder / 'game.tsv').stat().st_mtime_ns)
                 for folder in sorted(root.iterdir())
                 if folder.is_dir() and (folder / 'game.tsv').is_file())


def profiles(games=GAMES):
    """-> every registered profile, by name; an empty tuple when no profile exists.

    The scan is memoised on the folders' own timestamps: the supported-games
    window and every bridge action read the same list without re-parsing 59
    profiles per call, and a profile edited on disk is still picked up.
    """
    root = Path(games)
    signature = _signature(root)
    cached = _PROFILE_CACHE.get(root)
    if cached is not None and cached[0] == signature:
        return cached[1]
    found = tuple(sorted((_profile(Path(root) / key) for key, _ in signature),
                         key=lambda profile: (profile.name.casefold(), profile.key)))
    _PROFILE_CACHE[root] = (signature, found)
    return found


def by_key(key, games=GAMES):
    wanted = str(key).strip().upper()
    return next((profile for profile in profiles(games) if profile.key.upper() == wanted), None)


def by_title(value, games=GAMES):
    """-> the profile whose base Title ID is exactly `value`, or None."""
    try:
        wanted = parse_title(value)
    except (TypeError, ValueError):
        return None
    return next((profile for profile in profiles(games) if profile.title_id == wanted), None)


def update_delta():
    """An update package carries the base Title ID plus this."""
    return 0x800


def evidence(title):
    """-> the recorded evidence for one game, from the curated table.

    Only explicit records are returned. An absent row means "no record", which is
    not the same as "unsupported" and never becomes a success claim.
    """
    row = _evidence().get(format(parse_title(title), '016X'))
    return row or dict(build='none', runtime='none', source='', note='')


_EVIDENCE_CACHE = {}


def _evidence():
    stamp = EVIDENCE.stat().st_mtime_ns if EVIDENCE.is_file() else None
    cached = _EVIDENCE_CACHE.get('rows')
    if cached is not None and _EVIDENCE_CACHE.get('stamp') == stamp:
        return cached
    rows = {}
    if EVIDENCE.is_file():
        for line in EVIDENCE.read_text(encoding='utf-8').splitlines():
            if not line.strip() or line.lstrip().startswith('#'):
                continue
            columns = line.split('\t')
            if len(columns) < 3:
                continue
            title, build, runtime = (value.strip() for value in columns[:3])
            rows[title.upper()] = dict(build=build, runtime=runtime,
                                      source=columns[3].strip() if len(columns) > 3 else '',
                                      note=columns[4].strip() if len(columns) > 4 else '')
    _EVIDENCE_CACHE.update(rows=rows, stamp=stamp)
    return rows


def catalog(games=GAMES):
    """-> the payload the supported-games window and a bundled index share.

    `capability` is computed by the engine's own rule set, so the list never
    claims a build the engine would refuse; `evidence` is a separate record and
    never inferred from a profile's presence.
    """
    from tools.packaging_gui import capabilities
    registered = profiles(games)
    return dict(schema=1, source='dm/games',
                generated=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
                count=len(registered),
                games=[_summary(profile, capabilities.of(profile)) for profile in registered])


def _summary(profile, capability):
    return dict(
        id=profile.key,
        title_id=profile.title_hex,
        name=profile.name,
        app_name=profile.app_name,
        error=profile.error,
        versions=[dict(version=version, display=display,
                       modules=sorted(ids), build_ids=ids)
                  for version, display, ids in profile.versions],
        package=profile.package,
        shader_versions=list(profile.shader_versions),
        modules=list(profile.modules),
        romfs_marker=profile.romfs_marker,
        graphics_api=profile.graphics_api,
        archive_format=profile.archive_format,
        capability=capability,
        evidence=evidence(profile.title_id),
    )


def write_index(path, games=GAMES):
    """Write the catalog as a standalone JSON document (for a bundled App)."""
    payload = catalog(games)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, sort_keys=False) + '\n', encoding='utf-8')
    return target


def load_index(path):
    """-> a catalog written by write_index(); the reader side of the same boundary."""
    payload = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(payload, dict) or payload.get('schema') != 1 or not isinstance(payload.get('games'), list):
        raise ValueError('not a game catalog: ' + str(path))
    return payload


def main(argv=None):
    """`python3 -m tools.packaging_gui.registry [--games DIR] [--index OUT] [--list]`."""
    import argparse
    parser = argparse.ArgumentParser(description='Generate or list the game profile catalog.')
    parser.add_argument('--games', type=Path, default=GAMES, help='profile root (default: dm/games)')
    parser.add_argument('--index', type=Path, help='write the catalog JSON to this new file')
    parser.add_argument('--list', action='store_true', help='print one line per registered game')
    args = parser.parse_args(argv)
    if args.index:
        target = write_index(args.index, args.games)
        print('wrote ' + str(target) + ' (' + str(len(profiles(args.games))) + ' profiles)')
    if args.list or not args.index:
        for profile in profiles(args.games):
            print('\t'.join([profile.key, profile.title_hex, profile.name,
                             'error: ' + profile.error if profile.error else 'ok']))
    return 0


if __name__ == '__main__':
    sys.exit(main())
