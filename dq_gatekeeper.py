import duckdb
import pandas as pd
from datetime import datetime

def run_gatekeeper():
    print("Starting Data Quality Gatekeeper...\n")
    con = duckdb.connect("pulseiq.duckdb")
    
    # 1. Create the Results Table
    con.execute("DROP TABLE IF EXISTS dq_results;")
    con.execute("""
        CREATE TABLE dq_results (
            check_id VARCHAR,
            check_name VARCHAR,
            severity VARCHAR,
            bad_rows INTEGER,
            status VARCHAR,
            run_time TIMESTAMP,
            error_message VARCHAR
        );
    """)
    
    # 2. Define the Checks (SQL that returns BAD rows)
    # We use raw or warehouse depending on where the table currently sits
    checks = [
        {"id": "DQ-C03", "name": "Unique payroll rows", "severity": "Critical",
         "sql": "SELECT employee_key, date_key FROM warehouse.fact_payroll GROUP BY 1,2 HAVING COUNT(*) > 1"},
         
        {"id": "DQ-C04", "name": "No orphan employees", "severity": "Critical",
         "sql": "SELECT f.employee_key FROM warehouse.fact_payroll f LEFT JOIN warehouse.dim_employee d ON f.employee_key = d.employee_key WHERE d.employee_key IS NULL"},
         
        {"id": "DQ-C07", "name": "Invoice arithmetic", "severity": "Warning",
         "sql": "SELECT invoice_id FROM raw.fact_invoice WHERE amount_paid > total_amount OR balance_due < 0"},
         
        {"id": "DQ-C08", "name": "Expense arithmetic", "severity": "Warning",
         "sql": "SELECT expense_id FROM raw.fact_expense WHERE ABS(total_amount - (amount_excl_gst + gst_amount)) > 0.01"},
         
        {"id": "DQ-C09", "name": "Task dates sensible", "severity": "Warning",
         "sql": "SELECT task_id FROM warehouse.fact_task WHERE completed_date < started_date OR (status = 'Done' AND completed_date IS NULL)"},
         
        {"id": "DQ-C10", "name": "Leave dates sensible", "severity": "Warning",
         "sql": "SELECT leave_request_id FROM raw.fact_leave WHERE end_date < start_date"},
         
        {"id": "DQ-C12", "name": "Dim history does not overlap", "severity": "Critical",
         "sql": "SELECT a.employee_key FROM warehouse.dim_employee a JOIN warehouse.dim_employee b ON a.employee_id = b.employee_id AND a.employee_key < b.employee_key AND a.valid_to >= b.valid_from"}
    ]
    
    # 3. Execute Checks
    for check in checks:
        bad_rows = 0
        status = "PASS"
        error_msg = "None"
        
        try:
            # Run the query and count the bad rows returned
            result = con.execute(check['sql']).fetchall()
            bad_rows = len(result)
            
            if bad_rows > 0:
                status = "FAIL"
                
        except Exception as e:
            # If a column name is wrong, don't crash. Just log the error.
            status = "ERROR"
            error_msg = str(e).split('\n')[0][:50] + "..." # Keep error short
            
        # Log to results table
        con.execute(f"""
            INSERT INTO dq_results 
            VALUES ('{check['id']}', '{check['name']}', '{check['severity']}', {bad_rows}, '{status}', CURRENT_TIMESTAMP, '{error_msg}')
        """)
        
    # 4. Print Manager-Friendly Report
    print("="*80)
    print(f" DATA QUALITY GATEKEEPER REPORT - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("="*80)
    
    report = con.execute("SELECT check_id, check_name, severity, status, bad_rows, error_message FROM dq_results").df()
    print(report.to_string(index=False))
    print("="*80)
    
    # Check if any Critical tests failed
    critical_fails = con.execute("SELECT COUNT(*) FROM dq_results WHERE severity = 'Critical' AND status = 'FAIL'").fetchone()[0]
    if critical_fails > 0:
        print("\n🚨 ALERT: Critical checks failed! Pipeline load should be stopped.")
    else:
        print("\n✅ All critical checks passed. Pipeline safe to proceed.")
        
    con.close()

if __name__ == "__main__":
    run_gatekeeper()