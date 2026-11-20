from db_utils import get_connection
import streamlit as st
import duckdb
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Profit & Loss", layout="wide")

@st.cache_data
def load_financial_data():
    con = get_connection()
    df_pl = con.execute("SELECT * FROM metrics.vw_pl_monthly ORDER BY month_key").df()
    df_cat = con.execute("SELECT * FROM metrics.vw_expense_by_category").df()
    df_ven = con.execute("SELECT * FROM metrics.vw_top_vendors").df()
    con.close()
    
    # Format dates
    df_pl['Month'] = pd.to_datetime(df_pl['month_key'], format='%Y%m').dt.strftime('%B %Y')
    df_cat['Month'] = pd.to_datetime(df_cat['month_key'], format='%Y%m').dt.strftime('%B %Y')
    return df_pl, df_cat, df_ven

st.title("Profit & Loss Analytics")

try:
    df_pl, df_cat, df_ven = load_financial_data()
except Exception as e:
    st.error(f"Data loading error: {e}")
    st.stop()

# --- FILTERS ---
valid_months = df_pl['Month'].unique().tolist()
selected_month = st.selectbox("Select Month for Detail View", options=valid_months, index=len(valid_months)-1)

# --- MONTHLY KPI CARDS ---
month_data = df_pl[df_pl['Month'] == selected_month]
if not month_data.empty:
    col1, col2, col3, col4 = st.columns(4)
    rev = month_data['total_revenue'].values[0]
    exp = month_data['total_expense'].values[0]
    mar = month_data['margin'].values[0]
    mar_pct = (mar / rev * 100) if rev > 0 else 0
    
    col1.metric("Revenue", f"${rev:,.0f}")
    col2.metric("Expenses", f"${exp:,.0f}")
    col3.metric("Net Margin", f"${mar:,.0f}")
    col4.metric("Margin %", f"{mar_pct:.1f}%")

st.markdown("---")

# --- CHARTS ---
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("Revenue vs Expenses Over Time")
    fig_trend = px.line(df_pl, x='Month', y=['total_revenue', 'total_expense'], 
                        labels={'value': 'Amount ($)', 'variable': 'Category'},
                        color_discrete_map={'total_revenue': '#10B981', 'total_expense': '#EF4444'})
    st.plotly_chart(fig_trend, use_container_width=True)

with col_right:
    st.subheader("Top 10 Vendors (All Time)")
    fig_ven = px.bar(df_ven, x='total_spend', y='vendor_name', orientation='h',
                     labels={'total_spend': 'Total Spend ($)', 'vendor_name': 'Vendor'})
    fig_ven.update_layout(yaxis={'categoryorder':'total ascending'})
    st.plotly_chart(fig_ven, use_container_width=True)

st.markdown("---")

# --- EXPENSE CATEGORIES TABLE ---
st.subheader(f"Expense Breakdown by Category ({selected_month})")
month_cat_data = df_cat[df_cat['Month'] == selected_month].copy()
month_cat_data = month_cat_data.sort_values(by='total_spend', ascending=False)

st.dataframe(
    month_cat_data[['category', 'total_spend']].rename(columns={'category': 'Expense Category', 'total_spend': 'Amount ($)'}),
    use_container_width=True,
    hide_index=True
)