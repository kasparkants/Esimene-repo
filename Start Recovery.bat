@echo off
cd /d "%~dp0"
py -3 recovery_gui.py
if errorlevel 1 (
  echo Install Python 3.10 or newer from python.org with Tcl/Tk and the Python launcher enabled.
  pause
)
