@echo off
setlocal

cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo Python was not found on PATH.
  pause
  exit /b 1
)

:: Player 2+ - connects to listen server at 127.0.0.1:7777
:: Run start-multiplayer-host.bat first and wait for it to reach the map before launching this
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_project_a.ps1" -ConnectServer "127.0.0.1:7777" -ClientArg "-Port=7778" -GamePort 7778 -Label "mp-client" -Profile "developer2" %*
set EXITCODE=%ERRORLEVEL%

echo.
echo start-multiplayer-client.bat exited with code %EXITCODE%.
pause
exit /b %EXITCODE%
