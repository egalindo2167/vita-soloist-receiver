@echo off
cd /d "%~dp0"
py -3.14 host.py --audio-codec opus --bitrate 320
pause
