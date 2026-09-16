@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo Python is not on PATH. Install Python 3, then: pip install -r requirements.txt
    pause
    exit /b 1
)

if "%~1"=="" (
    python randomize.py
) else (
    python randomize.py %*
)

if errorlevel 1 pause
