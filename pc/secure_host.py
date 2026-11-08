"""TLS 1.3 paired-device transport. No plaintext compatibility listener.

Each device has a random 256-bit external TLS PSK provisioned over USB, never
over discovery. TLS authenticates both peers with PSK-DHE; no certificates,
password-derived keys, tickets, early data or opportunistic downgrade are used.
"""
import hashlib
from collections import deque
import hmac
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import select
import socket
import ssl
import struct
import sys
import tempfile
import threading
import time
import windows_host

MAGIC=b'VASEC01\0'
PAIR_BYTES=56
DISCOVERY_QUERY_BYTES=68
DISCOVERY_REPLY_BYTES=104
DISCOVERY_DOMAIN=b'VitaAudioReceiver discovery v1'
AUDIO_PORT=48152
CONTROL_PORT=48153
ROLE={'audio':b'VRA3','control':b'VRC3'}

class SecurityError(OSError):pass

def root_path():
    return Path(os.environ.get('LOCALAPPDATA',Path.home()/'AppData'/'Local'))/'VitaAudioReceiver'

def require_tls():
    if not getattr(ssl,'HAS_PSK',False) or not hasattr(ssl.SSLContext,'set_psk_server_callback'):
        raise RuntimeError('Secure host requires Python 3.13+ with TLS-PSK support. Use your Python 3.14 installation.')

def atomic_write(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    temporary=None
    try:
        with tempfile.NamedTemporaryFile('wb',dir=path.parent,delete=False) as file:
            temporary=Path(file.name);file.write(data)
        os.replace(temporary,path)
    finally:
        if temporary and temporary.exists():temporary.unlink()

class Registry:
    def __init__(self,root=None,protect=None,unprotect=None):
        self.root=Path(root) if root is not None else root_path()
        self.path=self.root/'paired-vitas.json'
        self.protect=protect or windows_host.protect_key
        self.unprotect=unprotect or windows_host.unprotect_key
        self.lock=threading.RLock();self.stamp=None;self.loaded_at=0;self.devices={};self.keys={};self.export_warned=False
    def _load(self,force=False):
        now=time.monotonic()
        if not force and now-self.loaded_at<0.25:return
        self.loaded_at=now
        try:stat=self.path.stat();stamp=(stat.st_mtime_ns,stat.st_size)
        except FileNotFoundError:stamp=None
        if not force and stamp==self.stamp:return
        self.stamp=stamp;self.keys={};self.devices={}
        if stamp is None:return
        if stamp[1]>65536:raise SecurityError('Pairing registry is too large')
        try:
            value=json.loads(self.path.read_text(encoding='utf-8'))
            devices=value['devices']
            if value['format']!=1 or not isinstance(devices,dict) or len(devices)>16:raise ValueError
            for identity,device in devices.items():
                if not re.fullmatch('[0-9a-f]{32}',identity) or not isinstance(device,dict):raise ValueError
                key=bytes.fromhex(self.unprotect(device['key_dpapi']))
                if len(key)!=32:raise ValueError
                self.keys[identity]=key;self.devices[identity]=device
        except (ValueError,KeyError,TypeError,RuntimeError,OSError) as exc:
            self.keys={};self.devices={};self.stamp=None
            raise SecurityError('Pairing registry cannot be read; access denied') from exc
    def lookup(self,identity):
        if not isinstance(identity,str) or not re.fullmatch('[0-9a-f]{32}',identity):return None
        with self.lock:self._load();return self.keys.get(identity)
    def resolve(self,wire_identity):
        """Rotating TLS identity; legacy IDs are accepted for old paired Vitas."""
        if not isinstance(wire_identity,str):return None
        if re.fullmatch('[0-9a-f]{32}',wire_identity):
            key=self.lookup(wire_identity)
            return (wire_identity,key) if key is not None else None
        if not re.fullmatch('v2:[0-9a-f]{32}:[0-9a-f]{32}',wire_identity):return None
        nonce=bytes.fromhex(wire_identity[3:35]);alias=bytes.fromhex(wire_identity[36:])
        with self.lock:
            self._load();result=None
            for identity,key in self.keys.items():
                if hmac.compare_digest(alias,identity_alias(key,b'tls',nonce)):result=(identity,key)
            return result
    def clear_export(self,identity,key):
        """Delete only this credential after the peer proves it already has it."""
        paths=[self.root/'pairing'/identity/'vita-pairing.bin',self.root/'pairing'/'vita-pairing.bin']
        removed=False
        for path in paths:
            try:
                with path.open('rb') as source:data=source.read(PAIR_BYTES+1)
                expected=MAGIC+bytes.fromhex(identity)+key
                if hmac.compare_digest(data,expected):
                    try:path.unlink();removed=True
                    except OSError:
                        if not self.export_warned:
                            print('Security: Windows could not delete a used PC pairing export. Close files using it and delete the exported PC copy manually.',flush=True)
                            self.export_warned=True
            except OSError:pass
        return removed
    def list(self):
        with self.lock:
            self._load(force=True)
            return [{'id':key,'name':str(value.get('name','PS Vita'))[:48]} for key,value in self.devices.items()]
    def pair(self,name='PS Vita'):
        with self.lock:
            self._load(force=True)
            if len(self.devices)>=16:raise SecurityError('Revoke an old Vita before pairing another (limit 16)')
            identity=secrets.token_bytes(16);key=secrets.token_bytes(32)
            name=''.join(c for c in name if c.isprintable())[:48] or 'PS Vita'
            self.devices[identity.hex()]={'name':name,'key_dpapi':self.protect(key.hex())}
            self._save()
            # Unique per-device export prevents pairing a second Vita from
            # replacing a file while another helper cleans up the first one.
            path=self.root/'pairing'/identity.hex()/'vita-pairing.bin'
            atomic_write(path,MAGIC+identity+key)
            return identity.hex(),path
    def revoke(self,identity):
        with self.lock:
            self._load(force=True)
            if identity not in self.devices:return False
            del self.devices[identity];self._save()
            # Do not leave a revoked credential exported for accidental reuse.
            for exported in (self.root/'pairing'/identity/'vita-pairing.bin',self.root/'pairing'/'vita-pairing.bin'):
                try:
                    with exported.open('rb') as source:data=source.read(PAIR_BYTES+1)
                    if len(data)==PAIR_BYTES and data[8:24].hex()==identity:exported.unlink()
                except FileNotFoundError:pass
            return True
    def _save(self):
        atomic_write(self.path,(json.dumps({'format':1,'devices':self.devices},indent=2)+'\n').encode('utf-8'))
        self.stamp=None;self.loaded_at=0

def discovery_key(key):return hmac.digest(key,DISCOVERY_DOMAIN,'sha256')

def identity_alias(key,purpose,nonce):
    return hmac.digest(key,b'VitaAudioReceiver alias v2 '+purpose+nonce,'sha256')[:16]

def tls_identity(key,nonce=None):
    nonce=secrets.token_bytes(16) if nonce is None else nonce
    if len(nonce)!=16:raise ValueError('Invalid identity nonce')
    return 'v2:'+nonce.hex()+':'+identity_alias(key,b'tls',nonce).hex()

def discovery_query(identity,key,nonce,private=False):
    identity=bytes.fromhex(identity) if isinstance(identity,str) else identity
    if len(identity)!=16 or len(key)!=32 or len(nonce)!=16:raise ValueError('Invalid discovery parameters')
    body=(b'VAD2'+identity_alias(key,b'discovery',nonce) if private else b'VAD1'+identity)+nonce
    return body+hmac.digest(discovery_key(key),body,'sha256')

def discovery_reply(request,registry,name=None):
    if len(request)!=DISCOVERY_QUERY_BYTES or request[:4] not in (b'VAD1',b'VAD2'):return None
    private=request[:4]==b'VAD2';key=None
    if private:
        with registry.lock:
            registry._load()
            for candidate in registry.keys.values():
                if hmac.compare_digest(request[4:20],identity_alias(candidate,b'discovery',request[20:36])):key=candidate
    else:key=registry.lookup(request[4:20].hex())
    if key is None:return None
    derived=discovery_key(key)
    if not hmac.compare_digest(request[36:],hmac.digest(derived,request[:36],'sha256')):return None
    name=re.sub('[^A-Za-z0-9_.-]','_',name or socket.gethostname())[:31] or 'Windows-PC'
    body=(b'VAH2' if private else b'VAH1')+request[4:36]+struct.pack('<HH',AUDIO_PORT,CONTROL_PORT)+name.encode('ascii').ljust(32,b'\0')
    return body+hmac.digest(derived,body,'sha256')

class RateGate:
    """Bound memory and accepted connection attempts, including pre-TLS failures."""
    def __init__(self,rate=1,burst=8,global_rate=4,global_burst=32):
        self.rate=rate;self.burst=burst;self.global_rate=global_rate;self.global_burst=global_burst
        self.peers={};self.tokens=float(global_burst);self.updated=time.monotonic()
    def allow(self,address):
        now=time.monotonic();self.tokens=min(self.global_burst,self.tokens+(now-self.updated)*self.global_rate);self.updated=now
        tokens,updated=self.peers.pop(address,(float(self.burst),now))
        tokens=min(self.burst,tokens+(now-updated)*self.rate)
        allowed=tokens>=1 and self.tokens>=1
        if allowed:tokens-=1;self.tokens-=1
        self.peers[address]=(tokens,now)
        while len(self.peers)>128:self.peers.pop(next(iter(self.peers)))
        return allowed

class SecureSocket:
    def __init__(self,sock,registry,identity,key):
        self.sock=sock;self.registry=registry;self.identity=identity;self.key_hash=hashlib.sha256(key).digest()
    def authorized(self):
        try:key=self.registry.lookup(self.identity)
        except SecurityError:return False
        return key is not None and hmac.compare_digest(hashlib.sha256(key).digest(),self.key_hash)
    def _check(self):
        if not self.authorized():raise SecurityError('Vita authorization revoked')
    def recv(self,*args,**kwargs):self._check();return self.sock.recv(*args,**kwargs)
    def send(self,*args,**kwargs):self._check();return self.sock.send(*args,**kwargs)
    def sendall(self,*args,**kwargs):self._check();return self.sock.sendall(*args,**kwargs)
    def __getattr__(self,name):return getattr(self.sock,name)
    def __enter__(self):return self
    def __exit__(self,*exc):self.sock.close()

class SecureListener:
    """Bounded concurrent pre-authentication, including shared-loopback relays.

    Loopback uses resource limits rather than one per-IP rate bucket. Old
    unauthenticated sockets rotate under pressure; a public flood can still
    exhaust the PC/network. No claimed identity bypasses TLS authentication.
    """
    MAX_HANDSHAKES=8
    MAX_WAITING=4
    HANDSHAKE_SECONDS=3.0

    def __init__(self,bind,port,purpose,registry=None):
        require_tls()
        if purpose not in ROLE:raise ValueError('Invalid secure channel purpose')
        self.registry=registry or Registry();self.purpose=purpose;self.gate=RateGate()
        self.lock=threading.RLock();self.workers={};self.waiting=deque();self.ready=deque()
        self.closed=False;self.timeout=.5;self.failed=0;self.noticed=0;self.last_notice=time.monotonic()
        self.sock=socket.socket()
        try:
            option=socket.SO_EXCLUSIVEADDRUSE if sys.platform=='win32' else socket.SO_REUSEADDR
            self.sock.setsockopt(socket.SOL_SOCKET,option,1)
            self.sock.bind((bind,port));self.sock.listen(32);self.sock.setblocking(False)
        except BaseException:self.sock.close();raise
    def __getattr__(self,name):return getattr(self.sock,name)
    def setblocking(self,enabled):self.timeout=None if enabled else 0.0
    def settimeout(self,seconds):
        if seconds is not None and seconds<0:raise ValueError('Timeout must be nonnegative')
        self.timeout=seconds
    def gettimeout(self):return self.timeout
    def __enter__(self):return self
    def __exit__(self,*exc):self.close()
    @staticmethod
    def _cancel(entry):
        entry['cancelled']=True
        sock=entry.get('connection') or entry['raw']
        try:sock.shutdown(socket.SHUT_RDWR)
        except OSError:pass
        sock.close()
    def _notice(self):
        now=time.monotonic()
        if self.failed-self.noticed>=20 and now-self.last_notice>=10:
            print(f'Security: {self.failed-self.noticed} failed/limited handshakes in the last interval; public probing may be occurring.',flush=True)
            self.noticed=self.failed;self.last_notice=now
    def _start(self,raw,address):
        entry={'raw':raw,'address':address,'cancelled':False}
        thread=threading.Thread(target=self._authenticate,args=(entry,),daemon=True,name='vita-tls-handshake')
        entry['thread']=thread;self.workers[id(entry)]=entry;thread.start()
    def _drain(self):
        with self.lock:
            while self.waiting and len(self.workers)<self.MAX_HANDSHAKES:
                # New arrivals must not sit behind a FIFO of silent sockets.
                raw,address,accepted=self.waiting.pop()
                if time.monotonic()-accepted>self.HANDSHAKE_SECONDS:raw.close();continue
                self._start(raw,address)
    def _authenticate(self,entry):
        raw=entry['raw'];connection=None;channel=None;authenticated={}
        deadline=time.monotonic()+self.HANDSHAKE_SECONDS
        try:
            context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.minimum_version=context.maximum_version=ssl.TLSVersion.TLSv1_3
            context.options|=ssl.OP_NO_TICKET;context.num_tickets=0
            def key_for(wire_identity):
                try:pair=self.registry.resolve(wire_identity)
                except SecurityError:return b''
                if pair is None:return b''
                identity,key=pair;authenticated.update(identity=identity,key=key);return key
            context.set_psk_server_callback(key_for)
            connection=context.wrap_socket(raw,server_side=True,do_handshake_on_connect=False)
            with self.lock:
                entry['connection']=connection
                if self.closed or entry['cancelled']:raise SecurityError('Handshake cancelled')
            connection.settimeout(max(.001,deadline-time.monotonic()));connection.do_handshake()
            if connection.version()!='TLSv1.3' or not connection.session_reused or not authenticated:
                raise SecurityError('Paired TLS authentication required')
            with self.lock:entry['verified']=True
            channel=SecureSocket(connection,self.registry,authenticated['identity'],authenticated['key'])
            preface=bytearray()
            while len(preface)<4:
                remaining=deadline-time.monotonic()
                if remaining<=0:raise SecurityError('Secure role preface timed out')
                channel.settimeout(remaining);part=channel.recv(4-len(preface))
                if not part:raise SecurityError('Missing secure channel preface')
                preface.extend(part)
            if preface!=ROLE[self.purpose]:raise SecurityError('Wrong secure channel purpose')
            channel.sendall(b'VSA1');connection.settimeout(5)
            self.registry.clear_export(authenticated['identity'],authenticated['key'])
            with self.lock:
                if self.closed or entry['cancelled'] or self.ready:raise SecurityError('Handshake no longer wanted')
                self.workers.pop(id(entry),None)
                self.ready.append((channel,entry['address']));channel=None;connection=None
        except Exception:
            with self.lock:self.failed+=1
        finally:
            if channel:channel.close()
            elif connection:connection.close()
            else:raw.close()
            with self.lock:self.workers.pop(id(entry),None)
    def _admit(self,raw,address):
        loopback=ipaddress.ip_address(address[0]).is_loopback
        with self.lock:
            if not loopback and not self.gate.allow(address[0]):
                raw.close();self.failed+=1;return
            if len(self.workers)<self.MAX_HANDSHAKES:self._start(raw,address);return
            oldest=next((e for e in self.workers.values() if not e['cancelled'] and not e.get('verified')),None)
            if oldest:self._cancel(oldest)
            if len(self.waiting)>=self.MAX_WAITING:self.waiting.popleft()[0].close();self.failed+=1
            self.waiting.append((raw,address,time.monotonic()))
    def accept(self):
        start=time.monotonic()
        while True:
            self._drain()
            with self.lock:
                if self.closed:raise OSError('Listener closed')
                self._notice()
                if self.ready:
                    result=self.ready.popleft()
                    for entry in list(self.workers.values()):self._cancel(entry)
                    while self.waiting:self.waiting.popleft()[0].close()
                    return result
            wait=.01 if self.timeout!=0 else 0
            readable,_,_=select.select([self.sock],[],[],wait)
            if readable:
                try:raw,address=self.sock.accept()
                except BlockingIOError:continue
                self._admit(raw,address)
            if self.timeout is not None and time.monotonic()-start>=self.timeout:
                raise socket.timeout('No authenticated Vita ready')
    def close(self):
        with self.lock:
            if self.closed:return
            self.closed=True;self.sock.close();entries=list(self.workers.values())
            for entry in entries:self._cancel(entry)
            while self.waiting:self.waiting.popleft()[0].close()
            while self.ready:self.ready.popleft()[0].close()
        deadline=time.monotonic()+1
        for entry in entries:entry['thread'].join(max(0,deadline-time.monotonic()))
