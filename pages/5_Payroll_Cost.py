from db_utils import get_connection
import streamlit as st
import duckdb
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Payroll Cost & Reconciliation", layout="wide")

CHART_CONFIG = {
    'displaylogo': False,
    'modeBarButtonsToRemove': ['zoom2d', 'pan2d', 'select2d', 'lasso2d', 'zoomIn2d', 'zoomOut2d', 'autoScale2d', 'hoverClosestCartesian', 'hoverCompareCartesian', 'hoverClosestPie']
}
COLORS = ['#3B82F6', '#10B981', '#6366F1', '#F59E0B']

@st.cache_data
def load_payroll_data():
    con = get_connection()
    
    con.execute("""
        CREATE OR REPLACE VIEW metrics.vw_app_payroll AS
        SELECT
            p.*,
            d.department_name
        FROM metrics.vw_payroll_monthly p
        LEFT JOIN raw.dim_department d ON p.department_id = d.department_id
    """)
    
    df = con.execute("SELECT * FROM metrics.vw_app_payroll").df()
    con.close()
    
    df['date'] = pd.to_datetime(df['date_key'].astype(str), format='%Y%m%d', errors='coerce')
    df['cost_per_employee'] = df['total_employer_cost'] / df['employees_paid']
    
    return df.sort_values('date')

st.title("Payroll Cost Dashboard")

try:
    df = load_payroll_data()
except Exception as e:
    st.error(f"Error loading data: {e}. Did you run task9_metrics.py?")
    st.stop()

# --- FILTERS ---
valid_depts = df['department_name'].dropna().unique().tolist()
selected_dept = st.sidebar.multiselect("Select Department", options=valid_depts, default=valid_depts)

filt_df = df[df['department_name'].isin(selected_dept)]

if filt_df.empty:
    st.warning("No data available for the selected filters.")
    st.stop()

# --- KPI CARDS ---
total_gross = filt_df['total_gross_pay'].sum()
total_net = filt_df['total_net_pay'].sum()
total_employer = filt_df['total_employer_cost'].sum()
avg_cost_per_emp = filt_df['total_employer_cost'].sum() / filt_df['employees_paid'].sum() if filt_df['employees_paid'].sum() > 0 else 0

st.markdown("### Aggregated Cost Totals")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Gross Pay", f"${total_gross:,.0f}")
col2.metric("Net Pay", f"${total_net:,.0f}")
col3.metric("Total Employer Cost", f"${total_employer:,.0f}")
col4.metric("Avg Cost per Employee", f"${avg_cost_per_emp:,.0f}")
st.markdown("---")

# --- CHARTS ---
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("Employer Cost Trend Over Time")
    trend_df = filt_df.groupby('date')['total_employer_cost'].sum().reset_index()
    fig_trend = px.line(trend_df, x='date', y='total_employer_cost', markers=True, color_discrete_sequence=[COLORS[0]])
    fig_trend.update_layout(xaxis_title="Month", yaxis_title="Total Employer Cost ($)")
    st.plotly_chart(fig_trend, use_container_width=True, config=CHART_CONFIG)

with col_right:
    st.subheader("Cost per Employee by Department")
    # Using the most recent month for an accurate current cross-section
    latest_month = filt_df['date'].max()
    recent_df = filt_df[filt_df['date'] == latest_month]
    
    fig_bar = px.bar(recent_df, x='cost_per_employee', y='department_name', orientation='h', color_discrete_sequence=[COLORS[1]])
    fig_bar.update_layout(yaxis={'categoryorder':'total ascending'}, xaxis_title="Cost per Employee ($)", yaxis_title="")
    st.plotly_chart(fig_bar, use_container_width=True, config=CHART_CONFIG)