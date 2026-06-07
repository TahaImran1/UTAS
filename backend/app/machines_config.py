"""
machines_config.py
------------------
CRUD helper for machines.json.
Keeps machine IP/port/location data completely separate from .env credentials.
"""
import json
import os
import logging

def get_app_data_dir():
    app_data = os.getenv('APPDATA')
    if not app_data:
        app_data = os.path.expanduser("~")
    dir_path = os.path.join(app_data, "UTAS")
    os.makedirs(dir_path, exist_ok=True)
    return dir_path

APP_DATA_DIR = get_app_data_dir()
MACHINES_FILE = os.path.join(APP_DATA_DIR, "machines.json")
logger = logging.getLogger(__name__)


def load_machines() -> list:
    """Load and return the list of machine configs."""
    if not os.path.exists(MACHINES_FILE):
        return []
    try:
        with open(MACHINES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return [data]
        if isinstance(data, list):
            return [m for m in data if isinstance(m, dict)]
        logger.error(f"machines.json has unexpected type: {type(data)}")
        return []
    except Exception as e:
        logger.error(f"Error loading machines.json: {e}")
        return []


def _save_machines(machines: list):
    """Persist the machine list to disk."""
    with open(MACHINES_FILE, "w") as f:
        json.dump(machines, f, indent=4)


def save_machine(machine: dict) -> dict:
    """
    Add or update a machine entry.
    Matches by SN first, then by IP:port if SN is empty.
    Returns the saved machine dict.
    """
    machines = load_machines()
    sn = machine.get("sn", "").strip()
    ip = machine.get("ip", "").strip()
    port = int(machine.get("port", 4370))

    for i, m in enumerate(machines):
        # Match by SN if both have it
        if sn and m.get("sn") == sn:
            machines[i] = machine
            _save_machines(machines)
            return machine
        # Match by IP+port as fallback
        if not sn and m.get("ip") == ip and int(m.get("port", 4370)) == port:
            machines[i] = machine
            _save_machines(machines)
            return machine

    machines.append(machine)
    _save_machines(machines)
    return machine


def delete_machine(sn: str = "", ip: str = "", port: int = 4370) -> bool:
    """Remove a machine by SN or IP:port. Returns True if removed."""
    machines = load_machines()
    original_len = len(machines)
    if sn:
        machines = [m for m in machines if m.get("sn") != sn]
    else:
        machines = [m for m in machines
                    if not (m.get("ip") == ip and int(m.get("port", 4370)) == port)]
    if len(machines) < original_len:
        _save_machines(machines)
        return True
    return False


def update_sn(ip: str, port: int, sn: str) -> bool:
    """
    Auto-update SN after a successful first connect.
    Called by pull_engine after connecting to a machine that had an empty SN.
    """
    machines = load_machines()
    for i, m in enumerate(machines):
        if m.get("ip") == ip and int(m.get("port", 4370)) == port:
            machines[i]["sn"] = sn
            _save_machines(machines)
            logger.info(f"Auto-updated SN={sn} for machine {ip}:{port}")
            return True
    return False


def get_machine(sn: str = "", ip: str = "", port: int = 4370) -> dict | None:
    """Find a single machine by SN or IP:port."""
    machines = load_machines()
    for m in machines:
        if sn and m.get("sn") == sn:
            return m
        if not sn and m.get("ip") == ip and int(m.get("port", 4370)) == port:
            return m
    return None

