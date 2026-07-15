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

from fastapi import FastAPI, Request, BackgroundTasks, Query, HTTPException, Depends, status, Response
from fastapi.responses import HTMLResponse, PlainTextResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from pydantic import BaseModel
from collections import deque

_dotenv_path = os.getenv("DOTENV_PATH")
if _dotenv_path and os.path.exists(_dotenv_path):
    load_dotenv(_dotenv_path, override=True)
else:
    load_dotenv()

# Initialize DB
db = None
try:
    from .zk import db
except ImportError:
    pass

ADMIN_USERNAME = os.getenv("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

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
            elif path.lower().startswith("/iclock/") and any(path.lower().endswith(ext) for ext in (".aspx", ".asp", ".php")):
                clean_path = path[:path.rfind(".")]
                scope = dict(scope)
                scope["path"] = clean_path
                scope["raw_path"] = clean_path.encode("utf-8")
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

ENROLL_VAR_INDEX = 0

def get_enroll_variations(user_id, backup_number, cloudtime, user_name):
    # Returns a list of tuples: (description, body_dict_or_str, use_len_prefix, bin_prefix_type)
    # bin_prefix_type: 0 = none, 1 = empty (4 bytes of 0), 2 = 4 bytes of data (0x00000004 + 4 bytes 0)
    vars_list = []
    
    payloads = [
        # 0. Standard response (like realtime_glog)
        {"ret": "ok", "result": True, "cloudtime": cloudtime},
        # 1. Simple success
        {"ret": "ok", "result": True},
        # 2. user_id as string
        {"ret": "ok", "result": True, "user_id": user_id},
        # 3. user_id and backup_number
        {"ret": "ok", "result": True, "user_id": user_id, "backup_number": backup_number},
        # 4. user_id, backup_number, cloudtime
        {"ret": "ok", "result": True, "user_id": user_id, "backup_number": backup_number, "cloudtime": cloudtime},
        # 5. user_id as int
        {"ret": "ok", "result": True, "user_id": int(user_id) if user_id.isdigit() else user_id},
        # 6. user_id as int, backup_number
        {"ret": "ok", "result": True, "user_id": int(user_id) if user_id.isdigit() else user_id, "backup_number": backup_number},
        # 7. user_id as int, backup_number, cloudtime
        {"ret": "ok", "result": True, "user_id": int(user_id) if user_id.isdigit() else user_id, "backup_number": backup_number, "cloudtime": cloudtime},
        # 8. Echoing user_name too
        {"ret": "ok", "result": True, "user_id": user_id, "backup_number": backup_number, "user_name": user_name},
        # 9. Echoing user_name with cloudtime
        {"ret": "ok", "result": True, "user_id": user_id, "backup_number": backup_number, "user_name": user_name, "cloudtime": cloudtime},
        # 10. Just ret ok
        {"ret": "ok"},
        # 11. Just result true
        {"result": True}
    ]
    
    for i, p in enumerate(payloads):
        vars_list.append((f"Var {i}a (JSON len-prefix only): {p}", p, True, 0))
        vars_list.append((f"Var {i}b (JSON len-prefix + empty bin-prefix): {p}", p, True, 1))
        vars_list.append((f"Var {i}c (JSON len-prefix + 4-byte bin data): {p}", p, True, 2))
        vars_list.append((f"Var {i}d (no prefixes): {p}", p, False, 0))
        
    return vars_list




# ── Auth Utilities ────────────────────────────────────────────────────────────
import auth_helper
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import Security

security_bearer = HTTPBearer(auto_error=False)

async def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Security(security_bearer)):
    # If the app is not initialized yet, block admin requests (except setup endpoints)
    if not auth_helper.is_auth_initialized():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Setup required: Password has not been initialized."
        )
    
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated."
        )
        
    token = credentials.credentials
    if not auth_helper.validate_session(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid."
        )
    return "master"

class InitializeIn(BaseModel):
    password: str

class MasterLoginIn(BaseModel):
    password: str

class ChangePasswordIn(BaseModel):
    old_password: str
    new_password: str


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
    company_names: List[str] = []
    name: str = ""
    enabled: bool = True
    driver: str = "zk"  # zk | fk (amt alias)
    machine_no: int = 1
    license: int = 1263
    net_password: int = 0
    pull_port: Optional[int] = None
    sync_type: str = "interval"
    sync_interval: int = 20
    sync_days: List[str] = []
    sync_time: str = "00:00"

class TestConnectionIn(BaseModel):
    ip: str
    port: int = 4370
    password: int = 0
    driver: str = "zk"
    license: int = 1263
    machine_no: int = 1
    sync_type: str = "interval"
    sync_interval: int = 20
    sync_days: List[str] = []
    sync_time: str = "00:00"

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
        try:
            if fk_protocol:
                m = MachineIn(
                    ip=ip,
                    sn=sn,
                    location="Auto-Detected (FK)",
                    port=4370,
                    password=0,
                    protocol="HTTP",
                    driver="fk",
                    company_name="None",
                    company_names=[]
                )
            else:
                m = MachineIn(
                    ip=ip,
                    sn=sn,
                    location="Auto-Detected (Push)",
                    port=4370,
                    password=0,
                    protocol="HTTP",
                    company_name="None",
                    company_names=[]
                )
            pull_manager.add_machine(m.model_dump())
        except Exception as e:
            logger.error(f"[AUTODETECT] Failed to register {sn}: {e}")
    else:
        current_proto = existing.get("protocol")
        current_driver = (existing.get("driver") or "zk").lower()
        current_company = existing.get("company_name", "None")

        if fk_protocol and current_driver not in ("fk", "amt"):
            pull_manager.update_fk_device_metadata(sn, company=current_company)
        elif not fk_protocol and current_proto != "HTTP":
            pull_manager.update_machine_metadata(sn, "HTTP", current_company)



def process_attendance_data(sn: str, raw_data: str):
    """Parse ADMS push data and insert to company databases."""
    state = pull_manager.get_machine(sn=sn)
    company_names = state.get("company_names", []) if state else []
    if not company_names:
        m = machines_config.get_machine(sn=sn)
        if m:
            company_names = m.get("company_names", [])
            if not company_names:
                c_single = m.get("company_name")
                company_names = [c_single] if c_single and c_single != "None" else []
    
    logger.info(f"[PROCESS ATT] SN={sn} companies={company_names} raw_len={len(raw_data)} preview={raw_data[:120]!r}")

    if not company_names:
        logger.warning(f"[PUSH ACCESS DENIED] Data from {sn} ignored — no company assigned. Assign a company first.")
        raise ValueError(f"Machine {sn} is not assigned to any company.")

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
            db.insert_log_generic(records, sn, company_names)
            log(f"Saved {count} records to databases.")
            if sn in pull_manager._machines:
                now_sync = datetime.datetime.now()
                pull_manager._machines[sn].last_sync = now_sync
                pull_manager._machines[sn].last_record_count = count
                try:
                    machines_config.update_machine_last_sync(sn, "", 0, now_sync.isoformat())
                except Exception as e:
                    log(f"Error saving last sync to config: {e}")
        except Exception as e:
            log(f"DB error: {e}")
            raise e


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

    # Resolve SN first
    current_sn = dev_id or SN
    if not current_sn:
        from urllib.parse import parse_qs
        try:
            parsed = parse_qs(body_text.split('\n')[0].strip())
            if 'SN' in parsed:
                current_sn = parsed['SN'][0]
        except Exception:
            pass
        if not current_sn:
            for line in body_text.splitlines():
                for part in line.replace('\t', '&').split('&'):
                    part = part.strip()
                    if part.upper().startswith('SN='):
                        current_sn = part.split('=', 1)[1].strip()
                        break
                if current_sn:
                    break

    if current_sn:
        state = pull_manager.get_machine(sn=current_sn)
        if state and not state.get("enabled", True):
            logger.warning(f"[ACCESS DENIED] Push from disabled machine SN={current_sn} rejected.")
            return Response(content="DISABLED", status_code=403)

    # Handle FK protocol devices (like AMF60)
    if req_code or dev_id:
        SN = dev_id or SN
        register_push_device(SN, ip, fk_protocol=True)

        # Echo FK protocol transactional headers
        trans_id = request.headers.get("trans_id")
        blk_no = request.headers.get("blk_no")

        def customize_headers(resp: Response, response_code: str = "SUCCESS") -> Response:
            raw_hdrs = [
                (b"Response_Code", response_code.encode("ascii")),
                (b"Connection", b"close"),
                (b"Content-Length", str(len(resp.body)).encode("ascii")),
            ]
            content_type = resp.headers.get("content-type", "application/octet-stream")
            raw_hdrs.append((b"Content-Type", content_type.encode("ascii")))
            if trans_id is not None:
                raw_hdrs.append((b"Trans_Id", trans_id.encode("ascii")))
            if blk_no is not None:
                raw_hdrs.append((b"Blk_No", blk_no.encode("ascii")))
            resp.raw_headers = raw_hdrs
            return resp

        import struct
        def make_fk_response(resp_dict: dict, response_code: str = "SUCCESS") -> Response:
            full_resp = resp_dict.copy()
            full_resp.update({
                "Response_Code": response_code,
                "response_code": response_code,
            })
            if trans_id is not None:
                try:
                    tid_int = int(trans_id)
                    full_resp["Trans_Id"] = tid_int
                    full_resp["trans_id"] = tid_int
                except:
                    full_resp["Trans_Id"] = trans_id
                    full_resp["trans_id"] = trans_id
            if blk_no is not None:
                try:
                    bid_int = int(blk_no)
                    full_resp["Blk_No"] = bid_int
                    full_resp["blk_no"] = bid_int
                except:
                    full_resp["Blk_No"] = blk_no
                    full_resp["blk_no"] = blk_no

            resp_json = json.dumps(full_resp)
            json_bytes = resp_json.encode("utf-8")
            body_bytes = struct.pack("<I", len(json_bytes)) + json_bytes
            resp = Response(content=body_bytes, media_type="application/octet-stream")
            return customize_headers(resp, response_code)

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
                    return customize_headers(PlainTextResponse(cmd_entry), "SUCCESS")
                elif cmd_entry == "get_glog":
                    end_ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    resp_data = {
                        "ret": "ok", "result": True,
                        "cloudtime": cloudtime, "wait": 0,
                        "data": {
                            "cmd": "get_glog",
                            "cmdid": 1,
                            "starttime": "2020-01-01 00:00:00",
                            "endtime": end_ts
                        }
                    }
                    return make_fk_response(resp_data)
                else:
                    resp_data = {"ret": "ok", "result": True, "cmd": cmd_entry, "cloudtime": cloudtime}
                    return make_fk_response(resp_data)
            else:
                resp_data = {"ret": "ok", "result": False, "cloudtime": cloudtime}
                return make_fk_response(resp_data, "ERROR_NO_CMD")

        elif req_code in ("get_glog", "getalllog", "get_attlog"):
            # Bulk log upload from device
            log(f"[FK PUSH] Received {req_code} bulk data from {SN} — body_len={len(body_text)}")
            raw = body_text.strip()
            if raw:
                import re
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
                            process_attendance_data(SN, "\n".join(lines))
                    else:
                        process_attendance_data(SN, raw)
                except Exception as e:
                    logger.error(f"[FK PUSH] Sync failed: {e}")
                    return make_fk_response({"ret": "fail", "result": False, "cloudtime": cloudtime}, "ERROR")
            return customize_headers(PlainTextResponse("result=OK", media_type="text/plain"), "SUCCESS")

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
                try:
                    process_attendance_data(SN, f"{user_id}\t{check_time}")
                except Exception as e:
                    logger.error(f"[FK PUSH] Sync failed: {e}")
                    return make_fk_response({"ret": "fail", "result": False, "cloudtime": cloudtime}, "ERROR")
            else:
                logger.warning(f"[FK GLOG] Skipped — missing user_id={user_id!r} or io_time={io_time!r}")

            resp_data = {"ret": "ok", "result": True, "cloudtime": cloudtime}
            return make_fk_response(resp_data)

        elif req_code == "realtime_enroll_data":
            global ENROLL_VAR_INDEX
            user_id = data.get("user_id", "500")
            user_name = data.get("user_name", "")
            enroll_array = data.get("enroll_data_array", [])
            backup_number = enroll_array[0].get("backup_number", 0) if enroll_array else 0
            
            variations = get_enroll_variations(user_id, backup_number, cloudtime, user_name)
            var_desc, var_payload, use_len_prefix, bin_prefix_type = variations[ENROLL_VAR_INDEX % len(variations)]
            
            logger.info(f"[SWITCHER] Try Variation {ENROLL_VAR_INDEX % len(variations)}: {var_desc}")
            
            # Increment index for the next request
            ENROLL_VAR_INDEX += 1
            
            if isinstance(var_payload, str):
                body_bytes = var_payload.encode("utf-8")
                if use_len_prefix:
                    import struct
                    body_bytes = struct.pack("<I", len(body_bytes)) + body_bytes
                resp = Response(content=body_bytes, media_type="text/plain" if not use_len_prefix else "application/octet-stream")
                return customize_headers(resp, "SUCCESS")
            else:
                full_resp = var_payload.copy()
                full_resp.update({
                    "Response_Code": "SUCCESS",
                    "response_code": "SUCCESS",
                })
                if trans_id is not None:
                    try:
                        tid_int = int(trans_id)
                        full_resp["Trans_Id"] = tid_int
                        full_resp["trans_id"] = tid_int
                    except:
                        full_resp["Trans_Id"] = trans_id
                        full_resp["trans_id"] = trans_id
                if blk_no is not None:
                    try:
                        bid_int = int(blk_no)
                        full_resp["Blk_No"] = bid_int
                        full_resp["blk_no"] = bid_int
                    except:
                        full_resp["Blk_No"] = blk_no
                        full_resp["blk_no"] = blk_no

                resp_json = json.dumps(full_resp)
                json_bytes = resp_json.encode("utf-8")
                
                if use_len_prefix:
                    import struct
                    body_bytes = struct.pack("<I", len(json_bytes)) + json_bytes
                    if bin_prefix_type == 1:
                        # Append 4 bytes of 0 (empty binary length prefix)
                        body_bytes += struct.pack("<I", 0)
                    elif bin_prefix_type == 2:
                        # Append 4 bytes of binary length (4) + 4 bytes of zero data
                        body_bytes += struct.pack("<I", 4) + b"\x00\x00\x00\x00"
                else:
                    body_bytes = json_bytes
                    
                resp = Response(content=body_bytes, media_type="application/octet-stream" if use_len_prefix else "application/json")
                return customize_headers(resp, "SUCCESS")

        else:
            # Acknowledge any other unhandled FK request with JSON (not plain text)
            # so the device does not retry indefinitely.
            logger.info(f"[FK PUSH] Unhandled req_code={req_code}, acknowledging with JSON ok")
            resp_data = {"ret": "ok", "result": True, "cloudtime": cloudtime}
            return make_fk_response(resp_data)
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
        try:
            process_attendance_data(SN, body_text)
            return "OK"
        except Exception as e:
            logger.error(f"Failed to process ATTLOG for standard ADMS device {SN}: {e}")
            raise HTTPException(status_code=500, detail=f"Database insertion failed: {e}")
    elif table == 'OPERLOG':
        return "OK"

    logger.info(f"[PUSH] Device SN={SN} table={table} from {ip} — body length={len(body_text)}")
    return "OK"


# Root handler removed â€” PathNormalizerMiddleware rewrites // â†’ /iclock/cdata


def parse_adms_info(sn: str, info_str: str):
    """Parse ZK ADMS INFO registration string and store in MachineState."""
    state = pull_manager._machines.get(sn)
    if not state:
        return
    
    try:
        parts = info_str.split(',')
        if len(parts) >= 5:
            pf_fw = parts[0]
            platform = pf_fw
            firmware = "Unknown"
            if "-Ver" in pf_fw:
                p_parts = pf_fw.split("-Ver")
                platform = p_parts[0]
                firmware = p_parts[1]
            elif "Ver" in pf_fw:
                p_parts = pf_fw.split("Ver")
                platform = p_parts[0]
                firmware = p_parts[1]

            users = int(parts[1])
            fingers = int(parts[2])
            records = int(parts[3])
            ip = parts[4]

            state.config["platform"] = platform
            state.config["firmware"] = firmware
            state.config["users"] = users
            state.config["fingers"] = fingers
            state.config["records"] = records
            if ip and ip != "0.0.0.0":
                state.ip = ip
                state.config["ip"] = ip
            
            import machines_config
            machines_config.save_machine(state.config)
            logger.info(f"[ADMS INFO] Parsed for {sn}: Platform={platform}, FW={firmware}, Users={users}, Records={records}")
    except Exception as e:
        logger.error(f"[ADMS INFO] Failed to parse info string '{info_str}' for {sn}: {e}")


@app.get("/iclock/getrequest", response_class=PlainTextResponse)
async def get_request(request: Request, SN: Optional[str] = Query(None)):
    ip = request.client.host
    if SN:
        state = pull_manager.get_machine(sn=SN)
        if state and not state.get("enabled", True):
            logger.warning(f"[ACCESS DENIED] getrequest from disabled machine SN={SN} rejected.")
            return Response(content="DISABLED", status_code=403)
        register_push_device(SN, ip, fk_protocol=False)
        log(f"Device {SN} getrequest from {ip}")
        
        info_param = request.query_params.get("INFO")
        if info_param:
            parse_adms_info(SN, info_param)
            
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


@app.api_route("/iclock/registry", methods=["GET", "POST"], response_class=PlainTextResponse)
async def device_registry(request: Request, SN: Optional[str] = Query(None)):
    ip = request.client.host
    dev_id = request.headers.get("dev_id") or SN
    if dev_id:
        register_push_device(dev_id, ip, fk_protocol=False)
        log(f"[ADMS REGISTRY] Registered {dev_id} from {ip}")
    return "RegistryCode=OK"


@app.api_route("/iclock/ping", methods=["GET", "POST"], response_class=PlainTextResponse)
async def device_ping(request: Request, SN: Optional[str] = Query(None)):
    ip = request.client.host
    dev_id = request.headers.get("dev_id") or SN
    if dev_id:
        register_push_device(dev_id, ip, fk_protocol=False)
        log(f"[ADMS PING] Ping from {dev_id} at {ip}")
    return "OK"


@app.api_route("/iclock/push", methods=["GET", "POST"], response_class=PlainTextResponse)
async def device_push(request: Request, SN: Optional[str] = Query(None)):
    ip = request.client.host
    dev_id = request.headers.get("dev_id") or SN
    if dev_id:
        register_push_device(dev_id, ip, fk_protocol=False)
        log(f"[ADMS PUSH] Push from {dev_id} at {ip}")
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

@app.get("/api/auth/status")
async def auth_status(request: Request):
    initialized = auth_helper.is_auth_initialized()
    lockout = False
    if not initialized and auth_helper.is_app_configured():
        lockout = True

    logged_in = False
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1]
        logged_in = auth_helper.validate_session(token)
    return {
        "initialized": initialized,
        "lockout": lockout,
        "logged_in": logged_in
    }

@app.post("/api/auth/initialize")
async def initialize_auth(body: InitializeIn):
    if auth_helper.is_auth_initialized():
        raise HTTPException(status_code=400, detail="Already initialized")
    if auth_helper.is_app_configured():
        raise HTTPException(
            status_code=403,
            detail="Security lockout: Existing configuration detected. Re-initialization of the master password is disabled to protect existing credentials. Wipe all data files in APPDATA\\UTAS to start fresh."
        )
    try:
        success = auth_helper.initialize_master_password(body.password)
        if success:
            token = auth_helper.create_session()
            return {"status": "success", "access_token": token}
        else:
            raise HTTPException(status_code=500, detail="Failed to initialize password")
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))

@app.post("/api/auth/login")
async def login(body: MasterLoginIn):
    if not auth_helper.is_auth_initialized():
        raise HTTPException(status_code=400, detail="Setup required: Password has not been initialized.")
    
    if auth_helper.verify_master_password(body.password):
        token = auth_helper.create_session()
        return {"access_token": token, "token_type": "bearer"}
    else:
        raise HTTPException(status_code=401, detail="Invalid password.")

@app.post("/api/auth/logout")
async def logout(request: Request):
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1]
        auth_helper.destroy_session(token)
    return {"status": "success"}

@app.post("/api/auth/change-password", dependencies=[Depends(get_current_user)])
async def change_password(body: ChangePasswordIn):
    try:
        success = auth_helper.change_master_password(body.old_password, body.new_password)
        if success:
            return {"status": "success", "message": "Password changed successfully."}
        else:
            raise HTTPException(status_code=500, detail="Failed to change password.")
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


@app.get("/api/admin/server/logs", dependencies=[Depends(get_current_user)])
async def get_server_logs():
    return list(log_buffer.logs)

@app.get("/api/admin/server/status", dependencies=[Depends(get_current_user)])
async def get_server_status():
    return {
        "enabled": pull_manager.enabled,
        "scheduler_running": pull_manager._scheduler.running
    }

@app.get("/api/admin/server/info")
async def get_server_info():
    """
    Returns the local IP address and port of this UTAS server so the 
    Dashboard can display it for ZKTeco device configuration.
    """
    import socket
    local_ip = "127.0.0.1"
    try:
        # Connect to a remote address to determine which local interface is used
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        try:
            local_ip = socket.gethostbyname(socket.gethostname())
        except Exception:
            local_ip = "127.0.0.1"
    return {
        "local_ip": local_ip,
        "port": SERVER_PORT,
        "hostname": socket.gethostname(),
        "server_url": f"http://{local_ip}:{SERVER_PORT}"
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
            conn = None
            cursor = None
            try:
                if db_type == "Oracle":
                    conn = db.connect_db_oracle(config)
                    cursor = conn.cursor()
                    cursor.execute("SELECT 1 FROM DUAL")
                else:
                    conn = db.connect_db_postgresql(config)
                    cursor = conn.cursor()
                    cursor.execute("SELECT 1")
            finally:
                if cursor:
                    try: cursor.close()
                    except Exception: pass
                if conn:
                    try: conn.close()
                    except Exception: pass
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
            config["col_pk"] = find_best(att_cols, ["HR_ATT_LOG_ID", "ID", "LOG_ID", "PK"], config.get("col_pk", config.get("column_pk", "HR_ATT_LOG_ID")))
            config["column_pk"] = config["col_pk"]  # maintain compatibility
            if config["col_pk"].upper() == "HR_ATT_LOG_ID":
                config["seq_pk"] = config.get("seq_pk", "HR_EMP_INOUT_ID_S")

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
    data = machine.model_dump()
    if data.get("port") == 5005 and data.get("driver") == "zk":
        data["driver"] = "fk"
    if "company_names" in data:
        data["company_name"] = data["company_names"][0] if data["company_names"] else "None"
    result = pull_manager.add_machine(data)
    return result


@app.get("/api/admin/companies", dependencies=[Depends(get_current_user)])
async def list_companies():
    """Return a list of unique company names registered in the system."""
    try:
        # Load mappings keys
        mappings = db.load_company_mappings()
        companies = set(mappings.keys())
        
        # Also load companies from machines.json
        machines = machines_config.load_machines()
        for m in machines:
            for c in m.get("company_names", []):
                if c and c != "None":
                    companies.add(c)
            c_single = m.get("company_name", "None")
            if c_single and c_single != "None":
                companies.add(c_single)
                
        return {"success": True, "companies": sorted(list(companies))}
    except Exception as e:
        logger.error(f"[Admin] Failed to fetch companies: {e}")
        return {"success": False, "error": str(e), "companies": []}

class CompanyAddIn(BaseModel):
    company_name: str

@app.post("/api/admin/companies/add", dependencies=[Depends(get_current_user)])
async def add_company(body: CompanyAddIn):
    """Add a new company name configuration."""
    mappings = db.load_company_mappings()
    if body.company_name in mappings:
        return {"success": True, "message": "Company already exists"}
    success = db.save_company_mapping(body.company_name, "")
    if not success:
        raise HTTPException(status_code=500, detail="Failed to add company")
    return {"success": True}

@app.delete("/api/admin/companies/{company_name}", dependencies=[Depends(get_current_user)])
async def delete_company(company_name: str):
    """Remove a company mapping."""
    success = db.delete_company_mapping(company_name)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete company")
    return {"success": True}

class CompanyMapDbIn(BaseModel):
    company_name: str
    profile_name: str

@app.post("/api/admin/companies/map-db", dependencies=[Depends(get_current_user)])
async def map_company_to_db(body: CompanyMapDbIn):
    """Map a company name to a named database profile."""
    success = db.save_company_mapping(body.company_name, body.profile_name)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to map company to database")
    return {"success": True}

@app.get("/api/admin/companies/mappings", dependencies=[Depends(get_current_user)])
async def get_company_mappings():
    """Get all company to DB profile mappings."""
    return db.load_company_mappings()

@app.get("/api/admin/db-profiles", dependencies=[Depends(get_current_user)])
async def list_db_profiles():
    """Get all configured database profiles."""
    return db.load_db_profiles()

@app.post("/api/admin/db-profiles/test", dependencies=[Depends(get_current_user)])
async def test_db_profile_connection(config: dict):
    """Test connection settings for a database profile."""
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

@app.post("/api/admin/db-profiles/{profile_name}", dependencies=[Depends(get_current_user)])
async def save_db_profile(profile_name: str, config: dict):
    """Save or update a database profile."""
    success = db.save_db_profile(profile_name, config)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to save database profile")
    return {"success": True}

@app.delete("/api/admin/db-profiles/{profile_name}", dependencies=[Depends(get_current_user)])
async def delete_db_profile(profile_name: str):
    """Delete a database profile."""
    success = db.delete_db_profile(profile_name)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete database profile")
    return {"success": True}

@app.post("/pull/machines/{sn}/toggle", dependencies=[Depends(get_current_user)])
async def toggle_machine(sn: str):
    """Toggle the enabled status of a machine."""
    machine = machines_config.get_machine(sn=sn)
    if not machine:
        for m in machines_config.load_machines():
            key = m.get("sn") or f"{m['ip']}:{m.get('port', 4370)}"
            if key == sn:
                machine = m
                break
    if not machine:
        raise HTTPException(status_code=404, detail="Machine not found")
    
    enabled = not machine.get("enabled", True)
    machine["enabled"] = enabled
    machines_config.save_machine(machine)
    pull_manager.reload()
    return {"success": True, "enabled": enabled}

@app.post("/api/admin/companies/map", dependencies=[Depends(get_current_user)])
async def map_devices_to_company(body: CompanyMapIn):
    """Bulk link a list of Serial Numbers to a Company Name."""
    try:
        for sn in body.sns:
            machine = machines_config.get_machine(sn=sn)
            if machine:
                company_names = machine.get("company_names", [])
                if not company_names:
                    single_comp = machine.get("company_name", "None")
                    if single_comp and single_comp != "None":
                        company_names = [single_comp]
                    else:
                        company_names = []
                
                if body.company_name not in company_names:
                    company_names.append(body.company_name)
                
                machine["company_names"] = company_names
                if "company_name" in machine:
                    del machine["company_name"]
                machines_config.save_machine(machine)
                
        pull_manager.reload()
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
    if not state:
        return {"success": False, "error": "Machine not found"}
        
    if not state.get("company_names"):
        return {
            "success": False,
            "error": "Machine is not assigned to any company. Please assign a company first."
        }
        
    driver = (state.get("driver") or "zk").lower()
    if state.get("protocol") == "HTTP":
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
    limit: int = Query(5000, description="Max rows to return")
):
    """
    Read pull execution history from local JSON tracker file.
    Used by the Logs Tracker page.
    """
    if not db or not hasattr(db, "PULL_HISTORY_FILE"):
        raise HTTPException(status_code=503, detail="Database module not initialized")
        
    history = []
    if os.path.exists(db.PULL_HISTORY_FILE):
        try:
            with open(db.PULL_HISTORY_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
        except Exception as e:
            logger.error(f"Error reading pull_history.json: {e}")
            
    all_machines = machines_config.get_all_machines()
    sn_lookup = {}
    ip_lookup = {}
    for m in all_machines:
        custom_name = m.get("name") or m.get("location") or ""
        if custom_name:
            if m.get("sn"):
                sn_lookup[str(m.get("sn")).strip().lower()] = custom_name
            if m.get("ip"):
                ip_lookup[str(m.get("ip")).strip().lower()] = custom_name

    filtered = []
    for entry in history:
        # Date filter (entry["date"] is YYYY-MM-DD HH:MM:SS)
        if date and not entry.get("date", "").startswith(date):
            continue
        # SN/Device filter
        if sn and sn.lower() not in entry.get("machine", "").lower():
            continue
            
        raw_machine = str(entry.get("machine", "")).strip()
        resolved_name = raw_machine
        if raw_machine.lower() in sn_lookup:
            resolved_name = sn_lookup[raw_machine.lower()]
        elif raw_machine.lower() in ip_lookup:
            resolved_name = ip_lookup[raw_machine.lower()]
        else:
            for sn_key, c_name in sn_lookup.items():
                if sn_key and sn_key in raw_machine.lower():
                    resolved_name = f"{c_name} ({raw_machine})"
                    break
            else:
                for ip_key, c_name in ip_lookup.items():
                    if ip_key and ip_key in raw_machine.lower():
                        resolved_name = f"{c_name} ({raw_machine})"
                        break

        entry_copy = dict(entry)
        entry_copy["custom_name"] = resolved_name
        filtered.append(entry_copy)
        
    return filtered[:limit]


# ── Device management ────────────────────────────────────────────────────────

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
            profiles = db.load_db_profiles()
            seen_keys = set()
            for name, config in profiles.items():
                key = f"{config.get('host')}:{config.get('port')}:{config.get('dbname')}:{config.get('username')}"
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                
                db_type = config.get("database", "Oracle")
                conn = None
                cursor = None
                try:
                    if db_type == "Oracle":
                        conn = db.connect_db_oracle(config)
                        cursor = conn.cursor()
                        table    = config["table"]
                        col_time = config["column2"]
                        cursor.execute(
                            f"SELECT COUNT(*) FROM {table} WHERE TRUNC({col_time}) = TRUNC(SYSDATE)"
                        )
                        record_count += cursor.fetchone()[0]
                    elif db_type == "PostgreSQL":
                        conn = db.connect_db_postgresql(config)
                        cursor = conn.cursor()
                        table    = config["table"]
                        col_time = config["column2"]
                        cursor.execute(
                            f"SELECT COUNT(*) FROM {table} WHERE DATE({col_time}) = CURRENT_DATE"
                        )
                        record_count += cursor.fetchone()[0]
                except Exception as db_err:
                    logger.error(f"Stats query failed for profile {name}: {db_err}")
                finally:
                    if cursor:
                        try: cursor.close()
                        except Exception: pass
                    if conn:
                        try: conn.close()
                        except Exception: pass
        except Exception as e:
            logger.error(f"Stats query failed: {e}")

    # Get unique companies count
    comp_count = 0
    try:
        mappings = db.load_company_mappings()
        companies = set(mappings.keys())
        
        machines_list = machines_config.load_machines()
        for m in machines_list:
            for c in m.get("company_names", []):
                if c and c != "None":
                    companies.add(c)
            c_single = m.get("company_name", "None")
            if c_single and c_single != "None":
                companies.add(c_single)
        comp_count = len(companies)
    except: pass

    return {
        "total_machines":  len(machines),
        "online_machines": online,
        "records_today":   record_count,
        "total_companies": comp_count,
        "recent_push_logs": len(RECENT_LOGS),
        "sync_interval_seconds": int(os.getenv("PULL_SYNC_INTERVAL", "20")),
    }


# ── Offline Logs and direct download ──────────────────────────────────────────

@app.get("/api/admin/offline-logs/status", dependencies=[Depends(get_current_user)])
def get_offline_logs_status():
    count = 0
    if db and hasattr(db, "OFFLINE_LOGS_FILE") and os.path.exists(db.OFFLINE_LOGS_FILE):
        try:
            with open(db.OFFLINE_LOGS_FILE, "r", encoding="utf-8") as f:
                logs = json.load(f)
                count = len(logs)
        except Exception as e:
            logger.error(f"Error reading offline logs status: {e}")
    return {"count": count, "has_offline_logs": count > 0}

@app.post("/api/admin/offline-logs/sync", dependencies=[Depends(get_current_user)])
def sync_offline_logs():
    if not db or not hasattr(db, "OFFLINE_LOGS_FILE"):
        raise HTTPException(status_code=503, detail="Database module not initialized")
        
    if not os.path.exists(db.OFFLINE_LOGS_FILE):
        return {"success": True, "synced": 0, "message": "No offline logs to sync."}
        
    try:
        with open(db.OFFLINE_LOGS_FILE, "r", encoding="utf-8") as f:
            all_logs = json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading offline logs: {e}")
        
    if not all_logs:
        return {"success": True, "synced": 0, "message": "No offline logs to sync."}
        
    class OfflineRecord:
        def __init__(self, user_id, timestamp):
            self.user_id = user_id
            if isinstance(timestamp, str):
                try:
                    self.timestamp = datetime.datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    self.timestamp = timestamp
            else:
                self.timestamp = timestamp

    # Group by machine
    grouped = {}
    for log_entry in all_logs:
        m = log_entry.get("machine")
        if m not in grouped:
            grouped[m] = []
        grouped[m].append(log_entry)
        
    remaining_logs = []
    synced_count = 0
    errors = []
    
    for machine_ref, logs_in_group in grouped.items():
        state = pull_manager.get_machine(sn=machine_ref) or pull_manager.get_machine(ip=machine_ref)
        company_names = []
        if state:
            company_names = state.get("company_names") or []
        else:
            try:
                all_machines = machines_config.load_machines()
                for m_cfg in all_machines:
                    if m_cfg.get("sn") == machine_ref or m_cfg.get("ip") == machine_ref:
                        company_names = m_cfg.get("company_names") or []
                        if not company_names and m_cfg.get("company_name"):
                            company_names = [m_cfg.get("company_name")]
                        break
            except Exception as cfg_err:
                logger.error(f"Error loading machines config during sync: {cfg_err}")
                
        if not company_names:
            remaining_logs.extend(logs_in_group)
            errors.append(f"No company assigned to machine {machine_ref}")
            continue
            
        records = [OfflineRecord(l["user_id"], l["timestamp"]) for l in logs_in_group]
        try:
            db.insert_log_generic(records, machine_ref, company_names, bypass_offline_save=True)
            synced_count += len(records)
        except Exception as e:
            remaining_logs.extend(logs_in_group)
            errors.append(f"Machine {machine_ref} sync failed: {str(e)}")
            
    # Save remaining logs back to file
    try:
        if remaining_logs:
            with open(db.OFFLINE_LOGS_FILE, "w", encoding="utf-8") as f:
                json.dump(remaining_logs, f, indent=4)
        else:
            if os.path.exists(db.OFFLINE_LOGS_FILE):
                os.remove(db.OFFLINE_LOGS_FILE)
    except Exception as e:
        logger.error(f"Error updating offline logs file: {e}")
        errors.append(f"Failed to update local storage: {e}")
        
    return {
        "success": len(errors) == 0,
        "synced": synced_count,
        "remaining": len(remaining_logs),
        "errors": errors
    }

@app.get("/api/admin/offline-logs/download", dependencies=[Depends(get_current_user)])
def download_offline_logs(format: str = "csv"):
    if not db or not hasattr(db, "OFFLINE_LOGS_FILE") or not os.path.exists(db.OFFLINE_LOGS_FILE):
        raise HTTPException(status_code=404, detail="No offline logs found")
        
    try:
        with open(db.OFFLINE_LOGS_FILE, "r", encoding="utf-8") as f:
            logs = json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading offline logs: {e}")
        
    if not logs:
        raise HTTPException(status_code=404, detail="No offline logs found")
        
    import io
    import csv
    
    output = io.StringIO()
    if format == "txt":
        writer = csv.writer(output, delimiter="\t")
        writer.writerow(["User ID", "Timestamp", "Machine"])
        for l in logs:
            writer.writerow([l.get("user_id"), l.get("timestamp"), l.get("machine")])
        content = output.getvalue()
        filename = f"offline_logs_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        media_type = "text/plain"
    else:
        writer = csv.writer(output)
        writer.writerow(["User ID", "Timestamp", "Machine"])
        for l in logs:
            writer.writerow([l.get("user_id"), l.get("timestamp"), l.get("machine")])
        content = output.getvalue()
        filename = f"offline_logs_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        media_type = "text/csv"
        
    headers = {"Content-Disposition": f"attachment; filename={filename}"}
    return Response(content=content, media_type=media_type, headers=headers)

@app.get("/pull/machines/{sn}/download-logs", dependencies=[Depends(get_current_user)])
def download_device_logs(sn: str, format: str = "csv"):
    import fk_bridge_client
    from fk_bridge_client import is_fk_driver
    
    # 1. Find the machine state
    machine_state = pull_manager._find_state(sn=sn, ip="", port=4370)
    if not machine_state:
        raise HTTPException(status_code=404, detail="Machine not found")
        
    machine_ref = machine_state.get_machine_ref()
    records = []
    source_name = ""
    
    if machine_state.protocol == "HTTP":
        # For HTTP push, we read from the database logs already uploaded
        if not db:
            raise HTTPException(status_code=503, detail="Database module not available")
        try:
            db_type = db.get_active_db_type()
            config = db.load_latest_config(db_type)
            conn = None
            cursor = None
            try:
                if db_type == "Oracle":
                    conn = db.connect_db_oracle(config)
                else:
                    conn = db.connect_db_postgresql(config)
                cursor = conn.cursor()
                
                table = config["table"]
                col_time = config["column2"]
                col_mach = config["column3"]
                col_uid = config["column1"]
                
                if db_type == "Oracle":
                    query = f'SELECT "{col_uid}", TO_CHAR("{col_time}", \'YYYY-MM-DD HH24:MI:SS\') FROM "{table}" WHERE "{col_mach}" = :sn ORDER BY "{col_time}" DESC'
                    cursor.execute(query, {"sn": sn})
                else:
                    query = f'SELECT "{col_uid}", TO_CHAR("{col_time}", \'YYYY-MM-DD HH24:MI:SS\') FROM "{table}" WHERE "{col_mach}" = %(sn)s ORDER BY "{col_time}" DESC'
                    cursor.execute(query, {"sn": sn})
                    
                rows = cursor.fetchall()
            finally:
                if cursor:
                    try: cursor.close()
                    except Exception: pass
                if conn:
                    try: conn.close()
                    except Exception: pass
            
            for r in rows:
                records.append({"user_id": r[0], "timestamp": r[1]})
            source_name = f"db_cache_{sn}"
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Database query failed: {e}")
    else:
        # For TCP pull (ZK or FK), pull directly from the device
        with machine_state.lock:
            try:
                if is_fk_driver(machine_state.driver):
                    if not machine_state.fk_connected and not pull_manager._connect(machine_state):
                        raise RuntimeError(machine_state.last_error or "Connection failed")
                    pulled_records, err = fk_bridge_client.pull_attendance(machine_state.ip, machine_state.port, machine_state.config)
                    if err:
                        raise RuntimeError(err)
                    for r in pulled_records:
                        ts = getattr(r, 'timestamp', None) or getattr(r, 'check_time', None)
                        ts_str = ts.strftime('%Y-%m-%d %H:%M:%S') if isinstance(ts, datetime.datetime) else str(ts)
                        uid = getattr(r, 'user_id', None) or getattr(r, 'uid', None) or getattr(r, 'pin', None)
                        records.append({"user_id": str(uid), "timestamp": ts_str})
                else:
                    if not machine_state.conn or not machine_state.conn.is_connect:
                        if not pull_manager._connect(machine_state):
                            raise RuntimeError(machine_state.last_error or "Connection failed")
                    pulled_records = machine_state.conn.get_attendance()
                    for r in pulled_records:
                        ts_str = r.timestamp.strftime('%Y-%m-%d %H:%M:%S') if isinstance(r.timestamp, datetime.datetime) else str(r.timestamp)
                        records.append({"user_id": str(r.user_id), "timestamp": ts_str})
                source_name = f"device_{sn}"
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to pull logs from device: {e}")
                
    if not records:
        raise HTTPException(status_code=404, detail="No logs found for this machine")
        
    import io
    import csv
    
    output = io.StringIO()
    if format == "txt":
        writer = csv.writer(output, delimiter="\t")
        writer.writerow(["User ID", "Timestamp", "Machine"])
        for r in records:
            writer.writerow([r.get("user_id"), r.get("timestamp"), machine_ref])
        content = output.getvalue()
        filename = f"{source_name}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        media_type = "text/plain"
    else:
        writer = csv.writer(output)
        writer.writerow(["User ID", "Timestamp", "Machine"])
        for r in records:
            writer.writerow([r.get("user_id"), r.get("timestamp"), machine_ref])
        content = output.getvalue()
        filename = f"{source_name}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        media_type = "text/csv"
        
    headers = {"Content-Disposition": f"attachment; filename={filename}"}
    return Response(content=content, media_type=media_type, headers=headers)


from fastapi import UploadFile, File

@app.post("/api/admin/companies/{company_name}/upload-logs", dependencies=[Depends(get_current_user)])
async def upload_company_logs(company_name: str, file: UploadFile = File(...)):
    if not db:
        raise HTTPException(status_code=503, detail="Database module not available")
        
    mappings = db.load_company_mappings()
    profile_name = mappings.get(company_name)
    if not profile_name or profile_name == "None":
        raise HTTPException(status_code=400, detail=f"Company '{company_name}' has no database profile assigned. Please configure mapping first.")
        
    try:
        contents = await file.read()
        text = contents.decode("utf-8-sig", errors="ignore")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read file: {e}")
        
    # Split into lines and filter empty
    raw_lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not raw_lines:
        raise HTTPException(status_code=400, detail="The file is empty")
        
    # Detect separator
    sep = "\t" if file.filename.endswith(".txt") or "\t" in raw_lines[0] else ","
    
    import csv
    import io
    reader = csv.reader(io.StringIO(text), delimiter=sep)
    rows = [r for r in reader if r]
    if not rows:
        raise HTTPException(status_code=400, detail="No rows found in file")
        
    # Check for header
    is_header = False
    first_row = rows[0]
    if len(first_row) > 1:
        val0 = first_row[0].strip().lower()
        val1 = first_row[1].strip().lower()
        if "user" in val0 or "id" in val0 or "emp" in val0 or "time" in val1 or "date" in val1 or "mach" in val0:
            is_header = True
            
    header = [h.strip().lower() for h in first_row]
    user_idx = -1
    time_idx = -1
    mach_idx = -1
    
    if is_header:
        for idx, name in enumerate(header):
            if "user" in name or "emp" in name or name == "uid" or name == "id":
                user_idx = idx
            elif "time" in name or "date" in name or name == "ts":
                time_idx = idx
            elif "mach" in name or "device" in name or name == "ref":
                mach_idx = idx
                
    # Resolve mapped machines for this company to get their reference names
    mapped_refs = []
    for m in pull_manager._machines.values():
        if company_name in m.company_names:
            mapped_refs.append(m.get_machine_ref())
            
    # Detect if serial number of any mapped machine is in the filename
    filename_lower = file.filename.lower()
    resolved_from_filename = None
    for m in pull_manager._machines.values():
        if m.sn and m.sn in filename_lower:
            resolved_from_filename = m.get_machine_ref()
            break
            
    default_mach_ref = resolved_from_filename or (mapped_refs[0] if len(mapped_refs) == 1 else "Uploaded File")

    # Fallbacks
    if user_idx == -1:
        user_idx = 0
    if time_idx == -1:
        time_idx = 1
        
    from collections import defaultdict, namedtuple
    UploadedRecord = namedtuple("UploadedRecord", ["user_id", "timestamp"])
    grouped_records = defaultdict(list)
    
    start_row = 1 if is_header else 0
    for row_num, r in enumerate(rows[start_row:], start=start_row+1):
        if len(r) <= max(user_idx, time_idx):
            continue
            
        uid = r[user_idx].strip()
        ts_str = r[time_idx].strip()
        if not uid or not ts_str:
            continue
            
        try:
            ts = None
            # Standard formats: YYYY-MM-DD HH:MM:SS, etc.
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
                try:
                    ts = datetime.datetime.strptime(ts_str, fmt)
                    break
                except ValueError:
                    continue
            if not ts:
                ts = datetime.datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        except Exception:
            continue
            
        mach = default_mach_ref
        if mach_idx != -1 and len(r) > mach_idx:
            mach = r[mach_idx].strip() or default_mach_ref
            
        grouped_records[mach].append(UploadedRecord(user_id=uid, timestamp=ts))
        
    total_parsed = sum(len(recs) for recs in grouped_records.values())
    if total_parsed == 0:
        raise HTTPException(status_code=400, detail="No valid records could be parsed. Check columns (User ID, Timestamp).")
        
    # Now execute inserts group by group
    total_inserted = 0
    errors = []
    
    for mach_ref, recs in grouped_records.items():
        try:
            # We bypass offline save so that we raise database errors to the user
            db.insert_log_generic(recs, mach_ref, [company_name], bypass_offline_save=True)
            total_inserted += len(recs)
        except Exception as e:
            errors.append(f"Batch for machine '{mach_ref}' failed: {e}")
            
    if errors:
        raise HTTPException(status_code=500, detail="; ".join(errors))
        
    return {
        "success": True,
        "message": f"Successfully parsed {total_parsed} records and inserted {total_inserted} records."
    }



# â”€â”€ Entry point â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
if __name__ == "__main__":
    import sys
    import uvicorn
    
    # Check for --reset-password switch
    if len(sys.argv) > 1 and sys.argv[1] == "--reset-password":
        try:
            import auth_helper
            print("[*] Performing administrative password reset...")
            if auth_helper.administrative_reset():
                print("[SUCCESS] Password configuration and lockout flags have been successfully reset.")
                print("You can now set a new password on the next application launch.")
                sys.exit(0)
            else:
                print("[ERROR] Failed to perform administrative password reset.")
                sys.exit(1)
        except Exception as err:
            print(f"[ERROR] Error during reset: {err}")
            sys.exit(1)

    log(f"[*] Starting UTAS Server on 0.0.0.0:{SERVER_PORT}")
    uvicorn.run(app, host="0.0.0.0", port=SERVER_PORT, http="h11", server_header=False, date_header=False)
