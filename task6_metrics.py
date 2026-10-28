import duckdb

def build_attendance_metrics():
    con = duckdb.connect("pulseiq.duckdb")
    
    print("Building Attendance & Leave Metric Views...")
    
    # --- 1. ATTENDANCE VIEW ---
    cols_df = con.execute("PRAGMA table_info('warehouse.fact_attendance_monthly')").df()
    columns = cols_df['name'].tolist()
    
    if "unpaid_absence_days" in columns and "paid_leave_days" in columns:
        working_days_expr = "present_days + paid_leave_days + unpaid_absence_days"
    else:
        working_days_expr = "present_days"
        
    late_arrivals_expr = "SUM(late_arrivals)" if "late_arrivals" in columns else "0"
    
    sql_attendance = f"""
        CREATE OR REPLACE VIEW metrics.vw_attendance AS
        SELECT
            department_id,
            date_key,
            SUM(present_days) AS total_days_present,
            SUM({working_days_expr}) AS total_working_days,
            ROUND((SUM(present_days) * 100.0) / NULLIF(SUM({working_days_expr}), 0), 2) AS attendance_rate_pct,
            {late_arrivals_expr} AS total_late_arrivals,
            SUM(overtime_hours) AS total_overtime_hours
        FROM warehouse.fact_attendance_monthly
        GROUP BY department_id, date_key
        HAVING COUNT(DISTINCT employee_key) >= 5;
    """
    con.execute(sql_attendance)
    print("✅ metrics.vw_attendance created.")

    # --- 2. LEAVE VIEW ---
    leave_cols_df = con.execute("PRAGMA table_info('raw.fact_leave')").df()
    leave_cols = leave_cols_df['name'].tolist()
    
    # Auto-detect column names based on the errors we've seen
    date_col = 'date_key' if 'date_key' in leave_cols else 'end_date_key'
    emp_col = 'employee_key' if 'employee_key' in leave_cols else 'employee_id'
    leave_type_col = 'leave_type' if 'leave_type' in leave_cols else 'leave_type_code'
    
    # NEW: Detect if the column is 'leave_days' or just 'days'
    leave_days_col = 'leave_days' if 'leave_days' in leave_cols else 'days'
    
    if 'department_id' in leave_cols:
        sql_leave = f"""
            CREATE OR REPLACE VIEW metrics.vw_leave AS
            SELECT
                department_id,
                {date_col} AS date_key,
                {leave_type_col} AS leave_type,
                SUM({leave_days_col}) AS total_leave_days
            FROM raw.fact_leave
            GROUP BY department_id, {date_col}, {leave_type_col}
            HAVING COUNT(DISTINCT {emp_col}) >= 5;
        """
    else:
        sql_leave = f"""
            CREATE OR REPLACE VIEW metrics.vw_leave AS
            SELECT
                e.department_id,
                l.{date_col} AS date_key,
                l.{leave_type_col} AS leave_type,
                SUM(l.{leave_days_col}) AS total_leave_days
            FROM raw.fact_leave l
            JOIN warehouse.dim_employee e ON l.{emp_col} = e.{emp_col}
            GROUP BY e.department_id, l.{date_col}, l.{leave_type_col}
            HAVING COUNT(DISTINCT l.{emp_col}) >= 5;
        """
    
    con.execute(sql_leave)
    print("✅ metrics.vw_leave created.")
    
    con.close()

if __name__ == "__main__":
    build_attendance_metrics()