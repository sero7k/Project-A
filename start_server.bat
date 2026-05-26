@echo off
setlocal
cd /d "%~dp0"

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

set "HAS_DATABASE_URL_ARG=0"
"%VENV_PY%" -c "import sys; sys.exit(0 if any(a == '--database-url' or a.startswith('--database-url=') for a in sys.argv[1:]) else 1)" %*
if not errorlevel 1 set "HAS_DATABASE_URL_ARG=1"

set "SERVER_ARGS=Server\project_a_server.py --host 127.0.0.1 --port 39001 --reset-state"
if not defined PROJECTA_DATABASE_URL if not defined DATABASE_URL if "%HAS_DATABASE_URL_ARG%"=="0" (
  set "SERVER_ARGS=%SERVER_ARGS% --allow-memory-db"
)

echo Starting Project A local server on https://127.0.0.1:39001
echo Game server will auto-start on udp://127.0.0.1:7777 when a match begins.
echo Press Ctrl+C to stop.
"%VENV_PY%" %SERVER_ARGS% %*
set EXITCODE=%ERRORLEVEL%
echo.
echo Server exited with code %EXITCODE%.
if not defined PROJECT_A_NO_PAUSE pause
exit /b %EXITCODE%

:fail
echo.
echo start_server.bat failed.
if not defined PROJECT_A_NO_PAUSE pause
exit /b 1
