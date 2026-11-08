"""Soloist-only process capture, guarded by a dedicated saved virtual output.

No default-output fallback. Native WASAPI include-process-tree capture is
independent of endpoint mixing; the cable keeps Soloist off physical speakers.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import sys
import threading
import time
import secure_host
import windows_host
from start_soloist import process_options,stop_process

from native_hashes import HELPER_SHA256
HERE=Path(__file__).resolve().parent
HEADER=struct.Struct('<4sIII')
ERRORS={
 1:'Choose a virtual cable on the PC. Run Setup Audio.cmd.',
 2:'Capture device missing. Check the virtual cable on the PC.',
 3:'Soloist is not running. Check Host Status on the PC.',
 4:'Soloist output mismatch. Set its output to the selected virtual cable.',
 5:'Soloist-only capture requires Windows 11 or build 20348 or newer.',
 6:'Could not initialize Soloist capture. Check Audio Status and host.log.',
 7:'Soloist cable routing is not verified. Run Setup Audio.cmd.',
 8:'Soloist build expired. Install a newer official Soloist build on the PC and restart the host.'}

class CaptureError(RuntimeError):
    def __init__(self,code,detail=None):
        self.code=code if code in ERRORS else 6
        super().__init__(ERRORS[self.code]+(' '+detail if detail else ''))

def helper_path():
    path=HERE/'native/soloist-capture.exe'
    try:raw=path.read_bytes()
    except OSError as exc:raise CaptureError(6,'Native helper missing; extract the complete release.') from exc
    if hashlib.sha256(raw).hexdigest()!=HELPER_SHA256:
        raise CaptureError(6,'Native helper integrity check failed; re-extract the release.')
    return path

def helper_json(arguments):
    if sys.platform!='win32':raise CaptureError(5)
    result=subprocess.run([str(helper_path()),*arguments],capture_output=True,timeout=12,
                          creationflags=subprocess.CREATE_NO_WINDOW)
    if len(result.stdout)>262144:raise CaptureError(6,'Oversized helper response.')
    try:value=json.loads(result.stdout.decode('utf-8'))
    except (ValueError,UnicodeError) as exc:raise CaptureError(6,'Invalid helper response.') from exc
    if not isinstance(value,dict) or value.get('format')!=1:raise CaptureError(6,'Invalid helper response.')
    if value.get('code',0):
        hr=value.get('hresult');detail=f'Windows error 0x{hr:08X}.' if type(hr) is int and 0<hr<=0xffffffff else None
        raise CaptureError(value['code'],detail)
    if result.returncode:raise CaptureError(6)
    return value

def render_devices():
    value=helper_json(['--list-devices']);devices=value.get('devices')
    if not isinstance(devices,list) or len(devices)>256:raise CaptureError(6)
    for device in devices:
        if (not isinstance(device,dict) or not isinstance(device.get('id'),str) or
            not 1<=len(device['id'])<=2048 or not isinstance(device.get('name'),str) or len(device['name'])>4096):
            raise CaptureError(6)
    return devices

def load_capture(config_path=None):
    path=Path(config_path) if config_path is not None else secure_host.root_path()/'host.json'
    try:
        if path.stat().st_size>65536:raise ValueError
        value=json.loads(path.read_text(encoding='utf-8'));source=value.get('capture')
    except (OSError,ValueError,AttributeError) as exc:raise CaptureError(1) from exc
    if (not isinstance(source,dict) or source.get('format')!=1 or source.get('mode')!='soloist-process' or
        not isinstance(source.get('device_id'),str) or not 1<=len(source['device_id'])<=2048 or
        not isinstance(source.get('device_name'),str) or len(source['device_name'])>4096):raise CaptureError(1)
    if source.get('route_verified') is not True:raise CaptureError(7)
    return source

def runtime_process(root=None):
    root=Path(root) if root is not None else secure_host.root_path();path=root/'soloist-runtime.json'
    try:
        if path.stat().st_size>65536:raise ValueError
        value=json.loads(path.read_text(encoding='utf-8'))
        if (value.get('format')!=1 or type(value.get('pid')) is not int or not 0<value['pid']<=0xffffffff or
            type(value.get('created')) is not int or not 0<value['created']<2**64 or
            not isinstance(value.get('exe'),str) or not 1<=len(value['exe'])<=32760):raise ValueError
        # Only the executable chosen by this installation may be targeted.
        config=json.loads((root/'host.json').read_text(encoding='utf-8'))
        if os.path.normcase(os.path.abspath(config['soloist_exe']))!=os.path.normcase(os.path.abspath(value['exe'])):raise ValueError
        return value
    except (OSError,ValueError,TypeError,KeyError,AttributeError) as exc:
        try:
            status=root/'soloist-status.json'
            if status.stat().st_size<=16384:
                state=json.loads(status.read_text(encoding='utf-8'))
                configured=json.loads((root/'host.json').read_text(encoding='utf-8'))['soloist_exe']
                if state.get('format')==1 and state.get('code')==10 and state.get('exe')==configured:raise CaptureError(8)
        except (OSError,ValueError,TypeError,KeyError,AttributeError):pass
        raise CaptureError(3) from exc

def process_args(device,process):
    return ['--device',device['device_id'],'--pid',str(process['pid']),
            '--created',str(process['created']),'--exe',process['exe']]

def probe(device,root=None):return helper_json(['--probe',*process_args(device,runtime_process(root))])

def source_status(code=0,source=None,root=None,state='ready'):
    root=Path(root) if root is not None else secure_host.root_path()
    value={'format':1,'updated':time.time(),'code':code,'state':state,
           'message':ERRORS.get(code,''),'mode':'soloist-process'}
    if source:value.update(device_id=source['device_id'],device_name=source['device_name'])
    secure_host.atomic_write(root/'capture-status.json',(json.dumps(value,indent=2)+'\n').encode())

def capture_block_reason(root=None):
    """Control helper: pause on a current route/device error; never leak a key."""
    root=Path(root) if root is not None else secure_host.root_path()
    try:source=load_capture(root/'host.json')
    except CaptureError as exc:return exc.code,str(exc)
    try:
        path=root/'capture-status.json'
        if path.stat().st_size>16384:raise ValueError
        value=json.loads(path.read_text(encoding='utf-8'))
        if value.get('device_id') in (None,source['device_id']) and value.get('code') in ERRORS:
            return value['code'],ERRORS[value['code']]
    except (OSError,ValueError,TypeError):pass
    return 0,''

class NativeSource:
    """Own one hash-verified helper for one already authenticated audio session."""
    def __init__(self,config_path=None,gain=.5,stats=None):
        self.process=None;self.job=None;self.reader=None;self.start_thread=None;self.error=None;self.closed=False
        self.source=None;self.stats=stats if stats is not None else {};self.gain=gain;self.ready=threading.Event()
        if not math.isfinite(gain) or not 0<=gain<=2:raise ValueError('Gain must be between 0 and 2')
        if sys.platform!='win32':raise CaptureError(5)
        try:
            self.source=load_capture(config_path);root=Path(config_path).parent if config_path else secure_host.root_path()
            self.root=root;process=runtime_process(root)
            self.job=windows_host.OwnedProcessJob()
            options=process_options();options['creationflags']|=subprocess.CREATE_NO_WINDOW
            environment=os.environ.copy();environment.pop('SOLOIST_API_KEY',None)
            self.process=subprocess.Popen([str(helper_path()),'--capture',*process_args(self.source,process)],
                stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=environment,bufsize=0,**options)
            try:self.job.assign(self.process)
            except RuntimeError:
                # A fast, already-exited helper still has a typed startup error
                # in its pipe. No live process remains to contain in that case.
                if self.process.poll() is None:raise
            self.reader=threading.Thread(target=self._events,daemon=True,name='soloist-capture-events');self.reader.start()
            self.handshake=None
            self.start_thread=threading.Thread(target=self._startup,daemon=True,name='soloist-capture-start');self.start_thread.start()
            if not self.ready.wait(6):raise CaptureError(6,'Capture startup timed out.')
            if self.error:raise self.error
            if self.handshake is None:raise CaptureError(6)
            source_status(0,self.source,root)
            print('Capturing only Soloist process tree; virtual output: '+self.source['device_name'],flush=True)
        except BaseException as exc:
            if isinstance(exc,CaptureError):
                try:source_status(exc.code,self.source,Path(config_path).parent if config_path else None,state='blocked')
                except OSError:pass
            self.close();raise
    def _startup(self):
        try:
            raw=self._exact(HEADER.size)
            tag,version,code,hr=HEADER.unpack(raw)
            if tag!=b'VACP' or version!=1:raise CaptureError(6,'Wrong native capture format.')
            if code:raise CaptureError(code,f'Windows error 0x{hr:08X}.' if hr else None)
            self.handshake=raw
        except Exception as exc:self.error=exc if isinstance(exc,CaptureError) else CaptureError(6)
        finally:self.ready.set()
    def _events(self):
        try:
            while True:
                line=self.process.stderr.readline(8193)
                if not line:break
                if len(line)>8192:
                    while line and not line.endswith(b'\n'):line=self.process.stderr.readline(8193)
                    continue
                try:value=json.loads(line)
                except (ValueError,UnicodeError):continue
                if not isinstance(value,dict):continue
                if value.get('event')=='error' and value.get('code') in ERRORS:
                    self.error=CaptureError(value['code'])
                    source_status(self.error.code,self.source,self.root,state='blocked')
                elif value.get('event')=='discontinuity' and type(value.get('count')) is int:
                    count=value['count']
                    if 0<=count<=0xffffffff:self.stats['discontinuities']=count
        except (OSError,ValueError,AttributeError):pass
    def _exact(self,size):
        data=bytearray()
        while len(data)<size:
            part=self.process.stdout.read(size-len(data))
            if not part:
                if self.reader and self.reader is not threading.current_thread():self.reader.join(.1)
                raise self.error or CaptureError(6,'Capture helper stopped.')
            data.extend(part)
        return bytes(data)
    def blocks(self):
        import numpy as np
        try:
            while not self.closed:
                raw=self._exact(4096)
                if self.error:raise self.error
                if self.gain==1:yield raw
                else:
                    samples=np.frombuffer(raw,dtype='<i2').astype(np.float32)
                    yield np.ascontiguousarray(np.clip(samples*self.gain,-32768,32767),dtype='<i2').tobytes()
        except CaptureError as exc:
            if not self.closed:
                source_status(exc.code,self.source,self.root,state='blocked');raise
    def close(self):
        if self.closed:return
        self.closed=True
        try:stop_process(self.process)
        finally:
            if self.job:self.job.close();self.job=None
            if self.start_thread:self.start_thread.join(1)
            if self.reader:self.reader.join(1)
            if self.process:
                for stream in (self.process.stdout,self.process.stderr):
                    if stream:stream.close()

def open_source(config_path=None,gain=.5,stats=None):return NativeSource(config_path,gain,stats)
