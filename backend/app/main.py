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

from fastapi import FastAPI, Request, BackgroundTasks, Query, HTTPException, Depends, status
from fastapi.responses import HTMLResponse, PlainTextResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from dotenv import load_dotenv
from pydantic import BaseModel
from jose import JWTError, jwt
from passlib.context import CryptContext
from collections import deque

load_dotenv()

# --- SECURITY CONFIG ---
SECRET_KEY = os.getenv("JWT_SECRET", "super-secret-key-123")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 # 1 day

# Initialize DB
db = None
try:
    from .zk import db
except ImportError:
    pass

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")

ADMIN_USERNAME = os.getenv("ADMIN_USER", "admin")
# Default password is 'admin123' if not set in .env
ADMIN_PASS_HASH = os.getenv("ADMIN_PASS_HASH", "$2b$12$HsX55kfXFpUGdXatBVl48OaojBm56HI0ZntORMuokZ0ISM/is.kh2")

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

# --- LOG TRACKING FOR UI ---
class DequeHandler(logging.Handler):
    def __init__(self, maxlen=100):
        super().__init__()
        self.logs = deque(maxlen=maxlen)

    def emit(self, record):
        msg = self.format(record)
        self.logs.append({
            "time": datetime.datetime.now().strftime("%H:%M:%S"),
            "level": record.levelname,
            "msg": msg
        })

log_buffer = DequeHandler()
log_buffer.setFormatter(logging.Formatter("%(message)s"))

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s — %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("utas")
logger.addHandler(log_buffer)

from contextlib import asynccontextmanager

# ── Lifespan context manager ──────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    logger.info("[UTAS] Server starting — initialising pull engine...")
    pull_manager.start()
    
    yield
    
    # Shutdown logic
    logger.info("[UTAS] Server shutting down — disconnecting devices...")
    pull_manager.stop()

app = FastAPI(
    title="UTAS — Unified Time Attendance System",
    description="ZKTeco ADMS push server + pyzk pull engine",
    version="2.0.0",
    lifespan=lifespan
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

# Queue for ADMS device commands (Push)
COMMAND_QUEUE = {}


# ── Auth Utilities ───────────────────────────────────────────────────────────
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.datetime.utcnow() + datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    return username

# ── Pydantic models ───────────────────────────────────────────────────────────
class LoginIn(BaseModel):
    username: str
    password: str

class ControlIn(BaseModel):
    action: str # "start" or "stop"

class MachineIn(BaseModel):
    ip: str
    port: int = 4370
    location: str = ""
    password: int = 0
    sn: str = ""
    protocol: str = "TCP" # TCP or HTTP
    company_name: str = "None"
class TestConnectionIn(BaseModel):
    ip: str
    port: int = 4370
    password: int = 0

class CompanyMapIn(BaseModel):
    company_name: str
    sns: list[str]




# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 1 — Push (ADMS) endpoints  (unchanged)
# ═══════════════════════════════════════════════════════════════════════════════

def log(msg):
    print(f"[{datetime.datetime.now()}] {msg}")

def register_push_device(sn: str, ip: str):
    """Auto-detect and add new push devices to the registry."""
    if not sn:
        return
    
    # Register pulse heartbeat
    pull_manager.update_pulse(sn)

    # Check if already registered
    existing = pull_manager.get_machine(sn=sn)
    if not existing:
        logger.info(f"[AUTODETECT] New Push device found: SN={sn} from IP={ip}")
        company_val = "None"
        if db:
            try:
                config_db = db.load_latest_config("Oracle")
                conn = db.connect_db_oracle(config_db)
                meta = db.get_machine_meta(conn)
                conn.close()
                if sn in meta:
                    company_val = meta[sn].get("company_name", "None")
            except Exception as e:
                logger.error(f"[AUTODETECT] Failed to fetch company metadata: {e}")

        try:
            m = MachineIn(
                ip=ip,
                sn=sn,
                location="Auto-Detected (Push)",
                port=4370,
                password=0,
                protocol="HTTP",
                company_name=company_val
            )
            # dict() instead of model_dump() for backwards compatibility, or just use what works
            pull_manager.add_machine(m.dict() if hasattr(m, "dict") else m.model_dump())
        except Exception as e:
            logger.error(f"[AUTODETECT] Failed to register {sn}: {e}")
    else:
        # BUG FIX: Force update protocol to HTTP if it's currently TCP/None for a push device
        if existing.get("protocol") != "HTTP":
            pull_manager.update_machine_metadata(sn, "HTTP", existing.get("company_name", "None"))
            logger.info(f"[AUTODETECT] Corrected protocol for {sn} to HTTP")



def process_attendance_data(sn: str, raw_data: str):
    """Background task: parse ADMS push data and insert to Oracle."""
    # MANDATORY CHECK: Machine must be assigned to a company
    state = pull_manager.get_machine(sn=sn)
    company = state.get("company_name") if state else "None"
    
    if company in ["None", "", None]:
        logger.warning(f"[PUSH ACCESS DENIED] Data from {sn} ignored - Machine not registered to a company.")
        return

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
    ip = request.client.host
    register_push_device(SN, ip)

    if request.method == 'GET':
        log(f"Device {SN} Heartbeat (GET) from {ip}")
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
async def get_request(request: Request, SN: Optional[str] = Query(None)):
    ip = request.client.host
    if SN:
        register_push_device(SN, ip)
        log(f"Device {SN} getrequest from {ip}")
        if SN in COMMAND_QUEUE and COMMAND_QUEUE[SN]:
            cmd = COMMAND_QUEUE[SN].pop(0)
            log(f"Sending queued command to {SN}: {cmd}")
            return cmd
    return "OK"


@app.post("/iclock/devicecmd", response_class=PlainTextResponse)
async def device_cmd(request: Request, SN: Optional[str] = Query(None)):
    body = await request.body()
    log(f"Device {SN} cmd result: {body.decode(errors='ignore').strip()}")
    return "OK"


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 1.5 — Auth & Admin endpoints
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/api/auth/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    if form_data.username != ADMIN_USERNAME or not verify_password(form_data.password, ADMIN_PASS_HASH):
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    
    access_token = create_access_token(data={"sub": form_data.username})
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/api/admin/server/logs", dependencies=[Depends(get_current_user)])
async def get_server_logs():
    return list(log_buffer.logs)

@app.get("/api/admin/server/status", dependencies=[Depends(get_current_user)])
async def get_server_status():
    return {
        "enabled": pull_manager.enabled,
        "scheduler_running": pull_manager._scheduler.running
    }

@app.post("/api/admin/server/control", dependencies=[Depends(get_current_user)])
async def control_server(body: ControlIn):
    if body.action == "start":
        pull_manager.enabled = True
        logger.info("[Admin] Pull Engine ENABLED by user")
    elif body.action == "stop":
        pull_manager.enabled = False
        logger.info("[Admin] Pull Engine DISABLED by user")
    return {"success": True, "enabled": pull_manager.enabled}

# ── Machine management ────────────────────────────────────────────────────────

@app.get("/pull/machines", dependencies=[Depends(get_current_user)])
async def list_machines():
    """List all machines with their live status."""
    return pull_manager.get_all_status()


@app.post("/pull/machines", dependencies=[Depends(get_current_user)])
async def add_machine(machine: MachineIn):
    """Add a new machine (writes to machines.json)."""
    result = pull_manager.add_machine(machine.dict())
    return result


@app.get("/api/admin/companies", dependencies=[Depends(get_current_user)])
async def list_companies():
    """Return a list of unique company names registered in the system."""
    try:
        config_db = db.load_latest_config("Oracle")
        conn = db.connect_db_oracle(config_db)
        meta = db.get_machine_meta(conn)
        conn.close()
        # Extract unique company names
        companies = sorted(list(set(m.get("company_name", "None") for m in meta.values())))
        return {"success": True, "companies": companies}
    except Exception as e:
        logger.error(f"[Admin] Failed to fetch companies: {e}")
        return {"success": False, "error": str(e), "companies": ["None"]}

@app.post("/api/admin/companies/map", dependencies=[Depends(get_current_user)])
async def map_devices_to_company(body: CompanyMapIn):
    """Bulk link a list of Serial Numbers to a Company Name."""
    try:
        config_db = db.load_latest_config("Oracle")
        conn = db.connect_db_oracle(config_db)
        
        for sn in body.sns:
            # 1. Update Oracle
            state = pull_manager.get_machine(sn=sn)
            ip = state.get("ip", "0.0.0.0") if state else "0.0.0.0"
            
            # Use current protocol or default to HTTP if SN mapping is happening
            proto = state.get("protocol", "HTTP")
            
            db.upsert_machine_meta(conn, sn, ip, proto, body.company_name)
            
            # 2. Update In-Memory Engine
            pull_manager.update_machine_metadata(sn, proto, body.company_name)
            
        conn.close()
        return {"success": True, "message": f"Mapped {len(body.sns)} devices to {body.company_name}"}
    except Exception as e:
        logger.error(f"[Admin] Mapping failed: {e}")
        return {"success": False, "error": str(e)}

@app.delete("/pull/machines/{sn}", dependencies=[Depends(get_current_user)])
async def remove_machine(sn: str):
    """Remove a machine by serial number."""
    return pull_manager.remove_machine(sn=sn)


@app.post("/pull/machines/test-connection", dependencies=[Depends(get_current_user)])
def test_connection(body: TestConnectionIn):
    """
    Test connectivity to a machine before adding it.
    Returns firmware, SN, device name on success.
    Used by the UI 'Add Machine' flow.
    """
    return pull_manager.test_connection(body.ip, body.port, body.password)


@app.post("/pull/machines/reload", dependencies=[Depends(get_current_user)])
async def reload_machines():
    """Hot-reload machines.json without server restart."""
    pull_manager.reload()
    return {"success": True, "machines": len(machines_config.load_machines())}


# ── Attendance pull ───────────────────────────────────────────────────────────

@app.post("/pull/attendance/{sn}", dependencies=[Depends(get_current_user)])
def manual_pull(sn: str):
    """Manually trigger a one-shot attendance pull from the given machine."""
    result = pull_manager.pull_once(sn=sn)
    return result


@app.get("/pull/attendance/logs", dependencies=[Depends(get_current_user)])
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

@app.get("/pull/device-info/{sn}", dependencies=[Depends(get_current_user)])
def device_info(sn: str):
    """Get firmware version, serial number, memory stats from a device."""
    return pull_manager.get_device_info(sn=sn)


@app.post("/pull/clear-attendance/{sn}", dependencies=[Depends(get_current_user)])
def clear_attendance(sn: str):
    """Clear attendance log on the device (password-protected in UI)."""
    state = pull_manager.get_machine(sn=sn)
    if state and state.get("protocol") == "HTTP":
        if sn not in COMMAND_QUEUE:
            COMMAND_QUEUE[sn] = []
        COMMAND_QUEUE[sn].append("C:1:CLEAR LOG")
        return {"success": True, "message": "Command queued for Push device. Logs will clear shortly."}
        
    return pull_manager.clear_attendance(sn=sn)


@app.post("/pull/sync-time/{sn}", dependencies=[Depends(get_current_user)])
def sync_time(sn: str):
    """Sync device clock to server time."""
    return pull_manager.sync_time(sn=sn)


# ── Dashboard stats ───────────────────────────────────────────────────────────

@app.get("/pull/stats", dependencies=[Depends(get_current_user)])
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

    # Get unique companies count
    comp_count = 0
    try:
        config_db = db.load_latest_config("Oracle")
        conn = db.connect_db_oracle(config_db)
        meta = db.get_machine_meta(conn)
        conn.close()
        comp_count = len(set(m.get("company_name", "None") for m in meta.values()))
    except: pass

    return {
        "total_machines":  len(machines),
        "online_machines": online,
        "records_today":   record_count,
        "total_companies": comp_count,
        "recent_push_logs": len(RECENT_LOGS),
        "sync_interval_seconds": int(os.getenv("PULL_SYNC_INTERVAL", "20")),
    }


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    log(f"[*] Starting UTAS Server on 0.0.0.0:{SERVER_PORT}")
    uvicorn.run(app, host="0.0.0.0", port=SERVER_PORT)
