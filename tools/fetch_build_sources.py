#!/usr/bin/env python3
"""Download only these published, hash-pinned upstream build inputs."""
import argparse
import hashlib
from pathlib import Path
import tarfile
from urllib.request import urlopen

SOURCES={
 'opus':('https://downloads.xiph.org/releases/opus/opus-1.6.1.tar.gz',
         '6ffcb593207be92584df15b32466ed64bbec99109f007c82205f0194572411a1','opus-1.6.1'),
 'mbedtls':('https://github.com/Mbed-TLS/mbedtls/releases/download/mbedtls-3.6.7/mbedtls-3.6.7.tar.bz2',
            'a7e8bcbec0e6f761b4af24f25677626b35f762f68eef79c08677a363212d11f6','mbedtls-3.6.7'),
 'zig':('https://ziglang.org/download/0.15.2/zig-x86_64-linux-0.15.2.tar.xz',
        '02aa270f183da276e5b5920b1dac44a63f1a49e55050ebde3aecc9eb82f93239','zig-x86_64-linux-0.15.2')}

def fetch(name,destination):
    url,checksum,directory=SOURCES[name];destination=Path(destination);destination.mkdir(parents=True,exist_ok=True)
    archive=destination/url.rsplit('/',1)[1]
    if not archive.is_file():
        with urlopen(url,timeout=30) as source,archive.open('wb') as output:
            while chunk:=source.read(1048576):output.write(chunk)
    if hashlib.sha256(archive.read_bytes()).hexdigest()!=checksum:
        raise RuntimeError('Source checksum failed: '+name)
    result=destination/directory
    if not result.exists():
        with tarfile.open(archive) as source:source.extractall(destination,filter='data')
    return result.resolve()

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('source',choices=SOURCES)
    parser.add_argument('destination',type=Path);args=parser.parse_args();print(fetch(args.source,args.destination))
