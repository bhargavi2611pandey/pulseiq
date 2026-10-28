import duckdb

con = duckdb.connect("pulseiq.duckdb")
print("Columns in raw.fact_payroll:")
print(con.execute("PRAGMA table_info('raw.fact_payroll')").df()['name'].tolist())

print("\nColumns in raw.dim_department:")
print(con.execute("PRAGMA table_info('raw.dim_department')").df()['name'].tolist())