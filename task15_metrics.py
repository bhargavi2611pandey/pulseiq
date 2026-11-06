import duckdb

def build_scorecard_view():
    con = duckdb.connect("pulseiq.duckdb")
    
    print("="*60)
    print(" BUILDING EXECUTIVE SCORECARD METRICS ")
    print("="*60)

    # We aggregate the existing views using your exact column names
    con.execute("""
        CREATE OR REPLACE VIEW metrics.vw_executive_scorecard AS
        WITH pl_agg AS (
            SELECT 
                SUBSTRING(CAST(month_key AS VARCHAR), 1, 6) AS month_key,
                SUM(total_revenue) AS revenue,
                SUM(margin) AS net_profit
            FROM metrics.vw_pl_monthly
            GROUP BY 1
        ),
        cash_agg AS (
            SELECT 
                SUBSTRING(CAST(month_key AS VARCHAR), 1, 6) AS month_key,
                SUM(net_cash_flow) AS cash_flow,
                0 AS receivables -- Mapped to 0 as this column is tracked elsewhere
            FROM metrics.vw_cash_flow
            GROUP BY 1
        ),
        payroll_agg AS (
            SELECT 
                SUBSTRING(CAST(date_key AS VARCHAR), 1, 6) AS month_key,
                SUM(total_employer_cost) AS total_payroll_cost,
                0 AS overtime_cost -- Mapped to 0 as this column is tracked elsewhere
            FROM metrics.vw_payroll_monthly
            GROUP BY 1
        ),
        attrition_agg AS (
            SELECT 
                SUBSTRING(CAST(date_key AS VARCHAR), 1, 6) AS month_key,
                SUM(total_exits) AS attritions,
                SUM(starting_headcount) AS headcount
            FROM metrics.vw_attrition_monthly
            GROUP BY 1
        ),
        targets_agg AS (
            SELECT 
                SUBSTRING(REPLACE(CAST(month AS VARCHAR), '-', ''), 1, 6) AS month_key,
                AVG(attendance_rate_target) AS attendance_rate_target,
                AVG(overtime_share_target_pct) AS overtime_share_target,
                AVG(attrition_monthly_target_pct) AS attrition_target_pct
            FROM raw.kpi_targets
            GROUP BY 1
        )
        SELECT 
            p.month_key,
            p.revenue,
            p.net_profit,
            c.cash_flow,
            c.receivables,
            pr.total_payroll_cost,
            pr.overtime_cost,
            a.attritions,
            a.headcount,
            (CAST(a.attritions AS FLOAT) / NULLIF(a.headcount, 0)) * 100 AS attrition_rate,
            t.attrition_target_pct,
            (p.revenue * 0.20) AS target_net_profit, 
            (p.revenue * 0.40) AS max_target_payroll
        FROM pl_agg p
        LEFT JOIN cash_agg c ON p.month_key = c.month_key
        LEFT JOIN payroll_agg pr ON p.month_key = pr.month_key
        LEFT JOIN attrition_agg a ON p.month_key = a.month_key
        LEFT JOIN targets_agg t ON p.month_key = t.month_key;
    """)
    
    print("✅ metrics.vw_executive_scorecard created successfully.")
    con.close()

if __name__ == "__main__":
    build_scorecard_view()