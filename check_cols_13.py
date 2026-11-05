import duckdb
import os

print("="*50)
print(" CHECKING COLUMNS ")
print("="*50)

con = duckdb.connect("pulseiq.duckdb")
tables = ['raw.fact_payroll', 'raw.fact_attendance_monthly', 'raw.dim_employee']

for table in tables:
    try:
        print(f"{table} columns:")
        print(con.execute(f"PRAGMA table_info('{table}')").df()['name'].tolist())
        print()
    except Exception as e:
        print(f"Error reading {table}: {e}")

print("="*50)
print(" SEARCHING FOR UNLOCK PQ-13 FILE ")
print("="*50)

# Check the Vault folder
vault_dir = '04_Validation_Vault'
if os.path.exists(vault_dir):
    print(f"Files in {vault_dir}:")
    print(os.listdir(vault_dir))
else:
    print(f"Directory '{vault_dir}' not found. Checking current directory for unlock files:")
    print([f for f in os.listdir('.') if '13' in f or 'unlock' in f.lower()])

con.close()