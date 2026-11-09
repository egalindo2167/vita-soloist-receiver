#!/usr/bin/env python3
"""Package validated sources/VPK, excluding caches, local state and secrets."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile
from source_policy import check_checkout,check_root_name,check_archive

SKIP_DIRS={'build','__pycache__','.pytest_cache','.git','.venv','venv','node_modules'}
SKIP_NAMES={'host.json','funnel.json','tunnel.json','paired-vitas.json','quality.bin','display.bin',
            'funnel-status.json','tunnel-status.json','vita-pairing.bin','remote-host.txt',
            'ngrok-vita.yml','ngrok-vita-check.yml'}

def package(root,output):
    root=Path(root).resolve();output=Path(output).resolve()
    check_checkout(root)
    # Reject unexpected root documents before replacing an existing archive.
    for path in root.iterdir():
        if path.is_file() and path!=output and (path.suffix.lower() in {'.py','.c','.h','.md','.txt','.cmd','.lock','.png','.svg','.xml','.yml','.yaml','.sh','.vpk','.dll','.json'} or path.name in {'LICENSE','.gitignore','.gitattributes'}):
            if path.name not in SKIP_NAMES:check_root_name(path.name)
    try:empty_favorites=json.loads((root/'pc/favorites.json').read_text(encoding='utf-8-sig'))==[]
    except (OSError,ValueError) as exc:raise ValueError('pc/favorites.json must be an empty release template.') from exc
    if not empty_favorites:raise ValueError('pc/favorites.json must be an empty release template; do not publish personal favorites.')
    output.parent.mkdir(parents=True,exist_ok=True)
    source=root/'build/vita-audio-receiver.vpk';vpk=root/'dist/vita-audio-receiver.vpk';vpk.parent.mkdir(exist_ok=True)
    if source.is_file():vpk.write_bytes(source.read_bytes())
    checksum=hashlib.sha256(vpk.read_bytes()).hexdigest()
    (root/'dist/SHA256SUMS.txt').write_text(checksum+'  vita-audio-receiver.vpk\n')
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for path in sorted(root.rglob('*')):
            if not path.is_file() or path.is_symlink() or path==output:continue
            relative=path.relative_to(root)
            if any(part in SKIP_DIRS for part in relative.parts) or path.name in SKIP_NAMES:continue
            capture_exe=relative.as_posix()=='pc/native/soloist-capture.exe'
            special=relative.as_posix() in {'LICENSE','.gitignore','.gitattributes'}
            if path.suffix.lower() not in {'.py','.c','.h','.md','.txt','.cmd','.lock','.png','.svg','.xml','.yml','.yaml','.sh','.vpk','.dll','.json'} and not capture_exe and not special:continue
            if path.suffix.lower()=='.json' and relative.as_posix()!='pc/favorites.json':continue
            if relative.parts[:2]==('pc','soloist') and relative.as_posix()!='pc/soloist/READ-ME.txt':continue
            if path.suffix.lower() in {'.pyc','.so','.a','.wav','.log','.zip'} or path.suffix.lower()=='.exe' and not capture_exe:continue
            if path.suffix.lower()=='.dll' and relative.as_posix()!='pc/native/opus.dll':continue
            archive.write(path,Path('vita-audio-receiver')/relative)
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None:raise RuntimeError('Archive integrity check failed')
        check_archive(archive)
    text=hashlib.sha256(output.read_bytes()).hexdigest()+'  '+output.name+'\n'+checksum+'  '+vpk.name+'\n'
    output.with_suffix(output.suffix+'.sha256').write_text(text);print(text,end='')

if __name__=='__main__':
    from release_metadata import version,write_info
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('output',type=Path,nargs='?')
    parser.add_argument('--release-dir',type=Path);parser.add_argument('--source-commit');parser.add_argument('--run-url')
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);args=parser.parse_args()
    if (args.output is None)==(args.release_dir is None):parser.error('Choose one output path or --release-dir')
    output=args.output if args.output is not None else args.release_dir/('vita-audio-receiver-'+version(args.root)+'.zip')
    info=write_info(args.root,args.source_commit,args.run_url);package(args.root,output)
    if args.release_dir is not None:
        (args.release_dir/'vita-audio-receiver.vpk').write_bytes((args.root/'dist/vita-audio-receiver.vpk').read_bytes())
        (args.release_dir/'SHA256SUMS.txt').write_text(output.with_suffix(output.suffix+'.sha256').read_text())
        (args.release_dir/'BUILD_INFO.txt').write_text(info)
