#!/usr/bin/env python3
"""Wait for Vita-initiated audio connections; capture only while connected."""
import argparse
import signal
from secure_host import SecureListener
import socket
import struct
import sys
import threading
import time
from capture_queue import CaptureQueue
import send_audio as sender
import opus_audio
import audio_source
from receiver_quality import Feedback,Adaptive
from audio_transport import ReceiverPacer,AudioBatch
from windows_host import host_stop_requested

AUDIO_PORT=48152

class CaptureDriverStuck(RuntimeError):pass

def stream_session(sock,device=None,gain=0.5,blocksize=8192,factory=None,stop=host_stop_requested,codec='opus',bitrate=320,capture_config=None,quality_memo=None):
    sock.settimeout(5);sock.setsockopt(socket.IPPROTO_TCP,socket.TCP_NODELAY,1)
    # Keep Windows' dynamic send-buffer sizing. The receiver-driven pacer below
    # bounds application backlog across the full route, including Funnel.
    use_opus=codec=='opus'
    if use_opus and quality_memo and quality_memo.get('mode')==0:
        bitrate=quality_memo.get('rate',bitrate)
    owned_source=None;stats={'discontinuities':0}
    if factory is None:
        try:owned_source=audio_source.open_source(capture_config,gain,stats)
        except (OSError,RuntimeError) as exc:
            code=exc.code if isinstance(exc,audio_source.CaptureError) else 6
            try:
                from pathlib import Path
                audio_source.source_status(code,root=Path(capture_config).parent if capture_config else None,state='blocked')
            except OSError:pass
            sock.sendall(struct.pack('<4sIII',b'VAER',code,1,0))
            raise audio_source.CaptureError(code) from exc
    encoder=None
    try:
        encoder=opus_audio.Encoder(bitrate) if use_opus else None
        sender.startup(sock,opus_audio.header(bitrate) if use_opus else sender.HEADER)
    except BaseException:
        if encoder:encoder.close()
        if owned_source:owned_source.close()
        raise
    source=factory or owned_source.blocks
    try:capture=CaptureQueue(source,max_blocks=192,stop_requested=stop)
    except BaseException:
        if encoder:encoder.close()
        if owned_source:owned_source.close()
        raise
    reblock=opus_audio.PcmFrames();wire_bytes=0;audio_frames=0
    feedback=Feedback();adaptive=Adaptive(bitrate,quality_memo.get('auto') if quality_memo else None);pacer=ReceiverPacer();batch=AudioBatch()
    try:
        capture.prefill(6)
        print('Vita audio connected; capture running.',flush=True)
        if use_opus:
            print(f'Audio transport: Opus {bitrate} kbps CBR, stereo 48000 Hz; {encoder.version}.',flush=True)
        else:
            print('Audio transport: PCM 1536 kbps, stereo 48000 Hz over TLS 1.3.',flush=True)
        def update_quality():
            for report in feedback.poll(sock):
                pacer.observe(report)
                if use_opus:adaptive.observe(report)
            if use_opus and adaptive.tick()!=encoder.bitrate:
                encoder.set_bitrate(adaptive.bitrate)
                print(f'Opus link changed to {adaptive.bitrate} kbps CBR: {adaptive.reason}.',flush=True)
            if use_opus and quality_memo is not None and adaptive.mode is not None:
                quality_memo.update(mode=adaptive.mode,rate=adaptive.bitrate,seen=time.monotonic())
                if adaptive.mode==0:quality_memo.setdefault('auto',{})[adaptive.remote]=adaptive.bitrate
        def send(block,frames):
            nonlocal wire_bytes,audio_frames
            while not stop():
                update_quality()
                if feedback.closed:raise ConnectionError('Vita closed the audio connection')
                if capture.dropped:raise RuntimeError('Capture backlog exceeded four seconds; reopening a fresh stream')
                delay=pacer.delay(frames)
                if not delay:break
                time.sleep(delay)
            if stop():raise InterruptedError('Audio host stopping')
            before=time.monotonic();sock.sendall(block)
            pacer.sent_audio(frames)
            if use_opus:adaptive.send_delay(time.monotonic()-before)
            wire_bytes+=len(block);audio_frames+=frames
        def queue_send(block,frames):
            if batch.add(block,frames):send(*batch.take())
        finished=False
        while not stop():
            update_quality()
            if feedback.closed:break
            try:block=capture.poll(0.1)
            except StopIteration:finished=not stop();break
            if block is None:continue
            if use_opus:
                for pcm in reblock.feed(block):
                    update_quality()
                    if feedback.closed:break
                    queue_send(opus_audio.framed(encoder.encode(pcm)),opus_audio.FRAMES)
            else:queue_send(block,len(block)//4)
        if finished and use_opus:
            for pcm in reblock.finish():queue_send(opus_audio.framed(encoder.encode(pcm)),opus_audio.FRAMES)
        if finished and batch.parts:send(*batch.take())
    finally:
        if encoder:encoder.close()
        if owned_source:owned_source.close()
        capture.close()
        if audio_frames:
            print(f'Audio link: {wire_bytes} bytes / {audio_frames/sender.RATE:.2f} audio seconds = '
                  f'{wire_bytes*sender.RATE/audio_frames:.0f} B/sec, excluding TLS, TCP/IP and control/artwork.',flush=True)
        print(capture.summary(),flush=True)
        print(f'Receiver pacing: {pacer.catchup_batches} catch-up batches; {pacer.waits} buffer-window waits.',flush=True)
        print(f"Windows capture discontinuity reports this session: {stats['discontinuities']}",flush=True)
        if capture.thread.is_alive():
            raise CaptureDriverStuck('Capture driver did not stop; restarting the audio helper releases it.')

def serve(bind='0.0.0.0',port=AUDIO_PORT,device=None,gain=0.5,blocksize=8192,stop=host_stop_requested,factory=None,on_listen=None,codec='opus',bitrate=320,security=None,capture_config=None):
    if codec not in ('pcm','opus'):raise ValueError('Codec must be pcm or opus')
    opus_audio.header(bitrate)
    if factory is None:
        import numpy
    memo={}
    with SecureListener(bind,port,'audio',security) as server:
        if on_listen is not None:on_listen(server.getsockname())
        print(f'Audio host listening on TCP {server.getsockname()[1]}; waiting for the Vita.',flush=True)
        while not stop():
            try:client,address=server.accept()
            except socket.timeout:continue
            except OSError:continue # Reject unauthenticated peers before starting capture.
            with client:
                if memo.get('peer')!=client.identity or time.monotonic()-memo.get('seen',0)>120:
                    memo.clear();memo.update(peer=client.identity,auto={})
                print(f'Audio request from {address[0]}',flush=True)
                try:stream_session(client,device,gain,blocksize,factory,stop,codec,bitrate,capture_config,memo)
                except CaptureDriverStuck:raise
                except (OSError,ValueError,RuntimeError) as exc:
                    print(f'Audio session ended: {exc}',flush=True)
            print('Waiting for the next Vita connection.',flush=True)

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bind',default='0.0.0.0');parser.add_argument('--port',type=int,default=AUDIO_PORT)
    parser.add_argument('--device');parser.add_argument('--gain',type=float,default=0.5)
    parser.add_argument('--capture-config',help='Saved dedicated Soloist capture configuration')
    parser.add_argument('--capture-blocksize',type=int,default=8192)
    parser.add_argument('--codec',choices=('opus','pcm'),default='opus')
    parser.add_argument('--bitrate',type=int,choices=opus_audio.BITRATES,default=320,help='Opus bitrate in kbps')
    args=parser.parse_args(argv)
    try:serve(args.bind,args.port,args.device,args.gain,args.capture_blocksize,codec=args.codec,bitrate=args.bitrate,capture_config=args.capture_config)
    except KeyboardInterrupt:return 0
    except (OSError,RuntimeError,ImportError) as exc:print(f'Audio host error: {exc}',file=sys.stderr);return 1

if __name__=='__main__':
    if sys.platform=='win32':signal.signal(signal.SIGBREAK,signal.default_int_handler)
    raise SystemExit(main())
