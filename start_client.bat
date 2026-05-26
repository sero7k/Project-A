@echo off
setlocal
cd /d "%~dp0"

set "HAS_RIOT_ARG="
set "HAS_CLIENT_EXE_ARG="
for %%A in (%*) do (
  if /I "%%~A"=="-RiotName" set "HAS_RIOT_ARG=1"
  if /I "%%~A"=="-TagLine" set "HAS_RIOT_ARG=1"
  if /I "%%~A"=="-AccountKey" set "HAS_RIOT_ARG=1"
  if /I "%%~A"=="-ClientExe" set "HAS_CLIENT_EXE_ARG=1"
)

if not defined HAS_RIOT_ARG if not defined PROJECT_A_RIOT_ID (
  set /p "PROJECT_A_RIOT_ID=Enter Riot ID (GameName#TAG, blank for DevPlayer#LOCAL): "
  if not defined PROJECT_A_RIOT_ID set "PROJECT_A_RIOT_ID=DevPlayer#LOCAL"
)

set "DEFAULT_CLIENT_EXE=%~dp0Project A Valorant\ShooterClient.exe"
if not defined HAS_CLIENT_EXE_ARG if not defined PROJECT_A_CLIENT_EXE (
  set "PROJECT_A_CLIENT_EXE=%DEFAULT_CLIENT_EXE%"
  if not exist "%DEFAULT_CLIENT_EXE%" (
    echo Client executable not found at:
    echo   %DEFAULT_CLIENT_EXE%
    echo Pass -ClientExe to use a different path.
    goto :fail
  )
)

set "PYTHON_CMD=python"
where py >nul 2>nul
if not errorlevel 1 set "PYTHON_CMD=py -3"

if not exist ".venv\Scripts\python.exe" (
  echo Creating .venv...
  %PYTHON_CMD% -m venv .venv
  if errorlevel 1 goto :fail
)

call ".venv\Scripts\activate.bat"
if errorlevel 1 goto :fail

echo Installing/updating dependencies...
python -m pip install --upgrade pip
if errorlevel 1 goto :fail
python -m pip install -r requirements.txt
if errorlevel 1 goto :fail

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\launch_client.ps1" -PatchClientCerts %*
set EXITCODE=%ERRORLEVEL%

echo.
echo start_client.bat exited with code %EXITCODE%.
pause
exit /b %EXITCODE%

:fail
echo.
echo start_client.bat failed.
pause
exit /b 1
