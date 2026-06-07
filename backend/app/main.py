import os
import sys
import subprocess
import datetime
import logging
import time
import psutil
import threading
import json
from typing import Optional, List

# â”€â”€ Auto-install dependencies â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def install_requirements():
    req_path = os.path.join(os.path.dirname(__file__), "..", "requirements.txt")
    if os.path.exists(req_path):
        print(f"[*] Checking/Installing dependencies...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "-r", req_path])
        except Exception as e:
            print(f"[!] Error auto-installing dependencies: {e}")

install_requirements()
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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

# â”€â”€ Path setup â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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

import sys
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s â€” %(message)s"))
root_logger.addHandler(console_handler)

logger = logging.getLogger("utas")
logger.addHandler(log_buffer)
logger.propagate = True

from contextlib import asynccontextmanager

# â”€â”€ Lifespan context manager â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    logger.info("[UTAS] Server starting â€” initialising pull engine...")
    pull_manager.start()
    
    yield
    
    # Shutdown logic
    logger.info("[UTAS] Server shutting down â€” disconnecting devices...")
    pull_manager.stop()

app = FastAPI(
    title="UTAS â€” Unified Time Attendance System",
    description="ZKTeco ADMS push server + pyzk pull engine",
    version="2.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# â”€â”€ AMF60 / ZKTeco path-normalizer middleware â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Some devices (e.g. AMF60) POST to '//' (double slash) because they have no
# configurable server path. This middleware rewrites any double-slash path to
# the standard ZKTeco ADMS endpoint /iclock/cdata so routing works correctly.
from starlette.types import ASGIApp, Receive, Send, Scope

class PathNormalizerMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] == "http":
            path: str = scope.get("path", "/")
            raw_path: bytes = scope.get("raw_path", b"/")

            # AMF60 and similar devices POST to '//' (double slash) which
            # uvicorn normalizes to '/'. Detect this via raw_path or by
            # checking if a root-path request comes from a device IP
            is_double_slash = raw_path in (b"//", b"///")
            is_root_from_device = (path == "/" and scope.get("method", "") == "POST")

            if is_double_slash or is_root_from_device:
                scope = dict(scope)
                scope["path"] = "/iclock/cdata"
                scope["raw_path"] = b"/iclock/cdata"
        await self.app(scope, receive, send)

app.add_middleware(PathNormalizerMiddleware)

# â”€â”€ Metrics Tracking â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
SERVER_START_TIME = time.time()
REQUEST_METRICS = {
    "total_requests": 0,
    "status_codes": {},
    "avg_latency": 0.0,
    "total_latency": 0.0
}

@app.middleware("http")
async def amf60_diagnostics_middleware(request: Request, call_next):
    client_ip = request.client.host
    # Check if request is from AMF-60 IP or contains FK push headers/params
    is_amf60 = (
        client_ip == "192.168.100.67"
        or "192.168.100.67" in str(request.url)
        or request.headers.get("request_code") is not None
        or request.headers.get("dev_id") is not None
    )

    if is_amf60:
        # Read request body without consuming it permanently
        body_bytes = await request.body()
        
        async def receive():
            return {"type": "http.request", "body": body_bytes, "more_body": False}
        request._receive = receive

        # Log to file in the scratch directory
        log_dir = os.path.join(os.path.dirname(__file__), "scratch")
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, "amf60_raw_requests.log")

        with open(log_file, "a", encoding="utf-8") as f:
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
            f.write(f"=== RECEIVED REQUEST AT {now} ===\n")
            f.write(f"Client IP: {client_ip}\n")
            f.write(f"Method: {request.method}\n")
            f.write(f"URL: {request.url}\n")
            f.write("Headers:\n")
            for k, v in request.headers.items():
                f.write(f"  {k}: {v}\n")
            f.write(f"Body length: {len(body_bytes)} bytes\n")
            if body_bytes:
                f.write("Body (Hex):\n")
                f.write(f"  {body_bytes.hex()}\n")
                f.write("Body (Decoded Text - UTF-8 / ASCII):\n")
                f.write(f"  {body_bytes.decode('utf-8', errors='ignore')}\n")
            f.write("=" * 60 + "\n\n")

    response = await call_next(request)
    return response


@app.middleware("http")
async def health_monitor_middleware(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    
    # Update metrics
    REQUEST_METRICS["total_requests"] += 1
    status_code = response.status_code
    REQUEST_METRICS["status_codes"][status_code] = REQUEST_METRICS["status_codes"].get(status_code, 0) + 1
    REQUEST_METRICS["total_latency"] += process_time
    REQUEST_METRICS["avg_latency"] = REQUEST_METRICS["total_latency"] / REQUEST_METRICS["total_requests"]
    
    return response

SERVER_PORT = int(os.getenv("SERVER_PORT", 4370))

# â”€â”€ In-memory push log (Phase 1 viewer) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
RECENT_LOGS = []

# Queue for ADMS device commands (Push)
COMMAND_QUEUE = {}

# Tracks FK devices that have already been sent the initial get_glog command
FK_SYNCED_DEVICES = set()


# â”€â”€ Auth Utilities â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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

# â”€â”€ Pydantic models â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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
    driver: str = "zk"  # zk | fk (amt alias)
    machine_no: int = 1
    license: int = 1262
    net_password: int = 0
    pull_port: Optional[int] = None
class TestConnectionIn(BaseModel):
    ip: str
    port: int = 4370
    password: int = 0
    driver: str = "zk"
    license: int = 1262
    machine_no: int = 1

class CompanyMapIn(BaseModel):
    company_name: str
    sns: list[str]




# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# PHASE 1 â€” Push (ADMS) endpoints  (unchanged)
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

def log(msg):
    logger.info(msg)

def register_push_device(sn: str, ip: str, fk_protocol: bool = False):
    """Auto-detect push devices (ZKTeco ADMS or FK/AMT dual-mode)."""
    if not sn:
        return
    
    pull_manager.update_pulse(sn)

    existing = pull_manager.get_machine(sn=sn)
    if not existing:
        label = "FK" if fk_protocol else "Push"
        logger.info(f"[AUTODETECT] New {label} device: SN={sn} from IP={ip}")
        company_val = "None"
        if db:
            try:
                db_type = db.get_active_db_type()
                config_db = db.load_latest_config(db_type)
                if db_type == "Oracle":
                    conn = db.connect_db_oracle(config_db)
                else:
                    conn = db.connect_db_postgresql(config_db)
                meta = db.get_machine_meta(conn, db_type=db_type)
                conn.close()
                if sn in meta:
                    company_val = meta[sn].get("company_name", "None")
            except Exception as e:
                logger.error(f"[AUTODETECT] Failed to fetch company metadata: {e}")

        try:
            if fk_protocol:
                m = MachineIn(
                    ip=ip,
                    sn=sn,
                    location="Auto-Detected (FK)",
                    port=5005,
                    password=0,
                    protocol="TCP",
                    driver="fk",
                    company_name=company_val,
                )
            else:
                m = MachineIn(
                    ip=ip,
                    sn=sn,
                    location="Auto-Detected (Push)",
                    port=4370,
                    password=0,
                    protocol="HTTP",
                    company_name=company_val,
                )
            # dict() instead of model_dump() for backwards compatibility, or just use what works
            pull_manager.add_machine(m.model_dump())
        except Exception as e:
            logger.error(f"[AUTODETECT] Failed to register {sn}: {e}")
    else:
        current_proto = existing.get("protocol")
        current_driver = (existing.get("driver") or "zk").lower()
        current_company = existing.get("company_name", "None")
        updated_company = current_company

        if fk_protocol and current_driver not in ("fk", "amt"):
            pull_manager.update_fk_device_metadata(sn, company=current_company)
        elif not fk_protocol and current_proto != "HTTP":
            pull_manager.update_machine_metadata(sn, "HTTP", current_company)

        if current_company == "None" and db:
            try:
                db_type = db.get_active_db_type()
                config_db = db.load_latest_config(db_type)
                if db_type == "Oracle":
                    conn = db.connect_db_oracle(config_db)
                else:
                    conn = db.connect_db_postgresql(config_db)
                meta = db.get_machine_meta(conn, db_type=db_type)
                conn.close()
                if sn in meta:
                    db_company = meta[sn].get("company_name", "None")
                    if db_company != "None":
                        updated_company = db_company
                        logger.info(f"[AUTODETECT] Synced company for {sn} from database: {db_company}")
            except Exception as e:
                logger.error(f"[AUTODETECT] Failed to sync company metadata for {sn}: {e}")

        if not fk_protocol and (current_proto != "HTTP" or current_driver != "zk" or updated_company != current_company):
            pull_manager.update_machine_metadata(sn, "HTTP", updated_company)
            logger.info(f"[AUTODETECT] Updated metadata for {sn}: protocol=HTTP, company={updated_company}")
        elif fk_protocol and updated_company != current_company:
            pull_manager.update_fk_device_metadata(sn, company=updated_company)



def process_attendance_data(sn: str, raw_data: str):
    """Background task: parse ADMS push data and insert to Oracle."""
    # MANDATORY CHECK: Machine must be assigned to a company
    state = pull_manager.get_machine(sn=sn)
    company = state.get("company_name") if state else "None"
    logger.info(f"[PROCESS ATT] SN={sn} company={company} raw_len={len(raw_data)} preview={raw_data[:120]!r}")

    if company in ["None", "", None]:
        logger.warning(f"[PUSH ACCESS DENIED] Data from {sn} ignored — no company assigned. Assign a company first.")
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
            db_type = db.get_active_db_type()
            db.insert_log_generic(records, sn, db_type)
            log(f"Saved {count} records to {db_type}.")
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
    body_bytes = await request.body()
    body_text = body_bytes.decode('utf-8', errors='ignore')

    req_code = request.headers.get("request_code")
    dev_id = request.headers.get("dev_id")

    # Handle FK protocol devices (like AMF60)
    if req_code or dev_id:
        SN = dev_id or SN
        register_push_device(SN, ip, fk_protocol=True)

        # Echo FK protocol transactional headers
        trans_id = request.headers.get("trans_id")
        blk_no = request.headers.get("blk_no")

        def make_headers(response_code: str = "SUCCESS") -> dict:
            hdrs = {"response_code": response_code, "Connection": "close"}
            if trans_id is not None:
                hdrs["trans_id"] = trans_id
            if blk_no is not None:
                hdrs["blk_no"] = blk_no
            return hdrs

        # ── FULL DIAGNOSTIC DUMP ──────────────────────────────────────────
        hdrs = dict(request.headers)
        logger.info(f"[FK RAW] ip={ip} SN={SN} req_code={req_code} body_len={len(body_text)}")
        logger.info(f"[FK HDR] {hdrs}")
        if body_text.strip():
            safe_body = body_text[:500].encode('ascii', errors='backslashreplace').decode('ascii')
            logger.info(f"[FK BODY] {safe_body!r}")
        # ───────────────────────────────────────────────────────────────────

        log(f"[FK CDATA HIT] ip={ip} SN={SN} req_code={req_code}")

        # --- Robust JSON extraction (handles binary wrappers) ---
        data = {}
        try:
            # Find the first '{' character
            start = body_text.find('{')
            if start != -1:
                # Use JSONDecoder to find the exact end of the JSON object
                decoder = json.JSONDecoder()
                obj, end = decoder.raw_decode(body_text[start:])
                data = obj
                logger.info(f"[FK PUSH] Parsed JSON keys: {list(data.keys())}")
            else:
                logger.warning("[FK PUSH] No '{' found in body")
        except Exception as e:
            logger.error(f"[FK PUSH] JSON decode error: {e}")

        cloudtime = datetime.datetime.now().strftime("%Y%m%d%H%M%S")

        if req_code == "receive_cmd":
            logger.info(f"[DEBUG] COMMAND_QUEUE for {SN}: {COMMAND_QUEUE.get(SN)}")
            # Device polling for commands
            if SN and SN not in FK_SYNCED_DEVICES:
                FK_SYNCED_DEVICES.add(SN)
                log(f"[FK PUSH] Device {SN} registered")
                if SN not in COMMAND_QUEUE:
                    COMMAND_QUEUE[SN] = []
                COMMAND_QUEUE[SN].append("get_glog")
                logger.info(f"[FK AUTO-SYNC] Queued initial get_glog for {SN}")

            # Send queued command if any
            if SN and SN in COMMAND_QUEUE and COMMAND_QUEUE[SN]:
                cmd_entry = COMMAND_QUEUE[SN].pop(0)
                log(f"[FK PUSH] Sending command to {SN}: {cmd_entry}")
                if cmd_entry.startswith("C:"):
                    return PlainTextResponse(cmd_entry, headers=make_headers("SUCCESS"))
                elif cmd_entry == "get_glog":
                    end_ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    resp = json.dumps({
                        "ret": "ok", "result": True,
                        "cloudtime": cloudtime, "wait": 0,
                        "data": {
                            "cmd": "get_glog",
                            "cmdid": 1,
                            "starttime": "2020-01-01 00:00:00",
                            "endtime": end_ts
                        }
                    })
                    return PlainTextResponse(resp, media_type="application/json",
                                            headers=make_headers("SUCCESS"))
                else:
                    resp = json.dumps({"ret": "ok", "result": True, "cmd": cmd_entry, "cloudtime": cloudtime})
                    return PlainTextResponse(resp, media_type="application/json",
                                            headers=make_headers("SUCCESS"))
            else:
                resp = json.dumps({"ret": "ok", "result": False, "cloudtime": cloudtime})
                return PlainTextResponse(resp, media_type="application/json",
                                        headers=make_headers("ERROR_NO_CMD"))

        elif req_code in ("get_glog", "getalllog", "get_attlog"):
            # Bulk log upload from device
            log(f"[FK PUSH] Received {req_code} bulk data from {SN} — body_len={len(body_text)}")
            raw = body_text.strip()
            if raw:
                try:
                    arr_match = re.search(r'\[.*\]', raw, re.DOTALL)
                    if arr_match:
                        records_json = json.loads(arr_match.group(0))
                        lines = []
                        for rec in records_json:
                            uid = rec.get("user_id") or rec.get("uid") or rec.get("pin")
                            ts = rec.get("io_time") or rec.get("time") or rec.get("checktime")
                            if uid and ts and len(str(ts)) == 14:
                                ts_fmt = f"{ts[0:4]}-{ts[4:6]}-{ts[6:8]} {ts[8:10]}:{ts[10:12]}:{ts[12:14]}"
                                lines.append(f"{uid}\t{ts_fmt}")
                        if lines:
                            background_tasks.add_task(process_attendance_data, SN, "\n".join(lines))
                    else:
                        background_tasks.add_task(process_attendance_data, SN, raw)
                except Exception:
                    background_tasks.add_task(process_attendance_data, SN, raw)
            return PlainTextResponse("result=OK", media_type="text/plain",
                                    headers=make_headers("SUCCESS"))

        elif req_code == "realtime_glog":
            # Realtime attendance log push from FK device (e.g. AMF60)
            user_id = data.get("user_id")
            io_time = str(data.get("io_time", ""))
            check_time = None

            if user_id and io_time:
                if len(io_time) == 14:
                    # Compact format: YYYYMMDDHHmmss
                    check_time = f"{io_time[0:4]}-{io_time[4:6]}-{io_time[6:8]} {io_time[8:10]}:{io_time[10:12]}:{io_time[12:14]}"
                elif len(io_time) == 19:
                    # Already formatted: YYYY-MM-DD HH:mm:ss
                    check_time = io_time
                else:
                    logger.warning(f"[FK GLOG] Unexpected io_time format: {io_time!r} — attempting direct use")
                    check_time = io_time

            if user_id and check_time:
                log(f"[FK PUSH] Realtime attendance: user_id={user_id} time={check_time} from {SN}")
                background_tasks.add_task(process_attendance_data, SN, f"{user_id}\t{check_time}")
            else:
                logger.warning(f"[FK GLOG] Skipped — missing user_id={user_id!r} or io_time={io_time!r}")

            # Return JSON so the device does not retry
            resp = json.dumps({"ret": "ok", "result": True, "cloudtime": cloudtime})
            return PlainTextResponse(resp, media_type="application/json",
                                    headers=make_headers("SUCCESS"))

        elif req_code == "realtime_enroll_data":
            # Device is pushing a fingerprint enrollment record.
            # Parse the JSON header (the first part of the body before the binary blob).
            user_id = data.get("user_id", "unknown")
            user_name = data.get("user_name", "")
            privilege = data.get("user_privilege", "")
            enroll_array = data.get("enroll_data_array", [])
            backup_numbers = [e.get("backup_number") for e in enroll_array]
            log(f"[FK ENROLL] user_id={user_id} name={user_name} privilege={privilege} fingers={backup_numbers} from {SN}")
            # Respond with JSON so the device stops retrying
            resp = json.dumps({"ret": "ok", "result": True, "cloudtime": cloudtime})
            return PlainTextResponse(resp, media_type="application/json",
                                    headers=make_headers("SUCCESS"))

        else:
            # Acknowledge any other unhandled FK request with JSON (not plain text)
            # so the device does not retry indefinitely.
            logger.info(f"[FK PUSH] Unhandled req_code={req_code}, acknowledging with JSON ok")
            resp = json.dumps({"ret": "ok", "result": True, "cloudtime": cloudtime})
            return PlainTextResponse(resp, media_type="application/json",
                                    headers=make_headers("SUCCESS"))
            # --- FALLBACK: Standard ZKTeco ADMS Protocol ---
    # Unconditional debug log for standard push
    print(f"[CDATA HIT] ip={ip} SN={SN} table={table} method={request.method} body_len={len(body_text)} body_preview={body_text[:300]}")

    if not SN or not table:
        from urllib.parse import parse_qs
        try:
            parsed = parse_qs(body_text.split('\n')[0].strip())
            if not SN and 'SN' in parsed:
                SN = parsed['SN'][0]
            if not table and 'table' in parsed:
                table = parsed['table'][0]
        except Exception:
            pass

        if not SN:
            for line in body_text.splitlines():
                for part in line.replace('\t', '&').split('&'):
                    part = part.strip()
                    if part.upper().startswith('SN='):
                        SN = part.split('=', 1)[1].strip()
                        break
                if SN:
                    break
        if not table:
            for line in body_text.splitlines():
                for part in line.replace('\t', '&').split('&'):
                    part = part.strip()
                    if part.lower().startswith('table='):
                        table = part.split('=', 1)[1].strip()
                        break
                if table:
                    break

    register_push_device(SN, ip)

    if request.method == 'GET':
        log(f"Device {SN} Heartbeat (GET) from {ip}")
        return "OK"
    if table == 'ATTLOG':
        log(f"Received ATTLOG from {SN}")
        background_tasks.add_task(process_attendance_data, SN, body_text)
        return "OK"
    elif table == 'OPERLOG':
        return "OK"

    logger.info(f"[PUSH] Device SN={SN} table={table} from {ip} â€” body length={len(body_text)}")
    return "OK"


# Root handler removed â€” PathNormalizerMiddleware rewrites // â†’ /iclock/cdata


@app.get("/iclock/getrequest", response_class=PlainTextResponse)
async def get_request(request: Request, SN: Optional[str] = Query(None)):
    ip = request.client.host
    if SN:
        register_push_device(SN, ip, fk_protocol=False)
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


# â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• 
# PHASE 1.5 â€” Auth & Admin endpoints
# â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• 

# â”€â”€ User management â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def get_app_data_dir():
    app_data = os.getenv('APPDATA')
    if not app_data:
        app_data = os.path.expanduser("~")
    dir_path = os.path.join(app_data, "UTAS")
    os.makedirs(dir_path, exist_ok=True)
    return dir_path

APP_DATA_DIR = get_app_data_dir()
USERS_FILE = os.path.join(APP_DATA_DIR, "users.json")

class UserRegister(BaseModel):
    username: str
    password: str

def load_users():
    if os.path.exists(USERS_FILE):
        try:
            if os.path.getsize(USERS_FILE) == 0: return {}
            with open(USERS_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"[Auth] Error loading users.json: {e}")
            return {}
    return {}

def save_users(users):
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=4)

@app.post("/api/auth/register")
async def register(user: UserRegister):
    users = load_users()
    if user.username in users or user.username == ADMIN_USERNAME:
        raise HTTPException(status_code=400, detail="Username already exists")
    
    hashed_pass = pwd_context.hash(user.password)
    users[user.username] = {"password": hashed_pass}
    save_users(users)
    logger.info(f"[Auth] New user registered: {user.username}")
    return {"message": "User registered successfully"}

@app.post("/api/auth/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    username = form_data.username
    password = form_data.password
    
    # Check Admin
    if username == ADMIN_USERNAME:
        if verify_password(password, ADMIN_PASS_HASH):
            access_token = create_access_token(data={"sub": username})
            return {"access_token": access_token, "token_type": "bearer"}
    
    # Check Regular Users
    users = load_users()
    if username in users:
        if verify_password(password, users[username]["password"]):
            access_token = create_access_token(data={"sub": username})
            return {"access_token": access_token, "token_type": "bearer"}
            
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect username or password",
        headers={"WWW-Authenticate": "Bearer"},
    )

@app.get("/api/admin/server/logs", dependencies=[Depends(get_current_user)])
async def get_server_logs():
    return list(log_buffer.logs)

@app.get("/api/admin/server/status", dependencies=[Depends(get_current_user)])
async def get_server_status():
    return {
        "enabled": pull_manager.enabled,
        "scheduler_running": pull_manager._scheduler.running
    }

@app.get("/api/admin/health", dependencies=[Depends(get_current_user)])
async def get_health():
    """Detailed health check and performance metrics."""
    # Database Health
    db_status = "offline"
    db_latency = 0
    db_type = db.get_active_db_type()
    if db:
        try:
            start = time.time()
            config = db.load_latest_config(db_type)
            if db_type == "Oracle":
                conn = db.connect_db_oracle(config)
                cursor = conn.cursor()
                cursor.execute("SELECT 1 FROM DUAL")
                cursor.close()
                conn.close()
            else:
                conn = db.connect_db_postgresql(config)
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                cursor.close()
                conn.close()
            db_status = "online"
            db_latency = round((time.time() - start) * 1000, 2)
        except Exception as e:
            db_status = f"error: {str(e)}"

    # System Metrics
    cpu_usage = psutil.cpu_percent(interval=None)
    memory = psutil.virtual_memory()
    process = psutil.Process()
    process_mem = process.memory_info().rss / (1024 * 1024) # MB
    
    # Threading Metrics
    active_threads = threading.active_count()
    pull_threads = sum(1 for t in threading.enumerate() if t.name and t.name.startswith("pull-"))

    # Push Engine Status
    push_devices = sum(1 for m in pull_manager._machines.values() if m.protocol == "HTTP")
    push_online = sum(1 for m in pull_manager.get_all_status() if m.get("protocol") == "HTTP" and m.get("status") == "online")

    return {
        "status": "healthy",
        "timestamp": datetime.datetime.now().isoformat(),
        "uptime_seconds": int(time.time() - SERVER_START_TIME),
        "api": {
            "status": "online",
            "metrics": {
                "total_requests": REQUEST_METRICS["total_requests"],
                "avg_latency_ms": round(REQUEST_METRICS["avg_latency"] * 1000, 2),
                "status_codes": REQUEST_METRICS["status_codes"],
                "active_threads": active_threads
            }
        },
        "database": {
            "status": db_status,
            "latency_ms": db_latency,
            "type": db_type
        },
        "engine": {
            "status": "online" if pull_manager.enabled else "paused",
            "scheduler": "running" if pull_manager._scheduler.running else "stopped",
            "active_machines": len(pull_manager._machines),
            "sync_threads": pull_threads
        },
        "push_engine": {
            "status": "online",
            "total_devices": push_devices,
            "online_devices": push_online,
            "queue_size": sum(len(q) for q in COMMAND_QUEUE.values())
        },
        "system": {
            "cpu_percent": cpu_usage,
            "memory_percent": memory.percent,
            "process_memory_mb": round(process_mem, 2)
        }
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

# â”€â”€ Database Config Endpoints â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@app.get("/api/admin/database/config")
async def get_db_config(db_type: Optional[str] = None, user=Depends(get_current_user)):
    try:
        if not db_type:
            db_type = db.get_active_db_type()
        config = db.load_latest_config(db_type)
        return config
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.post("/api/admin/database/config")
async def update_db_config(body: dict, user=Depends(get_current_user)):
    config = body.get("config")
    is_active = body.get("active", False)
    
    if not config:
        raise HTTPException(status_code=400, detail="Missing configuration data")

    success = db.save_config(config)
    if success:
        db.set_active_db_type(config["database"])
        logger.info(f"[Database] Active DB set to {config['database']}")
        return {"status": "success", "message": "Database configuration updated."}
    else:
        raise HTTPException(status_code=500, detail="Failed to save database configuration.")

@app.post("/api/admin/database/test")
async def test_db_connection(config: dict, user=Depends(get_current_user)):
    try:
        if config.get("database") == "Oracle":
            conn = db.connect_db_oracle(config)
            conn.close()
        else:
            conn = db.connect_db_postgresql(config)
            conn.close()
        return {"status": "success", "message": "Connection successful!"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/api/admin/database/connect-check", dependencies=[Depends(get_current_user)])
async def connect_and_check(body: dict):
    """
    Step 1 of the DB wizard.
    Attempts to connect with the supplied credentials, then checks whether
    the attendance-log table and the machine-link table already exist.
    If both exist the config is saved immediately (no further steps needed).
    """
    try:
        config   = body.get("config", {})
        att_tbl  = body.get("att_table",     config.get("table",         "HR_EMP_INOUT_DETAIL"))
        mach_tbl = body.get("machine_table", config.get("machine_table", "COMP_MACHINE"))
        db_type  = config.get("database", "Oracle")

        conn   = db.connect_one_shot(config)
        checks = db.check_tables_exist(conn, db_type, att_tbl, mach_tbl)

        # Helper to find best column match
        def find_best(cols, targets, default):
            for t in targets:
                for c in cols:
                    if c.upper() == t.upper(): return c
            return default

        # Auto-map Attendance columns
        if checks["att_table_exists"]:
            att_cols = db.get_table_columns(conn, db_type, att_tbl)
            config["table"]   = att_tbl
            config["column1"] = find_best(att_cols, ["employee_no", "user_id", "emp_id", "badgenumber", "pin"], config.get("column1", "employee_no"))
            config["column2"] = find_best(att_cols, ["swap_time", "timestamp", "log_time", "checktime", "event_time"], config.get("column2", "swap_time"))
            config["column3"] = find_best(att_cols, ["machine_ref", "ip_address", "machine_sn", "sn", "device_id"], config.get("column3", "machine_ref"))
            # Optional PK and Sequence
            config["column_pk"] = find_best(att_cols, ["HR_ATT_LOG_ID", "ID", "LOG_ID", "PK"], config.get("column_pk", "HR_ATT_LOG_ID"))

        # Auto-map Machine columns
        if checks["machine_table_exists"]:
            mach_cols = db.get_table_columns(conn, db_type, mach_tbl)
            config["machine_table"] = mach_tbl
            config["col_sn"]      = find_best(mach_cols, ["SN", "SERIAL_NUMBER", "MACHINE_SN", "DEVICE_SN"], config.get("col_sn", "SN"))
            config["col_ip"]      = find_best(mach_cols, ["IP", "IP_ADDRESS", "ADDRESS", "HOST"], config.get("col_ip", "IP"))
            config["col_proto"]   = find_best(mach_cols, ["PROTOCOL", "COMM_TYPE", "PROTO"], config.get("col_proto", "PROTOCOL"))
            config["col_company"] = find_best(mach_cols, ["COMPANY_NAME", "COMPANY", "CLIENT", "ORG"], config.get("col_company", "COMPANY_NAME"))

        conn.close()

        both_exist = checks["att_table_exists"] and checks["machine_table_exists"]
        if both_exist or checks["att_table_exists"] or checks["machine_table_exists"]:
            # Save whatever we found/mapped
            db.save_config(config)
            logger.info(f"[Wizard] Auto-mapped and saved config for {db_type}")

        return {
            "status": "connected",
            "message": "Connection successful",
            "att_table_exists":     checks["att_table_exists"],
            "machine_table_exists": checks["machine_table_exists"],
            "both_exist":           both_exist,
            "detected_config":      config
        }
    except Exception as e:
        logger.error(f"[Wizard] connect-check failed: {e}")
        return {"status": "error", "message": str(e)}


@app.post("/api/admin/database/create-attendance-table", dependencies=[Depends(get_current_user)])
async def create_att_table(body: dict):
    """
    Step 3 of the DB wizard.
    Creates the attendance log table in the DB using the supplied config,
    then saves the full config to database.json.
    """
    try:
        config  = body.get("config", {})
        db_type = config.get("database", "Oracle")

        conn = db.connect_one_shot(config)
        db.create_attendance_table(conn, db_type, config)
        conn.close()

        db.save_config(config)
        logger.info(f"[Wizard] Attendance table created: {config.get('table')}")
        return {"status": "success", "message": f"Table '{config.get('table')}' created successfully."}
    except Exception as e:
        logger.error(f"[Wizard] create-attendance-table failed: {e}")
        return {"status": "error", "message": str(e)}


@app.post("/api/admin/database/create-machine-table", dependencies=[Depends(get_current_user)])
async def create_mach_table(body: dict):
    """
    Step 5 of the DB wizard.
    Creates the machine-link table in the DB using the supplied column names,
    then saves the updated config (with machine_table key) to database.json.
    """
    try:
        config      = body.get("config", {})
        db_type     = config.get("database", "Oracle")
        table_name  = body.get("machine_table", "COMP_MACHINE")
        col_sn      = body.get("col_sn",      "SN")
        col_ip      = body.get("col_ip",      "IP")
        col_proto   = body.get("col_proto",   "PROTOCOL")
        col_company = body.get("col_company", "COMPANY_NAME")

        conn = db.connect_one_shot(config)
        db.create_machine_table(conn, db_type, table_name, col_sn, col_ip, col_proto, col_company)
        conn.close()

        # Persist machine_table name alongside the rest of the config
        config["machine_table"] = table_name
        db.save_config(config)
        logger.info(f"[Wizard] Machine table created: {table_name}")
        return {"status": "success", "message": f"Table '{table_name}' created successfully."}
    except Exception as e:
        logger.error(f"[Wizard] create-machine-table failed: {e}")
        return {"status": "error", "message": str(e)}

# —————————————————— Machine management ————————————————————————————————————————————————————————————


#@app.get("/pull/machines", dependencies=[Depends(get_current_user)])
@app.get("/pull/machines")
async def list_machines():
    """List all machines with their live status."""
    return pull_manager.get_all_status()


@app.post("/pull/machines", dependencies=[Depends(get_current_user)])
async def add_machine(machine: MachineIn):
    """Add a new machine (writes to machines.json)."""
    result = pull_manager.add_machine(machine.model_dump())
    return result


@app.get("/api/admin/companies", dependencies=[Depends(get_current_user)])
async def list_companies():
    """Return a list of unique company names registered in the system."""
    try:
        db_type = db.get_active_db_type()
        config_db = db.load_latest_config(db_type)
        if db_type == "Oracle":
            conn = db.connect_db_oracle(config_db)
        else:
            conn = db.connect_db_postgresql(config_db)
        meta = db.get_machine_meta(conn, db_type=db_type)
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
        db_type = db.get_active_db_type()
        config_db = db.load_latest_config(db_type)
        if db_type == "Oracle":
            conn = db.connect_db_oracle(config_db)
        else:
            conn = db.connect_db_postgresql(config_db)
        
        for sn in body.sns:
            # 1. Update Database
            state = pull_manager.get_machine(sn=sn)
            ip = state.get("ip", "0.0.0.0") if state else "0.0.0.0"
            
            # Use current protocol or default to HTTP if SN mapping is happening
            proto = state.get("protocol", "HTTP")
            
            db.upsert_machine_meta(conn, sn, ip, proto, body.company_name, db_type=db_type)
            
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
    return pull_manager.test_connection(body.ip, body.port, body.password, body.driver, body.model_dump())


@app.post("/pull/machines/reload", dependencies=[Depends(get_current_user)])
async def reload_machines():
    """Hot-reload machines.json without server restart."""
    pull_manager.reload()
    return {"success": True, "machines": len(machines_config.load_machines())}


# â”€â”€ Attendance pull â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

#@app.post("/pull/attendance/{sn}", dependencies=[Depends(get_current_user)])
@app.post("/pull/attendance/{sn}")
def manual_pull(sn: str):
    state = pull_manager.get_machine(sn=sn)
    driver = (state.get("driver") or "zk").lower() if state else "zk"
    if state and state.get("protocol") == "HTTP":
        # Queue command to fetch historical logs
        if sn not in COMMAND_QUEUE:
            COMMAND_QUEUE[sn] = []
        if driver in ("fk", "amt"):
            COMMAND_QUEUE[sn].append("get_glog")
            logger.info(f"[FK PUSH] Queued get_glog for {sn}")
        else:
            end_ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cmd = f"C:101:DATA QUERY ATTLOG StartTime=2000-01-01 00:00:00\tEndTime={end_ts}"
            COMMAND_QUEUE[sn].append(cmd)
            logger.info(f"[ZK PUSH] Queued DATA QUERY ATTLOG (full history) for {sn}")
        return {
            "success": True,
            "message": f"Sync command queued for {sn}. Device will upload logs within 60 seconds."
        }
    result = pull_manager.pull_once(sn=sn)
    return result


@app.get("/pull/attendance/logs", dependencies=[Depends(get_current_user)])
async def get_attendance_logs(
    date: Optional[str] = Query(None, description="Filter by date YYYY-MM-DD"),
    sn:   Optional[str] = Query(None, description="Filter by machine SN"),
    limit: int = Query(200, description="Max rows to return")
):
    """
    Query attendance logs from database.
    Used by the Attendance Logs page in the desktop app.
    """
    if not db:
        raise HTTPException(status_code=503, detail="Database module not available")
    try:
        db_type = db.get_active_db_type()
        config = db.load_latest_config(db_type)
        if db_type == "Oracle":
            conn = db.connect_db_oracle(config)
        else:
            conn = db.connect_db_postgresql(config)
        cursor = conn.cursor()

        table    = config["table"]
        col_emp  = config["column1"]
        col_time = config["column2"]
        col_mach = config["column3"]

        query = f"SELECT {col_emp}, {col_time}, {col_mach} FROM {table}"
        params = {}
        conditions = []

        if date:
            if db_type == "Oracle":
                conditions.append(f"TRUNC({col_time}) = TO_DATE(:date_val, 'YYYY-MM-DD')")
            else:
                conditions.append(f"DATE({col_time}) = %(date_val)s::DATE")
            params["date_val"] = date
        if sn:
            if db_type == "Oracle":
                conditions.append(f"{col_mach} LIKE :sn_val")
            else:
                conditions.append(f"{col_mach} LIKE %(sn_val)s")
            params["sn_val"] = f"%{sn}%"

        if conditions:
            query += " WHERE " + " AND ".join(conditions)
            
        if db_type == "Oracle":
            query += f" ORDER BY {col_time} DESC FETCH FIRST :limit ROWS ONLY"
        else:
            query += f" ORDER BY {col_time} DESC LIMIT %(limit)s"
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


# â”€â”€ Device management â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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


# â”€â”€ Dashboard stats â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


@app.get("/pull/fk-bridge/health")
def fk_bridge_health():
    import fk_bridge_client
    return fk_bridge_client.bridge_status()
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


# â”€â”€ Entry point â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
if __name__ == "__main__":
    import uvicorn
    log(f"[*] Starting UTAS Server on 0.0.0.0:{SERVER_PORT}")
    uvicorn.run(app, host="0.0.0.0", port=SERVER_PORT)
