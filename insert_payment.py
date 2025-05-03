import sqlite3

def insert_payment():
    db_path = 'instance/medconsult.db'
    query = "INSERT INTO payments (consultation_id, amount, status, timestamp) VALUES (?, ?, ?, ?);"

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Insert a new payment record for consultation ID 7 with $90
        consultation_id = 7
        amount = 90.0
        status = 'completed'
        timestamp = '2025-04-18 12:00:00'  # Current date and time

        cursor.execute(query, (consultation_id, amount, status, timestamp))
        conn.commit()
        conn.close()

        print(f"Payment of ${amount} for consultation ID {consultation_id} inserted successfully.")
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    insert_payment()