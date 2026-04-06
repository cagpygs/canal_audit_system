import psycopg2
import os

DB_CONFIG = {
    "host": "localhost",
    "database": "Irrigation",
    "user": "postgres",
    "password": "123456",
    "port": "5432"
}

def check_columns():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'master_submission'")
    print([r[0] for r in cur.fetchall()])
    cur.close()
    conn.close()

if __name__ == "__main__":
    check_columns()
