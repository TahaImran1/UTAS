import os
import sys
from dotenv import load_dotenv
import oracledb

load_dotenv()

host = os.getenv("ORACLE_HOST", "localhost")
port = os.getenv("ORACLE_PORT", "1521")
username = os.getenv("ORACLE_USER", "HR")
password = os.getenv("ORACLE_PASSWORD", "")
dbname = os.getenv("ORACLE_SERVICE_NAME", "orcl")
table_name = os.getenv("ORACLE_TABLE", "hr_emp_inout_detail").strip().upper()

print(f"Connecting to Oracle {username}@{host}:{port}/{dbname}...")

try:
    dsn_tns = oracledb.makedsn(host, port, service_name=dbname)
    conn = oracledb.connect(user=username, password=password, dsn=dsn_tns)
    cursor = conn.cursor()
    
    # Check count
    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
    count = cursor.fetchone()[0]
    print(f"Total rows in {table_name}: {count}")
    
    if count > 0:
        cursor.execute(f"SELECT * FROM {table_name} ORDER BY 1 DESC FETCH FIRST 5 ROWS ONLY")
        rows = cursor.fetchall()
        print(f"Latest records:")
        for r in rows:
            print(r)
            
    cursor.close()
    conn.close()
except Exception as e:
    print("Error:", e)
