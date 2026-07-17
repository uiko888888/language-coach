@echo off
setlocal
cd /d "%~dp0"
title Language Coach v2 Server

if not defined LANGUAGE_COACH_PORT set "LANGUAGE_COACH_PORT=8765"

where python >nul 2>nul
if errorlevel 1 (
  echo Python was not found in PATH.
  echo Install Python or run backend\server.py with your Python executable.
  pause
  exit /b 1
)

echo.
echo   Language Coach v2 is starting...
echo   Keep this window open while using the app.
echo   App URL: http://127.0.0.1:%LANGUAGE_COACH_PORT%
echo.

start "" /B powershell.exe -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 1; Start-Process 'http://127.0.0.1:%LANGUAGE_COACH_PORT%'"
python -u backend\server.py %LANGUAGE_COACH_PORT%

echo.
echo   The server has stopped. Press any key to close this window.
pause >nul
