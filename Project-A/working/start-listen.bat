@echo off
setlocal

cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo Python was not found on PATH.
  pause
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_project_a.ps1" -ListenServer -GameSocketReply none %*
set EXITCODE=%ERRORLEVEL%

echo.
echo start-listen.bat exited with code %EXITCODE%.
pause
exit /b %EXITCODE%
