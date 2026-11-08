"""Bounded, receiver-driven pacing. Codec frames stay 20 ms; writes batch 60 ms."""
import time

RATE=48000
BATCH_FRAMES=3
CAPACITY_MS=2048
TARGET_LOCAL_MS=256
TARGET_REMOTE_MS=1000

class ReceiverPacer:
    """Count decoded frames on the Vita, rather than the PC/Funnel TCP hop.

    Fresh VAQ2 feedback bounds audio in flight plus the receiver buffer. Catch-up
    is at most 4x and requires already captured samples; it never speeds playback.
    Legacy feedback keeps real-time pacing. Missing feedback never grants an
    unlimited burst, and intentional pacing waits are not network-stall samples.
    """
    def __init__(self):
        self.report=None;self.seen=None;self.sent=0;self.acked=0;self.wraps=0;self.raw_ack=0
        self.deadline=0.;self.speed=1.;self.catchup_batches=0;self.waits=0
    def observe(self,report,now=None):
        now=time.monotonic() if now is None else now
        if report.received_frames is not None:
            raw=report.received_frames
            if self.report is not None and self.report.received_frames is not None and raw<self.raw_ack:
                if self.raw_ack-raw>0x80000000:self.wraps+=1
                else:raise ValueError('Receiver audio acknowledgement moved backwards')
            ack=(self.wraps<<32)+raw
            if ack>self.sent:raise ValueError('Receiver acknowledged audio that was not sent')
            self.acked=ack;self.raw_ack=raw
        self.report=report;self.seen=now
    def estimate(self,now=None):
        now=time.monotonic() if now is None else now
        if self.report is None or self.report.received_frames is None or now-self.seen>2.5:return None
        report=self.report
        # Return-path latency makes this estimate conservative. Include frames
        # accepted by the PC/Funnel but not yet decoded on the actual Vita.
        drain=max(0,now-self.seen)*1000 if report.playing else 0
        return max(0.,report.buffer_ms+(self.sent-self.acked)*1000/RATE-drain)
    def delay(self,frames,now=None):
        now=time.monotonic() if now is None else now
        report=self.report;estimate=self.estimate(now)
        if report is not None and report.received_frames is not None and now-self.seen>5:
            raise TimeoutError('Vita audio feedback stalled; reopening a fresh audio stream')
        target=TARGET_REMOTE_MS if report is not None and report.remote else TARGET_LOCAL_MS
        if estimate is not None and estimate+frames*1000/RATE>min(CAPACITY_MS-120,target+180):
            self.waits+=1;return .025
        self.speed=4. if estimate is not None and estimate<target-100 else 1.
        return max(0.,min(.025,self.deadline-now))
    def sent_audio(self,frames,now=None):
        now=time.monotonic() if now is None else now
        self.sent+=frames
        if self.speed>1:self.catchup_batches+=1
        self.deadline=max(self.deadline,now)+frames/RATE/self.speed

class AudioBatch:
    """Join existing independent frames; no codec/quality/container change."""
    def __init__(self,count=BATCH_FRAMES):
        self.count=count;self.parts=[];self.frames=0
    def add(self,data,frames):
        self.parts.append(data);self.frames+=frames
        return len(self.parts)>=self.count
    def take(self):
        result=(b''.join(self.parts),self.frames);self.parts.clear();self.frames=0;return result
