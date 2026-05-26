@echo off
setlocal
cd /d "%~dp0"

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

set "HAS_DATABASE_URL_ARG=0"
python -c "import sys; sys.exit(0 if any(a == '--database-url' or a.startswith('--database-url=') for a in sys.argv[1:]) else 1)" %*
if not errorlevel 1 set "HAS_DATABASE_URL_ARG=1"

set "SERVER_ARGS=Server\project_a_server.py --host 127.0.0.1 --port 39001 --reset-state"
if not defined PROJECTA_DATABASE_URL if not defined DATABASE_URL if "%HAS_DATABASE_URL_ARG%"=="0" (
  set "SERVER_ARGS=%SERVER_ARGS% --allow-memory-db"
)

echo Starting Project A local server on http://127.0.0.1:39001
echo Press Ctrl+C to stop.
python %SERVER_ARGS% %*
set EXITCODE=%ERRORLEVEL%
echo.
echo Server exited with code %EXITCODE%.
pause
exit /b %EXITCODE%

:fail
echo.
echo start_server.bat failed.
pause
exit /b 1
