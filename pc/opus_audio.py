"""20 ms stereo Opus packets for the local receiver link. No Spotify API calls."""
import ctypes
import hashlib
from pathlib import Path
import ctypes.util
import struct
import sys

RATE=48000
FRAMES=960
PCM_BYTES=FRAMES*4
MAX_PACKET=1275
BITRATES=(96,128,160,192,256,320)

def header(bitrate=320):
    if bitrate not in BITRATES:raise ValueError('Opus bitrate must be 96, 128, 160, 192, 256 or 320 kbps')
    return struct.pack('<4sIHHI',b'VOPS',RATE,2,FRAMES,bitrate*1000)

# Built from the hash-pinned upstream Opus 1.6.1 release; see SUPPLY_CHAIN.md.
OPUS_DLL_SHA256='b60905db3ed1a2b9f33be9d5c74ceb233d53f1dab5ababe27f683604e52389ff'

def library():
    if sys.platform=='win32':
        path=Path(__file__).resolve().parent/'native'/'opus.dll'
        try:data=path.read_bytes()
        except OSError as exc:raise RuntimeError('The bundled Opus DLL is missing. Run Upgrade Host.cmd from the complete release.') from exc
        if hashlib.sha256(data).hexdigest()!=OPUS_DLL_SHA256:
            raise RuntimeError('Opus DLL integrity check failed. Re-extract the original release and run Upgrade Host.cmd.')
        # Full path and safe DLL search flags; do not load a PATH/working-dir DLL.
        return ctypes.CDLL(str(path),winmode=0x00001100)
    name=ctypes.util.find_library('opus')
    if not name:raise RuntimeError('Native tests require a system libopus or the hash-pinned source build.')
    return ctypes.CDLL(name)

class Encoder:
    """Own one native encoder; CBR gives predictable network use, no DTX gaps."""
    def __init__(self,bitrate=320):
        header(bitrate);self.state=None;self.lib=library();self.bitrate=bitrate
        lib=self.lib
        lib.opus_encoder_create.argtypes=[ctypes.c_int32,ctypes.c_int,ctypes.c_int,ctypes.POINTER(ctypes.c_int)]
        lib.opus_encoder_create.restype=ctypes.c_void_p
        lib.opus_encoder_destroy.argtypes=[ctypes.c_void_p];lib.opus_encoder_destroy.restype=None
        lib.opus_encoder_ctl.argtypes=[ctypes.c_void_p,ctypes.c_int];lib.opus_encoder_ctl.restype=ctypes.c_int
        lib.opus_encode.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_int16),ctypes.c_int,
                                 ctypes.POINTER(ctypes.c_ubyte),ctypes.c_int32]
        lib.opus_encode.restype=ctypes.c_int32
        lib.opus_get_version_string.restype=ctypes.c_char_p
        error=ctypes.c_int();self.state=lib.opus_encoder_create(RATE,2,2049,ctypes.byref(error)) # OPUS_APPLICATION_AUDIO
        if not self.state:raise RuntimeError(f'Opus encoder initialization failed: {error.value}')
        try:
            for request,value in [(4002,bitrate*1000),(4006,0),(4010,10),(4024,3002),(4016,0)]:
                if lib.opus_encoder_ctl(self.state,request,ctypes.c_int(value))<0:
                    raise RuntimeError('Could not configure the Opus music encoder')
        except Exception:self.close();raise
        self.output=(ctypes.c_ubyte*MAX_PACKET)()
    @property
    def version(self):return self.lib.opus_get_version_string().decode('ascii','replace')
    def set_bitrate(self,bitrate):
        header(bitrate)
        if not self.state:raise RuntimeError('Opus encoder is closed')
        if self.lib.opus_encoder_ctl(self.state,4002,ctypes.c_int(bitrate*1000))<0:
            raise RuntimeError('Could not change Opus bitrate')
        self.bitrate=bitrate
    def encode(self,pcm):
        if not self.state:raise RuntimeError('Opus encoder is closed')
        if len(pcm)!=PCM_BYTES:raise ValueError('Opus requires exactly 960 stereo PCM frames')
        samples=(ctypes.c_int16*(FRAMES*2)).from_buffer_copy(pcm)
        if sys.byteorder!='little':
            for i in range(FRAMES*2):samples[i]=int.from_bytes(pcm[i*2:i*2+2],'little',signed=True)
        size=self.lib.opus_encode(self.state,samples,FRAMES,self.output,MAX_PACKET)
        if size<1:raise RuntimeError(f'Opus encoding failed: {size}')
        return bytes(self.output[:size])
    def close(self):
        if self.state:self.lib.opus_encoder_destroy(self.state);self.state=None
    def __enter__(self):return self
    def __exit__(self,*exc):self.close()

def framed(packet):
    if not 1<=len(packet)<=MAX_PACKET:raise ValueError('Invalid Opus packet length')
    return struct.pack('<H',len(packet))+packet

class PcmFrames:
    """Reblock 1024-frame capture to 960 frames without dropping any samples."""
    def __init__(self):self.pending=bytearray()
    def feed(self,block):
        if not block or len(block)%4:raise ValueError('Invalid stereo PCM block')
        self.pending.extend(block)
        while len(self.pending)>=PCM_BYTES:
            result=bytes(self.pending[:PCM_BYTES]);del self.pending[:PCM_BYTES];yield result
    def finish(self):
        if self.pending:
            result=bytes(self.pending)+b'\0'*(PCM_BYTES-len(self.pending));self.pending.clear();yield result
