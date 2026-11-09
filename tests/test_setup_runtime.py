import contextlib
import io
from pathlib import Path
import sys
import unittest
import tempfile
from unittest import mock

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'pc'))
import check_python
import host

class SetupRuntimeTests(unittest.TestCase):
    def test_source_checkout_without_built_payloads_gets_actionable_setup_error(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            for name in ('native_hashes.py','native/soloist-capture.exe','native/opus.dll'):
                with self.assertRaisesRegex(RuntimeError,'complete application ZIP'):check_python.validate_payloads(root)
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'fixture')
            check_python.validate_payloads(root)
    def test_python_preflight_rejects_wrong_abi_architecture_and_missing_tls(self):
        for target,value,message in (('size',4,'x64'),('machine','ARM64','x64'),('abi',1,'free-threaded'),('tls',False,'TLS-PSK')):
            with self.subTest(target=target),mock.patch.object(check_python.struct,'calcsize',return_value=4 if target=='size' else 8), \
                 mock.patch.object(check_python.platform,'machine',return_value=value if target=='machine' else 'AMD64'), \
                 mock.patch.object(check_python.sysconfig,'get_config_var',return_value=value if target=='abi' else 0), \
                 mock.patch.object(check_python.ssl,'HAS_PSK',value if target=='tls' else True):
                with self.assertRaisesRegex(RuntimeError,message):check_python.validate()
        with mock.patch.object(check_python.platform,'machine',return_value='AMD64'),mock.patch.object(check_python.sysconfig,'get_config_var',return_value=0):check_python.validate()

    def test_upgrade_preserves_saved_codec_bitrate_and_explicit_override_is_optional(self):
        for codec,bitrate,override in (('pcm',128,False),('opus',128,False),('pcm',128,True)):
            config={'key_dpapi':'protected','soloist_exe':'/outside/soloist.exe','audio_codec':codec,'opus_bitrate':bitrate,'gain':.5,'capture':{'saved':'route'},'funnel_enabled':True}
            with self.subTest(codec=codec,override=override),mock.patch.object(host,'load_config',return_value=config), \
                 mock.patch.object(host.windows,'unprotect_key'),mock.patch.object(host.windows,'pythonw_path'), \
                 mock.patch.object(host.windows,'startup_shortcut',return_value=Path('/nonexistent/shortcut')), \
                 mock.patch.object(host,'validate_audio') as validate,mock.patch.object(host,'stop_running'), \
                 mock.patch.object(host,'install_files',return_value=Path('/new/app')),mock.patch.object(host,'save_config') as save, \
                 mock.patch.object(host,'start_background'),contextlib.redirect_stdout(io.StringIO()):
                host.upgrade('opus',192) if override else host.upgrade()
                expected=('opus',192) if override else (codec,bitrate)
                validate.assert_called_once_with(*expected)
                self.assertEqual((save.call_args.args[0]['audio_codec'],save.call_args.args[0]['opus_bitrate']),expected)
                self.assertEqual(save.call_args.args[0]['capture'],{'saved':'route'});self.assertTrue(save.call_args.args[0]['funnel_enabled'])

if __name__=='__main__':unittest.main()
