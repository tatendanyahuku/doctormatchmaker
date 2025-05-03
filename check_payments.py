import sqlite3

def check_payments():
    db_path = 'instance/medconsult.db'
    query = "SELECT consultation_id, amount, status FROM payments WHERE status='completed';"

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(query)
        results = cursor.fetchall()
        conn.close()

        if results:
            print("Completed Payments:")
            for row in results:
                print(f"Consultation ID: {row[0]}, Amount: ${row[1]}, Status: {row[2]}")
        else:
            print("No completed payments found.")
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_payments()