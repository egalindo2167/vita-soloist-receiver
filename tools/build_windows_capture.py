#!/usr/bin/env python3
"""Cross-build the Windows x64 process-capture helper with the pinned Zig toolchain."""
import argparse
import hashlib
from pathlib import Path
import subprocess
from fetch_build_sources import fetch

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('build_dir',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args();build=args.build_dir.resolve();build.mkdir(parents=True,exist_ok=True)
    zig=fetch('zig',build/'sources')/'zig';root=Path(__file__).resolve().parents[1]
    binary=build/'soloist-capture.exe';args.output.parent.mkdir(parents=True,exist_ok=True)
    subprocess.run([str(zig),'cc','-target','x86_64-windows-gnu','-std=c11','-O2',
        '-Wall','-Wextra','-Werror','-municode',str(root/'pc/native_src/soloist_capture.c'),
        '-lole32','-lmmdevapi','-lavrt','-lpropsys','-luuid','-o',str(binary)],check=True)
    subprocess.run(['objcopy','--strip-debug',str(binary),str(args.output)],check=True)
    print(hashlib.sha256(args.output.read_bytes()).hexdigest(),args.output)

if __name__=='__main__':main()
