import os
from typing import Optional
import duckdb
from fastapi import FastAPI, HTTPException, Query

DB_PATH = os.environ.get("DB_PATH", "pulseiq_prod.duckdb")

app = FastAPI(
    title="PulseIQ Metrics API",
    description=(
        "Read-only REST API exposing 5 trusted, governed company KPIs from "
        "`pulseiq_prod.duckdb` with business definitions, data lineage, and freshness statements."
    ),
    version="1.0.0",
)

# End-to-end lineage metadata for all 5 exposed metrics
LINEAGE_MAP = {
    "headcount": {
        "metric_id": "M01",
        "raw_tables": ["raw.dim_employee"],
        "etl_layer": "clean.dim_employee -> warehouse.dim_employee (SCD2)",
        "warehouse_tables": ["warehouse.dim_employee", "warehouse.dim_department"],
        "metric_view": "metrics.vw_headcount",
        "dashboard_pages": ["app.py (Executive Overview)", "pages/12_KPI_Explorer.py"],
        "api_endpoint": "/metrics/headcount",
    },
    "attrition-rate": {
        "metric_id": "M04",
        "raw_tables": ["raw.dim_employee"],
        "etl_layer": "clean.dim_employee -> warehouse.dim_employee (hire_date, exit_date)",
        "warehouse_tables": ["warehouse.dim_employee", "warehouse.dim_date"],
        "metric_view": "metrics.vw_attrition_monthly",
        "dashboard_pages": ["pages/01_People_Overview.py", "pages/12_KPI_Explorer.py"],
        "api_endpoint": "/metrics/attrition-rate",
    },
    "payroll-cost": {
        "metric_id": "M09",
        "raw_tables": ["raw.fact_payroll"],
        "etl_layer": "clean.fact_payroll -> warehouse.fact_payroll (employer_cost validation)",
        "warehouse_tables": ["warehouse.fact_payroll", "warehouse.dim_department"],
        "metric_view": "metrics.vw_payroll_cost",
        "dashboard_pages": ["pages/04_Payroll_Cost.py", "pages/12_KPI_Explorer.py"],
        "api_endpoint": "/metrics/payroll-cost",
    },
    "attendance-rate": {
        "metric_id": "M13",
        "raw_tables": ["raw.fact_attendance_monthly"],
        "etl_layer": "clean.fact_attendance_monthly -> warehouse.fact_attendance_monthly",
        "warehouse_tables": ["warehouse.fact_attendance_monthly", "warehouse.dim_department"],
        "metric_view": "metrics.vw_attendance",
        "dashboard_pages": ["pages/02_Attendance_and_Leave.py", "pages/12_KPI_Explorer.py"],
        "api_endpoint": "/metrics/attendance-rate",
    },
    "net-profit": {
        "metric_id": "FIN01",
        "raw_tables": ["raw.fact_ledger", "raw.fact_invoices"],
        "etl_layer": "clean.fact_ledger -> warehouse.fact_ledger (revenue vs expense mapping)",
        "warehouse_tables": ["warehouse.fact_ledger"],
        "metric_view": "metrics.vw_pl_monthly",
        "dashboard_pages": ["pages/06_Profit_and_Loss.py", "pages/11_Executive_Scorecard.py"],
        "api_endpoint": "/metrics/net-profit",
    },
}


def get_db():
    if not os.path.exists(DB_PATH):
        raise HTTPException(status_code=500, detail=f"Database not found at {DB_PATH}")
    return duckdb.connect(DB_PATH, read_only=True)


def get_freshness(con) -> dict:
    row = con.execute(
        "SELECT data_cutoff, last_refreshed_utc FROM metrics.data_metadata LIMIT 1"
    ).fetchone()
    cutoff = row[0] if row else "Unknown"
    refreshed = row[1] if row else "Unknown"
    return {
        "data_cutoff": cutoff,
        "last_refreshed_utc": refreshed,
        "refresh_schedule": "Daily at 06:00 UTC via GitHub Actions",
        "freshness_statement": (
            f"Data is current through {cutoff} and was last refreshed at {refreshed}. "
            "Automated refreshes run daily at 06:00 UTC."
        ),
    }


def get_catalog_entry(con, metric_id: str, fallback: dict) -> dict:
    row = con.execute(
        """
        SELECT metric_name, business_definition, formula, source_table, owner_team, unit, caveat
        FROM metrics.metric_catalog
        WHERE metric_id = ?
        LIMIT 1
        """,
        [metric_id],
    ).fetchone()
    if not row:
        return fallback
    return {
        "metric_name": row[0],
        "definition": row[1],
        "formula": row[2],
        "source_table": row[3],
        "owner_team": row[4],
        "unit": row[5],
        "caveat": None if (row[6] is None or str(row[6]).lower() == "nan") else row[6],
    }


@app.get("/", tags=["System"])
def root():
    con = get_db()
    try:
        freshness = get_freshness(con)
    finally:
        con.close()
    return {
        "service": "PulseIQ Metrics API",
        "status": "healthy",
        "docs_url": "/docs",
        "freshness": freshness,
        "endpoints": [
            "/metrics",
            "/metrics/headcount",
            "/metrics/attrition-rate",
            "/metrics/payroll-cost",
            "/metrics/attendance-rate",
            "/metrics/net-profit",
            "/lineage",
        ],
    }


@app.get("/metrics", tags=["Metrics"])
def list_metrics():
    con = get_db()
    try:
        freshness = get_freshness(con)
    finally:
        con.close()
    return {
        "count": len(LINEAGE_MAP),
        "freshness": freshness,
        "metrics": [
            {"slug": k, "metric_id": v["metric_id"], "endpoint": v["api_endpoint"], "source_view": v["metric_view"]}
            for k, v in LINEAGE_MAP.items()
        ],
    }


@app.get("/lineage", tags=["Lineage"])
def get_lineage():
    con = get_db()
    try:
        freshness = get_freshness(con)
    finally:
        con.close()
    return {"freshness": freshness, "lineage": LINEAGE_MAP}


@app.get("/metrics/headcount", tags=["Metrics"])
def metric_headcount(
    date_key: Optional[int] = Query(None, description="Optional YYYYMMDD period (defaults to latest month)")
):
    con = get_db()
    try:
        target_dk = date_key or con.execute("SELECT MAX(date_key) FROM metrics.vw_headcount").fetchone()[0]
        val = con.execute(
            "SELECT SUM(headcount) FROM metrics.vw_headcount WHERE date_key = ?", [target_dk]
        ).fetchone()[0]
        if val is None:
            raise HTTPException(status_code=404, detail=f"No headcount data found for date_key={target_dk}")
        meta = get_catalog_entry(
            con,
            "M01",
            {
                "metric_name": "Headcount",
                "definition": "Active employees on the last day of the month (permanent and contract).",
                "formula": "COUNT(DISTINCT employee_id) active at month end",
                "source_table": "metrics.vw_headcount",
                "owner_team": "HR Analytics",
                "unit": "count",
                "caveat": None,
            },
        )
        freshness = get_freshness(con)
    finally:
        con.close()

    return {
        "metric_id": "M01",
        "metric_name": meta["metric_name"],
        "period": str(target_dk),
        "value": int(val),
        "unit": meta["unit"],
        "definition": meta["definition"],
        "formula": meta["formula"],
        "source": "metrics.vw_headcount",
        "owner_team": meta["owner_team"],
        "caveat": meta["caveat"],
        "freshness": freshness,
        "lineage": LINEAGE_MAP["headcount"],
    }


@app.get("/metrics/attrition-rate", tags=["Metrics"])
def metric_attrition_rate(
    date_key: Optional[int] = Query(None, description="Optional YYYYMMDD period (defaults to latest month)")
):
    con = get_db()
    try:
        target_dk = date_key or con.execute("SELECT MAX(date_key) FROM metrics.vw_attrition_monthly").fetchone()[0]
        row = con.execute(
            """
            SELECT SUM(total_exits), SUM(starting_headcount)
            FROM metrics.vw_attrition_monthly
            WHERE date_key = ?
            """,
            [target_dk],
        ).fetchone()
        if not row or row[1] is None or row[1] == 0:
            raise HTTPException(status_code=404, detail=f"No attrition data found for date_key={target_dk}")
        exits, start_hc = float(row[0]), float(row[1])
        rate = round((exits / start_hc) * 100.0, 2)
        meta = get_catalog_entry(
            con,
            "M04",
            {
                "metric_name": "Attrition rate (monthly)",
                "definition": "Share of people who left in the month.",
                "formula": "Exits / headcount_start x 100",
                "source_table": "metrics.vw_attrition_monthly",
                "owner_team": "HR Analytics",
                "unit": "percent",
                "caveat": "Very noisy for small departments",
            },
        )
        freshness = get_freshness(con)
    finally:
        con.close()

    return {
        "metric_id": "M04",
        "metric_name": meta["metric_name"],
        "period": str(target_dk),
        "value": rate,
        "unit": meta["unit"],
        "components": {"total_exits": int(exits), "starting_headcount": int(start_hc)},
        "definition": meta["definition"],
        "formula": meta["formula"],
        "source": "metrics.vw_attrition_monthly",
        "owner_team": meta["owner_team"],
        "caveat": meta["caveat"],
        "freshness": freshness,
        "lineage": LINEAGE_MAP["attrition-rate"],
    }


@app.get("/metrics/payroll-cost", tags=["Metrics"])
def metric_payroll_cost(
    date_key: Optional[int] = Query(None, description="Optional YYYYMMDD period (defaults to latest month)")
):
    con = get_db()
    try:
        target_dk = date_key or con.execute("SELECT MAX(date_key) FROM metrics.vw_payroll_cost").fetchone()[0]
        val = con.execute(
            "SELECT SUM(total_payroll) FROM metrics.vw_payroll_cost WHERE date_key = ?", [target_dk]
        ).fetchone()[0]
        if val is None:
            raise HTTPException(status_code=404, detail=f"No payroll cost data found for date_key={target_dk}")
        meta = get_catalog_entry(
            con,
            "M09",
            {
                "metric_name": "Payroll cost (employer cost)",
                "definition": "Full cost of employees to the company: gross pay plus employer PF and ESI.",
                "formula": "SUM(employer_cost)",
                "source_table": "metrics.vw_payroll_cost",
                "owner_team": "Finance",
                "unit": "INR",
                "caveat": "Must reconcile with ledger accounts 5001-5005",
            },
        )
        freshness = get_freshness(con)
    finally:
        con.close()

    return {
        "metric_id": "M09",
        "metric_name": meta["metric_name"],
        "period": str(target_dk),
        "value": round(float(val), 2),
        "unit": meta["unit"],
        "definition": meta["definition"],
        "formula": meta["formula"],
        "source": "metrics.vw_payroll_cost",
        "owner_team": meta["owner_team"],
        "caveat": meta["caveat"],
        "freshness": freshness,
        "lineage": LINEAGE_MAP["payroll-cost"],
    }


@app.get("/metrics/attendance-rate", tags=["Metrics"])
def metric_attendance_rate(
    date_key: Optional[int] = Query(None, description="Optional YYYYMMDD period (defaults to latest month)")
):
    con = get_db()
    try:
        target_dk = date_key or con.execute("SELECT MAX(date_key) FROM metrics.vw_attendance").fetchone()[0]
        row = con.execute(
            """
            SELECT SUM(total_days_present), SUM(total_working_days)
            FROM metrics.vw_attendance
            WHERE date_key = ?
            """,
            [target_dk],
        ).fetchone()
        if not row or row[1] is None or row[1] == 0:
            raise HTTPException(status_code=404, detail=f"No attendance data found for date_key={target_dk}")
        present, working = float(row[0]), float(row[1])
        rate = round((present / working) * 100.0, 2)
        meta = get_catalog_entry(
            con,
            "M13",
            {
                "metric_name": "Attendance rate",
                "definition": "Days present (half day counts 0.5) divided by scheduled working days.",
                "formula": "(SUM(present_days) + 0.5 x SUM(half_days_unpaid)) / SUM(scheduled_days) x 100",
                "source_table": "metrics.vw_attendance",
                "owner_team": "HR Analytics",
                "unit": "percent",
                "caveat": "Paid leave counts as not present",
            },
        )
        freshness = get_freshness(con)
    finally:
        con.close()

    return {
        "metric_id": "M13",
        "metric_name": meta["metric_name"],
        "period": str(target_dk),
        "value": rate,
        "unit": "percent",
        "components": {"total_days_present": round(present, 1), "total_working_days": round(working, 1)},
        "definition": meta["definition"],
        "formula": meta["formula"],
        "source": "metrics.vw_attendance",
        "owner_team": meta["owner_team"],
        "caveat": meta["caveat"],
        "freshness": freshness,
        "lineage": LINEAGE_MAP["attendance-rate"],
    }


@app.get("/metrics/net-profit", tags=["Metrics"])
def metric_net_profit(
    month_key: Optional[int] = Query(None, description="Optional YYYYMM period (defaults to latest month)")
):
    con = get_db()
    try:
        target_mk = month_key or con.execute("SELECT MAX(month_key) FROM metrics.vw_pl_monthly").fetchone()[0]
        row = con.execute(
            """
            SELECT total_revenue, total_expense, margin
            FROM metrics.vw_pl_monthly
            WHERE month_key = ?
            """,
            [target_mk],
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"No P&L data found for month_key={target_mk}")
        rev, exp, margin = float(row[0]), float(row[1]), float(row[2])
        freshness = get_freshness(con)
    finally:
        con.close()

    return {
        "metric_id": "FIN01",
        "metric_name": "Monthly Net Profit (Margin)",
        "period": str(target_mk),
        "value": round(margin, 2),
        "unit": "INR",
        "components": {
            "total_revenue": round(rev, 2),
            "total_expense": round(exp, 2),
            "margin_pct": round((margin / rev) * 100.0, 2) if rev else 0.0,
        },
        "definition": "Total monthly revenue minus total monthly operating and payroll expenses.",
        "formula": "SUM(total_revenue) - SUM(total_expense)",
        "source": "metrics.vw_pl_monthly",
        "owner_team": "Finance",
        "caveat": "Accrual basis from posted general ledger entries.",
        "freshness": freshness,
        "lineage": LINEAGE_MAP["net-profit"],
    }