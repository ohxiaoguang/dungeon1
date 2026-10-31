#!/usr/bin/env python3
"""Audit the Git index and all reachable history without printing secret values."""
import csv, hashlib, json, re, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BAD={'.nsp','.xci','.nsz','.ncz','.xcz','.nca','.nso','.nro','.keys','.key','.tik',
     '.ipa','.metallib','.air','.ttf','.otf','.dds','.bank','.mp4','.raw','.dump',
     '.patched.bin','.dylib','.a','.o','.zip','.jpg','.jpeg','.dSYM'}
FORBIDDEN_DIRS={'romfs','exefs','save','saves','payload','private','release','build'}
SECRETS=[re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
         re.compile(rb'gh[pousr]_[A-Za-z0-9]{30,}'),
         re.compile(rb'(?m)^\s*(?:master_key_[0-9a-f]+|header_key|titlekek_[0-9a-f]+|key_area_key_\w+)\s*=\s*[0-9a-fA-F]{32,}')]

def git(*args): return subprocess.check_output(['git',*args],cwd=ROOT)

def main():
    known={row['path']:row['sha256'] for row in csv.DictReader((ROOT/'dm/third_party/translator-runtime/binaries.tsv').open(),delimiter='\t')}
    issues=[]; checked=set(); indexed=[]
    def check(name,data):
        identity=(name,hashlib.sha256(data).hexdigest())
        if identity in checked:return
        checked.add(identity); p=Path(name); parts=set(x.lower() for x in p.parts)
        if p.suffix.lower() in BAD or parts & FORBIDDEN_DIRS or any(x.lower().endswith('.app') for x in p.parts): issues.append((name,'private artifact path'))
        if data[:4] in (b'NSO0',b'NRO0',b'NCA3',b'PFS0',b'HFS0',b'ZBIC'): issues.append((name,'game/container signature'))
        if len(data)>10*1024*1024: issues.append((name,'large file over 10 MiB'))
        if any(pattern.search(data) for pattern in SECRETS): issues.append((name,'credential pattern'))
        binary=b'\0' in data[:4096] or p.suffix.lower() in ('.dll','.exe','.png')
        if binary:
            icon=name=='assets/app-icon/dungeon1.png' and data.startswith(b'\x89PNG')
            locked=known.get(name)==identity[1]
            if not (icon or locked): issues.append((name,'unreviewed binary'))
    for record in git('ls-files','--stage','-z').split(b'\0'):
        if not record:continue
        meta,rawname=record.split(b'\t',1); mode,oid,stage=meta.decode().split();name=rawname.decode()
        if mode!='100644' and mode!='100755':issues.append((name,'link or non-regular mode'))
        if stage!='0':issues.append((name,'unmerged index'))
        data=git('cat-file','blob',oid);check(name,data);indexed.append(name)
    reachable=git('rev-list','--objects','--all').decode().splitlines()
    for line in reachable:
        fields=line.split(' ',1)
        if len(fields)==2:
            oid,name=fields
            if git('cat-file','-t',oid).strip()==b'blob':check(name,git('cat-file','blob',oid))
    profiles=[n for n in indexed if re.fullmatch(r'dm/games/[^/]+/game.tsv',n)]
    if profiles!=['dm/games/01008F1008DA6000/game.tsv']:issues.append(('dm/games','not exactly one expected profile'))
    for name in ['LICENSE','THIRD_PARTY_NOTICES.md','docs/UPSTREAM.md','docs/public-release-audit.md']:
        if name not in indexed:issues.append((name,'required attribution/audit missing'))
    for name,expected in known.items():
        if name in indexed and hashlib.sha256(git('show',':'+name)).hexdigest()!=expected:issues.append((name,'locked translator changed'))
    print(json.dumps({'index_files':len(indexed),'unique_path_blobs_checked':len(checked),
        'reachable_objects':len(reachable),'refs':git('for-each-ref','--format=%(refname)').decode().splitlines(),
        'issues':[{'path':p,'reason':why} for p,why in sorted(set(issues))]},indent=2))
    raise SystemExit(bool(issues))
if __name__=='__main__':main()
