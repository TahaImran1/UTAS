import os
import sys
import subprocess
import datetime
from typing import Optional

# --- AUTO-INSTALL DEPENDENCIES ---
def install_requirements():
    req_path = os.path.join(os.path.dirname(__file__), "..", "requirements.txt")
    if os.path.exists(req_path):
        print(f"[*] Checking/Installing dependencies from {req_path}...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "-r", req_path])
        except Exception as e:
            print(f"[!] Error auto-installing dependencies: {e}")

install_requirements()
# ---------------------------------

from fastapi import FastAPI, Request, BackgroundTasks, Query
from fastapi.responses import HTMLResponse, PlainTextResponse
from dotenv import load_dotenv

load_dotenv()

# --- IN-MEMORY LOGS FOR VIEWER ---
RECENT_LOGS = []
# ---------------------------------

# Add current directory to path so we can import zk.db
sys.path.append(os.path.dirname(__file__))
sys.path.append(os.path.join(os.path.dirname(__file__), 'zk'))

try:
    from zk import db
except ImportError as e:
    print(f"[!] Warning: Could not import zk.db: {e}")
    db = None

app = FastAPI(title="UTAS")

# --- CONFIGURATION ---
SERVER_IP = "0.0.0.0" 
SERVER_PORT = int(os.getenv("SERVER_PORT", 4370)) 
# ---------------------

def log(msg):
    print(f"[{datetime.datetime.now()}] {msg}")

def process_attendance_data(sn: str, raw_data: str):
    """
    Asynchronously processes the attendance records in the background.
    """
    count = 0
    records = []
    
    # Parse lines
    lines = raw_data.splitlines()
    for line in lines:
        if not line.strip(): continue
        parts = line.split('\t')
        
        # Basic validation
        if len(parts) >= 2: 
            user_id = parts[0]
            check_time = parts[1]
            
            # Add to Web Viewer List
            RECENT_LOGS.append({
                'received_at': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'sn': sn,
                'user_id': user_id,
                'check_time': check_time
            })
            # Keep only last 100 logs in memory
            if len(RECENT_LOGS) > 100:
                RECENT_LOGS.pop(0)
            
            # Create record object for DB
            class Record:
                def __init__(self, uid, ts):
                    self.user_id = uid
                    self.timestamp = ts 
                    self.status = 1     
                    self.punch = 0      
            
            records.append(Record(user_id, check_time))
            count += 1
    
    log(f"Parsed {count} records from {sn}.")
    
    # --- DATABASE INSERTION ---
    if db and count > 0:
        try:
            for db_type in ["Oracle"]:
                try:
                    config = db.load_latest_config(db_type)
                    if config:
                        log(f"Background: Connecting to {db_type}...")
                        if db_type == "Oracle":
                            conn = db.connect_db_oracle(config)
                            db.insert_log_oracle(conn, records, sn, config)
                            conn.close()
                        log(f"Background: Saved to {db_type} successfully.")
                        break 
                except Exception as e:
                    log(f"Background: Failed to save to {db_type}: {e}")
        except Exception as e:
            log(f"Background: Database error: {e}")

@app.get("/", response_class=HTMLResponse)
async def index():
    return '<a href="/view"><h2>Click here to view Attendance Logs</h2></a>'

@app.get("/view", response_class=HTMLResponse)
async def view_logs():
    html = """
    <html>
    <head>
        <title>ZKTeco Attendance Logs</title>
        <meta http-equiv="refresh" content="5"> 
        <style>
            body { font-family: sans-serif; padding: 20px; }
            table { border-collapse: collapse; width: 100%; }
            th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
            th { background-color: #f2f2f2; }
            tr:nth-child(even) { background-color: #f9f9f9; }
            h1 { color: #333; }
        </style>
    </head>
    <body>
        <h1>Live Attendance Logs (UTAS Mode)</h1>
        <p><i>Auto-refreshing every 5 seconds...</i></p>
        <table>
            <tr>
                <th>Time</th>
                <th>Device SN</th>
                <th>User ID</th>
                <th>Check Time</th>
            </tr>
            {rows}
        </table>
    </body>
    </html>
    """
    # Sort logs new to old
    sorted_logs = sorted(RECENT_LOGS, key=lambda x: x['received_at'], reverse=True)
    
    rows = ""
    for entry in sorted_logs:
        rows += f"""
        <tr>
            <td>{entry['received_at']}</td>
            <td>{entry['sn']}</td>
            <td>{entry['user_id']}</td>
            <td>{entry['check_time']}</td>
        </tr>
        """
    return html.format(rows=rows)

@app.api_route("/iclock/cdata", methods=["GET", "POST"], response_class=PlainTextResponse)
async def receive_cdata(
    request: Request,
    background_tasks: BackgroundTasks,
    SN: Optional[str] = Query(None),
    table: Optional[str] = Query(None)
):
    if request.method == 'GET':
        log(f"Device {SN} Heartbeat/Check (GET)")
        return "OK"

    if request.method == 'POST':
        if table == 'ATTLOG':
            log(f"Received ATTLOG from {SN} (Queuing for background)")
            try:
                body = await request.body()
                raw_data = body.decode('utf-8', errors='ignore')
            except:
                raw_data = ""
            
            # Queue the heavy DB work to background
            background_tasks.add_task(process_attendance_data, SN, raw_data)
            
            # Immediately tell the ZK device OK!
            return "OK"
            
        elif table == 'OPERLOG':
             log(f"Received OPERLOG from {SN} (Ignoring)")
             return "OK"
        
        else:
            log(f"Received unknown table {table} from {SN}")
            return "OK"

@app.get("/iclock/getrequest", response_class=PlainTextResponse)
async def get_request():
    return "OK"

@app.post("/iclock/devicecmd", response_class=PlainTextResponse)
async def device_cmd():
    return "OK"

if __name__ == "__main__":
    import uvicorn
    log(f"[*] Starting UTAS Server on {SERVER_IP}:{SERVER_PORT}")
    uvicorn.run(app, host=SERVER_IP, port=SERVER_PORT)
