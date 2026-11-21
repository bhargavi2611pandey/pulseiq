import os
import pandas as pd
import streamlit as st
from db_utils import get_data_metadata

st.set_page_config(
    page_title="Data Lineage & API | PulseIQ",
    page_icon="🧬",
    layout="wide",
)

data_cutoff, last_refreshed = get_data_metadata()
api_base_url = os.environ.get("METRICS_API_URL", "https://pulseiq-metrics-api-9dgr.onrender.com")

st.title("🧬 Data Lineage, Freshness & Metrics API")

# -------------------------------------------------------------------
# 1. Data Freshness Statement (Required in both API and App)
# -------------------------------------------------------------------
st.info(
    f"**Data Freshness Statement:** PulseIQ analytics are current through **{data_cutoff}** "
    f"and were last refreshed on **{last_refreshed}**. Automated pipeline refreshes run "
    "**daily at 06:00 UTC** via GitHub Actions (`refresh_prod_data.yml`)."
)

c1, c2, c3 = st.columns(3)
c1.metric("Data Cut-Off", data_cutoff)
c2.metric("Last Refreshed (UTC)", last_refreshed)
c3.metric("Refresh Schedule", "Daily @ 06:00 UTC")

st.divider()

# -------------------------------------------------------------------
# 2. End-to-End Lineage Diagram (Native Graphviz — zero extra installs)
# -------------------------------------------------------------------
st.subheader("End-to-End Data Lineage (5 Governed Metrics)")
st.caption("Trace every KPI from raw source tables through ETL, warehouse models, metric views, and consumers.")

lineage_dot = """
digraph PulseIQLineage {
    rankdir=LR;
    node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10];
    edge [color="#64748b"];

    subgraph cluster_raw {
        label="1. Raw Tables";
        style=dashed; color="#94a3b8";
        r_emp [label="raw.dim_employee", fillcolor="#fee2e2"];
        r_pay [label="raw.fact_payroll", fillcolor="#fee2e2"];
        r_att [label="raw.fact_attendance_monthly", fillcolor="#fee2e2"];
        r_led [label="raw.fact_ledger /\\nraw.fact_invoices", fillcolor="#fee2e2"];
    }

    subgraph cluster_etl {
        label="2. ETL / Clean Layer";
        style=dashed; color="#94a3b8";
        e_emp [label="clean.dim_employee\\n(SCD2 & status)", fillcolor="#fef3c7"];
        e_pay [label="clean.fact_payroll\\n(employer_cost checks)", fillcolor="#fef3c7"];
        e_att [label="clean.fact_attendance_monthly\\n(half-day weighting)", fillcolor="#fef3c7"];
        e_led [label="clean.fact_ledger\\n(rev vs exp mapping)", fillcolor="#fef3c7"];
    }

    subgraph cluster_wh {
        label="3. Warehouse";
        style=dashed; color="#94a3b8";
        w_emp [label="warehouse.dim_employee\\n+ dim_department", fillcolor="#dbeafe"];
        w_pay [label="warehouse.fact_payroll\\n+ dim_department", fillcolor="#dbeafe"];
        w_att [label="warehouse.fact_attendance_monthly\\n+ dim_department", fillcolor="#dbeafe"];
        w_led [label="warehouse.fact_ledger", fillcolor="#dbeafe"];
    }

    subgraph cluster_met {
        label="4. Metric Views (pulseiq_prod.duckdb)";
        style=dashed; color="#94a3b8";
        m_hc  [label="metrics.vw_headcount\\n(M01)", fillcolor="#dcfce7"];
        m_att_r [label="metrics.vw_attrition_monthly\\n(M04)", fillcolor="#dcfce7"];
        m_pay [label="metrics.vw_payroll_cost\\n(M09)", fillcolor="#dcfce7"];
        m_att [label="metrics.vw_attendance\\n(M13)", fillcolor="#dcfce7"];
        m_pl  [label="metrics.vw_pl_monthly\\n(FIN01)", fillcolor="#dcfce7"];
    }

    subgraph cluster_cons {
        label="5. Consumers";
        style=dashed; color="#94a3b8";
        dash [label="Streamlit Dashboard\\n(Overview, Dept Pages,\\nKPI Explorer)", fillcolor="#ede9fe"];
        api  [label="FastAPI Metrics Service\\n(/metrics/* & /lineage)", fillcolor="#ede9fe"];
    }

    r_emp -> e_emp -> w_emp;
    w_emp -> m_hc;
    w_emp -> m_att_r;
    r_pay -> e_pay -> w_pay -> m_pay;
    r_att -> e_att -> w_att -> m_att;
    r_led -> e_led -> w_led -> m_pl;

    m_hc -> dash;   m_hc -> api;
    m_att_r -> dash; m_att_r -> api;
    m_pay -> dash;  m_pay -> api;
    m_att -> dash;  m_att -> api;
    m_pl -> dash;   m_pl -> api;
}
"""
st.graphviz_chart(lineage_dot, use_container_width=True)

# -------------------------------------------------------------------
# 3. Lineage Catalog & Column-Change Impact Table
# -------------------------------------------------------------------
st.subheader("Lineage Matrix & Column-Change Impact")

lineage_df = pd.DataFrame([
    {
        "Metric ID": "M01",
        "Metric Name": "Active Headcount",
        "Raw Table": "raw.dim_employee",
        "Warehouse Table": "warehouse.dim_employee, dim_department",
        "Metric View": "metrics.vw_headcount",
        "API Endpoint": "/metrics/headcount",
        "Critical Raw Columns": "employee_id, hire_date, exit_date, department_id",
    },
    {
        "Metric ID": "M04",
        "Metric Name": "Attrition Rate (Monthly)",
        "Raw Table": "raw.dim_employee",
        "Warehouse Table": "warehouse.dim_employee, dim_date",
        "Metric View": "metrics.vw_attrition_monthly",
        "API Endpoint": "/metrics/attrition-rate",
        "Critical Raw Columns": "employee_id, hire_date, exit_date, employment_status",
    },
    {
        "Metric ID": "M09",
        "Metric Name": "Payroll Cost (Employer)",
        "Raw Table": "raw.fact_payroll",
        "Warehouse Table": "warehouse.fact_payroll, dim_department",
        "Metric View": "metrics.vw_payroll_cost",
        "API Endpoint": "/metrics/payroll-cost",
        "Critical Raw Columns": "employer_cost, date_key, department_id",
    },
    {
        "Metric ID": "M13",
        "Metric Name": "Attendance Rate",
        "Raw Table": "raw.fact_attendance_monthly",
        "Warehouse Table": "warehouse.fact_attendance_monthly, dim_department",
        "Metric View": "metrics.vw_attendance",
        "API Endpoint": "/metrics/attendance-rate",
        "Critical Raw Columns": "present_days, half_days_unpaid, scheduled_days",
    },
    {
        "Metric ID": "FIN01",
        "Metric Name": "Monthly Net Profit",
        "Raw Table": "raw.fact_ledger, raw.fact_invoices",
        "Warehouse Table": "warehouse.fact_ledger",
        "Metric View": "metrics.vw_pl_monthly",
        "API Endpoint": "/metrics/net-profit",
        "Critical Raw Columns": "amount, account_type, posting_date",
    },
])
st.dataframe(lineage_df, use_container_width=True, hide_index=True)

st.divider()

# -------------------------------------------------------------------
# 4. Metrics REST API Quick Reference
# -------------------------------------------------------------------
st.subheader("Metrics REST API Endpoints")
st.markdown(f"**API Base URL:** `{api_base_url}`  |  **Interactive Docs:** `{api_base_url}/docs`")

st.code(
    f"""# Example API calls
curl -s {api_base_url}/metrics/headcount
curl -s {api_base_url}/metrics/attrition-rate
curl -s {api_base_url}/metrics/payroll-cost
curl -s {api_base_url}/metrics/attendance-rate
curl -s {api_base_url}/metrics/net-profit
curl -s {api_base_url}/lineage""",
    language="bash",
)