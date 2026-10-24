import duckdb
import pandas as pd

def build_metric_layer():
    print("Building Governed Metric Layer...\n")
    con = duckdb.connect("pulseiq.duckdb")
    
    # 1. Create the schema and the Metric Catalog View
    con.execute("CREATE SCHEMA IF NOT EXISTS metrics;")
    
    # The Catalog lists every metric from the dictionary
    con.execute("""
        CREATE OR REPLACE VIEW metrics.metric_catalog AS 
        SELECT * FROM raw.metric_dictionary;
    """)
    print("✅ metrics.metric_catalog view created successfully.")

    # 2. Build 5 Core Metric Views (Applying the minimum group size privacy rule)
    
    # View 1: Headcount by Department
    con.execute("""
        CREATE OR REPLACE VIEW metrics.vw_headcount AS
        SELECT department_id, date_key, COUNT(DISTINCT employee_key) as headcount
        FROM warehouse.fact_payroll
        GROUP BY department_id, date_key
        HAVING COUNT(DISTINCT employee_key) >= 5;
    """)
    
    # View 2: Total Payroll Cost
    con.execute("""
        CREATE OR REPLACE VIEW metrics.vw_payroll_cost AS
        SELECT department_id, date_key, SUM(net_pay) as total_payroll
        FROM warehouse.fact_payroll
        GROUP BY department_id, date_key
        HAVING COUNT(DISTINCT employee_key) >= 5;
    """)
    
    # View 3: Total Unpaid Leave (LOP) Days
    con.execute("""
        CREATE OR REPLACE VIEW metrics.vw_unpaid_leave AS
        SELECT department_id, date_key, SUM(lop_days) as total_lop_days
        FROM warehouse.fact_payroll
        GROUP BY department_id, date_key
        HAVING COUNT(DISTINCT employee_key) >= 5;
    """)
    
    # View 4: Total Task Completions
    con.execute("""
        CREATE OR REPLACE VIEW metrics.vw_tasks_completed AS
        SELECT team_id, sprint_id, COUNT(task_id) as tasks_done
        FROM warehouse.fact_task
        WHERE status = 'Done'
        GROUP BY team_id, sprint_id
        HAVING COUNT(DISTINCT assignee_employee_id) >= 5;
    """)
    
    # View 5: Invoice Revenue
    con.execute("""
        CREATE OR REPLACE VIEW metrics.vw_invoice_revenue AS
        SELECT client_id, invoice_date_key, SUM(total_amount) as revenue
        FROM raw.fact_invoice
        GROUP BY client_id, invoice_date_key;
    """)
    print("✅ 5 Core Metric Views created with privacy rules applied.\n")

    # 3. Fetch Evidence for the Report
    print("="*60)
    print(" METRIC CATALOG SUMMARY (EVIDENCE) ")
    print("="*60)
    
    # FIX: Grab the first few columns safely without guessing exact names
    catalog = con.execute("SELECT * FROM metrics.metric_catalog LIMIT 5").df()
    print(catalog.iloc[:, :3].to_string(index=False)) 
    
    print("\n" + "="*60)
    print(" HAND-CHECK CALCULATOR DATA (EVIDENCE) ")
    print("="*60)
    
    print("1. Total Headcount (First Row):")
    print(con.execute("SELECT * FROM metrics.vw_headcount LIMIT 1").df().to_string(index=False))
    
    print("\n2. Total Payroll Cost (First Row):")
    print(con.execute("SELECT * FROM metrics.vw_payroll_cost LIMIT 1").df().to_string(index=False))
    
    print("\n3. Total Tasks Completed (First Row):")
    print(con.execute("SELECT * FROM metrics.vw_tasks_completed LIMIT 1").df().to_string(index=False))
    
    con.close()
    print("\nMetric Layer build complete!")

if __name__ == "__main__":
    build_metric_layer()