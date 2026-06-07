@echo off
REM Run FkBridge connect+pull test (avoids .ps1 opening in Notepad from cmd.exe)
setlocal
set "DEVICE_IP=192.168.100.67"
if not "%~1"=="" set "DEVICE_IP=%~1"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0verify_fk_bridge_pull.ps1" -DeviceIp "%DEVICE_IP%"
exit /b %ERRORLEVEL%
