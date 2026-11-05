import duckdb

con = duckdb.connect("pulseiq.duckdb")

tables = ['raw.fact_ledger', 'raw.dim_account', 'raw.fact_expense', 'raw.dim_vendor']

for table in tables:
    try:
        print(f"{table} columns:")
        print(con.execute(f"PRAGMA table_info('{table}')").df()['name'].tolist())
        print()
    except Exception as e:
        print(f"Error reading {table}: {e}")