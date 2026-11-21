import duckdb
import pandas as pd
import altair as alt
import streamlit as st

DB_PATH = "pulseiq_prod.duckdb"
MIN_GROUP_SIZE = 5

st.set_page_config(page_title="Department 360° Drill-Down | PulseIQ", layout="wide")


@st.cache_data(ttl=300)
def load_department_data():
    con = duckdb.connect(DB_PATH, read_only=True)

    meta = con.execute(
        "SELECT data_cutoff, last_refreshed_utc FROM metrics.data_metadata LIMIT 1"
    ).fetchone()

    dept_map = con.execute("""
        SELECT DISTINCT department_id, department_name
        FROM metrics.vw_budget_variance
        ORDER BY department_id
    """).df()

    unified = con.execute("""
        SELECT
            department_name,
            month_key,
            CAST(headcount AS BIGINT) AS headcount,
            CAST(total_employer_cost AS DOUBLE) AS total_employer_cost,
            CAST(total_overtime_pay AS DOUBLE) AS total_overtime_pay,
            CAST(overtime_cost_per_head AS DOUBLE) AS overtime_cost_per_head,
            CAST(total_paid_leave_days AS BIGINT) AS total_paid_leave_days,
            CAST(leave_days_per_head AS DOUBLE) AS leave_days_per_head,
            CAST(total_overtime_hours AS DOUBLE) AS total_overtime_hours,
            CAST(attritions AS BIGINT) AS attritions
        FROM metrics.vw_department_unified
        ORDER BY department_name, month_key
    """).df()

    budget = con.execute("""
        SELECT
            department_id,
            department_name,
            date_key,
            CAST(budget_month AS VARCHAR) AS budget_month,
            CAST(actual_cost AS DOUBLE) AS actual_cost,
            CAST(budget_cost AS DOUBLE) AS budget_cost,
            CAST(variance_amount AS DOUBLE) AS variance_amount,
            CAST(variance_pct AS DOUBLE) AS variance_pct,
            budget_status
        FROM metrics.vw_budget_variance
        ORDER BY department_id, date_key
    """).df()

    risk = con.execute("""
        SELECT
            department_id,
            as_of_date_key,
            risk_band,
            CAST(SUM(employees_at_risk) AS BIGINT) AS employees_at_risk
        FROM metrics.vw_attrition_risk
        GROUP BY department_id, as_of_date_key, risk_band
    """).df()

    con.close()
    return meta, dept_map, unified, budget, risk


def format_inr(val: float) -> str:
    if abs(val) >= 1e7:
        return f"₹{val / 1e7:.2f} Cr"
    if abs(val) >= 1e5:
        return f"₹{val / 1e5:.2f} L"
    return f"₹{val:,.0f}"


# --- Header & Freshness ---
meta, dept_map, unified_df, budget_df, risk_df = load_department_data()
cutoff, refreshed = meta if meta else ("N/A", "N/A")

st.title("Department 360° Drill-Down")
st.caption(
    f"Unified view across People, Payroll, Budget Variance, Workload & Attrition Risk  |  "
    f"Data current through **{cutoff}** (Last refreshed: {refreshed})"
)

# --- Department Selector (Default to D06 if present) ---
dept_options = [
    f"{row.department_id} — {row.department_name}" for row in dept_map.itertuples()
]
default_idx = next((i for i, label in enumerate(dept_options) if label.startswith("D06")), 0)

selected_label = st.selectbox("Select Department", dept_options, index=default_idx)
selected_id, selected_name = selected_label.split(" — ", 1)

# Filter datasets
u_dept = unified_df[unified_df["department_name"] == selected_name].sort_values("month_key")
b_dept = budget_df[budget_df["department_id"] == selected_id].sort_values("date_key")
r_dept = risk_df[risk_df["department_id"] == selected_id].copy()

if u_dept.empty:
    st.warning(f"No unified department records found for {selected_name}.")
    st.stop()

latest_u = u_dept.iloc[-1]
prev_u = u_dept.iloc[-2] if len(u_dept) > 1 else latest_u
latest_b = b_dept.iloc[-1] if not b_dept.empty else None

# High-risk count with privacy check
high_risk_raw = int(r_dept.loc[r_dept["risk_band"] == "High", "employees_at_risk"].sum())
if 0 < high_risk_raw < MIN_GROUP_SIZE:
    high_risk_display = f"Suppressed (<{MIN_GROUP_SIZE})"
else:
    high_risk_display = str(high_risk_raw)

# --- 4-Card Executive Strip ---
c1, c2, c3, c4 = st.columns(4)

hc_delta = int(latest_u["headcount"] - prev_u["headcount"])
c1.metric(
    label=f"Active Headcount ({latest_u['month_key']})",
    value=f"{int(latest_u['headcount'])}",
    delta=f"{hc_delta:+d} MoM",
)

cost_per_head = (
    latest_u["total_employer_cost"] / latest_u["headcount"]
    if latest_u["headcount"] > 0
    else 0
)
c2.metric(
    label="Monthly Employer Payroll",
    value=format_inr(latest_u["total_employer_cost"]),
    delta=f"{format_inr(cost_per_head)} / head",
    delta_color="off",
)

if latest_b is not None:
    c3.metric(
        label="Latest Budget Variance",
        value=f"{latest_b['variance_pct']:+.2f}%",
        delta=str(latest_b["budget_status"]),
        delta_color="off",
    )
else:
    c3.metric(label="Latest Budget Variance", value="N/A")

c4.metric(
    label="High-Risk Attrition Cohort",
    value=high_risk_display,
    delta="k-anonymity (n ≥ 5) enforced",
    delta_color="off",
)

st.divider()

# --- Two Side-by-Side Charts ---
left, right = st.columns([1.3, 1])

with left:
    st.subheader("6-Month Actual vs. Budget Cost")
    if not b_dept.empty:
        b_recent = b_dept.tail(6).copy()
        b_recent["Month"] = b_recent["budget_month"].str.slice(0, 7)
        melted = b_recent.melt(
            id_vars=["Month"],
            value_vars=["actual_cost", "budget_cost"],
            var_name="Series",
            value_name="Amount",
        )
        melted["Series"] = melted["Series"].replace(
            {"actual_cost": "Actual Cost", "budget_cost": "Budget Cost"}
        )
        melted["Amount_Lakhs"] = melted["Amount"] / 1e5

        chart_budget = (
            alt.Chart(melted)
            .mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
            .encode(
                x=alt.X("Month:N", title="Month"),
                xOffset="Series:N",
                y=alt.Y("Amount_Lakhs:Q", title="INR (Lakhs)"),
                color=alt.Color(
                    "Series:N",
                    scale=alt.Scale(
                        domain=["Actual Cost", "Budget Cost"],
                        range=["#2563EB", "#94A3B8"],
                    ),
                ),
                tooltip=[
                    "Month",
                    "Series",
                    alt.Tooltip("Amount_Lakhs:Q", title="INR Lakhs", format=".2f"),
                ],
            )
            .properties(height=320)
        )
        st.altair_chart(chart_budget, use_container_width=True)
    else:
        st.info("No budget variance records available for this department.")

with right:
    st.subheader("Attrition Risk Breakdown")
    if not r_dept.empty:
        # Apply k-anonymity suppression for any band with 1..(MIN_GROUP_SIZE-1) employees
        r_display = r_dept.copy()
        suppressed_bands = r_display[
            (r_display["employees_at_risk"] > 0)
            & (r_display["employees_at_risk"] < MIN_GROUP_SIZE)
        ]["risk_band"].tolist()

        r_chart = r_display[r_display["employees_at_risk"] >= MIN_GROUP_SIZE].copy()

        if not r_chart.empty:
            chart_risk = (
                alt.Chart(r_chart)
                .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4, size=48)
                .encode(
                    x=alt.X("risk_band:N", sort=["High", "Medium", "Low"], title="Risk Band"),
                    y=alt.Y("employees_at_risk:Q", title="Employees Flagged"),
                    color=alt.Color(
                        "risk_band:N",
                        scale=alt.Scale(
                            domain=["High", "Medium", "Low"],
                            range=["#DC2626", "#D97706", "#64748B"],
                        ),
                        legend=None,
                    ),
                    tooltip=["risk_band", "employees_at_risk"],
                )
                .properties(height=320)
            )
            st.altair_chart(chart_risk, use_container_width=True)
        else:
            st.info(f"All risk cohorts for {selected_name} are suppressed (fewer than {MIN_GROUP_SIZE} employees per band).")

        if suppressed_bands:
            st.caption(
                f"Privacy guard active: {', '.join(suppressed_bands)} band(s) hidden because group size < {MIN_GROUP_SIZE}."
            )
    else:
        st.info("No attrition risk records flagged for this department.")

# --- Workload & Overtime Strip ---
st.subheader("Workload, Overtime & Leave Signals (Last 6 Months)")
u_recent = u_dept.tail(6).copy()

w1, w2, w3 = st.columns(3)
w1.metric("Avg Overtime Cost / Head", format_inr(u_recent["overtime_cost_per_head"].mean()))
w2.metric("Avg Paid Leave Days / Head", f"{u_recent['leave_days_per_head'].mean():.2f} days")
w3.metric("Total Exits (Last 6 Months)", f"{int(u_recent['attritions'].sum())}")

# --- 6-Month Department Brief Table + CSV Download ---
st.subheader(f"6-Month Department Brief — {selected_name}")
brief_df = u_recent[
    [
        "month_key",
        "headcount",
        "attritions",
        "total_employer_cost",
        "total_overtime_pay",
        "total_overtime_hours",
        "leave_days_per_head",
    ]
].sort_values("month_key", ascending=False)

st.dataframe(brief_df, use_container_width=True, hide_index=True)

csv_bytes = brief_df.to_csv(index=False).encode("utf-8")
st.download_button(
    label="Download Department Brief (CSV)",
    data=csv_bytes,
    file_name=f"pulseiq_dept_brief_{selected_id}_{selected_name.lower().replace(' ', '_')}.csv",
    mime="text/csv",
)