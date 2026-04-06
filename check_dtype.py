import crud, pandas as pd
conn = crud.get_connection()
df = pd.read_sql("SELECT table_name, data_type FROM information_schema.columns WHERE column_name='year_of_estimate';", conn)
df.to_csv("dtype_out.csv", index=False)
crud.release_connection(conn)
