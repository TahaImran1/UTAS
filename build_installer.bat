@echo off
cd /d %~dp0

echo ========================================================
echo UTAS Master Build Script
echo ========================================================

echo.
echo [1/3] Building Python Backend (PyInstaller)...
cd backend
call build_backend.bat
if %ERRORLEVEL% NEQ 0 (
    echo Error building backend!
    exit /b %ERRORLEVEL%
)

echo.
echo [2/3] Preparing Frontend...
cd ../frontend
call npm install
if %ERRORLEVEL% NEQ 0 (
    echo Error running npm install!
    exit /b %ERRORLEVEL%
)

echo.
echo [3/3] Building Electron Installer...
call npm run build-installer
if %ERRORLEVEL% NEQ 0 (
    echo Error building Electron installer!
    exit /b %ERRORLEVEL%
)

echo.
echo ========================================================
echo BUILD COMPLETE!
echo Your installer is located at: frontend\dist-final\
echo ========================================================
pause
