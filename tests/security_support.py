"""Isolated test credentials; production always uses Windows DPAPI."""
from contextlib import contextmanager
import base64
from pathlib import Path
import socket
import ssl
import tempfile
import secure_host

@contextmanager
def pairing():
    with tempfile.TemporaryDirectory() as directory:
        # Explicit dependency injection, never an environment-controlled bypass.
        registry=secure_host.Registry(directory,
            protect=lambda value:base64.b64encode(value.encode()).decode(),
            unprotect=lambda value:base64.b64decode(value).decode())
        identity,path=registry.pair('Test Vita')
        yield registry,identity,path,registry.lookup(identity)

def tls_client(address,identity,key,role='audio',context=None,private=False,server_hostname=None):
    if context is None:
        context=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname=False;context.verify_mode=ssl.CERT_NONE
        context.minimum_version=context.maximum_version=ssl.TLSVersion.TLSv1_3
        context.set_psk_client_callback(lambda hint:(secure_host.tls_identity(key) if private else identity,key))
    raw=socket.create_connection(address,timeout=4);sock=None
    try:
        sock=context.wrap_socket(raw,server_hostname=server_hostname)
        sock.sendall(secure_host.ROLE[role]);data=bytearray()
        while len(data)<4:
            part=sock.recv(4-len(data))
            if not part:raise OSError('No authenticated role acknowledgement')
            data.extend(part)
        if data!=b'VSA1':raise OSError('Wrong secure role reply')
        return sock
    except BaseException:(sock or raw).close();raise
