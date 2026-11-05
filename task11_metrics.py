import duckdb
import pandas as pd

def build_pl_metrics():
    con = duckdb.connect("pulseiq.duckdb")
    
    print("="*60)
    print(" BUILDING P&L METRICS AND VERIFYING TOTALS ")
    print("="*60)

    # 1. P&L by Month (Updated to match 'INCOME' and 'N')
    con.execute("""
        CREATE OR REPLACE VIEW metrics.vw_pl_monthly AS
        SELECT 
            SUBSTRING(CAST(f.date_key AS VARCHAR), 1, 6) AS month_key,
            SUM(CASE WHEN a.account_type = 'INCOME' THEN (COALESCE(f.credit, 0) - COALESCE(f.debit, 0)) ELSE 0 END) AS total_revenue,
            SUM(CASE WHEN a.account_type = 'EXPENSE' THEN (COALESCE(f.debit, 0) - COALESCE(f.credit, 0)) ELSE 0 END) AS total_expense,
            SUM(CASE WHEN a.account_type = 'INCOME' THEN (COALESCE(f.credit, 0) - COALESCE(f.debit, 0)) ELSE 0 END) - 
            SUM(CASE WHEN a.account_type = 'EXPENSE' THEN (COALESCE(f.debit, 0) - COALESCE(f.credit, 0)) ELSE 0 END) AS margin
        FROM raw.fact_ledger f
        JOIN raw.dim_account a ON f.account_code = a.account_code
        WHERE a.is_group = 'N'
        GROUP BY 1;
    """)

    # 2. Expense by Category
    con.execute("""
        CREATE OR REPLACE VIEW metrics.vw_expense_by_category AS
        SELECT 
            SUBSTRING(CAST(e.expense_date_key AS VARCHAR), 1, 6) AS month_key,
            a.account_name AS category,
            SUM(COALESCE(e.amount_excl_gst, 0)) AS total_spend
        FROM raw.fact_expense e
        JOIN raw.dim_account a ON e.category_account = a.account_code
        GROUP BY 1, 2;
    """)

    # 3. Top 10 Vendors
    con.execute("""
        CREATE OR REPLACE VIEW metrics.vw_top_vendors AS
        SELECT 
            v.vendor_name,
            SUM(COALESCE(e.amount_excl_gst, 0)) AS total_spend
        FROM raw.fact_expense e
        JOIN raw.dim_vendor v ON e.vendor_id = v.vendor_id
        GROUP BY 1
        ORDER BY 2 DESC
        LIMIT 10;
    """)
    
    print("✅ P&L, Category, and Vendor metric views created successfully.")
    
    # 4. Tie-out Verification for Report
    print("\n" + "="*60)
    print(" TIE-OUT VERIFICATION ")
    print("="*60)
    
    totals = con.execute("""
        SELECT 
            SUM(total_revenue) AS grand_total_revenue,
            SUM(total_expense) AS grand_total_expense,
            SUM(margin) AS grand_total_margin
        FROM metrics.vw_pl_monthly
    """).df()
    
    print(totals.to_string(index=False))

    con.close()

if __name__ == "__main__":
    build_pl_metrics()