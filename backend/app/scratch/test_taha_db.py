import sys
import os
import json
import oracledb
import datetime

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "zk"))

from zk import db
from collections import namedtuple

DummyRecord = namedtuple("DummyRecord", ["user_id", "timestamp"])

def test():
    profiles = db.load_db_profiles()
    profile = profiles.get("taha db")
    if not profile:
        print("Profile 'taha db' not found!")
        return
        
    print("Using profile:", json.dumps(profile, indent=2))
    
    try:
        conn = db.connect_db_oracle(profile)
        print("Connected and ensure_tables completed successfully!")
        
        # Verify if table was created
        cursor = conn.cursor()
        cursor.execute('SELECT column_name, data_type, identity_column FROM user_tab_cols WHERE table_name = \'Attendance Records\'')
        cols = cursor.fetchall()
        print("Table columns:")
        for col in cols:
            print(f" - {col[0]}: {col[1]} (Identity: {col[2]})")
            
        # Test insert of a dummy record
        records = [DummyRecord(user_id="12345", timestamp=datetime.datetime.now())]
        print("Testing record insertion...")
        db.insert_log_oracle(conn, records, "TEST_MACHINE_123", profile)
        print("Insertion successful!")
        
        # Verify inserted record
        cursor.execute('SELECT * FROM "Attendance Records" WHERE "Emp ID" = \'12345\'')
        row = cursor.fetchone()
        print("Fetched inserted row:", row)
        
        # Clean up test row
        cursor.execute('DELETE FROM "Attendance Records" WHERE "Emp ID" = \'12345\'')
        conn.commit()
        print("Cleaned up test row.")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print("Test failed with error:", e)

if __name__ == "__main__":
    test()
