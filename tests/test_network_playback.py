"""Receiver pacing, queue identity/async confirmation, and audio transition contracts."""
import contextlib
import io
import json
from pathlib import Path
import socket
import select
import ssl
import struct
import sys
import threading
import time
import unittest
from unittest import mock
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'pc'))
import audio_host
import audio_source
from audio_transport import ReceiverPacer,AudioBatch
from receiver_quality import Feedback,Report,Adaptive
from queue_navigation import QueueCache,QueueJump
from playback_transition import PlaybackTransition
import soloist_bridge as bridge
import opus_audio
import send_audio
import secure_host
from security_support import pairing,tls_client,read_exact

def report(buffer=200,remote=1,received=0,playing=1):
    return Report(320,0,buffer,10,playing,remote,320,received)
def track(n):return 'spotify:track:'+str(n).zfill(22)
def entries(start=1,count=32,duplicate=False):
    return [{'uid':f'entry-{n}','item':{'uri':track(1 if duplicate else n),
             'decorations':{'identity':{'name':f'Song {n}'}}}} for n in range(start,start+count)]
def player(queue=None):
    p=bridge.Player();p.update({'type':'auth_state','logged_in':True,'is_active':True})
    p.update({'type':'playback_state','is_active':True,'status':'playing',
        'item':{'uri':track(0)},'context':{'uri':'spotify:playlist:'+'P'*22},'position':{'position_ms':20000}})
    p.update({'type':'queue_changed','upcoming':queue if queue is not None else entries()})
    return p

class PacingTests(unittest.TestCase):
    def test_v2_feedback_fragmentation_mixed_versions_and_capacity_bounds(self):
        a=report(buffer=2048,received=0xfffffff0);b=Report(128,2,469,10,1,1,128)
        parser=Feedback();found=[]
        for byte in a.encode()+b.encode():found.extend(parser.feed(bytes([byte]),now=1))
        self.assertEqual(found,[a,b]);self.assertFalse(parser.data)
        with self.assertRaises(ValueError):Feedback().feed(report(buffer=2049).encode())
        with self.assertRaises(ValueError):Feedback().feed(b'VAQ3'+a.encode()[4:])
    def test_fresh_low_vita_buffer_allows_bounded_four_times_catchup(self):
        p=ReceiverPacer();p.observe(report(),now=10)
        self.assertEqual(p.delay(2880,10),0);self.assertEqual(p.speed,4)
        p.sent_audio(2880,10)
        self.assertAlmostEqual(p.deadline,10.015)
        self.assertAlmostEqual(p.estimate(10.01),250)
        self.assertEqual(p.catchup_batches,1)
    def test_receiver_and_inflight_audio_bound_prevents_tunnel_buffer_bloat(self):
        p=ReceiverPacer();p.sent=48000;p.observe(report(buffer=1000,received=4800),now=10)
        # PC/Funnel TCP accepted 900 ms that the Vita has not decoded yet.
        self.assertEqual(p.estimate(10),1900)
        self.assertGreater(p.delay(2880,10),0)
        p.observe(report(buffer=1000,received=48000),now=10.2)
        self.assertEqual(p.delay(2880,10.2),0);self.assertEqual(p.speed,1)
    def test_missing_stale_and_legacy_feedback_do_not_grant_unlimited_bursts(self):
        p=ReceiverPacer();self.assertEqual(p.delay(960,0),0);self.assertEqual(p.speed,1)
        p.observe(Report(320,0,0,1,1,1,320),now=1);p.delay(960,2);self.assertEqual(p.speed,1)
        p.observe(report(),now=3);p.delay(960,6);self.assertEqual(p.speed,1)
        with self.assertRaises(TimeoutError):p.delay(960,9)
    def test_short_audio_reset_can_keep_auto_rate_without_overriding_a_fixed_choice(self):
        p=Adaptive(resume_auto={True:128})
        auto=Report(0,0,0,0,0,1,128,0)
        self.assertEqual(p.observe(auto,0),128)
        self.assertEqual(p.observe(report(buffer=1000,received=0),1),320)
        local_auto=Report(0,0,0,0,0,0,320,0)
        self.assertEqual(p.observe(local_auto,2),320)
    def test_acknowledgements_reject_impossible_progress_and_handle_wrap(self):
        p=ReceiverPacer()
        with self.assertRaises(ValueError):p.observe(report(received=1),0)
        p.sent=(1<<32)+1000;p.observe(report(received=0xfffffff0),0)
        p.observe(report(received=100),1);self.assertEqual(p.acked,(1<<32)+100)
        with self.assertRaises(ValueError):p.observe(report(received=50),2)
    def test_batching_preserves_every_framed_packet_and_partial_last_batch(self):
        b=AudioBatch();parts=[opus_audio.framed(bytes([i+1])*800) for i in range(8)];out=[]
        for packet in parts:
            if b.add(packet,960):out.append(b.take())
        if b.parts:out.append(b.take())
        self.assertEqual([len(data) for data,_ in out],[2406,2406,1604])
        self.assertEqual(b''.join(data for data,_ in out),b''.join(parts))
        self.assertEqual(sum(frames for _,frames in out),8*960)
    def test_deterministic_wifi_stall_recovers_buffer_with_queued_capture(self):
        # Exercise the actual pacing model against a virtual decoder/playout clock.
        # A .6 s outage consumes 600 ms of a healthy 1 s receiver cushion.
        p=ReceiverPacer();now=10.;buffer=400.;received=48000;played=True
        p.sent=48000;p.observe(report(buffer=buffer,received=received),now)
        initial=buffer;max_buffer=buffer;sent_batches=0
        for step in range(250):
            now+=.01;buffer=max(0.,buffer-10)
            if step%25==0:p.observe(report(buffer=int(buffer),received=received),now)
            if not p.delay(2880,now):
                p.sent_audio(2880,now);received+=2880;buffer+=60;sent_batches+=1
            max_buffer=max(max_buffer,buffer)
        self.assertGreater(buffer,850);self.assertLess(max_buffer,1300)
        self.assertGreater(p.catchup_batches,0);self.assertGreater(sent_batches,0)

class QueueTests(unittest.TestCase):
    def test_ten_item_broadcast_merges_unchanged_or_advanced_tail_without_flicker(self):
        p=player();cache=p.queue_cache
        cache.update(entries(count=10),bridge.entity,now=1);self.assertEqual(len(cache.items),32)
        cache.update(entries(start=2,count=10),bridge.entity,now=2)
        self.assertEqual(len(cache.items),31);self.assertEqual(cache.items[0]['uri'],track(2))
        cache.request();cache.update(entries(start=2,count=10),bridge.entity,now=3)
        self.assertEqual(len(cache.items),31)
        cache.update(entries(start=2,count=32),bridge.entity,now=3.1);cache.tick(4)
        self.assertEqual(len(cache.items),32);self.assertEqual(cache.items[-1]['uri'],track(33))
    def test_real_short_queue_is_committed_and_context_change_discards_stale_tail(self):
        p=player();cache=p.queue_cache;cache.request();cache.update(entries(count=10),bridge.entity,now=1)
        cache.tick(1.2);self.assertEqual(len(cache.items),32)
        cache.tick(1.4);self.assertEqual(len(cache.items),10)
        p.set_context({'uri':'spotify:album:'+'X'*22});self.assertFalse(cache.items)
        cache.update(entries(50,10),bridge.entity,2);self.assertEqual(len(cache.items),10)
    def test_queue_selection_uses_entry_tokens_and_sequential_confirmed_skip_only(self):
        p=player();jump=QueueJump();token=p.queue[2]['selection']
        self.assertEqual(jump.start(token,p,now=1),[{'type':'command','command':'skip_next'}])
        # Command acceptance, a query snapshot, or a metadata change alone is not completion.
        self.assertEqual(jump.advance(p,1.1),[])
        for n in (1,2,3):
            p.update({'type':'track_changed','item':{'uri':track(n)}})
            self.assertEqual(jump.advance(p,1.1+n*.1),[])
            p.update({'type':'queue_changed','upcoming':entries(n+1,32)})
            commands=jump.advance(p,1.2+n*.1)
            self.assertEqual(commands,[] if n==3 else [{'type':'command','command':'skip_next'}])
        self.assertFalse(jump.active);self.assertEqual(p.queue[0]['uri'],track(4))
        self.assertEqual(p.context,'spotify:playlist:'+'P'*22)
    def test_duplicate_tracks_use_stable_uids_instead_of_matching_first_uri(self):
        p=player(entries(1,6,duplicate=True));jump=QueueJump();jump.start(p.queue[2]['selection'],p,1)
        for n in (1,2,3):
            p.update({'type':'track_changed','item':{'uri':track(1)}})
            p.update({'type':'queue_changed','upcoming':entries(n+1,6,duplicate=True)})
            jump.advance(p,1+n*.1)
        self.assertFalse(jump.active);self.assertEqual(jump.done,3)
    def test_selecting_from_paused_queue_resumes_without_replacing_its_context(self):
        p=player();p.status='paused';jump=QueueJump();jump.start(p.queue[0]['selection'],p,1)
        p.update({'type':'track_changed','item':{'uri':track(1)}})
        p.update({'type':'queue_changed','upcoming':entries(2,32)})
        self.assertEqual(jump.advance(p,1.2),[{'type':'command','command':'play'}])
        self.assertFalse(jump.active);self.assertEqual(p.context,'spotify:playlist:'+'P'*22)
    def test_stale_token_missing_uid_duplicates_and_inactive_context_do_not_start_new_play(self):
        p=player();jump=QueueJump();token=p.queue[2]['selection']
        p.set_context({'uri':'spotify:playlist:'+'Q'*22})
        with self.assertRaises(ValueError):jump.start(token,p,1)
        data=entries(1,4,duplicate=True)
        for entry in data:entry.pop('uid')
        p=player(data)
        with self.assertRaisesRegex(ValueError,'Duplicate'):jump.start(p.queue[2]['selection'],p,1)
        p=player();p.active=False
        with self.assertRaises(ValueError):jump.start(p.queue[0]['selection'],p,1)
    def test_skip_timeout_queries_once_then_cancels_without_replacing_queue(self):
        p=player();jump=QueueJump();original=list(p.queue);jump.start(p.queue[3]['selection'],p,1)
        commands=jump.advance(p,3.1);self.assertEqual([c['command'] for c in commands],['get_state','get_queue'])
        self.assertEqual(jump.advance(p,3.5),[])
        with self.assertRaises(ValueError):jump.advance(p,7.1)
        self.assertFalse(jump.active);self.assertEqual(p.queue,original)
    def test_queue_payload_carries_tokens_while_favorites_keep_spotify_uris(self):
        p=player();raw=bridge.list_payload(p.queue,True)
        self.assertEqual(raw[4+256:4+384].split(b'\0')[0].decode(),p.queue[0]['selection'])
        raw=bridge.list_payload(p.queue,False)
        self.assertEqual(raw[4+256:4+384].split(b'\0')[0].decode(),p.queue[0]['uri'])

class TransitionTests(unittest.TestCase):
    def test_seek_waits_for_actual_position_and_ignores_command_acceptance(self):
        p=player();t=PlaybackTransition();t.begin(p,'seek',80000,now=1)
        t.observe(p,{'type':'command_result','command':'seek'},1.1);self.assertTrue(t.hold)
        t.observe(p,{'type':'playback_state'},1.2);self.assertTrue(t.hold)
        p.position={'position_ms':80000};t.observe(p,{'type':'position_sync'},1.3)
        self.assertFalse(t.hold);self.assertEqual(struct.unpack('<II',t.marker())[1],0)
    def test_queue_hold_requires_explicit_completion_and_timeout_is_bounded(self):
        p=player();t=PlaybackTransition();t.begin(p,'queue',now=1)
        p.update({'type':'track_changed','item':{'uri':track(3)}});t.observe(p,{'type':'track_changed'},2);self.assertTrue(t.hold)
        t.finish(3);self.assertFalse(t.hold)
        t.begin(p,'queue',now=4);self.assertTrue(t.tick(26));self.assertFalse(t.hold)
    def test_pause_and_resume_finish_on_actual_state_not_dispatch(self):
        p=player();t=PlaybackTransition();t.begin(p,'status','paused',1)
        t.observe(p,{'type':'command_result'},1.1);self.assertTrue(t.hold)
        p.status='paused';t.observe(p,{'type':'playback_changed'},1.2);self.assertFalse(t.hold)

class NetworkIntegrationTests(unittest.TestCase):
    def test_real_encrypted_stream_rebuilds_buffer_after_a_blocked_sender(self):
        with pairing() as (registry,identity,path,key),contextlib.redirect_stdout(io.StringIO()) as logs:
            ready=threading.Event();stop=threading.Event();addresses=[];errors=[];blocked=threading.Event();released=threading.Event()
            original=secure_host.SecureSocket.sendall;count=[0];release_time=[None]
            def wire(sock,data,*args,**kwargs):
                if len(data)>16:
                    count[0]+=1
                    if count[0]==25:
                        blocked.set();time.sleep(.6);release_time[0]=time.monotonic();released.set()
                return original(sock,data,*args,**kwargs)
            def source():
                for block in send_audio.tone_blocks(4.2):
                    if stop.is_set():return
                    yield block;time.sleep(len(block)/4/48000)
            def serve():
                try:audio_host.serve('127.0.0.1',0,factory=source,stop=stop.is_set,security=registry,
                    on_listen=lambda address:(addresses.append(address),ready.set()))
                except BaseException as exc:errors.append(exc)
            levels=[];wire_data=bytearray();received=0;buffer=0.;playing=False;rebuffers=0;played=0.
            with mock.patch.object(secure_host.SecureSocket,'sendall',new=wire):
                worker=threading.Thread(target=serve,daemon=True);worker.start()
                try:
                    self.assertTrue(ready.wait(2))
                    with tls_client(addresses[0],identity,key) as client:
                        header=read_exact(client,16)
                        client.sendall(struct.pack('<4sI',b'VPOK',48000));client.setblocking(False)
                        start=last=next_report=time.monotonic();pending=bytearray()
                        while time.monotonic()-start<4.1:
                            now=time.monotonic();elapsed=now-last;last=now
                            if playing:
                                consumed=min(buffer,elapsed*48000);buffer-=consumed;played+=consumed
                                if buffer<=0:playing=False;rebuffers+=1
                            if client.pending() or select.select([client],[],[],.01)[0]:
                                try:data=client.recv(8192)
                                except ssl.SSLWantReadError:data=None
                                if data==b'':break
                                if data:
                                    pending.extend(data)
                                    while len(pending)>=2:
                                        n=struct.unpack_from('<H',pending)[0]
                                        if len(pending)<2+n:break
                                        self.assertEqual(n,800);wire_data.extend(pending[:2+n]);del pending[:2+n]
                                        received+=960;buffer+=960
                            if not playing and buffer>=49152:playing=True
                            now=time.monotonic()
                            if now>=next_report:
                                packet=Report(320,rebuffers,int(buffer*1000/48000),int(played/48000),int(playing),1,320,received).encode()
                                client.settimeout(1);client.sendall(packet);client.setblocking(False);next_report=now+.25
                            if blocked.is_set():levels.append((now,buffer*1000/48000))
                finally:stop.set();worker.join(5)
            self.assertFalse(worker.is_alive());self.assertFalse(errors,errors)
            self.assertTrue(released.is_set());self.assertTrue(levels)
            during=[v for t,v in levels if t<release_time[0]]
            recovered=[v for t,v in levels if t>release_time[0]+.5]
            self.assertLess(min(during),650);self.assertGreater(max(recovered),850)
            self.assertLess(max(v for _,v in levels),1500);self.assertEqual(rebuffers,0)
            text=logs.getvalue();self.assertIn('catch-up batches',text)
            import re
            match=re.search(r'Receiver pacing: (\d+) catch-up',text);self.assertIsNotNone(match)
            self.assertGreater(int(match.group(1)),0)
            # No frame was stretched/repacketized by the recovery path.
            self.assertEqual(len(wire_data)%802,0)

    def test_actual_tls_writes_batch_three_opus_frames_without_changing_payload(self):
        with pairing() as (registry,identity,path,key),contextlib.redirect_stdout(io.StringIO()):
            ready=threading.Event();stop=threading.Event();addresses=[];errors=[];writes=[]
            original=secure_host.SecureSocket.sendall
            def spy(sock,data,*args,**kwargs):
                if len(data)>16:writes.append(len(data))
                return original(sock,data,*args,**kwargs)
            def serve():
                try:audio_host.serve('127.0.0.1',0,factory=lambda:send_audio.tone_blocks(.6),stop=stop.is_set,
                    on_listen=lambda a:(addresses.append(a),ready.set()),security=registry)
                except BaseException as exc:errors.append(exc)
            with mock.patch.object(secure_host.SecureSocket,'sendall',new=spy):
                worker=threading.Thread(target=serve,daemon=True);worker.start();wire=bytearray()
                try:
                    self.assertTrue(ready.wait(2))
                    with tls_client(addresses[0],identity,key) as client:
                        header=read_exact(client,16)
                        self.assertEqual(bytes(header),opus_audio.header(320));client.sendall(struct.pack('<4sI',b'VPOK',48000))
                        while data:=client.recv(8192):wire.extend(data)
                finally:stop.set();worker.join(4)
            self.assertFalse(errors,errors);self.assertFalse(worker.is_alive())
            self.assertEqual(writes,[2406]*10)
            sizes=[];at=0
            while at<len(wire):
                n=struct.unpack_from('<H',wire,at)[0];sizes.append(n);at+=2+n
            self.assertEqual(sizes,[800]*30);self.assertEqual(at,len(wire))

if __name__=='__main__':unittest.main()
