@echo off
setlocal

set GPP=x86_64-w64-mingw32-g++
set FLAGS=-std=c++17 -O2 -Wall -DUNICODE -D_UNICODE

echo [build] Compiling toolkit.dll ...
%GPP% %FLAGS% -shared -o toolkit.dll toolkit.cpp ^
    -lkernel32 -luser32 -static -static-libgcc -static-libstdc++
if errorlevel 1 ( echo [build] FAILED toolkit.dll & goto :end )
echo [build] toolkit.dll OK

echo [build] Compiling injector.exe ...
%GPP% %FLAGS% -o injector.exe injector.cpp ^
    -lkernel32 -luser32 -static -static-libgcc -static-libstdc++
if errorlevel 1 ( echo [build] FAILED injector.exe & goto :end )
echo [build] injector.exe OK

echo.
echo [build] Done. Run:
echo   1. Start ShooterClient.exe
echo   2. Double-click injector.exe  (or run: injector.exe ShooterClient.exe)

:end
pause
