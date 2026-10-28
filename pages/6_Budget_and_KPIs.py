import streamlit as st
import duckdb
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Budget vs Actual & KPIs", layout="wide")

@st.cache_data
def load_data():
    con = duckdb.connect("pulseiq.duckdb")
    df_budget = con.execute("SELECT * FROM metrics.vw_budget_variance WHERE budget_cost IS NOT NULL").df()
    df_kpi = con.execute("SELECT * FROM metrics.vw_kpi_targets").df()
    con.close()
    
    df_budget['date'] = pd.to_datetime(df_budget['date_key'].astype(str), format='%Y%m%d', errors='coerce')
    return df_budget, df_kpi

st.title("Budget vs Actual & KPI Targets")

# Explicit Sign Rule
st.info("""
**Variance Sign Rule:** `Variance = Budget - Actual`
* **Positive Number (🟢)**: Favorable / Under Budget. The department spent less than allocated.
* **Negative Number (🔴/🟡)**: Unfavorable / Overspend. The department spent more than allocated.
""")

try:
    df_budget, df_kpi = load_data()
except Exception as e:
    st.error(f"Error loading data: {e}. Did you run task10_metrics.py?")
    st.stop()

# --- FILTERS ---
valid_months = df_budget['date'].dt.strftime('%Y-%m').unique().tolist()
selected_month = st.selectbox("Select Month", options=sorted(valid_months, reverse=True))

filt_budget = df_budget[df_budget['date'].dt.strftime('%Y-%m') == selected_month]

# --- RANKING DEPARTMENTS BY OVERSPEND ---
st.header(f"Department Payroll Variance ({selected_month})")

# Sort by variance_amount ascending (most negative = highest overspend)
ranked_budget = filt_budget.sort_values(by='variance_amount', ascending=True)

# Display Table
st.dataframe(
    ranked_budget[['department_name', 'budget_cost', 'actual_cost', 'variance_amount', 'variance_pct', 'budget_status']]
    .rename(columns={
        'department_name': 'Department', 
        'budget_cost': 'Budget ($)', 
        'actual_cost': 'Actual ($)', 
        'variance_amount': 'Variance ($)', 
        'variance_pct': 'Variance (%)',
        'budget_status': 'Status'
    }),
    use_container_width=True,
    hide_index=True
)

# --- VISUALIZATION ---
st.subheader("Variance by Department")
fig = px.bar(
    ranked_budget, 
    x='variance_amount', 
    y='department_name', 
    orientation='h',
    color='variance_amount',
    color_continuous_scale=['red', 'orange', 'green'],
    title="Favorable vs Unfavorable Variance"
)
fig.update_layout(xaxis_title="Variance ($) - Negative is Overspend", yaxis_title="")
st.plotly_chart(fig, use_container_width=True)

# --- KPI TARGETS REFERENCE ---
st.markdown("---")
st.header("KPI Target References")
st.write("Current benchmark targets for organizational health tracking:")
st.dataframe(df_kpi.head(10), use_container_width=True, hide_index=True)