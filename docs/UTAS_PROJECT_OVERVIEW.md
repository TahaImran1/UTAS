# 🌐 UTAS — Unified Time Attendance System (Desktop Edition)

## 1. Executive Summary & Purpose
**UTAS** is an enterprise-grade, hybrid desktop application designed to act as an intelligent **middleware and monitoring gateway** between physical biometric time-and-attendance hardware (e.g., ZKTeco, FingerTec clocks) and centralized enterprise databases (e.g., Oracle, PostgreSQL).

Instead of relying on fragmented vendor software, manual USB flash drive transfers, or unreliable legacy drivers, UTAS provides a unified, highly reliable system that automates **live attendance log extraction, device health monitoring, clock synchronization, and database ingestion** across multi-location organizational networks (such as retail stores, branch offices, and factories).

---

## 2. Core Problem Solved (Why This App Exists)
Organizations with distributed branches face major challenges in capturing employee attendance:
* **Firewall & NAT Limitations:** Remote branch devices cannot easily be reached over the internet by a central server without complex router port-forwarding.
* **Protocol & Hardware Diversity:** Different devices use proprietary protocols (legacy ZKTeco TCP, FingerTec DLLs, modern ADMS/HTTP Push).
* **Storage Overflow:** Physical clocks have limited internal flash storage (e.g., 100,000 records) and crash or freeze when full.
* **Data Silos:** Raw attendance logs (`ATTLOG`) must be accurately mapped to specific subsidiary companies/branches and converted into structured SQL rows (`BIODATA`) for payroll and HR systems without data loss.

UTAS solves all of these challenges in a single standalone desktop application.

---

## 3. Key Functional Scope & Features

### 📡 Multi-Protocol Hardware Engine
* **ADMS / HTTP Push Mode (Cloud Receiver):** Acts as an embedded HTTP server (`port 4370`) where physical clocks sitting behind remote branch firewalls automatically push live punch logs, heartbeats, and device diagnostics (`ADMS INFO`, `ATTLOG`) directly to UTAS.
* **Direct TCP Pull Mode (`port 4370` / `5005`):** Connects across LAN or WAN to local/remote devices via direct socket communication to pull attendance logs on demand or on a schedule.
* **FK Bridge (.NET Integration):** Interfaces with proprietary FingerTec devices using a dedicated C# `.NET 8` bridge (`FKAttend.dll`) for specialized hardware drivers.

### 🔄 Automated Synchronization & Scheduler
* **Configurable Auto-Pull Schedules:** Built-in background engine (`APScheduler`) automatically syncs devices at customized intervals (e.g., every 15 minutes, 2 hours, or daily).
* **Automatic Time Sync (`SyncTime`):** Keeps remote device hardware clocks perfectly synchronized with the central server timestamp so employee punch times are always legally accurate.
* **Smart Hardware Cleanup (`AUTO_DELETE`):** Optionally wipes device internal memory only *after* records have been successfully inserted into the enterprise database, preventing memory overflow.

### 🗄️ Enterprise Database & Company Mapping
* **Direct Database Ingestion:** Parses raw ZKTeco tab-delimited strings into clean, structured SQL payloads and inserts them into target database tables (`BIODATA` / generic attendance logs).
* **Multi-Company / Subsidiary Isolation:** Maps specific biometric terminals to designated company entities (e.g., `Sufi Emporium`, `Sufi Packages Mall`, `Shakir Sons`), ensuring proper segregation of attendance records.

### 🖥️ Centralized Monitoring & Management Dashboard
* **Live Health Badges:** Real-time visibility into whether each device is **Online**, **Offline**, or currently **Syncing**.
* **Hardware Diagnostics:** Displays firmware versions, platform models, MAC addresses, enrolled users vs. capacity (`users_cap`), and log capacity (`rec_cap`).
* **Error Tracking & Recovery:** Logs detailed connection failures, TCP timeouts, and socket drops, self-recovering automatically when connections stabilize.
* **Logs Tracker & Database Config:** Allows administrators to view historical sync logs and hot-swap database connection strings (Oracle/PostgreSQL) directly from the UI.

### ⚡ Automatic Updates (`electron-updater`)
* Distributed desktop installations across remote branch PCs automatically check GitHub Releases (`latest.yml`) on startup, downloading and installing new application versions seamlessly in the background.

---

## 4. Technical Architecture (The Hybrid Stack)

UTAS is built using a modern, decoupled hybrid desktop architecture:

```text
┌────────────────────────────────────────────────────────────────────────┐
│                   ELECTRON DESKTOP SHELL (Windows)                     │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                    FRONTEND (React 18 + Vite)                    │  │
│  │    Dashboard • Machines • Logs Tracker • Health • Master Config  │  │
│  └─────────────────────────────────┬────────────────────────────────┘  │
│                                    │ HTTP / IPC                        │
│  ┌─────────────────────────────────▼────────────────────────────────┐  │
│  │               BACKEND ENGINE (Python + FastAPI)                  │  │
│  │   Embedded API (`port 4370`) • PullEngine (`pyzk`) • APScheduler │  │
│  └───────┬─────────────────────────┬─────────────────────────┬──────┘  │
└──────────┼─────────────────────────┼─────────────────────────┼─────────┘
           │ TCP Socket (4370)       │ HTTP Push (/iclock)     │ Subprocess
           ▼                         ▼                         ▼
┌──────────────────────┐  ┌──────────────────────┐  ┌──────────────────────┐
│  ZKTeco TCP Devices  │  │  ADMS / Push Devices │  │  FkBridge (.NET 8)   │
│  (LAN / WAN Router)  │  │  (Remote Branches)   │  │  (FingerTec DLLs)    │
└──────────────────────┘  └──────────────────────┘  └──────────────────────┘
                                                               │
                                                               ▼
                                                    ┌──────────────────────┐
                                                    │  Enterprise Database │
                                                    │ (Oracle / PostgreSQL)│
                                                    └──────────────────────┘
```

1. **Frontend (Presentation Layer):**
   * **React 18 + Vite + Vanilla CSS:** Fast, responsive, dark/light theme user interface.
   * **Recharts & React Hot Toast:** Visual charting for attendance flow and instant feedback notifications.
2. **Desktop Shell (Orchestration Layer):**
   * **Electron + Node.js (`main.js`):** Packages the web UI into a standalone Windows `.exe`, handles system tray background operation, and manages over-the-air auto-updates (`electron-updater`).
3. **Core API & Engine Layer:**
   * **Python + FastAPI (`main.py`, `pull_engine.py`):** Runs an embedded local web server (`0.0.0.0:4370`). It processes both REST calls from the React frontend and incoming HTTP Push packets (`ATTLOG`, `ADMS INFO`) from physical ZKTeco clocks.
   * **APScheduler:** Manages concurrent, thread-safe background jobs for polling and time synchronization without freezing the UI.
4. **Hardware Driver & Database Layer:**
   * **`pyzk` & `cx_Oracle` / `psycopg2`:** Native Python libraries for ZKTeco binary protocol and database connection pools.
   * **`FkBridge` (.NET C#):** Executable bridge interacting with 32/64-bit Windows biometric SDK DLLs (`FKAttend.dll`).

---

## 5. Target Audience & Business Value
* **Primary Users:** HR Administrators, IT Network Officers, and Payroll Managers.
* **Key Business Value:**
  * **Zero Manual Effort:** Eliminates sending technicians to branches with USB flash drives to download attendance.
  * **Network Resilience:** Works flawlessly across complex topologies (HTTP Push for firewalled branch offices; TCP Pull for local LAN devices).
  * **Data Accuracy & Integrity:** Guaranteed synchronization directly into Oracle/PostgreSQL payroll databases with automatic duplicate handling and error reporting.
