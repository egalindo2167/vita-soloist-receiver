"""Retry real temporary HTTP failures without accepting unverified build inputs."""
import contextlib
import hashlib
from http.server import BaseHTTPRequestHandler,HTTPServer
import importlib.util
import io
from pathlib import Path
import ssl
import tarfile
import tempfile
import threading
import unittest
from unittest import mock
from urllib.error import HTTPError,URLError

spec=importlib.util.spec_from_file_location('fetch_build_sources',Path(__file__).resolve().parents[1]/'tools/fetch_build_sources.py')
fetcher=importlib.util.module_from_spec(spec);spec.loader.exec_module(fetcher)

class BuildSourceTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.root=Path(temporary.name)
        out=io.BytesIO();text=b'original verified source\n'
        with tarfile.open(fileobj=out,mode='w:gz') as tar:
            info=tarfile.TarInfo('fixture-1/CMakeLists.txt');info.size=len(text);tar.addfile(info,io.BytesIO(text))
        self.payload=out.getvalue();self.checksum=hashlib.sha256(self.payload).hexdigest()
        self.url='https://upstream.example.test/fixture.tar.gz'
        patch=mock.patch.dict(fetcher.SOURCES,{'fixture':(self.url,self.checksum,'fixture-1')})
        patch.start();self.addCleanup(patch.stop)

    def error(self,code):return HTTPError(self.url,code,'fixture',{},io.BytesIO(b'upstream error'))

    def assert_clean(self):
        self.assertFalse(list(self.root.glob('*.part')))
        self.assertFalse(any(p.name.startswith('.fixture-1-') for p in self.root.iterdir()))

    def test_temporary_504_retries_and_stdout_remains_only_for_cli_path(self):
        output=io.StringIO();errors=io.StringIO()
        with mock.patch.object(fetcher,'urlopen',side_effect=[self.error(504),io.BytesIO(self.payload)]) as network, \
             mock.patch.object(fetcher.time,'sleep') as sleep,contextlib.redirect_stdout(output),contextlib.redirect_stderr(errors):
            result=fetcher.fetch('fixture',self.root)
        self.assertTrue((result/'CMakeLists.txt').is_file());self.assertEqual(network.call_count,2)
        sleep.assert_called_once_with(2);self.assertEqual(output.getvalue(),'');self.assertIn('HTTP 504',errors.getvalue())
        self.assertEqual((self.root/'fixture.tar.gz').read_bytes(),self.payload);self.assert_clean()

    def test_interrupted_read_restarts_without_publishing_partial_cache(self):
        broken=mock.MagicMock();broken.__enter__.return_value=broken
        broken.read.side_effect=[b'partial',TimeoutError('read timed out')]
        def success(*args,**kwargs):
            self.assertFalse((self.root/'fixture.tar.gz').exists())
            return io.BytesIO(self.payload)
        with mock.patch.object(fetcher,'urlopen',side_effect=[broken]) as network, \
             mock.patch.object(fetcher.time,'sleep'),contextlib.redirect_stderr(io.StringIO()):
            calls=[0]
            def open_source(*args,**kwargs):
                calls[0]+=1
                return broken if calls[0]==1 else success()
            network.side_effect=open_source
            fetcher.fetch('fixture',self.root)
        self.assertEqual(calls[0],2);self.assertEqual((self.root/'fixture.tar.gz').read_bytes(),self.payload);self.assert_clean()

    def test_retries_stop_at_four_and_remove_temporary_files(self):
        with mock.patch.object(fetcher,'urlopen',side_effect=[self.error(504) for _ in range(4)]) as network, \
             mock.patch.object(fetcher.time,'sleep') as sleep,contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(HTTPError):fetcher.fetch('fixture',self.root)
        self.assertEqual(network.call_count,4);self.assertEqual(sleep.call_args_list,[mock.call(2),mock.call(4),mock.call(8)])
        self.assertEqual(list(self.root.iterdir()),[])

    def test_bad_content_never_retries_or_extracts_and_bad_cache_can_be_replaced(self):
        with mock.patch.object(fetcher,'urlopen',return_value=io.BytesIO(b'wrong bytes')) as network, \
             mock.patch.object(fetcher.time,'sleep') as sleep,mock.patch.object(fetcher.tarfile,'open') as extract:
            with self.assertRaisesRegex(RuntimeError,'checksum failed'):fetcher.fetch('fixture',self.root)
        network.assert_called_once();sleep.assert_not_called();extract.assert_not_called();self.assertEqual(list(self.root.iterdir()),[])
        (self.root/'fixture.tar.gz').write_bytes(b'old incomplete cache')
        with mock.patch.object(fetcher,'urlopen',return_value=io.BytesIO(self.payload)) as network,contextlib.redirect_stderr(io.StringIO()):
            fetcher.fetch('fixture',self.root)
        network.assert_called_once()
        with mock.patch.object(fetcher,'urlopen') as network:fetcher.fetch('fixture',self.root)
        network.assert_not_called();self.assert_clean()

    def test_permanent_http_and_certificate_errors_do_not_retry(self):
        for error in (self.error(404),URLError(ssl.SSLCertVerificationError('untrusted certificate'))):
            with self.subTest(error=type(error).__name__),mock.patch.object(fetcher,'urlopen',side_effect=error) as network, \
                 mock.patch.object(fetcher.time,'sleep') as sleep:
                with self.assertRaises(type(error)):fetcher.fetch('fixture',self.root)
            network.assert_called_once();sleep.assert_not_called();self.assertEqual(list(self.root.iterdir()),[])

    def test_official_api_fallback_keeps_binary_accept_header_and_same_hash(self):
        alternate='https://api.github.com/repos/example/source/releases/assets/1'
        with mock.patch.dict(fetcher.FALLBACKS,{'fixture':(alternate,)}), \
             mock.patch.object(fetcher,'urlopen',side_effect=[self.error(504),io.BytesIO(self.payload)]) as network, \
             mock.patch.object(fetcher.time,'sleep'),contextlib.redirect_stderr(io.StringIO()):
            fetcher.fetch('fixture',self.root)
        request=network.call_args.args[0]
        self.assertEqual(request.full_url,alternate);self.assertEqual(request.get_header('Accept'),'application/octet-stream')
        self.assertIsNone(request.get_header('Authorization'))
        self.assertEqual((self.root/'fixture.tar.gz').read_bytes(),self.payload)
        cmake=(Path(__file__).resolve().parents[1]/'CMakeLists.txt').read_text()
        self.assertIn(fetcher.FALLBACKS['mbedtls'][0],cmake)
        self.assertIn('SHA256='+fetcher.SOURCES['mbedtls'][1],cmake)

    def test_interrupted_extraction_cannot_become_cached_source(self):
        def interrupted(destination,filter):
            (Path(destination)/'fixture-1').mkdir();raise OSError('interrupted extraction')
        fake=mock.MagicMock();fake.__enter__.return_value=fake;fake.extractall.side_effect=interrupted
        with mock.patch.object(fetcher,'urlopen',return_value=io.BytesIO(self.payload)),mock.patch.object(fetcher.tarfile,'open',return_value=fake):
            with self.assertRaisesRegex(OSError,'interrupted extraction'):fetcher.fetch('fixture',self.root)
        self.assertFalse((self.root/'fixture-1').exists());self.assert_clean()
        with mock.patch.object(fetcher,'urlopen') as network:result=fetcher.fetch('fixture',self.root)
        network.assert_not_called();self.assertTrue((result/'CMakeLists.txt').is_file());self.assert_clean()

    def test_real_http_504_then_verified_archive(self):
        payload=self.payload;requests=[]
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_GET(self):
                requests.append(self.path);body=b'temporary gateway failure' if len(requests)==1 else payload
                self.send_response(504 if len(requests)==1 else 200)
                self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
        server=HTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            url=f'http://127.0.0.1:{server.server_port}/fixture.tar.gz'
            with mock.patch.dict(fetcher.SOURCES,{'fixture':(url,self.checksum,'fixture-1')}), \
                 mock.patch.object(fetcher.time,'sleep') as sleep,contextlib.redirect_stderr(io.StringIO()):
                result=fetcher.fetch('fixture',self.root)
            self.assertEqual(len(requests),2);sleep.assert_called_once_with(2)
            self.assertTrue((result/'CMakeLists.txt').is_file());self.assert_clean()
        finally:server.shutdown();server.server_close();thread.join(2)
        self.assertFalse(thread.is_alive())

if __name__=='__main__':unittest.main()
