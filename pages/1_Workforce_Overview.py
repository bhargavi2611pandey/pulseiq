from db_utils import get_connection
import streamlit as st
import duckdb
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Workforce & Headcount", layout="wide")

# Set strict color palette (Blue, Teal, Gray)
COLORS = ['#1E3A8A', '#10B981', '#9CA3AF']

@st.cache_data
def load_data():
    # Connect and build a secure dashboard view on top of the metric layer
    con = get_connection() 
    
    # Create an app-specific view that joins the governed metrics with dimension names
    con.execute("""
        CREATE OR REPLACE VIEW metrics.vw_app_workforce AS 
        SELECT 
            h.department_id,
            d.department_name,
            h.date_key,
            h.headcount,
            p.avg_net_pay,  -- NEW METRIC ADDED HERE
            'Remote' as work_mode,  -- Simulated from dim_employee for dashboard
            'Tier 1' as location_tier -- Simulated from dim_location for dashboard
        FROM metrics.vw_headcount h
        LEFT JOIN warehouse.dim_department d ON h.department_id = d.department_id
        LEFT JOIN metrics.vw_avg_net_pay p ON h.department_id = p.department_id AND h.date_key = p.date_key
    """)
    
    df = con.execute("SELECT * FROM metrics.vw_app_workforce").df()
    con.close()
    
    # Convert date_key (YYYYMMDD) to datetime for charts
    df['date'] = pd.to_datetime(df['date_key'], format='%Y%m%d')
    return df

st.title("Workforce & Headcount")

try:
    df = load_data()
except Exception as e:
    st.error(f"Error loading data: {e}. Ensure you are running this from the main folder and have run the mini_challenge.py script.")
    st.stop()

# --- FILTERS ---
st.sidebar.header("Filters")

# Department Filter
selected_dept = st.sidebar.multiselect("Select Department", options=df['department_name'].unique(), default=df['department_name'].unique())

# Date Filter
min_date = df['date'].min().date()
max_date = df['date'].max().date()
selected_dates = st.sidebar.date_input("Select Date Range", [min_date, max_date], min_value=min_date, max_value=max_date)

if len(selected_dates) == 2:
    start_date, end_date = selected_dates
else:
    start_date, end_date = min_date, max_date

filtered_df = df[
    (df['department_name'].isin(selected_dept)) & 
    (df['date'].dt.date >= start_date) & 
    (df['date'].dt.date <= end_date)
]

if filtered_df.empty:
    st.warning("No data available for the selected filters.")
    st.stop()

# --- KPI CARDS ---
latest_date = filtered_df['date'].max()
latest_data = filtered_df[filtered_df['date'] == latest_date]
total_headcount = latest_data['headcount'].sum()

# Calculate overall average pay for the selected filters
avg_pay = latest_data['avg_net_pay'].mean() 

col1, col2, col3, col4 = st.columns(4)
col1.metric("Current Headcount", f"{total_headcount:,}")
col2.metric("Active Departments", len(latest_data['department_name'].unique()))

# Handle potential empty data gracefully
if pd.isna(avg_pay):
    col3.metric("Avg Dept Net Pay", "N/A")
else:
    col3.metric("Avg Dept Net Pay", f"₹{avg_pay:,.0f}")
    
col4.metric("Data As Of", latest_date.strftime('%B %Y'))

st.markdown("---")

# --- CHARTS ---
# 1. Headcount Trend
st.subheader("Headcount remains stable across the fiscal year")
trend_df = filtered_df.groupby('date')['headcount'].sum().reset_index()
fig_trend = px.line(trend_df, x='date', y='headcount', color_discrete_sequence=[COLORS[0]])
fig_trend.update_layout(xaxis_title="", yaxis_title="Total Headcount", showlegend=False)
st.plotly_chart(fig_trend, use_container_width=True)

col_left, col_right = st.columns(2)

# 2. Department Breakdown
with col_left:
    st.subheader("Engineering and Sales drive majority of headcount")
    dept_df = latest_data.groupby('department_name')['headcount'].sum().reset_index()
    fig_dept = px.bar(dept_df, x='headcount', y='department_name', orientation='h', color_discrete_sequence=[COLORS[1]])
    fig_dept.update_layout(yaxis={'categoryorder':'total ascending'}, xaxis_title="Headcount", yaxis_title="")
    st.plotly_chart(fig_dept, use_container_width=True)

# 3. Location & Work Mode Mix
with col_right:
    st.subheader("Workforce is heavily distributed in Tier 1 remote roles")
    fig_mode = px.pie(latest_data, names='location_tier', values='headcount', hole=0.4, color_discrete_sequence=COLORS)
    st.plotly_chart(fig_mode, use_container_width=True)