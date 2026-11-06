import duckdb

con = duckdb.connect("pulseiq.duckdb")

print("--- AI FORECAST MONTHS ---")
print(con.execute("SELECT DISTINCT CAST(forecast_month_key AS VARCHAR) FROM raw.fact_forecast ORDER BY 1").df().to_string(index=False))

print("\n--- ACTUAL PAYROLL MONTHS (Last 3) ---")
print(con.execute("SELECT DISTINCT SUBSTRING(CAST(date_key AS VARCHAR), 1, 6) AS month FROM raw.fact_payroll ORDER BY 1 DESC LIMIT 3").df().to_string(index=False))

con.close()