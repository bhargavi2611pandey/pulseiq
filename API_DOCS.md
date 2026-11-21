# PulseIQ Metrics API & Data Lineage

Read-only REST API built with **FastAPI** and **DuckDB** (`pulseiq_prod.duckdb`) exposing 5 governed company KPIs with business definitions, formulas, lineage, and freshness metadata.

---

## Data Freshness Statement
* **Data Cut-off:** Current through `2026-09-30` (dynamically read from `metrics.data_metadata`).
* **Refresh Cadence:** Automated daily refresh at **06:00 UTC** via GitHub Actions (`.github/workflows/refresh_prod_data.yml`).
* **Runtime Metadata:** Every API response includes a `freshness` object with `data_cutoff`, `last_refreshed_utc`, `refresh_schedule`, and a plain-English `freshness_statement`.

---

## End-to-End Data Lineage (5 Core Metrics)

```mermaid
flowchart LR
    subgraph RAW["1. Raw Tables"]
        R1["raw.dim_employee"]
        R2["raw.fact_payroll"]
        R3["raw.fact_attendance_monthly"]
        R4["raw.fact_ledger / raw.fact_invoices"]
    end

    subgraph ETL["2. ETL / Clean Layer"]
        E1["clean.dim_employee (SCD2 & status normalization)"]
        E2["clean.fact_payroll (employer_cost validation)"]
        E3["clean.fact_attendance_monthly (half-day weighting)"]
        E4["clean.fact_ledger (revenue vs expense mapping)"]
    end

    subgraph WH["3. Warehouse Tables"]
        W1["warehouse.dim_employee + dim_department"]
        W2["warehouse.fact_payroll + dim_department"]
        W3["warehouse.fact_attendance_monthly + dim_department"]
        W4["warehouse.fact_ledger"]
    end

    subgraph MET["4. Governed Metric Views (pulseiq_prod.duckdb)"]
        M1["metrics.vw_headcount (M01)"]
        M2["metrics.vw_attrition_monthly (M04)"]
        M3["metrics.vw_payroll_cost (M09)"]
        M4["metrics.vw_attendance (M13)"]
        M5["metrics.vw_pl_monthly (FIN01)"]
    end

    subgraph CONS["5. Consumers (Dashboard & REST API)"]
        D1["Streamlit: Executive Overview & KPI Explorer"]
        D2["Streamlit: People Overview & KPI Explorer"]
        D3["Streamlit: Payroll Cost & KPI Explorer"]
        D4["Streamlit: Attendance & Leave & KPI Explorer"]
        D5["Streamlit: Profit & Loss & Executive Scorecard"]
        API["FastAPI: /metrics/* & /lineage"]
    end

    R1 --> E1 --> W1
    W1 --> M1 --> D1
    W1 --> M2 --> D2
    R2 --> E2 --> W2 --> M3 --> D3
    R3 --> E3 --> W3 --> M4 --> D4
    R4 --> E4 --> W4 --> M5 --> D5

    M1 --> API
    M2 --> API
    M3 --> API
    M4 --> API
    M5 --> API