import duckdb

def build_warehouse():
    print("Building Star Schema Warehouse...\n")
    con = duckdb.connect("pulseiq.duckdb")
    
    # Create the warehouse schema
    con.execute("CREATE SCHEMA IF NOT EXISTS warehouse;")
    
    # 1. Move Dimensions (from raw to warehouse)
    dimensions = ['dim_employee', 'dim_department', 'dim_date', 'dim_role', 'dim_team', 'dim_sprint']
    for dim in dimensions:
        con.execute(f"CREATE OR REPLACE TABLE warehouse.{dim} AS SELECT * FROM raw.{dim}")
        
    # 2. Move Clean Facts (from clean to warehouse)
    facts = ['fact_payroll', 'fact_attendance_monthly', 'fact_task']
    for fact in facts:
        con.execute(f"CREATE OR REPLACE TABLE warehouse.{fact} AS SELECT * FROM clean.{fact}")
        
    # 3. ORPHAN CHECKS (Evidence for your report)
    print("="*40)
    print(" ORPHAN CHECK OUTPUT ")
    print("="*40)
    
    # Check if any payroll rows have an employee_key that doesn't exist in dim_employee
    payroll_orphans = con.execute("""
        SELECT COUNT(*) FROM warehouse.fact_payroll f
        LEFT JOIN warehouse.dim_employee d ON f.employee_key = d.employee_key
        WHERE d.employee_key IS NULL
    """).fetchone()[0]
    print(f"Orphans in fact_payroll (missing employee_key): {payroll_orphans}")
    
    # Check if any task rows have a team_id that doesn't exist in dim_team
    task_orphans = con.execute("""
        SELECT COUNT(*) FROM warehouse.fact_task f
        LEFT JOIN warehouse.dim_team d ON f.team_id = d.team_id
        WHERE d.team_id IS NULL
    """).fetchone()[0]
    print(f"Orphans in fact_task (missing team_id): {task_orphans}")
    
    print("\n*Note: Zero orphans means every fact correctly points to a dimension.*")

    # 4. ROW COUNT RECONCILIATION
    print("\n" + "="*40)
    print(" ROW COUNT RECONCILIATION ")
    print("="*40)
    
    for fact in facts:
        clean_count = con.execute(f"SELECT COUNT(*) FROM clean.{fact}").fetchone()[0]
        warehouse_count = con.execute(f"SELECT COUNT(*) FROM warehouse.{fact}").fetchone()[0]
        status = "✅ MATCH" if clean_count == warehouse_count else "❌ MISMATCH"
        print(f"{fact}:")
        print(f"  Task 1 Clean Rows: {clean_count}")
        print(f"  Task 2 Warehouse:  {warehouse_count}  -> {status}\n")

    con.close()
    print("Warehouse build complete!")

if __name__ == "__main__":
    build_warehouse()