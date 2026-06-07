# FkBridge — FK / AMT dual-mode TCP pull service

HTTP bridge around **FKAttend.dll** for UTAS. Use for devices that push via FK headers (`request_code`, `dev_id`) and pull over TCP (default port **5005**).

## AMF60 / manual alignment

Official manual: `AMF-60-USER-Manual_compressed.pdf` (repo root). Device setup: [docs/AMF60_DEVICE_SETUP.md](../docs/AMF60_DEVICE_SETUP.md).

| Device (`MENU > SetComm`) | UTAS |
|---------------------------|------|
| Port NO. **5005** (do not change) | `port` / `pull_port` |
| Net Mode **Local** | FkBridge TCP pull |
| Net Mode **Internet** | HTTP push only; TCP pull backs off |
| Server IP / ServerPort (Internet) | UTAS host for `/iclock/cdata` |

**Order-time option:** TCP/IP may not be present on all units; SDK connect fails if hardware lacks TCP.

## Prerequisites

1. .NET 8 SDK, publish **win-x86**
2. Copy **FKAttend.dll** + **FKModelDic.ini** into publish folder (script below)
3. Device in **Local** mode for pull; **Internet** for push-only

## Build and deploy DLL

```powershell
cd fk-bridge\FkBridge
dotnet publish -c Release -r win-x86 --self-contained false
cd ..
.\copy-fk-dll.ps1
# Optional: .\copy-fk-dll.ps1 -VendorDllDir "E:\Projects\DFace_C#_202006\dll"
```

`copy-fk-dll.ps1` copies `FKAttend.dll`, `FKModelDic.ini`, and common runtime dependencies into `FkBridge\bin\Release\net8.0\win-x86\publish\`.

## Run

```bat
cd fk-bridge\FkBridge\bin\Release\net8.0\win-x86\publish
FkBridge.exe
```

Listens on `http://127.0.0.1:5001` (`appsettings.json`).

## HTTP API

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | `dll_loaded` |
| `/connect` | POST | `FK_ConnectNet` |
| `/pull` | POST | General log pull → JSON |
| `/clear` | POST | Empty device logs |
| `/info` | GET | Product / time info |
| `/sync_time` | POST | Set device clock |

POST body: `{ "ip", "port", "machineNo", "license", "timeoutMs", "netPassword" }`

## Verify

```powershell
cd ..\..\scripts
.\verify_amf60_tcp.ps1 -DeviceIp 192.168.100.67
.\verify_fk_bridge_pull.ps1 -DeviceIp 192.168.100.67
```

## UTAS integration

- `.env`: `FK_BRIDGE_URL=http://127.0.0.1:5001`
- `machines.json`: `"driver": "fk"`, `"protocol": "TCP"`, `"port": 5005`
- Optional: `license`, `machine_no`, `net_password`, `pull_port`
- Start: `scripts\start_utas_with_fk_bridge.bat` (copies DLL if publish exists, then FkBridge + UTAS)

Implementation status: [docs/FK_IMPLEMENTATION_STATUS.md](../docs/FK_IMPLEMENTATION_STATUS.md)
