"""Queue availability, PC filtering/paging, protocol and actual encrypted search."""
import base64
import copy
import contextlib
import hashlib
import json
from pathlib import Path
import socket
import struct
import tempfile
import threading
import time
import unittest
from test_network_playback import entries,player,track
from test_control_transport import exact,ws_send,ws_receive
from security_support import pairing,tls_client
from queue_navigation import LIMIT,QueueSearch,QueueJump
import soloist_bridge as bridge
import queue_probe

def page_decode(payload):
    request,revision,offset,total,available,flags,count=struct.unpack_from('<7I',payload)
    rows=[]
    for i in range(count):
        at=156+i*388;position=struct.unpack_from('<I',payload,at)[0]
        rows.append((position,payload[at+4:at+132].split(b'\0')[0].decode(),payload[at+260:at+388].split(b'\0')[0].decode()))
    return request,offset,total,available,rows

class SearchTests(unittest.TestCase):
    def test_all_available_command_and_eighty_entries_are_not_clamped_to_thirty_two(self):
        p=player(entries(1,80));self.assertEqual(len(p.queue),80)
        self.assertEqual(p.commands(11,0,''),[{'type':'command','command':'get_queue','limit':0}])
        s=QueueSearch();s.search(1,'Song 79');page=page_decode(bridge.queue_page_payload(s,p.queue_cache))
        self.assertEqual(page[:4],(1,0,1,80));self.assertEqual(page[4][0][0],79)
        p.update({'type':'queue_changed','upcoming':entries(1,10)})
        self.assertEqual(len(p.queue),80)
    def test_case_accents_multiple_artists_and_words_in_any_order(self):
        data=entries(1,3);data[1]['item']['decorations']={'identity':{'name':'Canción Étoile'},
            'creators':[{'entity':{'decorations':{'identity':{'name':'Mira Wells'}}}},
                        {'entity':{'decorations':{'identity':{'name':'Other Artist'}}}}]}
        p=player(data);s=QueueSearch();s.search(1,'WELLS cancion etoile');rows,total=s.results(p.queue_cache)
        self.assertEqual(total,1);self.assertEqual(rows[0][0],2)
        s.search(2,'other eto');self.assertEqual(s.results(p.queue_cache)[1],1)
    def test_five_thousand_entries_searches_last_song_and_sends_only_five_rows(self):
        p=player(entries(1,5000));s=QueueSearch();s.search(1,'Song');self.assertTrue(s.page(1,4995))
        payload=bridge.queue_page_payload(s,p.queue_cache);page=page_decode(payload)
        self.assertEqual(page[:4],(1,4995,5000,5000));self.assertEqual([r[0] for r in page[4]],list(range(4996,5001)))
        self.assertEqual(len(payload),156+5*388)
        s.search(2,'Song 5000');self.assertEqual(s.results(p.queue_cache)[0][0][0],5000)
        with self.assertRaisesRegex(ValueError,'256'):QueueJump().start(p.queue[-1]['selection'],p,1)
    def test_stale_page_identity_bad_offsets_and_invalid_text_do_not_change_query(self):
        p=player(entries(1,80));s=QueueSearch();s.search(2,'Song')
        self.assertFalse(s.page(1,20));self.assertEqual(s.offset,0)
        for offset in (-1,3,10000):
            with self.assertRaises(ValueError):s.page(2,offset)
        for query in ('x'*128,'a\nb','x\x00y'):
            with self.assertRaises(ValueError):s.search(3,query)
        self.assertEqual(s.query,'Song')
        for request in (0,-1,0x80000000):
            with self.assertRaises(ValueError):s.search(request,'')
    def test_cache_replacement_context_change_and_shorter_last_page(self):
        p=player(entries(1,80));s=QueueSearch();s.search(1,'Song');s.page(1,75)
        p.update({'type':'queue_changed','upcoming':entries(1,7)})
        rows,total=s.results(p.queue_cache);self.assertEqual((s.offset,total,len(rows)),(5,7,2))
        p.set_context({'uri':'spotify:playlist:'+'Z'*22});self.assertEqual(s.results(p.queue_cache),([],0))
    def test_safety_cap_is_explicit_and_does_not_break_legacy_receiver_format(self):
        p=player(entries(1,LIMIT+1));self.assertEqual(len(p.queue),LIMIT);self.assertTrue(p.queue_cache.truncated)
        p.update({'type':'queue_changed','upcoming':entries(1,10)})
        self.assertTrue(p.queue_cache.truncated)
        raw=bridge.queue_page_payload(QueueSearch(),p.queue_cache);self.assertEqual(struct.unpack_from('<I',raw,20)[0]&1,1)
        self.assertEqual(len(bridge.list_payload(p.queue,True)),4+32*384)
    def test_query_frames_are_fragment_safe_and_keep_playback_commands_separate(self):
        raw=b''.join(bridge.packet(b'CMND',struct.pack('<Ii',op,value)+bridge.fixed(text,128))
                     for op,value,text in [(13,7,'canción'),(14,35,'7'),(15,0,'')])
        decoder=bridge.Frames();found=[]
        for at in range(0,len(raw),3):found.extend(decoder.feed(raw[at:at+3]))
        self.assertEqual(found,[(13,7,'canción'),(14,35,'7'),(15,0,'')])
    def test_distant_jump_deadline_scales_but_still_has_a_hard_bound(self):
        p=player(entries(1,80));jump=QueueJump();jump.start(p.queue[78]['selection'],p,1)
        self.assertGreater(jump.deadline,100);self.assertLessEqual(jump.deadline,121)
        # All 79 confirmations can take longer than the old 20-second total.
        for n in range(1,80):
            p.update({'type':'track_changed','item':{'uri':track(n)}})
            p.update({'type':'queue_changed','upcoming':entries(n+1,80-n)})
            jump.advance(p,1+n*.5)
        self.assertFalse(jump.active);self.assertEqual(jump.done,79)
    def test_probe_sends_only_read_only_all_available_request(self):
        import websocket
        class Fake:
            def __init__(self):self.sent=[];self.events=[json.dumps({'type':'queue_changed','upcoming':[{}]*10}),json.dumps({'type':'queue_changed','upcoming':[{}]*80})]
            def send(self,text):self.sent.append(json.loads(text))
            def recv(self):
                if self.events:return self.events.pop(0)
                time.sleep(.01);raise websocket.WebSocketTimeoutException()
        ws=Fake();self.assertEqual(queue_probe.measure(ws,.03),80)
        self.assertEqual(ws.sent,[{'type':'command','command':'get_queue','limit':0}])

@contextlib.contextmanager
def live_queue(count,delay=0):
    with pairing() as (registry,identity,path,key),tempfile.TemporaryDirectory() as td:
        root=Path(td);(root/'favorites.json').write_text('[]')
        api=socket.socket();api.bind(('127.0.0.1',0));api.listen()
        (root/'ws.addr').write_text('127.0.0.1');(root/'ws.port').write_text(str(api.getsockname()[1]))
        upcoming=entries(1,count);commands=[];errors=[];stop=threading.Event();ready=threading.Event();addresses=[]
        state={'type':'playback_state','is_active':True,'status':'playing','item':{'uri':track(0)},
               'context':{'uri':'spotify:playlist:'+'P'*22},'position':{'position_ms':20000},'volume':60}
        def server():
            try:
                api.settimeout(5);conn,_=api.accept()
                with conn:
                    conn.settimeout(5);request=bytearray()
                    while not request.endswith(b'\r\n\r\n'):request.extend(exact(conn,1))
                    wskey=next(s.split(':',1)[1].strip() for s in request.decode().split('\r\n') if s.lower().startswith('sec-websocket-key:'))
                    accept=base64.b64encode(hashlib.sha1((wskey+'258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode()).digest())
                    conn.sendall(b'HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: '+accept+b'\r\n\r\n')
                    ws_send(conn,{'type':'auth_state','logged_in':True,'is_active':True});ws_send(conn,state)
                    while not stop.is_set():
                        event=ws_receive(conn);commands.append(event);name=event['command']
                        if name=='get_auth_state':ws_send(conn,{'type':'auth_state','logged_in':True,'is_active':True})
                        elif name=='get_state':ws_send(conn,copy.deepcopy(state))
                        elif name=='get_queue':
                            ws_send(conn,{'type':'queue_changed','upcoming':upcoming[:10]})
                            ws_send(conn,{'type':'queue_changed','upcoming':upcoming if not event.get('limit') else upcoming[:event['limit']]})
                        elif name=='skip_next':
                            ws_send(conn,{'type':'command_result','command':name});time.sleep(delay)
                            if upcoming:state['item']=upcoming.pop(0)['item'];state['position']={'position_ms':0}
                            ws_send(conn,copy.deepcopy(state));ws_send(conn,{'type':'queue_changed','upcoming':upcoming[:10]})
                        else:ws_send(conn,{'type':'command_result','command':name})
            except (EOFError,OSError):pass
            except BaseException as exc:errors.append(exc)
        def run():
            try:bridge.run(None,root,root/'favorites.json',0,True,'127.0.0.1',stop.is_set,registry,lambda a:(addresses.append(a),ready.set()))
            except BaseException as exc:errors.append(exc)
        workers=[threading.Thread(target=server,daemon=True),threading.Thread(target=run,daemon=True)]
        for w in workers:w.start()
        client=None
        try:
            if not ready.wait(3):raise AssertionError(errors)
            client=tls_client(addresses[0],identity,key,'control');client.settimeout(4)
            client.sendall(struct.pack('<4sI7I',b'RSTA',28,0,1000,10,1,320,1,7))
            yield client,commands,state,upcoming
        finally:
            if client is not None:client.close()
            stop.set();api.close()
            for w in reversed(workers):w.join(5)
            if errors:raise AssertionError(errors)
            if any(w.is_alive() for w in workers):raise AssertionError('Queue fixture worker did not stop')

def command(client,op,value=0,text=''):
    client.sendall(bridge.packet(b'CMND',struct.pack('<Ii',op,value)+bridge.fixed(text,128)))
def receive(client,predicate,seconds=6):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        tag,n=struct.unpack('<4sI',exact(client,8));payload=exact(client,n)
        if predicate(tag,payload):return payload
    raise AssertionError('Expected control response did not arrive')

class EncryptedSearchTests(unittest.TestCase):
    def test_five_thousand_api_entries_search_paging_stale_requests_and_no_playback_side_effects(self):
        with live_queue(5000) as (client,commands,state,upcoming):
            receive(client,lambda tag,p:tag==b'QPAG' and page_decode(p)[3]==5000)
            command(client,13,1,'Song 5000')
            raw=receive(client,lambda tag,p:tag==b'QPAG' and page_decode(p)[0]==1)
            self.assertEqual(page_decode(raw)[:4],(1,0,1,5000));self.assertEqual(page_decode(raw)[4][0][0],5000)
            command(client,13,2,'Song');command(client,14,4995,'2');command(client,14,0,'1')
            raw=receive(client,lambda tag,p:tag==b'QPAG' and page_decode(p)[:2]==(2,4995))
            self.assertEqual(len(raw),2096);self.assertEqual(page_decode(raw)[4][-1][0],5000)
            self.assertFalse(any(e['command'] not in ('get_auth_state','get_state','get_queue') for e in commands))
            self.assertTrue(all(e['limit']==0 for e in commands if e['command']=='get_queue'))
            self.assertEqual(len(upcoming),5000);self.assertEqual(state['item']['uri'],track(0))
    def test_search_result_beyond_thirty_two_preserves_queue_and_long_audio_hold(self):
        with live_queue(80,.12) as (client,commands,state,upcoming):
            receive(client,lambda tag,p:tag==b'QPAG' and page_decode(p)[3]==80)
            command(client,13,1,'Song 79')
            raw=receive(client,lambda tag,p:tag==b'QPAG' and page_decode(p)[0]==1)
            token=page_decode(raw)[4][0][2];command(client,12,0,token)
            markers=set();progress=[]
            def done(tag,p):
                if tag==b'AFLU':
                    marker,hold=struct.unpack('<II',p)
                    if hold:markers.add(marker)
                if tag==b'QJMP':progress.append(struct.unpack('<II',p))
                return tag==b'QPAG' and state['item']['uri']==track(79) and page_decode(p)[3]==1
            receive(client,done,25)
            self.assertEqual(sum(e['command']=='skip_next' for e in commands),79)
            self.assertFalse(any(e['command']=='play' and 'uri' in e for e in commands))
            self.assertEqual(upcoming[0]['item']['uri'],track(80));self.assertEqual(state['context']['uri'],'spotify:playlist:'+'P'*22)
            self.assertTrue(any(total==79 for _,total in progress));self.assertGreaterEqual(len(markers),2)
    def test_cancellation_stops_remaining_skips_without_starting_a_replacement_context(self):
        with live_queue(80,.12) as (client,commands,state,upcoming):
            raw=receive(client,lambda tag,p:tag==b'QPAG' and page_decode(p)[3]==80)
            token=page_decode(raw)[4][-1][2];command(client,12,0,token)
            receive(client,lambda tag,p:tag==b'QJMP' and struct.unpack('<II',p)[1]>0)
            command(client,15)
            receive(client,lambda tag,p:tag==b'QJMP' and struct.unpack('<II',p)==(0,0))
            sent=sum(e['command']=='skip_next' for e in commands)
            time.sleep(.2)
            self.assertEqual(sum(e['command']=='skip_next' for e in commands),sent)
            self.assertLess(sent,5);self.assertFalse(any(e['command']=='play' for e in commands))

if __name__=='__main__':unittest.main()
