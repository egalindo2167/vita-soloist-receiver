#!/usr/bin/env python3
"""Local CLI/daemon-state fixture; not a public relay or a Tailscale binary."""
import fcntl
import json
import os
from pathlib import Path
import signal
import sys
import time

ROOT=Path(os.environ['VITA_TEST_FUNNEL_ROOT']);NAME='desktop.example-tailnet.ts.net'

def state(change=None):
    with (ROOT/'state.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        try:value=json.loads((ROOT/'state.json').read_text())
        except FileNotFoundError:value={}
        if change is not None:
            change(value);(ROOT/'state.json').write_text(json.dumps(value))
        return value

args=sys.argv[1:]
if args==['version']:print('1.104.5');raise SystemExit(0)
if args==['funnel','--help']:print('--tcp --yes --bg');raise SystemExit(0)
if args==['status','--json']:
    print(json.dumps({'BackendState':'Running','Self':{'DNSName':NAME+'.'}}));raise SystemExit(0)
if args==['funnel','status','--json']:print(json.dumps(state()));raise SystemExit(0)
if args[0]!='funnel' or '--yes' not in args or len(args)!=4:raise SystemExit(2)
port=int(args[2].removeprefix('--tcp='));target=args[3].removeprefix('tcp://');session=str(os.getpid())
stopped=False
def stop(*unused):
    global stopped
    stopped=True
signal.signal(signal.SIGINT,stop);signal.signal(signal.SIGTERM,stop)
def add(value):
    value.setdefault('Foreground',{})[session]={'TCP':{str(port):{'TCPForward':target}},'AllowFunnel':{f'{NAME}:{port}':True}}
def remove(value):
    value.get('Foreground',{}).pop(session,None)
    if not value.get('Foreground'):value.pop('Foreground',None)
state(add)
print(f'tcp://{NAME}:{port} -> {target}',flush=True)
try:
    while not stopped:time.sleep(.05)
finally:state(remove)
