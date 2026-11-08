import importlib.util
import io
import pathlib
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import unittest
import wave
import types
from unittest import mock
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'pc'))
spec = importlib.util.spec_from_file_location('sender', ROOT / 'pc/send_audio.py')
sender = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sender)

class ShortReader(io.BytesIO):
    def read(self, n=-1):
        return super().read(min(n, 13))

class ScriptedSocket:
    def __init__(self, reply):
        self.reply = io.BytesIO(reply)
        self.sent = bytearray()
    def recv(self, size):
        return self.reply.read(min(size, 1))
    def sendall(self, data):
        self.sent.extend(data)

class SenderTests(unittest.TestCase):
    def test_fragmented_pipe_and_partial_final_block(self):
        pcm = bytes(range(256)) * 33
        blocks = list(sender.read_blocks(ShortReader(pcm)))
        self.assertEqual(b''.join(blocks), pcm)
        self.assertEqual([len(b) for b in blocks], [4096,4096,256])
    def test_truncated_stereo_frame_rejected(self):
        with self.assertRaises(ValueError):
            list(sender.read_blocks(io.BytesIO(b'123')))
    def test_tone_is_stereo_and_nonzero(self):
        raw = b''.join(sender.tone_blocks(0.1))
        self.assertEqual(len(raw), 4800*4)
        frames = list(struct.iter_unpack('<hh', raw))
        self.assertTrue(all(l == r for l,r in frames))
        self.assertGreater(max(abs(l) for l,r in frames), 3000)
    def test_startup_handles_fragmented_ack(self):
        s=ScriptedSocket(struct.pack('<4sI',b'VPOK',48000))
        sender.startup(s)
        self.assertEqual(s.sent, sender.HEADER)
    def test_audio_port_error_reported_before_pcm(self):
        s=ScriptedSocket(struct.pack('<4sI',b'VPER',0x80260003))
        with self.assertRaisesRegex(RuntimeError,'audio port: 0x80260003'):
            sender.startup(s)
        self.assertEqual(s.sent, sender.HEADER)
    def test_wrong_version_and_closed_connection(self):
        for reply, message in [(struct.pack('<4sI',b'VPER',1),'audio format'),
                               (struct.pack('<4sI',b'VPOK',44100),'Unexpected'),
                               (b'', 'closed the connection')]:
            with self.subTest(reply=reply):
                with self.assertRaisesRegex(RuntimeError,message):
                    sender.startup(ScriptedSocket(reply))
    def test_capture_conversion_gain_silence_and_channels(self):
        data=np.array([[0.0,0.0],[1.0,-1.0],[3.0,-3.0],[np.nan,np.inf]],dtype=np.float32)
        result=list(struct.iter_unpack('<hh',sender.capture_pcm(data,0.5)))
        self.assertEqual(result,[(0,0),(16383,-16383),(32767,-32767),(0,0)])
        with self.assertRaisesRegex(RuntimeError,'Expected stereo'):
            sender.capture_pcm(np.zeros((10,1)),0.5)
    def test_loopback_configuration_and_recording(self):
        recorder=mock.MagicMock()
        recorder.__enter__.return_value=recorder
        recorder.record.return_value=np.full((1024,2),0.5,dtype=np.float32)
        mic=mock.Mock(name='output',isloopback=True)
        mic.recorder.return_value=recorder
        mic.id='speakers'
        module=types.SimpleNamespace(all_speakers=lambda:[types.SimpleNamespace(id='speakers',name='Test output')],
                                     all_microphones=lambda **kw:[mic])
        with mock.patch.dict(sys.modules,{'soundcard':module}):
            blocks=sender.loopback_blocks('speakers',0.5,4096)
            block=next(blocks)
            blocks.close()
            mic.recorder.assert_called_once_with(samplerate=48000,channels=[0,1],blocksize=4096)
            self.assertEqual(len(block),4096)
            self.assertEqual(struct.unpack('<h',block[:2])[0],8191)
            recorder.__exit__.assert_called()
    def test_debug_wav_contains_exact_pcm_and_closes_on_stop(self):
        raw=b''.join(sender.tone_blocks(0.1))
        with tempfile.TemporaryDirectory() as td:
            path=str(pathlib.Path(td)/'capture.wav')
            g=sender.record_blocks([raw],path)
            self.assertEqual(next(g),raw)
            g.close()
            with wave.open(path,'rb') as f:
                self.assertEqual((f.getnchannels(),f.getsampwidth(),f.getframerate()),(2,2,48000))
                self.assertEqual(f.readframes(f.getnframes()),raw)

    def test_capture_only_never_connects_and_writes_exact_duration(self):
        with tempfile.TemporaryDirectory() as td:
            path=str(pathlib.Path(td)/'capture.wav')
            with mock.patch.object(sender,'loopback_blocks',return_value=sender.tone_blocks(1)), \
                 mock.patch.object(sender.socket,'create_connection',side_effect=AssertionError('No network allowed')):
                self.assertEqual(sender.main(['--capture-only',path,'--seconds','0.1']),0)
            with wave.open(path,'rb') as f:
                self.assertEqual(f.getnframes(),4800)
                self.assertEqual(f.getframerate(),48000)

    def test_retired_plaintext_cli_never_opens_a_network_connection(self):
        for arguments in (['127.0.0.1','--tone'],['127.0.0.1','--loopback'],['127.0.0.1','--stdin']):
            with mock.patch.object(sender.socket,'create_connection') as connect, \
                 mock.patch.object(sender.subprocess,'Popen') as spawn, \
                 mock.patch('sys.stderr',new=io.StringIO()) as error:
                with self.assertRaises(SystemExit) as result:sender.main(arguments)
                self.assertEqual(result.exception.code,2)
                self.assertIn('Unencrypted sending was retired',error.getvalue())
                connect.assert_not_called();spawn.assert_not_called()

if __name__=='__main__': unittest.main()
