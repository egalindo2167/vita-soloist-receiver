import contextlib
import importlib.util
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'pc'))
import start_soloist as launcher


class SoloistLauncherTests(unittest.TestCase):
    def test_find_official_archive_inside_one_enclosing_directory(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            executable = base/'soloist'/'windows_x86_64'/'soloist.exe'
            executable.parent.mkdir(parents=True)
            executable.touch()
            self.assertEqual(launcher.find_soloist(directory=base), executable.resolve())

    def test_missing_binary_does_not_download_or_launch_anything(self):
        with tempfile.TemporaryDirectory() as td, \
             mock.patch.object(launcher.shutil, 'which', return_value=None):
            with self.assertRaisesRegex(RuntimeError, 'official Windows'):
                launcher.find_soloist(directory=Path(td))

    def test_retired_launcher_does_not_start_unencrypted_helpers(self):
        with mock.patch.object(launcher.subprocess,'Popen') as spawn, \
             contextlib.redirect_stderr(io.StringIO()) as error:
            self.assertEqual(launcher.main(['10.1.43.227']),1)
            self.assertIn('Pair Vita.cmd',error.getvalue());spawn.assert_not_called()

    def test_expired_build_stops_before_starting_capture(self):
        soloist = mock.Mock(returncode=10)
        soloist.poll.return_value = 10
        with mock.patch.object(launcher, 'process_options', return_value={}), \
             mock.patch.object(launcher.subprocess, 'Popen', return_value=soloist) as start, \
             mock.patch.object(launcher.time, 'sleep'), \
             contextlib.redirect_stderr(io.StringIO()) as error:
            self.assertEqual(launcher.supervise(['official-soloist'], ['sender'], ROOT, {}), 1)
        self.assertEqual(start.call_count, 1)
        self.assertIn('expired', error.getvalue())

    def test_sender_failure_stops_owned_soloist_process(self):
        soloist = mock.Mock()
        soloist.poll.side_effect = [None, None]
        sender = mock.Mock(returncode=1)
        sender.poll.return_value = 1
        with mock.patch.object(launcher, 'process_options', return_value={}), \
             mock.patch.object(launcher.subprocess, 'Popen', side_effect=[soloist, sender]), \
             mock.patch.object(launcher.time, 'sleep'), \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(launcher.supervise(['official-soloist'], ['sender'], ROOT, {}), 1)
        soloist.send_signal.assert_called_once()
        soloist.wait.assert_called_once_with(timeout=3)

    def test_failed_sender_spawn_also_stops_soloist(self):
        soloist = mock.Mock()
        soloist.poll.return_value = None
        with mock.patch.object(launcher, 'process_options', return_value={}), \
             mock.patch.object(launcher.subprocess, 'Popen', side_effect=[soloist, OSError('cannot start')]), \
             mock.patch.object(launcher.time, 'sleep'):
            with self.assertRaisesRegex(OSError, 'cannot start'):
                launcher.supervise(['official-soloist'], ['sender'], ROOT, {})
        soloist.send_signal.assert_called_once()

    def test_interruption_stops_both_owned_processes(self):
        soloist, sender = mock.Mock(), mock.Mock()
        soloist.poll.return_value = None
        sender.poll.return_value = None
        with mock.patch.object(launcher, 'process_options', return_value={}), \
             mock.patch.object(launcher.subprocess, 'Popen', side_effect=[soloist, sender]), \
             mock.patch.object(launcher.time, 'sleep', side_effect=[None, KeyboardInterrupt]), \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(launcher.supervise(['official-soloist'], ['sender'], ROOT, {}), 0)
        sender.send_signal.assert_called_once()
        soloist.send_signal.assert_called_once()

    def test_interruption_stops_all_three_owned_processes(self):
        soloist, sender, bridge=mock.Mock(),mock.Mock(),mock.Mock()
        for p in (soloist,sender,bridge): p.poll.return_value=None
        with mock.patch.object(launcher,'process_options',return_value={}), \
             mock.patch.object(launcher.subprocess,'Popen',side_effect=[soloist,sender,bridge]), \
             mock.patch.object(launcher.time,'sleep',side_effect=[None,KeyboardInterrupt]), \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(launcher.supervise(['soloist'],['sender'],ROOT,{},['bridge']),0)
        for p in (soloist,sender,bridge): p.send_signal.assert_called_once()

    def test_controls_exit_does_not_stop_audio_before_soloist_exits(self):
        soloist,sender,bridge=mock.Mock(),mock.Mock(),mock.Mock(returncode=1)
        soloist.poll.side_effect=[None,10,10]; sender.poll.return_value=None; bridge.poll.return_value=1
        with mock.patch.object(launcher,'process_options',return_value={}), \
             mock.patch.object(launcher.subprocess,'Popen',side_effect=[soloist,sender,bridge]), \
             mock.patch.object(launcher.time,'sleep'), contextlib.redirect_stderr(io.StringIO()) as output:
            self.assertEqual(launcher.supervise(['soloist'],['sender'],ROOT,{},['bridge']),1)
        self.assertIn('Audio continues',output.getvalue())
        self.assertIn('expired',output.getvalue())


if __name__ == '__main__':
    unittest.main()
