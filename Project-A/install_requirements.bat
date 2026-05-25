@echo off
setlocal

cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo Python was not found on PATH.
  pause
  exit /b 1
)

echo Installing Python requirements from "%~dp0requirements.txt"...
python -m pip install -r "%~dp0requirements.txt"
set EXITCODE=%ERRORLEVEL%

echo.
if %EXITCODE%==0 (
  echo Requirements installed successfully.
) else (
  echo Requirements installation failed with code %EXITCODE%.
)

pause
exit /b %EXITCODE%
