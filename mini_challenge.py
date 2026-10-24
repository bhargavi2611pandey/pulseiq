import duckdb

def run_mini_challenge():
    con = duckdb.connect("pulseiq.duckdb")
    
    # Create the new metric view
    con.execute("""
        CREATE OR REPLACE VIEW metrics.vw_avg_net_pay AS
        SELECT department_id, date_key, AVG(net_pay) as avg_net_pay
        FROM warehouse.fact_payroll
        GROUP BY department_id, date_key
        HAVING COUNT(DISTINCT employee_key) >= 5;
    """)
    print("✅ New view 'metrics.vw_avg_net_pay' created!")
    
    # Print one row to hand-check
    print("\n--- HAND CHECK DATA ---")
    print(con.execute("SELECT * FROM metrics.vw_avg_net_pay LIMIT 1").df().to_string(index=False))
    
    con.close()

if __name__ == "__main__":
    run_mini_challenge()