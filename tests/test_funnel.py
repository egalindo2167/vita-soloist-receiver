import contextlib
import copy
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'pc'))
import funnel
import host
import remote_profile
import tunnel

NAME='desktop.example-tailnet.ts.net'
def state(port=443,session='owned',**handler):
    return {'Foreground':{session:{'TCP':{str(port):{'TCPForward':f'127.0.0.1:{funnel.PORTS[port]}',**handler}},
                                   'AllowFunnel':{f'{NAME}:{port}':True}}}}

class FunnelTests(unittest.TestCase):
    def test_exact_raw_tcp_routes_keep_320kbps_and_provider_opt_in(self):
        value={'app_dir':'/app','soloist_exe':'/app/soloist.exe','name':'Vita','gain':.5,'capture_blocksize':8192,
               'audio_codec':'opus','opus_bitrate':320}
        self.assertNotIn('Funnel',host.child_commands(value,'private'))
        value.update(funnel_enabled=True,tunnel_enabled=True)
        commands=host.child_commands(value,'private')
        self.assertEqual(commands['Funnel'],[sys.executable,str(Path('/app/funnel.py')),'--run'])
        self.assertNotIn('Tunnel',commands);self.assertIn('320',commands['Audio'])
        for port,local in funnel.PORTS.items():
            self.assertEqual(funnel.command('tailscale.exe',port),
                             ['tailscale.exe','funnel','--yes',f'--tcp={port}',f'tcp://127.0.0.1:{local}'])
    def test_status_validates_foreground_route_and_keeps_encryption(self):
        self.assertEqual(funnel.route_session(state(),NAME,443),'owned')
        for change in ('tls','proxy','https','http','target','public','duplicate','persistent','web','unknown'):
            value=state();block=value['Foreground']['owned'];handler=block['TCP']['443']
            if change=='tls':handler['TerminateTLS']=NAME
            if change=='proxy':handler['ProxyProtocol']=2
            if change=='https':handler['HTTPS']=True
            if change=='http':handler['HTTP']=True
            if change=='target':handler['TCPForward']='127.0.0.1:22'
            if change=='public':block['AllowFunnel'][f'{NAME}:443']=False
            if change=='duplicate':value['Foreground']['someone']=copy.deepcopy(block)
            if change=='persistent':value=block
            if change=='web':block['Web']={f'{NAME}:443':{'Handlers':{'/':{'Proxy':'http://127.0.0.1:22'}}}}
            if change=='unknown':handler['FutureMode']=True
            with self.subTest(change=change),self.assertRaises(RuntimeError):funnel.route_session(value,NAME,443)
    def test_conflicts_do_not_mutate_existing_configs_or_take_matching_routes(self):
        for value in (state(),{'TCP':{'443':{'HTTPS':True}}},
                      {'Web':{f'{NAME}:8443':{}}},{'AllowFunnel':{f'{NAME}:443':True}}):
            before=copy.deepcopy(value)
            with self.assertRaisesRegex(RuntimeError,'already reserved'):funnel.ensure_available(value)
            self.assertEqual(value,before)
        value={'TCP':{'10000':{'TCPForward':'127.0.0.1:9999'}}};funnel.ensure_available(value)
        funnel.ensure_available(state(),{443:'owned'})
        with self.assertRaises(RuntimeError):funnel.ensure_available(state(),{443:'not-owned'})
    def test_tailscale_login_and_hostname_are_checked_without_using_private_ips(self):
        for name in ('desktop.example-tailnet.ts.net.','DESKTOP.EXAMPLE-TAILNET.TS.NET'):
            with mock.patch.object(funnel,'cli',return_value=json.dumps({'BackendState':'Running','Self':{'DNSName':name}})):
                self.assertEqual(funnel.node_name('exe'),NAME)
        for value in ({'BackendState':'NeedsLogin'},{'BackendState':'Running','Self':{'DNSName':'100.64.1.2'}},
                      {'BackendState':'Running','Self':{'DNSName':'evil.ts.net.evil.org'}},
                      {'BackendState':'Running','Self':{'DNSName':'-bad.tailnet.ts.net'}}):
            with mock.patch.object(funnel,'cli',return_value=json.dumps(value)),self.assertRaises((RuntimeError,ValueError)):
                funnel.node_name('exe')
    def test_malformed_status_fails_closed_before_configuring_any_routes(self):
        for value in ({'Foreground':[]},{'Foreground':False},{'Foreground':{'x':{'Foreground':{'y':{}}}}},
                      {'TCP':[]},{'TCP':False},{'Web':'invalid'},{'AllowFunnel':['bad']},False,[]):
            with self.subTest(value=value),self.assertRaises(ValueError):funnel.ensure_available(value)
    def test_windows_job_tracks_only_two_cli_children_and_unwinds_an_assignment_failure(self):
        one=state();both=copy.deepcopy(one);both['Foreground'].update(state(8443,'owned-2')['Foreground'])
        for failed in (False,True):
            processes=[mock.Mock(stdout=io.StringIO('ready\n')),mock.Mock(stdout=io.StringIO('ready\n'))]
            for process in processes:process.poll.return_value=None
            with self.subTest(failed=failed),mock.patch.object(funnel.sys,'platform','win32'), \
                 mock.patch.object(funnel.subprocess,'CREATE_NEW_PROCESS_GROUP',0x200,create=True), \
                 mock.patch.object(funnel.subprocess,'CREATE_NO_WINDOW',0x08000000,create=True), \
                 mock.patch.object(funnel.windows_host,'OwnedProcessJob') as job, \
                 mock.patch.object(funnel,'configuration',side_effect=[{},{},one,one,both,both]), \
                 mock.patch.object(funnel.subprocess,'Popen',side_effect=processes) as launch, \
                 mock.patch.object(funnel,'stop_process') as cleanup, \
                 mock.patch.dict(os.environ,{'SOLOIST_API_KEY':'private','NGROK_AUTHTOKEN':'private'}), \
                 contextlib.redirect_stdout(io.StringIO()):
                if failed:job.return_value.assign.side_effect=[None,RuntimeError('job failed')]
                def exercise():
                    with funnel.Routes('tailscale.exe',NAME) as routes:routes.start()
                if failed:
                    with self.assertRaisesRegex(RuntimeError,'job failed'):exercise()
                else:exercise()
                self.assertEqual(job.return_value.assign.call_args_list,[mock.call(processes[0]),mock.call(processes[1])])
                self.assertEqual(cleanup.call_args_list,[mock.call(processes[0]),mock.call(processes[1])])
                job.return_value.close.assert_called_once()
                for call in launch.call_args_list:
                    self.assertNotIn('SOLOIST_API_KEY',call.kwargs['env']);self.assertNotIn('NGROK_AUTHTOKEN',call.kwargs['env'])
                    self.assertIn('tailscale.exe',call.args[0]);self.assertNotIn('--bg',call.args[0])
    def test_official_tailscale_cli_supports_the_generated_flags(self):
        executable=os.environ.get('VITA_TAILSCALE_TEST_CLI')
        if not executable:self.skipTest('Optional installed official Tailscale CLI')
        funnel.check_cli(executable)
    def test_setup_saves_no_api_token_and_preserves_bitrate_login_favorites_and_pairing(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);app=root/'app';app.mkdir();(app/'funnel.py').touch();exe=root/'tailscale.exe';exe.touch()
            value={'app_dir':str(app),'key_dpapi':'existing-key','audio_codec':'opus','opus_bitrate':320,
                   'capture_blocksize':8192,'tunnel_enabled':True};before=copy.deepcopy(value)
            with mock.patch.object(funnel.sys,'platform','win32'),mock.patch.object(funnel,'root_path',return_value=root), \
                 mock.patch.object(funnel,'find_cli',return_value=exe),mock.patch.object(funnel,'check_cli'), \
                 mock.patch.object(funnel,'node_name',return_value=NAME),mock.patch.object(funnel,'Routes') as routes, \
                 mock.patch.object(host,'load_config',return_value=value),mock.patch.object(host,'save_config') as save, \
                 mock.patch.object(host,'stop_running'),mock.patch.object(host,'start_background') as start, \
                 mock.patch.object(funnel,'wait_profile'),contextlib.redirect_stdout(io.StringIO()):
                funnel.setup()
            routes.return_value.__enter__.return_value.start.assert_called_once_with(timeout=600)
            self.assertEqual(json.loads((root/'funnel.json').read_text()),{'format':1,'tailscale_exe':str(exe)})
            self.assertEqual(value,{**before,'funnel_enabled':True,'tunnel_enabled':False})
            self.assertEqual(save.call_args.args[0],value);start.assert_called_once()
            profile=(root/'remote/remote-host.txt').read_text()
            self.assertIn('audio_host='+NAME,profile);self.assertIn('audio_port=443',profile);self.assertIn('control_port=8443',profile)
            self.assertNotIn('existing-key',profile)
    def test_provider_switches_are_exclusive_and_disabling_inactive_provider_keeps_selected_one(self):
        for module,old,new in ((funnel,'tunnel_enabled','funnel_enabled'),(tunnel,'funnel_enabled','tunnel_enabled')):
            value={old:True,new:False,'opus_bitrate':320,'key_dpapi':'existing'}
            with mock.patch.object(host,'load_config',return_value=value),mock.patch.object(host,'save_config'), \
                 mock.patch.object(host,'stop_running') as stop,mock.patch.object(host,'start_background'), \
                 mock.patch.object(module,'load_settings'),mock.patch.object(module,'wait_profile'),contextlib.redirect_stdout(io.StringIO()):
                module.enable(True);self.assertTrue(value[new]);self.assertFalse(value[old]);stop.assert_called_once()
                stop.reset_mock();other=tunnel if module is funnel else funnel
                other.enable(False);self.assertTrue(value[new]);stop.assert_not_called()
                self.assertEqual(value['opus_bitrate'],320);self.assertEqual(value['key_dpapi'],'existing')
    def test_generic_profile_export_selects_only_active_provider(self):
        with mock.patch.object(host,'load_config',return_value={'funnel_enabled':True}), \
             mock.patch.object(funnel,'show_profile',return_value=True) as show,mock.patch.object(tunnel,'show_profile') as wrong:
            self.assertEqual(remote_profile.main(),0);show.assert_called_once_with(True);wrong.assert_not_called()
    def test_failed_setup_cleans_up_and_restarts_previous_local_host_without_enabling_funnel(self):
        value={'app_dir':'/app','opus_bitrate':320};before=copy.deepcopy(value)
        with mock.patch.object(funnel.sys,'platform','win32'),mock.patch.object(Path,'is_file',return_value=True), \
             mock.patch.object(funnel,'find_cli',return_value=Path('/tailscale.exe')),mock.patch.object(funnel,'check_cli'), \
             mock.patch.object(funnel,'node_name',return_value=NAME),mock.patch.object(funnel,'Routes') as routes, \
             mock.patch.object(host,'load_config',return_value=value),mock.patch.object(host,'save_config') as save, \
             mock.patch.object(host,'stop_running'),mock.patch.object(host,'start_background') as start, \
             contextlib.redirect_stdout(io.StringIO()):
            routes.return_value.__enter__.return_value.start.side_effect=RuntimeError('port conflict')
            with self.assertRaisesRegex(RuntimeError,'port conflict'):funnel.setup()
            routes.return_value.__exit__.assert_called_once();start.assert_called_once();save.assert_not_called()
            self.assertEqual(value,before)
    @contextlib.contextmanager
    def fixture(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);exe=root/'tailscale'
            exe.write_text('#!'+sys.executable+'\n'+(ROOT/'tests/fake_tailscale.py').read_text().partition('\n')[2]);exe.chmod(0o755)
            unrelated={'TCP':{'10000':{'TCPForward':'127.0.0.1:9999'}}}
            (root/'state.json').write_text(json.dumps(unrelated))
            with mock.patch.dict(os.environ,{'VITA_TEST_FUNNEL_ROOT':str(root)}):yield root,exe,unrelated
    @unittest.skipIf(sys.platform=='win32','POSIX CLI subprocess fixture; Windows process APIs have separate mock checks')
    def test_real_cli_subprocesses_export_stable_profile_and_remove_only_owned_sessions(self):
        with self.fixture() as (root,exe,unrelated),contextlib.redirect_stdout(io.StringIO()):
            stop=threading.Event()
            funnel.secure_host.atomic_write(root/'funnel.json',json.dumps({'format':1,'tailscale_exe':str(exe)}).encode())
            errors=[]
            def run():
                try:funnel.run(stop.is_set,root)
                except BaseException as exc:errors.append(exc)
            thread=threading.Thread(target=run);thread.start();deadline=time.monotonic()+10;ready=False
            try:
                while time.monotonic()<deadline:
                    try:ready=json.loads((root/'funnel-status.json').read_text()).get('running',False)
                    except FileNotFoundError:pass
                    if ready:break
                    time.sleep(.05)
                self.assertTrue(ready,errors)
                self.assertEqual((root/'remote/remote-host.txt').read_bytes(),tunnel.profile_bytes(*funnel.endpoints(NAME)))
                value=funnel.configuration(exe);self.assertEqual(len(value['Foreground']),2)
                self.assertEqual(value['TCP'],unrelated['TCP'])
            finally:stop.set();thread.join(10)
            self.assertFalse(thread.is_alive());self.assertFalse(errors,errors)
            self.assertEqual(funnel.configuration(exe),unrelated)
            self.assertFalse(json.loads((root/'funnel-status.json').read_text())['running'])
    @unittest.skipIf(sys.platform=='win32','POSIX CLI subprocess fixture')
    def test_partial_start_failure_removes_owned_route_and_keeps_unrelated_configuration(self):
        with self.fixture() as (root,exe,unrelated),contextlib.redirect_stdout(io.StringIO()):
            original=funnel.command
            def command(executable,port):
                return [str(exe),'invalid'] if port==8443 else original(executable,port)
            with mock.patch.object(funnel,'command',side_effect=command):
                with self.assertRaisesRegex(RuntimeError,'exited'):
                    with funnel.Routes(exe,NAME) as routes:routes.start(timeout=2)
            self.assertEqual(funnel.configuration(exe),unrelated)

if __name__=='__main__':unittest.main()
