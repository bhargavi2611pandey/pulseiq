import duckdb

con = duckdb.connect("pulseiq.duckdb")
views = ['vw_pl_monthly', 'vw_cash_flow', 'vw_payroll_monthly', 'vw_attrition_monthly']

for view in views:
    try:
        cols = con.execute(f"PRAGMA table_info('metrics.{view}')").df()['name'].tolist()
        print(f"{view} columns: {cols}")
    except Exception as e:
        print(f"Error reading {view}: {e}")

con.close()