"""Manage Vita song/album/playlist shortcuts. No Spotify account credentials."""
import argparse
import json
from pathlib import Path
import re
import os
import tempfile
import sys
from urllib.parse import urlparse

DEFAULT_PATH=(Path(os.environ.get('LOCALAPPDATA',Path.home()/'AppData'/'Local'))/'VitaAudioReceiver'/'favorites.json'
              if sys.platform=='win32' else Path(__file__).resolve().parent/'favorites.json')
URI=re.compile(r'^spotify:(track|album|playlist|episode):[A-Za-z0-9]{22}$')

def spotify_uri(value):
    if not isinstance(value,str): raise ValueError('Expected a Spotify link or URI')
    value=value.strip()
    if URI.fullmatch(value): return value
    url=urlparse(value)
    if url.scheme=='https' and url.hostname=='open.spotify.com':
        parts=[p for p in url.path.split('/') if p]
        if parts and parts[0].startswith('intl-'): parts=parts[1:]
        if len(parts)==2:
            candidate='spotify:'+':'.join(parts)
            if URI.fullmatch(candidate): return candidate
    raise ValueError('Use a Spotify track, album, playlist or episode URL/URI')

def load_favorites(path=DEFAULT_PATH):
    path=Path(path)
    if not path.exists(): return []
    if path.stat().st_size>65536: raise ValueError('Favorites file is too large')
    data=json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data,list) or len(data)>32: raise ValueError('Favorites must be a list of at most 32 shortcuts')
    result=[]
    for entry in data:
        if not isinstance(entry,dict): raise ValueError('Each favorite needs name and uri fields')
        uri=spotify_uri(entry.get('uri',''))
        result.append({'title':str(entry.get('name') or uri)[:120],
                       'artist':uri.split(':')[1].capitalize(), 'uri':uri})
    return result

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='action',required=True)
    add=sub.add_parser('add'); add.add_argument('link'); add.add_argument('--name',required=True)
    sub.add_parser('list')
    remove=sub.add_parser('remove'); remove.add_argument('number',type=int)
    args=parser.parse_args(argv)
    try:
        entries=load_favorites()
        if args.action=='list':
            for n,item in enumerate(entries,1): print(f"{n}. {item['title']}  {item['uri']}")
            if not entries: print('No shortcuts yet. Use: py favorites.py add "SPOTIFY_URL" --name "My playlist"')
            return 0
        if args.action=='add':
            uri=spotify_uri(args.link)
            if not args.name.strip(): raise ValueError('Give the shortcut a name')
            if len(entries)>=32: raise ValueError('There are already 32 shortcuts; remove one first')
            entries.append({'title':args.name.strip(),'uri':uri})
        else:
            if not 1<=args.number<=len(entries): raise ValueError('Shortcut number is out of range')
            entries.pop(args.number-1)
        output=[{'name':e['title'],'uri':e['uri']} for e in entries]
        with tempfile.NamedTemporaryFile('w',encoding='utf-8',dir=DEFAULT_PATH.parent,delete=False) as f:
            json.dump(output,f,ensure_ascii=False,indent=2); f.write('\n'); temporary=f.name
        os.replace(temporary,DEFAULT_PATH)
        print('Saved favorites.json. The running bridge reloads it automatically.')
        return 0
    except (OSError,ValueError) as exc:
        print(f'Favorites error: {exc}'); return 1

if __name__=='__main__': raise SystemExit(main())
