import duckdb
import pandas as pd

def build_receivables_metrics():
    con = duckdb.connect("pulseiq.duckdb")
    
    print("="*60)
    print(" BUILDING RECEIVABLES & CASH FLOW METRICS ")
    print("="*60)

    # 1. Receivables Ageing Buckets (Only Open Invoices)
    con.execute("""
        CREATE OR REPLACE VIEW metrics.vw_receivables_ageing AS
        SELECT 
            CASE 
                WHEN days_past_due_at_cutoff <= 0 THEN 'Current (Not Due)'
                WHEN days_past_due_at_cutoff <= 30 THEN '0-30 Days'
                WHEN days_past_due_at_cutoff <= 60 THEN '31-60 Days'
                WHEN days_past_due_at_cutoff <= 90 THEN '61-90 Days'
                ELSE '90+ Days' 
            END AS ageing_bucket,
            SUM(balance_due) AS total_balance
        FROM raw.fact_invoice
        WHERE status IN ('SENT', 'OVERDUE', 'PARTIALLY_PAID')
        GROUP BY 1;
    """)
    
    # 2. Average Days to Pay by Client
    con.execute("""
        CREATE OR REPLACE VIEW metrics.vw_client_days_to_pay AS
        SELECT 
            c.client_name,
            AVG(i.days_to_pay) AS avg_days_to_pay,
            SUM(i.total_amount) AS total_lifetime_value
        FROM raw.fact_invoice i
        JOIN raw.dim_client c ON i.client_id = c.client_id
        WHERE i.days_to_pay IS NOT NULL
        GROUP BY 1
        HAVING COUNT(i.invoice_id) >= 3 -- Only clients with a history
        ORDER BY 2 DESC;
    """)

    # 3. Cash Flow (Cash In vs Cash Out)
    con.execute("""
        CREATE OR REPLACE VIEW metrics.vw_cash_flow AS
        WITH cash_in AS (
            SELECT 
                SUBSTRING(CAST(payment_date_key AS VARCHAR), 1, 6) AS month_key,
                SUM(amount) AS cash_in
            FROM raw.fact_invoice_payment
            GROUP BY 1
        ),
        cash_out AS (
            SELECT 
                SUBSTRING(CAST(expense_date_key AS VARCHAR), 1, 6) AS month_key,
                SUM(total_amount) AS cash_out
            FROM raw.fact_expense
            WHERE status = 'PAID'
            GROUP BY 1
        )
        SELECT 
            COALESCE(i.month_key, o.month_key) AS month_key,
            COALESCE(i.cash_in, 0) AS cash_in,
            COALESCE(o.cash_out, 0) AS cash_out,
            COALESCE(i.cash_in, 0) - COALESCE(o.cash_out, 0) AS net_cash_flow
        FROM cash_in i
        FULL OUTER JOIN cash_out o ON i.month_key = o.month_key;
    """)

    # 4. Top Overdue Clients
    con.execute("""
        CREATE OR REPLACE VIEW metrics.vw_top_overdue_clients AS
        SELECT 
            c.client_name,
            SUM(i.balance_due) AS total_overdue
        FROM raw.fact_invoice i
        JOIN raw.dim_client c ON i.client_id = c.client_id
        WHERE i.status = 'OVERDUE'
        GROUP BY 1
        ORDER BY 2 DESC
        LIMIT 10;
    """)
    
    print("✅ Views created successfully.\n")
    
    # --- VERIFICATION STEP FOR YOUR REPORT ---
    print("="*60)
    print(" TIE-OUT VERIFICATION  ")
    print("="*60)
    
    buckets_df = con.execute("SELECT * FROM metrics.vw_receivables_ageing").df()
    print("1. Ageing Buckets Breakdown:")
    print(buckets_df.to_string(index=False))
    
    bucket_sum = con.execute("SELECT SUM(total_balance) FROM metrics.vw_receivables_ageing").fetchone()[0]
    total_open = con.execute("SELECT SUM(balance_due) FROM raw.fact_invoice WHERE status IN ('SENT', 'OVERDUE', 'PARTIALLY_PAID')").fetchone()[0]
    
    print(f"\n2. Total in Buckets:   ${bucket_sum:,.2f}")
    print(f"3. Raw Open Invoices:  ${total_open:,.2f}")
    
    if round(bucket_sum, 2) == round(total_open, 2):
        print("✅ SUCCESS: The buckets perfectly add up to the total open receivables!")
    else:
        print("❌ ERROR: Mismatch detected.")
        
    con.close()

if __name__ == "__main__":
    build_receivables_metrics()