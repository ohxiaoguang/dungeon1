"""What the generic build engine can really do for one profile.

Capability is derived from the profile and the engine's own dependencies, never
from a list of game names: every registered profile resolves to the same stage
sequence, and the entries that differ are the ones a real missing piece or a
resource format makes impossible. Nothing here turns a gap into a selectable
option — a gap is reported as a reason the engine refuses.
"""

TARGETS = ('macos', 'ios')
MODES = ('nsp', 'directory')
# The App and IPA audits read their Shader library's own layout. The NVN chain has
# msl/b-<chain> with a stamp and constant-segment tables; an OpenGL game has
# msl/gl with one metallib and the table naming its Metal functions, which the
# audits check as a library and against gl_capture.tsv. A Vulkan game (msl/vk) has
# no artifact audit yet, so it stays unbuildable until one exists.
AUDITED_BACKENDS = ('nvn', 'gl')
# Per backend, the targets whose artifact audit really reads that layout. The
# macOS App audit and the IPA audit both understand msl/gl: the IPA one checks
# the layer's two files and their bytes against the validated cache, which
# gl_library.validate bound to gl_capture.tsv before packaging.
AUDITED_TARGETS = {'nvn': TARGETS, 'gl': TARGETS}
# build_ipa.sh writes the extended-virtual-addressing entitlement file only for a
# guest reservation above this; below it the unsigned IPA needs none.
IOS_ENTITLEMENT_ABOVE = 0x180000000

TARGET_NAMES = {'macos': 'macOS App', 'ios': 'iOS IPA'}
MODE_NAMES = {'nsp': 'External XCI / NSP', 'directory': 'Bundled resources (Directory)'}


def of(profile):
    """-> the capability record for one Profile, as JSON-ready data."""
    limitations = []
    targets = []
    for target in TARGETS:
        reason = _target_gap(profile, target)
        targets.append(dict(id=target, name=TARGET_NAMES[target], supported=not reason, reason=reason))
        if reason:
            limitations.append(TARGET_NAMES[target] + ': ' + reason)
    modes = [dict(id=mode, name=MODE_NAMES[mode], supported=True, reason='') for mode in MODES]
    if profile.mem_reserve > IOS_ENTITLEMENT_ABOVE:
        limitations.append('iOS needs the extended-virtual-addressing entitlement when signing '
                           '(guest reservation above 6 GB)')
    if profile.archive_format == 'glsl':
        limitations.append('Shader source is GLSL: reuse needs a completed GL library (gl_shaders.tsv and its '
                           'metallib); the GUI does not generate it, scripts/build_ipa_from_nsp.py does')
    elif profile.archive_format != 'nvn':
        limitations.append('Shader source is ' + profile.archive_format.upper()
                           + ': reuse needs a completed ' + profile.archive_format.upper()
                           + ' source build; automatic generation verifies the source archives')
    if not profile.readable:
        limitations.append('Profile is not readable: ' + profile.error)
    return dict(
        targets=targets,
        modes=modes,
        graphics_api=profile.graphics_api,
        archive_format=profile.archive_format,
        # Reuse is the one Shader path the GUI executes; generation stays a
        # preview everywhere because its tools are not part of this delivery.
        shader_reuse=bool(profile.shader_versions) and profile.readable,
        shader_generation='automatic (source verification required)',
        # A registered profile is a plan target; it is not a verification claim.
        plan_supported=profile.readable and all(entry['supported'] for entry in targets),
        limitations=limitations,
    )


def _target_gap(profile, target):
    if not profile.readable:
        return 'profile is not readable'
    if profile.graphics_api not in AUDITED_BACKENDS:
        return (profile.graphics_api + ' Shader libraries have no artifact audit in this engine '
                '(the audits read the NVN chain layout)')
    if profile.graphics_api == 'gl' and profile.archive_format != 'glsl':
        # The GL layer reads <DM_MSL_DIR>/gl/gl_shaders.tsv; an NVN or EASF chain
        # build writes msl/b-<chain> and would leave that table empty, so such a
        # profile stays unbuildable until its Shader source is translated.
        return ('graphics_api gl with archive_format ' + profile.archive_format
                + ': the GL layer reads msl/gl, which a chain build does not produce')
    if target not in AUDITED_TARGETS.get(profile.graphics_api, ()):
        return (profile.graphics_api + ' Shader libraries have no ' + TARGET_NAMES[target]
                + ' artifact audit yet (it reads the NVN chain layout)')
    if not profile.modules:
        return 'profile registers no code modules'
    if not profile.versions:
        return 'profile registers no program version'
    return ''


def gap(profile, target):
    """-> why this target cannot be built, or '' when the engine can plan it."""
    return _target_gap(profile, target)


def audited(profile):
    return profile.graphics_api in AUDITED_BACKENDS
