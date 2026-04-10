import os
import sys
import subprocess
import datetime
import logging
from typing import Optional

# ── Auto-install dependencies ────────────────────────────────────────────────
def install_requirements():
    req_path = os.path.join(os.path.dirname(__file__), "..", "requirements.txt")
    if os.path.exists(req_path):
        print(f"[*] Checking/Installing dependencies...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "-r", req_path])
        except Exception as e:
            print(f"[!] Error auto-installing dependencies: {e}")

install_requirements()
# ────────────────────────────────────────────────────────────────────────────

from fastapi import FastAPI, Request, BackgroundTasks, Query, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()

# ── Path setup ───────────────────────────────────────────────────────────────
sys.path.append(os.path.dirname(__file__))
sys.path.append(os.path.join(os.path.dirname(__file__), 'zk'))

try:
    from zk import db
except ImportError as e:
    print(f"[!] Warning: Could not import zk.db: {e}")
    db = None

from pull_engine import pull_manager
import machines_config

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(name)s — %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("utas")

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="UTAS — Unified Time Attendance System",
    description="ZKTeco ADMS push server + pyzk pull engine",
    version="2.0.0"
)

# Allow Electron frontend on any local origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

SERVER_PORT = int(os.getenv("SERVER_PORT", 4370))

# ── In-memory push log (Phase 1 viewer) ────────────────────────────────────
RECENT_LOGS = []


# ── Pydantic models ───────────────────────────────────────────────────────────
class MachineIn(BaseModel):
    ip: str
    port: int = 4370
    location: str = ""
    password: int = 0
    sn: str = ""


class TestConnectionIn(BaseModel):
    ip: str
    port: int = 4370
    password: int = 0


# ── Lifespan events ───────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    logger.info("[UTAS] Server starting — initialising pull engine...")
    pull_manager.start()


@app.on_event("shutdown")
async def shutdown():
    logger.info("[UTAS] Server shutting down — disconnecting devices...")
    pull_manager.stop()


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 1 — Push (ADMS) endpoints  (unchanged)
# ═══════════════════════════════════════════════════════════════════════════════

def log(msg):
    print(f"[{datetime.datetime.now()}] {msg}")


def process_attendance_data(sn: str, raw_data: str):
    """Background task: parse ADMS push data and insert to Oracle."""
    count = 0
    records = []
    for line in raw_data.splitlines():
        if not line.strip():
            continue
        parts = line.split('\t')
        if len(parts) >= 2:
            user_id, check_time = parts[0], parts[1]
            RECENT_LOGS.append({
                'received_at': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'sn': sn, 'user_id': user_id, 'check_time': check_time
            })
            if len(RECENT_LOGS) > 100:
                RECENT_LOGS.pop(0)

            class Record:
                def __init__(self, uid, ts):
                    self.user_id = uid
                    self.timestamp = ts
                    self.status = 1
                    self.punch = 0

            records.append(Record(user_id, check_time))
            count += 1

    log(f"Parsed {count} records from {sn}.")
    if db and count > 0:
        try:
            config = db.load_latest_config("Oracle")
            if config:
                conn = db.connect_db_oracle(config)
                db.insert_log_oracle(conn, records, sn, config)
                conn.close()
                log(f"Saved {count} records to Oracle.")
        except Exception as e:
            log(f"DB error: {e}")


@app.get("/", response_class=HTMLResponse)
async def index():
    return '<a href="/view"><h2>Click here to view Attendance Logs</h2></a>'


@app.get("/view", response_class=HTMLResponse)
async def view_logs():
    sorted_logs = sorted(RECENT_LOGS, key=lambda x: x['received_at'], reverse=True)
    rows = "".join(f"""
        <tr>
            <td>{e['received_at']}</td><td>{e['sn']}</td>
            <td>{e['user_id']}</td><td>{e['check_time']}</td>
        </tr>""" for e in sorted_logs)
    return f"""<html><head><title>UTAS Attendance Logs</title>
    <meta http-equiv="refresh" content="5">
    <style>body{{font-family:sans-serif;padding:20px}}
    table{{border-collapse:collapse;width:100%}}
    th,td{{border:1px solid #ddd;padding:8px;text-align:left}}
    th{{background:#f2f2f2}}</style></head>
    <body><h1>Live Attendance Logs (Push)</h1>
    <table><tr><th>Time</th><th>Device SN</th><th>User ID</th><th>Check Time</th></tr>
    {rows}</table></body></html>"""


@app.api_route("/iclock/cdata", methods=["GET", "POST"], response_class=PlainTextResponse)
async def receive_cdata(
    request: Request,
    background_tasks: BackgroundTasks,
    SN: Optional[str] = Query(None),
    table: Optional[str] = Query(None)
):
    if request.method == 'GET':
        log(f"Device {SN} Heartbeat (GET)")
        return "OK"
    if table == 'ATTLOG':
        log(f"Received ATTLOG from {SN}")
        body = await request.body()
        raw_data = body.decode('utf-8', errors='ignore')
        background_tasks.add_task(process_attendance_data, SN, raw_data)
        return "OK"
    elif table == 'OPERLOG':
        return "OK"
    return "OK"


@app.get("/iclock/getrequest", response_class=PlainTextResponse)
async def get_request():
    return "OK"


@app.post("/iclock/devicecmd", response_class=PlainTextResponse)
async def device_cmd():
    return "OK"


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 2 — Pull endpoints  /pull/*
# ═══════════════════════════════════════════════════════════════════════════════

# ── Machine management ────────────────────────────────────────────────────────

@app.get("/pull/machines")
async def list_machines():
    """List all machines with their live status."""
    return pull_manager.get_all_status()


@app.post("/pull/machines")
async def add_machine(machine: MachineIn):
    """Add a new machine (writes to machines.json)."""
    result = pull_manager.add_machine(machine.dict())
    return result


@app.delete("/pull/machines/{sn}")
async def remove_machine(sn: str):
    """Remove a machine by serial number."""
    return pull_manager.remove_machine(sn=sn)


@app.post("/pull/machines/test-connection")
async def test_connection(body: TestConnectionIn):
    """
    Test connectivity to a machine before adding it.
    Returns firmware, SN, device name on success.
    Used by the UI 'Add Machine' flow.
    """
    return pull_manager.test_connection(body.ip, body.port, body.password)


@app.post("/pull/machines/reload")
async def reload_machines():
    """Hot-reload machines.json without server restart."""
    pull_manager.reload()
    return {"success": True, "machines": len(machines_config.load_machines())}


# ── Attendance pull ───────────────────────────────────────────────────────────

@app.post("/pull/attendance/{sn}")
async def manual_pull(sn: str):
    """Manually trigger a one-shot attendance pull from the given machine."""
    result = pull_manager.pull_once(sn=sn)
    return result


@app.get("/pull/attendance/logs")
async def get_attendance_logs(
    date: Optional[str] = Query(None, description="Filter by date YYYY-MM-DD"),
    sn:   Optional[str] = Query(None, description="Filter by machine SN"),
    limit: int = Query(200, description="Max rows to return")
):
    """
    Query attendance logs from Oracle.
    Used by the Attendance Logs page in the desktop app.
    """
    if not db:
        raise HTTPException(status_code=503, detail="Database module not available")
    try:
        config = db.load_latest_config("Oracle")
        conn = db.connect_db_oracle(config)
        cursor = conn.cursor()

        table    = config["table"]
        col_emp  = config["column1"]
        col_time = config["column2"]
        col_mach = config["column3"]

        query = f"SELECT {col_emp}, {col_time}, {col_mach} FROM {table}"
        params = {}
        conditions = []

        if date:
            conditions.append(f"TRUNC({col_time}) = TO_DATE(:date_val, 'YYYY-MM-DD')")
            params["date_val"] = date
        if sn:
            conditions.append(f"{col_mach} LIKE :sn_val")
            params["sn_val"] = f"%{sn}%"

        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += f" ORDER BY {col_time} DESC FETCH FIRST :limit ROWS ONLY"
        params["limit"] = limit

        cursor.execute(query, params)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        return [
            {"user_id": r[0], "timestamp": str(r[1]), "machine": r[2]}
            for r in rows
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Device management ─────────────────────────────────────────────────────────

@app.get("/pull/device-info/{sn}")
async def device_info(sn: str):
    """Get firmware version, serial number, memory stats from a device."""
    return pull_manager.get_device_info(sn=sn)


@app.post("/pull/clear-attendance/{sn}")
async def clear_attendance(sn: str):
    """Clear attendance log on the device (password-protected in UI)."""
    return pull_manager.clear_attendance(sn=sn)


@app.post("/pull/sync-time/{sn}")
async def sync_time(sn: str):
    """Sync device clock to server time."""
    return pull_manager.sync_time(sn=sn)


# ── Dashboard stats ───────────────────────────────────────────────────────────

@app.get("/pull/stats")
async def dashboard_stats():
    """
    Aggregate stats for the Dashboard page.
    Returns machine count, online count, today's record count.
    """
    machines = pull_manager.get_all_status()
    online = sum(1 for m in machines if m["status"] == "online")
    today  = datetime.date.today().isoformat()

    record_count = 0
    if db:
        try:
            config = db.load_latest_config("Oracle")
            conn = db.connect_db_oracle(config)
            cursor = conn.cursor()
            table    = config["table"]
            col_time = config["column2"]
            cursor.execute(
                f"SELECT COUNT(*) FROM {table} WHERE TRUNC({col_time}) = TRUNC(SYSDATE)"
            )
            record_count = cursor.fetchone()[0]
            cursor.close()
            conn.close()
        except Exception as e:
            logger.error(f"Stats query failed: {e}")

    return {
        "total_machines":  len(machines),
        "online_machines": online,
        "records_today":   record_count,
        "recent_push_logs": len(RECENT_LOGS),
        "sync_interval_seconds": int(os.getenv("PULL_SYNC_INTERVAL", "20")),
    }


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    log(f"[*] Starting UTAS Server on 0.0.0.0:{SERVER_PORT}")
    uvicorn.run(app, host="0.0.0.0", port=SERVER_PORT)
