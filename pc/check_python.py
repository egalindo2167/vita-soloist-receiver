"""Check the supported interpreter before installing native wheels."""
import platform
import ssl
import struct
import sys
import sysconfig

def validate():
    if sys.implementation.name!='cpython' or sys.version_info[:2]!=(3,14):
        raise RuntimeError('Install standard CPython 3.14 from python.org, then use py -3.14.')
    if struct.calcsize('P')!=8 or platform.machine().lower() not in ('amd64','x86_64'):
        raise RuntimeError('Install the Windows x64 Python 3.14 runtime. Native Windows ARM Python is not supported.')
    if sysconfig.get_config_var('Py_GIL_DISABLED'):
        raise RuntimeError('The free-threaded 3.14t build is unsupported by this wheel lock. Install standard Python 3.14.')
    if not getattr(ssl,'HAS_PSK',False):
        raise RuntimeError('This Python/OpenSSL lacks TLS-PSK. Use the standard python.org Python 3.14 runtime.')

if __name__=='__main__':
    try:validate()
    except RuntimeError as exc:print('Python setup:',exc);raise SystemExit(1)
    print('Python 3.14 x64, standard ABI and TLS-PSK are ready.')
