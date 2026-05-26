@echo off
setlocal
cd /d "%~dp0"

set "HAS_RIOT_ARG="
set "HAS_CLIENT_EXE_ARG="
set "HAS_TOOLKIT_ARG="
for %%A in (%*) do (
  if /I "%%~A"=="-RiotName" set "HAS_RIOT_ARG=1"
  if /I "%%~A"=="-TagLine" set "HAS_RIOT_ARG=1"
  if /I "%%~A"=="-AccountKey" set "HAS_RIOT_ARG=1"
  if /I "%%~A"=="-ClientExe" set "HAS_CLIENT_EXE_ARG=1"
  if /I "%%~A"=="-UseToolkit" set "HAS_TOOLKIT_ARG=1"
  if /I "%%~A"=="-NoToolkit" set "HAS_TOOLKIT_ARG=1"
)

if not defined HAS_RIOT_ARG if not defined PROJECT_A_RIOT_ID (
  set /p "PROJECT_A_RIOT_ID=Enter Riot ID (GameName#TAG, blank for DevPlayer#LOCAL): "
  if not defined PROJECT_A_RIOT_ID set "PROJECT_A_RIOT_ID=DevPlayer#LOCAL"
)

set "DEFAULT_CLIENT_EXE=%~dp0..\Project A Valorant\ShooterClient.exe"
if not exist "%DEFAULT_CLIENT_EXE%" set "DEFAULT_CLIENT_EXE=%~dp0Project A Valorant\ShooterClient.exe"
set "TOOLKIT_EXE=%~dp0toolkit\injector.exe"
if not defined HAS_CLIENT_EXE_ARG if not defined PROJECT_A_CLIENT_EXE (
  set "PROJECT_A_CLIENT_EXE=%DEFAULT_CLIENT_EXE%"
  if not exist "%DEFAULT_CLIENT_EXE%" (
    echo Client executable not found at:
    echo   %DEFAULT_CLIENT_EXE%
    echo Pass -ClientExe to use a different path.
    goto :fail
  )
)

if not defined PROJECT_A_USE_TOOLKIT set "PROJECT_A_USE_TOOLKIT=0"

set "TOOLKIT_SWITCH="
if /I "%PROJECT_A_USE_TOOLKIT%"=="1" set "TOOLKIT_SWITCH=-UseToolkit"
if /I "%PROJECT_A_USE_TOOLKIT%"=="y" set "TOOLKIT_SWITCH=-UseToolkit"
if /I "%PROJECT_A_USE_TOOLKIT%"=="yes" set "TOOLKIT_SWITCH=-UseToolkit"
if /I "%PROJECT_A_USE_TOOLKIT%"=="true" set "TOOLKIT_SWITCH=-UseToolkit"

if defined TOOLKIT_SWITCH if not exist "%TOOLKIT_EXE%" (
  echo Toolkit injector not found at:
  echo   %TOOLKIT_EXE%
  goto :fail
)
set "PYTHON_CMD=python"
where py >nul 2>nul
if not errorlevel 1 set "PYTHON_CMD=py -3"
set "VENV_DIR=.venv"
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"

if exist "%VENV_DIR%" if not exist "%VENV_DIR%\pyvenv.cfg" (
  echo Recreating incomplete %VENV_DIR%...
  rmdir /s /q "%VENV_DIR%" 2>nul
)

if not exist "%VENV_PY%" (
  echo Creating %VENV_DIR%...
  %PYTHON_CMD% -m venv "%VENV_DIR%"
  if errorlevel 1 goto :fail
)

if not exist "%VENV_PY%" goto :fail

"%VENV_PY%" -m ensurepip --upgrade >nul 2>nul
if errorlevel 1 (
  echo Repairing %VENV_DIR%...
  rmdir /s /q "%VENV_DIR%" 2>nul
  %PYTHON_CMD% -m venv "%VENV_DIR%"
  if errorlevel 1 goto :fail
  if not exist "%VENV_PY%" goto :fail
  "%VENV_PY%" -m ensurepip --upgrade >nul 2>nul
)
if errorlevel 1 goto :fail

echo Installing/updating dependencies...
"%VENV_PY%" -m pip install --upgrade pip
if errorlevel 1 goto :fail
"%VENV_PY%" -m pip install -r requirements.txt
if errorlevel 1 goto :fail

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\launch_client.ps1" -PatchClientCerts %TOOLKIT_SWITCH% %*
set EXITCODE=%ERRORLEVEL%

echo.
echo start_client.bat exited with code %EXITCODE%.
if not defined PROJECT_A_NO_PAUSE pause
exit /b %EXITCODE%

:fail
echo.
echo start_client.bat failed.
if not defined PROJECT_A_NO_PAUSE pause
exit /b 1
