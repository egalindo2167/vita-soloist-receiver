#!/usr/bin/env python3
"""Attach this run's verified assets to a draft; never publish or replace a public release."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from release_metadata import source_commit,version

def prepare(root,assets,tag,commit,run=subprocess.run):
    root=Path(root);assets=Path(assets);source_commit(commit)
    if tag!='v'+version(root):raise ValueError('Tag/version mismatch')
    names=['vita-audio-receiver-'+version(root)+'.zip','vita-audio-receiver.vpk','SHA256SUMS.txt','BUILD_INFO.txt']
    for name in names:
        if not (assets/name).is_file():raise ValueError('Missing release asset: '+name)
    info=(assets/'BUILD_INFO.txt').read_text()
    if 'source_commit='+commit+'\n' not in info or 'version='+version(root)+'\n' not in info:raise ValueError('Release asset source/version mismatch')
    rows=(assets/'SHA256SUMS.txt').read_text().splitlines();expected={}
    for row in rows:
        digest,name=row.split('  ',1)
        if not re.fullmatch('[a-f0-9]{64}',digest) or name not in names[:2] or name in expected:raise ValueError('Invalid release checksum manifest')
        expected[name]=digest
    if set(expected)!=set(names[:2]):raise ValueError('Incomplete release checksum manifest')
    for name,digest in expected.items():
        if hashlib.sha256((assets/name).read_bytes()).hexdigest()!=digest:raise ValueError('Release asset checksum mismatch: '+name)
    repository=os.environ.get('GH_REPO','')
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repository):raise ValueError('GH_REPO must identify this repository')
    remote=run(['gh','api','repos/'+repository+'/commits/'+tag,'--jq','.sha'],capture_output=True,text=True,check=True)
    if remote.stdout.strip()!=commit:raise ValueError('The remote tag no longer matches the tested source commit')
    existing=run(['gh','release','view',tag,'--json','isDraft'],capture_output=True,text=True)
    if existing.returncode==0:
        if json.loads(existing.stdout).get('isDraft') is not True:raise ValueError('Refusing to modify an already published release')
    else:
        run(['gh','release','create',tag,'--verify-tag','--draft','--target',commit,'--title','Vita Audio Receiver '+version(root),
             '--notes-file',str(root/'RELEASE_NOTES.md')],check=True)
    run(['gh','release','upload',tag,*[str(assets/name) for name in names],'--clobber'],check=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('assets',type=Path);parser.add_argument('--tag',required=True);parser.add_argument('--commit',required=True)
    args=parser.parse_args();prepare(Path(__file__).resolve().parents[1],args.assets,args.tag,args.commit)
