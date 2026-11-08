#!/usr/bin/env python3
"""Run all Python checks with a hard per-test deadline and diagnostic stacks."""
import argparse
import faulthandler
import os
from pathlib import Path
import sys
import threading
import unittest

def run(directory,seconds):
    class Result(unittest.TextTestResult):
        def startTest(self,test):
            super().startTest(test)
            self.stream.flush()
            def expired():
                print(f"\nTEST DEADLINE ({seconds}s): {test.id()}",file=sys.stderr,flush=True)
                faulthandler.dump_traceback(file=sys.stderr,all_threads=True)
                os._exit(124)
            self.deadline=threading.Timer(seconds,expired)
            self.deadline.daemon=True
            self.deadline.start()
        def stopTest(self,test):
            self.deadline.cancel()
            super().stopTest(test)
    suite=unittest.defaultTestLoader.discover(str(directory),pattern='test_*.py')
    return unittest.TextTestRunner(verbosity=2,resultclass=Result).run(suite).wasSuccessful()

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',type=Path,default=Path(__file__).resolve().parents[1]/'tests')
    parser.add_argument('--timeout',type=float,default=120)
    args=parser.parse_args()
    if args.timeout<=0:parser.error('Timeout must be positive')
    raise SystemExit(0 if run(args.directory,args.timeout) else 1)
