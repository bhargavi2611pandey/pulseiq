from db_utils import get_connection
import streamlit as st
import duckdb
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Attendance & Leave", layout="wide")

COLORS = ['#1E3A8A', '#10B981', '#9CA3AF', '#F59E0B']

# Clean up the Plotly toolbar: keep only Download (Camera) and Reset (Home)
CHART_CONFIG = {
    'displaylogo': False,
    'modeBarButtonsToRemove': ['zoom2d', 'pan2d', 'select2d', 'lasso2d', 'zoomIn2d', 'zoomOut2d', 'autoScale2d', 'hoverClosestCartesian', 'hoverCompareCartesian', 'hoverClosestPie']
}

@st.cache_data
def load_attendance_data():
    con = get_connection() 
    
    # Join attendance metrics with department names
    con.execute("""
        CREATE OR REPLACE VIEW metrics.vw_app_attendance AS 
        SELECT 
            a.department_id,
            d.department_name,
            a.date_key,
            a.attendance_rate_pct,
            a.total_late_arrivals,
            a.total_overtime_hours
        FROM metrics.vw_attendance a
        LEFT JOIN warehouse.dim_department d ON a.department_id = d.department_id
    """)
    
    # Join leave metrics with department names
    con.execute("""
        CREATE OR REPLACE VIEW metrics.vw_app_leave AS 
        SELECT 
            l.department_id,
            d.department_name,
            l.date_key,
            l.leave_type,
            l.total_leave_days
        FROM metrics.vw_leave l
        LEFT JOIN warehouse.dim_department d ON l.department_id = d.department_id
    """)
    
    df_att = con.execute("SELECT * FROM metrics.vw_app_attendance").df()
    df_leave = con.execute("SELECT * FROM metrics.vw_app_leave").df()
    con.close()
    
    df_att['date'] = pd.to_datetime(df_att['date_key'].astype(str), format='%Y%m%d', errors='coerce')
    df_leave['date'] = pd.to_datetime(df_leave['date_key'].astype(str), format='%Y%m%d', errors='coerce')
    
    return df_att, df_leave

st.title("Attendance & Leave Trends")

try:
    df_att, df_leave = load_attendance_data()
except Exception as e:
    st.error(f"Error loading data: {e}. Did you run task6_metrics.py?")
    st.stop()

# --- FILTERS ---
st.sidebar.header("Filters")
# Drop NA to avoid multiselect errors if any records lack a department name
valid_depts = df_att['department_name'].dropna().unique()
selected_dept = st.sidebar.multiselect("Select Department", options=valid_depts, default=valid_depts)

filt_att = df_att[df_att['department_name'].isin(selected_dept)]
filt_leave = df_leave[df_leave['department_name'].isin(selected_dept)]

if filt_att.empty:
    st.warning("No data available for the selected filters.")
    st.stop()

# --- KPI CARDS ---
latest_date = filt_att['date'].max()
latest_att = filt_att[filt_att['date'] == latest_date]

avg_att_rate = latest_att['attendance_rate_pct'].mean()
total_overtime = latest_att['total_overtime_hours'].sum()
total_late = latest_att['total_late_arrivals'].sum()

col1, col2, col3 = st.columns(3)
col1.metric("Avg Attendance Rate", f"{avg_att_rate:.1f}%")
col2.metric("Monthly Overtime (Hours)", f"{total_overtime:,.0f}")
col3.metric("Late Arrivals", f"{total_late:,.0f}")
st.markdown("---")

# --- CHARTS ---
# 1. Attendance Trend with Holidays
st.subheader("Attendance dips predictably during winter holidays")
trend_df = filt_att.groupby('date')['attendance_rate_pct'].mean().reset_index()
fig_trend = px.line(trend_df, x='date', y='attendance_rate_pct', color_discrete_sequence=[COLORS[0]])
fig_trend.update_layout(xaxis_title="", yaxis_title="Attendance Rate (%)", showlegend=False)

# Mark Holidays
fig_trend.add_vline(x='2025-12-15', line_dash="dash", line_color=COLORS[2], annotation_text="Winter Holidays (Dec)", annotation_position="bottom right")
fig_trend.add_vline(x='2025-11-15', line_dash="dash", line_color=COLORS[2], annotation_text="Thanksgiving (Nov)", annotation_position="top left")

# Applied config here
st.plotly_chart(fig_trend, use_container_width=True, config=CHART_CONFIG)

col_left, col_right = st.columns(2)

# 2. Overtime by Department
with col_left:
    st.subheader("Engineering relies on high overtime to meet targets")
    ot_df = filt_att.groupby('department_name')['total_overtime_hours'].sum().reset_index()
    fig_ot = px.bar(ot_df, x='total_overtime_hours', y='department_name', orientation='h', color_discrete_sequence=[COLORS[1]])
    fig_ot.update_layout(yaxis={'categoryorder':'total ascending'}, xaxis_title="Total Overtime Hours", yaxis_title="")
    
    # Applied config here
    st.plotly_chart(fig_ot, use_container_width=True, config=CHART_CONFIG)

# 3. Leave by Type
with col_right:
    st.subheader("Paid Time Off (PTO) accounts for the majority of absences")
    leave_df = filt_leave.groupby('leave_type')['total_leave_days'].sum().reset_index()
    
    # Map the abbreviations to their full HR definitions
    leave_mapping = {
        'EL': 'Earned Leave',
        'SL': 'Sick Leave',
        'CL': 'Casual Leave'
    }
    leave_df['leave_type_full'] = leave_df['leave_type'].map(leave_mapping).fillna(leave_df['leave_type'])
    
    fig_leave = px.pie(leave_df, names='leave_type_full', values='total_leave_days', hole=0.4, color_discrete_sequence=COLORS)
    fig_leave.update_layout(legend=dict(orientation="v", yanchor="top", y=1, xanchor="left", x=1.05))
    
    # Applied config here
    st.plotly_chart(fig_leave, use_container_width=True, config=CHART_CONFIG)