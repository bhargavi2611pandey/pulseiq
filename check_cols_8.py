import duckdb

con = duckdb.connect("pulseiq.duckdb")

tables = [
    "raw.fact_task",
    "raw.dim_team",
    "raw.dim_sprint"
]

for t in tables:
    try:
        cols = con.execute(f"PRAGMA table_info('{t}')").df()['name'].tolist()
        print(f"{t}:\n{cols}\n")
    except Exception as e:
        print(f"Error reading {t}: {e}")