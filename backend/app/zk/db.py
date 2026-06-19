import logging
import oracledb
import os
import json
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def get_app_data_dir():
    app_data = os.getenv('APPDATA')
    if not app_data:
        app_data = os.path.expanduser("~")
    dir_path = os.path.join(app_data, "UTAS")
    os.makedirs(dir_path, exist_ok=True)
    return dir_path

APP_DATA_DIR = get_app_data_dir()
CONFIG_FILE = os.path.join(APP_DATA_DIR, "database.json")
LOG_FILE    = os.path.join(APP_DATA_DIR, "errors.log")

logging.basicConfig(
    filename = LOG_FILE,
    level    = logging.ERROR,
    format   = '%(asctime)s:%(levelname)s:%(message)s'
)

ACTIVE_DB_FILE = os.path.join(APP_DATA_DIR, "active_db.txt")

def get_active_db_type():
    """Returns the currently active database type (Oracle or PostgreSQL)."""
    if os.path.exists(ACTIVE_DB_FILE):
        try:
            with open(ACTIVE_DB_FILE, "r") as f:
                db_type = f.read().strip()
                if db_type in ["Oracle", "PostgreSQL"]:
                    return db_type
        except Exception as e:
            logging.error(f"Error reading active_db.txt: {e}")
    return os.getenv("ACTIVE_DB_TYPE", "Oracle")

def set_active_db_type(db_type):
    """Sets the active database type persistently."""
    if db_type not in ["Oracle", "PostgreSQL"]:
        raise ValueError(f"Invalid database type: {db_type}")
    try:
        with open(ACTIVE_DB_FILE, "w") as f:
            f.write(db_type)
        os.environ["ACTIVE_DB_TYPE"] = db_type
        return True
    except Exception as e:
        logging.error(f"Error writing active_db.txt: {e}")
        return False

# ─── New: Wizard helpers ─────────────────────────────────────────────────────

def connect_one_shot(config):
    """
    Create a single, non-pooled connection from raw credentials.
    Used during the initial wizard check — no pool caching side effects.
    """
    db_type = config.get("database", "Oracle")
    if db_type == "Oracle":
        dsn = oracledb.makedsn(config["host"], config["port"], service_name=config["dbname"])
        conn = oracledb.connect(user=config["username"], password=config["password"], dsn=dsn)
        return conn
    elif db_type == "PostgreSQL":
        import psycopg2
        conn = psycopg2.connect(
            host=config["host"], port=config["port"],
            user=config["username"], password=config["password"],
            dbname=config["dbname"]
        )
        return conn
    raise ValueError(f"Unsupported db type: {db_type}")


def check_tables_exist(connection, db_type, att_table, machine_table):
    """
    Returns a dict { att_table_exists: bool, machine_table_exists: bool }.
    Does NOT create anything — pure read.
    """
    result = {"att_table_exists": False, "machine_table_exists": False}
    try:
        cursor = connection.cursor()
        if db_type == "Oracle":
            cursor.execute(
                "SELECT count(*) FROM user_tables WHERE table_name = :tn",
                {"tn": att_table.upper()}
            )
            result["att_table_exists"] = cursor.fetchone()[0] > 0

            cursor.execute(
                "SELECT count(*) FROM user_tables WHERE table_name = :tn",
                {"tn": machine_table.upper()}
            )
            result["machine_table_exists"] = cursor.fetchone()[0] > 0
        elif db_type == "PostgreSQL":
            cursor.execute(
                "SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name=%s",
                (att_table.lower(),)
            )
            result["att_table_exists"] = cursor.fetchone() is not None

            cursor.execute(
                "SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name=%s",
                (machine_table.lower(),)
            )
            result["machine_table_exists"] = cursor.fetchone() is not None
        cursor.close()
    except Exception as e:
        logging.error(f"check_tables_exist error: {e}")
    return result


def get_table_columns(connection, db_type, table_name):
    """Fetch column names for a given table from DB metadata."""
    columns = []
    try:
        cursor = connection.cursor()
        if db_type == "Oracle":
            cursor.execute(
                "SELECT column_name FROM user_tab_columns WHERE table_name = :tn ORDER BY column_id",
                {"tn": table_name.upper()}
            )
        else:
            cursor.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_name = %s ORDER BY ordinal_position",
                (table_name.lower(),)
            )
        columns = [row[0] for row in cursor.fetchall()]
        cursor.close()
    except Exception as e:
        logging.error(f"Error fetching columns for {table_name}: {e}")
    return columns


def create_attendance_table(connection, db_type, config):
    """
    Create the attendance log table using the column names in config.
    config keys: table, col_pk, seq_pk, column1, column2, column3
    """
    table   = config["table"].upper() if db_type == "Oracle" else config["table"].lower()
    col_pk  = config.get("col_pk")
    seq_pk  = config.get("seq_pk")
    col1    = config["column1"]
    col2    = config["column2"]
    col3    = config["column3"]
    col4    = config.get("column4", "")
    cursor  = connection.cursor()
    try:
        if db_type == "Oracle":
            # Check if table exists
            cursor.execute("SELECT count(*) FROM user_tables WHERE table_name = :tn", {"tn": table})
            table_exists = cursor.fetchone()[0] > 0
            
            if not table_exists:
                extra_col = f", {col4} VARCHAR2(100)" if col4 else ""
                if col_pk:
                    cursor.execute(f"""
                        CREATE TABLE {table} (
                            {col_pk} NUMBER PRIMARY KEY,
                            {col1} VARCHAR2(50),
                            {col2} TIMESTAMP,
                            {col3} VARCHAR2(200){extra_col}
                        )
                    """)
                else:
                    cursor.execute(f"""
                        CREATE TABLE {table} (
                            id NUMBER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                            {col1} VARCHAR2(50),
                            {col2} TIMESTAMP,
                            {col3} VARCHAR2(200){extra_col}
                        )
                    """)
                logging.info(f"Oracle table {table} created.")
            else:
                logging.info(f"Oracle table {table} already exists. Skipping creation.")
                
            if seq_pk:
                # Check if sequence exists
                cursor.execute("SELECT count(*) FROM user_sequences WHERE sequence_name = :sn", {"sn": seq_pk.upper()})
                seq_exists = cursor.fetchone()[0] > 0
                if not seq_exists:
                    cursor.execute(f"CREATE SEQUENCE {seq_pk} START WITH 1 INCREMENT BY 1")
                    logging.info(f"Oracle sequence {seq_pk} created.")
                else:
                    logging.info(f"Oracle sequence {seq_pk} already exists. Skipping creation.")
                
        elif db_type == "PostgreSQL":
            # Check if table exists
            cursor.execute(
                "SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name=%s",
                (table,)
            )
            table_exists = cursor.fetchone() is not None
            
            if not table_exists:
                extra_col = f", {col4} VARCHAR(100)" if col4 else ""
                cursor.execute(f"""
                    CREATE TABLE {table} (
                        id SERIAL PRIMARY KEY,
                        {col1} VARCHAR(50),
                        {col2} TIMESTAMP,
                        {col3} VARCHAR(200){extra_col},
                        UNIQUE({col1}, {col2}, {col3})
                    )
                """)
                logging.info(f"PostgreSQL table {table} created.")
            else:
                logging.info(f"PostgreSQL table {table} already exists. Skipping creation.")
        connection.commit()
        cursor.close()
        return True
    except Exception as e:
        logging.error(f"create_attendance_table error: {e}")
        cursor.close()
        raise


def create_machine_table(connection, db_type, table_name, col_sn, col_ip, col_proto, col_company):
    """
    Create the machine-link table with user-supplied column names.
    """
    tbl    = table_name.upper() if db_type == "Oracle" else table_name.lower()
    cursor = connection.cursor()
    try:
        if db_type == "Oracle":
            cursor.execute(f"""
                CREATE TABLE {tbl} (
                    {col_sn} VARCHAR2(100) PRIMARY KEY,
                    {col_ip} VARCHAR2(50),
                    {col_proto} VARCHAR2(20),
                    {col_company} VARCHAR2(200)
                )
            """)
        elif db_type == "PostgreSQL":
            cursor.execute(f"""
                CREATE TABLE {tbl} (
                    {col_sn} VARCHAR(100) PRIMARY KEY,
                    {col_ip} VARCHAR(50),
                    {col_proto} VARCHAR(20),
                    {col_company} VARCHAR(200)
                )
            """)
        connection.commit()
        cursor.close()
        return True
    except Exception as e:
        logging.error(f"create_machine_table error: {e}")
        cursor.close()
        raise

def ensure_tables(connection, db_type, config):
    """Verifies that required tables exist, and creates them if they don't."""
    try:
        cursor = connection.cursor()
        
        # 1. Ensure Attendance Logs Table
        table_name = config.get("table", "HR_EMP_INOUT_DETAIL")
        col1 = config.get("column1", "EMPLOYEE_NO")
        col2 = config.get("column2", "SWAP_TIME")
        col3 = config.get("column3", "MACHINE_REF")
        
        if db_type == "Oracle":
            # Check if table exists
            cursor.execute("SELECT count(*) FROM user_tables WHERE table_name = :tn", {"tn": table_name.upper()})
            if cursor.fetchone()[0] == 0:
                logging.info(f"Creating Oracle table: {table_name}")
                col_pk = config.get('col_pk')
                if col_pk:
                    cursor.execute(f"""
                        CREATE TABLE {table_name} (
                            {col_pk} NUMBER PRIMARY KEY,
                            {col1} VARCHAR2(50),
                            {col2} TIMESTAMP,
                            {col3} VARCHAR2(200)
                        )
                    """)
                else:
                    cursor.execute(f"""
                        CREATE TABLE {table_name} (
                            id NUMBER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                            {col1} VARCHAR2(50),
                            {col2} TIMESTAMP,
                            {col3} VARCHAR2(200)
                        )
                    """)
            
            # Check if sequence exists independently (only if legacy config specifies it)
            seq_name = config.get('seq_pk')
            if seq_name:
                cursor.execute("SELECT count(*) FROM user_sequences WHERE sequence_name = :sn", {"sn": seq_name.upper()})
                if cursor.fetchone()[0] == 0:
                    logging.info(f"Creating Oracle sequence: {seq_name}")
                    cursor.execute(f"CREATE SEQUENCE {seq_name} START WITH 1 INCREMENT BY 1")
        
        elif db_type == "PostgreSQL":
            # Check Attendance Logs Table
            cursor.execute(f"SELECT 1 FROM information_schema.tables WHERE table_name = '{table_name.lower()}'")
            if not cursor.fetchone():
                logging.info(f"Creating PostgreSQL table: {table_name}")
                cursor.execute(f"""
                    CREATE TABLE {table_name} (
                        id SERIAL PRIMARY KEY,
                        {col1} VARCHAR(50),
                        {col2} TIMESTAMP,
                        {col3} VARCHAR(200),
                        UNIQUE({col1}, {col2}, {col3})
                    )
                """)

        connection.commit()
        cursor.close()
    except Exception as e:
        logging.error(f"Error ensuring tables: {e}")
        # Non-fatal error, but log it

def load_latest_config(selected_db_type):
    # Try reading from database.json first
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as config_file:
            try:
                configs = json.load(config_file)
                for config in configs:
                    if config.get("database") == selected_db_type:
                        return config
            except Exception as e:
                logging.error(f"Error parsing database.json: {e}")

    # Fallback to environment variables for Oracle if not in JSON
    if selected_db_type == "Oracle":
        config = {
            "database": "Oracle",
            "host": os.getenv("ORACLE_HOST", "localhost"),
            "port": os.getenv("ORACLE_PORT", "1521"),
            "username": os.getenv("ORACLE_USER", "HR"),
            "password": os.getenv("ORACLE_PASSWORD", ""),
            "dbname": os.getenv("ORACLE_SERVICE_NAME", "orcl"),
            "table": os.getenv("ORACLE_TABLE", "hr_emp_inout_detail").strip().upper(),
            "col_pk": os.getenv("ORACLE_COL_PK", "hr_att_log_id").strip().upper(),
            "seq_pk": os.getenv("ORACLE_SEQ_PK", "hr_emp_inout_id_s").strip().upper(),
            "column1": os.getenv("ORACLE_COL_EMP", "employee_no").strip().upper(),
            "column2": os.getenv("ORACLE_COL_TIME", "swap_time").strip().upper(),
            "column3": os.getenv("ORACLE_COL_MACHINE", "machine_ref").strip().upper()
        }
        return config
    
    error_msg = f"No configuration found for database type: {selected_db_type}"
    logging.error(error_msg)
    raise ValueError(error_msg)
    



oracle_pools = {}

def get_oracle_pool(config):
    global oracle_pools
    key = f"{config['host']}:{config['port']}:{config['dbname']}:{config['username']}"
    if key not in oracle_pools:
        try:
            dsn_tns = oracledb.makedsn(config['host'], config['port'], service_name=config['dbname'])
            pool = oracledb.create_pool(
                user=config['username'], 
                password=config['password'], 
                dsn=dsn_tns,
                min=2,
                max=50,          # Allow up to 50 concurrent DB connections
                increment=2      # Grow by 2 connections at a time if busy
            )
            oracle_pools[key] = pool
            logging.info(f"Oracle Connection Pool created successfully for {key}.")
        except Exception as error:
            error_msg = f"Error creating Oracle pool for {key}: {error}"
            logging.error(error_msg)
            raise Exception(error_msg)
    return oracle_pools[key]

def connect_db_oracle(config):
    pool = get_oracle_pool(config)
    try:
        connection = pool.acquire()
        ensure_tables(connection, "Oracle", config)
        return connection
    except Exception as error:
        error_msg = f"Error acquiring connection from Oracle pool: {error}"
        logging.error(error_msg)
        raise Exception(error_msg)

def connect_db_postgresql(config):
    import psycopg2
    try:
        conn = psycopg2.connect(
            host=config['host'],
            port=config['port'],
            user=config['username'],
            password=config['password'],
            dbname=config['dbname']
        )
        ensure_tables(conn, "PostgreSQL", config)
        return conn
    except Exception as error:
        logging.error(f"PostgreSQL connection error: {error}")
        raise Exception(f"PostgreSQL connection error: {error}")

def insert_log_generic(records, machine_ref, company_names: list[str]):
    """Insert logs into the databases of all assigned companies."""
    if not company_names:
        raise ValueError(f"No companies assigned to machine {machine_ref}")
        
    mappings = load_company_mappings()
    profiles = load_db_profiles()
    
    errors = []
    success_count = 0
    
    for company_name in company_names:
        if company_name in ["None", "", None]:
            continue
            
        profile_name = mappings.get(company_name)
        if not profile_name or profile_name == "None":
            print(f"Company '{company_name}' has no database profile assigned. Skipping log insertion for this company.")
            continue
            
        config = profiles.get(profile_name)
        if not config:
            print(f"Database profile '{profile_name}' for company '{company_name}' not found. Skipping log insertion.")
            continue
            
        db_type = config.get("database", "Oracle")
        try:
            if db_type == "Oracle":
                conn = connect_db_oracle(config)
                try:
                    insert_log_oracle(conn, records, machine_ref, config)
                finally:
                    conn.close()
            elif db_type == "PostgreSQL":
                conn = connect_db_postgresql(config)
                try:
                    insert_log_postgresql(conn, records, machine_ref, config)
                finally:
                    conn.close()
            success_count += 1
        except Exception as e:
            err_msg = f"Database write failed for company '{company_name}' (Profile: '{profile_name}'): {e}"
            logging.error(err_msg)
            errors.append(err_msg)
            
    if errors:
        raise RuntimeError(f"Insertion failed or incomplete: {'; '.join(errors)}")
        
    return True

def insert_log_postgresql(connection, attendance_records, machine_info, config):
    """Inserts logs into PostgreSQL."""
    try:
        cursor = connection.cursor()
        table = config['table']
        col1 = config['column1']
        col2 = config['column2']
        col3 = config['column3']
        
        query = f"INSERT INTO {table} ({col1}, {col2}, {col3}) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING"
        
        batch_data = []
        for att in attendance_records:
            batch_data.append((str(att.user_id), att.timestamp, str(machine_info)))
            
        cursor.executemany(query, batch_data)
        connection.commit()
        cursor.close()
    except Exception as e:
        logging.error(f"PostgreSQL insert error: {e}")
        raise

def insert_log_oracle(connection, attendance_records, machine_info, config):
    """
    Inserts logs with Data Isolation based on the Machine Serial Number.
    Uses INSERT...SELECT...WHERE NOT EXISTS to prevent duplicates.
    """
    rows_inserted = 0
    try:
        cursor = connection.cursor()

        table   = config['table']
        col_pk  = config.get('col_pk') or config.get('column_pk')
        seq_pk  = config.get('seq_pk')

        # Fallback defaults for standard Oracle setup if not explicitly configured
        if not col_pk and table.upper() == "HR_EMP_INOUT_DETAIL":
            col_pk = "HR_ATT_LOG_ID"
        if not seq_pk and table.upper() == "HR_EMP_INOUT_DETAIL":
            seq_pk = "HR_EMP_INOUT_ID_S"
        column1 = config['column1']
        column2 = config['column2']
        column3 = config['column3']

        # Optional column4 — only add if explicitly present in config (not as a default fallback)
        col_client = config.get('column4')  # returns None if not set — avoids inserting into CLIENT_ID by mistake
        client_val = config.get('client_id_val', '0')

        # Build query dynamically based on available columns
        columns      = [column1, column2, column3]
        placeholders = [":emp_no", "TO_DATE(:swp_time, 'YYYY-MM-DD HH24:MI:SS')", ":mach_ref"]

        if col_pk and seq_pk:
            columns.insert(0, col_pk)
            placeholders.insert(0, f"{seq_pk}.NEXTVAL")

        # Add CLIENT_ID column only when explicitly configured
        if col_client:
            columns.append(col_client)
            placeholders.append(":client_id")

        query = f"""
        INSERT INTO {table} ({', '.join(columns)})
        SELECT {', '.join(placeholders)}
        FROM dual
        WHERE NOT EXISTS (
            SELECT 1
            FROM {table}
            WHERE {column1} = :emp_no
            AND   {column2} = TO_DATE(:swp_time, 'YYYY-MM-DD HH24:MI:SS')
            AND   {column3} = :mach_ref
        )
        """

        # Prepare data for bulk insert
        import datetime
        batch_data = []
        for attendance in attendance_records:
            ts = attendance.timestamp
            if isinstance(ts, datetime.datetime):
                ts_str = ts.strftime('%Y-%m-%d %H:%M:%S')
            else:
                ts_str = str(ts)

            row = {
                "emp_no":   str(attendance.user_id),
                "swp_time": ts_str,
                "mach_ref": str(machine_info)
            }
            if col_client:
                row["client_id"] = client_val

            batch_data.append(row)

        print(f"Executing bulk insert for {len(batch_data)} records from Device {machine_info}...")

        # Get row count before insert to calculate actual inserted rows
        count_cursor = connection.cursor()
        count_cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count_before = count_cursor.fetchone()[0]
        count_cursor.close()

        # Execute all records in a single batch
        cursor.executemany(query, batch_data)
        connection.commit()

        # Calculate actual rows inserted by comparing table count
        count_cursor2 = connection.cursor()
        count_cursor2.execute(f"SELECT COUNT(*) FROM {table}")
        count_after = count_cursor2.fetchone()[0]
        count_cursor2.close()

        rows_inserted = count_after - count_before
        skipped = len(batch_data) - rows_inserted
        cursor.close()

    except Exception as error:
        error_msg = f"Error inserting log data: {error}"
        logging.error(error_msg)
        raise Exception(error_msg)

    print('Data Inserted Successfully')
    print(f"Number of entries inserted: {rows_inserted} (skipped as duplicates: {skipped})")
    if skipped > 0:
        logging.warning(f"[DB] {skipped} record(s) from {machine_info} were skipped — already exist in {table}. "
                        f"Check if the device is resending old attendance that was previously stored.")


# ─── Configuration Files Mappings (named profiles, no SQL tables) ───────────

PROFILES_FILE = os.path.join(APP_DATA_DIR, "databases.json")
COMPANY_DB_FILE = os.path.join(APP_DATA_DIR, "company_databases.json")

def load_db_profiles() -> dict:
    """Load and return all named database profiles."""
    if not os.path.exists(PROFILES_FILE):
        return {}
    try:
        with open(PROFILES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Error loading databases.json: {e}")
        return {}

def save_db_profile(name: str, config: dict) -> bool:
    """Save or update a named database profile."""
    try:
        profiles = load_db_profiles()
        profiles[name] = config
        with open(PROFILES_FILE, 'w', encoding='utf-8') as f:
            json.dump(profiles, f, indent=4)
        return True
    except Exception as e:
        logging.error(f"Error saving database profile {name}: {e}")
        return False

def delete_db_profile(name: str) -> bool:
    """Delete a database profile by name."""
    try:
        profiles = load_db_profiles()
        if name in profiles:
            del profiles[name]
            with open(PROFILES_FILE, 'w', encoding='utf-8') as f:
                json.dump(profiles, f, indent=4)
            # Reset connection pools to clear any active pool associated
            reset_pools()
            return True
        return False
    except Exception as e:
        logging.error(f"Error deleting database profile {name}: {e}")
        return False

def load_company_mappings() -> dict:
    """Load mappings from company_name to profile_name."""
    if not os.path.exists(COMPANY_DB_FILE):
        return {}
    try:
        with open(COMPANY_DB_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Error loading company_databases.json: {e}")
        return {}

def save_company_mapping(company_name: str, profile_name: str) -> bool:
    """Associate a company with a named database profile."""
    try:
        mappings = load_company_mappings()
        mappings[company_name] = profile_name
        with open(COMPANY_DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(mappings, f, indent=4)
        return True
    except Exception as e:
        logging.error(f"Error saving company mapping for {company_name}: {e}")
        return False

def delete_company_mapping(company_name: str) -> bool:
    """Remove mapping for a company."""
    try:
        mappings = load_company_mappings()
        if company_name in mappings:
            del mappings[company_name]
            with open(COMPANY_DB_FILE, 'w', encoding='utf-8') as f:
                json.dump(mappings, f, indent=4)
            return True
        return False
    except Exception as e:
        logging.error(f"Error deleting company mapping for {company_name}: {e}")
        return False

def save_config(config: dict) -> bool:
    """Compatibility function for legacy wizard endpoints."""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4)
        return True
    except Exception as e:
        logging.error(f"Error in compatibility save_config: {e}")
        return False

def reset_pools():
    """Close and clear existing database connection pools."""
    global oracle_pools
    for key, pool in list(oracle_pools.items()):
        try:
            pool.close()
        except:
            pass
    oracle_pools.clear()
    logging.info("All database pools have been reset.")
