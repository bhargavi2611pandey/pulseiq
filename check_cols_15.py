import duckdb

con = duckdb.connect("pulseiq.duckdb")

print("="*50)
print(" CHECKING KPI TARGETS ")
print("="*50)
try:
    print("Columns:")
    print(con.execute("PRAGMA table_info('raw.kpi_targets')").df()['name'].tolist())
    print("\nData:")
    print(con.execute("SELECT * FROM raw.kpi_targets").df().to_string(index=False))
except Exception as e:
    print(f"Error reading kpi_targets: {e}")

print("\n" + "="*50)
print(" LISTING AVAILABLE METRIC VIEWS ")
print("="*50)
try:
    print(con.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'metrics'").df()['table_name'].tolist())
except Exception as e:
    print(f"Error reading metrics schema: {e}")

con.close()