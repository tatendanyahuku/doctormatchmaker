import sqlite3

# Connect to the SQLite database
conn = sqlite3.connect('instance/medconsult.db')
cursor = conn.cursor()

# Add the 'recommended_fee' column to the 'specialty_fee_ranges' table
try:
    cursor.execute("""
        ALTER TABLE specialty_fee_ranges
        ADD COLUMN recommended_fee REAL NOT NULL DEFAULT 0.0;
    """)
    print("Column 'recommended_fee' added successfully.")
except sqlite3.OperationalError as e:
    print(f"Error: {e}")

# Add the 'wallet_balance' column to the 'doctors' table
try:
    cursor.execute("""
        ALTER TABLE doctors
        ADD COLUMN wallet_balance REAL NOT NULL DEFAULT 0.0;
    """)
    print("Column 'wallet_balance' added successfully.")
except sqlite3.OperationalError as e:
    print(f"Error: {e}")

# Commit changes and close the connection
conn.commit()
conn.close()