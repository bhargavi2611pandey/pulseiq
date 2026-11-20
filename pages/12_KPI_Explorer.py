import os
import pandas as pd
import streamlit as st
from db_utils import get_connection, get_data_metadata

st.set_page_config(
    page_title="KPI Explorer | PulseIQ",
    page_icon="🔍",
    layout="wide",
)

MIN_GROUP_SIZE = 5

# -------------------------------------------------------------------
# 1. Load Demo Users & Role Rules (from 05_Starter/demo_users.csv)
# -------------------------------------------------------------------
@st.cache_data
def load_demo_users() -> pd.DataFrame:
    csv_path = os.path.join("05_Starter", "demo_users.csv")
    if os.path.exists(csv_path):
        return pd.read_csv(csv_path)
    return pd.DataFrame([
        {"username": "admin.demo", "role": "ADMIN", "sees": "Everything, including salary-level data"},
        {"username": "hr.demo", "role": "HR", "sees": "People and payroll aggregates; salary detail only for own department"},
        {"username": "manager.demo", "role": "MANAGER", "sees": "Own team metrics only; groups smaller than the minimum group size are hidden"},
        {"username": "exec.demo", "role": "EXECUTIVE", "sees": "Company-level KPIs only, no individual or small-group data"},
    ])


@st.cache_data(ttl=300)
def load_explorer_cube() -> pd.DataFrame:
    con = get_connection()
    df = con.execute("SELECT * FROM metrics.kpi_explorer_base").df()
    con.close()
    return df


ROLE_CONFIG = {
    "ADMIN": {
        "levels": ["Company", "Department", "Team"],
        "metrics": [
            "Active Headcount",
            "Attrition Rate (%)",
            "Attendance Rate (%)",
            "Tasks Completed",
            "Total Employer Cost ($)",
            "Avg Net Pay ($)",
        ],
        "allow_dimensions": True,
        "own_dept": None,
        "own_team": None,
        "salary_own_dept_only": False,
    },
    "HR": {
        "levels": ["Company", "Department", "Team"],
        "metrics": [
            "Active Headcount",
            "Attrition Rate (%)",
            "Attendance Rate (%)",
            "Tasks Completed",
            "Total Employer Cost ($)",
            "Avg Net Pay ($)",
        ],
        "allow_dimensions": True,
        "own_dept": "Human Resources",
        "own_team": None,
        "salary_own_dept_only": True,
    },
    "MANAGER": {
        "levels": ["Team"],
        "metrics": [
            "Active Headcount",
            "Attrition Rate (%)",
            "Attendance Rate (%)",
            "Tasks Completed",
        ],
        "allow_dimensions": True,
        "own_dept": "Product & Design",
        "own_team": "Design Systems",
        "salary_own_dept_only": False,
    },
    "EXECUTIVE": {
        "levels": ["Company"],
        "metrics": [
            "Active Headcount",
            "Attrition Rate (%)",
            "Attendance Rate (%)",
            "Total Employer Cost ($)",
        ],
        "allow_dimensions": False,
        "own_dept": None,
        "own_team": None,
        "salary_own_dept_only": False,
    },
}

DIMENSION_MAP = {
    "None (Drill-Down Level Only)": None,
    "Work Location": "work_location",
    "Work Mode": "work_mode",
    "Job Level": "job_level",
}

LEVEL_COL_MAP = {
    "Company": "company",
    "Department": "department_name",
    "Team": "team_name",
}

# -------------------------------------------------------------------
# 2. Metric Computation & Privacy Engine
# -------------------------------------------------------------------
def aggregate_and_suppress(df: pd.DataFrame, group_cols: list[str], metric: str):
    """
    Aggregates additive base columns, computes the selected metric,
    and applies Primary + Complementary Suppression (MIN_GROUP_SIZE = 5).
    """
    agg = (
        df.groupby(group_cols, dropna=False, as_index=False)
        .agg(
            total_employees=("total_employees", "sum"),
            active_headcount=("active_headcount", "sum"),
            exited_count=("exited_count", "sum"),
            total_net_pay=("total_net_pay", "sum"),
            pay_records=("pay_records", "sum"),
            total_employer_cost=("total_employer_cost", "sum"),
            sum_attendance_rate=("sum_attendance_rate", "sum"),
            att_records=("att_records", "sum"),
            tasks_completed=("tasks_completed", "sum"),
        )
    )

    # Determine the effective privacy denominator for the chosen metric
    if metric in ("Avg Net Pay ($)", "Total Employer Cost ($)"):
        agg["privacy_n"] = agg[["active_headcount", "pay_records"]].min(axis=1)
    elif metric == "Attendance Rate (%)":
        agg["privacy_n"] = agg[["active_headcount", "att_records"]].min(axis=1)
    elif metric == "Attrition Rate (%)":
        agg["privacy_n"] = agg["total_employees"]
    else:
        agg["privacy_n"] = agg["active_headcount"]

    # Primary suppression: hide any group with fewer than MIN_GROUP_SIZE people
    agg["is_suppressed"] = agg["privacy_n"] < MIN_GROUP_SIZE

    # Complementary suppression (anti-differencing):
    # If exactly 1 group is hidden and >= 1 group is visible, hide the next smallest group
    # so users cannot subtract visible rows from a parent total to deduce the hidden group.
    suppressed_count = int(agg["is_suppressed"].sum())
    visible_count = int((~agg["is_suppressed"]).sum())
    complementary_applied = False
    if suppressed_count == 1 and visible_count >= 1:
        next_smallest_idx = agg.loc[~agg["is_suppressed"], "privacy_n"].idxmin()
        agg.loc[next_smallest_idx, "is_suppressed"] = True
        complementary_applied = True

    # Compute the requested metric only for safe rows
    if metric == "Active Headcount":
        agg["metric_value"] = agg["active_headcount"].astype(float)
    elif metric == "Attrition Rate (%)":
        agg["metric_value"] = (
            (agg["exited_count"] / agg["total_employees"].replace(0, pd.NA)) * 100.0
        ).fillna(0.0).round(2)
    elif metric == "Attendance Rate (%)":
        agg["metric_value"] = (
            (agg["sum_attendance_rate"] / agg["att_records"].replace(0, pd.NA))
        ).fillna(0.0).round(2)
    elif metric == "Tasks Completed":
        agg["metric_value"] = agg["tasks_completed"].astype(float)
    elif metric == "Total Employer Cost ($)":
        agg["metric_value"] = agg["total_employer_cost"].round(2)
    elif metric == "Avg Net Pay ($)":
        agg["metric_value"] = (
            (agg["total_net_pay"] / agg["pay_records"].replace(0, pd.NA))
        ).fillna(0.0).round(2)

    visible_df = agg[~agg["is_suppressed"]].copy()
    hidden_count = int(agg["is_suppressed"].sum())
    return visible_df, hidden_count, complementary_applied


def format_metric_value(metric: str, val: float) -> str:
    if metric in ("Active Headcount", "Tasks Completed"):
        return f"{int(round(val)):,}"
    if "(%)" in metric:
        return f"{val:.2f}%"
    return f"${val:,.0f}"


# -------------------------------------------------------------------
# 3. Page Header & Role Switcher (Sidebar)
# -------------------------------------------------------------------
data_cutoff, last_refreshed = get_data_metadata()
users_df = load_demo_users()
cube_df = load_explorer_cube()

st.title("🔍 Self-Service KPI Explorer (Privacy-Protected)")
st.caption(
    f"Data Cut-off: **{data_cutoff}** | Minimum Group Size: **{MIN_GROUP_SIZE}** | "
    "No individual employee records are stored or exposed."
)

st.sidebar.header("👤 Role Simulator (demo_users.csv)")
user_options = [
    f"{row['username']} ({row['role']})" for _, row in users_df.iterrows()
]
selected_user_label = st.sidebar.selectbox("Sign in as demo user:", user_options)
selected_row = users_df.iloc[user_options.index(selected_user_label)]
active_role = selected_row["role"]
role_desc = selected_row["sees"]
cfg = ROLE_CONFIG[active_role]

st.sidebar.info(f"**Role:** {active_role}\n\n**Access Policy:** {role_desc}")

# Optional demo toggle for MANAGER to test their own small-team privacy rule
manager_team = cfg["own_team"]
manager_dept = cfg["own_dept"]
if active_role == "MANAGER":
    st.sidebar.divider()
    st.sidebar.markdown("**Manager Team Assignment (Demo Test)**")
    mgr_choice = st.sidebar.radio(
        "Simulate managing:",
        [
            "Design Systems (Product & Design — 10 members)",
            "General - Data & AI (Data & AI — 2 members)",
        ],
    )
    if "Data & AI" in mgr_choice:
        manager_dept = "Data & AI"
        manager_team = "General - Data & AI"

# -------------------------------------------------------------------
# 4. Apply Role Scope Before Any Exploration
# -------------------------------------------------------------------
scoped_df = cube_df.copy()

if active_role == "MANAGER":
    scoped_df = scoped_df[
        (scoped_df["department_name"] == manager_dept)
        & (scoped_df["team_name"] == manager_team)
    ]

# -------------------------------------------------------------------
# 5. Explorer Controls (Metric, Drill-Down, Dimension, Filters)
# -------------------------------------------------------------------
col_m, col_l, col_d = st.columns(3)

with col_m:
    selected_metric = st.selectbox("1. Choose Metric", cfg["metrics"])

with col_l:
    selected_level = st.selectbox("2. Drill-Down Level", cfg["levels"])

with col_d:
    if cfg["allow_dimensions"]:
        selected_dim_label = st.selectbox(
            "3. Slice by Dimension (Optional)", list(DIMENSION_MAP.keys())
        )
    else:
        selected_dim_label = "None (Drill-Down Level Only)"
        st.selectbox(
            "3. Slice by Dimension (Optional)",
            [selected_dim_label],
            disabled=True,
            help="Executives view company-level aggregates only.",
        )

# Interactive Drill-Down Filters (Company -> Department -> Team)
filtered_df = scoped_df.copy()
selected_dept = "All Departments"

if active_role in ("ADMIN", "HR"):
    f1, f2, f3, f4 = st.columns(4)
    depts = ["All Departments"] + sorted(scoped_df["department_name"].dropna().unique().tolist())

    # HR salary rule: Avg Net Pay restricted to own department only
    if cfg["salary_own_dept_only"] and selected_metric == "Avg Net Pay ($)":
        st.warning(
            f"🔒 **HR Policy Enforced:** As `{selected_row['username']}`, **Avg Net Pay ($)** "
            f"is restricted to your own department (**{cfg['own_dept']}**)."
        )
        selected_dept = cfg["own_dept"]
        f1.selectbox("Department Filter", [selected_dept], disabled=True)
    else:
        selected_dept = f1.selectbox("Department Filter", depts)

    if selected_dept != "All Departments":
        filtered_df = filtered_df[filtered_df["department_name"] == selected_dept]

    teams = ["All Teams"] + sorted(filtered_df["team_name"].dropna().unique().tolist())
    selected_team = f2.selectbox("Team Filter", teams)
    if selected_team != "All Teams":
        filtered_df = filtered_df[filtered_df["team_name"] == selected_team]

    locs = ["All Locations"] + sorted(filtered_df["work_location"].dropna().unique().tolist())
    selected_loc = f3.selectbox("Work Location", locs)
    if selected_loc != "All Locations":
        filtered_df = filtered_df[filtered_df["work_location"] == selected_loc]

    modes = ["All Work Modes"] + sorted(filtered_df["work_mode"].dropna().unique().tolist())
    selected_mode = f4.selectbox("Work Mode", modes)
    if selected_mode != "All Work Modes":
        filtered_df = filtered_df[filtered_df["work_mode"] == selected_mode]

elif active_role == "MANAGER":
    st.info(f"🔒 **Manager Scope:** Locked to **{manager_dept} → {manager_team}**.")
    f1, f2, f3 = st.columns(3)
    locs = ["All Locations"] + sorted(filtered_df["work_location"].dropna().unique().tolist())
    selected_loc = f1.selectbox("Work Location", locs)
    if selected_loc != "All Locations":
        filtered_df = filtered_df[filtered_df["work_location"] == selected_loc]

    modes = ["All Work Modes"] + sorted(filtered_df["work_mode"].dropna().unique().tolist())
    selected_mode = f2.selectbox("Work Mode", modes)
    if selected_mode != "All Work Modes":
        filtered_df = filtered_df[filtered_df["work_mode"] == selected_mode]

    levels = ["All Job Levels"] + sorted(filtered_df["job_level"].dropna().unique().tolist())
    selected_jl = f3.selectbox("Job Level", levels)
    if selected_jl != "All Job Levels":
        filtered_df = filtered_df[filtered_df["job_level"] == selected_jl]

else:
    st.info("🔒 **Executive Scope:** Company-wide summary only. Department, team, and granular filters are disabled.")

st.divider()

# -------------------------------------------------------------------
# 6. Check Overall Slice Privacy Before Showing ANY Numbers
# -------------------------------------------------------------------
total_active = int(filtered_df["active_headcount"].sum())
total_emps = int(filtered_df["total_employees"].sum())
total_pay_rec = int(filtered_df["pay_records"].sum())
total_att_rec = int(filtered_df["att_records"].sum())

if selected_metric in ("Avg Net Pay ($)", "Total Employer Cost ($)"):
    overall_n = min(total_active, total_pay_rec)
elif selected_metric == "Attendance Rate (%)":
    overall_n = min(total_active, total_att_rec)
elif selected_metric == "Attrition Rate (%)":
    overall_n = total_emps
else:
    overall_n = total_active

if overall_n < MIN_GROUP_SIZE:
    st.error(
        f"🛡️ **Privacy Protection Triggered:** The selected filter combination matches fewer than "
        f"**{MIN_GROUP_SIZE} employees**. To prevent individual identification or pay disclosure, "
        f"all metrics for this slice are hidden. Broaden your filters or roll up to a higher level."
    )
    st.stop()

# Anti-differencing guard: block filter slices that leave a tiny remainder (1..4 people)
# inside the parent scope, which would let a user subtract to expose those 1-4 people.
if active_role in ("ADMIN", "HR"):
    if selected_dept != "All Departments":
        parent_df = scoped_df[scoped_df["department_name"] == selected_dept]
        parent_label = selected_dept
    else:
        parent_df = scoped_df
        parent_label = "PulseIQ Corp"
    parent_n = int(parent_df["active_headcount"].sum())
    remainder_n = parent_n - total_active
    if 0 < remainder_n < MIN_GROUP_SIZE:
        st.error(
            f"🛡️ **Anti-Differencing Protection Triggered:** Filtering to this slice leaves "
            f"fewer than **{MIN_GROUP_SIZE} employees** in the rest of **{parent_label}**. "
            "Showing this slice alongside the parent total would allow back-calculating "
            "those individuals' metrics, so this view is blocked."
        )
        st.stop()
elif active_role == "MANAGER":
    parent_n = int(scoped_df["active_headcount"].sum())
    remainder_n = parent_n - total_active
    if 0 < remainder_n < MIN_GROUP_SIZE:
        st.error(
            f"🛡️ **Anti-Differencing Protection Triggered:** This filter leaves fewer than "
            f"**{MIN_GROUP_SIZE} employees** in the rest of **{manager_team}**. "
            "To prevent back-calculating excluded teammates' metrics, this slice is blocked."
        )
        st.stop()

# -------------------------------------------------------------------
# 7. Group-Level Aggregation & Privacy Enforcement
# -------------------------------------------------------------------
level_col = LEVEL_COL_MAP[selected_level]
dim_col = DIMENSION_MAP[selected_dim_label]
group_cols = [level_col] + ([dim_col] if dim_col else [])

visible_df, hidden_count, complementary_applied = aggregate_and_suppress(
    filtered_df, group_cols, selected_metric
)

# Headline KPIs (only shown when overall slice is >= MIN_GROUP_SIZE and passes anti-differencing)
overall_df, _, _ = aggregate_and_suppress(filtered_df, ["company"], selected_metric)
overall_val = float(overall_df["metric_value"].iloc[0]) if not overall_df.empty else 0.0

k1, k2, k3 = st.columns(3)
k1.metric(f"Selected Scope — {selected_metric}", format_metric_value(selected_metric, overall_val))
k2.metric("Visible Groups (n ≥ 5)", f"{len(visible_df):,}")
k3.metric("Suppressed Groups (n < 5)", f"{hidden_count:,}")

if hidden_count > 0:
    msg = (
        f"🛡️ **{hidden_count} group(s) hidden** because they contain fewer than "
        f"**{MIN_GROUP_SIZE} employees**."
    )
    if complementary_applied:
        msg += (
            " *(Includes complementary suppression of the next smallest group so hidden "
            "values cannot be back-calculated from the total.)*"
        )
    st.warning(msg)

if visible_df.empty:
    st.error(
        f"🛡️ **All breakdown groups suppressed:** Every group at the **{selected_level}**"
        f"{' × ' + selected_dim_label if dim_col else ''} level has fewer than {MIN_GROUP_SIZE} "
        "employees. Try rolling up to a higher level or removing the breakdown dimension."
    )
    st.stop()

# -------------------------------------------------------------------
# 8. Visualization & Safe Data Table
# -------------------------------------------------------------------
display_df = visible_df.copy()
if dim_col:
    display_df["Group"] = display_df[level_col].astype(str) + " | " + display_df[dim_col].astype(str)
else:
    display_df["Group"] = display_df[level_col].astype(str)

display_df = display_df.sort_values("metric_value", ascending=False)

st.subheader(f"{selected_metric} by {selected_level}" + (f" × {selected_dim_label}" if dim_col else ""))
chart_df = display_df.set_index("Group")[["metric_value"]].rename(columns={"metric_value": selected_metric})
st.bar_chart(chart_df)

# Safe table (never show raw counts < 5 or duplicate Active Headcount columns)
if selected_metric == "Active Headcount":
    table_cols = group_cols + ["active_headcount"]
else:
    table_cols = group_cols + ["active_headcount", "metric_value"]

rename_map = {
    "company": "Company",
    "department_name": "Department",
    "team_name": "Team",
    "work_location": "Work Location",
    "work_mode": "Work Mode",
    "job_level": "Job Level",
    "active_headcount": "Active Headcount",
    "metric_value": selected_metric,
}
st.dataframe(
    display_df[table_cols].rename(columns=rename_map),
    use_container_width=True,
    hide_index=True,
)