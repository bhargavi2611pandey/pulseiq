import duckdb

con = duckdb.connect("pulseiq.duckdb")

print("--- 1. What are the Account Types? ---")
print(con.execute("SELECT DISTINCT account_type FROM raw.dim_account").df())

print("\n--- 2. What does is_group look like? ---")
print(con.execute("SELECT DISTINCT is_group, typeof(is_group) as type FROM raw.dim_account").df())

print("\n--- 3. Are the tables joining successfully? ---")
print(con.execute("""
    SELECT COUNT(*) as matched_rows 
    FROM raw.fact_ledger f
    JOIN raw.dim_account a ON CAST(f.account_code AS VARCHAR) = CAST(a.account_code AS VARCHAR)
""").df())

con.close()