import contextlib
import ctypes
import io
import os
from pathlib import Path
import socket
import struct
import subprocess
import sys
import threading
import time
import unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'pc'))
import audio_host
import opus_audio
import send_audio
from receiver_quality import Adaptive,Feedback,Report
from security_support import pairing,tls_client
from tunnel_support import TcpForward

def report(mode=0,underruns=0,buffer=469,seconds=10,playing=1,remote=1,actual=192):
    return Report(mode,underruns,buffer,seconds,playing,remote,actual)

class QualityTests(unittest.TestCase):
    def test_fragmented_feedback_and_invalid_input_have_bounded_state(self):
        reports=[report(mode=128),report(mode=320,remote=0)];wire=b''.join(r.encode() for r in reports)
        reader=Feedback();found=[]
        for byte in wire:found.extend(reader.feed(bytes([byte]),now=10))
        self.assertEqual(found,reports);self.assertFalse(reader.data)
        for bad in (report(mode=127),report(buffer=2001),report(playing=2),report(remote=2),report(actual=1)):
            with self.assertRaises(ValueError):Feedback().feed(bad.encode())
        with self.assertRaises(ValueError):Feedback().feed(b'XXXX'+reports[0].encode()[4:])
        with self.assertRaises(ValueError):Feedback().feed(b'x'*1025)
        with self.assertRaises(ValueError):Feedback().feed(report().encode()*17)
    def test_defaults_and_fixed_selection_do_not_adapt_after_stalls(self):
        adaptive=Adaptive(320);self.assertEqual(adaptive.tick(1000),320)
        self.assertEqual(adaptive.observe(report(mode=128),10),128)
        adaptive.send_delay(2,30);adaptive.send_delay(2,31)
        self.assertEqual(adaptive.observe(report(mode=128,underruns=99,buffer=0),100),128)
        self.assertEqual(adaptive.tick(1000),128)
        self.assertEqual(adaptive.observe(report(mode=320,remote=0),1001),320)
    def test_auto_tracks_vita_rebuffers_and_recovers_only_after_sustained_health(self):
        a=Adaptive();self.assertEqual(a.observe(report(),0),192)
        self.assertEqual(a.observe(report(underruns=1,buffer=20,playing=0),6),160)
        self.assertEqual(a.observe(report(underruns=3,buffer=0,playing=0),12),96)
        for t in range(13,72):self.assertEqual(a.observe(report(underruns=3,seconds=t),t),96)
        self.assertEqual(a.observe(report(underruns=3,seconds=73),73),128)
        # Healthy PC capture/network by itself cannot raise quality: feedback
        # must remain fresh and its buffer must be above the receiver threshold.
        self.assertEqual(a.tick(90),96)
    def test_auto_handles_startup_low_buffer_feedback_gaps_and_counter_resets(self):
        a=Adaptive();a.observe(report(buffer=0,seconds=0,playing=0),0)
        for t in range(1,10):self.assertEqual(a.observe(report(buffer=0,seconds=0,playing=0),t),192)
        a.observe(report(seconds=20),10)
        a.observe(report(buffer=40,seconds=21),11)
        self.assertEqual(a.observe(report(buffer=30,seconds=22),12),160)
        self.assertEqual(a.observe(report(seconds=0),13),160)
        self.assertEqual(a.tick(20),160)
        self.assertEqual(a.tick(24),128)
        a.observe(report(seconds=1),25)
        for t in (26,27,28,80):self.assertEqual(a.observe(report(seconds=t),t),128)
    def test_repeated_tcp_stalls_lower_auto_without_waiting_for_delayed_feedback(self):
        a=Adaptive();a.observe(report(remote=0,actual=320,buffer=256),0)
        self.assertEqual(a.send_delay(.3,6),320);self.assertEqual(a.send_delay(.2,7),256)
        self.assertEqual(a.send_delay(.5,8),256);self.assertEqual(a.send_delay(.5,9),256)
        self.assertEqual(a.tick(18),192)
    def test_encoder_changes_cbr_at_packet_boundaries_without_restarting(self):
        with opus_audio.Encoder(320) as encoder:
            state=encoder.state
            for bitrate in (320,128,96,160,192,256,320):
                encoder.set_bitrate(bitrate);packet=encoder.encode(b'\0'*opus_audio.PCM_BYTES)
                self.assertEqual(len(packet),bitrate*1000//8//50);self.assertEqual(encoder.state,state)
            with self.assertRaises(ValueError):encoder.set_bitrate(127)
            self.assertEqual(encoder.bitrate,320)
    def test_real_paired_stream_switches_quality_over_sni_relay_and_native_decoder_survives(self):
        with pairing() as (registry,identity,path,key),contextlib.redirect_stdout(io.StringIO()):
            addresses=[];ready=threading.Event();stop=threading.Event();errors=[]
            def serve():
                try:audio_host.serve('127.0.0.1',0,stop=stop.is_set,factory=lambda:send_audio.tone_blocks(1.4),
                    on_listen=lambda address:(addresses.append(address),ready.set()),security=registry)
                except BaseException as exc:errors.append(exc)
            thread=threading.Thread(target=serve);thread.start();wire=bytearray();sizes=[]
            def exact(sock,n):
                result=bytearray()
                while len(result)<n:
                    data=sock.recv(n-len(result))
                    if not data:raise EOFError
                    result.extend(data)
                return bytes(result)
            try:
                self.assertTrue(ready.wait(2))
                with TcpForward(addresses[0],expected_sni='desktop.example.ts.net') as relay:
                    with tls_client(relay.address,identity,key,private=True,server_hostname='desktop.example.ts.net') as client:
                        self.assertEqual(exact(client,16),opus_audio.header(320));client.sendall(struct.pack('<4sI',b'VPOK',48000))
                        client.sendall(report(mode=128).encode())
                        for frame in range(45):
                            if frame==15:client.sendall(report(mode=320).encode())
                            if frame==30:client.sendall(report(mode=0).encode())
                            length=exact(client,2);n=int.from_bytes(length,'little');data=exact(client,n)
                            wire.extend(length+data);sizes.append(n)
                        # Up to two 60 ms batches may already be encoded/in flight.
                        self.assertTrue(all(n==320 for n in sizes[8:15]),sizes)
                        self.assertTrue(all(n==800 for n in sizes[20:30]),sizes)
                        self.assertTrue(all(n==480 for n in sizes[35:45]),sizes)
                    self.assertEqual(relay.sni,['desktop.example.ts.net']);self.assertNotIn(bytes.fromhex(identity),relay.wire)
            finally:stop.set();thread.join(5)
            self.assertFalse(thread.is_alive());self.assertFalse(errors,errors)
            executable=os.environ.get('VITA_OPUS_TEST_DECODER')
            if executable:
                result=subprocess.run([executable,'--decode'],input=bytes(wire),capture_output=True,check=True,timeout=5)
                self.assertEqual(len(result.stdout),45*3840)

if __name__=='__main__':unittest.main()
