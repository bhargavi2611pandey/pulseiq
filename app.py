import streamlit as st
from db_utils import get_connection, get_data_metadata

st.set_page_config(
    page_title="PulseIQ — HR & Finance Analytics",
    page_icon="📊",
    layout="wide",
)

data_cutoff, last_refreshed = get_data_metadata()

# Sidebar status box (always visible on the landing page)
st.sidebar.title("📊 PulseIQ")
st.sidebar.markdown("**Navigation:** Select any page above to explore HR, Payroll, Finance, or AI Signals.")
st.sidebar.divider()
st.sidebar.info(
    f"**Data Cut-off:** {data_cutoff}\n\n"
    f"**Last Refreshed:** {last_refreshed}\n\n"
    f"**Refresh Schedule:** Daily at 06:00 UTC (GitHub Actions)"
)

# Main Landing Page
st.title("📊 PulseIQ — HR & Finance Analytics Suite")
st.caption(f"Live Production Dashboard | Data Cut-off: **{data_cutoff}** | Aggregated Metrics Only (No Raw PII)")

# Headline KPIs directly on the landing page (so a stranger can find Headcount immediately)
try:
    con = get_connection()
    latest = con.execute("""
        SELECT month_key, headcount, revenue, net_profit, cash_flow, attrition_rate
        FROM metrics.vw_executive_scorecard
        ORDER BY month_key DESC
        LIMIT 1
    """).fetchone()
    con.close()

    if latest:
        month_key, headcount, revenue, net_profit, cash_flow, attrition_rate = latest
        st.subheader(f"Latest Snapshot ({month_key})")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Active Headcount", f"{int(headcount):,}")
        c2.metric("Monthly Revenue", f"${revenue:,.0f}")
        c3.metric("Net Profit", f"${net_profit:,.0f}")
        c4.metric("Attrition Rate", f"{attrition_rate:.2f}%")
except Exception as e:
    st.warning(f"Could not load headline snapshot: {e}")

st.divider()

# Quick Navigation Guide
st.subheader("Where to Start")
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown(
        "**People & Workforce**\n"
        "- **1 Workforce Overview:** Headcount & average pay by department\n"
        "- **2 Attendance & Leave:** Presence and leave trends\n"
        "- **3 Attrition:** Monthly turnover & risk indicators\n"
        "- **4 Team Productivity:** Sprint delivery & task metrics"
    )

with col2:
    st.markdown(
        "**Finance & Payroll**\n"
        "- **5 Payroll Cost:** Gross pay & employer cost breakdown\n"
        "- **6 Budget & KPIs:** Budget variance & target tracking\n"
        "- **7 Profit & Loss:** Revenue, expenses & margins\n"
        "- **8 Cash & Receivables:** Cash flow & overdue clients"
    )

with col3:
    st.markdown(
        "**Executive & AI**\n"
        "- **9 Cross Department:** Unified department comparison\n"
        "- **10 AI Signals:** Anomaly detection & forecast accuracy\n"
        "- **11 Executive Scorecard:** Full leadership summary"
    )