# FK / AMT dual-mode — implementation status

Last aligned with plan: **FK AMF60 Manual Alignment**.

## Software (complete)

| Component | Path | Status |
|-----------|------|--------|
| FkBridge service | `fk-bridge/FkBridge/` | Done — connect, pull, clear, info, sync_time, health |
| DLL deploy script | `fk-bridge/copy-fk-dll.ps1` | Done |
| Python bridge client | `backend/app/fk_bridge_client.py` | Done |
| Pull engine `driver=fk` | `backend/app/pull_engine.py` | Done — no pyzk on FK devices |
| FK push autodetect | `backend/app/main.py` | Done — `register_push_device(..., fk_protocol=True)` |
| Manual pull branch | `backend/app/main.py` | Done — bridge for `driver=fk` |
| Bridge health API | `GET /pull/fk-bridge/health` | Done |
| Starter script | `scripts/start_utas_with_fk_bridge.bat` | Done |
| TCP verify script | `scripts/verify_amf60_tcp.ps1` | Done |
| Bridge pull verify | `scripts/verify_fk_bridge_pull.ps1` | Done |
| Device setup doc | `docs/AMF60_DEVICE_SETUP.md` | Done |
| Architecture notes | `docs/ARCHITECTURE.md` | Done |

## Operations (site-dependent)

| Step | Status | Action |
|------|--------|--------|
| AMF60 Net Mode = Local | Pending on device | `MENU > SetComm` per manual |
| TCP port 5005 open | Run `verify_amf60_tcp.ps1` | Fails until device Local + TCP option |
| SDK demo Open Comm | User/vendor | Same IP/port/license as UTAS |
| FkBridge `/connect` + `/pull` | Run `verify_fk_bridge_pull.ps1` | After TCP open |
| UTAS ingest for `AMT602511730` | After bridge pull OK | Manual pull or scheduler |

## Push-only fallback

If TCP cannot be enabled: keep **Internet** mode + UTAS Server IP; realtime push continues; scheduled TCP pull logs backoff with `FK_TCP_HINT` in pull engine.

## USB fallback

`MENU > U-Flash` → download glog — not automated in UTAS v1.
