# AMF60 / FK dual-mode device setup

Reference: `AMF-60-USER-Manual_compressed.pdf` (AMT / www.amts.pk).

## Communication modes (manual section 5: Set Comm)

On the device: **MENU > SetComm**

| Menu item | Manual | UTAS use |
|-----------|--------|----------|
| **Ethernet → IP Address** | Unique IP on LAN; use in PC software | `machines.json` `ip` |
| **Ethernet → Port NO.** | Default **5005 — do not change** | `port` / `pull_port`: 5005 |
| **Server Set → Server IP / ServerPortNO** | Used in **Internet (cloud)** mode | UTAS server for HTTP push |
| **Server Set → Response Time** | Realtime data from server to machine | Push tuning only |
| **Net Mode → Local** | Local network | **Required** for FkBridge / FKAttend.dll TCP pull |
| **Net Mode → Internet** | Cloud network (`Cloud.amts.pk`) | HTTP push only; no stored-log pull over HTTP |

### TCP/IP hardware option

Manual (wiring section): *TCP/IP is optional at order time — cannot be added on the client side.*

If the unit was sold without TCP/IP, SDK connect and UTAS historical pull will not work. Use HTTP push only or USB export.

## Recommended configurations

### Historical + realtime (dual-mode)

1. **SetComm → Net Mode = Local**
2. **Port NO. = 5005**, IP e.g. `192.168.100.67`
3. On PC: run `scripts\verify_amf60_tcp.ps1` — TCP must be open
4. Vendor SDK demo **Open Comm** (IP, 5005, license `1262`, machine `1`) must succeed
5. Start FkBridge; run `scripts\verify_fk_bridge_pull.ps1`
6. UTAS: `"driver": "fk"`, `"protocol": "TCP"` in `%APPDATA%\UTAS\machines.json`

### Push-only (Internet / no TCP)

1. **SetComm → Net Mode = Internet**
2. **Server IP** = UTAS host; **ServerPortNO** = UTAS HTTP port
3. UTAS still auto-registers on FK push (`realtime_glog`)
4. Scheduled TCP pull will backoff with hint: enable Local/TCP on port 5005

## USB offline export (manual section 8)

**MENU > U-Flash** (insert FAT32 8–16 GB USB) → download **glog**.

Not imported by UTAS v1; use when TCP is unavailable.

## SDK connect parameters (demo defaults)

| Field | Typical value |
|-------|----------------|
| `machine_no` | 1 |
| `license` | 1262 |
| `net_password` | 0 |

Override per device in `machines.json` if admin menu differs.

## Verification scripts

From **Command Prompt** (recommended — `.ps1` may open in Notepad if run as `.\file.ps1`):

```bat
cd E:\Projects\ZK\SUFI_LAST\sourse_code_ZKTECO\scripts
verify_amf60_tcp.bat 192.168.100.67
verify_fk_bridge_pull.bat 192.168.100.67
```

From **PowerShell**:

```powershell
cd E:\Projects\ZK\SUFI_LAST\sourse_code_ZKTECO\scripts
powershell -NoProfile -ExecutionPolicy Bypass -File .\verify_amf60_tcp.ps1 -DeviceIp 192.168.100.67
powershell -NoProfile -ExecutionPolicy Bypass -File .\verify_fk_bridge_pull.ps1 -DeviceIp 192.168.100.67
```

## ZKTeco vs AMF60 HTTP (why old logs differ)

- **ZKTeco HTTP:** device polls `getrequest`; server sends `get_glog`; device uploads stored logs.
- **AMF60 Internet:** device pushes `realtime_glog`; manual does not describe server-initiated HTTP log download.
- **AMF60 historical:** Local mode + TCP 5005 via FkBridge, or USB glog export.
