@echo off
setlocal
cd /d "%~dp0"
set "PYTHON=.venv\Scripts\python.exe"

if not exist "%PYTHON%" (
    py -3 -m venv .venv
    if errorlevel 1 goto :error
)

call "%PYTHON%" -m pip install -r requirements.txt
if errorlevel 1 goto :error

set "PYTHONPATH=%CD%\src"
call "%PYTHON%" main.py %*
if errorlevel 1 goto :error
exit /b 0

:error
echo.
echo Failed to run MicMute Lite.
exit /b 1
