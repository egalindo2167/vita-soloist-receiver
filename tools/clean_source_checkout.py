#!/usr/bin/env python3
"""Record moved-document deletions and stop tracking generated native outputs."""
import argparse
from pathlib import Path
import subprocess
from source_policy import MOVED_DOCUMENTS,GENERATED_NATIVE,check_checkout

def clean(root,apply=False):
    root=Path(root).resolve()
    top=Path(subprocess.check_output(['git','-C',str(root),'rev-parse','--show-toplevel'],text=True).strip()).resolve()
    if top!=root:raise ValueError('Run this in the project repository, not a parent checkout.')
    tracked=set(subprocess.check_output(['git','-C',str(root),'ls-files','-z']).decode().split('\0'))
    obsolete=[name for name in MOVED_DOCUMENTS if name in tracked or (root/name).exists()]
    for name in obsolete:
        replacement=root/MOVED_DOCUMENTS[name]
        if not replacement.is_file() or replacement.is_symlink():raise ValueError('Missing replacement for '+name+'; copy the complete new package first.')
        if (root/name).is_symlink():raise ValueError('Refusing symlink: '+name)
    generated=sorted(tracked&GENERATED_NATIVE)
    for name in obsolete:print('Remove obsolete document:',name,'->',MOVED_DOCUMENTS[name])
    for name in generated:print('Untrack generated output (keep local file):',name)
    if apply:
        for name in obsolete:
            if name in tracked:subprocess.run(['git','-C',str(root),'rm','--',name],check=True)
            else:(root/name).unlink()
        if generated:subprocess.run(['git','-C',str(root),'rm','--cached','--',*generated],check=True)
        check_checkout(root,tracked=True)
    elif obsolete or generated:print('Preview only. Add --apply to make these changes.')
    return obsolete,generated

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--apply',action='store_true')
    args=parser.parse_args();clean(Path(__file__).resolve().parents[1],args.apply)
