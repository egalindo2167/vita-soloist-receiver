"""Real Soloist WebSocket + paired TLS: selecting farther ahead preserves context."""
import base64
import copy
import hashlib
from pathlib import Path
import select
import socket
import struct
import sys
import tempfile
import threading
import time
import unittest
from test_control_transport import exact,ws_send,ws_receive
from test_network_playback import entries,track
from security_support import pairing,tls_client
import soloist_bridge as bridge
import audio_host
import send_audio

class QueueTransportTests(unittest.TestCase):
    def test_sixth_upcoming_track_advances_existing_queue_and_flushes_only_audio(self):
        with pairing() as (registry,identity,path,key),tempfile.TemporaryDirectory() as td:
            root=Path(td);(root/'favorites.json').write_text('[]')
            api=socket.socket();api.bind(('127.0.0.1',0));api.listen();self.addCleanup(api.close)
            (root/'ws.addr').write_text('127.0.0.1');(root/'ws.port').write_text(str(api.getsockname()[1]))
            upcoming=entries(1,45);commands=[];errors=[];addresses=[];ready=threading.Event();stop=threading.Event()
            sound=[0x1111];source_runs=[];audio_ready=threading.Event();audio_addresses=[]
            def source():
                source_runs.append(1)
                while not stop.is_set():
                    yield struct.pack('<h',sound[0])*2048
                    time.sleep(1024/48000)
            def audio_run():
                try:audio_host.serve('127.0.0.1',0,factory=source,codec='pcm',stop=stop.is_set,security=registry,
                    on_listen=lambda address:(audio_addresses.append(address),audio_ready.set()))
                except BaseException as exc:errors.append(exc)
            state={'type':'playback_state','is_active':True,'status':'playing','item':{'uri':track(0)},
                   'context':{'uri':'spotify:playlist:'+'P'*22},'position':{'position_ms':20000},'volume':60}
            def server():
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
                            elif name=='get_state':ws_send(conn,copy.deepcopy(state))
                            elif name=='get_queue':
                                # Broadcast races the explicit full reply on the same socket.
                                ws_send(conn,{'type':'queue_changed','upcoming':upcoming[:10]})
                                ws_send(conn,{'type':'queue_changed','upcoming':upcoming if not event.get('limit') else upcoming[:event['limit']]})
                            elif name=='skip_next':
                                ws_send(conn,{'type':'command_result','command':name})
                                time.sleep(.04) # Accepted first, actual playback changes later.
                                entry=upcoming.pop(0);state['item']=entry['item'];state['position']={'position_ms':0}
                                sound[0]=0x2222 if state['item']['uri']==track(6) else 0x3333
                                ws_send(conn,copy.deepcopy(state))
                                ws_send(conn,{'type':'queue_changed','upcoming':upcoming[:10]})
                            else:ws_send(conn,{'type':'command_result','command':name})
                except (EOFError,OSError):pass
                except BaseException as exc:errors.append(exc)
            def run():
                try:bridge.run(None,root,root/'favorites.json',0,True,'127.0.0.1',stop.is_set,registry,
                    lambda a:(addresses.append(a),ready.set()))
                except BaseException as exc:errors.append(exc)
            a=threading.Thread(target=server,daemon=True);b=threading.Thread(target=run,daemon=True);a.start();b.start()
            audio_worker=threading.Thread(target=audio_run,daemon=True);audio_worker.start();audio_client=None
            counts=[];markers=[];selected=False;final_queue=False
            try:
                self.assertTrue(ready.wait(2),errors)
                self.assertTrue(audio_ready.wait(2),errors)
                audio_client=tls_client(audio_addresses[0],identity,key)
                self.assertEqual(exact(audio_client,16),send_audio.HEADER);audio_client.sendall(struct.pack('<4sI',b'VPOK',48000))
                self.assertEqual(exact(audio_client,4096),struct.pack('<h',0x1111)*2048)
                with tls_client(addresses[0],identity,key,'control') as client:
                    client.settimeout(6)
                    client.sendall(struct.pack('<4sI7I',b'RSTA',28,0,1000,10,1,320,1,3))
                    deadline=time.monotonic()+8
                    while time.monotonic()<deadline:
                        tag,n=struct.unpack('<4sI',exact(client,8));payload=exact(client,n)
                        if tag==b'AFLU':
                            markers.append(struct.unpack('<II',payload))
                            if markers[-1][1] and audio_client is not None:audio_client.close();audio_client=None
                        if tag==b'QUEU':
                            count=struct.unpack_from('<I',payload)[0];counts.append(count)
                            if count>=6:
                                token=payload[4+5*384+256:4+6*384].split(b'\0')[0].decode()
                                if not selected and token.startswith('q:'):
                                    raw=struct.pack('<Ii',12,0)+bridge.fixed(token,128)
                                    # A second playback action must not race the
                                    # confirmed multi-step selection or overshoot it.
                                    extra=struct.pack('<Ii',3,0)+bridge.fixed('',128)
                                    client.sendall(bridge.packet(b'CMND',raw)+bridge.packet(b'CMND',extra));selected=True
                            if selected and count and payload[4+256:4+384].split(b'\0')[0].decode().startswith('q:'):
                                # Metadata names make it clear the head is now song 7.
                                final_queue=payload[4:132].split(b'\0')[0]==b'Song 7'
                        if final_queue and markers and markers[-1][1]==0:
                            audio_client=tls_client(audio_addresses[0],identity,key)
                            self.assertEqual(exact(audio_client,16),send_audio.HEADER);audio_client.sendall(struct.pack('<4sI',b'VPOK',48000))
                            self.assertEqual(exact(audio_client,4096),struct.pack('<h',0x2222)*2048)
                            audio_client.close();audio_client=None;break
                    self.assertTrue(selected);self.assertTrue(final_queue,(counts,commands,errors))
                    self.assertTrue(any(phase==1 for _,phase in markers),markers)
                    self.assertEqual(markers[-1][1],0,markers)
                    self.assertNotIn(10,counts,counts)
                    self.assertEqual(sum(c['command']=='skip_next' for c in commands),6,commands)
                    self.assertFalse(any(c['command']=='play' for c in commands),commands)
                    self.assertEqual(state['item']['uri'],track(6));self.assertEqual(upcoming[0]['item']['uri'],track(7))
                    self.assertEqual(state['context']['uri'],'spotify:playlist:'+'P'*22)
                    self.assertEqual(len(source_runs),2)
            finally:
                if audio_client is not None:audio_client.close()
                stop.set();b.join(4);a.join(2);audio_worker.join(4)
            self.assertFalse(b.is_alive());self.assertFalse(errors,errors)
            self.assertFalse(audio_worker.is_alive())

if __name__=='__main__':unittest.main()
