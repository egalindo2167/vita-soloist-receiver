#!/usr/bin/env python3
"""Start official Spotify Soloist on Windows and forward its output to a Vita."""
import argparse
import getpass
import importlib.util
import ipaddress
import math
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

DEFAULT_NAME = 'PS Vita (PC bridge)'
HERE = Path(__file__).resolve().parent
DOWNLOADS = 'https://developer.spotify.com/documentation/soloist/reference/downloads-and-updates'


def find_soloist(explicit=None, directory=HERE):
    if explicit:
        candidate = Path(explicit).expanduser().resolve()
        if not candidate.is_file():
            raise RuntimeError('The --soloist-exe path does not point to a file.')
        return candidate
    for candidate in (directory/'soloist'/'soloist.exe', directory/'soloist.exe'):
        if candidate.is_file():
            return candidate.resolve()
    # Some official archives contain one enclosing folder. Do not scan the PC.
    nested = sorted((directory/'soloist').glob('*/soloist.exe'))
    if len(nested) == 1:
        return nested[0].resolve()
    installed = shutil.which('soloist.exe')
    if installed:
        return Path(installed).resolve()
    raise RuntimeError('soloist.exe was not found. Extract the official Windows x86_64 '
                       'download into pc\\soloist, or pass --soloist-exe "C:\\path\\soloist.exe". '
                       f'Download: {DOWNLOADS}')


def storage_root():
    local = os.environ.get('LOCALAPPDATA')
    return (Path(local) if local else Path.home()/'AppData'/'Local')/'VitaAudioReceiver'/'soloist'


def process_options():
    # Separate groups let Ctrl+C in this launcher stop just the children it owns.
    return {'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP} if sys.platform == 'win32' else {}


def stop_process(process):
    if process is None or process.poll() is not None:
        return
    try:
        process.send_signal(signal.CTRL_BREAK_EVENT if sys.platform == 'win32' else signal.SIGINT)
        process.wait(timeout=3)
        return
    except (OSError, subprocess.TimeoutExpired):
        pass
    try:
        process.terminate()
        process.wait(timeout=2)
    except (OSError, subprocess.TimeoutExpired):
        if process.poll() is None:
            process.kill()
            process.wait(timeout=2)


def supervise(soloist_command, sender_command, soloist_directory, environment, bridge_command=None):
    """Audio survives an optional controls failure; own and stop all children."""
    soloist = sender = bridge = None
    try:
        options = process_options()
        soloist = subprocess.Popen(soloist_command, cwd=soloist_directory, env=environment, **options)
        # Catch immediate missing-DLL, invalid-key/argument, or expired-build exits
        # before opening the stream. Actual login happens later in Spotify.
        time.sleep(0.4)
        code = soloist.poll()
        if code is None:
            sender = subprocess.Popen(sender_command, cwd=HERE, env=environment, **options)
            if bridge_command is not None:
                bridge = subprocess.Popen(bridge_command, cwd=HERE, env=environment, **options)
        while code is None:
            if bridge is not None and bridge.poll() is not None:
                print('Controls bridge stopped. Audio continues; check its error above.',file=sys.stderr)
                bridge=None
            if sender.poll() is not None:
                result = sender.returncode
                print('Audio sender stopped; stopping Soloist.', flush=True)
                return result
            time.sleep(0.2)
            code = soloist.poll()
        if code == 10:
            print(f'Soloist build expired. Download a newer Windows build: {DOWNLOADS}', file=sys.stderr)
        else:
            print(f'Soloist exited with code {code}. Check its messages above.', file=sys.stderr)
        return 1 if code else 0
    except KeyboardInterrupt:
        print('\nStopping Soloist and the Vita sender...', flush=True)
        return 0
    finally:
        try:
            stop_process(bridge)
        finally:
            try:
                stop_process(sender)
            finally:
                stop_process(soloist)


def main(argv=None):
    print('Manual unencrypted launcher retired in 0.10. Use Setup Host.cmd, then Pair Vita.cmd.',file=sys.stderr)
    return 1

if __name__=='__main__':raise SystemExit(main())
