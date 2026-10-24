import duckdb
import pandas as pd

# Connect to your database
con = duckdb.connect("pulseiq.duckdb")

# Fetch and print the 14 rules
df = con.execute("SELECT * FROM raw.dq_checks_catalog").df()

# Print all columns nicely
pd.set_option('display.max_columns', None)
pd.set_option('display.width', 1000)
pd.set_option('display.max_colwidth', None)
print(df)

con.close()