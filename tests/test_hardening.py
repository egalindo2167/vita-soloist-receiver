import contextlib
import hashlib
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import io
import os
from pathlib import Path
import socket
import sys
import threading
import time
import unittest
from unittest import mock
from urllib.request import build_opener,ProxyHandler
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'pc'))
import host
import opus_audio
import secure_host as security
import soloist_bridge as bridge
from security_support import pairing,tls_client
from tunnel_support import TcpForward

class HardeningTests(unittest.TestCase):
    def test_sni_relay_junk_handshakes_do_not_exhaust_a_shared_ip_bucket(self):
        with pairing() as (registry,identity,path,key),security.SecureListener('127.0.0.1',0,'audio',registry) as listener:
            stop=threading.Event();accepted=[]
            def serve():
                while not stop.is_set():
                    try:
                        sock,_=listener.accept()
                        with sock:sock.sendall(b'ok');accepted.append(sock.identity)
                    except OSError:continue
            thread=threading.Thread(target=serve);thread.start()
            try:
                with TcpForward(listener.getsockname(),expected_sni='desktop.example.ts.net') as relay:
                    # Unlike a silent TCP connect, these ClientHellos actually
                    # satisfy a Funnel-style SNI ingress before PSK rejection.
                    for _ in range(16):
                        with self.assertRaises(OSError):
                            tls_client(relay.address,identity,b'x'*32,private=True,server_hostname='desktop.example.ts.net')
                    self.assertTrue(path.exists()) # failed proof cannot delete an export
                    with tls_client(relay.address,identity,key,private=True,server_hostname='desktop.example.ts.net') as client:
                        self.assertEqual(client.recv(2),b'ok')
                    self.assertEqual(len(relay.sni),17)
            finally:stop.set();thread.join(2)
            self.assertFalse(thread.is_alive());self.assertEqual(accepted,[identity])
    def test_slow_anonymous_loopback_peers_cannot_serially_block_a_paired_reconnect(self):
        with pairing() as (registry,identity,path,key),security.SecureListener('127.0.0.1',0,'audio',registry) as listener:
            stop=threading.Event();accepted=threading.Event();errors=[];peaks=[0,0]
            def serve():
                while not stop.is_set():
                    try:
                        with listener.lock:
                            peaks[0]=max(peaks[0],len(listener.workers));peaks[1]=max(peaks[1],len(listener.waiting))
                        sock,_=listener.accept()
                        with sock:sock.sendall(b'legitimate');accepted.set()
                    except socket.timeout:continue
                    except OSError as exc:
                        if not stop.is_set():errors.append(exc)
            thread=threading.Thread(target=serve);thread.start();slow=[]
            try:
                # Every connection appears as the same loopback relay source.
                for _ in range(12):slow.append(socket.create_connection(listener.getsockname()))
                time.sleep(.08);start=time.monotonic()
                with tls_client(listener.getsockname(),identity,key,private=True) as client:
                    self.assertEqual(client.recv(16),b'legitimate')
                self.assertLess(time.monotonic()-start,1.5);self.assertTrue(accepted.is_set())
                self.assertLessEqual(peaks[0],8);self.assertLessEqual(peaks[1],4)
            finally:
                stop.set()
                for sock in slow:sock.close()
                thread.join(2)
            self.assertFalse(thread.is_alive());self.assertFalse(errors,errors)
    def test_rotating_tls_and_discovery_aliases_are_bound_to_the_pairing_key_and_purpose(self):
        with pairing() as (registry,identity,path,key):
            aliases=[security.tls_identity(key) for _ in range(3)]
            self.assertEqual(len(set(aliases)),3)
            for alias in aliases:
                self.assertNotIn(identity,alias);self.assertEqual(registry.resolve(alias),(identity,key))
            self.assertIsNone(registry.resolve(aliases[0][:-1]+('1' if aliases[0][-1]!='1' else '2')))
            queries=[security.discovery_query(identity,key,bytes([i])*16,private=True) for i in (1,2)]
            self.assertNotEqual(queries[0][4:20],queries[1][4:20])
            for query in queries:
                self.assertEqual(query[:4],b'VAD2');self.assertNotIn(bytes.fromhex(identity),query)
                self.assertEqual(security.discovery_reply(query,registry)[:4],b'VAH2')
            self.assertNotEqual(security.identity_alias(key,b'tls',b'x'*16),security.identity_alias(key,b'discovery',b'x'*16))
            registry.revoke(identity);self.assertIsNone(registry.resolve(aliases[0]))
    def test_authenticated_pair_export_cleanup_never_deletes_another_device_export(self):
        with pairing() as (registry,identity,path,key):
            second,second_path=registry.pair('second');second_bytes=second_path.read_bytes()
            self.assertTrue(registry.clear_export(identity,key));self.assertEqual(second_path.read_bytes(),second_bytes)
            self.assertFalse(registry.clear_export(second,b'x'*32));self.assertTrue(second_path.exists())
            self.assertTrue(registry.clear_export(second,registry.lookup(second)));self.assertFalse(second_path.exists())
    def test_first_successful_tls_connection_deletes_only_matching_export(self):
        with pairing() as (registry,identity,path,key),security.SecureListener('127.0.0.1',0,'audio',registry) as listener:
            accepted=[]
            def accept():
                sock,_=listener.accept()
                with sock:accepted.append(sock.identity)
            thread=threading.Thread(target=accept);thread.start()
            with tls_client(listener.getsockname(),identity,key,private=True):pass
            thread.join(2);self.assertEqual(accepted,[identity]);self.assertFalse(path.exists())
    def test_export_delete_failure_is_reported_without_denying_an_authenticated_device(self):
        with pairing() as (registry,identity,path,key):
            with mock.patch.object(Path,'unlink',side_effect=PermissionError('locked')),contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertFalse(registry.clear_export(identity,key));self.assertFalse(registry.clear_export(identity,key))
            self.assertTrue(path.exists());self.assertEqual(output.getvalue().count('delete the exported PC copy manually'),1)
            self.assertEqual(registry.lookup(identity),key)
    def test_windows_listeners_use_exclusive_bind_instead_of_reuseaddr(self):
        sock=mock.Mock()
        with mock.patch.object(security.sys,'platform','win32'),mock.patch.object(security.socket,'SO_EXCLUSIVEADDRUSE',0xFFFF,create=True), \
             mock.patch.object(security.socket,'socket',return_value=sock):
            with security.SecureListener('127.0.0.1',0,'audio'):pass
        sock.setsockopt.assert_called_once_with(socket.SOL_SOCKET,0xFFFF,1)
    def test_remote_provider_defaults_to_loopback_but_lan_requires_explicit_scope(self):
        value={'app_dir':'/app','soloist_exe':'soloist.exe','name':'Vita','gain':.5,'capture_blocksize':8192,'funnel_enabled':True}
        self.assertEqual(host.listener_bind(value),'127.0.0.1')
        for scope,wanted in [('auto','127.0.0.1'),('remote','127.0.0.1'),('both','0.0.0.0')]:
            commands=host.child_commands({**value,'listen_scope':scope},'secret')
            for name in ('Audio','Controls'):
                at=commands[name].index('--bind');self.assertEqual(commands[name][at+1],wanted)
        self.assertEqual(host.listener_bind({}),'0.0.0.0')
        with self.assertRaises(ValueError):host.listener_bind({'listen_scope':'invalid'})
    def test_real_http_redirect_is_rejected_before_contacting_the_target(self):
        paths=[]
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_GET(self):
                paths.append(self.path);self.send_response(302)
                self.send_header('Location',f'http://127.0.0.1:{self.server.server_port}/secret');self.end_headers()
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever);thread.start()
        try:
            opener=build_opener(ProxyHandler({}),bridge.NoArtRedirect())
            with self.assertRaisesRegex(ValueError,'redirects'):
                opener.open(f'http://127.0.0.1:{server.server_port}/image',timeout=2)
            self.assertEqual(paths,['/image'])
        finally:server.shutdown();server.server_close();thread.join(2)
    def test_artwork_disallows_userinfo_ports_and_non_spotify_hosts_before_any_request(self):
        for url in ('https://i.scdn.co.evil.test/x','https://user:secret@i.scdn.co/x',
                    'https://i.scdn.co:8443/x','http://i.scdn.co/x','https://127.0.0.1/x'):
            with mock.patch.object(bridge,'build_opener') as opener,self.assertRaises(ValueError):bridge.download_art(url)
            opener.assert_not_called()
    def test_bundled_opus_has_expected_hash_and_tampering_is_rejected_before_loading(self):
        path=ROOT/'pc/native/opus.dll';raw=path.read_bytes()
        self.assertEqual(raw[:2],b'MZ');self.assertEqual(hashlib.sha256(raw).hexdigest(),opus_audio.OPUS_DLL_SHA256)
        with mock.patch.object(opus_audio.sys,'platform','win32'),mock.patch.object(Path,'read_bytes',return_value=b'tampered'), \
             mock.patch.object(opus_audio.ctypes,'CDLL') as load:
            with self.assertRaisesRegex(RuntimeError,'integrity'):opus_audio.library()
            load.assert_not_called()

if __name__=='__main__':unittest.main()
