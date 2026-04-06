import crud
import os

try:
    conn = crud.get_connection()
    cur = conn.cursor()
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'master_submission'")
    cols = [r[0] for r in cur.fetchall()]
    print("COLUMNS:" + ",".join(cols))
    crud.release_connection(conn)
except Exception as e:
    print(f"ERROR: {e}")
