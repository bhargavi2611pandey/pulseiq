import os
import duckdb
import streamlit as st


def get_db_path() -> str:
    """Read DB_PATH from Streamlit secrets (cloud) or env/default (local)."""
    try:
        if "DB_PATH" in st.secrets:
            return st.secrets["DB_PATH"]
    except Exception:
        pass
    return os.getenv("DB_PATH", "pulseiq_prod.duckdb")


def get_connection():
    """Return a DuckDB connection using the configured database path."""
    return duckdb.connect(get_db_path())


def get_data_metadata():
    """Fetch (data_cutoff, last_refreshed_utc) for display in the UI."""
    try:
        con = get_connection()
        row = con.execute(
            "SELECT data_cutoff, last_refreshed_utc FROM metrics.data_metadata LIMIT 1"
        ).fetchone()
        con.close()
        if row:
            return row[0], row[1]
    except Exception:
        pass
    return "2026-09-30", "N/A"