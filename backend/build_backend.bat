@echo off
cd /d %~dp0
echo Installing requirements...
pip install -r requirements.txt
echo Compiling backend with PyInstaller...
python -m PyInstaller --name=UTAS --onefile --noconsole --hidden-import=auth_helper --hidden-import=uvicorn --hidden-import=fastapi --hidden-import=psycopg2 --hidden-import=oracledb --hidden-import=passlib.handlers.bcrypt --hidden-import=bcrypt --hidden-import=cryptography --hidden-import=cryptography.hazmat.primitives.kdf --hidden-import=cryptography.hazmat.primitives.kdf.pbkdf2 app/main.py
echo Done!
