import ctypes
import hashlib
import hmac
import json
import os
from pathlib import Path
import socket
import ssl
import struct
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'pc'))
import secure_host as security
from security_support import pairing,tls_client
from tunnel_support import TcpForward

class SecurityTests(unittest.TestCase):
    def exchange(self,registry,client,role='audio',action=None):
        errors=[];accepted=[]
        with security.SecureListener('127.0.0.1',0,role,registry) as listener:
            def serve():
                try:
                    sock,_=listener.accept()
                    with sock:
                        accepted.append(sock.version())
                        if action:action(sock)
                except BaseException as exc:errors.append(exc)
            thread=threading.Thread(target=serve);thread.start()
            try:client(listener.getsockname())
            finally:thread.join(4)
            self.assertFalse(thread.is_alive())
        return accepted,errors

    def test_tls13_mutual_pair_authentication_for_audio_and_controls(self):
        with pairing() as (r,identity,path,key):
            for role in ('audio','control'):
                def client(address):
                    with tls_client(address,identity,key,role) as sock:
                        self.assertEqual(sock.version(),'TLSv1.3');self.assertTrue(sock.session_reused)
                        self.assertEqual(sock.recv(12),b'private data')
                accepted,errors=self.exchange(r,client,role,lambda c:c.sendall(b'private data'))
                self.assertEqual(accepted,['TLSv1.3']);self.assertEqual(errors,[])

    def test_unknown_wrong_and_revoked_keys_and_wrong_role_are_denied(self):
        with pairing() as (r,identity,path,key):
            for who,secret,role in [('f'*32,key,'audio'),(identity,b'x'*32,'audio'),(identity,key,'control')]:
                def client(address):
                    with self.assertRaises(OSError):tls_client(address,who,secret,role)
                accepted,errors=self.exchange(r,client)
                self.assertEqual(accepted,[]);self.assertTrue(errors)
            r.revoke(identity)
            accepted,errors=self.exchange(r,lambda a:self.denied(a,identity,key))
            self.assertFalse(accepted);self.assertTrue(errors)
    def denied(self,address,identity,key):
        with self.assertRaises(OSError):tls_client(address,identity,key)

    def test_no_plaintext_or_tls12_downgrade_and_slow_handshake_times_out(self):
        with pairing() as (r,identity,path,key):
            def plaintext(address):
                with socket.create_connection(address,timeout=4) as sock:
                    sock.sendall(b'VRX2'+b'\0'*100)
                    try:self.assertEqual(sock.recv(8),b'')
                    except ConnectionResetError:pass
            self.assertFalse(self.exchange(r,plaintext)[0])
            context=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT);context.check_hostname=False;context.verify_mode=ssl.CERT_NONE
            context.maximum_version=ssl.TLSVersion.TLSv1_2
            self.assertFalse(self.exchange(r,lambda a:self.legacy_denied(a,identity,key,context))[0])
            def silent(address):
                with socket.create_connection(address,timeout=4) as sock:self.assertEqual(sock.recv(8),b'')
            started=time.monotonic();accepted,errors=self.exchange(r,silent)
            self.assertFalse(accepted);self.assertTrue(errors);self.assertLess(time.monotonic()-started,3.8)
    def legacy_denied(self,address,identity,key,context):
        with self.assertRaises(OSError):tls_client(address,identity,key,context=context)

    def test_revocation_disconnects_existing_authenticated_sessions(self):
        with pairing() as (r,identity,path,key):
            for role in ('audio','control'):
                accepted=threading.Event();revoked=threading.Event();errors=[]
                # A new device per channel keeps this test independent.
                identity,path=r.pair(role);key=r.lookup(identity)
                def action(sock):
                    accepted.set();revoked.wait(2)
                    self.assertFalse(sock.authorized())
                    with self.assertRaisesRegex(security.SecurityError,'revoked'):sock.sendall(b'forbidden')
                def client(address):
                    with tls_client(address,identity,key,role) as sock:
                        self.assertTrue(accepted.wait(2));self.assertTrue(r.revoke(identity));revoked.set()
                        self.assertEqual(sock.recv(16),b'')
                result,errors=self.exchange(r,client,role,action)
                self.assertTrue(result);self.assertEqual(errors,[])

    def test_registry_protection_export_bounds_and_corruption_fail_closed(self):
        with pairing() as (r,identity,path,key):
            self.assertEqual(path.read_bytes(),security.MAGIC+bytes.fromhex(identity)+key)
            self.assertNotIn(key.hex(),r.path.read_text())
            self.assertEqual(r.list(),[{'id':identity,'name':'Test Vita'}])
            for i in range(15):r.pair('Vita '+str(i))
            with self.assertRaises(security.SecurityError):r.pair()
            self.assertTrue(r.revoke(identity));self.assertIsNone(r.lookup(identity))
            r.path.write_text('{invalid JSON')
            with self.assertRaises(security.SecurityError):r.list()
            self.assertIsNone(r.lookup(identity))

    def test_other_process_registry_changes_revoke_cached_sessions(self):
        with pairing() as (r,identity,path,key):
            reader=security.Registry(r.root,protect=r.protect,unprotect=r.unprotect)
            self.assertEqual(reader.lookup(identity),key)
            r.revoke(identity);time.sleep(.27)
            self.assertIsNone(reader.lookup(identity))

    def test_discovery_rejects_unknown_forged_and_legacy_requests(self):
        with pairing() as (r,identity,path,key):
            request=security.discovery_query(identity,key,b'n'*16)
            response=security.discovery_reply(request,r,'Windows-PC')
            self.assertEqual(len(request),68);self.assertEqual(len(response),104)
            self.assertEqual(response[:36],b'VAH1'+request[4:36])
            self.assertEqual(struct.unpack_from('<HH',response,36),(48152,48153))
            self.assertTrue(hmac.compare_digest(response[72:],hmac.digest(security.discovery_key(key),response[:72],'sha256')))
            for bad in [b'VITA_AUDIO_DISCOVER 1',request[:-1],request[:35]+b'x'+request[36:],security.discovery_query('f'*32,key,b'n'*16)]:
                self.assertIsNone(security.discovery_reply(bad,r))
            r.revoke(identity);self.assertIsNone(security.discovery_reply(request,r))

    def test_connection_rate_limit_has_bounded_memory_and_old_python_fails_closed(self):
        gate=security.RateGate()
        with mock.patch.object(security.time,'monotonic',return_value=gate.updated):
            self.assertEqual(sum(gate.allow('same') for i in range(50)),8)
            for i in range(1000):gate.allow(str(i))
            self.assertLessEqual(len(gate.peers),128)
        with mock.patch.object(security.ssl,'HAS_PSK',False):
            with self.assertRaisesRegex(RuntimeError,'3.13'):security.SecureListener('127.0.0.1',0,'audio')
            import host
            with mock.patch.object(host,'load_config') as load:
                with self.assertRaisesRegex(RuntimeError,'3.13'):host.set_audio('pcm',320)
                load.assert_not_called()

@unittest.skipUnless(os.environ.get('VITA_TLS_TEST_LIB'),'Set VITA_TLS_TEST_LIB to the native build of src/secure_net.c')
class NativeVitaTlsTests(unittest.TestCase):
    def setUp(self):
        self.lib=ctypes.CDLL(os.environ['VITA_TLS_TEST_LIB'])
        self.addCleanup(self.lib.secure_net_stop)
    def test_real_vita_tls_client_receives_records_and_reconnects_on_both_channels(self):
        self.native_exchange(False)
    def test_real_vita_tls_client_through_opaque_tcp_tunnels(self):
        self.native_exchange(True)
    def test_real_vita_tls_client_supplies_sni_through_funnel_style_ingress_on_both_channels(self):
        self.native_exchange(True,'desktop.example-tailnet.ts.net')
    def native_exchange(self,remote,hostname=None):
        with pairing() as (r,identity,path,key):
            self.assertEqual(self.lib.secure_net_start(str(path).encode()),0)
            for channel in (0,1,0):
                errors=[];data=b'private audio or metadata'*1000
                with security.SecureListener('127.0.0.1',0,'control' if channel else 'audio',r) as listener:
                    def serve():
                        try:
                            sock,_=listener.accept()
                            with sock:
                                # Multiple TLS records must remain in order.
                                for at in range(0,len(data),802):sock.sendall(data[at:at+802])
                        except Exception as e:errors.append(e)
                    thread=threading.Thread(target=serve);thread.start()
                    relay=TcpForward(listener.getsockname(),expected_sni=hostname) if remote else None
                    if relay:self.addCleanup(relay.close)
                    sock=socket.create_connection(relay.address if relay else listener.getsockname());sock.setblocking(False);fd=sock.detach()
                    if hostname:
                        self.assertEqual(self.lib.secure_net_handshake_host(fd,channel,hostname.encode(),None),0)
                    else:self.assertEqual(self.lib.secure_net_handshake(fd,channel,None),0)
                    result=bytearray();buffer=ctypes.create_string_buffer(8192);deadline=time.monotonic()+3
                    while time.monotonic()<deadline:
                        n=self.lib.secure_net_read(fd,buffer,len(buffer))
                        if n>0:result.extend(buffer.raw[:n])
                        elif n==-2:time.sleep(.002)
                        else:break
                    self.lib.secure_net_close(fd);thread.join(3)
                    self.assertFalse(errors,errors);self.assertEqual(bytes(result),data)
                    if hostname:
                        self.assertEqual(relay.sni,[hostname]);self.assertNotIn(data[:100],relay.wire)
    def test_funnel_style_ingress_refuses_old_client_without_sni(self):
        with pairing() as (r,identity,path,key):
            self.assertEqual(self.lib.secure_net_start(str(path).encode()),0)
            with TcpForward(('127.0.0.1',1),expected_sni='desktop.example.ts.net') as relay:
                sock=socket.create_connection(relay.address);sock.setblocking(False);fd=sock.detach()
                try:self.assertLess(self.lib.secure_net_handshake(fd,0,None),0)
                finally:os.close(fd)
                self.assertEqual(relay.sni,[None])
    def test_sni_does_not_authorize_an_unpaired_server(self):
        with pairing() as (r,identity,path,key):
            self.assertEqual(self.lib.secure_net_start(str(path).encode()),0);r.revoke(identity)
            with security.SecureListener('127.0.0.1',0,'audio',r) as listener:
                errors=[]
                def serve():
                    try:
                        client,_=listener.accept();client.close();errors.append('Unexpected authorization')
                    except OSError:pass
                thread=threading.Thread(target=serve);thread.start()
                with TcpForward(listener.getsockname(),expected_sni='desktop.example.ts.net') as relay:
                    sock=socket.create_connection(relay.address);sock.setblocking(False);fd=sock.detach()
                    try:self.assertLess(self.lib.secure_net_handshake_host(fd,0,b'desktop.example.ts.net',None),0)
                    finally:os.close(fd)
                    self.assertEqual(relay.sni,['desktop.example.ts.net'])
                thread.join(3);self.assertFalse(thread.is_alive());self.assertFalse(errors)
    def test_native_client_rejects_unpaired_host_without_falling_back(self):
        with pairing() as (r,identity,path,key):
            self.assertEqual(self.lib.secure_net_start(str(path).encode()),0)
            r.revoke(identity)
            with security.SecureListener('127.0.0.1',0,'audio',r) as listener:
                errors=[]
                def serve():
                    try:
                        client,_=listener.accept();client.close();errors.append('Unexpected authorization')
                    except OSError:pass
                thread=threading.Thread(target=serve);thread.start()
                sock=socket.create_connection(listener.getsockname());sock.setblocking(False);fd=sock.detach()
                try:self.assertLess(self.lib.secure_net_handshake(fd,0,None),0)
                finally:os.close(fd)
                thread.join(3);self.assertFalse(thread.is_alive());self.assertEqual(errors,[])
    def test_native_pair_file_rejects_malformed_length_and_magic(self):
        with pairing() as (r,identity,path,key),tempfile.NamedTemporaryFile() as bad:
            original=path.read_bytes()
            for raw in [original[:size] for size in (0,8,24,55)]+[original+b'x',b'BADMAGIC'+original[8:]]:
                bad.seek(0);bad.write(raw);bad.truncate();bad.flush()
                self.assertLess(self.lib.secure_net_start(bad.name.encode()),0)
                self.assertEqual(self.lib.secure_net_paired(),0)

    def test_native_discovery_mac_nonce_tamper_and_replay_protection(self):
        with pairing() as (r,identity,path,key):
            self.assertEqual(self.lib.secure_net_start(str(path).encode()),0)
            query=ctypes.create_string_buffer(68);self.assertEqual(self.lib.secure_net_query(query),0)
            response=security.discovery_reply(query.raw,r,'TestPC');self.assertIsNotNone(response)
            audio=ctypes.c_uint();control=ctypes.c_uint();name=ctypes.create_string_buffer(32)
            check=lambda raw:self.lib.secure_net_reply(raw,len(raw),ctypes.byref(audio),ctypes.byref(control),name)
            self.assertEqual(check(response[:-1]+bytes([response[-1]^1])),0)
            self.assertEqual(check(response),1);self.assertEqual((audio.value,control.value,name.value),(48152,48153,b'TestPC'))
            self.assertEqual(check(response),0)
            self.lib.secure_net_query(query);self.assertEqual(check(response),0)
            fresh=security.discovery_reply(query.raw,r);time.sleep(3.02)
            self.assertEqual(check(fresh),0)
            with tempfile.NamedTemporaryFile() as bad:
                bad.write(b'bad');bad.flush();self.assertNotEqual(self.lib.secure_net_start(bad.name.encode()),0)
                self.assertEqual(self.lib.secure_net_paired(),0)

if __name__=='__main__':unittest.main()
