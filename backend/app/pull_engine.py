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
from apscheduler.triggers.cron import CronTrigger

from zk import ZK
from zk.exception import ZKNetworkError, ZKErrorResponse, ZKErrorConnection
import machines_config
import fk_bridge_client
from fk_bridge_client import is_fk_driver

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
        self.protocol = config.get("protocol", "TCP") # TCP or HTTP
        self.driver = (config.get("driver") or "zk").lower()
        if self.driver == "amt":
            self.driver = "fk"

        self.name         = config.get("name", "")
        self.enabled      = config.get("enabled", True)
        if "company_names" in config:
            self.company_names = config["company_names"] or []
        else:
            comp = config.get("company_name", "None")
            if comp and comp != "None":
                self.company_names = [comp]
            else:
                self.company_names = []

        self.sync_type     = config.get("sync_type", "interval")
        self.sync_interval = int(config.get("sync_interval", 20))
        self.sync_days     = config.get("sync_days", [])
        self.sync_time     = config.get("sync_time", "00:00")

        self.conn: Optional[ZK]  = None
        self.fk_connected: bool = False
        self.status: str         = "offline"   # online | offline | syncing
        
        self.last_sync: Optional[datetime] = None
        last_sync_str = config.get("last_sync")
        if last_sync_str:
            try:
                self.last_sync = datetime.fromisoformat(last_sync_str.replace("Z", "+00:00"))
            except Exception:
                pass
                
        self.last_record_count: int = 0
        self.last_error: str     = ""
        self.last_seen: Optional[datetime] = None # For Push heartbeats
        self.lock = threading.Lock()

    def get_schedule_key(self) -> tuple:
        return (
            self.sync_type,
            self.sync_interval,
            tuple(self.sync_days) if self.sync_days else (),
            self.sync_time,
            self.protocol,
            self.driver,
            tuple(self.company_names) if self.company_names else (),
            self.enabled,
            self.name
        )

    def to_dict(self) -> dict:
        # For HTTP (Push) devices, status is based on recent pulse
        status = self.status
        if self.last_seen and (self.protocol == "HTTP" or is_fk_driver(self.driver)):
            delta = (datetime.now() - self.last_seen).total_seconds()
            if delta < 120: # 2 minutes
                status = "online"
            else:
                status = "offline"

        return {
            "sn":               self.sn,
            "ip":               self.ip,
            "port":             self.port,
            "location":         self.location,
            "status":           status,
            "last_sync":        self.last_sync.isoformat() if self.last_sync else None,
            "last_record_count":self.last_record_count,
            "last_error":       self.last_error,
            "protocol":         self.protocol,
            "company_name":     self.company_names[0] if self.company_names else "None",
            "company_names":    self.company_names,
            "driver":           self.driver,
            "sync_type":        self.sync_type,
            "sync_interval":    self.sync_interval,
            "sync_days":        self.sync_days,
            "sync_time":        self.sync_time,
            "name":             self.name,
            "enabled":          self.enabled,
        }

    def get_machine_ref(self) -> str:
        """Returns the machine reference string used for database inserts."""
        if self.protocol == "HTTP":
            return self.sn
        if is_fk_driver(self.driver):
            return self.sn or self.ip
        # For ZK TCP, try to get from active connection or cached config
        if self.conn and self.conn.is_connect:
            try:
                device_name = self.conn.get_device_name()
                sn = self.sn or self.conn.get_serialnumber()
                mac = self.conn.get_mac()
                return f"{device_name} - {sn} - {mac}"
            except Exception:
                pass
        
        # Fallback to cached properties in config
        device_name = self.config.get("device_name") or self.name or "ZK Device"
        mac = self.config.get("mac")
        if device_name and self.sn and mac:
            return f"{device_name} - {self.sn} - {mac}"
        return self.sn or self.ip


class ZKPullManager:
    """
    Central manager for all ZK pull operations.
    Created as a singleton and attached to the FastAPI app.
    """

    def __init__(self):
        self._machines: Dict[str, MachineState] = {}   # key = ip:port or sn
        self._scheduler = BackgroundScheduler(daemon=True)
        self._sync_lock = threading.Lock()
        self.enabled = True # Administrative toggle for the engine
        self._active_schedules = {} # Track active schedule keys

    # ─── Lifecycle ──────────────────────────────────────────────────────────────

    def start(self):
        """Called on FastAPI startup. Loads machines and starts scheduler."""
        self._reload_machines()
        # Sync Company/Protocol mappings from Oracle
        self.sync_metadata_from_oracle()
        if AUTO_START:
            self._scheduler.start()
            self.reconcile_jobs()
            logger.info("[PullEngine] Auto-sync started — per-machine jobs scheduled")
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
        self.reconcile_jobs()

    # ─── Internal helpers ────────────────────────────────────────────────────────

    def _reload_machines(self):
        configs = machines_config.load_machines()
        current_keys = set()
        for cfg in configs:
            key = cfg.get("sn") or f"{cfg['ip']}:{cfg.get('port', 4370)}"
            current_keys.add(key)
            if key not in self._machines:
                self._machines[key] = MachineState(cfg)
            else:
                state = self._machines[key]
                state.config = cfg
                last_sync_str = cfg.get("last_sync")
                if last_sync_str:
                    try:
                        state.last_sync = datetime.fromisoformat(last_sync_str.replace("Z", "+00:00"))
                    except Exception:
                        pass
                state.ip = cfg["ip"]
                state.port = int(cfg.get("port", 4370))
                state.location = cfg.get("location", "")
                state.password = int(cfg.get("password", 0))
                state.sn = cfg.get("sn", "")
                state.protocol = cfg.get("protocol", "TCP")
                state.name = cfg.get("name", "")
                state.enabled = cfg.get("enabled", True)
                state.company_names = cfg.get("company_names", [])
                if not state.company_names:
                    comp = cfg.get("company_name", "None")
                    if comp and comp != "None":
                        state.company_names = [comp]
                    else:
                        state.company_names = []
                state.sync_type = cfg.get("sync_type", "interval")
                state.sync_interval = int(cfg.get("sync_interval", 20))
                state.sync_days = cfg.get("sync_days", [])
                state.sync_time = cfg.get("sync_time", "00:00")
                state.driver = (cfg.get("driver") or "zk").lower()
                if state.driver == "amt":
                    state.driver = "fk"
        
        # Disconnect and remove deleted machines
        for key in list(self._machines.keys()):
            if key not in current_keys:
                state = self._machines.pop(key, None)
                if state:
                    self._disconnect(state)
        logger.info(f"[PullEngine] Loaded {len(self._machines)} machine(s)")

    def reconcile_jobs(self):
        """
        Reconcile scheduler jobs to match the current in-memory machines state.
        This handles adding new jobs, updating changed jobs, and removing deleted jobs.
        """
        if not self.enabled:
            for job in list(self._scheduler.get_jobs()):
                if job.id.startswith("pull_machine_"):
                    self._scheduler.remove_job(job.id)
            self._active_schedules.clear()
            return

        current_keys = set(self._machines.keys())
        
        # 1. Remove jobs for machines that no longer exist
        for job_id in [job.id for job in self._scheduler.get_jobs()]:
            if job_id.startswith("pull_machine_"):
                m_key = job_id[len("pull_machine_"):]
                if m_key not in current_keys:
                    try:
                        self._scheduler.remove_job(job_id)
                        logger.info(f"[PullEngine] Removed scheduler job for deleted machine: {m_key}")
                    except Exception as e:
                        logger.error(f"[PullEngine] Error removing job {job_id}: {e}")
                    self._active_schedules.pop(m_key, None)

        # 2. Add or update jobs for existing machines
        for key, state in self._machines.items():
            job_id = f"pull_machine_{key}"
            sched_key = state.get_schedule_key()
            
            existing_job = self._scheduler.get_job(job_id)
            if existing_job and self._active_schedules.get(key) == sched_key:
                continue
                
            if existing_job:
                try:
                    self._scheduler.remove_job(job_id)
                    logger.info(f"[PullEngine] Removing existing job {job_id} to update schedule.")
                except Exception as e:
                    logger.error(f"[PullEngine] Error removing job {job_id} for update: {e}")
            
            trigger = None
            if state.sync_type == "cron":
                try:
                    day_of_week = ",".join(state.sync_days) if state.sync_days else "*"
                    parts = state.sync_time.split(":")
                    hour = int(parts[0]) if len(parts) > 0 else 0
                    minute = int(parts[1]) if len(parts) > 1 else 0
                    trigger = CronTrigger(day_of_week=day_of_week, hour=hour, minute=minute, second=0)
                except Exception as e:
                    logger.error(f"[PullEngine] Failed to create CronTrigger for {key}: {e}. Falling back to default interval.")
            
            if trigger is None:
                interval_secs = state.sync_interval
                if interval_secs < 20:
                    interval_secs = 20
                trigger = IntervalTrigger(seconds=interval_secs)
                
            try:
                self._scheduler.add_job(
                    self._pull_machine_job,
                    trigger=trigger,
                    args=[key],
                    id=job_id,
                    replace_existing=True,
                    next_run_time=datetime.now()
                )
                self._active_schedules[key] = sched_key
                logger.info(f"[PullEngine] Scheduled job {job_id} successfully (Type: {state.sync_type}, Args: {sched_key})")
            except Exception as e:
                logger.error(f"[PullEngine] Failed to schedule job {job_id}: {e}")

    def _pull_machine_job(self, key: str):
        """Scheduler job callback: pulls from the machine or queues a push command."""
        if not self.enabled:
            return
            
        state = self._machines.get(key)
        if not state:
            logger.warning(f"[PullEngine] Scheduled job fired for non-existent machine: {key}")
            return

        if not state.enabled:
            logger.debug(f"[PullEngine] Scheduled job for {key} skipped — Machine is disabled.")
            return

        # MANDATORY CHECK: Machine must be assigned to a company
        if not state.company_names:
            logger.debug(f"[PullEngine] Scheduled job for {key} skipped — No company assigned.")
            return
            
        if state.protocol == "HTTP":
            self._queue_push_sync_command(state)
        else:
            threading.Thread(
                target=self._pull_machine,
                args=(state,),
                daemon=True,
                name=f"pull-{state.ip}"
            ).start()

    def _queue_push_sync_command(self, state: MachineState):
        """Queue a get_glog or DATA QUERY ATTLOG command in main.COMMAND_QUEUE for HTTP Push devices."""
        import sys
        COMMAND_QUEUE = None
        main_module = sys.modules.get('__main__')
        if main_module and hasattr(main_module, 'COMMAND_QUEUE'):
            COMMAND_QUEUE = main_module.COMMAND_QUEUE
        else:
            try:
                import main
                COMMAND_QUEUE = main.COMMAND_QUEUE
            except ImportError:
                pass

        if COMMAND_QUEUE is None:
            logger.error("[PullEngine] Failed to resolve COMMAND_QUEUE from __main__ or main")
            return

        sn = state.sn
        if not sn:
            logger.warning(f"[PullEngine] Push device scheduling skipped: no Serial Number found for {state.ip}")
            return

        if sn not in COMMAND_QUEUE:
            COMMAND_QUEUE[sn] = []

        driver = (state.driver or "zk").lower()
        if driver in ("fk", "amt"):
            if "get_glog" not in COMMAND_QUEUE[sn]:
                COMMAND_QUEUE[sn].append("get_glog")
                logger.info(f"[PullEngine] Scheduled: Queued initial get_glog for FK Push device {sn}")
        else:
            end_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cmd = f"C:101:DATA QUERY ATTLOG StartTime=2000-01-01 00:00:00\tEndTime={end_ts}"
            has_query = any("DATA QUERY ATTLOG" in c for c in COMMAND_QUEUE[sn])
            if not has_query:
                COMMAND_QUEUE[sn].append(cmd)
                logger.info(f"[PullEngine] Scheduled: Queued DATA QUERY ATTLOG for ZK Push device {sn}")

    def _get_or_create_state(self, ip: str, port: int = 4370) -> Optional[MachineState]:
        for state in self._machines.values():
            if state.ip == ip and state.port == port:
                return state
        return None

    def _connect(self, state: MachineState) -> bool:
        """Attempt connection (pyzk or FK bridge)."""
        if is_fk_driver(state.driver):
            try:
                ok, err = fk_bridge_client.connect(state.ip, state.port, state.config)
                state.fk_connected = ok
                if ok:
                    state.status = "online"
                    state.last_error = ""
                    return True
                state.status = "offline"
                state.last_error = err
                logger.warning(f"[PullEngine] FK bridge connect failed {state.ip}:{state.port} — {err}")
                return False
            except Exception as e:
                state.status = "offline"
                state.last_error = str(e)
                logger.warning(f"[PullEngine] FK bridge error {state.ip} — {e}")
                return False
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

    def _close_connection(self, state: MachineState):
        """Cleanly close TCP connection without modifying machine online status."""
        if is_fk_driver(state.driver):
            state.fk_connected = False
        elif state.conn:
            try:
                state.conn.disconnect()
            except Exception:
                pass
            state.conn = None

    def _disconnect(self, state: MachineState):
        self._close_connection(state)
        state.status = "offline"

    # ─── Sync operations ─────────────────────────────────────────────────────────

    def _sync_all_tick(self):
        """APScheduler job: called every SYNC_INTERVAL seconds."""
        if not self.enabled:
            logger.info("[PullEngine] Sync tick skipped (engine is DISABLED)")
            return

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
        if not state.enabled:
            logger.debug(f"[PullEngine] {state.sn or state.ip} skipped — Machine is disabled.")
            return

        if state.protocol == "HTTP":
            logger.debug(f"[PullEngine] {state.sn or state.ip} is HTTP push-only — skipping TCP pull")
            return

        # MANDATORY CHECK: Machine must be assigned to a company
        if not state.company_names:
            logger.debug(f"[PullEngine] {state.ip} skipped - Not mapped to any company.")
            return

        with state.lock:
            if state.status == "syncing":
                logger.debug(f"[PullEngine] {state.ip} already syncing, skipping")
                return

            state.status = "syncing"
            try:
                if is_fk_driver(state.driver):
                    if not state.fk_connected:
                        if not self._connect(state):
                            state.status = "offline"
                            return
                    records, err = fk_bridge_client.pull_attendance(state.ip, state.port, state.config)
                    if err:
                        raise RuntimeError(err)
                    count = len(records)
                    logger.info(f"[PullEngine] FK {state.ip} — {count} records pulled")
                    if count > 0:
                        machine_ref = state.sn or state.ip
                        self._insert_to_db(records, machine_ref, state.company_names)
                    if AUTO_DELETE and count > 0:
                        fk_bridge_client.clear_attendance(state.ip, state.port, state.config)
                else:
                    if not state.conn or not state.conn.is_connect:
                        if not self._connect(state):
                            state.status = "offline"
                            return
                    records = state.conn.get_attendance()
                    count = len(records)
                    logger.info(f"[PullEngine] {state.ip} — {count} records pulled")
                    if count > 0:
                        try:
                            device_name = state.conn.get_device_name()
                            sn          = state.sn or state.conn.get_serialnumber()
                            mac         = state.conn.get_mac()
                            machine_ref = f"{device_name} - {sn} - {mac}"
                        except Exception:
                            machine_ref = state.ip
                        self._insert_to_db(records, machine_ref, state.company_names)
                        if AUTO_DELETE:
                            try:
                                state.conn.disable_device()
                                try:
                                    state.conn.clear_attendance()
                                    logger.info(f"[PullEngine] {state.ip} — attendance cleared from device")
                                finally:
                                    state.conn.enable_device()
                            except Exception as e:
                                logger.error(f"[PullEngine] {state.ip} — clear failed: {e}")

                now_sync = datetime.now()
                state.last_sync = now_sync
                state.last_record_count = count
                state.status = "online"
                try:
                    machines_config.update_machine_last_sync(state.sn, state.ip, state.port, now_sync.isoformat())
                except Exception as e:
                    logger.error(f"[PullEngine] Error saving last sync to config: {e}")

            except Exception as e:
                logger.error(f"[PullEngine] {state.ip} pull failed: {e}")
                state.last_error = str(e)
                state.status = "offline"
                self._disconnect(state)
            finally:
                self._close_connection(state)

    def _insert_to_db(self, records, machine_ref: str, company_names: list[str]):
        """Reuse the existing zk/db.py generic insert function."""
        try:
            from zk import db
            db.insert_log_generic(records, machine_ref, company_names)
        except Exception as e:
            logger.error(f"[PullEngine] Database insert error: {e}")
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

        if state.status == "syncing":
            return {
                "success": True,
                "message": f"Device {state.sn or state.ip} is already syncing.",
                "records": state.last_record_count,
                "last_sync": state.last_sync.isoformat() if state.last_sync else None,
                "error": "",
            }

        state.status = "syncing"
        threading.Thread(
            target=self._pull_machine,
            args=(state,),
            daemon=True,
            name=f"manual-pull-{state.ip}"
        ).start()

        return {
            "success": True,
            "message": f"Sync started for {state.sn or state.ip}. Records will appear shortly.",
            "records": state.last_record_count,
            "last_sync": state.last_sync.isoformat() if state.last_sync else None,
            "error": "",
        }

    def get_device_info(self, sn: str = "", ip: str = "", port: int = 4370) -> dict:
        """
        Return firmware, serial, MAC, platform and memory info.
        Called from /pull/device-info/{sn}.
        """
        state = self._find_state(sn, ip, port)
        if not state:
            return {"error": "Machine not found"}
            
        if state.protocol == "HTTP":
            return {
                "ip":              state.ip,
                "port":            state.port,
                "location":        state.location,
                "firmware":        state.config.get("firmware", "Unknown"),
                "serial_number":   state.sn,
                "platform":        state.config.get("platform", "Unknown"),
                "mac":             state.config.get("mac", "Unknown"),
                "device_name":     state.config.get("device_name", "Unknown"),
                "device_time":     state.config.get("device_time", "Unknown"),
                "users":           state.config.get("users", 0),
                "records":         state.config.get("records", 0),
                "fingers":         state.config.get("fingers", 0),
                "users_cap":       state.config.get("users_cap", "Unknown"),
                "rec_cap":         state.config.get("rec_cap", "Unknown"),
            }

        try:
            with state.lock:
                if is_fk_driver(state.driver):
                    if not state.fk_connected and not self._connect(state):
                        return {"error": state.last_error}
                    info, err = fk_bridge_client.device_info(state.ip, state.port, state.config)
                    if err:
                        return {"error": err}
                    return {
                        "ip": state.ip,
                        "port": state.port,
                        "location": state.location,
                        "driver": state.driver,
                        "serial_number": info.get("serial_number"),
                        "device_name": info.get("product_name"),
                        "device_time": info.get("device_time"),
                    }
                if not state.conn or not state.conn.is_connect:
                    if not self._connect(state):
                        return {"error": state.last_error}

                conn = state.conn
                conn.read_sizes()
                time_obj = self._safe_call(conn.get_time)
                device_time_str = str(time_obj) if time_obj else "Unknown"
                
                return {
                    "ip":              state.ip,
                    "port":            state.port,
                    "location":        state.location,
                    "firmware":        self._safe_call(conn.get_firmware_version),
                    "serial_number":   self._safe_call(conn.get_serialnumber),
                    "platform":        self._safe_call(conn.get_platform),
                    "mac":             self._safe_call(conn.get_mac),
                    "device_name":     self._safe_call(conn.get_device_name),
                    "device_time":     device_time_str,
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
            with state.lock:
                if is_fk_driver(state.driver):
                    ok, err = fk_bridge_client.clear_attendance(state.ip, state.port, state.config)
                    return {"success": ok, "error": err or None}
                # Always close any stale connection first
                self._close_connection(state)
                if not self._connect(state):
                    return {"success": False, "error": state.last_error}
                try:
                    state.conn.disable_device()
                    try:
                        state.conn.clear_attendance()
                    finally:
                        state.conn.enable_device()
                finally:
                    self._close_connection(state)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def sync_time(self, sn: str = "", ip: str = "", port: int = 4370) -> dict:
        """Sync device clock to server time."""
        state = self._find_state(sn, ip, port)
        if not state:
            return {"success": False, "error": "Machine not found"}

        if state.protocol == "HTTP":
            driver = (state.driver or "zk").lower()
            if driver in ("fk", "amt"):
                return {
                    "success": True,
                    "message": f"FK Push device {state.sn} automatically syncs time on heartbeat."
                }
            else:
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cmd = f"C:102:SET OPTIONS DateTime={now_str}"
                import sys
                COMMAND_QUEUE = None
                main_module = sys.modules.get('__main__')
                if main_module and hasattr(main_module, 'COMMAND_QUEUE'):
                    COMMAND_QUEUE = main_module.COMMAND_QUEUE
                else:
                    try:
                        import main
                        COMMAND_QUEUE = main.COMMAND_QUEUE
                    except ImportError:
                        pass
                if COMMAND_QUEUE is None:
                    return {"success": False, "error": "Failed to resolve COMMAND_QUEUE"}
                if state.sn not in COMMAND_QUEUE:
                    COMMAND_QUEUE[state.sn] = []
                if cmd not in COMMAND_QUEUE[state.sn]:
                    COMMAND_QUEUE[state.sn].append(cmd)
                    logger.info(f"[PullEngine] SyncTime: Queued DateTime SET OPTIONS command for {state.sn}")
                return {
                    "success": True,
                    "message": f"Time sync command queued for {state.sn}. Clock will sync on next heartbeat."
                }

        try:
            with state.lock:
                if is_fk_driver(state.driver):
                    ok, err = fk_bridge_client.sync_time(state.ip, state.port, state.config)
                    return {"success": ok, "synced_to": datetime.now().isoformat(), "error": err or None}
                self._close_connection(state)
                if not self._connect(state):
                    return {"success": False, "error": state.last_error}
                try:
                    state.conn.disable_device()
                    try:
                        state.conn.set_time(datetime.now())
                    finally:
                        state.conn.enable_device()
                finally:
                    self._close_connection(state)
            return {"success": True, "synced_to": datetime.now().isoformat()}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def test_connection(self, ip: str, port: int = 4370, password: int = 0, driver: str = "zk", config: dict = None) -> dict:
        """
        Test a connection to a machine (used by UI Add Machine flow).
        Returns device info without persisting anything.
        """
        cfg = config or {"port": port, "password": password, "driver": driver}
        use_fk = is_fk_driver(driver) or port == 5005
        
        if use_fk:
            res = fk_bridge_client.test_connection(ip, port, cfg)
            if res.get("success"):
                res["driver"] = "fk"
                return res
            if is_fk_driver(driver):
                return res

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
                "driver":        "zk"
            }
            conn.disconnect()
            return info
        except Exception as e:
            if not use_fk:
                cfg_fk = cfg.copy()
                cfg_fk["driver"] = "fk"
                res = fk_bridge_client.test_connection(ip, port, cfg_fk)
                if res.get("success"):
                    res["driver"] = "fk"
                    return res
            return {"success": False, "error": str(e)}

    def add_machine(self, machine: dict) -> dict:
        """Add a new machine to machines.json and register it in the engine."""
        # 1. Save technical config to JSON
        machines_config.save_machine(machine)

        key = machine.get("sn") or f"{machine['ip']}:{machine.get('port', 4370)}"
        self._machines[key] = MachineState(machine)
        self.reconcile_jobs()
        return {"success": True, "machine": machine}

    def remove_machine(self, sn: str = "", ip: str = "", port: int = 4370) -> dict:
        """Remove a machine from machines.json and stop polling it."""
        state = self._find_state(sn, ip, port)
        if state:
            self._disconnect(state)
            key = sn or f"{ip}:{port}"
            self._machines.pop(key, None)
        machines_config.delete_machine(sn=sn, ip=ip, port=port)
        self.reconcile_jobs()
        return {"success": True}

    def get_all_status(self) -> list:
        """Return status of all registered machines (for dashboard and machines page)."""
        return [state.to_dict() for state in self._machines.values()]

    def sync_metadata_from_oracle(self):
        """No-op as COMP_MACHINE table is removed and local config is the source of truth."""
        pass

    def update_machine_metadata(self, sn: str, protocol: str, company: str):
        """Update the in-memory state of a machine after a mapping change."""
        if sn in self._machines:
            state = self._machines[sn]
            state.protocol = protocol
            state.company_names = [company] if company and company != "None" else []
            if protocol == "HTTP":
                state.driver = "zk"
                state.config["driver"] = "zk"
            state.config["protocol"] = protocol
            state.config["company_names"] = state.company_names
            if "company_name" in state.config:
                del state.config["company_name"]
            machines_config.save_machine(state.config)
            logger.info(f"[PullEngine] Updated and persisted metadata for {sn}: Protocol={protocol}, Companies={state.company_names}, Driver={state.driver}")
            self.reconcile_jobs()

    def update_fk_device_metadata(self, sn: str, company: str = None, port: int = None):
        """Upgrade or refresh FK dual-mode device registration."""
        if sn not in self._machines:
            return
        state = self._machines[sn]
        state.driver = "fk"
        state.protocol = "TCP"
        state.config["driver"] = "fk"
        state.config["protocol"] = "TCP"
        if port is not None:
            state.port = port
            state.config["port"] = port
        if company is not None:
            state.company_name = company
            state.config["company_name"] = company
        machines_config.save_machine(state.config)
        logger.info(f"[PullEngine] FK metadata for {sn}: driver=fk protocol=TCP port={state.port}")
        self.reconcile_jobs()

    def update_pulse(self, sn: str):
        """Register a heartbeat pulse for a push device."""
        if sn in self._machines:
            self._machines[sn].last_seen = datetime.now()
            # If it was marked offline (due to old pulse), it will become online in to_dict

    def get_machine(self, sn: str = "", ip: str = "", port: int = 4370) -> dict | None:
        """Query a registered machine's current status and config."""
        state = self._find_state(sn, ip, port)
        return state.to_dict() if state else None

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
