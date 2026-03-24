@echo off
title ZK ADMS Server
echo Checking and installing missing dependencies...
pip install -qr requirements.txt
echo.
echo Starting ZK ADMS Server (FastAPI Mode)...
echo ---------------------------------------------------
echo Web Viewer:  http://localhost:4370/view
echo.
echo YOUR CURRENT IP ADDRESS(ES):
ipconfig | findstr "IPv4"
echo.
echo [IMPORTANT]
echo If you changed networks, check the IP above.
echo You MUST update the Device "Server Address" to match it.
echo ---------------------------------------------------
echo.
python adms_server.py
pause
