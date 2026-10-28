import duckdb

def build_attrition_metrics():
    con = duckdb.connect("pulseiq.duckdb")
    print("Building Attrition Metric Views...")
    
    # 1. Historical Exits View (Aggregated with privacy rule)
    con.execute("""
        CREATE OR REPLACE VIEW metrics.vw_attrition_monthly AS
        SELECT
            department_id,
            date_key,
            SUM(headcount_start) AS starting_headcount,
            SUM(exits) AS total_exits,
            SUM(voluntary_exits) AS voluntary_exits,
            SUM(exits) - SUM(voluntary_exits) AS other_exits
        FROM raw.fact_headcount_monthly
        GROUP BY department_id, date_key
        HAVING SUM(headcount_start) >= 5;
    """)
    print("✅ metrics.vw_attrition_monthly created.")

    # 2. Predicted Risk View (Grouped by department/band to protect identities)
    con.execute("""
        CREATE OR REPLACE VIEW metrics.vw_attrition_risk AS
        SELECT
            department_id,
            as_of_date_key,
            risk_band,
            COUNT(DISTINCT employee_id) AS employees_at_risk
        FROM raw.fact_attrition_risk
        GROUP BY department_id, as_of_date_key, risk_band
        HAVING COUNT(DISTINCT employee_id) >= 5;
    """)
    print("✅ metrics.vw_attrition_risk created.")
    
    con.close()

if __name__ == "__main__":
    build_attrition_metrics()