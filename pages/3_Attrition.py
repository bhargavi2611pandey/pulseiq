import streamlit as st
import duckdb
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Attrition Analytics", layout="wide")

COLORS = ['#EF4444', '#F59E0B', '#10B981', '#6B7280'] # Red, Amber, Green, Gray

CHART_CONFIG = {
    'displaylogo': False,
    'modeBarButtonsToRemove': ['zoom2d', 'pan2d', 'select2d', 'lasso2d', 'zoomIn2d', 'zoomOut2d', 'autoScale2d', 'hoverClosestCartesian', 'hoverCompareCartesian', 'hoverClosestPie']
}

@st.cache_data
def load_attrition_data():
    con = duckdb.connect("pulseiq.duckdb")
    
    # Attach department names
    con.execute("""
        CREATE OR REPLACE VIEW metrics.vw_app_attrition AS
        SELECT a.*, d.department_name 
        FROM metrics.vw_attrition_monthly a
        LEFT JOIN warehouse.dim_department d ON a.department_id = d.department_id
    """)
    
    con.execute("""
        CREATE OR REPLACE VIEW metrics.vw_app_risk AS
        SELECT r.*, d.department_name 
        FROM metrics.vw_attrition_risk r
        LEFT JOIN warehouse.dim_department d ON r.department_id = d.department_id
    """)
    
    df_att = con.execute("SELECT * FROM metrics.vw_app_attrition").df()
    df_risk = con.execute("SELECT * FROM metrics.vw_app_risk").df()
    con.close()
    
    df_att['date'] = pd.to_datetime(df_att['date_key'].astype(str), format='%Y%m%d', errors='coerce')
    df_risk['date'] = pd.to_datetime(df_risk['as_of_date_key'].astype(str), format='%Y%m%d', errors='coerce')
    
    return df_att, df_risk

st.title("Attrition Analytics")

try:
    df_att, df_risk = load_attrition_data()
except Exception as e:
    st.error(f"Error loading data: {e}. Did you run task7_metrics.py?")
    st.stop()

# --- FILTERS ---
valid_depts = df_att['department_name'].dropna().unique()
selected_dept = st.sidebar.multiselect("Select Department", options=valid_depts, default=valid_depts)

filt_att = df_att[df_att['department_name'].isin(selected_dept)]
filt_risk = df_risk[df_risk['department_name'].isin(selected_dept)]

if filt_att.empty:
    st.warning("No data available for the selected filters.")
    st.stop()

# --- ACTUAL EXITS SECTION ---
st.header("Historical Exits")

# 1. Trend line of exits
df_trend = filt_att.groupby('date')[['voluntary_exits', 'other_exits']].sum().reset_index()
df_trend_melted = df_trend.melt(id_vars='date', value_vars=['voluntary_exits', 'other_exits'], var_name='Exit Type', value_name='Exits')
df_trend_melted['Exit Type'] = df_trend_melted['Exit Type'].replace({'voluntary_exits': 'Voluntary', 'other_exits': 'Other (Involuntary/End of Contract)'})

# Updated the title to be more descriptive and insightful
fig_trend = px.bar(df_trend_melted, x='date', y='Exits', color='Exit Type', 
                   title="Voluntary Exits Drive the Majority of Historical Turnover",
                   color_discrete_sequence=[COLORS[0], COLORS[3]])

# Added "Timeline (Month/Year)" for the X-axis and kept "Number of Exits" for the Y-axis
fig_trend.update_layout(xaxis_title="Timeline (Month/Year)", yaxis_title="Number of Exits", legend_title="")
st.plotly_chart(fig_trend, use_container_width=True, config=CHART_CONFIG)

# 2. Exits by Department
dept_exits = filt_att.groupby('department_name')[['total_exits']].sum().reset_index()
fig_dept = px.bar(dept_exits, x='total_exits', y='department_name', orientation='h', title="Total Exits by Department", color_discrete_sequence=[COLORS[0]])
fig_dept.update_layout(yaxis={'categoryorder':'total ascending'}, xaxis_title="Total Exits", yaxis_title="")
st.plotly_chart(fig_dept, use_container_width=True, config=CHART_CONFIG)


# --- PREDICTED RISK SECTION ---
st.markdown("---")
st.header("⚠️ Predicted, Not Certain")
st.info("**Important Note:** The predictive data below represents a statistical risk calculation designed to guide proactive retention conversations. It is *not* a guaranteed outcome about any individual. Individual identities are fully suppressed (groups < 5 are hidden) to strictly protect privacy.")

if not filt_risk.empty:
    risk_summary = filt_risk.groupby(['department_name', 'risk_band'])['employees_at_risk'].sum().reset_index()
    
    fig_risk = px.bar(risk_summary, x='employees_at_risk', y='department_name', color='risk_band', orientation='h',
                      title="Predicted Attrition Risk by Group",
                      color_discrete_map={'High': COLORS[0], 'Medium': COLORS[1], 'Low': COLORS[2]})
    fig_risk.update_layout(yaxis={'categoryorder':'total ascending'}, xaxis_title="Number of Employees", yaxis_title="", legend_title="Risk Band")
    st.plotly_chart(fig_risk, use_container_width=True, config=CHART_CONFIG)
else:
    st.warning("No valid predicted risk data available for the current selection.")