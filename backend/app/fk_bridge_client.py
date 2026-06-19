"""
fk_bridge_client.py - HTTP client for FkBridge (FK / AMT dual-mode TCP pull).
"""
import os
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import requests
from zk.attendance import Attendance

logger = logging.getLogger(__name__)

FK_BRIDGE_URL = os.getenv("FK_BRIDGE_URL", os.getenv("AMT_BRIDGE_URL", "http://127.0.0.1:5001"))
FK_BRIDGE_TIMEOUT = int(os.getenv("FK_BRIDGE_TIMEOUT", "120"))
FK_CONNECT_TIMEOUT = int(os.getenv("FK_CONNECT_TIMEOUT", "20"))
FK_TCP_HINT = (
    "TCP pull failed (No open connection). Enable Local/TCP on device port 5005. "
    "HTTP push can still work."
)


def is_fk_driver(driver: Optional[str]) -> bool:
    return (driver or "zk").lower() in ("fk", "amt")


def _payload(ip: str, port: int, config: dict) -> dict:
    return {
        "ip": ip,
        "port": int(config.get("pull_port") or config.get("port") or port),
        "machineNo": int(config.get("machine_no", 1)),
        "license": int(config.get("license", 1263)),
        "timeoutMs": int(config.get("timeout_ms", 5000)),
        "netPassword": int(config.get("net_password", 0)),
    }


def _request_error(exc: Exception) -> str:
    if isinstance(exc, requests.ConnectionError):
        return f"FkBridge not reachable at {FK_BRIDGE_URL}. Start FkBridge.exe."
    if isinstance(exc, requests.Timeout):
        return f"FkBridge timeout. Check device TCP port 5005."
    return str(exc)


def bridge_status() -> dict:
    try:
        r = requests.get(f"{FK_BRIDGE_URL.rstrip('/')}/health", timeout=5)
        r.raise_for_status()
        data = r.json()
        return {"reachable": True, "url": FK_BRIDGE_URL, "dll_loaded": data.get("dll_loaded", False)}
    except Exception as e:
        return {"reachable": False, "url": FK_BRIDGE_URL, "dll_loaded": False, "error": _request_error(e)}


def is_bridge_ready() -> bool:
    st = bridge_status()
    return bool(st.get("reachable") and st.get("dll_loaded"))


def _post(path: str, body: dict, timeout: Optional[int] = None) -> dict:
    r = requests.post(f"{FK_BRIDGE_URL.rstrip('/')}{path}", json=body, timeout=timeout or FK_BRIDGE_TIMEOUT)
    r.raise_for_status()
    return r.json()


def connect(ip: str, port: int, config: dict) -> Tuple[bool, str]:
    try:
        data = _post("/connect", _payload(ip, port, config), timeout=FK_CONNECT_TIMEOUT)
        if data.get("success"):
            return True, ""
        err = data.get("error") or "connect failed"
        if "No open connection" in str(err):
            err = FK_TCP_HINT
        return False, err
    except Exception as e:
        return False, _request_error(e)


def pull_attendance(ip: str, port: int, config: dict) -> Tuple[List[Attendance], str]:
    try:
        data = _post("/pull", _payload(ip, port, config))
        if not data.get("success"):
            err = data.get("error") or "pull failed"
            if "No open connection" in str(err):
                err = FK_TCP_HINT
            return [], err
        records = []
        for log in data.get("logs") or []:
            ts = log.get("timestamp")
            uid = str(log.get("userId") or log.get("user_id") or "")
            if not uid or not ts:
                continue
            if isinstance(ts, str):
                timestamp = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
            else:
                timestamp = ts
            records.append(Attendance(user_id=uid, timestamp=timestamp, status=1, punch=0))
        return records, ""
    except Exception as e:
        return [], _request_error(e)


def clear_attendance(ip: str, port: int, config: dict) -> Tuple[bool, str]:
    try:
        data = _post("/clear", _payload(ip, port, config))
        return (True, "") if data.get("success") else (False, data.get("error") or "clear failed")
    except Exception as e:
        return False, _request_error(e)


def device_info(ip: str, port: int, config: dict) -> Tuple[Dict[str, Any], str]:
    try:
        p = _payload(ip, port, config)
        r = requests.get(f"{FK_BRIDGE_URL.rstrip('/')}/info", params={
            "ip": p["ip"], "port": p["port"], "machine_no": p["machineNo"],
            "license": p["license"], "timeout_ms": p["timeoutMs"], "net_password": p["netPassword"],
        }, timeout=FK_CONNECT_TIMEOUT)
        r.raise_for_status()
        data = r.json()
        if not data.get("success"):
            return {}, data.get("error") or "info failed"
        return data.get("info") or {}, ""
    except Exception as e:
        return {}, _request_error(e)


def sync_time(ip: str, port: int, config: dict) -> Tuple[bool, str]:
    try:
        data = _post("/sync_time", _payload(ip, port, config))
        return (True, "") if data.get("success") else (False, data.get("error") or "sync failed")
    except Exception as e:
        return False, _request_error(e)


def test_connection(ip: str, port: int, config: dict) -> dict:
    st = bridge_status()
    if not st.get("reachable"):
        return {"success": False, "error": st.get("error", "FkBridge unreachable")}
    if not st.get("dll_loaded"):
        return {"success": False, "error": "FKAttend.dll not loaded next to FkBridge.exe"}
    
    # Try with original configuration first
    cfg = config.copy()
    ok, err = connect(ip, port, cfg)
    if ok:
        info, err2 = device_info(ip, port, cfg)
        if not err2:
            return {"success": True, "serial_number": info.get("serial_number"), "device_name": info.get("product_name"),
                    "device_time": info.get("device_time"), "bridge": st, "license": cfg.get("license", 1263)}
    
    # Fallback to alternate license
    orig_license = int(config.get("license", 1263))
    alt_license = 1263 if orig_license == 1262 else 1262
    cfg["license"] = alt_license
    
    logger.info(f"Retrying connection test to {ip}:{port} with alternate license {alt_license}...")
    ok_alt, err_alt = connect(ip, port, cfg)
    if ok_alt:
        info, err2 = device_info(ip, port, cfg)
        if not err2:
            # Propagate the working license back to the caller config dict
            config["license"] = alt_license
            return {"success": True, "serial_number": info.get("serial_number"), "device_name": info.get("product_name"),
                    "device_time": info.get("device_time"), "bridge": st, "license": alt_license}
        return {"success": False, "error": err2}
    
    return {"success": False, "error": err}