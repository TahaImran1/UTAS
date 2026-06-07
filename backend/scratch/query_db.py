import sys
import os
import json

sys.path.append(r"e:\Projects\ZK\SUFI_LAST\sourse_code_ZKTECO\backend")
sys.path.append(r"e:\Projects\ZK\SUFI_LAST\sourse_code_ZKTECO\backend\app")

from app.zk import db

db_type = db.get_active_db_type()
print(f"Active DB Type: {db_type}")

config = db.load_latest_config(db_type)
print(f"Config loaded: {config}")

try:
    if db_type == "Oracle":
        conn = db.connect_db_oracle(config)
    else:
        conn = db.connect_db_postgresql(config)
        
    print("Connection successful!")
    
    # Query COMP_MACHINE
    cursor = conn.cursor()
    mach_tbl = config.get("machine_table", "COMP_MACHINE")
    col_sn = config.get("col_sn", "SN")
    col_ip = config.get("col_ip", "IP")
    col_proto = config.get("col_proto", "PROTOCOL")
    col_company = config.get("col_company", "COMPANY_NAME")
    
    try:
        query = f"SELECT {col_sn}, {col_ip}, {col_proto}, {col_company} FROM {mach_tbl}"
        cursor.execute(query)
        rows = cursor.fetchall()
        print(f"Rows in {mach_tbl}:")
        for row in rows:
            print(f"  SN: {row[0]}, IP: {row[1]}, Proto: {row[2]}, Company: {row[3]}")
    except Exception as ex:
        print(f"Error querying {mach_tbl}: {ex}")
        
    cursor.close()
    conn.close()
except Exception as e:
    print(f"Database error: {e}")
