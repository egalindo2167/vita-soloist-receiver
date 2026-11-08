#!/usr/bin/env python3
"""Optional ngrok TCP tunnels. Provider forwards opaque, paired TLS sessions."""
import argparse
import getpass
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
from urllib.parse import urlsplit
from urllib.request import build_opener,ProxyHandler,HTTPRedirectHandler
import secure_host
import windows_host
from start_soloist import stop_process,process_options

HERE=Path(__file__).resolve().parent
PROFILE_NAME='remote-host.txt'
MAX_API_BYTES=65536

def root_path():return secure_host.root_path()

def endpoint(value):
    if not isinstance(value,str) or len(value)>280 or any(c.isspace() for c in value):
        raise ValueError('Expected a tcp://hostname:port endpoint')
    parsed=urlsplit(value)
    try:port=parsed.port
    except ValueError:raise ValueError('Invalid tunnel port') from None
    host=parsed.hostname
    if parsed.scheme!='tcp' or not host or parsed.username is not None or parsed.password is not None or parsed.path or parsed.query or parsed.fragment:
        raise ValueError('Use a raw tcp://hostname:port address, not an HTTP/TLS URL')
    if not port or not 1<=port<=65535 or not host_valid(host):raise ValueError('Invalid tunnel hostname or port')
    return host.lower(),port

def host_valid(host):
    if not host or len(host)>253:return False
    labels=host.split('.')
    if not all(re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?',label) for label in labels):return False
    if re.fullmatch(r'[0-9.]+',host):
        if len(labels)!=4 or any(len(p)>1 and p.startswith('0') or int(p)>255 for p in labels):return False
        if host in ('0.0.0.0','255.255.255.255'):return False
    return True

def profile_bytes(audio,controls):
    ah,ap=endpoint(audio);ch,cp=endpoint(controls)
    return f'VART1\naudio_host={ah}\naudio_port={ap}\ncontrol_host={ch}\ncontrol_port={cp}\n'.encode('ascii')

def export_profile(audio,controls,root=None):
    root=Path(root) if root is not None else root_path()
    path=root/'remote'/PROFILE_NAME;data=profile_bytes(audio,controls)
    try:changed=path.read_bytes()!=data
    except FileNotFoundError:changed=True
    if changed:secure_host.atomic_write(path,data)
    return path,changed

def config_text(api_port,audio_url="tcp://",control_url="tcp://"):
    if not 1<=api_port<=65535:raise ValueError('Invalid local API port')
    for url in (audio_url,control_url):
        if url!='tcp://':endpoint(url)
    if audio_url==control_url and audio_url!='tcp://':raise ValueError('Use two different reserved TCP addresses')
    # Only these two loopback upstreams are exposed, never Soloist's local API.
    # Authtoken is passed in the agent process environment, not this file/argv.
    return f'''version: 3
agent:
  web_addr: 127.0.0.1:{api_port}
  console_ui: false
endpoints:
  - name: vita-audio
    url: {audio_url}
    upstream:
      url: 127.0.0.1:48152
  - name: vita-controls
    url: {control_url}
    upstream:
      url: 127.0.0.1:48153
'''

def free_api_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));return sock.getsockname()[1]

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise OSError('Local agent API redirects are not allowed')

def read_agent(api_port):
    # No inherited HTTP proxy: credentials/endpoints are read only from loopback.
    opener=build_opener(ProxyHandler({}),NoRedirect())
    with opener.open(f'http://127.0.0.1:{api_port}/api/endpoints',timeout=1) as response:
        raw=response.read(MAX_API_BYTES+1)
    if len(raw)>MAX_API_BYTES:raise ValueError('Agent API response exceeds limit')
    return json.loads(raw)

def agent_endpoints(value):
    if not isinstance(value,dict) or not isinstance(value.get('endpoints'),list) or len(value['endpoints'])>8:
        raise ValueError('Invalid local agent API response')
    found={}
    expected={'vita-audio':48152,'vita-controls':48153}
    for item in value['endpoints']:
        if not isinstance(item,dict):raise ValueError('Invalid agent endpoint')
        name=item.get('name')
        if name not in expected:continue
        upstream=item.get('upstream')
        if name in found or not isinstance(upstream,dict):raise ValueError('Unexpected agent endpoint')
        addr=upstream.get('url')
        if addr not in (f'127.0.0.1:{expected[name]}',f'tcp://127.0.0.1:{expected[name]}'):
            raise ValueError('Tunnel points to an unexpected upstream')
        url=item.get('url');endpoint(url);found[name]=url
    if len(found)!=2:return None
    if found['vita-audio']==found['vita-controls']:raise ValueError('Audio and controls need separate TCP endpoints')
    return found['vita-audio'],found['vita-controls']

def load_settings(root=None):
    root=Path(root) if root is not None else root_path()
    path=root/'tunnel.json'
    if path.stat().st_size>16384:raise ValueError('Tunnel settings exceed limit')
    value=json.loads(path.read_text(encoding='utf-8'))
    if value.get('format')!=1 or not isinstance(value.get('token_dpapi'),str):raise ValueError('Run Setup Tunnel.cmd first')
    if not isinstance(value.get('ngrok_exe'),str) or not Path(value['ngrok_exe']).is_file():
        raise RuntimeError('ngrok.exe is missing. Run Setup Tunnel.cmd to select it again.')
    return value

def find_agent(explicit=None):
    candidates=[explicit] if explicit else [str(HERE/'ngrok.exe'),str(root_path()/'app/bin/ngrok.exe'),shutil.which('ngrok')]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():return Path(candidate).resolve()
    raise RuntimeError('Download official Windows ngrok.exe and place it beside Setup Tunnel.cmd, or install ngrok on PATH.')

def check_agent(executable,configuration):
    options={'creationflags':subprocess.CREATE_NO_WINDOW} if sys.platform=='win32' else {}
    version=subprocess.run([str(executable),'version'],capture_output=True,text=True,timeout=10,check=True,**options)
    if not re.search(r'\b3\.\d+',version.stdout):raise RuntimeError('Use the current ngrok v3 Windows agent.')
    subprocess.run([str(executable),'config','check','--config',str(configuration)],capture_output=True,text=True,timeout=10,check=True,**options)

def write_status(root,**fields):
    secure_host.atomic_write(root/'tunnel-status.json',(json.dumps({'format':1,'updated':time.time(),**fields},indent=2)+'\n').encode())

def pump_agent(process,token):
    try:
        while True:
            line=process.stdout.readline(MAX_API_BYTES+1)
            if not line:break
            if len(line)>MAX_API_BYTES:
                while line and not line.endswith('\n'):line=process.stdout.readline(MAX_API_BYTES+1)
                print('ngrok: oversized log line discarded',flush=True);continue
            print('ngrok: '+line.rstrip().replace(token,'<redacted>'),flush=True)
    except (OSError,ValueError):pass
    finally:process.stdout.close()

def run(stop=windows_host.host_stop_requested,root=None):
    root=Path(root) if root is not None else root_path()
    settings=load_settings(root);token=windows_host.unprotect_key(settings['token_dpapi'])
    if not token or len(token)>4096:raise ValueError('Invalid saved ngrok authtoken')
    api_port=free_api_port();configuration=root/'ngrok-vita.yml'
    secure_host.atomic_write(configuration,config_text(api_port,settings.get('audio_url','tcp://'),settings.get('control_url','tcp://')).encode())
    environment=os.environ.copy();environment.pop('SOLOIST_API_KEY',None)
    environment['NGROK_AUTHTOKEN']=token
    # Ignore provider credentials inherited from the parent; only authtoken is needed.
    environment.pop('NGROK_API_KEY',None)
    options=process_options()
    if sys.platform=='win32':options['creationflags']|=subprocess.CREATE_NO_WINDOW
    process=None;reader=None;failure=None;job=None
    try:
        write_status(root,running=False,message='Starting ngrok TCP tunnels...')
        if sys.platform=='win32':job=windows_host.OwnedProcessJob()
        process=subprocess.Popen([settings['ngrok_exe'],'start','--all','--config',str(configuration),
                                  '--log','stdout','--log-format','json'],
                                 env=environment,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                                 text=True,encoding='utf-8',errors='replace',**options)
        if job:job.assign(process)
        reader=threading.Thread(target=pump_agent,args=(process,token),daemon=True,name='ngrok-output');reader.start()
        next_poll=0;started=time.monotonic();exported=False
        print('Starting two raw TCP tunnels. Audio/control remain protected by app TLS pairing.',flush=True)
        while not stop():
            if process.poll() is not None:raise RuntimeError(f'ngrok exited ({process.returncode}). Check host.log for its error; TCP access may require account verification.')
            now=time.monotonic()
            if now>=next_poll:
                next_poll=now+2
                try:urls=agent_endpoints(read_agent(api_port))
                except (OSError,ValueError):urls=None
                if urls:
                    path,changed=export_profile(*urls,root)
                    write_status(root,running=True,audio=urls[0],controls=urls[1],profile=str(path),message='TCP tunnels available')
                    if changed or not exported:
                        print(f'Audio: {urls[0]}\nControls: {urls[1]}\nVita profile: {path}',flush=True)
                        print('Copy remote-host.txt by VitaShell USB if the addresses changed; then reopen the Vita app.',flush=True)
                    exported=True
                else:
                    write_status(root,running=False,message='Waiting for both ngrok endpoints; see host.log for provider errors.')
                    if not exported and now-started>60:raise RuntimeError('ngrok did not publish both TCP endpoints within 60 seconds; see host.log.')
            time.sleep(.1)
    except BaseException as exc:
        failure=str(exc).replace(token,'<redacted>');raise
    finally:
        try:stop_process(process)
        finally:
            if job:job.close()
        if reader:reader.join(2)
        elif process is not None and process.stdout:process.stdout.close()
        write_status(root,running=False,message=failure or 'Tunnel stopped; saved endpoint addresses may no longer be valid.')

def show_profile(open_folder=False):
    root=root_path();path=root/'remote'/PROFILE_NAME
    try:
        value=json.loads((root/'tunnel-status.json').read_text(encoding='utf-8'))
        fresh=0<=time.time()-float(value.get('updated',0))<10 and value.get('running')
        print('Tunnels are available.' if fresh else 'Tunnels are not confirmed active. Start Tunnel.cmd or check host.log.')
        print(value.get('message',''))
        if fresh:print('Audio:',value.get('audio',''), '\nControls:',value.get('controls',''))
    except (OSError,ValueError,TypeError):print('No tunnel status yet. Run Setup Tunnel.cmd / Start Tunnel.cmd.')
    if path.is_file():
        print('Public endpoint profile:',path)
        print('Copy to ux0:data/vita-audio-receiver/remote-host.txt with VitaShell USB; pairing file stays separate.')
        if open_folder and sys.platform=='win32':os.startfile(path.parent)
    return path.is_file()

def wait_profile(open_folder=True):
    not_before=time.time();available=False;deadline=time.monotonic()+20
    while time.monotonic()<deadline:
        try:
            state=json.loads((root_path()/'tunnel-status.json').read_text())
            if state.get('running') and state['updated']>=not_before:
                available=True;break
        except (OSError,ValueError,KeyError,TypeError):pass
        time.sleep(.5)
    show_profile(open_folder and available)
    if not available:print('The tunnel is still starting or failed. Check Tunnel Status.cmd and host.log before copying the profile.')
    print('Keep the PC awake and signed in. Once copied, select REMOTE with Triangle on the Vita waiting screen.')

def setup(audio_url=None,control_url=None):
    if sys.platform!='win32':raise RuntimeError('Tunnel setup is for Windows.')
    import host
    secure_host.require_tls();value=host.load_config();root=root_path();app=Path(value['app_dir'])
    if not (app/'tunnel.py').is_file():raise RuntimeError('Run Upgrade Host.cmd from this release first.')
    try:agent=find_agent()
    except RuntimeError:
        print('Get the Windows agent from https://ngrok.com/downloads/windows')
        agent=find_agent(input('Full path to your official ngrok.exe: ').strip().strip('"'))
    previous={}
    try:previous=load_settings()
    except (OSError,ValueError,RuntimeError):pass
    audio_url=audio_url if audio_url is not None else previous.get('audio_url','tcp://')
    control_url=control_url if control_url is not None else previous.get('control_url','tcp://')
    check_path=root/'ngrok-vita-check.yml';secure_host.atomic_write(check_path,config_text(free_api_port(),audio_url,control_url).encode())
    try:check_agent(agent,check_path)
    finally:check_path.unlink(missing_ok=True)
    print('Use the ngrok AUTHTOKEN from its dashboard, not an ngrok API key or Soloist key.')
    print('ngrok TCP endpoints require account/payment-method verification. Check its data-transfer limits before streaming.')
    token=getpass.getpass('ngrok authtoken (hidden; blank keeps the saved token): ').strip()
    if token:
        if len(token)>4096 or any(c.isspace() for c in token):raise ValueError('Invalid ngrok authtoken')
        protected=windows_host.protect_key(token)
    elif previous:protected=previous['token_dpapi'];windows_host.unprotect_key(protected)
    else:raise ValueError('An ngrok authtoken is required for first setup.')
    # A portable download is copied into the installed app, so deleting the
    # extracted receiver ZIP does not break sign-in startup. Store aliases stay put.
    pending=None
    try:
        if 'windowsapps' not in str(agent).lower():
            installed=app/'bin/ngrok.exe';installed.parent.mkdir(parents=True,exist_ok=True)
            if agent!=installed.resolve():
                pending=installed.with_name('ngrok-update.exe');shutil.copy2(agent,pending)
            agent=installed
        host.stop_running()
        if pending:os.replace(pending,agent)
    finally:
        if pending:pending.unlink(missing_ok=True)
    secure_host.atomic_write(root/'tunnel.json',(json.dumps({'format':1,'ngrok_exe':str(agent),'token_dpapi':protected,'audio_url':audio_url,'control_url':control_url},indent=2)+'\n').encode())
    value.update(tunnel_enabled=True,funnel_enabled=False);host.save_config(value);host.start_background();wait_profile()

def enable(enabled):
    import host
    secure_host.require_tls();value=host.load_config()
    if enabled:load_settings()
    if bool(value.get('tunnel_enabled'))!=enabled or enabled and value.get('funnel_enabled'):
        host.stop_running();value['tunnel_enabled']=enabled
        if enabled:value['funnel_enabled']=False
        host.save_config(value)
    host.start_background()
    if enabled:wait_profile()
    else:print('ngrok disabled. The host and any separately selected Funnel option keep their saved settings.')

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    actions=parser.add_mutually_exclusive_group(required=True)
    for name in ('setup','enable','disable','run','status','export'):actions.add_argument('--'+name,action='store_true')
    parser.add_argument('--audio-url',help='Optional reserved raw TCP address, or tcp:// for random')
    parser.add_argument('--control-url',help='Optional reserved raw TCP address, or tcp:// for random')
    args=parser.parse_args(argv)
    if (args.audio_url or args.control_url) and not args.setup:parser.error('Reserved endpoint URLs are configured with --setup')
    try:
        if args.run:run()
        elif args.setup:setup(args.audio_url,args.control_url)
        elif args.enable:enable(True)
        elif args.disable:enable(False)
        else:show_profile(args.export)
        return 0
    except KeyboardInterrupt:return 0
    except (OSError,RuntimeError,ValueError,KeyError,subprocess.SubprocessError) as exc:
        # No submitted token is included in errors or process command lines.
        if isinstance(exc,subprocess.CalledProcessError):
            print('Tunnel error: ngrok config check failed. Install the current ngrok v3 Windows agent.',file=sys.stderr)
        else:print(f'Tunnel error: {exc}',file=sys.stderr)
        return 1

if __name__=='__main__':
    if sys.platform=='win32':
        import signal
        signal.signal(signal.SIGBREAK,signal.default_int_handler)
    raise SystemExit(main())
