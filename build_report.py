import argparse
import calendar
from datetime import datetime
from pathlib import Path
import duckdb
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils.dataframe import dataframe_to_rows
from openpyxl.chart import BarChart, LineChart, Reference


def get_date_range(month_str: str):
    """Return (start_date, end_date, label) for a YYYYMM string."""
    year = int(month_str[:4])
    month = int(month_str[4:6])
    last_day = calendar.monthrange(year, month)[1]
    start_date = f"{year}-{month:02d}-01"
    end_date = f"{year}-{month:02d}-{last_day:02d}"
    label = datetime(year, month, 1).strftime("%B %Y")
    return start_date, end_date, label


def style_header_row(ws, row_idx: int):
    header_fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True)
    for cell in ws[row_idx]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")


def auto_fit_columns(ws):
    for col in ws.columns:
        max_len = max(len(str(cell.value or "")) for cell in col)
        ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 55)


def write_df_to_sheet(ws, df: pd.DataFrame, start_row: int = 1):
    for r_idx, row in enumerate(dataframe_to_rows(df, index=False, header=True), start=start_row):
        for c_idx, val in enumerate(row, start=1):
            ws.cell(row=r_idx, column=c_idx, value=val)
    style_header_row(ws, start_row)
    auto_fit_columns(ws)


def configure_chart(chart, title: str, x_title: str, y_title: str, show_legend: bool = False, width: int = 20, height: int = 12):
    """Apply clean axis titles, visible tick labels, and non-overlapping layout."""
    chart.title = title
    chart.title.overlay = False

    # Force both axes and their tick labels to stay visible
    chart.x_axis.delete = False
    chart.y_axis.delete = False
    chart.x_axis.tickLblPos = "low"
    chart.y_axis.tickLblPos = "low"

    # Set X and Y axis titles cleanly without overlapping the plot
    chart.x_axis.title = x_title
    chart.x_axis.title.overlay = False
    chart.y_axis.title = y_title
    chart.y_axis.title.overlay = False
    chart.y_axis.number_format = "#,##0"

    # Prevent single-series bar charts from putting categories into a rainbow legend
    if hasattr(chart, "varyColors"):
        chart.varyColors = False

    if show_legend:
        chart.legend.position = "b"
        chart.legend.overlay = False
    else:
        chart.legend = None

    chart.width = width
    chart.height = height


def build_report(month_key: str, db_path: str = "pulseiq.duckdb", out_dir: str = "reports"):
    start_date, end_date, month_label = get_date_range(month_key)
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    con = duckdb.connect(db_path, read_only=True)

    # Actual data cut-off from the database
    cutoff_row = con.execute("""
        SELECT MAX(SUBSTRING(CAST(date_key AS VARCHAR), 1, 8))
        FROM raw.fact_payroll
    """).fetchone()
    raw_cutoff = cutoff_row[0] if cutoff_row and cutoff_row[0] else end_date
    data_cutoff = (
        f"{raw_cutoff[:4]}-{raw_cutoff[4:6]}-{raw_cutoff[6:8]}"
        if len(str(raw_cutoff)) == 8 else str(raw_cutoff)
    )

    # 1. Executive Scorecard for selected month
    df_scorecard = con.execute(f"""
        SELECT
            month_key,
            ROUND(revenue, 2) AS revenue,
            ROUND(net_profit, 2) AS net_profit,
            ROUND(cash_flow, 2) AS cash_flow,
            ROUND(total_payroll_cost, 2) AS total_payroll_cost,
            headcount,
            ROUND(attrition_rate, 2) AS attrition_rate_pct
        FROM metrics.vw_executive_scorecard
        WHERE month_key = '{month_key}'
    """).df()

    # 2. P&L Trend (up to selected month)
    df_pl = con.execute(f"""
        SELECT
            SUBSTRING(CAST(month_key AS VARCHAR), 1, 6) AS month,
            ROUND(SUM(total_revenue), 2) AS total_revenue,
            ROUND(SUM(total_expense), 2) AS total_expense,
            ROUND(SUM(margin), 2) AS net_margin
        FROM metrics.vw_pl_monthly
        WHERE SUBSTRING(CAST(month_key AS VARCHAR), 1, 6) <= '{month_key}'
        GROUP BY 1
        ORDER BY 1
    """).df()

    # 3. Cash Flow Trend (up to selected month)
    df_cash = con.execute(f"""
        SELECT
            SUBSTRING(CAST(month_key AS VARCHAR), 1, 6) AS month,
            ROUND(SUM(cash_in), 2) AS cash_in,
            ROUND(SUM(cash_out), 2) AS cash_out,
            ROUND(SUM(net_cash_flow), 2) AS net_cash_flow
        FROM metrics.vw_cash_flow
        WHERE SUBSTRING(CAST(month_key AS VARCHAR), 1, 6) <= '{month_key}'
        GROUP BY 1
        ORDER BY 1
    """).df()

    # 4. Department Payroll (LEFT JOIN so new departments never drop)
    df_dept = con.execute(f"""
        SELECT
            COALESCE(d.department_name, p.department_id) AS department,
            SUM(p.employees_paid) AS employees_paid,
            ROUND(SUM(p.total_gross_pay), 2) AS total_gross_pay,
            ROUND(SUM(p.total_employer_cost), 2) AS total_employer_cost
        FROM metrics.vw_payroll_monthly p
        LEFT JOIN raw.dim_department d ON p.department_id = d.department_id
        WHERE SUBSTRING(CAST(p.date_key AS VARCHAR), 1, 6) = '{month_key}'
        GROUP BY 1
        ORDER BY 4 DESC
    """).df()

    # 5. Top 10 AI Anomalies by Money at Risk
    df_anom = con.execute("""
        SELECT
            anomaly_type,
            total_anomalies,
            ROUND(total_money_at_risk, 2) AS total_money_at_risk
        FROM metrics.vw_anomalies_summary
        ORDER BY total_money_at_risk DESC
        LIMIT 10
    """).df()

    con.close()

    # --- BUILD EXCEL WORKBOOK ---
    wb = Workbook()

    # Sheet 1: Executive Summary + Metadata Stamp
    ws1 = wb.active
    ws1.title = "1_Executive_Summary"
    ws1["A1"] = f"PulseIQ Monthly Management Report — {month_label}"
    ws1["A1"].font = Font(size=16, bold=True, color="1F4E78")

    meta_rows = [
        ("Reporting Month:", month_label),
        ("Report Date Range:", f"{start_date} to {end_date}"),
        ("Database Data Cut-off:", data_cutoff),
        ("Report Generated At:", generated_at),
        ("Data Source:", "pulseiq.duckdb (validated metrics.* views)"),
    ]
    for idx, (label, val) in enumerate(meta_rows, start=3):
        ws1.cell(row=idx, column=1, value=label).font = Font(bold=True)
        ws1.cell(row=idx, column=2, value=val)

    ws1.cell(row=9, column=1, value="Headline KPIs").font = Font(size=12, bold=True)
    if not df_scorecard.empty:
        write_df_to_sheet(ws1, df_scorecard, start_row=10)
    else:
        ws1.cell(row=10, column=1, value=f"No scorecard data available for {month_key}.")

    # Sheet 2: P&L Trend + Line Chart
    ws2 = wb.create_sheet("2_PL_Trend")
    write_df_to_sheet(ws2, df_pl, start_row=1)
    if len(df_pl) > 0:
        chart_pl = LineChart()
        data_ref = Reference(ws2, min_col=2, max_col=4, min_row=1, max_row=len(df_pl) + 1)
        cats_ref = Reference(ws2, min_col=1, min_row=2, max_row=len(df_pl) + 1)
        chart_pl.add_data(data_ref, titles_from_data=True)
        chart_pl.set_categories(cats_ref)
        configure_chart(
            chart_pl,
            title="Monthly Revenue, Expense & Margin",
            x_title="Month (YYYYMM)",
            y_title="Amount ($)",
            show_legend=True,
        )
        ws2.add_chart(chart_pl, "F2")

    # Sheet 3: Cash Flow Trend + Bar Chart
    ws3 = wb.create_sheet("3_Cash_Flow")
    write_df_to_sheet(ws3, df_cash, start_row=1)
    if len(df_cash) > 0:
        chart_cf = BarChart()
        data_ref = Reference(ws3, min_col=4, max_col=4, min_row=1, max_row=len(df_cash) + 1)
        cats_ref = Reference(ws3, min_col=1, min_row=2, max_row=len(df_cash) + 1)
        chart_cf.add_data(data_ref, titles_from_data=True)
        chart_cf.set_categories(cats_ref)
        configure_chart(
            chart_cf,
            title="Monthly Net Cash Flow",
            x_title="Month (YYYYMM)",
            y_title="Net Cash Flow ($)",
            show_legend=False,
        )
        ws3.add_chart(chart_cf, "F2")

    # Sheet 4: Department Payroll + Bar Chart
    ws4 = wb.create_sheet("4_Dept_Payroll")
    write_df_to_sheet(ws4, df_dept, start_row=1)
    if len(df_dept) > 0:
        chart_dept = BarChart()
        data_ref = Reference(ws4, min_col=4, max_col=4, min_row=1, max_row=len(df_dept) + 1)
        cats_ref = Reference(ws4, min_col=1, min_row=2, max_row=len(df_dept) + 1)
        chart_dept.add_data(data_ref, titles_from_data=True)
        chart_dept.set_categories(cats_ref)
        configure_chart(
            chart_dept,
            title=f"Employer Payroll Cost by Department ({month_label})",
            x_title="Department",
            y_title="Employer Cost ($)",
            show_legend=False,
        )
        ws4.add_chart(chart_dept, "F2")

    # Sheet 5: AI Anomalies + Horizontal Bar Chart
    ws5 = wb.create_sheet("5_AI_Anomalies")
    ws5["A1"] = "⚠️ AI-generated, for human review — Top 10 Anomalies Ranked by Money at Risk"
    ws5["A1"].font = Font(bold=True, color="B91C1C")
    write_df_to_sheet(ws5, df_anom, start_row=3)
    if len(df_anom) > 0:
        chart_anom = BarChart()
        chart_anom.type = "bar"
        data_ref = Reference(ws5, min_col=3, max_col=3, min_row=3, max_row=len(df_anom) + 3)
        cats_ref = Reference(ws5, min_col=1, min_row=4, max_row=len(df_anom) + 3)
        chart_anom.add_data(data_ref, titles_from_data=True)
        chart_anom.set_categories(cats_ref)
        # Note: For horizontal bar charts in openpyxl, x_axis is vertical (categories) and y_axis is horizontal (values)
        configure_chart(
            chart_anom,
            title="AI-generated, for human review: Money at Risk ($)",
            x_title="Anomaly Type",
            y_title="Money at Risk ($)",
            show_legend=False,
            width=24,
            height=14,
        )
        ws5.add_chart(chart_anom, "E3")

    Path(out_dir).mkdir(parents=True, exist_ok=True)
    output_file = Path(out_dir) / f"PulseIQ_Monthly_Report_{month_key}.xlsx"
    wb.save(output_file)
    print(f"✅ Report generated successfully: {output_file}")
    print(f"   Date Range: {start_date} to {end_date} | Data Cut-off: {data_cutoff}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate PulseIQ Monthly Management Report Pack.")
    parser.add_argument(
        "--month",
        required=True,
        help="Target month in YYYYMM format (e.g., 202603 or 202609)"
    )
    args = parser.parse_args()
    build_report(args.month)