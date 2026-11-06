import duckdb

print("="*50)
print(" CHECKING AI TABLE COLUMNS ")
print("="*50)

con = duckdb.connect("pulseiq.duckdb")
tables = ['raw.fact_anomaly', 'raw.fact_forecast', 'raw.fact_attrition_risk']

for table in tables:
    try:
        print(f"{table} columns:")
        print(con.execute(f"PRAGMA table_info('{table}')").df()['name'].tolist())
        print()
    except Exception as e:
        print(f"Error reading {table}: {e}")

con.close()