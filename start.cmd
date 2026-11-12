@echo off
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1
if exist ".venv\Scripts\python.exe" goto launch
where py >nul 2>nul
if not errorlevel 1 (
  py -3 -m venv .venv
) else (
  python -m venv .venv
)
if errorlevel 1 goto failed
:launch
".venv\Scripts\python.exe" -c "import sys; assert (3,10) <= sys.version_info < (3,14), 'Python 3.10-3.13 required'"
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -c "import PySide6.QtWidgets" >nul 2>nul
if errorlevel 1 (
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
  if errorlevel 1 goto failed
)
".venv\Scripts\python.exe" run.py %*
if errorlevel 1 goto failed
exit /b 0
:failed
echo.
echo BEFORE could not start. Install Python 3.10-3.13 from python.org,
echo enable the Python launcher, then open start.cmd again.
pause
exit /b 1
