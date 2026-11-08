"""Authenticated receiver feedback and conservative, packet-boundary Opus ABR."""
from collections import deque
from dataclasses import dataclass
import select
import ssl
import struct
import time
from opus_audio import BITRATES

WIRE=struct.Struct('<4s7I')
WIRE2=struct.Struct('<4s8I')

@dataclass(frozen=True)
class Report:
    mode:int
    underruns:int
    buffer_ms:int
    seconds:int
    playing:int
    remote:int
    actual:int
    received_frames:int|None=None
    def encode(self):
        fields=(self.mode,self.underruns,self.buffer_ms,self.seconds,self.playing,self.remote,self.actual)
        return WIRE.pack(b'VAQ1',*fields) if self.received_frames is None else WIRE2.pack(b'VAQ2',*fields,self.received_frames)

class Feedback:
    """At most one incomplete 32-byte frame; no plaintext or unauthenticated IPC."""
    def __init__(self):self.data=bytearray();self.closed=False;self.recent=deque()
    def feed(self,data,now=None):
        now=time.monotonic() if now is None else now
        if len(data)>1024:raise ValueError('Oversized receiver feedback read')
        self.data.extend(data);reports=[]
        while len(self.data)>=4:
            tag=bytes(self.data[:4]);wire=WIRE2 if tag==b'VAQ2' else WIRE
            if tag not in (b'VAQ1',b'VAQ2'):raise ValueError('Invalid receiver quality feedback')
            if len(self.data)<wire.size:break
            tag,*fields=wire.unpack_from(self.data);del self.data[:wire.size]
            report=Report(*fields)
            if (report.mode not in (0,*BITRATES) or report.buffer_ms>(2048 if tag==b'VAQ2' else 2000) or
                report.playing not in (0,1) or report.remote not in (0,1) or
                report.actual not in (0,*BITRATES)):
                raise ValueError('Invalid receiver quality feedback')
            while self.recent and self.recent[0]<now-1:self.recent.popleft()
            self.recent.append(now)
            if len(self.recent)>16:raise ValueError('Receiver feedback rate exceeded')
            reports.append(report)
        return reports
    def poll(self,sock):
        if not sock.authorized():raise OSError('Vita authorization revoked')
        reports=[];timeout=sock.gettimeout()
        try:
            sock.setblocking(False)
            for _ in range(4):
                readable,_,_=select.select([sock],[],[],0)
                if not readable and not sock.pending():break
                try:data=sock.recv(1024)
                except (ssl.SSLWantReadError,ssl.SSLWantWriteError):break
                if not data:self.closed=True;break
                reports.extend(self.feed(data))
        finally:sock.settimeout(timeout)
        return reports

class Adaptive:
    """Down promptly after receiver trouble; up one step after 60 healthy seconds.

    Auto is opt-in per route. No feedback leaves legacy/fixed bitrate unchanged.
    This observes the Vita buffer, never the PC's Wi-Fi link rate. TCP stalls
    and stale feedback inhibit recovery. It cannot repair a complete outage.
    """
    def __init__(self,default=320,resume_auto=None):
        self.bitrate=default;self.mode=None;self.remote=False;self.last_seen=None
        self.resume_auto={bool(k):v for k,v in (resume_auto or {}).items() if v in BITRATES}
        self.last_change=0.;self.healthy_since=None;self.low=0;self.previous=None
        self.stalls=deque();self.reason='PC default'
    def _set(self,value,now,reason):
        self.bitrate=value;self.last_change=now;self.healthy_since=None;self.low=0;self.reason=reason
        return value
    def _lower(self,now,reason,steps=1):
        if now-self.last_change<5:return self.bitrate
        index=BITRATES.index(self.bitrate);value=BITRATES[max(0,index-steps)]
        return self._set(value,now,reason) if value!=self.bitrate else self.bitrate
    def observe(self,report,now=None):
        now=time.monotonic() if now is None else now
        old_seen=self.last_seen;self.last_seen=now
        if (self.mode,self.remote)!=(report.mode,bool(report.remote)):
            self.mode=report.mode;self.remote=bool(report.remote);self.previous=report
            self.stalls.clear()
            return self._set(report.mode or self.resume_auto.get(bool(report.remote),192 if report.remote else 320),now,'Vita selection')
        previous=self.previous;self.previous=report
        if self.mode:return self.bitrate
        if previous and (report.underruns<previous.underruns or report.seconds<previous.seconds):
            self.healthy_since=None;self.low=0;self.last_change=now;return self.bitrate
        delta=report.underruns-(previous.underruns if previous else report.underruns)
        self.low=self.low+1 if report.buffer_ms<80 and (report.seconds or report.underruns) else 0
        if delta or self.low>=2:
            self.healthy_since=None
            return self._lower(now,'Vita rebuffer/low buffer',2 if delta>=2 else 1)
        healthy=report.playing and report.buffer_ms>=(300 if report.remote else 140)
        if not healthy or old_seen is None or now-old_seen>2.5:
            self.healthy_since=None;return self.bitrate
        if self.healthy_since is None:self.healthy_since=now
        if now-max(self.healthy_since,self.last_change)>=60:
            index=BITRATES.index(self.bitrate)
            if index+1<len(BITRATES):return self._set(BITRATES[index+1],now,'60 seconds of healthy Vita buffer')
        return self.bitrate
    def send_delay(self,seconds,now=None):
        now=time.monotonic() if now is None else now
        if self.mode!=0:return self.bitrate
        while self.stalls and self.stalls[0]<now-5:self.stalls.popleft()
        if seconds>=.15:self.stalls.append(now);self.healthy_since=None
        if len(self.stalls)>=2:
            self.stalls.clear();return self._lower(now,'Repeated TCP send stalls')
        return self.bitrate
    def tick(self,now=None):
        now=time.monotonic() if now is None else now
        if self.mode==0 and self.last_seen is not None and now-self.last_seen>4:
            self.healthy_since=None
            if now-self.last_change>=10:self._lower(now,'Receiver feedback stalled')
        return self.bitrate
