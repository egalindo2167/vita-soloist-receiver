"""Dedicated cable selection, owned-process identity, native pipe and TLS failure tests."""
import contextlib
import ctypes
import hashlib
import io
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import types
import unittest
from unittest import mock
import numpy as np # Import under the actual platform before exercising mocked Windows calls.

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'pc'))
import audio_config
import audio_source as audio
import audio_host
import host
import send_audio
import windows_host
from security_support import pairing,tls_client,read_exact

CABLE={'id':'{exact.cable.id}','name':'CABLE Input (VB-Audio Virtual Cable)'}
PHYSICAL={'id':'headphones','name':'Headphones (Realtek)'}

def write_config(root,verified=True):
    value={'format':1,'key_dpapi':'opaque','soloist_exe':str(root/'soloist.exe'),'gain':.5,
           'audio_codec':'opus','opus_bitrate':320,'funnel_enabled':True,'listen_scope':'auto',
           'capture':{'format':1,'mode':'soloist-process','device_id':CABLE['id'],
                      'device_name':CABLE['name'],'route_verified':verified}}
    (root/'host.json').write_text(json.dumps(value))
    (root/'soloist-runtime.json').write_text(json.dumps({'format':1,'pid':123,'created':456,'exe':value['soloist_exe']}))
    return value

class AudioPolicyTests(unittest.TestCase):
    def test_capture_helper_integrity_and_only_shipped_path(self):
        path=audio.helper_path();self.assertEqual(path,ROOT/'pc/native/soloist-capture.exe')
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),audio.HELPER_SHA256)
        with mock.patch.object(audio,'HELPER_SHA256','0'*64):
            with self.assertRaisesRegex(audio.CaptureError,'integrity'):audio.helper_path()

    def test_missing_or_unverified_capture_never_becomes_default_output(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            for contents,code in [({'device':'headphones'},1),({'capture':None},1)]:
                (root/'host.json').write_text(json.dumps(contents))
                with self.assertRaises(audio.CaptureError) as caught:audio.load_capture(root/'host.json')
                self.assertEqual(caught.exception.code,code)
            write_config(root,False)
            self.assertEqual(audio.capture_block_reason(root)[0],7)
            value=write_config(root,True)
            self.assertEqual(audio.load_capture(root/'host.json')['device_id'],CABLE['id'])
            value['capture']['route_verified']='yes';(root/'host.json').write_text(json.dumps(value))
            self.assertEqual(audio.capture_block_reason(root)[0],7)

    def test_picker_uses_render_cable_and_exact_id_never_nearest_default(self):
        cable2={**CABLE,'id':'other-cable'}
        self.assertEqual(audio_config.cable_candidates([PHYSICAL,CABLE]),[CABLE])
        self.assertEqual(audio_config.selected_device([cable2,CABLE],CABLE['id']),CABLE)
        with self.assertRaises(audio.CaptureError) as caught:
            audio_config.selected_device([PHYSICAL,cable2],CABLE['id'])
        self.assertEqual(caught.exception.code,2)
        with self.assertRaises(audio.CaptureError):audio_config.selected_device([CABLE,CABLE],CABLE['id'])

    def test_selection_preserves_keys_network_quality_and_favorites(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);value=write_config(root);value['device']='old-headphones'
            favorites=root/'favorites.json';favorites.write_text('["keep"]')
            with mock.patch.object(host,'data_root',return_value=root):
                audio_config.save_selection(value,CABLE,True)
            saved=json.loads((root/'host.json').read_text())
            self.assertEqual(saved['key_dpapi'],'opaque');self.assertTrue(saved['funnel_enabled'])
            self.assertEqual(saved['opus_bitrate'],320);self.assertNotIn('device',saved)
            self.assertEqual(favorites.read_text(),'["keep"]')
            self.assertEqual(audio.capture_block_reason(root),(0,''))

    def test_capture_errors_are_latched_until_a_successful_retry_or_setup(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);source=write_config(root)['capture']
            audio.source_status(4,source,root,state='blocked')
            self.assertEqual(audio.capture_block_reason(root)[0],4)
            audio.source_status(0,source,root)
            self.assertEqual(audio.capture_block_reason(root),(0,''))
            # A removed Soloist manifest cannot target an unrelated process.
            (root/'soloist-runtime.json').unlink()
            with self.assertRaises(audio.CaptureError) as caught:audio.runtime_process(root)
            self.assertEqual(caught.exception.code,3)

    def test_process_manifest_is_bound_to_configured_executable_and_numeric_identity(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);write_config(root);path=root/'soloist-runtime.json'
            good=json.loads(path.read_text());self.assertEqual(audio.runtime_process(root)['created'],456)
            for changes in ({'pid':0},{'pid':True},{'created':0},{'created':2**64},{'exe':str(root/'browser.exe')}):
                path.write_text(json.dumps({**good,**changes}))
                with self.subTest(changes=changes),self.assertRaises(audio.CaptureError):audio.runtime_process(root)

    def test_confirmed_soloist_expiry_gets_a_specific_error_and_is_cleared_on_restart(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);value=write_config(root);(root/'soloist-runtime.json').unlink()
            with mock.patch.object(host,'data_root',return_value=root):
                host.soloist_status(value,10)
                with self.assertRaises(audio.CaptureError) as caught:audio.runtime_process(root)
                self.assertEqual(caught.exception.code,8)
                host.soloist_status(value)
                with self.assertRaises(audio.CaptureError) as caught:audio.runtime_process(root)
                self.assertEqual(caught.exception.code,3)

    def test_ensure_missing_saved_cable_is_an_error_and_does_not_reselect(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);value=write_config(root)
            with mock.patch.object(audio_config,'check_platform'),mock.patch.object(host,'load_config',return_value=value), \
                 mock.patch.object(host,'data_root',return_value=root),mock.patch.object(audio,'render_devices',return_value=[PHYSICAL]), \
                 mock.patch('builtins.input',side_effect=AssertionError('Must not select a new device')):
                with self.assertRaises(audio.CaptureError) as caught:audio_config.setup(ensure=True)
            self.assertEqual(caught.exception.code,2)
            self.assertEqual(json.loads((root/'host.json').read_text())['capture']['device_id'],CABLE['id'])

    def test_wizard_prepares_only_cable_and_requires_successful_live_route(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);value=write_config(root,False)
            with mock.patch.object(audio_config,'check_platform'),mock.patch.object(audio_config,'ensure_runtime'), \
                 mock.patch.object(host,'load_config',side_effect=lambda:json.loads((root/'host.json').read_text())), \
                 mock.patch.object(host,'data_root',return_value=root),mock.patch.object(audio,'render_devices',return_value=[PHYSICAL,CABLE]), \
                 mock.patch.object(audio,'helper_json',return_value={}) as helper, \
                 mock.patch.object(audio,'probe',side_effect=[{'route_verified':False},audio.CaptureError(4),{'route_verified':True}]), \
                 mock.patch.object(os,'startfile',create=True) as settings,mock.patch('builtins.input',side_effect=['','','','']), \
                 contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(audio_config.setup(),0)
            helper.assert_called_once_with(['--prepare-device','--device',CABLE['id']])
            settings.assert_called_once_with('ms-settings:apps-volume')
            self.assertTrue(json.loads((root/'host.json').read_text())['capture']['route_verified'])

    def test_no_virtual_cable_does_not_select_headphones(self):
        with mock.patch.object(audio_config,'check_platform'),mock.patch.object(host,'load_config',return_value={}), \
             mock.patch.object(audio,'render_devices',return_value=[PHYSICAL]),mock.patch.object(host,'save_config') as save, \
             contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(audio.CaptureError):audio_config.setup()
        save.assert_not_called()

    def test_unsupported_windows_build_stops_before_choosing_an_audio_device(self):
        with mock.patch.object(audio,'helper_json',return_value={'format':1,'build':19045}):
            with self.assertRaises(audio.CaptureError) as caught:audio_config.check_platform()
        self.assertEqual(caught.exception.code,5)

    def test_diagnostic_endpoint_capture_requires_exact_explicit_device(self):
        output=types.SimpleNamespace(id='one',name='Exact output')
        sc=types.SimpleNamespace(all_speakers=lambda:[output],all_microphones=lambda **kw:[],
             default_speaker=mock.Mock(side_effect=AssertionError('Default output is forbidden')))
        with mock.patch.dict(sys.modules,{'soundcard':sc}):
            for hint in (None,'Exact','missing','one'):
                with self.subTest(hint=hint),self.assertRaises(RuntimeError):next(send_audio.loopback_blocks(hint))
        sc.default_speaker.assert_not_called()

    def test_managed_child_commands_enforce_capture_policy_and_do_not_pass_legacy_device(self):
        value={'app_dir':'app','soloist_exe':'soloist.exe','name':'Vita','gain':.5,'capture_blocksize':8192,'device':'headphones'}
        commands=host.child_commands(value,'secret')
        self.assertIn('--capture-config',commands['Audio']);self.assertNotIn('--device',commands['Audio'])
        self.assertIn('--capture-root',commands['Controls']);self.assertNotIn('secret',commands['Controls'])

    def test_owned_process_manifest_uses_os_creation_time_and_actual_image(self):
        api=mock.Mock();process=types.SimpleNamespace(pid=9123,_handle=0x12345678)
        def times(handle,born,*unused):
            self.assertEqual(handle,process._handle)
            born._obj.dwHighDateTime=0x12345678;born._obj.dwLowDateTime=0x90abcdef;return 1
        def image(handle,flags,buffer,size):
            self.assertEqual(handle,process._handle);self.assertEqual(flags,0)
            buffer.value=r'C:\Soloist\soloist.exe';size._obj.value=len(buffer.value);return 1
        api.GetProcessTimes.side_effect=times;api.QueryFullProcessImageNameW.side_effect=image
        with mock.patch.object(windows_host,'_windows'),mock.patch.object(ctypes,'WinDLL',return_value=api,create=True):
            value=windows_host.process_identity(process)
        self.assertEqual(value,{'format':1,'pid':9123,'created':0x1234567890abcdef,'exe':r'C:\Soloist\soloist.exe'})

class NativePipeTests(unittest.TestCase):
    @contextlib.contextmanager
    def native(self,root,body):
        """Actual child pipes and lifetime; only WASAPI/Windows job calls are replaced."""
        script=root/'fake_native.py';script.write_text('import sys,struct,time\n'+body)
        real_popen=subprocess.Popen;seen=[];processes=[];job=mock.Mock()
        def spawn(command,**options):
            seen.append((command,options));options.pop('creationflags',None)
            process=real_popen([sys.executable,str(script)],**options);processes.append(process);return process
        def stop(process):
            if process is not None and process.poll() is None:process.terminate();process.wait(timeout=3)
        with mock.patch.object(audio.sys,'platform','win32'), \
             mock.patch.object(audio,'process_options',return_value={'creationflags':0}), \
             mock.patch.object(audio.subprocess,'CREATE_NO_WINDOW',0x08000000,create=True), \
             mock.patch.object(audio.windows_host,'OwnedProcessJob',return_value=job), \
             mock.patch.object(audio.subprocess,'Popen',side_effect=spawn),mock.patch.object(audio,'stop_process',side_effect=stop):
            try:yield seen,processes,job
            finally:
                for process in processes:
                    stop(process)
                    for stream in (process.stdout,process.stderr):
                        if stream and not stream.closed:stream.close()

    def test_native_startup_pcm_gain_owned_identity_and_disconnect_cleanup(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);write_config(root)
            body="sys.stdout.buffer.write(struct.pack('<4sIII',b'VACP',1,0,0)+struct.pack('<h',10000)*2048);sys.stdout.buffer.flush();time.sleep(30)\n"
            with self.native(root,body) as (seen,processes,job):
                source=audio.NativeSource(root/'host.json',.5)
                try:
                    self.assertEqual(next(source.blocks()),struct.pack('<h',5000)*2048)
                    command=seen[0][0];self.assertIn('--pid',command);self.assertIn('123',command)
                    self.assertIn('--created',command);self.assertIn('456',command);self.assertIn(CABLE['id'],command)
                    job.assign.assert_called_once_with(processes[0])
                finally:source.close()
                self.assertIsNotNone(processes[0].poll());job.close.assert_called_once()
                self.assertFalse(source.reader.is_alive());self.assertFalse(source.start_thread.is_alive())

    def test_native_startup_route_error_closes_child_and_persists_clear_status(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);write_config(root)
            with self.native(root,"sys.stdout.buffer.write(struct.pack('<4sIII',b'VACP',1,4,0));sys.stdout.buffer.flush();time.sleep(30)\n") as (_,processes,job):
                with self.assertRaises(audio.CaptureError) as caught:audio.NativeSource(root/'host.json')
                self.assertEqual(caught.exception.code,4);self.assertIsNotNone(processes[0].poll())
                job.close.assert_called_once()
            self.assertEqual(audio.capture_block_reason(root)[0],4)

    def test_native_stderr_route_error_stops_audio_instead_of_delivering_more_pcm(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);write_config(root)
            body="sys.stdout.buffer.write(struct.pack('<4sIII',b'VACP',1,0,0));sys.stdout.buffer.flush();time.sleep(.1)\n" \
                 "sys.stderr.write('{\"event\":\"error\",\"code\":2}\\n');sys.stderr.flush();time.sleep(.1)\n"
            with self.native(root,body):
                source=audio.NativeSource(root/'host.json')
                try:
                    with self.assertRaises(audio.CaptureError) as caught:next(source.blocks())
                    self.assertEqual(caught.exception.code,2)
                finally:source.close()
            self.assertEqual(audio.capture_block_reason(root)[0],2)

    def test_unknown_native_startup_format_never_yields_pcm_and_cleans_up(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);write_config(root)
            with self.native(root,"sys.stdout.buffer.write(b'X'*16);sys.stdout.buffer.flush();time.sleep(30)\n") as (_,processes,job):
                with self.assertRaises(audio.CaptureError) as caught:audio.NativeSource(root/'host.json')
                self.assertEqual(caught.exception.code,6);self.assertIsNotNone(processes[0].poll())
                job.close.assert_called_once()

    def test_encoder_failure_also_closes_owned_native_capture(self):
        source=mock.Mock();sock=mock.Mock()
        with mock.patch.object(audio,'open_source',return_value=source), \
             mock.patch.object(audio_host.opus_audio,'Encoder',side_effect=RuntimeError('encoder failed')):
            with self.assertRaisesRegex(RuntimeError,'encoder failed'):audio_host.stream_session(sock)
        source.close.assert_called_once()
        self.assertFalse(any(c.args[:2]==(socket.SOL_SOCKET,socket.SO_SNDBUF) for c in sock.setsockopt.call_args_list))

class CaptureTlsTests(unittest.TestCase):
    def test_capture_failure_is_reported_after_auth_without_starting_pcm_or_opus(self):
        with pairing() as (registry,identity,path,key),tempfile.TemporaryDirectory() as td:
            root=Path(td);write_config(root);stop=threading.Event();ready=threading.Event();addresses=[];errors=[]
            def run():
                try:audio_host.serve('127.0.0.1',0,security=registry,stop=stop.is_set,capture_config=root/'host.json',
                    on_listen=lambda address:(addresses.append(address),ready.set()))
                except BaseException as exc:errors.append(exc)
            with mock.patch.object(audio,'open_source',side_effect=audio.CaptureError(2)) as source:
                worker=threading.Thread(target=run,daemon=True);worker.start()
                try:
                    self.assertTrue(ready.wait(2))
                    with socket.create_connection(addresses[0],timeout=2) as raw:
                        raw.sendall(b'garbage');raw.shutdown(socket.SHUT_WR)
                        with contextlib.suppress(OSError):raw.recv(64)
                    source.assert_not_called()
                    with tls_client(addresses[0],identity,key) as client:
                        header=read_exact(client,16)
                        self.assertEqual(bytes(header),struct.pack('<4sIII',b'VAER',2,1,0))
                        self.assertEqual(client.recv(1),b'')
                    self.assertEqual(source.call_count,1)
                finally:stop.set();worker.join(3)
                self.assertFalse(worker.is_alive());self.assertFalse(errors,errors)

if __name__=='__main__':unittest.main()
