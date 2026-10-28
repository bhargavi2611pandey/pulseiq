import duckdb
con = duckdb.connect("pulseiq.duckdb")

tables = [
    "warehouse.fact_headcount_monthly",
    "raw.fact_headcount_monthly", 
    "warehouse.fact_attrition_risk",
    "raw.fact_attrition_risk",
    "raw.fact_employee_exit" # Sometimes exits are stored in a separate table!
]

for t in tables:
    try:
        cols = con.execute(f"PRAGMA table_info('{t}')").df()['name'].tolist()
        print(f"{t}:\n{cols}\n")
    except Exception:
        pass