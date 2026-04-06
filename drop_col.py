import crud
conn = crud.get_connection()
cur = conn.cursor()
try:
    cur.execute("ALTER TABLE master_submission DROP COLUMN name_of_work;")
    conn.commit()
except Exception as e: pass
finally:
    cur.close()
    crud.release_connection(conn)
