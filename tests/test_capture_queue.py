import pathlib
import sys
import threading
import unittest

sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'pc'))
from capture_queue import CaptureQueue

class CaptureQueueTests(unittest.TestCase):
    def test_slow_sender_does_not_block_capture_and_lag_is_bounded(self):
        # Simulate capture continuing while networking makes no progress.
        worker=CaptureQueue(lambda:(bytes([i])*4096 for i in range(100)),max_blocks=4)
        try:
            self.assertTrue(worker.finished.wait(2))
            self.assertEqual(worker.captured,100)
            self.assertEqual(worker.dropped,96)
            self.assertEqual(worker.high_water,4)
            blocks=list(worker)
            self.assertEqual([b[0] for b in blocks],[96,97,98,99])
        finally:worker.close()
    def test_capture_exception_is_delivered_to_sender(self):
        def source():
            yield b'1234'
            raise RuntimeError('recording device disconnected')
        worker=CaptureQueue(source)
        try:
            self.assertEqual(next(worker),b'1234')
            with self.assertRaisesRegex(RuntimeError,'recording device disconnected'):
                next(worker)
        finally:worker.close()
    def test_recorder_created_and_closed_on_worker_thread(self):
        thread_ids=[];closed=threading.Event()
        def source():
            thread_ids.append(threading.get_ident())
            try:
                while True:yield b'1234'
            finally:
                thread_ids.append(threading.get_ident());closed.set()
        worker=CaptureQueue(source,max_blocks=2)
        self.assertEqual(next(worker),b'1234')
        worker.close()
        self.assertFalse(worker.thread.is_alive())
        self.assertTrue(closed.is_set())
        self.assertEqual(thread_ids[0],thread_ids[1])
        self.assertNotEqual(thread_ids[0],threading.get_ident())
