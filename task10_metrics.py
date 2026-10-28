import duckdb
import pandas as pd

def build_budget_metrics():
    con = duckdb.connect("pulseiq.duckdb")
    
    print("="*60)
    print(" BUILDING BUDGET & KPI VIEWS ")
    print("="*60)

    # 1. Budget Variance View
    # Sign Rule: Variance = Budget - Actual. Positive = Under budget (Good). Negative = Overspend (Bad).
    con.execute("""
        CREATE OR REPLACE VIEW metrics.vw_budget_variance AS
        SELECT 
            p.department_id,
            d.department_name,
            p.date_key,
            b.month AS budget_month,
            p.total_employer_cost AS actual_cost,
            b.budget_payroll_cost AS budget_cost,
            
            -- Variance Calculations
            (b.budget_payroll_cost - p.total_employer_cost) AS variance_amount,
            ROUND(((b.budget_payroll_cost - p.total_employer_cost) / b.budget_payroll_cost) * 100, 2) AS variance_pct,
            
            -- Traffic Light Logic
            CASE 
                WHEN (b.budget_payroll_cost - p.total_employer_cost) >= 0 THEN '🟢 Under Budget'
                WHEN (((b.budget_payroll_cost - p.total_employer_cost) / b.budget_payroll_cost) * 100) >= -5 THEN '🟡 Minor Overspend'
                ELSE '🔴 High Overspend'
            END AS budget_status
            
        FROM metrics.vw_payroll_monthly_dashboard p
        LEFT JOIN raw.dim_department d ON p.department_id = d.department_id
        -- Match dates by Year and Month safely
        LEFT JOIN raw.budget_payroll_dept_month b 
            ON p.department_id = b.department_id 
            AND CAST(SUBSTRING(CAST(p.date_key AS VARCHAR), 1, 6) AS INTEGER) = CAST(SUBSTRING(REPLACE(CAST(b.month AS VARCHAR), '-', ''), 1, 6) AS INTEGER)
    """)
    print("✅ metrics.vw_budget_variance created successfully.")

    # 2. KPI Targets View (Prepared for dashboard)
    con.execute("""
        CREATE OR REPLACE VIEW metrics.vw_kpi_targets AS
        SELECT 
            k.*,
            d.department_name
        FROM raw.kpi_targets k
        LEFT JOIN raw.dim_department d ON k.department_id = d.department_id
    """)
    print("✅ metrics.vw_kpi_targets created successfully.")

    # 3. Hand Verification for the Report
    print("\n" + "="*60)
    print(" HAND VERIFICATION TABLE (COPY THIS FOR YOUR REPORT) ")
    print("="*60)
    verify_df = con.execute("""
        SELECT 
            department_name, 
            date_key, 
            ROUND(budget_cost, 2) AS budget, 
            ROUND(actual_cost, 2) AS actual, 
            ROUND(variance_amount, 2) AS variance, 
            variance_pct,
            budget_status
        FROM metrics.vw_budget_variance
        WHERE budget_cost IS NOT NULL
        LIMIT 3
    """).df()
    print(verify_df.to_string(index=False))

    con.close()

if __name__ == "__main__":
    build_budget_metrics()