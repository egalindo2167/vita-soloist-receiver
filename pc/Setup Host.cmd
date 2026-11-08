@echo off
cd /d "%~dp0"
py -3.14 -m pip install --only-binary=:all: --require-hashes -r requirements-windows-x64.lock
if errorlevel 1 goto done
py -3.14 host.py --setup --install-startup
if errorlevel 1 goto done
py -3.14 audio_config.py --setup
:done
pause
