import psycopg2
import os

DB_CONFIG = {
    "host": "localhost",
    "database": "Irrigation",
    "user": "postgres",
    "password": "123456",
    "port": "5432"
}

def migrate():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    try:
        cur.execute("ALTER TABLE master_submission ADD COLUMN IF NOT EXISTS estimate_attachment VARCHAR(255);")
        cur.execute("ALTER TABLE master_submission ADD COLUMN IF NOT EXISTS sar_attachment VARCHAR(255);")
        conn.commit()
        print("Database migration successful: estimate_attachment and sar_attachment columns added.")
    except Exception as e:
        conn.rollback()
        print(f"Migration failed: {e}")
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    migrate()
