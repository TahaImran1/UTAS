import logging
import oracledb
import os
import json
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

CONFIG_FILE = os.path.join(os.path.dirname(__file__),"database.json")
LOG_FILE    = os.path.join(os.path.dirname(__file__),"errors.log")

logging.basicConfig(
    filename = LOG_FILE,
    level    = logging.ERROR,
    format   = '%(asctime)s:%(levelname)s:%(message)s'
)

def load_latest_config(selected_db_type):
    # Instead of reading database.json, we now read from environment variables
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
    
    # Keep PostgreSQL logic intact (falling back to database.json if needed)
    if not os.path.exists(CONFIG_FILE):
        error_msg = f"Configuration file {CONFIG_FILE} does not exist."
        logging.error(error_msg)
        raise FileNotFoundError(error_msg)
    
    with open(CONFIG_FILE, 'r') as config_file:
        configs = json.load(config_file)
    
    latest_config = None
    for config in configs:
        if config["database"] == selected_db_type:
            latest_config = config
    
    if not latest_config:
        error_msg = f"No configuration found for database type: {selected_db_type}"
        logging.error(error_msg)
        raise ValueError(error_msg)
    



oracle_pool = None

def get_oracle_pool(config):
    global oracle_pool
    if oracle_pool is None:
        try:
            dsn_tns = oracledb.makedsn(config['host'], config['port'], service_name=config['dbname'])
            oracle_pool = oracledb.create_pool(
                user=config['username'], 
                password=config['password'], 
                dsn=dsn_tns,
                min=2,
                max=50,          # Allow up to 50 concurrent DB connections
                increment=2      # Grow by 2 connections at a time if busy
            )
            logging.info("Oracle Connection Pool created successfully.")
        except Exception as error:
            error_msg = f"Error creating Oracle pool: {error}"
            logging.error(error_msg)
            raise Exception(error_msg)
    return oracle_pool

def connect_db_oracle(config):
    pool = get_oracle_pool(config)
    try:
        connection = pool.acquire()
        return connection
    except Exception as error:
        error_msg = f"Error acquiring connection from Oracle pool: {error}"
        logging.error(error_msg)
        raise Exception(error_msg)

def insert_log_oracle(connection, attendance_records, machine_info, config):
    rows_inserted=0
    try:
        cursor = connection.cursor()
        for attendance in attendance_records:
            user_id = attendance.user_id
            timestamp = attendance.timestamp
            
        table = config['table']
        col_pk = config['col_pk']
        seq_pk = config['seq_pk']
        column1 = config['column1']
        column2 = config['column2']
        column3 = config['column3']
        
        query = f"""
        INSERT INTO {table} ({col_pk}, {column1}, {column2}, {column3})
        SELECT {seq_pk}.NEXTVAL, :emp_no, TO_DATE(:swp_time, 'YYYY-MM-DD HH24:MI:SS'), :mach_ref
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
        batch_data = []
        for attendance in attendance_records:
            batch_data.append((attendance.user_id, attendance.timestamp, machine_info))
        
        print(f"Executing bulk insert for {len(batch_data)} records from Device {machine_info}...")
        
        # Execute all records in a single batch (massive performance improvement)
        cursor.executemany(query, batch_data)
        connection.commit()
        rows_inserted = cursor.rowcount
            
        cursor.close()
    except Exception as error:
        error_msg = f"Error inserting log data: {error}"
        logging.error(error_msg)
        raise Exception(error_msg)
    print('Data Downloaded')
    print(f"Number of entries inserted: {rows_inserted}")
