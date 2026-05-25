@echo off
setlocal

cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo Python was not found on PATH.
  pause
  exit /b 1
)

:: Player 1 - starts as listen server on port 7777
:: Other clients connect to 127.0.0.1:7777
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_project_a.ps1" -MultiplayerHost -GamePort 7777 -NumPlayers 2 -Label "mp-host" %*
set EXITCODE=%ERRORLEVEL%

echo.
echo start-multiplayer-host.bat exited with code %EXITCODE%.
pause
exit /b %EXITCODE%
