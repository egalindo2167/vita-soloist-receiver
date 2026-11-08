import contextlib
import ctypes
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'pc'))
import host
import tunnel
from security_support import pairing,tls_client
from tunnel_support import TcpForward
import secure_host
import windows_host

AUDIO='tcp://0.tcp.ngrok.io:12345'
CONTROLS='tcp://1.tcp.eu.ngrok.io:54321'

def api_value(audio=AUDIO,controls=CONTROLS):
    return {'endpoints':[{'name':'vita-audio','url':audio,'upstream':{'url':'127.0.0.1:48152'}},
                       {'name':'vita-controls','url':controls,'upstream':{'url':'127.0.0.1:48153'}}]}

class TunnelTests(unittest.TestCase):
    def test_profile_has_separate_endpoints_and_no_provider_or_pairing_credentials(self):
        with tempfile.TemporaryDirectory() as td:
            path,changed=tunnel.export_profile(AUDIO,CONTROLS,td)
            self.assertTrue(changed);self.assertEqual(path.name,'remote-host.txt')
            data=path.read_bytes()
            self.assertEqual(data,b'VART1\naudio_host=0.tcp.ngrok.io\naudio_port=12345\ncontrol_host=1.tcp.eu.ngrok.io\ncontrol_port=54321\n')
            stamp=path.stat().st_mtime_ns
            self.assertFalse(tunnel.export_profile(AUDIO,CONTROLS,td)[1]);self.assertEqual(path.stat().st_mtime_ns,stamp)
            self.assertTrue(tunnel.export_profile(AUDIO,'tcp://new.ngrok.io:30000',td)[1])
            self.assertNotIn(b'authtoken',data);self.assertNotIn(b'VASEC',data)
    def test_invalid_endpoints_are_rejected_without_overwriting_good_profile(self):
        with tempfile.TemporaryDirectory() as td:
            path,_=tunnel.export_profile(AUDIO,CONTROLS,td);before=path.read_bytes()
            for bad in ('http://x:443','tls://x:443','tcp://x','tcp://x:0','tcp://x:65536','tcp://user:password@x:1',
                        'tcp://x:1/path','tcp://x:1?token=secret','tcp://x:1#fragment','tcp://[::1]:1',
                        'tcp://a..b:1','tcp://-host:1','tcp://host-:1','tcp://a b:1','tcp://a\nb:1',
                        'tcp://0.0.0.0:1','tcp://256.0.0.1:1','tcp://127.1:1','tcp://0127.0.0.1:1',
                        'tcp://'+'a'*64+'.net:1','tcp://'+'a.'*130+'net:1'):
                with self.subTest(bad=bad),self.assertRaises(ValueError):tunnel.export_profile(bad,CONTROLS,td)
                self.assertEqual(path.read_bytes(),before)
    def test_agent_api_only_exports_expected_raw_tcp_upstreams(self):
        self.assertEqual(tunnel.agent_endpoints(api_value()),(AUDIO,CONTROLS))
        value=api_value();value['endpoints'].pop();self.assertIsNone(tunnel.agent_endpoints(value))
        for change in ('http','wrong-port','duplicate','oversized'):
            value=api_value()
            if change=='http':value['endpoints'][0]['url']='https://example.ngrok.app'
            if change=='wrong-port':value['endpoints'][0]['upstream']['url']='127.0.0.1:22'
            if change=='duplicate':value['endpoints'].append(value['endpoints'][0])
            if change=='oversized':value['endpoints']*=5
            with self.assertRaises(ValueError):tunnel.agent_endpoints(value)
    def test_ngrok_configuration_contains_only_two_loopback_tcp_services(self):
        text=tunnel.config_text(45001)
        self.assertEqual(text.count('url: tcp://\n'),2)
        self.assertIn('web_addr: 127.0.0.1:45001',text)
        self.assertIn('127.0.0.1:48152',text);self.assertIn('127.0.0.1:48153',text)
        self.assertNotIn('authtoken',text);self.assertNotIn('0.0.0.0',text)
    def test_real_ngrok_cli_accepts_generated_configuration(self):
        executable=os.environ.get('VITA_NGROK_TEST_AGENT')
        if not executable:self.skipTest('Optional official ngrok CLI config validation')
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'ngrok.yml';path.write_text(tunnel.config_text(45001))
            tunnel.check_agent(Path(executable),path)
    def test_host_only_starts_tunnels_after_opt_in_and_sends_no_keys_in_argv(self):
        value={'app_dir':'/app','soloist_exe':'/app/soloist.exe','name':'Vita','gain':.5,'capture_blocksize':8192}
        self.assertNotIn('Tunnel',host.child_commands(value,'soloist-private'))
        value['tunnel_enabled']=True;commands=host.child_commands(value,'soloist-private')
        self.assertEqual(commands['Tunnel'],[sys.executable,str(Path('/app/tunnel.py')),'--run'])
        self.assertNotIn('soloist-private',commands['Tunnel'])
    def test_agent_logs_redact_token(self):
        process=mock.Mock(stdout=io.StringIO('message: private-test-token\n'))
        with contextlib.redirect_stdout(io.StringIO()) as output:tunnel.pump_agent(process,'private-test-token')
        self.assertNotIn('private-test-token',output.getvalue());self.assertIn('<redacted>',output.getvalue())
    def test_supervisor_exports_changes_and_stops_only_its_owned_agent(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);process=mock.Mock();process.poll.return_value=None;process.stdout=io.StringIO('agent ready\n')
            stop=threading.Event();count=[0]
            def read(port):
                count[0]+=1
                if count[0]==2:stop.set()
                return api_value(controls=CONTROLS if count[0]==1 else 'tcp://changed.ngrok.io:12300')
            with mock.patch.object(tunnel,'load_settings',return_value={'ngrok_exe':'ngrok.exe','token_dpapi':'opaque'}), \
                 mock.patch.object(tunnel.windows_host,'unprotect_key',return_value='private-test-token'), \
                 mock.patch.object(tunnel.subprocess,'Popen',return_value=process) as launch, \
                 mock.patch.object(tunnel,'stop_process') as cleanup,mock.patch.object(tunnel,'read_agent',side_effect=read), \
                 contextlib.redirect_stdout(io.StringIO()) as output:
                tunnel.run(stop.is_set,root)
            command=launch.call_args.args[0];environment=launch.call_args.kwargs['env']
            self.assertNotIn('private-test-token',' '.join(command));self.assertEqual(environment['NGROK_AUTHTOKEN'],'private-test-token')
            self.assertNotIn('private-test-token',(root/'ngrok-vita.yml').read_text())
            self.assertIn('control_host=changed.ngrok.io',(root/'remote/remote-host.txt').read_text())
            self.assertFalse(json.loads((root/'tunnel-status.json').read_text())['running'])
            cleanup.assert_called_once_with(process);self.assertNotIn('private-test-token',output.getvalue())
    def test_setup_stores_provider_key_protected_and_copies_agent_to_stable_path(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);app=root/'app';app.mkdir();(app/'tunnel.py').touch()
            source=root/'ngrok.exe';source.write_bytes(b'test fixture, not executable')
            value={'app_dir':str(app),'key_dpapi':'existing-soloist-key','name':'existing device'}
            with mock.patch.object(tunnel.sys,'platform','win32'), \
                 mock.patch.object(tunnel,'root_path',return_value=root), \
                 mock.patch.object(tunnel,'find_agent',return_value=source), \
                 mock.patch.object(tunnel,'check_agent'), \
                 mock.patch.object(tunnel,'load_settings',side_effect=FileNotFoundError), \
                 mock.patch.object(tunnel.getpass,'getpass',return_value='provider-test-token'), \
                 mock.patch.object(tunnel.windows_host,'protect_key',return_value='opaque-dpapi') as protect, \
                 mock.patch.object(host,'load_config',return_value=value), \
                 mock.patch.object(host,'save_config') as save, \
                 mock.patch.object(host,'stop_running'),mock.patch.object(host,'start_background'), \
                 mock.patch.object(tunnel,'wait_profile'),contextlib.redirect_stdout(io.StringIO()) as output:
                tunnel.setup()
            saved=json.loads((root/'tunnel.json').read_text())
            self.assertEqual(saved['token_dpapi'],'opaque-dpapi');self.assertNotIn('provider-test-token',(root/'tunnel.json').read_text())
            self.assertEqual(Path(saved['ngrok_exe']),app/'bin/ngrok.exe');self.assertTrue(Path(saved['ngrok_exe']).is_file())
            self.assertTrue(save.call_args.args[0]['tunnel_enabled']);self.assertEqual(value['key_dpapi'],'existing-soloist-key')
            protect.assert_called_once_with('provider-test-token');self.assertNotIn('provider-test-token',output.getvalue())

    def test_windows_job_contains_only_owned_child_and_kills_on_handle_close(self):
        api=mock.Mock();api.CreateJobObjectW.return_value=777;api.SetInformationJobObject.return_value=1
        api.AssignProcessToJobObject.return_value=1;seen=[]
        def set_info(handle,kind,pointer,size):
            seen.append((handle,kind,size,ctypes.c_uint32.from_address(ctypes.cast(pointer,ctypes.c_void_p).value+16).value));return 1
        api.SetInformationJobObject.side_effect=set_info
        with mock.patch.object(windows_host,'_windows'),mock.patch.object(ctypes,'WinDLL',return_value=api,create=True):
            job=windows_host.OwnedProcessJob();job.assign(mock.Mock(_handle=321));job.close();job.close()
        self.assertEqual(seen,[(777,9,144,0x2000)])
        api.AssignProcessToJobObject.assert_called_once_with(777,321);api.CloseHandle.assert_called_once_with(777)

    def test_reserved_address_config_is_explicit_and_keeps_both_services_distinct(self):
        text=tunnel.config_text(45001,AUDIO,CONTROLS)
        self.assertIn('url: '+AUDIO,text);self.assertIn('url: '+CONTROLS,text)
        with self.assertRaises(ValueError):tunnel.config_text(45001,AUDIO,AUDIO)
        with self.assertRaises(ValueError):tunnel.config_text(45001,'https://not-a-tcp-endpoint',CONTROLS)
        with self.assertRaises(ValueError):tunnel.agent_endpoints(api_value(audio=AUDIO,controls=AUDIO))

    @unittest.skipIf(sys.platform=='win32','POSIX shebang fixture; production process job is checked separately')
    def test_real_agent_subprocess_local_api_export_and_owned_shutdown(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);agent=root/'fake-agent'
            agent.write_text('#!'+sys.executable+'\n'+(ROOT/'tests/fake_ngrok_agent.py').read_text());agent.chmod(0o700)
            (root/'tunnel.json').write_text(json.dumps({'format':1,'ngrok_exe':str(agent),'token_dpapi':'test-opaque'}))
            stop=threading.Event();received=[];errors=[]
            def observe():
                deadline=time.monotonic()+7
                while time.monotonic()<deadline and not stop.is_set():
                    path=root/'remote/remote-host.txt'
                    if path.exists():received.append(path.read_bytes());break
                    time.sleep(.02)
                stop.set()
            observer=threading.Thread(target=observe);observer.start()
            real_popen=subprocess.Popen
            try:
                with mock.patch.object(tunnel.windows_host,'unprotect_key',return_value='fixture-provider-token'), \
                     mock.patch.object(tunnel.subprocess,'Popen',wraps=real_popen) as launch, \
                     mock.patch.dict(os.environ,{'http_proxy':'http://127.0.0.1:9','NO_PROXY':''}), \
                     contextlib.redirect_stdout(io.StringIO()) as output:
                    tunnel.run(stop.is_set,root)
            finally:stop.set();observer.join(3)
            self.assertEqual(len(received),1)
            self.assertIn(b'audio_host=audio.example.test',received[0]);self.assertIn(b'control_port=25002',received[0])
            self.assertNotIn('fixture-provider-token',output.getvalue());self.assertIn('<redacted>',output.getvalue())
            self.assertFalse(json.loads((root/'tunnel-status.json').read_text())['running'])
            self.assertNotIn('fixture-provider-token',' '.join(launch.call_args.args[0]))
            self.assertNotIn('fixture-provider-token',(root/'ngrok-vita.yml').read_text())

    def test_agent_api_size_limit_and_redirect_rejection(self):
        response=mock.MagicMock();response.__enter__.return_value=response;response.read.return_value=b'x'*65537
        opener=mock.Mock();opener.open.return_value=response
        with mock.patch.object(tunnel,'build_opener',return_value=opener):
            with self.assertRaises(ValueError):tunnel.read_agent(45001)
        with self.assertRaises(OSError):tunnel.NoRedirect().redirect_request(None,None,None,None,None,None)

    def test_paired_audio_and_control_authentication_survive_opaque_tcp_relays(self):
        with pairing() as (registry,identity,path,key):
            for role in ('audio','control'):
                errors=[];payload=b'private song title and metadata '*40
                with secure_host.SecureListener('127.0.0.1',0,role,registry) as listener,TcpForward(listener.getsockname()) as relay:
                    def serve():
                        try:
                            channel,_=listener.accept()
                            with channel:channel.sendall(payload)
                        except BaseException as exc:errors.append(exc)
                    worker=threading.Thread(target=serve);worker.start()
                    with tls_client(('localhost',relay.address[1]),identity,key,role) as client:
                        received=bytearray()
                        while len(received)<len(payload):received.extend(client.recv(len(payload)-len(received)))
                        self.assertEqual(bytes(received),payload)
                    worker.join(3);self.assertFalse(errors,errors)
                    self.assertNotIn(payload[:40],relay.wire)

@unittest.skipUnless(os.environ.get('VITA_REMOTE_TEST_LIB'),'Native remote profile parser library optional')
class NativeProfileTests(unittest.TestCase):
    def test_pc_export_is_accepted_by_exact_receiver_parser(self):
        class Profile(ctypes.Structure):
            _fields_=[('audio_host',ctypes.c_char*254),('control_host',ctypes.c_char*254),
                      ('audio_port',ctypes.c_uint),('control_port',ctypes.c_uint)]
        lib=ctypes.CDLL(os.environ['VITA_REMOTE_TEST_LIB']);lib.remote_profile_parse.argtypes=[ctypes.c_char_p,ctypes.c_size_t,ctypes.POINTER(Profile)]
        data=tunnel.profile_bytes(AUDIO,CONTROLS);profile=Profile()
        for raw in (data,data.replace(b'\n',b'\r\n')):
            self.assertEqual(lib.remote_profile_parse(raw,len(raw),ctypes.byref(profile)),1)
            self.assertEqual((profile.audio_host,profile.audio_port,profile.control_host,profile.control_port),
                             (b'0.tcp.ngrok.io',12345,b'1.tcp.eu.ngrok.io',54321))
        for raw in (data+b'unknown=x\n',data+b'\nunknown=x\n',data+b'\0'):
            self.assertEqual(lib.remote_profile_parse(raw,len(raw),ctypes.byref(profile)),0)

if __name__=='__main__':unittest.main()
