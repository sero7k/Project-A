@echo off
:: Project A - Launch game + local server (no admin required)
set ROOT=%~dp0
set TOOLKIT=%ROOT%toolkit\injector.exe

echo.
echo  ========================================
echo   Project A - Local Launcher
echo  ========================================
echo.
echo   [0] Launch without toolkit
echo   [1] Launch with toolkit injected
echo.
echo  ========================================
set /p CHOICE="  Enter choice [0-1]: "

if "%CHOICE%"=="0" goto :no_toolkit
if "%CHOICE%"=="1" goto :with_toolkit
echo  Invalid choice.
pause & exit /b 1

:no_toolkit
echo.
echo  [launch] Starting without toolkit...
cd /d "%ROOT%working"
call start.bat %*
goto :end

:with_toolkit
echo.
echo  [launch] Starting with toolkit injection...
if not exist "%TOOLKIT%" (
    echo  [launch] ERROR: injector.exe not found at %TOOLKIT%
    pause & exit /b 1
)

:: Start the game + server in a new window
start "Project-A Launcher" cmd /c "cd /d "%ROOT%working" && start.bat %*"

:: Inject — injector.exe waits for the game process itself
echo  [launch] Injecting toolkit...
"%TOOLKIT%"
echo  [launch] Toolkit injected. Debug console log: toolkit\toolkit.log
pause

:end
