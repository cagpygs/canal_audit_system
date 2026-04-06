import crud
conn = crud.get_connection()
cur = conn.cursor()
cur.execute("SELECT table_name FROM information_schema.tables WHERE table_name LIKE 'contract_management_%' AND table_schema='public';")
tables = [r[0] for r in cur.fetchall()]
print("\n".join(tables))
crud.release_connection(conn)
