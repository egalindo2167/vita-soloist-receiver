#!/usr/bin/env python3
"""Cross-build upstream Opus on Linux using the pinned official Zig compiler.

Requires CMake, GNU ar/ranlib/objcopy. Output is Windows x64, UCRT, shared Opus.
Existing caches must be trusted or cleared before using this for a new release.
"""
import argparse
import hashlib
from pathlib import Path
import shutil
import subprocess
from fetch_build_sources import fetch

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('build_dir',type=Path)
    parser.add_argument('output',type=Path);args=parser.parse_args();build=args.build_dir.resolve();build.mkdir(parents=True,exist_ok=True)
    source=fetch('opus',build/'sources');zig=fetch('zig',build/'sources')/'zig'
    compiler=build/'zigcc';compiler.write_text('#!/bin/sh\nexec "'+str(zig)+'" cc -target x86_64-windows-gnu "$@"\n');compiler.chmod(0o755)
    binary=build/'opus'
    subprocess.run(['cmake','-S',str(source),'-B',str(binary),'-DCMAKE_SYSTEM_NAME=Windows',
      '-DCMAKE_C_COMPILER='+str(compiler),'-DCMAKE_AR='+shutil.which('ar'),'-DCMAKE_RANLIB='+shutil.which('ranlib'),
      '-DCMAKE_BUILD_TYPE=Release','-DOPUS_BUILD_SHARED_LIBRARY=ON','-DOPUS_BUILD_PROGRAMS=OFF',
      '-DOPUS_BUILD_TESTING=OFF','-DOPUS_DRED=OFF','-DOPUS_OSCE=OFF',
      '-DOPUS_INSTALL_PKG_CONFIG_MODULE=OFF','-DOPUS_INSTALL_CMAKE_CONFIG_MODULE=OFF'],check=True)
    subprocess.run(['cmake','--build',str(binary),'-j2'],check=True)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    subprocess.run(['objcopy','--strip-debug',str(binary/'libopus.dll'),str(args.output)],check=True)
    print(hashlib.sha256(args.output.read_bytes()).hexdigest(),args.output)

if __name__=='__main__':main()
