"""Source/release layout rules shared by CI, packaging and checkout cleanup."""
import argparse
from pathlib import Path, PurePosixPath
import subprocess

MOVED_DOCUMENTS={
    'BUILDING.md':'docs/dev/BUILDING.md',
    'BUILD_VALIDATION.md':'docs/dev/BUILD_VALIDATION.md',
    'NETWORK_TUNING.md':'docs/NETWORK_TUNING.md',
    'PUBLISHING.md':'docs/dev/PUBLISHING.md',
    'REVIEW_1.1.md':'docs/dev/REVIEW_1.1.md',
    'SECURITY_REVIEW_0.13.md':'docs/dev/SECURITY_REVIEW_0.13.md',
    'SOLOIST_SETUP.md':'docs/SOLOIST_SETUP.md',
    'SUPPLY_CHAIN.md':'docs/dev/SUPPLY_CHAIN.md',
    'TUNNEL_SETUP.md':'docs/advanced/NGROK_SETUP.md',
    'USER_GUIDE.md':'docs/REFERENCE.md',
}
GENERATED_NATIVE={'pc/native/soloist-capture.exe','pc/native/opus.dll',
                  'pc/native/SHA256SUMS.txt','pc/native_hashes.py'}
ALLOWED_ROOT_FILES={
    '.gitattributes','.gitignore','CMakeLists.txt','LICENSE','BUILD_INFO.txt',
    'README.md','RELEASE_NOTES.md','CHANGELOG.md','CONTRIBUTING.md','SUPPORT.md',
    'AUDIO_SETUP.md','HOST_SETUP.md','UI_GUIDE.md','QUALITY.md','SEARCH.md',
    'FAVORITES.md','FUNNEL_SETUP.md','SECURITY.md','THIRD_PARTY_NOTICES.md',
    'MBEDTLS-LICENSE.txt','OPUS-LICENSE.txt','PSPSDK-LICENSE.txt',
    'UI-FONT-LICENSE.txt','VitaSpotify-MIT-LICENSE.txt',
}

def check_checkout(root,tracked=False):
    root=Path(root).resolve()
    stale=[name for name in MOVED_DOCUMENTS if (root/name).exists()]
    if stale:raise ValueError('Obsolete root documents: '+', '.join(sorted(stale))+'. Run python tools/clean_source_checkout.py --apply, then commit the deletions.')
    if tracked:
        names=set(subprocess.check_output(['git','-C',str(root),'ls-files','-z']).decode().split('\0'))
        generated=names&GENERATED_NATIVE
        if generated:raise ValueError('Generated native outputs must not be tracked: '+', '.join(sorted(generated))+'. Run python tools/clean_source_checkout.py --apply, then commit.')

def check_root_name(name):
    if name not in ALLOWED_ROOT_FILES:raise ValueError('Unapproved release root file: '+name)

def check_archive(archive):
    for name in archive.namelist():
        parts=PurePosixPath(name).parts
        if not parts or parts[0]!='vita-audio-receiver' or '..' in parts:raise ValueError('Invalid release archive path')
        if len(parts)==2 and not name.endswith('/'):check_root_name(parts[1])

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--tracked',action='store_true');args=parser.parse_args()
    check_checkout(args.root,args.tracked);print('Source layout policy passed.')
