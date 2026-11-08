import base64
import contextlib
import ctypes
import io
import logging
import os
from pathlib import Path
import socket
import struct
import sys
import tempfile
import threading
import time
import types
import unittest
import warnings
from unittest import mock
import numpy as np

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'pc'))
import audio_host
import capture_queue
import host
import send_audio
import soloist_bridge
import windows_host
import secure_host
from security_support import pairing,tls_client

def exact(sock,n):
    data=bytearray()
    while len(data)<n:
        chunk=sock.recv(n-len(data))
        if not chunk:raise EOFError
        data.extend(chunk)
    return bytes(data)

class PersistentHostTests(unittest.TestCase):
    def test_audio_listener_serves_two_paired_sessions_without_restarting(self):
        with pairing() as (registry,identity,path,key):
            stop=threading.Event();ready=threading.Event();addresses=[];errors=[];calls=[]
            def source():calls.append(1);return send_audio.tone_blocks(0.2)
            def run():
                try:audio_host.serve('127.0.0.1',0,stop=stop.is_set,factory=source,codec='pcm',
                    on_listen=lambda address:(addresses.append(address),ready.set()),security=registry)
                except BaseException as exc:errors.append(exc)
            thread=threading.Thread(target=run,daemon=True);thread.start()
            try:
                self.assertTrue(ready.wait(2))
                with socket.create_connection(addresses[0],timeout=4) as client:
                    client.sendall(b'BAD!'+b'0'*30)
                    try:self.assertEqual(client.recv(8),b'')
                    except ConnectionResetError:pass
                self.assertEqual(calls,[])
                expected=b''.join(send_audio.tone_blocks(0.2))
                for _ in range(2):
                    with tls_client(addresses[0],identity,key) as client:
                        self.assertEqual(exact(client,16),send_audio.HEADER)
                        client.sendall(struct.pack('<4sI',b'VPOK',48000));received=bytearray()
                        while True:
                            chunk=client.recv(173)
                            if not chunk:break
                            received.extend(chunk)
                        self.assertEqual(bytes(received),expected)
                self.assertEqual(len(calls),2)
            finally:stop.set();thread.join(3)
            self.assertFalse(thread.is_alive());self.assertFalse(errors,errors)

    def test_discovery_replies_only_to_authenticated_paired_requests(self):
        with pairing() as (registry,identity,path,key):
            reserve=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);reserve.bind(('127.0.0.1',0))
            port=reserve.getsockname()[1];reserve.close();stop=threading.Event()
            thread=threading.Thread(target=host.discovery_server,args=(stop.is_set,mock.Mock(),'127.0.0.1',port,registry),daemon=True)
            thread.start()
            try:
                with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sock:
                    sock.settimeout(0.2);deadline=time.monotonic()+2;response=None
                    query=secure_host.discovery_query(identity,key,b'n'*16)
                    while time.monotonic()<deadline:
                        sock.sendto(query,('127.0.0.1',port))
                        try:response,_=sock.recvfrom(256);break
                        except socket.timeout:pass
                    self.assertEqual(response,secure_host.discovery_reply(query,registry))
                    for invalid in (b'VITA_AUDIO_DISCOVER 1',query[:-1]+b'!',b'bad'):
                        sock.sendto(invalid,('127.0.0.1',port))
                        with self.assertRaises(socket.timeout):sock.recvfrom(256)
            finally:stop.set();thread.join(2)

    def test_a_single_capture_discontinuity_is_not_printed_over_and_over(self):
        recorder=mock.MagicMock();recorder.__enter__.return_value=recorder
        count=[0]
        def record(**kw):
            count[0]+=1
            if count[0]==1:warnings.warn('data discontinuity in recording')
            return np.zeros((1024,2),dtype=np.float32)
        recorder.record.side_effect=record
        mic=mock.Mock(isloopback=True);mic.recorder.return_value=recorder
        mic.id='output'
        module=types.SimpleNamespace(all_speakers=lambda:[types.SimpleNamespace(id='output',name='Test output')],all_microphones=lambda **kw:[mic])
        stats={};error=io.StringIO()
        with mock.patch.dict(sys.modules,{'soundcard':module}), \
             mock.patch.object(send_audio.time,'monotonic',side_effect=[10*i for i in range(20)]), \
             contextlib.redirect_stderr(error),contextlib.redirect_stdout(io.StringIO()):
            stream=send_audio.loopback_blocks('output',stats=stats)
            for _ in range(12):next(stream)
            stream.close()
        self.assertEqual(stats['discontinuities'],1)
        self.assertEqual(error.getvalue().count('Windows capture reports'),1)

    def test_prefill_and_external_stop_cancel_capture_without_waiting_for_more_samples(self):
        release=threading.Event();stopped=threading.Event()
        def source():
            release.wait(2);yield b'\0'*4096
        worker=capture_queue.CaptureQueue(source,stop_requested=stopped.is_set)
        try:
            stopped.set()
            with self.assertRaises(InterruptedError):worker.prefill()
            with self.assertRaises(StopIteration):next(worker)
        finally:release.set();worker.close()
        self.assertFalse(worker.thread.is_alive())

    def test_audio_mmcss_registration_is_reverted_even_after_an_exception(self):
        api=mock.Mock();api.AvSetMmThreadCharacteristicsW.return_value=123
        with mock.patch.object(capture_queue.sys,'platform','win32'), \
             mock.patch.object(ctypes,'WinDLL',return_value=api,create=True):
            with self.assertRaisesRegex(RuntimeError,'test'):
                with capture_queue.audio_priority():raise RuntimeError('test')
        self.assertEqual(api.AvSetMmThreadCharacteristicsW.call_args.args[0],'Audio')
        api.AvRevertMmThreadCharacteristics.assert_called_once_with(123)

    def test_install_preserves_existing_favorites_and_avoids_copying_recordings(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);source=root/'source';source.mkdir();data=root/'data';data.mkdir()
            (source/'host.py').write_text('# test');(source/'capture.wav').write_bytes(b'not application data')
            (source/'favorites.json').write_text('[]');(source/'soloist').mkdir();(source/'soloist'/'soloist.exe').write_bytes(b'test executable')
            (data/'favorites.json').write_text('[{"name":"Keep me","uri":"spotify:track:'+'A'*22+'"}]')
            with mock.patch.object(host,'HERE',source),mock.patch.object(host,'data_root',return_value=data):
                destination=host.install_files()
            self.assertTrue((destination/'host.py').exists());self.assertTrue((destination/'soloist'/'soloist.exe').exists())
            self.assertFalse((destination/'capture.wav').exists())
            self.assertIn('Keep me',(data/'favorites.json').read_text())

    def test_native_key_is_not_passed_to_audio_or_control_helpers_and_is_redacted(self):
        value={'app_dir':'/app','soloist_exe':'/app/soloist/soloist.exe','name':'Vita',
               'gain':0.5,'capture_blocksize':8192,'device':None}
        commands=host.child_commands(value,'private-test-key')
        self.assertIn('private-test-key',commands['Soloist'])
        self.assertNotIn('private-test-key',commands['Audio']);self.assertNotIn('private-test-key',commands['Controls'])
        self.assertIn('--listen',commands['Controls'])
        record=logging.LogRecord('test',20,'',0,'Native output: %s',('private-test-key',),None)
        host.Redact('private-test-key').filter(record)
        self.assertNotIn('private-test-key',record.getMessage())

    def test_dpapi_calls_user_scope_without_prompt_and_frees_returned_memory(self):
        crypt=mock.Mock();kernel=mock.Mock();kept=[];flags=[]
        def output_bytes(pointer,data):
            storage=ctypes.create_string_buffer(data);kept.append(storage)
            output=ctypes.cast(pointer,ctypes.POINTER(windows_host.Blob)).contents
            output.size=len(data);output.data=ctypes.cast(storage,ctypes.POINTER(ctypes.c_ubyte))
        def protect(source,description,entropy,reserved,prompt,flag,output):
            self.assertIsNone(prompt);self.assertIsNone(entropy);flags.append(flag)
            output_bytes(output,b'opaque Windows ciphertext');return 1
        def unprotect(source,description,entropy,reserved,prompt,flag,output):
            self.assertIsNone(prompt);flags.append(flag);output_bytes(output,b'private-test-key');return 1
        crypt.CryptProtectData.side_effect=protect;crypt.CryptUnprotectData.side_effect=unprotect
        with mock.patch.object(windows_host,'_windows'), \
             mock.patch.object(ctypes,'WinDLL',side_effect=lambda name,**kw:crypt if name=='crypt32' else kernel,create=True):
            saved=windows_host.protect_key('private-test-key')
            self.assertNotIn(b'private-test-key',base64.b64decode(saved))
            self.assertEqual(windows_host.unprotect_key(saved),'private-test-key')
        self.assertEqual(flags,[1,1]);self.assertEqual(kernel.LocalFree.call_count,2)

    def test_artwork_chunks_yield_to_state_and_survive_partial_socket_writes(self):
        class Socket:
            def __init__(self):self.data=bytearray()
            def send(self,data):n=min(len(data),257);self.data.extend(data[:n]);return n
        sock=Socket();writer=soloist_bridge.VitaOutbox();pixels=bytes(range(256))*392 # exactly 224*224*2
        self.assertEqual(len(pixels),224*224*2)
        writer.artwork(42,pixels)
        for i in range(1000):
            if i==2:writer.queue(b'STAT',b'state update')
            writer.flush(sock,i*0.005)
            if writer.art is None and not writer.pending and not writer.latest:break
        data=bytes(sock.data);tags=[];result=bytearray()
        while data:
            tag,n=struct.unpack_from('<4sI',data);payload=data[8:8+n];data=data[8+n:];tags.append(tag)
            if tag==b'ARTC':
                art_id,offset=struct.unpack_from('<II',payload)
                self.assertEqual(art_id,42);self.assertEqual(offset,len(result));result.extend(payload[8:])
        self.assertEqual(bytes(result),pixels)
        self.assertEqual(tags[:3],[b'ARTC',b'STAT',b'ARTC'])

    def test_startup_uses_installed_pythonw_and_only_removes_its_own_shortcut(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);shortcut=root/'Vita Audio Host.lnk';other=root/'Another app.lnk'
            other.write_text('keep this shortcut')
            application=root/"Emanuel's app"/'host.py'
            interpreter=root/'Python 3.14'/'pythonw.exe'
            with mock.patch.object(windows_host,'startup_shortcut',return_value=shortcut), \
                 mock.patch.object(windows_host,'pythonw_path',return_value=interpreter), \
                 mock.patch.object(windows_host.subprocess,'CREATE_NO_WINDOW',0x08000000,create=True), \
                 mock.patch.object(windows_host.subprocess,'run') as launch:
                self.assertEqual(windows_host.install_startup(application),shortcut)
                args=launch.call_args.args[0]
                self.assertEqual(args[:4],['powershell.exe','-NoProfile','-NonInteractive','-Command'])
                script=args[4]
                self.assertIn('pythonw.exe',script);self.assertIn('--run',script)
                self.assertIn("Emanuel''s app",script)
                self.assertNotIn('--api-key',script)
                shortcut.write_text('installed shortcut')
                windows_host.remove_startup()
                self.assertFalse(shortcut.exists());self.assertTrue(other.exists())

    def test_receiver_diagnostics_are_distinct_from_spotify_commands(self):
        reports=[];frames=soloist_bridge.Frames(reports.append)
        raw=soloist_bridge.packet(b'RSTA',struct.pack('<4I',2,180,90,1))
        self.assertEqual(frames.feed(raw),[]);self.assertEqual(reports,[(2,180,90,1)])

if __name__=='__main__':unittest.main()
