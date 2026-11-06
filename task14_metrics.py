import duckdb
import pandas as pd

def build_ai_metrics():
    con = duckdb.connect("pulseiq.duckdb")
    
    print("="*60)
    print(" BUILDING AI SIGNALS METRICS ")
    print("="*60)

    # 1. Anomalies by type and money at risk
    con.execute("""
        CREATE OR REPLACE VIEW metrics.vw_anomalies_summary AS
        SELECT 
            reason_text AS anomaly_type,
            COUNT(record_id) AS total_anomalies,
            SUM(COALESCE(money_at_risk, 0)) AS total_money_at_risk
        FROM raw.fact_anomaly
        GROUP BY 1
        ORDER BY 3 DESC;
    """)
    
    # 2. Forecast vs Actuals (Joining Forecasts to Actual Payroll Cost)
    con.execute("""
        CREATE OR REPLACE VIEW metrics.vw_forecast_accuracy AS
        WITH actual_payroll AS (
            SELECT 
                department_id,
                SUBSTRING(CAST(date_key AS VARCHAR), 1, 6) AS month_key,
                SUM(employer_cost) AS actual_cost
            FROM raw.fact_payroll
            GROUP BY 1, 2
        )
        SELECT 
            f.metric,
            COALESCE(d.department_name, CAST(f.department_id AS VARCHAR)) AS department_name,
            SUBSTRING(CAST(f.forecast_month_key AS VARCHAR), 1, 6) AS month_key,
            f.forecast_value,
            f.lower_80,
            f.upper_80,
            a.actual_cost AS actual_value
        FROM raw.fact_forecast f
        LEFT JOIN actual_payroll a 
            ON f.department_id = a.department_id 
            AND SUBSTRING(CAST(f.forecast_month_key AS VARCHAR), 1, 6) = a.month_key
        LEFT JOIN raw.dim_department d 
            ON f.department_id = d.department_id;
    """)
    
    print("✅ AI metric views created successfully.")
    
    # Output summary for report
    anomalies = con.execute("SELECT * FROM metrics.vw_anomalies_summary LIMIT 5").df()
    print("\n--- TOP ANOMALIES BY MONEY AT RISK ---")
    print(anomalies.to_string(index=False))
    
    con.close()

if __name__ == "__main__":
    build_ai_metrics()