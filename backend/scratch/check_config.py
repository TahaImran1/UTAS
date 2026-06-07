import sys
import os
import json

# Setup paths to import the app modules
sys.path.append(r"e:\Projects\ZK\SUFI_LAST\sourse_code_ZKTECO\backend")
sys.path.append(r"e:\Projects\ZK\SUFI_LAST\sourse_code_ZKTECO\backend\app")

from app.machines_config import load_machines
from app.zk import db

print("--- CONFIG DIRECTORY APP_DATA ---")
app_data = os.getenv('APPDATA')
if app_data:
    dir_path = os.path.join(app_data, "UTAS")
    print(f"UTAS path: {dir_path}")
    machines_file = os.path.join(dir_path, "machines.json")
    db_file = os.path.join(dir_path, "database.json")
    if os.path.exists(machines_file):
        with open(machines_file, 'r') as f:
            print("Machines in machines.json:")
            print(json.dumps(json.load(f), indent=2))
    else:
        print("machines.json does not exist!")
        
    if os.path.exists(db_file):
        with open(db_file, 'r') as f:
            print("Database configuration:")
            print(json.dumps(json.load(f), indent=2))
    else:
        print("database.json does not exist!")
