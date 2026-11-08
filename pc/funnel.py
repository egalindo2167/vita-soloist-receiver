#!/usr/bin/env python3
"""Tailscale Funnel: two owned foreground TCP routes, preserving paired TLS."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import threading
import time
import secure_host
import windows_host
from start_soloist import process_options,stop_process
from tunnel import export_profile,host_valid,PROFILE_NAME

PORTS={443:48152,8443:48153}
MAX_JSON=262144

def root_path():return secure_host.root_path()

def find_cli(explicit=None):
    candidates=[explicit] if explicit else [shutil.which('tailscale')]+[
        str(Path(os.environ.get(name,'C:/Program Files'))/'Tailscale/tailscale.exe')
        for name in ('ProgramFiles','ProgramW6432')]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():return Path(candidate).resolve()
    raise RuntimeError('Install Tailscale for Windows from https://tailscale.com/download/windows, sign in, then run Setup Funnel.cmd again.')

def cli(executable,*args):
    options={'creationflags':subprocess.CREATE_NO_WINDOW} if sys.platform=='win32' else {}
    result=subprocess.run([str(executable),*args],capture_output=True,text=True,encoding='utf-8',
                          errors='replace',timeout=15,**options)
    if result.returncode:
        detail=(result.stderr or result.stdout).strip()[:1500]
        raise RuntimeError('Tailscale command failed: '+(detail or str(result.returncode)))
    if len(result.stdout)>MAX_JSON or len(result.stderr)>MAX_JSON:raise ValueError('Tailscale response exceeds limit')
    # Current official CLI writes successful --help output to stderr.
    return result.stdout or result.stderr

def check_cli(executable):
    version=cli(executable,'version')
    match=re.search(r'(?m)^\s*(\d+)\.(\d+)\.(\d+)',version)
    if not match or tuple(map(int,match.groups()))<(1,52,0):
        raise RuntimeError('Install a current Tailscale Windows release (1.52 or newer).')
    help_text=cli(executable,'funnel','--help')
    if '--tcp' not in help_text or '--yes' not in help_text:
        raise RuntimeError('This Tailscale CLI lacks the required Funnel TCP flags. Update Tailscale.')

def node_name(executable):
    value=json.loads(cli(executable,'status','--json'))
    if not isinstance(value,dict) or value.get('BackendState')!='Running':
        raise RuntimeError('Tailscale is not connected. Open Tailscale on this PC and sign in/connect first.')
    me=value.get('Self')
    name=me.get('DNSName','') if isinstance(me,dict) else ''
    if not isinstance(name,str):raise ValueError('Invalid Tailscale DNS name')
    name=name.removesuffix('.').lower()
    if not host_valid(name) or not name.endswith('.ts.net') or len(name.split('.'))<4:
        raise RuntimeError('No usable Tailscale hostname. Enable MagicDNS for the tailnet and reconnect Tailscale.')
    return name

def configuration(executable):
    value=json.loads(cli(executable,'funnel','status','--json'))
    if value is None:return {}
    if not isinstance(value,dict):raise ValueError('Invalid Tailscale Serve/Funnel configuration')
    return value

def blocks(value):
    """Inspect both persistent and ephemeral configs; never rewrite either."""
    if not isinstance(value,dict):raise ValueError('Invalid Tailscale configuration block')
    yield None,value
    foreground=value.get('Foreground')
    if foreground is None:foreground={}
    if not isinstance(foreground,dict) or len(foreground)>128:raise ValueError('Invalid Tailscale foreground sessions')
    for session,block in foreground.items():
        if not isinstance(session,str) or not session or not isinstance(block,dict) or block.get('Foreground'):
            raise ValueError('Invalid Tailscale foreground configuration')
        yield session,block

def claims(value,port):
    found=[]
    for session,block in blocks(value):
        maps={}
        for key in ('TCP','Web','AllowFunnel'):
            maps[key]=block.get(key)
            if maps[key] is None:maps[key]={}
            if not isinstance(maps[key],dict):raise ValueError('Invalid Tailscale '+key+' configuration')
        used=str(port) in maps['TCP'] or any(
            str(key).rsplit(':',1)[-1]==str(port) for field in ('Web','AllowFunnel') for key in maps[field])
        if used:found.append((session,block))
    return found

def route_session(value,hostname,port):
    found=claims(value,port)
    if not found:return None
    if len(found)!=1:raise RuntimeError(f'Tailscale port {port} has conflicting routes; configuration left untouched.')
    session,block=found[0];handler=(block.get('TCP') or {}).get(str(port))
    valid=(session is not None and isinstance(handler,dict) and
           handler.get('TCPForward')==f'127.0.0.1:{PORTS[port]}' and
           not handler.get('TerminateTLS') and not handler.get('HTTPS') and not handler.get('HTTP') and
           not handler.get('ProxyProtocol') and
           not set(handler)-{'TCPForward','TerminateTLS','HTTPS','HTTP','ProxyProtocol'} and
           (block.get('AllowFunnel') or {}).get(f'{hostname}:{port}') is True and not block.get('Web'))
    if not valid:raise RuntimeError(f'Tailscale port {port} is used by another or incompatible route. Stop that route yourself; its configuration was left untouched.')
    return session

def ensure_available(value,owned=None):
    owned=owned or {}
    for port in PORTS:
        found=claims(value,port)
        if port in owned:
            if len(found)!=1 or found[0][0]!=owned[port]:
                raise RuntimeError(f'Owned Funnel route {port} changed. Restart the host after checking Funnel Status.cmd.')
        elif found:
            raise RuntimeError(f'Tailscale port {port} is already reserved by Serve/Funnel. Stop that route yourself, then retry. No existing configuration was changed.')

def command(executable,port):
    if port not in PORTS:raise ValueError('Invalid Funnel port')
    # No --bg: the daemon removes each route when its CLI watch session closes,
    # including a killed child. Do not terminate TLS or prepend PROXY headers.
    return [str(executable),'funnel','--yes',f'--tcp={port}',f'tcp://127.0.0.1:{PORTS[port]}']

def pump(process,port):
    try:
        while True:
            line=process.stdout.readline(8193)
            if not line:break
            if len(line)>8192:
                while line and not line.endswith('\n'):line=process.stdout.readline(8193)
                print(f'Funnel {port}: oversized output discarded',flush=True);continue
            print(f'Funnel {port}: '+line.rstrip(),flush=True)
    except (OSError,ValueError):pass
    finally:process.stdout.close()

class Routes:
    def __init__(self,executable,hostname,stop=lambda:False):
        self.executable=str(executable);self.hostname=hostname;self.stop=stop
        self.processes={};self.readers=[];self.sessions={};self.job=None
    def __enter__(self):return self
    def __exit__(self,*args):self.close()
    def start(self,timeout=60):
        ensure_available(configuration(self.executable))
        if sys.platform=='win32':self.job=windows_host.OwnedProcessJob()
        environment=os.environ.copy()
        for key in ('SOLOIST_API_KEY','NGROK_API_KEY','NGROK_AUTHTOKEN'):environment.pop(key,None)
        options=process_options()
        if sys.platform=='win32':options['creationflags']|=subprocess.CREATE_NO_WINDOW
        for port in PORTS:
            if self.stop():raise InterruptedError('Funnel startup cancelled')
            ensure_available(configuration(self.executable),self.sessions)
            process=subprocess.Popen(command(self.executable,port),env=environment,stdin=subprocess.DEVNULL,
                                     stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,
                                     encoding='utf-8',errors='replace',**options)
            self.processes[port]=process
            if self.job:self.job.assign(process)
            reader=threading.Thread(target=pump,args=(process,port),daemon=True,name=f'funnel-{port}')
            self.readers.append(reader);reader.start();deadline=time.monotonic()+timeout
            while not self.stop():
                self.check_processes()
                session=route_session(configuration(self.executable),self.hostname,port)
                if session:self.sessions[port]=session;break
                if time.monotonic()>=deadline:
                    raise RuntimeError('Funnel was not enabled in time. Run Setup Funnel.cmd and approve the Tailscale URL shown there; check MagicDNS/HTTPS/Funnel permissions.')
                time.sleep(.2)
            else:raise InterruptedError('Funnel startup cancelled')
        self.poll()
    def check_processes(self):
        for port,process in self.processes.items():
            if process.poll() is not None:
                raise RuntimeError(f'Funnel {port} exited ({process.returncode}); see output above or host.log. Run Setup Funnel.cmd if authorization is required.')
    def poll(self):
        self.check_processes();value=configuration(self.executable)
        for port in PORTS:
            if route_session(value,self.hostname,port)!=self.sessions.get(port) or port not in self.sessions:
                raise RuntimeError(f'Funnel {port} is no longer active. Check Tailscale, then restart the host.')
    def close(self):
        try:
            for process in self.processes.values():stop_process(process)
        finally:
            if self.job:self.job.close();self.job=None
            for reader in self.readers:reader.join(2)
            for process in self.processes.values():
                if process.stdout and not process.stdout.closed:process.stdout.close()
            self.processes.clear()

def write_status(root,**fields):
    secure_host.atomic_write(Path(root)/'funnel-status.json',(json.dumps({'format':1,'updated':time.time(),**fields},indent=2)+'\n').encode())

def endpoints(hostname):return f'tcp://{hostname}:443',f'tcp://{hostname}:8443'

def load_settings(root=None):
    root=Path(root) if root is not None else root_path();path=root/'funnel.json'
    if path.stat().st_size>16384:raise ValueError('Funnel settings exceed limit')
    value=json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(value,dict) or value.get('format')!=1 or not isinstance(value.get('tailscale_exe'),str):
        raise ValueError('Run Setup Funnel.cmd first')
    value['tailscale_exe']=str(find_cli(value['tailscale_exe']))
    return value

def run(stop=windows_host.host_stop_requested,root=None):
    root=Path(root) if root is not None else root_path();failure=None
    try:
        executable=load_settings(root)['tailscale_exe'];hostname=node_name(executable)
        write_status(root,running=False,message='Starting Tailscale Funnel...')
        with Routes(executable,hostname,stop) as routes:
            routes.start();exported=False;next_poll=0
            while not stop():
                if time.monotonic()>=next_poll:
                    next_poll=time.monotonic()+2;routes.poll()
                    if node_name(executable)!=hostname:raise RuntimeError('Tailscale hostname changed. Restart the host, then copy the new Remote profile.')
                    urls=endpoints(hostname);path,changed=export_profile(*urls,root)
                    write_status(root,running=True,audio=urls[0],controls=urls[1],profile=str(path),message='Both Funnel routes configured; public DNS/reachability still depends on Tailscale and the network.')
                    if changed or not exported:
                        print(f'Funnel audio: {urls[0]}\nFunnel controls: {urls[1]}\nVita profile: {path}',flush=True)
                        print('App TLS pairing and configured audio bitrate are unchanged. Copy the profile by USB, then choose REMOTE on Vita.',flush=True)
                    exported=True
                time.sleep(.1)
    except InterruptedError:
        if not stop():raise
    except BaseException as exc:failure=str(exc);raise
    finally:write_status(root,running=False,message=failure or 'Funnel stopped. Local host and saved settings are retained.')

def show_profile(open_folder=False):
    root=root_path();path=root/'remote'/PROFILE_NAME;fresh=False
    try:
        value=json.loads((root/'funnel-status.json').read_text(encoding='utf-8'))
        fresh=bool(value.get('running')) and 0<=time.time()-float(value.get('updated',0))<20
        print('Both Funnel routes are configured.' if fresh else 'Funnel is not confirmed active. Run Start Funnel.cmd or check host.log.')
        print(value.get('message',''))
        if fresh:print('Audio:',value.get('audio',''),'\nControls:',value.get('controls',''))
    except (OSError,ValueError,TypeError):print('No Funnel status yet. Run Setup Funnel.cmd first.')
    if path.is_file():
        print('Public endpoint profile:',path)
        print('Copy to ux0:data/vita-audio-receiver/remote-host.txt using VitaShell USB. Keep your existing vita-pairing.bin.')
        if open_folder and fresh and sys.platform=='win32':os.startfile(path.parent)
    return fresh and path.is_file()

def wait_profile(open_folder=True):
    not_before=time.time();deadline=time.monotonic()+35;available=False
    while time.monotonic()<deadline:
        try:
            state=json.loads((root_path()/'funnel-status.json').read_text(encoding='utf-8'))
            if state.get('running') and state['updated']>=not_before:available=True;break
        except (OSError,ValueError,KeyError,TypeError):pass
        time.sleep(.5)
    show_profile(open_folder and available)
    if not available:print('Check Funnel Status.cmd and host.log before copying. Initial public DNS can take up to 10 minutes.')

def setup():
    if sys.platform!='win32':raise RuntimeError('Funnel setup is for Windows.')
    import host
    secure_host.require_tls();value=host.load_config();root=root_path()
    if not (Path(value['app_dir'])/'funnel.py').is_file():raise RuntimeError('Run Upgrade Host.cmd from this release first.')
    executable=find_cli();check_cli(executable);hostname=node_name(executable)
    print('This enables public access to the paired audio/control listeners only. Pairing is still required.')
    print('If Tailscale prints an authorization URL, open it on this PC and approve Funnel/HTTPS for your tailnet.')
    print('Waiting up to 10 minutes for approval. Ctrl+C cancels. Existing Serve/Funnel routes are never reset.',flush=True)
    host.stop_running()
    try:
        with Routes(executable,hostname) as routes:
            routes.start(timeout=600)
            export_profile(*endpoints(hostname),root)
        secure_host.atomic_write(root/'funnel.json',(json.dumps({'format':1,'tailscale_exe':str(executable)},indent=2)+'\n').encode())
        value.update(funnel_enabled=True,tunnel_enabled=False);host.save_config(value)
    finally:host.start_background()
    print('Funnel saved. Audio codec/bitrate, Soloist login, favorites and device pairing were preserved.')
    wait_profile()

def enable(enabled):
    import host
    secure_host.require_tls();value=host.load_config()
    if enabled:load_settings()
    if bool(value.get('funnel_enabled'))!=enabled or enabled and value.get('tunnel_enabled'):
        host.stop_running();value['funnel_enabled']=enabled
        if enabled:value['tunnel_enabled']=False
        host.save_config(value)
    host.start_background()
    if enabled:wait_profile()
    else:print('Funnel disabled. The local host continues; pairing and Spotify settings are retained.')

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);actions=parser.add_mutually_exclusive_group(required=True)
    for name in ('setup','enable','disable','run','status','export'):actions.add_argument('--'+name,action='store_true')
    args=parser.parse_args(argv)
    try:
        if args.run:run()
        elif args.setup:setup()
        elif args.enable:enable(True)
        elif args.disable:enable(False)
        else:show_profile(args.export)
        return 0
    except KeyboardInterrupt:return 0
    except (OSError,RuntimeError,ValueError,KeyError,subprocess.SubprocessError) as exc:
        print(f'Funnel error: {exc}',file=sys.stderr);return 1

if __name__=='__main__':
    if sys.platform=='win32':
        import signal
        signal.signal(signal.SIGBREAK,signal.default_int_handler)
    raise SystemExit(main())
