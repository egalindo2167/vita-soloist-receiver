#!/usr/bin/env python3
"""Test-only local agent API fixture. Never connects to ngrok or the internet."""
import json
import os
from pathlib import Path
import re
import signal
import sys
from http.server import BaseHTTPRequestHandler,HTTPServer

def main():
    configuration=Path(sys.argv[sys.argv.index('--config')+1]).read_text()
    port=int(re.search(r'web_addr: 127\.0\.0\.1:(\d+)',configuration)[1])
    token=os.environ.get('NGROK_AUTHTOKEN')
    if token!='fixture-provider-token':raise SystemExit('Missing test-only process credential')
    print('Fixture log redaction check: '+token,flush=True)
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path!='/api/endpoints':self.send_error(404);return
            value={'endpoints':[
                {'name':'vita-audio','url':'tcp://audio.example.test:25001','upstream':{'url':'127.0.0.1:48152'}},
                {'name':'vita-controls','url':'tcp://control.example.test:25002','upstream':{'url':'127.0.0.1:48153'}}]}
            data=json.dumps(value).encode();self.send_response(200)
            self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)))
            self.end_headers();self.wfile.write(data)
        def log_message(self,*args):pass
    def stop(*args):raise SystemExit(0)
    signal.signal(signal.SIGINT,stop)
    with HTTPServer(('127.0.0.1',port),Handler) as server:server.serve_forever(.05)
if __name__=='__main__':main()
