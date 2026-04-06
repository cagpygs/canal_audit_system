import psycopg2
import json

def check_db():
    try:
        conn = psycopg2.connect(
            host='localhost',
            database='Irrigation',
            user='postgres',
            password='123456',
            port='5432'
        )
        cur = conn.cursor()
        
        # Check all records for estimate '22'
        cur.execute("""
            SELECT id, user_id, module, status, estimate_number, year_of_estimate, name_of_project 
            FROM master_submission 
            WHERE estimate_number='22'
        """)
        rows = cur.fetchall()
        print(f"Found {len(rows)} records for estimate '22':")
        for row in rows:
            print(row)
            
        # Check all users
        cur.execute("SELECT id, username FROM users")
        users = cur.fetchall()
        print("\nUsers:")
        for user in users:
            print(user)
            
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_db()
