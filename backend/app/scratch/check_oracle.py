import sys
import os
import json
import oracledb

# Add app paths
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "zk"))

from zk import db

def check():
    profiles = db.load_db_profiles()
    profile = profiles.get("taha db")
    if not profile:
        print("Profile 'taha db' not found!")
        return
        
    print("\nConnecting to Oracle...")
    try:
        conn = db.connect_db_oracle(profile)
        print("Connected successfully!")
        
        cursor = conn.cursor()
        
        # List sequences
        cursor.execute("SELECT sequence_name FROM user_sequences")
        seqs = [row[0] for row in cursor.fetchall()]
        print("Sequences in database:", seqs)
        
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Connection failed: {e}")

if __name__ == "__main__":
    check()
