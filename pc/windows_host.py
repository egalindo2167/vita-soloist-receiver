"""Windows-only key protection, single-instance control and sign-in shortcut."""
import base64
import ctypes
from ctypes import wintypes
from pathlib import Path
import os
import subprocess
import sys

NAME='Local\\VitaAudioReceiverHost'

class Blob(ctypes.Structure):
    _fields_=[('size',wintypes.DWORD),('data',ctypes.POINTER(ctypes.c_ubyte))]

def _windows():
    if sys.platform!='win32': raise RuntimeError('The persistent host setup requires Windows.')

def protect_key(key):
    _windows(); raw=key.encode('utf-8'); storage=ctypes.create_string_buffer(raw)
    source=Blob(len(raw),ctypes.cast(storage,ctypes.POINTER(ctypes.c_ubyte))); output=Blob()
    crypt=ctypes.WinDLL('crypt32',use_last_error=True); kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    crypt.CryptProtectData.argtypes=[ctypes.POINTER(Blob),wintypes.LPCWSTR,ctypes.c_void_p,
                                    ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(Blob)]
    crypt.CryptProtectData.restype=wintypes.BOOL
    kernel.LocalFree.argtypes=[ctypes.c_void_p]; kernel.LocalFree.restype=ctypes.c_void_p
    if not crypt.CryptProtectData(ctypes.byref(source),'Vita Audio Host',None,None,None,1,ctypes.byref(output)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:return base64.b64encode(ctypes.string_at(output.data,output.size)).decode('ascii')
    finally:kernel.LocalFree(ctypes.cast(output.data,ctypes.c_void_p))

def unprotect_key(encoded):
    _windows(); raw=base64.b64decode(encoded,validate=True); storage=ctypes.create_string_buffer(raw)
    source=Blob(len(raw),ctypes.cast(storage,ctypes.POINTER(ctypes.c_ubyte))); output=Blob()
    crypt=ctypes.WinDLL('crypt32',use_last_error=True); kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    crypt.CryptUnprotectData.argtypes=[ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.c_void_p,
                                      ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(Blob)]
    crypt.CryptUnprotectData.restype=wintypes.BOOL
    kernel.LocalFree.argtypes=[ctypes.c_void_p]; kernel.LocalFree.restype=ctypes.c_void_p
    if not crypt.CryptUnprotectData(ctypes.byref(source),None,None,None,None,1,ctypes.byref(output)):
        raise RuntimeError('Windows could not unlock the saved key. Run Setup Host again under this Windows account.')
    try:return ctypes.string_at(output.data,output.size).decode('utf-8')
    finally:kernel.LocalFree(ctypes.cast(output.data,ctypes.c_void_p))

class HostSignals:
    """Named handles are local to this signed-in Windows session."""
    def __init__(self,owner=False):
        _windows(); self.kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        k=self.kernel
        k.CreateMutexW.argtypes=[ctypes.c_void_p,wintypes.BOOL,wintypes.LPCWSTR]; k.CreateMutexW.restype=wintypes.HANDLE
        k.CreateEventW.argtypes=[ctypes.c_void_p,wintypes.BOOL,wintypes.BOOL,wintypes.LPCWSTR];k.CreateEventW.restype=wintypes.HANDLE
        k.OpenEventW.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.LPCWSTR];k.OpenEventW.restype=wintypes.HANDLE
        k.SetEvent.argtypes=[wintypes.HANDLE];k.SetEvent.restype=wintypes.BOOL
        k.ResetEvent.argtypes=[wintypes.HANDLE];k.ResetEvent.restype=wintypes.BOOL
        k.WaitForSingleObject.argtypes=[wintypes.HANDLE,wintypes.DWORD];k.WaitForSingleObject.restype=wintypes.DWORD
        k.CloseHandle.argtypes=[wintypes.HANDLE]; k.CloseHandle.restype=wintypes.BOOL
        self.mutex=self.event=None; self.already_running=False
        if owner:
            ctypes.set_last_error(0); self.mutex=k.CreateMutexW(None,False,NAME)
            if not self.mutex: raise ctypes.WinError(ctypes.get_last_error())
            self.already_running=ctypes.get_last_error()==183
            if not self.already_running:
                self.event=k.CreateEventW(None,True,False,NAME+'Stop')
                if not self.event: self.close();raise ctypes.WinError(ctypes.get_last_error())
                k.ResetEvent(self.event)
        else:self.event=k.OpenEventW(0x00100002,False,NAME+'Stop')
    def requested(self):return bool(self.event and self.kernel.WaitForSingleObject(self.event,0)==0)
    def stop(self):
        if not self.event:return False
        return bool(self.kernel.SetEvent(self.event))
    def close(self):
        for name in ('event','mutex'):
            value=getattr(self,name,None)
            if value:self.kernel.CloseHandle(value);setattr(self,name,None)

def host_stop_requested():
    """Children can exit cleanly even when launched without a console."""
    global _child_signals
    if sys.platform!='win32' or not os.environ.get('VITA_HOST_CHILD'):return False
    try:
        if _child_signals is None:_child_signals=HostSignals()
        return _child_signals.requested()
    except OSError:return False

_child_signals=None

def host_running():
    _windows(); kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.OpenMutexW.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.LPCWSTR]
    kernel.OpenMutexW.restype=wintypes.HANDLE
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    handle=kernel.OpenMutexW(0x00100000,False,NAME)
    if not handle:return False
    kernel.CloseHandle(handle);return True

def process_identity(process):
    """Bind capture to the owned Soloist PID, creation time and actual image."""
    _windows();kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.GetProcessTimes.argtypes=[wintypes.HANDLE,*([ctypes.POINTER(wintypes.FILETIME)]*4)]
    kernel.GetProcessTimes.restype=wintypes.BOOL
    kernel.QueryFullProcessImageNameW.argtypes=[wintypes.HANDLE,wintypes.DWORD,wintypes.LPWSTR,ctypes.POINTER(wintypes.DWORD)]
    kernel.QueryFullProcessImageNameW.restype=wintypes.BOOL
    times=[wintypes.FILETIME() for _ in range(4)];image=ctypes.create_unicode_buffer(32768);size=wintypes.DWORD(32768)
    if not kernel.GetProcessTimes(process._handle,*[ctypes.byref(t) for t in times]):raise ctypes.WinError(ctypes.get_last_error())
    if not kernel.QueryFullProcessImageNameW(process._handle,0,image,ctypes.byref(size)):raise ctypes.WinError(ctypes.get_last_error())
    created=(int(times[0].dwHighDateTime)<<32)|int(times[0].dwLowDateTime)
    return {'format':1,'pid':int(process.pid),'created':created,'exe':image.value}

def startup_shortcut():
    _windows()
    return Path(os.environ['APPDATA'])/'Microsoft'/'Windows'/'Start Menu'/'Programs'/'Startup'/'Vita Audio Host.lnk'

def pythonw_path():
    path=Path(sys.executable).with_name('pythonw.exe')
    if not path.is_file():raise RuntimeError('pythonw.exe was not found beside Python. Use a standard Windows Python installation.')
    return path

def install_startup(host_script):
    shortcut=startup_shortcut(); shortcut.parent.mkdir(parents=True,exist_ok=True)
    def ps(value):return "'"+str(value).replace("'","''")+"'"
    arguments=subprocess.list2cmdline([str(host_script),'--run'])
    script=(f'$s=New-Object -ComObject WScript.Shell; $l=$s.CreateShortcut({ps(shortcut)}); '
            f'$l.TargetPath={ps(pythonw_path())}; $l.Arguments={ps(arguments)}; '
            f'$l.WorkingDirectory={ps(host_script.parent)}; $l.Description="Vita Audio Host"; $l.Save()')
    subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',script],
                   check=True,capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW)
    return shortcut

def remove_startup():
    path=startup_shortcut(); path.unlink(missing_ok=True);return path

class OwnedProcessJob:
    """Kill owned native helper children if their manager exits (Windows)."""
    def __init__(self):
        _windows()
        class Basic(ctypes.Structure):
            _fields_=[('process_time',ctypes.c_int64),('job_time',ctypes.c_int64),
                      ('flags',ctypes.c_uint32),('min_working_set',ctypes.c_size_t),
                      ('max_working_set',ctypes.c_size_t),('active_processes',ctypes.c_uint32),
                      ('affinity',ctypes.c_size_t),('priority',ctypes.c_uint32),('scheduling',ctypes.c_uint32)]
        class IO(ctypes.Structure):
            _fields_=[('counts',ctypes.c_uint64*6)]
        class Extended(ctypes.Structure):
            _fields_=[('basic',Basic),('io',IO),('process_memory',ctypes.c_size_t),
                      ('job_memory',ctypes.c_size_t),('peak_process',ctypes.c_size_t),('peak_job',ctypes.c_size_t)]
        self.kernel=ctypes.WinDLL('kernel32',use_last_error=True);k=self.kernel
        k.CreateJobObjectW.argtypes=[ctypes.c_void_p,wintypes.LPCWSTR];k.CreateJobObjectW.restype=wintypes.HANDLE
        k.SetInformationJobObject.argtypes=[wintypes.HANDLE,ctypes.c_int,ctypes.c_void_p,ctypes.c_uint32]
        k.SetInformationJobObject.restype=wintypes.BOOL
        k.AssignProcessToJobObject.argtypes=[wintypes.HANDLE,wintypes.HANDLE];k.AssignProcessToJobObject.restype=wintypes.BOOL
        k.CloseHandle.argtypes=[wintypes.HANDLE];k.CloseHandle.restype=wintypes.BOOL
        self.handle=k.CreateJobObjectW(None,None)
        if not self.handle:raise RuntimeError('Could not create the helper process containment job')
        info=Extended();info.basic.flags=0x2000 # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not k.SetInformationJobObject(self.handle,9,ctypes.byref(info),ctypes.sizeof(info)):
            self.close();raise RuntimeError('Could not configure helper process containment')
    def assign(self,process):
        if not self.kernel.AssignProcessToJobObject(self.handle,int(process._handle)):
            raise RuntimeError('Could not contain the helper process; startup was cancelled')
    def close(self):
        if self.handle:self.kernel.CloseHandle(self.handle);self.handle=None
