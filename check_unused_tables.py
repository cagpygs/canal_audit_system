import psycopg2
import os

DB_CONFIG = {
    "host": "localhost",
    "database": "Irrigation",
    "user": "postgres",
    "password": "123456",
    "port": "5432"
}

def check_unused_tables():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    # Get all tables
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_type = 'BASE TABLE'
    """)
    db_tables = [r[0] for r in cur.fetchall()]
    
    # Known system tables used in code
    system_tables = ['users', 'master_submission']
    
    # Module prefixes used in code
    module_prefixes = ['contract_management', 'canal_performance']
    
    in_use = []
    not_in_use = []
    
    for table in db_tables:
        if table in system_tables:
            in_use.append(table)
            continue
        
        match = False
        for prefix in module_prefixes:
            if table.startswith(prefix + "_"):
                match = True
                break
        
        if match:
            in_use.append(table)
        else:
            if table not in ('spatial_ref_sys'): # Exclude PostGIS system table if exists
                not_in_use.append(table)
                
    print(f"Total tables in database: {len(db_tables)}")
    print(f"Tables in use by app: {len(in_use)}")
    print(f"Tables NOT in use by app: {len(not_in_use)}")
    print("\nNOT IN USE:")
    for t in sorted(not_in_use):
        print(f" - {t}")
        
    cur.close()
    conn.close()

if __name__ == "__main__":
    check_unused_tables()
