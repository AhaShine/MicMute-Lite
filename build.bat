@echo off
setlocal
cd /d "%~dp0"
set "PYTHON=.venv\Scripts\python.exe"
set "PYINSTALLER=.venv\Scripts\pyinstaller.exe"
set "APP_NAME=MicMuteLite"
set "OUT_NAME=%APP_NAME%"

if not exist "%PYTHON%" (
    py -3 -m venv .venv
    if errorlevel 1 goto :error
)

call "%PYTHON%" -m pip install -r requirements.txt pyinstaller
if errorlevel 1 goto :error

if exist "dist\%APP_NAME%.exe" (
    del /q "dist\%APP_NAME%.exe" >nul 2>&1
    if exist "dist\%APP_NAME%.exe" (
        set "OUT_NAME=%APP_NAME%_new"
        if exist "dist\%OUT_NAME%.exe" del /q "dist\%OUT_NAME%.exe" >nul 2>&1
    )
)

call "%PYINSTALLER%" --noconfirm --clean --onefile --windowed --icon "assets\app\micmute_app.ico" --name %OUT_NAME% --paths src --add-data "assets;assets" main.py
if errorlevel 1 goto :error

echo.
echo Ready: dist\%OUT_NAME%.exe
if /I not "%OUT_NAME%"=="%APP_NAME%" (
    echo Existing dist\%APP_NAME%.exe is in use, so the new build was written to dist\%OUT_NAME%.exe
)
exit /b 0

:error
echo.
echo Build failed.
exit /b 1
