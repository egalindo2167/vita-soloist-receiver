"""Real loopback WebSocket/TCP test using a fake Soloist and fake Vita endpoint."""
import base64
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from test_control_bridge import ROOT, TRACK, item
import soloist_bridge as bridge
from security_support import pairing,tls_client
from tunnel_support import TcpForward

def exact(sock,n):
    result=bytearray()
    while len(result)<n:
        chunk=sock.recv(n-len(result))
        if not chunk: raise EOFError
        result.extend(chunk)
    return bytes(result)

def ws_send(sock,event):
    data=json.dumps(event).encode()
    header=bytes([0x81,len(data)]) if len(data)<126 else b'\x81\x7e'+struct.pack('!H',len(data)) if len(data)<65536 else b'\x81\x7f'+struct.pack('!Q',len(data))
    sock.sendall(header+data)

def ws_receive(sock):
    a,b=exact(sock,2); n=b&127
    if n==126: n=struct.unpack('!H',exact(sock,2))[0]
    elif n==127: n=struct.unpack('!Q',exact(sock,8))[0]
    if n>1024*1024: raise ValueError('oversize test frame')
    mask=exact(sock,4) if b&128 else None
    data=exact(sock,n)
    if mask: data=bytes(v^mask[i%4] for i,v in enumerate(data))
    if a&15==8:
        sock.sendall(b'\x88\x00'); raise EOFError
    return json.loads(data)

@unittest.skipUnless(importlib.util.find_spec('websocket'),'Install requirements-soloist.txt for transport test')
class TransportTests(unittest.TestCase):
    def test_real_soloist_events_and_commands_over_paired_tls_with_reconnect(self):
        with pairing() as credentials:self.exercise(credentials)

    def test_spotify_commands_metadata_and_reconnect_through_raw_tcp_tunnel(self):
        with pairing() as credentials:self.exercise(credentials,True)

    def test_legacy_client_mode_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'Legacy unencrypted'):
            bridge.run('127.0.0.1',Path('.'),Path('missing'),listen=False)

    def exercise(self,credentials,remote=False):
        registry,identity,path,key=credentials
        reverse=True
        api=socket.socket(); api.bind(('127.0.0.1',0)); api.listen()
        vita=socket.socket(); vita.bind(('127.0.0.1',0)); vita.listen()
        api_port=api.getsockname()[1];vita_port=vita.getsockname()[1]
        if reverse:vita.close()
        relay=TcpForward(('127.0.0.1',vita_port)) if remote else None
        if relay:self.addCleanup(relay.close)
        public_port=relay.address[1] if relay else vita_port
        done=threading.Event(); received=threading.Event(); errors=[]; commands=[]; seen=[]
        current=item(); current['decorations'].pop('visual_identity')
        state={'type':'playback_state','status':'playing','item':current,'is_active':True,
               'volume':65,'options':{'shuffle':False,'repeat':'off'},'position':{'position_ms':45000,'speed':0}}
        def soloist_server():
            try:
                api.settimeout(6); conn,_=api.accept()
                with conn:
                    conn.settimeout(6); request=bytearray()
                    while not request.endswith(b'\r\n\r\n'): request.extend(exact(conn,1))
                    lines=request.decode().split('\r\n')
                    key=next(l.split(':',1)[1].strip() for l in lines if l.lower().startswith('sec-websocket-key:'))
                    accept=base64.b64encode(hashlib.sha1((key+'258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode()).digest())
                    conn.sendall(b'HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: '+accept+b'\r\n\r\n')
                    ws_send(conn,{'type':'auth_state','logged_in':True,'is_active':True})
                    ws_send(conn,state)
                    while not done.is_set():
                        event=ws_receive(conn); commands.append(event)
                        name=event['command']
                        if name=='get_auth_state': ws_send(conn,{'type':'auth_state','logged_in':True,'is_active':True})
                        elif name=='get_state': ws_send(conn,state)
                        elif name=='get_queue': ws_send(conn,{'type':'queue_changed','upcoming':[{'item':current}]})
                        else:
                            if name=='set_volume':
                                state['volume']=event['volume']; ws_send(conn,{'type':'volume_changed','volume':state['volume']})
                            ws_send(conn,{'type':'command_result','command':name})
            except (EOFError,OSError): pass
            except Exception as exc: errors.append(exc)
            finally: api.close()
        def vita_server():
            try:
                sessions=[(65,60),(60,55)] if reverse else [(65,60)]
                for initial,target in sessions:
                    if reverse:
                        deadline=time.monotonic()+6
                        while True:
                            try:conn=tls_client(('localhost',public_port),identity,key,'control');break
                            except OSError:
                                if time.monotonic()>=deadline:raise
                                time.sleep(0.03)
                    else:vita.settimeout(6);conn,_=vita.accept()
                    with conn:self.vita_session(conn,initial,target,done,seen)
                received.set()
            except (EOFError,OSError): pass
            except Exception as exc: errors.append(exc)
            finally: vita.close()
        t1=threading.Thread(target=soloist_server,daemon=True); t2=threading.Thread(target=vita_server,daemon=True)
        t1.start(); t2.start()
        with tempfile.TemporaryDirectory() as td:
            directory=Path(td); (directory/'ws.addr').write_text('127.0.0.1')
            (directory/'ws.port').write_text(str(api_port))
            f=directory/'favorites.json'; f.write_text('[]')
            bridge_errors=[]
            def run_bridge():
                try:bridge.run(None,directory,f,vita_port,True,'127.0.0.1',done.is_set,registry)
                except BaseException as exc:bridge_errors.append(exc)
            worker=threading.Thread(target=run_bridge,daemon=True);worker.start()
            try:success=received.wait(10)
            finally:done.set();worker.join(4)
            self.assertTrue(success,(errors,bridge_errors))
            self.assertFalse(worker.is_alive());self.assertFalse(bridge_errors,bridge_errors)
        t1.join(2); t2.join(2)
        self.assertFalse(errors,errors)
        self.assertIn({'type':'command','command':'set_volume','volume':60},commands)
        if reverse:
            self.assertIn({'type':'command','command':'set_volume','volume':55},commands)
            self.assertFalse(any(c['command'] in ('pause','deactivate') for c in commands))
        self.assertIn(b'STAT',seen); self.assertIn(b'QUEU',seen); self.assertIn(b'FAVS',seen)

    def vita_session(self,conn,initial,target,done,seen):
                    conn.settimeout(6); sent=False; queue_seen=False;favorites_seen=False
                    while not done.is_set():
                        tag,n=struct.unpack('<4sI',exact(conn,8)); payload=exact(conn,n); seen.append(tag)
                        if tag==b'QUEU' and struct.unpack_from('<I',payload)[0]: queue_seen=True
                        if tag==b'FAVS':favorites_seen=True
                        if tag==b'STAT':
                            fields=struct.unpack_from('<11I',payload)
                            if fields[5]==initial and payload[44:236].split(b'\0')[0]:
                                if not sent:
                                    raw=struct.pack('<Ii',4,-5)+bridge.fixed('',128)
                                    # Fragment a real command across writes, like TCP can do.
                                    message=bridge.packet(b'CMND',raw)
                                    conn.sendall(message[:5]); conn.sendall(message[5:]); sent=True
                            if fields[5]==target and queue_seen and favorites_seen:return

if __name__=='__main__': unittest.main()
