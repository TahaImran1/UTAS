import sys
import os
import json

sys.path.append(r"e:\Projects\ZK\SUFI_LAST\sourse_code_ZKTECO\backend")
sys.path.append(r"e:\Projects\ZK\SUFI_LAST\sourse_code_ZKTECO\backend\app")

from app.zk import db

db_type = db.get_active_db_type()
config = db.load_latest_config(db_type)

try:
    if db_type == "Oracle":
        conn = db.connect_db_oracle(config)
    else:
        conn = db.connect_db_postgresql(config)
        
    cursor = conn.cursor()
    table = config["table"]
    col_emp = config["column1"]
    col_time = config["column2"]
    col_mach = config["column3"]
    
    query = f"SELECT {col_emp}, {col_time}, {col_mach} FROM {table} ORDER BY {col_time} DESC"
    
    if db_type == "Oracle":
        query = f"SELECT * FROM (SELECT {col_emp}, {col_time}, {col_mach} FROM {table} ORDER BY {col_time} DESC) WHERE ROWNUM <= 10"
    else:
        query = f"{query} LIMIT 10"
        
    cursor.execute(query)
    rows = cursor.fetchall()
    
    print(f"Latest 10 rows in {table}:")
    for r in rows:
        print(f"  EmpNo: {r[0]}, SwapTime: {r[1]}, IP/SN: {r[2]}")
        
    cursor.close()
    conn.close()
except Exception as e:
    print(f"Error querying logs: {e}")
