import importlib.util
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'pc'))
from security_support import read_exact
class CiDeadlineTests(unittest.TestCase):
    def test_partial_header_eof_fails_promptly(self):
        a,b=socket.socketpair()
        with a,b:
            a.settimeout(1);b.sendall(b'VOPS');b.shutdown(socket.SHUT_WR)
            with self.assertRaisesRegex(EOFError,'4 of 16'):read_exact(a,16)
    def test_runner_stops_a_hung_test_with_its_name_and_stacks(self):
        with tempfile.TemporaryDirectory() as td:
            Path(td,'test_hang.py').write_text('import unittest,time\nclass Hung(unittest.TestCase):\n def test_blocked(self):time.sleep(30)\n')
            result=subprocess.run([sys.executable,str(ROOT/'tools/run_python_tests.py'),'--directory',td,'--timeout','.3'],capture_output=True,text=True,timeout=5)
            self.assertEqual(result.returncode,124)
            self.assertIn('test_blocked',result.stderr);self.assertIn('TEST DEADLINE',result.stderr)
            self.assertIn('test_hang.py',result.stderr)
