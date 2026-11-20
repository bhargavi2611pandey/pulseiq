from db_utils import get_connection
import streamlit as st
import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="Cross-Department Impact", layout="wide")

@st.cache_data
def load_unified_data():
    con = get_connection()
    df = con.execute("SELECT * FROM metrics.vw_department_unified").df()
    con.close()
    
    df['Month'] = pd.to_datetime(df['month_key'], format='%Y%m').dt.strftime('%B %Y')
    return df

st.title("Cross-Department Impact View")
st.markdown("Analyzing the relationship between **Overtime, Attrition, and Cost**.")

df = load_unified_data()

# --- AGGREGATE FOR THE CHART ---
# We aggregate the metrics across all months to show department health
dept_agg = df.groupby('department_name').agg(
    total_overtime_pay=('total_overtime_pay', 'sum'),
    total_attritions=('attritions', 'sum'),
    avg_leave_per_head=('leave_days_per_head', 'mean')
).reset_index()

# --- THE UNIFIED CHART ---
st.subheader("Department Comparison: Overtime Cost vs. Attrition")

# Plotly dual-axis chart
fig = go.Figure()

# Bar Chart for Overtime
fig.add_trace(go.Bar(
    x=dept_agg['department_name'],
    y=dept_agg['total_overtime_pay'],
    name='Total Overtime Cost ($)',
    marker_color='#3b82f6',
    yaxis='y1'
))

# Line Chart for Attrition
fig.add_trace(go.Line(
    x=dept_agg['department_name'],
    y=dept_agg['total_attritions'],
    name='Total Attritions',
    mode='lines+markers',
    marker=dict(color='#ef4444', size=10),
    line=dict(color='#ef4444', width=3),
    yaxis='y2'
))

fig.update_layout(
    xaxis=dict(title='Department'),
    yaxis=dict(title='Overtime Cost ($)', side='left', showgrid=False),
    yaxis2=dict(title='Total Attritions', side='right', overlaying='y', showgrid=False),
    legend=dict(x=0.01, y=0.99),
    plot_bgcolor='rgba(0,0,0,0)',
    paper_bgcolor='rgba(0,0,0,0)'
)

st.plotly_chart(fig, use_container_width=True)

st.markdown("---")

# --- DATA TABLE FOR RECONCILIATION ---
st.subheader("Unified Department Grain Table (For Vault Reconciliation)")
valid_months = df['Month'].unique().tolist()
selected_month = st.selectbox("Select Month to Inspect", options=valid_months, index=len(valid_months)-1)

display_df = df[df['Month'] == selected_month].copy()
st.dataframe(
    display_df[['department_name', 'headcount', 'total_employer_cost', 'total_overtime_pay', 'leave_days_per_head', 'attritions']],
    use_container_width=True,
    hide_index=True
)