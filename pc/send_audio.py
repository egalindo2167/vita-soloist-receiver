#!/usr/bin/env python3
"""Send local PCM audio to Vita Audio Receiver. Python 3.10+; no Spotify credentials."""
import argparse
import array
import math
import shutil
import socket
import struct
import subprocess
import sys
import time
import wave
import warnings
from capture_queue import CaptureQueue
from version import VERSION

RATE = 48000
FRAMES = 1024
BLOCK = FRAMES * 4
HEADER = struct.pack('<4sIHHI', b'VPCM', RATE, 2, 16, FRAMES)


def receive_exact(sock, size):
    data = bytearray()
    while len(data) < size:
        part = sock.recv(size-len(data))
        if not part:
            raise RuntimeError('Vita closed the connection during startup. Install the package VPK and inspect its log.txt.')
        data.extend(part)
    return bytes(data)


def startup(sock,header=HEADER):
    sock.sendall(header)
    try:
        tag, code = struct.unpack('<4sI', receive_exact(sock, 8))
    except socket.timeout as exc:
        raise RuntimeError('No startup reply from Vita. Use the package VPK; check the Vita screen/log.') from exc
    if tag == b'VPER':
        if code == 1:
            raise RuntimeError('Vita rejected the audio format; install matching receiver and sender versions.')
        if code == 2:
            raise RuntimeError('Vita could not initialize its Opus decoder. Inspect its log.txt.')
        raise RuntimeError(f'Vita could not open its audio port: 0x{code:08X}. See receiver log.txt.')
    if tag != b'VPOK' or code != RATE:
        raise RuntimeError('Unexpected Vita startup reply; use matching receiver and sender versions.')


def read_blocks(stream):
    """Preserve frame/block boundaries even when pipe reads return short data."""
    pending = bytearray()
    while True:
        chunk = stream.read(BLOCK - len(pending))
        if not chunk:
            if len(pending) % 4:
                raise ValueError('PCM input ended in the middle of a stereo frame')
            if pending:
                yield bytes(pending)
            return
        pending.extend(chunk)
        if len(pending) == BLOCK:
            yield bytes(pending)
            pending.clear()


def tone_blocks(seconds):
    total = round(seconds * RATE)
    for start in range(0, total, FRAMES):
        samples = array.array('h')
        for i in range(start, min(start + FRAMES, total)):
            # Quiet 440 Hz stereo tone; start with a low Vita volume.
            fade = min(1.0, i / (RATE*0.01), (total-i) / (RATE*0.01))
            value = round(32767 * 0.12 * fade * math.sin(2*math.pi*440*i/RATE))
            samples.extend((value, value))
        if sys.byteorder != 'little':
            samples.byteswap()
        yield samples.tobytes()


def transmit(sock, blocks, paced):
    sent = 0
    start = time.monotonic()
    for block in blocks:
        if not block or len(block) % 4:
            raise ValueError('Invalid PCM block')
        if paced:
            delay = start + sent / (RATE * 4) - time.monotonic()
            if delay > 0:
                time.sleep(delay)
        sock.sendall(block)
        sent += len(block)
    return sent


def capture_pcm(data, gain):
    """Convert Windows loopback floats to contiguous stereo s16le PCM."""
    import numpy as np
    samples = np.asarray(data, dtype=np.float32)
    if samples.ndim != 2 or samples.shape[1] != 2:
        raise RuntimeError(f'Expected stereo capture; received shape {samples.shape}')
    samples = np.nan_to_num(samples, nan=0.0, posinf=0.0, neginf=0.0)
    samples = np.clip(samples * gain, -1.0, 1.0)
    return np.ascontiguousarray(samples * 32767, dtype='<i2').tobytes()


def record_blocks(blocks, path):
    """Record the exact bytes sent; compare this WAV on the PC with Vita output."""
    with wave.open(path, 'wb') as writer:
        writer.setnchannels(2); writer.setsampwidth(2); writer.setframerate(RATE)
        for block in blocks:
            writer.writeframesraw(block)
            yield block


def loopback_blocks(device_hint, gain=0.5, capture_blocksize=8192, stats=None):
    try:
        import numpy as np
        import soundcard as sc
    except ImportError as exc:
        raise RuntimeError('For loopback install: py -m pip install -r requirements-loopback.txt') from exc
    if not device_hint:
        raise RuntimeError('Diagnostic endpoint capture requires --device with an exact output ID/name. No default-output fallback.')
    outputs=list(sc.all_speakers())
    matches=[s for s in outputs if s.id==device_hint]
    if not matches:matches=[s for s in outputs if s.name==device_hint]
    if len(matches)!=1:raise RuntimeError('Diagnostic capture device missing or ambiguous. Run --list-devices; no fallback is allowed.')
    microphones=[m for m in sc.all_microphones(include_loopback=True) if m.isloopback and m.id==matches[0].id]
    if len(microphones)!=1:raise RuntimeError('Exact loopback endpoint is missing; no fallback is allowed.')
    mic=microphones[0]
    print(f'Capturing output: {mic.name}', flush=True)
    if not mic.isloopback:
        raise RuntimeError('Selected device is not a loopback endpoint. Choose an output from --list-devices.')
    print(f'Capture gain: {gain:g}; capture buffer: {capture_blocksize} frames', flush=True)
    notices_total = 0
    notices_reported = 0
    last_notice = 0.0
    with mic.recorder(samplerate=RATE, channels=[0, 1], blocksize=capture_blocksize) as recorder:
        while True:
            # Count the WASAPI warnings rather than writing a traceback to the
            # terminal for every gap; terminal I/O can itself delay capture.
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter('always')
                data = recorder.record(numframes=FRAMES)
            for warning in caught:
                if 'data discontinuity' in str(warning.message):
                    notices_total += 1
                    if stats is not None:
                        stats['discontinuities'] = notices_total
                else:
                    print(f'Capture warning: {warning.message}', file=sys.stderr)
            now = time.monotonic()
            if notices_total>notices_reported and now-last_notice >= 5:
                print(f'Windows capture reports {notices_total} discontinuities so far; '
                      'audio gaps may be audible.', file=sys.stderr)
                last_notice = now
                notices_reported = notices_total
            yield capture_pcm(data, gain)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('vita_ip', nargs='?', help='IP shown on Vita receiver screen')
    parser.add_argument('--port', type=int, default=49152)
    source = parser.add_mutually_exclusive_group()
    source.add_argument('--tone', action='store_true', help='Send a quiet test tone')
    source.add_argument('--file', help='Play a local MP3/WAV/FLAC through FFmpeg')
    source.add_argument('--stdin', action='store_true', help='Read 48000 Hz stereo s16le PCM from stdin')
    source.add_argument('--loopback', action='store_true', help='Capture PC output (primarily Windows WASAPI)')
    parser.add_argument('--seconds', type=float, default=5.0, help='Duration for test tone or capture-only recording')
    parser.add_argument('--device', help='SoundCard loopback device ID/name')
    parser.add_argument('--list-devices', action='store_true')
    parser.add_argument('--gain', type=float, default=0.5,
                        help='Loopback level multiplier; default 0.5 (-6 dB). Does not affect test tone/files.')
    parser.add_argument('--capture-blocksize', type=int, default=8192,
                        help='Loopback capture buffer in frames; default 8192')
    parser.add_argument('--record-wav', help='Also save the sent PCM to a local WAV for diagnosis')
    source.add_argument('--capture-only', metavar='WAV',
                        help='Record PC output to WAV without connecting to Vita')
    parser.add_argument('--version', action='version', version='Vita capture diagnostics '+VERSION)
    args = parser.parse_args(argv)
    if not args.capture_only and not args.list_devices:
        parser.error("Unencrypted sending was retired in 0.10. Use Setup/Upgrade Host and Pair Vita.cmd. Capture-only diagnostics remain available.")
    if args.list_devices:
        try:
            import soundcard as sc
        except ImportError:
            parser.error('Install requirements-loopback.txt first')
        for speaker in sc.all_speakers():
            print(f'{speaker.name}\n  ID: {speaker.id}')
        return 0
    if not args.vita_ip and not args.capture_only:
        parser.error('Provide the IP shown on the Vita')
    if not 1 <= args.port <= 65535:
        parser.error('Port must be 1..65535')
    if not math.isfinite(args.seconds) or args.seconds <= 0:
        parser.error('--seconds must be a positive finite number')
    if not math.isfinite(args.gain) or not 0 <= args.gain <= 2:
        parser.error('--gain must be between 0 and 2')
    if not 1024 <= args.capture_blocksize <= 48000:
        parser.error('--capture-blocksize must be 1024..48000')
    if args.capture_only and args.record_wav:
        parser.error('Use --capture-only or --record-wav, not both')
    stats = {'discontinuities': 0}
    blocks = None
    stage = "preparing audio"
    try:
        if args.capture_only:
            stage = 'recording PC audio without network'
            print(f'Capture-only: recording {args.seconds:g} seconds. No Vita connection.',file=sys.stderr)
            blocks = loopback_blocks(args.device, args.gain, args.capture_blocksize, stats)
            remaining = round(args.seconds*RATE)*4
            with wave.open(args.capture_only,'wb') as writer:
                writer.setnchannels(2);writer.setsampwidth(2);writer.setframerate(RATE)
                for block in blocks:
                    n=min(remaining,len(block))
                    writer.writeframesraw(block[:n]);remaining-=n
                    if not remaining:break
            print(f'Saved {args.capture_only}',file=sys.stderr)
            return 0
    except KeyboardInterrupt:
        print('\nStopped.', file=sys.stderr)
        return 0
    except (OSError, RuntimeError, ValueError) as exc:
        print(f'Error while {stage}: {exc}', file=sys.stderr)
        return 1
    finally:
        if args.loopback or args.capture_only:
            print(f"Windows capture discontinuity reports: {stats['discontinuities']}",file=sys.stderr)
        if blocks is not None and hasattr(blocks, 'close'):
            blocks.close()

if __name__ == '__main__':
    if sys.platform == 'win32':
        # The launcher gives this child its own console process group and uses
        # Ctrl+Break to request the same clean shutdown as a manual Ctrl+C.
        import signal
        signal.signal(signal.SIGBREAK, signal.default_int_handler)
    raise SystemExit(main())
