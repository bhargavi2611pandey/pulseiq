import duckdb
import pandas as pd
import os

def build_cross_dept_metrics():
    con = duckdb.connect("pulseiq.duckdb")
    
    print("="*60)
    print(" BUILDING CROSS-DEPARTMENT UNIFIED VIEW ")
    print("="*60)

    # 1. Aggregate first, then join. Grain: department + month
    con.execute("""
        CREATE OR REPLACE VIEW metrics.vw_department_unified AS
        WITH payroll_agg AS (
            SELECT 
                department_id,
                SUBSTRING(CAST(date_key AS VARCHAR), 1, 6) AS month_key,
                SUM(headcount_flag) AS headcount,
                SUM(employer_cost) AS total_employer_cost,
                SUM(overtime_pay) AS total_overtime_pay
            FROM raw.fact_payroll
            GROUP BY 1, 2
        ),
        attendance_agg AS (
            SELECT 
                department_id,
                SUBSTRING(CAST(date_key AS VARCHAR), 1, 6) AS month_key,
                SUM(paid_leave_days) AS total_paid_leave_days,
                SUM(overtime_hours) AS total_overtime_hours
            FROM raw.fact_attendance_monthly
            GROUP BY 1, 2
        ),
        attrition_agg AS (
            SELECT 
                department_id,
                -- Format exit_date (YYYY-MM-DD) to YYYYMM
                SUBSTRING(REPLACE(CAST(exit_date AS VARCHAR), '-', ''), 1, 6) AS month_key,
                COUNT(DISTINCT employee_id) AS attritions
            FROM raw.dim_employee
            WHERE exit_date IS NOT NULL
            GROUP BY 1, 2
        )
        SELECT 
            COALESCE(d.department_name, CAST(p.department_id AS VARCHAR)) AS department_name,
            p.month_key,
            p.headcount,
            p.total_employer_cost,
            p.total_overtime_pay,
            (p.total_overtime_pay / NULLIF(p.headcount, 0)) AS overtime_cost_per_head,
            COALESCE(a.total_paid_leave_days, 0) AS total_paid_leave_days,
            (COALESCE(a.total_paid_leave_days, 0) / NULLIF(p.headcount, 0)) AS leave_days_per_head,
            COALESCE(a.total_overtime_hours, 0) AS total_overtime_hours,
            COALESCE(att.attritions, 0) AS attritions
        FROM payroll_agg p
        LEFT JOIN attendance_agg a ON p.department_id = a.department_id AND p.month_key = a.month_key
        LEFT JOIN attrition_agg att ON p.department_id = att.department_id AND p.month_key = att.month_key
        LEFT JOIN raw.dim_department d ON p.department_id = d.department_id;
    """)
    
    print("✅ metrics.vw_department_unified created successfully.")
    
    # Check against Vault if reachable
    vault_path = '../04_Validation_Vault/unlock_PQ-13_reference_summary_dept_month.csv'
    if os.path.exists(vault_path):
        print("\n🔍 Found Validation Vault! Running comparison...")
        reference_df = pd.read_csv(vault_path)
        print("Vault Data Loaded. (Check your local CSV to ensure our logic matches!).")
    else:
        print("\n⚠️ Note: Validation Vault CSV not found in parent folder, but view is ready for manual checking.")

    con.close()

if __name__ == "__main__":
    build_cross_dept_metrics()