import os
from datetime import datetime, timezone
import duckdb

SRC_DB = "pulseiq.duckdb"
PROD_DB = "pulseiq_prod.duckdb"

if os.path.exists(PROD_DB):
    os.remove(PROD_DB)

con = duckdb.connect(PROD_DB)
con.execute(f"ATTACH '{SRC_DB}' AS src (READ_ONLY)")

# 1. Create schemas
for schema in ("metrics", "warehouse", "raw"):
    con.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")

# 2. Copy only non-PII lookup dimension tables used by dashboard joins
safe_dims = [
    ("warehouse", "dim_department"),
    ("raw", "dim_department"),
    ("raw", "dim_team"),
    ("raw", "dim_sprint"),
]
for schema, table in safe_dims:
    exists = con.execute(f"""
        SELECT COUNT(*) FROM information_schema.tables
        WHERE table_catalog = 'src'
          AND table_schema = '{schema}'
          AND table_name = '{table}'
    """).fetchone()[0]
    if exists:
        con.execute(f"CREATE TABLE {schema}.{table} AS SELECT * FROM src.{schema}.{table}")
        print(f"Copied lookup table: {schema}.{table}")

# 3. Materialize all aggregated metrics views (skip vw_app_* so page-level CREATE OR REPLACE VIEW won't clash)
metric_objects = con.execute("""
    SELECT table_name, table_type
    FROM information_schema.tables
    WHERE table_catalog = 'src'
      AND table_schema = 'metrics'
    ORDER BY table_name
""").fetchall()

for name, obj_type in metric_objects:
    if name.startswith("vw_app_"):
        continue
    con.execute(f"CREATE TABLE metrics.{name} AS SELECT * FROM src.metrics.{name}")
    print(f"Materialized aggregate: metrics.{name}")

# 4. Save data cut-off and refresh timestamp (so the app doesn't need raw.fact_payroll)
cutoff_row = con.execute("""
    SELECT MAX(SUBSTRING(CAST(date_key AS VARCHAR), 1, 8))
    FROM src.raw.fact_payroll
""").fetchone()
raw_cutoff = cutoff_row[0] if cutoff_row and cutoff_row[0] else "Unknown"
data_cutoff = (
    f"{raw_cutoff[:4]}-{raw_cutoff[4:6]}-{raw_cutoff[6:8]}"
    if len(str(raw_cutoff)) == 8 else str(raw_cutoff)
)
refreshed_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

con.execute("""
    CREATE TABLE metrics.data_metadata (
        data_cutoff VARCHAR,
        last_refreshed_utc VARCHAR
    )
""")
con.execute(
    "INSERT INTO metrics.data_metadata VALUES (?, ?)",
    [data_cutoff, refreshed_utc]
)

# 5. Build privacy-safe additive cube for Task 18 Self-Service KPI Explorer (no employee_id or names)
con.execute("""
    CREATE TABLE metrics.kpi_explorer_base AS
    WITH latest_pay_dt AS (
        SELECT MAX(date_key) AS max_dk FROM src.warehouse.fact_payroll
    ),
    latest_att_dt AS (
        SELECT MAX(date_key) AS max_dk FROM src.warehouse.fact_attendance_monthly
    ),
    emp_team_tasks AS (
        SELECT
            assignee_employee_id AS employee_id,
            team_id,
            COUNT(*) AS task_cnt,
            SUM(CASE WHEN LOWER(COALESCE(status, '')) IN ('done', 'completed', 'closed') THEN 1 ELSE 0 END) AS tasks_done,
            ROW_NUMBER() OVER (PARTITION BY assignee_employee_id ORDER BY COUNT(*) DESC) AS rn
        FROM src.warehouse.fact_task
        WHERE assignee_employee_id IS NOT NULL
        GROUP BY 1, 2
    ),
    emp_base AS (
        SELECT
            e.employee_id,
            COALESCE(d.department_name, 'Unknown') AS department_name,
            COALESCE(t.team_name, tl.team_name, 'General - ' || COALESCE(d.department_name, 'Unknown')) AS team_name,
            COALESCE(e.work_location, 'Unknown') AS work_location,
            COALESCE(e.work_mode, 'Unknown') AS work_mode,
            COALESCE(e.job_level, 'Unknown') AS job_level,
            CASE WHEN e.exit_date IS NULL AND LOWER(COALESCE(e.employment_status, 'active')) = 'active' THEN 1 ELSE 0 END AS is_active,
            CASE WHEN e.exit_date IS NOT NULL OR LOWER(COALESCE(e.employment_status, '')) IN ('exited', 'terminated', 'resigned', 'inactive') THEN 1 ELSE 0 END AS is_exited,
            p.net_pay,
            p.employer_cost,
            a.attendance_rate,
            COALESCE(et.tasks_done, 0) AS tasks_done
        FROM src.warehouse.dim_employee e
        LEFT JOIN src.warehouse.dim_department d
            ON e.department_id = d.department_id
        LEFT JOIN emp_team_tasks et
            ON e.employee_id = et.employee_id AND et.rn = 1
        LEFT JOIN src.warehouse.dim_team t
            ON et.team_id = t.team_id
        LEFT JOIN src.warehouse.dim_team tl
            ON e.employee_id = tl.team_lead_employee_id
        LEFT JOIN src.warehouse.fact_payroll p
            ON e.employee_id = p.employee_id
           AND p.date_key = (SELECT max_dk FROM latest_pay_dt)
        LEFT JOIN src.warehouse.fact_attendance_monthly a
            ON e.employee_id = a.employee_id
           AND a.date_key = (SELECT max_dk FROM latest_att_dt)
        WHERE e.is_current = TRUE
    )
    SELECT
        'PulseIQ Corp' AS company,
        department_name,
        team_name,
        work_location,
        work_mode,
        job_level,
        COUNT(*) AS total_employees,
        SUM(is_active) AS active_headcount,
        SUM(is_exited) AS exited_count,
        COALESCE(SUM(net_pay), 0.0) AS total_net_pay,
        COUNT(net_pay) AS pay_records,
        COALESCE(SUM(employer_cost), 0.0) AS total_employer_cost,
        COALESCE(SUM(attendance_rate), 0.0) AS sum_attendance_rate,
        COUNT(attendance_rate) AS att_records,
        SUM(tasks_done) AS tasks_completed
    FROM emp_base
    GROUP BY 1, 2, 3, 4, 5, 6
""")
print("Built privacy-safe explorer cube: metrics.kpi_explorer_base")

con.execute("DETACH src")
con.close()

size_mb = round(os.path.getsize(PROD_DB) / (1024 * 1024), 2)
print(f"\nDone! Created {PROD_DB} ({size_mb} MB) | Data Cut-off: {data_cutoff}")