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

con.execute("DETACH src")
con.close()

size_mb = round(os.path.getsize(PROD_DB) / (1024 * 1024), 2)
print(f"\nDone! Created {PROD_DB} ({size_mb} MB) | Data Cut-off: {data_cutoff}")