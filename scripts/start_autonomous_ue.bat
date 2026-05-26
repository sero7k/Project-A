@echo off
setlocal
cd /d "%~dp0"

if not defined PROJECT_A_RIOT_ID set "PROJECT_A_RIOT_ID=DevPlayer#LOCAL"
if not defined PROJECT_A_CLIENT_EXE set "PROJECT_A_CLIENT_EXE=%~dp0Project A Valorant\ShooterClient.exe"
set "PROJECT_A_USE_TOOLKIT=0"
set "PROJECT_A_NO_PAUSE=1"

call "%~dp0start_client.bat" -UEGameServer %*
