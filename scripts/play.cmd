@echo off
setlocal
cd /d "%~dp0\.."
py -3 launcher.py --mode tui
