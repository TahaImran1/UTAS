@echo off
REM Run AMF60 TCP check (avoids .ps1 opening in Notepad from cmd.exe)
setlocal
set "DEVICE_IP=192.168.100.67"
set "PORT=5005"
if not "%~1"=="" set "DEVICE_IP=%~1"
if not "%~2"=="" set "PORT=%~2"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0verify_amf60_tcp.ps1" -DeviceIp "%DEVICE_IP%" -Port %PORT%
exit /b %ERRORLEVEL%
