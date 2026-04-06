import crud
import pandas as pd
conn = crud.get_connection()
df = pd.read_sql("SELECT table_name, column_name FROM information_schema.columns WHERE table_schema='public';", conn)
df[df['column_name'].str.contains('name_of_work|project|name_of_project', case=False)].to_csv("db_cols.csv", index=False)
crud.release_connection(conn)
