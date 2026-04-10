"""
pull_engine.py
--------------
Manages all ZKTeco pull-protocol connections.

- APScheduler runs get_attendance() for every configured machine every PULL_SYNC_INTERVAL seconds
- All machines accessed with ommit_ping=True (remote/internet machines via port-forward)
- Uses the same insert_log_oracle() from zk/db.py as the push server
- Thread-safe: each machine gets its own connection object
"""
import os
import logging
import threading
from datetime import datetime
from typing import Dict, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from zk import ZK
from zk.exception import ZKNetworkError, ZKErrorResponse, ZKErrorConnection
import machines_config

logger = logging.getLogger(__name__)

# ─── Configuration from .env ───────────────────────────────────────────────────
SYNC_INTERVAL = int(os.getenv("PULL_SYNC_INTERVAL", "20"))
AUTO_START    = os.getenv("PULL_AUTO_START", "true").lower() == "true"
AUTO_DELETE   = os.getenv("PULL_AUTO_DELETE", "false").lower() == "true"
PULL_TIMEOUT  = int(os.getenv("PULL_TIMEOUT", "15"))


# ─── State ─────────────────────────────────────────────────────────────────────
class MachineState:
    def __init__(self, config: dict):
        self.config   = config          # IP, port, location, sn, password
        self.sn       = config.get("sn", "")
        self.ip       = config["ip"]
        self.port     = int(config.get("port", 4370))
        self.location = config.get("location", "")
        self.password = int(config.get("password", 0))

        self.conn: Optional[ZK]  = None
        self.status: str         = "offline"   # online | offline | syncing
        self.last_sync: Optional[datetime] = None
        self.last_record_count: int = 0
        self.last_error: str     = ""
        self.lock = threading.Lock()

    def to_dict(self) -> dict:
        return {
            "sn":               self.sn,
            "ip":               self.ip,
            "port":             self.port,
            "location":         self.location,
            "status":           self.status,
            "last_sync":        self.last_sync.isoformat() if self.last_sync else None,
            "last_record_count":self.last_record_count,
            "last_error":       self.last_error,
        }


class ZKPullManager:
    """
    Central manager for all ZK pull operations.
    Created as a singleton and attached to the FastAPI app.
    """

    def __init__(self):
        self._machines: Dict[str, MachineState] = {}   # key = ip:port or sn
        self._scheduler = BackgroundScheduler(daemon=True)
        self._sync_lock = threading.Lock()

    # ─── Lifecycle ──────────────────────────────────────────────────────────────

    def start(self):
        """Called on FastAPI startup. Loads machines and starts scheduler."""
        self._reload_machines()
        if AUTO_START:
            self._scheduler.add_job(
                self._sync_all_tick,
                trigger=IntervalTrigger(seconds=SYNC_INTERVAL),
                id="pull_sync_all",
                replace_existing=True,
                next_run_time=datetime.now()   # run immediately on start
            )
            self._scheduler.start()
            logger.info(f"[PullEngine] Auto-sync started — every {SYNC_INTERVAL}s")
        else:
            logger.info("[PullEngine] Auto-sync disabled (PULL_AUTO_START=false)")

    def stop(self):
        """Called on FastAPI shutdown. Gracefully disconnects all devices."""
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
        for key, state in self._machines.items():
            self._disconnect(state)
        logger.info("[PullEngine] Stopped.")

    def reload(self):
        """Hot-reload machines from machines.json without restart."""
        self._reload_machines()

    # ─── Internal helpers ────────────────────────────────────────────────────────

    def _reload_machines(self):
        configs = machines_config.load_machines()
        for cfg in configs:
            key = cfg.get("sn") or f"{cfg['ip']}:{cfg.get('port', 4370)}"
            if key not in self._machines:
                self._machines[key] = MachineState(cfg)
        logger.info(f"[PullEngine] Loaded {len(self._machines)} machine(s)")

    def _get_or_create_state(self, ip: str, port: int = 4370) -> Optional[MachineState]:
        for state in self._machines.values():
            if state.ip == ip and state.port == port:
                return state
        return None

    def _connect(self, state: MachineState) -> bool:
        """Attempt TCP connection to device. Returns True if successful."""
        try:
            zk = ZK(
                state.ip,
                port=state.port,
                timeout=PULL_TIMEOUT,
                password=state.password,
                ommit_ping=True,       # ← critical for remote/internet machines
                verbose=False
            )
            conn = zk.connect()
            state.conn = conn

            # Auto-resolve SN if not stored yet
            if not state.sn:
                try:
                    sn = conn.get_serialnumber()
                    state.sn = sn
                    machines_config.update_sn(state.ip, state.port, sn)
                    logger.info(f"[PullEngine] Auto-fetched SN={sn} for {state.ip}")
                    # Re-key in _machines dict
                    self._machines[sn] = state
                except Exception:
                    pass

            state.status = "online"
            state.last_error = ""
            return True
        except (ZKNetworkError, ZKErrorConnection, ZKErrorResponse, OSError) as e:
            state.status = "offline"
            state.last_error = str(e)
            logger.warning(f"[PullEngine] Cannot connect to {state.ip}:{state.port} — {e}")
            return False

    def _disconnect(self, state: MachineState):
        if state.conn:
            try:
                state.conn.disconnect()
            except Exception:
                pass
            state.conn = None
        state.status = "offline"

    # ─── Sync operations ─────────────────────────────────────────────────────────

    def _sync_all_tick(self):
        """APScheduler job: called every SYNC_INTERVAL seconds."""
        logger.info(f"[PullEngine] Sync tick @ {datetime.now().strftime('%H:%M:%S')}")
        self._reload_machines()   # pick up any newly added machines
        for key, state in list(self._machines.items()):
            threading.Thread(
                target=self._pull_machine,
                args=(state,),
                daemon=True,
                name=f"pull-{state.ip}"
            ).start()

    def _pull_machine(self, state: MachineState):
        """Pull attendance from one machine and insert to Oracle."""
        with state.lock:
            if state.status == "syncing":
                logger.debug(f"[PullEngine] {state.ip} already syncing, skipping")
                return

            state.status = "syncing"
            try:
                # Connect if not already connected
                if not state.conn or not state.conn.is_connect:
                    if not self._connect(state):
                        return

                # Pull records
                records = state.conn.get_attendance()
                count = len(records)
                logger.info(f"[PullEngine] {state.ip} — {count} records pulled")

                if count > 0:
                    # Get machine reference string (same format as old app)
                    try:
                        device_name = state.conn.get_device_name()
                        sn          = state.sn or state.conn.get_serialnumber()
                        mac         = state.conn.get_mac()
                        machine_ref = f"{device_name} - {sn} - {mac}"
                    except Exception:
                        machine_ref = state.ip

                    # Insert to Oracle using existing db function
                    self._insert_to_oracle(records, machine_ref)

                    # Auto-delete from device if configured
                    if AUTO_DELETE:
                        try:
                            state.conn.clear_attendance()
                            logger.info(f"[PullEngine] {state.ip} — attendance cleared from device")
                        except Exception as e:
                            logger.error(f"[PullEngine] {state.ip} — clear failed: {e}")

                state.last_sync = datetime.now()
                state.last_record_count = count
                state.status = "online"

            except Exception as e:
                logger.error(f"[PullEngine] {state.ip} pull failed: {e}")
                state.last_error = str(e)
                state.status = "offline"
                self._disconnect(state)

    def _insert_to_oracle(self, records, machine_ref: str):
        """Reuse the existing zk/db.py Oracle insert function."""
        try:
            from .zk import db
            config = db.load_latest_config("Oracle")
            conn = db.connect_db_oracle(config)
            db.insert_log_oracle(conn, records, machine_ref, config)
            conn.close()
        except Exception as e:
            logger.error(f"[PullEngine] Oracle insert error: {e}")
            raise

    # ─── Manual / API-triggered operations ───────────────────────────────────────

    def pull_once(self, sn: str = "", ip: str = "", port: int = 4370) -> dict:
        """
        Manually trigger a one-shot pull for a specific machine.
        Called from the /pull/attendance/{sn} endpoint.
        """
        state = self._find_state(sn, ip, port)
        if not state:
            return {"success": False, "error": "Machine not found"}
        self._pull_machine(state)
        return {
            "success": state.status in ("online", "syncing"),
            "records": state.last_record_count,
            "last_sync": state.last_sync.isoformat() if state.last_sync else None,
            "error": state.last_error,
        }

    def get_device_info(self, sn: str = "", ip: str = "", port: int = 4370) -> dict:
        """
        Return firmware, serial, MAC, platform and memory info.
        Called from /pull/device-info/{sn}.
        """
        state = self._find_state(sn, ip, port)
        if not state:
            return {"error": "Machine not found"}
        try:
            if not state.conn or not state.conn.is_connect:
                if not self._connect(state):
                    return {"error": state.last_error}

            conn = state.conn
            conn.read_sizes()
            return {
                "ip":              state.ip,
                "port":            state.port,
                "location":        state.location,
                "firmware":        self._safe_call(conn.get_firmware_version),
                "serial_number":   self._safe_call(conn.get_serialnumber),
                "platform":        self._safe_call(conn.get_platform),
                "mac":             self._safe_call(conn.get_mac),
                "device_name":     self._safe_call(conn.get_device_name),
                "users":           conn.users,
                "records":         conn.records,
                "fingers":         conn.fingers,
                "users_cap":       conn.users_cap,
                "rec_cap":         conn.rec_cap,
            }
        except Exception as e:
            return {"error": str(e)}

    def clear_attendance(self, sn: str = "", ip: str = "", port: int = 4370) -> dict:
        """Clear attendance log on the device."""
        state = self._find_state(sn, ip, port)
        if not state:
            return {"success": False, "error": "Machine not found"}
        try:
            if not state.conn or not state.conn.is_connect:
                if not self._connect(state):
                    return {"success": False, "error": state.last_error}
            state.conn.clear_attendance()
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def sync_time(self, sn: str = "", ip: str = "", port: int = 4370) -> dict:
        """Sync device clock to server time."""
        state = self._find_state(sn, ip, port)
        if not state:
            return {"success": False, "error": "Machine not found"}
        try:
            if not state.conn or not state.conn.is_connect:
                if not self._connect(state):
                    return {"success": False, "error": state.last_error}
            state.conn.set_time(datetime.now())
            return {"success": True, "synced_to": datetime.now().isoformat()}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def test_connection(self, ip: str, port: int = 4370, password: int = 0) -> dict:
        """
        Test a connection to a machine (used by UI Add Machine flow).
        Returns device info without persisting anything.
        """
        try:
            zk = ZK(ip, port=port, timeout=PULL_TIMEOUT,
                    password=password, ommit_ping=True, verbose=False)
            conn = zk.connect()
            info = {
                "success":       True,
                "firmware":      self._safe_call(conn.get_firmware_version),
                "serial_number": self._safe_call(conn.get_serialnumber),
                "device_name":   self._safe_call(conn.get_device_name),
                "platform":      self._safe_call(conn.get_platform),
                "mac":           self._safe_call(conn.get_mac),
            }
            conn.disconnect()
            return info
        except Exception as e:
            return {"success": False, "error": str(e)}

    def add_machine(self, machine: dict) -> dict:
        """Add a new machine to machines.json and register it in the engine."""
        machines_config.save_machine(machine)
        key = machine.get("sn") or f"{machine['ip']}:{machine.get('port', 4370)}"
        self._machines[key] = MachineState(machine)
        return {"success": True, "machine": machine}

    def remove_machine(self, sn: str = "", ip: str = "", port: int = 4370) -> dict:
        """Remove a machine from machines.json and stop polling it."""
        state = self._find_state(sn, ip, port)
        if state:
            self._disconnect(state)
            key = sn or f"{ip}:{port}"
            self._machines.pop(key, None)
        machines_config.delete_machine(sn=sn, ip=ip, port=port)
        return {"success": True}

    def get_all_status(self) -> list:
        """Return status of all registered machines (for dashboard and machines page)."""
        return [state.to_dict() for state in self._machines.values()]

    # ─── Utilities ───────────────────────────────────────────────────────────────

    def _find_state(self, sn: str, ip: str, port: int) -> Optional[MachineState]:
        if sn and sn in self._machines:
            return self._machines[sn]
        key = f"{ip}:{port}"
        if key in self._machines:
            return self._machines[key]
        # search by IP+port
        for state in self._machines.values():
            if state.ip == ip and state.port == port:
                return state
        return None

    @staticmethod
    def _safe_call(fn):
        try:
            return fn()
        except Exception:
            return None


# Singleton instance — imported by main.py
pull_manager = ZKPullManager()
