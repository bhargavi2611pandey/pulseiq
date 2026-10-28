import streamlit as st
import duckdb
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Team Productivity", layout="wide")

CHART_CONFIG = {
    'displaylogo': False,
    'modeBarButtonsToRemove': ['zoom2d', 'pan2d', 'select2d', 'lasso2d', 'zoomIn2d', 'zoomOut2d', 'autoScale2d', 'hoverClosestCartesian', 'hoverCompareCartesian', 'hoverClosestPie']
}

@st.cache_data
def load_team_data():
    con = duckdb.connect("pulseiq.duckdb")
    
    con.execute("""
        CREATE OR REPLACE VIEW metrics.vw_app_team_productivity AS
        SELECT
            m.*,
            t.team_name,
            s.sprint_name,
            s.start_date
        FROM metrics.vw_team_sprint_metrics m
        LEFT JOIN raw.dim_team t ON m.team_id = t.team_id
        LEFT JOIN raw.dim_sprint s ON m.sprint_id = s.sprint_id
    """)
    
    df = con.execute("SELECT * FROM metrics.vw_app_team_productivity").df()
    con.close()
    
    # Sort sprints chronologically
    df['start_date'] = pd.to_datetime(df['start_date'], errors='coerce')
    df = df.sort_values(by=['start_date', 'sprint_id'])
    return df

st.title("Team Productivity Dashboard")

st.info("""
**Metric Rules & Definitions:**
- **Velocity:** Total story points of tasks successfully marked 'Done' in a sprint.
- **Cycle Time:** Average days from 'Started' to 'Done'.
- **On-Time Rate:** Percentage of completed tasks finished on or before their due date.
- **Cancelled Tasks:** Ignored entirely in velocity and cycle time calculations to maintain fair baseline comparisons between teams.
""")

try:
    df = load_team_data()
except Exception as e:
    st.error(f"Error loading data: {e}. Did you run task8_metrics.py?")
    st.stop()

# --- FILTERS ---
st.sidebar.header("Filters")
valid_teams = df['team_name'].dropna().unique().tolist()
valid_sprints = df['sprint_name'].dropna().unique().tolist()

# Default to a few teams to prevent a messy chart on first load
selected_teams = st.sidebar.multiselect("Select Team", options=valid_teams, default=valid_teams[:4] if len(valid_teams) >= 4 else valid_teams)
selected_sprints = st.sidebar.multiselect("Select Sprint", options=valid_sprints, default=valid_sprints)

filt_df = df[(df['team_name'].isin(selected_teams)) & (df['sprint_name'].isin(selected_sprints))]

if filt_df.empty:
    st.warning("No data available for the selected filters.")
    st.stop()

# --- KPI CARDS ---
st.markdown("### Aggregate Performance (Selected Filters)")
col1, col2, col3, col4 = st.columns(4)

total_vel = filt_df['velocity'].sum()
avg_cyc = filt_df['avg_cycle_time_days'].mean()
tot_comp = filt_df['completed_tasks'].sum()
tot_on_time = filt_df['on_time_tasks'].sum()

on_time_rate = (tot_on_time / tot_comp * 100) if tot_comp > 0 else 0
tot_blocked = filt_df['blocked_tasks'].sum()
tot_reopened = filt_df['reopened_tasks'].sum()

col1.metric("Total Velocity (Story Points)", f"{total_vel:,.0f}")
col2.metric("Avg Cycle Time (Days)", f"{avg_cyc:.1f}")
col3.metric("On-Time Delivery Rate", f"{on_time_rate:.1f}%")
col4.metric("Blocked Tasks", f"{tot_blocked:,.0f}")
st.markdown("---")

# --- CHARTS ---
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("Velocity over Sprints")
    fig_vel = px.line(filt_df, x='sprint_name', y='velocity', color='team_name', markers=True)
    fig_vel.update_layout(xaxis_title="Sprint", yaxis_title="Story Points (Velocity)", legend_title="Team")
    st.plotly_chart(fig_vel, use_container_width=True, config=CHART_CONFIG)

with col_right:
    st.subheader("Quality & Delays: Reopened vs Blocked")
    team_issues = filt_df.groupby('team_name')[['blocked_tasks', 'reopened_tasks']].sum().reset_index()
    team_issues_melted = team_issues.melt(id_vars='team_name', value_vars=['blocked_tasks', 'reopened_tasks'], var_name='Issue Type', value_name='Task Count')
    team_issues_melted['Issue Type'] = team_issues_melted['Issue Type'].replace({'blocked_tasks': 'Blocked', 'reopened_tasks': 'Reopened'})

    fig_issues = px.bar(team_issues_melted, x='team_name', y='Task Count', color='Issue Type', barmode='group',
                        color_discrete_sequence=['#EF4444', '#F59E0B'])
    fig_issues.update_layout(xaxis_title="Team", yaxis_title="Total Tasks", legend_title="")
    st.plotly_chart(fig_issues, use_container_width=True, config=CHART_CONFIG)