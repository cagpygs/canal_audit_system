import psycopg2
import os

DB_CONFIG = {
    "host": "localhost",
    "database": "Irrigation",
    "user": "postgres",
    "password": "123456",
    "port": "5432"
}

def check():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    # Check master_submission
    cur.execute("SELECT id, estimate_number, year_of_estimate, name_of_project FROM master_submission WHERE estimate_number='22'")
    recs = cur.fetchall()
    print("Master Records for Estimate '22':")
    for r in recs:
        print(f"ID={r[0]}, Est={r[1]}, Yr={r[2]}, Name='{r[3]}'")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    check()
