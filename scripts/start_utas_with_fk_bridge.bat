@echo off
set FK_BRIDGE_PUBLISH=%~dp0..\fk-bridge\FkBridge\bin\Release\net8.0\win-x86\publish
set FK_BRIDGE_URL=http://127.0.0.1:5001
if exist "%FK_BRIDGE_PUBLISH%\FkBridge.exe" (
  if not exist "%FK_BRIDGE_PUBLISH%\FKAttend.dll" (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0..\fk-bridge\copy-fk-dll.ps1" -PublishDir "%FK_BRIDGE_PUBLISH%"
  )
  start "FkBridge" /D "%FK_BRIDGE_PUBLISH%" FkBridge.exe
  timeout /t 2 /nobreak >nul
) else (
  echo Build FkBridge first: cd fk-bridge\FkBridge ^& dotnet publish -c Release -r win-x86
)
cd /d %~dp0..\backend\app
set FK_BRIDGE_URL=http://127.0.0.1:5001
python main.py
