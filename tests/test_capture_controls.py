"""Actual Soloist WebSocket and paired TLS: block playback until the route is verified."""
import base64
import copy
import hashlib
import json
from pathlib import Path
import socket
import struct
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock
from test_audio_source import write_config
from test_control_transport import exact,ws_send,ws_receive
from test_control_bridge import item
from security_support import pairing,tls_client
import audio_source
import soloist_bridge as bridge

class CaptureControlTests(unittest.TestCase):
    def test_cli_enforces_capture_policy_even_without_an_explicit_capture_root(self):
        with mock.patch.object(bridge,'run',return_value=None) as run:
            self.assertIsNone(bridge.main(['--listen','--data-dir','data']))
        self.assertIsInstance(run.call_args.kwargs['capture_root'],Path)
        self.assertEqual(run.call_args.kwargs['capture_root'].name,'VitaAudioReceiver')

    def test_route_guard_pauses_blocks_play_then_recovers_without_restarting_bridge(self):
        with pairing() as (registry,identity,path,key),tempfile.TemporaryDirectory() as td:
            root=Path(td);write_config(root,False);favorites=root/'favorites.json';favorites.write_text('[]')
            api=socket.socket();api.bind(('127.0.0.1',0));api.listen();self.addCleanup(api.close)
            (root/'ws.addr').write_text('127.0.0.1');(root/'ws.port').write_text(str(api.getsockname()[1]))
            stop=threading.Event();ready=threading.Event();addresses=[];commands=[];errors=[]
            current=item();current['decorations'].pop('visual_identity',None)
            state={'type':'playback_state','is_active':True,'status':'playing','item':current,'volume':60}
            def soloist():
                try:
                    api.settimeout(6);conn,_=api.accept()
                    with conn:
                        conn.settimeout(6);request=bytearray()
                        while not request.endswith(b'\r\n\r\n'):request.extend(exact(conn,1))
                        lines=request.decode().split('\r\n')
                        ws_key=next(s.split(':',1)[1].strip() for s in lines if s.lower().startswith('sec-websocket-key:'))
                        accept=base64.b64encode(hashlib.sha1((ws_key+'258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode()).digest())
                        conn.sendall(b'HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: '+accept+b'\r\n\r\n')
                        ws_send(conn,{'type':'auth_state','logged_in':True,'is_active':True});ws_send(conn,state)
                        while not stop.is_set():
                            event=ws_receive(conn);commands.append(event);name=event['command']
                            if name=='get_auth_state':ws_send(conn,{'type':'auth_state','logged_in':True,'is_active':True})
                            elif name=='get_state':ws_send(conn,state)
                            elif name=='get_queue':ws_send(conn,{'type':'queue_changed','upcoming':[]})
                            elif name in ('pause','play'):
                                state['status']='paused' if name=='pause' else 'playing';ws_send(conn,copy.deepcopy(state))
                            else:ws_send(conn,{'type':'command_result','command':name})
                except (OSError,EOFError):pass
                except BaseException as exc:errors.append(exc)
            def controls():
                try:bridge.run(None,root,favorites,0,True,'127.0.0.1',stop.is_set,registry,
                    lambda address:(addresses.append(address),ready.set()),capture_root=root)
                except BaseException as exc:errors.append(exc)
            server=threading.Thread(target=soloist,daemon=True);worker=threading.Thread(target=controls,daemon=True)
            server.start();worker.start()
            def state_frame(client,needle):
                deadline=time.monotonic()+5
                while time.monotonic()<deadline:
                    tag,n=struct.unpack('<4sI',exact(client,8));payload=exact(client,n)
                    if tag==b'STAT' and needle in payload:return payload
                self.fail('Capture guard state did not reach the Vita')
            try:
                self.assertTrue(ready.wait(2),errors)
                with tls_client(addresses[0],identity,key,'control') as client:
                    state_frame(client,b'routing is not verified')
                    # A direct track-selection command must not start playback.
                    raw=struct.pack('<Ii',8,0)+bridge.fixed('spotify:track:'+'A'*22,128)
                    client.sendall(bridge.packet(b'CMND',raw));state_frame(client,b'routing is not verified')
                    self.assertTrue(any(c['command']=='pause' for c in commands),commands)
                    self.assertFalse(any(c['command'] in ('activate','play') for c in commands),commands)
                    value=json.loads((root/'host.json').read_text());value['capture']['route_verified']=True
                    (root/'host.json').write_text(json.dumps(value));audio_source.source_status(0,value['capture'],root)
                    deadline=time.monotonic()+4
                    while time.monotonic()<deadline and not any(c['command']=='play' for c in commands):time.sleep(.02)
                    self.assertTrue(any(c['command']=='play' for c in commands),commands)
                    # A runtime device mismatch is propagated and pauses again.
                    audio_source.source_status(4,value['capture'],root,state='blocked')
                    state_frame(client,b'output mismatch')
                    deadline=time.monotonic()+2
                    while time.monotonic()<deadline and sum(c['command']=='pause' for c in commands)<2:time.sleep(.02)
                    self.assertEqual(sum(c['command']=='pause' for c in commands),2,commands)
            finally:stop.set();worker.join(4);server.join(2)
            self.assertFalse(worker.is_alive());self.assertFalse(errors,errors)

if __name__=='__main__':unittest.main()
