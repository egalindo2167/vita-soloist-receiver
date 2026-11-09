"""Canonical versions, provenance and native-payload metadata for CI releases."""
import argparse
import ast
import hashlib
from pathlib import Path
import re
import struct
import zipfile

def constants(path):
    values={}
    for node in ast.parse(Path(path).read_text()).body:
        if isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name):
            values[node.targets[0].id]=ast.literal_eval(node.value)
    return values

def version(root):
    value=constants(Path(root)/'pc/version.py')['VERSION']
    if not isinstance(value,str) or not re.fullmatch(r'\d+\.\d+(?:\.\d+)?',value):raise ValueError('Invalid release version')
    header=Path(root)/'src/version.h'
    if header.exists() and '#define RECEIVER_VERSION "'+value+'"' not in header.read_text():raise ValueError('Host and Vita versions disagree')
    return value

def verify_vpk(root):
    root=Path(root);path=root/'build/vita-audio-receiver.vpk'
    if not path.is_file():path=root/'dist/vita-audio-receiver.vpk'
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:raise ValueError('Invalid VPK integrity')
        s=archive.read('sce_sys/param.sfo')
    if len(s)<20:raise ValueError('Invalid VPK identity')
    magic,_,keys,data,count=struct.unpack_from('<5I',s)
    if magic!=0x46535000 or count>64 or not 20+16*count<=keys<=data<=len(s):raise ValueError('Invalid VPK identity')
    fields={}
    for i in range(count):
        ko,kind,size,capacity,vo=struct.unpack_from('<HHIII',s,20+16*i)
        if keys+ko>=data or size>capacity or data+vo+capacity>len(s):raise ValueError('Invalid VPK metadata bounds')
        key=s[keys+ko:data].split(b'\0',1)[0]
        if key in (b'APP_VER',b'TITLE_ID'):
            if kind!=0x0204 or key in fields:raise ValueError('Invalid VPK identity field')
            fields[key]=s[data+vo:data+vo+size].rstrip(b'\0').decode('ascii')
    cmake=(root/'CMakeLists.txt').read_text()
    expected=re.search(r'vita_create_vpk\([^\n]* VERSION (\d{2}\.\d{2})',cmake)
    if expected is None or fields.get(b'APP_VER')!=expected.group(1) or fields.get(b'TITLE_ID')!='VRXA00001':raise ValueError('VPK does not match this release source')

def check_ref(root,ref):
    if ref.startswith('refs/tags/') and ref!='refs/tags/v'+version(root):
        raise ValueError('Release tag must be v'+version(root)+' to match the application version')

def source_commit(value):
    if value is not None and not re.fullmatch('[a-f0-9]{40}',value):raise ValueError('Invalid source commit')
    return value

def stamp_native(root,commit=None):
    root=Path(root);source_commit(commit);digests={}
    for name in ('soloist-capture.exe','opus.dll'):
        raw=(root/'pc/native'/name).read_bytes()
        if len(raw)<64 or raw[:2]!=b'MZ':raise ValueError('Not a Windows payload: '+name)
        offset=struct.unpack_from('<I',raw,60)[0]
        if raw[offset:offset+4]!=b'PE\0\0' or raw[offset+4:offset+6]!=b'\x64\x86':raise ValueError('Not a Windows x64 PE: '+name)
        digests[name]=hashlib.sha256(raw).hexdigest()
    (root/'pc/native_hashes.py').write_text('"""Generated expected hashes for these source-built native payloads."""\nSOURCE_COMMIT='+repr(commit)+'\nHELPER_SHA256='+repr(digests['soloist-capture.exe'])+'\nOPUS_DLL_SHA256='+repr(digests['opus.dll'])+'\n')
    (root/'pc/native/SHA256SUMS.txt').write_text(''.join(digest+'  '+name+'\n' for name,digest in digests.items()))
    return digests

def verify_native(root,commit=None):
    root=Path(root);expected=constants(root/'pc/native_hashes.py')
    if commit is not None and expected.get('SOURCE_COMMIT')!=source_commit(commit):raise ValueError('Native payloads were not built for this source commit')
    manifest={}
    for name,key in (('soloist-capture.exe','HELPER_SHA256'),('opus.dll','OPUS_DLL_SHA256')):
        if hashlib.sha256((root/'pc/native'/name).read_bytes()).hexdigest()!=expected.get(key):raise ValueError('Native payload hash mismatch: '+name)
        manifest[name]=expected[key]
    rows=(root/'pc/native/SHA256SUMS.txt').read_text().splitlines()
    if rows!=[digest+'  '+name for name,digest in manifest.items()]:raise ValueError('Native checksum manifest mismatch')

def write_info(root,commit=None,run_url=None):
    root=Path(root);source_commit(commit)
    if run_url is not None and not re.fullmatch(r'https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/actions/runs/\d+',run_url):raise ValueError('Invalid public CI run URL')
    verify_native(root,commit);verify_vpk(root)
    text='version='+version(root)+'\nsource_commit='+(commit or 'local-preparation')+'\nbuild_run='+(run_url or 'not-built-by-GitHub-Actions')+'\n'
    (root/'BUILD_INFO.txt').write_text(text)
    return text

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--check-ref');parser.add_argument('--stamp-native',action='store_true');parser.add_argument('--source-commit')
    args=parser.parse_args()
    if args.check_ref:check_ref(args.root,args.check_ref)
    if args.stamp_native:stamp_native(args.root,args.source_commit)
    print(version(args.root))
