import duckdb

con = duckdb.connect("pulseiq.duckdb")

tables = ['raw.fact_invoice', 'raw.fact_invoice_payment', 'raw.dim_client']

for table in tables:
    try:
        print(f"{table} columns:")
        print(con.execute(f"PRAGMA table_info('{table}')").df()['name'].tolist())
        print()
    except Exception as e:
        print(f"Error reading {table}: {e}")