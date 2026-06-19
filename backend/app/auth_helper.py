"""
auth_helper.py
-------------
Helper for Master Password storage (hashing via bcrypt), complexity checks,
and in-memory session token registry.
"""
import os
import json
import bcrypt
import secrets
import re
import logging

logger = logging.getLogger("utas.auth")

# In-memory session store (token -> bool)
ACTIVE_SESSIONS = set()

def get_app_data_dir() -> str:
    app_data = os.getenv('APPDATA')
    if not app_data:
        app_data = os.path.expanduser("~")
    dir_path = os.path.join(app_data, "UTAS")
    os.makedirs(dir_path, exist_ok=True)
    return dir_path

def get_auth_file_path() -> str:
    return os.path.join(get_app_data_dir(), "auth.json")

def is_auth_initialized() -> bool:
    """Returns True if the Master Password has been configured."""
    filepath = get_auth_file_path()
    if not os.path.exists(filepath):
        return False
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return bool(data.get("password_hash"))
    except Exception as e:
        logger.error(f"[Auth] Error reading auth.json: {e}")
        return False

def get_registry_flag() -> bool:
    if os.name != 'nt':
        return False
    import winreg
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\UTAS")
        val, _ = winreg.QueryValueEx(key, "Initialized")
        winreg.CloseKey(key)
        return val == 1
    except FileNotFoundError:
        return False
    except Exception as e:
        logger.error(f"[Auth] Registry read error: {e}")
        return False

def set_registry_flag(initialized: bool = True) -> bool:
    if os.name != 'nt':
        return False
    import winreg
    try:
        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\UTAS")
        val = 1 if initialized else 0
        winreg.SetValueEx(key, "Initialized", 0, winreg.REG_DWORD, val)
        winreg.CloseKey(key)
        return True
    except Exception as e:
        logger.error(f"[Auth] Registry write error: {e}")
        return False

def clear_registry_flag() -> bool:
    if os.name != 'nt':
        return False
    import winreg
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software", 0, winreg.KEY_ALL_ACCESS)
        winreg.DeleteKey(key, "UTAS")
        winreg.CloseKey(key)
        return True
    except FileNotFoundError:
        return True
    except Exception as e:
        logger.error(f"[Auth] Registry delete error: {e}")
        return False

def get_hidden_file_path() -> str:
    home = os.path.expanduser("~")
    return os.path.join(home, ".utas_sec")

def get_hidden_file_flag() -> bool:
    fpath = get_hidden_file_path()
    if not os.path.exists(fpath):
        return False
    try:
        with open(fpath, "r", encoding="utf-8") as f:
            data = json.load(f)
            return bool(data.get("initialized"))
    except Exception:
        return False

def set_hidden_file_flag(initialized: bool = True) -> bool:
    fpath = get_hidden_file_path()
    try:
        if initialized:
            with open(fpath, "w", encoding="utf-8") as f:
                json.dump({"initialized": True}, f)
        else:
            if os.path.exists(fpath):
                os.remove(fpath)
        return True
    except Exception as e:
        logger.error(f"[Auth] Hidden file write error: {e}")
        return False

def is_app_configured() -> bool:
    """Returns True if any user configurations or installation flags exist."""
    # 1. Check Registry Flag
    if get_registry_flag():
        return True

    # 2. Check Hidden File Flag
    if get_hidden_file_flag():
        return True

    # 3. Check AppData Config Files
    app_data_dir = get_app_data_dir()
    
    # Check machines.json
    machines_path = os.path.join(app_data_dir, "machines.json")
    if os.path.exists(machines_path):
        try:
            with open(machines_path, "r", encoding="utf-8") as f:
                machines = json.load(f)
                if isinstance(machines, list) and len(machines) > 0:
                    return True
                if isinstance(machines, dict) and len(machines) > 0:
                    return True
        except Exception:
            pass

    # Check databases.json, database.json (legacy), company_databases.json
    for fname in ["databases.json", "database.json", "company_databases.json"]:
        fpath = os.path.join(app_data_dir, fname)
        if os.path.exists(fpath):
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict) and len(data) > 0:
                        return True
                    if isinstance(data, list) and len(data) > 0:
                        return True
            except Exception:
                pass

    return False


def validate_password_strength(password: str) -> bool:
    """Enforces secure password strength:
    - Minimum 8 characters
    - At least 1 uppercase letter
    - At least 1 lowercase letter
    - At least 1 number
    - At least 1 special character
    """
    if len(password) < 8:
        return False
    if not re.search(r"[A-Z]", password):
        return False
    if not re.search(r"[a-z]", password):
        return False
    if not re.search(r"\d", password):
        return False
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return False
    return True

def initialize_master_password(password: str) -> bool:
    """Saves the Master Password bcrypt hash if not already initialized."""
    if is_auth_initialized():
        logger.warning("[Auth] Master password already initialized. Use change_master_password instead.")
        return False

    if is_app_configured():
        raise ValueError("Security lockout: Existing configuration detected. Re-initialization of the master password is disabled.")

    if not validate_password_strength(password):
        raise ValueError("Password does not meet complexity requirements.")

    try:
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        
        filepath = get_auth_file_path()
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump({"password_hash": hashed.decode('utf-8')}, f, indent=4)
        
        # Write registry and hidden file status flags
        set_registry_flag(True)
        set_hidden_file_flag(True)

        logger.info("[Auth] Master password successfully initialized.")
        return True
    except Exception as e:
        logger.error(f"[Auth] Failed to initialize password: {e}")
        return False

def administrative_reset() -> bool:
    """Wipes password hash and resets registry and hidden file status flags."""
    try:
        # 1. Delete auth.json
        filepath = get_auth_file_path()
        if os.path.exists(filepath):
            os.remove(filepath)
            
        # 2. Clear registry
        clear_registry_flag()
        
        # 3. Clear hidden file
        set_hidden_file_flag(False)
        
        logger.info("[Auth] Administrative password reset completed successfully.")
        return True
    except Exception as e:
        logger.error(f"[Auth] Failed administrative reset: {e}")
        return False

def verify_master_password(password: str) -> bool:
    """Verifies plain password against stored Master Password bcrypt hash."""
    filepath = get_auth_file_path()
    if not os.path.exists(filepath):
        return False
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        hashed_password = data.get("password_hash", "")
        if not hashed_password:
            return False
        return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception as e:
        logger.error(f"[Auth] Error verifying password: {e}")
        return False

def change_master_password(old_password: str, new_password: str) -> bool:
    """Verifies old password and updates the Master Password to the new value."""
    if not verify_master_password(old_password):
        raise ValueError("Incorrect current password.")

    if not validate_password_strength(new_password):
        raise ValueError("New password does not meet complexity requirements.")

    try:
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(new_password.encode('utf-8'), salt)
        
        filepath = get_auth_file_path()
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump({"password_hash": hashed.decode('utf-8')}, f, indent=4)
            
        logger.info("[Auth] Master password changed successfully.")
        return True
    except Exception as e:
        logger.error(f"[Auth] Failed to change password: {e}")
        return False

# ── Session Token helpers ──────────────────────────────────────────────────
def create_session() -> str:
    """Generates and registers an active session token."""
    token = secrets.token_hex(32)
    ACTIVE_SESSIONS.add(token)
    return token

def validate_session(token: str) -> bool:
    """Validates if a session token is active."""
    return token in ACTIVE_SESSIONS

def destroy_session(token: str) -> bool:
    """Destroys an active session token."""
    if token in ACTIVE_SESSIONS:
        ACTIVE_SESSIONS.remove(token)
        return True
    return False
