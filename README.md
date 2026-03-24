# UTAS (ZKTeco ADMS Server)

## Description
This is a standalone server for ZKTeco Time Attendance devices supporting the **Push SDK (ADMS)**. It receives attendance logs from the device via HTTP and saves them directly to an **Oracle** database in real-time.

> [!IMPORTANT]
> This server requires a ZKTeco attendance machine that supports the **Push Protocol (ADMS/Cloud Server)**. Standard "Pull" based devices are not compatible with this approach.

## Team Members
- Taha Imran (Roll No. 24L-2560)
- Umer Khan (Roll No. 24L-2583)
- Rai Fahd Sultan (Roll No. 24L-2509)
## Tech Stack
- **Backend**: FastAPI (Python)
- **Database**: Oracle

## How to Configure & Run

### 1. Backend Setup
Navigate to the `backend/` directory and install dependencies:
```bash
cd backend
pip install -r requirements.txt
```
*(Alternatively, simply run the `run_server.bat` file which handles this automatically).*

### 2. Configure Database (.env)
Create a `.env` file inside the `backend/` directory. You can use `.env.example` as a template.

```env
# Oracle Database Configuration
ORACLE_HOST=your_host
ORACLE_PORT=1521
ORACLE_USER=your_user
ORACLE_PASSWORD=your_password
ORACLE_SERVICE_NAME=orcl

# Oracle Table Configuration
ORACLE_TABLE=hr_emp_inout_detail
ORACLE_COL_PK=hr_att_log_id
ORACLE_SEQ_PK=hr_emp_inout_id_s
ORACLE_COL_EMP=employee_no
ORACLE_COL_TIME=swap_time
ORACLE_COL_MACHINE=ip_address
```

### 3. Run the Server
From the `backend/` directory, run:
```bash
run_server.bat
```
*Or manually via Python:*
```bash
python app/main.py
```
The server will start on port **4370**. Note the IP address displayed in the console.

> [!CAUTION]
> **Firewall Configuration**: You MUST allow inbound traffic on TCP port **4370** in your Windows Firewall or any other antivirus/security software. If this port is blocked, the machine will not be able to connect to your server.

### 4. Configure ZKTeco Machine (ADMS)
Follow these steps on your physical attendance device to connect it to this server:

1.  **Open Menu**: Press **Menu** or **M/OK**.
2.  **Network Settings**: Navigate to **Comm.** -> **Ethernet** and ensure the device has a valid IP address on your local network.
3.  **Cloud Server/ADMS Settings**: Go to **Comm.** -> **Cloud Server Setting** (or **ADMS** on some models).
4.  **Server Address**: Enter the **IP Address** of the computer running this backend (e.g., `192.168.100.31`).
5.  **Server Port**: Enter `4370`.
6.  **Enable Domain Name**: Set to **OFF**.
7.  **HTTPS**: Set to **OFF**.
8.  **Sync Data**: Ensure the device shows a "Connected" icon (usually a cloud symbol with a green check or arrows).

### 5. View Logs
Open your browser to see live records being received from the device:
👉 **http://localhost:4370/view**

## Project Structure
```text
/
├── backend/            # FastAPI Backend
│   ├── app/            # Application logic
│   │   ├── main.py     # Entry point (Auto-installs dependencies)
│   │   └── zk/         # ZK SDK & Database logic
│   ├── .env.example    # Environment variables template
│   ├── requirements.txt
│   └── run_server.bat  # Easy launcher
├── database/           # Database scripts and schemas
│   ├── schema.sql      # Oracle DDL statements
│   └── erd.png         # ERD image
├── docs/               # Project documentation
│   └── report.md       # (Placeholder)
└── README.md
```
