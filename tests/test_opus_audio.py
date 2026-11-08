import contextlib
import io
import math
import os
from pathlib import Path
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'pc'))
import audio_host
import host
import opus_audio
import send_audio
from security_support import pairing,tls_client
from tunnel_support import TcpForward

def exact(sock,size):
    data=bytearray()
    while len(data)<size:
        part=sock.recv(size-len(data))
        if not part:raise EOFError
        data.extend(part)
    return bytes(data)

class OpusTests(unittest.TestCase):
    def test_reblocking_preserves_all_stereo_samples_and_pads_only_the_tail(self):
        original=bytes(range(256))*173
        self.assertEqual(len(original)%4,0)
        reblock=opus_audio.PcmFrames();frames=[]
        for at in range(0,len(original),4096):frames.extend(reblock.feed(original[at:at+4096]))
        frames.extend(reblock.finish())
        self.assertTrue(all(len(f)==3840 for f in frames))
        joined=b''.join(frames);self.assertEqual(joined[:len(original)],original)
        self.assertEqual(joined[len(original):],b'\0'*(len(joined)-len(original)))
        self.assertLess(len(joined)-len(original),3840)

    def test_encoder_cbr_sizes_and_real_stereo_decoding(self):
        # Exercise the same native ABI as Windows; no mock encoder/decoder.
        lib=opus_audio.library()
        import ctypes
        lib.opus_decoder_create.argtypes=[ctypes.c_int32,ctypes.c_int,ctypes.POINTER(ctypes.c_int)]
        lib.opus_decoder_create.restype=ctypes.c_void_p
        lib.opus_decoder_destroy.argtypes=[ctypes.c_void_p]
        lib.opus_decode.argtypes=[ctypes.c_void_p,ctypes.c_char_p,ctypes.c_int32,
                                 ctypes.POINTER(ctypes.c_int16),ctypes.c_int,ctypes.c_int]
        lib.opus_decode.restype=ctypes.c_int
        error=ctypes.c_int();decoder=lib.opus_decoder_create(48000,2,ctypes.byref(error));self.assertTrue(decoder)
        result=[]
        try:
            with opus_audio.Encoder(320) as encoder:
                for frame in range(30):
                    pcm=b''.join(struct.pack('<hh',round(6000*math.sin((frame*960+i)*2*math.pi*440/48000)),
                                                    round(6000*math.sin((frame*960+i)*2*math.pi*997/48000))) for i in range(960))
                    packet=encoder.encode(pcm);self.assertEqual(len(packet),800)
                    out=(ctypes.c_int16*1920)()
                    self.assertEqual(lib.opus_decode(decoder,packet,len(packet),out,960,0),960)
                    result.extend(out)
                encoder.close()
                with self.assertRaises(RuntimeError):encoder.encode(pcm)
        finally:lib.opus_decoder_destroy(decoder)
        left=result[0::2];right=result[1::2]
        self.assertGreater(max(abs(v) for v in left),4000)
        self.assertGreater(sum((a-b)**2 for a,b in zip(left,right)),len(left)*1000000)
        for bitrate in opus_audio.BITRATES:
            with opus_audio.Encoder(bitrate) as encoder:
                self.assertEqual(len(encoder.encode(b'\0'*3840)),bitrate*1000//8//50)

    def test_invalid_codec_parameters_and_frames_are_rejected(self):
        for bitrate in (0,95,321,320000):
            with self.assertRaises(ValueError):opus_audio.header(bitrate)
        for packet in (b'',b'\0'*1276):
            with self.assertRaises(ValueError):opus_audio.framed(packet)
        reblock=opus_audio.PcmFrames()
        for bad in (b'',b'123'):
            with self.assertRaises(ValueError):list(reblock.feed(bad))
        with opus_audio.Encoder() as encoder:
            with self.assertRaises(ValueError):encoder.encode(b'1234')

    def test_paired_tls_audio_stream_reconnects_and_fixed_point_decoder_plays_it(self):
        self.audio_exchange(False)

    def test_opus_audio_through_raw_tcp_tunnel_reconnects_and_decodes(self):
        self.audio_exchange(True)

    def audio_exchange(self,remote):
        with pairing() as (registry,identity,path,key):
            stop=threading.Event();ready=threading.Event();addresses=[];errors=[]
            source=lambda:send_audio.tone_blocks(0.2)
            def run():
                try:audio_host.serve('127.0.0.1',0,stop=stop.is_set,factory=source,
                    on_listen=lambda address:(addresses.append(address),ready.set()),security=registry)
                except BaseException as exc:errors.append(exc)
            thread=threading.Thread(target=run,daemon=True);thread.start()
            try:
                self.assertTrue(ready.wait(2))
                relay=TcpForward(addresses[0]) if remote else None
                if relay:self.addCleanup(relay.close)
                target=('localhost',relay.address[1]) if relay else addresses[0]
                for _ in range(2):
                    with tls_client(target,identity,key) as sock:
                        self.assertEqual(exact(sock,16),opus_audio.header())
                        ack=struct.pack('<4sI',b'VPOK',48000);sock.sendall(ack[:3]);sock.sendall(ack[3:])
                        content=bytearray()
                        while True:
                            part=sock.recv(177)
                            if not part:break
                            content.extend(part)
                    self.assertEqual(len(content),8020)
                    for at in range(0,len(content),802):self.assertEqual(struct.unpack_from('<H',content,at)[0],800)
                    decoder=os.environ.get('VITA_OPUS_TEST_DECODER')
                    if decoder:
                        decoded=subprocess.run([decoder,'--decode'],input=content,capture_output=True,check=True).stdout
                        self.assertEqual(len(decoded),len(b''.join(source())))
                        self.assertGreater(max(abs(v[0]) for v in struct.iter_unpack('<h',decoded)),2000)
            finally:stop.set();thread.join(3)
            self.assertFalse(thread.is_alive());self.assertFalse(errors,errors)

    def test_update_preserves_protected_key_pairing_path_and_favorites_without_prompt(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);source=root/'source';source.mkdir();data=root/'data';data.mkdir()
            (source/'host.py').write_text('# upgraded host');exe=data/'app/soloist/soloist.exe'
            exe.parent.mkdir(parents=True);exe.write_bytes(b'test executable')
            (data/'favorites.json').write_text('[{"name":"Keep me"}]')
            (data/'paired-vitas.json').write_text('existing protected registry')
            previous={'format':1,'key_dpapi':'protected-key','soloist_exe':str(exe),'name':'Same device',
                      'gain':0.5,'capture_blocksize':8192,'device':'same output','app_dir':str(data/'app')}
            with mock.patch.object(host,'HERE',source),mock.patch.object(host,'data_root',return_value=data), \
                 mock.patch.object(host,'load_config',return_value=previous),mock.patch.object(host.windows,'unprotect_key'), \
                 mock.patch.object(host.windows,'pythonw_path'),mock.patch.object(host,'validate_audio'), \
                 mock.patch.object(host,'stop_running'),mock.patch.object(host,'start_background'), \
                 mock.patch.object(host.getpass,'getpass') as prompt,contextlib.redirect_stdout(io.StringIO()):
                host.upgrade()
                self.assertEqual(host.load_config()['key_dpapi'],'protected-key')
            import json
            saved=json.loads((data/'host.json').read_text());self.assertEqual(saved['key_dpapi'],'protected-key')
            self.assertEqual(saved['soloist_exe'],str(exe));self.assertEqual(saved['gain'],0.5)
            self.assertEqual(saved['audio_codec'],'opus');self.assertEqual(saved['opus_bitrate'],320)
            self.assertIn('Keep me',(data/'favorites.json').read_text());prompt.assert_not_called()
            self.assertEqual((data/'paired-vitas.json').read_text(),'existing protected registry')

    def test_upgrade_refreshes_existing_startup_shortcut_to_current_python(self):
        with tempfile.TemporaryDirectory() as td:
            app=Path(td);shortcut=app/'Vita Audio Host.lnk';shortcut.touch()
            value={'key_dpapi':'test','soloist_exe':'/different/soloist.exe'}
            with mock.patch.object(host.sys,'platform','win32'), \
                 mock.patch.object(host,'load_config',return_value=value), \
                 mock.patch.object(host.security,'require_tls'), \
                 mock.patch.object(host.windows,'unprotect_key'), \
                 mock.patch.object(host.windows,'pythonw_path'), \
                 mock.patch.object(host.windows,'startup_shortcut',return_value=shortcut), \
                 mock.patch.object(host.windows,'install_startup') as install, \
                 mock.patch.object(host,'validate_audio'),mock.patch.object(host,'stop_running'), \
                 mock.patch.object(host,'install_files',return_value=app), \
                 mock.patch.object(host,'save_config'),mock.patch.object(host,'start_background'), \
                 contextlib.redirect_stdout(io.StringIO()):
                host.upgrade()
                install.assert_called_once_with(app/'host.py')

    def test_failed_opus_preflight_keeps_existing_host_running(self):
        with mock.patch.object(host,'load_config',return_value={'key_dpapi':'protected'}), \
             mock.patch.object(host.windows,'unprotect_key'),mock.patch.object(host.windows,'pythonw_path'), \
             mock.patch.object(host,'validate_audio',side_effect=RuntimeError('codec missing')), \
             mock.patch.object(host,'stop_running') as stop:
            with self.assertRaisesRegex(RuntimeError,'codec missing'):host.upgrade()
        stop.assert_not_called()

if __name__=='__main__':unittest.main()
