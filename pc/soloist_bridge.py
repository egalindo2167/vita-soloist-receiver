#!/usr/bin/env python3
"""Soloist controls/metadata/artwork side channel. Does not capture or send audio."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import io
import json
from pathlib import Path
import select
import signal
import ssl
from secure_host import SecureListener, RateGate
import socket
import struct
import sys
import time
from urllib.parse import urlparse
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler
from version import VERSION
import zlib
from favorites import load_favorites, spotify_uri, DEFAULT_PATH
from windows_host import host_stop_requested
from queue_navigation import QueueCache,QueueJump,QueueSearch
from playback_transition import PlaybackTransition

EDGE=224
ITEM_LIMIT=32
STATE_SIZE=908
COMMAND_SIZE=136
MAX_SOLOIST_EVENT=16*1024*1024

def fixed(value,size):
    raw=str(value or '').encode('utf-8')[:size-1].decode('utf-8','ignore').encode('utf-8')
    return raw+b'\0'*(size-len(raw))

def packet(tag,payload): return struct.pack('<4sI',tag,len(payload))+payload

class Frames:
    def __init__(self,on_diagnostic=None): self.data=bytearray();self.on_diagnostic=on_diagnostic
    def feed(self,chunk):
        self.data.extend(chunk); result=[]
        while len(self.data)>=8:
            tag,size=struct.unpack_from('<4sI',self.data)
            if not ((tag==b'CMND' and size==COMMAND_SIZE) or (tag==b'RSTA' and size in (16,24,28))):
                raise ValueError('Invalid Vita control frame')
            if len(self.data)<8+size: break
            payload=bytes(self.data[8:8+size]); del self.data[:8+size]
            if tag==b'RSTA':
                if self.on_diagnostic:self.on_diagnostic(struct.unpack('<'+str(size//4)+'I',payload))
                continue
            op,value=struct.unpack_from('<Ii',payload)
            uri=payload[8:].split(b'\0',1)[0].decode('utf-8','strict')
            if not 1<=op<=15: raise ValueError('Unknown Vita command')
            result.append((op,value,uri))
        if len(self.data)>COMMAND_SIZE+8: raise ValueError('Control frame is too large')
        return result

class VitaOutbox:
    """Bounded metadata plus one cover, sent without blocking the event loop.

    Cover chunks are rate-limited to about 80 KiB/s and yield to metadata.
    This prevents a cover from monopolizing Wi-Fi or delaying volume controls.
    """
    def __init__(self):
        self.latest={};self.art=None;self.pending=b'';self.offset=0;self.next_art=0;self.art_interval=.025;self.features=0
    def queue(self,tag,payload):
        self.latest[tag]=payload
    def artwork(self,art_id,pixels):self.art=[art_id,pixels,0]
    def flush(self,sock,now=None):
        now=time.monotonic() if now is None else now
        if not self.pending:
            for tag in (b'AFLU',b'STAT',b'QJMP',b'QPAG',b'QUEU',b'FAVS'):
                if tag in self.latest:
                    self.pending=packet(tag,self.latest.pop(tag));break
            if not self.pending and self.art is not None and now>=self.next_art:
                art_id,pixels,offset=self.art
                chunk=pixels[offset:offset+2048]
                self.pending=packet(b'ARTC',struct.pack('<II',art_id,offset)+chunk)
                self.art[2]+=len(chunk);self.next_art=now+self.art_interval
                if self.art[2]==len(pixels):self.art=None
            self.offset=0
        if self.pending:
            try:n=sock.send(self.pending[self.offset:self.offset+4096])
            except (BlockingIOError,ssl.SSLWantReadError,ssl.SSLWantWriteError):return
            if not n:raise OSError('Vita stopped receiving controls')
            self.offset+=n
            if self.offset==len(self.pending):self.pending=b'';self.offset=0

def entity(item):
    item=item if isinstance(item,dict) else {}
    d=item.get('decorations') or {}
    parent=(d.get('parent') or {}).get('entity') or {}
    creators=d.get('creators') or []
    names=[((c.get('entity') or {}).get('decorations') or {}).get('identity',{}).get('name','')
           for c in creators if isinstance(c,dict)]
    cover=(d.get('visual_identity') or {}).get('cover') or \
          ((parent.get('decorations') or {}).get('visual_identity') or {}).get('cover') or []
    choices=[c for c in cover if isinstance(c,dict) and isinstance(c.get('url'),str)]
    choices.sort(key=lambda c:{'default':0,'large':1,'small':2,'xlarge':3}.get(c.get('size'),4))
    return {'title':(d.get('identity') or {}).get('name') or '',
            'artist':', '.join(n for n in names if n),
            'album':((parent.get('decorations') or {}).get('identity') or {}).get('name') or '',
            'uri':item.get('uri') or '', 'cover':choices[0]['url'] if choices else '',
            'duration':int((d.get('playback') or {}).get('duration_ms') or 0)}

class Player:
    def __init__(self):
        self.api=False; self.logged=False; self.active=False; self.status='idle'
        self.volume=50; self.shuffle=False; self.repeat='off'
        self.item=entity({}); self.position={}; self.queue=[]; self.context='';self.queue_cache=QueueCache()
        self.message='Connecting to Soloist...'
    @property
    def art_id(self):
        if not self.item['uri']: return 0
        return zlib.crc32((self.item['uri']+'|'+self.item['cover']).encode())
    def update(self,event):
        kind=event.get('type'); self.api=True
        if kind=='auth_state':
            self.logged=bool(event.get('logged_in')); self.active=bool(event.get('is_active'))
            self.message='' if self.logged else 'Select PS Vita (PC bridge) in Spotify to pair.'
            if not self.logged:
                self.item=entity({}); self.queue=[]; self.status='idle'; self.position={}
                self.context='';self.queue_cache.reset()
        elif kind=='playback_state':
            self.set_context(event.get('context'))
            self.item=entity(event.get('item')); self.status=event.get('status','idle')
            self.position=event.get('position') or {}; self.volume=clamp(event.get('volume',self.volume),0,100)
            self.active=bool(event.get('is_active',self.active)); self.options(event.get('options') or {})
        elif kind=='track_changed':
            self.item=entity(event.get('item')); self.position={}
        elif kind=='playback_changed': self.status=event.get('status','idle')
        elif kind=='position_sync': self.position=event.get('position') or {}
        elif kind=='volume_changed': self.volume=clamp(event.get('volume',self.volume),0,100)
        elif kind=='device_changed': self.active=bool(event.get('is_active'))
        elif kind=='options_changed': self.options(event.get('options') or {})
        elif kind=='context_changed':self.set_context(event.get('context'))
        elif kind=='queue_changed':
            self.queue_cache.update(event.get('upcoming') or [],entity);self.queue=self.queue_cache.items
        elif kind=='error': self.message=str(event.get('message') or 'Soloist rejected the command')[:159]
        elif kind=='command_result': self.message=''
    def set_context(self,context):
        if context is None:return
        uri=context.get('uri','') if isinstance(context,dict) else ''
        if not isinstance(uri,str):uri=''
        if uri!=self.context:
            self.context=uri;self.queue_cache.reset(uri);self.queue=[]
    def options(self,options):
        self.shuffle=bool(options.get('shuffle',self.shuffle))
        value=options.get('repeat',self.repeat)
        if value in ('off','context','track'): self.repeat=value
    def position_ms(self,now=None):
        p=self.position; value=float(p.get('position_ms') or 0)
        stamp=p.get('timestamp_ms'); speed=float(p.get('speed') or 0)
        if self.status=='playing' and stamp:
            value+=max(0,(time.time() if now is None else now)*1000-float(stamp))*speed
        return clamp(value,0,self.item['duration'] or 0x7fffffff)
    def state_payload(self):
        fields=(1,int(self.api),int(self.logged),int(self.active),
                {'idle':0,'playing':1,'paused':2,'buffering':3}.get(self.status,0),
                self.volume,int(self.shuffle),('off','context','track').index(self.repeat),
                self.position_ms(),clamp(self.item['duration'],0,0x7fffffff),self.art_id)
        raw=struct.pack('<11I',*fields)+b''.join(fixed(self.item[k],192) for k in ('title','artist','album'))
        raw+=fixed(self.item['uri'],128)+fixed(self.message,160)
        assert len(raw)==STATE_SIZE
        return raw
    def commands(self,op,value,uri):
        if op==11:
            return [{'type':'command','command':'get_queue','limit':0}] if self.logged else []
        if not self.logged: raise ValueError('Pair the bridge by selecting it in Spotify first.')
        def command(name,**kw): return {'type':'command','command':name,**kw}
        if op==1:
            if not self.active: return [command('activate'),command('play')]
            return [command('pause' if self.status=='playing' else 'play')]
        if op in (2,3): return [command('skip_prev' if op==2 else 'skip_next')]
        if op in (4,5):
            self.volume=clamp(self.volume+value if op==4 else value,0,100)
            return [command('set_volume',volume=self.volume)]
        if op==6:
            self.shuffle=not self.shuffle
            return [command('set_shuffle',enabled=self.shuffle)]
        if op==7:
            self.repeat=('context' if self.repeat=='off' else 'track' if self.repeat=='context' else 'off')
            # Clear the other repeat flag first, as required by Soloist's API.
            if self.repeat=='track':
                return [command('set_repeat_context',enabled=False),command('set_repeat_track',enabled=True)]
            return [command('set_repeat_track',enabled=False),
                    command('set_repeat_context',enabled=self.repeat=='context')]
        if op==8:
            uri=spotify_uri(uri)
            return ([command('activate')] if not self.active else [])+[command('play',uri=uri)]
        if op in (9,10):
            target=self.position_ms()+value if op==9 else value
            return [command('seek',position_ms=clamp(target,0,self.item['duration'] or 0x7fffffff))]
        raise ValueError('Unknown control command')

def clamp(value,low,high): return max(low,min(high,int(value)))

def list_payload(items,queue_tokens=False):
    items=items[:ITEM_LIMIT]
    return struct.pack('<I',len(items))+b''.join(fixed(item.get(k,''),128)
                                               for item in items for k in ('title','artist','selection' if queue_tokens else 'uri'))

def queue_page_payload(search,cache):
    rows,total=search.results(cache)
    flags=int(cache.truncated)|(2 if cache.awaiting and not cache.items else 0)
    header=struct.pack('<7I',search.request_id,cache.revision&0xffffffff,search.offset,total,len(cache.items),flags,len(rows))
    return header+fixed(search.query,128)+b''.join(struct.pack('<I',position)+
        b''.join(fixed(item.get(k,''),128) for k in ('title','artist','selection')) for position,item in rows)

class NoArtRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise ValueError('Artwork redirects are not allowed')

def download_art(url):
    from PIL import Image, ImageOps
    parsed=urlparse(url)
    host=(parsed.hostname or '').lower()
    if (parsed.scheme!='https' or parsed.username is not None or parsed.password is not None or
        parsed.port not in (None,443) or not (host.endswith('.scdn.co') or host.endswith('.spotifycdn.com'))):
        raise ValueError('Unrecognized Spotify artwork URL')
    request=Request(url,headers={'User-Agent':'VitaAudioReceiver/'+VERSION})
    opener=build_opener(ProxyHandler({}),NoArtRedirect())
    with opener.open(request,timeout=5) as response:
        data=response.read(4*1024*1024+1)
    if len(data)>4*1024*1024: raise ValueError('Artwork download exceeds 4 MB')
    with Image.open(io.BytesIO(data)) as image:
        if image.width*image.height>16000000: raise ValueError('Artwork dimensions are too large')
        resized=ImageOps.contain(image.convert('RGB'),(EDGE,EDGE),Image.Resampling.LANCZOS)
        square=Image.new('RGB',(EDGE,EDGE),(20,27,36))
        square.paste(resized,((EDGE-resized.width)//2,(EDGE-resized.height)//2))
        raw=square.tobytes()
    result=bytearray(EDGE*EDGE*2)
    for i in range(EDGE*EDGE):
        r,g,b=raw[3*i:3*i+3]; packed=((r>>3)<<11)|((g>>2)<<5)|(b>>3)
        struct.pack_into('<H',result,2*i,packed)
    return bytes(result)

def endpoint(directory):
    address=(directory/'ws.addr').read_text().strip(); port=int((directory/'ws.port').read_text().strip())
    if address not in ('127.0.0.1','localhost') or not 1<=port<=65535:
        raise ValueError('Soloist WebSocket must be bound to 127.0.0.1')
    return f'ws://127.0.0.1:{port}'

def run(vita_ip,directory,favorites_path,port=48153,listen=True,bind='0.0.0.0',stop=host_stop_requested,security=None,on_listen=None,capture_root=None):
    import websocket
    if not listen or vita_ip:raise ValueError('Legacy unencrypted connections were retired. Use Setup/Upgrade Host and pair your Vita.')
    server=SecureListener(bind,port,'control',security);server.setblocking(False)
    if on_listen:on_listen(server.getsockname())
    print(f'Paired TLS controls listening on TCP {server.getsockname()[1]}.',flush=True)
    command_gate=RateGate(rate=20,burst=20,global_rate=20,global_burst=20)
    player=Player(); ws=vita=None; decoder=Frames()
    outbox=VitaOutbox();resume_pending=False;standby_at=time.monotonic()+3 if listen else None
    jump=QueueJump();transition=PlaybackTransition();search=QueueSearch()
    last_diagnostic=[0,0]
    def diagnostic(values):
        nonlocal previous_queue,previous_page
        underruns,buffer_ms,seconds,playing,*quality=values
        if quality:outbox.art_interval=.25 if quality[1] else .025
        if len(quality)>=3 and outbox.features!=(quality[2]&7):
            outbox.features=quality[2]&7;previous_queue=previous_page=None
            if outbox.features&4:outbox.latest.pop(b'QUEU',None)
            if transition.valid and outbox.features&1:outbox.queue(b'AFLU',transition.marker())
        if seconds<last_diagnostic[1]:last_diagnostic[0]=0
        if underruns>last_diagnostic[0]:
            print(f'Vita playback rebuffer count: {underruns}; buffered {buffer_ms} ms; session {seconds}s.',flush=True)
        last_diagnostic[:]=[underruns,seconds]
    retry_ws=retry_vita=next_state=next_query=next_favorites=0.0
    previous_queue=previous_favorites=previous_page=previous_jump=None; favorites=[]; favorite_stamp=None
    reported_queue=None
    last_art=0; requested_art=None; future=None; art_cache=None
    pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='spotify-artwork')
    last_notice=0.0
    def send_command(command):
        if command['command']=='get_queue':player.queue_cache.request()
        ws.send(json.dumps(command,separators=(',',':')))
    def lose_api():
        nonlocal ws
        if ws is not None:ws.close()
        ws=None;player.api=player.logged=False;player.queue_cache.reset(player.context);player.queue=[]
        player.message='Reconnecting to Soloist...'
    def advance_queue(now):
        commands=jump.advance(player,now)
        for command in commands:send_command(command)
        if not jump.active:
            if commands and commands[-1]['command']=='play' and player.status!='playing':
                transition.kind='status';transition.target='playing';transition.started=now
            else:transition.finish(now)
        elif now-transition.started>=8:
            # Keep the bounded receiver hold alive during a long, cancellable
            # sequence. No repeated audio samples or key changes are involved.
            transition.begin(player,'queue',now=now)
    from audio_source import capture_block_reason
    block_code=0;block_message='';last_block=0;next_capture_check=0;paused_for_block=0
    try:
        while not stop():
            now=time.monotonic()
            player.queue_cache.tick(now);player.queue=player.queue_cache.items
            if player.queue_cache.needs_query and next_query>now+.05:next_query=now+.05
            if capture_root is not None and now>=next_capture_check:
                next_capture_check=now+.25
                block_code,block_message=capture_block_reason(capture_root)
                if not block_code and last_block:resume_pending=listen and vita is not None
            if ws is None and now>=retry_ws:
                retry_ws=now+2
                try:
                    ws=websocket.create_connection(endpoint(directory),timeout=0.3,
                          enable_multithread=True,http_no_proxy=['127.0.0.1','localhost'])
                    print('Controls: connected to the local Soloist API.',flush=True)
                    paused_for_block=0
                    send_command({'type':'command','command':'get_auth_state'})
                except (OSError,ValueError,websocket.WebSocketException):
                    if ws: ws.close()
                    ws=None
            if vita is None and (listen or now>=retry_vita):
                retry_vita=now+1
                try:
                    vita,_=server.accept()
                    command_gate=RateGate(rate=20,burst=20,global_rate=20,global_burst=20)
                    vita.setblocking(False)
                    vita.setsockopt(socket.IPPROTO_TCP,socket.TCP_NODELAY,1)
                    decoder=Frames(diagnostic);outbox=VitaOutbox()
                    previous_queue=previous_favorites=previous_page=previous_jump=None;last_art=0;next_state=0
                    search=QueueSearch()
                    resume_pending=listen;standby_at=None;last_diagnostic[:]=[0,0]
                    print('Controls: Vita display connected.',flush=True)
                except OSError: vita=None
            if now>=next_favorites:
                next_favorites=now+2
                try:
                    stamp=favorites_path.stat().st_mtime_ns if favorites_path.exists() else None
                    if stamp!=favorite_stamp:
                        favorites=load_favorites(favorites_path); favorite_stamp=stamp
                except (OSError,ValueError) as exc:
                    player.message=f'Favorites: {exc}'[:159]
            readable=[]
            if ws is not None and (ws.sock is None or not ws.connected):
                lose_api()
            sockets=([ws.sock] if ws is not None else [])+([vita] if vita is not None else [])
            if listen and vita is None:sockets.append(server)
            if sockets: readable,_,_=select.select(sockets,[],[],0.01)
            else: time.sleep(0.05)
            if ws is not None and ws.sock in readable:
                try:
                    raw=ws.recv()
                    if not raw: raise OSError('Soloist disconnected')
                    if len(raw)>MAX_SOLOIST_EVENT: raise ValueError('Soloist event exceeds 16 MB')
                    event=json.loads(raw)
                    if isinstance(event,dict):
                        old_uri=player.item['uri'];old_position=player.position_ms();old_duration=player.item['duration']
                        was_pending=transition.hold
                        player.update(event)
                        if event.get('type')=='queue_changed' and len(event.get('upcoming') or [])!=10:
                            observed=(player.context,len(player.queue_cache.items),player.queue_cache.source_count)
                            if observed!=reported_queue:
                                reported_queue=observed
                                print(f'Soloist queue: {observed[1]} searchable upcoming entries; {observed[2]} returned. Requested all available (limit 0); not a playlist total.',flush=True)
                        transition.observe(player,event,now)
                        if event.get('type')=='error' and jump.active:
                            jump.cancel();transition.finish(now)
                        if jump.active:
                            try:
                                advance_queue(now)
                            except ValueError as exc:
                                transition.finish(now);player.message=str(exc)[:159]
                        if not was_pending and now-transition.last_reset>.5:
                            # Preserve the tail of natural/gapless transitions. Only
                            # explicit actions or observed early jumps discard audio.
                            natural=old_duration>0 and old_position>=old_duration-3000
                            track_jump=event.get('type') in ('track_changed','playback_state') and old_uri and player.item['uri'] and old_uri!=player.item['uri']
                            seek_jump=event.get('type') in ('position_sync','playback_state') and old_uri==player.item['uri'] and abs(player.position_ms()-old_position)>2500
                            if not natural and (track_jump or seek_jump):transition.reset(now)
                        if event.get('type') in ('auth_state','track_changed','command_result'):
                            next_query=0
                except websocket.WebSocketTimeoutException:
                    pass
                except (OSError,ValueError,websocket.WebSocketException):
                    lose_api(); retry_ws=now+1
            if vita is not None and (vita in readable or vita.pending() or not vita.authorized()):
                try:
                    chunk=vita.recv(4096)
                    if not chunk: raise OSError('Vita disconnected')
                    for op,value,uri in decoder.feed(chunk):
                        if not command_gate.allow('paired'):raise ValueError('Control command rate exceeded')
                        vita._check()
                        try:
                            if ws is None and op not in (13,14,15): raise ValueError('Soloist API is reconnecting.')
                            if transition.hold and op not in (4,5,11,13,14,15):
                                if op==1 and player.status=='playing':jump.cancel()
                                else:raise ValueError('Playback change in progress. Please wait, or pause to cancel.')
                            if op in (13,14):
                                if not outbox.features&4:raise ValueError('Queue search requires the current Vita receiver.')
                                if op==13:search.search(value,uri)
                                else:
                                    if not uri.isascii() or not uri.isdecimal() or len(uri)>10:raise ValueError('Invalid queue request identity')
                                    search.page(int(uri),value)
                                previous_page=None
                                commands=[]
                            elif op==15:
                                jump.cancel();transition.finish(now);commands=[]
                                player.message='Queue jump cancelled. A dispatched skip may still finish.'
                            elif op==12:
                                if block_code:raise ValueError(block_message)
                                if jump.active:jump.cancel();transition.finish(now)
                                commands=jump.start(uri,player,now);transition.begin(player,'queue',now=now)
                                outbox.latest.pop(b'QUEU',None)
                            else:
                                commands=player.commands(op,value,uri)
                            if block_code and any(c['command'] in ('activate','play','skip_prev','skip_next','seek') for c in commands):
                                raise ValueError(block_message)
                            if op not in (12,13,14,15):
                                changing=next((c for c in commands if c['command'] in ('play','pause','skip_prev','skip_next','seek')),None)
                                if changing:
                                    jump.cancel()
                                    name=changing['command']
                                    kind='seek' if name=='seek' else 'status' if name in ('pause','play') and 'uri' not in changing else 'change'
                                    target=changing.get('position_ms') if kind=='seek' else 'paused' if name=='pause' else 'playing'
                                    transition.begin(player,kind,target,now)
                            for command in commands:send_command(command)
                            if op not in (13,14):next_query=0
                            next_state=0
                        except ValueError as exc: player.message=str(exc)[:159]; next_state=0
                except (ssl.SSLWantReadError,ssl.SSLWantWriteError):pass
                except (OSError,ValueError,websocket.WebSocketException):
                    vita.close();vita=None;standby_at=now+3 if listen else None
                    jump.cancel();transition.finish(now)
            if ws is not None and player.logged:
                try:
                    if block_code and block_code!=paused_for_block:
                        if player.active:send_command({'type':'command','command':'pause'})
                        paused_for_block=block_code
                        next_state=0
                    elif not block_code:paused_for_block=0
                    if resume_pending and vita is not None and not block_code:
                        if not player.active:send_command({'type':'command','command':'activate'})
                        if player.status!='playing':send_command({'type':'command','command':'play'})
                        resume_pending=False;next_query=0
                    if standby_at is not None and now>=standby_at and vita is None:
                        if player.active:
                            send_command({'type':'command','command':'pause'})
                            send_command({'type':'command','command':'deactivate'})
                        standby_at=None
                except (OSError,websocket.WebSocketException):
                    lose_api()
            if ws is not None and player.logged and now>=next_query:
                try:
                    send_command({'type':'command','command':'get_state'})
                    send_command({'type':'command','command':'get_queue','limit':0})
                    next_query=now+3
                except (OSError,websocket.WebSocketException):
                    lose_api()
            if jump.active:
                try:
                    if ws is None:jump.cancel();transition.finish(now)
                    else:
                        advance_queue(now)
                        if jump.active:player.message=jump.message
                except ValueError as exc:transition.finish(now);player.message=str(exc)[:159]
            notice=transition.tick(now)
            if notice:jump.cancel();player.message=notice
            if transition.changed:
                if outbox.features&1:outbox.queue(b'AFLU',transition.marker())
                transition.changed=False
            if block_code:player.message=block_message[:159]
            elif last_block:player.message=''
            last_block=block_code
            if future is not None and future.done():
                art_id=requested_art
                try: art_cache=(art_id,future.result())
                except Exception as exc:
                    print(f'Artwork unavailable: {type(exc).__name__}',file=sys.stderr)
                future=None
            if not jump.active and future is None and player.item['cover'] and player.art_id!=requested_art:
                requested_art=player.art_id; future=pool.submit(download_art,player.item['cover'])
            if vita is not None:
                try:
                    if now>=next_state:
                        outbox.queue(b'STAT',player.state_payload()); next_state=now+0.5
                    f=list_payload(favorites)
                    if outbox.features&4:
                        progress=struct.pack('<II',jump.done if jump.active else 0,jump.total if jump.active else 0)
                        if progress!=previous_jump:outbox.queue(b'QJMP',progress);previous_jump=progress
                        if not jump.active:
                            page=queue_page_payload(search,player.queue_cache)
                            if page!=previous_page:outbox.queue(b'QPAG',page);previous_page=page
                    else:
                        q=list_payload(player.queue,bool(outbox.features&2))
                        if not jump.active and q!=previous_queue:outbox.queue(b'QUEU',q);previous_queue=q
                    if f!=previous_favorites:outbox.queue(b'FAVS',f);previous_favorites=f
                    if not jump.active and art_cache and art_cache[0]==player.art_id and last_art!=player.art_id:
                        # A state frame must establish this artwork ID before its pixels arrive.
                        outbox.queue(b'STAT',player.state_payload())
                        outbox.artwork(art_cache[0],art_cache[1]);last_art=art_cache[0]
                    outbox.flush(vita,now)
                except OSError:
                    vita.close();vita=None;standby_at=now+3 if listen else None
                    jump.cancel();transition.finish(now)
            if (ws is None or vita is None) and now-last_notice>=15:
                print('Controls: waiting for '+('Soloist API' if ws is None else 'a Vita connection')+'. Audio runs separately.',flush=True)
                last_notice=now
    finally:
        if vita is not None: vita.close()
        if ws is not None: ws.close()
        if server is not None:server.close()
        pool.shutdown(wait=False,cancel_futures=True)

def main(argv=None):
    from secure_host import root_path
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('vita_ip',nargs='?'); parser.add_argument('--data-dir',type=Path,required=True)
    parser.add_argument('--listen',action='store_true');parser.add_argument('--bind',default='0.0.0.0')
    parser.add_argument('--favorites',type=Path,default=DEFAULT_PATH)
    parser.add_argument('--port',type=int)
    parser.add_argument('--capture-root',type=Path,default=root_path(),help='Managed Soloist-only capture policy directory')
    args=parser.parse_args(argv)
    if not args.listen or args.vita_ip:parser.error('Use --listen with a paired Vita; unencrypted client mode was retired.')
    port=args.port or 48153
    try: run(args.vita_ip,args.data_dir,args.favorites,port,args.listen,args.bind,capture_root=args.capture_root)
    except KeyboardInterrupt: return 0
    except (OSError,ValueError,RuntimeError,ImportError) as exc:
        print(f'Controls bridge error: {exc}',file=sys.stderr); return 1

if __name__=='__main__':
    if sys.platform=='win32': signal.signal(signal.SIGBREAK,signal.default_int_handler)
    raise SystemExit(main())
