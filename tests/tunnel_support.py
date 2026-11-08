"""Opaque TCP forwarding for integration tests; never terminates TLS."""
import select
import socket
import threading

class TcpForward:
    def __init__(self,upstream,expected_sni=None):
        self.upstream=upstream;self.stop=threading.Event();self.threads=[];self.wire=bytearray();self.lock=threading.Lock()
        self.expected_sni=expected_sni;self.sni=[]
        self.listener=socket.socket();self.listener.bind(('127.0.0.1',0));self.listener.listen(4);self.listener.settimeout(.1)
        self.address=self.listener.getsockname()
        self.thread=threading.Thread(target=self.accept,daemon=True);self.thread.start()
    def accept(self):
        while not self.stop.is_set():
            try:client,_=self.listener.accept()
            except socket.timeout:continue
            except OSError:break
            worker=threading.Thread(target=self.forward,args=(client,),daemon=True);self.threads.append(worker);worker.start()
    def forward(self,client):
        try:
            initial=b''
            if self.expected_sni is not None:
                # Like Funnel ingress, inspect ClientHello without terminating
                # TLS. Keep all bytes intact, including PSK/binder/key share.
                client.settimeout(4);initial,hostname=client_hello(client)
                with self.lock:self.sni.append(hostname);self.wire.extend(initial)
                if hostname!=self.expected_sni:
                    client.close();return
            with client,socket.create_connection(self.upstream,timeout=4) as server:
                client.settimeout(4);server.settimeout(4)
                if initial:server.sendall(initial)
                while not self.stop.is_set():
                    readable,_,_=select.select([client,server],[],[],.1)
                    for source in readable:
                        data=source.recv(16384)
                        if not data:return
                        with self.lock:
                            if len(self.wire)<1024*1024:self.wire.extend(data)
                        (server if source is client else client).sendall(data)
        except (OSError,ValueError,IndexError):client.close()
    def close(self):
        self.stop.set();self.listener.close();self.thread.join(2)
        for thread in self.threads:thread.join(2)
    def __enter__(self):return self
    def __exit__(self,*args):self.close()

def client_hello(sock):
    def exact(n):
        result=bytearray()
        while len(result)<n:
            chunk=sock.recv(n-len(result))
            if not chunk:raise ValueError('Truncated ClientHello')
            result.extend(chunk)
        return bytes(result)
    wire=bytearray();handshake=bytearray()
    while True:
        header=exact(5);length=int.from_bytes(header[3:5],'big')
        if header[0]!=22 or length>16384:raise ValueError('Expected TLS handshake record')
        payload=exact(length);wire.extend(header+payload);handshake.extend(payload)
        if len(handshake)>65536:raise ValueError('Oversized ClientHello')
        if len(handshake)>=4 and len(handshake)>=4+int.from_bytes(handshake[1:4],'big'):break
    if handshake[0]!=1:raise ValueError('Expected ClientHello')
    h=handshake[4:];at=34;at+=1+h[at]
    at+=2+int.from_bytes(h[at:at+2],'big');at+=1+h[at]
    end=at+2+int.from_bytes(h[at:at+2],'big');at+=2
    if end>len(h):raise ValueError('Truncated extensions')
    while at+4<=end:
        kind=int.from_bytes(h[at:at+2],'big');size=int.from_bytes(h[at+2:at+4],'big');at+=4
        extension=h[at:at+size];at+=size
        if kind==0:
            if len(extension)<5 or extension[2]!=0:raise ValueError('Invalid server name')
            size=int.from_bytes(extension[3:5],'big')
            return bytes(wire),bytes(extension[5:5+size]).decode('ascii')
    return bytes(wire),None
