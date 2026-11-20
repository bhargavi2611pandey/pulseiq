from db_utils import get_connection
import streamlit as st
import duckdb
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Cash & Receivables", layout="wide")

@st.cache_data
def load_cash_data():
    con = get_connection()
    df_ageing = con.execute("SELECT * FROM metrics.vw_receivables_ageing").df()
    df_days = con.execute("SELECT * FROM metrics.vw_client_days_to_pay").df()
    df_cash = con.execute("SELECT * FROM metrics.vw_cash_flow ORDER BY month_key").df()
    df_overdue = con.execute("SELECT * FROM metrics.vw_top_overdue_clients").df()
    con.close()
    
    df_cash['Month'] = pd.to_datetime(df_cash['month_key'], format='%Y%m').dt.strftime('%b %Y')
    return df_ageing, df_days, df_cash, df_overdue

st.title("Cash Flow & Receivables")

# Required by Task Checklist: Explicitly write the open statuses on the page
st.info("📌 **Active Rule Applied:** 'Open' accounts receivable are strictly defined as invoices with statuses of **SENT, OVERDUE, or PARTIALLY_PAID**.")

df_ageing, df_days, df_cash, df_overdue = load_cash_data()

# --- TOP ROW: KPI CARDS ---
total_overdue = df_overdue['total_overdue'].sum() if not df_overdue.empty else 0
total_open = df_ageing['total_balance'].sum() if not df_ageing.empty else 0

col1, col2, col3 = st.columns(3)
col1.metric("Total Open Receivables", f"${total_open:,.0f}")
col2.metric("Money Currently Overdue", f"${total_overdue:,.0f}")
col3.metric("Slowest Payer (Avg Days)", f"{df_days['avg_days_to_pay'].max():.0f} Days")

st.markdown("---")

# --- ROW 2: AGEING AND OVERDUE CLIENTS ---
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("Accounts Receivable Ageing Buckets")
    fig_ageing = px.bar(df_ageing, x='ageing_bucket', y='total_balance',
                        labels={'ageing_bucket': 'Age Bucket', 'total_balance': 'Balance ($)'},
                        color='ageing_bucket',
                        category_orders={"ageing_bucket": ["Current (Not Due)", "0-30 Days", "31-60 Days", "61-90 Days", "90+ Days"]})
    st.plotly_chart(fig_ageing, use_container_width=True)

with col_right:
    st.subheader("Highest Overdue Balances (Priority Collection List)")
    st.dataframe(
        df_overdue.rename(columns={'client_name': 'Client Name', 'total_overdue': 'Overdue Amount ($)'}),
        use_container_width=True,
        hide_index=True
    )

st.markdown("---")

# --- ROW 3: CASH FLOW & SLOW PAYERS ---
col_bottom1, col_bottom2 = st.columns(2)

with col_bottom1:
    st.subheader("Cash In vs. Cash Out (Liquidity)")
    fig_cash = px.line(df_cash, x='Month', y=['cash_in', 'cash_out'], 
                       labels={'value': 'Amount ($)', 'variable': 'Cash Direction'},
                       color_discrete_map={'cash_in': '#10B981', 'cash_out': '#EF4444'})
    st.plotly_chart(fig_cash, use_container_width=True)

with col_bottom2:
    st.subheader("Slowest Paying Clients (Avg Days to Pay)")
    slow_payers = df_days.head(10).copy()
    fig_slow = px.bar(slow_payers, x='avg_days_to_pay', y='client_name', orientation='h',
                      labels={'avg_days_to_pay': 'Average Days to Pay', 'client_name': 'Client'})
    fig_slow.update_layout(yaxis={'categoryorder':'total ascending'})
    st.plotly_chart(fig_slow, use_container_width=True)