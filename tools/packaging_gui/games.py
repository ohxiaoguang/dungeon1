"""Identify the game a resource really is, from the resource itself.

The registry decides the list; this module maps the Title ID the native reader
reports to a registered profile and explains anything else. A file name or a
folder name never decides which game is being packaged, and an update package
carries a different Title ID (base + 0x800) which is reported as such instead of
being mistaken for another base game.

A registered profile is a plan target, not a verification claim: which platforms
and modes the engine can build is `tools/packaging_gui/capabilities.py`, and what
was built and run is `tools/packaging_gui/data/evidence.tsv`.
"""
from tools.packaging_gui import registry


def title_hex(value):
    """-> the 16-digit uppercase form used in the UI and in errors."""
    return registry.title_hex(value)


def parse(value):
    """-> the numeric Title ID of an int or of its 16 hex digits."""
    return registry.parse_title(value)


def by_key(key):
    """-> the profile whose key (its folder name) is `key`, or None."""
    return registry.by_key(key)


def by_title(value):
    """-> the profile whose base Title ID is exactly `value`, or None."""
    return registry.by_title(value)


def update_title(profile):
    """-> the Title ID an update package of this base game carries."""
    return profile.title_id + registry.update_delta()


def supported():
    """-> every registered profile, as the games list shows them."""
    return registry.profiles()


def describe(title):
    """-> what a raw Program NCA Title ID is, without touching any file.

    Every result is a JSON-ready dict so the bridge, the review report and the
    GUI share one vocabulary. `ok` is true only for a registered base game;
    everything else stops the build with a readable reason.
    """
    value = parse(title)
    profile = registry.by_title(value)
    if profile:
        return dict(ok=True, kind='base', title_id=value, title_hex=title_hex(value),
                    game=profile.key, name=profile.name,
                    message='已识别：' + profile.name + '（' + title_hex(value) + '）')
    for candidate in registry.profiles():
        if value == update_title(candidate):
            return dict(ok=False, kind='update', title_id=value, title_hex=title_hex(value),
                        game=candidate.key, name=candidate.name,
                        message=('这是 ' + candidate.name + ' 的更新包（Title ID ' + title_hex(value)
                                 + '），不是游戏本体。请把基础游戏文件选为「游戏本体」，'
                                 '更新包选为「更新包」。'))
    return dict(ok=False, kind='unknown', title_id=value, title_hex=title_hex(value),
                game=None, name=None,
                message=('无法识别的游戏：资源内的 Title ID 是 ' + title_hex(value)
                         + '，dm/games 中没有对应的 Profile。请确认所选文件是基础游戏'
                         '（.xci / .nsp），而不是更新包、DLC 或解包后的目录；'
                         '新游戏的 Profile 需要先按 dm/games/README.md 登记。'))


def identify(base, keys, library, update=None):
    """Mount read-only and report the base game found in the resource itself.

    No extraction, no key logging: the reader names the Title ID, this module
    only maps it. A mount failure is turned into a Chinese diagnostic that
    says which input to re-check, because the GUI has no other channel to
    explain a native error.
    """
    from tools.nxrom.resourcefs import ResourceFS
    try:
        with ResourceFS(str(library), base=str(base), keys=str(keys),
                        update=str(update) if update else None, title=0) as fs:
            return describe(fs.title)
    except (OSError, ValueError) as error:
        detail = str(error).strip() or error.__class__.__name__
        return dict(ok=False, kind='error', title_id=None, title_hex=None, game=None,
                    name=None,
                    message=('无法读取游戏资源：' + detail
                             + '。请确认 prod.keys 与游戏本体匹配、文件完整，'
                               'Also confirm the bundled Reader resources are intact.'))
