"""Authenticated control markers discard audio across both app and TCP buffers."""
import struct
import time
import secrets

class PlaybackTransition:
    def __init__(self):
        self.serial=secrets.randbits(32) or 1;self.valid=False;self.hold=False;self.kind=None;self.last_reset=-100.;self.changed=False
    def marker(self):return struct.pack('<II',self.serial,int(self.hold))
    def begin(self,player,kind,target=None,now=None):
        now=time.monotonic() if now is None else now
        self.serial=self.serial%0xffffffff+1;self.hold=True;self.kind=kind;self.target=target
        self.uri=player.item['uri'];self.context=player.context;self.position=player.position_ms()
        self.started=now;self.changed=True;self.valid=True
    def finish(self,now=None):
        if not self.hold:return
        self.hold=False;self.kind=None;self.changed=True;self.last_reset=time.monotonic() if now is None else now
    def reset(self,now=None):
        self.serial=self.serial%0xffffffff+1;self.hold=False;self.kind=None;self.changed=True
        self.last_reset=time.monotonic() if now is None else now;self.valid=True
    def observe(self,player,event,now=None):
        now=time.monotonic() if now is None else now
        if not self.hold or self.kind=='queue':return
        kind=event.get('type')
        if kind=='error':self.finish(now);return
        if self.kind=='status':
            if kind in ('playback_state','playback_changed') and player.status==self.target:self.finish(now)
            return
        changed=player.item['uri']!=self.uri or player.context!=self.context
        if self.kind=='seek':
            if changed:self.finish(now);return
            if kind in ('position_sync','playback_state') and abs(player.position_ms()-self.target)<=1500:
                self.finish(now)
        elif changed or (kind in ('position_sync','playback_state') and self.position>2000 and player.position_ms()<1500):
            self.finish(now)
    def tick(self,now=None):
        now=time.monotonic() if now is None else now
        if self.hold and now-self.started>(21 if self.kind=='queue' else 7):
            self.finish(now);return 'Playback change was not confirmed; audio resumed.'
        return ''
