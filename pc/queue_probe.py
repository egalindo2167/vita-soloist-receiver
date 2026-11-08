#!/usr/bin/env python3
"""Read-only measurement of the running Soloist build's available queue."""
import argparse
import json
from pathlib import Path
import time
from soloist_bridge import endpoint,MAX_SOLOIST_EVENT
from start_soloist import storage_root

def measure(connection,seconds=3):
    import websocket
    connection.send(json.dumps({'type':'command','command':'get_queue','limit':0}))
    end=time.monotonic()+seconds;counts=[]
    while time.monotonic()<end:
        try:raw=connection.recv()
        except websocket.WebSocketTimeoutException:continue
        if not raw:break
        if len(raw)>MAX_SOLOIST_EVENT:raise ValueError('Queue event exceeds the 16 MB safety bound.')
        event=json.loads(raw)
        if isinstance(event,dict) and event.get('type')=='error':
            raise ValueError('Soloist rejected the read-only queue request. Select the bridge in Spotify first.')
        if isinstance(event,dict) and event.get('type')=='queue_changed' and isinstance(event.get('upcoming'),list):
            counts.append(len(event['upcoming']))
    if not counts:raise ValueError('No queue reply. Keep the host running and select its device in Spotify.')
    return max(counts)

def main(argv=None):
    import websocket
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir',type=Path,default=storage_root()/'data')
    args=parser.parse_args(argv)
    connection=None
    try:
        connection=websocket.create_connection(endpoint(args.data_dir),timeout=.3,
                http_no_proxy=['127.0.0.1','localhost'])
        count=measure(connection)
        print(f'Largest observed all-available reply: {count} upcoming entries.')
        print('This is Soloist\'s current queue window, not the playlist length.')
        print('Spotify\'s announcement describes up to 80 upcoming tracks; builds may differ.')
        print('Only get_queue(limit=0) was sent. Playback and the queue were not changed.')
        return 0
    except (OSError,ValueError,websocket.WebSocketException) as exc:
        print('Queue check:',exc);return 1
    finally:
        if connection is not None:connection.close()

if __name__=='__main__':raise SystemExit(main())
