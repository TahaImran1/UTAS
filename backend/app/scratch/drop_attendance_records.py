import sys
import os
import json
import oracledb

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "zk"))

from zk import db

def drop():
    profiles = db.load_db_profiles()
    profile = profiles.get("taha db")
    if not profile:
        print("Profile 'taha db' not found!")
        return
        
    print("Connecting to Oracle...")
    try:
        conn = db.connect_db_oracle(profile)
        print("Connected successfully!")
        
        cursor = conn.cursor()
        
        # Check if table exists
        table_name = "Attendance Records"
        print(f"Dropping table: {table_name}")
        try:
            cursor.execute(f'DROP TABLE "{table_name}"')
            conn.commit()
            print(f"Table '{table_name}' dropped successfully!")
        except Exception as drop_err:
            print(f"Failed to drop table (might not exist or drop failed): {drop_err}")
            
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Connection failed: {e}")

if __name__ == "__main__":
    drop()
