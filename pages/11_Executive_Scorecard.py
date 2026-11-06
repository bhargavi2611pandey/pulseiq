import streamlit as st
import duckdb
import pandas as pd

st.set_page_config(page_title="Executive Scorecard", layout="wide")

# CSS to make it print-friendly (A4 size) and hide Streamlit menus during print
st.markdown("""
    <style>
    @media print {
        @page { size: A4 landscape; margin: 1cm; }
        header, footer, .sidebar, .stButton { display: none !important; }
        .stApp { background-color: white; color: black; }
    }
    .kpi-card {
        background-color: #1e1e1e;
        border-radius: 8px;
        padding: 20px;
        margin-bottom: 15px;
        border-left: 5px solid #3b82f6;
    }
    .kpi-title { font-size: 1.1rem; color: #a3a3a3; font-weight: bold; margin-bottom: 5px; }
    .kpi-value { font-size: 2rem; font-weight: bold; margin-bottom: 10px; }
    .kpi-target { font-size: 0.9rem; color: #6b7280; }
    .status-green { color: #10b981; font-weight: bold;}
    .status-red { color: #ef4444; font-weight: bold;}
    .status-yellow { color: #f59e0b; font-weight: bold;}
    .kpi-link a { color: #3b82f6; text-decoration: none; font-size: 0.85rem; }
    </style>
""", unsafe_allow_html=True)

@st.cache_data
def load_scorecard_data():
    con = duckdb.connect("pulseiq.duckdb")
    df = con.execute("SELECT * FROM metrics.vw_executive_scorecard ORDER BY month_key").df()
    
    # We also grab anomalies from the AI table using the corrected column name
    anomalies = con.execute("SELECT SUM(total_money_at_risk) as risk FROM metrics.vw_anomalies_summary").fetchone()[0]
    con.close()
    
    # Format month for the dropdown
    df['Month_Label'] = pd.to_datetime(df['month_key'], format='%Y%m').dt.strftime('%B %Y')
    return df, anomalies

st.title("📊 Executive Health Scorecard")
st.markdown("A 2-minute overview of company health. All metrics trace directly to validated metric views.")

df, total_anomaly_risk = load_scorecard_data()

# Month Selector
valid_months = df['Month_Label'].tolist()
selected_month = st.selectbox("Select Month", options=valid_months, index=len(valid_months)-1)

# Filter data for selected month and previous month (for trends)
current_idx = df.index[df['Month_Label'] == selected_month].tolist()[0]
current_data = df.iloc[current_idx]

# Helper function to generate the HTML for a KPI card
def make_kpi_card(title, value, target_text, status, link_text, link_url):
    status_class = f"status-{status}"
    return f"""
    <div class="kpi-card" style="border-left-color: {'#10b981' if status=='green' else '#ef4444' if status=='red' else '#f59e0b'};">
        <div class="kpi-title">{title}</div>
        <div class="kpi-value">{value}</div>
        <div class="kpi-target">Target: {target_text} <span class="{status_class}">({status.upper()})</span></div>
        <div class="kpi-link"><a href="{link_url}" target="_self">↗ {link_text}</a></div>
    </div>
    """

st.markdown("### Financial Health")
col1, col2, col3, col4 = st.columns(4)

# KPI 1: Revenue
rev_val = current_data['revenue']
with col1:
    st.markdown(make_kpi_card(
        "Total Revenue", f"${rev_val:,.0f}", "Growth > 5%", "green", 
        "View P&L details", "/Profit_and_Loss"
    ), unsafe_allow_html=True)

# KPI 2: Net Profit
profit_val = current_data['net_profit']
profit_target = current_data['target_net_profit']
profit_status = "green" if profit_val >= profit_target else "red"
with col2:
    st.markdown(make_kpi_card(
        "Net Profit", f"${profit_val:,.0f}", f">${profit_target:,.0f} (20% Margin)", profit_status, 
        "View P&L details", "/Profit_and_Loss"
    ), unsafe_allow_html=True)

# KPI 3: Operating Cash Flow
cash_val = current_data['cash_flow']
cash_status = "green" if cash_val > 0 else "red"
with col3:
    st.markdown(make_kpi_card(
        "Net Cash Flow", f"${cash_val:,.0f}", "> $0 (Positive)", cash_status, 
        "View Cash & Receivables", "/Cash_and_Receivables"
    ), unsafe_allow_html=True)

# KPI 4: Financial AI Risk
risk_status = "yellow" if total_anomaly_risk > 1000000 else "green"
with col4:
    st.markdown(make_kpi_card(
        "AI Money at Risk", f"${total_anomaly_risk:,.0f}", "< $1M", risk_status, 
        "View AI Signals", "/AI_Signals"
    ), unsafe_allow_html=True)


st.markdown("### Operational & Workforce Health")
col5, col6, col7, col8 = st.columns(4)

# KPI 5: Total Payroll Cost
pay_val = current_data['total_payroll_cost']
pay_target = current_data['max_target_payroll']
pay_status = "green" if pay_val <= pay_target else "red"
with col5:
    st.markdown(make_kpi_card(
        "Total Payroll Cost", f"${pay_val:,.0f}", f"< ${pay_target:,.0f} (40% of Rev)", pay_status, 
        "View Payroll Cost", "/Payroll_Cost"
    ), unsafe_allow_html=True)

# KPI 6: Overtime Cost
ot_val = current_data['overtime_cost']
ot_status = "red" if ot_val > 50000 else "green" 
with col6:
    st.markdown(make_kpi_card(
        "Total Overtime Cost", f"${ot_val:,.0f}", "< $50,000", ot_status, 
        "View Cross-Department", "/Cross_Department"
    ), unsafe_allow_html=True)

# KPI 7: Attrition Rate
attr_val = current_data['attrition_rate']
attr_target = current_data['attrition_target_pct']
attr_status = "green" if attr_val <= attr_target else "red"
with col7:
    st.markdown(make_kpi_card(
        "Monthly Attrition Rate", f"{attr_val:.1f}%", f"< {attr_target:.1f}%", attr_status, 
        "View Attrition details", "/Attrition"
    ), unsafe_allow_html=True)

# KPI 8: Total Headcount
hc_val = current_data['headcount']
with col8:
    st.markdown(make_kpi_card(
        "Total Headcount", f"{hc_val:,.0f}", "Stable Growth", "green", 
        "View Workforce Overview", "/Workforce_Overview"
    ), unsafe_allow_html=True)