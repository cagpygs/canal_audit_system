import crud
conn = crud.get_connection()
cur = conn.cursor()
try:
    cur.execute("ALTER TABLE master_submission ALTER COLUMN year_of_estimate TYPE TEXT;")
    # Convert existing 'YYYY-MM-DD' dates to financial year 'YYYY-YY'
    cur.execute("""
        UPDATE master_submission 
        SET year_of_estimate = SUBSTRING(year_of_estimate FROM 1 FOR 4) || '-' || SUBSTRING((CAST(SUBSTRING(year_of_estimate FROM 1 FOR 4) AS INTEGER) + 1)::text FROM 3 FOR 2)
        WHERE year_of_estimate ~ '^\d{4}-\d{2}-\d{2}$';
    """)
    conn.commit()
    print("Migrated year_of_estimate to TEXT")
except Exception as e:
    print(f"Error: {e}")
finally:
    cur.close()
    crud.release_connection(conn)
