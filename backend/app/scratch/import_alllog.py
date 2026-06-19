"""
import_alllog.py
---------------
Imports AllLog.txt (from FKAttendDIICSSample) into Oracle via UTAS db layer.
Run from: e:\Projects\ZK\SUFI_LAST\sourse_code_ZKTECO\backend\app

AllLog.txt format:
No.    EnrNo    Verify    InOut    DateTime
1      1        33        2        2026/04/14 21:47:00
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'zk'))

from datetime import datetime

ALLLOG_PATH = r"E:\Projects\DFace_C#_202006\SDKDEMO\c#\bin\x86\Debug\AllLog.txt"
MACHINE_SN  = "AMT602511730"   # AMF-60 device serial number

class Record:
    def __init__(self, user_id, timestamp, verify, inout):
        self.user_id   = str(user_id)
        self.timestamp = timestamp   # datetime object or string
        self.status    = verify      # verify mode (33 = face)
        self.punch     = inout       # 0=check-in, 2=check-out, 3=break-out, 1=break-in

def parse_alllog(path):
    records = []
    skipped = 0
    with open(path, 'r', encoding='utf-8') as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith("No."):
                continue
            parts = line.split('\t')
            if len(parts) < 5:
                skipped += 1
                continue
            try:
                _, enr_no, verify, inout, dt_str = parts[0], parts[1], parts[2], parts[3], parts[4]
                # Parse datetime: "2026/04/14 21:47:00"
                timestamp = datetime.strptime(dt_str.strip(), "%Y/%m/%d %H:%M:%S")
                records.append(Record(enr_no.strip(), timestamp, int(verify), int(inout)))
            except Exception as e:
                skipped += 1
                print(f"  Line {lineno} skipped: {e} — {line!r}")
    print(f"Parsed {len(records)} records ({skipped} skipped)")
    return records

def main():
    from zk import db

    print(f"Reading: {ALLLOG_PATH}")
    records = parse_alllog(ALLLOG_PATH)
    if not records:
        print("No records to import.")
        return

    print(f"Connecting to database...")
    db_type = db.get_active_db_type()
    print(f"DB type: {db_type}")

    try:
        print(f"Inserting {len(records)} records for machine {MACHINE_SN}...")
        db.insert_log_generic(records, MACHINE_SN, db_type)
        print(f"\n✓ Successfully imported {len(records)} records into {db_type}")
        print(f"  Date range: {records[0].timestamp} → {records[-1].timestamp}")
        print(f"  Unique users: {len(set(r.user_id for r in records))}")
    except Exception as e:
        print(f"\n✗ Import failed: {e}")
        import traceback; traceback.print_exc()

if __name__ == "__main__":
    main()
