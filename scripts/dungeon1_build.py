#!/usr/bin/env python3
"""Dungeon1 single-game builder. Private prepared assets or your own NSP inputs."""
import argparse, hashlib, json, os, re, runpy, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
GAME = '01008F1008DA6000'
PROFILE = ROOT / 'dm/games' / GAME
BUNDLE = 'com.ohxiaoguang.dungeon1'

def run(argv, env=None):
    subprocess.run([str(a) for a in argv], cwd=ROOT, env=env, check=True)

def validate(prepared):
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / 'dm/games'))
    import game
    from tools.nxrom.gl_library import validate as gl_validate
    g = game.load(GAME)
    patched = prepared / 'patched_v393216'
    for module in g.words('modules'):
        data = (patched / (module + '.fixups.tsv')).read_text()
        expected = g.builds()['v393216'][module]
        if '# BUILD_ID\t' + expected not in data:
            raise ValueError('Wrong 1.3.0 Build ID: ' + module)
        if not (patched / (module + '.patched.bin')).is_file():
            raise ValueError('Missing rewritten module: ' + module)
    # The legacy stamp includes all profiles the rewriter imported. Removed game
    # profiles cannot apply to these Build IDs. All retained inputs must match.
    stamp = patched / 'build_src.sha256'
    matched = set()
    for line in stamp.read_text().splitlines():
        sha, name = line.split('  ', 1)
        p = (ROOT / 'dm/tools' / name).resolve()
        if not p.is_relative_to(ROOT):
            raise ValueError('Unsafe source stamp path')
        if not p.exists() and name.startswith('../games/') and GAME not in name:
            continue
        if hashlib.sha256(p.read_bytes()).hexdigest() != sha:
            raise ValueError('Prepared modules need rewriting: ' + name)
        matched.add(name)
    if not {'patch_nso.py','nso_code.py','nso_asm.py','sdk_patches.py', '../games/' + GAME + '/patches.py'} <= matched:
        raise ValueError('Incomplete rewriter source stamp')
    gates = (patched / 'main.gates.tsv').read_text().splitlines()
    patches = runpy.run_path(str(PROFILE / 'patches.py'))
    for kind, table in [('obs','OBS'), ('filter','FILTERS')]:
        for site, number, *_ in patches[table][g.builds()['v393216']['main']]:
            if not any(len(c:=line.split('\t')) >= 4 and c[1] == kind and int(c[2],0) == number and int(c[3],0) == site for line in gates):
                raise ValueError('Missing ' + kind + ' gate ' + str(number))
    for platform in ['gl', 'ios/gl']:
        gl_validate(prepared / 'shader' / platform, PROFILE / 'gl_capture.tsv')
    if not (prepared / 'extract/v393216/RomFS' / g.get('romfs_marker')).is_file():
        raise ValueError('Wrong RomFS')
    return patched

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--target', choices=['mac','ios'], required=True)
    ap.add_argument('--prepared', type=Path, help='Private preparation root: extract/, patched_v393216/, shader/')
    ap.add_argument('--nsp-dir', type=Path, help='Bootstrap/rewrite from privately supplied base/update containers')
    ap.add_argument('--keys', type=Path)
    ap.add_argument('--icon', type=Path, help='Private user-supplied PNG; never copied into source')
    ap.add_argument('--font-python', default=os.environ.get('FONT_PY',sys.executable), help='Python with fonttools')
    ap.add_argument('--work', type=Path, required=True, help='Private build/cache directory on a volume with free space')
    ap.add_argument('--out', type=Path, required=True, help='New Dungeon1.app or Dungeon1.ipa path')
    ap.add_argument('--resource-backend', choices=['directory','nsp'], default='directory')
    a = ap.parse_args()
    a.work = a.work.resolve(); a.out = a.out.resolve()
    a.work.mkdir(parents=True, exist_ok=True); a.out.parent.mkdir(parents=True, exist_ok=True)
    if a.out.exists(): ap.error('--out must be a new path')
    if bool(a.prepared) == bool(a.nsp_dir): ap.error('Choose --prepared or --nsp-dir')
    env = dict(os.environ, DM_GAME=GAME, GAME=GAME, PYTHON=sys.executable,
               PYTHONDONTWRITEBYTECODE='1', CLANG_MODULE_CACHE_PATH=str(a.work/'clang-cache'),
               SWIFT_MODULECACHE_PATH=str(a.work/'swift-cache'), TMPDIR=str(a.work/'tmp'))
    Path(env['TMPDIR']).mkdir(exist_ok=True)
    # Original artwork is rendered from source; no game artwork is used.
    icon = a.icon.resolve() if a.icon else ROOT / 'assets/app-icon/dungeon1.png'
    if a.icon and not icon.is_file(): ap.error('Missing --icon image')
    if not icon.exists():
        run(['xcrun','swift','-module-cache-path', a.work/'swift-cache', ROOT/'assets/app-icon/make_icon.swift', icon], env)
    if a.nsp_dir:
        if a.resource_backend != 'directory': ap.error('Bootstrap currently prepares bundled directory mode; use --prepared for external mode')
        keys = a.keys or a.nsp_dir/'prod.keys'
        env['DUNGEON1_PREPARE_WORK'] = str(a.work/'prepared')
        env['DM_ICON'] = str(icon)
        command = [sys.executable, ROOT/'scripts/build_ipa_from_nsp.py', a.nsp_dir, '--keys',keys,
                   '--package','v393216','--app-name','Dungeon1','--bundle-id',BUNDLE,'--keep-extracted']
        command += ['--platform','mac'] if a.target == 'mac' else ['--out',a.out]
        run(command, env)
        if a.target == 'mac':
            run([sys.executable, Path(__file__), '--target','mac','--prepared',a.work/'prepared',
                 '--font-python',a.font_python,'--icon',icon,'--work',a.work/'package','--out',a.out],env)
        return
    prepared = a.prepared.resolve()
    patched = validate(prepared)
    print('1.3.0 Build IDs, retained rewriter sources, input gates and both GL libraries verified', flush=True)
    romfs = prepared/'extract/v393216/RomFS'
    aoc = prepared/'aoc'
    if aoc.exists() and not (aoc/'manifest.json').is_file():
        candidates = sorted(prepared.glob('aoc-*/manifest.json'))
        if len(candidates) != 1: raise ValueError('Supply a preparation with one verified AOC manifest')
        aoc = candidates[0].parent
    if aoc.exists():
        from tools.packaging_gui.dlc import audit_tree
        audit_tree(aoc, int(GAME,16))
    if a.target == 'mac':
        host = a.work/'dmhost'
        run(['make','-C',ROOT/'dm/host','GAME='+GAME,'HOST='+str(host),'GEN='+str(a.work/'host-gen')],env)
        font = a.work/'font'; font.mkdir(exist_ok=True)
        import shutil
        shutil.copyfile('/System/Library/Fonts/Supplemental/Arial Unicode.ttf',font/'standard.ttf')
        run([a.font_python,ROOT/'dm/tools/make_ext_font.py',font/'nintendo_ext.ttf'],env)
        settings = a.work/'launcher.json'
        run([sys.executable, ROOT/'dm/games/settings.py',GAME,patched,prepared/'extract/v393216/control.nacp',settings],env)
        command = [sys.executable,ROOT/'scripts/build_mac_app.py','--resource-backend',a.resource_backend,
                   '--host',host,'--patched',patched,'--shaders',prepared/'shader/gl','--profile',PROFILE,
                   '--font',font,'--settings',settings,'--output',a.out,'--title-id',GAME,'--name','Dungeon1','--version','1.3.0']
        if a.resource_backend == 'directory':
            command += ['--romfs',romfs]
            if aoc.exists(): command += ['--aoc',aoc]
        run(command,env)
        import plistlib
        info = a.out/'Contents/Info.plist'; data=plistlib.loads(info.read_bytes()); data['CFBundleIconFile']='Dungeon1'; info.write_bytes(plistlib.dumps(data))
        iconset=a.work/'Dungeon1.iconset'; iconset.mkdir(exist_ok=True)
        for size in (16,32,128,256,512):
            for factor in (1,2):
                name='icon_%dx%d%s.png'%(size,size,'@2x' if factor==2 else '')
                run(['sips','-z',size*factor,size*factor,icon,'--out',iconset/name],env)
        run(['iconutil','-c','icns',iconset,'-o',a.out/'Contents/Resources/Dungeon1.icns'],env)
        run(['codesign','--force','--deep','--sign','-',a.out],env)
    else:
        env.update(W=str(a.work/'ios-work'), PATCHED=str(patched), ROMFS=str(romfs),
                   MSL_IOS=str(prepared/'shader/ios'), AOC=str(aoc) if aoc.exists() and a.resource_backend=='directory' else '',
                   GFXAPI='gl', FONT_PY=a.font_python, DM_DISPLAY_NAME='Dungeon1', DM_APP_VERSION='1.3.0',
                   DM_BUNDLE_ID=BUNDLE, DM_ICON=str(icon), DM_RESOURCE_BACKEND=a.resource_backend,
                   DM_IOS_BUILD_DIR=str(a.work/'ios-project'), DM_XCODE_DERIVED_DATA=str(a.work/'xcode-dd'))
        run(['bash',ROOT/'dm/ios/tools/build_ipa.sh',a.out],env)
    print('Built local private artifact:',a.out)

if __name__ == '__main__': main()
