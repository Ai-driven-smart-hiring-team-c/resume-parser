"""
list_accounts.py
Quick one-off: prints every recruiter/admin account in the database so you
can find which email you signed up with.

Usage (inside milestone2/milestone2):
    python list_accounts.py
"""

from db import init_db, get_connection

if __name__ == "__main__":
    init_db()
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, name, email, role, created_at FROM recruiters ORDER BY created_at")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    if not rows:
        print("No accounts found. Sign up through the app first.")
    else:
        print(f"Found {len(rows)} account(s):\n")
        for row in rows:
            print(f"  name: {row['name']}  |  email: {row['email']}  |  role: {row['role']}  |  created: {row['created_at']}")