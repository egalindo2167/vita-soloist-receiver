#!/usr/bin/env python3
"""Build both Windows binaries from this checkout, then bind their hashes."""
import argparse
from pathlib import Path
import subprocess
import sys
from release_metadata import source_commit,stamp_native

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('build_dir',type=Path);parser.add_argument('--source-commit')
    args=parser.parse_args();source_commit(args.source_commit);root=Path(__file__).resolve().parents[1]
    for recipe,name in (('build_windows_capture.py','soloist-capture.exe'),('build_windows_opus.py','opus.dll')):
        subprocess.run([sys.executable,str(root/'tools'/recipe),str(args.build_dir),str(root/'pc/native'/name)],check=True)
    for name,digest in stamp_native(root,args.source_commit).items():print(digest,name)
