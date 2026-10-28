import duckdb
import pandas as pd

def build_payroll_metrics():
    con = duckdb.connect("pulseiq.duckdb")
    
    print("="*60)
    print(" FINAL RECONCILIATION: ISOLATING THE 4 BAD ROWS ")
    print("="*60)
    
    # Hunt down the 4 bad test rows identified by the 'PI-X' prefix
    bad_rows_df = con.execute("""
        SELECT 
            payroll_item_id, 
            date_key, 
            employee_id, 
            gross_pay, 
            employer_cost,
            'Manual override/Test row (PI-X prefix) causing duplication or inflated costs' AS exclusion_reason
        FROM raw.fact_payroll
        WHERE payroll_item_id LIKE 'PI-X%'
    """).df()
    
    print(f"Found {len(bad_rows_df)} bad rows! Copy this table for your report:\n")
    print(bad_rows_df.to_string(index=False))

    print("\n" + "="*60)
    print(" BUILDING CLEANED PAYROLL VIEWS ")
    print("="*60)

    # 1. Base view for RECONCILIATION
    con.execute("""
        CREATE OR REPLACE VIEW metrics.vw_payroll_reconciliation AS
        SELECT
            date_key,
            SUM(employer_cost) AS total_employer_cost,
            COUNT(DISTINCT employee_id) AS employees_paid
        FROM raw.fact_payroll
        WHERE payroll_item_id NOT LIKE 'PI-X%' -- Excludes the 4 bad rows
        GROUP BY date_key;
    """)

    # 2. View for the DASHBOARD (Applies the privacy rule to hide small groups)
    con.execute("""
        CREATE OR REPLACE VIEW metrics.vw_payroll_monthly_dashboard AS
        SELECT
            department_id,
            date_key,
            SUM(gross_pay) AS total_gross_pay,
            SUM(net_pay) AS total_net_pay,
            SUM(employer_cost) AS total_employer_cost,
            COUNT(DISTINCT employee_id) AS employees_paid
        FROM raw.fact_payroll
        WHERE payroll_item_id NOT LIKE 'PI-X%' -- Excludes the 4 bad rows
        GROUP BY department_id, date_key
        HAVING COUNT(DISTINCT employee_id) >= 5; -- Privacy Rule
    """)
    print("✅ Metrics views created successfully.")
    
    # Verify against Answer Key
    reconciled_total = con.execute("SELECT SUM(total_employer_cost) FROM metrics.vw_payroll_reconciliation").fetchone()[0]
    print(f"\n💰 RECONCILED TOTAL EMPLOYER COST: ${reconciled_total:,.2f}")
    
    if abs(reconciled_total - 861586392.42) < 0.1:
        print("🎉 PERFECT MATCH! You successfully reconciled with the answer key!")
    else:
        print("⚠️ Still off target. Please share this output so we can adjust.")

    con.close()

if __name__ == "__main__":
    build_payroll_metrics()