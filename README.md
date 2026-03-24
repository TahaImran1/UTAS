# ZK ADMS Server

This is a standalone server for ZK Time Attendance devices supporting the **Push SDK (ADMS)**.
It receives attendance logs from the device via HTTP and saves them directly to an **Oracle** database.

## Setup Instructions

### 1. Install Dependencies
Make sure you have Python installed. Then run:
```bash
pip install -r requirements.txt
```

### 2. Configure Database (.env)
Create a `.env` file in the root directory to configure your Oracle database credentials and the target table schema. 

Example `.env` structure:
```env
# Oracle Database Configuration
ORACLE_HOST=192.168.1.50
ORACLE_PORT=1521
ORACLE_USER=HR
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
```bash
python adms_server.py
```
The server will start on port **4370**.

### 4. Configure ZK Device
On your ZK Device, go to **Menu -> Comm. -> Cloud Server / ADMS**:
- **Server Address**: IP of this computer (e.g., `192.168.1.100`)
- **Server Port**: `4370`
- **Enable Domain Name**: `OFF`
- **HTTPS**: `OFF`

### 5. View Logs
Open your browser and go to:
`http://localhost:4370/view`
