# Release Notes — PulseIQ Analytics Platform

All notable changes to PulseIQ are documented in this file, following [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and Semantic Versioning.

## [1.0.0] — 2026-11-21

### What Is Included
- **Production Warehouse (`pulseiq_prod.duckdb`):** Unified DuckDB analytical database with 30 governed metric views across People, Payroll, Attendance, Finance (P&L, Cash Flow, Receivables), and Team Delivery.
- **Live Streamlit Dashboard (`https://pulseiq-dashboard00.streamlit.app/`):** 14 interactive pages covering Executive Overview, Workforce, Attendance & Leave, Attrition, Team Productivity, Payroll Cost, Budget & KPIs, Profit & Loss, Cash & Receivables, Cross-Department Analysis, AI Signals, Executive Scorecard, RBAC KPI Explorer, Data Lineage & API, and the **Department 360° Drill-Down** (Final Challenge).
- **Live FastAPI Metrics Service (`https://pulseiq-metrics-api-9dgr.onrender.com`):** Read-only REST API deployed on Render from the same GitHub repository, exposing 5 governed KPI endpoints (`/metrics/headcount`, `/metrics/attrition-rate`, `/metrics/payroll-cost`, `/metrics/attendance-rate`, `/metrics/net-profit`), `/lineage`, and interactive Swagger docs (`/docs`).
- **Governance & Privacy Controls:** Role-Based Access Control (`ADMIN`, `HR`, `MANAGER`, `EXECUTIVE`), k-anonymity suppression (`MIN_GROUP_SIZE = 5`), anti-differencing guards, and a 28-metric catalog (`metrics.metric_catalog`).
- **Automated Refresh & Reconciliation:** Daily GitHub Actions refresh schedule (06:00 UTC) with freshness metadata (`metrics.data_metadata`) and live reconciliation checks (`reconcile_live_data.py` — 0 negative headcount/payroll rows, 0 out-of-range attendance rates, 0 P&L margin mismatches).
- **Executive Board Pack:** 9-slide board presentation (`PulseIQ_Board_Pack_v1.0.0.pptx`) backed by live production figures and programmatic chart generation (`build_board_deck.py`).

### What Is Not Included
- **Real-Time / Streaming Ingestion:** Data refreshes on a daily batch cadence rather than live webhook streaming from HRIS/ERP systems.
- **SSO / Enterprise Identity Provider:** Role switching in the dashboard is demonstration-grade RBAC rather than OAuth2/SAML authentication.
- **Automated Collections / HRIS Write-Back:** PulseIQ is strictly read-only; it does not send automated dunning emails or update payroll/HR records.
- **SLA-Linked Team Incentives:** Intentionally excluded from recommendations until upstream due-date logging is fixed.

### Known Limits
- **Unpopulated `on_time_tasks` Metric:** In `metrics.vw_team_sprint_metrics`, `on_time_tasks` currently evaluates to `0` across sprints because upstream due-date/SLA timestamps are incomplete.
- **Free-Tier Cold Starts:** Both Streamlit Community Cloud and Render free tiers sleep after inactivity; first-visit wake-up takes ~30–60 seconds (anyone with the link can wake them).
- **Data Cutoff:** Current production snapshot covers data through `2026-09-30`.
- **Small-Group Suppression:** Cohorts with fewer than 5 employees are intentionally masked in KPI Explorer and Department 360° Drill-Down to prevent individual re-identification.
