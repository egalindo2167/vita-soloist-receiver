#!/usr/bin/env python3
"""Choose a dedicated virtual cable and verify Soloist's Windows audio route."""
import argparse
import json
from pathlib import Path
import os
import sys
import time
import audio_source as audio
import host

def cable_candidates(devices):
    # These are render endpoints, never CABLE Output recording inputs.
    return [d for d in devices if 'cable' in d['name'].casefold() and
            ('input' in d['name'].casefold() or 'vb-audio' in d['name'].casefold())]

def selected_device(devices,device_id):
    matches=[d for d in devices if d['id']==device_id]
    if len(matches)!=1:raise audio.CaptureError(2)
    return matches[0]

def save_selection(value,device,verified=False):
    source={'format':1,'mode':'soloist-process','device_id':device['id'],
            'device_name':device['name'],'route_verified':bool(verified)}
    value['capture']=source
    value.pop('device',None) # Old system-loopback preference is never a fallback.
    host.save_config(value)
    audio.source_status(0 if verified else 7,source,host.data_root(),state='ready' if verified else 'blocked')
    return source

def check_platform():
    info=audio.helper_json(['--info'])
    if type(info.get('build')) is not int or info['build']<20348:raise audio.CaptureError(5)

def ensure_runtime():
    if not host.windows.host_running():host.start_background()
    deadline=time.monotonic()+8
    while True:
        try:return audio.runtime_process(host.data_root())
        except audio.CaptureError:
            if time.monotonic()>=deadline:raise
            time.sleep(.2)

def setup(ensure=False):
    check_platform();value=host.load_config();devices=audio.render_devices()
    if ensure:
        try:source=audio.load_capture(host.data_root()/'host.json')
        except audio.CaptureError as exc:
            if exc.code not in (1,7):raise
        else:
            device=selected_device(devices,source['device_id'])
            print('Dedicated output retained:',device['name'])
            print('Capture stays Soloist-only. Run Audio Status.cmd to verify the live route.');return
    candidates=cable_candidates(devices)
    if not candidates:
        print('No active virtual-cable playback device was found.')
        print('Install VB-CABLE from https://vb-audio.com/Cable/ and restart Windows, then run Setup Audio.cmd.')
        print('Do not change the Windows default output to the cable.')
        raise audio.CaptureError(2)
    print('\nChoose the dedicated virtual playback device (normally CABLE Input):')
    saved=(value.get('capture') or {}).get('device_id')
    for index,device in enumerate(candidates,1):
        print(f"  {index}. {device['name']}"+(' [saved]' if device['id']==saved else ''))
    default=next((i for i,d in enumerate(candidates,1) if d['id']==saved),1)
    answer=input(f'Device number [{default}]: ').strip()
    if not answer:answer=str(default)
    if not answer.isdecimal() or not 1<=int(answer)<=len(candidates):raise ValueError('Invalid device number.')
    device=candidates[int(answer)-1]
    # Only the selected cable's master level is changed. The default output is untouched.
    audio.helper_json(['--prepare-device','--device',device['id']])
    source=save_selection(value,device)
    ensure_runtime()
    print('\nSelected:',device['name'])
    print('The selected cable is now unmuted at 100%; your normal default output is unchanged.')
    print('1. Open Spotify and play a song on your Soloist / PS Vita (PC bridge) device.')
    print('2. In Windows Settings > System > Sound > Volume mixer, find Soloist.')
    print('3. Set ONLY Soloist output to the virtual cable above; set its app volume to 100%.')
    print('4. Keep your normal Windows default output as your headphones or speakers.')
    print('5. Do not enable "Listen to this device" for CABLE Output.')
    print('If Soloist is absent, resume a song in Spotify so Windows creates its audio session.')
    os.startfile('ms-settings:apps-volume')
    while True:
        answer=input('\nPress Enter to verify the route (Q saves unfinished setup and exits): ').strip()
        if answer.casefold()=='q':
            print('Routing is not verified. Vita streaming stays blocked until Setup Audio.cmd succeeds.');return 1
        try:
            result=audio.probe(source,host.data_root())
            if result.get('route_verified') is not True:
                print('No Soloist audio session exists on that cable yet. Play a song and set its output, then retry.');continue
        except audio.CaptureError as exc:
            print(str(exc));continue
        # Reload to avoid overwriting any separate host-setting changes made while the wizard was open.
        save_selection(host.load_config(),device,True)
        print('\nVerified: only the owned Soloist process tree is captured, with Soloist routed to '+device['name']+'.')
        print('Open or reconnect the Vita app. Other PC audio stays on your normal default output.')
        print('No repeat setup is needed at each connection. The host still starts at Windows sign-in.')
        return 0

def status():
    check_platform();root=host.data_root();source=audio.load_capture(root/'host.json')
    device=selected_device(audio.render_devices(),source['device_id'])
    print('Mode: Soloist process and child processes only (not system-output loopback).')
    print('Dedicated output:',device['name']);print('Exact endpoint ID:',device['id'])
    result=audio.probe(source,root)
    if result.get('route_verified') is not True:raise audio.CaptureError(7,'Play a song in Soloist, then retry.')
    audio.source_status(0,source,root)
    print('Live Soloist route verified. Windows default output is not used for capture.')
    return 0

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);action=parser.add_mutually_exclusive_group(required=True)
    for name in ('setup','ensure','status'):action.add_argument('--'+name,action='store_true')
    args=parser.parse_args(argv)
    try:
        if sys.platform!='win32':raise audio.CaptureError(5)
        return status() if args.status else setup(args.ensure)
    except (OSError,ValueError,RuntimeError) as exc:
        print('Audio setup: '+str(exc),file=sys.stderr);return 1

if __name__=='__main__':raise SystemExit(main())
