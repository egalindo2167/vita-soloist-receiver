#!/usr/bin/env python3
"""Download only these published, hash-pinned upstream build inputs."""
import argparse
import hashlib
from http.client import IncompleteRead
import os
from pathlib import Path
import ssl
import sys
import tarfile
import tempfile
import time
from urllib.error import HTTPError,URLError
from urllib.request import Request,urlopen

DOWNLOAD_ATTEMPTS=4
RETRY_HTTP={408,429,500,502,503,504}

SOURCES={
 'opus':('https://downloads.xiph.org/releases/opus/opus-1.6.1.tar.gz',
         '6ffcb593207be92584df15b32466ed64bbec99109f007c82205f0194572411a1','opus-1.6.1'),
 'mbedtls':('https://github.com/Mbed-TLS/mbedtls/releases/download/mbedtls-3.6.7/mbedtls-3.6.7.tar.bz2',
            'a7e8bcbec0e6f761b4af24f25677626b35f762f68eef79c08677a363212d11f6','mbedtls-3.6.7'),
 'zig':('https://ziglang.org/download/0.15.2/zig-x86_64-linux-0.15.2.tar.xz',
        '02aa270f183da276e5b5920b1dac44a63f1a49e55050ebde3aecc9eb82f93239','zig-x86_64-linux-0.15.2')}

# Official GitHub release-asset API for the identical Mbed TLS archive. Its
# bytes were independently checked against the unchanged pinned SHA-256.
FALLBACKS={'mbedtls':('https://api.github.com/repos/Mbed-TLS/mbedtls/releases/assets/464469768',)}

def digest(path):
    value=hashlib.sha256()
    with path.open('rb') as source:
        while chunk:=source.read(1048576):value.update(chunk)
    return value.hexdigest()

def download(name,url,archive,checksum):
    urls=(url,)+FALLBACKS.get(name,())
    for attempt in range(1,DOWNLOAD_ATTEMPTS+1):
        temporary=None
        try:
            fd,filename=tempfile.mkstemp(prefix='.'+archive.name+'-',suffix='.part',dir=archive.parent)
            temporary=Path(filename)
            target=urls[min(attempt-1,len(urls)-1)]
            request=Request(target,headers={'Accept':'application/octet-stream','User-Agent':'VitaAudioReceiver-build'}) if target.startswith('https://api.github.com/') else target
            with os.fdopen(fd,'wb') as output:
                with urlopen(request,timeout=30) as source:
                    while chunk:=source.read(1048576):output.write(chunk)
            if digest(temporary)!=checksum:raise RuntimeError('Source checksum failed: '+name)
            os.replace(temporary,archive)
            return
        except HTTPError as exc:
            exc.close()
            if exc.code not in RETRY_HTTP or attempt==DOWNLOAD_ATTEMPTS:raise
            reason='HTTP '+str(exc.code)
        except (URLError,TimeoutError,ConnectionError,IncompleteRead) as exc:
            # Do not retry away certificate validation failures or bypass TLS.
            if isinstance(exc,URLError) and isinstance(exc.reason,ssl.SSLCertVerificationError):raise
            if attempt==DOWNLOAD_ATTEMPTS:raise
            reason=type(exc).__name__
        finally:
            if temporary is not None:temporary.unlink(missing_ok=True)
        delay=2**attempt
        print(f'{name}: download attempt {attempt}/{DOWNLOAD_ATTEMPTS} failed ({reason}); retrying in {delay}s.',file=sys.stderr,flush=True)
        time.sleep(delay)

def fetch(name,destination):
    url,checksum,directory=SOURCES[name];destination=Path(destination);destination.mkdir(parents=True,exist_ok=True)
    archive=destination/url.rsplit('/',1)[1]
    if archive.is_file() and digest(archive)!=checksum:
        print(f'{name}: discarding an invalid cached archive; fetching the pinned source again.',file=sys.stderr,flush=True)
        archive.unlink()
    if not archive.is_file():download(name,url,archive,checksum)
    result=destination/directory
    if not result.exists():
        # Interrupted extraction must not leave a directory mistaken for a
        # complete cached source tree on the next run.
        with tempfile.TemporaryDirectory(prefix='.'+directory+'-',dir=destination) as temporary:
            staging=Path(temporary)
            with tarfile.open(archive) as source:source.extractall(staging,filter='data')
            extracted=staging/directory
            if not extracted.is_dir():raise RuntimeError('Expected source directory missing: '+name)
            os.replace(extracted,result)
    return result.resolve()

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('source',choices=SOURCES)
    parser.add_argument('destination',type=Path);args=parser.parse_args();print(fetch(args.source,args.destination))
