"""Keep capture running while a network sender waits. No audio dependencies."""
import contextlib
import queue
import sys
import threading
import time


@contextlib.contextmanager
def com_thread():
    """SoundCard initializes COM on import; worker threads need their own init.

    Import SoundCard on the main thread BEFORE starting this worker. Never move
    an active WASAPI recorder between threads; the factory creates it here.
    """
    if sys.platform != 'win32':
        yield
        return
    import ctypes
    ole = ctypes.OleDLL('ole32')
    ole.CoInitializeEx.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    ole.CoInitializeEx.restype = ctypes.c_long
    hr = ole.CoInitializeEx(None, 0)  # multithreaded apartment
    if hr < 0:
        raise RuntimeError(f'Capture thread COM initialization failed: 0x{hr & 0xffffffff:08X}')
    try:
        yield
    finally:
        ole.CoUninitialize()


@contextlib.contextmanager
def audio_priority():
    """Ask Windows MMCSS to schedule only this capture worker as audio work."""
    handle=None
    if sys.platform=='win32':
        try:
            import ctypes
            avrt=ctypes.WinDLL('avrt',use_last_error=True)
            avrt.AvSetMmThreadCharacteristicsW.argtypes=[ctypes.c_wchar_p,ctypes.POINTER(ctypes.c_uint32)]
            avrt.AvSetMmThreadCharacteristicsW.restype=ctypes.c_void_p
            avrt.AvRevertMmThreadCharacteristics.argtypes=[ctypes.c_void_p]
            avrt.AvRevertMmThreadCharacteristics.restype=ctypes.c_int
            task=ctypes.c_uint32()
            handle=avrt.AvSetMmThreadCharacteristicsW('Audio',ctypes.byref(task))
        except (OSError,AttributeError):
            handle=None
    try:
        yield
    finally:
        if handle: avrt.AvRevertMmThreadCharacteristics(handle)


class CaptureQueue:
    """Non-blocking producer; on overflow discard oldest audio, report counts.

    Default buffer: about 1.37 s at 64 x 1024 frames. The persistent host
    selects 192 blocks (4.096 s), then reconnects if it overflows. Dropping old blocks keeps a stalled
    sender from building unlimited lag. A drop can cause a click, so it is
    exposed in diagnostics rather than claimed to be seamless.
    """
    def __init__(self, factory, max_blocks=64, stop_requested=None):
        if max_blocks < 1:
            raise ValueError('max_blocks must be positive')
        self.blocks = queue.Queue(maxsize=max_blocks)
        self.stop = threading.Event()
        self.finished = threading.Event()
        self.error = None
        self.stop_requested=stop_requested
        self.captured = 0
        self.dropped = 0
        self.high_water = 0
        self.thread = threading.Thread(target=self._run, args=(factory,),
                                       name='vita-audio-capture', daemon=True)
        self.thread.start()

    def _run(self, factory):
        try:
            with com_thread(),audio_priority():
                source = iter(factory())
                try:
                    for block in source:
                        if self.stop.is_set():
                            break
                        if not block:
                            continue
                        self.captured += 1
                        while not self.stop.is_set():
                            try:
                                self.blocks.put_nowait(block)
                                self.high_water = max(self.high_water, self.blocks.qsize())
                                break
                            except queue.Full:
                                try:
                                    self.blocks.get_nowait()
                                    self.dropped += 1
                                except queue.Empty:
                                    pass
                finally:
                    if hasattr(source, 'close'):
                        source.close()
        except Exception as exc:
            self.error = exc
        finally:
            self.finished.set()

    def __iter__(self):
        return self

    def __next__(self):
        while True:
            block=self.poll(0.1)
            if block is not None:return block

    def poll(self,timeout=0.1):
        """Allow a persistent server to check peer/stop status during silence."""
        if self.stop.is_set() or (self.stop_requested is not None and self.stop_requested()):
            raise StopIteration
        try:return self.blocks.get(timeout=timeout)
        except queue.Empty:
            if self.finished.is_set():
                if self.error:raise RuntimeError(f'Capture worker failed: {self.error}') from self.error
                raise StopIteration
            return None

    def close(self):
        self.stop.set()
        self.thread.join(timeout=2)

    def prefill(self,minimum=6,timeout=3):
        """Build a small cushion before transmitting regularly timed blocks."""
        deadline=time.monotonic()+timeout
        while self.blocks.qsize()<minimum and not self.finished.is_set():
            if self.stop.is_set() or (self.stop_requested is not None and self.stop_requested()):
                raise InterruptedError('Audio capture startup cancelled')
            if time.monotonic()>=deadline: raise RuntimeError('Audio capture did not fill the startup buffer')
            time.sleep(0.005)
        if self.error: raise RuntimeError(f'Capture worker failed: {self.error}') from self.error
        if self.blocks.empty(): raise RuntimeError('Audio capture ended without samples')

    def summary(self):
        return (f'Capture queue: {self.captured} blocks captured; '
                f'{self.dropped} dropped while sender was behind; '
                f'peak buffered {self.high_water} blocks.')
