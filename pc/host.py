#!/usr/bin/env python3
"""Install and run the persistent Windows host. The Vita initiates sessions."""
import argparse
import getpass
import importlib.util
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from start_soloist import find_soloist,storage_root,stop_process,DEFAULT_NAME
import windows_host as windows
import secure_host as security
from version import VERSION

HERE=Path(__file__).resolve().parent
DISCOVERY_PORT=48154
AUDIO_PORT=48152
CONTROL_PORT=48153

def data_root():
    return Path(os.environ.get('LOCALAPPDATA',Path.home()/'AppData'/'Local'))/'VitaAudioReceiver'

def load_config():
    value=json.loads((data_root()/'host.json').read_text(encoding='utf-8'))
    if value.get('format')!=1 or not value.get('key_dpapi'):raise ValueError('Run Setup Host to save a Soloist key.')
    if not Path(value['soloist_exe']).is_file():raise ValueError('The saved Soloist executable is missing. Run Setup Host again.')
    return value

def save_config(value):
    root=data_root();root.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile('w',encoding='utf-8',dir=root,delete=False) as f:
        json.dump(value,f,indent=2); f.write('\n'); temporary=f.name
    os.replace(temporary,root/'host.json')

def install_files():
    destination=data_root()/'app';destination.mkdir(parents=True,exist_ok=True)
    if HERE!=destination.resolve():
        for file in HERE.iterdir():
            if file.is_file() and file.suffix.lower() in ('.py','.txt','.cmd','.lock'):
                shutil.copy2(file,destination/file.name)
        if (HERE/'soloist').is_dir():
            shutil.copytree(HERE/'soloist',destination/'soloist',dirs_exist_ok=True)
        if (HERE/'native').is_dir():
            shutil.copytree(HERE/'native',destination/'native',dirs_exist_ok=True)
    favorites=data_root()/'favorites.json'
    if not favorites.exists():
        source=HERE/'favorites.json'
        favorites.write_text(source.read_text(encoding='utf-8') if source.exists() else '[]\n',encoding='utf-8')
    return destination

def listener_bind(value):
    scope=value.get('listen_scope','auto')
    if scope not in ('auto','both','remote'):raise ValueError('Unknown network exposure setting')
    remote=scope=='remote' or scope=='auto' and (value.get('funnel_enabled') or value.get('tunnel_enabled'))
    return '127.0.0.1' if remote else '0.0.0.0'

def set_network(scope):
    value=load_config();listener_bind({**value,'listen_scope':scope})
    stop_running();value['listen_scope']=scope;save_config(value);start_background()
    print('Receiver listeners:',listener_bind(value),'; Soloist API remains loopback only.')

def validate_audio(codec,bitrate):
    import opus_audio
    if codec not in ('pcm','opus'):raise ValueError('Audio codec must be pcm or opus')
    opus_audio.header(bitrate)
    if codec=='opus':
        with opus_audio.Encoder(bitrate) as encoder:
            encoder.encode(b'\0'*opus_audio.PCM_BYTES)

def stop_running():
    if not windows.host_running():return
    signals=windows.HostSignals()
    try:signals.stop()
    finally:signals.close()
    print('Stopping the previous host...',flush=True)
    deadline=time.monotonic()+20
    while windows.host_running() and time.monotonic()<deadline:time.sleep(0.2)
    if windows.host_running():raise RuntimeError('The previous host is still stopping. Try again shortly.')

def setup(autostart=False,codec='opus',bitrate=320):
    if sys.platform!='win32':raise RuntimeError('Setup Host is for Windows.')
    security.require_tls()
    for module in ('soundcard','numpy','websocket','PIL'):
        if importlib.util.find_spec(module) is None:
            raise RuntimeError('Install requirements-loopback.txt and requirements-soloist.txt with this Python first.')
    windows.pythonw_path() # Validate before changing the saved installation.
    validate_audio(codec,bitrate)
    stop_running()
    previous={}
    try:previous=load_config()
    except (OSError,ValueError,KeyError):pass
    try:executable=find_soloist(previous.get('soloist_exe')) if previous else find_soloist()
    except RuntimeError:
        entered=input('Full path to your official soloist.exe: ').strip().strip('"')
        executable=find_soloist(entered)
    print('Enter your personal Soloist key once. Windows will protect it for this Windows account.')
    key=getpass.getpass('Soloist API key (hidden; blank keeps an existing saved key): ').strip()
    if key:encrypted=windows.protect_key(key)
    elif previous:encrypted=previous['key_dpapi']; windows.unprotect_key(encrypted)
    else:raise ValueError('A Soloist API key is required for the first setup.')
    application=install_files()
    if executable.is_relative_to(HERE):executable=application/executable.relative_to(HERE)
    value={'format':1,'key_dpapi':encrypted,'soloist_exe':str(executable),
           'name':previous.get('name',DEFAULT_NAME),'gain':previous.get('gain',0.5),
           'capture_blocksize':previous.get('capture_blocksize',8192),
           'device':previous.get('device'),'app_dir':str(application),
           'audio_codec':codec,'opus_bitrate':bitrate,'tunnel_enabled':bool(previous.get('tunnel_enabled')),
           'funnel_enabled':bool(previous.get('funnel_enabled')),'listen_scope':previous.get('listen_scope','auto'),
           'capture':previous.get('capture')}
    save_config(value)
    if autostart:windows.install_startup(application/'host.py')
    print('Setup saved. Pairing and account data stay in the existing Soloist data directory.')
    print('Installed application:',application)
    print('Favorites:',data_root()/'favorites.json')
    print('Next, run Pair Vita.cmd once and copy its pairing file to the Vita with USB.')
    start_background()

def upgrade(codec=None,bitrate=None):
    """Upgrade an installed host without asking for its key or pairing again."""
    security.require_tls()
    value=load_config();windows.unprotect_key(value['key_dpapi'])
    codec=value.get('audio_codec','opus') if codec is None else codec
    bitrate=value.get('opus_bitrate',320) if bitrate is None else bitrate
    windows.pythonw_path();validate_audio(codec,bitrate)
    stop_running();application=install_files()
    executable=Path(value['soloist_exe'])
    if executable.is_relative_to(HERE):value['soloist_exe']=str(application/executable.relative_to(HERE))
    value.update(app_dir=str(application),audio_codec=codec,opus_bitrate=bitrate)
    save_config(value)
    if sys.platform=='win32' and windows.startup_shortcut().exists():windows.install_startup(application/'host.py')
    print('Existing device pairing is retained. Use Pair Vita.cmd only for a new or replacement device.')
    print(f'Host upgraded. Audio link: {codec.upper()}'+(f' {bitrate} kbps CBR.' if codec=='opus' else '.'))
    start_background()

def set_audio(codec,bitrate):
    security.require_tls()
    value=load_config();validate_audio(codec,bitrate)
    stop_running();value.update(audio_codec=codec,opus_bitrate=bitrate);save_config(value)
    print(f'Audio link set to {codec.upper()}'+(f' {bitrate} kbps CBR.' if codec=='opus' else '.'))
    start_background()

def start_background():
    security.require_tls()
    if windows.host_running():print('Vita Audio Host is already running.');return
    value=load_config();script=Path(value['app_dir'])/'host.py'
    subprocess.Popen([str(windows.pythonw_path()),str(script),'--run'],cwd=script.parent,
                     creationflags=subprocess.CREATE_NO_WINDOW)
    deadline=time.monotonic()+5
    while time.monotonic()<deadline:
        if windows.host_running():
            print('Vita Audio Host started. Open the Vita app to connect.')
            print('Logs:',data_root()/'host.log');return
        time.sleep(0.1)
    raise RuntimeError('The host did not start. Check host.log or run: py host.py --run')

class Redact(logging.Filter):
    def __init__(self,key):super().__init__();self.key=key
    def filter(self,record):
        record.msg=record.getMessage().replace(self.key,'<redacted>');record.args=();return True

def configure_logging(key):
    root=data_root();root.mkdir(parents=True,exist_ok=True)
    logger=logging.getLogger('vita-host');logger.setLevel(logging.INFO);logger.handlers.clear()
    handler=RotatingFileHandler(root/'host.log',maxBytes=2*1024*1024,backupCount=2,encoding='utf-8')
    handler.setFormatter(logging.Formatter('%(asctime)s %(message)s'));handler.addFilter(Redact(key));logger.addHandler(handler)
    if sys.stdout is not None:
        console=logging.StreamHandler(sys.stdout);console.addFilter(Redact(key));logger.addHandler(console)
    return logger

def discovery_server(stop,logger,bind='0.0.0.0',port=DISCOVERY_PORT,registry=None):
    registry=registry or security.Registry();gate=security.RateGate(rate=4,burst=8,global_rate=16,global_burst=32)
    while not stop():
        try:
            with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sock:
                sock.bind((bind,port));sock.settimeout(0.5)
                while not stop():
                    try:message,address=sock.recvfrom(256)
                    except socket.timeout:continue
                    if not gate.allow(address[0]):continue
                    try:response=security.discovery_reply(message,registry)
                    except security.SecurityError:continue
                    if response:sock.sendto(response,address)
        except OSError as exc:
            if not stop():logger.warning('Discovery unavailable: %s',exc);time.sleep(2)

def pump_output(process,name,logger):
    try:
        for line in process.stdout:
            text=line.rstrip()
            if text:logger.info('%s: %s',name,text)
    finally:process.stdout.close()

def child_commands(value,key):
    application=Path(value['app_dir']);root=storage_root();bind=listener_bind(value)
    soloist=[value['soloist_exe'],'--device-name',value['name'],'--api-key',key,
             '--data-dir',str(root/'data'),'--cache-dir',str(root/'cache'),'--cache-size','512',
             '--ws','127.0.0.1:0']
    audio=[sys.executable,str(application/'audio_host.py'),'--bind',bind,'--port',str(AUDIO_PORT),
           '--gain',str(value['gain']),'--capture-blocksize',str(value['capture_blocksize']),
           '--codec',value.get('audio_codec','pcm'),'--bitrate',str(value.get('opus_bitrate',320))]
    controls=[sys.executable,str(application/'soloist_bridge.py'),'--listen','--bind',bind,'--port',str(CONTROL_PORT),
              '--data-dir',str(root/'data'),'--favorites',str(data_root()/'favorites.json'),
              '--capture-root',str(data_root())]
    commands={'Soloist':soloist,'Audio':audio,'Controls':controls}
    audio.extend(['--capture-config',str(data_root()/'host.json')])
    if value.get('funnel_enabled'):commands['Funnel']=[sys.executable,str(application/'funnel.py'),'--run']
    elif value.get('tunnel_enabled'):commands['Tunnel']=[sys.executable,str(application/'tunnel.py'),'--run']
    return commands

def soloist_status(value,code=0):
    state={'format':1,'code':code,'state':'expired' if code==10 else 'running','exe':value['soloist_exe']}
    security.atomic_write(data_root()/'soloist-status.json',(json.dumps(state)+'\n').encode())

def run_host():
    security.require_tls()
    owner=windows.HostSignals(owner=True)
    if owner.already_running:owner.close();return 0
    children={};stop_thread=threading.Event();logger=None
    try:
        value=load_config();key=windows.unprotect_key(value['key_dpapi'])
        logger=configure_logging(key);logger.info('Vita Audio Host %s starting (paired TLS 1.3); waiting for Vita-initiated connections.',VERSION)
        validate_audio(value.get('audio_codec','pcm'),value.get('opus_bitrate',320))
        for directory in ('data','cache'):(storage_root()/directory).mkdir(parents=True,exist_ok=True)
        commands=child_commands(value,key)
        environment=os.environ.copy();environment.pop('SOLOIST_API_KEY',None)
        environment['VITA_HOST_CHILD']='1';environment['PYTHONUNBUFFERED']='1'
        stop=lambda:owner.requested() or stop_thread.is_set()
        if listener_bind(value)!='127.0.0.1':
            threading.Thread(target=discovery_server,args=(stop,logger),daemon=True,name='vita-discovery').start()
        retry={name:0.0 for name in commands};attempts={name:0 for name in commands};started={}
        while not stop():
            now=time.monotonic()
            for name,command in commands.items():
                process=children.get(name)
                if process is not None and process.poll() is not None:
                    code=process.returncode;children.pop(name)
                    logger.warning('%s exited (%s).',name,code)
                    if name=='Soloist':(data_root()/'soloist-runtime.json').unlink(missing_ok=True)
                    if name=='Soloist' and code==10:
                        soloist_status(value,10)
                        retry[name]=float('inf');logger.error('Soloist build expired. Install a newer official build and restart the host.')
                    else:
                        attempts[name]=0 if now-started[name]>60 else attempts[name]+1
                        retry[name]=now+min(60,2**min(attempts[name],6))
                if name not in children and now>=retry[name]:
                    options={'creationflags':subprocess.CREATE_NO_WINDOW|subprocess.CREATE_NEW_PROCESS_GROUP}
                    try:
                        process=subprocess.Popen(command,cwd=Path(value['soloist_exe']).parent if name=='Soloist' else value['app_dir'],
                              env=environment,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,
                              encoding='utf-8',errors='replace',bufsize=1,**options)
                        children[name]=process;started[name]=now
                        if name=='Soloist':
                            soloist_status(value)
                            try:
                                identity=windows.process_identity(process)
                                security.atomic_write(data_root()/'soloist-runtime.json',(json.dumps(identity)+'\n').encode())
                            except (OSError,RuntimeError):
                                (data_root()/'soloist-runtime.json').unlink(missing_ok=True)
                                logger.error('Could not verify the owned Soloist process; audio capture remains disabled.')
                        threading.Thread(target=pump_output,args=(process,name,logger),daemon=True).start()
                    except OSError as exc:retry[name]=now+10;logger.error('%s could not start: %s',name,exc)
            time.sleep(0.2)
    except KeyboardInterrupt:
        if logger:logger.info('Stopping from keyboard.')
    finally:
        owner.stop();stop_thread.set()
        for name in ('Funnel','Tunnel','Audio','Controls','Soloist'):
            process=children.get(name)
            if process is not None and name!='Soloist':
                try:process.wait(timeout=14 if name in ('Tunnel','Funnel') else 3)
                except subprocess.TimeoutExpired:pass
            stop_process(process)
        (data_root()/'soloist-runtime.json').unlink(missing_ok=True)
        owner.close()
        if logger:logger.info('Host stopped.')
    return 0

def pair_vita():
    security.require_tls()
    registry=security.Registry()
    identity,path=registry.pair()
    print('New Vita pairing created:',identity)
    print('Copy this file using VitaShell USB:',path)
    print('Destination: ux0:data/vita-audio-receiver/vita-pairing.bin')
    print('Close and reopen the Vita app. Treat this file like a password.')
    print('The matching PC export is deleted on its first authenticated connection. The protected registry is retained.')
    print('Pairing an additional Vita needs a different file. Manage Vitas.cmd revokes lost devices.')
    if sys.platform=='win32':os.startfile(path.parent)

def manage_vitas():
    registry=security.Registry();devices=registry.list()
    if not devices:print('No paired Vitas. Run Pair Vita.cmd.');return
    for index,device in enumerate(devices,1):print(f"{index}. {device['name']}  {device['id']}")
    choice=input('Number to revoke (blank cancels): ').strip()
    if not choice:return
    if not choice.isdecimal() or not 1<=int(choice)<=len(devices):raise ValueError('Invalid device number')
    identity=devices[int(choice)-1]['id']
    registry.revoke(identity)
    print('Vita revoked. Its audio and controls disconnect automatically; it cannot reconnect with the old file.')

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    action=parser.add_mutually_exclusive_group(required=True)
    for name in ('setup','upgrade','run','start','stop','status','remove-startup','pair-vita','manage-vitas','list-vitas'):action.add_argument('--'+name,action='store_true')
    action.add_argument('--audio-codec',choices=('opus','pcm'))
    action.add_argument('--network-scope',choices=('auto','both','remote'))
    action.add_argument('--revoke-vita',metavar='DEVICE_ID')
    parser.add_argument('--install-startup',action='store_true')
    parser.add_argument('--codec',choices=('opus','pcm'),help='Override setup/upgrade codec; upgrades normally keep the saved value')
    parser.add_argument('--bitrate',type=int,choices=(96,128,160,192,256,320),help='Override Opus bitrate; upgrades normally keep the saved value')
    args=parser.parse_args(argv)
    try:
        if sys.platform!='win32':raise RuntimeError('This persistent host is for Windows.')
        if args.setup:setup(args.install_startup,args.codec or 'opus',args.bitrate or 320)
        elif args.upgrade:upgrade(args.codec,args.bitrate)
        elif args.audio_codec:set_audio(args.audio_codec,args.bitrate or 320)
        elif args.network_scope:set_network(args.network_scope)
        elif args.run:return run_host()
        elif args.start:start_background()
        elif args.stop:
            signals=windows.HostSignals()
            try:print('Stop requested.' if signals.stop() else 'Host is not running.')
            finally:signals.close()
        elif args.pair_vita:pair_vita()
        elif args.manage_vitas:manage_vitas()
        elif args.list_vitas:
            for device in security.Registry().list():print(device['id'],device['name'])
        elif args.revoke_vita:
            if not security.Registry().revoke(args.revoke_vita):raise ValueError('Unknown paired Vita')
            print('Vita revoked.')
        elif args.status:
            print('Host is running.' if windows.host_running() else 'Host is not running.')
            value=load_config();codec=value.get('audio_codec','pcm')
            print('Configured audio link:',codec.upper(),f"{value.get('opus_bitrate',320)} kbps CBR" if codec=='opus' else '1536 kbps')
            source=value.get('capture') or {}
            print('Capture: Soloist process only; dedicated output:',source.get('device_name','NOT CONFIGURED - run Setup Audio.cmd'))
            print('Saved output ID:',source.get('device_id','none'),'; routing verified:',bool(source.get('route_verified')))
            from audio_source import capture_block_reason
            code,message=capture_block_reason(data_root())
            print('Capture state:',message if code else 'configured; run Audio Status.cmd for a live route check')
            addresses=sorted({item[4][0] for item in socket.getaddrinfo(socket.gethostname(),None,socket.AF_INET)
                              if not item[4][0].startswith('127.')})
            print('Security: TLS 1.3,',len(security.Registry().list()),'paired Vita(s).')
            print('Remote provider:', 'Tailscale Funnel' if value.get('funnel_enabled') else 'ngrok' if value.get('tunnel_enabled') else 'disabled')
            print('Receiver listener bind:',listener_bind(value),'(auto limits tunnels to loopback; --network-scope both enables LAN too)')
            print('PC IPv4 addresses:',', '.join(addresses) or 'No LAN address')
            print('Log:',data_root()/'host.log')
        elif args.remove_startup:windows.remove_startup();print('Automatic sign-in startup removed.')
        return 0
    except (OSError,RuntimeError,ValueError,KeyError,subprocess.SubprocessError) as exc:
        if args.run:
            try:
                root=data_root();root.mkdir(parents=True,exist_ok=True)
                with (root/'host.log').open('a',encoding='utf-8') as f:f.write(f'Host startup failed: {type(exc).__name__}: {exc}\n')
            except OSError:pass
        if sys.stdout is not None:print(f'Host error: {exc}',file=sys.stderr)
        return 1

if __name__=='__main__':raise SystemExit(main())
