import duckdb

def run_etl():
    # Connect to the DuckDB database you just created
    con = duckdb.connect("pulseiq.duckdb")
    
    # Create clean and quarantine schemas
    con.execute("CREATE SCHEMA IF NOT EXISTS clean;")
    con.execute("CREATE SCHEMA IF NOT EXISTS quarantine;")
    
    # Setup summary table (drops first so you can re-run safely)
    con.execute("DROP TABLE IF EXISTS etl_summary;")
    con.execute("""
        CREATE TABLE etl_summary (
            table_name VARCHAR,
            rows_in INTEGER,
            rows_passed INTEGER,
            rows_quarantined INTEGER
        );
    """)

    # The rules based on your Zenith Nova README
    tables = {
        'fact_payroll': "employee_key IS NOT NULL AND date_key IS NOT NULL AND department_id IS NOT NULL",
        'fact_attendance_monthly': "employee_key IS NOT NULL AND date_key IS NOT NULL",
        'fact_task': "team_id IS NOT NULL AND sprint_id IS NOT NULL",
        'fact_ledger': "account_code IS NOT NULL AND date_key IS NOT NULL"
    }

    for table, condition in tables.items():
        # Count raw rows
        raw_count = con.execute(f"SELECT COUNT(*) FROM raw.{table}").fetchone()[0]
        
        # Quarantine bad rows
        con.execute(f"""
            CREATE OR REPLACE TABLE quarantine.{table} AS 
            SELECT *, 'Failed contract rule' AS reason 
            FROM raw.{table} 
            WHERE NOT ({condition});
        """)
        quarantine_count = con.execute(f"SELECT COUNT(*) FROM quarantine.{table}").fetchone()[0]
        
        # Save clean rows
        con.execute(f"""
            CREATE OR REPLACE TABLE clean.{table} AS 
            SELECT * 
            FROM raw.{table} 
            WHERE ({condition});
        """)
        passed_count = con.execute(f"SELECT COUNT(*) FROM clean.{table}").fetchone()[0]
        
        # Log to summary
        con.execute(f"""
            INSERT INTO etl_summary 
            VALUES ('{table}', {raw_count}, {passed_count}, {quarantine_count});
        """)

    # Print your final required report
    print("\n--- ETL SUMMARY REPORT ---")
    print(con.execute("SELECT * FROM etl_summary").df().to_string(index=False))
    
    con.close()

if __name__ == "__main__":
    run_etl()
    