# System Architecture Diagram

This document outlines the high-level architecture of the **UTAS (Unified Time Attendance System)**. The system is designed to handle both **Push (ADMS)** and **Pull (TCP)** protocols for ZKTeco attendance devices, providing a unified interface for data synchronization and device management.

## High-Level Architecture (3-Tier)

![UTAS Architecture Diagram](C:\Users\ALIENWARE\.gemini\antigravity\brain\7a3d203d-e46a-46e5-b77b-bec63c0248b9\utas_architecture_diagram_1777834267124.png)

```mermaid
graph TD
    UI["<b>Application</b><br/>User Interface (React)"]
    Logic["<b>Business & Data Logic</b><br/>FastAPI / UTAS Engines"]
    DB[("<b>Database</b><br/>Oracle / PostgreSQL")]
    Devices["<b>Attendance Devices</b><br/>ZKTeco (Push/Pull)"]

    UI <--> Logic
    Logic <--> DB
    Devices --> Logic

    style UI fill:#87CEEB,stroke:#333,stroke-width:2px
    style Logic fill:#FFA500,stroke:#333,stroke-width:2px
    style DB fill:#FFD700,stroke:#333,stroke-width:2px
    style Devices fill:#D3D3D3,stroke:#333,stroke-width:2px
```


## Detailed System Architecture

```mermaid
graph TB
    subgraph "User Interface Layer"
        UI_D["React Desktop Dashboard"]
    end

    subgraph "Application Layer (FastAPI Backend)"
        API["API Layer (Auth, Management, Config)"]
        PushSrv["ADMS Push Server (/iclock)"]
        PullEng["Pull Engine (APScheduler)"]
        DBC["Database Connector (Oracle / PostgreSQL)"]
    end

    subgraph "Storage Layer"
        LocalJSON["Local Config (JSON Files)"]
        RemoteDB[("External DB (Oracle / PostgreSQL)")]
    end

    subgraph "Device Layer"
        PushDev["Push Devices (ADMS/HTTP)"]
        PullDev["Pull Devices (TCP/Port 4370)"]
    end

    %% Interactions
    UI_D <-->|"REST API (HTTP/JWT)"| API
    
    %% Device Interactions
    PushDev -->|"Push Attendance (HTTP)"| PushSrv
    PushSrv -->|"Queue Commands"| PushDev
    PullEng -->|"Poll Records (TCP)"| PullDev
    
    %% Backend Internal
    API <--> PullEng
    API <--> PushSrv
    API <--> DBC
    PushSrv --> DBC
    PullEng --> DBC
    
    %% Storage Interactions
    DBC <--> LocalJSON
    DBC <--> RemoteDB
    
    %% Style
    style UI_D fill:#f9f,stroke:#333,stroke-width:2px
    style RemoteDB fill:#bbf,stroke:#333,stroke-width:2px
    style API fill:#dfd,stroke:#333,stroke-width:2px
    style PushSrv fill:#dfd,stroke:#333,stroke-width:2px
    style PullEng fill:#dfd,stroke:#333,stroke-width:2px
```


## Component Descriptions

### 1. User Interface Layer
*   **React Dashboard**: A modern, high-contrast UI built with React. It provides real-time health monitoring, device management, attendance log viewing, and a multi-step database configuration wizard.

### 2. Application Layer (FastAPI)
*   **API Layer**: Handles administrative tasks, user authentication (JWT), and configuration management.
*   **ADMS Push Server**: Implements the ZKTeco Push protocol. Devices connect to these endpoints (`/iclock/cdata`) to upload logs and receive commands.
*   **Pull Engine**: A background service using `APScheduler` and `pyzk`. It periodically connects to legacy or remote devices via TCP to "pull" attendance logs.
*   **Database Connector**: A generic abstraction layer that supports both Oracle and PostgreSQL. It handles connection pooling, table auto-mapping, and data insertion.

### 3. Storage Layer
*   **Local Config**: JSON files (`database.json`, `machines.json`, `users.json`) store local system state and device lists for quick access and recovery.
*   **External Database**: The primary persistent store for attendance logs and enterprise-level machine metadata (e.g., company mappings).

### 4. Device Layer
*   **Push Devices**: Modern ZKTeco machines configured with ADMS/Cloud Server settings. They initiate communication via HTTP.
*   **Pull Devices**: Legacy or standalone machines that listen on port 4370. The server initiates communication via TCP.

## Data Flow
1.  **Attendance Ingestion**: Logs are received via Push (HTTP POST) or Pull (TCP fetch).
2.  **Processing**: The backend parses raw data, validates company assignment, and formats records.
3.  **Persistence**: Records are inserted into the configured `HR_EMP_INOUT_DETAIL` (or equivalent) table in the active database.
4.  **Monitoring**: The frontend polls the API for live status updates, health metrics, and recent logs.
