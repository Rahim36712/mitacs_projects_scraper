@echo off
title Mitacs Scraper
cd /d "%~dp0"

echo.
echo  ============================================
echo    MITACS PROJECT SCRAPER - starting up...
echo  ============================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo  [!] Python was not found on this PC.
    echo      Please install Python 3.11+ from https://www.python.org/downloads/
    echo      IMPORTANT: tick "Add Python to PATH" during install.
    echo.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo  [1/3] First run detected - setting things up ^(one time only, a few minutes^)...
    python -m venv .venv
    ".venv\Scripts\python.exe" -m pip install --upgrade pip --quiet
    ".venv\Scripts\python.exe" -m pip install flask playwright --quiet
    ".venv\Scripts\python.exe" -m playwright install chromium
    echo  [1/3] Setup done!
) else (
    echo  [1/3] Environment ready.
)

echo  [2/3] Starting local server...

start "" /b powershell -NoProfile -Command ^
  "$u='http://127.0.0.1:5001/api/health'; for($i=0;$i -lt 120;$i++){ try { Invoke-RestMethod $u | Out-Null; break } catch { Start-Sleep -Milliseconds 500 } }; Start-Process 'http://127.0.0.1:5001'"

".venv\Scripts\python.exe" mitacs_scraper\main.py ui --host 127.0.0.1 --port 5001

echo.
echo  [3/3] Server stopped. You can close this window.
pause
